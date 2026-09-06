-- =============================================================================
-- Wathiq — 01. Reference data: tenants, currencies, jurisdictions, locations
--
-- Nothing here is tenant-scoped: this is platform-wide reference data shared by
-- every tenant. It is also the only place in the schema where a natural key
-- (ISO code) is preferred over a UUID, because these values are stable, public,
-- and appear in exported documents.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Tenants
--
-- SRS 2.1 and 2.8 both mandate isolation per real-estate company, but no use
-- case across all 134 creates or manages a tenant. tenant_id therefore lands on
-- every business table from migration #1 while the MVP seeds exactly one row.
-- Retrofitting this across ~40 tables holding live contract data is a six-week
-- job with a data-integrity risk on legal documents; carrying the column now
-- costs a few hours.
-- -----------------------------------------------------------------------------
create type app.tenant_status as enum ('active', 'suspended', 'closed');

create table app.tenants (
    id           uuid primary key default app.uuid_generate_v7(),
    slug         varchar(63)      not null,
    name_ar      varchar(255)     not null,
    name_en      varchar(255)     not null,
    status       app.tenant_status not null default 'active',
    settings     jsonb            not null default '{}'::jsonb,
    created_at   timestamptz      not null default now(),
    updated_at   timestamptz      not null default now(),

    constraint tenants_slug_format check (slug ~ '^[a-z0-9]([a-z0-9-]*[a-z0-9])?$')
);

create unique index tenants_slug_key on app.tenants (slug);

create trigger tenants_touch
    before update on app.tenants
    for each row execute function app.touch_updated_at();

-- -----------------------------------------------------------------------------
-- Currencies
--
-- `exponent` is the reason this table exists. Never assume 2.
-- -----------------------------------------------------------------------------
create table app.currencies (
    code        app.currency_code primary key,
    exponent    smallint     not null,
    name_ar     varchar(64)  not null,
    name_en     varchar(64)  not null,
    symbol      varchar(8)   not null,
    is_active   boolean      not null default true,

    constraint currencies_exponent_range check (exponent between 0 and 4)
);

insert into app.currencies (code, exponent, name_ar, name_en, symbol) values
    ('ILS', 2, 'شيكل إسرائيلي جديد', 'Israeli New Shekel', '₪'),
    ('JOD', 3, 'دينار أردني',        'Jordanian Dinar',    'د.أ'),
    ('USD', 2, 'دولار أمريكي',       'US Dollar',          '$'),
    ('EUR', 2, 'يورو',               'Euro',               '€');

comment on column app.currencies.exponent is
  'Number of decimal places. JOD is 3 (1000 fils), not 2. Read this column; never hardcode x100.';

-- -----------------------------------------------------------------------------
-- Countries and legal jurisdictions
--
-- NFR-2.4 requires supporting multiple countries and legal systems without a
-- redesign. Jurisdiction is modelled separately from country because a country
-- can hold several applicable bodies of law, and because the knowledge base and
-- contract both reference the jurisdiction, not the country.
-- -----------------------------------------------------------------------------
create table app.countries (
    id           uuid primary key default app.uuid_generate_v7(),
    iso2         char(2)      not null,
    iso3         char(3)      not null,
    name_ar      varchar(128) not null,
    name_en      varchar(128) not null,
    dial_code    varchar(8)   not null,
    is_supported boolean      not null default false,
    created_at   timestamptz  not null default now(),

    constraint countries_iso2_format check (iso2 ~ '^[A-Z]{2}$'),
    constraint countries_iso3_format check (iso3 ~ '^[A-Z]{3}$')
);

create unique index countries_iso2_key on app.countries (iso2);
create unique index countries_iso3_key on app.countries (iso3);

insert into app.countries (iso2, iso3, name_ar, name_en, dial_code, is_supported) values
    ('PS', 'PSE', 'فلسطين', 'Palestine', '+970', true);

create type app.law_type as enum ('sale', 'rent', 'ownership', 'tax', 'general');

create table app.jurisdictions (
    id            uuid primary key default app.uuid_generate_v7(),
    country_id    uuid         not null references app.countries (id) on delete restrict,
    code          varchar(32)  not null,
    name_ar       varchar(255) not null,
    name_en       varchar(255) not null,
    is_active     boolean      not null default true,
    created_at    timestamptz  not null default now(),

    constraint jurisdictions_code_format check (code ~ '^[A-Z0-9_]+$')
);

create unique index jurisdictions_country_code_key on app.jurisdictions (country_id, code);

-- -----------------------------------------------------------------------------
-- Locations (FR-13.6, UC-034)
--
-- Adjacency list plus a materialised path. The path denormalises the ancestor
-- chain so a subtree filter ("everything in Gaza governorate") is one index
-- range scan instead of a recursive CTE per search request — this sits directly
-- on the NFR-1.2 hot path.
--
-- Depth is shallow and administrative divisions change rarely, so a trigger
-- maintaining the path is cheaper than a closure table.
-- -----------------------------------------------------------------------------
create type app.location_level as enum ('country', 'governorate', 'city', 'area');

create table app.locations (
    id          uuid primary key default app.uuid_generate_v7(),
    parent_id   uuid         references app.locations (id) on delete restrict,
    country_id  uuid         not null references app.countries (id) on delete restrict,
    level       app.location_level not null,
    name_ar     varchar(191) not null,
    name_en     varchar(191) not null,
    path        text         not null default '',
    centroid    geography(Point, 4326),
    is_active   boolean      not null default true,
    created_at  timestamptz  not null default now(),
    updated_at  timestamptz  not null default now(),

    -- Only a country-level node may be rootless.
    constraint locations_root_is_country check (
        (parent_id is null and level = 'country') or
        (parent_id is not null and level <> 'country')
    )
);

create index locations_parent_idx  on app.locations (parent_id);
create index locations_country_idx on app.locations (country_id);
create index locations_path_idx    on app.locations (path text_pattern_ops);
create unique index locations_sibling_name_key
    on app.locations (coalesce(parent_id, '00000000-0000-0000-0000-000000000000'::uuid), name_ar);

create or replace function app.maintain_location_path()
returns trigger
language plpgsql
as $$
declare
  parent_path text := '';
begin
    if new.parent_id is not null then
        select path into parent_path from app.locations where id = new.parent_id;
    end if;
    new.path := parent_path || '/' || new.id::text;
    return new;
end;
$$;

create trigger locations_path
    before insert or update of parent_id on app.locations
    for each row execute function app.maintain_location_path();

create trigger locations_touch
    before update on app.locations
    for each row execute function app.touch_updated_at();

comment on column app.locations.path is
  'Materialised ancestor path, "/uuid/uuid/...". Subtree filter: path LIKE ''/<ancestor>/%''.';
