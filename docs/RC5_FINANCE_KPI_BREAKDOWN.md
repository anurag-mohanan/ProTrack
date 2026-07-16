# RC5 — Finance KPI card drill-down (composition)

**Status:** CTO-approved Phase I — Internal UAT  
**Date:** 2026-07-16  
**Stakeholders:** Head of Finance · Head of Engineering · Head of Sales · CEO · President · Creative Head · CTO

---

## 1. Problem

KPI cards on Overview / Overheads show **totals only**. Leadership cannot see **what rolls up** into Operating cost, Overhead OpEx, Pool, or CPR — so they cannot spot **where spend is concentrated** vs **where little is booked**.

---

## 2. Brainstorm lock

| Stakeholder | Verdict |
|-------------|---------|
| **Head of Finance** | Click a KPI → drawer with **ranked contributors** (amount + % of total). Flag **high** (top share) vs **thin / empty** catalogue categories for OpEx. Same formulas as dashboard (no second math). |
| **Creative Head** | Drawer / side panel — modern, scannable bars or ranked list; keep cards clickable with cursor affordance. |
| **Head of Engineering** | `GET /finance/kpi-breakdown?metric=…` — reuse salary/expense factors from dashboard_service. |
| **Head of Sales** | CPR drill-down must show pool ÷ FTE clearly for bid burden. |
| **CEO / President** | One click from cockpit number → drivers. |
| **CTO** | Read-only breakdown; no schema change; Overview + Overheads cards. |

### Metrics (v1)

| Metric key | Surface | Lines |
|------------|---------|-------|
| `operating_cost` | Overview | Salaries (people) + Prosohm OpEx (expenses) in scope |
| `overhead_salaries` | Overheads | Management (+ Corporate if any) salary people |
| `overhead_opex` | Overheads | Mgmt+Corp Prosohm OpEx lines + empty category hints |
| `overhead_pool` | Overheads | Salary block + OpEx block + top drivers |
| `overhead_cpr` | Overheads / Overview | Pool composition + billable N + CPR |
| `team_fees` | Overview | Commercial fee terms by team |
| `revenue_quarter` | Overview | Quote revenue signal + fees (×3 note) |

---

## 3. CTO-approved scope

| # | Change |
|---|--------|
| I1 | `kpi_breakdown_service` + `GET /finance/kpi-breakdown` |
| I2 | Shared `FinanceKpiBreakdownDrawer` |
| I3 | Wire Overview + Overheads `KpiMetricCard` onClick |
| I4 | Tests + dist + restart → UAT |

---

## 4. Pipeline

1. Dev → 2. CTO → 3. ST → 4. Regression → 5. QC → 6. Restart → **UAT**

### ST matrix

- [x] Click Overheads OpEx → ranked expense lines + %  
- [x] Click Pool / CPR → composition matches dashboard totals  
- [x] Click Overview operating cost → salary + OpEx drivers  
- [x] Empty categories show as thin/not spent hints on OpEx  
- [x] Dashboard / overhead tests still green  

**QC:** KPI breakdown API + drawer + tests + dist + restart for UAT.

---

## Related

- [RC5_FINANCE_OVERHEADS_MULTI_ENTRY.md](./RC5_FINANCE_OVERHEADS_MULTI_ENTRY.md)  
- [RC5_FINANCE_PLANNING_UX_COCKPIT.md](./RC5_FINANCE_PLANNING_UX_COCKPIT.md)  
