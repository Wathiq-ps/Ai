# Add a JurisdictionSeeder (app.jurisdictions is never seeded)

## Problem

`database/seeders/` has a `CountrySeeder` but no seeder for `app.jurisdictions`.
A freshly migrated database therefore comes up with countries but **zero
jurisdictions**.

`app.jurisdictions` is the partition key for the knowledge base. Three columns
reference it as **NOT NULL**:

```
knowledge.sources.jurisdiction_id      NOT NULL  -> app.jurisdictions(id)
knowledge.kb_versions.jurisdiction_id  NOT NULL  -> app.jurisdictions(id)
knowledge.chunks.jurisdiction_id       NOT NULL  -> app.jurisdictions(id)
```

(plus FKs from `app.contracts`, `app.contract_templates` and
`app.lawyer_credentials` — all `ON DELETE RESTRICT`.)

With no jurisdiction row, the AI service cannot insert a source, a kb_version,
or a chunk — every write is rejected by the foreign key. That makes the whole
retrieval pipeline non-functional on any fresh database: CI, a new developer's
machine, staging, or a rebuilt production volume.

Production currently works only because the row was inserted by hand as a
superuser on 2026-09-07. That insert is not reproducible and not in version
control, which is the actual defect here.

The AI service cannot seed this itself: `wathiq_ai` is granted select-only on
`app.jurisdictions` by `2026_08_04_990000_grant_wathiq_privileges.php`
(`has_table_privilege('app.jurisdictions','insert')` returns `false`). That
grant is correct and should not be widened — seeding belongs on the Laravel
side.

## Requested change

Add a `JurisdictionSeeder`, registered in `DatabaseSeeder` after
`CountrySeeder`, seeding one row:

| column     | value                               |
|------------|-------------------------------------|
| country_id | `app.countries` where `iso2 = 'PS'`  |
| code       | `PS`                                 |
| name_ar    | فلسطين                               |
| name_en    | Palestine                            |
| is_active  | `true`                               |

It must be idempotent — seeders get re-run.

This matches the row already present in production, so nothing needs to change
in the live database. The point of the change is that a fresh database should
reach the same state without a manual insert.

### Why one row

The governing real-estate law is understood to apply uniformly across
Palestine, so a single jurisdiction is correct for the MVP. The table is keyed
on `(country_id, code)` rather than `code` alone, so additional jurisdictions
can be added later as extra rows under the same country if any body of law
turns out to be territory-specific. No schema change would be needed for that —
please just keep the seeder easy to extend with more rows.

## Watch out: the conflict target is composite

The hand-run insert used `on conflict (code)` and failed:

```
ERROR:  there is no unique or exclusion constraint matching the ON CONFLICT specification
STATEMENT:  insert into app.jurisdictions (country_id, code, name_ar, name_en, is_active)
            values ($1, 'PS', 'فلسطين', 'Palestine', true)
            on conflict (code) do update set is_active = true
            returning id
```

There is no unique index on `code` alone. The table has:

```
CREATE UNIQUE INDEX jurisdictions_country_code_key
  ON app.jurisdictions USING btree (country_id, code);
```

So the conflict target must be `(country_id, code)`:

```sql
on conflict (country_id, code) do update set is_active = true
```

Or in Eloquent:

```php
Jurisdiction::updateOrCreate(
    ['country_id' => $countryId, 'code' => 'PS'],
    ['name_ar' => 'فلسطين', 'name_en' => 'Palestine', 'is_active' => true],
);
```

Note `jurisdictions_code_format` also constrains `code` to `^[A-Z0-9_]+$`.

## Verifying

After `php artisan migrate:fresh --seed` on a clean database:

```sql
select j.code, j.name_en, c.iso2
from app.jurisdictions j join app.countries c on c.id = j.country_id;
```

should return the `PS` / Palestine row, and re-running the seeder should not
error.
