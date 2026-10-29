# Phase 1, Step 3 — Quote-to-Delivery Management Reporting

Status: implemented on the existing data model. No schema change, no migration, no data
written. This is one reporting increment of Quote-to-Delivery Intelligence. It is not the
Engineering Control Tower and contains no forecasting or risk scoring.

## 1. Where it lives

* Screen: Reports → **Quote-to-Delivery** tab (`/reports?tab=quote-to-delivery`), after
  Engineering Performance.
* API: `GET /api/v1/reports/quote-to-delivery` (JSON, paginated project table) and
  `GET /api/v1/reports/quote-to-delivery/export.xlsx` (Excel, every matching row).
* Service: `app/services/reporting/quote_to_delivery.py`; schema
  `app/schemas/quote_to_delivery.py`; Excel `app/services/reporting/excel/quote_to_delivery.py`.

## 2. Single calculation source

Every per-project number comes from `ProjectEngineeringMetrics`, the payload the project
page's Engineering metrics panel shows. Step 3 split the existing builder into:

* `load_metric_inputs(db, projects)` — a fixed set of grouped queries (estimates,
  milestones, estimate revisions, `batch_calculate_hours`, hours by timesheet status, stage
  buckets, baseline histories, active quotes and their revisions) for any number of projects;
* `compute_project_metrics(project, inputs, …)` — the unchanged rules, with no database access;
* `build_project_engineering_metrics` (project page) and `build_engineering_metrics_batch`
  (report) both call the two above.

The report sums values and counts statuses only. React, the routes, the Excel writer and
SQL contain no hour, variance or delivery rule. The reconciliation script checks that the batch
payload is identical to the per-project payload for every project.

## 3. Populations and date fields

| Population | Selected by | Period applies | Delivery judged against |
|---|---|---|---|
| Completed (historical, default) | status Completed and `completed_at` in the period | Yes — actual completion date | Original approved baseline |
| Open (operational) | status Planning, In progress or On hold today | No | Current target date (due date, else current baseline) |

Cancelled and deleted projects are never included. Archived projects follow the Reports
page "Include archived" switch. Summary, project table and stage section use the selected
population. The delivery section always shows both, side by side and labelled: historical
results for completed-in-period and current overdue work for open projects. They are never
mixed. The status filter offers only open statuses, and only for the open population.

Period boundaries are inclusive calendar days on the stored `completed_at` (naive, as
stored): 00:00:00 on the first day through 23:59:59 on the last day. A project completed
at 23:59:59 on the baseline date has 0 days variance, because the completion date is
`completed_at`'s date, the same convention as Step 2 and Engineering Performance.

## 4. KPI definitions (also returned as `definitions` and shown as tooltips)

**Summary**

* Eligible projects — size of the selected population.
* Original quoted hours — Σ `quoted_hours` over projects that have them. Never added to estimates.
* Current approved estimate — Σ current estimate where the estimate source is approved
  stage estimates (including approved revisions) or milestone planned hours. Projects whose
  only estimate is quoted hours are excluded here and reported in `estimate_source_counts`.
* Actual hours — Σ known actual hours (non-deleted entries, any timesheet status, the Step 1
  rule). Completed projects with no hours are "missing" and excluded, not zero.
* Comparable project — approved estimate source, estimate > 0 and known actual hours.
* Aggregate variance = Σ actual − Σ estimate over comparable projects (positive = over).
* Utilization = Σ actual ÷ Σ estimate × 100 over comparable projects. It is never an average of
  percentages.
* Over / under / on estimate — comparable projects only. Everything else is "not in hour totals".
* Missing or incomplete metrics — `unavailable` (no estimate, or actual missing) and
  `limited` (calculated but with a data-quality warning). Incomplete data is not a risk rating.
* For open projects, variance and utilization are hours consumed to date, not a forecast. A
  warning on the screen and in the export says so.

**Project table** — per-project values exactly as on the project page, with the estimate
source label. Variance on a non-comparable row (for example measured against quoted hours) is shown
and marked "not in totals". Delivery variance is shown only for completed projects with an
original approved baseline. It is blank otherwise.

**Stage section** — one row per stage present in the population (configured by templates):

* Eligible for a stage = approved estimate for the stage, actual hours known, and stage
  attribution `complete` or `no_hours` (every hour linked to a staged milestone, or none
  booked yet).
* Σ approved stage estimate, Σ stage actual, variance and utilization over eligible projects only.
* Over stage estimate (eligible only), not attributable (has an estimate but not eligible),
  no estimate (stage present, no approved estimate — e.g. Feasibility).
