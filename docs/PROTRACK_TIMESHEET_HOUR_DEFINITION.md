# ProTrack — Authoritative Definition of Actual Engineering Hours

Status: **in force** (Pre-Implementation Maintenance, 2026-11-02).
Code: `app/services/actual_hours.py`. Tests: `tests/test_timesheet_hour_definition.py`.

## 1. Definition

| Timesheet status | Official actual hours | How it is shown |
|---|---|---|
| **Approved** | **Yes** | The actual-hours figure |
| Submitted (awaiting approval) | No | Separately, as **provisional** hours |
| Draft | No | Listed as "draft (not counted)" |
| Rejected | No | Listed as "rejected (not counted)" |
| Entry with no timesheet record | No | Data-quality warning |
| Deleted entry (`is_deleted`) | No | Not shown |

* **Total effort** is every official hour booked to the project, billable or not.
* **Billable effort** is the subset of official hours where `is_billable` is true. It is never larger than the total.
* Hours worked after completion count, as before, and are still split by post-completion type.
* An entry belongs to exactly one timesheet. The rule is applied as `timesheet_id IN (approved timesheets)`, so joins to quotes, milestones or people cannot count an entry twice.
* When a timesheet is approved, its hours move from provisional to official. The sum of the two never changes.

No existing documented business rule established a different approved workflow. `docs/PHASE1_STEP1_ENGINEERING_METRICS.md` recorded the old all-statuses rule as "the current project rule" and left the status question as a pending **business decision**. This definition answers it.

## 2. One authoritative service

| Layer | Function | Role |
|---|---|---|
| Rule | `actual_hours.official_entry_clause()` / `provisional_entry_clause()` / `entries_on(statuses)` | The only place the status filter is defined |
| Project totals | `post_completion_work.hours_by_post_completion_type` → `project_calculation_service.calculate_hours` / `batch_calculate_hours` | Total, before and after completion, and the cached `Project.actual_hours` |
| Metrics | `engineering_metrics_service.load_metric_inputs` / `compute_project_metrics` / `build_engineering_metrics_batch` | Total, billable, provisional, the status breakdown and the stage split |

These modules consume the service and no longer apply a status filter of their own:

| Consumer | Path |
|---|---|
| Project page, project lists, project hours report | `calculate_hours` / `batch_calculate_hours` (`crud/project_metrics`, `crud/reports`, `reporting/data_service` project performance, `crud/dashboard` project detail, `command_center_service`) |
| Engineering metrics panel, stage split, contributors, milestone and stage-line actuals | `engineering_metrics_service`, `project_contributor_service`, `milestone_workspace_service`, `project_estimate_service` |
| Engineering Performance report (including the effort-by-function split) | `batch_calculate_hours` and `official_entry_clause` |
| Quote-to-delivery analytics | `build_engineering_metrics_batch` |
| Control Tower | `load_metric_inputs` + `compute_project_metrics` |
| Phase 3 effort and capacity forecasting | `build_engineering_metrics_batch` |
| Phase 7 hour predictions and outcome evaluation | `predictive/inputs.load_facts` → `build_engineering_metrics_batch`; resource-demand scoring and non-project shares use `official_entry_clause` |
| Phase 6 Assistant | `assistant/tools/projects._metrics` → `build_engineering_metrics_batch` |
| Dashboard total actual hours and post-completion counts | `official_entry_clause` |
| Working-model health (project-based, retainer, overheads) and provisional scheduler | `calculate_hours`, and `official_entry_clause` for milestone actuals |

## 3. What changed and the discrepancies it removed

| Module | Before | After |
|---|---|---|
| Project totals (`hours_by_post_completion_type`) and everything built on them | Every status (draft, submitted, approved, rejected) | Approved only |
| Stage split, contributors, milestone actuals, scheduler actuals | Every status | Approved only (they reconcile with the total again) |
| Engineering metrics `entry_count` / `actual.status` | Any entry made the status "recorded" | Only approved entries do. A completed project with only unapproved hours is **missing**, not zero |
| Engineering metrics data-quality codes | `includes_rejected_hours` (warning), `includes_unapproved_hours` | `provisional_hours_pending` (info), `unapproved_hours_excluded` (info) |
| `ActualHoursMetrics` | — | New `billable_hours` field (additive; existing fields unchanged) |
| Phase 7 resource-demand evaluation and non-project share | Every status except rejected | Approved only. Scoring waits while draft or submitted hours remain in the window, for at most 14 days after it ends, then records the excluded hours in the outcome note |
| Dashboard total actual hours | Every status | Approved only |
| User-facing explanations (Control Tower, Phase 3, Phase 7, Assistant, quote-to-delivery, project page) | "Draft, submitted and rejected hours count under the current project rule" | "Approved timesheet hours; submitted are provisional; draft and rejected are not counted" |

