import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "ocr_eval", Path(__file__).resolve().parent.parent / "scripts" / "ocr_eval.py"
)
ocr_eval = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ocr_eval)


def test_cer_ignores_what_a_scan_cannot_be_blamed_for():
    """Diacritics, punctuation, line breaks and digit script differ between a
    scan and its reference text without being misreadings."""
    reference = "المادة (١٠٨) — البيعُ الصحيح\nهو البيع الجائز."
    assert ocr_eval.cer(reference, "المادة 108 البيع الصحيح هو البيع الجائز") == 0


def test_cer_counts_a_misread_word():
    """The kind of slip measured on 2026-09-26: الماصيون read as المصايف."""
    assert 0 < ocr_eval.cer("حي الماصيون", "حي المصايف") < 1
    assert ocr_eval.cer("", "") == 0
