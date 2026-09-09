"""Document loader: local corpus files -> ingest_document() input.
See SPRINT4_NEXT_STEPS.md's "Build the document loader" item -- nothing read
`knowledge.documents.raw_path` before this (confirmed empty use in the code
and present-but-unused on the live schema).

Convention: raw source files live under CORPUS_DIR (repo-root `corpus/`),
one file per `knowledge.sources` row. `raw_path` stores the path relative to
the repo root -- stable, human-inspectable, good enough for the MVP's
single-machine deploy. Revisit if ingestion ever needs to run somewhere
without the repo checked out (e.g. object storage + a URL column instead).
"""

from pathlib import Path

CORPUS_DIR = Path(__file__).resolve().parent.parent / "corpus"

# ponytail: plain text/markdown only -- that covers Sprint 5's starting
# document. PDF/DOCX extraction (pypdf/python-docx) is a real ceiling: add
# it when an actual PDF shows up (Land Authority sources are PDF-only per
# SPRINT4_NEXT_STEPS.md) rather than guessing at an untested extractor now.
SUPPORTED_SUFFIXES = {".txt", ".md"}


class UnsupportedDocumentFormat(Exception):
    pass


def load_corpus_file(relative_path: str, corpus_dir: Path = CORPUS_DIR) -> tuple[str, str]:
    """Read one file under `corpus_dir`, return (text, raw_path).

    `raw_path` is relative to `corpus_dir`'s parent (the repo root for the
    default), exactly what `knowledge.documents.raw_path` should store.
    """
    base = corpus_dir.resolve()
    path = (base / relative_path).resolve()
    if base not in path.parents:
        raise ValueError(f"{relative_path!r} escapes {base}")
    if path.suffix.lower() not in SUPPORTED_SUFFIXES:
        raise UnsupportedDocumentFormat(f"no loader for {path.suffix!r} yet ({path.name})")
    if not path.is_file():
        raise FileNotFoundError(path)

    text = path.read_text(encoding="utf-8").strip()
    raw_path = str(path.relative_to(base.parent))
    return text, raw_path
