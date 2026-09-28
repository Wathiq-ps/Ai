import asyncio
import json
import uuid
from datetime import date

import pytest

import app.analyze_contract as ac
from app.analyze_contract import (
    CLAUSE_KINDS,
    AnalysisFailed,
    Citation,
    ClauseCoverage,
    Finding,
    _InvalidAnalysis,
    _parse_and_ground,
    _vote,
    analyze_contract,
    risk_score,
)
from app.knowledge import SearchResult

JURISDICTION_ID = uuid.uuid4()


def _result(seed: int = 1) -> SearchResult:
    return SearchResult(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        source_id=uuid.uuid4(),
        kb_version_id=uuid.uuid4(),
        content=f"Article text {seed}",
        score=0.9,
        law_type="sale",
        article=f"Article ({seed})",
        effective_from=date(2020, 1, 1),
        effective_to=None,
        source_title="Test law",
        source_citation=None,
    )


def _coverage(**overrides) -> dict:
    """A full checklist — every clause kind present and clean unless overridden."""
    cov = {k: {"status": "present", "note": "البند مستوفٍ."} for k in CLAUSE_KINDS}
    cov.update(overrides)
    return cov


def _analysis_json(findings: list[dict], coverage: dict | None = None) -> str:
    return json.dumps(
        {
            "summary_ar": "ملخص",
            "summary_en": "summary",
            "coverage": coverage if coverage is not None else _coverage(),
            "findings": findings,
        }
    )


def _finding(**overrides) -> dict:
    entry = {
        "kind": "ambiguity",
        "clause_kind": "duration",
        "severity": "high",
        "title_ar": "صياغة غامضة",
        "title_en": "Ambiguous wording",
        "description": "The handover condition is not described.",
        "suggested_text": "Add one.",
        "cites": ["C1"],
        "confidence": 0.8,
    }
    entry.update(overrides)
    return entry


def test_parse_and_ground_hydrates_real_citations_from_context():
    context = {"C1": _result(1)}

    _cov, findings, summary_ar, summary_en = _parse_and_ground(_analysis_json([_finding()]), context)

    assert (summary_ar, summary_en) == ("ملخص", "summary")
    assert len(findings) == 1
    citation = findings[0].citations[0]
    assert citation.source_id == context["C1"].source_id
    assert citation.chunk_id == context["C1"].chunk_id
    assert citation.article_ref == context["C1"].article


def test_parse_and_ground_accepts_a_clean_contract():
    _cov, findings, _, _ = _parse_and_ground(_analysis_json([]), {"C1": _result(1)})

    assert findings == []
    assert risk_score([], findings) == 0


def test_coverage_may_report_an_absent_clause_without_citing_anything():
    """A clause the statute never mentions has nothing to cite. Requiring a
    citation here only sent the repair loop around again at ~100s a turn —
    BR-25 bans invented citations, not uncited checklist verdicts."""
    raw = _analysis_json([], _coverage(termination={"status": "absent", "note": "لا يوجد بند إنهاء."}))

    coverage, findings, _, _ = _parse_and_ground(raw, {"C1": _result(1)})

    termination = next(c for c in coverage if c.clause_kind == "termination")
    assert termination.status == "absent"
    assert termination.citations == []


@pytest.mark.parametrize(
    "raw",
    [
        "not json",
        json.dumps({"summary_en": "x", "findings": []}),  # no summary_ar
        json.dumps({"summary_ar": "x", "summary_en": " ", "findings": []}),
        json.dumps({"summary_ar": "x", "summary_en": "y"}),  # no findings array
        _analysis_json([_finding(kind="not_a_kind")]),
        _analysis_json([_finding(severity="catastrophic")]),
        _analysis_json([_finding(title_en="")]),
        _analysis_json([_finding(description=" ")]),
        _analysis_json([_finding(confidence=2)]),
    ],
)
def test_parse_and_ground_rejects_malformed_analyses(raw):
    with pytest.raises(_InvalidAnalysis):
        _parse_and_ground(raw, {"C1": _result(1)})


def _built(severity: str) -> Finding:
    return Finding(
        kind="risk", clause_kind="other", severity=severity, title_ar="a", title_en="b", description="c",
        suggested_text=None, citations=[], confidence=0.5,
    )


def _cov(status: str, kind: str = "price") -> ClauseCoverage:
    return ClauseCoverage(clause_kind=kind, status=status, note="n", citations=[])


