# ProTrack Phase 8 — Business Intelligence and Strategic Management

Status: Stages 1–8 implemented and tested in order. The changes are in the working tree on
`rca/shared-regression-recovery` and are not committed.

**Principle.** Every figure carries its kind: actual, approved plan, forecast, target, baseline or
manual entry. Different kinds are never added together, and they are never shown as interchangeable.
A figure without reliable data is shown as "not available" with the reason, never as zero.

## 0. Implementation status

| Area (brief part) | Status | Notes |
| --- | --- | --- |
| Readiness audit and KPI definitions (1) | Implemented | §1, §3 |
| Management Cockpit: filters, business, operations, workforce, customers (2) | Implemented | Business-unit filter appears only when teams have a business unit (none do today). Allocated capacity is not available (no allocation model) |
| Customer intelligence profile (3) | Implemented | No profitability (no cost data). Region analysis is blocked: `Customer.country` is empty for all 9 customers |
| Engineering efficiency analytics (4) | Implemented | No per-designer comparison by design (see §6.3) |
| Strategic objectives and KPI management (5) | Implemented | Managers cannot propose a target revision; only an approver changes a target |
| Strategic initiatives (6) | Implemented | Progress is the owner's reported progress, labelled as such |
| Management reviews (7) | Implemented | No in-app AI draft of the summary; the summary is written by a person |
| AI management intelligence (8) | Implemented | Six read-only Assistant tools |
| Action tracking (9) | Implemented | Actions link to a review, objective, initiative or project; no task copy |
| Reports and exports (10) | Implemented | Eight Excel reports through the existing report template and audit |
| Security and governance (11) | Implemented | §9 |
| Tests (12) | Implemented | §10 |
| Revenue trend from a predicted billing target ("are we on track?") | Partially implemented | Answered against an objective's approved target with elapsed-time pace; no billing forecast is added to the actual |
| New vs repeat business | Partially implemented | Shown, but marked *limited* until invoice history covers a full year before the period |
| Business-unit filter | Blocked by data | Supported in code; `teams.business_unit` is empty |
| Planned leave in future capacity | Not implemented | ProTrack records no planned (future) leave |
| Person-to-project allocation | Not implemented | No allocation model exists; approved remaining work and Phase 7 forecasts are shown instead |

## 1. Readiness findings (Stage 1)

The repository was checked, and so was a disposable copy of the working database
(`%TEMP%\p8_protrack_copy.db`). The copy was taken through the startup schema steps. `protrack.db`
was never opened by the application; its last write time is unchanged (2026-10-29 12:20:48).

### 1.1 Phase 0–7 status

| Phase | Evidence | Status |
| --- | --- | --- |
| 0 Audit | `docs/PHASE0_QUOTE_TO_DELIVERY_AUDIT.md`; 12 known failing tests (§3.1 there) | Present |
| 1 Engineering metrics, delivery variance, quote-to-delivery | `engineering_metrics_service`, `delivery_variance_service`, `reporting/quote_to_delivery.py`, `engineering_performance.py` | Present |
| 2 Control Tower | `control_tower_service.py`, `project_risk_*` tables | Present |
| 3 Forecasting | `forecasting/effort.py`, `capacity.py`, `finance.py` | Present |
| 4 Skills | `services/skills/*` (gaps, matching, verified vs claimed) | Present |
| 5 Template reconciliation and automation | `template_reconciliation.py`, `automation/*` | Present |
| 6 AI Assistant | `services/assistant/*` (tool registry, orchestrator, permission-scoped tools) | Present |
| 7 Predictive intelligence | `services/predictive/*`, `predictions` tables, `docs/PROTRACK_PHASE_7_PREDICTIVE_INTELLIGENCE.md` | Present |

### 1.2 Data available in the working database copy

