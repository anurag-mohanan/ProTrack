# R1 Critical Platform — QC / UVT checklist

Decisions: [ADR-001](../architecture/ADR-001-r1-platform.md)

## Engineering smoke
- [ ] `GET /health` returns `checks.database` and `checks.upload_dir_writable`
- [ ] SQLite backup create/list/restore still works from Admin
- [ ] With Postgres `DATABASE_URL`, backup creates `.dump` when `pg_dump` available
- [ ] Historical import run enqueues `background_jobs` row and completes
- [ ] `POST /emails/queue/process` returns processed count + job_id
- [ ] Ops action `process_background_jobs` runs due jobs
- [ ] `python -m app.jobs.runner --once` exits 0
- [ ] User create with import+approve timesheet specials returns 422 SoD message
- [ ] Alembic: `alembic history` shows `001_r1_baseline`
- [ ] Login, timesheets, projects, reports, HR onboarding — no UX regressions

## QC
- [ ] No SPA route/theme/nav changes
- [ ] `/api/v1` contract additive only
- [ ] Upload dir warning logged if not writable
- [ ] Deploy README reviewed

## UVT / UAT (platform)
- [ ] Admin: Backup on SQLite
- [ ] Admin: Security / Users SoD rejection message clear
- [ ] Ops: process email queue + process background jobs
- [ ] Staging Postgres boot (optional): compose up, migrate, API `/health` ok

**QC:** ________ **UVT:** ________ **UAT:** ________ **Date:** ________
