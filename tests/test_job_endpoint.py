"""Sprint 5: /v1/jobs -> the kind's runner (app/jobs.py) -> signed callback.

Everything here is offline: httpx.AsyncClient is swapped for a capturing fake,
and the job's resources (app.main.get_pool / get_llm_provider /
get_embedding_provider) are monkeypatched per test."""

import asyncio
import json
import logging
import math
import uuid
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import ClassVar, get_args

import httpx
import pytest
from fastapi.testclient import TestClient

import app.analyze_contract as ac
import app.generate_contract as gc
import app.jobs as jobs
from app import main
from app.analyze_contract import AnalyzeContractResult, ClauseCoverage, Finding
from app.config import settings
from app.generate_contract import CLAUSE_KINDS, Citation, Clause, GenerateContractResult
from app.jobs import JOBS, JobRequest
from app.knowledge import SearchResult
from app.providers.openai_compatible import OpenAICompatibleLLMProvider
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


def _post_job(job_id: str, payload: dict, kind: str = "generate_contract") -> object:
    return client.post(
        "/v1/jobs",
        json={"job_id": job_id, "kind": kind, "jurisdiction_id": str(uuid.uuid4()), "payload": payload},
    )


def _no_resources(monkeypatch) -> None:
    """A payload that cannot be served must cost no connection and no provider
    client — validation runs before anything is acquired (JobKind.validate)."""

    def _boom_sync(*args, **kwargs):
        raise AssertionError("an invalid payload must not acquire resources")

    async def _boom_async(*args, **kwargs):
        raise AssertionError("an invalid payload must not acquire resources")

    monkeypatch.setattr(main, "get_pool", _boom_async)
    monkeypatch.setattr(main, "get_llm_provider", _boom_sync)
    monkeypatch.setattr(main, "get_embedding_provider", _boom_sync)


def _verify_signature(call: dict) -> dict:
    ts = int(call["headers"]["X-Wathiq-Signature"].split(",")[0][2:])
    assert call["headers"]["X-Wathiq-Signature"] == sign_callback(call["content"], settings.ai_webhook_secret, timestamp=ts)
    return json.loads(call["content"])


def test_missing_payload_fields_sends_failed_callback_with_valid_signature(monkeypatch):
    _no_resources(monkeypatch)

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
    # `usage` is appended; the fields Laravel already reads keep their shape.
    assert list(body) == ["job_id", "kind", "status", "result", "error", "error_code", "provenance", "usage"]
    # Failed before any LLM call: nothing spent, but the time still counts.
    assert body["usage"]["prompt_tokens"] == body["usage"]["completion_tokens"] == 0
    assert isinstance(body["usage"]["latency_ms"], int) and body["usage"]["latency_ms"] >= 0


def test_success_path_sends_signed_callback_with_result(monkeypatch):
    kb_version_id, source_id, chunk_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()

    async def _fake_generate_contract(*args, **kwargs):
        return GenerateContractResult(
            body="full text",
            clauses=[Clause(
                clause_kind="parties", content="x",
                citations=[Citation(source_id=source_id, article_ref="Article (1)", chunk_id=chunk_id,
                                    excerpt="...", law="Law 1")],
            )],
            citations=[],
            kb_version_id=kb_version_id,
        )

    monkeypatch.setattr(jobs, "generate_contract", _fake_generate_contract)
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
    # A citation is a reference: the excerpt's text stays in knowledge.chunks.
    assert body["result"]["clauses"] == [{
        "clause_kind": "parties", "content": "x",
        "citations": [{"chunk_id": str(chunk_id), "article_ref": "Article (1)", "law": "Law 1"}],
    }]
    assert "citations" not in body["result"]
    assert body["error_code"] is None
    assert body["provenance"]["kb_version_id"] == str(kb_version_id)
    assert body["provenance"]["prompt_version"] == JOBS["generate_contract"].prompt_version
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

    monkeypatch.setattr(jobs, "analyze_contract", _fake_analyze_contract)
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
    assert body["provenance"]["prompt_version"] == JOBS["analyze_contract"].prompt_version


@pytest.mark.parametrize("payload", [{}, {"content": ""}], ids=["missing", "empty"])
def test_analyze_contract_without_content_fails_closed(monkeypatch, payload):
    _no_resources(monkeypatch)

    response = client.post(
        "/v1/jobs",
        json={"job_id": str(uuid.uuid4()), "kind": "analyze_contract", "jurisdiction_id": str(uuid.uuid4()), "payload": payload},
    )
    assert response.status_code == 202

    [used] = _CapturingClient.instances
    [call] = used.calls
    body = _verify_signature(call)
    assert body["status"] == "failed"
    assert body["error_code"] == "invalid_payload"
    assert "content" in body["error"]


