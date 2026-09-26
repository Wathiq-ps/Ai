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

from pydantic import BaseModel, field_validator


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

    `contract_type` is a plain string, not a `Literal["rent"]`: `rent` is what
    this service can *draft*, and any other value is accepted on the wire and
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


class AnalyzeContractPayload(BaseModel):
    """openapi.yaml AnalyzeContractPayload.

    `contract_version_id` is optional though the spec used to require it: this
    service never reads it (Laravel correlates a callback by `job_id`), so
    requiring it could only fail a caller for nothing.
    """

    content: str
    contract_version_id: uuid.UUID | None = None
    contract_type: str | None = None
    samples: int = 3

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


class JobCallback(BaseModel):
    """openapi.yaml JobCallback, in the field order Laravel already reads it.

    Signed and sent as this model's JSON: `main._send_callback` serialises it
    rather than hand-writing the dict, so adding a field here is the only way to
    add one on the wire — and the wire-contract test fails until the spec says so.
    """

    job_id: uuid.UUID
    kind: str
    status: Literal["succeeded", "failed", "timed_out"]
    result: dict | None = None
    error: str | None = None
    error_code: ErrorCode | None = None
    provenance: Provenance
    usage: Usage
