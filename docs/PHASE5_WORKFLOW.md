# ProTrack — Smart Template Reconciliation and Phase 5 Workflow Automation

Status: **template reconciliation is delivered and verified. Phase 5 automation is a first
increment.** It has a working rule engine, six executable rules (Projects and Resource
Planning), a catalogue of the automations that already run in other modules, an admin page and a
decision audit. Phase 5 is **not** complete: Timesheet, Finance, IT and onboarding automations
are listed in the catalogue but not moved into the engine (§8, §13).

Evidence base: code inspection, `tests/test_template_reconciliation.py`,
`tests/test_workflow_automation.py`, and checks on a disposable copy of `protrack.db`
(`%TEMP%\phase110_migration_copy.db`, copied 2026-10-30). The development database was never
opened by the backend; its last write time is still `2026-10-29T12:20:48`.

---

## 1. Previous-phase status

| Phase | Status carried forward |
|---|---|
| 0 Audit | Complete. Open defects B0.1–B0.5 and S1–S3 unchanged |
| 1 Reconciliation | Complete. Whether draft and rejected hours count towards actuals is **still an open decision** |
| 2 Control Tower | Complete. Now excludes merged, superseded and archived milestones (§5); used by the overdue rule (§8) |
| 3 Forecasting | First increment only, unchanged |
| 4 Skills | First increment only, unchanged |

## 2. Template change before this work (Part A)

- `POST /projects/{id}/apply-template` **deleted every milestone** and regenerated the list
  from the new template.
- To make that safe, the change was **blocked** once any milestone was completed or had
  timesheet hours (`project_template_service` blocker functions). After real work started the
  template could not be changed at all.
- No record of which template a milestone came from survived a change, no history of template
  changes was kept, and template edits had no version link to the projects using them.

## 3. Architecture and template change (Parts B and F)

```
Change Template dialog ──► POST …/template-reconciliation/preview   (read-only, returns a fingerprint)
        │ user decisions (match / add / keep / supersede / archive / merge)
        ▼
POST …/template-reconciliation/apply  (confirm + fingerprint + plan_version + request_key)
        │ one transaction: compare-and-set plan version → reload → re-plan → write → audit
        ▼
after commit: recalculate project, emit "project.template_reconciled" to automation (§8)
```

- **Service:** `app/services/template_reconciliation.py`. Preview and apply use the same
  `load_snapshot` and `build_plan`, so what is applied is exactly what was previewed.
- **The template can now be changed at any time**, including after completed milestones,
  hours, assignments and comments. It is still blocked for archived, deleted and cancelled
  projects, and for a completed project if the change would add required milestones.
- The legacy `apply-template` endpoint now only applies a first template to a project with no
  milestones. Otherwise it returns 409 and points to Change Template. It never deletes.
- A project needs a project type before its template can be changed. All 24 projects on the
  database copy have no type yet (§11).

## 4. Matching and duplicate rules

Template milestones are matched to existing milestones in this order. **Name similarity on its
own never produces an automatic match.**

| Classification | Rule | Applied automatically |
|---|---|---|
| Confirmed | Same template milestone id; or same lineage across template versions; or same template family and same normalised name; or same normalised name with a compatible stage | Yes |
| Likely | Same normalised name but the stage conflicts | No; the user chooses |
| Possible | Token similarity ≥ 0.5 (stop-words removed) and a compatible stage | No; the user chooses |
| Different | None of the above | Never offered |

- Names are normalised by lower-casing, turning `&` into "and" and removing punctuation.
- A match is one-to-one, and the chosen milestone must be one of the listed candidates.
- A template milestone with a confirmed match cannot be added as new.

**Duplicates** are pairs of existing active milestones, classified the same way. The canonical
(surviving) milestone is chosen in this order:

1. completed first, earliest completion first;
2. linked to the target template;
3. most advanced status;
4. oldest.

Only **confirmed** duplicates default to merge. Likely and possible duplicates default to
"keep both".

## 5. Merge, lifecycle and preservation