def test_job_kind_without_a_worker_is_rejected_up_front():
    """A 202 here would mean a callback that never comes."""
    response = client.post(
        "/v1/jobs",
        json={"job_id": str(uuid.uuid4()), "kind": "summarize", "jurisdiction_id": str(uuid.uuid4()), "payload": {}},
    )
    assert response.status_code == 422
    assert _CapturingClient.instances == []


def test_contract_type_that_cannot_be_drafted_fails_with_its_own_code(monkeypatch):
    _no_resources(monkeypatch)

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
    assert body["result"]["clauses"][0]["citations"] == [
        {"chunk_id": str(law.chunk_id), "article_ref": "المادة (2)", "law": law.source_title}
    ]
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

    monkeypatch.setattr(jobs, "generate_contract", _never_finishes)
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
    assert body["usage"]["prompt_tokens"] == 0
    assert body["usage"]["latency_ms"] > 0  # the budget it burned, not a placeholder


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

    monkeypatch.setattr(jobs, "analyze_contract", _fake_analyze_contract)
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


# --- usage: the real agents over stub retrieval and a stub LLM endpoint -----


def _stub_llm(*replies: tuple[str, int, int]) -> OpenAICompatibleLLMProvider:
    """The real provider over a stub client. Each reply is (content,
    prompt_tokens, completion_tokens), handed out in call order."""
    queue = list(replies)

    class _Completions:
        async def create(self, **kwargs):
            content, prompt_tokens, completion_tokens = queue.pop(0)
            return SimpleNamespace(
                choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content=content))],
                usage=SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens),
            )

    return OpenAICompatibleLLMProvider(SimpleNamespace(chat=SimpleNamespace(completions=_Completions())), "stub")


def _stub_agent_deps(monkeypatch, llm, agent_module) -> None:
    hit = SearchResult(
        chunk_id=uuid.uuid4(), document_id=uuid.uuid4(), source_id=uuid.uuid4(), kb_version_id=uuid.uuid4(),
        content="Article text", score=0.9, law_type="rent", article="Article (1)",
        effective_from=date(2020, 1, 1), effective_to=None, source_title="Test law", source_citation=None,
    )

    async def _search_many(*args, **kwargs):
        return [[hit] for _ in kwargs["queries"]]

    monkeypatch.setattr(agent_module, "search_many", _search_many)
    monkeypatch.setattr(main, "get_llm_provider", lambda: llm)
    monkeypatch.setattr(main, "get_embedding_provider", lambda: None)
    monkeypatch.setattr(main, "get_pool", lambda: _async_none())


def test_analyze_callback_sums_usage_over_every_sample_and_retry(monkeypatch, caplog):
    """Three samples run as concurrent tasks and one of them needs a repair
    retry: four calls, and every one of them must land in the same total."""
    valid = json.dumps({
        "summary_ar": "ملخص", "summary_en": "summary", "findings": [],
        "coverage": {k: {"status": "present", "note": "مستوفٍ."} for k in CLAUSE_KINDS},
    })
    llm = _stub_llm(("not json", 1000, 40), (valid, 1100, 300), (valid, 1000, 310), (valid, 1000, 320))
    _stub_agent_deps(monkeypatch, llm, ac)
    caplog.set_level(logging.INFO, logger="wathiq_ai")

    job_id = str(uuid.uuid4())
    client.post(
        "/v1/jobs",
        json={"job_id": job_id, "kind": "analyze_contract", "jurisdiction_id": str(uuid.uuid4()),
              "payload": {"content": "contract text"}},
    )

    [used] = _CapturingClient.instances
    body = _verify_signature(used.calls[0])
    assert body["status"] == "succeeded"
    assert body["usage"]["prompt_tokens"] == 4100
    assert body["usage"]["completion_tokens"] == 970
    assert isinstance(body["usage"]["latency_ms"], int)

    stages = [r.getMessage() for r in caplog.records if " stage=" in r.getMessage()]
    assert all(line.startswith(f"job {job_id} stage=") for line in stages)
    assert sum(" stage=retrieval " in line for line in stages) == 1
    assert sum(" stage=llm sample=" in line for line in stages) == 4
    assert any(" stage=vote samples=3 " in line for line in stages)
    assert any(" stage=total status=succeeded prompt_tokens=4100 " in line for line in stages)


def test_failed_generate_callback_still_reports_the_tokens_it_spent(monkeypatch):
    """Three invalid drafts is a failed job, but three calls' worth of spend."""
    llm = _stub_llm(("not json", 2000, 100), ("still not json", 2100, 200), ("{}", 2200, 300))
    _stub_agent_deps(monkeypatch, llm, gc)

    _post_job(str(uuid.uuid4()), {"contract_type": "rent", "parties": [{"name": "A"}], "property": {"address": "Gaza"}})

    [used] = _CapturingClient.instances
    body = _verify_signature(used.calls[0])
    assert body["status"] == "failed"
    assert body["error_code"] == "llm_invalid_output"
    assert (body["usage"]["prompt_tokens"], body["usage"]["completion_tokens"]) == (6300, 600)


