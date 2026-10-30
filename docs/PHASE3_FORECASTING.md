# ProTrack — Phase 3: Financial and Capacity Forecasting

Status: **first increment only. Phase 3 is not complete.** See §10 for what is deferred.

Evidence base: `docs/PROTRACK_PHASE_VERIFICATION.md` (Phase 0–2 verification), code inspection of
the services named below, and read-only counts on a disposable copy of `protrack.db`
(`%TEMP%\phase3_inspect.db`, copied 2026-10-29).

---

## 1. Prerequisite assessment and release gate

### 1.1 Data available in the development database (copy)

| Item | Count | Consequence |
|---|---|---|
| Projects / open projects | 24 / 2 | Very small population |
| Completed projects with an approved estimate and recorded actuals | **0** | No effort history, so no backtest is possible |
| Project stage estimates / milestones with planned hours | 0 / 0 | Neither open project has an approved estimate (quoted hours only) |
| Timesheet entries | 2 | Actuals effectively absent |
| Baseline or estimate revisions | 0 | Original commitment = current due date |
| Quotes, invoice lines, payment lines, payment milestones | **0, 0, 0, 0** | Finance forecasts can only be checked with test data |
| Capacity-planning users (active, employee, `kpi_capacity_planning`) | 9 | Supply side has real inputs |
| Shift masters / shift assignments | 5 (3 active) / **0** | Everyone falls back to `working_hours_per_day` (8 h, Mon–Fri) |
| Holidays | **0** | No holiday deduction until the calendar is maintained |
| Skills / user skills | 6 / **0** | No verified skills |
| Users with `on_leave`/`unavailable` status | 0 | — |

### 1.2 Prerequisites

| # | Prerequisite | Status | Evidence | Effect on Phase 3 |
|---|---|---|---|---|
| 1 | Actual hours reconcile with timesheets | **Met in code** | Phase 1 §7: 0 mismatches over 24 projects; one rule in `engineering_metrics_service`. Draft/rejected hours still count (open decision) | Effort forecasts reuse the shared actual and show the status split |
| 2 | Approved estimates distinguishable from quotes and revisions | **Met** | `estimate_source` ∈ {stage_estimates, milestone_hours} = approved; `quoted_hours` is never approved | Forecasts only start from an approved estimate |
| 3 | Stage metrics reliable | **Partial** | Model and tests pass (Phase 1 §4), but the weekly grid and imports never set `milestone_id` (finding 2.2), so stage actuals are incomplete | **Stage forecasting deferred** |
| 4 | Baselines preserved | **Met in model, no data** | `delivery_variance_service` verified-original rule; 0 revisions in data | Original commitment and current target are shown side by side |
| 5 | Resource availability and demand from authoritative data | **Supply: partial. Demand: not met** | Supply: shifts (`rp_shift_assignments`), working days, `working_hours_per_day`, holidays, `joining_date`/`leaving_date`, `max_allocation_percent`, employee-only user clause. **No planned-leave model** (only an undated current `availability_status` flag; timesheets record leave after the fact). **No allocation model**: the resource grid's demand is heuristic (16 h / 40 h floors, fixed 100/40/15 % role shares, even spreading to the due date) | Capacity supply forecast: **preliminary**. Phased demand, capacity gaps and skill demand: **deferred** |
| 6 | Finance records have reliable project and customer links | **Partial** | `quotes.customer_id` is NOT NULL; `quotes.project_id` is nullable and several quotes can point at one project (Phase 1 finding 1.2). **No quote award status exists.** Invoice/payment lines are the authoritative ledger (`quote_cash_ledger_service`) | Collections from issued invoices: implementable. Billing forecast only for quotes linked to a live project, with the award assumption stated |
| 7 | Control Tower alerts use validated calculations | **Met** | Phase 2 §9: 16 tests, reuses shared metrics and delivery services | Forecast-based alerts remain deferred (they need a validated completion forecast) |
| 8 | Backend authorization enforced | **Met with exceptions** | Reports gate + `project_visibility_clause`/`resolve_report_scope`; Finance gate `MODULE_FINANCIAL_PLANNING` view; Resource Planning module or `view_resource_planning`. High defects S1–S3 open but outside the forecast data path | New endpoints reuse these gates |