`milestones.lifecycle_state` (`active`, `merged`, `superseded`, `archived`) is separate from
`status`, so workflow status and completion history are never rewritten.

- **Nothing is physically deleted.** A merged milestone keeps:
  - its status, completion date and hours;
  - its comments and history;
  - `merged_into_id`, pointing at the canonical milestone.
- Timesheet entries are never re-pointed.
- If the canonical milestone has no owner, it takes the merged milestone's owner.
- Dependents are reconnected:
  - On a merge, dependents move to the canonical milestone, and the merged milestone's
    predecessors carry over.
  - On supersede or archive, dependents bridge to the removed milestone's predecessors. This
    also works along chains.
- A completed milestone is **never** merged into an incomplete one. Preview and apply both
  refuse it.
- Milestones in the new template can only be kept.
- Existing milestones missing from the new template are **kept by default**. The user may
  supersede, archive or merge them.
- Inactive milestones are excluded from planned hours, progress, counts, health, stage gates,
  stage sync, scheduling, dashboards, reports, KPIs, AI context, the Control Tower metrics,
  calendar and resource planning, so nothing is counted twice.
  - Their **actual hours still count** in project actuals, because the hours were really worked.
  - Delete-eligibility counts, the activity feed, performance reviews and baseline snapshots
    deliberately still see them.
- Inactive milestones cannot be edited or deleted (409). A milestone that others were merged
  into cannot be deleted either.
- **Dependencies:**
  - Template dependencies are added only if they create no loop.
  - A completed milestone is never made to wait for a new one; a warning is shown instead.
  - The final graph is checked for cycles before commit.
- **Dates:**
  - New milestones get a due date only from the project start date plus the template offset,
    and never a date in the past. Otherwise they are left unscheduled and the reason is shown.
  - Existing due dates are never changed.
- **Owners:** only the existing assignment rules (template default user, template role mapped
  to the project team) are used. Otherwise the milestone is left unassigned and a warning is
  shown.
- **Hours:** new milestones start at 0 planned hours unless the user opts into template
  estimates. A change in planned hours needs an explicit acknowledgement.
- **Progress:** completed stays completed. The existing stage-sync rule runs inside the
  transaction, so adding required work reopens the stage. The preview warns if the change
  would leave every required milestone closed.

## 6. Preview and apply

- **The preview has five sections:**
  - A. Completed and in-progress work kept
  - B. Template milestones matched to existing work, with choices for likely and possible matches
  - C. New milestones, with position, due-date rule, owner rule and dependencies
  - D. Possible duplicates, with merge or keep both, and what is preserved
  - E. Existing milestones not in the new template, with keep, supersede, archive or merge
- Alongside the sections it shows:
  - counts;
  - dependency changes;
  - planned hours before and after;
  - warnings and blockers;
  - the rules applied.
- **The confirmation step** restates the counts, takes an optional reason, and needs an "I have
  reviewed" tick, plus the estimate acknowledgement when planned hours change. Cancel at any
  step changes nothing.
- **Apply:**
  - It is one transaction. A compare-and-set on `projects.milestone_plan_version` rejects
    concurrent applies with 409.
  - It reloads the snapshot and recomputes the fingerprint. If the project changed after the
    preview (another user, a milestone edit, a template edit), it returns 409 "Preview again".
  - Any failure rolls back everything. The failure is recorded in its own row with
    `status = failed` and the error message.
- **Idempotency:** the client sends a `request_key`. Re-sending it returns the stored result with
  `replayed: true` and changes nothing.

## 7. Versioning

- Editing a template **never** changes projects.
- `project_template_milestones.lineage_id` follows a milestone across template versions:
  new versions copy it from their source row. Existing rows have no lineage, so readers fall
  back to the row id, and family-plus-name matching covers them.
- `projects.milestone_plan_version` increases on every applied reconciliation.
- `project_template_reconciliations` records:
  - the previous and new template, with versions;
  - counts;
  - the reason, the confirming user and the time;
  - `decisions_json`: request key, existing ids, added, matched, retained, merged pairs with
    completion dates and hours, superseded, archived, relinked, dependency and order changes,
    planned hours, options, project stage, warnings and the confirmation.
