"""Measure how well deepseek-flash reads Arabic document images (DOCUMENT_IMAGES.md).

    uv run python scripts/ocr_eval.py page1.jpg page2.png
    uv run python scripts/ocr_eval.py page1.jpg --reference page1.txt

One call per image, thinking off, in parallel. Prints time, tokens and — when a
reference text is given — the character error rate. Each transcription is
written next to its image as <image>.ocr.txt. Spends real tokens (about $0.001
a page); needs DEEPSEEK_API_KEY.
"""

import argparse
import asyncio
import base64
import mimetypes
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from openai import AsyncOpenAI

from app.config import settings

PROMPT = (
    "Transcribe all the Arabic text in this image exactly as written, line by line, top to bottom. "
    "Do not correct, rephrase, summarise or translate. Keep numbers as they appear. "
    "Write [غير مقروء] for any word you cannot read. Output only the transcribed text."
)
_NOISE = re.compile(r"[\u064B-\u0652\u0670\u0640]")  # diacritics, tatweel


def normalise(text: str) -> str:
    """Compare letters and digits only: diacritics, punctuation and line breaks
    differ between a scan and its reference without being reading errors."""
    text = _NOISE.sub("", text).translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
    return re.sub(r"[\W_]", "", text)


def cer(reference: str, hypothesis: str) -> float:
    a, b = normalise(reference), normalise(hypothesis)
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb)))
        previous = current
    return previous[-1] / max(len(a), 1)


async def read_page(client: AsyncOpenAI, path: Path) -> tuple[str, float, int, int]:
    media_type = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    data = base64.b64encode(path.read_bytes()).decode()
    started = time.monotonic()
    response = await client.chat.completions.create(
        model=settings.chat_model,
        max_tokens=8000,
        messages=[{"role": "user", "content": [
            {"type": "text", "text": PROMPT},
            {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{data}", "detail": "high"}},
        ]}],
        extra_body={"thinking": {"type": "disabled"}},
    )
    return (
        response.choices[0].message.content or "",
        time.monotonic() - started,
        response.usage.prompt_tokens,
        response.usage.completion_tokens,
    )


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("images", nargs="+", type=Path)
    parser.add_argument("--reference", type=Path, help="known text of the page(s), for CER; one image only")
    args = parser.parse_args()
    if args.reference and len(args.images) != 1:
        parser.error("--reference scores one image at a time")
    if not settings.deepseek_api_key:
        parser.error("DEEPSEEK_API_KEY is not set")

    client = AsyncOpenAI(api_key=settings.deepseek_api_key, base_url=settings.deepseek_base_url)
    results = await asyncio.gather(*(read_page(client, path) for path in args.images))
    for path, (text, seconds, tokens_in, tokens_out) in zip(args.images, results, strict=True):
        path.with_suffix(path.suffix + ".ocr.txt").write_text(text, encoding="utf-8")
        score = f"CER={cer(args.reference.read_text(encoding='utf-8'), text):.3f}" if args.reference else ""
        unreadable = text.count("غير مقروء")
        print(f"{path.name}: {seconds:.1f}s in={tokens_in} out={tokens_out} unreadable={unreadable} {score}")


if __name__ == "__main__":
    asyncio.run(main())
