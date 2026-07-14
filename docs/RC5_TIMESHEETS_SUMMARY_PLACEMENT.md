# RC5 — Timesheets summary bar placement

## Ops + Engineering Manager brainstorm → Senior decision

### Problem
On **My Entries**, the hour rollup sat between the tabs and the entry form, while a large empty band remained under the form/actions next to the NP Codes rail. That made the page top-heavy and visually uneven.

### Approved layout

| View | Summary position |
|------|------------------|
| **My Entries** | Under quick actions, **left column**, filling the empty band beside NP Codes; entries table full-width below |
| **All Users** | Stay near top (after tabs) — monitors need rollup before team list |

Page flow (My Entries):
1. Month + tabs + status alerts  
2. Entry form + quick actions + **summary** | NP Codes  
3. Entries table  

### Ideas parked
- Compact single-line mini-summary above the table only  
- Move Efficiency into a tooltip on Monthly progress  

## Senior-approved code

| File | Change |
|------|--------|
| `frontend/src/pages/TimesheetsPage.tsx` | Relocate summary for My Entries into left column |
| `frontend/src/components/timesheets/TimesheetMonthSummaryBar.tsx` | Optional `sx` for nested spacing |
| `frontend/src/components/timesheets/TimesheetQuickActions.tsx` | Drop extra bottom margin (parent gap owns spacing) |

## Testing checklist

| # | Check | Pass |
|---|--------|------|
| 1 | My Entries: no summary strip between tabs and entry form | |
| 2 | My Entries: summary sits under Copy/Duplicate actions | |
| 3 | My Entries: empty white band above Entries table is gone / filled | |
| 4 | NP Codes still on the right, always open | |
| 5 | Entries table still full width under the form/summary row | |
| 6 | All Users: team rollup still appears near top | |
| 7 | Status chip still visible on the summary | |
| 8 | Add Entry + summary counts refresh after save | |

## Testing lead → QC

- [ ] Smoke My Entries + All Users (EM)  
- [ ] Deploy `frontend/dist`, hard refresh  
- [ ] Sign-off → user testing  