- The Change Template dialog has a **History** tab.
- When a newer version of a project's template becomes active, the "Template update available"
  rule recommends a review. It never updates the project.

## 8. Automation rules (Part C)

**Engine:** `app/services/automation/engine.py`.

- Rule definitions live in code. `automation_rules` only stores the on/off switch and the
  last-run state, and **every rule is off until an administrator enables it**.
- Each evaluation of a rule for one target is one `automation_executions` row. It records:
  rule, trigger, actor, target, project, status, summary, result, error, attempts, review,
  start and finish.
- `dedupe_key` is unique, so a repeated event, a re-run sweep or two racing workers act at most
  once.
- The action runs in a savepoint. A failure leaves no partial changes and is recorded as
  `failed`. Retries happen only when an administrator asks.
- Actions are in-app notifications (through the existing `create_notification`, no email) and
  `pending_review` recommendations. Rules never approve, pay, assign, complete or change status.
- **Triggers:**
  - Events are emitted after commit from the reconciliation apply and from milestone completion
    (`crud/milestone.update`). An automation error never blocks the user's change.
  - Sweeps run through the existing job queue (`automation_sweep` job type, or `python -m
    app.jobs.runner --automation`), or from "Run scheduled rules now" on the admin page.

| Rule | Trigger | What it does | Dedupe |
|---|---|---|---|
| Template change notice | Reconciliation applied | Tells the design leader, designer and surfacer what changed (not the person who applied it) | Per reconciliation |
| New milestones without an owner | Reconciliation applied | Asks the design leader to assign the added milestones that have no owner | Per reconciliation |
| Milestone ready to start | Milestone completed | Tells the owner of each waiting milestone whose predecessors are now all closed. **Never changes its status** | Per milestone and completion |
| Overdue milestone alert | Daily sweep | One alert per milestone and due date; links the open Control Tower finding. Moving the due date re-arms it once | Milestone and due date |
| Template update available | Daily sweep | `pending_review` recommendation plus a notice to the design leader | Project and template version |
| Live project without a designer | Sweep | Tells the design leader, or creates a review item if there is no leader | Project and ISO week |

**Catalogued, not moved** (they keep running in their own modules, with their own settings and
dedupe; the page shows them as "External" and they cannot be switched here):

- timesheet workflow notifications;
- quote-not-invoiced and payment follow-up reminders (Finance: no auto-approval, no payments);
- IT renewals and the ticket SLA sweep;
- new-hire onboarding;
- the Control Tower evaluation.

**Admin API** (`/api/v1/automation`, administrators only, enforced on the backend):

| Endpoint | Purpose |
|---|---|
| `GET /rules` | Rule definitions plus state |
| `PATCH /rules/{key}` | Switch a rule on or off; audited, 409 for external rules |
| `POST /run-sweeps` | Run the enabled sweep rules now |
| `GET /executions` | Execution history, filterable |
| `POST /executions/{id}/retry` | Retry a failed execution |
| `POST /executions/{id}/review` | Acknowledge or dismiss a recommendation |
| `GET /decision-audit` | The searchable decision audit (§9) |

**UI:**

- Admin → System Settings → **Workflow Automation**: rules, definitions, switches, history,
  failures, retry and review.
- Admin → Audit → **Decision Audit**.

## 9. Audit (§15)

- **Activities:**
  - `project_template_reconciled` for each applied change;
  - `milestone_lifecycle_changed` for each merged, superseded or archived milestone;
  - `milestone_created` for each added milestone;
  - `automation_rule_changed` with the old and new state and the reason.
- **The reconciliation row** holds the previous and new template, the milestone ids for each
  action, the confirmation and the reason (§7).
- **The Decision Audit** joins reconciliations, lifecycle changes, rule switches and automation
  executions. For each entry it shows: actor, action, target, project, previous and new values,
  trigger, reason, approval or review reference, result, error and time.
  - It is searchable by text, type, project and date.
  - It is **administrators only**.

## 10. Files

