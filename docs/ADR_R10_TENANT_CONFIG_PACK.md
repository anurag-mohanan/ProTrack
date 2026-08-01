# ADR R10-005 — Tenant config pack (branding + terminology + numbering)

**Status:** Accepted / implementing  
**Date:** 2026-08-01  
**Related:** [R10_COMMERCIALIZATION_STRATEGY.md](./R10_COMMERCIALIZATION_STRATEGY.md)

## Context

Commercial packaging needs a single **tenant pack**: labels, numbering rules, and branding — without forking Prosohm Theme / Company settings UIs.

## Decision

1. **Terminology & numbering** live on `tenants.terminology_json` / `numbering_policy_json` (expanded catalogs in `tenant_pack_service`).
2. **Branding & company** remain in `branding_settings` / `company_settings` (already tenant-scoped); the pack **reads** them as the live façade.
3. API: `GET /commercial/me/pack`, `PATCH /commercial/me/terminology`, `PATCH /commercial/me/numbering`.
4. Admin Commercial page edits terminology/numbering and shows branding summary (Theme page remains source of colour edits).
5. `ensure_tenant_config_defaults` fills missing catalog keys on startup / pack read (overrides preserved).

## Exit criteria

- [x] Pack service + catalogs
- [x] Commercial pack APIs
- [x] Admin UI editors
- [x] Tests
