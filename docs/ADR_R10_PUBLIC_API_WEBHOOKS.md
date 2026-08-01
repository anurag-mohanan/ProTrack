# ADR R10-007 — Public API + outbound webhooks (draft)

**Status:** Accepted / implementing (draft surface)  
**Date:** 2026-08-01  
**Related:** [R10_COMMERCIALIZATION_STRATEGY.md](./R10_COMMERCIALIZATION_STRATEGY.md)

## Context

Commercial packaging needs a **versioned public API** and **outbound webhooks** gated by edition flags (`feature.public_api`, `feature.webhooks`), separate from the JWT session API.

## Decision

1. Mount public API at **`/api/public/v1`** (not under session `/api/v1`).
2. Authenticate with **tenant API keys** (`Authorization: Bearer pt_live_…` or `X-Api-Key`).
3. Store only **SHA-256 hashes** of keys; show raw secret once at creation.
4. Admin manages keys + webhook endpoints under Commercial settings (JWT Admin).
5. Draft resources: `GET /health`, `GET /projects`, `GET /projects/{id}`.
6. Webhooks: register URL + event types; `emit_event` POSTs signed JSON (HMAC-SHA256) and records delivery attempts.
7. Gate routes with feature flags; Prosohm enterprise keeps both ON.

## Non-goals (this draft)

- Full REST parity with internal CRUD  
- Celery/Redis broker (see R10-008 for in-process retries)  
- OAuth client-credentials for partners  

## Follow-on

See [ADR_R10_PUBLIC_API_EXPAND_RETRIES.md](./ADR_R10_PUBLIC_API_EXPAND_RETRIES.md) (R10-008).

## Exit criteria

- [x] ADR + models + phase72
- [x] Public API key auth + projects read
- [x] Webhook endpoint CRUD + signed emit stub
- [x] Admin UI on Commercial page
- [x] Tests
