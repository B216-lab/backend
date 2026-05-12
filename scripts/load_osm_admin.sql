CREATE EXTENSION IF NOT EXISTS postgis;

TRUNCATE TABLE osm_admin.boundaries;

INSERT INTO osm_admin.boundaries (
    osm_id,
    name,
    name_ru,
    name_en,
    admin_level,
    place,
    boundary,
    wikidata,
    parent_osm_id,
    geom,
    imported_at
)
SELECT
    src.osm_id,
    NULLIF(src.name, ''),
    NULLIF(src.name_ru, ''),
    NULLIF(src.name_en, ''),
    src.admin_level::SMALLINT,
    NULLIF(src.place, ''),
    COALESCE(NULLIF(src.boundary, ''), 'administrative'),
    NULLIF(src.wikidata, ''),
    NULL,
    ST_Multi(
        ST_CollectionExtract(
            ST_MakeValid(
                CASE
                    WHEN ST_SRID(src.geometry) = 4326 THEN src.geometry
                    ELSE ST_Transform(src.geometry, 4326)
                END
            ),
            3
        )
    )::geometry(MultiPolygon, 4326),
    CURRENT_TIMESTAMP
FROM :"staging_schema".admin_boundaries AS src
WHERE src.admin_level ~ '^[0-9]+$'
  AND src.geometry IS NOT NULL;

WITH ranked_parents AS (
    SELECT
        child.osm_id AS child_osm_id,
        parent.osm_id AS parent_osm_id,
        ROW_NUMBER() OVER (
            PARTITION BY child.osm_id
            ORDER BY parent.admin_level DESC, ST_Area(parent.geom::geography) ASC
        ) AS rn
    FROM osm_admin.boundaries AS child
    JOIN osm_admin.boundaries AS parent
      ON parent.osm_id <> child.osm_id
     AND parent.admin_level < child.admin_level
     AND ST_Covers(parent.geom, ST_PointOnSurface(child.geom))
)
UPDATE osm_admin.boundaries AS child
SET parent_osm_id = ranked_parents.parent_osm_id
FROM ranked_parents
WHERE child.osm_id = ranked_parents.child_osm_id
  AND ranked_parents.rn = 1;

ANALYZE osm_admin.boundaries;
