"""Sprint 5 (1B') — RAG eval harness.

Scores `search()` against a hand-built golden set of question -> article
references (eval/golden_set.jsonl). The unit of truth is the *article label*
(`المادة (4)`), not the chunk id: chunk ids move on every reindex, article
numbers don't, so a golden set written today survives re-chunking.

Metrics per query, then macro-averaged:
  recall    = hit articles / expected articles     (did we find the law?)
  precision = hit articles / retrieved articles    (how much noise came with it)
  iou       = |hit| / |expected u retrieved|
  f_beta    = weighted harmonic mean; beta > 1 favours recall, which is what
              legal retrieval wants — a missed article is worse than an extra.

ponytail: article labels are not unique across statutes (every law has a
`المادة (4)`), so each golden entry carries the `law_type` its answer lives in
and the runner passes it to `search()` as a filter. Score by document_id too
if a single law_type ever holds more than one statute.
"""

import json
from dataclasses import dataclass
from pathlib import Path

GOLDEN_SET_PATH = Path(__file__).resolve().parent.parent / "eval" / "golden_set.jsonl"
DEFAULT_BETA = 2.0


@dataclass
class GoldenQuery:
    id: str
    question: str
    articles: list[str]
    law_type: str | None = None


@dataclass
class QueryScore:
    id: str
    recall: float
    precision: float
    iou: float
    f_beta: float
    expected: list[str]
    retrieved: list[str]


def load_golden_set(path: Path = GOLDEN_SET_PATH) -> list[GoldenQuery]:
    entries = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [
        GoldenQuery(id=e["id"], question=e["question"], articles=e["articles"], law_type=e.get("law_type"))
        for e in entries
    ]


def score_query(query: GoldenQuery, retrieved_articles: list[str | None], beta: float = DEFAULT_BETA) -> QueryScore:
    expected = {_normalize(a) for a in query.articles}
    retrieved = {_normalize(a) for a in retrieved_articles if a}
    hits = expected & retrieved

    recall = len(hits) / len(expected) if expected else 0.0
    precision = len(hits) / len(retrieved) if retrieved else 0.0
    union = expected | retrieved
    iou = len(hits) / len(union) if union else 0.0

    return QueryScore(
        id=query.id,
        recall=recall,
        precision=precision,
        iou=iou,
        f_beta=_f_beta(precision, recall, beta),
        expected=sorted(expected),
        retrieved=sorted(retrieved),
    )


def macro_average(scores: list[QueryScore]) -> dict[str, float]:
    if not scores:
        return {"recall": 0.0, "precision": 0.0, "iou": 0.0, "f_beta": 0.0}
    return {
        metric: round(sum(getattr(s, metric) for s in scores) / len(scores), 4)
        for metric in ("recall", "precision", "iou", "f_beta")
    }


def _f_beta(precision: float, recall: float, beta: float) -> float:
    if precision == 0.0 and recall == 0.0:
        return 0.0
    b2 = beta * beta
    return (1 + b2) * precision * recall / (b2 * precision + recall)


def _normalize(article: str) -> str:
    """Article labels differ only by whitespace across sources — `المادة (4)`
    vs `المادة ( 4 )`. Everything else (bis suffixes, digits) is significant."""
    return " ".join(article.split()).replace("( ", "(").replace(" )", ")")
