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
import logging
import re
import uuid
from collections import Counter
from dataclasses import dataclass

from app.errors import JobFailed
from app.generate_contract import (
    ALL_CLAUSE_KINDS,
    CLAUSE_KINDS,
    CONTRACT_LAW_TYPES,
    MAX_ATTEMPTS,
    RENT_EXTRA_KINDS,
    Citation,
    citation_from,
    clause_kinds,
    clause_topics,
)
from app.knowledge import SearchResult, search_many
from app.providers.base import EmbeddingProvider, LLMProvider
from app.usage import job_tag, stage
from app.wire import ErrorCode

logger = logging.getLogger("wathiq_ai")

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
# A lease's mechanics (deposit, utilities, maintenance, handover, access) are
# what a sound lease carries, not what it cannot be enforced without: their
# absence is a real gap, not the same risk as a lease with no rent or term.
ADVISORY_KINDS = set(RENT_EXTRA_KINDS)
ADVISORY_SEVERITY = {"absent": "medium", "incomplete": "low"}
SEVERITIES = ["low", "medium", "high", "critical"]

# Deterministic rubric, in two halves that cannot drown each other out.
#
# risk-v1 summed severity weights over every finding and capped at 100. Once
# the checklist started emitting a verdict for all 11 clause kinds, that
# saturated: a thin lease with 5 absent + 5 incomplete clauses scores
# 5*18 + 5*8 = 130 from completeness alone, before a single judgement finding.
# Measured on the demo lease, two runs of deepseek-chat both scored exactly
# 100 — a number that is the same for every flawed contract says nothing.
#
# risk-v2 scores completeness as a *share* of the checklist (at most
# COMPLETENESS_CAP) and the judgement findings by severity (at most
# JUDGEMENT_CAP), so neither half can reach 100 on its own and the score keeps
# moving in the range real contracts live in. Bump the version with any weight
# change — stored scores from an older rubric are not comparable.
RISK_RUBRIC_VERSION = "risk-v3"
SEVERITY_WEIGHTS = {"low": 3, "medium": 8, "high": 18, "critical": 35}
COVERAGE_WEIGHTS = {"absent": 1.0, "incomplete": 0.5, "present": 0.0}
# risk-v3: the completeness share weighs an advisory kind at half an essential
# one, so adding the lease's five mechanics to the checklist does not dilute
# a missing rent clause into a smaller share.
ADVISORY_WEIGHT = 0.5
COMPLETENESS_CAP = 55
JUDGEMENT_CAP = 45


class AnalysisFailed(JobFailed):
    """No verified law found, or the LLM never produced valid structured
    output after MAX_ATTEMPTS — fail closed (BR-28), no partial analysis."""


@dataclass
class Finding:
    kind: str
    clause_kind: str
    severity: str
    title_ar: str
    title_en: str
    description: str
    suggested_text: str | None
    citations: list[Citation]
    confidence: float
    # The clause the finding is about, when the caller sent clauses: None is
    # the contract as a whole (or no clause sent to point at).
    ordinal: int | None = None


@dataclass
class ClauseCoverage:
    clause_kind: str
    status: str
    note: str
    citations: list[Citation]
    # Every sent clause of this kind — filled here from the input, never by the
    # model. None when the caller sent `content` only.
    ordinals: list[int] | None = None


