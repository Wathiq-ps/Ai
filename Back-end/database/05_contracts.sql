-- =============================================================================
-- Wathiq — 05. Contracts: entity, versions, clauses, state machine
--
-- Module 6 (FR-6.x), SRS 3.7.1 / 3.7.2, Module 12 review loop (FR-6.11/6.12).
--
-- This is the table the product exists to protect. Three things are enforced in
-- the database rather than in application services, because a legal instrument
-- that reached an impossible state is not a bug you fix forward:
--   1. the status transition whitelist (data-driven, below)
--   2. contract version immutability
--   3. exactly one seal per contract (see 07_signatures.sql)
-- =============================================================================

create type app.contract_type as enum ('sale', 'rent');

-- SRS 3.7.2. Note: 3.7.2 names 'Requires Modification' while UC-070's scenario
-- writes 'Modification'. The status table is authoritative; standardised here.
create type app.contract_status as enum (
    'draft',
    'under_ai_review',
    'pending_lawyer_review',
    'requires_modification',
    'approved',
    'awaiting_signatures',
    'fully_signed',
    'awaiting_payment',
    'active',
    'completed',
    'cancelled',
    'expired'
);

create table app.contracts (
    id                 uuid primary key default app.uuid_generate_v7(),
    tenant_id          uuid not null references app.tenants (id) on delete restrict,
    reference          varchar(24) not null,

    request_id         uuid not null,
    property_id        uuid not null,
    owner_id           uuid not null references app.users (id) on delete restrict,
    beneficiary_id     uuid not null references app.users (id) on delete restrict,
    lawyer_id          uuid references app.users (id) on delete restrict,
    template_id        uuid,

    type               app.contract_type   not null,
    status             app.contract_status not null default 'draft',
    jurisdiction_id    uuid not null references app.jurisdictions (id) on delete restrict,

    value_amount       app.money_minor   not null,
    value_currency     app.currency_code not null references app.currencies (code),

    -- Rental term; null for sale.
    starts_on          date,
    ends_on            date,

    current_version_id uuid,   -- FK added after contract_versions exists
    created_by         uuid not null references app.users (id) on delete restrict,
    approved_at        timestamptz,
    activated_at       timestamptz,
    completed_at       timestamptz,
    cancelled_at       timestamptz,
    cancellation_reason text,
    created_at         timestamptz not null default now(),
    updated_at         timestamptz not null default now(),

    constraint contracts_parties_distinct check (owner_id <> beneficiary_id),
    constraint contracts_term_pair    check ((starts_on is null) = (ends_on is null)),
    constraint contracts_term_ordered check (ends_on is null or ends_on > starts_on),
    constraint contracts_rent_has_term check (type <> 'rent' or starts_on is not null),
    constraint contracts_cancelled_has_reason check (
        status <> 'cancelled' or cancellation_reason is not null
    ),
    -- BR-29: no contract may be approved without a licensed lawyer attached.
    constraint contracts_approved_has_lawyer check (
        status not in ('approved', 'awaiting_signatures', 'fully_signed',
                       'awaiting_payment', 'active', 'completed')
        or lawyer_id is not null
    ),

    unique (id, tenant_id),
    foreign key (request_id, tenant_id)
        references app.property_requests (id, tenant_id) on delete restrict,
    foreign key (property_id, tenant_id)
        references app.properties (id, tenant_id) on delete restrict
);

create unique index contracts_reference_key on app.contracts (tenant_id, reference);
-- One contract per accepted request.
create unique index contracts_request_key on app.contracts (request_id);

create index contracts_property_idx    on app.contracts (property_id, status);
create index contracts_owner_idx       on app.contracts (tenant_id, owner_id, created_at desc);
create index contracts_beneficiary_idx on app.contracts (tenant_id, beneficiary_id, created_at desc);
-- The lawyer's review queue (UC-026 .. UC-029).
create index contracts_lawyer_queue_idx
    on app.contracts (tenant_id, lawyer_id, status)
    where status in ('pending_lawyer_review', 'requires_modification');
create index contracts_expiry_idx on app.contracts (ends_on) where status = 'active';

create trigger contracts_touch
    before update on app.contracts
    for each row execute function app.touch_updated_at();

-- A property cannot carry two overlapping live rentals. btree_gist supplies the
-- `=` operator for uuid inside the GiST index; the daterange handles overlap.
alter table app.contracts
    add constraint contracts_no_overlapping_rentals
    exclude using gist (
        property_id with =,
        daterange(starts_on, ends_on, '[]') with &&
    )
    where (type = 'rent' and status in ('active', 'awaiting_payment', 'fully_signed'));

-- =============================================================================
-- Contract versions (FR-6.13)
--
-- Append-only. A version is what a party actually signed; editing one after the
-- fact would destroy the evidentiary chain that app.signatures.document_hash
-- depends on. Lawyer edits create a new version, never a mutation.
-- =============================================================================
create type app.contract_version_author as enum ('ai', 'lawyer', 'owner', 'admin', 'system');

