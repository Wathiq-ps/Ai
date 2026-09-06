-- =============================================================================
-- Wathiq — 02. Identity: users, RBAC, sessions, KYC
--
-- Module 1 (FR-1.x), Module 2 (FR-2.1/2.3), NFR-4.1/4.3/4.4.
--
-- Note on tenancy: `users` is deliberately NOT tenant-scoped. A person may hold
-- membership in more than one company; the membership is what carries the
-- tenant, via app.tenant_memberships. Putting tenant_id on users directly would
-- force duplicate accounts and duplicate KYC for the same human being.
-- =============================================================================

create type app.user_status as enum (
    'pending_verification',  -- registered, email not yet confirmed (UC-039)
    'active',
    'suspended',             -- admin action (FR-13.1)
    'deactivated'            -- user-initiated
);

create table app.users (
    id                 uuid primary key default app.uuid_generate_v7(),
    email              app.email        not null,
    phone              app.phone,
    password_hash      text             not null,
    status             app.user_status  not null default 'pending_verification',
    locale             app.locale       not null default 'ar',
    email_verified_at  timestamptz,
    phone_verified_at  timestamptz,
    last_login_at      timestamptz,
    -- NFR-4.5 brute-force protection. Cleared on successful authentication.
    failed_login_count smallint         not null default 0,
    locked_until       timestamptz,
    created_at         timestamptz      not null default now(),
    updated_at         timestamptz      not null default now(),
    deleted_at         timestamptz,

    constraint users_verified_implies_timestamp check (
        status <> 'pending_verification' or email_verified_at is null
    )
);

-- Partial: a soft-deleted account must not block re-registration of the address.
create unique index users_email_key on app.users (email) where deleted_at is null;
create unique index users_phone_key on app.users (phone) where phone is not null and deleted_at is null;
create index users_status_idx on app.users (status) where deleted_at is null;

create trigger users_touch
    before update on app.users
    for each row execute function app.touch_updated_at();

comment on column app.users.password_hash is
  'Argon2id preferred, bcrypt acceptable (NFR-4.3). Never plaintext, never reversible encryption.';

-- -----------------------------------------------------------------------------
-- Profiles
-- -----------------------------------------------------------------------------
create table app.user_profiles (
    user_id          uuid primary key references app.users (id) on delete cascade,
    first_name       varchar(96)  not null,
    last_name        varchar(96)  not null,
    display_name     varchar(191) generated always as (first_name || ' ' || last_name) stored,
    national_id      varchar(32),
    date_of_birth    date,
    nationality_id   uuid references app.countries (id),
    address_line     varchar(255),
    location_id      uuid references app.locations (id),
    avatar_path      text,
    bio              text,
    created_at       timestamptz  not null default now(),
    updated_at       timestamptz  not null default now(),

    constraint user_profiles_dob_sane check (
        date_of_birth is null or date_of_birth between '1900-01-01' and current_date
    )
);

create trigger user_profiles_touch
    before update on app.user_profiles
    for each row execute function app.touch_updated_at();

-- -----------------------------------------------------------------------------
-- RBAC (NFR-4.4)
--
-- Role assignment is tenant-scoped: the same person can be a lawyer for one
-- company and an owner in another. Permissions are seeded, not user-editable in
-- the MVP (role/permission administration is Phase 2, FR-13.2).
-- -----------------------------------------------------------------------------
create table app.roles (
    id          uuid primary key default app.uuid_generate_v7(),
    code        varchar(32)  not null,
    name_ar     varchar(96)  not null,
    name_en     varchar(96)  not null,
    is_system   boolean      not null default true,
    created_at  timestamptz  not null default now(),

    constraint roles_code_format check (code ~ '^[a-z_]+$')
);

create unique index roles_code_key on app.roles (code);

