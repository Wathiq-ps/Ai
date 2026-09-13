"""Sprint 6 (1D) — analyze_contract: retrieve -> find -> score.
See AI_IMPLEMENTATION_PLAN.md Phase 1D and openapi.yaml's AnalyzeContractResult.

Same shape as app/generate_contract.py on purpose (one LLM call + bounded
JSON-repair loop, citations hydrated from what we actually retrieved), so the
two agents stay readable side by side. The model can only cite by short label
`[C3]`; the real source_id/chunk_id come from our own retrieval, so a finding
can never cite a law we never read (BR-25).

The risk score is NOT asked of the model — it is a deterministic
severity-weighted sum over the findings (RISK_RUBRIC_VERSION), so the same
findings always produce the same number (open decision #5).
"""

import asyncio
import json
import re
import uuid
from collections import Counter
from dataclasses import dataclass

from app.generate_contract import (
    CLAUSE_KINDS,
    CLAUSE_TOPICS,
    CONTRACT_LAW_TYPES,
    MAX_ATTEMPTS,
    Citation,
)
from app.knowledge import SearchResult, search_many
from app.providers.base import EmbeddingProvider, LLMProvider

FINDING_KINDS = ["missing_clause", "legal_conflict", "ambiguity", "suggestion", "risk"]

# Which findings get reported was the least stable thing about this agent:
# over four runs of one contract, mean pairwise Jaccard on the finding set was
# 0.36 and only 2 of 11 distinct findings appeared every time, with the risk
# score swinging 43-70. Sampling determinism is not available to us (a hosted
# reasoning model ignores temperature/seed for this purpose), so the fix is to
# stop asking an open question. The model must now return a verdict for every
# clause kind, so `missing_clause` findings are an enumeration over a fixed
# checklist rather than whatever it felt like mentioning — and their severity
# is mapped here, not judged.
COVERAGE_STATUSES = ["present", "incomplete", "absent"]
COVERAGE_SEVERITY = {"absent": "high", "incomplete": "medium"}
SEVERITIES = ["low", "medium", "high", "critical"]

# Deterministic rubric: severity weights summed and capped at 100. Chosen so a
# single critical finding lands in the top band, and it takes a pile of low
# findings to get there. Bump the version string with any weight change —
# stored scores from an older rubric are not comparable.
RISK_RUBRIC_VERSION = "risk-v1"
SEVERITY_WEIGHTS = {"low": 3, "medium": 8, "high": 18, "critical": 35}


class AnalysisFailed(Exception):
    """No verified law found, or the LLM never produced valid structured
    output after MAX_ATTEMPTS — fail closed (BR-28), no partial analysis."""


@dataclass
class Finding:
    kind: str
    severity: str
    title_ar: str
    title_en: str
    description: str
    suggested_text: str | None
    citations: list[Citation]
    confidence: float


@dataclass
class ClauseCoverage:
    clause_kind: str
    status: str
    note: str
    citations: list[Citation]


@dataclass
class AnalyzeContractResult:
    coverage: list[ClauseCoverage]
    findings: list[Finding]
    risk_score: int
    summary_ar: str
    summary_en: str
    confidence: float
    kb_version_id: uuid.UUID


