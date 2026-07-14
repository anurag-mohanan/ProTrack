# RC5 — Timesheets compact header / month toolbar

## Ops + Engineering Manager brainstorm → Senior decision

### Problem
The top of Timesheets felt blank and noisy: generic subtitle, a large centered month title, **plus** separate Month / Year / Jump controls that all did the same job. Too much whitespace, little value.

### Locked decisions

| Item | Decision |
|------|----------|
| Subtitle (“Enter and review your monthly hours”) | **Remove** — page title already says Timesheets |
| Month/Year dropdown pair | **Remove** — redundant with arrows + jump |
| Centered giant month band | **Replace** with compact inline toolbar |
| Keep | `‹ Month Year ›` + one **Jump** month picker |
| Mode tabs + Submit | Sit on the **same toolbar row** (right side) |

### Resulting My Entries chrome
`[‹ July 2026 ›] [Jump] …… [My Entries | All Users] [Submit]`  
→ alerts → entry form + NP codes → summary → table

## Senior-approved code

| File | Change |
|------|--------|
| `frontend/src/components/timesheets/TimesheetMonthNavigation.tsx` | Compact toolbar + `endAdornment` |
| `frontend/src/pages/TimesheetsPage.tsx` | Drop PageHeader fluff; tabs/Submit in month toolbar |

## Testing checklist

| # | Check | Pass |
|---|--------|------|
| 1 | No generic “Enter and review…” subtitle under title | |
| 2 | No separate Month + Year dropdowns | |
| 3 | Prev / next still change months | |
| 4 | Jump picker still jumps to any month | |
| 5 | My Entries / All Users still switch modes | |
| 6 | Submit Timesheet still shows when draft has entries | |
| 7 | Top of page is one tight row (no large blank band) | |
| 8 | Mobile: toolbar wraps cleanly without overlap | |

## Testing lead → QC

- [ ] Smoke My Entries + All Users  
- [ ] Deploy `frontend/dist`, hard refresh  
- [ ] Sign-off → user testing  
