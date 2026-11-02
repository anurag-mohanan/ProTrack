# ProTrack Phase 7 — Predictive Engineering Intelligence

Status: Stages 1–7 implemented and tested (2026-11-02). Not committed; see section 14 for the file list.

**Summary.** ProTrack now produces stored, explainable, permission-filtered forecasts for project completion dates, final engineering hours, milestone finish dates, engineering workload against capacity (2, 4, 8 and 12 weeks), and monthly billing and collections. It scores those forecasts against actual outcomes, governs model versions, raises separate predictive Control Tower findings, supports isolated what-if scenarios, and lets the Assistant answer from stored forecasts. On the current working data every project-level forecast is honestly reported as *insufficient data*, with the reason, because the imported history has no start dates, approved estimates or project-linked actual hours (section 1). The engine was verified on deterministic test data only; no historical data was manufactured.

## 1. Readiness findings and historical data assessment (Stage 1)

Checked against the repository and a disposable copy of the working database (`%TEMP%\phase7_inspect.db`, copied 2026-11-02 and taken through the normal startup migrations). `protrack.db` itself was not opened by the application; its last write time is unchanged (2026-10-29 12:20:48).

### 1.1 Phase 0–6 status

| Phase | Evidence | Status |
| --- | --- | --- |
| 0 Audit | `docs/PHASE0_QUOTE_TO_DELIVERY_AUDIT.md`; 12 known failing tests | Present |
| 1 Engineering metrics, delivery variance, quote-to-delivery | `engineering_metrics_service`, `delivery_variance_service`, `reporting/engineering_performance.py` | Present |
| 2 Control Tower | `control_tower_service.py`, 17 rules, `project_risk_*` tables; four forecast rules listed as deferred | Present. Never evaluated on the working data (0 runs) |
| 3 Forecasting | `forecasting/effort.py` (remaining effort, backtest), `capacity.py` (supply), `finance.py` (billing and collections) | Present as a first increment. Completion dates, phased demand, capacity gaps, stage forecasts and scenarios were deferred for lack of data and models |
| 4 Skills | `services/skills/*`; verified vs claimed levels, requirements, gaps | Present. 0 user skills and 0 project requirements in the data |
| 5 Template reconciliation and automation | `template_reconciliation.py`, `automation/*` (commit `caffb65`) | Present. `app/schemas/template_reconciliation.py`, `frontend/src/api/automation.ts` and `AutomationPage.tsx` are still uncommitted although committed code imports them |
| 6 AI Assistant | `services/assistant/*`, `/assistant` API and page (commit `e60d7b3`) | Present. Two Phase 6 edits are not in the commit: the `/ai/chat` permission gate in `app/api/v1/ai.py` and the Assistant navigation entry in `frontend/src/utils/permissions.ts`. Without the first, the committed `/ai/chat` is open to every signed-in user |

### 1.2 Historical data available (working database copy)

| Item | Count | Reliable for modelling? |
| --- | --- | --- |
| Projects | 24 (21 completed, 2 in progress, 1 cancelled) | — |
| Completed projects with a completion timestamp | 15 | **No.** 14 were stamped on the same day (2026-07-03) and 1 on 2026-07-01, a few days after all 24 projects were created by import on 2026-06-26. These record when the data was tidied, not when work finished |
| Projects with a start date (planned, actual or baseline) | 0 | No duration can be measured |
| Projects with quoted hours | 24 | Commercial figure only |
| Projects with an approved estimate (stage estimates or milestone planned hours) | 0 | No approved baseline to compare against |
| Projects with recorded actual hours | 0 (2 timesheet entries exist; neither is linked to a project) | No effort history |
| Projects with a baseline or due-date revision | 0 (all 24 due dates are 2026-09-24) | Original vs revised due dates cannot be distinguished; the identical date is an import default |
| Project type / template | 0 of 24 | Workflow differences cannot be used |
| Classification / complexity | 24 "unclassified" / "medium" (defaults) | Not informative |
| Customers on projects | 4 | Too few projects per customer |
| Milestones | 168 (7 per project) | — |
| Milestones with a due date, baseline, planned start or actual start | 0 | No planned-vs-actual milestone duration |
| Completed milestones with a completion timestamp | 97 (92 on 2026-06-26, 5 on 2026-07-01) | **No.** Import timestamps |
| Milestones with dependencies or a template link | 0 / 0 | No dependency network |
| Quotes, invoice lines, payment lines, billing milestones | 0, 0, 0, 0 | No finance history |
| Holidays / shift assignments / planned leave | 0 / 0 / no leave model | Capacity uses working hours per day only |
| Verified user skills / project skill requirements | 0 / 0 | No skill bottleneck analysis possible |
| Control Tower runs / findings | 0 / 0 | — |

