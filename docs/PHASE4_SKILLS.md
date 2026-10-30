# ProTrack — Phase 4: Engineering Knowledge and Skills Graph

Status: **first increment: verified skills matrix and relational foundation.** The knowledge
graph is **not** complete. What exists is a relational foundation (skills, relationships between
skills, employee-skill records with history, project evidence and project requirements). Graph
queries, customer knowledge nodes and visualisation are deferred (§11–§12).

Evidence base: `docs/PROTRACK_PHASE_VERIFICATION.md` (Phases 0–2), `docs/PHASE3_FORECASTING.md`,
`docs/PHASE0_QUOTE_TO_DELIVERY_AUDIT.md` §4.5, code inspection, and checks on a disposable copy
of `protrack.db` (`%TEMP%\phase4_migration_copy.db`, copied 2026-10-30).

---

## 1. Previous-phase status

| Phase | Status carried forward |
|---|---|
| 0 Audit | Complete. Open defects B0.1–B0.5 and S1–S3 are unchanged, except that the skills part of S1 is fixed here (§8) |
| 1 Reconciliation | Complete. The rule that draft and rejected hours count towards actuals is **still an open decision**; Phase 4 shows the status split rather than choosing |
| 2 Control Tower | Complete. Extended here with capability rules (§7); existing rules unchanged |
| 3 Forecasting | First increment only. The capacity supply forecast is reused unchanged for availability (§6); phased demand is still not modelled |

The full backend suite still has exactly the 12 failures that were already there before Phase 4 (§10).

## 2. Existing skills functionality (before Phase 4)

Inspection confirmed the three separate systems recorded in the Phase 0 audit:

1. **Stream skill matrix** (`StreamSkill`, `UserSkillRating`, `LearningPlan`): the Performance
   team skill matrix and a warn-only assignment fit check. **Left unchanged.**
2. **Foundation `Skill` / `UserSkill` / `EngineeringDiscipline`**: seeded with NX, Creo, CATIA,
   SolidWorks, AutoCAD and Moldflow. It had no verification, history or requirements, and the
   frontend never called it. The development database has **6 skills and 0 employee-skill rows**.
3. **`User.skill_level`**: a single display-only value. **Left unchanged.**

Phase 4 builds on system 2, the employee master's own skills tables. No parallel employee or
competency master was created.

Pre-existing defects found and fixed along the way:

- `GET /settings/skills` and `GET /settings/users/{id}/skills` needed no login (part of S1).
  Both now require a login, and the per-user endpoint applies the skills profile scope.
- `PUT /settings/users/{id}/skills` (admin only) **deleted** every record not in the payload.
  It now archives instead, and records an event for each change.
- The phase7 startup seed re-created a seeded skill after it was renamed. It now matches on
  the normalised name and on aliases.

## 3. Models reused and added

**Reused, with additive columns only:**
- `skills` (10 new columns): `kind`, `description`, `aliases`, `discipline_id`, `customer_id`,
  `is_critical`, `min_verified_coverage`, `specialist_level`, `reassessment_months`, `sort_order`.
- `user_skills` (16 new columns): `status`, `origin`, `declared_level`, `verified_level`,
  `verification_method`, `verified_at`, `verified_by_id`, `last_assessed_at`,
  `last_assessed_by_id`, `years_experience`, `last_used_on`, `employee_note`,
  `assessment_feedback`, `confidential_notes`, `status_changed_at`, `updated_by_id`.

  The legacy four-value `proficiency` column is kept and stays in step with the new level, so
  the old screens keep working.

**Reused without change:** `users`, teams and team membership (scope), `projects`, timesheets
and entries (experience hours), `customers`, `engineering_disciplines`, `activities` (audit),
the Phase 3 capacity forecast, and the shared engineering metrics.

**New tables** (`app/models/skills.py`):

| Table | Purpose |
|---|---|
| `skill_proficiency_levels` | Labels and descriptions for levels 1–5 (defaults: Awareness, Basic, Intermediate, Advanced, Expert) |
| `skill_relationships` | Relationship between two skills: `used_with`, `specialization_of`, `related`, `prerequisite` |
| `user_skill_events` | Append-only history of each employee-skill record (levels, status, method, feedback, confidential note, actor, time) |
| `user_skill_evidence` | A project cited as evidence for a record |
| `project_skill_requirements` | Skill and minimum level required by a project, mandatory or optional |
| `skill_development_plans` | Development, training and knowledge-transfer objectives |