async def analyze_contract(
    pool,
    llm: LLMProvider,
    embedder: EmbeddingProvider,
    *,
    jurisdiction_id: uuid.UUID,
    content: str,
    contract_type: str | None = None,
    k_per_topic: int = 5,
    samples: int = 1,
) -> AnalyzeContractResult:
    """`samples` > 1 runs that many independent analyses over the *same*
    retrieved excerpts and keeps only what they agree on — self-consistency.
    One sample's findings are not reproducible (measured: mean pairwise
    Jaccard 0.48 over four runs, risk_score 35-67 on one contract), and a
    lawyer re-running a review should not get a different report.

    Measured over four runs of one contract: k=3 lifts mean pairwise Jaccard
    0.48 -> 0.58 and the findings present in every run from 2 to 4, and
    narrows risk_score from 35-67 to 48-67. It helps; it does not make the
    report reproducible.

    Costs `samples` times the tokens, and — despite asyncio.gather — roughly
    twice the wall clock, not the same: the endpoint serialises concurrent
    requests on one key, so k=3 measured 115-134s against a 60s budget
    (NFR-1.1). That is why the default is 1. Do not raise it without either a
    higher budget or a provider that really runs these in parallel.
    """
    context = await _retrieve_context(
        pool, embedder, jurisdiction_id=jurisdiction_id, contract_type=contract_type,
        content=content, k_per_topic=k_per_topic,
    )
    if not context:
        raise AnalysisFailed("no verified law found for this jurisdiction")

    # search() only serves the one `active` kb_version per jurisdiction.
    kb_version_id = next(iter(context.values())).kb_version_id

    system, user = _build_prompt(content, contract_type, context)

    # Every sample sees the same excerpts and the same labels, so a `C3` in one
    # sample means what it means in every other — that is what makes the votes
    # below comparable.
    results = await asyncio.gather(
        *(_one_analysis(llm, system, user, context) for _ in range(samples)),
        return_exceptions=True,
    )
    usable = [r for r in results if not isinstance(r, BaseException)]
    if not usable:
        raise AnalysisFailed(f"no sample produced valid structured output: {results[0]}")

    coverage, judgements, summary_ar, summary_en = _vote(usable)
    findings = [_coverage_finding(c) for c in coverage if c.status != "present"] + judgements
    return AnalyzeContractResult(
        coverage=coverage,
        findings=findings,
        risk_score=risk_score(findings),
        summary_ar=summary_ar,
        summary_en=summary_en,
        confidence=_overall_confidence(findings),
        kb_version_id=kb_version_id,
    )


async def _one_analysis(llm, system: str, user: str, context: dict[str, SearchResult]):
    """One sample, with its own bounded JSON-repair loop."""
    last_error = ""
    for _ in range(MAX_ATTEMPTS):
        prompt = user if not last_error else f"{user}\n\nYour last reply was invalid: {last_error}. Reply with corrected JSON only."
        raw = await llm.chat(system, prompt, json_mode=True, max_tokens=16384)
        try:
            return _parse_and_ground(raw, context)
        except _InvalidAnalysis as exc:
            last_error = str(exc)
    raise AnalysisFailed(f"LLM never produced valid structured output: {last_error}")


# Worst-first, so a tied vote on a clause fails safe rather than silently
# clearing it: a legal review should over-report, not under-report.
_STATUS_RANK = {"absent": 0, "incomplete": 1, "present": 2}


def _finding_key(f: Finding) -> tuple:
    """What a finding is *about* — findings carry no id, and two samples will
    word the same problem differently, so identity is its kind plus the
    articles it rests on."""
    return (f.kind, tuple(sorted(c.article_ref or "?" for c in f.citations)))


def _vote(samples: list[tuple]) -> tuple[list[ClauseCoverage], list[Finding], str, str]:
    """Majority across samples. Coverage is voted per clause kind (the
    checklist guarantees every sample has an opinion on every one). Judgement
    findings are kept when at least half the samples raise them, which is what
    drops the one-off flags that made the report unstable."""
    n = len(samples)
    threshold = (n + 1) // 2

    coverage = []
    for i, kind in enumerate(CLAUSE_KINDS):
        verdicts = [s[0][i] for s in samples]
        counts = Counter(v.status for v in verdicts)
        top = max(counts.values())
        status = min((s for s, c in counts.items() if c == top), key=_STATUS_RANK.__getitem__)
        # Keep a real note and real citations: take them from a sample that
        # actually voted this way, not a synthesised summary of the vote.
        coverage.append(next(v for v in verdicts if v.status == status))
        assert coverage[-1].clause_kind == kind

    seen: Counter = Counter()
    first: dict[tuple, Finding] = {}
    for _cov, findings, _, _ in samples:
        for key in {_finding_key(f) for f in findings}:
            seen[key] += 1
        for f in findings:
            first.setdefault(_finding_key(f), f)

    judgements = [f for key, f in first.items() if seen[key] >= threshold]
    return coverage, judgements, samples[0][2], samples[0][3]


