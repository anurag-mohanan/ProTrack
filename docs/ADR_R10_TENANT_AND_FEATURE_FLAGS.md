# ADR R10-001 — Tenant spine & feature flags (commercial foundation)

**Status:** Accepted for implementation  
**Date:** 2026-08-01  
**Related:** [R10_COMMERCIALIZATION_STRATEGY.md](./R10_COMMERCIALIZATION_STRATEGY.md)

## Context

ProTrack runs as a single-company (Prosohm) production system. Commercial SaaS requires tenant isolation and edition gating **without** forking the codebase or interrupting Prosohm.

## Decision

1. Introduce a `tenants` table. Seed **Prosohm** as the default tenant (stable UUID).  
2. Bind per-request tenant via context (`X-Tenant-Id` optional; default = Prosohm).  
3. Do **not** backfill `tenant_id` onto every business table in this phase — that is Phase M1 expand (tracked separately). This phase ships the **spine** only.  
4. Introduce `feature_flags` scoped by `tenant_id`. Catalog is code-defined; rows are overrides/state.  
5. Tenant `edition` selects default flag matrix; Prosohm edition = `enterprise` (all product flags ON).  
6. Terminology / numbering dictionaries live on the tenant as JSON config (extensible without migrations per key).

## Consequences

- Prosohm behaviour unchanged when flags default ON.  
- External tenants can be created later with restricted editions.  
- Future M1 adds `tenant_id` columns with online backfill to Prosohm UUID.  
- No `if company == Prosohm` in domain code — use tenant config + flags.

## Out of scope (this slice)

- Billing / Stripe  
- Host-based tenant routing  
- Row-level security on projects/users  
- Customer portals  
- Full `tenant_id` backfill → **done in M1** ([ADR_R10_M1_TENANT_ID_BACKFILL.md](./ADR_R10_M1_TENANT_ID_BACKFILL.md))

## Exit criteria

- [x] RFC published  
- [x] Prosohm tenant seeded on startup
- [x] Feature flags API + Admin UI
- [x] Tests: default tenant, enterprise flags ON, flag override
