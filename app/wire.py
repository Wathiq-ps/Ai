"""The wire contract with Laravel, declared once.

Every field Laravel must send, every error code this service can return, and the
callback envelope itself are pydantic models here. They replace hand-rolled
`payload.get(...)` checks in the job runners that agreed with openapi.yaml only
by accident: the spec required `contract_version_id` on an analysis and the code
never read it, and `reindex` had neither a payload nor a result schema, so a
reindex success could not be described by the contract at all.

`tests/test_wire_contract.py` reads openapi.yaml and fails when the two drift, so
this module is the declaration and the spec is its documentation. Change a field
here and the spec has to move with it.
"""

from __future__ import annotations

import uuid
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class ErrorCode(StrEnum):
    """What lands in `ai_jobs.error_code` (openapi.yaml's enum). Every failure
    path raises with a member of this — never a bare string — and the wire-contract
    test checks the spec lists exactly these."""

    INVALID_PAYLOAD = "invalid_payload"
    UNSUPPORTED_CONTRACT_TYPE = "unsupported_contract_type"
    NO_VERIFIED_SOURCES = "no_verified_sources"
    LLM_INVALID_OUTPUT = "llm_invalid_output"
    TIMEOUT = "timeout"
    NO_DOCUMENTS = "no_documents"
    INTERNAL = "internal"


class GenerateContractPayload(BaseModel):
    """openapi.yaml GenerateContractPayload.

    `contract_type` is a plain string, not a `Literal["rent", "sale"]`: those are
    what this service can *draft*, and any other value is accepted on the wire and
    answered with a signed `unsupported_contract_type` failure. A Literal here
    would turn that into a 422 and leave Laravel with no callback at all.

    `terms` stays an open object rather than a model: the drafting agent writes
    whatever it is given straight into the prompt, and the spec documents the
    known keys.
    """

    contract_type: str
    parties: list[dict]
    property: dict
    terms: dict | None = None
    language: Literal["ar", "en"] = "ar"


class AnalyzeClause(BaseModel):
    """openapi.yaml AnalyzeClause — one clause row as Laravel stores it."""

    ordinal: int
    clause_kind: str | None = None
    content: str = Field(min_length=1)


class AnalyzeContractPayload(BaseModel):
    """openapi.yaml AnalyzeContractPayload.

    `contract_version_id` is optional though the spec used to require it: this
    service never reads it (Laravel correlates a callback by `job_id`), so
    requiring it could only fail a caller for nothing.

    `clauses` is the version as Laravel holds it. Sent, the analysis judges
    each clause as the kind it is and answers findings by `ordinal`; `content`
    is then derived from it. `content` alone is the older form, still served.
    """

    # An empty contract is not a request: without min_length it would run a
    # full paid analysis on nothing.
    content: str | None = Field(default=None, min_length=1)
    clauses: list[AnalyzeClause] | None = Field(default=None, min_length=1)
    contract_version_id: uuid.UUID | None = None
    contract_type: str | None = None
    samples: int = 3

    @model_validator(mode="after")
    def _one_form_of_the_contract(self) -> AnalyzeContractPayload:
        if self.clauses is None:
            if self.content is None:
                raise ValueError("send the contract as `clauses` or `content`")
            return self
        ordinals = [c.ordinal for c in self.clauses]
        if len(set(ordinals)) != len(ordinals):
            raise ValueError("clause ordinals must be unique")
        self.clauses = sorted(self.clauses, key=lambda c: c.ordinal)
        # The same "\n\n" join generate_contract uses for `body`.
        self.content = "\n\n".join(c.content for c in self.clauses)
        return self

    @field_validator("samples")
    @classmethod
    def _clamp_samples(cls, value: int) -> int:
        """Clamped, not rejected — a stray value must not blow NFR-1.1's 60s
        budget, and a 422 would leave Laravel without a callback."""
        return max(1, min(3, value))


class ReindexPayload(BaseModel):
    """openapi.yaml ReindexPayload — UC-080. Both fields are optional: what gets
    rebuilt is every document of the jurisdiction already in
    `knowledge.documents`, and the AI service cannot create or verify sources."""

    tag: str | None = None
    notes: str | None = None


