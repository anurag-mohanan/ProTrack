# Phase 1, Step 1 — Engineering Metrics Foundation

**Date:** 29 Oct 2026  **Builds on:** `docs/PHASE0_QUOTE_TO_DELIVERY_AUDIT.md`

This increment adds one shared, read-only calculation of a project's approved estimate, actual hours, variance, utilization and remaining estimate. Each value comes with explicit data-quality indicators. The results appear on the project workspace (Overview tab).

This is **not** full Quote-to-Delivery Intelligence:
- no forecasting or risk scoring;
- no Finance changes;
- no schema changes.

---

## 1. Authoritative sources (verified in code)

| Metric | Source | Rule |
|---|---|---|
| **Original quoted hours** | `projects.quoted_hours` | Shown as recorded. Set from stage hours at creation; stage-estimate revisions do not change it (confirmed by `test_estimate_revision_keeps_original_and_records_audit`). |
| **Original estimate** | `project_stage_estimates.original_hours` | Σ original stage hours + planned hours of non-skipped milestones outside the three stages. Without stage estimates: `quoted_hours`, else milestone planned hours. Never overwritten. |
| **Current approved estimate** | `project_stage_estimates.current_hours` | Σ current stage hours (original + approved revisions, which need the *Revise estimates* permission and a reason) + other milestone hours. Fallbacks: `projects.current_planned_hours` (milestone planned hours), then `quoted_hours`. **This is the existing Engineering Performance report rule, now shared.** |
| **Actual hours** | `timesheet_entries` | Σ `hours` where `project_id = P` and `is_deleted = false`, for any timesheet status and date, including post-completion hours. This is the existing rule of the project page (`calculate_hours`), the Contributors panel and the Engineering Performance report. |
| **Stage actual hours** | `timesheet_entries.milestone_id → milestones.project_stage` | Counted only when the milestone belongs to the same project. |
| **Milestone dates** | `projects.due_date` (current target), `projects.baseline_completion_date` (current baseline), `project_baseline_revisions` (first `previous_completion_date` = original commitment), `milestones.completed_at` / `completed_date` | Read only. |
| **Finance quote** | `quotes` (`is_active = true`, `project_id = P`) + `quote_revisions` at the quote's `current_version` / `current_revision` pointer | Cross-check only. **Never used as the estimate.** |

### Finance quotes and estimate selection

**Quote status.** `Quote` has no status or "awarded" flag. The only selection rule the codebase supports is `is_active`, so inactive quotes are never selected.

**Ambiguous links.** When more than one active quote is linked to a project, there is no rule for choosing between them. The service reports `quote_link_ambiguous` and uses none of them.

**Missing revision.** When the quote's current pointer matches no stored revision, the service reports `quote_revision_unresolved`. It does not fall back to the newest revision. Some Finance services do fall back, but they disagree with each other on how.

**Hours mismatch.** When the quote's hours differ from the project's quoted hours, the service reports `quote_hours_differ` (project quoted hours are copied from the quote once and never re-synced).

**Visibility.** Quote number, revision and quote hours are returned only to users with Finance (Financial Planning) view access. Everyone else sees only the link status.

---

## 2. Calculation rules

| Value | Formula | Unavailable when |
|---|---|---|
| Hour variance | actual − current estimate (positive = over estimate) | no estimate, or actual hours missing |
| Estimate utilization | actual ÷ current estimate × 100 | no estimate or actual missing (*unavailable*); estimate = 0 (*not applicable*) |
| Remaining estimated hours | current estimate − actual; **negative values are kept** (overrun) | as for variance |
| Variance vs original | actual − original estimate | as for variance |

- **Rounding.** Results are rounded to 2 decimals, half-up, matching `project_calculation_service._round_hours`.
- **Shape of each value.** Every value is a `{value, status, reason}` object. `value` is `null` whenever `status` is not `available`, so the UI never shows a fabricated zero.
- **Not a forecast.** These are performance indicators, not forecasts. The stage plan's EAC/forecast is separate and unchanged.

### Actual hours: missing vs. genuine zero

| Status | Condition | Effect |
|---|---|---|
| `recorded` | ≥ 1 non-deleted entry | Total shown |
| `none_recorded` | No entries, project not completed and no completed milestones | Total = 0 (genuine zero) |
| `missing` | No entries, but the project is completed or has completed milestones | Total = `null`; variance, utilization and remaining unavailable |

### Stage attribution

Each non-deleted entry lands in exactly one bucket, because entry → milestone is many-to-one, so joins cannot double-count:

- **Planned stage:** a milestone of this project in Blockout, Intermediate Design or Final Design.
- **Other stage:** a milestone of this project in another stage.
- **No stage:** a milestone of this project with no stage.
- **No milestone:** the entry has no milestone.
- **Invalid milestone:** the milestone belongs to another project or no longer exists.

The buckets always sum to the project's actual hours. Status values:

| Status | Meaning | Stage rows shown? |
|---|---|---|
| `complete` | all hours are on staged milestones | Yes |
| `partial` | some hours are unattributed | Yes, with an explicit "Not attributed to a stage" row and a warning |
| `unavailable` | no stage plan, or no hours on staged milestones | No |
| `no_hours` | stage plan exists but no hours | No |