Answers to the brief's readiness questions:

1. Historical records: project and milestone shells from one import, 2 timesheet entries, no finance ledger.
2. Completed projects usable for analysis: **0** (15 have completion stamps, none has a start date, approved estimate or actual hours).
3. Records with reliable quoted, approved and actual hours: **0** (quoted only).
4. Milestones with reliable planned and actual dates: **0**.
5. Projects with reliable original and revised due dates: **0**.
6. Missing or inconsistent: start dates, approved estimates, timesheet actuals linked to projects, milestone plans, dependencies, project types, finance ledger, leave, skills. Completion stamps are bulk timestamps.
7. Reusable calculations: shared engineering metrics (estimate source, actuals, remaining, delivery reference dates), delivery-variance definitions, Phase 3 effort history and backtest, capacity supply (`day_capacity`), Finance ledger and FIFO allocation, Phase 3 billing and collection items, Skills coverage and gaps, Control Tower rule engine and finding lifecycle.
8. Not feasible on the current data: every numeric prediction. The engine is built and verified on deterministic test data; on the working data it reports, per project, why no reliable prediction can be produced.

### 1.3 Data-quality rules applied by the engine

* A completed project counts as history only if it has a start date (actual, else planned, else baseline), a completion date after that start, and an approved original estimate above zero. Duration history additionally needs the completion date to be at least one day after the start.
* Effort history uses the Phase 3 sample rule (approved original estimate above zero and recorded actual hours above zero).
* Milestone history needs a recorded start (actual, else planned), a completion date and a planned finish.
* Payment behaviour needs fully paid invoice lines with a due date; invoicing lag needs a completed project linked to a quote with an invoice dated on or after completion.
* Groups smaller than the minimum sample (5) are not used. Nothing is filled in, interpolated or defaulted to make a prediction possible.

### 1.4 Constraints carried forward

* No allocation model and no planned leave: phased demand is an assumption (remaining hours spread evenly over the assignee's working days until the project's end date), stated on every output.
* Quotes have no award status (Phase 3 assumption kept).
* `build_receivables_aging` still fails for quotes linked to a project (B0.x); the predictive finance layer uses the lower-level ledger functions, as Phase 3 does.
* The rule that draft and rejected hours count toward actuals is still an open business decision; the split is shown.

## 2. Architecture

```
Shared metrics (engineering_metrics_service, Phase 3 forecasting, Finance ledger, capacity supply, Skills coverage)
        │  read only
        ▼
predictive/inputs.py ── plain dataclasses (ProjectFacts, samples); no ORM rows reach a predictor
        │
        ▼
Pure predictors: hours.py · delivery.py · milestone.py · resources.py · finance.py   (stats.py: median, quantile, rank test)
        │
        ├── engine.py ── prediction run: active version + candidate versions in shadow → predictions / prediction_runs
        │        └── evaluation.py ── scores earlier predictions against actual outcomes (outcome columns only)
        ├── scenarios.py ── same predictors on modified copies of the inputs → prediction_scenarios only
        ├── alerts.py ── predictive Control Tower findings (source = predictive) from stored predictions
        ├── accuracy.py ── accuracy, calibration, degradation, activation guard, enable/disable
        ├── patterns.py ── portfolio patterns on request (nothing stored)
        └── read.py ── the only read path: permission-filtered latest/history rows, freshness
                 │
                 ├── /api/v1/predictions (FastAPI)  ──► /predictive page (React)
                 └── Assistant tools (services/assistant/tools/predictions.py)
```

Principles enforced in code:

