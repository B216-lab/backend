#!/usr/bin/env bash
set -euo pipefail

GOOSE_IMAGE="${GOOSE_IMAGE:-backend-goose-cli}"
GOOSE_VERSION="${GOOSE_VERSION:-v3.27.0}"

if [[ $# -lt 1 ]]; then
  echo "usage: scripts/goose.sh <command> [args...]" >&2
  exit 1
fi

if [[ -z "${GOOSE_DATABASE_URL:-}" ]]; then
  GOOSE_DATABASE_URL="postgres://${POSTGRES_USER:-umrs}:${POSTGRES_PASSWORD:-secret}@localhost:${POSTGRES_PORT:-5432}/${POSTGRES_DB:-umrs_go_backend}?sslmode=disable"
fi

command_name="$1"
shift

docker build \
  --build-arg "GOOSE_VERSION=${GOOSE_VERSION}" \
  -f Dockerfile.bootstrap \
  -t "${GOOSE_IMAGE}" \
  . >/dev/null

case "${command_name}" in
  create)
    exec docker run --rm \
      -v "${PWD}:/work" \
      -w /work \
      --entrypoint goose \
      "${GOOSE_IMAGE}" \
      -dir db/migrations \
      create "$@"
    ;;
  *)
    exec docker run --rm \
      --network host \
      -v "${PWD}:/work" \
      -w /work \
      --entrypoint goose \
      "${GOOSE_IMAGE}" \
      -dir db/migrations \
      postgres "${GOOSE_DATABASE_URL}" \
      "${command_name}" "$@"
    ;;
esac
