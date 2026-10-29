# ProTrack — Phase Verification, Release Gate and Phase 2 (Engineering Control Tower)

**Date:** 29 Oct 2026  **Code baseline:** commit `6f9c407` (Phase 1 Steps 2 and 3) plus two
uncommitted Step 3 frontend hunks in the working tree (see §1.3).
**Method:** code and tests are the source of truth; documents are supporting evidence only.
Every test run used an isolated database (`DATABASE_URL` pointing at
`%TEMP%\phase1_test_runtime.db`). Data checks ran on copies of `protrack.db`, opened
read-only. `protrack.db` itself was not written (its last write time stayed
`2026-10-29 12:20:48` throughout).

Result values: **PASS** (implementation plus appropriate tests or reconciliation),
**PARTIAL** (works, but one or more requirements are missing), **FAIL** (absent or demonstrably
incorrect), **NOT VERIFIED** (insufficient access, data, tests or evidence).

---

## 1. Baseline

### 1.1 Test baseline before any Phase 2 change

| Check | Command | Result |
|---|---|---|
| Full backend suite | `pytest -q -p no:cacheprovider -W ignore::DeprecationWarning` (isolated DB) | **1261 passed, 12 failed, 1 skipped** (40 min 34 s) |
| Phase 1 suites | `pytest tests/test_quote_to_delivery_report.py tests/test_engineering_metrics.py tests/test_stage_delivery_metrics.py tests/test_engineering_performance_report.py tests/test_engineering_management.py` | **75 passed** |
| Frontend type-check | `npx tsc -b` | 0 errors |
| Frontend build | `npm run build` | Passed |
| ESLint on Phase 1 files | `npx eslint <files>` | 0 problems (the repository-wide lint has pre-existing errors, see Phase 0 §3.1) |

### 1.2 Pre-existing failures (unchanged since Phase 0)

The 12 failures are exactly the Phase 0 set (Phase 0 report §3.2). None is in engineering
metrics, reporting or project code:

`test_connected_protrack_wave45::test_quote_extract_reports_ocr_unavailable_for_scanned_pdf`,
`test_customer_timesheet_pack::test_customer_timesheet_pack_api_export`,
`test_finance_quote_pdf_import::test_extract_quote_pdf_does_not_create_quote`,
`test_finance_wave1_closeout` (3 tests), `test_fixed_resource_overhead::test_team_salary_includes_non_primary_billable_when_no_primary_home`,
`test_historical_timesheet_import::test_duplicate_week_skip`,
`test_it_data_import::test_assets_commit_and_rollback_batch_only`,
`test_prosohm_quote_pdf_import::test_parse_prosohm_quote_golden_text`,
`test_quote_invoicing_notifier::test_is_invoiced_yes_no_and_revenue_date`,
`test_quote_manual_entry::test_quote_invoiced_date_set_and_clear`.

### 1.3 Working-tree risk

At 15:25:58 an external file sync (FreeFileSync state file `sync.ffs_db` changed at the same
moment) deleted individual lines from about 15 files and left
`app/services/reporting/engineering_performance.py` unparsable. The files were rebuilt by
replaying the recorded edits on top of the last commit, and every check in §1.1 was re-run
afterwards.

Phase 1 Steps 2 and 3 were then committed as `6f9c407` (16:23). That commit is missing two
Step 3 frontend changes that exist only in the working tree:
- the Quote-to-Delivery tab in `frontend/src/pages/ReportsPage.tsx`;
- the shared `downloadReportExcel` helper in `frontend/src/api/engineeringPerformance.ts`.

The committed `frontend/src/api/quoteToDelivery.ts` imports that helper, so **`6f9c407` alone
does not type-check**; the working tree does. **Recommendation:** commit those two files
(together with Phase 2), and exclude the repository from the file sync while work is in progress.

---

## 2. Phase 0 — Audit and foundation

Evidence: `docs/PHASE0_QUOTE_TO_DELIVERY_AUDIT.md` (Phase 0 report), `scripts/phase0_data_quality_audit.py`.