* **Computed once, in the backend.** The frontend and the Assistant only display stored predictions; neither computes a date, an hour figure or an amount. The Assistant's system prompt (rule 11) forbids computing forecasts, and every predictive tool returns stored values with factors, uncertainty, limitations and sources.
* **Reuse.** Actuals, estimate sources, remaining hours, delivery reference dates, capacity per person-day, the Finance ledger and the Phase 3 billing and collection items are read from the existing services; the predictive layer does not re-implement them.
* **No writes to business records.** Runs write `predictions` and `prediction_runs`; scenarios write `prediction_scenarios`; governance writes `prediction_settings` and `prediction_model_versions`; Control Tower evaluation writes only its own finding tables. Verified on a database copy (section 13.3).
* **Works without an AI provider.** Nothing in the prediction path calls an LLM. The Assistant is only a reader.
* **No machine-learning libraries.** Medians, empirical percentiles and a Mann–Whitney rank test in pure Python. More complex models were deliberately not introduced: the data cannot support them, and they would be harder to explain.

## 3. Prediction types

| Type | Subject | Output | Compared against (baseline) | Model |
| --- | --- | --- | --- | --- |
| `project_delivery` | Open project | Forecast completion date, 10th–90th percentile range, days late or early | Current target date (recorded) | `delivery-1` |
| `project_final_hours` | Open project | Forecast final actual hours, range, variance | Current approved estimate (recorded) | `hours-1` |
| `milestone_delay` | Open milestone with a plan | Forecast finish date, range, variance | Milestone target (due date or baseline finish) | `milestone-1` |
| `resource_demand` | Person, team and required skill × 2/4/8/12 weeks | Forecast project demand hours, utilisation, shortage, overloaded weeks (conflicts), single-person dependency, under-utilisation | Allocatable capacity | `demand-1` |
| `finance_billing` | Currency × month (6 months) | Forecast invoicing per month | Phase 3 billing dated by current targets | `billing-1` |
| `finance_collections` | Currency × month (6 months) | Forecast cash collected per month | Phase 3 collections on contractual due dates | `collections-1` |

Every prediction row has `status` = `predicted` or `insufficient_data` (with a reason), the comparison group and its size (`sample_size`), calculation and context factors, warnings, the model version and the date it was made (`as_of`). A likely range is stored only when at least 10 comparable outcomes exist. `observed_frequency` (the share of comparable outcomes that exceeded the target or estimate) is reported as a historical frequency, never as a probability.

Awarded, invoiced, collected, outstanding and remaining-to-invoice amounts are carried on every finance row as recorded ledger totals and labelled as such; forecast billing and forecast collections are separate fields.

## 4. Algorithms and assumptions

Shared rules (`stats.py`, `inputs.py`): minimum comparable sample 5; range only from 10; central value is the median; ranges are the 10th and 90th empirical percentiles (type-7 interpolation). The comparison group is the most specific level that reaches the minimum: same project type, complexity and customer → same project type and complexity → same project type. Different project types are never pooled. Customer is only ever a refinement inside a group of the same type and complexity, so it is never a stand-in for complexity. History is organisation-wide and limited to what was known at `as_of`, so a prediction does not depend on who asks.

