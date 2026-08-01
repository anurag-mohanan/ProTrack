# ADR R10-009 — Optional PostgreSQL RLS

**Status:** Accepted  
**Date:** 2026-08-01  
**Related:** [ADR_R10_M1C_TENANT_QUERY_FILTER.md](./ADR_R10_M1C_TENANT_QUERY_FILTER.md)

## Context

ORM loader criteria (M1c) isolate tenants in application SQL. Raw SQL, reporting tools, and compromised queries can still leak rows. PostgreSQL RLS is defense in depth when a second tenant is imminent.

## Decision

1. Gate with **`PROTRACK_ENABLE_PG_RLS=true`** (default **off** — Prosohm SQLite/single-tenant unaffected).
2. On Postgres startup (phase74): `ENABLE ROW LEVEL SECURITY` + policy `protrack_tenant_isolation` on tenant-scoped tables (+ `feature_flags`).
3. Policy: allow when `app.bypass_rls = '1'` **or** `tenant_id::text = app.tenant_id`.
4. Session hooks set GUCs via `set_config(..., true)` (transaction-local) on `after_begin` and `sync_session_rls(session)`.
5. **`PROTRACK_ENABLE_PG_RLS_FORCE`** (default true): `FORCE ROW LEVEL SECURITY` so the app role cannot bypass as table owner.
6. ORM `without_tenant_filter()` sets bypass GUC on the next transaction begin; call `sync_session_rls(db, bypass=True)` inside long transactions if needed.

## Non-goals

- RLS on SQLite  
- Replacing ORM filters (both layers stay)  
- Per-table custom policies  

## Ops

```bash
# Postgres only, after backups
set PROTRACK_ENABLE_PG_RLS=true
# restart API → phase74 applies policies
```

Rollback: set env false and `DROP POLICY protrack_tenant_isolation ON …` / `DISABLE ROW LEVEL SECURITY` if needed.

## Exit criteria

- [x] ADR + phase74 + `app/db/pg_rls.py`
- [x] Session GUC sync + startup install
- [x] Tests (no-op on SQLite; policy SQL helpers)
