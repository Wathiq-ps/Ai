-- =============================================================================
-- Wathiq — 08. Payments, wallet ledger, receipts
--
-- Module 7 financial portions (FR-7.5 .. FR-7.9), SRS 3.8.2, UC-022, UC-051.
--
-- Scope note: FR-7.8 (wallet) is classified Phase 2, but UC-022 makes the wallet
-- the primary payment method in the MVP. A minimal wallet — balance, debit,
-- ledger — is therefore unavoidable now. Commission splitting (FR-7.10/7.11),
-- payouts (FR-7.12) and refunds (FR-7.17) stay out; SRS 7.5 already says
-- operations settles those manually during Phase 1.
--
-- The ledger is double-entry-shaped and append-only. Balances are derived, and
-- the derivation is checked by the database on every write. A payments system
-- where the balance column can drift from the entries is a payments system that
-- will eventually be wrong and unable to prove when it started being wrong.
-- =============================================================================

-- SRS 3.8.2
create type app.payment_status as enum (
    'pending',
    'processing',
    'succeeded',
    'failed',
    'cancelled',
    'refunded',      -- Phase 2 path; state exists so history stays representable
    'partially_refunded'
);

create type app.payment_method as enum ('wallet', 'card', 'bank_transfer', 'cash_deposit');

create table app.payments (
    id                 uuid primary key default app.uuid_generate_v7(),
    tenant_id          uuid not null references app.tenants (id) on delete restrict,
    reference          varchar(24) not null,
    contract_id        uuid not null,
    payer_id           uuid not null references app.users (id) on delete restrict,

    amount             app.money_minor   not null,
    currency           app.currency_code not null references app.currencies (code),
    method             app.payment_method not null,
    status             app.payment_status not null default 'pending',

    gateway            varchar(48),
    gateway_reference  varchar(128),
    gateway_payload    jsonb,

    -- UC-022 and UC-051 run against an external gateway over mobile networks.
    -- A retried POST must never charge twice; this is the anchor for that.
    idempotency_key    varchar(128) not null,

    initiated_at       timestamptz not null default now(),
    confirmed_at       timestamptz,
    failed_at          timestamptz,
    failure_code       varchar(64),
    failure_message    text,

    constraint payments_amount_positive check (amount > 0),
    constraint payments_succeeded_has_confirmation check (
        status <> 'succeeded' or confirmed_at is not null
    ),
    constraint payments_failed_has_code check (
        status <> 'failed' or failure_code is not null
    ),
    -- An external payment without a gateway reference cannot be reconciled.
    constraint payments_external_has_gateway_ref check (
        method = 'wallet' or status <> 'succeeded' or gateway_reference is not null
    ),

    unique (id, tenant_id),
    foreign key (contract_id, tenant_id)
        references app.contracts (id, tenant_id) on delete restrict
);

create unique index payments_reference_key       on app.payments (tenant_id, reference);
create unique index payments_idempotency_key     on app.payments (tenant_id, idempotency_key);
create unique index payments_gateway_ref_key     on app.payments (gateway, gateway_reference)
    where gateway_reference is not null;
-- At most one payment in flight or settled per contract in the MVP
-- (instalments are out of scope).
create unique index payments_one_live_per_contract
    on app.payments (contract_id)
    where status in ('pending', 'processing', 'succeeded');

create index payments_contract_idx on app.payments (contract_id, initiated_at desc);
create index payments_payer_idx    on app.payments (tenant_id, payer_id, initiated_at desc);
create index payments_pending_idx  on app.payments (status, initiated_at)
    where status in ('pending', 'processing');

-- Gateway callbacks, kept verbatim. When a reconciliation dispute happens the
-- question is always "what exactly did the gateway send us, and when".
create table app.payment_events (
    id            uuid primary key default app.uuid_generate_v7(),
    tenant_id     uuid not null references app.tenants (id) on delete restrict,
    payment_id    uuid not null,
    from_status   app.payment_status,
    to_status     app.payment_status not null,
    source        varchar(32) not null,   -- 'gateway' | 'system' | 'admin'
    raw_payload   jsonb,
    signature_ok  boolean,
    occurred_at   timestamptz not null default now(),

    foreign key (payment_id, tenant_id)
        references app.payments (id, tenant_id) on delete cascade
);

create index payment_events_payment_idx on app.payment_events (payment_id, occurred_at);

create trigger payment_events_immutable
    before update or delete on app.payment_events
    for each row execute function app.reject_any_change();

-- =============================================================================
-- Wallets and ledger
-- =============================================================================
create table app.wallets (
    id             uuid primary key default app.uuid_generate_v7(),
    tenant_id      uuid not null references app.tenants (id) on delete restrict,
    user_id        uuid not null references app.users (id) on delete restrict,
    currency       app.currency_code not null references app.currencies (code),
    -- Cached projection of the entries. Maintained by trigger and verified
    -- against balance_after on every insert; never written directly.
    balance        app.money_minor not null default 0,
    is_frozen      boolean not null default false,
    created_at     timestamptz not null default now(),
    updated_at     timestamptz not null default now(),

    unique (id, tenant_id)
);

