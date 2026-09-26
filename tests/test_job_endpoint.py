"""Sprint 5: /v1/jobs -> generate_contract background task -> signed callback.
Everything here is offline: httpx.AsyncClient is swapped for a capturing
fake, and app.main.generate_contract/get_pool are monkeypatched per test."""

import asyncio
import json
import uuid
from datetime import date
from typing import ClassVar

import httpx
import pytest
from fastapi.testclient import TestClient

import app.generate_contract as gc
from app import main
from app.analyze_contract import AnalyzeContractResult, ClauseCoverage, Finding
from app.config import settings
from app.generate_contract import CLAUSE_KINDS, Citation, Clause, GenerateContractResult
from app.knowledge import SearchResult
from app.security import sign_callback

client = TestClient(main.app)


class _CapturingClient:
    instances: ClassVar[list["_CapturingClient"]] = []

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
            status_code = 200

        return _Resp()


@pytest.fixture(autouse=True)
def _capture_httpx(monkeypatch):
    _CapturingClient.instances.clear()
    monkeypatch.setattr(main.httpx, "AsyncClient", _CapturingClient)
    settings.ai_webhook_secret = "test-secret"
    yield


def _post_job(job_id: str, payload: dict) -> object:
    return client.post(
        "/v1/jobs",
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
    assert body["error_code"] == "invalid_payload"
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
        job_id, {"contract_type": "rent", "parties": [{"name": "A"}], "property": {"address": "Gaza"}}
    )
    assert response.status_code == 202

    [used] = _CapturingClient.instances
    [call] = used.calls
    body = _verify_signature(call)

    assert body["status"] == "succeeded"
    assert body["result"]["clauses"] == [{"clause_kind": "parties", "content": "x"}]
    assert body["result"]["citations"][0]["source_id"] == str(source_id)
    assert body["error_code"] is None
    assert body["provenance"]["kb_version_id"] == str(kb_version_id)
    assert body["provenance"]["prompt_version"] == main.GENERATE_CONTRACT_PROMPT_VERSION
    # ai_jobs_success_has_provenance refuses a succeeded row without it.
    assert body["provenance"]["model_version"]


