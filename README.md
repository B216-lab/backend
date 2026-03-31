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

Atlas and Postgres CLI tooling run via pinned Docker images in this repository, so you do not need local installs for them.

### Core Commands

```bash
just schema-plan
just schema-apply
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

`just up` starts PostgreSQL, applies `db/schema.sql`, loads `db/seed.sql`, and then starts the API.

## Schema Workflow

`db/schema.sql` is the schema source of truth.
`db/seed.sql` contains idempotent reference data for bootstrapping an empty database.

Typical change flow:

1. Edit `db/schema.sql`
2. Start PostgreSQL if needed: `docker compose up -d postgres`
3. Preview the plan: `just schema-plan`
4. Apply the schema: `just schema-apply`
5. Re-run reference data if needed: `just db-seed`

This setup is intentionally optimized for the current stage: empty-database bootstrap and first deployment. If environments start to carry state that must evolve safely over time, that is the point where versioned migrations become worth reintroducing.

### Docker Smoke Check

```bash
just docker-smoke
```

## Devcontainer

The repository includes a compose-based devcontainer configuration in `.devcontainer/`.
It brings up PostgreSQL plus a development container with Go, `just`, and `pre-commit`.
