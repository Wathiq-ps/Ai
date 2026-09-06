-- =============================================================================
-- Wathiq — 06. AI jobs, analyses, and the legal knowledge base
--
-- Module 6 AI portions (FR-6.7 .. FR-6.10), Module 12 (FR-12.1 .. FR-12.5),
-- NFR-12.3 (log model version and knowledge-base version for every generation).
--
-- The `knowledge` schema is a privilege boundary. The AI service holds a role
-- with rights there and nowhere else: it receives contract text in the job
-- payload over HTTP and therefore has no business reading app.contracts. That
-- makes the boundary physical rather than a convention someone can forget.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Knowledge base versions
--
-- Every generation records which KB version produced it (NFR-12.3). Because a
-- version pins the embedding model and its dimensionality, switching models is
-- a new version and a full re-embed — which is exactly the FR-12.3 re-index
-- flow, not a special case.
-- -----------------------------------------------------------------------------
create type app.kb_version_status as enum ('building', 'ready', 'active', 'superseded', 'failed');

create table knowledge.kb_versions (
    id                   uuid primary key default app.uuid_generate_v7(),
    tag                  varchar(64) not null,
    jurisdiction_id      uuid not null references app.jurisdictions (id) on delete restrict,
    embedding_model      varchar(128) not null,
    embedding_dimensions smallint     not null,
    chunk_count          integer      not null default 0,
    status               app.kb_version_status not null default 'building',
    built_at             timestamptz,
    activated_at         timestamptz,
    notes                text,
    created_at           timestamptz not null default now(),

    constraint kb_versions_dimensions_positive check (embedding_dimensions > 0)
);

create unique index kb_versions_tag_key on knowledge.kb_versions (jurisdiction_id, tag);
-- Exactly one active version per jurisdiction. Retrieval reads the active one;
-- a half-finished rebuild must never be able to serve traffic.
create unique index kb_versions_one_active
    on knowledge.kb_versions (jurisdiction_id)
    where status = 'active';

-- -----------------------------------------------------------------------------
-- Sources and documents (FR-12.1, FR-12.5)
-- -----------------------------------------------------------------------------
create table knowledge.sources (
    id              uuid primary key default app.uuid_generate_v7(),
    jurisdiction_id uuid not null references app.jurisdictions (id) on delete restrict,
    law_type        app.law_type not null,
    title_ar        varchar(255) not null,
    title_en        varchar(255),
    publisher       varchar(191) not null,
    citation        varchar(191),
    source_url      text,
    effective_from  date not null,
    effective_to    date,
    is_verified     boolean not null default false,
    verified_by     uuid references app.users (id) on delete restrict,
    verified_at     timestamptz,
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now(),

    constraint sources_effective_range check (effective_to is null or effective_to > effective_from),
    constraint sources_verified_complete check (
        is_verified = false or (verified_by is not null and verified_at is not null)
    )
);

create index sources_jurisdiction_idx on knowledge.sources (jurisdiction_id, law_type)
    where is_verified;

create trigger sources_touch
    before update on knowledge.sources
    for each row execute function app.touch_updated_at();

comment on column knowledge.sources.is_verified is
  'BR-23/BR-24: only verified sources may be retrieved for contract generation. Filter on this in every RAG query.';

create table knowledge.documents (
    id           uuid primary key default app.uuid_generate_v7(),
    source_id    uuid not null references knowledge.sources (id) on delete cascade,
    title        varchar(255) not null,
    language     app.locale   not null default 'ar',
    article_ref  varchar(64),
    raw_path     text,
    checksum     app.sha256_hex not null,
    created_at   timestamptz not null default now()
);

create index documents_source_idx on knowledge.documents (source_id);