create table app.contract_versions (
    id            uuid primary key default app.uuid_generate_v7(),
    tenant_id     uuid not null references app.tenants (id) on delete restrict,
    contract_id   uuid not null,
    version_no    integer not null,
    body          text    not null,
    body_format   varchar(16) not null default 'markdown',
    -- SHA-256 over the canonical body. This is the value copied into every
    -- signature record, and the anchor of the whole integrity story.
    content_hash  app.sha256_hex not null,
    author_type   app.contract_version_author not null,
    author_id     uuid references app.users (id) on delete restrict,
    ai_job_id     uuid,   -- FK added in 06_ai.sql
    change_note   text,
    created_at    timestamptz not null default now(),

    constraint contract_versions_no_positive check (version_no > 0),
    constraint contract_versions_human_has_author check (
        author_type in ('ai', 'system') or author_id is not null
    ),

    unique (id, tenant_id),
    unique (contract_id, version_no),
    foreign key (contract_id, tenant_id)
        references app.contracts (id, tenant_id) on delete cascade
);

create index contract_versions_contract_idx on app.contract_versions (contract_id, version_no desc);
create unique index contract_versions_hash_key on app.contract_versions (contract_id, content_hash);

-- Total immutability: no column of a written version may change.
create or replace function app.reject_any_change()
returns trigger
language plpgsql
as $$
begin
    raise exception '%.% is append-only; create a new row instead of modifying %',
        tg_table_schema, tg_table_name, old.id
        using errcode = 'restrict_violation';
end;
$$;

create trigger contract_versions_immutable
    before update or delete on app.contract_versions
    for each row execute function app.reject_any_change();

alter table app.contracts
    add constraint contracts_current_version_fk
    foreign key (current_version_id) references app.contract_versions (id) on delete restrict
    deferrable initially deferred;

-- Clause-level breakdown, so AI findings and lawyer decisions can point at a
-- specific clause rather than a character offset into a blob.
create type app.clause_kind as enum (
    'parties', 'subject', 'price', 'payment_terms', 'duration', 'obligations',
    'warranties', 'termination', 'dispute_resolution', 'governing_law', 'other'
);

create table app.contract_clauses (
    id                  uuid primary key default app.uuid_generate_v7(),
    tenant_id           uuid not null references app.tenants (id) on delete restrict,
    contract_version_id uuid not null,
    ordinal             smallint not null,
    kind                app.clause_kind not null,
    heading             varchar(255),
    body                text not null,
    is_ai_generated     boolean not null default true,

    unique (contract_version_id, ordinal),
    foreign key (contract_version_id, tenant_id)
        references app.contract_versions (id, tenant_id) on delete cascade
);

create index contract_clauses_version_idx on app.contract_clauses (contract_version_id, ordinal);

create trigger contract_clauses_immutable
    before update or delete on app.contract_clauses
    for each row execute function app.reject_any_change();

-- =============================================================================
-- Templates (FR-13.8)
-- =============================================================================
create table app.contract_templates (
    id              uuid primary key default app.uuid_generate_v7(),
    tenant_id       uuid not null references app.tenants (id) on delete restrict,
    jurisdiction_id uuid not null references app.jurisdictions (id) on delete restrict,
    type            app.contract_type not null,
    name_ar         varchar(191) not null,
    name_en         varchar(191) not null,
    body            text not null,
    version         integer not null default 1,
    is_active       boolean not null default true,
    created_by      uuid not null references app.users (id) on delete restrict,
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now(),

    unique (id, tenant_id)
);

create unique index contract_templates_active_key
    on app.contract_templates (tenant_id, jurisdiction_id, type)
    where is_active;

create trigger contract_templates_touch
    before update on app.contract_templates
    for each row execute function app.touch_updated_at();

alter table app.contracts
    add constraint contracts_template_fk
    foreign key (template_id, tenant_id)
    references app.contract_templates (id, tenant_id) on delete restrict;

-- =============================================================================
-- The state machine, held in a table
--
-- A status column that any service can assign is not a state machine. Putting
-- the transition set in a table and checking it in a BEFORE UPDATE trigger
-- means every path into the database — Eloquent, a queue worker, an admin
-- running raw SQL at 2am, a future service in another language — obeys the same
-- rules. The alternative is trusting that all of them remembered to.
-- =============================================================================
create table app.contract_status_transitions_allowed (
    from_status app.contract_status not null,
    to_status   app.contract_status not null,
    note        text,

    primary key (from_status, to_status),
    constraint transitions_not_self check (from_status <> to_status)
);

