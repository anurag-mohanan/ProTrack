# ProTrack Phase 0 — Codebase Audit, Data Integrity & Intelligence Foundation

**Audit date:** 29 Oct 2026  **Code baseline:** commit `21103a5` (branch `rca/shared-regression-recovery`)
**Scope:** read-only audit. No business records, schema or financial rules were changed.
Phase 1 (Quote-to-Delivery Intelligence) is **not** implemented here.

Evidence labels used throughout:

| Label | Meaning |
|---|---|
| **Confirmed (run)** | Reproduced by running the app, the test suite or a query against a disposable DB copy |
| **Confirmed (code)** | Traced in source with file/line evidence; not exercised at runtime |
| **Unverified** | Plausible from code reading but not confirmed; needs a test or real data |
| **Not testable** | Blocked by missing data, credentials or environment |

---

## 1. Executive summary

ProTrack is a large, mostly working modular monolith (FastAPI + SQLAlchemy + React/TypeScript). 1,208 of 1,221 backend tests pass. The building blocks for Quote-to-Delivery Intelligence exist: projects, quotes with revisions, invoice and payment ledger lines, timesheets with milestone/stage attribution, stage estimates with revision history, baselines, and a capacity grid. **However, the data linking them is not yet trustworthy enough to build intelligence on.**

The biggest risks, in priority order:

1. **Security gaps that should be fixed before any new analytics layer** (§8):
   - six settings endpoints answer without authentication — **confirmed (run)**;
   - salary history is readable by almost any employee through HR lifecycle — **confirmed (code)**;
   - timesheet entries can be read by id or project without scope checks — **confirmed (code)**.
2. **No single definition of "actual hours" or "variance"** (§7). The project page counts every non-deleted timesheet entry, including rejected and draft sheets. Period reports exclude rejected sheets. Several dashboards read a cached column. Variance is `original − quoted` in some places and `actual − quoted` in others.
3. **The quote → project link is weak** (§5, §6):
   - the link is a nullable `quotes.project_id`, matched on tool number only (not customer);
   - quotes have no status (every active quote is treated as awarded);
   - `Project.quoted_hours` is copied from the quote at most once and never re-synced.
4. **Finance reporting uses three different revenue-recognition rules** (§6). It also sums mixed currencies in receivables and project summaries. Code paths that reference a non-existent `project.name` will crash once a quote is linked to a project (confirmed: `Project` has no `name` attribute).
5. **The development database cannot support data-level reconciliation** (§3.4). Every Finance table is empty. There are 2 timesheet entries, neither on a project. All 24 projects are legacy imports: unclassified, no template, and 20 of the 21 "completed" projects still have open required milestones. **Every finance and hours lineage finding is therefore code-level only.**
6. **There is no scheduler** (§9). "Scheduled" automations (quote reminders, lifecycle applies, SLA sweep) run only at application startup or when triggered manually.
7. **CI runs 2 of 214 backend test files** and no frontend checks.

### Verified readiness (vs. the initial assessment)

| Area | Initial assessment | Verified status | Key evidence |
|---|---|---|---|
| Project health & risk indicators | Partially implemented | **Partially implemented — inconsistent** | Health is calculated (`project_calculation_service.calculate_project_health`) but can also be set manually and is then overwritten; only refreshed on events; cancelled projects turn red; ≥5 different "at risk" definitions; `/ai/health` raises `TypeError` |
| Quote-to-delivery data linkage | Partially implemented | **Partially implemented — weak, unverifiable with current data** | Nullable `Quote.project_id`, tool-number-only matching, no quote status, quoted hours copied once; 0 quotes in dev DB |
| Resource capacity planning | Partially implemented | **Partially implemented** | Shift- and holiday-aware daily grid exists; no leave model, no allocation model, heuristic remaining effort (16 h / 40 h floors), `max_allocation_percent` unused, scheduling ignores capacity |
| Finance linkage | Partially implemented | **Partially implemented — reporting inconsistencies** | Quote-centric ledger works; three revenue rules, mixed-currency sums, `project.name` crash, `ProjectFinancialSnapshot` never written, no credit notes, invoice/payment writes not audited |
| Employee skills matrix | Basic | **Basic (three disconnected systems)** | Stream skill matrix used only for a warn-only fit check; foundation `Skill`/`UserSkill` dormant (0 rows); no verification history or project requirements |
| Workflow automation | Partially implemented | **Partially implemented** | Ticket/onboarding/IT provisioning are idempotent and audited; reminders, digests and report schedules have no scheduler; no rule engine |
| Preferred starting point | Audit first | **Confirmed correct** | Data relationships and calculation definitions must be fixed before intelligence features |

---

## 2. Architecture map

### 2.1 Repository layout

| Path | Contents |
|---|---|
| `app/` | FastAPI backend: `main.py`, `api/v1/*` (~60 routers), `api/public_v1.py` (API-key public API), `core/` (config, auth, permissions, access control), `crud/`, `services/` (business logic, `reporting/`, `finance/`, `ai/`, `working_model/`), `models/` (`models.py`, `finance.py`, `foundation.py`, `it_operations.py`, `resource_shifts.py`, `training.py`, `intelligence.py` …), `schemas/`, `db/` (session, tenant filter, 103 `phase*_schema_sync.py` migrations), `jobs/runner.py` |
| `frontend/` | Vite + React 19 + TypeScript + MUI v9 + TanStack Query v5; `src/pages`, `src/components`, `src/api`, `src/utils`, `src/context`; Playwright specs in `frontend/e2e/` |
| `tests/` | 214 pytest files, in-memory SQLite fixtures (`tests/conftest.py`) |
| `alembic/` | Single baseline revision `001_r1_baseline.py` (create_all on empty DB only) |
| `deploy/` | `Dockerfile` (python 3.13-slim, uvicorn, no frontend build), `docker-compose.yml` (Postgres 16 + API), `README.md` |
| `.github/workflows/ci.yml` | Two pytest jobs (see §3.3) |
| `docs/` | Existing ADRs, audits, UAT checklists (this report lives here) |
| `scripts/` | Operational scripts; this audit adds `scripts/phase0_data_quality_audit.py` |

### 2.2 Backend

- **Startup (`app/main.py` `lifespan`, ~L324–628).** The steps run in this order:
  1. Production security assertion.
  2. `Base.metadata.create_all`.
  3. About 100 `phase*_schema_sync` steps, each wrapped in try/except. Failures are only logged, so the app can start on a partially migrated schema.
  4. Reference seeds.
  5. FX refresh.
  6. Lifecycle, compensation and offboarding due-applies.
  7. Quote invoicing and payment reminders.
  8. Ticket SLA sweep.
- **Migrations.** The real mechanism is the additive startup phase-sync scripts. Alembic contains only a baseline, although `deploy/README.md` tells operators to run `alembic upgrade head`.
- **Database.** `app/db/session.py`: `DATABASE_URL` defaults to `sqlite:///./protrack.db`, and PostgreSQL is supported. The active dev configuration is SQLite. A tenant filter (`app/db/tenant_filter.py`) applies to SELECTs, falling back to the default Prosohm tenant.
- **Enums.** 56 columns use `Enum(native_enum=False)` (stored as VARCHAR); 36 models use free-text status strings.
- **Authentication.**
  - HS256 JWT, 480-minute tokens stored in `localStorage`; token-version revocation; lockout (5 attempts / 30 minutes); rate-limited login.
  - Optional OIDC (Entra) SSO; Admin impersonation.
  - `get_current_user` lives in `app/api/auth_deps.py`.
- **Authorization.** `require_roles`, `require_module_action`, `require_special` (`auth_deps.py`); data scope (`core/data_scope.py`); team scoping (`core/team_access.py`); module defaults (`core/access_control.py`).
- **Logging and audit.** `RequestLoggingMiddleware`; `activity_service.log_activity` (old/new values); a weaker `finance._audit` (new value only); HR compensation changes are recorded only as `UserJobEvent`.
- **Background work.** `services/job_queue.py` (email and import jobs, 3 retries) runs through FastAPI `BackgroundTasks`, the CLI runner or a manual Ops action. **There is no periodic scheduler.**

