"""The wire, recorded: contract/*.json is what Laravel's tests replay.

Each scenario drives the real endpoint and job code — only retrieval and the
LLM are stubbed — and records the request Laravel sends, the 202, and the
exact callback body. The files are the contract artefact Wathiq-ps/Back-end
copies in (pinned by commit), so a change to what goes over the wire fails
this test until the goldens are regenerated on purpose:

    UPDATE_GOLDENS=1 uv run pytest tests/test_contract_goldens.py

Deterministic by construction: fixed ids, fixed law excerpts, scripted
replies. `usage.latency_ms` is the one measured value and is recorded as 0.
"""

import json
import os
import uuid
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.analyze_contract as ac
import app.generate_contract as gc
from app import main
from app.config import settings
from app.knowledge import SearchResult
from app.security import sign_callback
from app.usage import add_tokens

CONTRACT_DIR = Path(__file__).resolve().parent.parent / "contract"
UPDATE = os.environ.get("UPDATE_GOLDENS") == "1"

JURISDICTION_ID = "00000000-0000-4000-8000-00000000000a"
KB_VERSION_ID = uuid.UUID("00000000-0000-4000-8000-00000000000b")
RENT_LAW = "قانون المالكين والمستأجرين رقم (62) لسنة 1953"
LAW = SearchResult(
    chunk_id=uuid.UUID("00000000-0000-4000-8000-0000000000c1"),
    document_id=uuid.UUID("00000000-0000-4000-8000-0000000000d1"),
    source_id=uuid.UUID("00000000-0000-4000-8000-0000000000e1"),
    kb_version_id=KB_VERSION_ID,
    content="لا يجوز لأية محكمة أن تصدر حكماً بإخراج مستأجر ... خلال ثلاثين يوماً من تاريخ تبليغه ...",
    score=0.9, law_type="rent", article="المادة (4)", effective_from=date(1953, 1, 1), effective_to=None,
    source_title=RENT_LAW, source_citation=None,
)

RENT_REQUEST = {
    "contract_type": "rent",
    "language": "ar",
    "parties": [
        {"role": "landlord", "name": "أحمد خليل", "nationality": "فلسطيني",
         "document_type": "national_id", "document_number": "401234567", "address": "رام الله، شارع الإرسال"},
        {"role": "tenant", "name": "سارة يوسف", "nationality": "فلسطينية",
         "document_type": "national_id", "document_number": "852345678", "address": "نابلس، رفيديا"},
    ],
    "property": {"type": "apartment", "city": "رام الله", "district": "الماصيون", "building_number": "12",
                 "area_sqm": "120", "rooms": 3, "floor_number": 2, "is_furnished": False},
    "terms": {"price": "450", "currency": "JOD", "price_unit": "per_month", "deposit": "900",
              "starts_on": "2026-11-01", "ends_on": "2027-10-31"},
}
RENT_KINDS = gc.clause_kinds("rent")


class _ScriptedLLM:
    """Replies with one fixed JSON, and reports the tokens a real call would."""

    def __init__(self, reply: dict):
        self._reply = json.dumps(reply, ensure_ascii=False)

    async def chat(self, system, user, *, json_mode=False, max_tokens=None):
        add_tokens(1200, 300)
        return self._reply


def _draft_reply() -> dict:
    return {"clauses": [
        {"clause_kind": k, "content": f"نص بند {ac.CLAUSE_LABELS_AR[k]}",
         "cites": [] if k in gc.CITATION_OPTIONAL_KINDS else ["C1"]}
        for k in RENT_KINDS
    ]}


def _analysis_reply() -> dict:
    return {
        "summary_ar": "عقد إيجار شقة سكنية لمدة سنة، مكتمل البنية مع فراغ في مدة رد التأمين.",
        "summary_en": "A one-year residential lease, complete apart from the deposit refund period.",
        "coverage": {
            k: {"status": "incomplete" if k == "deposit" else "present",
                "note": "مدة رد التأمين متروكة فراغاً." if k == "deposit" else "البند مستوفٍ.",
                "cites": ["C1"] if k == "termination" else []}
            for k in RENT_KINDS
        },
        "findings": [{
            "kind": "legal_conflict", "clause_kind": "termination", "clause": f"§{RENT_KINDS.index('termination') + 1}",
            "severity": "high", "title_ar": "مهلة الإنذار غير مذكورة", "title_en": "Notice period not stated",
            "description": "لا يذكر البند مهلة الثلاثين يوماً التي تشترطها المادة (4).",
            "suggested_text": "خلال ثلاثين يوماً من تاريخ تبليغه بواسطة الكاتب العدل.",
            "cites": ["C1"], "confidence": 0.9,
        }],
    }


