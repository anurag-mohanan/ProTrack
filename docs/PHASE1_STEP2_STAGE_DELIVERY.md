# Phase 1, Step 2 — Stage-wise Engineering Performance and Delivery Variance

Status: implemented on the existing data model. No schema change, no migration, no data
written. This is one increment of Quote-to-Delivery Intelligence, not the full capability.

## 1. Concepts kept separate

| Concept | Where it lives | Used for |
|---|---|---|
| Engineering stage | `Milestone.project_stage` (`feasibility`, `preliminary` = Blockout, `intermediate`, `final`, `completed`), set per template milestone | Stage-wise hours |
| Approved stage estimate | `ProjectStageEstimate` (Blockout, Intermediate Design, Final Design only); `original_hours` never overwritten; revisions in `ProjectEstimateRevision` | Stage variance |
| Milestone | `Milestone` (due date, baseline start/finish, completion) | Delivery variance |
| Timesheet task type | `TaskType` (per stream, `function_category`) — no stage link | Effort by classification |
| Project status | `Project.execution_status` | Completed / cancelled rules |

Templates decide which stages a project has. Seeded examples: General Mold Design has
Feasibility + three planned stages + unstaged File/BOM Release; Crest and Redoe map every
milestone to a planned stage; Sybridge, Lamko, TI Automotive, B & B, CAD Development,
Engineering Change, DFM, Surfacing, Fixture and Electrode templates have no stages.

## 2. Stage-wise actual hours

Lineage: timesheet entry → `milestone_id` → milestone's `project_stage`, same project only.
`milestone_id` is optional and is only captured on the single-entry timesheet page
(`/timesheets/:id/entries/new`); the weekly grid does not set it. Task types carry no
stage. There is therefore no other authoritative route to a stage.

Rules (`engineering_metrics_service.stage_hour_buckets`, `project_plan_stages`,
`stage_attribution_status`, `_stage_attribution`):

* Same entry population as project actual hours: every non-deleted entry, any timesheet
  status (rejected/draft/submitted counted and flagged, as in Step 1).
* Each entry lands in exactly one bucket: a stage, or unattributed (no milestone,
  milestone without a stage, milestone of another project / missing). Stage rows +
  unattributed = total. No proportional allocation.
* Only stages that exist for the project are listed (an estimate row, an active
  milestone with that stage, or booked hours). A stage missing from the plan is not shown
  as zero. Feasibility appears when the template has it, with "no approved estimate".
* Attribution status: `complete` (every hour staged), `partial` (some unattributed — stage
  actuals may be understated and are flagged), `unavailable` (no stages, or no hours
  linked to a staged milestone — stage actuals shown as Unavailable, not 0), `no_hours`.
* Missing project actuals (completed work, no hours) make stage actuals Unavailable.
* Each row: actual hours, % of project actual, data quality (`complete` / `limited` /
  `unavailable`) with the reasons.

## 3. Stage estimates and variance

Only `ProjectStageEstimate` is treated as an approved stage estimate. Per row: approved
(current) estimate, original estimate, variance = actual − estimate, utilization =
actual ÷ estimate × 100, remaining = estimate − actual. Missing estimate → all three
unavailable with a reason; zero estimate → variance/remaining shown, utilization not
applicable. The project estimate (quoted or milestone hours) is never split across stages.

## 4. Delivery dates available and rules (`delivery_variance_service.py`)

| Date | Source | Preserved? |
|---|---|---|
| Original project baseline completion | earliest `ProjectBaselineRevision` (revision 1 `new_completion_date`) | Yes, once a baseline exists |
| Current project baseline completion | `Project.baseline_completion_date` | Overwritten on re-baseline |
| Current project due date | `Project.due_date` | Edited in place; no history |
| Original approved project due date | — | **Not stored** |
| Project actual completion | `Project.completed_at` (date part) | Yes |
| Original milestone baseline finish | first `previous_milestones_json` snapshot holding it, else current baseline | Yes |
| Current milestone target | `Milestone.due_date`, else current baseline finish | Overwritten on re-baseline |
| Milestone actual completion | `completed_date`, else `completed_at` date part | Yes |

* Reference for early / on time / late = original approved baseline. Labels:
  `original_baseline`, `baseline_unverified` (baseline exists without revision history, or
  history starts after an earlier baseline), `current_due_date` (no baseline — original
  commitment unknown), `none`.