### 2.3 Frontend

- Entry is `src/main.tsx`, then `App.tsx`. Providers: QueryClient, then Auth, Theme, Toast, then BrowserRouter.
- Route guards: `ProtectedRoute`, `ModuleRoute`, `RoleRoute`, `AdminRoute`.
- `context/AuthContext.tsx` re-syncs permissions every 60 seconds and on window focus.
- `api/client.ts` is an axios client with a Bearer token.

**Business logic duplicated or living only in the frontend:**
- `utils/projectCommandCenter.ts`: overdue, due-this-week (Monday–Sunday), and portfolio KPIs computed over at most 100 loaded rows.
- `utils/projectHoursMetrics.ts`: a frontend-only EAC and hours colour thresholds. Its docstring contradicts the code.
- Mirrors of backend calculators: `utils/financeScenarios.ts`, `utils/financeWhatIf.ts`, `utils/timesheetLocking.ts`.

### 2.4 Integrations

| Integration | Implementation | Notes |
|---|---|---|
| PDF/document parsing | pdfplumber / pypdf | Available |
| OCR | `pdf2image`, `pytesseract` | **Not installed** in this environment (`/health` → `document_import.optional`) |
| Email | SMTP engine | Synchronous inside the HTTP request; queue retry is manual |
| FX rates | Live refresh at startup | — |
| Outbound webhooks | Signed delivery with retries | Only the Admin "ping" emits events |
| Public API | API-key authenticated | — |

---

## 3. Baseline test results

All commands were run from the repository root on Windows (Python 3.13 / miniconda, Node via npx).

### 3.1 Commands and results

| Check | Command | Result |
|---|---|---|
| Backend test suite | `python -m pytest -q -p no:warnings -p no:cacheprovider --tb=line -p no:logging tests` | **1208 passed, 12 failed, 1 skipped** (37 min 31 s) — Confirmed (run). *Note:* this run used the default `DATABASE_URL`, so app startup inside the tests wrote to `protrack.db` (see §16 correction). |
| Frontend type-check | `cd frontend; npx tsc -b` | **Pass, 0 errors** |
| Frontend build | `cd frontend; npm run build` | **Pass** (`vite build`) |
| Frontend lint | `cd frontend; npx eslint src` | **163 errors, 56 warnings** — 86 `react-hooks/set-state-in-effect`, 56 `exhaustive-deps`, 35 `only-export-components`, 21 `preserve-manual-memoization`, 9 `refs`, 5 unused vars. All are pre-existing style/hook rules; no new code in this audit. |
| Backend startup | `uvicorn app.main:app` with `DATABASE_URL` set to a **disposable copy** of `protrack.db` | Started; `GET /health` → 200, `database: ok`. Startup logs repeated harmless `phase71 … cannot drop sqlite_autoindex` messages. |
| API reachability | Unauthenticated `GET /api/v1/projects`, `/finance/quotes`, `/reports/engineering-performance`, `/hr/users/{id}/lifecycle`, `/timesheet-entries/{id}` | 401 (auth enforced) |
| Unauthenticated settings | `GET /api/v1/settings/company`, `/file-paths`, `/holidays`, `/skills`, `/timesheet-policy`, `/legal-entities` | **200 without a token** — see §8 |
| Frontend load | `npx vite --port 5180` → `GET http://localhost:5180/`, `/src/main.tsx`, and `/api/v1/settings/public` via the proxy | 200 |
| Frontend e2e (Playwright) | Not run | Specs need a signed-in admin and `global-setup.ts` can *create/ensure* an admin account (a write); not run against any shared DB |
| Authenticated screens | Not verified | No credentials available to the audit; a sign-in attempt in the previous session was rejected. Screen behaviour is covered only through backend tests and code reading. |

### 3.2 Pre-existing failures (identical on a clean checkout of the parent commit in the previous session)

| Test | Failure | Likely cause | Classification |
|---|---|---|---|
| `test_finance_wave1_closeout::test_receivables_ages_unpaid_invoice_into_bucket` | `'aging_unavailable' == '31_60'` | Aging moved to due-date buckets; the test posts an invoice line without `due_date` | Stale test (semantics changed) |
| `…::test_receivables_drops_settled_quote_and_ages_old_invoice` | `'aging_unavailable' == '90_plus'` | Same | Stale test |
| `…::test_quote_pdf_extract_previews_then_confirm_creates` | `AttributeError: … has no attribute 'extract_prosohm_quote_text'` | Patch target moved to `prosohm_quote_pdf_parser` / document-intelligence service | Stale test |
| `test_finance_quote_pdf_import::test_extract_quote_pdf_does_not_create_quote` | Same AttributeError | Same | Stale test |
| `test_connected_protrack_wave45::test_quote_extract_reports_ocr_unavailable_for_scanned_pdf` | Same AttributeError | Same; **not** caused by missing OCR | Stale test |
| `test_prosohm_quote_pdf_import::test_parse_prosohm_quote_golden_text` | `'2026-04-10' == '10/04/2026'` | Parser now emits ISO dates | Stale test |
| `test_quote_invoicing_notifier::test_is_invoiced_yes_no_and_revenue_date` | `True is False` | Setting `is_invoiced` creates a real ledger line; clearing the flag cannot remove it (ledger is source of truth) | **Behaviour question** — possibly a real defect: "un-invoice" silently does nothing |
| `test_quote_manual_entry::test_quote_invoiced_date_set_and_clear` | `True is False` | Same | Same |
| `test_customer_timesheet_pack::test_customer_timesheet_pack_api_export` | Expects `PP_` filename prefix | Export naming convention changed | Stale test |
| `test_historical_timesheet_import::test_duplicate_week_skip` | `0 == 1` | `ignore_duplicate_check` defaults to `True`, so duplicate-week "skip" never triggers | **Likely real defect** — duplicate imports are not prevented by default |
| `test_fixed_resource_overhead::test_team_salary_includes_non_primary_billable_when_no_primary_home` | `0.0 == 90000.0` | `_team_rollups` ignores the passed quote revenue and reads DB quotes | Unverified (stale test or defect) |
| `test_it_data_import::test_assets_commit_and_rollback_batch_only` | `assert False` | Not investigated (IT module, outside this scope) | Unverified |

### 3.3 CI coverage gap

`.github/workflows/ci.yml` runs only `tests/test_r1_platform.py` and `tests/test_auth.py` (SQLite). The Postgres job is `continue-on-error: true`. There is no frontend build, type-check, lint or security scan in CI. **About 99% of the backend suite never runs in CI.**

### 3.4 Development database inventory (read-only)

Queries were run with `scripts/phase0_data_quality_audit.py` against a disposable copy (`%TEMP%\phase0_audit.db`), opened in SQLite `mode=ro`.

| Table | Rows | | Table | Rows |
|---|---|---|---|---|
| projects | 24 | | quotes | **0** |
| milestones | 168 | | quote_revisions / invoice_lines / payment_lines | **0** |
| timesheets | 4 | | project_stage_estimates | **0** |
| timesheet_entries | **2** (both non-project) | | project_estimate_revisions / baseline_revisions | **0** |
| customers | 9 | | skills / user_skills | 6 / **0** |
| users | 14 (all `employee`) | | rp_shift_assignments | **0** |

114 of 166 tables are empty. **The dev database is a thin legacy import and cannot validate finance, hours or capacity calculations.** Whether a production database with real data exists elsewhere is unknown (see Outstanding decisions).

---

## 4. Module-by-module findings

### 4.1 Projects and milestones — lifecycle map

