import asyncio
import json
import uuid
from datetime import date

import pytest

import app.analyze_contract as ac
from app.analyze_contract import (
    AnalysisFailed,
    Finding,
    _InvalidAnalysis,
    _parse_and_ground,
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
    )


def _analysis_json(findings: list[dict]) -> str:
    return json.dumps({"summary_ar": "ملخص", "summary_en": "summary", "findings": findings})


def _finding(**overrides) -> dict:
    entry = {
        "kind": "missing_clause",
        "severity": "high",
        "title_ar": "بند مفقود",
        "title_en": "Missing clause",
        "description": "No dispute resolution clause.",
        "suggested_text": "Add one.",
        "cites": ["C1"],
        "confidence": 0.8,
    }
    entry.update(overrides)
    return entry


def test_parse_and_ground_hydrates_real_citations_from_context():
    context = {"C1": _result(1)}

    findings, summary_ar, summary_en = _parse_and_ground(_analysis_json([_finding()]), context)

    assert (summary_ar, summary_en) == ("ملخص", "summary")
    assert len(findings) == 1
    citation = findings[0].citations[0]
    assert citation.source_id == context["C1"].source_id
    assert citation.chunk_id == context["C1"].chunk_id
    assert citation.article_ref == context["C1"].article


def test_parse_and_ground_accepts_a_clean_contract():
    findings, _, _ = _parse_and_ground(_analysis_json([]), {"C1": _result(1)})

    assert findings == []
    assert risk_score(findings) == 0


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
        kind="risk", severity=severity, title_ar="a", title_en="b", description="c",
        suggested_text=None, citations=[], confidence=0.5,
    )


def test_risk_score_is_deterministic_severity_weighted_and_capped():
    assert risk_score([]) == 0
    assert risk_score([_built("low")]) == 3
    assert risk_score([_built("critical")]) == 35
    assert risk_score([_built("high"), _built("medium")]) == 26
    assert risk_score([_built("critical")] * 10) == 100


class _ScriptedLLM:
    def __init__(self, replies: list[str]):
        self._replies = list(replies)

    async def chat(self, system: str, user: str, *, json_mode: bool = False, max_tokens: int | None = None) -> str:
        return self._replies.pop(0)


def _run(llm, monkeypatch, results):
    async def _fake_search(*args, **kwargs):
        return results

    monkeypatch.setattr(ac, "search", _fake_search)
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

    findings, _, _ = _parse_and_ground(_analysis_json([_finding(description=value)]), context)

    assert findings[0].description == value
