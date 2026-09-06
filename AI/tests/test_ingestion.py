import hashlib

from app.ingestion import detect_language, sha256_checksum


def test_sha256_checksum_matches_hashlib():
    raw = "some legal text".encode("utf-8")
    assert sha256_checksum(raw) == hashlib.sha256(raw).hexdigest()
    assert len(sha256_checksum(raw)) == 64


def test_detect_language_arabic():
    assert detect_language("هذا نص قانوني باللغة العربية يخص عقد البيع") == "ar"


def test_detect_language_english():
    assert detect_language("This is a legal text regarding a sale contract") == "en"


def test_detect_language_empty_defaults_to_en():
    assert detect_language("123 456") == "en"