def test_risk_score_scores_completeness_and_judgement_separately():
    clean = [_cov("present", k) for k in CLAUSE_KINDS]

    assert risk_score(clean, []) == 0
    assert risk_score(clean, [_built("low")]) == 3
    assert risk_score(clean, [_built("critical")]) == 35
    assert risk_score(clean, [_built("high"), _built("medium")]) == 26
    # Neither half can reach 100 alone — that saturation is what risk-v1 did.
    assert risk_score(clean, [_built("critical")] * 10) == 45
    assert risk_score([_cov("absent", k) for k in CLAUSE_KINDS], []) == 55
    assert risk_score([_cov("incomplete", k) for k in CLAUSE_KINDS], []) == 28
    assert risk_score([_cov("absent", k) for k in CLAUSE_KINDS], [_built("critical")] * 10) == 100


class _ScriptedLLM:
    def __init__(self, replies: list[str]):
        self._replies = list(replies)

    async def chat(self, system: str, user: str, *, json_mode: bool = False, max_tokens: int | None = None) -> str:
        return self._replies.pop(0)


def _run(llm, monkeypatch, results):
    async def _fake_search(*args, **kwargs):
        return [results for _ in kwargs["queries"]]

    monkeypatch.setattr(ac, "search_many", _fake_search)
    return asyncio.run(
        analyze_contract(
            pool=None,
            llm=llm,
            embedder=None,
            jurisdiction_id=JURISDICTION_ID,
            content="This contract is missing things.",
            contract_type="sale",
        )
    )


def test_analyze_contract_fails_closed_with_no_retrieval(monkeypatch):
    with pytest.raises(AnalysisFailed):
        _run(_ScriptedLLM([]), monkeypatch, [])


def test_analyze_contract_retries_then_succeeds(monkeypatch):
    seeded = _result(1)
    llm = _ScriptedLLM(["not json", _analysis_json([_finding(), _finding(kind="risk", severity="low")])])

    result = _run(llm, monkeypatch, [seeded])

    assert result.risk_score == 21
    assert result.kb_version_id == seeded.kb_version_id
    assert result.confidence == 0.8
    assert all(f.citations for f in result.findings)


def test_analyze_contract_gives_up_after_max_attempts(monkeypatch):
    llm = _ScriptedLLM(["not json"] * ac.MAX_ATTEMPTS)

    with pytest.raises(AnalysisFailed):
        _run(llm, monkeypatch, [_result(1)])


@pytest.mark.parametrize(
    "field, value",
    [
        ("description", "وفق C1(هـ) لا يجوز الإخلاء."),
        ("description", "تعالج المادة C3 الأمر."),
        ("title_ar", "مخالفة C2"),
        ("title_en", "Conflicts with C12"),
        ("suggested_text", "See C4 for the wording."),
    ],
)
def test_parse_and_ground_rejects_internal_labels_leaking_into_prose(field, value):
    """`C3` is a retrieval label, meaningless to the lawyer reading the report.
    A live run leaked them into descriptions ("وفق C1(هـ)"), so the parser
    rejects and lets the repair loop rewrite — the same treatment an ungrounded
    citation gets."""
    context = {"C1": _result(1)}

    with pytest.raises(_InvalidAnalysis, match="internal excerpt label"):
        _parse_and_ground(_analysis_json([_finding(**{field: value})]), context)


@pytest.mark.parametrize(
    "value",
    [
        "المادة (4) تمنع الإخلاء دون حكم.",       # article numbers are the right way to refer
        "Clause C-1 of the annex is unaffected.",  # not a bare label
        "الحد الأقصى 100 CFA.",                    # letter+digits, but not a label
    ],
)
def test_parse_and_ground_allows_prose_that_merely_looks_label_ish(value):
    context = {"C1": _result(1)}

    _cov, findings, _, _ = _parse_and_ground(_analysis_json([_finding(description=value)]), context)

    assert findings[0].description == value


def _cov_entry(kind: str, status: str) -> ClauseCoverage:
    return ClauseCoverage(clause_kind=kind, status=status, note=f"{status} note", citations=[])


def _sample(statuses: dict, findings: list[Finding]) -> tuple:
    coverage = [_cov_entry(k, statuses.get(k, "present")) for k in CLAUSE_KINDS]
    return (coverage, findings, "ملخص", "summary")


def _judgement(kind: str, article: str, clause_kind: str = "duration") -> Finding:
    return Finding(
        kind=kind, clause_kind=clause_kind, severity="medium", title_ar="عنوان", title_en="Title",
        description="desc", suggested_text=None,
        citations=[Citation(source_id=uuid.uuid4(), article_ref=article, chunk_id=uuid.uuid4(), excerpt="x")],
        confidence=0.8,
    )


