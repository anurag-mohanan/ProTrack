# Finance Module Overhaul — Implementation Report

Date: 2026-09-03

## 1. Root causes

- **Invoiced / Not Invoiced chips** filtered only in the browser after `GET /finance/quotes?team_id=…`, with wrong semantics: “Invoiced” included any partial cash (`is_invoiced || total_invoiced > 0`).
- **Deep links** such as `/finance/budgets` and `/finance/reports` never selected a tab (tab state was local `useState(0)` only).
- **Scenario Save** was disabled until a saved scenario was loaded, which looked broken.
- **Scenario Planning** lacked a transparent capacity/revenue/cost what-if layer with formula explanations.
- User-facing label remained **Financial Planning** while the product intent is a broader **Finance** command center.
- Two expense dashboard tests expected full yearly amounts in monthly OpEx signals (should be amount ÷ 12).

## 2. Finance renaming

User-facing copy updated to **Finance** (nav, page title, module label, admin help, delete dialogs, loading text, API 403 detail).  
Internal key **`financial_planning`**, route **`/finance`**, and API prefix **`/finance`** unchanged.

## 3. Filter fixes

- New [`quote_filter_service.py`](../app/services/finance/quote_filter_service.py): canonical `none` / `partial` / `full`.
- `GET /finance/quotes` accepts `list_filter`, `invoice_status`, `payment_status`, `q`, `project_linked`, `missing_quoted_date`, `payment_follow_up_due`.
- Chip **Not invoiced** = `none`; **Partially invoiced** = `partial`; **Invoiced** = `full` only.
- Frontend passes filters to the API; KPI strip still loads the unfiltered team set for counts.
- Legacy `is_invoiced` without cash lines treated as `full` for list consistency.

## 4. Button / link audit

- Tab deep-links via `?tab=` and path aliases (`/finance/budgets`, `/finance/scenarios`, …).
- Scenario actions: **Update saved** / **Save as new** (Update disabled with tooltip until a scenario is loaded).
- ERP export labeled **CSV stub (not live sync)**.
- Project profitability report wired in Reports & budgets with links to `/projects/{id}`.
- Awarded quotes table: **Open project** link when `project_id` is set.

## 5. Financial calculations

- Dashboard **`quote_billing`**: awarded value, remaining to invoice, total invoiced, outstanding, paid, status counts (from cash ledger).
- Overview KPI tooltips explain estimated vs actual / gross profit / margin.
- Existing P&L / snapshots unchanged as source of truth for project profitability.

## 6. Scenario Planning

- Transparent what-if engine: [`financeWhatIf.ts`](../frontend/src/utils/financeWhatIf.ts) + [`what_if_calculator.py`](../app/services/finance/what_if_calculator.py).
- UI: [`FinanceWhatIfPanel.tsx`](../frontend/src/components/finance/FinanceWhatIfPanel.tsx) — inputs with explanations, formula expanders, current vs scenario, base/best/worst, warnings, executive summary.
- Persisted on scenario draft as `what_if` (schema_version 3) alongside existing expansion/overhead model.

## 7. Important files

Frontend: `FinanceDashboardPage.tsx`, `FinanceQuotesPanel.tsx`, `FinanceQuotesTable.tsx`, `FinanceOverviewPanel.tsx`, `FinanceScenariosPanel.tsx`, `FinanceWhatIfPanel.tsx`, `FinanceBudgetsReportsPanel.tsx`, `utils/financeWhatIf.ts`, `utils/financeScenarios.ts`, `config/accessControl.ts`, `utils/permissions.ts`

Backend: `app/api/v1/finance.py`, `quote_filter_service.py`, `what_if_calculator.py`, `dashboard_service.py`, `schemas/finance.py`

Tests: `tests/test_finance_quote_filters.py`, `tests/test_finance_what_if.py`, expense monthly-run-rate assertions in `tests/test_ebmp_finance.py`

## 8. Database / API changes

- No migrations.
- Extended `GET /finance/quotes` query params.
- Dashboard JSON gains `quote_billing`.

## 9. Testing

- `pytest tests/test_finance_quote_filters.py tests/test_finance_what_if.py` + fixed ebmp expense tests — pass
- Frontend `npm run build` — pass
- Manual checklist: Invoiced/Not Invoiced/Partial chips; Clear; `/finance?tab=budgets`; scenario what-if + How calculated; open linked project

## 10. Remaining issues

- Quote list still loads all active quotes then filters in Python (correct semantics; SQL push-down can follow if volume grows).
- Permission key remains `financial_planning` (intentional).
- ERP export remains a stub.
- Full nine-page IA rewrite not done — tabs + deep links used instead.
- Best/Worst presets scale the user’s base inputs (not hardcoded 10/14/7 business defaults).
