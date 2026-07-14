# RC5 — Timesheets page cleanup (remove redundant banner)

## Ops + Engineering Manager brainstorm → Senior decision

### Question
Do we need the large sticky card under **Timesheets** that shows month + “Your teams — timesheet overview” + Customer/Due/Draft placeholders?

### Answer (locked)
**No.** It duplicates information already on the page and wastes vertical space without helping entry or monitoring.

| Block | Keep? | Why |
|-------|-------|-----|
| Page title + short subtitle | Yes | Orientation |
| Sticky “July 2026 / overview / Draft” card | **Remove** | Redundant with month nav + summary status |
| Month navigation (arrows + Month/Year/Jump) | Yes | Primary period control |
| My Entries / All Users | Yes | Mode switch |
| Summary rollup (Today/Weekly/Monthly + Billable…) | Yes | The useful “at a glance” strip |
| Team/person timesheet list | Yes | Primary work surface |

### Ideas parked (later)
- Collapse Month/Year into the arrow row only (Jump-to remains)
- Sticky mini summary on scroll for long All Users lists

## Senior-approved code

| File | Change |
|------|--------|
| `frontend/src/pages/TimesheetsPage.tsx` | Remove `StickyRecordHeader`; shorten PageHeader subtitle |
| `frontend/src/components/timesheets/TimesheetMonthNavigation.tsx` | Always-shrink Month/Year labels (no overlap) |

Draft / Submitted / Approved status remains visible on **TimesheetMonthSummaryBar** (`TimesheetStatusChip`).

## Page flow after change

1. Title → Submit (when available)  
2. Month picker  
3. Mode tabs (when applicable)  
4. Summary rollup  
5. Entries form (My Entries) **or** team overview list (All Users)

## Testing checklist

| # | Check | Pass |
|---|--------|------|
| 1 | No large empty sticky card under page title | |
| 2 | Month still controllable via arrows + Month/Year/Jump | |
| 3 | Status chip still visible on summary bar | |
| 4 | EM All Users: team rollup + person rows unchanged | |
| 5 | My Entries: entry form + table still work | |
| 6 | Submit Timesheet still appears when draft has entries | |
| 7 | Month/Year dropdown labels do not overlap values | |

## Testing lead → QC

- [ ] Desktop smoke: My Entries + All Users  
- [ ] Deploy `frontend/dist`, hard refresh  
- [ ] Sign-off → user testing  
