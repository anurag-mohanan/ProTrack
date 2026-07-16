# RC5 — Financial Planning declutter (background vs visual)

**Status:** CTO-approved Phase E — Internal UAT  
**Date:** 2026-07-16  
**Stakeholders:** Head of Finance · Head of Engineering · Head of Sales · CEO · President · CTO

---

## 1. Trigger

Budgets & reports showed a full **Cost centres** card grid (EMP_SALARY, SW_LICENSES, …). Leadership asked: do users need this on the planning surface, or is it reference data that should stay in the **background** for posting/calculations?

---

## 2. Brainstorm lock

| Stakeholder | Verdict |
|-------------|---------|
| **Head of Finance** | Cost centres are a **chart of accounts for expense posting**, not a board decision widget. Keep on Expenses/Overheads forms as dropdowns; **remove the visual catalogue** from Budgets & reports. |
| **Head of Engineering** | Less scroll noise; engineers don’t browse 18 posting codes when reviewing budgets. |
| **Head of Sales** | Same — revenue/quotes matter; posting codes do not. |
| **CEO / President** | Financial Planning should show **decisions and signals** (KPIs, plans, budgets, P&L, overhead CPR) — not master-data galleries. |
| **CTO** | No schema delete. API `GET /finance/cost-centres` remains for forms. UI-only declutter this phase. |

### Visual vs background

| Data | Visual? | Where it stays |
|------|---------|----------------|
| Cost centre **catalogue grid** on Budgets & reports | **No** — remove | Background: Expense / Overheads **dropdown** + API seed |
| Cost centre on expense create/edit | **Yes** (required field) | Expenses & subscriptions, Overheads recurring form |
| FX rates gallery on Budgets | **Advanced only** | Keep collapsed “Show FX rates” (already) |
| AI forecast **placeholder** cards on Budgets | **No** | Already removed in Phase D; placeholders table may remain seeded for future |
| Overview / Annual Plan / Budgets KPIs & charts | **Yes** | Decision surfaces |
| Overheads CPR / pool | **Yes** | Already improved; do not strip |

---

## 3. CTO-approved scope

| # | Change |
|---|--------|
| E1 | Remove Cost centres section + query from `FinanceBudgetsReportsPanel` |
| E2 | Document declutter matrix (this file) |
| E3 | Regression: expense create still lists centres; budgets cockpit + approve/sync still work |
| E4 | Rebuild dist + restart → UAT |

**Out of scope:** Deleting CostCentre table; Admin CRUD for centres; changing Overheads layout beyond leaving it alone.

---

## 4. Pipeline

1. Dev → 2. CTO approve → 3. Senior Tester → 4. Testing regression → 5. ST approve → 6. QC → 7. Restart → **UAT**

### ST matrix

- [x] Budgets & reports has **no** Cost centres card grid  
- [ ] Expenses form still shows Cost centre select with seeded options  
- [ ] Overheads recurring form still has Cost centre select  
- [ ] Budget create / approve / sync-spent / cockpit KPIs still work  

---

## Related

- [RC5_FINANCE_BUDGETS_REPORTS_UX.md](./RC5_FINANCE_BUDGETS_REPORTS_UX.md)  
- [RC5_FINANCE_REBUILD.md](./RC5_FINANCE_REBUILD.md)  