```
Create (ProjectFormDialog → POST /projects → CRUDProject.create)
  ├─ customer defaults: team, type, template, working model (crud/project.py 199-214)
  ├─ classification required (full_design | small_task)    schemas/project.py 131-145
  ├─ stage_hours → ProjectStageEstimate(original = current); quoted_hours = Σ stages
  ├─ template resolved (project_template_service.resolve_template 136-207)
  │     → milestones generated (stage, hours, required, dependencies, original_planned_hours)
  └─ start_date set → baseline written (scheduling_service._write_baseline)
Update (PATCH /projects/{id})
  ├─ due_date / quoted_hours / start_date: edited in place, Activity log only, no revision row
  ├─ health: manual value accepted, then overwritten on next recalculation
  └─ status → completed: stage gate requires required milestones closed (project_stage_gate_service)
Milestone status change (crud/milestone.py → sync_project_stage_from_milestones)
  ├─ all required closed → project completed + completed_at (if empty)
  └─ reopen → project back to in-progress, completed_at KEPT (PATCH reopen CLEARS it)
Planning (/projects/{id}/stage-plan, revise-estimate, revise-baseline, overrides)
  ├─ ProjectEstimateRevision (reason, by, at) — requires revise_estimates special
  ├─ ProjectBaselineRevision (previous dates + milestone snapshot) — requires approve_baselines
  └─ forecast recalculated (provisional, one person × effort hours/day)
Recalculation triggers: project / milestone / timesheet-entry CRUD, planning endpoints, imports.
No periodic refresh (PostgreSQL startup only).
```

**Answers to the specific questions (evidence in `app/` unless noted):**

| # | Question | Finding | Evidence |
|---|---|---|---|
| 1 | Health manual or calculated? | **Both.** Calculated by `calculate_project_health`; a manual value via `ProjectUpdate.health` is applied after recalculation but silently overwritten by the next `recalculate_project`. No refresh schedule. | `services/project_calculation_service.py` 135-192, 253-269; `crud/project.py` 666, 687-691 |
| 2 | What makes a project at risk? | In order: past due → red; hours over quote → red; due within 5 days → yellow; ≥85% of quote → yellow; overdue milestone + due within 14 days → yellow; plus working-model strategies (project-based uses *actual incl. post-completion*; retainer 90%; T&M approval ratio). **Other places use different rules:** red only vs red+yellow ("High Risk" in frontend), 85% vs 90%, original vs actual hours. `ManagementKpis.high_risk_projects` is never set (always 0). | `project_calculation_service.py` 135-192; `working_model/strategies/*`; `ai/risk_analysis.py`; `frontend/src/.../buildRoleKpiCards.ts` 115, 299; `schemas/kpi.py` 39 |
| 3 | Overdue milestones consistent? | **No.** Most checks exclude only `completed`; the stage plan excludes completed/cancelled/not_applicable and compares the baseline finish before the target date. | §7 calculation inventory |
| 4 | Can completed/cancelled appear overdue? | Completed projects: no (at project level), but their open milestones are counted in the workflow dashboard and command-center timeline. **Cancelled projects: yes** — attention list, executive wall "late", project delay report; health becomes red and is counted in health totals. | `services/dashboard_service.py` 178, 472; `crud/reports.py` 445-446; `count_projects_by_health` 289-314 (no filters) |
| 5 | Original dates/estimates preserved? | Stage original hours, milestone original planned hours and baseline dates: yes. **Project `due_date` and `quoted_hours`: no** — only an Activity row. Template re-apply leaves stale baselines. | `models.py` 1326-1442; `api/v1/projects.py` 849-862, 918-959 |
| 6 | History of schedule/estimate changes? | Yes for stage-estimate revisions, baseline revisions, overrides and stage history. No approval workflow — the editor is recorded as the approver. Direct due-date/quoted-hours edits need no reason. | `api/v1/project_planning.py` 307, 344, 385 |
| 7 | Completion consistent? | Auto- and manual completion both require closed required milestones, but reopen behaves differently (kept vs cleared `completed_at`; milestone path skips the reopen permission). Historical import sets completed without `completed_at`. **Dev DB: 20/21 completed projects have 3 open required milestones each; 6 have no `completed_at`.** | `services/project_stage_sync_service.py` 150-238; `historical_import_service.py` 182-183; §3.4 |
| 8 | Templates configurable? | **Yes.** Versioned families, editor, stage/hours/required/dependencies, in-use templates create a new version; tests cover it. | `crud/project_template.py` 522-589; `tests/test_engineering_management.py` |
| 9 | Different sequences per customer/type? | **Yes.** General Mold, CAD Development, Sybridge, Lamko, TI Automotive, Crest (staged), B&B (unstaged), Redoe (staged, not linked to a customer), Engineering Change, DFM, Surfacing, Fixture, Electrode. "CAD Support" and "Tooling Support" types have **no template**, so project creation with them fails. **Dev DB: 0 of 24 projects use any template.** | `db/project_template_seed.py` 43-248 |
| 10 | Dependencies enforced? | **Scheduling only** (dependency-mode templates). Not checked on status change, not editable per project, not displayed per project. | `scheduling_service.py` 198-331; `crud/milestone.py` 38-136 |
| 11 | Persisted vs frontend-only? | Health, hours, baseline/forecast and completion are persisted. Portfolio KPIs, due-this-week, EAC and hours colours are frontend-only. The Projects page computes KPIs from ≤100 loaded rows although `/projects/summary` exists and is unused. | `frontend/src/utils/projectCommandCenter.ts`, `projectHoursMetrics.ts`; `pages/ProjectsPage.tsx` 300-312 |

**Field coverage.** These all exist: project code, tool number, part description, customer, contact, end customer, design leader, designer, surfacer, type, classification, start date, single due date, baseline and forecast dates, quoted / current planned / actual hours, priority, health, and stage/status/completion.

**Missing fields:** parent project, separate project-manager field, original due date, project-level delay reason, cancellation reason.

**Other confirmed defects:**
- `GET /api/v1/ai/health` will raise `TypeError`: `ai/scoring.py` L18 passes `db` positionally to a keyword-only parameter. Confirmed (code).
- `enrich_milestone_read` drops `is_required`, `project_stage` and the baseline/forecast fields from `/milestones` responses (`milestone_workspace_service.py` 39-80).
- Progress % counts cancelled/not-applicable milestones in its denominator.
- Users with progress-only rights can edit milestone due dates (`api/v1/milestones.py` 43-45).

### 4.2 Timesheets

- **Model.**
  - `Timesheet`: unique `(user_id, week_start)`, without `tenant_id`; Monday is not enforced; status is draft / submitted / approved / rejected.
  - `TimesheetEntry`: optional project / milestone / task type; soft delete with a deletion log; `post_completion_type`; `home_team_id` snapshot.
- **Workflow** (`services/timesheet_workflow_service.py`):
  - Submit → approve/reject (reject requires a comment) → return to draft. Return to draft is logged as `timesheet_rejected` (mislabelled).
  - Admin and Engineering Manager can approve their **own** timesheets (`core/permissions.py` 382).
  - A Design Leader's approval covers the whole sheet, including projects they don't lead.
- **Corrections.** Approved sheets stay editable inside the 2-month window. Edits do **not** reset approval, so post-approval changes keep the sheet marked "approved".
- **Hard deletes that bypass the audit and recalculation:**
  - `crud/timesheet.py` `delete_for_user` 95-110: the cascade removes entries without a deletion log, and `Project.actual_hours` goes stale.
  - The import "replace" option bulk-deletes week entries.
- **Duplicates.**
  - No duplicate check on entries.
  - Historical imports default to `ignore_duplicate_check=True` (confirmed by a failing test).
  - Imports force existing draft/rejected sheets to approved with `approved_by = NULL`, and never set `milestone_id`.
- **Rework.**
  - `post_completion_type` (additional work, rework, customer change, internal correction) applies only to completed projects.
  - During an active project, rework appears only as `ContributionReason.rework_quality` / `engineering_change`, which still count as "original" hours.
  - `EngineeringChange.hours` is a manual number, not linked to timesheets.

### 4.3 Finance

Covered in §6.

### 4.4 Resource planning

Detailed in §4.6 below and in the capacity readiness section of §9.

### 4.5 Skills