class _InvalidAnalysis(Exception):
    pass


# A bare C-label in prose (C1, C12) — but not a word that merely starts with C,
# and not "C1" inside a longer token.
_LABEL_IN_PROSE = re.compile(r"(?<![A-Za-z0-9])C\d+(?![A-Za-z0-9])")


def risk_score(findings: list[Finding]) -> int:
    """0-100, severity-weighted, capped. Deterministic — no model involved."""
    return min(100, sum(SEVERITY_WEIGHTS[f.severity] for f in findings))


def _overall_confidence(findings: list[Finding]) -> float:
    """Mean of per-finding confidence; a clean contract (no findings) is a
    confident result, not an unknown one."""
    if not findings:
        return 1.0
    return round(sum(f.confidence for f in findings) / len(findings), 3)


async def _retrieve_context(
    pool, embedder: EmbeddingProvider, *, jurisdiction_id: uuid.UUID, contract_type: str | None,
    content: str, k_per_topic: int,
) -> dict[str, SearchResult]:
    """One retrieval per clause topic, seeded with the contract's own text so
    the excerpts follow what this contract actually says, deduplicated by
    chunk_id and labeled `C1..Cn`."""
    # ponytail: first 2000 chars as the query seed — embedders truncate long
    # inputs anyway. Chunk the contract and retrieve per clause if recall on
    # long contracts turns out to be poor.
    seed = content[:2000]
    prefix = f"{contract_type} contract" if contract_type else "contract"
    law_types = CONTRACT_LAW_TYPES.get(contract_type, ["general"]) if contract_type else None
    queries = [f"{prefix}: {topic}. {seed}" for topic in CLAUSE_TOPICS.values()]
    context: dict[str, SearchResult] = {}
    for results in await search_many(
        pool, embedder, jurisdiction_id=jurisdiction_id, queries=queries,
        law_type=law_types, k=k_per_topic,
    ):
        for result in results:
            context.setdefault(str(result.chunk_id), result)

    return {f"C{i + 1}": result for i, result in enumerate(context.values())}


