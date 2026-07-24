# Performance Cycle Dossier — Decisions (Gate 0)

Brainstorm input: `docs/performance-cycle-dossier-brainstorm.md`.

| Topic | Decision |
|-------|----------|
| Domain | Extend Performance module with a **Cycle dossier** (not a new top-level nav module). |
| Period | Existing `review_period_bounds(review_year)` — **1 Jul (year−1) → 30 Jun (year)**. |
| API | `GET /hr/performance/dossier?user_id=&review_year=` and `GET /hr/performance/dossier-roster?review_year=&team_id=`. |
| Access | Same as performance dashboard: self always; others if in `_managed_team_ids` members or HR edit/view. |
| Hours | Per-month `compute_month_summary` with expected = working days × `user.working_hours_per_day`. |
| Over-capacity months | Count months where `monthly_percent > 100`. |
| Leave | Timesheet leave days only; disclaimer that GreytHR is SoR for balances. |
| Projects | Reuse `discover_employee_projects` for the period; enrich with quoted/actual hours. |
| Checking | Sum hours where task type name matches check/review heuristics. |
| Prior review | Latest **acknowledged annual** sheet ending on/before period end (prefer prior year); expose score + goals/summaries. |
| Roster | One row per visible employee with headline KPIs (hours %, leave days, project count, prior score). |
| UI | Performance → **Cycle dossier** section; individual view + leader roster when viewer manages teams. |
| Write path | Read-only derived; no new tables in v1. |
