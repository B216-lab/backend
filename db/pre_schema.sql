CREATE EXTENSION IF NOT EXISTS postgis;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'movements_form_submissions'
          AND column_name = 'home_address'
          AND udt_name = 'jsonb'
    ) THEN
        ALTER TABLE movements_form_submissions
            ALTER COLUMN home_address
            TYPE geometry(Point, 4326)
            USING CASE
                WHEN home_address IS NULL THEN NULL
                ELSE ST_SetSRID(ST_GeomFromGeoJSON(home_address::text), 4326)
            END;
    END IF;
END
$$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'movements'
          AND column_name = 'departure_place'
          AND udt_name = 'jsonb'
    ) THEN
        ALTER TABLE movements
            ALTER COLUMN departure_place
            TYPE geometry(Point, 4326)
            USING CASE
                WHEN departure_place IS NULL THEN NULL
                ELSE ST_SetSRID(ST_GeomFromGeoJSON(departure_place::text), 4326)
            END;
    END IF;
END
$$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'movements'
          AND column_name = 'destination_place'
          AND udt_name = 'jsonb'
    ) THEN
        ALTER TABLE movements
            ALTER COLUMN destination_place
            TYPE geometry(Point, 4326)
            USING CASE
                WHEN destination_place IS NULL THEN NULL
                ELSE ST_SetSRID(ST_GeomFromGeoJSON(destination_place::text), 4326)
            END;
    END IF;
END
$$;
