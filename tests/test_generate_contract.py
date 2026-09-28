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


RENT = gc.clause_kinds("rent")


def _full_draft_json(
    context: dict, cite_label: str, governing_law: str = "governing_law text", kinds: list[str] = CLAUSE_KINDS
) -> str:
    return json.dumps(
        {
            "clauses": [
                {"clause_kind": k, "content": governing_law if k == "governing_law" else f"{k} text", "cites": [cite_label]}
                for k in kinds
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
            law=context["C1"].source_title,
        )
    ]
    # Each clause keeps its own citations, so a reviewer sees which law backs which term.
    assert all(c.citations == citations for c in clauses)


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
    llm = _ScriptedLLM([_full_draft_json({}, "C1", invented, kinds=RENT), _full_draft_json({}, "C1", grounded, kinds=RENT)])

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
            return _full_draft_json({}, "C1", kinds=RENT)

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


def test_sale_retrieval_covers_the_registry_and_tax_laws_and_asks_no_lease_question(monkeypatch):
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
            None, _LLM(), None, jurisdiction_id=JURISDICTION_ID, contract_type="sale",
            parties=[{"role": "seller", "name": "A"}, {"role": "buyer", "name": "B"}], property={"address": "Y"},
        )
    )

    [call] = seen
    assert call["law_type"] == ["sale", "ownership", "tax", "general"]
    assert len(call["queries"]) == len(CLAUSE_KINDS)
    assert not any("contract duration" in q for q in call["queries"])
    assert any("Land Registry" in q for q in call["queries"])


def _system_prompt(contract_type: str) -> str:
    system, _user = gc._build_prompt(
        contract_type, [{"role": "x", "name": "A"}], {"address": "X"}, None, "ar", {"C1": _result(1)}
    )
    return system


def test_sale_prompt_drafts_a_sale_agreement_between_seller_and_buyer():
    system = _system_prompt("sale")

    assert "اتفاقية بيع" in system
    assert "الطرف الأول (البائع)" in system and "الطرف الثاني (المشتري)" in system
    assert all(note in system for note in gc.SALE_DRAFTING_NOTES.values())
    assert "ownership passes to the buyer only when the sale is registered" in system
    assert "a sale between two Palestinians" in system
    # None of the lease wording leaks into a sale.
    for lease in ("عقد إيجار", "(المؤجر)", "(المستأجر)", "[تاريخ بدء الإجارة]", "a lease between"):
        assert lease not in system


def test_rent_prompt_keeps_its_lease_wording():
    """Rent is live: the per-type split must not change a word of its prompt."""
    system = _system_prompt("rent")

    assert "the plain, operative register of a عقد إيجار executed before الكاتب العدل" in system
    assert "an excerpt about foreigners, sales or taxes has no place in a lease between two Palestinians." in system
    assert "a bracketed blank such as [تاريخ بدء الإجارة] rather than" in system
    assert all(f"- {kind}: {gc.DRAFTING_NOTES[kind]}" in system for kind in CLAUSE_KINDS)
    assert "البائع" not in system and "دائرة تسجيل الأراضي" not in system


def test_sale_is_draftable():
    assert gc.DRAFTABLE_CONTRACT_TYPES == {"rent", "sale"}


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


def test_different_terms_reach_the_prompt_as_different_drafts(monkeypatch):
    """Laravel knows the rent and the dates; the draft must use them instead of
    leaving [bracketed blanks] the analysis then flags as incomplete."""
    prompts: list[str] = []

    async def _fake_search(*args, **kwargs):
        return [[_result(1)] for _ in kwargs["queries"]]

    monkeypatch.setattr(gc, "search_many", _fake_search)

    class _LLM:
        async def chat(self, system, user, *, json_mode=False, max_tokens=None):
            prompts.append(user)
            return _full_draft_json({}, "C1", kinds=RENT)

    kwargs = dict(
        pool=None, llm=_LLM(), embedder=None, jurisdiction_id=JURISDICTION_ID, contract_type="rent",
        parties=[{"name": "A"}], property={"address": "Ramallah"},
    )
    asyncio.run(generate_contract(**kwargs, terms={"price": "450.00", "currency": "JOD"}))
    asyncio.run(generate_contract(**kwargs, terms={"price": "500.00", "currency": "JOD"}))

    assert "450 (أربعمائة وخمسون)" in prompts[0]
    assert len(prompts) == 2