insert into app.roles (code, name_ar, name_en) values
    ('admin',       'مدير النظام',   'System Administrator'),
    ('owner',       'مالك عقار',     'Property Owner'),
    ('beneficiary', 'مستفيد',        'Beneficiary'),
    ('lawyer',      'محامٍ معتمد',   'Licensed Lawyer'),
    ('broker',      'وسيط عقاري',    'Real Estate Broker');  -- Phase 2, seeded now

create table app.permissions (
    id          uuid primary key default app.uuid_generate_v7(),
    code        varchar(64)  not null,
    description varchar(255) not null,

    constraint permissions_code_format check (code ~ '^[a-z_]+\.[a-z_]+$')
);

create unique index permissions_code_key on app.permissions (code);

create table app.role_permissions (
    role_id       uuid not null references app.roles (id)       on delete cascade,
    permission_id uuid not null references app.permissions (id) on delete cascade,
    primary key (role_id, permission_id)
);

create type app.membership_status as enum ('active', 'suspended', 'revoked');

create table app.tenant_memberships (
    id          uuid primary key default app.uuid_generate_v7(),
    tenant_id   uuid not null references app.tenants (id) on delete restrict,
    user_id     uuid not null references app.users (id)   on delete cascade,
    role_id     uuid not null references app.roles (id)   on delete restrict,
    status      app.membership_status not null default 'active',
    granted_by  uuid references app.users (id),
    granted_at  timestamptz not null default now(),
    revoked_at  timestamptz,

    constraint memberships_revoked_has_timestamp check (
        (status = 'revoked') = (revoked_at is not null)
    )
);

create unique index memberships_unique_active
    on app.tenant_memberships (tenant_id, user_id, role_id)
    where status <> 'revoked';

create index memberships_user_idx   on app.tenant_memberships (user_id)   where status = 'active';
create index memberships_tenant_idx on app.tenant_memberships (tenant_id) where status = 'active';

-- Lawyer licensing (FR-13.5). Kept separate from the profile because it carries
-- its own verification lifecycle and only applies to one role.
create table app.lawyer_credentials (
    user_id            uuid primary key references app.users (id) on delete cascade,
    license_number     varchar(64)  not null,
    bar_association    varchar(191) not null,
    jurisdiction_id    uuid         not null references app.jurisdictions (id),
    issued_at          date         not null,
    expires_at         date,
    verified_at        timestamptz,
    verified_by        uuid references app.users (id),
    document_path      text         not null,
    created_at         timestamptz  not null default now(),
    updated_at         timestamptz  not null default now(),

    constraint lawyer_credentials_validity check (expires_at is null or expires_at > issued_at)
);

create unique index lawyer_credentials_license_key
    on app.lawyer_credentials (jurisdiction_id, license_number);

create trigger lawyer_credentials_touch
    before update on app.lawyer_credentials
    for each row execute function app.touch_updated_at();

-- -----------------------------------------------------------------------------
-- Sessions and refresh-token rotation (NFR-4.1, UC-045, UC-084, UC-085)
--
-- Access tokens are stateless JWTs and are not stored. Refresh tokens are, so
-- that "terminate other sessions" is possible at all — and so a replayed token
-- is detectable.
--
-- Rotation chain: each refresh mints a successor and sets replaced_by_id on the
-- predecessor. Presenting an already-replaced token means the token leaked;
-- the correct response is to revoke the whole chain, which `session_family_id`
-- makes a single indexed UPDATE.
-- -----------------------------------------------------------------------------
create type app.session_revocation_reason as enum (
    'logout', 'rotated', 'user_terminated', 'admin_terminated', 'reuse_detected', 'expired'
);

