# RC5 — Project Timesheets tab (lines + KPI)

## Ops + Engineering Manager brainstorm → Senior decision

### Problem
Project workspace **Timesheets** tab was a placeholder pointing users to the Timesheets module. Ops/EM need in-context visibility of every line against the tool: who worked, what tasks, total hours, and checking effort (e.g. CMT-2649).

### Ideas → locked

| Idea | Verdict |
|------|---------|
| Keep deep-link only | Rejected — managers need project-context burn |
| Reuse Overview contributors only | Rejected — no task lines / checking |
| Edit timesheets inline on project tab | Parked — editing stays in Timesheets module |
| **Read-only project entry table + KPI strip** | **Locked** |
| Checking hours = productive task types matching Design Review / `check` / `review` (same as engineering reports) | **Locked** |
| Do not treat `contribution_reason=peer_review` as checking | **Locked** |
| KPIs: Total hours, Designers worked, Checking hours, Distinct tasks + hours-by-designer chips | **Locked** |

## Senior-approved code

| File | Change |
|------|--------|
| `frontend/.../ProjectTimesheetsPanel.tsx` | New tab UI: KPIs + designer chips + entry table |
| `frontend/.../ProjectWorkspace.tsx` | Wire Timesheets tab to panel |
| `frontend/src/utils/projectTimesheetSummary.ts` | Aggregate + checking classification |
| `frontend/src/api/timesheets.ts` | Document `project_id` on `fetchTimesheetEntries` |

## Testing checklist

| # | Check | Pass |
|---|--------|------|
| 1 | Hard refresh; open project → Timesheets tab | |
| 2 | KPI strip shows Total / Designers / Checking / Tasks | |
| 3 | Hours-by-designer chips match sum of table hours | |
| 4 | Table lists Date, Designer, Task, Description, Contribution, Hours | |
| 5 | Date format is DD-MM-YYYY | |
| 6 | Checking KPI rises when Design Review (or check/review) lines exist | |
| 7 | Empty project shows empty state; Open Timesheets still works | |
| 8 | Project with many lines loads (cap 500 warning if hit) | |

## Testing lead → QC

- [ ] Smoke on a tool with known timesheet history (e.g. 2649)
- [ ] Cross-check Total hours ≈ command-center / milestones actual hours
- [ ] Sign-off → user testing