def _build_prompt(content: str, contract_type: str | None, context: dict[str, SearchResult]) -> tuple[str, str]:
    excerpts = "\n".join(f"[{label}] {r.content}" for label, r in context.items())
    system = (
        "You are a Palestinian-law contract reviewer. Judge the contract only against the law "
        "excerpts provided; do not invent legal rules. Reply with JSON only, no prose, no markdown "
        'fences, shaped exactly as: {"summary_ar": "...", "summary_en": "...", "coverage": '
        '{"parties": {"status": "...", "note": "...", "cites": ["C1"]}, ...}, "findings": '
        '[{"kind": "...", "severity": "...", "title_ar": "...", "title_en": "...", '
        '"description": "...", "suggested_text": "..." or null, "cites": ["C1"], "confidence": 0.8}]}. '
        f"`coverage` MUST contain an entry for every one of these {len(CLAUSE_KINDS)} clause kinds, "
        f"with no others and none left out: {', '.join(CLAUSE_KINDS)}. This is a checklist, not a "
        "list of problems — say something about each one even when it is fine. status is "
        f"{' | '.join(COVERAGE_STATUSES)}: `present` = the clause is there and usable; `incomplete` "
        "= the clause is there but unusable as written (an unfilled blank, a term left open); "
        "`absent` = there is no such clause. note is one Arabic sentence saying why, and is what the "
        "reader sees, so name articles by number. A missing or inadequate clause is reported HERE "
        f"and nowhere else — do NOT put missing_clause entries in `findings`.\n"
        f"`findings` carries only the judgement calls: {', '.join(k for k in FINDING_KINDS if k != 'missing_clause')}. "
        f"severity must be one of: {', '.join(SEVERITIES)}, judged against these anchors — the "
        "risk score is computed from them, so apply them literally rather than by feel:\n"
        "  critical — the contract or the term is void or unenforceable, or it strips a party of a "
        "protection the statute makes mandatory.\n"
        "  high — the term conflicts with the law and a court would likely strike or reverse it, or "
        "something required to enforce the contract at all is absent (parties, property, rent).\n"
        "  medium — a gap or ambiguity that will cause a dispute but is curable by filling it in "
        "(an unfilled date, a missing inventory, an unnamed court).\n"
        "  low — a customary protective term that is advisable but not legally required.\n"
        "Every finding must cite at least one label from the excerpts that grounds it — a finding "
        "you cannot ground in an excerpt must be left out. confidence is 0..1. "
        "The labels C1, C2 ... are internal plumbing: put them in `cites` and NEVER write them in a "
        "title, description or suggested_text. A lawyer reading the report has never seen them. "
        "Refer to law the way the excerpt itself does — by its article number, e.g. المادة (4). "
        "suggested_text is contract Arabic ready to paste into the contract, using bracketed blanks "
        "such as [تاريخ بدء الإجارة] for anything the parties must still supply — never dotted lines. "
        "Report contradictions with the excerpts (legal_conflict), vague or unenforceable "
        "wording (ambiguity), improvements (suggestion), and commercial/legal exposure (risk). "
        "summary_ar is Arabic, summary_en is English; both summarise the contract's state in a "
        "short paragraph. Return an empty findings array if the contract is sound."
    )
    user = (
        f"Contract type: {contract_type or 'unspecified'}\n\n"
        f"Contract under review:\n{content}\n\n"
        f"Law excerpts:\n{excerpts}"
    )
    return system, user


def _parse_and_ground(
    raw: str, context: dict[str, SearchResult]
) -> tuple[list[ClauseCoverage], list[Finding], str, str]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise _InvalidAnalysis(f"not valid JSON ({exc})") from exc

    summary_ar = data.get("summary_ar")
    summary_en = data.get("summary_en")
    for name, value in (("summary_ar", summary_ar), ("summary_en", summary_en)):
        if not isinstance(value, str) or not value.strip():
            raise _InvalidAnalysis(f"missing or empty {name!r}")

    coverage = _parse_coverage(data.get("coverage"), context)

    raw_findings = data.get("findings")
    if not isinstance(raw_findings, list):
        raise _InvalidAnalysis("missing 'findings' array")

    findings = [_ground_finding(entry, context) for entry in raw_findings]
    if any(f.kind == "missing_clause" for f in findings):
        raise _InvalidAnalysis("missing_clause belongs in 'coverage', not 'findings'")

    return coverage, findings, summary_ar.strip(), summary_en.strip()


def _parse_coverage(raw: object, context: dict[str, SearchResult]) -> list[ClauseCoverage]:
    """Every clause kind, every time — that fixed cardinality is the whole
    point, so a short checklist is a failure the repair loop must fix."""
    if not isinstance(raw, dict):
        raise _InvalidAnalysis("missing 'coverage' object")

    missing = [k for k in CLAUSE_KINDS if k not in raw]
    if missing:
        raise _InvalidAnalysis(f"coverage is missing clause kind(s): {missing}")
    unknown = [k for k in raw if k not in CLAUSE_KINDS]
    if unknown:
        raise _InvalidAnalysis(f"coverage has unknown clause kind(s): {sorted(unknown)}")

    coverage = []
    for kind in CLAUSE_KINDS:
        entry = raw[kind]
        if not isinstance(entry, dict):
            raise _InvalidAnalysis(f"coverage entry for {kind!r} is not an object")
        status = entry.get("status")
        if status not in COVERAGE_STATUSES:
            raise _InvalidAnalysis(f"unknown coverage status {status!r} for {kind!r}")
        note = entry.get("note")
        if not isinstance(note, str) or not note.strip():
            raise _InvalidAnalysis(f"empty coverage note for {kind!r}")
        if _LABEL_IN_PROSE.search(note):
            raise _InvalidAnalysis(
                f"coverage note for {kind!r} names an internal excerpt label; "
                "cite the article number instead"
            )
        cites = entry.get("cites") or []
        if not all(label in context for label in cites):
            raise _InvalidAnalysis(f"coverage entry for {kind!r} cites an unknown label")
        # BR-25 again: a non-`present` verdict becomes a finding, and a finding
        # with no grounding is not a finding. A clean clause needs no citation.
        if status != "present" and not cites:
            raise _InvalidAnalysis(f"coverage entry for {kind!r} is {status} but cites nothing")
        coverage.append(
            ClauseCoverage(
                clause_kind=kind,
                status=status,
                note=note.strip(),
                citations=[_citation(context[label]) for label in sorted(set(cites))],
            )
        )
    return coverage