| # | Requirement | Evidence inspected | Verification method | Result | Outstanding issue |
|---|---|---|---|---|---|
| 0.1 | Architecture map | Phase 0 §2 (backend, frontend, DB, integrations) | Spot-checked against `app/main.py` lifespan, `app/api/v1/api.py`, `frontend/src/App.tsx` | **PASS** | — |
| 0.2 | Module-by-module audit | Phase 0 §4 (Projects, Timesheets, Resource planning, Skills), §6 Finance, §7 Reporting, §8 Permissions, §9 Automation | Read; findings re-checked in code where Phase 2 depends on them (milestone statuses, completion, health) | **PASS** | — |
| 0.3 | Quote-to-delivery lineage matrix | Phase 0 §5 | Read; lineage used by Phase 1 confirmed in `engineering_metrics_service.py` | **PASS** | Data-level reconciliation impossible (0 quotes in dev DB) |
| 0.4 | Calculation inventory and authoritative sources | Phase 0 §7 | Read; legacy duplicates still present (`frontend/src/utils/projectHoursMetrics.ts`, `projectCommandCenter.ts`, dashboard tiles) | **PASS** (as an inventory) | Duplicate legacy calculations remain in the product (see 1.10) |
| 0.5 | Data-quality findings | Phase 0 §10 | Re-run through `scripts/engineering_metrics_reconciliation.py` on a DB copy: 6 completed without date, 20 completed with open milestones, 24 unclassified, 0 project hours — **identical** | **PASS** | Nothing repaired (by design) |
| 0.6 | Permission and security findings | Phase 0 §8 | Re-checked in code today: S1 `app/api/v1/settings.py` router has no auth dependency; S2 `hr.py` `get_user_lifecycle` returns compensation `from/to` values with only `_require_performance_view`; S3 `timesheet_entries.py` `get_timesheet_entry` has no read check | **PASS** (findings documented) | **S1–S3 remain unfixed** (see §6) |
| 0.7 | Migration and data-preservation strategy | Phase 0 §12 | Read; used for the Phase 2 additive tables (§10) | **PASS** | — |
| 0.8 | Prioritised Phase 1 backlog | Phase 0 §14 | Compared with what was built | **PARTIAL** | P0 hotfixes B0.1–B0.5 not implemented; P1-1 (quote linkage), P1-4 (revision required for quoted-hours/due-date edits), P1-6 (finance) not started |
| 0.9 | Baseline and regression results | Phase 0 §3 | Reproduced: the same 12 failures today | **PASS** | — |
| 0.10 | Phase 1 recommendation | Phase 0 §15 | Read | **PASS** (documented) | The recommended order (hotfixes first) was not followed |

**Phase 0 hotfix status (verified in code, 29 Oct):**

| Item | Status | Evidence |
|---|---|---|
| B0.1 Authenticate settings GETs (S1) | **Open** | `settings.py` L66 `APIRouter(prefix="/settings")` with no dependency; `api.py` L159 mounts it without one |
| B0.2 Scope HR lifecycle (S2) | **Open** | `hr.py` L2290–2330 |
| B0.3 Scope timesheet-entry reads (S3) | **Open** | `timesheet_entries.py` L86–91 (`get_timesheet_entry` has no user check); list by `project_id` unscoped |
| B0.4 `project.name` crash | **Open** | `receivables_service.py` L111, L181; `customer_financial_service.py` L279, L414 |
| B0.5 Test-harness isolation and phase35 idempotency | **Open** (worked around) | `tests/conftest.py` still does not set `DATABASE_URL`; every run since Phase 1 sets it manually |

---

## 3. Phase 1 Step 1 — Shared engineering metrics

Evidence: `app/services/engineering_metrics_service.py`, `app/schemas/engineering_metrics.py`,
`GET /api/v1/projects/{id}/engineering-metrics`, `tests/test_engineering_metrics.py` (20 tests),
`docs/PHASE1_STEP1_ENGINEERING_METRICS.md`.

| # | Requirement | Evidence inspected | Verification method | Result | Outstanding issue |
|---|---|---|---|---|---|
| 1.1 | Original quoted hours distinct from current approved estimate | `resolve_estimate`; `EstimateMetrics.quoted_hours` / `original_estimate_hours` / `current_estimate_hours` | `test_revision_keeps_original_estimate_separate`; `test_engineering_management.py::test_estimate_revision_keeps_original_and_records_audit` | **PASS** | — |
| 1.2 | Quote revisions follow existing approval/award rules | `_quote_linkage` follows the `current_version/current_revision` pointer; inactive quotes never used | Metrics tests (inactive quote, pointer, ambiguous link) | **PARTIAL** | No quote status/award model exists, so "awarded" cannot be verified; ambiguous links are reported, not resolved |
| 1.3 | Actual hours use authoritative timesheet records and status rules | Σ non-deleted `timesheet_entries.hours` (any sheet status) = `calculate_hours` | Tests; reconciliation 24/24 projects 0 mismatches | **PASS** | **Open decision:** draft and rejected hours are included (project-page rule); period reports exclude rejected sheets |
| 1.4 | Duplicate joins do not inflate actuals | Grouped queries; entry→milestone many-to-one | `test_status_rules_deleted_entries_and_join_duplication` (several quotes, stage rows and milestones on one project) | **PASS** | — |
| 1.5 | Variance = actual − applicable approved estimate | `hour_metrics` | 100/80 → −20 h; 100/120 → +20 h | **PASS** | — |
| 1.6 | Utilization correct | actual ÷ estimate × 100, half-up | Tests | **PASS** | — |
| 1.7 | Missing vs zero estimate | `unavailable` vs `not_applicable` | Tests | **PASS** | — |
| 1.8 | Remaining hours consistent | estimate − actual, negatives kept | Tests | **PASS** | — |
| 1.9 | Project page, APIs and reports use consistent definitions | Project metrics endpoint, Engineering Performance and Quote-to-Delivery share `resolve_estimate` / `stage_hour_buckets` / the metrics builder | `test_rows_reconcile_with_project_metrics_endpoint`; reconciliation "batch identical 24/24" | **PARTIAL** | Legacy surfaces still use their own rules: dashboard tiles, Projects-list KPIs (`projectHoursMetrics.ts`), command-center KPIs (quoted vs cached actual) |
| 1.10 | Metrics in a shared backend service | `engineering_metrics_service.py` (`load_metric_inputs` + `compute_project_metrics`) | Code | **PASS** | — |
| 1.11 | Backend permissions enforced | Same project read check as the stage plan | Tests: 401/403/404/422; quote details hidden without Finance access | **PASS** | — |
| 1.12 | Historical source records not rewritten | Service is read-only | `test_reading_metrics_does_not_modify_source_records`; `protrack.db` unchanged | **PASS** | Pre-existing phase35 startup step still rewrites one team description on every app start (outside metrics) |

