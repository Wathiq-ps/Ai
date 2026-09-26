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
        _analysis_json([_finding(cites=[])]),  # BR-25
        _analysis_json([_finding(cites=["C_missing"])]),
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


def test_analyze_contract_is_idempotent_for_the_same_input(monkeypatch):
    """The live-demo risk this guards against: re-analysing the same contract
    must not silently roll new dice and hand back a different risk_score. A
    second call with identical inputs must not touch the LLM again — if it
    did, this second reply ("not json") would make it fail closed."""
    seeded = _result(1)
    llm = _ScriptedLLM([_analysis_json([_finding()]), "not json"])

    first = _run(llm, monkeypatch, [seeded])
    second = _run(llm, monkeypatch, [seeded])

    assert second is first
    assert second.risk_score == first.risk_score


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

    assert set(CLAUSE_LABELS_AR) == set(CLAUSE_KINDS)


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
