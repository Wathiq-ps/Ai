import re
from dataclasses import dataclass, field

MAX_CHUNK_CHARS = 2000

_ARTICLE_ANCHOR = re.compile(r"^\s*((?:المادة|Article)\s*\(?\d+\)?)\s*[:\-–.]?\s*", re.MULTILINE)
_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n+")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!؟?])\s+")


@dataclass
class Chunk:
    ordinal: int
    content: str
    token_count: int
    metadata: dict = field(default_factory=dict)


def _approx_token_count(text: str) -> int:
    """ponytail: chars/4 as a sizing stand-in, not a real tokenizer — good
    enough for the `token_count` metadata column, not exact. Swap for the
    embedding model's actual tokenizer once Sprint 5 finalizes one."""
    return max(1, len(text) // 4)


def _split_articles(text: str) -> list[tuple[str | None, str]]:
    """(article_label, body) pairs split at each 'Article N' / 'المادة N'
    anchor. No anchors found -> one unlabeled piece."""
    matches = list(_ARTICLE_ANCHOR.finditer(text))
    if not matches:
        return [(None, text)]

    pieces = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        pieces.append((m.group(1).strip(), text[m.start() : end].strip()))

    preamble = text[: matches[0].start()].strip()
    if preamble:
        pieces.insert(0, (None, preamble))
    return pieces


def _greedy_pack(pieces: list[str], max_chars: int) -> list[str]:
    chunks: list[str] = []
    current = ""
    for piece in pieces:
        candidate = f"{current} {piece}".strip() if current else piece
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                chunks.append(current)
            # piece itself may still exceed max_chars (one giant sentence) —
            # ponytail: kept whole rather than word-split mid-sentence; revisit
            # if oversized single-sentence chunks turn up in the real corpus.
            current = piece
    if current:
        chunks.append(current)
    return chunks


def _split_to_size(text: str, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    paragraphs = [p.strip() for p in _PARAGRAPH_SPLIT.split(text) if p.strip()]
    if len(paragraphs) <= 1:
        paragraphs = [s.strip() for s in _SENTENCE_SPLIT.split(text) if s.strip()]
    return _greedy_pack(paragraphs, max_chars)


def chunk_document(text: str, max_chars: int = MAX_CHUNK_CHARS) -> list[Chunk]:
    """Split on article-number anchors first — that's the citation unit legal
    retrieval needs (BR-25) — then paragraph, then sentence for any piece
    still over `max_chars`."""
    text = text.strip()
    if not text:
        return []

    chunks: list[Chunk] = []
    ordinal = 0
    for label, body in _split_articles(text):
        for piece in _split_to_size(body, max_chars):
            metadata = {"article": label} if label else {}
            chunks.append(
                Chunk(ordinal=ordinal, content=piece, token_count=_approx_token_count(piece), metadata=metadata)
            )
            ordinal += 1
    return chunks
