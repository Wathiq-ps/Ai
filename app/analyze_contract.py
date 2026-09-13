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

import json
import re
import uuid
from dataclasses import dataclass

from app.generate_contract import (
    CLAUSE_KINDS,
    CLAUSE_TOPICS,
    CONTRACT_LAW_TYPES,
    MAX_ATTEMPTS,
    Citation,
)
from app.knowledge import SearchResult, search
from app.providers.base import EmbeddingProvider, LLMProvider

FINDING_KINDS = ["missing_clause", "legal_conflict", "ambiguity", "suggestion", "risk"]
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
class AnalyzeContractResult:
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
) -> AnalyzeContractResult:
    context = await _retrieve_context(
        pool, embedder, jurisdiction_id=jurisdiction_id, contract_type=contract_type,
        content=content, k_per_topic=k_per_topic,
    )
    if not context:
        raise AnalysisFailed("no verified law found for this jurisdiction")

    # search() only serves the one `active` kb_version per jurisdiction.
    kb_version_id = next(iter(context.values())).kb_version_id

    system, user = _build_prompt(content, contract_type, context)

    last_error = ""
    for _ in range(MAX_ATTEMPTS):
        prompt = user if not last_error else f"{user}\n\nYour last reply was invalid: {last_error}. Reply with corrected JSON only."
        raw = await llm.chat(system, prompt, json_mode=True, max_tokens=16384)
        try:
            findings, summary_ar, summary_en = _parse_and_ground(raw, context)
        except _InvalidAnalysis as exc:
            last_error = str(exc)
            continue
        return AnalyzeContractResult(
            findings=findings,
            risk_score=risk_score(findings),
            summary_ar=summary_ar,
            summary_en=summary_en,
            confidence=_overall_confidence(findings),
            kb_version_id=kb_version_id,
        )

    raise AnalysisFailed(f"LLM never produced valid structured output: {last_error}")


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
    context: dict[str, SearchResult] = {}
    for topic in CLAUSE_TOPICS.values():
        query = f"{prefix}: {topic}. {seed}"
        results = await search(
            pool, embedder, jurisdiction_id=jurisdiction_id, query=query,
            law_type=law_types, k=k_per_topic,
        )
        for result in results:
            context.setdefault(str(result.chunk_id), result)

    return {f"C{i + 1}": result for i, result in enumerate(context.values())}


def _build_prompt(content: str, contract_type: str | None, context: dict[str, SearchResult]) -> tuple[str, str]:
    excerpts = "\n".join(f"[{label}] {r.content}" for label, r in context.items())
    system = (
        "You are a Palestinian-law contract reviewer. Judge the contract only against the law "
        "excerpts provided; do not invent legal rules. Reply with JSON only, no prose, no markdown "
        'fences, shaped exactly as: {"summary_ar": "...", "summary_en": "...", "findings": '
        '[{"kind": "...", "severity": "...", "title_ar": "...", "title_en": "...", '
        '"description": "...", "suggested_text": "..." or null, "cites": ["C1"], "confidence": 0.8}]}. '
        f"kind must be one of: {', '.join(FINDING_KINDS)}. "
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
        f"Check completeness against these clause groups: {', '.join(CLAUSE_KINDS)} — report each "
        "absent or inadequate one as a missing_clause finding with suggested_text. "
        "Also report contradictions with the excerpts (legal_conflict), vague or unenforceable "
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


def _parse_and_ground(raw: str, context: dict[str, SearchResult]) -> tuple[list[Finding], str, str]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise _InvalidAnalysis(f"not valid JSON ({exc})") from exc

    summary_ar = data.get("summary_ar")
    summary_en = data.get("summary_en")
    for name, value in (("summary_ar", summary_ar), ("summary_en", summary_en)):
        if not isinstance(value, str) or not value.strip():
            raise _InvalidAnalysis(f"missing or empty {name!r}")

    raw_findings = data.get("findings")
    if not isinstance(raw_findings, list):
        raise _InvalidAnalysis("missing 'findings' array")

    findings = [_ground_finding(entry, context) for entry in raw_findings]
    return findings, summary_ar.strip(), summary_en.strip()


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
        citations=[
            Citation(
                source_id=context[label].source_id,
                article_ref=context[label].article,
                chunk_id=context[label].chunk_id,
                excerpt=context[label].content,
            )
            for label in sorted(set(cites))
        ],
        confidence=float(confidence),
    )