class _Recorder:
    """Stands in for httpx.AsyncClient and keeps the callback body."""

    bodies: list[dict] = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, content, headers):
        _Recorder.bodies.append(json.loads(content))

        class _Resp:
            status_code = 204

        return _Resp()


@pytest.fixture
def wire(monkeypatch):
    async def _search(*args, **kwargs):
        return [[LAW] for _ in kwargs["queries"]]

    async def _no_pool():
        return None

    _Recorder.bodies = []
    monkeypatch.setattr(main.httpx, "AsyncClient", _Recorder)
    monkeypatch.setattr(gc, "search_many", _search)
    monkeypatch.setattr(ac, "search_many", _search)
    monkeypatch.setattr(main, "get_pool", _no_pool)
    monkeypatch.setattr(main, "get_embedding_provider", lambda: None)
    # What production reports, without its keys: provenance reads these.
    monkeypatch.setattr(settings, "deepseek_api_key", "golden")
    monkeypatch.setattr(settings, "chat_model", "deepseek-flash")
    monkeypatch.setattr(settings, "ai_webhook_secret", "test-secret")

    def run(job_id: str, kind: str, payload: dict, reply: dict) -> dict:
        monkeypatch.setattr(main, "get_llm_provider", lambda: _ScriptedLLM(reply))
        request = {"job_id": job_id, "kind": kind, "jurisdiction_id": JURISDICTION_ID, "payload": payload}
        response = TestClient(main.app).post("/v1/jobs", json=request)
        assert response.status_code == 202
        [callback] = _Recorder.bodies
        callback["usage"]["latency_ms"] = 0
        return {"request": request, "accepted": response.json(), "callback": callback}

    return run


def _check(name: str, exchange: dict) -> None:
    path = CONTRACT_DIR / f"{name}.json"
    text = json.dumps(exchange, ensure_ascii=False, indent=2) + "\n"
    if UPDATE:
        path.write_text(text)
        return
    assert path.exists(), f"{path.name} missing — run with UPDATE_GOLDENS=1"
    assert json.loads(path.read_text()) == exchange, (
        f"the wire changed for {name}; if that is intended, regenerate with UPDATE_GOLDENS=1 "
        "and tell Back-end to re-sync contract/"
    )


def test_a_rent_draft_on_the_wire(wire):
    exchange = wire("00000000-0000-4000-8000-000000000001", "generate_contract", RENT_REQUEST, _draft_reply())

    assert exchange["callback"]["status"] == "succeeded"
    assert [c["clause_kind"] for c in exchange["callback"]["result"]["clauses"]] == RENT_KINDS
    _check("generate_contract.succeeded", exchange)


def test_a_draft_the_service_cannot_make_on_the_wire(wire):
    payload = {**RENT_REQUEST, "contract_type": "barter"}
    exchange = wire("00000000-0000-4000-8000-000000000002", "generate_contract", payload, _draft_reply())

    assert exchange["callback"]["error_code"] == "unsupported_contract_type"
    _check("generate_contract.failed", exchange)


def test_an_analysis_of_clauses_on_the_wire(wire):
    clauses = [{"ordinal": i + 1, "clause_kind": k, "content": f"نص بند {k}"} for i, k in enumerate(RENT_KINDS)]
    payload = {"contract_type": "rent", "clauses": clauses}
    exchange = wire("00000000-0000-4000-8000-000000000003", "analyze_contract", payload, _analysis_reply())

    result = exchange["callback"]["result"]
    assert {f["kind"]: f["ordinal"] for f in result["findings"]} == {
        "missing_clause": RENT_KINDS.index("deposit") + 1,
        "legal_conflict": RENT_KINDS.index("termination") + 1,
    }
    _check("analyze_contract.succeeded", exchange)


def test_the_signature_vector_both_sides_check():
    """Back-end's AiWiringTest pins this exact header for this body and secret;
    the signer here must keep producing it."""
    vector = json.loads((CONTRACT_DIR / "hmac.json").read_text())

    assert sign_callback(vector["body"].encode(), vector["secret"], vector["timestamp"]) == vector["header"]
