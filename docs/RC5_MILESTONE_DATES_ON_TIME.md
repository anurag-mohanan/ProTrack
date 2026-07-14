# RC5 — Unified DD-MM-YYYY dates + On-time milestone column

## Ops + Engineering Manager brainstorm → Senior decision

### Problem
Target date inputs showed **DD-MM-YYYY** while completion dates rendered as **M/D/YYYY** (browser locale via `toLocaleDateString()`). Hours column cluttered Milestones with `0/0 hrs` and was not the schedule focus. Ops needs a clear **completed in time** signal vs Target.

### Ideas → locked

| Idea | Verdict |
|------|---------|
| Leave locale-dependent date display | Rejected — inconsistent across machines |
| Force US M/D/YYYY | Rejected — does not match India office / existing Target pickers |
| **Canonical display `DD-MM-YYYY` via `formatDate` / `DD-MM-YYYY HH:mm` via `formatDateTime`** | **Locked** |
| Custom date picker lib for inputs | Parked — native picker still OK; grid cell shows DD-MM-YYYY |
| Keep Hours on milestone rows | Rejected for this grid (planned hours still on Add + summary) |
| **Remove Hours column; add Completed in time (On time / Late / —)** | **Locked** |
| On time = completion calendar day ≤ Target | **Locked** |

## Senior-approved code

| File | Change |
|------|--------|
| `frontend/src/utils/format.ts` | Fixed DD-MM-YYYY; `isCompletedOnTime()` helper |
| `frontend/.../ProjectMilestoneGrid.tsx` | Drop Hours header; add Completed in time |
| `frontend/.../ProjectMilestoneGridRow.tsx` | Display Target as DD-MM-YYYY; On time / Late column |

## Testing checklist

| # | Check | Pass |
|---|--------|------|
| 1 | Hard refresh frontend (API restart not required) | |
| 2 | Milestones: no Hours column | |
| 3 | Target and Completed dates both show **DD-MM-YYYY** (e.g. `01-07-2026`) | |
| 4 | Other screens using `formatDate` (project due, drawers) also show DD-MM-YYYY | |
| 5 | Completed with target in future/same day → **On time** | |
| 6 | Completed after target → **Late** | |
| 7 | Not completed or missing target → **—** | |
| 8 | Click Target cell → date picker still saves correctly | |

## Testing lead → QC

- [ ] Smoke project 2649 Milestones for date parity + On time/Late
- [ ] Spot-check Projects list Due column format
- [ ] Sign-off → user testing