- **Three disconnected systems:**
  1. **Stream skill matrix** (`StreamSkill`, `UserSkillRating`; proficiency learning → developing → proficient → expert; manager-assessed). This is the only one in use: a **warn-only** assignment fit check (`services/assignment_skill_fit_service.py`) maps project complexity to a minimum proficiency.
  2. **Foundation** `Skill` / `UserSkill` / `EngineeringDiscipline`. Seeded NX, Creo, CATIA, SolidWorks, AutoCAD, Moldflow, plus disciplines. Mostly dormant: 0 user skill rows in the dev DB, and the frontend fetchers are never called.
  3. **`User.skill_level`**, a single display-only value.
- **What is missing:**
  - verification history, self- vs manager-assessment, "last used", evidence;
  - project skill requirements;
  - links to training or certification.
  - Cimatron, electrode design and fixture design are not modelled as skills.
- **Inference.** Skills are never inferred from project history. The only inference is the "primary CAD tool" taken from licence assignments, which shows licence possession, not competence.

### 4.6 Resource planning / capacity

| Capability | Status | Evidence / limitation |
|---|---|---|
| Available working hours | Yes, daily | `resource_planning_service._daily_capacity` 118-139: person's working days, holidays, shift paid hours, fallback `working_hours_per_day or 8`. Ignores `max_allocation_percent`, joining/leaving dates and regional holidays (no caller passes `region`) |
| Planned effort | Project/milestone level only | Open-milestone planned hours; never per person |
| Actual effort | Yes | Timesheets |
| Remaining effort | Heuristic | `_active_planning_remaining` 69-106 falls back to invented 16 h per open milestone and a 40 h "carry" |
| Leave | **No leave model** | Only a manual `availability_status` flag (no dates) and past leave as timesheet codes; leave lives in GreytHR (`india_leave_defaults.py`) |
| Shifts / calendars | Yes | `ResourceShift`, rotations, company working days, holidays |
| Allocation model | **None** | Three FK roles on `Project`; load spread with fixed role shares (designer 100%, surfacer 40%, design leader 15%) |
| Over-allocation | Detected (colour), not prevented | Thresholds differ between backend (100%) and UI (90%) |
| Scheduling vs capacity | Independent | `scheduling_service` docstring: provisional, one person × effort hours/day |
| Hard-coded assumptions | Many | 40 h/week in `dashboard_service`, `team_reports`, `ai/forecasting`, `ai/context`, `command_center_service`; 8 h/day fallbacks in multiple places; Monday–Friday in `periods.count_working_days`, `holiday_service.add_business_days` |

### 4.7 Automation

Covered in §9.

### 4.8 Reporting

Covered in §7.

### 4.9 Permissions

Covered in §8.

---

## 5. Quote-to-Delivery data lineage matrix

Reliability: **Verified** = code traced, tests pass and data checked; **Partially verified** = code traced and tests pass, but no real data to validate; **Unreliable** = code shows inconsistent or lossy behaviour; **Unavailable** = no source exists; **Not tested** = not traced end to end.

| Data element | Source model/table | Relationship path | Current calculation | Reliability | Missing data or risk |
|---|---|---|---|---|---|
| Original quotation | `quotes` + `quote_revisions` (version/revision unique) | `Quote 1─< QuoteRevision`; pointers `current_version/current_revision` | First revision row | Partially verified (code + tests; 0 rows in dev) | `update_quote` edits the current revision **in place** (no new revision); `quote_hours_balance_service._current_revision` uses a different "current" rule than the pointers |
| Quoted engineering hours | `quote_revisions.quoted_hours`; copied to `projects.quoted_hours` | `Quote.project_id → Project` | Finance uses the revision; project/health/reports use `Project.quoted_hours`, copied only when the project value is 0 | **Unreliable** | Later revisions never update the project; the shell project from a quote import starts at 0; stage-estimate creation overwrites `Project.quoted_hours` with the stage total |
| Awarded quotation | **No status column** | — | Every active quote = awarded | **Unavailable** | Cannot separate pipeline vs won vs lost; "quoted value" = "awarded value" |
| Quote → project link | `quotes.project_id` (nullable FK) | Matched by `lower(tool_number)` only, any customer (`quote_import_service.py` 150-155) | Set on import/confirm | **Unreliable** | No customer check; cleared when tool number changes without a match; N quotes : 0..1 project |
| Project creation from quote | `ensure_project_for_quote_import` | Quote → shell `Project` | `part_description=""`, `quoted_hours=0`, classification `unclassified` | Partially verified | Shell projects bypass classification, template and stage estimates |
| Customer project number / tool number / PO | `projects.tool_number` (unique/tenant), `projects.code`, `quotes.tool_number`, `quotes.customer_po_number`, `external_quote_number` | Tool number is the join key | — | Partially verified | PO and project code never used for matching; quote tool numbers not unique |
| Approved estimate & revisions | `project_stage_estimates` (original/current), `project_estimate_revisions` | `Project 1─< StageEstimate 1─< Revision` | Revision updates `current_hours` only | Partially verified (tests; 0 rows in dev) | Revision does **not** update `Project.quoted_hours`; direct `quoted_hours` edits bypass revisions |
| Planned hours by stage | `project_stage_estimates`; `milestones.planned_hours` / `original_planned_hours`, `project_stage` | Milestone.project_stage ∈ preliminary/intermediate/final | Stage plan & engineering performance | Partially verified | Legacy projects: no estimates; dev DB 48/168 milestones have no stage, 168/168 no original hours |
| Timesheet entries on a project | `timesheet_entries.project_id` | `Timesheet 1─< Entry → Project` | `hours_by_post_completion_type`: all non-deleted entries, **any sheet status** | **Unreliable** (definition conflict) | Project page counts rejected/draft; period reports exclude rejected; cached `Project.actual_hours` can be stale (hard deletes, import replace, spreadsheet-imported values) |
| Timesheet approval status | `timesheets.status` | Sheet-level only | — | Partially verified | Post-approval edits keep "approved"; imports force "approved" with null approver; self-approval possible for Admin/EM |
| Actual hours by stage | `timesheet_entries.milestone_id → milestones.project_stage` | Outer join | Stage actuals; anything else is "unstaged" | **Unreliable for history** | `milestone_id` optional in UI, never set by imports; "unstaged" mixes no-milestone, no-stage and non-planned stages; **missing actuals = 0** (cannot be told apart) |
| Actual hours by designer | entries grouped by `Timesheet.user_id`, membership windows | Period reports | `_designer_productivity` | Partially verified | Will not reconcile with project totals (includes NP/leave; excludes rejected, non-KPI users) |
| Milestone completion dates | `milestones.completed_at` (tz-aware), `completed_date` (date) | — | Set by `apply_progress_rules` | Partially verified | Dev DB: all 97 completed milestones have `completed_at` but none has `completed_date` |
| Delivery baseline | `projects.baseline_*`, `project_baseline_revisions`; legacy `due_date` | — | On-time = completion ≤ baseline (legacy: due date) | Partially verified | Original due date not preserved; legacy projects have no baseline (dev: 0 baselines) |
| Rework / EC hours | `post_completion_type` (completed projects only); `ContributionReason` during active work; `engineering_changes.hours` (manual) | — | Post-completion buckets; contribution-reason report | **Unreliable** | Rework during active projects counts as original hours; EC hours not linked to timesheets |
| Invoices | `quote_invoice_lines` | `Quote 1─< InvoiceLine` (no `project_id`) | `summarize_quote_cash` | Partially verified (tests; 0 rows) | No credit notes/voids (hard delete, unaudited); invoices on unlinked quotes invisible to project roll-ups |
| Payments | `quote_payment_lines` (optional `invoice_line_id`) | `Quote 1─< PaymentLine` | FIFO allocation across invoice lines | Partially verified | `invoice_line_id` ignored in aging; writes not audited |
| Outstanding / receivables | derived | Quote → lines | `build_receivables_aging` | **Unreliable** | Mixed currencies summed; manual invoices lack due dates ("aging unavailable"); `project.name` crash when linked |
| Recognized revenue | derived | — | **Three rules** (full award on first invoice date / per-line date / full award incl. inactive quotes in ERP export) | **Unreliable** | No authoritative recognition rule |
| Completed-project performance | `services/reporting/engineering_performance.py` | Completed in period (`completed_at`) + timesheets + stage estimates | Central KPI definitions | Partially verified (tests) | Depends on all rows above; dev DB: 6/21 completed projects have no completion date |

