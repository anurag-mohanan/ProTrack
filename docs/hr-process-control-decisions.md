# HR Process Control — Decisions

Captured for delivery (Gate 0). Product choices **1A** (create User when onboarding starts) and **2A** (in-app + email to team leader) are confirmed.

| Topic | Decision |
|-------|----------|
| User create timing | When onboarding checklist is **started** (`POST /hr/onboarding`) |
| Minimum fields | `employee_name` + **email** required to auto-create User. Temporary password generated; `must_change_password=true`. `team_id` / `reporting_manager_id` preferred but not blocking create (orphan placement audited). |
| Default role | Provisional **Designer** (or payload `role_id` if provided). Leader or Admin may change role later. |
| Notify recipients | Prefer team `team_lead_id`; fallback `reporting_manager_id`. No Help Desk ticket for leader. No mandatory HR CC in v1. |
| Duplicate email | **Block** create with clear validation error. If `employee_user_id` already set, **link only** (no second User). |
| Incomplete onboarding SLA | `in_progress` and (`joining_date` or checklist `created_at`) older than **14 days**. |
| Missing exit | User has `leaving_date` set **or** `is_active=false`, and no exit interview with `status=completed` linked via `employee_user_id`. |
| Exit done, still active | Flag when exit interview `completed` but linked user still `is_active=true` and no `leaving_date` (or leaving_date in future). |
| Audit access | HR + Admin (module Human Resources view / manage). |
| Leader notify content | New hire name, team, joining date; ask leader to set role/access; deep links to Users + Onboarding. |