* No stage estimate is inferred from quoted or project totals. Unattributed hours are never
  allocated. Each row explains why data is insufficient when it is.

**Historical delivery** (completed in period):

* Eligible = reference source `original_baseline` (first baseline revision, Step 2 rule).
* On or before baseline: variance ≤ 0. After baseline: variance > 0. Average and median days.
* Excluded and counted: baseline without revision history, due date only, no date.
* Completed projects with no completion date are counted (any period) and listed in a warning.
* Revised baselines are never used as the original commitment. This is stricter than the
  Engineering Performance delivery KPI, which includes labelled fallbacks.

**Current overdue work** (open, as of today):

* Projects with overdue milestones (milestone not completed, current target passed), number
  of overdue milestones, projects past their current target, projects without a current
  target, projects without an original baseline.

## 5. Filters

Reuses the Engineering Performance filter dependency (`_performance_filters`): period
(weekly, monthly, financial quarter or year, custom ≤ 5 years), customer, team, design leader / PM,
designer, project type, template, include archived. Authorization scope and project
visibility are applied in the same place. Added for this report: population,
`project_classification`, `status` (open only), `search` (code, tool number, part,
customer — table and export only), `segment` + `stage` (drill-down — table and export only),
`sort`, `page`, `page_size` (1–100). Filters intersect. An empty result returns 200 with
`empty_message` and zero counts, which the screen shows distinctly from a load error.

## 6. Export

`export.xlsx` takes the same query parameters and writes the same payload. Sheets: Summary,
Projects, Stages, Delivery, Definitions. The Projects sheet holds every row matching filters,
search and drill-down. Pagination is ignored, and the Summary states the row count and that the
export is not limited to the page. Headers carry units ("(h)", "(%)", "(days)"). Blank means
unavailable, not zero. Data quality and issue codes are per row. If rows would exceed an
Excel sheet, the API returns 422 rather than truncating. The export requires the
`export_reports` permission (backend-enforced) and is logged with `log_report_generation`.

## 7. Permissions

Router-level Reports access (`can_view_reports`). `resolve_report_scope` (team filter outside
scope is 403). `project_visibility_clause` is always ANDed. Filters can only narrow the result,
never widen it. Rows carry only project ids the caller can see, and the project-page link enforces
its own access. No Finance figures are returned (`finance_details_visible=False`; quote
linkage is not included in the payload).

## 8. Performance

The populations are loaded in two queries. Metrics for both use the bulk loader in chunks of
500 projects, with a constant number of queries per chunk (test asserts equal statement counts
for 3 and 10 projects). There is one query for undated completed projects and one set of name
lookups. Existing indexes cover every per-project lookup (`timesheet_entries.project_id`,
`milestones.project_id`, `project_baseline_revisions.project_id`,
`project_stage_estimates.project_id`, `projects.completed_at`), so no index was added.
Aggregation runs on the backend. The browser receives one page of rows.

## 9. Known limitations

* Stage hours depend on `TimesheetEntry.milestone_id`, which only the single-entry timesheet
  page sets. Projects booked through the weekly grid are "not attributable" by design.
* Original baselines exist only where `ProjectBaselineRevision` history exists. Older
  projects fall back to labelled references and are excluded from historical delivery.
* Project due-date changes are not versioned. "Current target" is today's value.
* Search, sort and drill-down run on the backend after metrics are computed for the whole
  filtered population. This is suitable for the current data size. Very large populations
  would need search pushed into SQL.
* On the current development data (24 projects) no project has stage estimates, booked
  hours or baseline history, so most metrics are correctly "unavailable".

## 10. Verification (29 Oct 2026, isolated test database)

* `tests/test_quote_to_delivery_report.py`: 15 passed. With the Step 1–2 metrics, stage/delivery,
  Engineering Performance and engineering-management suites: 75 passed.
* Full suite: 1261 passed, 12 failed, 1 skipped. The 12 failures are the pre-existing ones
  (quote PDF import, receivables, fixed overhead, historical/IT import, customer timesheet
  pack, invoicing); none are in reporting or metrics code touched here.
* `tsc -b` clean, ESLint clean on the changed files, `npm run build` succeeds.
* `scripts/engineering_metrics_reconciliation.py` on a copy of the database: 0 mismatches,
  batch payload identical to the per-project payload for 24/24 projects, completed
  population 15 = raw count 15, open population 2 = raw count 2.
* Browser check not performed (skipped at the user's request).