def test_analyze_contract_sends_signed_callback_with_findings_and_score(monkeypatch):
    kb_version_id, source_id, chunk_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()

    async def _fake_analyze_contract(*args, **kwargs):
        return AnalyzeContractResult(
            coverage=[
                ClauseCoverage(
                    clause_kind="dispute_resolution",
                    status="absent",
                    note="لا يوجد بند لتسوية النزاعات.",
                    citations=[Citation(source_id=source_id, article_ref="Article (1)", chunk_id=chunk_id, excerpt="...")],
                )
            ],
            findings=[
                Finding(
                    kind="missing_clause",
                    clause_kind="dispute_resolution",
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
        json={"job_id": str(uuid.uuid4()), "kind": "analyze_contract", "jurisdiction_id": str(uuid.uuid4()), "payload": {}},
    )
    assert response.status_code == 202

    [used] = _CapturingClient.instances
    [call] = used.calls
    body = _verify_signature(call)
    assert body["status"] == "failed"
    assert "content" in body["error"]


def test_job_kind_without_a_worker_is_rejected_up_front():
    """A 202 here would mean a callback that never comes."""
    response = client.post(
        "/v1/jobs",
        json={"job_id": str(uuid.uuid4()), "kind": "summarize", "jurisdiction_id": str(uuid.uuid4()), "payload": {}},
    )
    assert response.status_code == 422
    assert _CapturingClient.instances == []


def test_contract_type_that_cannot_be_drafted_fails_with_its_own_code():
    response = _post_job(
        str(uuid.uuid4()), {"contract_type": "gift", "parties": [{"name": "A"}], "property": {"address": "Gaza"}}
    )
    assert response.status_code == 202

    [used] = _CapturingClient.instances
    body = _verify_signature(used.calls[0])
    assert body["status"] == "failed"
    assert body["error_code"] == "unsupported_contract_type"


def test_a_sale_is_drafted_end_to_end(monkeypatch):
    """The payload BACKEND_INTEGRATION.md tells Laravel to send for a sale, through
    the real generate_contract — only retrieval and the LLM are stubbed."""
    law = SearchResult(
        chunk_id=uuid.uuid4(), document_id=uuid.uuid4(), source_id=uuid.uuid4(), kb_version_id=uuid.uuid4(),
        content="ينحصر إجراء جميع معاملات التصرف في الأراضي ... في دوائر تسجيل الأراضي.", score=0.9,
        law_type="sale", article="المادة (2)", effective_from=date(1953, 1, 1), effective_to=None,
        source_title="قانون التصرف في الأموال غير المنقولة رقم (49) لسنة 1953", source_citation=None,
    )
    systems: list[str] = []

    class _LLM:
        async def chat(self, system, user, *, json_mode=False, max_tokens=None):
            systems.append(system)
            return json.dumps(
                {"clauses": [{"clause_kind": k, "content": f"{k} نص", "cites": ["C1"]} for k in CLAUSE_KINDS]}
            )

    async def _search(*args, **kwargs):
        return [[law] for _ in kwargs["queries"]]

    monkeypatch.setattr(gc, "search_many", _search)
    monkeypatch.setattr(main, "get_llm_provider", _LLM)
    monkeypatch.setattr(main, "get_embedding_provider", lambda: None)
    monkeypatch.setattr(main, "get_pool", lambda: _async_none())
    payload = {
        "contract_type": "sale",
        "parties": [{"role": "seller", "name": "A"}, {"role": "buyer", "name": "B"}],
        "property": {"address": "Ramallah", "parcel_number": "12"},
        "terms": {"price": "120000.00", "currency": "JOD"},
    }

    assert _post_job(str(uuid.uuid4()), payload).status_code == 202

    [used] = _CapturingClient.instances
    body = _verify_signature(used.calls[0])
    assert body["status"] == "succeeded", body["error"]
    assert [c["clause_kind"] for c in body["result"]["clauses"]] == CLAUSE_KINDS
    assert body["result"]["citations"][0]["article_ref"] == "المادة (2)"
    assert "الطرف الأول (البائع)" in systems[0]


def test_a_repeated_job_id_is_accepted_but_runs_once():
    """Laravel re-POSTs when our 202 is slow to arrive; that must not double the work."""
    job_id = str(uuid.uuid4())
    first = _post_job(job_id, {})
    second = _post_job(job_id, {})

    assert first.status_code == second.status_code == 202
    assert len(_CapturingClient.instances) == 1


def test_callback_is_retried_after_a_network_error(monkeypatch):
    monkeypatch.setattr(main, "CALLBACK_BACKOFF_SECONDS", (0, 0))
    attempts = []

    class _FlakyClient(_CapturingClient):
        async def post(self, url, content, headers):
            attempts.append(headers["X-Wathiq-Signature"])
            if len(attempts) == 1:
                raise httpx.ConnectError("laravel restarting")
            return await super().post(url, content, headers)

    monkeypatch.setattr(main.httpx, "AsyncClient", _FlakyClient)
    _post_job(str(uuid.uuid4()), {})

    assert len(attempts) == 2
    delivered = [c for client in _CapturingClient.instances for c in client.calls]
    assert _verify_signature(delivered[0])["error_code"] == "invalid_payload"


def test_callback_rejected_by_laravel_is_not_retried(monkeypatch):
    monkeypatch.setattr(main, "CALLBACK_BACKOFF_SECONDS", (0, 0))
    attempts = []

    class _RejectingClient(_CapturingClient):
        async def post(self, url, content, headers):
            attempts.append(url)

            class _Resp:
                status_code = 401

            return _Resp()

    monkeypatch.setattr(main.httpx, "AsyncClient", _RejectingClient)
    _post_job(str(uuid.uuid4()), {})

    assert len(attempts) == 1


async def _async_none():
    return None


def test_job_over_the_time_budget_reports_timed_out(monkeypatch):
    async def _never_finishes(*args, **kwargs):
        await asyncio.sleep(10)

    monkeypatch.setattr(main, "generate_contract", _never_finishes)
    monkeypatch.setattr(main, "get_pool", lambda: _async_none())
    monkeypatch.setattr(settings, "job_timeout_seconds", 0.01)

    response = _post_job(
        str(uuid.uuid4()), {"contract_type": "rent", "parties": [{"name": "A"}], "property": {"address": "Gaza"}}
    )
    assert response.status_code == 202

    [used] = _CapturingClient.instances
    [call] = used.calls
    body = _verify_signature(call)
    assert body["status"] == "timed_out"
    assert body["error_code"] == "timeout"
    assert "NFR-1.1" in body["error"]


def test_analyze_callback_carries_the_full_clause_checklist(monkeypatch):
    """coverage[] is what makes a report reproducible: it names every clause
    that was checked, including the ones that were fine, which findings[]
    cannot express. Laravel needs it on the wire, not just in our dataclass."""
    source_id, chunk_id = uuid.uuid4(), uuid.uuid4()
    cite = Citation(source_id=source_id, article_ref="Article (1)", chunk_id=chunk_id, excerpt="...")

    async def _fake_analyze_contract(*args, **kwargs):
        return AnalyzeContractResult(
            coverage=[
                ClauseCoverage(clause_kind="parties", status="present", note="مستوفٍ.", citations=[]),
                ClauseCoverage(clause_kind="duration", status="incomplete", note="التواريخ فارغة.", citations=[cite]),
            ],
            findings=[],
            risk_score=8,
            summary_ar="ملخص",
            summary_en="summary",
            confidence=0.9,
            kb_version_id=uuid.uuid4(),
        )

    monkeypatch.setattr(main, "analyze_contract", _fake_analyze_contract)
    monkeypatch.setattr(main, "get_pool", lambda: _async_none())
    _CapturingClient.instances.clear()
    response = client.post(
        "/v1/jobs",
        json={
            "job_id": str(uuid.uuid4()),
            "kind": "analyze_contract",
            "jurisdiction_id": str(uuid.uuid4()),
            "payload": {"contract_version_id": str(uuid.uuid4()), "content": "contract text"},
        },
    )
    assert response.status_code == 202

    [used] = _CapturingClient.instances
    [call] = used.calls
    body = _verify_signature(call)
    coverage = body["result"]["coverage"]
    assert [c["clause_kind"] for c in coverage] == ["parties", "duration"]
    assert coverage[0]["status"] == "present" and coverage[0]["citations"] == []
    assert coverage[1]["status"] == "incomplete"
    assert coverage[1]["citations"][0]["chunk_id"] == str(chunk_id)
