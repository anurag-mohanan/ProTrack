# ADR R10-008 — Public API expand + webhook retries

**Status:** Accepted  
**Date:** 2026-08-01  
**Related:** [ADR_R10_PUBLIC_API_WEBHOOKS.md](./ADR_R10_PUBLIC_API_WEBHOOKS.md), [R10_COMMERCIALIZATION_STRATEGY.md](./R10_COMMERCIALIZATION_STRATEGY.md)

## Context

The R10-007 draft exposed projects only and delivered webhooks once. Partners need a slightly richer read surface and reliable delivery with backoff.

## Decision

1. **Public API v1** (still `/api/public/v1`, API-key auth):
   - Enrich `GET /projects` / `/{id}` with status, stage, health, priority, due_date, customer_id.
   - Add `GET /projects/{id}/milestones` (`milestones:read`).
   - Add `GET /users` directory (`users:read`) — non-sensitive fields only.
   - Add `GET /me` — key + tenant metadata for the calling key.
2. **Scopes:** `projects:read`, `milestones:read`, `users:read`, `*` (admin wildcard).
3. **Webhook retries** (no external broker yet):
   - Columns: `next_attempt_at`, `max_attempts` (default 5) on `webhook_deliveries`.
   - Failed POSTs stay `pending` with exponential backoff; exhausted → `dead`.
   - `process_due_deliveries()` drains due rows; admin `POST .../webhooks/process-retries` (+ optional per-delivery retry).
4. Phase73 schema sync for new columns.

## Non-goals

- Full CRUD on public API  
- Celery/Redis worker (cron or admin trigger is enough for this stage)  
- Partner OAuth  

## Exit criteria

- [x] ADR + phase73 columns  
- [x] Expanded public routes + scopes  
- [x] Retry processor + admin trigger  
- [x] Tests + strategy checklist  
