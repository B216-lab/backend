# Backups

Store PostgreSQL custom dumps for local `backend` DB.

## Make backup

Run from `backend/`:

```bash
ts="$(date +%Y%m%d_%H%M%S)"
docker exec -i backend-postgres-1 sh -lc 'PGPASSWORD=${POSTGRES_PASSWORD:-secret} pg_dump -Fc -U ${POSTGRES_USER:-umrs} -d ${POSTGRES_DB:-umrs_go_backend}' > "backups/umrs_go_backend_${ts}.dump"
```

## Restore backup

Run from `backend/`:

```bash
docker exec -i backend-postgres-1 sh -lc 'PGPASSWORD=${POSTGRES_PASSWORD:-secret} pg_restore --clean --if-exists --no-owner --no-privileges -U ${POSTGRES_USER:-umrs} -d ${POSTGRES_DB:-umrs_go_backend}' < backups/umrs_go_backend_YYYYMMDD_HHMMSS.dump
```

## Notes

- Format: PostgreSQL custom dump (`pg_dump -Fc`)
- Restore replaces existing DB objects
- Ensure `backend-postgres-1` is running first
