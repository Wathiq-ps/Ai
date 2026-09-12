"""Sprint 5: /v1/jobs -> generate_contract background task -> signed callback.
Everything here is offline: httpx.AsyncClient is swapped for a capturing
fake, and app.main.generate_contract/get_pool are monkeypatched per test."""

import json
import uuid

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.config import settings
from app.analyze_contract import AnalyzeContractResult, Finding
from app.generate_contract import Citation, Clause, GenerateContractResult
from app.security import sign_callback

client = TestClient(main.app)


class _CapturingClient:
    instances: list["_CapturingClient"] = []

    def __init__(self, *args, **kwargs):
        self.calls: list[dict] = []
        _CapturingClient.instances.append(self)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, content, headers):
        self.calls.append({"url": url, "content": content, "headers": headers})

        class _Resp:
            def raise_for_status(self_inner):
                pass

        return _Resp()


@pytest.fixture(autouse=True)
def _capture_httpx(monkeypatch):
    _CapturingClient.instances.clear()
    monkeypatch.setattr(main.httpx, "AsyncClient", _CapturingClient)
    settings.ai_service_api_key = "test-key"
    settings.ai_webhook_secret = "test-secret"
    yield


def _post_job(job_id: str, payload: dict) -> object:
    return client.post(
        "/v1/jobs",
        headers={"X-API-Key": "test-key"},
        json={"job_id": job_id, "kind": "generate_contract", "jurisdiction_id": str(uuid.uuid4()), "payload": payload},
    )


def _verify_signature(call: dict) -> dict:
    ts = int(call["headers"]["X-Wathiq-Signature"].split(",")[0][2:])
    assert call["headers"]["X-Wathiq-Signature"] == sign_callback(call["content"], settings.ai_webhook_secret, timestamp=ts)
    return json.loads(call["content"])


def test_missing_payload_fields_sends_failed_callback_with_valid_signature():
    job_id = str(uuid.uuid4())
    response = _post_job(job_id, {"contract_type": "sale"})  # missing parties/property
    assert response.status_code == 202

    [used] = _CapturingClient.instances
    [call] = used.calls
    body = _verify_signature(call)

    assert body["job_id"] == job_id
    assert body["status"] == "failed"
    assert "parties" in body["error"] and "property" in body["error"]
    assert body["provenance"]["kb_version_id"] is None


def test_success_path_sends_signed_callback_with_result(monkeypatch):
    kb_version_id, source_id, chunk_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()

    async def _fake_generate_contract(*args, **kwargs):
        return GenerateContractResult(
            body="full text",
            clauses=[Clause(clause_kind="parties", content="x")],
            citations=[Citation(source_id=source_id, article_ref="Article (1)", chunk_id=chunk_id, excerpt="...")],
            kb_version_id=kb_version_id,
        )

    monkeypatch.setattr(main, "generate_contract", _fake_generate_contract)
    monkeypatch.setattr(main, "get_pool", lambda: _async_none())

    job_id = str(uuid.uuid4())
    response = _post_job(
        job_id, {"contract_type": "sale", "parties": [{"name": "A"}], "property": {"address": "Gaza"}}
    )
    assert response.status_code == 202

    [used] = _CapturingClient.instances
    [call] = used.calls
    body = _verify_signature(call)

    assert body["status"] == "succeeded"
    assert body["result"]["clauses"] == [{"clause_kind": "parties", "content": "x"}]
    assert body["result"]["citations"][0]["source_id"] == str(source_id)
    assert body["provenance"]["kb_version_id"] == str(kb_version_id)
    assert body["provenance"]["prompt_version"] == main.GENERATE_CONTRACT_PROMPT_VERSION


def test_analyze_contract_sends_signed_callback_with_findings_and_score(monkeypatch):
    kb_version_id, source_id, chunk_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()

    async def _fake_analyze_contract(*args, **kwargs):
        return AnalyzeContractResult(
            findings=[
                Finding(
                    kind="missing_clause",
                    severity="high",
                    title_ar="بند مفقود",
                    title_en="Missing clause",
                    description="No dispute resolution clause.",
                    suggested_text="Add one.",
                    citations=[Citation(source_id=source_id, article_ref="Article (1)", chunk_id=chunk_id, excerpt="...")],
                    confidence=0.8,
                )
            ],
            risk_score=18,
            summary_ar="ملخص",
            summary_en="summary",
            confidence=0.8,
            kb_version_id=kb_version_id,
        )

    monkeypatch.setattr(main, "analyze_contract", _fake_analyze_contract)
    monkeypatch.setattr(main, "get_pool", lambda: _async_none())

    job_id = str(uuid.uuid4())
    response = client.post(
        "/v1/jobs",
        headers={"X-API-Key": "test-key"},
        json={
            "job_id": job_id,
            "kind": "analyze_contract",
            "jurisdiction_id": str(uuid.uuid4()),
            "payload": {"contract_version_id": str(uuid.uuid4()), "content": "contract text"},
        },
    )
    assert response.status_code == 202

    [used] = _CapturingClient.instances
    [call] = used.calls
    body = _verify_signature(call)

    assert body["status"] == "succeeded"
    assert body["result"]["risk_score"] == 18
    assert body["result"]["findings"][0]["citations"][0]["chunk_id"] == str(chunk_id)
    assert body["provenance"]["prompt_version"] == main.ANALYZE_CONTRACT_PROMPT_VERSION


def test_analyze_contract_without_content_fails_closed():
    response = client.post(
        "/v1/jobs",
        headers={"X-API-Key": "test-key"},
        json={"job_id": str(uuid.uuid4()), "kind": "analyze_contract", "jurisdiction_id": str(uuid.uuid4()), "payload": {}},
    )
    assert response.status_code == 202

    [used] = _CapturingClient.instances
    [call] = used.calls
    body = _verify_signature(call)
    assert body["status"] == "failed"
    assert "content" in body["error"]


def test_unsupported_job_kind_is_accepted_but_not_dispatched():
    response = client.post(
        "/v1/jobs",
        headers={"X-API-Key": "test-key"},
        json={"job_id": str(uuid.uuid4()), "kind": "summarize", "jurisdiction_id": str(uuid.uuid4()), "payload": {}},
    )
    assert response.status_code == 202
    assert _CapturingClient.instances == []  # no callback attempted -- no worker for this kind


async def _async_none():
    return None
