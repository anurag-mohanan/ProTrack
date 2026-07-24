# Employee Training — Decisions (Gate 0)

Brainstorm input: `docs/employee-training-brainstorm.md`.

| Topic | Decision |
|-------|----------|
| Domain | New **Training** module under HR (not R4 learning plans). |
| Models | `TrainingCourse` (catalog) + `TrainingAssignment` (per user). |
| Common courses | Seed five required-for-onboarding courses (orientation, IT security, ProTrack basics, leave/payslips, H&S). |
| Onboarding link | When onboarding checklist is created **and** `employee_user_id` is set, auto-assign all `is_required_for_onboarding` active courses. |
| Full onboarding | Checklist cannot reach `status=completed` while required training assignments for that employee are still `assigned`/`in_progress` past create (blocking). Soft message in API. |
| Employee complete | Employee (or HR) marks assignment `completed` with `completed_at`. |
| New courses | HR Admin creates course; optional assign-now to selected users / all active with due date. |
| Notify | `NotificationType.training_assigned` in-app; email template slug when available. Soft reminders: due soon / overdue (audit). |
| Availability | Due date only — no calendar free/busy in v1. |
| Audit | Process Audit flag `incomplete_training`: required or assigned training overdue (due_date passed, or required without due_date and &gt;14 days since assigned). Deep link `/hr/training`. |
| Access | HR manage: create courses/assign; employee: view own + mark complete; Process Audit: same as existing HR audit. |
| Content | Title, description, estimated minutes, optional `external_url`, owning department label — no file LMS in v1. |