Additional findings from inspection:

- **F3.1** `summarize_quote_payment_schedule` (Finance) writes while reading: it flips a payment
  milestone to `INVOICED` when it finds a matching invoice line. A forecast must not call it.
  The read-only matching rule was extracted into a shared helper (`matched_invoice_line`) so
  both paths use one definition; the Finance function's behaviour is unchanged.
- **F3.2** `build_receivables_aging` still crashes on quotes linked to a project
  (`project.name`, B0.4). The forecast does not call it; it reuses the lower-level ledger
  functions (`calculate_awarded_quote_financial_status`, `allocate_invoice_outstanding`,
  `payment_timing_status`), which is the same FIFO rule.
- **F3.3** The existing stage-plan forecast (`scheduling_service.recalculate_forecast`) is
  labelled *provisional*: it converts hours to days at a fixed effort rate per milestone and
  ignores other work and capacity. That is the "hours ÷ 8" pattern the brief forbids, so it is
  shown only as the existing provisional schedule and never as a completion forecast.
- **F3.4** The Treasury cash-flow forecast projects future collections from the FY average
  (`cash_flow_forecast_service`). It is a company cash view, not an invoice-level forecast; it
  is left unchanged and the new collection forecast does not feed it.
- **F3.5** Amounts on quotes are in the quote currency (`quotes.currency_code`). Finance
  forecast totals are therefore grouped by currency; nothing is converted.

### 1.3 Gate decision

| Capability | Decision | Reason |
|---|---|---|
| Remaining-effort forecast | **Implement** with an explicit status | Approved estimate + shared actuals exist in the model. History-adjusted values only when enough comparable completed projects exist; otherwise *unavailable*, with the approved plan shown separately |
| Effort backtest | **Implement** | Time-ordered, no leakage; reports *not possible* when the sample is too small (it is, in dev data) |
| Completion-date forecast | **Defer** | Needs phased demand, allocation and leave; the only scheduler is provisional (F3.3) |
| Stage forecast | **Defer** | Prerequisite 3 partial |
| Capacity supply (gross, holidays, employment window, status, allocatable) | **Implement as preliminary** | Authoritative supply inputs exist; planned leave and non-project commitments are unknown |
| Phased demand, capacity gaps, skill demand | **Defer** | No allocation model, no verified skills, no required-skill field on projects |
| Collections forecast (issued invoices by contractual due date) | **Implement** | Ledger and due dates are authoritative; no payment-behaviour model is invented |
| Billing forecast (remaining to invoice, billing milestones) | **Implement with limits** | Dated only when a billing milestone's trigger maps to a recorded date; award status assumed from the project link |
| Scenarios | **Defer** | The brief requires working forecasts first; the delivery and capacity impacts a scenario would show are themselves deferred |
| Persisted forecasts | **Not needed** | All forecasts are on-demand and reproducible from `as_of` + method version; no migration |

---

## 2. Implemented capabilities

| Capability | Status in output | Where |
|---|---|---|
| Remaining effort per open project (estimate at completion, remaining) | available / preliminary / unavailable per project | `app/services/forecasting/effort.py` |
| Effort history factor and time-ordered backtest | factor status + backtest *evaluated* or *not possible* | same |
| Approved plan, actuals, quoted hours, original commitment, current target and the existing provisional schedule, side by side | plan / actual / commitment labels | same |
| Capacity supply per person, team and period (weekly or monthly, 1–26 periods) | **preliminary** | `app/services/forecasting/capacity.py` |
| Known demand: approved remaining hours per designer, **unphased** | approved plan | same |
| Collections: outstanding issued invoices by contractual due date; overdue and undated shown separately | available | `app/services/forecasting/finance.py` |
| Billing: remaining to invoice split into ready / dated by project target / undated / excluded | available, with per-item date status | same |
| Central catalogue of forecast definitions, method versions and deferred items | — | `app/services/forecasting/definitions.py` |
| Reports → **Forecasts** tab | — | `frontend/src/components/reports/ForecastsPanel.tsx` |

