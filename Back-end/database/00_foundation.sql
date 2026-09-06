-- =============================================================================
-- Wathiq — 00. Foundation: extensions, schemas, roles, primitives
-- PostgreSQL 17
--
-- Run order matters. This file must run first and must run as a role that can
-- CREATE EXTENSION and CREATE ROLE (on Supabase, the `postgres` role).
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Extensions
-- -----------------------------------------------------------------------------
create extension if not exists pgcrypto;    -- gen_random_bytes, digest
create extension if not exists citext;      -- case-insensitive email
create extension if not exists pg_trgm;     -- fuzzy property search
create extension if not exists btree_gist;  -- uuid `=` inside GiST exclusion constraints
create extension if not exists postgis;     -- radius / nearest search (UC-017, UC-025)
create extension if not exists vector;      -- legal knowledge base embeddings

-- -----------------------------------------------------------------------------
-- Schemas
--
-- The split is a privilege boundary, not organisation for its own sake:
--   app       business data; the application role owns read/write here
--   knowledge legal KB + embeddings; the AI service role reads ONLY this
--   ops       outbox, idempotency, webhook deliveries — infrastructure state
--   audit     append-only. No role holds UPDATE or DELETE. See 09_platform.sql
-- -----------------------------------------------------------------------------
create schema if not exists app;
create schema if not exists knowledge;
create schema if not exists ops;
create schema if not exists audit;

-- -----------------------------------------------------------------------------
-- Roles
--
-- Least privilege is the point. `wathiq_app` deliberately cannot mutate the
-- audit log; that is what makes NFR-4.6 ("un-modifiable, un-deletable") a
-- property of the database rather than a promise made by application code.
--
-- Passwords are placeholders — set them from the environment at provisioning.
-- -----------------------------------------------------------------------------
do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'wathiq_migrator') then
    create role wathiq_migrator login password 'CHANGE_ME';
  end if;
  if not exists (select 1 from pg_roles where rolname = 'wathiq_app') then
    create role wathiq_app login password 'CHANGE_ME';
  end if;
  if not exists (select 1 from pg_roles where rolname = 'wathiq_ai') then
    create role wathiq_ai login password 'CHANGE_ME';
  end if;
  if not exists (select 1 from pg_roles where rolname = 'wathiq_readonly') then
    create role wathiq_readonly login password 'CHANGE_ME';
  end if;
end
$$;

-- =============================================================================
-- Identifiers
-- =============================================================================

-- UUIDv7: time-ordered, so inserts stay at the right edge of the B-tree instead
-- of scattering across it the way v4 does. Public-facing IDs must not be
-- sequential integers — those leak transaction volume to competitors and make
-- enumeration trivial on a system where the objects are contracts.
--
-- PostgreSQL 18 ships uuidv7() natively. On 18+, drop this and alias it.
create or replace function app.uuid_generate_v7()
returns uuid
language plpgsql
volatile
parallel safe
as $$
declare
  v_ms    bigint := (extract(epoch from clock_timestamp()) * 1000)::bigint;
  v_bytes bytea  := gen_random_bytes(16);
begin
  -- bytes 0-5: big-endian millisecond timestamp
  v_bytes := set_byte(v_bytes, 0, ((v_ms >> 40) & 255)::int);
  v_bytes := set_byte(v_bytes, 1, ((v_ms >> 32) & 255)::int);
  v_bytes := set_byte(v_bytes, 2, ((v_ms >> 24) & 255)::int);
  v_bytes := set_byte(v_bytes, 3, ((v_ms >> 16) & 255)::int);
  v_bytes := set_byte(v_bytes, 4, ((v_ms >>  8) & 255)::int);
  v_bytes := set_byte(v_bytes, 5, ( v_ms        & 255)::int);
  -- byte 6 high nibble: version 7
  v_bytes := set_byte(v_bytes, 6, (get_byte(v_bytes, 6) & 15) | 112);
  -- byte 8 high bits: RFC 4122 variant
  v_bytes := set_byte(v_bytes, 8, (get_byte(v_bytes, 8) & 63) | 128);
  return encode(v_bytes, 'hex')::uuid;
end;
$$;

comment on function app.uuid_generate_v7() is
  'RFC 9562 UUIDv7. Time-ordered for index locality. Replace with native uuidv7() on PostgreSQL 18+.';

