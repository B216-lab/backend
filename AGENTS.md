# AGENTS.md

## 1. Git

- Use conventional commit messages; title <= 100 chars
- Never install a new dependency without asking first
- Never modify database schema without showing the migration plan first

## 2. Go Style

- Target Go 1.26+
- Keep packages focused and small; avoid god files
- Prefer explicit constructors and dependency injection over globals
- Return wrapped errors with context (`fmt.Errorf("...: %w", err)`)
- Keep methods simple; use early returns and avoid deep nesting
- No magic strings for domain codes; centralize constants/maps where reused
- Keep JSON/API structs stable; preserve current public wire contract
- Avoid wildcard-like behavior in SQL; keep queries explicit
- Prefer immutable data flow in service layer where practical

## 3. HTTP / Service Boundaries

- Controllers/handlers contain transport logic only
- Business rules and normalization stay in service layer
- Persistence logic stays in repository layer
- Keep error bodies consistent and machine-readable
- Do not add auth/session features in this service scope

## 4. Persistence

- `db/schema.sql` is the schema source of truth
- Apply schema changes with Atlas `schema apply`
- `db/seed.sql` contains idempotent reference data for empty-database bootstrap
- Never change database manually to “fix” migration drift
- Keep seed data idempotent (`ON CONFLICT` upserts)
- Prefer transactions for multi-step writes

## 5. Testing

- Run `just check` before pushing
- Core behavior tests for form normalization and validation must stay green
- Add tests for any new business rules before implementation changes

## 6. Build / Run

- Local checks: `just check`
- Preview schema changes: `just schema-plan`
- Apply schema locally: `just schema-apply`
- Seed reference data locally: `just db-seed`
- Bootstrap empty local DB: `just db-bootstrap`
- Start stack: `just up`
- Stop stack: `just down`
- Docker smoke: `just docker-smoke`
