# Timesheet overview — only people who must fill

## Senior developer — decision

Team / all-teams Timesheets overview (Office Admin completion monitoring, EM/DL team view) lists **only users with Requires timesheet = Yes**.

| Shown | Hidden |
|-------|--------|
| Designers / Surfacers / Design Leaders with Requires on | Office Administrator, HR, Planning Board, System Admin |
| Anyone Admin marked **Requires timesheet** | Managers / team members with Requires **off** (manage-only) |

If someone still appears with “No hours this month” (e.g. Abhay CK), open **Users** admin and turn **Requires timesheet** off for that person — they are currently flagged as required in the database.

### Code
- `app/services/timesheet_overview_service.py` — overview + visible IDs filtered to `requires_timesheet`
- `frontend/src/utils/timesheetOverview.ts` — defensive UI filter
- Banner on OA Timesheets explains the rule

## Testing team

| # | Check | Pass |
|---|--------|------|
| 1 | OA → Timesheets | Chandrashekhar J / Planning Board / System Admin **not** listed |
| 2 | Unassigned | Empty or only required users (no System Admin) |
| 3 | Team sections | Only Requires-timesheet people |
| 4 | Designer with Requires on + 0 h | Still shown + “No hours this month” |
| 5 | Turn Requires off for a manage-only user | Disappears from overview after refresh |
| 6 | Designer self view | Unchanged (own form) |

## QC before UAT

- [ ] Monitor-only accounts absent from OA overview  
- [ ] Required designers still visible  
- [ ] Requires flag on Users controls visibility  
- [ ] Sign-off → UAT  