insert into app.contract_status_transitions_allowed (from_status, to_status, note) values
    ('draft',                 'under_ai_review',       'UC-008 submit for analysis'),
    ('draft',                 'cancelled',             'UC-091'),
    ('under_ai_review',       'pending_lawyer_review', 'UC-047 analysis complete'),
    ('under_ai_review',       'draft',                 'analysis failed; return for edit'),
    ('under_ai_review',       'cancelled',             'UC-091'),
    ('pending_lawyer_review', 'approved',              'UC-027'),
    ('pending_lawyer_review', 'requires_modification', 'UC-070'),
    ('pending_lawyer_review', 'cancelled',             'UC-091'),
    ('requires_modification', 'pending_lawyer_review', 'UC-070 resubmission'),
    ('requires_modification', 'cancelled',             'UC-091'),
    ('approved',              'awaiting_signatures',   'UC-030 send to sign'),
    ('approved',              'cancelled',             'UC-091'),
    ('awaiting_signatures',   'fully_signed',          'UC-046 / UC-058 all parties signed'),
    ('awaiting_signatures',   'cancelled',             'UC-091'),
    ('awaiting_signatures',   'expired',               'signature window elapsed'),
    ('fully_signed',          'awaiting_payment',      'UC-059 final version issued'),
    ('awaiting_payment',      'active',                'UC-022 / UC-051 payment verified'),
    ('awaiting_payment',      'cancelled',             'UC-091 — see the guard below'),
    ('active',                'completed',             'UC-054 / UC-055 handover confirmed'),
    ('active',                'cancelled',             'UC-091 — see the guard below'),
    ('active',                'expired',               'rental term elapsed');
-- 'completed', 'cancelled' and 'expired' are terminal: no row has them as from_status.

create or replace function app.enforce_contract_transition()
returns trigger
language plpgsql
as $$
begin
    if new.status = old.status then
        return new;
    end if;

    if not exists (
        select 1
          from app.contract_status_transitions_allowed t
         where t.from_status = old.status
           and t.to_status   = new.status
    ) then
        raise exception 'illegal contract transition % -> % on contract %',
            old.status, new.status, old.id
            using errcode = 'restrict_violation',
                  hint = 'Permitted transitions are rows in app.contract_status_transitions_allowed.';
    end if;

    -- UC-091 is the only transition that fires from many sources, and the two
    -- post-payment ones move money. FR-7.16 requires recording the effect of
    -- cancellation on payments, but refunds (FR-7.17) and transfers (FR-7.12)
    -- are Phase 2. Until a settlement path exists, cancelling a contract that
    -- has taken payment must be an explicit operations action, not something an
    -- ordinary request path can reach.
    if new.status = 'cancelled' and old.status in ('awaiting_payment', 'active') then
        if coalesce(current_setting('wathiq.allow_settled_cancellation', true), 'off') <> 'on' then
            raise exception
                'contract % is in % and may have settled funds; cancellation requires an operations override',
                old.id, old.status
                using errcode = 'restrict_violation',
                      hint = 'SET LOCAL wathiq.allow_settled_cancellation = ''on'' inside the reviewed ops transaction.';
        end if;
    end if;

    -- Timestamp bookkeeping, so no service can forget it.
    if new.status = 'approved'  then new.approved_at  := coalesce(new.approved_at,  now()); end if;
    if new.status = 'active'    then new.activated_at := coalesce(new.activated_at, now()); end if;
    if new.status = 'completed' then new.completed_at := coalesce(new.completed_at, now()); end if;
    if new.status = 'cancelled' then new.cancelled_at := coalesce(new.cancelled_at, now()); end if;

    return new;
end;
$$;

create trigger contracts_enforce_transition
    before update of status on app.contracts
    for each row execute function app.enforce_contract_transition();

-- -----------------------------------------------------------------------------
-- Transition history (FR-6.14)
--
-- Distinct from the audit log: this is queryable domain history shown in the
-- contract timeline UI. The audit log is the compliance record.
-- -----------------------------------------------------------------------------
create table app.contract_status_history (
    id           uuid primary key default app.uuid_generate_v7(),
    tenant_id    uuid not null references app.tenants (id) on delete restrict,
    contract_id  uuid not null,
    from_status  app.contract_status,
    to_status    app.contract_status not null,
    actor_id     uuid references app.users (id) on delete restrict,
    reason       text,
    occurred_at  timestamptz not null default now(),

    foreign key (contract_id, tenant_id)
        references app.contracts (id, tenant_id) on delete cascade
);

create index contract_status_history_idx on app.contract_status_history (contract_id, occurred_at);

create trigger contract_status_history_immutable
    before update or delete on app.contract_status_history
    for each row execute function app.reject_any_change();

create or replace function app.record_contract_transition()
returns trigger
language plpgsql
as $$
begin
    if new.status is distinct from old.status then
        insert into app.contract_status_history
            (tenant_id, contract_id, from_status, to_status, actor_id, reason)
        values
            (new.tenant_id, new.id, old.status, new.status,
             nullif(current_setting('wathiq.actor_id', true), '')::uuid,
             new.cancellation_reason);
    end if;
    return null;
end;
$$;

create trigger contracts_record_transition
    after update of status on app.contracts
    for each row execute function app.record_contract_transition();

comment on function app.record_contract_transition() is
  'Reads the actor from the wathiq.actor_id GUC. The application sets it per transaction: SET LOCAL wathiq.actor_id = ''<uuid>''.';
