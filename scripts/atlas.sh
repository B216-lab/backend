#!/usr/bin/env bash
set -euo pipefail

ATLAS_IMAGE="${ATLAS_IMAGE:-arigaio/atlas@sha256:5bd26b6ab9c12d0433fab9a0837bd2dca1d1ed2bec48dce8cc47e43e2756f3fc}"

if [[ -z "${ATLAS_DATABASE_URL:-}" ]]; then
  ATLAS_DATABASE_URL="postgres://${POSTGRES_USER:-umrs}:${POSTGRES_PASSWORD:-secret}@localhost:${POSTGRES_PORT:-5432}/${POSTGRES_DB:-umrs_go_backend}?sslmode=disable&search_path=public"
fi

if [[ -z "${ATLAS_DEV_DATABASE_URL:-}" ]]; then
  ATLAS_DEV_DATABASE_URL="${ATLAS_DATABASE_URL}"
fi

exec docker run --rm \
  --network host \
  -e ATLAS_DATABASE_URL="${ATLAS_DATABASE_URL}" \
  -e ATLAS_DEV_DATABASE_URL="${ATLAS_DEV_DATABASE_URL}" \
  -v "${PWD}:/work" \
  -w /work \
  "${ATLAS_IMAGE}" "$@"
