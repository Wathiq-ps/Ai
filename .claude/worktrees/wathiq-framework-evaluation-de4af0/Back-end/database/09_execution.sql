-- =============================================================================
-- Wathiq — 09. Execution: QR handover, execution log, public verification
--
-- Module 7 execution portions (FR-7.13 .. FR-7.18), UC-023, UC-024,
-- UC-052, UC-053, UC-054, UC-055, UC-060.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Handover codes (FR-7.13, UC-052)
--
-- The QR encodes a token; the database stores only its hash, so a leaked backup
-- cannot be used to confirm a handover. Single use, time-boxed, and bound to
-- the contract.
-- -----------------------------------------------------------------------------
create type app.handover_code_status as enum ('active', 'consumed', 'expired', 'revoked');

create table app.handover_codes (
    id           uuid primary key default app.uuid_generate_v7(),
    tenant_id    uuid not null references app.tenants (id) on delete restrict,
    contract_id  uuid not null,
    token_hash   app.sha256_hex not null,
    status       app.handover_code_status not null default 'active',
    issued_by    uuid not null references app.users (id) on delete restrict,
    issued_at    timestamptz not null default now(),
    expires_at   timestamptz not null,
    consumed_at  timestamptz,
    consumed_by  uuid references app.users (id) on delete restrict,
    consumed_ip  inet,

    constraint handover_expiry_after_issue check (expires_at > issued_at),
    constraint handover_consumed_complete check (
        (status = 'consumed') = (consumed_at is not null and consumed_by is not null)
    ),

    foreign key (contract_id, tenant_id)
        references app.contracts (id, tenant_id) on delete cascade
);

create unique index handover_codes_token_key on app.handover_codes (token_hash);
-- One live code per contract; reissuing revokes the previous one.
create unique index handover_codes_one_active on app.handover_codes (contract_id) where status = 'active';
create index handover_codes_expiry_idx on app.handover_codes (expires_at) where status = 'active';

-- -----------------------------------------------------------------------------
-- Execution log (FR-7.18, UC-060)
--
-- The human-readable timeline of what physically happened after signing —
-- distinct from contract_status_history (state transitions) and from the audit
-- log (compliance record).
-- -----------------------------------------------------------------------------
create type app.execution_step as enum (
    'contract_activated',
    'payment_received',
    'handover_code_issued',
    'handover_confirmed',
    'keys_delivered',
    'documents_delivered',
    'contract_closed',
    'note'
);

create table app.contract_executions (
    id           uuid primary key default app.uuid_generate_v7(),
    tenant_id    uuid not null references app.tenants (id) on delete restrict,
    contract_id  uuid not null,
    step         app.execution_step not null,
    actor_id     uuid references app.users (id) on delete restrict,
    notes        text,
    attachments  jsonb not null default '[]'::jsonb,
    occurred_at  timestamptz not null default now(),

    foreign key (contract_id, tenant_id)
        references app.contracts (id, tenant_id) on delete cascade
);

create index contract_executions_idx on app.contract_executions (contract_id, occurred_at);

create trigger contract_executions_immutable
    before update or delete on app.contract_executions
    for each row execute function app.reject_any_change();

-- -----------------------------------------------------------------------------
-- Public verification view (UC-053)
--
-- Anyone can scan a QR code, so the verification endpoint is unauthenticated.
-- It must therefore be incapable of leaking contract terms — not merely
-- careful not to. This view is the entire public surface: reference, status,
-- masked party names, seal hash, dates. No value, no clauses, no addresses.
--
-- The endpoint reads this view and nothing else, and the public role (10_grants)
-- is granted SELECT here and on no base table.
-- -----------------------------------------------------------------------------
create or replace function app.mask_name(full_name text)
returns text
language sql
immutable
strict
parallel safe
as $$
    -- "Ahmad Yousef Khalil" -> "Ahmad Y. K."
    select (string_to_array(full_name, ' '))[1] || ' ' ||
           coalesce(
             string_agg(left(part, 1) || '.', ' ')
               filter (where ordinality > 1),
             ''
           )
      from unnest(string_to_array(full_name, ' ')) with ordinality as t(part, ordinality);
$$;

create or replace view app.contract_verification_public
with (security_barrier = true)
as
select
    c.reference                              as contract_reference,
    c.status::text                           as status,
    c.type::text                             as contract_type,
    app.mask_name(op.display_name)           as owner_name_masked,
    app.mask_name(bp.display_name)           as beneficiary_name_masked,
    s.pdf_sha256                             as seal_hash,
    s.sealed_at                              as issued_at,
    j.name_ar                                as jurisdiction_ar,
    j.name_en                                as jurisdiction_en
  from app.contracts c
  join app.contract_seals s  on s.contract_id = c.id
  join app.user_profiles op  on op.user_id = c.owner_id
  join app.user_profiles bp  on bp.user_id = c.beneficiary_id
  join app.jurisdictions j   on j.id = c.jurisdiction_id
 where c.status in ('active', 'completed', 'expired', 'cancelled');

comment on view app.contract_verification_public is
  'The complete unauthenticated surface for QR verification (UC-053). Adding a column here widens what any passer-by can read — treat changes as a security review, and rate-limit the endpoint aggressively.';
