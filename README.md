# UMRS Go Backend

Lightweight Go backend for movements form ingestion.

## Public API

- `POST /api/v1/public/forms/movements`
- `POST /v1/public/forms/movements` (compat alias)
- `GET /healthz`

## Local Development

### Prerequisites

- Go 1.26+
- `just`
- Docker + Docker Compose
- Optional: `pre-commit`

### Bootstrap

```bash
cp .env.example .env
go mod download
pre-commit install
```

Goose and Postgres CLI tooling run via Docker in this repository, so you do not need local installs for them.

### Core Commands

```bash
just migrate-status
just migrate-up
just migrate-down
just migrate-redo
just migrate-create add_new_feature
just db-seed
just db-bootstrap
just fmt
just fmt-check
just test
just vet
just build
just check
```

### Run with Docker Compose

```bash
just up
curl --fail http://localhost:8081/healthz
just down
```

`just up` starts PostgreSQL, applies Goose migrations, loads `db/seed.sql`, and then starts the API.

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

## Devcontainer

The repository includes a compose-based devcontainer configuration in `.devcontainer/`.
It brings up PostgreSQL plus a development container with Go, `just`, and `pre-commit`.
