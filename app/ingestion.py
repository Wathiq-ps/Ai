import hashlib
import re

_ARABIC_CHARS = re.compile(r"[؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿]")
_LETTERS = re.compile(r"[^\W\d_]", re.UNICODE)


def sha256_checksum(raw: bytes) -> str:
    """Matches `app.sha256_hex`: lowercase 64-char hex."""
    return hashlib.sha256(raw).hexdigest()


def detect_language(text: str) -> str:
    """'ar' or 'en' — matches `app.locale`.

    ponytail: ratio of Arabic-script letters over all letters, no ML model.
    Corpus is ar/en only per Sprint 4 scope. Ceiling: garbles on transliterated
    Arabic (Latin script) or heavily mixed-script text — if that shows up,
    upgrade to a real langid library (e.g. `lingua` or `fasttext`) instead of
    tuning this regex further.
    """
    letters = _LETTERS.findall(text)
    if not letters:
        return "en"
    arabic = _ARABIC_CHARS.findall(text)
    return "ar" if len(arabic) / len(letters) > 0.5 else "en"
