# Consuming the AI service from Laravel

For whoever builds Sprint 7 (outbox relay, webhook controller, review UI).
`openapi.yaml` is the authoritative schema; this is the part a schema cannot
tell you — what the fields *mean*, and what will bite you.

## The shape of an exchange

You `POST /v1/jobs` with `X-API-Key`. You get **202 immediately** — that
response carries no result, only `{job_id, status: "running"}`. The answer
arrives later as a signed `POST` to `LARAVEL_CALLBACK_URL`. There is no
polling endpoint. If you never get a callback, the job is lost (see
*Failure modes*).

```
Laravel ──POST /v1/jobs (X-API-Key)──▶ AI          202 {job_id, status:running}
Laravel ◀──POST callback (HMAC)────── AI          the actual result
```

Callback body, every kind, every outcome:

```json
{
  "job_id": "...",
  "kind": "generate_contract | analyze_contract | reindex",
  "status": "succeeded | failed | timed_out",
  "result": { ... } ,          // null unless succeeded
  "error": "...",              // null unless failed/timed_out
  "provenance": {
    "provider": "deepseek",
    "model_id": "deepseek-v4-flash",
    "prompt_version": "analyze-contract-v1",
    "kb_version_id": "..."
  }
}
```

**Persist `provenance` on every job.** `kb_version_id` and `prompt_version`
are how you answer "why did this contract say that" six months from now. The
knowledge base is versioned and the active version changes on every reindex —
a result is only reproducible against the version that produced it.

## Verifying the callback

`X-Wathiq-Signature: t=<unix_ts>,v1=<hex>` where the digest is
`HMAC-SHA256(AI_WEBHOOK_SECRET, "<t>.<raw_body>")`.

Verify against the **raw body**, before JSON decoding — re-encoding changes
bytes and the signature will not match. Reject if `t` is more than 5 minutes
old, and dedupe on `job_id` via `ops.webhook_deliveries` so a replayed
delivery cannot apply twice.

## `analyze_contract` — the part that needs explaining

The result has **two views of the same analysis**, deliberately.

`coverage[]` is a checklist: **always exactly 11 entries**, one per clause
kind, including clauses that are fine.

```json
{"clause_kind": "duration", "status": "incomplete",
 "note": "تُرك تاريخ بدء الإجارة وتاريخ انتهائها فارغين.",
 "citations": [ ... ]}
```

`findings[]` is the problem list. Every `coverage` entry whose status is not
`present` is **also** emitted there as a `missing_clause` finding, followed by
the model's judgement findings (`legal_conflict`, `ambiguity`, `suggestion`,
`risk`).

So: **read `findings[]` to show problems. Read `coverage[]` to show what was
checked.** A review UI that only lists findings cannot tell a lawyer "the
price clause was checked and is fine" — which is most of what they want to
know. Don't render both as one list; you will show every defect twice.

Severity on a `missing_clause` finding is assigned by *this service* from the
coverage status (`absent` → high, `incomplete` → medium), not judged by the
model. Severity on the other kinds is the model's.

### Reproducibility — read this before building anything that compares runs

Analysing the same contract twice does **not** give the same findings. Measured
over four runs of the same contract:

| | mean pairwise Jaccard | `risk_score` range | findings in every run |
|---|---|---|---|
| before the checklist | 0.36 | 43–70 | 2 of 11 |
| with the checklist | 0.48 | 35–67 | 2 of 10 |
| checklist + 3-sample vote | 0.58 | 48–67 | 4 of 11 |

The 3-sample vote is **off by default**: it costs 3x the tokens and ~2x the
wall clock (115-134s measured, against a 60s budget), because the endpoint
serialises concurrent requests. Assume single-sample behaviour unless told
otherwise.

The checklist fixes the *cardinality* of the completeness half — all 11
verdicts are always present, and their severities are assigned by this service
rather than sampled. It does **not** fix the judgement: whether a given clause
is called `present` or `incomplete` still varies between runs, which is why
the score still moves. Bit-identical output is not achievable against a hosted
reasoning model (`temperature=0` and `seed` are accepted and do not deliver
it).

Treat `risk_score` as a **band**, not a number. Do not show it to a user as a
precise figure, and do not threshold a workflow on a single point — a contract
near a band edge will cross it on re-run.

Practical consequences for you:

- **Never diff two analyses to show "what changed".** A disappeared finding
  usually means resampling, not a fixed contract.
- **Do not re-run to refresh a stored analysis.** Store the result, show it,
  and re-run only when the contract text or `kb_version_id` changes.
- A risk score is comparable only against the same `risk_rubric_version`
  **and** the same `kb_version_id`.

## `generate_contract`

`body` is `clauses[]` joined by blank lines, in a fixed order — it is derived,
not independently generated, so the two can never disagree. Render whichever
suits you, but do not expect `body` to contain anything `clauses[]` does not.

`citations[]` is **document-level, not per-clause.** The model cites by
internal label and we hydrate the real ids from our own retrieval, but the
label→clause mapping is not currently preserved. If the review UI needs "which
article backs this clause", that is a change on our side — ask.

Drafts contain `[bracketed blanks]` such as `[تاريخ بدء الإجارة]` wherever an
input was not supplied. These are deliberate, not failures — surface them as
fields to fill. A draft is **not** signable: the opening formula, تمهيد,
execution line and signature block are not part of `body`.

## Failure modes

| `status` | Meaning | What to do |
|---|---|---|
| `failed` | Fail-closed. No verified sources, KB unreachable, or the model never returned valid output after 3 attempts | Return the contract to `draft`, notify. `error` is safe to log, not to show a user |
| `timed_out` | Exceeded the 60s budget (NFR-1.1) | Same as failed. Retrying may succeed — it is a latency limit, not a verdict |
| *no callback* | The AI service died, or callback delivery failed | **We do not retry callback delivery.** Your relay needs its own timeout to move a stuck job out of `dispatched` |

An empty `findings[]` with a full `coverage[]` means the contract is sound —
that is a real result, not an error. A *missing* `coverage[]` is a bug; report
it rather than working around it.

BR-24/BR-28 mean an unverified knowledge base produces `failed`, never a
partial answer. If every job suddenly fails, check `knowledge.sources.is_verified`
before suspecting the model.

## Not built yet

- `answer_query` / `summarize` — Phase 3. Sending them today returns 202 and
  then **nothing**, forever. Do not enqueue them.
- `usage` (token counts, latency) — declared in `openapi.yaml`, never sent.
- Callback retry/redelivery on our side.

## Local

Leave `DEEPSEEK_API_KEY` / `OPENROUTER_API_KEY` unset and the service runs on
deterministic fakes — no network, no spend. Useful for exercising your relay
and webhook controller against real HTTP without real drafts.