# --- the kind table is the only declaration of a kind -----------------------


def test_every_job_kind_declares_a_runner_and_a_prompt_version():
    """The wire Literal is read off JOBS, so a kind cannot be accepted without a
    runner to serve it — which is what a hand-kept Literal beside a hand-kept
    _RUNNERS dict could not promise."""
    assert get_args(JobRequest.model_fields["kind"].annotation) == tuple(JOBS)
    for name, kind in JOBS.items():
        assert kind.name == name
        assert kind.prompt_version
        assert callable(kind.run)
        assert callable(kind.provenance)
        assert callable(kind.timeout)


def test_reindex_accepts_an_empty_payload():
    """UC-080's payload carries an optional tag and notes, nothing required —
    the documents to rebuild from come from knowledge.documents."""
    assert JOBS["reindex"].accept({}).model_dump() == {"tag": None, "notes": None}


def test_only_the_60s_budget_kinds_are_bounded(monkeypatch):
    """NFR-1.1 bounds generate/analyze; UC-080's rebuild takes minutes and has
    no budget at all."""
    monkeypatch.setattr(settings, "job_timeout_seconds", 42.0)

    assert JOBS["generate_contract"].timeout() == 42.0
    assert JOBS["analyze_contract"].timeout() == 42.0
    assert JOBS["reindex"].timeout() is None


def test_the_202_says_how_long_until_no_callback_is_coming(monkeypatch):
    """Laravel schedules its no-callback check from this, not from a copied constant."""
    monkeypatch.setattr(main, "get_pool", lambda: _async_none())
    response = _post_job(str(uuid.uuid4()), {"contract_type": "rent", "parties": [], "property": {}})

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "running"
    assert body["respond_within_seconds"] == math.ceil(settings.job_timeout_seconds + main.CALLBACK_WINDOW_SECONDS)
    assert main.respond_within_seconds(JOBS["reindex"]) is None


def test_an_oversized_party_name_fails_before_any_provider_is_called(monkeypatch):
    """Every payload value ends up in a prompt: a 2 MB name was accepted and
    would have been billed (seam test, 2026-09-28). It is now a signed
    invalid_payload failure, reached without a connection or a provider."""
    _no_resources(monkeypatch)

    job_id = str(uuid.uuid4())
    payload = {"contract_type": "rent", "property": {"city": "رام الله"},
               "parties": [{"role": "landlord", "name": "A" * 100_000}]}
    assert _post_job(job_id, payload).status_code == 202

    body = _verify_signature(_CapturingClient.instances[0].calls[0])
    assert body["error_code"] == "invalid_payload"
    assert "parties.0.name" in body["error"]


@pytest.mark.parametrize("payload", [
    {"contract_type": "rent", "property": {"city": "x"}, "parties": [{"role": "tenant"}] * 5},
    {"contract_type": "rent", "property": {"city": {"nested": "x"}}, "parties": []},
    {"contract_type": "rent", "property": {f"k{i}": "x" for i in range(21)}, "parties": []},
    {"contract_type": "rent", "property": {}, "parties": [], "terms": {"price": "1" * 301}},
])
def test_a_draft_payload_outside_its_bounds_is_invalid(monkeypatch, payload):
    _no_resources(monkeypatch)
    assert _post_job(str(uuid.uuid4()), payload).status_code == 202
    assert _verify_signature(_CapturingClient.instances[0].calls[0])["error_code"] == "invalid_payload"


def test_an_analysis_over_the_contract_cap_is_invalid(monkeypatch):
    _no_resources(monkeypatch)
    clauses = [{"ordinal": i, "content": "ب" * 9_000} for i in range(1, 8)]  # 63k joined
    assert _post_job(str(uuid.uuid4()), {"clauses": clauses}, kind="analyze_contract").status_code == 202
    assert _verify_signature(_CapturingClient.instances[0].calls[0])["error_code"] == "invalid_payload"


def test_a_job_body_over_the_cap_is_refused_before_it_is_read(monkeypatch):
    """422, which Laravel treats as final: nothing is parsed, queued or called back."""
    _no_resources(monkeypatch)
    job = {"job_id": str(uuid.uuid4()), "kind": "generate_contract", "jurisdiction_id": str(uuid.uuid4()),
           "payload": {"contract_type": "rent", "property": {}, "parties": [{"name": "A" * 600_000}]}}

    response = client.post("/v1/jobs", json=job)

    assert response.status_code == 422
    assert _CapturingClient.instances == []


def test_a_real_lease_request_is_well_inside_the_caps(monkeypatch):
    """The recorded exchanges are what Laravel actually sends; none may trip a cap."""
    for name in ("generate_contract.succeeded", "analyze_contract.succeeded"):
        request = json.loads((Path(__file__).resolve().parent.parent / "contract" / f"{name}.json").read_text())["request"]
        assert len(json.dumps(request, ensure_ascii=False).encode()) < main.MAX_JOB_BODY_BYTES // 10
