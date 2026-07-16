# RC5 — Financial Planning FP&A Improvement (industry-aligned)

**Status:** CTO-approved Phase A — implemented for Internal UAT  
**Date:** 2026-07-16  
**Stakeholders:** Head of Finance · Head of Engineering · Head of Sales · CEO · President · CTO

---

## 1. Leadership brainstorm (reference systems)

Benchmarks reviewed: **Anaplan**, **Workday Adaptive Planning**, **Prophix**, **Abacum**, **Mosaic**, **QuickBooks Online**, **Xero**.

| Stakeholder | Priority | Industry pattern borrowed |
|-------------|----------|---------------------------|
| **Head of Finance** | See plan vs live actuals without rebuilding Excel | QBO/Xero budget-vs-actual; Adaptive variance |
| **Head of Sales** | Sales plan vs booked quotes + retainers | Abacum / Mosaic pipeline → plan bridge |
| **Head of Engineering** | Headcount & overhead drivers feed the plan | Mosaic PSA + Abacum driver models |
| **CEO** | One rolling view: YTD actual + remaining plan = FY forecast | Adaptive / Anaplan rolling forecast lite |
| **President** | Scenarios for board (base / stretch / downside) without new FY | Anaplan / Adaptive versions |
| **CTO** | Ship Phase A inside existing `/finance` + ACL; no GL/ERP | Prophix-lite on ProTrack stack |

### What we will **not** build this phase (explicit out of scope)

- Full Anaplan-style connected planning cubes or multi-entity consolidation  
- GL / bank feeds / AR / AP (unchanged from Rebuild 1)  
- Live AI forecasts (placeholders remain)  
- Three-statement BS + cash-flow suite  
- Activity-based multi-driver allocations beyond existing CPR  

---

## 2. CTO-approved Phase A (ship now)

| # | Capability | Where |
|---|------------|--------|
| A1 | **Plan vs Actual + rolling forecast** — YTD plan months vs live run-rate actuals; FY forecast = actual YTD + remaining plan | `GET /finance/plans/{id}/plan-vs-actual` · Annual Plan tab |
| A2 | **Seed from live costs** — Wages & Overhead lines from salary roster + Management/Corporate overhead pool | `POST /finance/plans/{id}/seed-from-live` |
| A3 | **Scenario clone** — Copy a plan under the same FY as Base / Stretch / Downside | `POST /finance/plans/{id}/clone` |
| A4 | **Budget variance clarity** — Show spent, variance %, utilization on Budgets & reports | Budgets tab UI |
| A5 | **Structured Budget vs Actual P&L strip** — Plan YTD / Actual YTD / Variance next to existing P&L signals | Budgets & reports |

### Methodology lock (Finance + CTO)

| Signal | Definition |
|--------|------------|
| FY calendar | Apr–Mar (unchanged) |
| Months elapsed | Inclusive FY months from plan `fy_start_date` through `as_of` (cap 0–12) |
| Plan YTD | Sum of `month_01`…`month_N` for sales / expenses |
| Actual monthly run-rate | Dashboard convention: quote book + monthly team fees (sales); salary + Prosohm opex (expenses) |
| Actual YTD | Monthly run-rate × months elapsed |
| Remaining plan | FY plan − plan YTD |
| Rolling FY forecast | Actual YTD + remaining plan |
| Variance (sales) | Actual YTD − Plan YTD (positive = ahead) |
| Variance (expenses / P&L) | Plan YTD − Actual YTD for cost lines; gain/loss variance = actual gain/loss YTD − plan gain/loss YTD |
| Seed wages | Delivery + all salary-required monthly total × 12, even-split to Q1–Q4 on `wages` line |
| Seed overhead | Management + Corporate overhead pool monthly × 12, even-split on `overhead` line |
| Scenarios | Multiple plans may share `fiscal_year_label`; uniqueness is **name + FY label** |

Annual Plan “Overhead” grid line remains a **planning ledger** — seed copies live pool into the ledger; CPR on Overheads tab stays independent.

---

## 3. Pipeline gates

1. **Development** — implement A1–A5 vs this lock  
2. **CTO approve** — scope & methodology above (this document)  
3. **Senior Tester** — detailed study of variance math, seed side-effects, clone isolation  
4. **Testing team** — regression: existing Annual Plan edit, renewals sync, budgets create/approve, Overview/CPR, quotes  
5. **Senior Tester approve** — blockers cleared  
6. **QC expert** — final audit (ACL, no double-count CPR into net profit, docs match UI)  
7. **Restart backend + frontend** → **UAT (UAV)**

### Senior Tester / Testing matrix

- [ ] Create plan → Plan vs Actual returns months_elapsed and non-null YTD fields  
- [ ] Edit Q1 sales → plan YTD and rolling forecast update  
- [ ] Seed from live → `wages` and `overhead` quarters change; other lines unchanged  
- [ ] Clone Stretch → second plan same FY, independent cell edits  
- [ ] Sync renewals still works on both base and clone  
- [ ] Budget card shows variance % when spent & allocated present  
- [ ] Designer without `financial_planning` still 403 on new endpoints  
- [ ] Regression: Overview CPR, leaving_date proration, quote CRUD  

### QC audit

- [ ] No GL/ERP scope creep  
- [ ] Seed does not overwrite Sales customer lines  
- [ ] Plan vs Actual uses same monthly run-rate basis as Overview (documented)  
- [ ] Scenario clone does not delete source plan  

---

## 4. Dev map

| Layer | Files |
|-------|--------|
| Direction | `docs/RC5_FINANCE_PLANNING_FPA_IMPROVEMENT.md` |
| Service | `app/services/finance/plan_vs_actual_service.py`, `annual_plan_service.py` (clone + seed) |
| API | `app/api/v1/finance.py` |
| Schemas | `app/schemas/finance.py` |
| UI | `AnnualPlanPanel.tsx`, `FinanceDashboardPage.tsx` (Budgets tab) |
| Tests | `tests/test_finance_plan_vs_actual.py` |

---

## 5. Later phases (backlog — not this UAT)

| Phase | Theme | Inspiration |
|-------|--------|-------------|
| B | Driver worksheet (headcount × rate → wages; utilization × fee → sales) | Abacum, Mosaic |
| C | Workflow lock / board pack export PDF | Prophix, Adaptive |
| D | Monthly actuals posting from timesheets/invoices | QBO, Xero |
| E | Full scenario compare grid side-by-side | Anaplan |

---

## Related

- [RC5_FINANCE_REBUILD.md](./RC5_FINANCE_REBUILD.md)  
- [FINANCE_ANNUAL_PLAN.md](./FINANCE_ANNUAL_PLAN.md)  
- [RC5_FINANCE_OVERHEADS_PNL.md](./RC5_FINANCE_OVERHEADS_PNL.md)  
- [RC5_FINANCE_MANAGEMENT_TEAM_LAST_DAY.md](./RC5_FINANCE_MANAGEMENT_TEAM_LAST_DAY.md)  
