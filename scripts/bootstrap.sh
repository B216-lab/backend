#!/bin/sh
set -eu

DATABASE_URL="${DATABASE_URL:-${BOOTSTRAP_DATABASE_URL:-}}"
MIGRATIONS_DIR="${MIGRATIONS_DIR:-db/migrations}"

if [ -z "${DATABASE_URL}" ]; then
  echo "DATABASE_URL or BOOTSTRAP_DATABASE_URL must be set" >&2
  exit 1
fi

echo "Waiting for database readiness..."
attempt=0
until psql "${DATABASE_URL}" -v ON_ERROR_STOP=1 -c 'select 1' >/dev/null 2>&1; do
  attempt=$((attempt + 1))
  if [ "${attempt}" -ge 60 ]; then
    echo "Database did not become ready in time" >&2
    exit 1
  fi
  sleep 2
done

echo "Ensuring PostGIS extension and geometry migration..."
psql "${DATABASE_URL}" -v ON_ERROR_STOP=1 -f db/pre_schema.sql

echo "Applying schema with Goose..."
goose -dir "${MIGRATIONS_DIR}" postgres "${DATABASE_URL}" up

echo "Seeding reference data..."
psql "${DATABASE_URL}" -v ON_ERROR_STOP=1 -f db/seed.sql

echo "Bootstrap completed successfully."
