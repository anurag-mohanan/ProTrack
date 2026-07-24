# R1 Platform deploy runbook

## Defaults
- Prosohm production may keep **SQLite** (`DATABASE_URL=sqlite:///./protrack.db`).
- Staging / future scale: **Postgres** via `DATABASE_URL=postgresql+psycopg2://...`.

## Upload volume
Set `PROTRACK_UPLOAD_DIR` to a persistent path (e.g. `/var/lib/protrack/uploads`).  
If not writable, API starts but `/health` reports `degraded` and logs a warning.

## Greenfield Postgres
1. Start Postgres (see `docker-compose.yml`).
2. `alembic upgrade head` (creates ORM tables).
3. Start API — phase sync fills remaining columns/indexes.
4. Optional: `python -m app.jobs.runner --loop` for durable job processing.

## Backups
- SQLite: Admin Backup copies `*.db` files under `Backups/`.
- Postgres: Admin Backup runs `pg_dump -Fc` to `Backups/*.dump` (requires `pg_dump` on PATH).

## Jobs
- Ops maintenance action `process_background_jobs`, or CLI runner above.
- Historical / timesheet imports enqueue durable rows then run via BackgroundTasks.

## Later cutover (not R1 mandatory)
Documented in [ADR-001](../architecture/ADR-001-r1-platform.md). Plan a maintenance window, `pg_dump`/`restore` or ETL, dual validation, then flip `DATABASE_URL`.