| Item | Count | Effect on Phase 8 |
| --- | --- | --- |
| Active quotes / invoice lines / payment lines | 0 / 0 / 0 | Every Finance figure on the real data shows "not available"; the logic is proven by tests on deterministic data |
| Customers / with a country | 9 / 0 | Region analysis is impossible |
| Projects / completed | 24 / 21 | — |
| Distinct completion days | 2 | Completion stamps are bulk tidy-up dates, so the cockpit marks completions *limited* |
| Projects with an original baseline | 0 | On-time rate and delivery variance are "not available" on the real data |
| Timesheet entries | 2 | Hours-based figures are effectively empty |
| Holidays / shifts / shift assignments | 0 / 5 / 0 | Capacity uses each person's own working hours; the cockpit says so |
| Teams / with a business unit | 3 / 0 | Business-unit filter hidden |
| Training assignments / user skills | 0 / 0 | Training and skill figures are empty |

Cockpit read on the copy (FY 2026-27):
- 12 active employees (virtual and system accounts excluded);
- 18,792 h available capacity, marked *limited* because no holidays are recorded and no shift assignments exist;
- 2 active projects, 2 overdue;
- 15 completions, marked *limited*;
- 4 customers in scope;
- all Finance figures "not available".

### 1.3 Findings that shaped the design

- **No award status.** ProTrack has no quoted-versus-awarded state. Every active quote is what the
  Finance dashboard counts as awarded, so Phase 8 shows *awarded value* and states that a separate
  quoted (pipeline) value does not exist.
- **Two revenue rules exist.** The Finance dashboard counts awarded value by quoted date. The FY
  turnover control counts invoice lines by invoice date. Phase 8 uses the FY turnover rule for
  invoiced revenue and the dashboard rule for awarded value. Each is defined separately and neither
  is changed.
- **Capacity calendar exists; planned leave does not.** Capacity comes from shifts, holidays,
  employment dates and personal hours (`forecasting/capacity`). Recorded leave is deducted from
  elapsed capacity. Future leave cannot be deducted.
- **Bulk completion stamps** (Phase 7 finding) make throughput by month unreliable on the real data.

## 2. Existing services reused

No new calculation engine was written. Each Phase 8 figure comes from an existing service.

| Area | Service reused | Phase 8 caller |
| --- | --- | --- |
| Invoiced revenue, collections, outstanding, awarded value (INR) | `finance.fy_turnover_service.quote_ledger_inr` (the FY turnover rule, now shared, no rule change), `quote_cash_ledger_service.summarize_quote_cash` | `management/business.py` |
| Payment lead time | FIFO payment allocation as in `predictive/finance.paid_allocations` | `business.payment_lead_times` |
| Completed and active project figures, quoted/approved/actual hours, delivery variance | `reporting/quote_to_delivery.build_quote_to_delivery_report` (Phase 1 shared metrics) | `management/operations.py`, `customers.py`, `efficiency.py` |
| Official hours rule (approved only) | `services/actual_hours.official_entry_clause` | `operations.booked_hours`, `workforce` |
| Current risks, forecast risks | `control_tower_service` (operational vs predictive findings) | `operations.risk_projects` |
| Capacity | `forecasting/capacity.day_capacity`, `capacity_planning_users`, `build_capacity_forecast` | `management/workforce.py` |
| Headcount | `hr_dashboard_service.is_active_employee`, `employee_user_clause` | `workforce` |
| Skills | `skills.gaps.build_gap_report`, `resolve_skill_access` | `workforce._skills` |
| Forecasts | `predictive.predictions.latest`, `freshness` (Phase 7) | cockpit workload bottlenecks, customer profile, review forecasts section |
| Report scope and project visibility | `reporting.report_scope.resolve_report_scope`, `team_access.project_visibility_clause` | `management/access.py` |
| Excel export | `reporting/excel/letterhead`, `styles`, `report_authorization.log_report_generation` | `reporting/excel/management.py` |
| Audit and notifications | `activity_service.log_activity`, `notification_service.create_notification` | `management/events.py`, `actions.py` |