@dataclass(frozen=True)
class SentClause:
    """One clause as the caller sent it (wire.AnalyzeClause)."""

    ordinal: int
    clause_kind: str | None
    content: str


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
    samples: int = 3,
    clauses: list[SentClause] | None = None,
) -> AnalyzeContractResult:
    """`samples` > 1 runs that many independent analyses over the *same*
    retrieved excerpts and keeps only what they agree on — self-consistency.
    One sample's findings are not reproducible (measured: mean pairwise
    Jaccard 0.48 over four runs, risk_score 35-67 on one contract), and a
    lawyer re-running a review should not get a different report.

    Measured over four runs of one contract: 3 samples lift mean pairwise
    Jaccard 0.48 -> 0.58 and the findings present in every run from 2 to 4,
    and narrow risk_score's spread. It helps; it does not make the report
    reproducible.

    It also does the model's discipline for it: deepseek-chat re-reports
    missing clauses as `risk`/`suggestion` findings despite the prompt
    forbidding it, and those duplicates differ from run to run, so the vote
    drops them — 11 judgement findings on one sample became 2 across three.

    The default was 1 while a sample cost 100s+. On deepseek-chat three
    samples measured 36s end to end against the 60s budget (NFR-1.1), which
    is what makes this affordable: the cost is 3x the tokens, and the wall
    clock is under 3x only because asyncio.gather overlaps what the endpoint
    lets it overlap. Raising it further needs a higher budget.
    """
    with stage("retrieval"):
        context = await _retrieve_context(
            pool, embedder, jurisdiction_id=jurisdiction_id, contract_type=contract_type,
            content=content, k_per_topic=k_per_topic, clauses=clauses,
        )
    if not context:
        raise AnalysisFailed("no verified law found for this jurisdiction", ErrorCode.NO_VERIFIED_SOURCES)

    # search() only serves the one `active` kb_version per jurisdiction.
    kb_version_id = next(iter(context.values())).kb_version_id

    system, user = _build_prompt(content, contract_type, context, clauses)
    kinds = clause_kinds(contract_type)
    sent = {c.ordinal: c for c in clauses} if clauses else None

    # Every sample sees the same excerpts and the same labels, so a `C3` in one
    # sample means what it means in every other — that is what makes the votes
    # below comparable.
    results = await asyncio.gather(
        *(_one_analysis(llm, system, user, context, kinds, sent, sample=i + 1) for i in range(samples)),
        return_exceptions=True,
    )
    usable = [r for r in results if not isinstance(r, BaseException)]
    if not usable:
        raise AnalysisFailed(f"no sample produced valid structured output: {results[0]}", ErrorCode.LLM_INVALID_OUTPUT)

    with stage("vote", samples=len(usable)):
        coverage, judgements, summary_ar, summary_en = _vote(usable)
        if sent is not None:
            for entry in coverage:
                entry.ordinals = [o for o, c in sent.items() if c.clause_kind == entry.clause_kind]
        judgements = _drop_restated_gaps(coverage, judgements)
        findings = [_coverage_finding(c) for c in coverage if c.status != "present"] + judgements
    result = AnalyzeContractResult(
        coverage=coverage,
        findings=findings,
        risk_score=risk_score(coverage, judgements),
        summary_ar=summary_ar,
        summary_en=summary_en,
        confidence=_overall_confidence(judgements),
        kb_version_id=kb_version_id,
    )
    return result


async def _one_analysis(
    llm, system: str, user: str, context: dict[str, SearchResult], kinds: list[str] = CLAUSE_KINDS,
    sent: dict[int, SentClause] | None = None, *, sample: int = 1,
):
    """One sample, with its own bounded JSON-repair loop."""
    last_error = ""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        prompt = user if not last_error else f"{user}\n\nYour last reply was invalid: {last_error}. Reply with corrected JSON only."
        with stage("llm", sample=sample, attempt=attempt):
            raw = await llm.chat(system, prompt, json_mode=True, max_tokens=16384)
        try:
            return _parse_and_ground(raw, context, kinds, sent)
        except _InvalidAnalysis as exc:
            last_error = str(exc)
            # What the repair round is for: the one rule the model most often
            # breaks is where a prompt fix pays back a whole extra LLM call.
            logger.info("job %s rejected attempt %d: %s", job_tag(), attempt, last_error)
    raise AnalysisFailed(f"LLM never produced valid structured output: {last_error}", ErrorCode.LLM_INVALID_OUTPUT)


# Worst-first, so a tied vote on a clause fails safe rather than silently
# clearing it: a legal review should over-report, not under-report.
_STATUS_RANK = {"absent": 0, "incomplete": 1, "present": 2}