## 3. Deferred capabilities

| Capability | Why | What would unblock it |
|---|---|---|
| Completion-date forecast | No allocation model, no planned leave, only a fixed-rate provisional scheduler (F3.3). Any date would be the forbidden "hours ÷ rate added to today" | An allocation (assignment-percentage) model and a leave calendar, then a capacity-constrained schedule |
| Stage forecast | Stage actuals incomplete (weekly grid and imports do not set `milestone_id`) | Attribute hours to milestones in the weekly grid and imports |
| Capacity gaps by period, team and skill | Demand cannot be phased; skills unverified | Allocation model; verified `user_skills`; a required-skill field on projects |
| Scenarios | Their delivery, capacity and workload impacts depend on the deferred forecasts | The two items above |
| Forecast-based Control Tower rules (`estimate_overrun_forecast`, `delivery_forecast_risk`, `resource_bottleneck`) | Same prerequisites; effort forecast also needs history (0 samples today) | ≥ 5 completed projects with approved estimates and actuals, and a passing backtest |
| Collections on not-yet-issued invoices | Would chain two uncertain dates (invoice date, then payment) | A validated completion forecast |

## 4. Sources and methods

**Remaining effort (`effort-1`).** Inputs come only from `build_engineering_metrics_batch` (the
shared engineering metrics). A project is forecast only if its estimate source is approved
(stage estimates or milestone planned hours). History = completed projects with
`completed_at` ≤ `as_of`, an approved original estimate > 0 and recorded actual hours > 0.
Factor = median(actual ÷ original approved estimate). Estimate at completion (EAC) = original
approved estimate × factor; remaining = EAC − actual to date. Status: *unavailable* with 0
samples, *preliminary* with 1–4, *available* with ≥ 5. When actual ≥ EAC the forecast is
*unavailable* (history cannot tell how much is left). The original estimate is used on both
sides so that late estimate revisions do not leak the outcome into the factor. The factor is
org-wide so the number does not depend on who asks; only sample projects the caller can see are
listed.

**Backtest.** Projects ordered by completion date; each one is predicted with a factor fitted
only on projects completed strictly earlier (at least 5). Reported: evaluated count, mean
absolute error (hours and %), bias, and the same errors for the naive "plan as is" baseline.

**Capacity supply (`capacity-1`).** People = `capacity_planning_users` (active, not archived or
deleted, employee user type, capacity-planning flag, capacity roles only). Per person-day on
the person's working days: shift hours from `shift_hours_for_range` (paid hours of the resolved
shift), else `working_hours_per_day`. That scheduled time is then classified, in this order:
outside the employment window (`joining_date`/`leaving_date`), holiday (`load_holiday_dates`),
on-leave/unavailable status, else available. Allocatable = available × `max_allocation_percent`.
The daily rule is the Resource Planning grid's `_daily_capacity` plus the employment window; a
test asserts both give the same hours for a person without an employment window. Team scope
uses `resolve_team_scope`, as the grid does.

**Collections and billing (`finance-1`).** Per active quote:
`calculate_awarded_quote_financial_status` (awarded value from the current revision, invoice
lines, payment lines, closed balances), `allocate_invoice_outstanding` (FIFO) and the invoice
line's own `due_date`. Billing milestones come from `quote_payment_milestones`; a milestone
counts as invoiced when `matched_invoice_line` finds its invoice or its status is
INVOICED/WAIVED. Remaining to invoice is split into milestone items plus an unscheduled
remainder. If the open milestones add up to more than the remaining value, the schedule is not
used (one undated item and a warning), so nothing is counted twice.

