# ADR R10-002 — M1 `tenant_id` backfill

**Status:** Accepted / implementing  
**Date:** 2026-08-01  
**Related:** [ADR_R10_TENANT_AND_FEATURE_FLAGS.md](./ADR_R10_TENANT_AND_FEATURE_FLAGS.md), [R10_COMMERCIALIZATION_STRATEGY.md](./R10_COMMERCIALIZATION_STRATEGY.md)

## Context

M0 shipped the tenant spine (`tenants`, `feature_flags`, request context). Commercial isolation still requires every business row to carry `tenant_id`, backfilled to Prosohm for the current single-tenant deployment.

## Decision

1. Add `TenantMixin` (`tenant_id` → `tenants.id`, indexed, default = request tenant or Prosohm).
2. Phase **70** adds `tenant_id` to all tenant-scoped tables (A+B inventory), backfills `PROSOHM_TENANT_ID`, creates indexes.
3. **Do not** add `tenant_id` to: `tenants`, `currencies` (global ISO), or re-declare on `feature_flags`.
4. **Defer M1b:** rebuild global unique constraints to `(tenant_id, …)` — still safe while only Prosohm exists.
5. **Defer M1c:** automatic query filtering / RLS — columns + write defaults first.

## Inventory source of truth

`app/db/tenant_scoped_tables.py` — `TENANT_SCOPED_TABLES`.

## Exit criteria

- [x] ADR published
- [x] Phase70 adds + backfills columns
- [x] ORM `TenantMixin` on scoped models
- [x] Tests: Prosohm backfill on core roots; new ORM rows get Prosohm by default
- [x] Unique-constraint rebuild → M1b ([ADR_R10_M1B_TENANT_UNIQUES.md](./ADR_R10_M1B_TENANT_UNIQUES.md))

## Ops

Restart API after deploy so phase70 runs. Prosohm behaviour unchanged (all rows → same tenant).