New `ActivityAction` values: `skill_profile_changed` and `skill_taxonomy_changed`.

## 4. APIs and UI

**API** (`app/api/v1/skills.py`, prefix `/api/v1/skills`): access flags; taxonomy (skills,
category rename, relationships, levels, standard pack with dry run); my profile, declarations,
submit, archive, evidence; profiles, project experience and assessment; matrix; review queue;
gaps; development plans; project requirements; candidate match. Every rule is enforced in the
backend (§8).

**UI:**
- New **HR → Engineering Skills** page (`/skills`). Tabs: My skills, Matrix, Gaps,
  Development plans, Candidate finder, Taxonomy. Each tab appears only when the user's access
  flags allow it.
- The matrix offers a heatmap or a table and filters by team, category, type, software, minimum
  level, status, text search and critical-only.
  - Verified levels are green shades. Self-declared claims are dashed blue. Records needing
    reassessment are orange.
  - **No record shows as a dashed grey "·" labelled "Unknown — not level 0".**
  - Clicking a cell opens the profile drawer with the assess form, history and evidence.
- New **Resource Planning → Skill match** tab, which uses the same candidate finder.
- **Control Tower** shows a new "Skills capability" category.

## 5. Verification and proficiency rules

- **Levels 1–5 only.** A level is never derived from years of experience, project count, hours
  or licences.
- **Kept distinct:**
  - `declared_level`: the employee's claim;
  - `verified_level`: set only by a review decision;
  - `verification_method`: manager assessment, or independent verification (panel, test or
    certification);
  - `origin`: self, manager or legacy.
- **Statuses:** `self_declared`, `pending_verification`, `verified`, `rejected` (shown as
  "Not confirmed"), `needs_reassessment` and `archived`. A verified record is also shown as
  needing reassessment once the skill's `reassessment_months` have passed.
- **No silent change to a verified skill.**
  - A new claim on a verified record keeps the verified level and is flagged "new claim
    awaiting review".
  - Rejecting a claim on a verified record keeps the verified level.
  - Archiving a verified record requires an authorised reviewer.
  - Re-declaring an archived skill never carries the old verification over; the event keeps
    the old level.
- **Audit.** Every change writes a `user_skill_events` row and an `activities` entry. The
  activity entry never contains comments.
- **Confidential notes** are returned only to authorised reviewers of that employee, never to
  the employee or to view-only users.
- **Nobody assesses their own skills.**
- **Legacy rows** from the old settings endpoint become `origin = legacy`,
  `status = pending_verification`, with no 1–5 level, because the old four-value scale does not
  map onto the new one.

## 6. Resource Planning integration

- **Candidate finder:** uses a project's requirements, or ad-hoc requirements, plus a team and
  a horizon.
- **Suitability** uses verified records only:
  - confirmed: every mandatory skill is verified at or above its minimum level;
  - unconfirmed: relies on claims, reassessments or missing records;
  - below requirement: a mandatory skill is verified below its minimum level.
- **Availability** comes from the Phase 3 capacity forecast (allocatable hours in the horizon)
  plus current open-project commitments. Its values are *capacity indicated (preliminary)*,
  *uncertain*, *committed* and *unavailable*.
- Suitability and availability are **shown side by side, never combined into a score.** Nobody
  is described as "immediately available".
- **Never auto-assigns.** The endpoint rolls back its session, and a test confirms that
  assignments are unchanged.
- The capacity forecast's skill note now points to the candidate finder. Skill demand is still
  not phased by period.

## 7. Gaps, succession and Control Tower

- **Coverage** counts current verified records only, through one shared definition
  (`services/skills/coverage.py`) used by matching, the gap report and the Control Tower.
- **Critical skills** are a management flag on the skill (`is_critical`, with an optional
  minimum verified coverage and a specialist level, default 4). A skill is never marked critical
  because of its counts.