def _finding_key(f: Finding) -> tuple:
    """What a finding is *about* — findings carry no id, and two samples will
    word the same problem differently, so identity is its kind plus the clause
    it concerns.

    It used to be kind plus the articles cited. That was too strict to vote
    on: three samples all flagged the vague lease term, each grounding it in a
    different article, so no key reached the majority and the report came back
    with zero judgement findings (measured). Which clause a finding is about
    is the model's own answer to "what is this about", and it is stable in a
    way its choice of supporting article is not.

    With clauses sent, the clause is its ordinal, so two clauses of one kind
    (a lawyer's second obligations clause) are two different subjects."""
    return (f.kind, f.ordinal if f.ordinal is not None else f.clause_kind)


def _vote(samples: list[tuple]) -> tuple[list[ClauseCoverage], list[Finding], str, str]:
    """Majority across samples. Coverage is voted per clause kind (the
    checklist guarantees every sample has an opinion on every one). Judgement
    findings are kept when at least half the samples raise them, which is what
    drops the one-off flags that made the report unstable."""
    n = len(samples)
    threshold = (n + 1) // 2

    coverage = []
    for i, kind in enumerate(c.clause_kind for c in samples[0][0]):
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
    # The summary is prose from one sample, so take it from the sample that
    # agrees most with the vote. Sample 1's summary described two risks its own
    # findings raised and the vote dropped, beside a report with no findings
    # at all (measured 2026-09-28). Ties go to the earliest sample.
    voted_keys = {_finding_key(f) for f in judgements}
    voted_status = [c.status for c in coverage]

    def agreement(sample) -> int:
        keys = {_finding_key(f) for f in sample[1]}
        same_status = sum(c.status == s for c, s in zip(sample[0], voted_status, strict=True))
        return same_status + len(keys & voted_keys) - len(keys - voted_keys)

    best = max(samples, key=agreement)
    return coverage, judgements, best[2], best[3]


# Findings that can only restate a checklist gap in other words. A
# legal_conflict or risk on the same clause is a claim about the law or the
# exposure, and stays.
_RESTATING_KINDS = {"ambiguity", "suggestion"}


def _drop_restated_gaps(coverage: list[ClauseCoverage], judgements: list[Finding]) -> list[Finding]:
    """The prompt says a missing or inadequate clause is reported in coverage
    and nowhere else; the model still raises it again as an ambiguity — blank
    id numbers came back as both "incomplete parties" and "حقول رقم الهوية
    فارغة" (measured 2026-09-28), so the lawyer resolved one problem twice and
    risk_score counted it twice. A clause the checklist already flags carries
    its gap on its missing_clause finding."""
    flagged = {c.clause_kind for c in coverage if c.status != "present"}
    return [f for f in judgements if not (f.kind in _RESTATING_KINDS and f.clause_kind in flagged)]


class _InvalidAnalysis(Exception):
    pass


# A bare C-label in prose (C1, C12) — but not a word that merely starts with C,
# and not "C1" inside a longer token.
_LABEL_IN_PROSE = re.compile(r"(?<![A-Za-z0-9])(?:C\d+|§\s?\d+)(?![A-Za-z0-9])")
# A clause label as the prompt shows it: §3.
_CLAUSE_LABEL = re.compile(r"^§\s?(\d+)$")
# An English clause-kind key in Arabic prose — "parties، subject، price" leaked
# into a summary_ar a lawyer reads.
_CLAUSE_KIND_IN_PROSE = re.compile(r"(?<![A-Za-z_])(?:" + "|".join(ALL_CLAUSE_KINDS) + r")(?![A-Za-z_])")