### Required reconciliation checks (how to validate without double-counting)

| Check | Authoritative source & rule | Exclusions to apply consistently | Current status |
|---|---|---|---|
| Quoted vs actual hours | Quoted: current `QuoteRevision.quoted_hours` **or** current stage-estimate total (decision required). Actual: `SUM(timesheet_entries.hours)` where `is_deleted = 0`, joined to sheets with the agreed status set | Deleted entries; agreed sheet statuses; post-completion hours reported separately | Cannot reconcile today: three quoted sources, two status policies |
| Stage actual vs total actual | Σ stage actuals + **unattributed bucket** (no milestone) + non-planned-stage bucket = project actual | Same filters as above | Possible once unattributed hours are reported separately |
| Designer actual vs project actual | Σ over all users (not just KPI designers), productive category, same statuses = project actual | NP/leave excluded from both sides | Not reconciled; designer totals include NP/leave |
| Milestones vs delivery baseline | `milestones.completed_at` vs `baseline_finish_date` (legacy `due_date`) | Cancelled / not-applicable milestones | Partial (stage plan only) |
| Project invoices vs Finance totals | Σ `quote_invoice_lines.amount` for quotes with `project_id = P`, in quote currency **and** converted with revision FX | Inactive quotes; unlinked quotes listed separately | Not reconciled (mixed currency, unlinked quotes) |
| Project payments vs Finance totals | Σ `quote_payment_lines.amount` per project quote set | Same | Same |

---

## 6. Finance linkage

### 6.1 Entity diagram

```
Customer ──< Project (tool_number unique/tenant; quoted_hours; actual_hours cache)
   │             ▲ 0..1
   │             │ quotes.project_id (nullable; matched on tool_number only)
   └──< Quote (no status; currency; is_invoiced/is_paid cache flags; payment terms)
          ├──< QuoteRevision (quoted_hours, quoted_revenue, cost, fx, version/revision)
          ├──< QuoteInvoiceLine (amount, line_date, due_date, invoice_number; NO project_id)
          │       └──< QuotePaymentLine.invoice_line_id (optional, ignored in aging)
          ├──< QuotePaymentLine (amount, line_date)
          ├──< QuotePaymentMilestone (schedule; status NOT_YET_TRIGGERED → READY → INVOICED)
          └──< QuoteBalanceClosure (explicit write-off of remaining balance)
ProjectFinancialSnapshot (project_id unique) — model exists, never written
FinancePlan / FinancePlanLine / FinancePlanningScenario — forecasts, separate tables
Expense.project_id (cost side, optional)
```

### 6.2 Value definitions

| Concept | Exists? | Where |
|---|---|---|
| Quoted value | Yes | `QuoteRevision.quoted_revenue` |
| Awarded value | **Same as quoted** (no status) | — |
| Invoiced value | Yes | Σ invoice lines (`quote_cash_ledger_service.summarize_quote_cash`) |
| Collected value | Yes | Σ payment lines |
| Outstanding balance | Yes | invoiced − paid (FIFO) |
| Remaining to invoice | Yes | awarded − invoiced − closures |
| Recognized revenue | **No single definition** | See 6.3 |
| Projected billing | Separate | payment milestones, plans, scenarios, cash-flow forecast |

### 6.3 Discrepancies affecting project-level billing and collection analysis (Confirmed (code) unless marked)

1. **Three revenue-recognition rules:**
   - The dashboard and the Annual Plan recognize the full award on the first invoice date (`finance/dashboard_service.py` 184-424; `plan_sales_from_quotes_service.py`).
   - FY turnover and the monthly P&L recognize each invoice line on its own date (`fy_turnover_service.py` 96-109; `monthly_pnl_service.py` 80-91).
   - The ERP export uses the full award and includes inactive quotes (`erp_export_service.py` 41-77).
2. **Mixed-currency sums** in `project_financial_summary`, customer totals, receivables and the P&L drilldown. Only the dashboard billing summary and FY turnover apply FX.
3. **`project.name` does not exist.** It is referenced at `receivables_service.py` 111, 181 and `customer_financial_service.py` 279, 414. `hasattr(Project, "name")` is False (confirmed by running). These paths will raise once a quote is linked to a project; current tests never link one.
4. **`ProjectFinancialSnapshot` is never written**, so project profitability is always empty.
5. **No invoice → project FK.** Unlinked quotes' invoices are invisible to project roll-ups.
6. **Project matching ignores the customer.**
7. **No credit notes, voids or reversals.** Corrections are hard deletes and are not audited.
8. **Invoice, payment, milestone-trigger, balance-closure and plan-line writes are not audited.** `_audit` records only the new value.
9. **Manual invoice lines skip customer and quote default payment terms**, so they get no due date and fall into "aging unavailable". Dev DB: 9/9 customers have no default payment terms either.
10. **"Un-invoicing" a quote silently does nothing** once a ledger line exists (2 failing tests).
11. **No quote pipeline status.** Invoicing reminders fire for every active quote 15 days after creation.
12. **Finance hours** use the cached `Project.actual_hours` across all projects, ignoring the team filter, and label it "billable".
13. **Permissions.** All 105 finance endpoints call `_require_finance_action` (good). View access is granted to anyone holding the module, and there is no team row scoping.

---

## 7. Calculation inventory (key metrics)

| Metric | Where computed | Source | Filters | Reconciles with project page? |
|---|---|---|---|---|
| Project actual hours (reference) | `crud/project_metrics.py` → `project_calculation_service.calculate_hours` → `post_completion_work.hours_by_post_completion_type` | Entries | `is_deleted = 0`; **no sheet status**; lifetime | Reference |
| Cached `Project.actual_hours` | `recalculate_project` | Entries | Same | Only while fresh |
| Dashboard `total_actual_hours_productive` | `dashboard_service.get_dashboard_kpis` | Entries (live projects) | No status; team-scoped | Yes per project |
| Portfolio quoted/actual/remaining | `aggregate_portfolio_hours` | Cache | No `is_deleted`/cancelled filter | **No** (includes deleted/cancelled; remaining = quoted − actual) |
| Dashboard billable/NP split | `crud/dashboard.get_dashboard_summary` 289-341 | Entries | **Approved only; deleted entries counted**; lifetime; unscoped | **No** |
| Reporting engine (designer, customer, team, period tool hours) | `reporting/data_service._entry_base_filters` | Entries | Draft + submitted + approved (rejected excluded), period | **No** (rejected) |
| Engineering report quoted vs actual / project performance | `data_service._quoted_vs_actual`, `_project_performance` | `calculate_hours` | Lifetime, inside a period report | Mixed (two "actual" meanings) |
| Engineering Performance (completed) | `reporting/engineering_performance.py` | Entries + stage estimates | Completed in period | Actual yes; variance = actual − plan |
| Customer timesheet pack | `reporting/customer_timesheet_pack.py` | Entries | Rejected and inactive users excluded | No |
| Monthly team summary | `crud/team_reports.py` 314-356 | Entries | **Deleted entries counted** | No |
| Finance dashboard hours | `finance/dashboard_service.py` 1043-1049 | Cache | All projects, unscoped | No |
| Variance | Project page / project hours report: `original − quoted`; team, customer, executive wall, engineering performance: `actual − quoted` | — | — | **Two definitions** |
| Remaining | `quoted − original` (project) vs `quoted − actual` (portfolio, staff rows, AI) | — | — | Two definitions |
| Utilization | ≥10 formulas: `reporting/utilization_capacity` (productive ÷ windowed capacity), executive summary, team summary, customer pack (+leave), team reports (lifetime ÷ quoted), AI (÷40 h), command center (weekly − lifetime quoted) | — | — | Not comparable |
| Overdue milestone | Most: excludes `completed` only; stage plan excludes all closed and uses the baseline date | — | — | No |
| Overdue project | Most exclude completed + cancelled; **attention list and delay report exclude completed only** | — | — | No |
| At-risk count | red only (summary, command center) vs red + yellow (frontend dashboards); `count_projects_by_health` unfiltered | — | — | No |
| Completed projects in period | Engineering Performance: `completed_at` ∈ [start, end+1); executive summary: `completed_at <= end_date` (naive datetime, likely drops last-day completions — Unverified) and unscoped | — | — | No |

