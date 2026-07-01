-- +goose Up
CREATE SCHEMA IF NOT EXISTS osm_admin;

CREATE TABLE IF NOT EXISTS osm_admin.boundaries (
    osm_id        BIGINT PRIMARY KEY,
    name          TEXT,
    name_ru       TEXT,
    name_en       TEXT,
    admin_level   SMALLINT NOT NULL,
    place         TEXT,
    boundary      TEXT NOT NULL DEFAULT 'administrative',
    wikidata      TEXT,
    parent_osm_id BIGINT REFERENCES osm_admin.boundaries (osm_id),
    geom          geometry(MultiPolygon, 4326) NOT NULL,
    imported_at   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_osm_admin_boundaries_admin_level
    ON osm_admin.boundaries (admin_level);

CREATE INDEX IF NOT EXISTS idx_osm_admin_boundaries_parent_osm_id
    ON osm_admin.boundaries (parent_osm_id);

CREATE INDEX IF NOT EXISTS idx_osm_admin_boundaries_geom
    ON osm_admin.boundaries
    USING GIST (geom);

CREATE OR REPLACE VIEW osm_admin.federal_subjects AS
SELECT *
FROM osm_admin.boundaries
WHERE admin_level = 4;

CREATE OR REPLACE VIEW osm_admin.administrative_districts AS
SELECT *
FROM osm_admin.boundaries
WHERE admin_level IN (5, 6);

CREATE OR REPLACE VIEW osm_admin.cities AS
SELECT *
FROM osm_admin.boundaries
WHERE boundary = 'administrative'
  AND (
    (admin_level IN (6, 7) AND name IS NOT NULL)
    OR name_en = 'Moscow'
  );

CREATE OR REPLACE VIEW osm_admin.local_areas AS
SELECT *
FROM osm_admin.boundaries
WHERE admin_level IN (9, 10);

-- +goose Down
DROP VIEW IF EXISTS osm_admin.local_areas;
DROP VIEW IF EXISTS osm_admin.cities;
DROP VIEW IF EXISTS osm_admin.administrative_districts;
DROP VIEW IF EXISTS osm_admin.federal_subjects;

DROP INDEX IF EXISTS osm_admin.idx_osm_admin_boundaries_geom;
DROP INDEX IF EXISTS osm_admin.idx_osm_admin_boundaries_parent_osm_id;
DROP INDEX IF EXISTS osm_admin.idx_osm_admin_boundaries_admin_level;

DROP TABLE IF EXISTS osm_admin.boundaries;
DROP SCHEMA IF EXISTS osm_admin;
