Before I put on that hat, let me look at what already exists so the plan is grounded in the repo rather than generic.


Ran 5 commands, read README.md
Backend lead: stack & roadmap
Wathiq Backend — Lead Engineer's Plan
I've read the SRS, the README's proposed stack, and the repo state. Current reality: Back-end/ is an empty .gitkeep, Mobile/ is a Flutter app already scaffolded in clean architecture, AI/ and Front/ are empty. So I'm starting the backend from zero, with 69 use cases and a mobile client that will consume my API. That shapes everything below.

Part 1 — The First Two Weeks (before a single feature ships)
I don't start with UC-037: Register. In a system where a contract is a legal instrument and money moves, the cost of retrofitting foundations is brutal. Here's my ordered list.

Step 1 — Close the open architectural questions (Days 1–2)
Four decisions must be made before the first migration, because all four are near-impossible to retrofit:

1.1 Multi-tenancy — the biggest unresolved risk in this project.
The SRS §2.1 states the system uses Multi-Tenant Architecture with full data isolation per real-estate company. But I searched all 134 use cases: there is no use case for creating, managing, or switching a tenant anywhere in phases 1, 2, or 3. No "Manage Companies," no company entity, no tenant-scoped admin. Multi-tenancy is declared architecturally and unsupported functionally.

My call: put tenant_id on every business table from migration #1 and enforce it with a global query scope + a BelongsToTenant trait, even though the MVP has exactly one tenant (a "default" seed row). Cost now: ~2 days. Cost of adding it in month 9 across 40 tables with live contract data: 6+ weeks and a data-integrity risk on legal documents. This is cheap insurance. I need product to confirm, but I'll build it either way.

1.2 The AI service boundary.
The SRS mandates AI contract generation/analysis in ≤60s (NFR-1.1) with RAG over a vector DB. That is not PHP work. AI/ becomes a separate Python service (FastAPI + LangGraph + Qdrant). Laravel never calls the LLM. Laravel enqueues a job, calls the AI service over an internal HTTP contract, and the AI service posts results back to a signed webhook. Rationale: 60-second synchronous calls in a PHP-FPM worker will exhaust your pool at ~50 concurrent contract analyses, and NFR-1.4 demands 1,000 concurrent users.

1.3 The LLM provider.
The README lists "Microsoft Copilot (replaceable)." Copilot is an end-user product, not an API you build a legal-analysis pipeline on. This needs to be Azure OpenAI, or the Anthropic/OpenAI API directly. Also relevant: NFR-12.3 requires logging the model version and knowledge-base version for every generation — that only works against a versioned API endpoint. I'd raise this in week 1, and design the AI service behind a provider interface so the choice stays reversible.

1.4 Money representation.
Every monetary value is a BIGINT in minor units + a char(3) currency code. No floats, no decimals-as-strings-in-JSON-parsed-loosely. A wrapper Money value object, and a lint rule that fails CI if a migration adds a float/double column. Contract values here are property prices; a rounding drift on a legal document is not a bug you recover from reputationally.

Step 2 — Repository and pipeline before features (Days 2–4)
composer create-project laravel/laravel Back-end
Then, before anything else, the pipeline. My non-negotiable Definition of Done for the repo itself:

Gate	Tool	Threshold
Static analysis	Larastan (PHPStan)	Level 8, zero baseline exceptions on new code
Code style	Laravel Pint	Enforced, auto-fix in pre-commit
Tests	Pest	See coverage policy below
Architecture rules	Pest arch plugin	Module boundaries enforced as tests
Dependency CVEs	composer audit	Fails build on any advisory
Migrations	migrate:fresh on ephemeral Postgres	Every CI run, from zero
API contract	Spectator / OpenAPI diff	Breaking change fails the build
Coverage policy — I don't believe in a flat percentage:

100% branch coverage, mandatory: money arithmetic, all state machines, authorization policies, signature verification, audit-log writes.
≥80%: everything else.
0% required: framework glue, DTOs.
A blanket "80% overall" lets people test getters and skip the payment reconciliation path. I gate on the critical-path list specifically.

Step 3 — The skeleton: model the domain, not the CRUD (Days 4–8)
I'd write the full ERD and migrations for the MVP domain before building endpoints, because the entity relationships in this SRS are deeply interlocked (property → request → contract → signatures → payment → handover → closure).

Four cross-cutting mechanisms get built first, as infrastructure every feature then plugs into:

