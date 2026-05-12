set shell := ["bash", "-euo", "pipefail", "-c"]

default:
  @just --list

migrate *args:
  bash ./scripts/goose.sh {{args}}

migrate-status:
  bash ./scripts/goose.sh status

migrate-up:
  bash ./scripts/goose.sh up

migrate-up-by-one:
  bash ./scripts/goose.sh up-by-one

migrate-down:
  bash ./scripts/goose.sh down

migrate-redo:
  bash ./scripts/goose.sh redo

migrate-version:
  bash ./scripts/goose.sh version

migrate-create name:
  bash ./scripts/goose.sh create {{name}} sql

schema-plan:
  @echo "Atlas schema plan was removed. Use `just migrate-status` with Goose."

schema-apply:
  bash ./scripts/goose.sh up

db-seed:
  bash ./scripts/seed.sh

export-region region="custom-data/chelyabinsk_agglomeration.geojson" out_dir="exports/chelyabinsk_agglomeration" database_url="":
  python3 ./scripts/export_region_data.py \
    --region-geojson "{{region}}" \
    --out-dir "{{out_dir}}" \
    {{ if database_url != "" { "--database-url \"" + database_url + "\"" } else { "" } }}

export-chelyabinsk:
  just export-region

db-bootstrap:
  docker compose up -d postgres
  docker compose build bootstrap
  docker compose run --rm bootstrap

osm-admin-import pbf="data/russia-260510.osm.pbf":
  docker compose up -d postgres
  docker compose build osm-admin-import
  docker compose run --rm -e PBF_PATH="/work/{{pbf}}" osm-admin-import

bootstrap:
  docker compose build bootstrap
  docker compose run --rm bootstrap

fmt:
  gofmt -w $(find . -name '*.go' -type f | sort)

fmt-check:
  test -z "$(gofmt -l $(find . -name '*.go' -type f | sort))"

test:
  go test ./...

vet:
  go vet ./...

build:
  go build ./...

check: fmt-check test vet build

up:
  docker compose up -d --build

down:
  docker compose down -v --remove-orphans

docker-smoke:
  bash -euo pipefail -c ' \
    trap "docker compose down -v --remove-orphans" EXIT; \
    docker compose up -d --build; \
    for _ in {1..45}; do \
      if curl --silent --fail http://localhost:${SERVER_PORT:-8081}/healthz >/dev/null; then \
        break; \
      fi; \
      sleep 2; \
    done; \
    curl --silent --show-error --fail \
      -H "Content-Type: application/json" \
      -X POST \
      --data "{\"movementsDate\":\"2026-04-01\",\"movements\":[{\"movementType\":\"ON_FOOT\",\"departurePlace\":\"HOME_RESIDENCE\",\"arrivalPlace\":\"SCHOOL\",\"departureTime\":\"08:30\",\"arrivalTime\":\"09:00\"}]}" \
      http://localhost:${SERVER_PORT:-8081}/api/v1/public/forms/movements >/dev/null \
  '
