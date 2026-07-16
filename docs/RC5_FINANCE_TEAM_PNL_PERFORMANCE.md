# RC5 — Team P&L performance + revenue-friendly KPI bands (Phase N)

**Status:** Shipped — UAT ready  
**Date:** 2026-07-16  
**Stakeholders:** Head of Engineering · Head of Sales · CEO · Creative Head · President · CTO

---

## 1. Problem

1. **Revenue drill-down** used spend language (“High spend”) and danger styling on quote/fee contributors — misleading for income lines.
2. **Team comparison** showed OpEx vs fees chart only; leadership could not judge **per-team P&L** (revenue vs cost vs margin) in one view.

---

## 2. Direction lock

| Stakeholder | Verdict |
|-------------|---------|
| **Head of Finance** | Revenue breakdown = **Top driver** / contributor bands, never “high spend”. Team table: revenue, operating cost, gross & net profit, net margin %. |
| **CEO / President** | Sortable team P&L on Overview (all teams) to rank delivery performance. |
| **Head of Sales** | Revenue = quotes + commercial fees; same formulas as dashboard. |
| **Creative Head** | Green/success for revenue bands; red reserved for costs and negative net margin. |
| **Head of Engineering** | Extend `by_team` rollups in `dashboard_service`; `band_mode=revenue` in KPI breakdown. |
| **CTO** | No new tables; read-only signals; tests + dist + restart → UAT |

---

## 3. Shipped scope

| # | Change |
|---|--------|
| N1 | `kpi_breakdown_service` — revenue/fees use `leading` band, not `high` |
| N2 | `FinanceKpiBreakdownDrawer` — metric-aware labels & colours |
| N3 | `TeamFinanceBreakdown` + `_team_rollups` — gross/net profit & margins |
| N4 | `FinanceTeamPnlTable` on Overview (all teams) |
| N5 | Tests + dist + restart → UAT |

### P&L formulas (per team, monthly signal)

- **Revenue** = awarded quote revenue + commercial fees  
- **Gross profit** = revenue − estimated quote cost  
- **Net profit** = gross profit − operating cost (salary + Prosohm OpEx)  
- **Net margin %** = net profit ÷ revenue  

Corporate / Management overhead home excluded from delivery ranking table.

---

## 4. UAT

1. Overview → click **Revenue / quarter** → lines show **Top driver**, not High spend.  
2. Overview (all teams) → **Team P&L performance** table sorts by net margin.  
3. Filter one team → KPI cards still scoped; P&L table hidden (portfolio view).  
4. Regression: finance KPI + dashboard tests green.

---

## Related

- [RC5_FINANCE_KPI_BREAKDOWN.md](./RC5_FINANCE_KPI_BREAKDOWN.md)  
- [RC5_FINANCE_PLANNING_UX_COCKPIT.md](./RC5_FINANCE_PLANNING_UX_COCKPIT.md)
