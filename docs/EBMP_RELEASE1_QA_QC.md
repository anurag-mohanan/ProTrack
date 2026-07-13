# EBMP Release 1 — QA / QC / UAT Gate

## Phase 5 — Senior Developer Implementation Review

Completed Release 1 scope:
- Modular left nav: Engineering Operations, Financial Planning, HR, Reports & Analytics, System Administration, Future placeholders
- Module permissions: `financial_planning`, `human_resources`, `reports_analytics` (+ action matrix helper)
- Financial Planning Access defaults for Admin + Engineering Manager (assignable via user module_access; not hardcoded in feature code)
- Multi-currency with INR base; FX rates; quote import CSV/Excel with revision history
- Cost centres, expenses, employee cost profiles, budgets + approval
- Finance dashboard sections + AI forecast placeholders (no live AI calc)
- Finance KPI strategy registry (project_based / time_materials / retainer)
- HR shell + HR / Office Administrator roles
- Reports & Analytics catalog hub
- Primary team optional (at most one primary)

## Phase 6 — Senior QA

Automated suite: `tests/test_ebmp_finance.py` (10 passed) plus regression (access control, teams, dashboard, production permissions, user teams).

Covered:
- [x] Finance ACL (designer 403, admin/EM allowed)
- [x] Quote CSV import + FX to INR
- [x] Budget create/approve
- [x] Cost centre seed
- [x] KPI strategy registry
- [x] HR shell ACL
- [x] Analytics catalog ACL
- [x] Primary team optional
- [x] Regression on existing ops permissions

Manual residual (staging):
- Excel quote import with openpyxl installed
- EM multi-currency P&L spot-check vs sample USD quote
- Nav visibility for HR role after creating HR user in Admin

## Phase 7 — QC

- UI: Finance / HR / Analytics pages use existing PageHeader + MUI patterns
- Nav: Business Modules section + Future stubs (disabled)
- Security: Finance APIs require `financial_planning` module action; salary costs not on Ops routes
- Audit: quote import, budget approve, FX/cost updates write Activity rows
- Data integrity: quote revisions unique on (quote_id, version, revision); base_amount_inr stored at write

## Phase 8 — Internal UAT

**Status: Ready for Internal User Testing**

Suggested UAT accounts:
1. Admin — full Finance + Analytics + Admin
2. Engineering Manager — Financial Planning + Ops
3. Designer — must NOT see Finance nav or `/finance` APIs
4. New HR user — HR dashboard + analytics only

Do not release to production until Internal UAT sign-off.