-- -----------------------------------------------------------------------------
-- Chunks and embeddings (FR-12.2, FR-12.3)
--
-- pgvector rather than a separate vector store. The decisive argument is not
-- convenience but atomicity: the chunk, its metadata, its law version and its
-- embedding are one row, so a re-index either lands or does not. Split across
-- two datastores it is a two-phase commit that can tear, leaving generations
-- attributed to a KB version that never fully existed — unacceptable when the
-- output is a legal instrument and NFR-12.3 demands provenance.
--
-- Retrieval filters (jurisdiction, law type, effective date) are ordinary
-- indexed columns, which is precisely the "payload filtering" a dedicated
-- vector database would have been chosen for.
-- -----------------------------------------------------------------------------
create table knowledge.chunks (
    id              uuid primary key default app.uuid_generate_v7(),
    kb_version_id   uuid not null references knowledge.kb_versions (id) on delete cascade,
    document_id     uuid not null references knowledge.documents (id)   on delete cascade,
    jurisdiction_id uuid not null references app.jurisdictions (id)     on delete restrict,
    law_type        app.law_type not null,
    ordinal         integer      not null,
    content         text         not null,
    token_count     smallint,
    -- Dimension is pinned per deployment and must match
    -- kb_versions.embedding_dimensions. Changing the embedding model means a
    -- new kb_version and a full rebuild; see the note above.
    embedding       vector(1536) not null,
    effective_from  date         not null,
    effective_to    date,
    metadata        jsonb        not null default '{}'::jsonb,
    created_at      timestamptz  not null default now(),

    unique (kb_version_id, document_id, ordinal)
);

create index chunks_filter_idx
    on knowledge.chunks (kb_version_id, jurisdiction_id, law_type);
create index chunks_effective_idx
    on knowledge.chunks (effective_from, effective_to);

-- Deliberately NOT indexed at launch.
--
-- The Palestinian real-estate corpus is thousands to low tens of thousands of
-- chunks. Exact search over that is a few milliseconds and returns exact
-- results; an HNSW index would trade that accuracy for speed the workload does
-- not need, and its recall degrades under the restrictive metadata filters this
-- schema is built around. Enable it when measurement — not intuition — says the
-- scan is the bottleneck, and set hnsw.iterative_scan so filtered queries can
-- still reach k results:
--
--   create index concurrently chunks_embedding_hnsw
--       on knowledge.chunks using hnsw (embedding vector_cosine_ops)
--       with (m = 16, ef_construction = 64);
--   -- per session: set hnsw.ef_search = 100; set hnsw.iterative_scan = 'relaxed_order';

-- =============================================================================
-- AI jobs (ADR: async boundary — the API never calls an LLM inline)
--
-- NFR-1.1 allows 60s for generation. Holding a PHP-FPM worker for that would
-- saturate the pool long before NFR-1.4's 1,000 concurrent users. Laravel
-- enqueues, the AI service calls back over a signed webhook.
-- =============================================================================
create type app.ai_job_kind   as enum ('generate_contract', 'analyze_contract', 'answer_query', 'summarize');
create type app.ai_job_status as enum ('queued', 'dispatched', 'running', 'succeeded', 'failed', 'cancelled', 'timed_out');

create table app.ai_jobs (
    id                uuid primary key default app.uuid_generate_v7(),
    tenant_id         uuid not null references app.tenants (id) on delete restrict,
    contract_id       uuid,
    kind              app.ai_job_kind   not null,
    status            app.ai_job_status not null default 'queued',
    requested_by      uuid references app.users (id) on delete restrict,

    -- Provenance, mandated by NFR-12.3. Nullable until the job runs, then
    -- required on success — see the constraint below.
    provider          varchar(64),
    model_id          varchar(128),
    model_version     varchar(64),
    prompt_version    varchar(32),
    kb_version_id     uuid references knowledge.kb_versions (id) on delete restrict,

    input_hash        app.sha256_hex,
    tokens_input      integer,
    tokens_output     integer,
    latency_ms        integer,
    attempts          smallint not null default 0,
    error_code        varchar(64),
    error_message     text,

    queued_at         timestamptz not null default now(),
    dispatched_at     timestamptz,
    completed_at      timestamptz,

    -- A succeeded generation with no recorded model or KB version cannot satisfy
    -- NFR-12.3, so the database refuses to store one.
    constraint ai_jobs_success_has_provenance check (
        status <> 'succeeded' or (
            provider is not null and model_id is not null
            and model_version is not null and kb_version_id is not null
        )
    ),
    constraint ai_jobs_failure_has_code check (
        status <> 'failed' or error_code is not null
    ),

    unique (id, tenant_id),
    foreign key (contract_id, tenant_id)
        references app.contracts (id, tenant_id) on delete cascade
);