def test_vote_takes_the_majority_verdict_for_each_clause():
    samples = [
        _sample({"duration": "absent"}, []),
        _sample({"duration": "present"}, []),
        _sample({"duration": "present"}, []),
    ]

    coverage, _, _, _ = _vote(samples)

    assert [c.clause_kind for c in coverage] == CLAUSE_KINDS
    assert next(c for c in coverage if c.clause_kind == "duration").status == "present"


def test_vote_breaks_a_tie_toward_the_worse_verdict():
    """A split decision on a clause must not silently clear it — a legal review
    should over-report rather than under-report."""
    samples = [_sample({"price": "absent"}, []), _sample({"price": "present"}, [])]

    coverage, _, _, _ = _vote(samples)

    assert next(c for c in coverage if c.clause_kind == "price").status == "absent"


def test_vote_keeps_findings_a_majority_raised_and_drops_one_off_flags():
    agreed = _judgement("legal_conflict", "المادة (4)")
    one_off = _judgement("suggestion", "المادة (6)")
    samples = [
        _sample({}, [agreed, one_off]),
        _sample({}, [_judgement("legal_conflict", "المادة (4)")]),
        _sample({}, [_judgement("legal_conflict", "المادة (4)")]),
    ]

    _, judgements, _, _ = _vote(samples)

    assert [(f.kind, f.citations[0].article_ref) for f in judgements] == [("legal_conflict", "المادة (4)")]


def test_vote_groups_the_same_problem_even_when_samples_cite_different_articles():
    """The vote is on kind + clause_kind, not on the articles cited. Three
    samples flagging the vague lease term against three different articles are
    one finding with a majority, not three one-offs that all get dropped."""
    samples = [
        _sample({}, [_judgement("ambiguity", "المادة (4)", "duration")]),
        _sample({}, [_judgement("ambiguity", "المادة (6)", "duration")]),
        _sample({}, [_judgement("ambiguity", "المادة (2)", "duration")]),
    ]

    _, judgements, _, _ = _vote(samples)

    assert [(f.kind, f.clause_kind) for f in judgements] == [("ambiguity", "duration")]


def test_vote_keeps_the_coverage_note_from_a_sample_that_voted_that_way():
    """The note and citations shown to the reader must come from a sample that
    actually reached that verdict, not be stitched together from the losers."""
    samples = [
        _sample({"warranties": "absent"}, []),
        _sample({"warranties": "incomplete"}, []),
        _sample({"warranties": "incomplete"}, []),
    ]

    coverage, _, _, _ = _vote(samples)
    warranties = next(c for c in coverage if c.clause_kind == "warranties")

    assert warranties.status == "incomplete"
    assert warranties.note == "incomplete note"


def test_every_clause_kind_has_an_arabic_label():
    from app.analyze_contract import CLAUSE_LABELS_AR
    from app.generate_contract import ALL_CLAUSE_KINDS

    assert set(CLAUSE_LABELS_AR) == set(ALL_CLAUSE_KINDS)


def test_a_sale_is_judged_on_its_price_and_registry_transfer_not_a_rent():
    system, _ = ac._build_prompt("عقد بيع", "sale", {"C1": _result(1)})

    assert "absent (parties, property, price, a commitment to complete the transfer at دائرة تسجيل الأراضي)" in system
    assert "[رقم القطعة]" in system
    assert "property, rent" not in system and "الإجارة" not in system


@pytest.mark.parametrize("contract_type", ["rent", None, "barter"])
def test_rent_and_untyped_reviews_keep_the_wording_analyze_shipped_with(contract_type):
    system, _ = ac._build_prompt("عقد", contract_type, {"C1": _result(1)})

    assert "absent (parties, property, rent).\n" in system
    assert "bracketed blanks such as [تاريخ بدء الإجارة] for anything" in system
    assert "دائرة تسجيل الأراضي" not in system


def test_sale_review_retrieves_the_sale_laws(monkeypatch):
    seen: list = []

    async def _recording_search(pool, embedder, **kwargs):
        seen.append(kwargs)
        return [[_result(1)] for _ in kwargs["queries"]]

    monkeypatch.setattr(ac, "search_many", _recording_search)
    asyncio.run(
        analyze_contract(
            pool=None, llm=_ScriptedLLM([_analysis_json([])] * 3), embedder=None,
            jurisdiction_id=JURISDICTION_ID, content="اتفاقية بيع شقة.", contract_type="sale",
        )
    )

    [call] = seen
    assert call["law_type"] == ["sale", "ownership", "tax", "general"]
    assert not any("contract duration" in q for q in call["queries"])