Duplicated helpers with *different* rounding: `_pct` (≥7 copies, half-up vs half-even, float vs Decimal), `_round_hours` (`dashboard_service.py` 90 rounds half-even, the others half-up), `_q2`, `_decimal` (~12 copies).

---

## 8. Security and permissions findings

| # | Finding | Severity | Status | Evidence |
|---|---|---|---|---|
| S1 | Settings GET endpoints require **no authentication**: company profile (address, email, phone, GST), server file paths, holidays, skills, timesheet policy, legal entities; also notifications, departments, contact types, disciplines and `/settings/users/{id}/skills` per code | High | **Confirmed (run)** for 6 endpoints (200 without token) | `app/api/v1/settings.py` router L66 has no auth dependency |
| S2 | `GET /hr/users/{id}/lifecycle` needs only Performance "view" (default for nearly all roles) and returns job events including compensation `from/to` values for **any** user, unscoped | High | Confirmed (code); 401 without token confirmed | `app/api/v1/hr.py` 2290-2325; `_require_performance_view` |
| S3 | `GET /timesheet-entries/{id}` has no read check; `GET /timesheet-entries?project_id=…` / `timesheet_id=…` skip visibility scoping | Medium | Confirmed (code); router requires login | `app/api/v1/timesheet_entries.py` 27-91 |
| S4 | `list_activities` with `project_id`/`user_id` and `/activities/project/{id}` have no scope check | Medium | Confirmed (code, per explorer) | `app/api/v1/activities.py` 57, 99 |
| S5 | Company-wide data behind login only: dashboard `/kpis`, `/attention-projects`, `/project/{id}`; `/ai/knowledge`, `/ai/chat`, `/ai/quote/{project_id}`; `/calendar/engineering` (frontend gates some of these) | Medium | Confirmed (code, per explorer) | `api/v1/dashboard.py`, `ai.py`, `calendar.py` |
| S6 | Admin/EM can approve their own timesheets; approval uses raw role names and ignores the `approve_timesheets` special | Medium | Confirmed (code) | `core/permissions.py` 382 |
| S7 | `OIDC_TESTING` accepts fake codes and is not flagged by `security_config_problems`; `STRICT_SECURITY` defaults to false; the compose file ships a dev secret and `INTERNAL_RELEASE=true` | Medium (deployment) | Confirmed (code, per explorer) | `core/oidc.py` 137-185; `core/config.py` 161; `deploy/docker-compose.yml` |
| S8 | `frontend/e2e/helpers/auth.ts` contains a default admin credential literal | Low | Confirmed (code) | value intentionally not reproduced here |
| S9 | Admin can impersonate another Admin | Low | Confirmed (code, per explorer) | `api/v1/auth.py` 480 |

**Virtual (system) users.**

`User.user_type` exists (employee / virtual) and is excluded from:
- salary and cost;
- HR headcount;
- KPI and capacity participation;
- shift rosters;
- IT allocation through `employee_block`;
- timesheet requirement and compliance;
- data quality.

**Not excluded:**
- `workstation_package_service.assign_package`, `it_stock_service.issue`, the IT employee roster picker;
- performance review members, review creation and review cycles;
- `/lookups/users`, ticket assignees;
- recipient fan-outs (timesheet approvers, digests, finance reminders).

**Dev DB:** all 14 users are `employee`; no shared or system account has been reclassified yet.

**Unverified:** forged `X-Tenant-Id` behaviour; billable-override and org-chart edit enforcement on the backend; virtual-user checks on project designer assignment.

---

## 9. Automation inventory

There is **no generic rule engine and no periodic scheduler**. The configurable pieces are ticket routing/SLA policies, `NotificationSettings` toggles, per-expense renewal settings and onboarding template items.