create index ai_jobs_contract_idx on app.ai_jobs (contract_id, queued_at desc);
create index ai_jobs_pending_idx  on app.ai_jobs (status, queued_at)
    where status in ('queued', 'dispatched', 'running');

alter table app.contract_versions
    add constraint contract_versions_ai_job_fk
    foreign key (ai_job_id) references app.ai_jobs (id) on delete set null;

-- =============================================================================
-- Analyses and findings (FR-6.7 .. FR-6.10)
-- =============================================================================
create table app.contract_analyses (
    id                  uuid primary key default app.uuid_generate_v7(),
    tenant_id           uuid not null references app.tenants (id) on delete restrict,
    contract_id         uuid not null,
    contract_version_id uuid not null,
    ai_job_id           uuid not null references app.ai_jobs (id) on delete restrict,

    -- 0-100 integer. Deliberately not a float: the bands below are exact and a
    -- legal risk score that renders as 60.00000000000001 is indefensible.
    risk_score          smallint not null,
    risk_band           varchar(16) generated always as (
        case
            when risk_score <= 20 then 'very_low'
            when risk_score <= 40 then 'low'
            when risk_score <= 60 then 'medium'
            when risk_score <= 80 then 'high'
            else 'critical'
        end
    ) stored,
    summary_ar          text,
    summary_en          text,
    report_path         text,
    created_at          timestamptz not null default now(),

    constraint analyses_risk_range check (risk_score between 0 and 100),

    unique (id, tenant_id),
    unique (contract_version_id),   -- one analysis per version
    foreign key (contract_id, tenant_id)
        references app.contracts (id, tenant_id) on delete cascade,
    foreign key (contract_version_id, tenant_id)
        references app.contract_versions (id, tenant_id) on delete cascade
);

create index analyses_contract_idx on app.contract_analyses (contract_id, created_at desc);

create type app.finding_kind as enum ('missing_clause', 'legal_conflict', 'ambiguity', 'suggestion', 'risk');
create type app.finding_severity as enum ('info', 'low', 'medium', 'high', 'critical');
-- The lawyer's decision on each AI suggestion (UC-028/UC-029).
create type app.finding_resolution as enum ('open', 'accepted', 'rejected', 'superseded');

create table app.analysis_findings (
    id            uuid primary key default app.uuid_generate_v7(),
    tenant_id     uuid not null references app.tenants (id) on delete restrict,
    analysis_id   uuid not null,
    clause_id     uuid references app.contract_clauses (id) on delete set null,
    kind          app.finding_kind     not null,
    severity      app.finding_severity not null,
    title_ar      varchar(255) not null,
    title_en      varchar(255),
    description   text not null,
    suggested_text text,
    -- Grounding: which knowledge chunks supported this finding. BR-25 forbids
    -- unsourced legal claims, so a finding with no citation is a bug and this
    -- column is how it becomes visible.
    citations     jsonb not null default '[]'::jsonb,
    resolution    app.finding_resolution not null default 'open',
    resolved_by   uuid references app.users (id) on delete restrict,
    resolved_at   timestamptz,
    resolution_note text,
    created_at    timestamptz not null default now(),

    constraint findings_resolution_complete check (
        resolution = 'open' or (resolved_by is not null and resolved_at is not null)
    ),

    foreign key (analysis_id, tenant_id)
        references app.contract_analyses (id, tenant_id) on delete cascade
);

create index findings_analysis_idx on app.analysis_findings (analysis_id, severity);
create index findings_open_idx     on app.analysis_findings (analysis_id) where resolution = 'open';