## 5. Assumptions and limitations

- Actual hours include draft, submitted and rejected hours (the project rule; open decision).
  Each project shows the split.
- The effort factor is not segmented by customer, working model or complexity.
- Milestone planned hours are not revision-tracked; their original and current values coincide.
- Planned leave and non-project commitments are not recorded, so capacity is overstated by them.
  An on-leave/unavailable status has no end date and is applied to the whole horizon.
- Quotes have no award status: a quote linked to a live project is treated as awarded; others
  are listed as excluded from billing (their issued invoices are still in collections).
- Billing dates use the project's current target date, a commitment rather than a forecast, and
  only for completion-triggered milestones.
- Collections assume the contractual due date; overdue and undated balances get no expected
  date. Payment history is not used.
- A projected invoice is not revenue. P&L turnover remains invoice-date based in Finance.
- No confidence interval or probability is produced anywhere (`confidence` is always null).
- The Finance forecast queries each quote's ledger separately (as the Finance pages do);
  with many hundreds of active quotes it will slow down.

## 6. UI and API changes

API (all read-only, `GET`, authenticated):

| Endpoint | Access rule | Scope |
|---|---|---|
| `/api/v1/forecasts` | any signed-in user | returns definitions and which forecasts the caller may open |
| `/api/v1/forecasts/engineering?as_of=` | Reports access (`can_view_reports`) | `project_visibility_clause` + `resolve_report_scope` |
| `/api/v1/forecasts/capacity?start=&granularity=&periods=&team_id=&as_of=` | Resource Planning roles, module or `view_resource_planning` | `resolve_team_scope`; 403 for a team outside scope |
| `/api/v1/forecasts/finance?as_of=&granularity=&periods=&team_id=&customer_id=` | Finance module view action (same as `/finance/*`) | team / customer filters |

UI: Reports → **Forecasts** tab (`?tab=forecasts`), after Control Tower. A selector shows only
the forecasts the user may open, so Finance data is not requested without Finance access.
Each forecast shows a status chip, method version, as-of and generation time, and an
expandable list of sources, assumptions and limitations. Column headers carry
Actual / Plan / Forecast / Commitment chips. Unavailable forecasts show their reason and no
number. Deferred capabilities are listed with their reasons. Weekly/monthly horizon controls
follow the Resource Planning convention; dates use the app's `dd-mm-yyyy` formatter.

Small shared change: `matched_invoice_line()` extracted in
`app/services/finance/payment_schedule_service.py`; `summarize_quote_payment_schedule`
calls it and behaves exactly as before.

## 7. Database changes and preservation

**None.** No table, column, index or migration was added; nothing is persisted. Forecasts are
reproducible by calling the same endpoint with the same `as_of` and method version.
`protrack.db` was never opened by the application: inspection and smoke runs used the copy
`%TEMP%\phase3_inspect.db`. `protrack.db` last-write time is unchanged at
`2026-10-29T12:20:48`. Tests use the disposable test database.

## 8. Tests (executed 2026-10-29)