-- One wallet per user per currency. Mixing currencies in one balance is how
-- multi-currency systems lose money.
create unique index wallets_user_currency_key on app.wallets (tenant_id, user_id, currency);

create trigger wallets_touch
    before update on app.wallets
    for each row execute function app.touch_updated_at();

create type app.ledger_direction as enum ('credit', 'debit');
create type app.ledger_reference_type as enum ('payment', 'refund', 'topup', 'withdrawal', 'commission', 'adjustment');

create table app.wallet_entries (
    id             uuid primary key default app.uuid_generate_v7(),
    tenant_id      uuid not null references app.tenants (id) on delete restrict,
    wallet_id      uuid not null,
    direction      app.ledger_direction not null,
    amount         app.money_minor not null,
    -- Running balance after this entry. Storing it makes the ledger auditable
    -- by inspection and lets the consistency trigger below catch a lost update
    -- immediately rather than at month-end reconciliation.
    balance_after  app.money_signed not null,
    reference_type app.ledger_reference_type not null,
    reference_id   uuid,
    description    text,
    created_at     timestamptz not null default now(),

    constraint wallet_entries_amount_positive check (amount > 0),
    constraint wallet_entries_balance_non_negative check (balance_after >= 0),

    foreign key (wallet_id, tenant_id)
        references app.wallets (id, tenant_id) on delete restrict
);

create index wallet_entries_wallet_idx on app.wallet_entries (wallet_id, created_at desc);
create index wallet_entries_ref_idx    on app.wallet_entries (reference_type, reference_id);
-- One ledger entry per source event: a replayed gateway callback must not
-- credit the wallet twice.
create unique index wallet_entries_reference_key
    on app.wallet_entries (wallet_id, reference_type, reference_id)
    where reference_id is not null;

create trigger wallet_entries_immutable
    before update or delete on app.wallet_entries
    for each row execute function app.reject_any_change();

-- Ledger integrity, enforced at write time.
--
-- Locks the wallet row, recomputes the balance from the entry, and rejects the
-- insert if the caller's balance_after disagrees. The FOR UPDATE lock is what
-- makes two concurrent debits serialise instead of both reading a stale balance
-- — the classic double-spend, and the reason this belongs in the database
-- rather than in a service that "remembers to use a transaction".
create or replace function app.apply_wallet_entry()
returns trigger
language plpgsql
as $$
declare
  current_balance bigint;
  wallet_currency app.currency_code;
  is_frozen       boolean;
  new_balance     bigint;
begin
    select balance, currency, w.is_frozen
      into current_balance, wallet_currency, is_frozen
      from app.wallets w
     where w.id = new.wallet_id
       for update;

    if not found then
        raise exception 'wallet % not found', new.wallet_id
            using errcode = 'foreign_key_violation';
    end if;

    if is_frozen then
        raise exception 'wallet % is frozen', new.wallet_id
            using errcode = 'restrict_violation';
    end if;

    new_balance := case new.direction
                     when 'credit' then current_balance + new.amount
                     when 'debit'  then current_balance - new.amount
                   end;

    if new_balance < 0 then
        raise exception 'insufficient funds in wallet %: balance %, debit %',
            new.wallet_id, current_balance, new.amount
            using errcode = 'restrict_violation';
    end if;

    if new.balance_after <> new_balance then
        raise exception
            'wallet_entries.balance_after is inconsistent: computed %, supplied %',
            new_balance, new.balance_after
            using errcode = 'restrict_violation';
    end if;

    update app.wallets set balance = new_balance where id = new.wallet_id;
    return new;
end;
$$;

create trigger wallet_entries_apply
    before insert on app.wallet_entries
    for each row execute function app.apply_wallet_entry();

-- Standalone reconciliation check, for the nightly job and for tests.
create or replace function app.assert_wallet_balances_consistent()
returns void
language plpgsql
as $$
declare
  drift record;
begin
    for drift in
        select w.id,
               w.balance as cached,
               coalesce(sum(case when e.direction = 'credit' then e.amount else -e.amount end), 0) as computed
          from app.wallets w
          left join app.wallet_entries e on e.wallet_id = w.id
         group by w.id, w.balance
        having w.balance <> coalesce(sum(case when e.direction = 'credit' then e.amount else -e.amount end), 0)
    loop
        raise exception 'wallet % balance drift: cached %, ledger %',
            drift.id, drift.cached, drift.computed
            using errcode = 'data_exception';
    end loop;
end;
$$;

-- =============================================================================
-- Receipts (FR-7.7)
-- =============================================================================
create table app.receipts (
    id           uuid primary key default app.uuid_generate_v7(),
    tenant_id    uuid not null references app.tenants (id) on delete restrict,
    payment_id   uuid not null,
    number       varchar(32) not null,
    pdf_path     text,
    pdf_sha256   app.sha256_hex,
    issued_at    timestamptz not null default now(),

    unique (id, tenant_id),
    foreign key (payment_id, tenant_id)
        references app.payments (id, tenant_id) on delete restrict
);

create unique index receipts_number_key  on app.receipts (tenant_id, number);
create unique index receipts_payment_key on app.receipts (payment_id);

create trigger receipts_immutable
    before update or delete on app.receipts
    for each row execute function app.reject_any_change();
