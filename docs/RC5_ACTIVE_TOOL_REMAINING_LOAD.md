# RC5 — Active tools always show remaining load (Assigned ≠ Open)

## Ops + Engineering Manager brainstorm → Senior decision

### Problem
Designers clearly working tools (e.g. Sarath on project 2649 — milestones In Progress / Completed) still looked **free / Open** on Resource Planning: weekly cells `0% · 40h free` while the chip said Assigned. Milestone rows showed **`0/0 hrs (NaN%)`** and summary **0% progress · 0 hrs remaining**.

### Root causes
1. RP remaining hours = `max(planned_or_quoted − actual, 0)` → **0** once actual exceeds plan (342 vs 210).
2. Milestone planned hours of `0` / `"0.00"` → JS `actual / "0.00"` → **NaN%**.
3. Summary progress averaged raw `progress_percent` (0 even on completed historical rows) instead of status-aware progress.

### Ideas → locked
| Idea | Verdict |
|------|---------|
| Hide Assigned chip when util 0 | Rejected — hides assignment truth |
| Cap remaining at 0 and ignore overburn tools | Rejected — makes actives look idle |
| **Active tools schedule unfinished milestone planned hours; else quote-share of open MS; else floor (16h × open MS or 40h carry for CBW/planning)** | **Locked** |
| Status-aware progress (completed=100%) + finite hours % | **Locked** |

## Senior-approved code

| File | Change |
|------|--------|
| `app/services/resource_planning_service.py` | `_active_planning_remaining` + open-milestone batch load |
| `app/services/milestone_workspace_service.py` | Status-aware overall progress; remaining from open MS / quote share |
| `frontend/.../ProjectMilestoneGridRow.tsx` | `toFiniteNumber`; no NaN% when planned ≤ 0 |

## Testing checklist

| # | Check | Pass |
|---|--------|------|
| 1 | Restart API + hard refresh | |
| 2 | Designer on live over-burned tool: RP cells not all `0% · 40h free` | |
| 3 | Left list hours align with grid totals for that designer | |
| 4 | Assigned/Open chip matches live assignment; Open only if no live tools | |
| 5 | Milestones: no `NaN%`; shows `actual/planned hrs` without bogus % when planned=0 | |
| 6 | Milestone summary: progress > 0 when some MS completed; remaining > 0 when open MS remain | |
| 7 | Set planned hours on open MS → RP uses those planned totals | |

## Testing lead → QC

- [ ] Smoke Resource Planning + Project Milestones for an over-hours live tool  
- [ ] Sign-off → user testing  
