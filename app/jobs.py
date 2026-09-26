"""One interface per job kind (Sprint 5/6 wiring).

A job kind is the whole agreement between Laravel and this service: the payload
it accepts, the work it does, the shape it returns, the prompt version that
produced it, and the budget it may take. That agreement used to be written in
five places — `JobRequest.kind`'s `Literal`, the `_RUNNERS` dict, a `_run_*`
function, a PROMPT_VERSION constant and openapi.yaml's enum — none derived from
another, so adding a kind meant remembering all five, and a `Literal` that
accepted a kind with no `_RUNNERS` entry failed at request time instead of at
import. `answer_query`/`summarize` are already reserved in `app.ai_jobs`
(AI_IMPLEMENTATION_PLAN.md §4 Phase 3), so this is the shape they get added to.

Everything that needs to know the set of kinds reads `JOBS` — the route, and
`tests/test_wire_contract.py` against openapi.yaml.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal

import asyncpg
from pydantic import BaseModel

from app.analyze_contract import RISK_RUBRIC_VERSION, AnalysisFailed, analyze_contract
from app.config import settings
from app.generate_contract import (
    DRAFTABLE_CONTRACT_TYPES,
    GenerationFailed,
    generate_contract,
)
from app.providers.base import EmbeddingProvider, LLMProvider
from app.reindex import reindex

# ponytail: bump manually when a prompt changes materially — no registry,
# these strings are just what lands in provenance.prompt_version.
GENERATE_CONTRACT_PROMPT_VERSION = "generate_contract-v4"
ANALYZE_CONTRACT_PROMPT_VERSION = "analyze_contract-v1"
REINDEX_PROMPT_VERSION = "reindex-v1"  # no prompt; provenance wants a version string


@dataclass(frozen=True)
class JobContext:
    """What a job runs against. Built per job by `main.build_job_context()`."""

    pool: asyncpg.Pool
    llm: LLMProvider
    embedder: EmbeddingProvider


@dataclass(frozen=True)
class JobOutcome:
    """A successful run: the result dict that goes in the callback verbatim, and
    the kb_version that produced it (provenance.kb_version_id)."""

    result: dict
    kb_version_id: uuid.UUID


Run = Callable[["JobContext", "JobRequest"], Awaitable[JobOutcome]]
Provenance = Callable[[], tuple[str, str]]
Budget = Callable[[], "float | None"]
Validate = Callable[[dict], None]
# Forward refs above (JobRequest is defined below JOBS, since its `kind` is the
# Literal derived from the table — one declaration, not two).


def _unbounded() -> None:
    """No budget: UC-080's rebuild is minutes by design, not a NFR-1.1 job."""
    return None


def _job_budget() -> float:
    """NFR-1.1's 60s budget. Read per call, not at import, so a config change
    (or a test moving it) is what the next job actually gets."""
    return settings.job_timeout_seconds


def _llm_provenance() -> tuple[str, str]:
    if settings.deepseek_api_key:
        return "deepseek", settings.chat_model
    return "fake", "fake"


def _embedding_provenance() -> tuple[str, str]:
    if settings.openrouter_api_key:
        return "openrouter", settings.embedding_model
    return "fake", "fake"


def _validate_generate_contract(payload: dict) -> None:
    missing = [k for k in ("contract_type", "parties", "property") if k not in payload]
    if missing:
        raise GenerationFailed(f"payload missing required field(s): {missing}", "invalid_payload")
    if payload["contract_type"] not in DRAFTABLE_CONTRACT_TYPES:
        raise GenerationFailed(
            f"drafting a {payload['contract_type']!r} contract is not supported yet",
            "unsupported_contract_type",
        )


def _validate_analyze_contract(payload: dict) -> None:
    if not payload.get("content"):
        raise AnalysisFailed("payload missing required field: content", "invalid_payload")


async def _generate_contract(ctx: JobContext, job: JobRequest) -> JobOutcome:
    payload = job.payload
    result = await generate_contract(
        ctx.pool,
        ctx.llm,
        ctx.embedder,
        jurisdiction_id=job.jurisdiction_id,
        contract_type=payload["contract_type"],
        parties=payload["parties"],
        property=payload["property"],
        terms=payload.get("terms"),
        language=payload.get("language", "ar"),
    )
    return JobOutcome(
        result={
            "body": result.body,
            "clauses": [{"clause_kind": c.clause_kind, "content": c.content} for c in result.clauses],
            "citations": [citation_json(c) for c in result.citations],
        },
        kb_version_id=result.kb_version_id,
    )