**New:**

- `app/models/workflow.py`
- `app/db/phase110_workflow_reconciliation_schema_sync.py`
- `app/services/template_reconciliation.py`
- `app/services/milestone_lifecycle.py`
- `app/services/automation/{__init__,engine,rules,events}.py`
- `app/schemas/template_reconciliation.py`
- `app/api/v1/automation.py`
- `frontend/src/services/templateReconciliationService.ts`
- `frontend/src/components/projects/TemplateReconciliationPreviewView.tsx`
- `frontend/src/api/automation.ts`
- `frontend/src/pages/admin/{AutomationPage,DecisionAuditPage}.tsx`
- `tests/test_template_reconciliation.py`
- `tests/test_workflow_automation.py`

**Changed:**

- Models, enums and the project schema (lifecycle fields and `depends_on_ids` on `MilestoneRead`).
- `crud/project_template.py` (lineage), `crud/milestone.py` (completion event),
  `crud/project_metrics.py`.
- `project_template_service.py` (old blockers removed, legacy endpoint made safe).
- `milestone_workspace_service.py`.
- API: `projects.py` (three endpoints), `milestones.py` (inactive milestones protected,
  `include_inactive`), `api.py`.
- `job_queue.py`, `jobs/runner.py`, `main.py` (migration registration).
- Active-lifecycle filters in about 30 read paths (listed in §5).
- Frontend: `ChangeProjectTemplateDialog.tsx` (rewritten), `ProjectFormDialog.tsx`,
  `ProjectDetailPage.tsx`, `types/Milestone.ts`, `App.tsx`, `config/adminNavigation.ts`.
- `tests/test_project_templates.py`: two tests updated for the new, intended behaviour.

## 11. Migrations and data safety (Part D)

`ensure_phase110_workflow_reconciliation_foundation` is additive only:

- **New tables:** `project_template_reconciliations`, `automation_rules`, `automation_executions`.
- **New columns:**
  - `milestones`: `lifecycle_state` (NOT NULL DEFAULT 'active'), `merged_into_id`,
    `lifecycle_changed_at`, `lifecycle_changed_by_id`, `lifecycle_reason`, `reconciliation_id`;
  - `projects.milestone_plan_version` (NOT NULL DEFAULT 0);
  - `project_template_milestones.lineage_id`.
- Three indexes.
- PostgreSQL enum values are added with `ADD VALUE IF NOT EXISTS`.
- Nothing is dropped or renamed. No values are invented.

**Checked on the disposable copy** (`%TEMP%\phase110_migration_check.py`; stages: copy,
migrate, compare, migrate again, idempotent, readback, idempotent):

- **All 166 pre-existing tables are unchanged**: same row counts and the same content hash over
  the original columns.
- The new columns were added as listed above.
- **New tables:** the three phase-110 tables, all empty. The copy also gained the Phase 2–4
  tables, because the backend has never run on this database.
- **Backfill:**
  - milestones: 168, all `active`;
  - merged or reconciliation links: 0;
  - projects: 24, all at plan version 0;
  - template milestones: 100, lineage empty as designed.
- A second migration run made **no differences**.
- **Read-back:**
  - **24 of 24** previews succeeded, 1 with a blocker, 0 errors;
  - 168 milestones matched with confirmed classification, 0 additions, 0 review items, 0
    duplicates;
  - 13 rules registered, 0 enabled.

  The projects have no project type, so the read-back assigned Mold Design inside a transaction
  that was rolled back. The copy was byte-identical by table hash afterwards.

**Rollback:** the new columns are defaulted or nullable and older code ignores them. Dropping
the three new tables removes the feature. Merged, superseded or archived milestones would then
count again as ordinary milestones, so restore them first if that matters.

**Concurrency and failure:** a compare-and-set plan version plus the snapshot fingerprint (409),
a unique `(project_id, request_key)`, a unique automation `dedupe_key`, one transaction per
apply with full rollback, failures recorded separately, and automation savepoints.

## 12. Tests (executed 2026-10-30)

