set shell := ["bash", "-euo", "pipefail", "-c"]

default:
  @just --list

atlas *args:
  bash ./scripts/atlas.sh {{args}}

schema-plan:
  bash ./scripts/atlas.sh schema apply --env local --config file://atlas.hcl --dry-run

schema-apply:
  bash ./scripts/atlas.sh schema apply --env local --config file://atlas.hcl --auto-approve

db-seed:
  bash ./scripts/seed.sh

db-bootstrap:
  just schema-apply
  just db-seed

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
