# Mutation reliability audit

Audit date: 2026-09-02. Entry point: project team changes appearing in UI but not persisting after refresh.

## Summary

| Area | Risk | Status |
|------|------|--------|
| Project PATCH (team_id) | High — full payload re-authorized unchanged team | Fixed |
| Project create payload | Medium — missing required fields surfaced as 422 | Tests updated |
| Performance review PATCH | High — manager section save replaced all rows | Fixed (partial updates) |
| Performance review fields | Medium — goals/comments permission gaps | Fixed + tested |
| Timesheet entry stream | Low — task type must match project stream | Validated in tests |
| Silent mutation failures (frontend) | Medium — missing error handlers | Partially fixed |

## Project mutations

### Root cause (team change)

1. Frontend sent full project body on every save, always including `team_id`.
2. Backend `can_assign_project_team()` rejected PATCH when the user could edit a cross-team assignment but lacked scope on the project's current team.
3. Save errors were easy to miss in the UI; command-center cache was not invalidated.

### Fixes

- `can_change_project_team()` — skip team re-authorization when `team_id` is unchanged.
- `ProjectFormDialog` — partial PATCH via `buildChangedProjectUpdate()`; designer→team sync only on create.
- `queryInvalidation` — invalidate command-center detail after project save.
- `ProjectDetailPage` — decision update/delete use `.catch()` + user-visible errors.

### Regression tests

- `test_edit_assigned_cross_team_project_with_unchanged_team_id`
- `test_team_change_persists_for_authorized_editor`
- `test_cannot_move_project_to_unauthorized_team`
- `test_imported_project_full_edit_workflow`

## Performance review mutations

### Issues

1. Manager PATCH used `_apply_manager_sections`, clearing and recreating section rows (IDs changed; fragile for concurrent edits).
2. `career_goals` (Targets / Goals) and `employee_summary` (Employee comments) must persist through save → reload.
3. Field permissions: employees edit own comments/goals; managers edit strengths, improvements, reviewer notes, ratings.

### Fixes

- `_apply_manager_section_updates()` — partial section/item updates by ID; preserves structure.
- Frontend `buildPerformanceReviewSaveBody()` — only sends fields the user may edit.
- Frontend labels aligned: bottom field maps to `career_goals`.

### Regression tests

- `test_employee_can_save_career_goals_and_reload`
- `test_manager_can_save_career_goals_and_reviewer_notes`
- Existing self-rating and admin edit tests

## Timesheet / reporting (prior work)

- Utilization uses team membership windows and working days (`utilization_capacity.py`).
- Report section selection and company logo path resolution verified in tests.

## Remaining follow-ups

1. Scan other frontend mutations for `void promise` without `.catch()` (projects partially addressed).
2. IT import and bulk mutation paths — separate audit if historical import regressions recur.
3. Command-center stream filters — verify team change reflects in list/filter after invalidation (manual QA).

## Manual verification checklist

- [ ] Admin: move imported project team Eng3 → Eng4, refresh, confirm list + reports.
- [ ] Employee: save performance review goals + comments, reload workspace, confirm values.
- [ ] Manager: save ratings + reviewer notes on in-progress review, reload, confirm locked after complete.
