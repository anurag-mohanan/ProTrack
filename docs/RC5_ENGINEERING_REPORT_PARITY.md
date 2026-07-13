# Engineering Excel report parity — Senior → Testing → QC

Baseline samples:
- `monthly-engineering-2026-06-01.xlsx` (Jun 2026)
- `quarterly-engineering-2026-04-01.xlsx` (Q2 2026: Apr–Jun)

## Senior developer — verdict

**Sheet structure already matches the prior production workbooks (14 sheets, same columns).**  
What looked “thinner” in UI was an incomplete on-screen preview, not a reduced Excel model. Excel remains the source of truth for full depth.

| Sheet | Prior monthly sample | Current generator |
|-------|----------------------|-------------------|
| Executive Summary | 19 KPIs | Same 19 KPIs |
| Designer Productivity | 10 cols | Same |
| Designer Tool Breakdown | Design/Surf/Review/BOM/Meetings/NP/Other | Same |
| Tool Hours | Quoted/Actual/Variance/Stage/Status + assignments | Same |
| Customer / Team Summary | Present | Same |
| Function / NP / Leave | Present | Same |
| Quoted vs Actual | Health + late milestones | Same |
| Project Performance | Milestone % + predicted finish | Same |
| Detailed Entries | Full period line items (~218 rows in sample) | Same columns; customer now resolved via project when entry.customer_id is null |
| Charts | 5 series (designers, P vs NP, customers, functions, over-quote) | Same 5 |
| AI Insights | Narrative bullets | Generated for executive-category reports |

### Semantics to preserve (do not “simplify”)
1. **Period sheets** (productivity, NP, leave, detailed entries, function hours, customer/team summaries) are **period-scoped**.
2. **Tool Hours / Quoted vs Actual / Project Performance** use **life-to-date project actuals** vs quoted (same as prior samples).
3. Download path: Reports → Engineering Overview → Monthly/Quarterly → **Download Excel**.

### Fixes in this pass
- Detailed Entries: fill Customer from `Project.customer_id` when entry customer is null (historical import parity).
- Engineering Overview UI: preview now surfaces all major workbook sections (not only 3 tables).
- Banner lists the 14 Excel sheet names so testers know full depth is in the file.

### Deploy blockers before parity testing
- API on `192.168.20.254` must not return 502 (see `docs/RC5_RELEASE_GATE.md`).
- Production DB must contain the historical timesheet rows (local empty DB will look empty even when structure is correct).

## Testing team — section matrix

| # | Check | Pass criteria |
|---|--------|---------------|
| 1 | Monthly engineering Excel | Opens with **exactly 14 sheets** named as prior |
| 2 | Quarterly engineering Excel | Same 14 sheets; period label is quarterly range |
| 3 | Executive KPIs | Period, working days, team size, hours, billable %, util %, leave, projects, quoted/actual/variance, top tool/customer/designer |
| 4 | Designer Productivity | Productive / NP / leave / util / projects / customers populated for active designers |
| 5 | Designer Tool Breakdown | Per designer × tool rows; NP bucket present |
| 6 | Tool Hours | Assignment columns + variance coloring |
| 7 | Customer / Team / Function / NP / Leave | Non-empty when period has matching hours |
| 8 | Quoted vs Actual + Project Performance | Health + completion present |
| 9 | Detailed Entries | Row count ≈ timesheet lines in period; Customer/Tool filled when project known |
| 10 | Charts | 5 chart blocks with objects (not empty) |
| 11 | AI Insights | At least one bullet when data exists |
| 12 | UI preview | Shows tool breakdown, NP, leave, quoted, performance, detailed preview + Excel sheet banner |

Compare a regenerated **June 2026 monthly** (on production DB) against the provided sample for column headers and sheet inventory (row totals may differ if data changed).

## QC — final audit before UAT

- [ ] Sample monthly regenerated on production host after API health PASS
- [ ] Sheet inventory = 14 / names match prior
- [ ] Spot-check Detailed Entries customer/tool for a known productive day
- [ ] Spot-check Tool Hours quoted vs actual for one over-budget tool
- [ ] Spot-check Charts sheet has embedded charts
- [ ] Spot-check AI Insights not blank with real data
- [ ] UI preview shows expanded sections (not KPIs-only)
- [ ] Sign-off → release for user testing
