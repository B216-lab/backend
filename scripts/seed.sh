#!/usr/bin/env bash
set -euo pipefail

SEED_IMAGE="${SEED_IMAGE:-postgres:18-alpine}"

if [[ -z "${SEED_DATABASE_URL:-}" ]]; then
  SEED_DATABASE_URL="postgres://${POSTGRES_USER:-umrs}:${POSTGRES_PASSWORD:-secret}@localhost:${POSTGRES_PORT:-5432}/${POSTGRES_DB:-umrs_go_backend}?sslmode=disable"
fi

exec docker run --rm \
  --network host \
  -v "${PWD}:/work" \
  -w /work \
  "${SEED_IMAGE}" \
  psql "${SEED_DATABASE_URL}" -v ON_ERROR_STOP=1 -f db/seed.sql