- **Gap findings:**
  - critical skill with no verified coverage (high);
  - critical skill with a single specialist (high);
  - critical skill with no holder at specialist level (medium);
  - critical skill below its target coverage (medium);
  - critical skill with records needing reassessment (medium);
  - non-critical single-specialist dependency (info).

  The report also covers team depth, project requirement coverage, training needs and overdue
  reassessments. People with no record are reported as *unknown*.
- **Development plans** record a baseline verified level, a target level, training, knowledge
  transfer, mentor, review date and status. **Completing a plan never changes proficiency**
  (tested).
- **Control Tower** (`RULES_VERSION` 2) has three capability rules on mandatory project
  requirements, organisation-wide and verified only:
  - `skill_requirement_uncovered` (medium);
  - `skill_no_confirmed_candidate` (medium): every requirement has holders, but nobody holds
    all of them;
  - `skill_requirement_single_specialist` (info).

  Each finding explains itself, shows counts and never names, and states: *"a missing record
  does not prove that nobody has the skill. This finding does not mean the project is
  delayed."* Delivery status is untouched.

## 8. Permissions and audit (backend-enforced)

| Role (defaults) | Own profile | View others | Assess | Taxonomy | Candidate match |
|---|---|---|---|---|---|
| Admin | Yes | All | All | Yes | Yes |
| HR, Office Administrator | Yes | All | All | HR `configure` | If Resource Planning access |
| Team lead, team leader, engineering manager, reviewer | Yes | Own teams | Own teams | No | If Resource Planning access |
| Performance editors | Yes | Accessible teams | Accessible teams | No | If Resource Planning access |
| Human Resources viewers, resource planners | Yes | Accessible teams | No | No | Resource planners only |
| Planning Board | Yes | All | **No** | No | Yes |
| Designer | Yes | No | No | No | No |

- Assessment scope follows `user_can_manage_team_reviews`, with one deliberate deviation:
  **Planning Board is excluded from reviewing.** It is a shared wall-monitor login, and a
  verified skill needs an accountable reviewer.
- Project evidence and experience reuse project visibility. A project the viewer cannot see is
  masked.
- Unknown team: 400. Out-of-scope team or profile: 403. No token: 401.

## 9. Migrations and data preservation

- **`phase109_engineering_skills_schema_sync`** is additive: `ALTER TABLE … ADD COLUMN` (nullable
  or defaulted) plus two indexes. The new tables come from `create_all`. On PostgreSQL it also
  adds the two enum values. It runs before phase7 at startup and is idempotent.
- **Check on a disposable copy** of `protrack.db`. Steps run: `create_all`, then phase109, then
  phase7 — the steps Phase 4 adds or changes. The full startup was not run, because it also
  fetches live FX rates, sends quote reminders and runs the SLA sweep.
  - **All 166 existing tables have identical row counts and content hashes** before and after,
    computed over the original columns.
  - New tables: the 6 skills tables (0 rows). The 3 `project_risk_*` tables from Phase 2 also
    appeared, because the copy had never been started with Phase 2 code.
  - Added columns: exactly the 10 and 16 listed in §3.
  - A **second run changed nothing**.
  - Data on the copy: 6 skills (5 CAD, 1 Analysis) and 0 employee-skill records, so there is
    nothing to backfill.
- **Standard pack, dry run on the copy:** it would add 25 skills (CAD software, mold design,
  surfacing, fixture and tooling, documentation). It recognises the existing "NX" as Siemens NX
  instead of adding a duplicate, and files Cimatron under the existing "CAD" category. Nothing
  was written. **Customer and workflow knowledge (category F) is not seeded**, because the
  entries can't be known without inventing data. Administrators add them as `customer_standard`
  skills linked to a customer.
- **`protrack.db` was never opened**; its last-write time is unchanged at
  `2026-10-29T12:20:48`.
- **Rollback.** Roll back the application code; the old code ignores the new columns and
  tables. To remove the schema, drop the six new tables (and, on PostgreSQL, the added columns).
  No existing column, table or value is altered. Records archived by the legacy endpoint can be
  identified from `user_skill_events`.
- No mock or seed records were created. The standard pack is an explicit, previewed
  administrator action.