def test_summary_ar_may_not_name_clause_kinds_by_their_english_keys():
    """Regression: a summary_ar read "مكتمل في عناصره الأساسية: parties، subject، price"."""
    raw = json.loads(_analysis_json([]))
    raw["summary_ar"] = "العقد مكتمل في عناصره: parties، subject، price."

    with pytest.raises(_InvalidAnalysis, match="English keys"):
        _parse_and_ground(json.dumps(raw), {"C1": _result(1)})

    # A Latin word that merely contains a key is not one.
    raw["summary_ar"] = "العقد مكتمل (subjectively fine)."
    _parse_and_ground(json.dumps(raw), {"C1": _result(1)})


def test_an_ambiguity_restating_a_flagged_clause_is_dropped_but_a_legal_conflict_stays():
    """Regression: blank id numbers came back as both "incomplete parties" and
    an ambiguity finding saying the same thing, counted twice in risk_score."""
    coverage = [_cov_entry(k, "incomplete" if k == "parties" else "present") for k in CLAUSE_KINDS]
    judgements = [
        _judgement("ambiguity", "Article (3)", clause_kind="parties"),
        _judgement("suggestion", "Article (3)", clause_kind="parties"),
        _judgement("legal_conflict", "Article (3)", clause_kind="parties"),
        _judgement("ambiguity", "Article (4)", clause_kind="duration"),
    ]

    kept = ac._drop_restated_gaps(coverage, judgements)

    assert [(f.kind, f.clause_kind) for f in kept] == [("legal_conflict", "parties"), ("ambiguity", "duration")]


def test_every_excerpt_reaches_the_reviewer_under_its_law_title():
    """Regression: without the title the model cited the Mejelle's art. 494 as
    قانون المالكين والمستأجرين."""
    _system, user = ac._build_prompt("عقد", "rent", {"C1": _result(1)})

    assert "[C1] (Test law) Article text 1" in user


def test_vote_takes_the_summary_from_the_sample_that_agrees_with_the_result():
    """Regression: the report had no findings, but sample 1's summary described
    the two risks it alone had raised."""
    lonely = _judgement("risk", "Article (1)", clause_kind="other")
    samples = [
        (_sample({}, [lonely])[0], [lonely], "ملخص يذكر خطراً", "mentions a risk"),
        (_sample({}, [])[0], [], "ملخص نظيف", "clean summary"),
        (_sample({}, [])[0], [], "ملخص آخر", "another"),
    ]

    _coverage_, judgements, summary_ar, summary_en = _vote(samples)

    assert judgements == []
    assert (summary_ar, summary_en) == ("ملخص نظيف", "clean summary")


@pytest.mark.parametrize("cites", [[], ["C_missing"], ["C1", "C_missing"]])
def test_an_ungrounded_finding_is_left_out_and_the_rest_of_the_sample_kept(cites):
    """BR-25: a finding with no grounding is not a finding. It used to fail the
    whole sample, re-rolling 11 verdicts to drop one line (~9s a round)."""
    grounded = _finding(kind="risk", clause_kind="price")
    raw = _analysis_json([_finding(cites=cites), grounded])

    _cov, findings, _, _ = _parse_and_ground(raw, {"C1": _result(1)})

    assert [(f.kind, f.clause_kind) for f in findings] == [("risk", "price")]


def test_a_lease_is_checked_against_its_own_list_and_its_mechanics_weigh_less():
    from app.generate_contract import clause_kinds

    rent = clause_kinds("rent")
    system, _ = ac._build_prompt("عقد", "rent", {"C1": _result(1)})
    assert f"every one of these {len(rent)} clause kinds" in system

    raw = json.dumps({
        "summary_ar": "ملخص", "summary_en": "summary", "findings": [],
        "coverage": {k: {"status": "absent" if k == "deposit" else "present", "note": "ملاحظة."} for k in rent},
    })
    coverage, _f, _a, _e = _parse_and_ground(raw, {"C1": _result(1)}, rent)
    assert [c.clause_kind for c in coverage] == rent

    no_deposit = ac._coverage_finding(next(c for c in coverage if c.clause_kind == "deposit"))
    assert no_deposit.severity == "medium"  # a gap, not an unenforceable lease

    no_rent = [ClauseCoverage(k, "absent" if k == "price" else "present", "n", []) for k in rent]
    no_deposit_cov = [ClauseCoverage(k, "absent" if k == "deposit" else "present", "n", []) for k in rent]
    assert risk_score(no_rent, []) == 2 * risk_score(no_deposit_cov, [])


