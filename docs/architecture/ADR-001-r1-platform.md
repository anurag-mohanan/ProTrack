# ADR-001 — R1 Critical Platform Foundations

**Status:** Accepted  
**Date:** 2026-07-24  
**Context:** ProTrack enterprise evolution Release 1 (platform only).

## Decision

Harden ProTrack for production and Postgres readiness **without** changing user-facing workflows, SPA routes, themes, or breaking `/api/v1` contracts.

### Locked choices

| Topic | Decision |
|-------|----------|
| Database | SQLite remains default for Prosohm. Postgres is first-class via `DATABASE_URL`. No forced cutover in R1. |
| Migrations | Phase sync (startup `ensure_*`) remains source of truth for upgrades. Alembic provides a **baseline** for greenfield Postgres; freeze of phase sync is deferred. |
| Jobs | Durable `background_jobs` table + CLI/ops runner. No Redis/Celery in R1. |
| Storage | Local `PROTRACK_UPLOAD_DIR` on a persistent volume. Object storage deferred. |
| API | Freeze `/api/v1`. Additive endpoints only. No `/api/v2` in R1. |
| Auth | Soft segregation-of-duties (SoD) on special permissions. MFA/SSO columns stay unused (no Entra UI). |

## Consequences

- Existing deployments keep working unchanged after pull + restart.
- Staging can boot on Postgres with Alembic stamp/baseline + phase sync.
- Imports and email processing survive process restart when the job runner is used.
- Breaking API or UX changes require a new ADR and are out of scope for R1.

## API compatibility rule

Any change under `/api/v1` must be **backward compatible** (new fields optional, new endpoints additive). Removals or semantic breaks require a major API version and explicit migration notes.
