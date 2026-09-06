-- =============================================================================
-- Wathiq — 03. Properties: listings, media, ownership proof, search
--
-- Module 3 (FR-3.x), Module 4 (FR-4.x), NFR-1.2 (<=2s over 100,000 properties).
--
-- Tenant-integrity pattern used from here on:
--   parent  ... unique (id, tenant_id)
--   child   ... foreign key (parent_id, tenant_id) references parent (id, tenant_id)
-- The composite reference makes a cross-tenant row pair structurally
-- impossible. An application bug can then produce a foreign-key violation, but
-- never a photograph of one company's property attached to another's listing.
-- =============================================================================

create type app.property_type as enum (
    'apartment', 'house', 'villa', 'land', 'office', 'shop', 'warehouse', 'building', 'farm'
);

create type app.listing_type as enum ('sale', 'rent');

-- FR-3.5. `draft` and `pending_verification` are pre-publication; `under_contract`
-- is entered when a request is accepted and released on contract cancellation.
create type app.property_status as enum (
    'draft',
    'pending_verification',
    'published',
    'paused',
    'under_contract',
    'sold',
    'rented',
    'archived',
    'rejected'
);

create table app.properties (
    id                 uuid primary key default app.uuid_generate_v7(),
    tenant_id          uuid not null references app.tenants (id) on delete restrict,
    reference          varchar(24) not null,
    owner_id           uuid not null references app.users (id) on delete restrict,
    -- Phase 2 delegation (FR-3.6/3.7). Column present now; no MVP write path.
    broker_id          uuid references app.users (id) on delete set null,

    title              varchar(191) not null,
    description        text,
    type               app.property_type not null,
    listing_type       app.listing_type  not null,
    status             app.property_status not null default 'draft',

    price_amount       app.money_minor   not null,
    price_currency     app.currency_code not null references app.currencies (code),

    area_sqm           numeric(10, 2) not null,
    rooms              smallint,
    bathrooms          smallint,
    floor_number       smallint,
    total_floors       smallint,
    year_built         smallint,
    is_furnished       boolean not null default false,

    location_id        uuid not null references app.locations (id) on delete restrict,
    address_line       varchar(255),
    coordinates        geography(Point, 4326),

    -- Maintained by trigger; see app.refresh_property_search below.
    search_document    tsvector,

    published_at       timestamptz,
    archived_at        timestamptz,
    created_at         timestamptz not null default now(),
    updated_at         timestamptz not null default now(),
    deleted_at         timestamptz,

    constraint properties_area_positive   check (area_sqm > 0),
    constraint properties_rooms_sane      check (rooms      is null or rooms      between 0 and 100),
    constraint properties_bathrooms_sane  check (bathrooms  is null or bathrooms  between 0 and 100),
    constraint properties_year_sane       check (year_built is null or year_built between 1800 and extract(year from current_date) + 5),
    constraint properties_floors_sane     check (total_floors is null or floor_number is null or floor_number <= total_floors),
    constraint properties_published_has_timestamp check (
        status <> 'published' or published_at is not null
    ),
    -- Land has no rooms, bathrooms or floors. Cheap rule, prevents nonsense listings.
    constraint properties_land_has_no_rooms check (
        type <> 'land' or (rooms is null and bathrooms is null and floor_number is null)
    ),

    unique (id, tenant_id)
);

create unique index properties_reference_key on app.properties (tenant_id, reference);

-- NFR-1.2 hot path. The composite covers the overwhelmingly common query shape:
-- "published listings in this tenant, of this listing type, newest first".
create index properties_browse_idx
    on app.properties (tenant_id, listing_type, published_at desc)
    where status = 'published' and deleted_at is null;

create index properties_owner_idx    on app.properties (tenant_id, owner_id) where deleted_at is null;
create index properties_location_idx on app.properties (location_id)         where status = 'published';
create index properties_price_idx    on app.properties (tenant_id, price_currency, price_amount) where status = 'published';
create index properties_type_idx     on app.properties (tenant_id, type)     where status = 'published';

-- Full-text (NFR-1.2) and geospatial (UC-017 radius, UC-025 nearest).
create index properties_search_idx on app.properties using gin (search_document);
create index properties_geo_idx    on app.properties using gist (coordinates) where status = 'published';
-- Trigram fallback for short/misspelled fragments the tsvector will not match.
create index properties_title_trgm_idx on app.properties using gin (app.normalize_arabic(title) gin_trgm_ops);

create trigger properties_touch
    before update on app.properties
    for each row execute function app.touch_updated_at();

comment on column app.properties.reference is
  'Human-readable listing reference shown to users and printed on contracts. Generated by the application, unique per tenant.';

-- -----------------------------------------------------------------------------
-- Search document maintenance
--
-- Chosen over a materialised view deliberately. A matview needs REFRESH
-- CONCURRENTLY, a unique index, a scheduler, and it is stale between refreshes
-- — an owner who fixes a typo expects the listing to be findable immediately.
-- A trigger keeps it transactional and always current; at ~100k rows with a few
-- hundred writes a day the write cost is irrelevant next to the read benefit.
--
-- Weights: A title, B location, C description, D address.
-- -----------------------------------------------------------------------------
create or replace function app.refresh_property_search()
returns trigger
language plpgsql
as $$
declare
  location_text text;
