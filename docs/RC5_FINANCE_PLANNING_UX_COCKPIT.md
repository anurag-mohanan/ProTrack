# RC5 — Financial Planning UX Cockpit (Phase B)

**Status:** CTO-approved Phase B — visual FP&A cockpit for Internal UAT  
**Date:** 2026-07-16  
**Stakeholders:** Head of Finance · Head of Engineering · Head of Sales · CEO · President · Head of UI/UX · Graphic Designer · CTO

---

## 1. Why Phase B

Phase A shipped plan-vs-actual math and scenario clone, but the Finance UI still read as **stacked text cards**. Leadership asked for a module that feels closer to **Abacum / Adaptive / Mosaic / QBO / Xero** — scannable, chart-led, decision-oriented.

---

## 2. Brainstorm (product + design)

| Stakeholder | Pain | Direction |
|-------------|------|-----------|
| **Head of Finance** | Cannot spot variance or cost mix in 5 seconds | Hero KPIs + Plan vs Actual bars + cost composition donut |
| **Head of Sales** | Revenue signals buried in labels | Revenue / fee KPIs with accent + team fee bars |
| **Head of Engineering** | Overhead CPR and OpEx look the same as text | Distinct overhead strip + utilization-style meters |
| **CEO / President** | Board glance needs one composition | Overview = executive cockpit; Annual Plan = workbook + variance visual |
| **Head of UI/UX** | Dense caption/value cards, no hierarchy | Design-system KPI cards, AppCard sections, chartTheme palette |
| **Graphic Designer** | Flat outlined boxes feel legacy | Soft elevation, semantic accents, donut/bar charts, progress tracks — not purple glow / neon |

### Inspiration map (what we borrow, what we don’t)

| Platform | Borrow | Skip this phase |
|----------|--------|-----------------|
| Abacum | KPI strip + variance callouts | Full driver modeler |
| Adaptive / Anaplan | Plan vs Actual grouped bars | Multi-cube scenarios UI |
| Mosaic | Services cost mix + utilization feel | PSA resource grid |
| Prophix | Sectioned report cards | Board pack PDF |
| QBO / Xero | Budget remaining meters, P&L clarity | Bank feeds / GL |

---

## 3. CTO-approved Phase B scope

| # | Surface | Change |
|---|---------|--------|
| B1 | **Overview** | Executive cockpit: KPI strip (KpiMetricCard), cost-mix donut, team OpEx bars, renewal chips |
| B2 | **Annual Plan** | Plan vs Actual grouped bar chart + rolling forecast KPI strip; keep editable grids |
| B3 | **Budgets & reports** | Visual budget utilization meters + Budget vs Actual signal panel (styled) |
| B4 | **Page chrome** | Clearer FP&A subtitle; tab labels stay; visuals use existing design tokens / chartTheme |
| B5 | **Regression** | No API contract breaks; Phase A endpoints unchanged |

**Out of scope:** new GL, live AI, dark-mode finance theme, replacing tab IA, rebuilding Expenses/Quotes forms.

---

## 4. Visual language (UI/UX + Graphic Designer lock)

- Reuse `KpiMetricCard`, `AppCard` / section Paper, `designTokens`, `chartTheme`
- Charts via existing `@mui/x-charts` wrappers (`AnalyticsDonutChart`, `AnalyticsBarChart`)
- Indian number formatting for money where finance already uses it
- Accent mapping: revenue → success/primary · cost → warning/neutral · margin → success/error · overhead → info
- Mobile: stack KPIs 1–2 cols; charts full width

---

## 5. Pipeline gates

1. **Development** — B1–B4  
2. **CTO approve** — this document  
3. **Senior Tester** — visual smoke + Phase A math still correct  
4. **Testing team** — regression Overview / Annual Plan edit / renewals / budgets / CPR / quotes  
5. **Senior Tester approve**  
6. **QC expert** — ACL unchanged; no double-count; docs match UI  
7. **Restart frontend + backend → UAT**

### ST / Testing matrix

- [ ] Overview shows KPI strip + at least one chart when data present  
- [ ] Plan vs Actual chart renders after plan cells saved  
- [ ] Seed / Clone / Sync renewals still work  
- [ ] Budget cards show utilization bar  
- [ ] Designer without finance module still 403  
- [ ] Phase A PVA API fields unchanged  

---

## 6. Dev map

| Layer | Files |
|-------|--------|
| Direction | `docs/RC5_FINANCE_PLANNING_UX_COCKPIT.md` |
| Overview | `frontend/src/components/finance/FinanceOverviewPanel.tsx` |
| Shared visuals | `frontend/src/components/finance/FinanceCockpitPrimitives.tsx` |
| Annual Plan | `frontend/src/components/finance/AnnualPlanPanel.tsx` |
| Budgets chrome | `frontend/src/pages/FinanceDashboardPage.tsx` |
| Prior math | `docs/RC5_FINANCE_PLANNING_FPA_IMPROVEMENT.md` |

---

## Related

- [RC5_FINANCE_PLANNING_FPA_IMPROVEMENT.md](./RC5_FINANCE_PLANNING_FPA_IMPROVEMENT.md)  
- [RC5_FINANCE_REBUILD.md](./RC5_FINANCE_REBUILD.md)  
