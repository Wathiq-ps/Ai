"""openapi.yaml is the contract Laravel codes against; app/wire.py is what this
service actually sends and accepts.

Nothing kept them in step but care, and they had drifted: the spec required a
`contract_version_id` the code never read, declared `enum: [rent]` for a field
the code accepts from anyone, and had no reindex payload or result schema at all
— so a reindex success could not be described by the contract. This test reads
both and fails on drift, which is what makes app/wire.py the declaration and the
spec its documentation rather than a second copy.
"""

from pathlib import Path
from typing import get_args

import pytest
import yaml

from app.jobs import JOBS, JobRequest
from app.wire import (
    AnalyzeContractPayload,
    ErrorCode,
    GenerateContractPayload,
    JobCallback,
    Provenance,
    ReindexPayload,
    Usage,
)

SPEC = yaml.safe_load((Path(__file__).resolve().parent.parent / "openapi.yaml").read_text())
SCHEMAS = SPEC["components"]["schemas"]

PAYLOAD_MODELS = {
    "GenerateContractPayload": GenerateContractPayload,
    "AnalyzeContractPayload": AnalyzeContractPayload,
    "ReindexPayload": ReindexPayload,
}
ENVELOPE_MODELS = {"JobCallback": JobCallback, "Provenance": Provenance, "Usage": Usage}


def _required(model) -> list[str]:
    """Fields with no default — what a caller must send."""
    return sorted(name for name, field in model.model_fields.items() if field.is_required())


def _refs(node: dict) -> set[str]:
    return {item["$ref"].rsplit("/", 1)[-1] for item in node["oneOf"]}


@pytest.mark.parametrize(("name", "model"), list(PAYLOAD_MODELS.items()) + list(ENVELOPE_MODELS.items()))
def test_schema_declares_exactly_the_models_fields(name, model):
    schema = SCHEMAS[name]
    assert sorted(schema.get("properties", {})) == sorted(model.model_fields), name
    assert sorted(schema.get("required", [])) == _required(model), name


def test_job_request_schema_matches_the_model():
    schema = SCHEMAS["JobRequest"]
    assert sorted(schema["properties"]) == sorted(JobRequest.model_fields)
    assert sorted(schema["required"]) == _required(JobRequest)


def test_the_kind_enum_is_the_kind_table():
    """The set of accepted kinds is JOBS — both in the spec and in the model the
    route validates against."""
    assert sorted(SCHEMAS["JobRequest"]["properties"]["kind"]["enum"]) == sorted(JOBS)
    assert get_args(JobRequest.model_fields["kind"].annotation) == tuple(JOBS)


def test_payload_oneOf_covers_every_payload_schema():
    """A payload the spec cannot describe is a payload Laravel cannot validate
    against — reindex was in that state."""
    assert _refs(SCHEMAS["JobRequest"]["properties"]["payload"]) == set(PAYLOAD_MODELS)


def test_result_oneOf_covers_every_kind_that_returns_a_result():
    assert _refs(SCHEMAS["JobCallback"]["properties"]["result"]) == {
        "GenerateContractResult",
        "AnalyzeContractResult",
        "ReindexResult",
    }


def test_each_kind_uses_its_own_payload_schema():
    assert JOBS["generate_contract"].payload_model is GenerateContractPayload
    assert JOBS["analyze_contract"].payload_model is AnalyzeContractPayload
    assert JOBS["reindex"].payload_model is ReindexPayload


def test_status_and_error_code_enums_match_the_code():
    """error_code is what Laravel stores in ai_jobs.error_code; every failure
    path raises with a member of ErrorCode, so this enum is the closed set."""
    callback = SCHEMAS["JobCallback"]
    assert sorted(callback["properties"]["error_code"]["enum"]) == sorted(code.value for code in ErrorCode)
    assert sorted(callback["properties"]["status"]["enum"]) == sorted(
        get_args(JobCallback.model_fields["status"].annotation)
    )


def test_contract_type_is_not_declared_as_an_enum():
    """`rent` is what this service can *draft*, not what it accepts: any other
    value gets a signed unsupported_contract_type callback, so an enum in the
    spec would be a lie a generated client would enforce."""
    assert "enum" not in SCHEMAS["GenerateContractPayload"]["properties"]["contract_type"]


def test_analyze_samples_are_clamped_to_the_spec_range():
    """openapi.yaml says 1..3. Clamped, not rejected, because a 422 would leave
    Laravel without a callback — and unclamped samples blow the 60s budget."""
    assert AnalyzeContractPayload(content="x", samples=0).samples == 1
    assert AnalyzeContractPayload(content="x", samples=99).samples == 3
    assert AnalyzeContractPayload(content="x").samples == 3
