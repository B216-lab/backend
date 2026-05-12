# UMRS Go Backend

## Local Development

### Bootstrap

```bash
cp .env.example .env
go mod download
pre-commit install
```

Goose and Postgres CLI tooling run via Docker in this repository, so you do not need local installs for them.

## Schema Workflow

`db/migrations/` is the schema source of truth.
Goose stores applied migration versions in the target database and skips versions that were already applied.
`db/seed.sql` stays separate from migrations because it is rerunnable reference data, not schema history.

Typical change flow:

1. Create a new migration: `just migrate-create add_new_feature`
2. Edit the generated SQL migration in `db/migrations/`
3. Start PostgreSQL if needed: `docker compose up -d postgres`
4. Check migration state: `just migrate-status`
5. Apply pending migrations: `just migrate-up`
6. Re-run reference data if needed: `just db-seed`

### Docker Smoke Check

```bash
just docker-smoke
```

## Administrative Boundary Import

This repository can import only Russian administrative boundaries from an OSM `.pbf` into the same PostGIS database without loading the default heavy `planet_osm_*` schema.

What it does:

- uses `imposm3` with a mapping that only keeps `boundary=administrative` polygons
- loads the raw import into disposable schemas
- copies normalized data into `osm_admin.boundaries`
- exposes convenience views for `federal_subjects`, `administrative_districts`, `cities`, and `local_areas`

Run it against the bundled Russia extract:

```bash
just migrate-up
just osm-admin-import
```

Use a different `.pbf` file under the backend working tree:

```bash
just osm-admin-import pbf=data/another-russia-extract.osm.pbf
```

After import, example queries:

```sql
SELECT name, admin_level
FROM osm_admin.cities
WHERE name ILIKE 'Новосибирск';

SELECT name, admin_level, parent_osm_id
FROM osm_admin.local_areas
WHERE parent_osm_id = (
  SELECT osm_id
  FROM osm_admin.cities
  WHERE name = 'Новосибирск'
  LIMIT 1
);
```