`fy_turnover_service.build_fy_turnover_control` now calls `quote_ledger_inr`. Its results are
unchanged:
- the same active-quote set and team filter;
- outstanding still sums `balance_due` from invoice and payment lines.

The Finance test suites pass apart from the known baseline failures.

## 3. KPI definitions

All definitions live in `app/services/management/metrics.py` (`KPI_DEFINITIONS`). The API serves
them at `GET /api/v1/management/definitions`, which filters out Finance definitions for users
without Finance access. The UI shows each one as a tooltip on its KPI card.

| KPI | Unit | Kind | Definition (short) |
| --- | --- | --- | --- |
| Invoiced revenue | INR | Actual | Invoice lines dated in the period, at each quote's locked revision rate |
| FY invoiced revenue | INR | Actual | FY start to the earlier of the period end and today |
| Collections received | INR | Actual | Payment lines dated in the period |
| Awarded project value | INR | Actual | Current revision value of active quotes quoted in the period |
| Outstanding receivables | INR | Actual | Invoiced − paid per active quote, today (a position) |
| Month-on-month growth | % | Actual | Latest month vs the month before; blank if that month had no invoices |
| Repeat-business share | % | Actual | Revenue from customers first invoiced before the period; *limited* while history < 1 year |
| Average payment lead time | days | Actual | Invoice date → full payment (FIFO) for lines fully paid in the period |
| Active projects | count | Actual | Planning, in progress or on hold, today |
| Projects completed | count | Actual | Completed with a completion date in the period |
| Projects overdue | count | Actual | Active and past the current target date, today |
| Projects at risk | count | Actual | Active with an open operational Control Tower risk |
| Projects with forecast risk | count | **Forecast** | Active with an open predictive finding; never added to "at risk" |
| Projects exceeding approved hours | count | Actual | Active with approved hours to date above the approved estimate |
| Original quoted hours | h | Quoted | Never added to approved estimates |
| Current approved hours | h | **Approved plan** | Approved stage estimates (else milestone plan) |
| Actual engineering hours | h | Actual | Approved timesheet hours only |
| Average delivery variance | days | Actual | Completion − original baseline, completed projects with a baseline |
| Engineering-hour variance | % | Actual | (Σ actual − Σ approved) ÷ Σ approved over comparable completed projects |
| On-time delivery | % | Actual | Delivered on or before the original baseline ÷ projects with one |
| Approved hours booked | h | Actual | Approved hours dated in the period |
| Rework and engineering-change hours | h | Actual | Approved hours typed Rework, Customer Change or Internal Correction |
| Active employees | count | Actual | Virtual/system users and leavers excluded |
| Available / allocatable capacity | h | Actual | Capacity calendar; allocatable × maximum allocation % |
| Allocated capacity | h | — | Not available: no allocation model |
| Approved remaining work | h | **Approved plan** | Approved estimate − approved hours over open projects |
| Recorded capacity utilisation | % | Actual | Approved project hours ÷ available hours (after recorded leave), elapsed part only |
| Training completion | % | Actual | Completed ÷ non-cancelled assignments |
| Verified holders of a skill | count | Actual | Active employees with a current verified record at or above a level |

## 4. New database entities and migrations

These are additive tables only (`app/models/management.py`). No existing table, column, enum value or
relationship was dropped or renamed.

| Table | Purpose |
| --- | --- |
| `strategic_objectives` | Objective, period (annual, quarterly, monthly), unit, direction, automatic KPI key and parameters or manual measurement, target, baseline, approval, owner, status |
| `objective_measurements` | Append-only manual values with evidence; corrections supersede, never overwrite |
| `strategic_initiatives` | Lightweight plan: objective, owner, dates, status, reported progress, priority, milestones, dependencies, risks, notes, linked project ids |
| `management_reviews` | Monthly, quarterly or annual review; immutable JSON snapshot once final; human executive summary; separate `ai_summary_draft` field |
| `management_actions` | Tracked follow-up: review, objective, initiative, project, owner, priority, due date, status, completion evidence, decision link |
| `management_events` | Append-only history for all four entities: comments, decisions, status, target and baseline changes, with actor and approver |

