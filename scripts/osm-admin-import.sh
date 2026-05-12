#!/bin/sh
set -eu

DATABASE_URL="${DATABASE_URL:-}"
PBF_PATH="${PBF_PATH:-/work/data/russia-260510.osm.pbf}"
MAPPING_FILE="${MAPPING_FILE:-/work/osm/imposm-admin-mapping.yml}"
POST_IMPORT_SQL="${POST_IMPORT_SQL:-/work/scripts/load_osm_admin.sql}"
STAGING_SCHEMA="${STAGING_SCHEMA:-osm_admin_stage}"
PRODUCTION_SCHEMA="${PRODUCTION_SCHEMA:-osm_admin_production}"
BACKUP_SCHEMA="${BACKUP_SCHEMA:-osm_admin_backup}"
CACHE_DIR="${CACHE_DIR:-/tmp/imposm-cache}"
KEEP_STAGING="${KEEP_STAGING:-0}"

if [ -z "${DATABASE_URL}" ]; then
  echo "DATABASE_URL must be set" >&2
  exit 1
fi

if [ ! -f "${PBF_PATH}" ]; then
  echo "PBF file not found: ${PBF_PATH}" >&2
  exit 1
fi

if [ ! -f "${MAPPING_FILE}" ]; then
  echo "Mapping file not found: ${MAPPING_FILE}" >&2
  exit 1
fi

if [ ! -f "${POST_IMPORT_SQL}" ]; then
  echo "Post-import SQL not found: ${POST_IMPORT_SQL}" >&2
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

imposm_connection="${DATABASE_URL}"
case "${imposm_connection}" in
  postgres://*)
    imposm_connection="postgis://${imposm_connection#postgres://}"
    ;;
  postgresql://*)
    imposm_connection="postgis://${imposm_connection#postgresql://}"
    ;;
esac

case "${imposm_connection}" in
  *\?*)
    imposm_connection="${imposm_connection}&prefix=NONE"
    ;;
  *)
    imposm_connection="${imposm_connection}?prefix=NONE"
    ;;
esac

mkdir -p "${CACHE_DIR}"

echo "Preparing disposable import schemas..."
psql "${DATABASE_URL}" -v ON_ERROR_STOP=1 \
  -v staging_schema="${STAGING_SCHEMA}" \
  -v production_schema="${PRODUCTION_SCHEMA}" \
  -v backup_schema="${BACKUP_SCHEMA}" <<'SQL'
DROP SCHEMA IF EXISTS :"staging_schema" CASCADE;
DROP SCHEMA IF EXISTS :"production_schema" CASCADE;
DROP SCHEMA IF EXISTS :"backup_schema" CASCADE;

CREATE SCHEMA :"staging_schema";
CREATE SCHEMA :"production_schema";
CREATE SCHEMA :"backup_schema";
SQL

echo "Importing administrative boundaries with imposm..."
imposm import \
  -mapping "${MAPPING_FILE}" \
  -read "${PBF_PATH}" \
  -write \
  -optimize \
  -overwritecache \
  -cachedir "${CACHE_DIR}" \
  -connection "${imposm_connection}" \
  -dbschema-import "${STAGING_SCHEMA}" \
  -dbschema-production "${PRODUCTION_SCHEMA}" \
  -dbschema-backup "${BACKUP_SCHEMA}"

echo "Loading normalized boundary data into osm_admin..."
psql "${DATABASE_URL}" -v ON_ERROR_STOP=1 \
  -v staging_schema="${STAGING_SCHEMA}" \
  -f "${POST_IMPORT_SQL}"

if [ "${KEEP_STAGING}" != "1" ]; then
  echo "Dropping disposable import schemas..."
  psql "${DATABASE_URL}" -v ON_ERROR_STOP=1 \
    -v staging_schema="${STAGING_SCHEMA}" \
    -v production_schema="${PRODUCTION_SCHEMA}" \
    -v backup_schema="${BACKUP_SCHEMA}" <<'SQL'
DROP SCHEMA IF EXISTS :"staging_schema" CASCADE;
DROP SCHEMA IF EXISTS :"production_schema" CASCADE;
DROP SCHEMA IF EXISTS :"backup_schema" CASCADE;
SQL
fi

echo "Administrative boundary import completed successfully."
