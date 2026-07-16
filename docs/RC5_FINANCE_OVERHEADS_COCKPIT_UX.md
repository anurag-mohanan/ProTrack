# RC5 — Overheads cockpit UX (defaults + modern UI)

**Status:** CTO-approved Phase G — Internal UAT  
**Date:** 2026-07-16  
**Stakeholders:** Head of Finance · Head of Engineering · Head of Sales · CEO · President · Creative Head · CTO

---

## 1. Problem

Overheads tab is a **basic** title + four outlined metric cards + flat create form + read-only list. Users see an empty FY OpEx list until they invent line names — while seeded cost centres already define the HQ catalogue (Rent, Utilities, …). Overview / Budgets / Annual Plan already use the cockpit language (`FinanceHeroBanner`, `KpiMetricCard`, sections).

---

## 2. Brainstorm lock

| Stakeholder | Verdict |
|-------------|---------|
| **Head of Finance** | Show **default HQ overhead placeholders** (Rent, Utilities, Insurance, Office, Internet, Maintenance, Cloud, Software licenses, Training, Travel) so amounts can be entered without inventing names. Pool/CPR math unchanged (Management + Corporate Prosohm OpEx + salaries ÷ delivery billable FTE). |
| **Creative Head** | Match Phase B cockpit: hero, KPI strip (`info` accent), sectioned cards, Indian money formatting — not a bare form. |
| **Head of Engineering** | Same expense APIs (`POST/PATCH/DELETE /expenses`); placeholders map to cost-centre codes; no schema invent. |
| **Head of Sales** | Clear CPR signal for burden in bids; no sales-pipeline clutter on this tab. |
| **CEO / President** | One glance: pool mix (salaries vs OpEx) + editable default lines + live CPR. |
| **CTO** | UI-first Phase G; keep calculation services; edit/delete on this tab; custom recurring form remains as advanced escape hatch. |

### Visual vs background

| Surface | Visual? |
|---------|---------|
| KPI strip (mgmt salary, OpEx, pool, CPR) | Yes — `KpiMetricCard` |
| Default overhead placeholder grid | Yes — enter amounts |
| Pool mix chart (salary vs OpEx) | Yes |
| Cost-centre master list | Background (dropdown only) |
| Custom recurring form | Advanced / secondary |

---

## 3. CTO-approved scope

| # | Change |
|---|--------|
| G1 | Rewrite `FinanceOverheadsPanel` to cockpit chrome |
| G2 | Default placeholders by cost-centre code; create/update/delete via existing expense APIs |
| G3 | Donut/bar pool mix; chips for FY + FTE |
| G4 | Regression: dashboard overhead fields + P&L CPR + expense create still work |
| G5 | Rebuild dist + restart → UAT |

**Out of scope:** Changing pool formula; auto-seed expense rows into DB on startup; CapEx in monthly pool.

---

## 4. Pipeline

1. Dev → 2. CTO → 3. Senior Tester → 4. Regression → 5. ST → 6. QC → 7. Restart → **UAT**

### ST matrix

- [x] Hero + KPI strip + placeholder grid render  
- [x] Enter amount on empty placeholder → creates Corporate/Management Prosohm OpEx  
- [x] Edit amount on existing → PATCH; Delete → soft-delete; CPR refreshes  
- [x] Custom recurring still works (advanced collapse)  
- [x] Dashboard overhead + P&L CPR tests green  

**QC:** Direction doc + cockpit UI + tests + `frontend/dist` rebuild + API/Vite restart for UAT.

---

## Related

- [RC5_FINANCE_OVERHEADS_PNL.md](./RC5_FINANCE_OVERHEADS_PNL.md)  
- [RC5_FINANCE_MANAGEMENT_TEAM_LAST_DAY.md](./RC5_FINANCE_MANAGEMENT_TEAM_LAST_DAY.md)  
- [RC5_FINANCE_PLANNING_UX_COCKPIT.md](./RC5_FINANCE_PLANNING_UX_COCKPIT.md)  