| Command | Result |
|---|---|
| `pytest tests/test_workflow_automation.py tests/test_template_reconciliation.py tests/test_project_templates.py` | **49 passed** |
| Full backend suite (`DATABASE_URL` set to a temporary file) | **1342 passed, 12 failed, 1 skipped** (45 min 46 s). The 12 failures are exactly the 12 baseline failures in `PHASE0_QUOTE_TO_DELIVERY_AUDIT.md` §3; none is new |
| `npx tsc -b` | Passed |
| `npm run build` | Passed |
| `npx eslint` on new and changed frontend files | New files clean. Pre-existing: `adminNavigation.ts:287` unused `_roleName`; `ProjectFormDialog.tsx` set-state-in-effect at lines 353 and 374 |
| `ruff --select F,E9` on new and changed backend files | New files clean. 7 findings, all present at HEAD (`api.py` unused imports, `crud/milestone.py`, `milestone_workspace_service.py`) |

**Reconciliation scenarios.**

- One test per acceptance scenario:
  1. Blockout-only template changed to the full template
  2. Change with pending milestones
  3. Similar names are not matched or merged
  4. Two completed duplicates merge into one
  5. Completed and pending duplicate
  6. Downgrade keeps everything until the user archives
  7. Cancelled and superseded milestones are not reactivated
  8. A cancelled preview changes nothing
  9. A failure rolls back and records the error
  10. Repeated application is idempotent
- Safety tests:
  - a completed milestone is never merged into an incomplete one;
  - apply requires confirmation;
  - a stale preview after a concurrent edit is rejected;
  - the legacy endpoint no longer replaces milestones;
  - a read-only user gets 403;
  - dependencies follow the template rules with no cycles;
  - template hours need the estimate acknowledgement;
  - existing due dates never change;
  - a renamed milestone matches through version lineage.

**Automation (§20).**

- Rules are off by default and do nothing.
- Admin only (project manager, read-only user and design leader get 403).
- External rules cannot be switched, and switches are audited.
- "Ready to start" notifies without changing status, and a repeat event is deduplicated.
- The overdue sweep links the Control Tower finding, never duplicates, and re-arms on a new
  due date.
- The overdue sweep ignores inactive milestones and archived projects.
- A failed action is rolled back and recorded, is not retried automatically, and a manual retry
  succeeds.
- A template update is only recommended, then reviewed, with the project unchanged.
- A project without a designer is flagged once per week.
- The reconciliation event notifies the owners and appears in the decision audit.

**Not verified:**

- No browser check. As instructed, the UI was verified only by type-check and build.
- PostgreSQL migration (only SQLite was run).

## 13. Limitations

- **Partial:**
  - Phase 5 covers Projects and Resource Planning.
  - Timesheet, Finance, IT and onboarding automations are catalogued, not moved, so their
    history is not in the engine's execution log.
  - No email channel for engine rules.
  - No per-rule parameters such as thresholds or recipients.
- **Not yet supported:**
  - Rule scheduling inside the app needs the existing runner (`--automation`) on a scheduled
    task.
  - There is no in-process scheduler.
- **Pre-existing, not changed:**
  - Timesheet entries do not validate their milestone, so hours can still be booked to an
    inactive milestone through the API.
  - The activities endpoints are unscoped (Phase 0 S-series).
- **Data:** every project in the development database lacks a project type. Change Template
  asks for the type first.
- **The decision audit** merges sources in memory per page, which is fine at current volumes.
  It filters lifecycle activities by project via the milestone.
- **Template lineage** is empty for template rows that existed before this change. Those rows
  match by family and name instead.

## 14. Next increment

1. Move timesheet and finance reminders into the engine, keeping their dedupe keys, so all
   automation history is in one place.
2. Per-rule parameters (thresholds, recipients) and an optional email channel through the
   existing notification settings.
3. Validate the timesheet milestone against the lifecycle (block booking to inactive milestones).
4. A PostgreSQL migration run on a staging copy.
5. A browser walkthrough of Change Template and the Automation pages.
6. Decide the open Phase 1 question on draft and rejected hours.