def _citation(result: SearchResult) -> Citation:
    return Citation(
        source_id=result.source_id,
        article_ref=result.article,
        chunk_id=result.chunk_id,
        excerpt=result.content,
    )


def _coverage_finding(entry: ClauseCoverage) -> Finding:
    """A checklist verdict rendered as a finding. Severity comes from the
    status table, not from the model, so the same verdict always scores the
    same — which is what makes risk_score reproducible."""
    return Finding(
        kind="missing_clause",
        severity=COVERAGE_SEVERITY[entry.status],
        title_ar=f"{'بند غائب' if entry.status == 'absent' else 'بند غير مكتمل'}: {entry.clause_kind}",
        title_en=f"{'Absent' if entry.status == 'absent' else 'Incomplete'} clause: {entry.clause_kind}",
        description=entry.note,
        suggested_text=None,
        citations=entry.citations,
        confidence=1.0,
    )


def _ground_finding(entry: object, context: dict[str, SearchResult]) -> Finding:
    if not isinstance(entry, dict):
        raise _InvalidAnalysis("finding is not an object")

    kind = entry.get("kind")
    severity = entry.get("severity")
    if kind not in FINDING_KINDS:
        raise _InvalidAnalysis(f"unknown finding kind {kind!r}")
    if severity not in SEVERITIES:
        raise _InvalidAnalysis(f"unknown severity {severity!r} on a {kind} finding")

    for field in ("title_ar", "title_en", "description"):
        value = entry.get(field)
        if not isinstance(value, str) or not value.strip():
            raise _InvalidAnalysis(f"empty {field!r} on a {kind} finding")

    # `C3` is an internal retrieval label, meaningless to the lawyer reading
    # the report — and it was leaking into descriptions ("وفق C1(هـ)"). Asking
    # the model not to do it is not enough on its own; reject and let the
    # repair loop rewrite, the same way an ungrounded citation is rejected.
    for field in ("title_ar", "title_en", "description", "suggested_text"):
        value = entry.get(field)
        if isinstance(value, str) and _LABEL_IN_PROSE.search(value):
            raise _InvalidAnalysis(
                f"{field!r} on a {kind} finding names an internal excerpt label; "
                "cite the article number instead"
            )

    cites = entry.get("cites") or []
    # BR-25: a finding with no grounding is not a finding.
    if not cites or not all(label in context for label in cites):
        raise _InvalidAnalysis(f"{kind} finding cites an unknown or missing label")

    confidence = entry.get("confidence", 0.5)
    if not isinstance(confidence, (int, float)) or not 0.0 <= confidence <= 1.0:
        raise _InvalidAnalysis(f"confidence {confidence!r} out of range on a {kind} finding")

    suggested = entry.get("suggested_text")
    return Finding(
        kind=kind,
        severity=severity,
        title_ar=entry["title_ar"].strip(),
        title_en=entry["title_en"].strip(),
        description=entry["description"].strip(),
        suggested_text=suggested.strip() if isinstance(suggested, str) and suggested.strip() else None,
        citations=[_citation(context[label]) for label in sorted(set(cites))],
        confidence=float(confidence),
    )