a) State machines as first-class objects. The SRS defines explicit status tables — contract (§3.7.2, 12 states), payment (§3.8.2, 7 states), plus property and request lifecycles. I will not let these be a status string that any service can assign. Each gets a transition table:

// Contract: only these transitions exist. Everything else throws.
'Draft'                 => ['Under AI Review', 'Cancelled'],
'Under AI Review'       => ['Pending Lawyer Review', 'Draft'],
'Pending Lawyer Review' => ['Approved', 'Requires Modification', 'Cancelled'],
'Requires Modification' => ['Pending Lawyer Review', 'Cancelled'],   // UC-070
'Approved'              => ['Awaiting Signatures', 'Cancelled'],
'Awaiting Signatures'   => ['Fully Signed', 'Cancelled'],            // UC-046, UC-058
'Fully Signed'          => ['Awaiting Payment'],                     // UC-059
'Awaiting Payment'      => ['Active', 'Cancelled'],                  // UC-022, UC-051
'Active'                => ['Completed', 'Cancelled', 'Expired'],    // UC-054
'Completed'             => [],                                       // UC-055, UC-060 — terminal
'Cancelled'             => [],                                       // UC-091 — terminal
Two notes I'd raise immediately: the SRS's own §3.7.2 lists Requires Modification, but UC-070's scenario writes Modification — I'm standardizing on the table. And UC-091 (Cancel Contract, which you just moved into the MVP) is the only transition that can fire from many states, so it needs its own guard rules per source state, especially Awaiting Payment and Active where money has moved.

b) Append-only audit log. NFR-4.6 requires audit entries be un-modifiable and un-deletable. An Eloquent model with a "please don't delete" convention does not satisfy that. I implement it at the database level: a dedicated Postgres role for the app that holds INSERT and SELECT on audit_logs but no UPDATE/DELETE grant, plus a BEFORE UPDATE OR DELETE trigger that raises an exception. The SRS demands this in ~15 different use cases; building it once, correctly, at the DB layer is the only version I trust.

c) Transactional outbox for all side effects. Every notification (UC-056), every AI job dispatch, every webhook is written to an outbox table inside the same DB transaction as the state change, then relayed by a worker. Without this you get the classic failure: contract marked Approved, then the mail server hiccups, and the lawyer never learns. With ~20 notification-triggering events in the MVP, this pays for itself immediately.

d) Idempotency keys on every mutating financial endpoint. UC-022 (payment) and UC-051 (verification) run against an external gateway over mobile networks. A retried POST must never double-charge. Idempotency-Key header, stored request hash + response, 24h retention.

Step 4 — API contract first, so mobile isn't blocked (Days 8–10)
The Flutter app already has features/auth/{domain,data,presentation} scaffolded. That team cannot start their data layer until my contract exists. So I write OpenAPI 3.1 for the entire auth + profile surface before implementing it, publish it, and stand up a mock server. Mobile builds against the mock while I build the real thing.

This is the single highest-leverage sequencing decision in the project: it decouples two teams from week 2 instead of week 10.

Step 5 — Walk one thin vertical slice end to end (Days 10–14)
Before broad feature work, I build one complete path: UC-037 Register → UC-039 Verify Email → UC-038 Login → UC-042 Update Profile, fully done — migration, policy, request validation, service, resource, OpenAPI, feature tests, audit entries, ar/en error messages, rate limiting, CI green, deployed to staging.

That slice becomes the reference implementation. Every subsequent feature is reviewed against it. It also proves the whole pipeline works before 10 more features are in flight.

