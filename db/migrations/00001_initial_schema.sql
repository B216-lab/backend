-- +goose Up
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS social_statuses (
    id             BIGSERIAL PRIMARY KEY,
    code           VARCHAR(64)  NOT NULL UNIQUE,
    description_ru VARCHAR(256) NOT NULL
);

CREATE TABLE IF NOT EXISTS ref_validation_status (
    id             BIGSERIAL PRIMARY KEY,
    code           VARCHAR(128) NOT NULL UNIQUE,
    description_ru VARCHAR(512) NOT NULL
);

CREATE TABLE IF NOT EXISTS ref_movement_type (
    id             BIGSERIAL PRIMARY KEY,
    code           VARCHAR(64)  NOT NULL UNIQUE,
    description_ru VARCHAR(256) NOT NULL
);

CREATE TABLE IF NOT EXISTS ref_place_type (
    id             BIGSERIAL PRIMARY KEY,
    code           VARCHAR(128) NOT NULL UNIQUE,
    description_ru VARCHAR(512) NOT NULL
);

CREATE TABLE IF NOT EXISTS ref_vehicle_type (
    id             BIGSERIAL PRIMARY KEY,
    code           VARCHAR(128) NOT NULL UNIQUE,
    description_ru VARCHAR(512) NOT NULL
);

CREATE TABLE IF NOT EXISTS allowed_respondent_keys (
    id             BIGSERIAL PRIMARY KEY,
    name           VARCHAR(255) NOT NULL UNIQUE,
    respondent_key VARCHAR(255) NOT NULL UNIQUE,
    is_active      BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS movements_form_submissions (
    id                        BIGSERIAL PRIMARY KEY,
    allowed_respondent_key_id BIGINT REFERENCES allowed_respondent_keys (id),
    birthday                  DATE,
    gender                    VARCHAR(16),
    social_status_id          BIGINT REFERENCES social_statuses (id),
    transport_cost_min        INTEGER,
    transport_cost_max        INTEGER,
    income_min                INTEGER,
    income_max                INTEGER,
    home_address              geometry(Point, 4326),
    home_readable_address     VARCHAR(512),
    movements_date            DATE,
    created_at                TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS movements (
    id                           BIGSERIAL PRIMARY KEY,
    movement_type_id             BIGINT NOT NULL REFERENCES ref_movement_type (id),
    departure_time               TIMESTAMPTZ,
    destination_time             TIMESTAMPTZ,
    departure_place              geometry(Point, 4326),
    destination_place            geometry(Point, 4326),
    departure_place_address      VARCHAR(512),
    destination_place_address    VARCHAR(512),
    departure_place_type_id      BIGINT NOT NULL REFERENCES ref_place_type (id),
    validation_status_id         BIGINT NOT NULL REFERENCES ref_validation_status (id),
    destination_place_type_id    BIGINT NOT NULL REFERENCES ref_place_type (id),
    vehicle_type_id              BIGINT REFERENCES ref_vehicle_type (id),
    cost                         NUMERIC(12, 2),
    waiting_time                 INTEGER,
    seats_amount                 INTEGER,
    comment                      VARCHAR(2000),
    created_at                   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    movements_form_submission_id BIGINT NOT NULL REFERENCES movements_form_submissions (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_movements_form_submissions_social_status_id
    ON movements_form_submissions (social_status_id);

CREATE INDEX IF NOT EXISTS idx_movements_form_submissions_allowed_respondent_key_id
    ON movements_form_submissions (allowed_respondent_key_id);

CREATE INDEX IF NOT EXISTS idx_movements_form_submissions_created_at
    ON movements_form_submissions (created_at);

CREATE INDEX IF NOT EXISTS idx_movements_form_submissions_home_address
    ON movements_form_submissions
    USING GIST (home_address);

CREATE INDEX IF NOT EXISTS idx_movements_movements_form_submission_id
    ON movements (movements_form_submission_id);

CREATE INDEX IF NOT EXISTS idx_movements_created_at
    ON movements (created_at);

CREATE INDEX IF NOT EXISTS idx_movements_departure_place
    ON movements
    USING GIST (departure_place);

CREATE INDEX IF NOT EXISTS idx_movements_destination_place
    ON movements
    USING GIST (destination_place);

-- +goose Down
DROP INDEX IF EXISTS idx_movements_destination_place;
DROP INDEX IF EXISTS idx_movements_departure_place;
DROP INDEX IF EXISTS idx_movements_created_at;
DROP INDEX IF EXISTS idx_movements_movements_form_submission_id;
DROP INDEX IF EXISTS idx_movements_form_submissions_home_address;
DROP INDEX IF EXISTS idx_movements_form_submissions_created_at;
DROP INDEX IF EXISTS idx_movements_form_submissions_allowed_respondent_key_id;
DROP INDEX IF EXISTS idx_movements_form_submissions_social_status_id;

DROP TABLE IF EXISTS movements;
DROP TABLE IF EXISTS movements_form_submissions;
DROP TABLE IF EXISTS allowed_respondent_keys;
DROP TABLE IF EXISTS ref_vehicle_type;
DROP TABLE IF EXISTS ref_place_type;
DROP TABLE IF EXISTS ref_movement_type;
DROP TABLE IF EXISTS ref_validation_status;
DROP TABLE IF EXISTS social_statuses;