def risk_score(coverage: list[ClauseCoverage], judgements: list[Finding]) -> int:
    """0-100. Deterministic — no model involved.

    `judgements` is the model's findings only: the checklist verdicts are
    already scored through `coverage`, and passing the `missing_clause`
    findings derived from them would count the same gap twice.
    """
    weight = {c.clause_kind: ADVISORY_WEIGHT if c.clause_kind in ADVISORY_KINDS else 1.0 for c in coverage}
    share = sum(COVERAGE_WEIGHTS[c.status] * weight[c.clause_kind] for c in coverage) / (sum(weight.values()) or 1)
    judgement = min(JUDGEMENT_CAP, sum(SEVERITY_WEIGHTS[f.severity] for f in judgements))
    return round(COMPLETENESS_CAP * share + judgement)


def _overall_confidence(judgements: list[Finding]) -> float:
    """Mean of per-finding confidence over the model's judgements only.

    The checklist findings are all confidence 1.0 by construction (their
    severity comes from a table here, not from the model), so averaging them
    in just pulled every report towards 1.0 — a thin lease with two shaky
    judgement findings reported 0.98. A clean contract (no judgements) is a
    confident result, not an unknown one.
    """
    if not judgements:
        return 1.0
    return round(sum(f.confidence for f in judgements) / len(judgements), 3)


async def _retrieve_context(
    pool, embedder: EmbeddingProvider, *, jurisdiction_id: uuid.UUID, contract_type: str | None,
    content: str, k_per_topic: int, clauses: list[SentClause] | None = None,
) -> dict[str, SearchResult]:
    """One retrieval per clause topic, seeded with the contract's own text so
    the excerpts follow what this contract actually says, deduplicated by
    chunk_id and labeled `C1..Cn`.

    With clauses sent, each topic is seeded with its own clauses' text: the
    first 2000 chars of a lease are its parties, subject and price, so the
    inspection or handover query never saw the clause it was retrieving for.
    A kind with no clause is queried on its topic alone."""
    prefix = f"{contract_type} contract" if contract_type else "contract"
    law_types = CONTRACT_LAW_TYPES.get(contract_type, ["general"]) if contract_type else None
    if clauses:
        # ponytail: 600 chars of a kind's clauses — the embedder truncates
        # long input anyway, and one clause rarely runs longer.
        by_kind = {k: " ".join(c.content for c in clauses if c.clause_kind == k)[:600] for k in clause_kinds(contract_type)}
        queries = [f"{prefix}: {topic}. {by_kind[k]}".rstrip(". ") for k, topic in clause_topics(contract_type).items()]
    else:
        # ponytail: first 2000 chars as the query seed — embedders truncate long
        # inputs anyway.
        seed = content[:2000]
        queries = [f"{prefix}: {topic}. {seed}" for topic in clause_topics(contract_type).values()]
    context: dict[str, SearchResult] = {}
    for results in await search_many(
        pool, embedder, jurisdiction_id=jurisdiction_id, queries=queries,
        law_type=law_types, k=k_per_topic,
    ):
        for result in results:
            context.setdefault(str(result.chunk_id), result)

    return {f"C{i + 1}": result for i, result in enumerate(context.values())}


# The only prompt wording that differs by contract type: what a contract
# cannot be enforced without, and the example blank. A sale is judged on its
# price and on binding the parties to the registry transfer — a West Bank sale
# of land happens only at دائرة تسجيل الأراضي (Law 49/1953 art. 2). Rent's is
# the wording analyze shipped with, and stays the fallback for an omitted or
# unknown type.
REVIEW_BY_TYPE = {
    "rent": {"essentials": "parties, property, rent", "blank": "[تاريخ بدء الإجارة]"},
    "sale": {
        "essentials": "parties, property, price, a commitment to complete the transfer at دائرة تسجيل الأراضي",
        "blank": "[رقم القطعة]",
    },
}


