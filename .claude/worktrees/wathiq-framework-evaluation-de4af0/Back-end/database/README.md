# Wathiq — Database Schema

MVP schema (SRS ch. 7 §7.2, 62 use cases). PostgreSQL 17 + PostGIS + pgvector.

52 tables · 36 enums · 180 indexes · 70 check constraints · 33 triggers.

## Run order

Numeric order, no exceptions — later files add foreign keys to earlier ones.

```bash
for f in Back-end/database/[0-9]*.sql; do psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f "$f"; done
```

| File | Contents |
|---|---|
| `00_foundation.sql` | Extensions, schemas, roles, UUIDv7, money domains, Arabic normalisation, shared triggers |
| `01_reference.sql` | Tenants, currencies, countries, jurisdictions, locations |
| `02_identity.sql` | Users, profiles, RBAC, sessions & refresh rotation, one-time tokens, KYC |
| `03_property.sql` | Listings, media, ownership documents, amenities, favourites, search index |
| `04_requests.sql` | Purchase and rental requests |
| `05_contracts.sql` | Contracts, versions, clauses, templates, **state machine** |
| `06_ai_knowledge.sql` | AI jobs, analyses, findings; `knowledge` schema and embeddings |
| `07_signatures.sql` | Invitations, signature evidence, contract seals |
| `08_payments.sql` | Payments, gateway events, wallet ledger, receipts |
| `09_execution.sql` | QR handover codes, execution log, public verification view |
| `10_platform.sql` | Notifications, outbox, idempotency keys, audit log |
| `11_grants.sql` | Privileges. **Re-run after every migration.** |

## Using this from Laravel

Raw SQL is the source of truth because roughly a third of what protects this
data — triggers, partial and expression indexes, exclusion constraints,
generated columns, role grants — has no representation in Laravel's schema
builder. Wrap each file in a migration rather than translating it:

```php
public function up(): void
{
    DB::unprepared(file_get_contents(database_path('sql/05_contracts.sql')));
}
```

Eloquent works normally on top: enums arrive as strings, composite foreign keys
need no model changes, and the `id` defaults mean you never assign a primary key.

## Session variables the application must set

Two triggers read transaction-scoped GUCs. Set them in a middleware that opens
the request transaction; both degrade safely when absent.

```sql
SET LOCAL wathiq.actor_id = '<user-uuid>';               -- attributes status transitions
SET LOCAL wathiq.allow_settled_cancellation = 'on';      -- ops-only, see below
```

## Design decisions worth knowing before you edit anything

**Tenant integrity is structural.** Parents carry `unique (id, tenant_id)`;
children reference `(parent_id, tenant_id)` compositely. A cross-tenant row pair
is not "prevented by a global scope" — it fails with a foreign key violation.
Keep the pattern when you add tables.

**The contract state machine is data.** `app.contract_status_transitions_allowed`
holds the 22 legal transitions from SRS §3.7.2; a `BEFORE UPDATE` trigger rejects
everything else. Eloquent, a queue worker, and an admin running raw SQL at 2am
all obey it. Add a transition by inserting a row, not by editing code.

**Cancelling a paid contract needs an override.** FR-7.16 requires recording
cancellation's effect on payments, but refunds (FR-7.17) and transfers (FR-7.12)
are Phase 2 — SRS §7.5 says operations settles manually meanwhile. So
`awaiting_payment → cancelled` and `active → cancelled` are refused unless
`wathiq.allow_settled_cancellation` is set inside a reviewed transaction. This
is deliberate friction: it keeps UC-091 from silently dragging the whole
settlement module into the MVP.

**Signatures verify themselves.** `app.signatures.document_hash` must equal the
`content_hash` of the version being signed; a trigger checks it rather than
trusting the caller. Without that column you can prove someone signed, but not
what they agreed to.