begin
    select l.name_ar || ' ' || l.name_en
      into location_text
      from app.locations l
     where l.id = new.location_id;

    new.search_document :=
        setweight(app.to_bilingual_tsvector(coalesce(new.title, '')),        'A') ||
        setweight(app.to_bilingual_tsvector(coalesce(location_text, '')),    'B') ||
        setweight(app.to_bilingual_tsvector(coalesce(new.description, '')),  'C') ||
        setweight(app.to_bilingual_tsvector(coalesce(new.address_line, '')), 'D') ||
        setweight(to_tsvector('simple', coalesce(new.reference, '')),        'A');
    return new;
end;
$$;

create trigger properties_search_document
    before insert or update of title, description, address_line, location_id, reference
    on app.properties
    for each row execute function app.refresh_property_search();

-- -----------------------------------------------------------------------------
-- Media (FR-3.4, UC-003)
-- -----------------------------------------------------------------------------
create table app.property_media (
    id           uuid primary key default app.uuid_generate_v7(),
    tenant_id    uuid not null references app.tenants (id) on delete restrict,
    property_id  uuid not null,
    disk         varchar(32)  not null default 'private',
    path         text         not null,
    mime_type    varchar(96)  not null,
    size_bytes   bigint       not null,
    width        integer,
    height       integer,
    checksum     app.sha256_hex not null,
    is_cover     boolean      not null default false,
    sort_order   smallint     not null default 0,
    created_at   timestamptz  not null default now(),

    constraint property_media_size_positive check (size_bytes > 0),
    constraint property_media_is_image check (mime_type like 'image/%'),

    foreign key (property_id, tenant_id)
        references app.properties (id, tenant_id) on delete cascade
);

create index property_media_property_idx on app.property_media (property_id, sort_order);
create unique index property_media_single_cover on app.property_media (property_id) where is_cover;
-- Same file uploaded twice to one listing is a duplicate, not two photos.
create unique index property_media_checksum_key on app.property_media (property_id, checksum);

-- -----------------------------------------------------------------------------
-- Ownership documents (FR-2.2, FR-2.4, UC-004)
--
-- BR: a property may not be published until at least one ownership document is
-- approved. Enforced in the publish transition, not here — a CHECK cannot span
-- tables, and a trigger doing the lookup on every property UPDATE would cost
-- more than it protects.
-- -----------------------------------------------------------------------------
create type app.ownership_document_type as enum (
    'title_deed', 'sale_contract', 'inheritance_deed', 'power_of_attorney', 'municipal_record'
);

create table app.ownership_documents (
    id               uuid primary key default app.uuid_generate_v7(),
    tenant_id        uuid not null references app.tenants (id) on delete restrict,
    property_id      uuid not null,
    uploaded_by      uuid not null references app.users (id) on delete restrict,
    type             app.ownership_document_type not null,
    document_number  varchar(64),
    issued_on        date,
    path             text        not null,
    checksum         app.sha256_hex not null,
    status           app.verification_status not null default 'pending',
    reviewed_by      uuid        references app.users (id),
    reviewed_at      timestamptz,
    rejection_reason text,
    created_at       timestamptz not null default now(),
    updated_at       timestamptz not null default now(),

    constraint ownership_documents_review_complete check (
        status not in ('approved', 'rejected') or (reviewed_by is not null and reviewed_at is not null)
    ),
    constraint ownership_documents_rejection_has_reason check (
        status <> 'rejected' or rejection_reason is not null
    ),

    foreign key (property_id, tenant_id)
        references app.properties (id, tenant_id) on delete cascade
);

create index ownership_documents_property_idx on app.ownership_documents (property_id);
create index ownership_documents_queue_idx
    on app.ownership_documents (tenant_id, status, created_at)
    where status in ('pending', 'under_review');

create trigger ownership_documents_touch
    before update on app.ownership_documents
    for each row execute function app.touch_updated_at();

-- -----------------------------------------------------------------------------
-- Amenities and favourites
-- -----------------------------------------------------------------------------
create table app.amenities (
    id       uuid primary key default app.uuid_generate_v7(),
    code     varchar(48)  not null,
    name_ar  varchar(96)  not null,
    name_en  varchar(96)  not null,
    icon     varchar(64),
    is_active boolean     not null default true
);

create unique index amenities_code_key on app.amenities (code);

create table app.property_amenities (
    property_id uuid not null,
    tenant_id   uuid not null,
    amenity_id  uuid not null references app.amenities (id) on delete cascade,

    primary key (property_id, amenity_id),
    foreign key (property_id, tenant_id)
        references app.properties (id, tenant_id) on delete cascade
);

create index property_amenities_amenity_idx on app.property_amenities (amenity_id);

create table app.favorites (
    user_id     uuid not null references app.users (id) on delete cascade,
    property_id uuid not null,
    tenant_id   uuid not null,
    created_at  timestamptz not null default now(),

    primary key (user_id, property_id),
    foreign key (property_id, tenant_id)
        references app.properties (id, tenant_id) on delete cascade
);

create index favorites_property_idx on app.favorites (property_id);