def _build_prompt(
    content: str, contract_type: str | None, context: dict[str, SearchResult],
    clauses: list[SentClause] | None = None,
) -> tuple[str, str]:
    # The statute's title on every excerpt, as generate does. Without it the
    # model guessed which law an article belongs to and cited the Mejelle's
    # art. 494 as "قانون المالكين والمستأجرين" (measured 2026-09-28).
    excerpts = "\n".join(f"[{label}] ({r.source_title}) {r.content}" for label, r in context.items())
    review = REVIEW_BY_TYPE.get(contract_type, REVIEW_BY_TYPE["rent"])
    kinds = clause_kinds(contract_type)
    system = (
        "You are a Palestinian-law contract reviewer. Judge the contract only against the law "
        "excerpts provided; do not invent legal rules. Reply with JSON only, no prose, no markdown "
        'fences, shaped exactly as: {"summary_ar": "...", "summary_en": "...", "coverage": '
        '{"parties": {"status": "...", "note": "...", "cites": ["C1"]}, ...}, "findings": '
        '[{"kind": "...", "clause_kind": "...", "severity": "...", "title_ar": "...", "title_en": "...", '
        '"description": "...", "suggested_text": "..." or null, "cites": ["C1"], "confidence": 0.8'
        + (', "clause": "§3" or null' if clauses else "")
        + '}]}. '
        f"`coverage` MUST contain an entry for every one of these {len(kinds)} clause kinds, "
        f"with no others and none left out: {', '.join(kinds)}. This is a checklist, not a "
        "list of problems — say something about each one even when it is fine. status is "
        f"{' | '.join(COVERAGE_STATUSES)}: `present` = the clause is there and usable; `incomplete` "
        "= the clause is there but unusable as written (an unfilled blank, a term left open); "
        "`absent` = there is no such clause. note is one Arabic sentence saying why, and is what the "
        "reader sees, so name articles by number. cites carries the excerpt labels the verdict "
        "rests on where the law speaks to that clause, and is an empty list where it does not — "
        "do not invent a citation to fill it. A missing or inadequate clause is reported HERE "
        f"and nowhere else — do NOT put missing_clause entries in `findings`.\n"
        f"`findings` carries only the judgement calls: {', '.join(k for k in FINDING_KINDS if k != 'missing_clause')}. "
        f"clause_kind says which clause the finding is about and must be one of the same "
        f"{len(kinds)} kinds; use `other` when it concerns the contract as a whole. "
        + (
            "The contract is given clause by clause, each labelled [§n] with its kind. `clause` "
            "names the one clause a finding is about by that label, and is null when the finding "
            "concerns the contract as a whole. The § labels are internal plumbing like the C labels: "
            "never write them in a title, description or suggested_text. "
            if clauses else ""
        )
        + f"severity must be one of: {', '.join(SEVERITIES)}, judged against these anchors — the "
        "risk score is computed from them, so apply them literally rather than by feel:\n"
        "  critical — the contract or the term is void or unenforceable, or it strips a party of a "
        "protection the statute makes mandatory.\n"
        "  high — the term conflicts with the law and a court would likely strike or reverse it, or "
        f"something required to enforce the contract at all is absent ({review['essentials']}).\n"
        "  medium — a gap or ambiguity that will cause a dispute but is curable by filling it in "
        "(an unfilled date, a missing inventory, an unnamed court).\n"
        "  low — a customary protective term that is advisable but not legally required.\n"
        "Every finding must cite at least one label from the excerpts that grounds it — a finding "
        "you cannot ground in an excerpt must be left out. confidence is 0..1. "
        "The labels C1, C2 ... are internal plumbing: put them in `cites` and NEVER write them in a "
        "title, description or suggested_text. A lawyer reading the report has never seen them. "
        "Refer to law the way the excerpt itself does — by its article number, e.g. المادة (4). "
        "suggested_text is contract Arabic ready to paste into the contract, using bracketed blanks "
        f"such as {review['blank']} for anything the parties must still supply — never dotted lines — "
        "and keeping every name, number and date the contract already states. "
        "Report contradictions with the excerpts (legal_conflict), vague or unenforceable "
        "wording (ambiguity), improvements (suggestion), and commercial/legal exposure (risk). "
        "summary_ar is Arabic, summary_en is English; both summarise the contract's overall state "
        "in two or three sentences — what it is, and how complete — without listing defects, which "
        "is what `findings` and `coverage` are for. The clause kind names above are keys, not words: never write them in "
        "summary_ar — name a clause in Arabic (e.g. بند المدة). Name each law as its excerpt's "
        "title in parentheses names it. Return an empty findings array if the contract is sound."
    )
    if clauses:
        content = "\n\n".join(f"[§{c.ordinal}] ({c.clause_kind or 'unlabelled'}) {c.content}" for c in clauses)
    user = (
        f"Contract type: {contract_type or 'unspecified'}\n\n"
        f"Contract under review:\n{content}\n\n"
        f"Law excerpts:\n{excerpts}"
    )
    return system, user


