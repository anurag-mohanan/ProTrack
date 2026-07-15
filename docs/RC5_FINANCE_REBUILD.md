# RC5 — Financial Planning Rebuild 1

## HOD lock (Finance + CEO + Head of Engineering)

| Decision | Lock |
|----------|------|
| IA rebuild | Overview, People costs, Expenses & subscriptions, Team commercial, Annual plan, Revenue/quotes, Budgets & reports |
| Paid by | `prosohm` \| `customer` only |
| P&L | Only **Prosohm-paid** opex hits company operating cost; customer-paid = pass-through |
| Renewals | Default notify **7 days** before `next_renewal_date` (in-app) |
| Salaries | Full active-employee roster under `financial_planning` ACL |
| Team models | Reuse Working Models + `team_commercial_terms` fee/period |
| Out of scope | GL, bank feeds, AR/AP, payroll, live AI |

## Click map

| What | Where |
|------|--------|
| Financial Planning | Business Modules → Financial Planning (`/finance`) |
| Overview | Tab **Overview** — company cost, pass-through, renewals strip |
| People costs | Tab **People costs** — all employees, missing-salary filter |
| Expenses | Tab **Expenses & subscriptions** — Paid by, renewal notify |
| Team commercial | Tab **Team commercial** — model + fixed/subscription fee |
| Annual plan / Quotes | Existing tabs unchanged in purpose |

## Pipeline gates

1. **Development** — this rebuild vs HOD lock  
2. **Senior Tester verify** — smoke ACL, paid_by rollup, roster, renewals, team commercial  
3. **Testing team** — debug matrix below  
4. **Senior Tester approve** — blockers cleared  
5. **QC final audit** — salary not on Ops routes; docs match UI  
6. **UAT** — Head of Finance + EM; CEO margin spot-check  

### Senior Tester / Testing matrix

- [x] Automated: expense Paid by Customer → company opex unchanged; pass-through increases (`test_expense_paid_by_customer_is_pass_through`)
- [x] Automated: recurring Prosohm software in ≤7 days → Overview renewals + notify once (`test_expense_renewal_window_and_notify`)
- [x] Automated: People costs roster lists active employees; save updates profile (`test_employee_cost_roster_lists_all_active_users`)
- [x] Automated: Team Subscription fee in Overview (`test_team_commercial_terms_in_dashboard`)
- [x] Automated: Designer 403 on roster / finance dashboard
- [ ] Manual: Annual plan + quote import regression on staging after deploy
- [ ] Manual: UI Paid by / Notify 1 week before / Team commercial form walkthrough

### QC audit

- [x] `paid_by` / renewal fields on Expense + phase22 sync
- [x] Dashboard uses Prosohm-only opex for operating cost
- [x] Module ACL unchanged for designers (tests green)
- [ ] Staging: docs match UI tab labels (Overview, People costs, Expenses & subscriptions, Team commercial)
- [ ] Confirm salary never exposed on Ops routes (spot-check)

## API surface (new / extended)

- `GET /finance/dashboard` — adds `upcoming_renewals`, paid-by cost splits, salary + team fee signals  
- `GET /finance/employee-costs/roster`  
- `POST /finance/employee-costs` (unchanged upsert)  
- `POST /finance/expenses` — `paid_by`, renewal fields, `vendor_name`  
- `POST /finance/renewals/notify` — generate in-app renewal notifications  
- `GET|POST /finance/team-commercial`, `PUT|DELETE /finance/team-commercial/{id}`  
- Budget approve remains `PATCH /finance/budgets/{id}/status` (wired in UI)

## Related

- Prior gate: [EBMP_RELEASE1_QA_QC.md](./EBMP_RELEASE1_QA_QC.md) (Finance UAT was NO-GO; Rebuild 1 is the path to Internal UAT for finance).