-- =============================================================================
-- Money
--
-- Every monetary value is (BIGINT minor units, ISO-4217 code). No float, ever.
-- The minor-unit exponent is per-currency and read from app.currencies — it is
-- NOT always 2. Palestine circulates ILS (2), USD (2) and JOD (3). A hardcoded
-- x100 silently divides every JOD amount by ten, on legal instruments.
-- =============================================================================
create domain app.money_minor as bigint
  constraint money_minor_non_negative check (value >= 0);

create domain app.money_signed as bigint;   -- ledger deltas only

create domain app.currency_code as char(3)
  constraint currency_code_format check (value ~ '^[A-Z]{3}$');

comment on domain app.money_minor is
  'Monetary amount in minor units. Pair with a currency_code column; resolve the exponent via app.currencies.';

-- =============================================================================
-- Common column helpers
-- =============================================================================
create domain app.email as citext
  constraint email_format check (value ~ '^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$');

-- E.164
create domain app.phone as varchar(20)
  constraint phone_format check (value ~ '^\+[1-9][0-9]{7,14}$');

create domain app.sha256_hex as char(64)
  constraint sha256_hex_format check (value ~ '^[0-9a-f]{64}$');

create type app.locale as enum ('ar', 'en');

-- -----------------------------------------------------------------------------
-- updated_at maintenance
-- -----------------------------------------------------------------------------
create or replace function app.touch_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at := now();
  return new;
end;
$$;

-- -----------------------------------------------------------------------------
-- Immutable-column guard
--
-- Applied to columns that must never change after insert (signature evidence,
-- seal hashes, ledger entries). Cheaper and more reliable than remembering.
-- -----------------------------------------------------------------------------
create or replace function app.reject_column_change()
returns trigger
language plpgsql
as $$
declare
  col text;
begin
  foreach col in array tg_argv loop
    if to_jsonb(new) -> col is distinct from to_jsonb(old) -> col then
      raise exception
        'column %.%.% is immutable once written', tg_table_schema, tg_table_name, col
        using errcode = 'restrict_violation';
    end if;
  end loop;
  return new;
end;
$$;

-- =============================================================================
-- Arabic text normalisation
--
-- Arabic search fails without this. Users type "احمد" and the listing says
-- "أحمد"; they type "شقه" and it says "شقة". The snowball stemmer does not
-- fold those. Normalise before building the tsvector:
--   * strip harakat (U+064B-U+0652), superscript alef (U+0670), tatweel (U+0640)
--   * fold alef forms  أ إ آ ٱ -> ا
--   * fold ta marbuta  ة -> ه
--   * fold alef maqsura ى -> ي
--   * fold Arabic-Indic digits ٠-٩ -> 0-9
--
-- IMMUTABLE so it is usable inside index expressions.
-- =============================================================================
create or replace function app.normalize_arabic(t text)
returns text
language sql
immutable
strict
parallel safe
as $$
  select translate(
           regexp_replace(t, E'[ً-ْٰـ]', '', 'g'),
           E'أإآٱةى٠١٢٣٤٥٦٧٨٩',
           E'ااااهي0123456789'
         );
$$;

comment on function app.normalize_arabic(text) is
  'Folds Arabic orthographic variants before tokenisation. Apply to both indexed text and query text — asymmetric application silently breaks matching.';

-- Bilingual document builder. 'simple' retains exact tokens (reference numbers,
-- transliterations); 'arabic' and 'english' add stemming.
create or replace function app.to_bilingual_tsvector(t text)
returns tsvector
language sql
immutable
strict
parallel safe
as $$
  select to_tsvector('simple',  app.normalize_arabic(t))
      || to_tsvector('arabic',  app.normalize_arabic(t))
      || to_tsvector('english', t);
$$;

-- =============================================================================
-- Guard against floating-point money
--
-- backendArch.md specifies a CI check. This is the same rule enforced one layer
-- lower, where it cannot be skipped by someone running migrations by hand.
-- Call it after every migration run; it raises if any real/double/float column
-- exists in a business schema.
-- =============================================================================
create or replace function app.assert_no_float_columns()
returns void
language plpgsql
as $$
declare
  offending text;
begin
  select string_agg(format('%I.%I.%I (%s)', table_schema, table_name, column_name, data_type), ', ')
    into offending
    from information_schema.columns
   where table_schema in ('app', 'ops', 'audit', 'knowledge')
     and data_type in ('real', 'double precision')
     -- pgvector and PostGIS internals are exempt
     and udt_name not in ('vector', 'geography', 'geometry');

  if offending is not null then
    raise exception 'floating-point columns are forbidden: %', offending
      using errcode = 'restrict_violation',
            hint = 'Monetary values use app.money_minor + app.currency_code. Scores use smallint or numeric.';
  end if;
end;
$$;