def _parse_and_ground(
    raw: str, context: dict[str, SearchResult], kinds: list[str] = CLAUSE_KINDS,
    sent: dict[int, SentClause] | None = None,
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

    if _CLAUSE_KIND_IN_PROSE.search(summary_ar):
        raise _InvalidAnalysis("summary_ar names clause kinds by their English keys; name them in Arabic")

    coverage = _parse_coverage(data.get("coverage"), context, kinds)

    raw_findings = data.get("findings")
    if not isinstance(raw_findings, list):
        raise _InvalidAnalysis("missing 'findings' array")

    findings = [f for f in (_ground_finding(entry, context, kinds, sent) for entry in raw_findings) if f is not None]
    if any(f.kind == "missing_clause" for f in findings):
        raise _InvalidAnalysis("missing_clause belongs in 'coverage', not 'findings'")

    return coverage, findings, summary_ar.strip(), summary_en.strip()


def _parse_coverage(
    raw: object, context: dict[str, SearchResult], kinds: list[str] = CLAUSE_KINDS,
) -> list[ClauseCoverage]:
    """Every clause kind, every time — that fixed cardinality is the whole
    point, so a short checklist is a failure the repair loop must fix."""
    if not isinstance(raw, dict):
        raise _InvalidAnalysis("missing 'coverage' object")

    missing = [k for k in kinds if k not in raw]
    if missing:
        raise _InvalidAnalysis(f"coverage is missing clause kind(s): {missing}")
    unknown = [k for k in raw if k not in kinds]
    if unknown:
        raise _InvalidAnalysis(f"coverage has unknown clause kind(s): {sorted(unknown)}")

    coverage = []
    for kind in kinds:
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
        # No "non-present must cite" rule here, deliberately. It was the single
        # biggest cost in this agent: measured on one thin lease, all three
        # DeepSeek models failed it on the first attempt (pro, flash and chat
        # each on a different clause), so the common case was two or three
        # 100s+ LLM calls against a 60s budget — a self-inflicted timeout.
        #
        # It was also the wrong rule. BR-25 forbids citing law we never
        # retrieved; it does not require a citation for every verdict. A
        # `missing_clause` finding is an enumeration of *our* checklist
        # (FR-6.2), not a claim about a statute, and "this lease has no
        # termination clause" is often true with no excerpt that says it must.
        # Judgement findings still must cite — those are claims about the law.
        coverage.append(
            ClauseCoverage(
                clause_kind=kind,
                status=status,
                note=note.strip(),
                citations=[citation_from(context[label]) for label in sorted(set(cites))],
            )
        )
    return coverage


# User-facing names for the clause kinds, so a checklist finding's Arabic title
# doesn't carry the English enum value ("بند غائب: duration").
CLAUSE_LABELS_AR = {
    "parties": "أطراف العقد",
    "subject": "محل العقد",
    "price": "البدل",
    "payment_terms": "طريقة الدفع",
    "duration": "مدة العقد",
    "obligations": "التزامات الطرفين",
    "warranties": "الضمانات",
    "termination": "إنهاء العقد",
    "dispute_resolution": "تسوية النزاعات",
    "governing_law": "القانون الواجب التطبيق",
    "other": "أحكام ختامية",
    "deposit": "التأمين",
    "utilities": "الخدمات والرسوم",
    "maintenance": "الصيانة والإصلاحات",
    "handover": "التسليم والاستلام",
    "inspection": "المعاينة",
}


def _coverage_finding(entry: ClauseCoverage) -> Finding:
    """A checklist verdict rendered as a finding. Severity comes from the
    status table, not from the model, so the same verdict always scores the
    same — which is what makes risk_score reproducible."""
    return Finding(
        kind="missing_clause",
        clause_kind=entry.clause_kind,
        severity=(ADVISORY_SEVERITY if entry.clause_kind in ADVISORY_KINDS else COVERAGE_SEVERITY)[entry.status],
        title_ar=f"{'بند غائب' if entry.status == 'absent' else 'بند غير مكتمل'}: {CLAUSE_LABELS_AR[entry.clause_kind]}",
        title_en=f"{'Absent' if entry.status == 'absent' else 'Incomplete'} clause: {entry.clause_kind.replace('_', ' ')}",
        description=entry.note,
        suggested_text=None,
        citations=entry.citations,
        confidence=1.0,
        # An incomplete clause is one row to point at; an absent kind, or two
        # clauses of it, is not.
        ordinal=entry.ordinals[0] if entry.ordinals and len(entry.ordinals) == 1 else None,
    )


def _ground_finding(
    entry: object, context: dict[str, SearchResult], kinds: list[str] = CLAUSE_KINDS,
    sent: dict[int, SentClause] | None = None,
) -> Finding | None:
    if not isinstance(entry, dict):
        raise _InvalidAnalysis("finding is not an object")

    kind = entry.get("kind")
    severity = entry.get("severity")
    clause_kind = entry.get("clause_kind")
    if kind not in FINDING_KINDS:
        raise _InvalidAnalysis(f"unknown finding kind {kind!r}")
    # Which clause the finding is about. Required because the vote is taken on
    # it (see _finding_key), and useful to a review UI that wants to show a
    # judgement next to the clause it concerns.
    if clause_kind not in kinds:
        raise _InvalidAnalysis(f"unknown clause_kind {clause_kind!r} on a {kind} finding")
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

    # BR-25: a finding with no grounding is not a finding — so it is left out,
    # as the prompt already tells the model to do. It used to fail the whole
    # sample instead, re-rolling 11 verdicts and every other finding to get rid
    # of one: the most common repair by far (6 of 7 rejections in one measured
    # job, 2026-09-28), ~9s each, and one sample lost all three attempts to it.
    cites = entry.get("cites") or []
    if not cites or not all(label in context for label in cites):
        logger.info("job %s dropped an ungrounded %s finding on %s", job_tag(), kind, clause_kind)
        return None

    confidence = entry.get("confidence", 0.5)
    if not isinstance(confidence, (int, float)) or not 0.0 <= confidence <= 1.0:
        raise _InvalidAnalysis(f"confidence {confidence!r} out of range on a {kind} finding")

    # The clause is grounded the way a citation is: the model names a label we
    # handed out, and the ordinal and kind come from what the caller sent. A
    # label we never handed out points at nothing, so the finding falls back to
    # the whole contract rather than to a guess.
    ordinal = None
    if sent is not None:
        match = _CLAUSE_LABEL.match(str(entry.get("clause") or "").strip())
        if match and int(match.group(1)) in sent:
            ordinal = int(match.group(1))
            clause_kind = sent[ordinal].clause_kind or clause_kind
        elif entry.get("clause"):
            logger.info("job %s: a %s finding named clause %r, which was not sent", job_tag(), kind, entry.get("clause"))

    suggested = entry.get("suggested_text")
    return Finding(
        ordinal=ordinal,
        kind=kind,
        clause_kind=clause_kind,
        severity=severity,
        title_ar=entry["title_ar"].strip(),
        title_en=entry["title_en"].strip(),
        description=entry["description"].strip(),
        suggested_text=suggested.strip() if isinstance(suggested, str) and suggested.strip() else None,
        citations=[citation_from(context[label]) for label in sorted(set(cites))],
        confidence=float(confidence),
    )