---

## 4. Phase 1 Step 2 — Stage-wise performance and delivery variance

Evidence: `app/services/delivery_variance_service.py`, stage buckets in
`engineering_metrics_service.py`, `tests/test_stage_delivery_metrics.py` (18 tests),
`docs/PHASE1_STEP2_STAGE_DELIVERY.md`.

| # | Requirement | Evidence inspected | Verification method | Result | Outstanding issue |
|---|---|---|---|---|---|
| 2.1 | Configured stages respected | Stage rows only for stages in the project's plan | `test_stage_without_estimate_and_configurable_stage_set`, `test_template_without_stages_has_no_stage_rows` | **PASS** | — |
| 2.2 | Entries attributed via authoritative relationships | `timesheet_entries.milestone_id → milestones.project_stage` (same project only) | Tests; invalid cross-project link not staged | **PASS** | Only the single-entry timesheet page sets `milestone_id`; the weekly grid and imports do not |
| 2.3 | Σ stages + unattributed = total | Buckets | `test_stage_rows_and_unattributed_hours_reconcile_to_total`; reconciliation | **PASS** | — |
| 2.4 | Missing attribution ≠ zero | Stage actual `null` when unattributable | `test_missing_actual_hours_are_not_zero_in_stage_rows` | **PASS** | — |
| 2.5 | Stage estimates only when authoritative | `has_approved_estimate`; no allocation from totals | Tests | **PASS** | Dev DB: 0 stage estimates |
| 2.6 | Stage variance/utilization correct | `test_stage_under_and_over_estimate`, `test_zero_stage_estimate_has_no_utilization` | Tests | **PASS** | — |
| 2.7 | Original baselines preserved | First `project_baseline_revisions.previous_*` is the original | `test_revised_baseline_never_replaces_the_original`, `test_baseline_history_predating_revisions_is_unverified` | **PASS** | Dev DB: 0 baseline revisions |
| 2.8 | Current target distinct from original commitment | `ProjectDelivery.current_target_date` vs `original_baseline_completion_date` | Tests | **PASS** | Project `due_date` edits are not versioned |
| 2.9 | Completion dates not inferred from due dates | `project_completion_date` = `completed_at` date only | `test_completion_dates_follow_stored_calendar_date`; 6 undated completed projects reported as `completion_date_missing` | **PASS** | — |
| 2.10 | Historical variance only with reliable dates | Only `original_baseline` reference counts in the historical KPI | `test_historical_delivery_variance_uses_original_baseline` | **PASS** | — |
| 2.11 | Completed projects not currently overdue | `_classify` | `test_completed_project_is_never_overdue` | **PASS** | — |
| 2.12 | Project/customer workflows not broken | Full suite | 1261 passed; failures pre-existing | **PASS** | — |

---

## 5. Phase 1 Step 3 — Management reporting

Evidence: `app/services/reporting/quote_to_delivery.py`, `app/api/v1/reports.py`
(`/reports/quote-to-delivery`, `/export.xlsx`), `QuoteToDeliveryPanel.tsx`,
`tests/test_quote_to_delivery_report.py` (15 tests), `docs/PHASE1_STEP3_QUOTE_TO_DELIVERY_REPORT.md`.

