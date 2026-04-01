CREATE TABLE social_statuses (
    id             BIGSERIAL PRIMARY KEY,
    code           VARCHAR(64)  NOT NULL UNIQUE,
    description_ru VARCHAR(256) NOT NULL
);

CREATE TABLE ref_validation_status (
    id             BIGSERIAL PRIMARY KEY,
    code           VARCHAR(128) NOT NULL UNIQUE,
    description_ru VARCHAR(512) NOT NULL
);

CREATE TABLE ref_movement_type (
    id             BIGSERIAL PRIMARY KEY,
    code           VARCHAR(64)  NOT NULL UNIQUE,
    description_ru VARCHAR(256) NOT NULL
);

CREATE TABLE ref_place_type (
    id             BIGSERIAL PRIMARY KEY,
    code           VARCHAR(128) NOT NULL UNIQUE,
    description_ru VARCHAR(512) NOT NULL
);

CREATE TABLE ref_vehicle_type (
    id             BIGSERIAL PRIMARY KEY,
    code           VARCHAR(128) NOT NULL UNIQUE,
    description_ru VARCHAR(512) NOT NULL
);

CREATE TABLE allowed_respondent_keys (
    id             BIGSERIAL PRIMARY KEY,
    name           VARCHAR(255) NOT NULL,
    respondent_key VARCHAR(255) NOT NULL UNIQUE,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE movements_form_submissions (
    id                    BIGSERIAL PRIMARY KEY,
    birthday              DATE,
    gender                VARCHAR(16),
    social_status_id      BIGINT REFERENCES social_statuses (id),
    transport_cost_min    INTEGER,
    transport_cost_max    INTEGER,
    income_min            INTEGER,
    income_max            INTEGER,
    home_address          JSONB,
    home_readable_address VARCHAR(512),
    movements_date        DATE,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE movements (
    id                           BIGSERIAL PRIMARY KEY,
    movement_type_id             BIGINT NOT NULL REFERENCES ref_movement_type (id),
    departure_time               TIMESTAMPTZ,
    destination_time             TIMESTAMPTZ,
    departure_place              JSONB,
    destination_place            JSONB,
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

CREATE INDEX idx_movements_form_submissions_social_status_id
    ON movements_form_submissions (social_status_id);

CREATE INDEX idx_movements_form_submissions_created_at
    ON movements_form_submissions (created_at);

CREATE INDEX idx_movements_movements_form_submission_id
    ON movements (movements_form_submission_id);

CREATE INDEX idx_movements_created_at
    ON movements (created_at);
