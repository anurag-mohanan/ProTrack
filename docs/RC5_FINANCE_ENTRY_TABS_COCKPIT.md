# RC5 — Finance entry tabs cockpit polish (People · Expenses · Commercial · Quotes)

**Status:** CTO-approved Phase J — shipped to UAT  
**Date:** 2026-07-16  
**Stakeholders:** Head of Engineering · Head of Sales · CEO · President · Creative Head · CTO  
**(Finance HOD alignment):** Same visual language as Overview / Overheads / Budgets

---

## 1. Problem

People costs, Expenses & subscriptions, Team commercial, and Revenue/quotes already have **heroes** and full CRUD, but still look like **flat forms + outlined card lists**. Overview / Overheads use KPI strips + `FinanceSection` + `financeMoney`. Phase C C4 called for creative wraps; Phase J ships them.

---

## 2. Brainstorm lock

| Stakeholder | Verdict |
|-------------|---------|
| **Creative Head** | KPI strip + sectioned form/list on all four tabs; Indian money formatting; keep density usable for data entry. |
| **Head of Engineering** | UI-only — no API contract changes; preserve create/edit/delete/import/roster save. |
| **Head of Sales** | Quotes & Team commercial must stay fast for booking revenue and retainer fees. |
| **CEO / President** | Entry tabs should feel like the same product as the cockpit Overview. |
| **CTO** | No schema; regression on expense/quote/commercial/roster tests. |

### Visual targets

| Tab | KPIs (examples) | Sections |
|-----|-----------------|----------|
| People costs | Headcount, missing salaries, monthly salary Σ, exempt | Filters · Roster |
| Expenses | Line count, Prosohm Σ, customer-paid Σ, renewals | Form · List |
| Team commercial | Terms count, fee signal Σ, billable Σ | Form · Active terms |
| Quotes | Quote count, booked revenue Σ, linked, missing date | Manual · Upload · List |

---

## 3. CTO-approved scope

| # | Change |
|---|--------|
| J1 | Polish `FinancePeopleCostsPanel` |
| J2 | Polish `FinanceExpensesPanel` |
| J3 | Polish `FinanceTeamCommercialPanel` |
| J4 | Polish `FinanceQuotesPanel` |
| J5 | Regression + dist + restart → UAT |

**Out of scope:** Changing paid-by rules, quote schema, commercial fee math.

---

## 4. Pipeline

1. Dev → 2. CTO → 3. ST → 4. Regression → 5. QC → 6. Restart → **UAT**

### Shipped (2026-07-16)

| Gate | Result |
|------|--------|
| J1–J4 UI | People · Expenses · Team commercial · Quotes — KPI strips + `FinanceSection` + list rows |
| Regression | `test_ebmp_finance` + `test_finance_plan_sales_from_quotes` — **37 passed** |
| Dist | `frontend` `npm run build` OK |
| Restart | API `:8000` · Vite `:5173` |

---

## Related

- [RC5_FINANCE_ANNUAL_PLAN_AI_UX.md](./RC5_FINANCE_ANNUAL_PLAN_AI_UX.md) (C4)  
- [RC5_FINANCE_COMMERCIAL_UX_EXPENSE_CRUD.md](./RC5_FINANCE_COMMERCIAL_UX_EXPENSE_CRUD.md)  
- [RC5_FINANCE_PLANNING_UX_COCKPIT.md](./RC5_FINANCE_PLANNING_UX_COCKPIT.md)  