* Variance days = actual completion − reference (negative early, 0 on time, positive late).
* Completed work is never overdue. Incomplete work is overdue only when today is after its
  current target (due date — the date the project list, reports and dashboard already use).
* Dates compared as stored calendar dates, same convention as the Engineering Performance
  report and stage plan; "today" is the server date.
* No forecasts or predictions.

**Correction to Step 1:** Step 1 took the original baseline from the first revision's
*previous* date, which is empty for revision 1, so after a re-baseline it reported the
revised baseline as the original. `MilestoneReadiness.original_baseline_completion_date`
now comes from the shared delivery rule. `open_overdue` / `open_without_target_date` now
use the current target (due date first) instead of baseline-first.

**Known definition difference (unchanged):** the Stage Plan tab's milestone "overdue" flag
still uses current baseline finish first, then due date. They normally match because
baselining sets due dates; they differ only after a manual due-date edit.

## 5. Historical comparison (Engineering Performance report)

Existing fields, period rule (completed in period), filters and on-time KPI are
unchanged. The on-time definition text now states it uses the *current* baseline.
Added:

* Stage rows: eligible projects (approved estimate for the stage and `complete`
  attribution), average and median stage variance, number and % over estimate, stage share
  of actual hours (complete-attribution projects). Counts of complete / partial /
  unattributed projects and the eligibility rule are shown.
* Summary: delivery variance vs original baseline — average, median, early / on date /
  late counts, projects with a reference, and which reference was used.
* Project rows: original and current baseline completion, delivery reference, status,
  variance days, stage attribution status.
* Effort by classification: actual hours by task-type function category (+ "No task
  type"); sums to report actual hours.
* Export: columns appended (existing positions unchanged), same five sheets.

## 6. UI

* Project → Overview → Engineering hours card: stage table
  (Stage | Approved estimate | Actual hours | Variance | Utilization | Data quality) with
  "Not attributed to a stage" row and sign convention; new Delivery section with original
  baseline, current target, actual completion, schedule variance (labelled reference) and a
  milestone delivery table.
* Reports → Engineering Performance: delivery-variance KPI, stage estimate comparison
  table with project counts, effort-by-classification table, delivery variance column.
* Permissions unchanged: project endpoint uses `can_read_project`; report uses existing
  report scope.

## 7. Database

No schema change, migration, backfill or write. Reconciliation runs read-only on a copy.

## 8. Reconciliation on a copy of the dev database

`python scripts/engineering_metrics_reconciliation.py <copy>`: 24 projects, 0
mismatches (raw sum, project page rule, stage buckets, stage rows + unattributed,
completed-not-overdue, cached column). The dev data has no timesheet entries, no stage
estimates, no baselines and no re-baselines, so stage figures are `no_hours` with actuals
missing, and delivery uses the current due date for all 24 projects (15 completed early vs
due date, 6 completed without a completion date, 2 incomplete overdue, 1 cancelled). The
new rules are therefore proven by tests, not by production-like data.

## 9. Tests

`tests/test_stage_delivery_metrics.py` (18 tests) covering A–D; Step 1 test updated for
the stage-row contract (rows listed with actual Unavailable instead of hidden).

| Check | Result |
|---|---|
| Step 1 verification (metrics, Engineering Performance, engineering management suites) | 42 passed |
| New Step 2 tests | 18 passed |
| Full suite, isolated `DATABASE_URL` | 1246 passed, 12 failed, 1 skipped (1501 s) — the same 12 pre-existing failures recorded before Step 1 |
| Frontend `tsc -b`, eslint on changed files, `npm run build` | clean / clean / built |
| `protrack.db` last write time | unchanged (2026-10-29 12:20:48) |

Browser verification was not performed (no credentials provided).

## 10. Gaps and next increment

* Hours rarely carry a milestone (weekly grid has no milestone field) — stage actuals will
  be mostly `unavailable`/`partial` until milestone capture exists in the weekly grid.
* Original project due date is not preserved; only the baseline protects the commitment.
* No stage estimates for Feasibility or other stages.
* Stage Plan overdue flag precedence differs (see §4).
* Next: capture milestone/stage on weekly timesheet rows (with user decision on the
  default), due-date change history, and a per-customer/template comparison once
  attributed data exists.
