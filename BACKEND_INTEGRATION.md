# Consuming the AI service from Laravel

For whoever builds or maintains the Laravel side (dispatch job, webhook
controller, review UI).
`openapi.yaml` is the authoritative schema; this is the part a schema cannot
tell you — what the fields *mean*, and what will bite you.

## The shape of an exchange

You `POST /v1/jobs` (no auth header — call it over Railway's private
network, `http://ai.railway.internal:8001`). You get **202 immediately** — that
response carries no result, only `{job_id, status: "running"}`. The answer
arrives later as a signed `POST` to `LARAVEL_CALLBACK_URL`
(`https://<back-end>/api/v1/ai/callback`). There is no polling endpoint. If
you never get a callback, the job is lost (see *Failure modes*).

Only `generate_contract`, `analyze_contract` and `reindex` are accepted; any
other `kind` is a `422`. Sending the same `job_id` twice (your retry after a
slow 202) gets a 202 both times and runs the job once.

```
Laravel ──POST /v1/jobs────────────▶ AI          202 {job_id, status:running}
Laravel ◀──POST callback (HMAC)────── AI          the actual result
```

Callback body, every kind, every outcome:

```json
{
  "job_id": "...",
  "kind": "generate_contract | analyze_contract | reindex",
  "status": "succeeded | failed | timed_out",
  "result": { ... } ,          // null unless succeeded
  "error": "...",              // null unless failed/timed_out; for logs
  "error_code": "...",         // null unless failed/timed_out; see Failure modes
  "provenance": {
    "provider": "deepseek",
    "model_id": "deepseek-chat",
    "model_version": "deepseek-chat",
    "prompt_version": "analyze_contract-v1",
    "kb_version_id": "..."     // null unless succeeded
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
`risk`). Every finding carries a `clause_kind` saying which of the 11 clauses
it concerns (`other` = the contract as a whole), so a review UI can show a
judgement beside the clause it is about.

So: **read `findings[]` to show problems. Read `coverage[]` to show what was
checked.** A review UI that only lists findings cannot tell a lawyer "the
price clause was checked and is fine" — which is most of what they want to
know. Don't render both as one list; you will show every defect twice.

Severity on a `missing_clause` finding is assigned by *this service* from the
coverage status (`absent` → high, `incomplete` → medium), not judged by the
model. Severity on the other kinds is the model's.

`citations` on a `coverage` entry **can be empty, on any status.** A missing
clause is measured against this service's 11-clause checklist, not against a
statute that demands it — there is often no article that says a lease must
carry a termination clause, and demanding one only made the model invent a
citation or fail validation. Judgement findings are the claims about law, and
those still always cite (BR-25). A review UI must render an uncited coverage
entry, not treat it as malformed.

`risk_score` is two halves that cannot drown each other out: completeness —
the share of the checklist that is `absent` (weight 1) or `incomplete`
(weight 0.5), worth at most 55 — plus the judgement findings by severity,
worth at most 45. This is `risk-v2`. Under `risk-v1` (a plain severity sum
over all findings) every flawed contract scored exactly 100, because the
11-clause checklist alone overflows the cap; scores from the two rubrics are
not comparable.

`confidence` is the mean over the model's judgement findings only. Checklist
findings carry 1.0 by construction, so averaging them in pulled every report
to ~0.98. A contract with no judgement findings reports 1.0.

### Reproducibility — read this before building anything that compares runs

Analysing the same contract twice does **not** give the same findings. Measured
over four runs of the same contract, on `deepseek-v4-pro` under the `risk-v1`
rubric:

| | mean pairwise Jaccard | `risk_score` range | findings in every run |
|---|---|---|---|
| before the checklist | 0.36 | 43–70 | 2 of 11 |
| with the checklist | 0.48 | 35–67 | 2 of 10 |
| checklist + 3-sample vote | 0.58 | 48–67 | 4 of 11 |

**These three rows are history, not the current service.** Since they were
measured the model changed to `deepseek-chat`, the rubric to `risk-v2`, and
the vote now groups findings by the clause they concern rather than by the
articles they cite — which changes what "the same finding" means, so the
Jaccard column is not comparable across that line. What is measured on the
current build: three runs of the demo lease took 15–35s each and scored 38–82.
Treat the spread, not the table, as the live fact; the table is due a
re-measure.

The 3-sample vote is **on by default** (`"samples": 3`, clamped to 1–3). It
costs 3x the tokens and, because the endpoint only partly parallelises them,
under 3x the wall clock — 36s end to end measured against the 60s budget
(NFR-1.1). Drop to `"samples": 1` for a faster, noisier report.

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

Until you have somewhere of your own to store a result (Sprint 7), the AI
service covers the gap: submitting the exact same `(jurisdiction_id,
contract_type, content, samples)` again returns the exact same report from an
in-process cache, no new sampling involved — see `_analysis_cache` in
`app/analyze_contract.py`. This makes "run it again live" safe for a demo, but
it is **not** a substitute for real storage: it's per-process (an AI-service
restart clears it) and per-worker if this ever runs more than one. Build your
own store per the bullet above once Sprint 7 starts; don't depend on this
staying around.

`analyze_contract`'s job payload accepts an optional `"samples"` integer (1-3,
default 3) that sets how many independent analyses are voted on. Send 1 when
latency matters more than agreement (see NFR-1.1 in *Failure modes*).

## `generate_contract`

Only `contract_type: "rent"` can be drafted today — the drafting notes are
written for a lease. Anything else fails with `unsupported_contract_type`
rather than coming back in lease wording. Adding sale is new drafting notes
(and ideally its registration law in the KB) on this side, not a wire change.

Send `terms` (`price` as a major-unit string, `currency`, `price_unit`,
`starts_on`, `ends_on`) with whatever you know. Anything left out becomes a
`[bracketed blank]` in the draft, which the analysis then reports as
`incomplete`.

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
| `failed` | Fail-closed. `error_code` says why: `invalid_payload`, `unsupported_contract_type`, `no_verified_sources`, `llm_invalid_output`, `internal` (`no_documents` for reindex) | Return the contract to `draft`. `error` is safe to log, not to show a user |
| `timed_out` | Exceeded the 60s budget (NFR-1.1); `error_code` is `timeout` | Same as failed. Retrying may succeed — it is a latency limit, not a verdict |
| *no callback* | The AI service died mid-job, or delivery failed 3 times | We retry delivery up to 3 times (network error or 5xx), re-signed each time; a 4xx from you is final. You still need your own timeout to move a stuck job out of `running` |

A `timed_out` is not always the model's fault: the embedding provider is on a
free tier that answers 429 past 20 requests/minute, and our client waits it
out in 20s steps. A burst of jobs can therefore spend the whole 60s budget in
retrieval backoff before the LLM is ever called. If timeouts cluster, check
the embedding quota before blaming the analysis.

An empty `findings[]` with a full `coverage[]` means the contract is sound —
that is a real result, not an error. A *missing* `coverage[]` is a bug; report
it rather than working around it.

BR-24/BR-28 mean an unverified knowledge base produces `failed`, never a
partial answer. If every job suddenly fails, check `knowledge.sources.is_verified`
before suspecting the model.

## Not built yet

- `answer_query` / `summarize` — Phase 3. Sending them is a `422`.
- `usage` (token counts, latency) — declared in `openapi.yaml`, never sent.
- Drafting anything but rent (see `generate_contract`).

## Local

Leave `DEEPSEEK_API_KEY` / `OPENROUTER_API_KEY` unset and the service runs on
deterministic fakes — no network, no spend. The fake LLM does not return
JSON, so every `generate_contract`/`analyze_contract` ends in a signed
`failed` callback (`llm_invalid_output`): good for exercising your failure
path and signature check, not the happy path. For real drafts, point at the
deployed service.
