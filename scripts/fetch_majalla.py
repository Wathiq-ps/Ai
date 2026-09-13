"""Extract the Mejelle's statute articles from Shamela book 8502 (Hawawini ed.).

Shamela's edition interleaves Hawawini's commentary with the statute. A
paragraph carrying an article marker `(المادة N)` is statute; paragraphs with no
marker at all are his explanations (`يعني أن...`, `مثال ذلك:`,
`يتفرع على هذه القاعدة...`) and must not be retrievable as citable law (BR-25).

Do NOT try to separate them by vocalization -- measured over 40 pages, the
commentary is vocalized as heavily as the statute (~0.9 marks/letter). The
article marker is the only reliable signal.

Markers are NOT reliably at the start of a paragraph: one <p> often carries the
tail of article N and the opening of article N+1, so we scan for every marker in
the paragraph rather than anchoring at ^. Three markup defects are handled --
art. 42 tagged span.c5 not span.c2, arts. 61-63 left bare by an orphan </span>,
art. 17 preceded by a stray tanween -- by matching the marker text itself rather
than trusting the span class.

Text before the first marker of a page's FIRST paragraph continues whatever
ended the previous page: kept when that page ended on statute, dropped when it
ended on commentary.
"""

import html
import re
import sys
import time
import unicodedata
import urllib.request

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
NASS = re.compile(r'<div class="nass[^"]*"[^>]*>(.*?)</div>', re.DOTALL)
PARA = re.compile(r"<p\b[^>]*>(.*?)</p>", re.DOTALL)
TAG = re.compile(r"<[^>]+>")
# Requires the closing paren: statute markers are always parenthesised in one of
# `(المادة 34)`, `المادة (1361)`, `(المادة٨٣٩)`, `المادة 42)`, while Hawawini's
# cross-references are colon forms (`انظر المادة: ٥٩٦`) that must NOT be read as
# article starts -- matching those would splice commentary into a real article.
MARKER = re.compile(r"\(?\s*المادة\s*\(?\s*(\d+)\s*\)\s*[:\-–.]?\s*")
AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def plain(fragment: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(TAG.sub(" ", fragment))).strip()


def unvocalized(text: str) -> str:
    """Strip combining marks + tatweel so markers match `chunking.py`'s
    `_ARTICLE_ANCHOR`, which expects a bare `المادة (N)`."""
    return "".join(c for c in text if not unicodedata.combining(c)).replace("ـ", "").translate(AR_DIGITS)


def fetch(page: int) -> str | None:
    req = urllib.request.Request(f"https://shamela.ws/book/8502/{page}", headers={"User-Agent": UA})
    try:
        body = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
    except Exception as exc:  # scraper skips any bad page and continues
        print(f"page {page}: {exc}", file=sys.stderr)
        return None
    found = NASS.search(body)
    return found.group(1) if found else None


def main(out: str, last_page: int = 400) -> None:
    articles: dict[str, list[str]] = {}
    order: list[str] = []
    open_article: str | None = None
    prev_page_ended_on_statute = False

    for page in range(1, last_page + 1):
        nass = fetch(page)
        if nass is None:
            if page > 1:
                break
            continue

        paragraphs = [p for p in (plain(x) for x in PARA.findall(nass)) if p]
        for index, para in enumerate(paragraphs):
            bare = unvocalized(para)
            marks = list(MARKER.finditer(bare))

            if not marks:
                # No marker: a page-break continuation of an open article, or commentary.
                if index == 0 and prev_page_ended_on_statute and open_article:
                    articles[open_article].append(bare)
                else:
                    prev_page_ended_on_statute = False
                continue

            lead = bare[: marks[0].start()].strip()
            if lead and index == 0 and prev_page_ended_on_statute and open_article:
                articles[open_article].append(lead)

            for i, mark in enumerate(marks):
                end = marks[i + 1].start() if i + 1 < len(marks) else len(bare)
                number = mark.group(1)
                if not 1 <= int(number) <= 1851:  # the Mejelle ends at 1851
                    continue
                body = bare[mark.end() : end].strip()
                if number not in articles:
                    articles[number] = []
                    order.append(number)
                if body:
                    articles[number].append(body)
                open_article = number
            prev_page_ended_on_statute = True

        if page % 100 == 0:
            print(f"page {page}: {len(order)} articles", file=sys.stderr)
        time.sleep(0.4)

    with open(out, "w", encoding="utf-8") as fh:
        fh.write(
            "\n\n".join(f"المادة ({n})\n{' '.join(articles[n]).strip()}" for n in sorted(order, key=int)) + "\n"
        )
    print(f"DONE {len(order)} articles -> {out}", file=sys.stderr)


main(sys.argv[1])