| Automation | Trigger | Configurable | Idempotent | History | Reusable? |
|---|---|---|---|---|---|
| Ticket notify / SLA / escalation | Inline, startup, POST `/tickets/sla/run` | Yes | **Yes** (`TicketNotificationLog`, idempotency key) | Yes | **Best pattern to reuse** |
| Onboarding checklist → task tickets | Checklist creation | Template | Yes | Yes | Yes |
| IT provisioning | Hire / onboarding | Packages | Yes (idempotency key) | `log_activity` | Yes |
| Timesheet submit/approve/reject | User action | No | Status guard | Activity + notification (return mislabelled) | Partly |
| Timesheet compliance reminders | Manual POST | No | No dedupe | Notification | No (doesn't exclude virtual users) |
| Quote uninvoiced / unpaid reminders | **Startup** + manual | No | Per-day stamp | Notification only | Fragile: misses days, bypasses settings |
| Expense renewal notifier | Manual POST | Per expense | Yes | Notification | Yes |
| Engineering digests | Manual only | No (preference check is dead code) | No | Email rows | No |
| Compensation approval L1 → L2 → apply | User + startup | No | Yes | `UserJobEvent` only | Partly |
| Email queue | Manual / job | Retries | Status-based | `EmailMessage` | Messages stuck in `sending` never retried |
| Webhooks | Admin ping only | Endpoints | Delivery rows | Yes | Not wired to domain events |
| Report schedules | Stored **in memory** | — | — | None | **Non-functional** (never executed, lost on restart) |
| Ops maintenance actions (restore roles/streams/types, refresh cache) | Manual | — | — | — | Some report success without doing anything |

**Reliability risks:**
- Startup-only execution.
- No execution history for reminders.
- `except Exception: pass` in new-hire notices.
- `queue_email` commits the caller's transaction.
- Synchronous email inside HTTP requests.

---

## 10. Data-quality findings (dev DB copy, read-only)

Source: `scripts/phase0_data_quality_audit.py` (SELECT-only, `mode=ro`). Nothing was repaired.

| Finding | Count | Records / impact | Recommended remediation |
|---|---|---|---|
| Completed projects with open required milestones | 20 of 21 (3 each) | Legacy import set status without closing milestones; progress %, stage and on-time metrics wrong | Owner review: close milestones with actual dates, or mark not-applicable |
| Completed projects without `completed_at` | 6 (`4276-M`, `4277-M`, `4279-M`, `7742-C`, `7744-C`, `17974`) | Excluded from period reports (already flagged by the Data Quality panel) | Enter actual completion dates from records |
| Projects `unclassified` | 24/24 | Classification-dependent rules (stage estimates, small tasks) don't apply | Classify in bulk with owner sign-off |
| Projects without a template | 24/24 | No standard milestone sequence | Optional; only for live projects |
| Live projects missing start date / team / baseline | 2 / 2 / 2 | No forecast, not shown under a team | Fill on the 2 live projects |
| Live projects overdue | 2 | — | Confirm due dates |
| Stored health on completed/cancelled | 22 green | Cancelled project shows green now but would turn red after recalculation (rule has no cancelled case) | Fix rule (backlog) |
| Completed milestones missing `completed_date` | 97/97 (all have `completed_at`) | Reports using `completed_date` see nothing | Derive `completed_date` from `completed_at` (migration, needs approval) |
| Milestones without stage | 48/168 | Stage reporting incomplete | Map via template stage mapping |
| Milestones without original planned hours | 168/168 | No original baseline at milestone level | Cannot be reconstructed; prospective only |
| Open milestones without due date | 71 | No overdue tracking | Owner input |
| Timesheet entries on projects | 0 (2 NP entries total) | **No actual-hours history at all** | Historical timesheet import, if source files exist |
| Quotes / invoices / payments | 0 | Finance lineage untestable | Import Finance history, or audit a production copy |
| Customers without payment terms | 9/9 | Aging unavailable for future invoices | Enter terms per customer |
| Possible duplicate customer | 1 (`Sybridge` ×2) | Split customer reporting | Merge decision by Admin |
| Active employees with no skill records | 12/12 | Skill-based planning impossible | Skills capture (prospective) |
| Virtual/system accounts | 0 classified | Shared accounts (if any) treated as employees | Admin review of accounts |
| Orphan entries / milestones, duplicate codes, cached-vs-live hour mismatches | 0 | — | — |

**Missing historical data cannot be told apart from zero** for stage actuals and for projects without timesheet entries. Any Phase 1 feature must show "no data" explicitly.

---

## 11. Architecture recommendations (intelligence foundation)

Reuse existing services and extend them minimally. **Do not create new masters or a parallel automation system.**

| Logical service | Reuse | Small refactor needed | Defer |
|---|---|---|---|
| **A. Engineering metrics** | `project_calculation_service` (hours), `engineering_performance.py` (central KPI definitions), `project_estimate_service.stage_breakdown` | Make `hours_by_post_completion_type` the only actual-hours source, with an explicit, decided status policy and an *unattributed* bucket; retire cached-column reads in reports | — |
| **B. Estimate & variance** | `ProjectStageEstimate`/`ProjectEstimateRevision`, baselines | One variance definition; decide quoted-hours authority; sync or flag `Project.quoted_hours` divergence; revision required for quoted-hours edits | — |
| **C. Forecast** | `scheduling_service` (provisional, labelled) | Expose assumptions and data-quality flags (already partly done) | Capacity-aware forecasting |
| **D. Resource capacity** | `resource_planning_service` grid, shifts, holidays | Use `max_allocation_percent`, joining/leaving dates and regions; remove invented floors or label them | Allocation model, leave periods |
| **E. Financial forecast** | Payment milestones, plans, cash-flow forecast | Choose one revenue-recognition rule; FX-normalize; fix `project.name` | Project-level billing forecast |
| **F. Skills** | Stream skill matrix + fit check | Scope the fit check to the project stream | Requirements, verification history |
| **G. Automation** | Ticket notification log pattern, job queue | Add a periodic runner (separate process) for existing reminders/SLA sweeps | Rule engine |
| **H. Permission-aware analytics** | `project_visibility_clause`, `resolve_report_scope`, `can_view_reports` | Close S1–S5 first | Query layer for AI |

**Design principles to keep:** actuals, approved plans, forecasts and scenarios stay in separate tables; baselines are preserved; every metric exposes its source filters and a data-quality indicator; access control stays in the backend.

---

## 12. Migration and data-preservation plan (only where changes may become necessary)

No migration was applied in Phase 0. Candidate future changes, all additive:

| Change | Why | Impact | Backup / rollback | Preservation check |
|---|---|---|---|---|
| `quotes.status` (e.g. draft/submitted/awarded/lost, default `awarded` for existing rows) | Distinguish pipeline vs award | Existing behaviour preserved by default | DB file copy before startup; column is additive, so it can be ignored on rollback | Row counts and Σ quoted revenue unchanged |
| `projects.original_due_date` (backfilled from current `due_date` **only where the Activity log shows no change**, otherwise NULL) | Preserve the original commitment | None to existing reads | Same | No `due_date` changes |
| `quote_invoice_lines.status` / credit-note support (`is_void`, `voided_at`, `void_reason`) instead of hard delete | Audit trail for corrections | Totals must exclude voided lines | Same | Invoiced totals identical before/after for existing rows |
| `milestones.completed_date` backfill from `completed_at` | 97 missing in dev | Read-only effect | Same | `completed_at` untouched |
| Optional `project_skill_requirements`, `user_availability_periods` | Capacity/skills phase | New tables only | — | — |

**Mandatory before any migration:**
1. Copy `protrack.db` (or `pg_dump`) and record row counts plus key sums: quotes, invoice/payment amounts, timesheet hours, project counts by status.
2. Rehearse on a disposable copy.
3. Compare counts and sums after the migration.
4. Keep the copy until sign-off.

---

## 13. Regression test plan

These existing workflows must stay green in every Phase 1 change. They are all covered by the current suite unless marked.

- **Projects:**
  - create/edit with classification, template resolution, stage estimates, baseline;
  - reopen permission;
  - (`test_engineering_management.py`, `test_project_templates.py`, `test_project_stage_sync.py`, `test_project_lifecycle.py`, `test_project_calculation.py`, `test_project_hours.py`).
- **Timesheets:**
  - entry CRUD, calendar lock, workflow approvals;
  - post-completion rules, imports;
  - (`test_workflow.py`, `test_timesheet*.py`, `test_post_completion_*`, `test_historical_timesheet_import.py`).
- **Reports:**
  - Engineering Performance, team/customer reports, exports;
  - (`test_engineering_performance_report.py`, `test_reporting_engine.py`, `test_engineering_report_filters.py`, `test_timesheet_resource_movement.py`).
- **Finance:**
  - quote import/revisions, invoice/payment ledger, aging, payment terms, PDF import;
  - (`test_finance_*`, `test_quote_*`).
- **Permissions:**
  - `test_access_control.py`, `test_team_projects_enabled.py`, `test_user_types.py`, planning 403 tests.
- **New tests required** (not present today):
  - unauthenticated settings → 401;
  - lifecycle salary scoping;
  - timesheet-entry IDOR;
  - cancelled projects excluded from overdue lists;
  - quote linked to a project in receivables (would expose the `project.name` crash);
  - `/ai/health`;
  - a reconciliation test asserting Σ stage + unattributed = project actual.
- **CI:** run the full backend suite plus `tsc -b` and `npm run build` on every push.

---

## 14. Prioritized implementation backlog

Each item lists: problem/evidence · reuse · changes · migration · dependencies · permissions/audit · tests · acceptance · risk/priority.

### P0 — Hotfixes before Phase 1 (security and crash, small)

**B0.1 Authenticate settings GETs.**
- Problem/evidence: S1, confirmed by running.
- Reuse: `get_current_user` and the existing settings CRUD.
- Changes: add the router dependency. Keep `/settings/public` (and any login-page data) explicitly public.
- Migration: none.
- Tests: 401 without a token for each GET; the public endpoint still works unauthenticated.
- Acceptance: only the documented public endpoints answer anonymously.
- Risk/priority: low risk · P0.

**B0.2 Scope HR lifecycle and redact compensation.**
- Problem/evidence: S2.
- Reuse: the `hr._scoped_member_ids` pattern and `finance._redact_salary_fields`.
- Changes: return compensation values only to users who manage the employee or hold the salary permission.
- Tests: a designer reading a peer gets 403 or redacted values; the manager sees them.
- Risk/priority: P0.

**B0.3 Scope timesheet-entry and activity reads.**
- Problem/evidence: S3, S4.
- Reuse: `get_timesheet_visible_user_ids` and `can_read_project`.
- Tests: reading another user's entry by id gets 403.
- Risk/priority: P0.

**B0.4 Fix the `project.name` references and the `/ai/health` call.**
- Problem/evidence: §6.3 item 3; §4.1.
- Changes: use `part_description` / `code`; pass `db=` by keyword.
- Tests: a receivables test with a linked project; an `/ai/health` smoke test.
- Risk/priority: P0.

**B0.5 Expand CI** to the full backend suite plus frontend type-check and build. Fix or quarantine the 12 known failures, each with a reason. First isolate the test harness from the dev database: set `DATABASE_URL` to a temporary file in `tests/conftest.py`. Also make `phase35_overhead_team_merge_schema_sync` idempotent (found in Phase 1 Step 1).
- Risk/priority: P0.

### Phase 1 — Quote-to-Delivery Intelligence (in this order)

**1. Authoritative sources and relationships.**
- Problem: weak quote ↔ project link; no quote status; quoted hours have three sources.
- Reuse: `ensure_project_for_quote_import`, `suggest_project_matches`.
- Changes:
  - customer-scoped matching;
  - a "link status" read model (linked / unlinked / conflicting) and a Data Quality check for unlinked quotes and mismatched tool numbers;
  - after an owner decision, an additive `quotes.status`.
- Migration: optional `quotes.status` (default `awarded`).
- Dependencies: B0.4.
- Permissions/audit: finance EDIT to link; log every link change in the Activity log.
- Tests: wrong-customer match is rejected; unlinked quotes are reported.
- Acceptance: every quote is classified linked / unlinked / conflicting, and counts reconcile.
- Risk/priority: medium · **P1-1**.

**2. Consistent project-hour and estimate calculation.**
- Problem: two status policies, two variance and two remaining definitions, cached-column reads (§7).
- Reuse: `hours_by_post_completion_type`, `engineering_performance` definitions.
- Changes:
  - one `project_hours` service function with a decided status policy;
  - route the dashboard, team, customer, finance-dashboard and AI reads through it;
  - one variance and remaining definition, documented in the KPI definitions.
- Migration: none.
- Dependencies: decision on rejected/draft hours.
- Tests: the same project gives the same actual hours in the project page, dashboard, team report and Engineering Performance.
- Acceptance: a reconciliation endpoint shows zero differences across the listed views.
- Risk/priority: medium (numbers will change on some screens) · **P1-2**.

**3. Reliable stage-level actuals.**
- Problem: unattributed hours are mixed into "other"; missing is shown as zero.
- Reuse: `_stage_actuals`, `stage_breakdown`.
- Changes:
  - separate buckets for no milestone, milestone without stage, and non-planned stage;
  - a data-coverage % per project;
  - show "no data" instead of 0;
  - optionally require a milestone for productive entries on staged projects (prospective, behind a setting).
- Migration: none.
- Tests: Σ buckets = project actual.
- Acceptance: stage reports state their coverage.
- Risk/priority: low · **P1-3**.

**4. Estimate revisions and baseline preservation.**
- Problem: direct `quoted_hours` / `due_date` edits bypass history; the original due date is lost.
- Reuse: `ProjectEstimateRevision`, `ProjectBaselineRevision`.
- Changes:
  - require a reason and write a revision row for quoted-hours and due-date edits;
  - sync or flag quoted hours against the stage total;
  - additive `original_due_date` (prospective; backfill only where provably unchanged).
- Migration: additive column.
- Tests: an edit without a reason is rejected; the history shows the old value.
- Acceptance: every estimate or date change has who, when, why, old and new.
- Risk/priority: medium · **P1-4**.

**5. Milestone and delivery variance.**
- Problem: overdue and at-risk rules disagree; cancelled projects appear as overdue.
- Reuse: `calculate_project_health`, `live_project_where`.
- Changes:
  - one shared overdue predicate (closed statuses excluded; cancelled projects excluded);
  - a cancelled-project health rule;
  - a periodic health refresh through the runner (G);
  - delivery variance = completion − baseline.
- Tests: cancelled projects never appear as overdue; milestone overdue counts are equal everywhere.
- Risk/priority: low · **P1-5**.

**6. Project-level quote, invoice and payment linkage.**
- Problem: §6.3 items 1, 2, 4, 7, 8.
- Reuse: `summarize_quote_cash`, `project_financial_summary`, FX in `fy_turnover_service`.
- Changes:
  - FX-normalized project billing summary (quoted, invoiced, collected, outstanding);
  - pick one recognition rule (owner decision) and label the others;
  - audit invoice and payment writes;
  - void instead of hard-delete.
- Migration: optional void columns.
- Tests: multi-currency project totals; deleting an invoice leaves an audit row.
- Risk/priority: high (finance figures) · **P1-6**; needs a Finance owner's sign-off.

**7. Historical reconciliation and data-quality indicators.**
- Reuse: `engineering_data_quality.py` and the Phase 0 script checks.
- Changes:
  - add the checks from §10 (open milestones on completed projects, unlinked quotes, missing terms, unattributed hours, cache drift);
  - a per-project "confidence" flag.
- Tests: each check has a unit test.
- Risk/priority: low · **P1-7**.

**8. Management reporting on validated metrics.**
- Only after items 1–7.
- Uses the Engineering Performance tab plus a project billing view.
- **Prospective data collection is required** for stage actuals, original dates and quote status. Historical comparisons must be labelled "insufficient data" where the sources are missing.
- Risk/priority: **P1-8**.

---

## 15. Phase 1 recommendation

Start with **B0.1–B0.5** (one short hardening task). Then do **Phase 1 item 2 + item 3 together: "Authoritative Project Hours & Stage Attribution"**.

Why this order:
- It needs no schema migration.
- It touches no financial figures.
- It turns every later intelligence feature (variance, forecast, billing per hour) from "unreliable" into "reconcilable".
- It can be validated with tests even though the dev database has no project hours.

Item 1 (quote linkage) follows next, once the owner decides quote-status semantics. Item 6 (finance) needs a Finance owner and real Finance data.

---

## 16. Phase 0 acceptance checklist

| Criterion | Status |
|---|---|
| Repository structure and entry points documented | Passed (§2) |
| Active database configuration identified | Passed (SQLite `protrack.db`; PostgreSQL supported, not active) |
| Existing tests run | Passed (§3) |
| Startup/API failures recorded | Passed (§3) |
| Existing failures distinguished from new findings | Passed (§3.2) |
| No unsupported test claims | Passed |
| No business records deleted/reset/overwritten | **Corrected (Phase 1 Step 1):** the audit tools only used copies, but the full pytest run itself writes to `protrack.db`, because the test client runs app startup against the default `DATABASE_URL`. No rows were added or removed and no business values changed. The pre-existing phase35 startup step appended its merge suffix again to one inactive team's description/notes and touched `updated_at` on 3 reference tables. See `docs/PHASE1_STEP1_ENGINEERING_METRICS.md` §6. |
| No destructive migration applied | Passed |
| No fabricated data | Passed |
| Authoritative entities identified | Passed (§5) |
| Inconsistencies reported, not repaired | Passed (§10) |
| Experimental writes only on a disposable copy | Passed (backend startup ran migrations on `%TEMP%\phase0_runtime.db`) |
| Project lifecycle traced | Passed (§4.1) |
| Quote-to-project linkage investigated | Passed (code); **Not verified with data** (0 quotes) |
| Timesheet/stage hour calculations investigated | Passed (code); **Not verified with data** (0 project entries) |
| Finance linkage via invoices/payments | Passed (code); **Not verified with data** |
| Resource capacity & skills sources identified | Passed |
| Automation & reporting paths inspected | Passed |
| Important calculations traced | Passed (§7) |
| Authoritative quoted/actual hour sources documented | Passed — with an open decision |
| Approved/rejected/corrected/duplicate timesheet treatment documented | Passed (§4.2) |
| Finance rules for invoices/payments/reversals/revenue documented | Passed (§6) |
| Missing stage data vs zero distinguishable | Assessed — **currently not distinguishable** |
| Baseline preservation assessed | Passed (§4.1 Q5) |
| Unreconcilable metrics identified | Passed (§5, §7) |
| Reusable services & duplicate calculation risks documented | Passed (§7, §11) |
| Backend permissions assessed | Passed (§8); some items Unverified |
| System vs employee user behaviour checked | Passed (code); dev DB has no virtual users |
| Proposed architecture reuses authoritative data | Passed (§11) |
| Phase 1 backlog with dependencies & acceptance criteria | Passed (§14) |
| No second source of truth introduced | Passed |
| Authenticated UI screens verified in a browser | **Not verified** — no credentials |
| Playwright e2e | **Not verified** — needs credentials, and its setup writes to the DB |
