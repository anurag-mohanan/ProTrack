# ADR R10-003 — M1b tenant-scoped unique constraints

**Status:** Accepted / implementing  
**Date:** 2026-08-01  
**Related:** [ADR_R10_M1_TENANT_ID_BACKFILL.md](./ADR_R10_M1_TENANT_ID_BACKFILL.md)

## Context

M1 added `tenant_id` on business rows. Global uniques (`users.email`, `projects.tool_number`, …) would still block a second tenant from reusing natural keys.

## Decision

1. Rebuild natural-key uniques as `(tenant_id, …)` — catalog in `app/db/tenant_unique_constraints.py`.
2. Add singleton uniques on `tenant_id` for settings packs (company/branding/email/…).
3. Leave UUID-FK child uniques unchanged (`timesheets(user_id, week_start)`, etc.).
4. Phase **71** drops legacy uniques where possible and creates tenant-scoped indexes/constraints.
5. **SQLite note:** table-level autoindexes on old column UNIQUE may not be droppable; new installs via `create_all` are correct. Postgres production path fully rebuilds.

## Exit criteria

- [x] Catalog + ADR
- [x] ORM `UniqueConstraint("tenant_id", …)`
- [x] Phase71 wired
- [x] Tests: cross-tenant same email OK; same tenant duplicate rejected