Hours are **never** spread across stages.

### Data-quality indicators

These are kept separate from project health and risk.

**Overall status:**
- `unavailable`: no estimate, or actual hours missing.
- `available_with_limitations`: any warning-level issue.
- `available`: otherwise.

**Issue codes:**

| Category | Codes |
|---|---|
| Estimate | `estimate_unavailable`, `estimate_zero`, `estimate_from_milestone_plan`, `estimate_from_quoted_hours`, `quoted_hours_differ_from_original` |
| Actual hours | `actual_hours_missing`, `no_hours_recorded`, `includes_rejected_hours`, `includes_unapproved_hours`, `entries_without_timesheet` |
| Stage attribution | `stage_attribution_partial`, `stage_attribution_unavailable`, `invalid_milestone_link` |
| Delivery and completion | `completed_without_date`, `open_milestones_on_completed_project`, `original_commitment_unavailable` |
| Finance quote | `quote_unlinked`, `quote_link_ambiguous`, `quote_revision_unresolved`, `quote_hours_differ` |

---

## 3. Code changes

| File | Change |
|---|---|
| `app/services/engineering_metrics_service.py` (new) | `resolve_estimate`, `stage_hour_buckets`, `hour_metrics`, `build_project_engineering_metrics` (read-only; never writes to the session) |
| `app/schemas/engineering_metrics.py` (new) | Response schema |
| `app/api/v1/project_planning.py` | `GET /api/v1/projects/{id}/engineering-metrics` (same project read check as the stage plan: 404 for unknown/deleted, 403 outside the user's scope, 401 unauthenticated) |
| `app/services/reporting/engineering_performance.py` | Uses the shared `resolve_estimate` and `stage_hour_buckets` instead of its own copies, so the report and the project page share one definition |
| `frontend/src/components/projects/workspace/ProjectEngineeringMetricsPanel.tsx` (new) | "Engineering hours" card on the project Overview tab: estimate, actual (with status split), variance, utilization, remaining, stage table when reliable, dates, quote link, data-quality notes, definition tooltips |
| `frontend/src/components/projects/workspace/ProjectWorkspace.tsx` | Renders the panel on Overview |
| `frontend/src/api/projectPlanning.ts`, `frontend/src/types/projectPlanning.ts` | Fetcher, query key and types |
| `tests/test_engineering_metrics.py` (new) | 20 tests (see §5) |
| `scripts/engineering_metrics_reconciliation.py` (new) | Read-only reconciliation against a DB copy |
| `scripts/compare_db_row_counts.py`, `scripts/count_merge_suffix.py` (new) | Read-only DB comparison tools used to check data preservation |

**API compatibility:** additive only. No existing endpoint or response changed.

**Engineering Performance behaviour change:** hours booked to *another project's* milestone are now counted as unstaged instead of under that milestone's stage. This affects only invalid links, and project totals are unchanged.

**Database changes:** none. No migration, column or persisted total was added.

---

## 4. Reconciliation results

### Automated, in tests

- **Same project, same numbers.** The metrics endpoint returns the same estimate, actual hours, variance and plan source as the Engineering Performance report row for that project.
- **Actual hours.** Metrics actual = `calculate_hours` (project page) = Σ Contributors panel hours = Σ timesheet-status split.
- **Stages.** Σ stage rows + unattributed buckets = actual hours.
- **Excluded entries.** Deleted entries are excluded. Rejected and draft entries are included (existing rule) and flagged.
- **Read-only.** Calling the endpoint leaves these source values unchanged: project quoted, actual, health and `updated_at`; entry count and sum; stage estimates.

### Development database

Run on a read-only copy (`python scripts/engineering_metrics_reconciliation.py <copy>`):

- **24 projects checked; 0 mismatches** between metrics actual, the raw entry sum, `calculate_hours`, the stage buckets and the cached `projects.actual_hours`.
- **All 24 are `unavailable`.** Each has completed milestones (or is completed) but no project timesheet entries, so actual hours are reported as *missing*, not zero. All use quoted hours as the estimate, and none is linked to a Finance quote.
- **Other issues found:** 20 completed projects have open required milestones, and 6 have no completion date.

### Known, expected differences (not changed)

- **Period reports exclude rejected sheets.** The reporting engine (`reporting/data_service._entry_base_filters`) drops entries on rejected timesheets, so its period hours can be lower than project actual hours whenever rejected hours exist. The definitions differ; neither was altered.
- **Stage-plan variance is forecast-based.** The stage plan's "variance" is EAC − plan, not actual − plan. It is labelled as a forecast there.
- **Legacy frontend calculations remain.** `projectHoursMetrics.ts` and the command-center KPIs still use `quoted_hours` against the cached `actual_hours`. They were not touched, to keep this increment small.

---

## 5. Tests

`tests/test_engineering_metrics.py` covers:

- **Calculation rules.** 100/80 gives −20 h, 80%, 20 h remaining. 100/120 gives +20 h, 120%, −20 h remaining. A missing estimate is unavailable; a zero estimate is not applicable; missing actuals differ from a genuine zero; decimal half-up rounding.
- **Estimate selection.** An approved revision keeps the original separate. Inactive quotes are never selected. The quote revision pointer is followed, and the quote never replaces the estimate.
- **Aggregation.** Status rules; deleted entries excluded; multiple quotes, stage rows and milestones don't inflate totals; designer, stage and project totals reconcile; an entry on another project's milestone is not staged.
- **API and permissions.** Complete-data values; missing-data indicators; other-team access gives 403/404; unknown project 404; malformed id 422; deleted project 404; unauthenticated 401; quote details hidden without Finance access.
- **Reconciliation and safety.** Agrees with the Engineering Performance report; source records unchanged.

### Results

| Check | Command | Result |
|---|---|---|
| New tests | `python -m pytest tests/test_engineering_metrics.py -q -p no:warnings -p no:cacheprovider -p no:logging` | **20 passed** |
| Full backend suite (isolated `DATABASE_URL`) | `$env:DATABASE_URL="sqlite:///<TEMP>/phase1_test_runtime.db"; python -m pytest -q -p no:warnings -p no:cacheprovider --tb=line -p no:logging tests` | **1228 passed, 12 failed, 1 skipped** (37 min 22 s). The 12 failures are exactly the pre-existing Phase 0 set (§3.2 of the Phase 0 report); there are no new failures. |
| Frontend type-check | `npx tsc -b` | 0 errors |
| Frontend build | `npm run build` | Passed |
| Lint on changed frontend files | `npx eslint <changed files>` | 0 problems |
| Authenticated UI in a browser | — | **Not verified**: no login credentials were available to the agent |

---

## 6. Test-harness safety defect found during this step (pre-existing)

**The test suite writes to the real development database.** `tests/conftest.py` swaps `SessionLocal` but not `app.db.session.engine`, and `with TestClient(app)` runs the full startup lifespan (`app/main.py`) against `DATABASE_URL`, which defaults to `./protrack.db`. Every API test therefore runs, against the dev database:
- `create_all`, the ~100 schema-sync steps and the seeds;
- the lifecycle due-applies, quote reminders and SLA sweep.

**Measured impact (read-only comparison against `Backups/`):**
- Row counts are identical in all 166 tables, from 19 Oct to now.
- Content differs in only three tables: `teams`, `team_commercial_terms` and `org_departments`.
- The changed columns are `updated_at`, `teams.description` and `team_commercial_terms.notes`.

**Root cause of the text change.** `app/db/phase35_overhead_team_merge_schema_sync.py` appends " [merged into Corporate / Management]" to the inactive *Management* team's description and its commercial-terms notes **on every startup**. Normal app restarts do this too, not just tests. The suffix count grew from 6,072 (7 Sep) to 15,950 (19 Oct) to 17,256 now (~1 MB of text per field). Test runs made today added 588 of these.

**What changed in this step.** No repair was made, in line with the audit rules. Regression runs from now on use `DATABASE_URL` pointing at a disposable file (`%TEMP%\phase1_test_runtime.db`); during that run `protrack.db` was confirmed unchanged.

**Further side effect.** The historical-import tests copy whichever database `DATABASE_URL` points to into `Backups/` (`historical_timesheet_folder_import_service`, `timesheet_reset_service`). That is how the `Backups/…2026-10-29_*.db` files dated today were created.

**Recommended fix (small, separate change, needs approval):**
1. In `tests/conftest.py`, set `DATABASE_URL` to a temporary file before `app` is imported.
2. Make phase35 idempotent: append the suffix only when the merge actually happens.
3. Trim the repeated suffix in the two fields, after a backup and with owner approval.

---

## 7. Remaining gaps and next increment

- **Rejected and draft hours.** Rejected hours count toward project actual hours (current project rule) but not toward period reports. **Business decision needed:** should actual hours exclude rejected sheets everywhere? The service is ready to apply one rule centrally.
- **Quote status.** There is no quote status ("awarded"), so quoted vs awarded can't be separated. Multiple active quotes per project can't be resolved.
- **Quoted hours sync.** `projects.quoted_hours` is never re-synced from the quote or from estimate revisions. Direct edits bypass revision history and are flagged when they differ from the original stage total.
- **Historical data.** All 24 dev projects lack timesheet hours, stage estimates and baselines. Historical stage attribution cannot be reconstructed. For new projects, require a milestone on productive entries of staged projects (setting-controlled) to make stage hours reliable from now on.
- **Original due date.** It is not stored. Only baseline revisions preserve the original commitment.
- **Other surfaces.** Projects list KPIs, dashboard and command-center hour tiles still use their own calculations (see Phase 0 §7). Routing them through this service is the natural next step.

**Recommended next increment.**
1. After a decision on rejected and draft hours, route the dashboard, team/customer reports and Projects-list hours through this service.
2. Fix the test-harness isolation and the phase35 defect.
3. Add the optional milestone requirement for productive entries on staged projects.