* **Final hours (`hours-1`).** Ratio actual ÷ approved original estimate from comparable completed projects (the Phase 3 sample rule), applied to this project's original estimate. Conditioned on hours already recorded: only comparable outcomes still above the recorded hours are used, and the forecast is never below what is recorded. Quoted hours alone are never used (commercial figure). A scenario scope change scales the remaining part.
* **Completion date (`delivery-1`).** Calendar days per approved original estimate hour from comparable completed projects, applied from the recorded start date. Conditioned on the project not having finished yet (only durations longer than the elapsed time). A capacity check finds the earliest day the assigned designer's free capacity, after their other project work, covers the forecast remaining hours; it can only move the date later. Milestone counts and percent complete are context, never a proxy for elapsed time.
* **Milestone finish (`milestone-1`).** Actual ÷ planned duration of completed milestones of the same template milestone, else the same stage; conditioned on elapsed time for started milestones; a start waits only for **recorded** predecessors forecast to finish later. Milestone sequences are not assumed to be the same across projects.
* **Workload (`demand-1`).** Remaining hours (forecast final − actual, else approved remaining) spread evenly over the assigned designer's working days until the forecast (else target) end. Capacity is the Phase 3 allocatable hours per person-day less the person's historical non-project share (needs 4 weeks of timesheets in the last 12, otherwise not deducted and flagged as overstated). Shortage = demand above capacity; overloaded weeks = weeks where overlapping projects exceed capacity; single-person dependency = one person carries at least 60% of a team's demand, or a required skill has one verified holder; under-utilisation = below 50% at 4 weeks with complete demand. Projects with no basis for remaining hours are counted as missing, never as idle time. The even-spread assumption is printed on every row: ProTrack has no allocation plan, so this is a forecast of load, not a schedule.
* **Billing (`billing-1`).** Phase 3 billing items. Completion-triggered items are dated by actual or forecast completion plus the median historical completion-to-invoice lag (customer, else company), conditioned on time already waited. Completion alone is never treated as an invoice: without lag history nothing is dated, and items ready to invoice now are reported separately.
* **Collections (`collections-1`).** Phase 3 outstanding invoice lines moved from the contractual due date by the median payment delay (customer, else company), conditioned on how long the line is already overdue.

Assumptions stated on outputs: comparable history represents the future; the even-spread workload model; the capacity rule; customer refinement only inside type and complexity; draft and rejected hours are shown separately from approved actuals.

## 5. Models, versioning and migrations

New tables (created by `create_all`, all additive):

| Table | Purpose |
| --- | --- |
| `prediction_settings` | One row per type: enabled flag, disabled reason, active model version, who changed it |
| `prediction_model_versions` | Version lifecycle per type: `active`, `candidate` (runs in shadow) or `retired`; activation time, user and note |
| `prediction_runs` | One row per run: trigger, `as_of`, status, counts, error |
| `predictions` | Every prediction ever made, with `is_latest`, `is_shadow`, factors, data used, warnings and the outcome columns (`outcome_status`, actual value or date, error, percentage error, naive error, horizon) |
| `prediction_scenarios` | Saved what-if scenarios: assumptions, result, model versions, created and updated by, soft delete |

`app/db/phase112_predictive_schema_sync.py` (additive, idempotent): adds `source` (default `operational`), `prediction_id`, `triage_status`, `triage_note`, `triaged_at`, `triaged_by_id` and `recommendation_id` to `project_risk_findings`, an index on `source`, and the new Activity enum values on PostgreSQL. Existing findings are backfilled as `operational`, which they are. No column, table or enum is dropped or renamed. Rollback is described in the module docstring.

History is preserved: a new run marks the previous row for the same subject `is_latest = false` but never deletes or edits it. Only the last prediction of each day counts for accuracy, so repeated runs on one day do not inflate the sample. A failed run keeps only its failure record; earlier predictions stay current. A run abandoned for 30 minutes no longer blocks new runs.

## 6. Services

| Module | Responsibility |
| --- | --- |
| `inputs.py` | Builds `ProjectFacts` and history samples from the shared metrics; comparable-group selection |
| `hours.py`, `delivery.py`, `milestone.py`, `resources.py`, `finance.py` | Pure predictors returning `Outcome` objects |
| `engine.py` | `run_predictions`: enabled types, active version plus candidates in shadow, supersede, persist; `capacity_checks` |
| `evaluation.py` | Scores earlier predictions when the outcome is known (final hours 14 days after completion so late timesheets arrive) |
| `accuracy.py` | Accuracy report, calibration, horizons, degradation, activation guard, enable/disable with audit |
| `alerts.py` | Four predictive Control Tower rules, deduplicated against operational findings |
| `scenarios.py` | Evaluate, save, update and soft-delete scenarios |
| `patterns.py` | Portfolio project patterns and customer payment patterns with n, period, comparison group, p-value and limitations |
| `read.py` | Permission-filtered reads and freshness, shared by the API and the Assistant |
| `registry.py` | Prediction types, versions, settings sync |

Integration points:

