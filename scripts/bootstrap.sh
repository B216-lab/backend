#!/bin/sh
set -eu

DATABASE_URL="${DATABASE_URL:-${BOOTSTRAP_DATABASE_URL:-}}"

if [ -z "${DATABASE_URL}" ]; then
  echo "DATABASE_URL or BOOTSTRAP_DATABASE_URL must be set" >&2
  exit 1
fi

add_search_path() {
  case "$1" in
    *search_path=*)
      printf '%s' "$1"
      ;;
    *\?*)
      printf '%s&search_path=public' "$1"
      ;;
    *)
      printf '%s?search_path=public' "$1"
      ;;
  esac
}

ATLAS_DATABASE_URL="${ATLAS_DATABASE_URL:-$(add_search_path "${DATABASE_URL}")}"
ATLAS_DEV_DATABASE_URL="${ATLAS_DEV_DATABASE_URL:-${ATLAS_DATABASE_URL}}"

export ATLAS_DATABASE_URL
export ATLAS_DEV_DATABASE_URL

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

echo "Applying schema with Atlas..."
atlas schema apply --env local --config file://atlas.hcl --auto-approve

echo "Seeding reference data..."
psql "${DATABASE_URL}" -v ON_ERROR_STOP=1 -f db/seed.sql

echo "Bootstrap completed successfully."