def _drafted_prompt(monkeypatch, terms: dict, language: str = "ar") -> str:
    async def _fake_search(*args, **kwargs):
        return [[_result(1)] for _ in kwargs["queries"]]

    monkeypatch.setattr(gc, "search_many", _fake_search)
    llm = _ScriptedLLM([_full_draft_json({}, "C1", kinds=RENT)])
    asyncio.run(
        generate_contract(
            pool=None, llm=llm, embedder=None, jurisdiction_id=JURISDICTION_ID, contract_type="rent",
            parties=[{"name": "A"}], property={"address": "Ramallah"}, terms=terms, language=language,
        )
    )
    [prompt] = llm.prompts
    return prompt


def test_a_supplied_price_reaches_the_prompt_in_digits_and_words(monkeypatch):
    """Regression: a draft read "450.000 دينار أردني (JOD)" and a reviewer
    took 450.000 for four hundred fifty thousand. The model now gets the
    amount already stated in digits and words, and never sees the raw decimal
    or the currency code to copy."""
    prompt = _drafted_prompt(
        monkeypatch,
        {"price": "450.000", "currency": "JOD", "price_unit": "per_month", "starts_on": "2026-10-01"},
    )

    assert '"price_ar": "450 (أربعمائة وخمسون) ديناراً أردنياً"' in prompt
    assert '"price_unit_ar": "شهرياً"' in prompt
    assert '"starts_on": "1/10/2026"' in prompt
    for raw in ("450.000", "JOD", "per_month"):
        assert raw not in prompt


@pytest.mark.parametrize(
    ("terms", "language"),
    [
        ({"starts_on": "not a date"}, "ar"),  # no price: still a bracketed blank
        ({"price": "450", "currency": "GBP"}, "ar"),  # no Arabic name on file
        ({"price": "450", "currency": "JOD", "price_unit": "per_month"}, "en"),  # English draft
    ],
)
def test_terms_without_a_statable_arabic_price_reach_the_prompt_unchanged(monkeypatch, terms, language):
    prompt = _drafted_prompt(monkeypatch, terms, language)

    assert f"Terms: {json.dumps(terms, ensure_ascii=False)}\n" in prompt
    assert "price_ar" not in prompt


def test_arabic_terms_carry_day_first_dates(monkeypatch):
    """An Arabic contract writes 1/11/2026, not the ISO 2026-11-01 the model copied."""
    prompt = _drafted_prompt(monkeypatch, {"starts_on": "2026-11-01", "ends_on": "2027-10-31"})

    assert '"starts_on": "1/11/2026", "ends_on": "31/10/2027"' in prompt


def test_the_property_reaches_an_arabic_prompt_under_arabic_labels():
    """Regression: `rooms: 3` was drafted as "الشقة رقم 3" — an apartment number
    nobody supplied. The model now reads what each value means."""
    shown = gc._prompt_property(
        {"type": "apartment", "rooms": 3, "floor_number": 2, "is_furnished": False, "basin_name": "X"}, "ar"
    )

    assert shown == {"نوع العقار": "شقة", "عدد الغرف": 3, "رقم الطابق": 2, "مفروش": "لا", "basin_name": "X"}
    assert gc._prompt_property({"rooms": 3}, "en") == {"rooms": 3}


def test_retrieval_queries_do_not_depend_on_the_property(monkeypatch):
    """Fixed per contract type, so their embeddings are reusable across drafts."""
    seen: list = []

    async def _recording_search(pool, embedder, **kwargs):
        seen.append(kwargs["queries"])
        return [[_result(1)] for _ in kwargs["queries"]]

    monkeypatch.setattr(gc, "search_many", _recording_search)

    class _LLM:
        async def chat(self, system, user, *, json_mode=False, max_tokens=None):
            return _full_draft_json({}, "C1", kinds=RENT)

    for address in ("Ramallah", "Nablus"):
        asyncio.run(
            generate_contract(
                None, _LLM(), None, jurisdiction_id=JURISDICTION_ID, contract_type="rent",
                parties=[{"role": "landlord", "name": "A"}], property={"address": address},
            )
        )

    assert seen[0] == seen[1]