Part 2 — Stack & Technical Specification
Confirmed vs. changed from the README
Layer	README proposal	My decision	Why
API framework	Laravel / PHP	Laravel 12, PHP 8.4 ✅	Right call. Mature RBAC/queue/policy ecosystem, fast MVP velocity, wide hiring pool regionally
Database	PostgreSQL	PostgreSQL 17 ✅	Confirmed. Plus extensions below
Auth	JWT + Refresh	Sanctum + custom JWT layer ⚠️	NFR-4.1 mandates JWT+refresh; Sanctum alone issues opaque tokens. Use firebase/php-jwt for access tokens + DB-tracked rotating refresh tokens (needed for UC-045 and UC-084's "terminate other sessions")
LLM	Microsoft Copilot	Azure OpenAI / Anthropic API ❌	See §1.3 — Copilot has no suitable API surface, and NFR-12.3's version-logging requirement can't be met
AI orchestration	LangGraph/LangChain	FastAPI + LangGraph, separate service ✅	Confirmed, but as an independent deployable, not a Laravel package
Vector DB	Qdrant or ChromaDB	Qdrant ✅	Chroma is fine for prototypes; Qdrant has the payload filtering we need to scope retrieval by country + law type (UC-012, UC-062)
Search	—	PostgreSQL GIN + pg_trgm + PostGIS	See below
Core PHP stack
Laravel 12 · PHP 8.4 · PostgreSQL 17 · Redis 7 · Horizon (queues) · Octane optional (post-MVP)
Concern	Package	Note
RBAC (NFR-4.4)	spatie/laravel-permission	5 roles: owner, beneficiary, lawyer, admin, (broker → phase 2)
State machines	spatie/laravel-model-states	Enforces §3.7.2 / §3.8.2 transition tables
Media & documents	spatie/laravel-medialibrary	Property images (UC-003), documents (UC-004), KYC (UC-040)
Activity/audit	Custom, not a package	Off-the-shelf audit packages allow deletion; NFR-4.6 forbids it
Query filtering	spatie/laravel-query-builder	Backs UC-018 filters, UC-025 sorting
PDF generation	spatie/laravel-pdf (Browsershot)	UC-059 final sealed contract; needs real RTL/Arabic shaping — DomPDF fails here
QR	bacon/bacon-qr-code	UC-052
Testing	pestphp/pest + arch plugin	
Static analysis	larastan/larastan	Level 8
Database specifics
Primary keys: UUIDv7 for all public-facing entities. Sequential integer IDs on properties and contracts leak business volume to competitors and make enumeration attacks trivial. UUIDv7 keeps index locality (unlike v4) so we don't pay the B-tree fragmentation cost.
Extensions: pg_trgm (fuzzy property search), postgis (UC-017 map/radius search, "nearest" sort in UC-025), pgcrypto.
Search strategy for NFR-1.2 (≤2s over 100,000 properties): a denormalized property_search materialized projection with a GIN index on a tsvector (Arabic + English configs) plus a GiST index on the PostGIS geography column. No Elasticsearch in the MVP — 100k rows is well within Postgres's capability, and introducing a second datastore means a sync pipeline, a consistency bug class, and an ops burden we don't need yet. I'd revisit at ~1M listings.
Encryption at rest: KYC documents and ownership deeds (UC-040, UC-004) stored in a private S3-compatible bucket, server-side encrypted, served only via short-lived pre-signed URLs. Never a public URL, ever.
Contract integrity — the part that has to be right
This is a LegalTech product; the contract artifact is the whole value proposition.

On Fully Signed (UC-058 → UC-059), generate the final PDF, compute SHA-256, store the hash in an immutable contract_seals row alongside the model version, KB version (NFR-12.3), and the ordered signature evidence.
Signature evidence per signer (UC-046): signer identity, server-side UTC timestamp, IP, user agent, signature method, and the hash of the document as it existed at signing time. Without that last field you cannot prove what a party actually agreed to.
QR verification (UC-052/053) resolves to a public, unauthenticated, aggressively rate-limited endpoint returning only: contract reference, status, parties' masked names, seal hash, issue date. It must never leak contract terms — anyone can scan a QR code.
Service topology
                    ┌──────────────────┐
   Flutter ────────▶│  Laravel API     │◀──── Web dashboards (Front/)
   (Mobile/)        │  /api/v1         │
                    └────────┬─────────┘
                             │
        ┌────────────────────┼─────────────────────┐
        ▼                    ▼                     ▼
  PostgreSQL 17        Redis + Horizon        S3-compatible
  (+PostGIS,           (queues, cache,        (docs, images,
   pg_trgm)             rate limiting)         sealed PDFs)
                             │
                             │  async job + signed webhook callback
                             ▼
                    ┌──────────────────┐
                    │  AI Service      │────▶ Qdrant (legal KB vectors)
                    │  FastAPI+LangGraph│────▶ LLM provider
                    └──────────────────┘
Modular monolith, not microservices. One Laravel deployable with enforced internal module boundaries (app/Modules/{Identity,Property,Request,Contract,Signature,Payment,Execution,Notification,Admin,Knowledge}), boundaries enforced by architecture tests. A 5-person team building 69 use cases against a hard MVP deadline does not have the operational budget for distributed transactions across a contract-signature-payment flow. The only thing that gets its own process is the AI service — because it's a different language, a different scaling profile, and a different failure mode.

Part 3 — The Track: Milestone Map
All 69 MVP use cases, sequenced by dependency. Each milestone is independently demoable.

#	Milestone	Use Cases	Count	Key backend deliverables
M0	Foundations	—	0	CI/CD, Postgres+Redis, audit log, outbox, state-machine base, tenant scoping, OpenAPI pipeline, error/i18n envelope
M1	Identity & Access	037, 038, 039, 040, 041, 042, 045, 084, 085, 086	10	JWT+refresh rotation, RBAC roles, KYC upload, session termination, rate limiting (NFR-4.5)
M2	Admin & Verification	031, 032, 033, 034, 035	5	Admin policies, verification workflows, locations (PostGIS seed), lawyer approval
M3	Property Lifecycle	001, 002, 003, 004, 005, 013, 014, 015, 016	9	Property state machine, media pipeline, ownership-doc verification gate
M4	Search & Discovery	017, 018, 019, 025	4	tsvector projection, GIN/GiST indexes, load test against 100k seeded rows → NFR-1.2
M5	Requests	020, 021, 006, 007, 043, 063, 087	7	Request state machine (Pending→Accepted/Rejected/Cancelled→Closed), contract handoff
M6	Contract Core	008, 009, 010, 011, 012, 044	6	Contract entity, versioning, law selection, export
M7	AI Integration	036, 047, 048, 049, 050, 057, 061, 062	8	AI service + Qdrant, async job protocol, signed webhooks, KB ingestion/reindex, version logging
M8	Lawyer Review	026, 027, 028, 029, 070	5	Assignment, approve/reject/modify loop, review closure
M9	E-Signature	030, 046, 058, 059	4	Signature invitations, evidence capture, completion check, sealed PDF + SHA-256
M10	Payments	022, 051	2	Gateway integration, idempotency, minimal wallet, reconciliation
M11	Execution & Closure	023, 024, 052, 053, 054, 055, 060, 091	8	QR generate/verify, handover, execution log, closure, cancellation
M12	Notifications	056	1	Email channel over outbox (built incrementally from M1, hardened here)
M13	Hardening	—	0	Load test to NFR-1.4 (1,000 concurrent / 300 rps), pen test, backup/restore drill (NFR-11), observability
Critical path: M0 → M1 → M3 → M5 → M6 → M7 → M8 → M9 → M10 → M11. M2 and M4 can run in parallel with a second developer. M7 (AI service) should start as a spike during M3 — it's the highest-uncertainty component and the one that will surprise us.

Parallelization
Track	Owner	Milestones
Core API	Me + 1 backend	M0 → M1 → M3 → M5 → M6
Search & Admin	Backend #2	M2, M4
AI Service	Python dev	M7 (spike from week 4)
Contract/Signature/Payment	Me	M8 → M9 → M10 → M11
Part 4 — Things I'd escalate in the first project meeting
Multi-tenancy has no functional home. Declared in SRS §2.1, zero use cases across all three phases. I'm building tenant_id in defensively — but product must decide whether this is a real business requirement or aspirational README language, because it also affects pricing, onboarding, and the admin surface.
UC-091 (Cancel Contract) now depends on refunds, which are phase 2. You moved it into the MVP. FR-7.16 requires recording "the effect of cancellation on payments," and FR-7.17 (refunds) plus FR-7.12 (fund transfers) are still phase 2. My recommendation: scope MVP cancellation to contracts that have not yet reached Awaiting Payment, and treat post-payment cancellation as a manual ops process — consistent with the manual-settlement caveat already in SRS §7.5. Otherwise UC-091 silently pulls the entire financial settlement module into the MVP.
FR-7.8 (wallet) is phase 2, but UC-022 depends on it. UC-022 makes the wallet the primary payment method. I need a minimal wallet (balance + debit + ledger) in M10 regardless. I'd like that formally acknowledged rather than discovered at integration time.
UC-063 has no functional requirement. Flagged in the last analysis — needs an FR-5.7 written before M5, defining close conditions and read-only enforcement.
No payment gateway has been selected. M10 is 8 milestones away, but gateway onboarding in this region involves commercial agreements and compliance review with lead times measured in months. This procurement needs to start in week 1, not when I reach M10.
Immediate next step: if you want, I'll scaffold the Laravel project in Back-end/ with the M0 foundations — module structure, the audit-log migration with the DB-level immutability trigger, the state-machine base classes, the tenant scoping trait, and the CI workflow — so M1 can start against a real skeleton. Say the word and I'll build it.