| Check | Result |
|---|---|
| Full backend suite (`pytest`, disposable `DATABASE_URL`) | **12 failed, 1297 passed, 1 skipped** in 42 min 32 s. The 12 failures are exactly the 12 pre-existing ones listed in `PHASE0_QUOTE_TO_DELIVERY_AUDIT.md` §3.1; none involve forecasting |
| `tests/test_forecasting.py` (20 tests, within the run above) | 20 passed |
| Frontend `npx tsc -b` | exit 0 |
| Frontend `npm run build` | exit 0 |
| ESLint on the new frontend files | clean (the existing `ReportsPage.tsx` `set-state-in-effect` error is pre-existing) |
| Ruff (`F`, `I`, `E9`) on the new backend files | clean |
| Browser check | not done (skipped at the user's request; tests and build only) |

What `tests/test_forecasting.py` covers, against the Phase 3 acceptance list:

- **Actual / plan / forecast kept apart:** quoted-only project is *unavailable*; the approved remaining plan
  is reported separately from the forecast remaining (60 h vs 80 h).
- **No invented numbers:** 0 history → *unavailable*; 2 samples → *preliminary*; actual past
  EAC → *unavailable* with no EAC; `confidence` is null.
- **No leakage:** history completed after `as_of` is excluded; the backtest predicts each project
  only from earlier completions and reports MAE 33.33 h / bias −33.33 h on a hand-computed set;
  too few samples → *not possible* with the reason.
- **Capacity:** each component checked (weekend, shift hours, holiday, leaver, on-leave
  status, allocation %); virtual users are excluded; totals reconcile
  (scheduled = holiday + outside employment + status + available) and match the Resource Planning
  grid's `_daily_capacity`; demand is unphased approved plan (70 h).
- **Collections:** FIFO outstanding (530) = scheduled (180) + overdue (300) + no due date (50);
  invoice statuses are not modified.
- **Billing:** remaining = ready (200) + dated by target (300) + undated (100) + unscheduled (50);
  milestones exceeding remaining are flagged and not counted twice; unlinked or cancelled-project
  quotes are excluded and listed; currencies kept separate.
- **Read-only:** no pending session changes after the engineering forecast; Finance forecast
  leaves milestone statuses unchanged (all three services were also checked for pending changes
  in the smoke run on the database copy).
- **Performance:** query count does not grow with the number of projects/people.
- **Authorization:** designer without access → 403 on capacity and Finance; no token → 401;
  engineering limited to the caller's visible projects; unknown team → 400.

## 9. Reconciliation and backtesting on current data

Run on the disposable copy, `as_of` 2026-10-29 (read-only; the session had no pending changes):

| Forecast | Result |
|---|---|
| Remaining effort | **Unavailable.** 2 open projects, both with quoted hours only (210 h, 190 h) and no approved estimate; 0 completed projects with approved estimate + actuals |
| Backtest | **Not possible:** 0 comparable completed projects (needs ≥ 6 to evaluate one) |
| Capacity supply (monthly, 3 periods) | Preliminary. 9 people. Oct (29–31 only) 144 h, Nov 1,512 h, Dec 1,656 h, total 3,312 h. Hand check: 9 × 8 h × 2 / 21 / 23 working days. No holidays, shift assignments or unavailable statuses exist, so available = scheduled |
| Demand | 0 h approved remaining (no approved estimates) |
| Collections / billing | Unavailable: 0 active quotes. Reconciliation checks hold trivially |

Real-data accuracy therefore **cannot be stated**. The methods are verified only on test
fixtures.

## 10. Risks and next increment

Risks:

- The effort forecast stays unavailable until enough completed projects carry approved estimates
  and timesheet actuals. Planned hours have to be entered on milestones or stages.
- Capacity is overstated by unrecorded leave and non-project work; it is labelled preliminary.
- Treating "linked to a live project" as "awarded" can include lost or unawarded quotes linked
  by tool number.
- The actuals rule (drafts and rejected hours counted) is still an open decision; changing it shifts
  history factors.
- The pre-existing defect where un-invoicing has no effect means a quote's ledger can
  show invoices the user believes were cleared; billing and collections follow the ledger.

Next increment (in order):

1. Record planned leave (dated) and non-project commitments; replace the undated status deduction.
2. Add an allocation model (person × project × period %) so demand can be phased, which enables
   capacity gaps per team and period.
3. Verify user skills and add a required skill on projects, which enables skill demand.
4. Attribute timesheet hours to milestones in the weekly grid and imports, which enables
   stage forecasts.
5. With 2 and 1 in place, add a capacity-constrained completion-date forecast showing the original
   commitment and current target.
6. Then build non-destructive scenarios on top, and the deferred Control Tower forecast rules
   once a backtest can be evaluated.
7. Add a quote award status (Finance change, out of scope here) to replace the project-link
   assumption.
