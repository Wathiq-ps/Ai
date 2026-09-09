import asyncio
import json
import uuid
from datetime import date

import pytest

import app.generate_contract as gc
from app.generate_contract import (
    CLAUSE_KINDS,
    GenerationFailed,
    _InvalidDraft,
    _parse_and_ground,
    generate_contract,
)
from app.knowledge import SearchResult

JURISDICTION_ID = uuid.uuid4()


def _result(label_seed: int) -> SearchResult:
    return SearchResult(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        source_id=uuid.uuid4(),
        content=f"Article text {label_seed}",
        score=0.9,
        law_type="sale",
        article=f"Article ({label_seed})",
        effective_from=date(2020, 1, 1),
        effective_to=None,
    )


def _full_draft_json(context: dict, cite_label: str) -> str:
    return json.dumps(
        {"clauses": [{"clause_kind": k, "content": f"{k} text", "cites": [cite_label]} for k in CLAUSE_KINDS]}
    )


def test_parse_and_ground_hydrates_real_citations_from_context():
    context = {"C1": _result(1)}
    raw = _full_draft_json(context, "C1")

    clauses, citations = _parse_and_ground(raw, context)

    assert [c.clause_kind for c in clauses] == CLAUSE_KINDS
    assert citations == [
        gc.Citation(
            source_id=context["C1"].source_id,
            article_ref=context["C1"].article,
            chunk_id=context["C1"].chunk_id,
            excerpt=context["C1"].content,
        )
    ]


@pytest.mark.parametrize(
    "raw",
    [
        "not json",
        json.dumps({"clauses": []}),
        json.dumps({"clauses": [{"clause_kind": "not_a_kind", "content": "x", "cites": ["C1"]}]}),
        json.dumps({"clauses": [{"clause_kind": "parties", "content": "", "cites": ["C1"]}]}),
        json.dumps({"clauses": [{"clause_kind": "parties", "content": "x", "cites": ["C_missing"]}]}),
        json.dumps(
            {
                "clauses": [
                    {"clause_kind": "parties", "content": "x", "cites": ["C1"]},
                    {"clause_kind": "parties", "content": "y", "cites": ["C1"]},
                ]
            }
        ),
        json.dumps({"clauses": [{"clause_kind": "parties", "content": "x", "cites": ["C1"]}]}),  # missing kinds
    ],
)
def test_parse_and_ground_rejects_malformed_drafts(raw):
    with pytest.raises(_InvalidDraft):
        _parse_and_ground(raw, {"C1": _result(1)})


class _ScriptedLLM:
    def __init__(self, replies: list[str]):
        self._replies = list(replies)

    async def chat(self, system: str, user: str, *, json_mode: bool = False, max_tokens: int | None = None) -> str:
        return self._replies.pop(0)


def test_generate_contract_fails_closed_with_no_retrieval(monkeypatch):
    async def _empty_search(*args, **kwargs):
        return []

    monkeypatch.setattr(gc, "search", _empty_search)

    with pytest.raises(GenerationFailed):
        asyncio.run(
            generate_contract(
                pool=None,
                llm=_ScriptedLLM([]),
                embedder=None,
                jurisdiction_id=JURISDICTION_ID,
                contract_type="sale",
                parties=[{"name": "A"}],
                property={"address": "Gaza"},
            )
        )


def test_generate_contract_retries_then_succeeds(monkeypatch):
    seeded = _result(1)

    async def _fake_search(*args, **kwargs):
        return [seeded]

    monkeypatch.setattr(gc, "search", _fake_search)

    llm = _ScriptedLLM(["not json", _full_draft_json({}, "C1")])

    result = asyncio.run(
        generate_contract(
            pool=None,
            llm=llm,
            embedder=None,
            jurisdiction_id=JURISDICTION_ID,
            contract_type="sale",
            parties=[{"name": "A"}],
            property={"address": "Gaza"},
        )
    )

    assert {c.clause_kind for c in result.clauses} == set(CLAUSE_KINDS)
    assert result.citations[0].chunk_id == seeded.chunk_id
    assert result.body  # assembled from clause contents


def test_generate_contract_fails_closed_after_max_attempts(monkeypatch):
    async def _fake_search(*args, **kwargs):
        return [_result(1)]

    monkeypatch.setattr(gc, "search", _fake_search)

    llm = _ScriptedLLM(["not json"] * gc.MAX_ATTEMPTS)

    with pytest.raises(GenerationFailed):
        asyncio.run(
            generate_contract(
                pool=None,
                llm=llm,
                embedder=None,
                jurisdiction_id=JURISDICTION_ID,
                contract_type="sale",
                parties=[{"name": "A"}],
                property={"address": "Gaza"},
            )
        )