## 4. Impact assessment before the change

This was run read-only on a copy of `protrack.db` (`%TEMP%\maint_hours_impact.py`; the original file's timestamp was unchanged):

| Measure | Result |
|---|---|
| Timesheets | 4 (1 approved, 3 draft) |
| Non-deleted entries booked to a project | **0** |
| Live projects whose actual hours change | **0 of 24** |
| Projects whose stored `actual_hours` differs from the old rule | 0 |
| Duplicate entries / duplicate timesheets (same user and week) | 0 / 0 |

**Impact on real data: none.** Every project shows 0 actual hours under both rules, and no stored value changes. The change matters for future timesheets: draft and submitted hours no longer raise project actuals, variance, overrun findings or forecasts until they are approved.

## 5. Records and workflow — what was not changed

* No timesheet, entry or approval status was modified. The approval workflow (statuses, transitions, permissions, notifications) is unchanged.
* `Project.actual_hours` is a cache. It is rewritten by the existing triggers (`recalculate_project` after entry, milestone or project edits, and the admin "timesheet reconciliation" action). One trigger was added: because official hours now depend on approval, `timesheet_workflow_service` calls the same `recalculate_project` for the sheet's projects when a transition enters or leaves **approved**. In the current workflow approval is final (reject and return-to-draft are only allowed from submitted), so in practice this runs on approval. Without it the cache would stay at its pre-approval value until the next entry edit. **No bulk recalculation was run.** On real data it would change nothing (section 4).
* Historical prediction rows keep their stored values. Only new evaluations use the new rule.

## 6. Remaining discrepancies (period and person reports, intentionally unchanged)

These report hours worked **in a period by person, team or customer**. They are not project actual hours. They keep their current filters, which should be reviewed as a separate business decision:

| Report | Current filter | Note |
|---|---|---|
| Reporting engine period reports (`reporting/data_service._entry_base_filters`: designer, customer, team, tool hours) | Draft + submitted + approved | Shows work in progress for the period |
| Monthly team summary (`crud/team_reports`) | Draft + submitted + approved | Same |
| Cross-team hours (`reporting/cross_team_hours`) | Draft + submitted + approved | Same |
| Dashboard billable/non-productive split (`crud/dashboard`) | Approved only | Already consistent |
| Timesheet status report (`crud/reports`) | Lists approved / submitted / draft separately | A breakdown, not a total |
| Customer timesheet pack (`reporting/customer_timesheet_pack`) | Draft + submitted + approved (`_PACK_STATUSES`); inactive users excluded | A customer billing document: **not changed**, per the instruction not to alter billing calculations |
| Time-and-materials working model | Shows approved and submitted+approved separately; "billable" now follows the official total | Health indicator, not an invoice |
| Template reconciliation "milestone has hours" check | Every status | A safety check that blocks merging milestones with any booked time; deliberately broad |
| Scheduler first-entry date | Every status | Evidence that work started, not an hour total |
| Legacy AI modules (`services/ai/*`) | Their own filters | Not used by the Phase 6 Assistant or Phase 7 |

## 7. Tests

`tests/test_timesheet_hour_definition.py`:

| Required test | Test |
|---|---|
| Approved timesheet hours | `test_approved_hours_are_official` |
| Draft hours | `test_draft_hours_are_not_actual_hours` |
| Rejected hours | `test_rejected_hours_are_not_actual_hours` |
| Submitted / pending hours | `test_submitted_hours_are_provisional_not_official`, `test_completed_project_with_only_unapproved_hours_is_missing_not_zero` |
| Mixed-status project | `test_mixed_statuses_count_only_approved` |
| Billable vs non-billable | `test_billable_is_a_subset_of_total_effort` |
| Duplicate prevention | `test_approval_moves_hours_from_provisional_to_official_without_double_counting`, `test_joins_do_not_duplicate_hours` |
| Report and forecast regression | `test_reports_forecasts_control_tower_and_predictions_agree` (project page, batch totals, metrics, contributors, Phase 3 forecast, Phase 7 facts, Control Tower, cached `actual_hours`), `test_demand_outcome_waits_for_pending_approval` |

Through the API and the real approval workflow (`tests/test_project_hours.py`):
* an entry on a draft sheet leaves project actual hours at 0, and submit then approve makes them 8;
* edits and deletes after approval recalculate the total;
* a submitted sheet that is then rejected never adds hours.

Existing tests that asserted the old all-statuses totals were updated to the approved-only values:
* `test_engineering_metrics.py`: the status breakdown still sums to every non-deleted hour (51.75 h), and the official total is the approved 42.5 h.
* `test_stage_delivery_metrics.py`: total 32 h, with rejected hours excluded.
* `test_project_hours.py`, `test_timesheet_reset.py` and `test_imported_project_editable.py`: these now approve the sheet before expecting project hours.