class Provenance(BaseModel):
    """openapi.yaml Provenance. `ai_jobs` refuses a succeeded row without it
    (NFR-12.3), so every callback carries one."""

    provider: str
    model_id: str
    model_version: str
    prompt_version: str
    kb_version_id: uuid.UUID | None


class Usage(BaseModel):
    """openapi.yaml Usage — what the job cost. Sent on failed and timed_out too:
    a failed job still spent its tokens."""

    prompt_tokens: int
    completion_tokens: int
    latency_ms: int


# --- Results ---------------------------------------------------------------
#
# What `result` holds on a succeeded callback, per kind. Every field the service
# always sends is required here (nullable where it can be null), so the spec's
# `required` lists say exactly what Laravel can rely on.

Severity = Literal["low", "medium", "high", "critical"]

# openapi.yaml ClauseKind, and Laravel's app.clause_kind enum. The drafting and
# analysis code already refuse a kind outside their per-type list; this is the
# last gate, so not even a bug here can put an unknown kind on the wire.
# tests/test_wire_contract.py holds it to ALL_CLAUSE_KINDS in
# app/generate_contract.py (which imports this module, so it cannot import that).
ClauseKind = Literal[
    "parties", "subject", "price", "payment_terms", "deposit", "duration", "obligations",
    "utilities", "maintenance", "handover", "inspection", "warranties", "termination",
    "dispute_resolution", "governing_law", "other",
]


class Citation(BaseModel):
    """openapi.yaml Citation — a reference; the text is knowledge.chunks.content."""

    chunk_id: uuid.UUID
    article_ref: str | None
    law: str


class DraftClause(BaseModel):
    """openapi.yaml DraftClause."""

    clause_kind: ClauseKind
    content: str
    citations: list[Citation]


class GenerateContractResult(BaseModel):
    """openapi.yaml GenerateContractResult."""

    body: str
    clauses: list[DraftClause]


class ClauseCoverage(BaseModel):
    """openapi.yaml ClauseCoverage."""

    clause_kind: ClauseKind
    status: Literal["present", "incomplete", "absent"]
    note: str
    citations: list[Citation]
    ordinals: list[int] | None


class Finding(BaseModel):
    """openapi.yaml Finding."""

    kind: Literal["missing_clause", "legal_conflict", "ambiguity", "suggestion", "risk"]
    clause_kind: ClauseKind
    severity: Severity
    title_ar: str
    title_en: str
    description: str
    suggested_text: str | None
    citations: list[Citation]
    confidence: float = Field(ge=0, le=1)
    ordinal: int | None


class AnalyzeContractResult(BaseModel):
    """openapi.yaml AnalyzeContractResult."""

    coverage: list[ClauseCoverage]
    findings: list[Finding]
    risk_score: int = Field(ge=0, le=100)
    risk_rubric_version: str
    summary_ar: str
    summary_en: str
    confidence: float = Field(ge=0, le=1)


class ReindexResult(BaseModel):
    """openapi.yaml ReindexResult."""

    kb_version_id: uuid.UUID
    documents: int


JobResult = GenerateContractResult | AnalyzeContractResult | ReindexResult


class JobAccepted(BaseModel):
    """openapi.yaml JobAccepted — the 202 body.

    `respond_within_seconds` is the latest this service will still be trying to
    deliver the callback: the kind's budget plus every callback attempt and its
    backoff. Laravel schedules its no-callback check from it (plus its own
    slack) rather than from a number copied out of this repo. None for a kind
    with no budget (reindex)."""

    job_id: uuid.UUID
    status: Literal["running"]
    respond_within_seconds: int | None


class JobCallback(BaseModel):
    """openapi.yaml JobCallback, in the field order Laravel already reads it.

    Signed and sent as this model's JSON: `main._send_callback` serialises it
    rather than hand-writing the dict, so adding a field here is the only way to
    add one on the wire — and the wire-contract test fails until the spec says so.
    """

    job_id: uuid.UUID
    kind: str
    status: Literal["succeeded", "failed", "timed_out"]
    result: JobResult | None = None
    error: str | None = None
    error_code: ErrorCode | None = None
    provenance: Provenance
    usage: Usage
