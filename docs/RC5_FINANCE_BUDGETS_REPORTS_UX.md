# RC5 — Budgets & Reports Cockpit (Phase D)

**Status:** CTO-approved Phase D — Internal UAT  
**Date:** 2026-07-16  
**Stakeholders:** CEO · President · CFO · Creative Head · CTO

---

## 1. Leadership brainstorm

| Stakeholder | Pain | Direction |
|-------------|------|-----------|
| **CFO** | Budgets tab is a create form + flat cards; no portfolio view, weak P&L, no risk radar | Budget **cockpit**: KPI strip, alloc vs forecast by quarter, at-risk list, sync spent from live OpEx |
| **CEO** | Cannot brief board on budget health in one glance | Approved vs draft counts, utilization %, variance callouts |
| **President** | Reports feel bolted-on (placeholders + raw P&L labels) | Statement-style P&L + chart; retire “future AI placeholder” clutter from primary path |
| **Creative Head** | Still denser/less composed than Overview / Annual Plan | Dedicated panel, hero + sections, KPI cards, side insights — **do not restyle Overheads** |
| **CTO** | Keep ACL + renewal forecast math; additive APIs only | `GET /finance/budgets/cockpit` + opt-in `POST …/sync-spent`; no GL |

### Inspiration

| Platform | Borrow |
|----------|--------|
| QBO / Xero | Budget remaining / utilization meters, P&L clarity |
| Adaptive / Abacum | Portfolio KPI strip + variance |
| Prophix | Sectioned report cards |
| Mosaic | Services cost signals next to budget |

---

## 2. CTO-approved scope

| # | Deliverable |
|---|-------------|
| D1 | `GET /finance/budgets/cockpit` — totals, quarterly rollups, risk insights, budget rows enrichment |
| D2 | `POST /finance/budgets/{id}/sync-spent` — set spent from live YTD operating run-rate (opt-in) |
| D3 | `FinanceBudgetsReportsPanel` — KPI strip, filters, create dialog, Q chart, cards, P&L statement, insights rail, FX collapsed |
| D4 | Slim `FinanceDashboardPage` tab 7 to host the new panel |
| D5 | Tests + dist rebuild + restart → UAT |

**Out of scope:** Overheads restyle, multi-level approval workflows, ERP postings, external LLM.

### Methodology lock

- Forecast quarters still include renewals on create (unchanged).  
- Variance on model = allocated − forecast (existing).  
- Utilization = spent / allocated. **At risk** = utilization ≥ 85% or forecast > allocated.  
- Sync spent = `monthly_operating_cost × FY months elapsed` (capped at allocated); team filter uses team OpEx when scoped.

---

## 3. Pipeline

1. Dev → 2. CTO approve (this doc) → 3. Senior Tester → 4. Testing regression → 5. ST approve → 6. QC → 7. Restart → **UAT**

### ST matrix

- [ ] Cockpit returns totals matching listed budgets  
- [ ] Sync spent updates spent/remaining on a draft budget  
- [ ] Create + approve still work  
- [ ] Overheads tab unchanged  
- [ ] Overview / Annual Plan AI Assist regression  

---

## 4. Dev map

| Layer | Path |
|-------|------|
| Direction | `docs/RC5_FINANCE_BUDGETS_REPORTS_UX.md` |
| Service | `app/services/finance/budget_cockpit_service.py` |
| API | `app/api/v1/finance.py` |
| Schemas | `app/schemas/finance.py` |
| UI | `frontend/src/components/finance/FinanceBudgetsReportsPanel.tsx` |
| Tests | `tests/test_finance_budgets_cockpit.py` |

---

## Related

- [RC5_FINANCE_PLANNING_UX_COCKPIT.md](./RC5_FINANCE_PLANNING_UX_COCKPIT.md)  
- [RC5_FINANCE_ANNUAL_PLAN_AI_UX.md](./RC5_FINANCE_ANNUAL_PLAN_AI_UX.md)  
- [RC5_FINANCE_REBUILD.md](./RC5_FINANCE_REBUILD.md)  
