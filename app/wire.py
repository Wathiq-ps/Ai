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


# What a legitimate request can hold, with room to spare, and no more. Every
# value below ends up in an LLM prompt, so an unbounded field is an unbounded
# bill: a 2 MB party name was accepted before these (seam test, 2026-09-28).
# Laravel's own columns are far smaller (users.name is varchar(191)); a full
# 16-clause lease is ~10k characters.
MAX_FIELD_CHARS = 300  # one party / property / terms value
MAX_FIELDS = 20  # keys in one party / property / terms object
MAX_PARTIES = 4
MAX_CONTRACT_CHARS = 60_000  # the whole contract sent for analysis
MAX_CLAUSES = 80
MAX_CLAUSE_CHARS = 10_000


def _bounded(value: dict, where: str) -> dict:
    """A flat object of short values — what a party, a property or the terms
    are. Nested values are refused rather than measured: none is legitimate,
    and each would be one more way around the per-value cap."""
    if len(value) > MAX_FIELDS:
        raise ValueError(f"{where}: at most {MAX_FIELDS} fields")
    for key, item in value.items():
        if len(key) > 64:
            raise ValueError(f"{where}: field names are at most 64 characters")
        if isinstance(item, (dict, list)):
            raise ValueError(f"{where}.{key}: must be a single value")
        if isinstance(item, str) and len(item) > MAX_FIELD_CHARS:
            raise ValueError(f"{where}.{key}: at most {MAX_FIELD_CHARS} characters")
    return value


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

    contract_type: str = Field(max_length=32)
    parties: list[dict] = Field(max_length=MAX_PARTIES)
    property: dict
    terms: dict | None = None
    language: Literal["ar", "en"] = "ar"

    @field_validator("parties")
    @classmethod
    def _bounded_parties(cls, parties: list[dict]) -> list[dict]:
        return [_bounded(party, f"parties.{i}") for i, party in enumerate(parties)]

    @field_validator("property", "terms")
    @classmethod
    def _bounded_objects(cls, value: dict | None, info) -> dict | None:
        return None if value is None else _bounded(value, info.field_name)


class AnalyzeClause(BaseModel):
    """openapi.yaml AnalyzeClause — one clause row as Laravel stores it."""

    ordinal: int
    clause_kind: str | None = Field(default=None, max_length=64)
    content: str = Field(min_length=1, max_length=MAX_CLAUSE_CHARS)


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
    content: str | None = Field(default=None, min_length=1, max_length=MAX_CONTRACT_CHARS)
    clauses: list[AnalyzeClause] | None = Field(default=None, min_length=1, max_length=MAX_CLAUSES)
    contract_version_id: uuid.UUID | None = None
    contract_type: str | None = Field(default=None, max_length=32)
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
        if len(self.content) > MAX_CONTRACT_CHARS:
            raise ValueError(f"the clauses together are over {MAX_CONTRACT_CHARS} characters")
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

    tag: str | None = Field(default=None, max_length=64)
    notes: str | None = Field(default=None, max_length=2000)


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
