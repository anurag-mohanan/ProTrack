# ADR R10-004 — M1c query-time tenant filter

**Status:** Accepted / implementing  
**Date:** 2026-08-01  
**Related:** [ADR_R10_M1_TENANT_ID_BACKFILL.md](./ADR_R10_M1_TENANT_ID_BACKFILL.md), [ADR_R10_M1B_TENANT_UNIQUES.md](./ADR_R10_M1B_TENANT_UNIQUES.md)

## Context

Rows carry `tenant_id` (M1) and natural keys are per-tenant (M1b). Without query filtering, any authenticated session can still load another tenant’s rows by id or unscoped list.

## Decision

1. Register a SQLAlchemy `Session.do_orm_execute` listener that applies `with_loader_criteria` for `TenantMixin` (and `FeatureFlag`) on SELECT.
2. Effective tenant = `get_tenant_id()` or **Prosohm** (same default as request middleware) — Prosohm ops and background jobs keep working with no header.
3. Opt-out:
   - `execution_options(skip_tenant_filter=True)` on a statement/execute
   - `without_tenant_filter()` context manager (seeds, rare cross-tenant admin)
4. `before_flush`: block persisting a `TenantMixin` row whose `tenant_id` ≠ effective tenant (unless opt-out).
5. Prefer `select()` over `session.get()` when switching tenants in one Session — a filtered `get` miss can be identity-cached.
6. **Optional later:** PostgreSQL RLS — see [ADR_R10_PG_RLS.md](./ADR_R10_PG_RLS.md) (`PROTRACK_ENABLE_PG_RLS`).

## Consequences

- Cross-tenant reads via ORM lists/`get` return empty/miss under the wrong tenant.
- Raw SQL is **not** filtered — prefer ORM; document for ops scripts.
- SQLite autoindexes / legacy DBs unchanged by this phase (no schema migration).

## Exit criteria

- [x] ADR published
- [x] Listener + helpers in `app/db/tenant_filter.py`
- [x] Registered on app `SessionLocal`
- [x] Tests: isolation + Prosohm default + opt-out
