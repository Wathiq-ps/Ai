-- =============================================================================
-- Wathiq — 10. Platform: notifications, outbox, idempotency, audit log
--
-- Module 8 (FR-8.x), NFR-3.3 (retry), NFR-4.6 (immutable audit),
-- NFR-10.x (monitoring and logging).
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Notifications (FR-8.1 .. FR-8.4)
--
-- MVP delivers email only (SRS 2.9). The channel enum carries the Phase 2
-- values now so the notification history stays representable when push and SMS
-- arrive, without a migration that rewrites existing rows.
-- -----------------------------------------------------------------------------
create type app.notification_channel as enum ('email', 'in_app', 'push', 'sms');
create type app.notification_status  as enum ('queued', 'sending', 'sent', 'delivered', 'failed', 'read');

create table app.notification_types (
    code         varchar(64) primary key,
    name_ar      varchar(191) not null,
    name_en      varchar(191) not null,
    is_mandatory boolean not null default false,

    constraint notification_types_code_format check (code ~ '^[a-z_]+\.[a-z_]+$')
);

comment on column app.notification_types.is_mandatory is
  'Mandatory types ignore user preferences. Contract signature requests and payment confirmations are legal notices, not marketing.';

insert into app.notification_types (code, name_ar, name_en, is_mandatory) values
    ('account.email_verification', 'تأكيد البريد الإلكتروني', 'Email verification',      true),
    ('account.password_reset',     'إعادة تعيين كلمة المرور', 'Password reset',          true),
    ('identity.approved',          'اعتماد الهوية',           'Identity approved',       false),
    ('identity.rejected',          'رفض الهوية',              'Identity rejected',       true),
    ('property.approved',          'اعتماد العقار',           'Property approved',       false),
    ('request.received',           'طلب جديد',                'New request received',    false),
    ('request.accepted',           'قبول الطلب',              'Request accepted',        false),
    ('request.rejected',           'رفض الطلب',               'Request rejected',        false),
    ('contract.analysis_ready',    'اكتمال تحليل العقد',      'Contract analysis ready', false),
    ('contract.lawyer_assigned',   'تعيين محامٍ',             'Lawyer assigned',         false),
    ('contract.approved',          'اعتماد العقد',            'Contract approved',       true),
    ('contract.signature_request', 'طلب توقيع',               'Signature requested',     true),
    ('contract.fully_signed',      'اكتمال التوقيعات',        'Contract fully signed',   true),
    ('payment.confirmed',          'تأكيد الدفع',             'Payment confirmed',       true),
    ('handover.confirmed',         'تأكيد الاستلام',          'Handover confirmed',      true),
    ('contract.cancelled',         'إلغاء العقد',             'Contract cancelled',      true);

create table app.notifications (
    id           uuid primary key default app.uuid_generate_v7(),
    tenant_id    uuid not null references app.tenants (id) on delete restrict,
    user_id      uuid not null references app.users (id) on delete cascade,
    type_code    varchar(64) not null references app.notification_types (code) on delete restrict,
    channel      app.notification_channel not null,
    locale       app.locale not null default 'ar',
    subject      varchar(255),
    body         text not null,
    payload      jsonb not null default '{}'::jsonb,
    status       app.notification_status not null default 'queued',
    attempts     smallint not null default 0,
    sent_at      timestamptz,
    read_at      timestamptz,
    failure_reason text,
    created_at   timestamptz not null default now(),

    constraint notifications_sent_has_timestamp check (
        status not in ('sent', 'delivered', 'read') or sent_at is not null
    )
);

create index notifications_user_idx    on app.notifications (user_id, created_at desc);
create index notifications_unread_idx  on app.notifications (user_id) where read_at is null;
create index notifications_pending_idx on app.notifications (status, created_at)
    where status in ('queued', 'sending');

create table app.notification_preferences (
    user_id    uuid not null references app.users (id) on delete cascade,
    type_code  varchar(64) not null references app.notification_types (code) on delete cascade,
    channel    app.notification_channel not null,
    is_enabled boolean not null default true,

    primary key (user_id, type_code, channel)
);

-- =============================================================================
-- Transactional outbox (NFR-3.2, NFR-3.3)
--
-- Every side effect — email, AI dispatch, webhook — is written here inside the
-- same transaction as the state change that caused it, then relayed by a
-- worker. Without this you get the classic split-brain: the contract commits as
-- Approved, the mail server hiccups, and the lawyer is never told. With ~20
-- notification-triggering events in the MVP that failure is not hypothetical.
-- =============================================================================
create table ops.outbox (
    id             bigint generated always as identity primary key,
    tenant_id      uuid not null,
    aggregate_type varchar(64) not null,
    aggregate_id   uuid not null,
    event_type     varchar(96) not null,
    payload        jsonb not null,
    available_at   timestamptz not null default now(),
    published_at   timestamptz,
    attempts       smallint not null default 0,
    last_error     text,
    created_at     timestamptz not null default now()
);

