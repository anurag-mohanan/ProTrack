# Immutable / historical employee data

**Status:** Implemented  
**Does not rewrite existing employee rows.** Fill-in of previously blank dates remains allowed.

---

## Schema review (`users` + related)

There is **no `employee_number` / `employee_id` column on `User`**. Identity is:

| Field | Location | Classification |
|-------|----------|----------------|
| `id` | `users.id` (UUID) | **Immutable** — system-generated |
| `employee_code` | Onboarding / exit checklists only | **Immutable after set** (HR employee ID, e.g. PP045) |
| `joining_date` | `users.joining_date` | **Immutable after set** — company hire / tenure / finance / timesheet windows |
| `first_job_date` | `users.first_job_date` | **Immutable after set** — industry experience (Performance) |
| `created_at` | mixin | **Immutable** — not on update schema |

`leaving_date` is **not** immutable: it is the offboard control (already confirmation-gated).

---

## Remain editable (current operational state)

Team, department (`department_id` / org chart placement), role, designation, manager, stream / work function, active flag, contact (email/phone/name), skills, KPIs, working hours, employment type, availability.

**Workstream** is a project taxonomy, not an employee field.

---

## Historical records (do not overwrite silently)

| Change | Existing mechanism |
|--------|-------------------|
| Team (primary) | `TeamMembershipPeriod` + `UserJobEvent` transfer (`user_change_service.record_transfer`) |
| Role / designation | Lifecycle **Promote** → `UserJobEvent` |
| Working model / billing | `UserWorkingModelPeriod` + job event |
| Org department (chart) | `POST /org-departments/{id}/assign-user` logs `user_department_changed` |
| Last working day | Offboard service + `employee_offboard_*` activities |

**Fix applied:** changing primary team on **User edit** now records a dated transfer instead of only rewriting `User.team_id` / wiping membership without a period close.

Role/designation on the Users form remain live fields (people change jobs). Use **Performance → lifecycle Promote** when you need an effective-dated promotion on the history timeline. Do not treat current role as a hire-date fact.

---

## Controlled corrections (admin)

`POST /api/v1/users/{id}/historical-corrections`

Body: optional `joining_date`, `first_job_date`, required `reason`.

- Admin-only (same as `/users`)
- Rejects no-op / empty payloads
- Writes `ActivityAction.user_historical_correction` (old/new, actor, time, reason)
- Writes `UserJobEvent` `historical_correction` for the employee timeline
- Syncs linked onboarding checklist `joining_date` when that date is corrected

Normal `PATCH /users/{id}` **rejects** changes to already-set `joining_date` / `first_job_date` (422). Blank → value is allowed once.

Onboarding `PATCH` rejects changes to an already-set `employee_code` or `joining_date`.

---

## UI

Users admin: hire dates and user UUID are read-only with a lock when already set; **Correct historical dates** collects a reason. Onboarding edit locks Employee ID / joining date once set.