## 10. Tests (executed 2026-10-30)

| Check | Result |
|---|---|
| `tests/test_engineering_skills.py` | **16 passed** |
| Full backend suite (`pytest`, disposable `DATABASE_URL`) | **12 failed, 1313 passed, 1 skipped** in 45 min 26 s. The 12 failures are exactly the ones already listed in `PHASE0_QUOTE_TO_DELIVERY_AUDIT.md` §3.1 (quote PDF extract patch targets, receivables aging, un-invoicing, timesheet pack naming, duplicate-week import, team salary roll-up, IT asset import); none involve skills. The suite grew from 1297 to 1313 passing (16 new skills tests) |
| Frontend `npx tsc -b` | exit 0 |
| Frontend `npm run build` | exit 0 (warnings only from third-party `@mui/x-virtualizer`) |
| ESLint on new and changed frontend files | clean. One existing `react-refresh/only-export-components` error remains in `AppBreadcrumbs.tsx` at line 183, which Phase 4 did not touch |
| Ruff (`F`, `I`, `E9`) on new and changed backend files | clean, except four findings already in `api/v1/api.py` at HEAD |
| Migration on the database copy | 166/166 tables unchanged; idempotent (§9) |
| Browser check | not done (skipped at the user's request; tests and build only) |

The 16 tests cover:
- taxonomy: duplicates across names and aliases (409), rename keeps an alias, deactivate;
- relationships: no self-links, duplicates or cycles;
- standard pack: dry run first, idempotent, reuses existing skills;
- configurable levels;
- a declaration is never a verification, and a missing record is not level 0;
- the full verification workflow, history, confidentiality and audit;
- unauthorised reviews and self-assessment are forbidden (403);
- archiving and re-declaring;
- project experience from real projects (12 h draft and 8 h approved shown separately;
  masking; never verifies a skill);
- matching keeps suitability and availability separate (on leave means unavailable; a claim is
  unconfirmed; assignments unchanged);
- gaps count only verified records, and criticality comes only from the management flag;
- development plans never change proficiency;
- legacy settings endpoints are authenticated and non-destructive;
- the phase109 migration on an old-shape SQLite database preserves rows, marks them
  legacy / pending, and is idempotent;
- the phase7 seed does not re-create a renamed skill;
- the Control Tower capability rules.

## 11. Limitations

- **There is no verified skills data yet.** Production-shape data has 0 employee-skill records,
  so every coverage, gap and Control Tower capability result will be "no verified coverage"
  until people declare their skills and reviewers verify them.
- **Knowledge graph:** only the relational foundation exists. There is no traversal (for
  example, "who has a prerequisite of X"), no inferred related skills and no graph view.
  Relationships are stored and validated only.
- **Customer and workflow knowledge** is supported only as a skill linked to a customer. There
  are no customer standard documents or workflows as entities.
- **Project history** does not record which CAD software or discipline was used. Experience
  shows roles from the current project fields (earlier reassignments are lost), and hours
  include draft and rejected timesheets (Phase 1 open decision).
- **Availability** is preliminary: there is no planned-leave model, no allocation model, and
  remaining work is not phased (Phase 3 limitations). Only designer hours count as committed
  remaining work.
- The **stream skill matrix**, `LearningPlan` and `User.skill_level` remain separate systems.
  Plans do not link to `TrainingCourse`; training is free text.
- **No notifications** are sent for the review queue or reassessment due dates.
- The PostgreSQL migration path is written but only SQLite was tested.
- `crud.foundation.replace_user_skills` is no longer called; it was left in place.

## 12. Next increment

1. Capture skills: employees declare theirs and reviewers verify. Load the standard pack after
   reviewing the dry-run preview.
2. Management marks critical skills and sets coverage targets; define project requirements on
   open projects.
3. Notifications for pending reviews and reassessments due.
4. Link development plans to `TrainingCourse` and assignments.
5. Decide whether the stream skill matrix fit check should read verified foundation skills, and
   how the three systems converge.
6. Graph queries on the relational foundation: prerequisites, related-skill substitutes in
   candidate search, and customer knowledge entities.
7. Once Phase 3 adds phased demand and allocations: period-level skill demand against verified
   supply.
