from app.chunking import chunk_document


def test_empty_text_yields_no_chunks():
    assert chunk_document("") == []
    assert chunk_document("   ") == []


def test_splits_on_arabic_article_anchors():
    text = (
        "المادة (1)\n"
        "يجب تسجيل كل عقد بيع عقاري لدى الجهة المختصة.\n\n"
        "المادة (2)\n"
        "لا يجوز التصرف بالعقار قبل تسجيل العقد."
    )
    chunks = chunk_document(text)
    assert [c.metadata["article"] for c in chunks] == ["المادة (1)", "المادة (2)"]
    assert "تسجيل" in chunks[0].content
    assert "التصرف" in chunks[1].content
    assert [c.ordinal for c in chunks] == [0, 1]


def test_splits_on_english_article_anchors():
    text = "Article 1\nEvery sale contract must be registered.\n\nArticle 2\nNo disposal before registration."
    chunks = chunk_document(text)
    assert [c.metadata["article"] for c in chunks] == ["Article 1", "Article 2"]


def test_no_anchors_falls_back_to_one_unlabeled_piece():
    chunks = chunk_document("Just some plain text with no article markers at all.")
    assert len(chunks) == 1
    assert chunks[0].metadata == {}


def test_oversized_article_body_splits_further_but_keeps_label():
    paragraph = "This is a filler sentence about real estate law. " * 20  # > 200 chars
    text = f"Article 1\n{paragraph}\n\n{paragraph}\n\n{paragraph}"
    chunks = chunk_document(text, max_chars=200)
    assert len(chunks) > 1
    assert all(c.metadata["article"] == "Article 1" for c in chunks)
    assert [c.ordinal for c in chunks] == list(range(len(chunks)))


def test_token_count_is_positive_and_roughly_length_over_four():
    chunks = chunk_document("Article 1\nA reasonably short article body.")
    assert chunks[0].token_count > 0
    assert chunks[0].token_count == max(1, len(chunks[0].content) // 4)
