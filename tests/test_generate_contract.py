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
RENT_LAW = "قانون المالكين والمستأجرين رقم (62) لسنة 1953"


def _result(label_seed: int) -> SearchResult:
    return SearchResult(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        source_id=uuid.uuid4(),
        kb_version_id=uuid.uuid4(),
        content=f"Article text {label_seed}",
        score=0.9,
        law_type="sale",
        article=f"Article ({label_seed})",
        effective_from=date(2020, 1, 1),
        effective_to=None,
        source_title=RENT_LAW,
        source_citation="قانون رقم (62) لسنة 1953 وتعديلاته",
    )


def _full_draft_json(context: dict, cite_label: str, governing_law: str = "governing_law text") -> str:
    return json.dumps(
        {
            "clauses": [
                {"clause_kind": k, "content": governing_law if k == "governing_law" else f"{k} text", "cites": [cite_label]}
                for k in CLAUSE_KINDS
            ]
        },
        ensure_ascii=False,
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


@pytest.mark.parametrize(
    "governing_law",
    [
        f"تسري على هذا العقد أحكام {RENT_LAW}.",
        "تسري على هذا العقد أحكام قانون المالكين والمستأجرين رقم ٦٢ لسنة ١٩٥٣.",
        "تسري على هذا العقد أحكام مجلة الأحكام العدلية.",  # no number/year to check
    ],
)
def test_parse_and_ground_accepts_a_statute_named_by_a_cited_source(governing_law):
    _parse_and_ground(_full_draft_json({}, "C1", governing_law), {"C1": _result(1)})


@pytest.mark.parametrize(
    "governing_law",
    [
        # The live regression: a real-sounding statute the knowledge base does not hold.
        "تسري على هذا العقد أحكام قانون المالكين والمستأجرين رقم (7) لسنة 1958.",
        # The right number with the wrong year is still a different statute.
        "تسري على هذا العقد أحكام قانون المالكين والمستأجرين رقم (62) لسنة 1958.",
        f"تسري على هذا العقد أحكام {RENT_LAW} وقانون رقم 11/1954.",
    ],
)
def test_parse_and_ground_rejects_a_statute_not_among_the_cited_sources(governing_law):
    with pytest.raises(_InvalidDraft, match="governing_law names"):
        _parse_and_ground(_full_draft_json({}, "C1", governing_law), {"C1": _result(1)})


def test_parse_and_ground_requires_the_named_statute_to_be_cited_by_the_clause_itself():
    """Retrieved is not enough: the governing_law clause must cite an excerpt
    from the statute it names, so the citation backs the name."""
    mejelle = _result(2)
    mejelle.source_title, mejelle.source_citation = "مجلة الأحكام العدلية", None
    context = {"C1": mejelle, "C2": _result(1)}

    with pytest.raises(_InvalidDraft, match="governing_law names"):
        _parse_and_ground(_full_draft_json({}, "C1", f"تسري عليه أحكام {RENT_LAW}."), context)


class _ScriptedLLM:
    def __init__(self, replies: list[str]):
        self._replies = list(replies)
        self.prompts: list[str] = []

    async def chat(self, system: str, user: str, *, json_mode: bool = False, max_tokens: int | None = None) -> str:
        self.prompts.append(user)
        return self._replies.pop(0)


def test_generate_contract_fails_closed_with_no_retrieval(monkeypatch):
    async def _empty_search(*args, **kwargs):
        return [[] for _ in kwargs["queries"]]

    monkeypatch.setattr(gc, "search_many", _empty_search)

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
        return [[seeded] for _ in kwargs["queries"]]

    monkeypatch.setattr(gc, "search_many", _fake_search)

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


def test_generate_contract_retries_a_draft_that_names_an_uncited_statute(monkeypatch):
    seeded = _result(1)

    async def _fake_search(*args, **kwargs):
        return [[seeded] for _ in kwargs["queries"]]

    monkeypatch.setattr(gc, "search_many", _fake_search)
    invented = "تسري على هذا العقد أحكام قانون المالكين والمستأجرين رقم (7) لسنة 1958."
    grounded = f"تسري على هذا العقد أحكام {RENT_LAW}."
    llm = _ScriptedLLM([_full_draft_json({}, "C1", invented), _full_draft_json({}, "C1", grounded)])

    result = asyncio.run(
        generate_contract(
            pool=None, llm=llm, embedder=None, jurisdiction_id=JURISDICTION_ID,
            contract_type="rent", parties=[{"name": "A"}], property={"address": "Gaza"},
        )
    )

    [governing_law] = [c for c in result.clauses if c.clause_kind == "governing_law"]
    assert governing_law.content == grounded
    # The model is shown each excerpt's source, and told what it got wrong.
    assert f"[C1] ({RENT_LAW})" in llm.prompts[0]
    assert "رقم (7) لسنة 1958" in llm.prompts[1]


def test_generate_contract_is_idempotent_for_the_same_input(monkeypatch):
    """Re-drafting the same request must not touch the LLM again — if it did,
    this second scripted reply ("not json") would make it fail closed."""
    seeded = _result(1)

    async def _fake_search(*args, **kwargs):
        return [[seeded] for _ in kwargs["queries"]]

    monkeypatch.setattr(gc, "search_many", _fake_search)
    llm = _ScriptedLLM([_full_draft_json({}, "C1"), "not json"])

    kwargs = dict(
        pool=None, llm=llm, embedder=None, jurisdiction_id=JURISDICTION_ID,
        contract_type="sale", parties=[{"name": "A"}], property={"address": "Gaza"},
    )
    first = asyncio.run(generate_contract(**kwargs))
    second = asyncio.run(generate_contract(**kwargs))

    assert second is first


def test_generate_contract_fails_closed_after_max_attempts(monkeypatch):
    async def _fake_search(*args, **kwargs):
        return [[_result(1)] for _ in kwargs["queries"]]

    monkeypatch.setattr(gc, "search_many", _fake_search)

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


def test_generate_contract_scopes_retrieval_to_the_contract_law_plus_general(monkeypatch):
    """A lease must not be grounded in the foreigners-ownership or tax statutes.
    Regression: before CONTRACT_LAW_TYPES, generate passed no law_type at all
    and a rent draft cited قانون ... من الأجانب رقم (40) لسنة 1953."""
    seen: list = []

    async def _recording_search(pool, embedder, **kwargs):
        seen.append(kwargs)
        return [[_result(1)] for _ in kwargs["queries"]]

    monkeypatch.setattr(gc, "search_many", _recording_search)

    class _LLM:
        async def chat(self, system, user, *, json_mode=False, max_tokens=None):
            return _full_draft_json({}, "C1")

    asyncio.run(
        generate_contract(
            None, _LLM(), None, jurisdiction_id=JURISDICTION_ID, contract_type="rent",
            parties=[{"role": "landlord", "name": "A"}], property={"address": "X"},
        )
    )

    # One batched call for all 11 clause topics, not 11 sequential ones.
    assert len(seen) == 1, f"expected one batched retrieval, got {len(seen)}"
    assert len(seen[0]["queries"]) == len(gc.CLAUSE_TOPICS)
    assert seen[0]["law_type"] == ["rent", "general"]


def test_generate_contract_falls_back_to_general_for_an_unknown_contract_type(monkeypatch):
    seen: list = []

    async def _recording_search(pool, embedder, **kwargs):
        seen.append(kwargs)
        return [[_result(1)] for _ in kwargs["queries"]]

    monkeypatch.setattr(gc, "search_many", _recording_search)

    class _LLM:
        async def chat(self, system, user, *, json_mode=False, max_tokens=None):
            return _full_draft_json({}, "C1")

    asyncio.run(
        generate_contract(
            None, _LLM(), None, jurisdiction_id=JURISDICTION_ID, contract_type="barter",
            parties=[{"role": "a", "name": "A"}], property={"address": "X"},
        )
    )

    assert [c["law_type"] for c in seen] == [["general"]]