* **Control Tower** (`control_tower_service.py`, rules version 3): rules `delivery_forecast_risk`, `estimate_overrun_forecast` (at least 10% over; high from 25%), `milestone_delay_forecast` (high from 14 days) and `resource_bottleneck` (new category "Resource capacity"; high from 150%). They use only the latest non-shadow predictions of enabled types from the last 8 days, respect the working model's risk types, and are suppressed when the matching operational finding (`project_past_target`, `estimate_overrun_realized`, `milestone_overdue` on the same milestone) is live, so one problem never appears twice. Bottleneck findings never name the designer. Findings carry `source` and a "Forecast" label, and have their own view and KPI. New actions for every finding: **Investigate**, **Dismiss** (note required), **Clear triage** and **Create workflow action** (an `AIRecommendation` in the existing recommendations workflow, created once). None of these changes the condition, the project or any other record; each is logged.
* **Assistant** tools: `list_project_predictions`, `explain_project_prediction`, `get_resource_demand_forecast` (capacity access), `get_finance_timing_forecast` (Finance access), `get_historical_patterns` (organisation-wide Reports; payment patterns need Finance), `get_prediction_accuracy`, `run_what_if_scenario` (does not save). Five new suggested questions cover the brief's examples.
* **Jobs**: queue job `prediction_run`; `python -m app.jobs.runner --predictions --control-tower` runs predictions and then the Control Tower so forecast findings are fresh.