# --- Clauses in, ordinals out (C3) ---------------------------------------

SALE_CLAUSES = [ac.SentClause(i + 1, k, f"نص بند {k}") for i, k in enumerate(CLAUSE_KINDS)]
SENT = {c.ordinal: c for c in SALE_CLAUSES}


def test_a_finding_names_its_clause_by_label_and_takes_the_sent_kind():
    """The model points at §n; the ordinal and kind come from what was sent,
    the way a citation is hydrated from what was retrieved."""
    raw = _analysis_json([
        _finding(clause="§5", clause_kind="price"),       # kind from the sent row wins
        _finding(kind="risk", clause=None),                # the contract as a whole
        _finding(kind="suggestion", clause="§99"),         # never sent: falls back to whole
    ])

    _cov, findings, _, _ = _parse_and_ground(raw, {"C1": _result(1)}, CLAUSE_KINDS, SENT)

    assert [(f.ordinal, f.clause_kind) for f in findings] == [(5, "duration"), (None, "duration"), (None, "duration")]


def test_without_sent_clauses_findings_carry_no_ordinal():
    _cov, findings, _, _ = _parse_and_ground(_analysis_json([_finding(clause="§5")]), {"C1": _result(1)})

    assert findings[0].ordinal is None


def test_the_vote_keeps_findings_on_two_clauses_of_one_kind_apart():
    """A lawyer's second obligations clause is a second subject, not the same one."""
    first = Finding(**{**_judgement("ambiguity", "Article (1)", "obligations").__dict__, "ordinal": 6})
    second = Finding(**{**_judgement("ambiguity", "Article (1)", "obligations").__dict__, "ordinal": 12})
    samples = [_sample({}, [first, second]), _sample({}, [first, second]), _sample({}, [])]

    _coverage, judgements, _, _ = _vote(samples)

    assert sorted(f.ordinal for f in judgements) == [6, 12]


def test_coverage_lists_each_kinds_ordinals_and_a_gap_points_at_its_one_clause(monkeypatch):
    coverage = _coverage(duration={"status": "incomplete", "note": "التاريخ فارغ."})
    llm = _ScriptedLLM([_analysis_json([], coverage)] * 3)

    async def _fake_search(*args, **kwargs):
        return [[_result(1)] for _ in kwargs["queries"]]

    monkeypatch.setattr(ac, "search_many", _fake_search)
    two_obligations = [*SALE_CLAUSES, ac.SentClause(12, "obligations", "بند إضافي")]
    result = asyncio.run(analyze_contract(
        pool=None, llm=llm, embedder=None, jurisdiction_id=JURISDICTION_ID,
        content="x", contract_type="sale", clauses=two_obligations,
    ))

    by_kind = {c.clause_kind: c.ordinals for c in result.coverage}
    assert by_kind["duration"] == [5] and by_kind["obligations"] == [6, 12]
    [gap] = [f for f in result.findings if f.kind == "missing_clause"]
    assert gap.ordinal == 5


def test_each_topic_is_retrieved_with_its_own_clause_text(monkeypatch):
    """The first 2000 chars of a lease are its parties and price; the handover
    query never saw the handover clause."""
    seen: list = []

    async def _recording_search(pool, embedder, **kwargs):
        seen.extend(kwargs["queries"])
        return [[_result(1)] for _ in kwargs["queries"]]

    monkeypatch.setattr(ac, "search_many", _recording_search)
    asyncio.run(ac._retrieve_context(
        None, None, jurisdiction_id=JURISDICTION_ID, contract_type="sale", content="x", k_per_topic=5,
        clauses=[ac.SentClause(1, "price", "الثمن مائة ألف")],
    ))

    assert any("price" in q and "الثمن مائة ألف" in q for q in seen)
    assert not any("الثمن مائة ألف" in q for q in seen if "price or rent value" not in q)


def test_a_clause_label_in_prose_is_sent_back_like_an_excerpt_label():
    with pytest.raises(_InvalidAnalysis, match="internal excerpt label"):
        _parse_and_ground(_analysis_json([_finding(description="البند §5 غامض")]), {"C1": _result(1)}, CLAUSE_KINDS, SENT)