def test_a_clause_that_quotes_the_law_is_sent_back():
    """Regression: told not to recite a rule, the model quoted it instead."""
    context = {"C1": _result(1)}
    raw = json.loads(_full_draft_json(context, "C1"))
    raw["clauses"][3]["content"] = "يحق للمؤجر 'فسخ العقد في حال تأخر المستأجر عن السداد لمدة تزيد عن ثلاثين يوماً'."

    with pytest.raises(gc._InvalidDraft, match="quotes text"):
        _parse_and_ground(json.dumps(raw), context)

    raw["clauses"][3]["content"] = 'ويشار إلى العقار فيما يلي بـ "المأجور".'
    _parse_and_ground(json.dumps(raw), context)


def test_a_stray_label_is_dropped_but_a_clause_citing_nothing_real_is_sent_back():
    context = {"C1": _result(1)}
    raw = json.loads(_full_draft_json(context, "C1"))
    raw["clauses"][5]["cites"] = ["C1", "C99"]

    clauses, _ = _parse_and_ground(json.dumps(raw), context)
    assert [c.chunk_id for c in clauses[5].citations] == [context["C1"].chunk_id]

    raw["clauses"][5]["cites"] = ["C99"]
    with pytest.raises(gc._InvalidDraft, match="cites no label"):
        _parse_and_ground(json.dumps(raw), context)


def test_a_lease_carries_the_standard_forms_mechanics_in_contract_order():
    """Deposit, utilities, maintenance, handover and access are conditions
    every WB/Jordanian residential form carries; the 11 kinds had none of them."""
    assert set(RENT) - set(CLAUSE_KINDS) == {"deposit", "utilities", "maintenance", "handover", "inspection"}
    assert gc.clause_kinds("sale") == CLAUSE_KINDS
    assert gc.clause_kinds(None) == CLAUSE_KINDS

    context = {"C1": _result(1)}
    raw = json.loads(_full_draft_json(context, "C1", kinds=RENT))
    raw["clauses"].reverse()  # the model's order is not the contract's
    for entry in raw["clauses"]:
        if entry["clause_kind"] in gc.CITATION_OPTIONAL_KINDS:
            entry["cites"] = []

    clauses, _ = _parse_and_ground(json.dumps(raw), context, RENT)

    assert [c.clause_kind for c in clauses] == RENT
    assert next(c for c in clauses if c.clause_kind == "deposit").citations == []

    # A lease missing its deposit clause goes back for repair.
    raw["clauses"] = [e for e in raw["clauses"] if e["clause_kind"] != "deposit"]
    with pytest.raises(gc._InvalidDraft, match="deposit"):
        _parse_and_ground(json.dumps(raw), context, RENT)


def test_the_lease_notes_follow_west_bank_law_on_expiry_and_notice():
    """Law 62/1953: the end of the term is not a ground to evict, and the
    notice period must be written out — the draft said «المدة القانونية»."""
    system = _system_prompt("rent")

    assert "the end of the term is not by itself a ground to evict" in system
    assert "write that number of days out" in system
    assert "- deposit:" in system and "- inspection:" in system
    assert "- deposit:" not in _system_prompt("sale")


def test_a_deposit_is_stated_in_the_rents_currency_in_digits_and_words(monkeypatch):
    prompt = _drafted_prompt(monkeypatch, {"price": "450", "currency": "JOD", "deposit": "900"})

    assert '"deposit_ar": "900 (تسعمائة) دينار أردني"' in prompt
    assert '"deposit"' not in prompt


def test_parties_reach_an_arabic_prompt_under_arabic_labels():
    shown = gc._prompt_parties(
        [{"role": "landlord", "name": "أحمد", "document_type": "national_id", "document_number": "401"}], "ar"
    )
    assert shown == [{"role": "landlord", "الاسم": "أحمد", "نوع وثيقة الهوية": "بطاقة هوية", "رقم وثيقة الهوية": "401"}]