Enum additions:
- `ActivityAction`: `strategy_objective_changed`, `strategy_target_changed`,
  `strategy_initiative_changed`, `management_review_changed`, `management_action_changed`;
- `NotificationType`: `management_action_assigned`;
- `EntityType`: `strategic_objective`, `strategic_initiative`, `management_review`,
  `management_action`.

**Migration.**
- SQLite: the tables are created by the normal `Base.metadata.create_all` at startup.
- PostgreSQL: `app/db/phase113_management_schema_sync.py` adds the new enum values. It is registered
  in `app/main.py` as `phase113_management`.
- Copy check: on the working database copy, all 132 startup schema steps ran with no failures. No
  table was dropped, no column removed, and every existing table kept its row count. The six Phase 8
  tables were created empty.
- The copy also received additive columns from Phases 5–7 that the real database has not yet had,
  because the app has not been started on it since.

## 5. Dashboard and UI changes

There is a new page at `/management`, labelled "Management Cockpit" in the Operations navigation. It
is visible to users who can view reports, matching the backend gate. Tabs are addressable by URL
(`?tab=`):

- **Filter bar:**
  - financial year (April–March from company settings), customer, classification, project manager
    (the project's design leader; ProTrack has no separate project-manager field), team;
  - business unit, when any team has one;
  - an optional custom date range, which overrides the financial year once both dates are set.
- **Cockpit:**
  - business KPIs with a monthly invoiced-vs-collected chart and new-vs-repeat counts;
  - operations KPIs with a table setting quoted, approved-plan and actual hours side by side for
    *completed in period* and *active today*;
  - hours by stage;
  - workforce KPIs, skills distribution and gaps, and the 4-week bottleneck forecast (labelled
    forecast);
  - top customers.
- **Customers:** table with Finance columns only for Finance users. The profile shows contacts, Finance
  KPIs, delivery for the period and five-year history, observed signals with evidence,
  "not assessable" reasons, an FY trend, active projects, and forecasts in their own table.
- **Efficiency:** comparison by month, quarter, financial year, customer, classification, team or
  project manager, with classification mix, a fairness note, and effort by classification, customer,
  stage, task type and month.
- **Objectives:** list with target (marked *proposed* until approved), actual, progress against
  expected pace, owner status and suggested status. A detail dialog covers status with reason,
  target change and approval, manual measurement with evidence, comments and full history.
  **Initiatives** are listed below with create and update.
- **Reviews:** generate a draft for a month, quarter or year. The detail view has:
  - the human executive summary, with generated highlights shown separately;
  - the ten sections and a forecasts section;
  - comparison with the previous review;
  - decisions (optionally creating an action), discussion comments, and finalise.
- **Actions:** open, overdue, blocked and due-soon counts; filters for open-only and mine; create;
  owner or manager update with reason, evidence and comment.
- Every KPI card shows a kind chip (Actual, Approved plan, Forecast, Target, Manual entry, Baseline).
  Restricted sections show why they are hidden.
- Export buttons appear only with `export_reports`, and only for sections the user can see.

## 6. Strategic objectives implementation

### 6.1 Automatic and manual measurement

- **Automatic** objectives name a registry KPI (`management/kpis.py` `REGISTRY`): Finance,
  operations or workforce KPIs, with validated parameters such as customer, classification, team or
  skill.
  - The actual is calculated on read from the same services as the cockpit, for the objective's
    period. It is never stored or editable.
  - A manual value posted to an automatic objective is rejected with "calculated automatically".
    The update schema has no actual field.
- **Manual** objectives take values only with evidence and a period inside the objective period.
  Values are append-only; a correction supersedes the earlier entry. The latest entry is labelled
  *Manual entry* with who recorded it.

### 6.2 Targets, baselines and approval

- Unit and direction must match the KPI. "Lower is better" needs a baseline.
- A target set by someone without `approve_strategy` is *proposed* until approved.
- Changing a target or baseline needs `approve_strategy` and a reason. It records the approver and
  the old and new values in `management_events` and in the activity log
  (`strategy_target_changed`).
- Progress is `(actual − baseline) ÷ (target − baseline)`, or actual ÷ target without a baseline
  when increasing.
- Pace compares progress with elapsed time for cumulative measures (currency, count, hours). Level
  measures are compared with the target directly. It produces a *suggested* status only; the owner
  sets the real status, and at risk, delayed or cancelled need a reason.

### 6.3 Fair comparison

Efficiency analytics never rank individual designers. Comparisons are by period, customer,
classification, team or project manager, and always show the sample size and classification mix. The
fairness note explains that raw hours and project counts do not reflect complexity, scope, leave or
assignment, and must not be used for performance reviews.

## 7. Management review workflow

1. **Generate.** A user with `manage_strategy` creates a monthly, quarterly or annual review for a
   period that has started.
   - The snapshot is computed with org-wide calculation access, so every viewer sees the same
     figures, redacted to their permissions.
   - It holds ten sections: executive summary, financial, delivery, efficiency, customer, workforce,
     objectives, risks, decisions required and action items.
   - A separate forecasts section uses Phase 7 predictions and is never used in any actual figure.
2. **Draft.** Managers write the executive summary and may regenerate the figures. Generated
   highlights are shown separately and are never the official summary.
3. **Discuss and decide.**
   - Comments are open to anyone who can see reviews.
   - Decisions need `manage_strategy`. A decision can create a tracked action with owner, due date
     and priority, and the owner is notified.
4. **Finalise.** This needs `approve_strategy` and a human executive summary. After finalising, the
   snapshot and summary are frozen; later Finance or timesheet changes do not alter the review.
5. **History and comparison.**
   - Reviews list newest first.
   - Each review links to the previous review of the same type.
   - The comparison shows actual-to-actual KPI changes between two reviews; forecasts are not
     compared.

**AI and the summary.** The `ai_summary_draft` field exists and is labelled "draft – not reviewed".
No endpoint fills it yet. Management can ask the Assistant (§8), but its text never becomes the
review summary unless a person writes it in.

## 8. AI integration

Six read-only tools were added to the Phase 6 Assistant (`app/services/assistant/tools/strategy.py`).
They are registered in the existing tool registry and pass through the existing orchestrator. The
orchestrator checks `allowed()` before every call and filters the data before it is sent to the
provider.

| Tool | Needs | Answers |
| --- | --- | --- |
| `get_business_performance` | Finance view | FY or period revenue, collections, awarded, outstanding, top customers, plus objective targets shown as targets |
| `get_customer_performance` | Reports + customer in scope | Customer profile, observed signals, forecasts kept separate |
| `get_engineering_operations` | Reports | Delivery and efficiency, compare by period, customer or classification |
| `get_workforce_summary` | Resource Planning or HR | Capacity, utilisation, skills, bottleneck forecasts |
| `get_strategic_objectives` | Reports (values redacted by kind) | Objective progress, optionally behind-plan only |
| `get_management_focus` | Reports | Overdue and blocked actions, behind-plan objectives, top risks, forecast risk |

Every result includes:
- the period, with a *complete* flag and note;
- a kinds note separating actuals, plans, forecasts and targets;
- limitations;
- source references that link to the cockpit tab.

The tools return only figures the services calculated. The model receives no raw records and no
Finance data without Finance access. Suggested questions were added: FY performance, stage hours,
objectives at risk and management focus. Tests use the existing fake provider and never call a live
AI API.

## 9. Permission controls

All checks are enforced on the server in `management/access.py`; the UI only mirrors them.

| Capability | Rule |
| --- | --- |
| Open management reporting | Reports module (or Read-only / Planning Board roles) and a valid report scope |
| Project figures | The caller's project visibility clause and report team scope |
| Finance figures, columns, sheets, AI tool | Finance module `view` |
| Workforce figures | Resource Planning capacity view or HR view |
| Reviews | Organisation-wide report scope or `manage_strategy` |
| Create or edit objectives, initiatives, actions, reviews; record decisions | `manage_strategy` (new special permission; Engineering Manager default) |
| Approve targets, change targets or baselines, finalise reviews | `approve_strategy` (new special permission; Admin and executives) |
| Owner updates | Owners may change only status (with reason), reported progress, evidence and comments on their own items |
| Exports | `export_reports`, plus the Finance, workforce or review rule of the report |

Other safeguards:
- Restricted objective values (target, baseline, actual, progress) are removed for viewers without
  the matching access, in the API, the exports and review snapshots.
- Every change writes a `management_events` row, and non-comment changes also write an activity log
  entry.
- Exports are logged through `log_report_generation` (`module="management"`) with their filters.

## 10. Test results

Tests use deterministic data, with no live AI and no network.

| Brief test | Tests |
| --- | --- |
| 1 Financial-year filters | `test_management_cockpit::test_financial_year_and_sub_periods_follow_april_to_march`, `test_resolve_period_uses_company_fy_and_custom_range` |
| 2 Revenue vs collections | `test_business_keeps_awarded_invoiced_collected_and_outstanding_apart`, `test_payment_lead_time_uses_fully_paid_lines` |
| 3 Completed vs active | `test_operations_separate_completed_and_active_projects` |
| 4 Customer contribution | `test_customer_contribution_and_new_vs_repeat`, `test_customer_table_and_profile` |
| 5 Actual-hours aggregation | `test_booked_hours_count_only_approved_hours_in_period` |
| 6 Capacity | `test_capacity_uses_personal_hours_holidays_and_skips_virtual_users` |
| 7 Objective create and update | `test_management_objectives::test_automatic_objective_reads_finance_actual`, `test_owner_updates_status_with_reason_but_not_other_fields`, `test_objective_validation` |
| 8 Automatic KPIs | `test_automatic_objective_reads_finance_actual`, `test_progress_and_pace_rules` |
| 9 Manual KPIs and audit | `test_manual_values_never_overwrite_automatic_actuals`, `test_manual_measurement_with_audit_and_correction`, `test_target_changes_need_approval_and_record_the_approver` |
| 10 Initiatives | `test_management_actions::test_initiative_links_objective_and_existing_projects`, `test_initiative_permissions` |
| 11 Review generation | `test_management_reviews::test_review_generates_all_sections_with_forecasts_apart` |
| 12 Review history | `test_finalising_needs_human_summary_and_approval_then_freezes`, `test_review_history_and_period_comparison` |
| 13 Decisions and actions | `test_decisions_create_linked_actions`, `test_action_assignment_notifies_owner_and_completion_needs_evidence`, `test_action_visibility_and_reopening` |
| 14 Export filters | `test_management_exports` (5 tests: filtered export equals the cockpit, every report builds, permissions, redaction, stored review snapshot) |
| 15 Backend permissions | `test_cockpit_requires_reports_access`, `test_cockpit_hides_finance_and_workforce_without_access`, `test_customer_profile_hides_finance_and_out_of_scope_customers`, `test_objective_permissions_and_redaction`, `test_review_permissions_and_redaction`, export permission test |
| 16 AI data access | `test_management_assistant` (5 tests, including Finance never reaching the model without access) |
| 17 Regressions | Full suite, below |

Results:
- Phase 8 suites: 42 tests across `test_management_cockpit` (15), `_objectives` (8), `_actions`
  (4), `_reviews` (5), `_assistant` (5) and `_exports` (5). All pass.
- Assistant and predictive regression (`test_ai_assistant`, `test_predictive`): 68 passed.
- Full suite (disposable SQLite database; run 2026-11-03, 48 min 47 s): **1468 passed, 12 failed,
  1 skipped**.
  - The 12 failures are exactly the pre-existing baseline listed in
    `docs/PHASE0_QUOTE_TO_DELIVERY_AUDIT.md` §3.2: stale quote-PDF patch targets (4),
    receivables aging without a due date (2), un-invoice (2), the timesheet pack filename, duplicate
    timesheet weeks, fixed-resource overhead, and IT asset import.
  - There are no new failures. The pre-Phase 8 run was 1426 passed; the 42 extra passes are the new
    management tests.
- Efficiency analytics (brief part 4) is covered by
  `test_efficiency_groups_completed_projects_without_ranking_designers`. Filter validation is
  covered by `test_filter_validation_and_options` and `test_build_filters_rejects_unknown_values`.
- Frontend: `npx tsc -b` passes; `npm run build` succeeds; `npx eslint` on all new and changed files
  is clean. A pre-existing `react-refresh/only-export-components` error remains in
  `AppBreadcrumbs.tsx`, unchanged from the committed version.
- The browser check was skipped as instructed; validation relies on tests and the build.

## 11. Known limitations

- **No Finance records in the working database.** Every Finance figure, Finance signal and revenue
  objective will read "not available" until quotes, invoice lines and payment lines are entered.
- **No award status.** Quoted (pipeline) and awarded value cannot be separated; every active quote
  counts as awarded, as on the Finance dashboard.
- **Bulk completion stamps** and missing original baselines make completions *limited*, and leave
  on-time rate and delivery variance blank on the real data.
- **Capacity:**
  - planned leave and non-project commitments are not recorded;
  - no holidays are recorded for the current year;
  - no shift assignments exist, so capacity uses personal working hours.
- **Region and business unit** analysis need `Customer.country` and `Team.business_unit`, which are
  empty.
- **Rework before completion** is not separately identifiable; only post-completion work types
  count.
- **Objectives:**
  - the KPI of an objective cannot change after creation (cancel and recreate);
  - managers without `approve_strategy` cannot propose a target revision, only approvers can change
    targets;
  - KPIs that need parameters (for example, verified holders of a skill) can be created through the
    API but not yet from the UI form.
- **Reviews** have no in-app AI draft endpoint (§7).
- **Initiative milestones, dependencies, risks and linked projects** can be set through the API; the
  UI form covers name, objective, owner, target date, priority, status, progress and comments.
- **Payment lead time** depends on dated invoice and payment lines; legacy flag-only payments have
  no per-line dates.

## 12. Configuration

- **Financial year:** the start month comes from company settings (April by default). It is used by
  every filter, objective period and review period.
- **Permissions:** grant `manage_strategy` and `approve_strategy` in Users → special permissions.
  Defaults: Admin has both; executives (Managing Director, Directors) have both; Engineering Manager
  has `manage_strategy`. Existing saved permission lists receive these role defaults automatically.
  Exports need `export_reports`.
- **Data to enter for meaningful figures:**
  - quotes with invoice and payment lines;
  - original baselines on projects;
  - approved timesheets;
  - holidays and shift assignments;
  - a country on customers and a business unit on teams (optional).
- **Database:** no manual step. SQLite creates the tables at startup; PostgreSQL also runs the
  `phase113_management` enum sync. Take a backup before the first start on production, as for any
  release.
- **AI:** no new configuration. The tools use the Phase 6 provider settings and work with the
  provider disabled through suggested questions.

## 13. Recommended next increment

1. **Data readiness on the real database:** enter Finance lines, original baselines and approved
   timesheets. Then review the cockpit with Finance and Engineering to confirm the figures against
   their own records.
2. **Award status on quotes** (an additive field), so quoted pipeline and awarded value can be shown
   separately without changing the existing Finance rules.
3. **Target proposal workflow:** managers propose a target change and an approver accepts it, using
   the existing events table.
4. **Reviewed AI summary draft:** the Assistant fills `ai_summary_draft` from the snapshot only. A
   person edits it and copies it into the executive summary before finalising.
5. **UI for parameterised KPIs and initiative milestones and linked projects.**
6. **Planned-leave records,** so future capacity and utilisation forecasts can deduct them.
