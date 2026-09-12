import math

from app.retrieval_eval import GoldenQuery, load_golden_set, macro_average, score_query


def _query(articles):
    return GoldenQuery(id="q", question="?", articles=articles)


def test_perfect_retrieval_scores_one():
    score = score_query(_query(["المادة (4)"]), ["المادة (4)"])

    assert (score.recall, score.precision, score.iou, score.f_beta) == (1.0, 1.0, 1.0, 1.0)


def test_whitespace_variants_of_an_article_label_still_match():
    score = score_query(_query(["المادة (4)"]), ["المادة ( 4 )"])

    assert score.recall == 1.0


def test_bis_articles_are_not_the_same_article():
    score = score_query(_query(["المادة (4)"]), ["المادة (4 مكرر)"])

    assert score.recall == 0.0
    assert score.iou == 0.0


def test_extra_results_cost_precision_but_f2_still_favours_recall():
    score = score_query(_query(["المادة (4)"]), ["المادة (4)", "المادة (7)", "المادة (8)"])

    assert score.recall == 1.0
    assert math.isclose(score.precision, 1 / 3)
    assert score.f_beta > score.precision  # beta=2 weights recall above precision


def test_empty_retrieval_scores_zero_not_an_error():
    score = score_query(_query(["المادة (4)"]), [])

    assert (score.recall, score.precision, score.f_beta) == (0.0, 0.0, 0.0)


def test_macro_average_over_no_scores_is_zero():
    assert macro_average([]) == {"recall": 0.0, "precision": 0.0, "iou": 0.0, "f_beta": 0.0}


def test_shipped_golden_set_loads_and_is_well_formed():
    queries = load_golden_set()

    assert len(queries) >= 10
    assert all(q.question.strip() and q.articles for q in queries)
    assert len({q.id for q in queries}) == len(queries)
