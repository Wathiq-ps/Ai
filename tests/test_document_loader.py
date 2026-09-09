import pytest

from app.document_loader import UnsupportedDocumentFormat, load_corpus_file


def test_loads_text_file_and_returns_repo_relative_raw_path(tmp_path):
    corpus_dir = tmp_path / "corpus"
    corpus_dir.mkdir()
    (corpus_dir / "majalla.txt").write_text("  المادة (1): نص  \n", encoding="utf-8")

    text, raw_path = load_corpus_file("majalla.txt", corpus_dir=corpus_dir)

    assert text == "المادة (1): نص"
    assert raw_path == "corpus/majalla.txt"


def test_loads_from_a_subdirectory(tmp_path):
    corpus_dir = tmp_path / "corpus"
    (corpus_dir / "west_bank").mkdir(parents=True)
    (corpus_dir / "west_bank" / "law49.txt").write_text("content", encoding="utf-8")

    text, raw_path = load_corpus_file("west_bank/law49.txt", corpus_dir=corpus_dir)

    assert text == "content"
    assert raw_path == "corpus/west_bank/law49.txt"


def test_rejects_unsupported_extension(tmp_path):
    corpus_dir = tmp_path / "corpus"
    corpus_dir.mkdir()
    (corpus_dir / "scan.pdf").write_bytes(b"%PDF-1.4")

    with pytest.raises(UnsupportedDocumentFormat):
        load_corpus_file("scan.pdf", corpus_dir=corpus_dir)


def test_missing_file_raises(tmp_path):
    corpus_dir = tmp_path / "corpus"
    corpus_dir.mkdir()

    with pytest.raises(FileNotFoundError):
        load_corpus_file("missing.txt", corpus_dir=corpus_dir)


def test_path_traversal_is_rejected(tmp_path):
    corpus_dir = tmp_path / "corpus"
    corpus_dir.mkdir()
    (tmp_path / "secret.txt").write_text("nope", encoding="utf-8")

    with pytest.raises(ValueError):
        load_corpus_file("../secret.txt", corpus_dir=corpus_dir)
