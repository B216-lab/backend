-- +goose Up
ALTER TABLE movements_form_submissions
    ADD COLUMN IF NOT EXISTS home_city_id BIGINT,
    ADD COLUMN IF NOT EXISTS home_city_name TEXT;

CREATE INDEX IF NOT EXISTS idx_movements_form_submissions_home_city_id
    ON movements_form_submissions (home_city_id);

CREATE INDEX IF NOT EXISTS idx_movements_form_submissions_home_city_name
    ON movements_form_submissions (home_city_name);

UPDATE movements_form_submissions s
SET
    home_city_id = matched.city_id,
    home_city_name = matched.city_name
FROM (
    SELECT
        s2.id AS submission_id,
        c.osm_id AS city_id,
        COALESCE(c.name_ru, c.name, c.name_en) AS city_name
    FROM movements_form_submissions s2
    JOIN LATERAL (
        SELECT c.osm_id, c.name_ru, c.name, c.name_en
        FROM osm_admin.cities c
        WHERE ST_Covers(c.geom, s2.home_address)
        ORDER BY c.admin_level ASC, ST_Area(c.geom::geography) ASC
        LIMIT 1
    ) c ON TRUE
    WHERE s2.home_address IS NOT NULL
      AND s2.home_city_id IS NULL
) matched
WHERE s.id = matched.submission_id;

-- +goose Down
DROP INDEX IF EXISTS idx_movements_form_submissions_home_city_name;
DROP INDEX IF EXISTS idx_movements_form_submissions_home_city_id;

ALTER TABLE movements_form_submissions
    DROP COLUMN IF EXISTS home_city_name,
    DROP COLUMN IF EXISTS home_city_id;