**The wallet balance cannot drift.** `app.wallets.balance` is a cache;
`app.wallet_entries` is the append-only truth. Every insert takes `FOR UPDATE`
on the wallet, recomputes, and rejects a `balance_after` that disagrees.
Verified under concurrency: two simultaneous 400.00 debits against a 600.00
balance produce one commit and one `insufficient funds`, never an overdraft.

**Append-only means grants, not conventions.** `wathiq_app` holds `INSERT` and
`SELECT` on `audit.audit_logs` and is never granted `UPDATE`/`DELETE`. Triggers
are the second layer, catching roles that do hold the privilege. Same treatment
for contract versions, signatures, seals, ledger entries, and receipts.

**Arabic search needs normalisation, not just a stemmer.** `app.normalize_arabic`
folds alef forms, ta marbuta, alef maqsura, harakat, tatweel and Arabic-Indic
digits. Apply it to **both** indexed text and query text — applying it to only
one side silently breaks matching, and the failure looks like "search is bad"
rather than a bug.

**Money is `BIGINT` minor units + ISO code, exponent from `app.currencies`.**
JOD is 3 decimal places. A hardcoded ×100 divides every JOD amount by ten.
`app.assert_no_float_columns()` fails the build if a float column appears.

**No HNSW index at launch.** The corpus is thousands of chunks; exact search is
milliseconds and exact, and HNSW recall degrades under the restrictive
jurisdiction/law-type filters this schema is built around. The index statement
is in `06_ai_knowledge.sql`, commented, with the `hnsw.iterative_scan` setting
it needs. Enable it when measurement says so.

## CI

Run after every migration:

```sql
SELECT app.assert_privilege_invariants();     -- also calls assert_no_float_columns()
SELECT app.assert_wallet_balances_consistent();
```

The first fails if `wathiq_app` gained write access to the audit log, if
`wathiq_ai` gained read access to contracts, or if `wathiq_readonly` gained
access to KYC documents. A green migration that quietly granted one of those is
worse than a failed one.

## Verification status

Executed end to end on PostgreSQL 16.14 — all 12 files, then ~35 behavioural
assertions covering the state machine, transition history, terminal states, the
cancellation guard, version and signature immutability, document-hash matching,
duplicate-signature rejection, idempotency keys, the gateway-reference rule,
ledger consistency, overdraft rejection, replayed-callback rejection, audit
UPDATE/DELETE/TRUNCATE rejection, the privilege matrix, cross-tenant reference
rejection, rental-overlap exclusion, Arabic folding, and the concurrent-debit
race. All passed.

Two caveats on that run:

- **PostGIS and pgvector were not installed** on the test box, so
  `geography(Point,4326)` and `vector(1536)` were substituted with `text`. Every
  other object is verified; the geospatial index (`properties_geo_idx`), the
  distance/radius queries behind UC-017 and UC-025, and the embedding column
  need re-checking on a box that has both. Everything else is unaffected.
- **PostgreSQL 16, not 17.** Nothing here uses 17-only syntax, but run the suite
  on 17 before trusting it in staging.

## Open items

1. **UC-063 (Close Request) has no functional requirement.** Nothing in the SRS
   defines closure conditions or what read-only means afterwards.
   `04_requests.sql` assumes closure is terminal, reachable from `accepted` once
   the contract completes and from `pending` on withdrawal. Needs an FR before M5.
2. **Embedding dimension is pinned at 1536.** The LLM provider is undecided.
   `knowledge.kb_versions` records the model and dimension per version, so a
   change is a new version and a full re-embed — the FR-12.3 re-index flow. If
   the chosen model has a different dimension, change the column before seeding.
3. **`app.contract_status_transitions_allowed` is global, not per-tenant.** Fine
   while there is one tenant. If tenants ever need different lifecycles, this
   table grows a `tenant_id` and the trigger grows a lookup.
4. **`audit.audit_logs` is unpartitioned.** Add monthly range partitioning when
   volume justifies it. Attach new partitions; never delete rows.