| # | Requirement | Evidence inspected | Verification method | Result | Outstanding issue |
|---|---|---|---|---|---|
| 3.1 | Project metrics displayed correctly | Rows built from the shared metrics payload | `test_rows_reconcile_with_project_metrics_endpoint` | **PASS** (API) | **NOT VERIFIED in a browser** (skipped at the user's request) |
| 3.2 | Quoted vs approved estimates distinguishable | Separate totals; quoted-only projects excluded from estimate totals | `test_summary_sums_hours_and_never_averages_percentages` | **PASS** | — |
| 3.3 | Aggregate actuals reconcile with timesheets | Σ row actuals = summary | Test; reconciliation script | **PASS** | — |
| 3.4 | Aggregate variance from the correct population | Comparable projects only | Test | **PASS** | — |
| 3.5 | Utilization from aggregate hours | Σactual ÷ Σestimate | Test | **PASS** | — |
| 3.6 | Stage reporting states its eligible population | Eligibility rule + counts | `test_stage_section_counts_only_eligible_projects` | **PASS** | — |
| 3.7 | Historical vs current overdue separated | Two delivery blocks | `test_operational_overdue_work_is_separate_from_history` | **PASS** | — |
| 3.8 | Historical reporting uses completion date | `completed_at` in period, inclusive | `test_period_selects_by_actual_completion_date_inclusive` | **PASS** | — |
| 3.9 | Filters consistent | Customer, classification, status, period, team, PM/designer | `test_filters_intersect_and_empty_result_is_not_an_error`, `test_filters_cannot_widen_project_scope` | **PASS** | — |
| 3.10 | Data-quality limitations visible | Per-row status/issues, warnings | Tests | **PASS** | — |
| 3.11 | Export matches filtered population | All matching rows, not the page | `test_export_contains_every_matching_row_not_just_the_page` | **PASS** | — |
| 3.12 | Export totals reconcile with display | Same payload | Same test | **PASS** | — |
| 3.13 | Report and export permissions | Reports access + scope; `export_reports` | `test_reports_module_and_export_permission_are_enforced` | **PASS** | — |
| 3.14 | Empty result ≠ API failure | 200 + `empty_message` vs error state | Test; UI code | **PASS** (API) | UI state not verified in a browser |
| 3.15 | Existing workflows still operational | Full suite; `test_engineering_performance_report_still_serves` | 1261 passed | **PASS** | — |

---

## 6. Summary of findings

**Critical blockers for Phase 2 (core alerts):** none. The metrics the first alerts need
(actual hours, approved estimate, milestone status and target date, project status) are
implemented, shared and tested.

**Open security defects (High, pre-existing, not in the Control Tower's data path):** S1
unauthenticated settings reads; S2 HR lifecycle exposes compensation values; S3 timesheet
entry readable by id without scope; plus the `project.name` crash (B0.4). They do not block
the Control Tower, but **ProTrack must not be declared production-ready until B0.1–B0.4 are
fixed.** They were not fixed in this task: each changes behaviour outside the scope of
this phase and needs its own regression check (for example, the login page's use of settings).

**Non-critical defects:** legacy surfaces with their own hour/variance rules (1.9); quote award
status missing (1.2); weekly grid never sets `milestone_id` (2.2); project due-date edits not
versioned (2.8); phase35 startup rewrite (1.12).

**Missing tests:** browser/UI checks for all three Phase 1 screens; Playwright e2e (needs
credentials); the Phase 0 security items (no tests until they are fixed).

**Historical data limitations (dev DB copy):** 24 projects; 0 project timesheet entries; 0
stage estimates; 0 estimate or baseline revisions; 0 quotes; all 168 milestones lack a target
date usable for delivery; 6 completed projects have no completion date; 20 completed projects
still have open required milestones.

**Changes made during verification:** none to business logic. The working tree was restored
after the external sync (§1.3).

---

## 7. Real-data reconciliation (read-only, DB copy `%TEMP%\qtd_reconcile_copy2.db`)

`python scripts/engineering_metrics_reconciliation.py <copy>`:

- 24 projects, **0 mismatches** between metrics actual, raw entry sum, `calculate_hours`,
  stage buckets and the cached `projects.actual_hours`.
- Bulk metrics loader identical to the per-project payload: **24/24**.
- Quote-to-Delivery: completed population 15 = raw 15; open population 2 = raw 2; quoted
  1845.00 h / 400.00 h; actual 0 (missing, not zero); comparable 0.
- Delivery: 15 completed projects all measured against a due date only (no baseline), 6
  undated; 2 open projects past their current target.

| Representative case | Available in dev data? | Check |
|---|---|---|
| Complete estimate and timesheet history | **No** (0 project entries, 0 stage estimates) | NOT VERIFIED with data; covered by tests |
| Missing estimate or stage information | Yes (all 24) | Reported as unavailable / quoted-only — PASS |
| Completed project | Yes (21) | Not overdue; 6 flagged undated — PASS |
| Overdue milestone | **No** (no milestone has a target date) | NOT VERIFIED with data; covered by tests |
| Revised due date or estimate | **No** (0 revisions) | NOT VERIFIED with data; covered by tests |

Service-level reconciliation stands in for API/UI totals: every route calls the same service
with no extra calculation. The authenticated UI was not checked (no credentials; browser
check skipped by the user).

---

## 8. Release gate

### Gate A — required for all Phase 2 alerts

| Prerequisite | Status | Evidence |
|---|---|---|
| Reliable project identity and status | **Met** | `projects.id`, `execution_status`; populations tested in Step 3 |
| Correct project access permissions | **Met** | `project_visibility_clause` + `resolve_report_scope`; Step 3 scope tests |
| Consistent definition of actual hours | **Met within the shared service** | One rule in `engineering_metrics_service`; the draft/rejected decision is still open, so every finding shows the status split |
| Reliable approved-estimate source | **Met where it exists** | Stage estimates or milestone planned hours. Quoted-hours-only projects are **not** treated as approved (consistent with Step 3) |
| Reliable milestone status and target date | **Met where dates exist** | Step 2 `milestone_delivery` (target = due date, else baseline finish; cancelled / not-applicable skipped) |
| Completed and cancelled handling | **Met** | Step 2 `_classify`; Step 3 populations |
| Automated tests for alert calculations | **Met** for reused metrics; new rules need Phase 2 tests | — |
| Auditable reason for every alert | To be built | Phase 2 requirement |

### Gate B — specific alerts

| Alert | Prerequisite | Status | Decision |
|---|---|---|---|
| Overdue milestone | Milestone status + target date | Met | **Implement** |
| Realized estimate overrun | Approved estimate + known actuals | Met where present | **Implement** (approved sources only) |
| Project past current target | Project status + current target | Met | **Implement** |
| Data-quality blockers | Existing issue codes | Met | **Implement** (informational) |
| Forecast overrun | Credible remaining-effort calculation | **Not met**: stage-plan forecast is provisional (one person × effort hours/day); Phase 0 §4.6 heuristic floors | **Defer** |
| Forecast delivery risk | Validated completion forecast | **Not met**: same scheduler, ignores capacity | **Defer** |
| Stage-specific overrun | Stage estimates + attributed actuals | Model met; data absent; weekly grid does not attribute | **Defer** (stage view already in Step 3 report) |
| Historical schedule performance | Original baselines | Met in model, 0 rows in data | Not an alert; stays in Step 3 report |
| Resource bottleneck | Availability, calendars, assignments, demand, skills, leave | **Not met**: no leave model, no allocation model, heuristic demand (16 h / 40 h floors), fixed role shares, skills dormant | **Defer** |
| Statistical / ML prediction | Historical outcomes | **Not met** (0 project hours) | Not attempted |

### Gate C — quality

| Requirement | Status |
|---|---|
| Regression failures understood and isolated | **Met**: 12 known failures, none in scope |
| No unresolved critical permission defect | **Met with exceptions**: no Critical-rated defect; High S1–S3 open outside the Control Tower data path (§6) |
| No destructive database changes | **Met**: Phase 2 adds three new tables only (§9.9) |
| No duplicate source of truth for metrics | **Met**: Phase 2 reuses the shared metrics and delivery services |
| No fabricated historical data | **Met** |
| No unverified production-ready claim | **Met**: not production-ready (§6) |

### Decision

**Proceed with Phase 2 for overdue milestones, realized estimate overruns, projects past
their current target, and data-quality findings. Defer forecast overrun, forecast delivery
risk, stage-specific overrun and resource bottlenecks.** Fixing B0.1–B0.4 remains a release
condition for production, not for this increment.

---

## 9. Phase 2 — Engineering Control Tower (first increment)

### 9.1 Verification status

Phase 0 and Phase 1 are verified as described in §2–§5. Phase 0 is complete as an audit, but its
P0 hotfixes are still open. Phase 1 Steps 1–3 pass on code and tests; their remaining gaps are
§3 1.2 and 1.9, §4 2.2, and the browser check, which was not run. The Control Tower first
increment is implemented and tested (§9.10). **It is not production-ready**, for the reasons in §9.12.

### 9.2 Evidence

Tests (§9.10), reconciliation on a disposable copy (§9.11), the additive-table check with
row-count and content-hash comparison (§9.9), `tsc`, `eslint` on the new files, and the
production build.

### 9.3 Defects

Found and fixed during this increment:
- The command center's "Delayed milestone" risk counted cancelled and not-applicable
  milestones, and ignored the baseline finish date when a milestone had no due date. Both
  checks now use the Step 2 definitions (§9.8).
- The command center's "Project overdue" risk ignored the baseline completion date when a
  project had no due date. Fixed the same way.

Found and not fixed (out of scope): S1–S3 and B0.4 (§6); legacy hour/variance surfaces (§3 1.9).

### 9.4 Gate decision

See §8. Implemented: overdue milestones, projects past their current target, realized estimate
overrun, and seven data-quality checks. Deferred: forecast overrun, forecast delivery risk,
stage overrun, resource bottleneck.

### 9.5 Files

| File | Change |
|---|---|
| `app/models/control_tower.py` | New: `ProjectRiskEvaluationRun`, `ProjectRiskFinding`, `ProjectRiskFindingEvent` |
| `app/models/models.py` | Registers the three models (import only) |
| `app/services/control_tower_service.py` | New: rule catalogue, evaluator, persistence, read model |
| `app/schemas/control_tower.py` | New: API payloads |
| `app/api/v1/control_tower.py`, `app/api/v1/api.py` | New router `/api/v1/control-tower`, registered |
| `app/services/delivery_variance_service.py` | Shared helpers `project_current_target`, `milestone_current_target`, `is_milestone_skipped`, `is_milestone_overdue` (existing functions now use them; behaviour unchanged) |
| `app/services/command_center_service.py` | Overdue and delayed-milestone risks use the shared helpers |
| `app/services/working_model/resolver.py` | `resolve_working_models_for_projects` (same precedence as the single-project resolver, two queries) |
| `app/services/job_queue.py`, `app/jobs/runner.py` | Job type `control_tower_evaluation`; `python -m app.jobs.runner --control-tower` |
| `frontend/src/components/reports/ControlTowerPanel.tsx` | New Control Tower tab content |
| `frontend/src/api/controlTower.ts`, `frontend/src/types/ControlTower.ts` | New API client and types |
| `frontend/src/pages/ReportsPage.tsx` | "Control Tower" tab after Quote-to-Delivery (this file also carries the uncommitted Step 3 tab, §1.3) |
| `tests/test_control_tower.py` | 16 acceptance tests |

### 9.6 Rules

The catalogue is in `control_tower_service.RULES`; the API returns it, and the UI shows it under
"Rules, severity and deferred alerts". Every rule reads the shared metrics payload
(`compute_project_metrics`) and the Step 2 delivery rows. No metric is recalculated.

| Rule | Category | Condition (summary) | Severity |
|---|---|---|---|
| `milestone_overdue` | schedule | Milestone not completed/cancelled/not applicable; evaluation date > current target (due date, else baseline finish) | High if required, Medium if optional |
| `project_past_target` | delivery | Project open (planning / in progress / on hold); evaluation date > current target (due date, else baseline completion) | Critical |
| `estimate_overrun_realized` | effort | Approved estimate (stage estimates or milestone planned hours) > 0, actual recorded, actual **>** estimate | High |
| `dq_approved_estimate_missing` | data_quality | Overrun applies to the working model, but there is no approved estimate (quoted-only or none) | Informational |
| `dq_actual_hours_incomplete` | data_quality | Issue `actual_hours_missing` or `entries_without_timesheet` | Informational |
| `dq_stage_attribution_incomplete` | data_quality | Stage-estimated, hours recorded, attribution partial or unavailable | Informational |
| `dq_quote_link_unresolved` | data_quality | Issue `quote_link_ambiguous` or `quote_revision_unresolved` | Informational |
| `dq_milestone_target_missing` | data_quality | Open milestones without a due date or baseline finish (one finding per project) | Informational |
| `dq_project_target_missing` | data_quality | Open project without a due date or baseline completion | Informational |
| `dq_original_baseline_unavailable` | data_quality | Current target exists, but there is no verified original baseline | Informational |

**Applicability:** rules tied to a `ProjectRiskType` run only where the project's working model
allows that type, the same filter as the command center. Retainer and T&M projects get no
overrun rules; Overheads projects get no schedule or delivery rules.

**Population:** open projects (planning, in progress, on hold) that are not deleted or archived.
Completed and cancelled projects are not evaluated, and their open findings resolve.

**Deferred rules** (shown in the UI with reasons): forecast overrun, forecast delivery risk,
stage overrun, resource bottleneck (§8 Gate B).

### 9.7 Severity and metric rules

- **Scale:** Critical > High > Medium > Informational. Values follow the existing command
  center conventions (overdue = critical, delayed milestone = high, hours over quote = high).
  Medium is used only for optional milestones.
- **Fixed severities:** severity never escalates over time. "Days past target" is shown as
  evidence instead, so the ranking stays predictable.
- **Actual hours:** the project rule, which counts all non-deleted entries of any sheet status.
  Every overrun finding shows the approved, draft-or-submitted and rejected split, because the
  draft/rejected decision is still open.
- **Dates:** the evaluation date is the server's `date.today()`, the same as the rest of the app.
  "Overdue" means strictly after the target date; a target of today is not overdue.
- **Risks vs data quality:** findings are kept separate by `category = data_quality`. Data-quality
  findings are always Informational and never count toward risk totals.
- **Not assessable:** if a risk finding's inputs disappear, the open finding becomes
  `not_assessable` rather than being resolved. Examples are a deleted milestone due date, an
  estimate removed, or actual hours becoming missing. A new finding is never opened from missing data.

### 9.8 API and UI changes

- `GET /api/v1/control-tower` is read-only and never evaluates.
  - Access: Reports access (`can_view_reports`). Rows are clipped by
    `project_visibility_clause` and the report team scope, the same as the other project reports.
  - Parameters: `view` (risks / data_quality / resolved), `severity`, `category`, `status`,
    `project_id`, `owner_id` (or `unassigned`), `search`, `page`, `page_size` (≤ 100). All
    filtering and paging happen in SQL.
  - Response: `state` (never_evaluated / running / last_run_failed / stale / ok) with a message,
    the latest and last successful runs, summary counts, owner and project filter options from
    visible findings only, the rule catalogue, deferred rules, `can_evaluate` and
    `can_acknowledge`, and `empty_message`.
- `POST /api/v1/control-tower/evaluate` requires `edit_projects` and re-evaluates every open
  project.
  - Returns 409 if a run is in progress. A run older than 15 minutes is treated as abandoned.
  - Returns 500 if the run fails. Earlier findings are kept and the state shows `last_run_failed`.
- `GET /api/v1/control-tower/findings/{id}` returns the finding and its event history. Returns
  404 when the project is outside the caller's scope.
- `POST /api/v1/control-tower/findings/{id}/acknowledge` requires `edit_projects` and a visible
  project. It records who and when, plus an optional note, and adds an `acknowledged` event.
  It never resolves the finding. Returns 409 if already acknowledged or resolved.
- **Background:** job type `control_tower_evaluation` in the existing queue.
  `python -m app.jobs.runner --control-tower` queues and runs one evaluation, for a daily Windows
  Task Scheduler entry. No scheduler is installed by this change, and no emails, notifications
  or tickets are sent.
- **Command center:** the "Delayed milestone" and "Project overdue" risks now use the shared
  overdue definitions (§9.3).
- **UI:** Reports → "Control Tower" tab.
  - A state banner gives a distinct message for never evaluated, running, failed, stale and
    up to date. A failed or missing evaluation is never presented as zero risks.
  - Severity KPI cards act as filters. There are Risks / Data quality / Resolved views; filters
    for severity, category, status, project, owner and search; and a server-paginated table.
  - Each row expands to show the explanation, evidence lines, recommended action, rule, owner and
    owner basis, acknowledgement, and history.
  - Projects link to `/projects/{id}` and milestones to `/projects/{id}?tab=milestones`.
  - "Evaluate now" and "Acknowledge" appear only when the API says the user may use them, and
    the API enforces the same rules.
  - Loading, error and empty states are separate.

### 9.9 Database changes and preservation

- **Additive only:** three new tables, `project_risk_evaluation_runs`, `project_risk_findings`
  and `project_risk_finding_events`, created by the existing `Base.metadata.create_all` at
  startup. No existing table, column, enum or relationship is changed.
  - A partial unique index `(tenant_id, finding_key) WHERE status != 'resolved'` prevents
    duplicate open findings at database level.
- **Why new tables:** no existing model can hold findings with a stable key, first and last
  evaluation times, an open/resolved lifecycle, acknowledgement and audit history.
  `Notification` is per user, `ProjectRiskItem` is computed on read, and `StockAlert` is IT
  inventory.
  - The design follows the `StockAlert` episode pattern: one row per episode, and a recurrence
    opens a new row linked by `previous_episode_id`.
  - Acknowledgement history lives in its own event table. That avoids adding values to the
    shared `ActivityAction`/`EntityType` enums, which would need a migration on Postgres.
- **Disposable copy test:** `protrack.db` was copied twice.
  1. `create_all` on the work copy added exactly the three tables.
  2. Two evaluations were run (§9.11).
  3. `scripts/compare_db_row_counts.py` logic compared the copies: **166 pre-existing tables,
     0 differing in row count or content hash**. Key counts were unchanged: projects 24,
     milestones 168, timesheet_entries 2, users 14, customers 9.
  4. Orphan findings 0, orphan events 0.
- **Rollback**, tested on the copy: drop the three tables, in the order events, findings, runs,
  and remove the router registration. After dropping them, the copy compared identical to the
  baseline on all 166 tables. Alternatively, stop calling `/evaluate`; nothing else reads the
  tables.
- `protrack.db` was never opened by the application or the tests (last write time
  `2026-10-29 12:20:48`).

### 9.10 Tests

`tests/test_control_tower.py`, 16 tests, all passing (`16 passed in 31.04s`):

| §20 area | Tests |
|---|---|
| Overdue milestones | `test_overdue_milestone_rules`: past due, due today (not overdue), future, completed, cancelled, not applicable, optional → Medium, baseline-only target, undated → data quality, owner from assignee or design leader. `test_cancelled_and_completed_projects_are_not_evaluated` (on-hold still evaluated) |
| Estimate overrun | `test_realized_overrun_uses_approved_estimate_and_never_changes_it`: over, exactly equal (no finding), under, quoted-only → data quality, estimates and quoted hours unchanged. `test_overrun_respects_working_model` (retainer) |
| Delivery risk | `test_project_past_target_shows_current_and_original_separately`: current target vs verified original baseline, target moved 18 days, no target → data quality, dates unchanged |
| Lifecycle | `test_lifecycle_no_duplicates_update_resolve_and_recur`, `test_missing_inputs_make_a_finding_not_assessable_instead_of_resolved`, `test_findings_resolve_when_project_closes`, `test_failed_evaluation_keeps_findings_and_is_never_shown_as_clean`, `test_concurrent_evaluation_is_refused`, `test_acknowledgement_is_recorded_and_audited` |
| API and permissions | `test_api_views_filters_pagination_and_summary`, `test_get_never_writes`, `test_permissions_in_api` (no Reports access → 403; out-of-scope project hidden from list, filter, options and detail → 404; evaluate and acknowledge → 403 without `edit_projects`; unauthenticated → 401) |
| Performance and regression | `test_evaluation_uses_a_constant_number_of_queries` (2 vs 12 projects, same statement count); `test_command_center_uses_shared_overdue_definitions` |

The resource-bottleneck rule is not implemented, so it has no tests.

Other checks: `ruff check --select F,I,E9` clean on all new and changed backend files (the
pre-existing I001 in `command_center_service.py` was left as it was); `npx tsc -b` 0 errors;
`npx eslint` on the new frontend files 0 problems; `npm run build` passed.

**Full regression** (isolated test database, after all Phase 2 changes):
`pytest -q -p no:cacheprovider -W ignore::DeprecationWarning` gave **1277 passed, 12 failed,
1 skipped** in 42 min 37 s. That is the baseline 1261 + 16 new tests, and the 12 failures are
exactly the pre-existing set in §1.2. Afterwards the test-touched `data/health_history.json` and
`docs/IT_IMPORT_RESULT.md` were restored, the test-created
`Backups/Before_Historical_Reimport_20261029_1721.db` was deleted, and `protrack.db` was
confirmed unchanged (last write `2026-10-29 12:20:48`).

### 9.11 Reconciliation (disposable copy of `protrack.db`)

| Run | Projects evaluated | Opened | Updated | Resolved | Open |
|---|---|---|---|---|---|
| 1 | 2 | 10 | 0 | 0 | 10 |
| 2 (immediately after) | 2 | **0** | **0** | **0** | 10 |

Findings (10 rows, 10 distinct keys, 2 projects): `project_past_target` Critical ×2,
`dq_actual_hours_incomplete` ×2, `dq_approved_estimate_missing` ×2,
`dq_milestone_target_missing` ×2, `dq_original_baseline_unavailable` ×2.

These agree with the Step 3 reconciliation (§7): 2 open projects, both past their current target;
no approved estimates, so no overrun can be assessed; actual hours missing; no milestone target
dates, so `milestone_overdue` cannot fire on this data; due dates only, no baselines. The
milestone-overdue and realized-overrun rules therefore have **no real-data confirmation yet**;
only the tests in §9.10 cover them.

### 9.12 Limitations

- **Not production-ready.** B0.1–B0.4 (S1–S3 and the `project.name` crash) are open. The
  authenticated UI was not checked in a browser. No scheduled job is installed, so findings go
  stale unless someone presses "Evaluate now" or schedules the runner, and the UI then shows
  "stale".
- Draft and rejected hours count toward actuals (open decision). Overrun findings show the split.
- Owners are the milestone assignee or the project design leader; there is no project-manager
  field. Findings without either show "Unassigned".
- Severity does not escalate with age, by design (§9.7).
- Forecast, stage and resource rules are deferred (§8).
- Real data cannot exercise milestone-overdue or overrun findings (§9.11).
- No email, notification or ticket is generated. That was required ("no duplicate notification
  system"), but it also means nobody is alerted unless they open the tab.

### 9.13 Next increment

1. Fix B0.1–B0.4 and B0.5 (test isolation), then run a browser check of the Control Tower and
   the Quote-to-Delivery tab with a signed-in user.
2. Decide the draft/rejected-hours rule for actuals.
3. Set milestone due dates and approve baselines on open projects so the schedule rules have data.
4. Install a daily scheduled run (`python -m app.jobs.runner --control-tower`), then consider an
   opt-in digest through the existing notification engine, sent once per new finding and never
   repeated.
5. Revisit the deferred rules once the weekly grid attributes hours to milestones (stage overrun)
   and a capacity or leave model exists (resource bottleneck, forecasts).