API (`/api/v1/predictions`, Reports access required on every route): `GET /overview`, `GET ?prediction_type=` (403 when the type is outside the caller's scope), `GET /projects/{id}`, `GET /accuracy`, `GET /patterns`, `POST /run` (edit-projects permission), `PUT /settings/{type}` and `POST /models/{type}/{version}/activate` (administrators), and scenarios: `GET /projects/{id}/scenarios`, `POST …/preview` (writes nothing), `POST` create, `PUT /scenarios/{id}`, `DELETE /scenarios/{id}` (edit-projects permission).

## 7. User interface

`/predictive` (navigation: Operations → Predictive Intelligence; shown to users with Reports access, the same rule as the backend). A freshness line or warning shows when predictions were last produced and which types are disabled. Users with the edit-projects permission see **Refresh predictions**.

* **A. Portfolio** — four KPI cards (likely late, likely over estimate, milestones likely late, capacity shortages at 4 weeks), the top 10 likely-late and likely-overrun projects (recorded target or approved estimate next to the forecast, range and variance), late milestones, forecast completions by month, a collapsed "why some items cannot be forecast" list, a bottleneck summary, the billing and collections forecast (Finance users only, ledger figures labelled as recorded), and collapsed portfolio patterns (organisation-wide users only, loaded on demand).
* **B. Project** — project picker; a **Recorded figures** card (committed and current target dates, start, quoted hours, original and current estimate with approval status, approved actual hours, hours awaiting approval, open and overdue milestones) beside a **Forecast** card (completion date and final hours with range, variance and an expandable "why this forecast" showing factors, comparison group, n, range basis, limitations and model version); milestone forecasts; forecast history with outcomes once known.
* **C. Resource demand** — 2/4/8/12-week horizon; demand, capacity, people over capacity, skill bottlenecks; tables for teams, designers (hover for the projects, clipped to the user's access) and required skills with shortage, overloaded-week, single-person, under-utilised and incomplete-demand signals; the not-forecast list with reasons. Requires Resource Planning access.
* **D. Accuracy** — per type: scored, pending and not-scorable counts; error figures only from 10 scored forecasts; comparison with the naive baseline (recorded target or estimate); range coverage; horizon table; calibration; degradation; recent forecast-versus-actual examples; model versions with their own accuracy. Administrators can enable or disable a type (reason required) and activate a version (refused when worse; justification required when evidence is insufficient).
* **E. Scenarios** — project picker, assumptions (scope change, customer or approval delay, move target date, different designer, additional support hours per week, start date when none is recorded, milestone delays), **Compare with baseline** (not saved), save, edit and delete for users with edit-projects permission, a baseline/scenario/difference table under a "Hypothetical scenario" banner, and saved scenarios with who created and last changed them.

Forecast values always carry a "Forecast" label or column heading; recorded values are labelled "recorded", "actual" or "approved". Nothing on the page edits a project, estimate, assignment or Finance record.

## 8. Accuracy results

* **Working data (database copy, 2026-11-02):** 0 predictions scored against actual outcomes for every type. No accuracy figure is reportable. This is expected: no project-level prediction could be made (section 1), and outcomes are only scored once a forecast project finishes.
* **Test data:** accuracy, horizon breakdown, calibration, degradation and the activation guard are verified with deterministic scored rows (section 13). These are test fixtures, not results.

Accuracy should be reviewed once at least 10 forecasts of a type have been scored. Until then the page and the Assistant report the count only.

## 9. Limitations

* The working data cannot support any project, milestone or finance prediction today; workload forecasts exist only for people and teams whose open projects have a basis for remaining hours (32 predicted, 12 insufficient on the copy). Predictions become available as start dates, approved estimates, project-linked timesheets, milestone plans and Finance records are captured; nothing has to change in the code.
* Workload uses an even-spread assumption (no allocation plan) and no planned leave or holidays in the data.
* A different designer in a scenario changes only the capacity check; comparable history is not designer-specific.
* Skill demand counts all work on a project that requires the skill; the share needing the skill is not recorded.
* Portfolio patterns test several groups at once; roughly 1 in 20 tested differences can look significant by chance (stated on the page).
* Finance timing depends on the Phase 3 items and inherits their assumptions (quotes have no award status). B0.x (`build_receivables_aging` with project-linked quotes) is still open and is avoided rather than fixed.
* Predictions are produced on demand or by the job runner; there is no built-in schedule. Rows older than 8 days are flagged as possibly out of date and are not used for Control Tower findings.

## 10. Security

* Every route checks Reports access in the backend; type-level access is enforced again in `read.py` (projects: the caller's visible projects within their report team scope; workload: Resource Planning access, team-scoped callers see only their teams' person and team rows and no skill rows; finance: Finance view). Project names inside workload rows are clipped to projects the caller can see, with a count of the rest.
* Running predictions and saving scenarios need the edit-projects permission; enabling, disabling and activating models are administrator-only. Portfolio patterns need organisation-wide Reports access; payment patterns also need Finance.
* Scenario creators and modifiers are stored on the scenario and every save, update, delete, triage, conversion, setting change and activation is written to the activity log.
* The Assistant receives only permission-filtered stored predictions through the same read path; no raw records are sent for forecasting. Tests confirm a team-scoped user sees nothing outside their scope and no finance data without Finance access.
* No predictive service writes to project, estimate, assignment, timesheet, invoice, payment or accounting records. Verified by table snapshots on a database copy.
* No secrets are used or stored by this phase.

## 11. Configuration

| Setting | Where | Default |
| --- | --- | --- |
| Enable or disable a prediction type | Accuracy tab or `PUT /predictions/settings/{type}` (reason required to disable) | All enabled |
| Active model version | Accuracy tab or `POST /predictions/models/{type}/{version}/activate` | First version of each type |
| Minimum comparable sample / range sample / pattern group | `predictive/stats.py` | 5 / 10 / 8; significance 0.05 |
| Minimum scored predictions for accuracy; degradation factor; recent window | `predictive/accuracy.py` | 10; 1.25×; 90 days |
| Freshness and Control Tower age limit | `read.py`, `alerts.py` | 8 days |
| Control Tower thresholds | `alerts.py` | overrun 10% (high 25%); milestone delay high 14 days; utilisation high 150% |
| Workload rules | `resources.py` | horizons 2/4/8/12 weeks; non-project share needs 4 of the last 12 weeks; under-utilised below 50%; dependency at 60% |
| Finance horizon | `finance.py` | 6 months |
| Saved scenarios per project | `scenarios.py` | 20 |
| Scheduled runs | `python -m app.jobs.runner --predictions --control-tower` from the existing scheduler | Not scheduled by default |

## 12. Test results

* Phase 7 tests: 41 passed; with the Control Tower and Assistant suites, all pass.
* Full backend suite: 1410 passed, 12 failed (the 12 known baseline failures, none new), 1 skipped.
* Frontend: type-check and production build pass; ESLint clean on new files.
* Database copy: migration additive and idempotent; runs write only their own tables; the original database untouched.

Details, and the mapping from each of the brief's 18 tests to the test functions, are in section 13.

## 13. Verification

### 13.1 Phase 7 tests (`tests/test_predictive.py`, 41 tests, deterministic data, no live AI)

| Brief test | Covered by |
| --- | --- |
| 1 Delivery | `test_delivery_from_elapsed_time_and_comparable_durations`, `test_delivery_refuses_without_start_or_when_past_history`, `test_milestone_counts_do_not_drive_the_delivery_date`, `test_capacity_check_can_only_move_delivery_later`, `test_capacity_finish_respects_other_work` |
| 2 Hours | `test_final_hours_from_comparable_history`, `test_final_hours_never_below_recorded_and_ranges_need_ten` |
| 3 Milestone | `test_milestones_follow_recorded_dependencies_only`, `test_started_milestones_are_conditioned_on_elapsed_time` |
| 4 Resource | `test_demand_is_phased_to_the_end_date_and_shortages_are_flagged`, `test_underutilisation_concentration_and_skill_bottlenecks`, `test_demand_without_any_estimate_is_not_reported_as_idle`, `test_non_project_share_needs_four_weeks`, `test_person_demand_is_scored_against_booked_project_hours` |
| 5 Finance | `test_collections_move_due_dates_by_payment_history`, `test_collections_without_payment_history_are_insufficient`, `test_billing_needs_completion_and_invoicing_history`, `test_finance_predictions_are_scored_like_for_like` |
| 6 Incomplete data | `test_insufficient_history_and_quoted_hours_alone`, `test_delivery_refuses_without_start_or_when_past_history`, `test_demand_without_any_estimate_is_not_reported_as_idle` |
| 7 Small samples | `test_final_hours_never_below_recorded_and_ranges_need_ten`, `test_patterns_need_size_and_significance_and_respect_strata`, `test_patterns_report_no_difference_without_significance` |
| 8 Customer workflow | `test_customer_only_refines_a_group_of_the_same_type`, `test_patterns_need_size_and_significance_and_respect_strata` |
| 9 Template differences | `test_other_project_types_are_never_pooled` |
| 10 Versioning | `test_disabled_types_do_not_run_and_candidates_run_in_shadow`, `test_a_worse_model_is_never_activated_and_changes_are_audited`, `test_reruns_preserve_history_and_score_only_the_last_of_a_day` |
| 11 Prediction vs actual | `test_outcomes_are_scored_against_actuals`, `test_cancelled_projects_are_not_scored`, `test_finance_predictions_are_scored_like_for_like` |
| 12 Degradation | `test_accuracy_needs_enough_scored_predictions_and_detects_degradation` |
| 13 Scenario isolation | `test_scenarios_are_isolated_hypothetical_and_audited` |
| 14 Permissions | `test_predictions_api_enforces_permissions_and_separates_actuals`, `test_assistant_reads_stored_predictions_and_respects_permissions` |
| 15 AI integration | `test_assistant_reads_stored_predictions_and_respects_permissions` (scripted provider) |
| 16 Control Tower | `test_forecast_findings_are_separate_and_explain_the_forecast`, `test_forecasts_defer_to_operational_findings_and_skip_stale_shadow_or_disabled`, `test_resource_bottleneck_is_raised_once_without_naming_the_designer`, `test_triage_and_convert_never_change_the_condition_or_records` |
| 17 Phase 3 regression | Full suite (`tests/test_forecasting.py` and others), section 13.2 |
| 18 Finance and resource regression | Full suite, section 13.2; `test_run_persists_predictions_without_touching_projects`, `test_failed_run_keeps_nothing_but_the_failure` |
| Migration | `test_phase112_migration_is_idempotent` |
| Jobs | `test_prediction_job_runs_from_the_queue` |

Result: **41 passed** (`tests/test_predictive.py`); with `tests/test_control_tower.py` and `tests/test_ai_assistant.py` all pass. Ruff (`F`, `E9`) clean on all new and changed Python files.

### 13.2 Full suite and frontend

Full backend suite (disposable `DATABASE_URL`): **1410 passed, 12 failed, 1 skipped** in 46 min 55 s. The 12 failures are exactly the 12 baseline failures in `PHASE0_QUOTE_TO_DELIVERY_AUDIT.md` §3.1 (quote PDF extraction patch targets, receivables aging, invoiced flag, timesheet pack naming, duplicate-week import, team salary roll-up, IT asset import); none is new and none involves forecasting, Control Tower, Finance calculations or resource planning. Phase 3 (`tests/test_forecasting.py`), Finance, resource planning and Control Tower suites pass within this run. (Phase 6 run: 1369 passed; the difference is the Phase 7 tests and other additions since.)

Frontend: `npx tsc -b` passes; `npm run build` succeeds; ESLint is clean on all new files. The one ESLint error reported in `AppBreadcrumbs.tsx` (`useBreadcrumbTitle` export, react-refresh rule) predates this phase; this phase only added a route label there.

### 13.3 Database copy check (2026-11-02)

On a fresh copy of `protrack.db` in `%TEMP%` (the original was never opened; last write time unchanged at 2026-10-29 12:20:48):

* Migration: 162 of 166 existing tables unchanged; `fx_rates`, `org_departments`, `team_commercial_terms` and `teams` change through pre-existing startup seeds, not phase112. A second startup is idempotent for phase112. The `phase71` "could not drop sqlite unique" messages are pre-existing.
* Prediction run: succeeded. Final hours 2 insufficient (no approved estimate), completion date 2 insufficient (no start date), milestones 7 insufficient (no target date), workload 32 predicted and 12 insufficient, finance 0 rows (no ledger). No non-prediction table changed.
* Control Tower evaluation: 10 operational findings, 0 predictive (no project-level forecast exists); no table outside the Control Tower tables changed.

## 14. Files

New: `app/models/prediction.py`, `app/db/phase112_predictive_schema_sync.py`, `app/services/predictive/` (all modules), `app/schemas/predictive.py`, `app/api/v1/predictions.py`, `app/services/assistant/tools/predictions.py`, `tests/test_predictive.py`, `frontend/src/types/Predictive.ts`, `frontend/src/api/predictive.ts`, `frontend/src/components/predictive/` (all files), `frontend/src/pages/PredictivePage.tsx`, this document.

Changed for Phase 7: `app/models/models.py` (registers the prediction models), `app/models/enums.py` (activity enum values), `app/models/control_tower.py`, `app/main.py` (phase112 startup step), `app/api/v1/api.py`, `app/api/v1/control_tower.py`, `app/schemas/control_tower.py`, `app/services/control_tower_service.py`, `app/services/job_queue.py`, `app/jobs/runner.py`, `app/services/assistant/registry.py`, `orchestrator.py`, `suggestions.py`, `tools/projects.py`, `tests/test_control_tower.py`, `frontend/src/App.tsx`, `frontend/src/utils/permissions.ts`, `frontend/src/components/layout/AppBreadcrumbs.tsx`, `frontend/src/api/controlTower.ts`, `frontend/src/types/ControlTower.ts`, `frontend/src/components/reports/ControlTowerPanel.tsx`.

## 15. Outstanding work

* Capture the data the models need: project start dates, approved estimates, project-linked timesheets, milestone plans and dependencies, project types, and Finance records. Predictions appear automatically once comparable history reaches the minimum.
* Schedule `--predictions --control-tower` in the existing job scheduler (daily is sufficient).
* Decide whether draft and rejected hours count toward actuals (open since Phase 1).
* Fix B0.x (`receivables_service` reads `project.name`) so finance aging can be used directly; Phase 7 avoids it.
* Commit the outstanding Phase 5 and 6 files listed in section 1.1.
* Browser check of `/predictive` was not performed (by instruction); verification relied on tests and the build.

## 16. Next increment

1. Once at least 10 forecasts of a type are scored, review accuracy against the naive baseline and decide whether the model earns its place; disable any type that does not beat it.
2. Allocation-aware workload (planned allocations and leave) to replace the even-spread assumption.
3. Stage-level forecasts and stage overrun findings (`stage_overrun` is still deferred in the Control Tower).
4. Trial a second hours or delivery model in shadow (for example, adding recorded progress) and promote it only through the activation guard.
5. Scenario comparison across several projects (portfolio what-if) once project-level forecasts exist.