create table app.user_sessions (
    id                 uuid primary key default app.uuid_generate_v7(),
    user_id            uuid        not null references app.users (id) on delete cascade,
    session_family_id  uuid        not null,
    -- SHA-256 of the token. The token itself never touches the database, so a
    -- dump of this table cannot be replayed against the API.
    token_hash         app.sha256_hex not null,
    replaced_by_id     uuid        references app.user_sessions (id) on delete set null,
    device_name        varchar(191),
    ip_address         inet,
    user_agent         text,
    issued_at          timestamptz not null default now(),
    last_used_at       timestamptz,
    expires_at         timestamptz not null,
    revoked_at         timestamptz,
    revocation_reason  app.session_revocation_reason,

    constraint sessions_expiry_after_issue check (expires_at > issued_at),
    constraint sessions_revoked_has_reason check ((revoked_at is null) = (revocation_reason is null))
);

create unique index sessions_token_hash_key on app.user_sessions (token_hash);
create index sessions_active_idx on app.user_sessions (user_id) where revoked_at is null;
create index sessions_family_idx on app.user_sessions (session_family_id) where revoked_at is null;
create index sessions_expiry_idx on app.user_sessions (expires_at) where revoked_at is null;

create trigger sessions_immutable
    before update on app.user_sessions
    for each row execute function app.reject_column_change('user_id', 'token_hash', 'issued_at', 'session_family_id');

-- -----------------------------------------------------------------------------
-- One-time tokens: email verification (UC-039) and password reset (UC-041)
-- -----------------------------------------------------------------------------
create type app.one_time_token_purpose as enum ('email_verification', 'password_reset', 'email_change');

create table app.one_time_tokens (
    id          uuid primary key default app.uuid_generate_v7(),
    user_id     uuid        not null references app.users (id) on delete cascade,
    purpose     app.one_time_token_purpose not null,
    token_hash  app.sha256_hex not null,
    payload     jsonb,          -- e.g. the requested new address for email_change
    expires_at  timestamptz not null,
    consumed_at timestamptz,
    created_at  timestamptz not null default now(),
    request_ip  inet
);

create unique index one_time_tokens_hash_key on app.one_time_tokens (token_hash);
-- At most one live token per purpose per user: re-requesting invalidates the old one.
create unique index one_time_tokens_live_key
    on app.one_time_tokens (user_id, purpose)
    where consumed_at is null;

-- -----------------------------------------------------------------------------
-- KYC / identity documents (FR-2.1, FR-2.3, UC-040)
--
-- Files live in private object storage and are served only via short-lived
-- signed URLs — this table holds the key, never a public URL.
-- -----------------------------------------------------------------------------
create type app.verification_status as enum ('pending', 'under_review', 'approved', 'rejected');
create type app.identity_document_type as enum ('national_id', 'passport', 'residency_permit', 'commercial_register');

create table app.identity_documents (
    id             uuid primary key default app.uuid_generate_v7(),
    tenant_id      uuid not null references app.tenants (id) on delete restrict,
    user_id        uuid not null references app.users (id)   on delete cascade,
    type           app.identity_document_type not null,
    document_number varchar(64) not null,
    issuing_country_id uuid references app.countries (id),
    front_path     text        not null,
    back_path      text,
    expires_on     date,
    status         app.verification_status not null default 'pending',
    reviewed_by    uuid        references app.users (id),
    reviewed_at    timestamptz,
    rejection_reason text,
    created_at     timestamptz not null default now(),
    updated_at     timestamptz not null default now(),

    constraint identity_documents_review_complete check (
        status not in ('approved', 'rejected') or (reviewed_by is not null and reviewed_at is not null)
    ),
    constraint identity_documents_rejection_has_reason check (
        status <> 'rejected' or rejection_reason is not null
    )
);

-- One approved identity document per user per tenant; re-submission is allowed
-- only while nothing is approved.
create unique index identity_documents_approved_key
    on app.identity_documents (tenant_id, user_id)
    where status = 'approved';

create index identity_documents_queue_idx
    on app.identity_documents (tenant_id, status, created_at)
    where status in ('pending', 'under_review');

create trigger identity_documents_touch
    before update on app.identity_documents
    for each row execute function app.touch_updated_at();
