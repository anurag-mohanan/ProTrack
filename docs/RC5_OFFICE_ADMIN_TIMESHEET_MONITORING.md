# Office Administrator — all-teams timesheet monitoring

## Senior developer — product intent

Office Administrator does **not** fill a personal timesheet. Their job is to ensure **every team** logs time regularly. They need:

| Capability | Decision |
|------------|----------|
| Open Timesheets module | Yes (already in role modules) |
| Personal entry form | No |
| Team-wise overview of **all** teams | **Yes — implemented** |
| Expand each person and see month entries | Yes (read-only) |
| Highlight people with Requires timesheet + 0 hours | Yes |
| Approve / reject / edit others’ timesheets | **No** (stays with Design Leader / EM) |

HR receives the same all-teams read-only scope (same compliance monitor class).

### Implementation notes
- Backend: `TIMESHEET_COMPLIANCE_VIEWER_ROLES` = Office Administrator + HR
  - Overview `scope_all_teams=true`
  - `can_read_timesheet` / `filter_visible_timesheets` include compliance viewers
  - Approve paths unchanged
- Frontend: `canViewAllTimesheets` includes HR / Office Admin; lands on all-teams overview; compliance banner + “No hours this month” chips

## Testing team — matrix

| # | Check | Pass |
|---|--------|------|
| 1 | Login as Office Administrator | Timesheets nav visible |
| 2 | Open Timesheets | Lands on **All teams — completion monitoring** (no personal form) |
| 3 | Team accordion list | Every active team appears (not only one home team) |
| 4 | Expand a designer with hours | Month entries visible, read-only |
| 5 | User with Requires timesheet + empty month | Warning chip “No hours this month” |
| 6 | Attempt approve/reject as Office Admin | Controls not available / API rejects |
| 7 | Login as Designer | Still only own timesheet (no all-teams) |
| 8 | Login as Design Leader | Team-scoped overview (not necessarily all teams) |
| 9 | Login as HR | Same all-teams read-only behavior as Office Admin |

## QC — audit before UAT

- [ ] Office Admin sees all teams on Timesheets
- [ ] No personal entry form for Office Admin
- [ ] Missing-hours highlight works for required users
- [ ] Cannot approve others’ timesheets
- [ ] Designer / DL scopes unchanged
- [ ] Sign-off → release for user testing
