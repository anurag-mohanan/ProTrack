# ADR-002: R2 Operational Control

## Status

Accepted (2026-07-24)

## Context

R1 established platform reliability (Postgres-ready, jobs, health, SoD). R2 focuses on
operational governance without redesigning timesheets, project create, navigation, or theme.

## Decision

Ship additive controls:

1. **Soft stage gate** — block `execution_status=completed` and `project_stage=final` when
   required milestones remain open (`ProTrackValidationError`).
2. **Quote→project handoff chip** — `needs_setup` + `setup_gaps` on `ProjectRead` for
   planning shells missing type/team/leader/due date/template.
3. **Timesheet org policy pack** — env-backed `PROTRACK_TIMESHEET_EDITABLE_MONTHS_BACK` and
   `PROTRACK_TIMESHEET_SOFT_LOCK_ENABLED`; exposed via `GET /api/v1/settings/timesheet-policy`;
   soft-lock banner on the oldest editable month.
4. **Unified approvals inbox** — `/approvals` reuses dashboard my-tasks; My Tasks “View all”
   links here.
5. **Pagination wiring** — Customers use server pagination + search; Projects list uses
   paginated API (`page_size` up to 500) while keeping client command-center filters.

## Consequences

- Completion/final requires required milestones first (existing tests already complete them).
- Soft-lock is advisory (edits still allowed); hard-lock unchanged aside from configurable window.
- Multi-country policy packs remain future work; one org pack is enough for Prosohm scale.