async def _analyze_contract(ctx: JobContext, job: JobRequest) -> JobOutcome:
    payload = job.payload
    # Self-consistency voting is on by default now that a sample is cheap
    # (deepseek-chat, no reasoning tokens): 3 samples measured 36s end to
    # end against the 60s budget (NFR-1.1), and they buy both stability
    # (mean pairwise Jaccard 0.48->0.58) and a cleaner findings list. A
    # caller in a hurry can drop to 1. Clamped either way so a stray value
    # can't blow the timeout.
    samples = max(1, min(3, int(payload.get("samples", 3))))
    result = await analyze_contract(
        ctx.pool,
        ctx.llm,
        ctx.embedder,
        jurisdiction_id=job.jurisdiction_id,
        content=payload["content"],
        contract_type=payload.get("contract_type"),
        samples=samples,
    )
    return JobOutcome(
        result={
            # The checklist is emitted alongside findings, not instead of them:
            # every non-`present` verdict is already mirrored as a
            # missing_clause finding, so a consumer that only reads findings[]
            # is unaffected. Read coverage[] when you want the clauses that
            # were checked and found fine — findings[] cannot tell you that.
            "coverage": [
                {
                    "clause_kind": c.clause_kind,
                    "status": c.status,
                    "note": c.note,
                    "citations": [citation_json(x) for x in c.citations],
                }
                for c in result.coverage
            ],
            "findings": [
                {
                    "kind": f.kind,
                    "clause_kind": f.clause_kind,
                    "severity": f.severity,
                    "title_ar": f.title_ar,
                    "title_en": f.title_en,
                    "description": f.description,
                    "suggested_text": f.suggested_text,
                    "citations": [citation_json(c) for c in f.citations],
                    "confidence": f.confidence,
                }
                for f in result.findings
            ],
            "risk_score": result.risk_score,
            "risk_rubric_version": RISK_RUBRIC_VERSION,
            "summary_ar": result.summary_ar,
            "summary_en": result.summary_en,
            "confidence": result.confidence,
        },
        kb_version_id=result.kb_version_id,
    )


async def _reindex(ctx: JobContext, job: JobRequest) -> JobOutcome:
    """UC-080. Rebuilds this jurisdiction's kb_version from what is already in
    knowledge.documents; the payload only carries optional tag/notes — the AI
    service cannot create or verify sources (see app/reindex.py)."""
    embedding_model = settings.embedding_model if settings.openrouter_api_key else "fake"
    kb_version_id, documents = await reindex(
        ctx.pool,
        ctx.embedder,
        jurisdiction_id=job.jurisdiction_id,
        embedding_model=embedding_model,
        tag=job.payload.get("tag"),
        notes=job.payload.get("notes"),
    )
    return JobOutcome(
        result={"kb_version_id": str(kb_version_id), "documents": documents},
        kb_version_id=kb_version_id,
    )


@dataclass(frozen=True)
class JobKind:
    """Everything this service knows about one kind of job. `validate` runs
    before any resource is acquired, so a payload that cannot be served costs no
    connection and no provider client."""

    name: str
    run: Run
    validate: Validate | None
    prompt_version: str
    provenance: Provenance
    timeout: Budget


JOBS: dict[str, JobKind] = {
    kind.name: kind
    for kind in (
        JobKind(
            name="generate_contract",
            run=_generate_contract,
            validate=_validate_generate_contract,
            prompt_version=GENERATE_CONTRACT_PROMPT_VERSION,
            provenance=_llm_provenance,
            timeout=_job_budget,
        ),
        JobKind(
            name="analyze_contract",
            run=_analyze_contract,
            validate=_validate_analyze_contract,
            prompt_version=ANALYZE_CONTRACT_PROMPT_VERSION,
            provenance=_llm_provenance,
            timeout=_job_budget,
        ),
        JobKind(
            name="reindex",
            run=_reindex,
            validate=None,  # tag/notes only, both optional
            prompt_version=REINDEX_PROMPT_VERSION,
            provenance=_embedding_provenance,
            timeout=_unbounded,
        ),
    )
}


def citation_json(c) -> dict:
    return {
        "source_id": str(c.source_id),
        "article_ref": c.article_ref,
        "chunk_id": str(c.chunk_id),
        "excerpt": c.excerpt,
    }


class JobRequest(BaseModel):
    """The wire request (openapi.yaml JobRequest). `kind` is the Literal derived
    from JOBS, so a kind with no worker is a 422 rather than a 202 that never
    calls back — and a kind cannot be added to the type without a runner.

    `payload` is validated by the kind's own runner (see each `_run_*` above),
    so a malformed payload is a signed `failed` callback rather than a 422:
    Laravel's contract is that every accepted job gets an answer (see
    BACKEND_INTEGRATION.md's Failure modes)."""

    job_id: uuid.UUID
    kind: Literal[*JOBS]
    jurisdiction_id: uuid.UUID
    payload: dict
