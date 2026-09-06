-- =============================================================================
-- Wathiq — 07. Electronic signature and contract sealing
--
-- Module 7 signature portions (FR-7.1 .. FR-7.4), UC-030, UC-046, UC-058, UC-059.
--
-- If any part of this schema is going to be challenged in a dispute, it is this
-- one. Two rules drive the design:
--
--   1. A signature is evidence, not a status flag. It records who signed, when
--      (server clock, never the client's), from where, and — critically — the
--      hash of the document as it existed at that moment. Without that last
--      field you can prove somebody signed but not what they agreed to.
--   2. Everything here is append-only. There is no legitimate reason to update
--      a signature row; the ability to do so is itself the vulnerability.
-- =============================================================================

create type app.signer_role     as enum ('owner', 'beneficiary', 'lawyer', 'broker', 'witness');
create type app.signature_method as enum ('drawn', 'typed', 'uploaded_image', 'otp_confirmed');
create type app.signature_invitation_status as enum ('pending', 'viewed', 'signed', 'declined', 'expired', 'revoked');

-- -----------------------------------------------------------------------------
-- Invitations (FR-7.1, UC-030)
--
-- Bound to a specific contract_version_id. If the contract is amended after
-- invitations go out, the version changes and outstanding invitations must be
-- reissued — otherwise a party could sign a document that has since been
-- rewritten. The FK carries that rule.
-- -----------------------------------------------------------------------------
create table app.signature_invitations (
    id                  uuid primary key default app.uuid_generate_v7(),
    tenant_id           uuid not null references app.tenants (id) on delete restrict,
    contract_id         uuid not null,
    contract_version_id uuid not null,
    signer_id           uuid not null references app.users (id) on delete restrict,
    signer_role         app.signer_role not null,
    signing_order       smallint not null default 1,
    token_hash          app.sha256_hex not null,
    status              app.signature_invitation_status not null default 'pending',
    sent_at             timestamptz not null default now(),
    viewed_at           timestamptz,
    responded_at        timestamptz,
    expires_at          timestamptz not null,
    decline_reason      text,

    constraint invitations_expiry_after_send check (expires_at > sent_at),
    constraint invitations_declined_has_reason check (
        status <> 'declined' or decline_reason is not null
    ),

    unique (id, tenant_id),
    foreign key (contract_id, tenant_id)
        references app.contracts (id, tenant_id) on delete cascade,
    foreign key (contract_version_id, tenant_id)
        references app.contract_versions (id, tenant_id) on delete restrict
);

create unique index invitations_token_key on app.signature_invitations (token_hash);
-- One live invitation per signer per version.
create unique index invitations_one_live_per_signer
    on app.signature_invitations (contract_version_id, signer_id)
    where status in ('pending', 'viewed');
create index invitations_contract_idx on app.signature_invitations (contract_id, signing_order);
create index invitations_expiry_idx   on app.signature_invitations (expires_at)
    where status in ('pending', 'viewed');

-- -----------------------------------------------------------------------------
-- Signatures (FR-7.2, UC-046)
-- -----------------------------------------------------------------------------
create table app.signatures (
    id                  uuid primary key default app.uuid_generate_v7(),
    tenant_id           uuid not null references app.tenants (id) on delete restrict,
    contract_id         uuid not null,
    contract_version_id uuid not null,
    invitation_id       uuid references app.signature_invitations (id) on delete restrict,
    signer_id           uuid not null references app.users (id) on delete restrict,
    signer_role         app.signer_role not null,

    -- Identity as it stood at signing time. Denormalised on purpose: if the
    -- user later changes their legal name, the contract must still show the
    -- name that signed it.
    signer_name_snapshot     varchar(191) not null,
    signer_national_id_snapshot varchar(32),

    method              app.signature_method not null,
    signature_image_path text,

    -- The evidentiary core. document_hash must equal the content_hash of
    -- contract_version_id at the moment of signing; the trigger below verifies
    -- it rather than trusting the caller.
    document_hash       app.sha256_hex not null,

    -- Server clock. Never accept a client-supplied signing time.
    signed_at           timestamptz not null default now(),
    ip_address          inet not null,
    user_agent          text not null,
    -- Anything else worth preserving: geolocation, OTP reference, device id.
    evidence            jsonb not null default '{}'::jsonb,

    constraint signatures_drawn_has_image check (
        method not in ('drawn', 'uploaded_image') or signature_image_path is not null
    ),

    foreign key (contract_id, tenant_id)
        references app.contracts (id, tenant_id) on delete restrict,
    foreign key (contract_version_id, tenant_id)
        references app.contract_versions (id, tenant_id) on delete restrict
);

-- A party signs a given version exactly once.
create unique index signatures_one_per_signer_per_version
    on app.signatures (contract_version_id, signer_id);
create index signatures_contract_idx on app.signatures (contract_id, signed_at);

create trigger signatures_immutable
    before update or delete on app.signatures
    for each row execute function app.reject_any_change();

-- Verify the hash against the version rather than taking the application's word
-- for it. A mismatch means the signing flow read a different document than the
-- one it recorded — the exact failure this column exists to make impossible.
create or replace function app.verify_signature_document_hash()
returns trigger
language plpgsql
as $$
declare
  expected app.sha256_hex;
begin
    select content_hash into expected
      from app.contract_versions
     where id = new.contract_version_id;

    if expected is null then
        raise exception 'contract version % not found', new.contract_version_id
            using errcode = 'foreign_key_violation';
    end if;

    if new.document_hash <> expected then
        raise exception
            'signature document_hash does not match contract version % (expected %, got %)',
            new.contract_version_id, expected, new.document_hash
            using errcode = 'restrict_violation',
                  hint = 'The signing flow rendered a document that is not the stored version.';
    end if;

    return new;
end;
$$;

create trigger signatures_verify_hash
    before insert on app.signatures
    for each row execute function app.verify_signature_document_hash();

-- -----------------------------------------------------------------------------
-- Seals (UC-059)
--
-- Produced once, when the contract becomes fully signed: the final rendered PDF,
-- its SHA-256, the AI provenance required by NFR-12.3, and the ordered signature
-- evidence frozen as it stood. This row is what a QR verification resolves
-- against and what an expert would be handed in a dispute.
-- -----------------------------------------------------------------------------
create table app.contract_seals (
    id                  uuid primary key default app.uuid_generate_v7(),
    tenant_id           uuid not null references app.tenants (id) on delete restrict,
    contract_id         uuid not null,
    contract_version_id uuid not null,

    pdf_path            text not null,
    pdf_sha256          app.sha256_hex not null,
    pdf_size_bytes      bigint not null,

    -- Provenance snapshot (NFR-12.3), copied rather than joined so the seal
    -- remains self-contained if the job record is ever pruned.
    model_id            varchar(128),
    model_version       varchar(64),
    kb_version_tag      varchar(64),

    -- Ordered [{signer_id, role, signed_at, document_hash, ip}, ...]
    signature_evidence  jsonb not null,
    signature_count     smallint not null,

    sealed_at           timestamptz not null default now(),

    constraint seals_signature_count_positive check (signature_count > 0),
    constraint seals_pdf_size_positive check (pdf_size_bytes > 0),
    constraint seals_evidence_is_array check (jsonb_typeof(signature_evidence) = 'array'),

    unique (id, tenant_id),
    foreign key (contract_id, tenant_id)
        references app.contracts (id, tenant_id) on delete restrict,
    foreign key (contract_version_id, tenant_id)
        references app.contract_versions (id, tenant_id) on delete restrict
);

-- Exactly one seal per contract. Re-sealing would create two documents both
-- claiming to be final.
create unique index seals_one_per_contract on app.contract_seals (contract_id);
create unique index seals_pdf_hash_key     on app.contract_seals (pdf_sha256);

create trigger seals_immutable
    before update or delete on app.contract_seals
    for each row execute function app.reject_any_change();
