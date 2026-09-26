# Contracts from images: reading scanned and photographed documents

Status: study, 2026-09-26. Nothing here is built yet. It answers "can Wathiq
analyse a contract someone photographed or scanned, and how should it?"

## Today: no

`analyze_contract` takes `payload.content`, a string. There is no image or PDF
path anywhere in the service: `app/document_loader.py` reads `.txt`/`.md` only,
and OCR was deferred in `WATHIQ_AI_SPRINT_PLAN.md` because the one cheap managed
option (GLM-OCR) has no Arabic, and the Arabic one (QARI-OCR) is self-host only.

## What changed

The LLM we already call reads images. `deepseek-flash` (DeepSeek-V4.1-Flash, the
model behind the old `deepseek-chat` name) accepts images in a user message as
base64, an https URL, or a Files API `file_id`: JPEG, PNG, GIF or WebP, up to
32 MiB each, 48 MiB per request. Same key, same vendor, no GPU to host.
Source: [DeepSeek vision guide](https://api-docs.deepseek.com/guides/vision/),
[models and pricing](https://api-docs.deepseek.com/quick_start/pricing/).

## Measured

One page per call, `detail: "high"`, thinking off, asked to transcribe
verbatim and write `[غير مقروء]` for anything unreadable. The score is the
character error rate (CER) against the known text, after dropping diacritics,
tatweel, punctuation and whitespace, and unifying digits.

| Page | Source | CER | Time | Tokens in / out |
|---|---|---|---|---|
| AI-drafted lease, page 1 | clean print | 1.2% | 11.3 s | 1,064 / 664 |
| same | simulated phone photo: 1.6° skew, blur, uneven light | 0.9% | 12.4 s | 1,064 / 664 |
| AI-drafted lease, page 2 | clean print | 0.1% | 9.8 s | 1,064 / 441 |
| same | simulated phone photo | 0.1% | 10.4 s | 1,064 / 446 |
| Majalla, 1876 typeset scan, arts. 108–122 | `corpus/majalla-1293h.pdf` p. 24 | 3.9%\* | 11.8 s | 1,037 / 570 |
| Ottoman disposal law, 1913 scan | `corpus/immovable-property-disposal-1331h.pdf` p. 1 | no reference text; reads cleanly | 13.7 s | 1,053 / 513 |

\* Includes wording differences between that edition and our text of it.

What the errors were:

- **Every number came back exact:** ID numbers, area, rent, article numbers.
- **Dates:** `2026-10-01` came back as `01-10-2026`. It's the same date, read in
  right-to-left order, but code comparing dates must parse them, not compare
  strings.
- **Proper nouns are where it slips:** the district `الماصيون` became `المصايف`,
  and in the statute's name `المالكين` became `الملكين`. A wrong statute name is
  exactly what the analysis would then report as a legal conflict.
- Diacritics are dropped (harmless).
- Thinking mode gave no gain (0.9% → 0.9%, 3.9% → 4.0%) and was slower.

Cost: about 1,000 image tokens plus 450–700 output tokens per page, roughly
$0.001 a page at peak prices.

Not tested yet: real phone photos of real signed contracts, handwriting,
stamps and signatures over text, folded or shadowed paper. Two of the rows
above are rendered pages, not photographs. **Before building, run the same
script on about ten real photographed Palestinian leases.**

## Recommendation: transcribe first, then analyse the text

```
photos ──extract_document──▶ text ──lawyer confirms/corrects──▶ analyze_contract (unchanged)
```

1. **A new job kind, `extract_document`.** It makes one vision call per page,
   runs the pages in parallel with thinking off, and returns the text.
2. **Laravel stores the text as a contract version** and shows it next to the
   page images, so someone confirms or corrects names, numbers and statute
   titles.
3. **`analyze_contract` runs on the confirmed text**, exactly as it does today.

Why not send the images straight into the analysis:

- Analysis looks law up by querying with the contract's text (`content[:2000]`
  seeds retrieval), so it needs text anyway.
- Findings point at clauses, and the lawyer edits clauses into new versions,
  so the contract has to exist as `contract_versions.body` / `contract_clauses`.
- The three-sample vote would pay for the images three times and add about 10 s
  a sample. Analysis already takes 29–61 s of its 60 s budget, measured today.
- A misread statute name has to be caught by a person before it turns into a
  finding, not after.
- Re-running an analysis would otherwise mean reading the images again.

## Wire proposal

Request. The images go base64 inside the job POST over the private network, so
they never need a public URL:

```json
{
  "job_id": "…", "kind": "extract_document", "jurisdiction_id": "…",
  "payload": {
    "language": "ar",
    "pages": [
      {"media_type": "image/jpeg", "data": "<base64>"},
      {"media_type": "image/jpeg", "data": "<base64>"}
    ]
  }
}
```

Result:

```json
{
  "text": "…all pages, in order…",
  "pages": [{"page": 1, "text": "…", "unreadable": 0}, {"page": 2, "text": "…", "unreadable": 3}]
}
```

- **Limits:** at most 20 pages and 5 MB a page. The app should shrink photos to
  about 2000 px on the long side before upload; the model scales to about
  1300 px anyway.
- **Budget:** the pages run in parallel, so the wall time is the slowest page
  (about 10–14 s). The job can keep the 60 s budget, with a timeout on each page.
- **Errors:** `invalid_payload` for a bad media type, too many pages or an
  oversized page. A page that comes back mostly `[غير مقروء]` is a `pages[].unreadable`
  count for the UI to flag, not a failure.
- `ErrorCode`, `app/wire.py` and `openapi.yaml` all gain the new kind, and the
  wire-contract test keeps them in step.

## Back-end work this needs

- `app.ai_job_kind` gains `extract_document` (a migration, since the enum is a
  Postgres type).
- An upload endpoint for contract page images and somewhere to store them.
- `app.contract_version_author` has `ai`, `lawyer`, `owner`, `admin` and
  `system`, but nothing that means "transcribed from an upload". Either use
  `system` and record the job id, or add a value.
- A "confirm transcription" step in the flow before *submit for analysis*.

## Also possible once this exists

- **Land Registry deeds.** Reading اسم الحوض ورقمه, رقم القطعة and رقم الشقة from
  a photographed سند تسجيل fills the blanks every sale draft has today, because
  `properties` has no columns for them.
- **Scanned statutes.** The corpus's two scanned PDFs could be ingested without
  self-hosting QARI-OCR. The 1331h law is repealed by 49/1953, so it isn't
  needed; the Majalla already has a text source.
- **KYC ID cards** are a separate flow with separate privacy rules. Don't route
  them through this job.

## Privacy

Contract text already goes to DeepSeek. Images add whatever else is on the
page: signatures, stamps, and ID cards if someone photographs them alongside.
Users should be told, and pages that aren't the contract should be left out.
