# Verify the four seeded knowledge sources (AI retrieval is dark until you do)

## Problem

`knowledge.sources` holds four West Bank law sources, all with
`is_verified = false`:

| id | law_type | title |
|----|----------|-------|
| `01a08684-2ed6-7beb-841d-99c3159d5ee8` | general | مجلة الأحكام العدلية |
| `01a08684-3bbe-748f-a9d8-1d0fa4385d71` | rent | قانون المالكين والمستأجرين رقم (62) لسنة 1953 |
| `01a08684-3e37-77e5-9e71-ad97bb8433cf` | tax | قانون ضريبة الأبنية والأراضي رقم (11) لسنة 1954 |
| `01a08684-409d-73d4-bccf-4ac7f568be6e` | ownership | قانون إيجار وبيع الأموال غير المنقولة من الأجانب رقم (40) لسنة 1953 |

The knowledge base on top of them is built and active — `kb_versions` row
`real-corpus-v1`, 1714 chunks, real embeddings.

`app/knowledge.py`'s `search()` filters on `s.is_verified` per BR-24, so with
these four unverified it returns **zero rows for every query**, and both agents
then fail closed (BR-28) exactly as designed. Measured live today: full index
present, `search()` → 0 hits. Lifting only that filter in a read-only
diagnostic gives macro recall 1.00 @ k=5 over a 15-query Arabic golden set, so
the retrieval stack itself is working. Verification is the only thing between
the current state and a working end-to-end demo.

## Why the AI service can't do it itself

`sources_verified_complete` requires a verifier whenever the flag is set:

```
CHECK ((is_verified = false) OR ((verified_by IS NOT NULL) AND (verified_at IS NOT NULL)))
sources_verified_by_fkey  FOREIGN KEY (verified_by) REFERENCES app.users(id) ON DELETE RESTRICT
```

`wathiq_ai` has `INSERT/SELECT/UPDATE/DELETE` on `knowledge.*` but no select on
`app.users`:

```
select count(*) from app.users;
ERROR:  permission denied for table users
```

So it cannot obtain a `verified_by` value, and a fabricated uuid is rejected by
the foreign key. This grant is correct and should not be widened —
verification is a human admin act and belongs on the Laravel side. That is
also what `SPRINT4_NEXT_STEPS.md` assumed when the reindex endpoint was
specified: the AI service *receives* verified source ids, it never creates
them.

## Requested change

The real deliverable is the KB admin verification flow already scheduled in
Sprint 7 ("KB admin endpoints: CRUD sources/documents + verification
workflow, trigger reindex"). Two parts, in whatever order suits you:

1. **An admin-only verify action** on `knowledge.sources` — set
   `is_verified = true`, `verified_at = now()`, `verified_by = auth()->id()`.
   `verified_by` must be the acting admin, not a system account: that column
   is the audit trail for who vouched for a body of law (BR-24 / NFR-12.3).
2. **A reindex trigger after verification.** The AI service already exposes it
   — `POST /v1/jobs` with `kind: "reindex"`, `jurisdiction_id`, and an
   optional `payload.tag` / `payload.notes`; 202 + a signed callback when the
   rebuild finishes. Verification does not itself require a rebuild (the
   chunks are already indexed and the filter is evaluated at query time), but
   any later source edit does.

**Interim, if the admin UI is further out than the demo:** a one-off artisan
command or tinker statement is enough to unblock us, as long as a real admin
user id goes in:

```php
DB::table('knowledge.sources')
    ->where('jurisdiction_id', $palestineJurisdictionId)
    ->update([
        'is_verified' => true,
        'verified_at' => now(),
        'verified_by' => $adminUserId,   // a real app.users row
    ]);
```

## Please don't seed this as "verified" on fresh databases

Unlike the jurisdiction row (see `ISSUE_jurisdiction_seeder.md`), this should
**not** become a seeder default. `LAW_CORPUS_RESEARCH.md` records that the
statute identification is web-sourced and has had no legal review, and one of
the four (`مجلة الأحكام العدلية`) is the only text confirmed common across
territories. A seeder that marks sources verified would put a false audit
trail in every environment including production. Verification should stay an
explicit act by a named admin.

## Verifying

After the change, from the AI service:

```
uv run python scripts/run_eval.py 5
```

Expect macro recall 1.00 over the 15-query golden set (today it is 0.00 —
every query returns nothing). The two live smoke tests then also become
runnable:

```
WATHIQ_DB_TESTS=1 uv run pytest tests/test_generate_contract_live.py tests/test_analyze_contract_live.py
```
