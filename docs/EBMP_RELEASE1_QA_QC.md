# EBMP Release 1 — QA / QC / UAT Gate

**Last updated:** 2026-07-13  
**QC decision:** Conditional Internal UAT **GO** · Full Finance UAT / Production **NO-GO**

## Phase 5 — Senior Developer Implementation Review

Completed Release 1 scope:
- Modular left nav: Engineering Operations, Financial Planning, HR, Reports & Analytics, System Administration, Future placeholders
- Module permissions: `financial_planning`, `human_resources`, `reports_analytics` (+ action matrix helper)
- Financial Planning Access defaults for Admin + Engineering Manager (assignable via user module_access; not hardcoded in feature code)
- Multi-currency with INR base; FX rates API; quote import CSV/Excel with revision history
- Cost centres, expenses, employee cost profiles, budgets + approval API
- Finance dashboard sections + AI forecast placeholders (no live AI calc)
- Finance KPI strategy registry (project_based / time_materials / retainer)
- HR shell + HR / Office Administrator roles
- Reports & Analytics catalog hub
- Primary team optional (at most one primary)

## Phase 6 — Senior QA (multi-tester)

Automated suite: `tests/test_ebmp_finance.py` plus regression (access control, teams, user teams).

Covered:
- [x] Finance ACL (designer 403, admin/EM allowed)
- [x] Quote CSV import + FX to INR
- [x] Budget create/approve (API)
- [x] Cost centre seed
- [x] KPI strategy registry
- [x] HR shell ACL
- [x] Analytics catalog ACL (admin categories; designer empty)
- [x] Primary team optional
- [x] Regression on existing ops permissions

Manual residual / known gaps:
- Excel quote import with openpyxl installed
- FX rates UI (API only)
- Budget approve button in UI (API only)
- Dashboard cost line items still stubbed at 0 in places
- EM multi-currency P&L spot-check vs sample USD quote
- Nav visibility for HR role after creating HR user in Admin
- Legacy users with frozen `module_access` must Reset to role defaults

## Phase 7 — QC

- UI: Finance / HR / Analytics pages use existing PageHeader + MUI patterns; lazy + Suspense
- Nav: Business Modules section + Future stubs (disabled)
- Security: Finance APIs require `financial_planning` module action; salary costs not on Ops routes
- Audit: quote import, budget approve, FX/cost updates write Activity rows
- Data integrity: quote revisions unique on (quote_id, version, revision); treat dashboard revenue as provisional if multiple revisions exist
- Stale UI recovery: clear `frontend/node_modules/.vite`, run Vite on **5173 only**, hard refresh, re-login, Reset module access if needed

## Phase 8 — Internal UAT

**Status: Conditional Ready for Internal User Testing**

### Where to look (click map)

| What | Where |
|------|--------|
| Financial Planning | Left nav → **Business Modules** → **Financial Planning** (`/finance`) |
| Human Resources | Left nav → **Business Modules** → **Human Resources** (`/hr`) |
| Reports & Analytics | Left nav → **Business Modules** → **Reports & Analytics** (`/analytics`) |
| Grant modules | **System Administration** → **Manage** → **Users** → Create/Edit → **Module Access** (Financial Planning ★, Human Resources ★, Reports & Analytics) |
| Optional primary team | Same Users form → **Teams** → checkbox **Primary (optional)** (not required) |
| New roles | Users → Role dropdown → **HR**, **Office Administrator** |
| Future stubs | Left nav → **Future Modules** (disabled) |

### Suggested UAT accounts

1. Admin — full Finance + Analytics + Admin
2. Engineering Manager — Financial Planning + Ops
3. Designer — must NOT see Finance nav or `/finance` APIs
4. New HR user — HR dashboard + analytics only

### Pre-UAT checklist for each tester browser

1. Open **only** http://localhost:5173 (not another port)
2. Hard refresh (`Ctrl+Shift+R`) or Incognito
3. Log out / log in
4. If Business Modules missing: edit user → Module Access → **Reset to role defaults** → Save

Do not release to production until Internal UAT sign-off and Finance UI gaps are closed or formally waived.