-- bigint identity, not uuid: the relay reads in insertion order and this table
-- is high-churn append/delete. Ordering is the whole point here.
create index outbox_unpublished_idx
    on ops.outbox (available_at, id)
    where published_at is null;
create index outbox_aggregate_idx on ops.outbox (aggregate_type, aggregate_id);

comment on table ops.outbox is
  'Relay claims rows with SELECT ... FOR UPDATE SKIP LOCKED ordered by (available_at, id). Prune published rows on a retention schedule.';

-- Signed webhook deliveries from the AI service (and, later, gateways).
create table ops.webhook_deliveries (
    id              uuid primary key default app.uuid_generate_v7(),
    direction       varchar(8) not null,      -- 'inbound' | 'outbound'
    source          varchar(48) not null,     -- 'ai_service' | 'payment_gateway'
    event_type      varchar(96),
    signature_valid boolean,
    -- Replay defence: a signature is accepted once. The unique index below is
    -- what turns "we check the HMAC" into "a captured request cannot be resent".
    signature       varchar(255),
    request_id      uuid,
    http_status     smallint,
    payload         jsonb,
    received_at     timestamptz not null default now(),

    constraint webhook_direction_valid check (direction in ('inbound', 'outbound'))
);

create unique index webhook_signature_key
    on ops.webhook_deliveries (source, signature)
    where direction = 'inbound' and signature is not null;
create index webhook_received_idx on ops.webhook_deliveries (received_at desc);

-- =============================================================================
-- Idempotency keys
--
-- Mandatory on every mutating financial endpoint. Stores the request hash and
-- the response, so a retry returns the original result instead of performing
-- the operation twice.
--
-- The request_hash comparison matters: the same key with a different body is a
-- client bug and must be rejected loudly (409), not served the cached response.
-- =============================================================================
create table ops.idempotency_keys (
    id              uuid primary key default app.uuid_generate_v7(),
    tenant_id       uuid not null,
    user_id         uuid,
    idempotency_key varchar(128) not null,
    endpoint        varchar(191) not null,
    request_hash    app.sha256_hex not null,
    locked_at       timestamptz,
    response_status smallint,
    response_body   jsonb,
    completed_at    timestamptz,
    expires_at      timestamptz not null default now() + interval '24 hours',
    created_at      timestamptz not null default now()
);

create unique index idempotency_keys_key on ops.idempotency_keys (tenant_id, endpoint, idempotency_key);
create index idempotency_keys_expiry_idx on ops.idempotency_keys (expires_at);

-- =============================================================================
-- Audit log (NFR-4.6)
--
-- "Un-modifiable and un-deletable by ordinary users" is not achievable with a
-- convention or an Eloquent observer. It is achieved with two mechanisms, and
-- both are needed:
--
--   1. Grants — wathiq_app holds INSERT and SELECT here and is never granted
--      UPDATE or DELETE (see 11_grants.sql). This is the real protection: a
--      compromised application literally lacks the privilege.
--   2. The trigger below — catches mistakes made by roles that DO hold the
--      privilege, such as the migration role during a botched fix.
--
-- Note honestly what this does not stop: the table owner can disable a trigger,
-- and a superuser can do anything. Off-site shipping of audit records (NFR-10.x)
-- is what covers that, and belongs in the observability workstream.
-- =============================================================================
create table audit.audit_logs (
    id            bigint generated always as identity primary key,
    tenant_id     uuid,
    actor_id      uuid,
    actor_role    varchar(32),
    action        varchar(96) not null,
    subject_type  varchar(96) not null,
    subject_id    uuid,
    before_state  jsonb,
    after_state   jsonb,
    ip_address    inet,
    user_agent    text,
    request_id    uuid,
    occurred_at   timestamptz not null default now()
);

-- No global tenant scope here on purpose: a platform administrator must be able
-- to audit across tenants, which is the one legitimate cross-tenant read.
create index audit_logs_tenant_idx  on audit.audit_logs (tenant_id, occurred_at desc);
create index audit_logs_subject_idx on audit.audit_logs (subject_type, subject_id, occurred_at desc);
create index audit_logs_actor_idx   on audit.audit_logs (actor_id, occurred_at desc);
create index audit_logs_action_idx  on audit.audit_logs (action, occurred_at desc);

create or replace function audit.reject_mutation()
returns trigger
language plpgsql
as $$
begin
    raise exception 'audit.audit_logs is append-only (NFR-4.6): % is not permitted', tg_op
        using errcode = 'restrict_violation';
end;
$$;

create trigger audit_logs_no_update
    before update on audit.audit_logs
    for each row execute function audit.reject_mutation();

create trigger audit_logs_no_delete
    before delete on audit.audit_logs
    for each row execute function audit.reject_mutation();

create trigger audit_logs_no_truncate
    before truncate on audit.audit_logs
    execute function audit.reject_mutation();

comment on table audit.audit_logs is
  'Append-only. Protected by role grants (primary) and triggers (secondary). Partition by month once volume warrants it — attach a new partition rather than deleting rows.';
