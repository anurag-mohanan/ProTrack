# RC5 — KPI / metric card sizing (equal strip, page-fit)

## Ops + Engineering Manager brainstorm → Senior decision

### Problem
On **Workload** (and similarly Resource Planning) the top KPI row looked uneven: “Hours This Week” stretched wider with an empty value area; “Billable %” used oversized type; cards didn’t read as one matched strip. Nested KPIs inside a tinted `ModernPageHeader` summary box also fought the page layout.

### Ideas considered
| Idea | Verdict |
|------|---------|
| Per-page one-off CSS patches | Rejected — drifts again |
| Different card component per page | Rejected — three visual languages |
| **Shared equal CSS-grid `KpiStrip` + fill-width `KpiMetricCard`; KPIs sit on the page (not in a soft box); coerce Decimal/string hours** | **Locked** |
| Collapse 4 KPIs into 2 “hero” stats | Parked |

### Locked rules
1. **Equal cells** — KPI strips use `minmax(0, 1fr)` columns; every card is `width/height: 100%`.
2. **Same density** — compact strip cards share min-height (~96px), ~24px value type, tabular nums, ellipsis overflow.
3. **Always show a value** — blank / NaN formats fall back to `0` (or `—` when intentionally unavailable).
4. **No nested chrome** — don’t wrap strips in a second tinted panel; KPIs sit under the page title like Dashboard.
5. **Finite numbers** — API Decimals arrived as strings; use `toFiniteNumber` before reduce / %.

## Senior-approved code

| File | Change |
|------|--------|
| `frontend/src/components/analytics/KpiStrip.tsx` | Equal CSS grid; `Children.toArray`; legacy `columns` object still works |
| `frontend/src/components/ui/design-system/KpiMetricCard.tsx` | Fill cell; tighter compact scale; blank → `0` |
| `frontend/src/components/dashboard/DashboardKpiCard.tsx` | Explicit `width: 100%` |
| `frontend/src/components/ui/design-system/ModernPageHeader.tsx` | Drop tinted summary box (full-width slot only) |
| `frontend/src/pages/WorkloadPage.tsx` | KPIs under header; coerce hours; equal strip |
| `frontend/src/pages/ResourcePlanningPage.tsx` | Same strip pattern + number coerce |
| `frontend/src/utils/format.ts` | `toFiniteNumber` + string-safe `formatNumber` |

## Testing checklist

| # | Check | Pass |
|---|--------|------|
| 1 | Workload: 4 KPI cards equal width across page (desktop) | |
| 2 | Workload: “Hours This Week” shows a number (incl. `0`), not blank | |
| 3 | Workload: Billable % / NP Share look balanced (not oversized / clipped) | |
| 4 | Resource Planning: 4 KPIs equal width, Allocated Hours value visible | |
| 5 | Reports KPI strips still render equal columns | |
| 6 | Dashboard Executive KPI grid still even / clickable | |
| 7 | Projects command-center dense KPIs still select/filter | |
| 8 | Tablet / narrow: strip stacks 1→2→4 without horizontal overflow | |

## Testing lead → QC

- [ ] Smoke Workload, Resource Planning, Dashboard, Projects wall KPIs  
- [ ] Deploy `frontend/dist`, hard refresh  
- [ ] Sign-off → user testing  
