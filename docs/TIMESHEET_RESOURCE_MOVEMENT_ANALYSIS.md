# Timesheet resource movement — analysis

**Status:** Analysis complete; incremental implementation follows.  
**Does not rewrite existing timesheet rows.**

---

## Current behavior

### Models

| Entity | Team-related fields |
|--------|---------------------|
| `User` | `team_id` (live primary home), `org_department_id`, `stream_id` |
| `Team` / `TeamMember` | Live membership; `effective_from` |
| `TeamMembershipPeriod` | Dated primary-home stints (`effective_from` / `effective_to`) |
| `UserJobEvent` (`transfer`) | Transfer audit used to floor stints |
| `Project` | `team_id`, `stream_id`, `customer_id` — **work context** |
| `Timesheet` | `user_id`, `week_start` only |
| `TimesheetEntry` | `entry_date`, `hours`, `work_category`, `project_id`, `customer_id`, `task_type_id`, `non_productive_code_id` — **no home-team snapshot** |

Internal work (Training `C504`, Meetings, Leave, Internal Work, …) is `work_category = non_productive` with an NP code and **no project**.

Customer work is `productive` and is tied to `project_id` (customer copied from the project).

### How reports attribute team today

Timesheet / designer-by-team reports **do not** join `User.team_id` as the sole team for a month. They:

1. Build **membership windows** (`team_membership_windows.py`) from `TeamMembershipPeriod` + transfer floors, **primary home only**.
2. Filter entries to days the person was on the requested team (permission + historical roster).
3. Label hours with `primary_home_team_timeline` **as of `entry_date`**.

`User.team_id` is documented as **not** inventing full-range coverage after a transfer.

### Problem

1. **`TimesheetEntry` has no frozen home team.** Attribution is reconstructed every report. If periods are missing, backfilled to hire date, or floored incorrectly, hours move.
2. **Fallback is still `user.team_id`.** In `data_service._designer_productivity`, detailed timesheet export, and `cross_team_hours`, when the timeline does not cover `entry_date`, the code uses **current** home. After Mold → CAD, uncovered historical days can be labelled CAD.
3. **Single-team report relabel.** When the report is scoped to one team, productivity rows force `home_team = scoped_team_id` for every included entry. That is OK only if membership windows already excluded other days.
4. **Two different “team” meanings are mixed:**
   - **Resource home** (who the person belonged to that day) — correct for Training / meetings / leave.
   - **Work / project team** (`Project.team_id`) — correct for customer delivery. Working on a Mold project after moving to CAD must stay Customer A / Mold project, not become CAD delivery hours.
5. **Legacy `crud/team_reports.get_hours_by_team_report`** sums `Project.actual_hours` by `Project.team_id` only — training never appears there; dashboards that use `Project.actual_hours` are project-scoped, not home-scoped.

### What already works

- Dated transfers write `TeamMembershipPeriod` + job events (Users edit and Teams transfer).
- Team-filtered timesheet reports use membership windows so CAD-only viewers do **not** get Mold-era hours just because the person now sits on CAD.
- Cross-team hours compare home-as-of-date vs `Project.team_id`.
- Project / customer reports join `project_id` / `customer_id`, not live `User.team_id`.

---

## Recommended data model

Keep reconstructing from periods for **legacy rows**. For **new and edited** entries, snapshot context at write time:

| Column (on `timesheet_entries`) | Source at save | Used for |
|--------------------------------|----------------|----------|
| `home_team_id` (nullable FK → teams) | Primary home as of `entry_date` (`TeamMembershipPeriod` / live home if no period) | Internal hours; designer-by-team split |
| Existing `project_id` / `customer_id` | Unchanged | Customer / project / workstream via project |
| Existing `task_type_id` / NP code / `entry_date` / `hours` | Unchanged | Task and hours |

**Do not** snapshot workstream/department in this increment (no dated department history; stream lives on the project). They can be added later if needed.

### Attribution rules

| Kind | Team for **team timesheet / utilization** | Context for **customer / project / workstream** |
|------|-------------------------------------------|--------------------------------------------------|
| Internal (NP, leave, training, meetings, admin) | Home team **as of entry date** (snapshot, else timeline) | N/A (no project) |
| Customer / project | Home team as of date for “who booked it while on which roster”; **delivery team** = `Project.team_id` | Project, customer, stream on the project |

Never use live `User.team_id` when a timeline exists but does not cover that day (treat as unknown rather than the post-transfer home).

---

## Migration

- Add nullable `home_team_id` only. **No UPDATE of existing hours.**
- Existing rows keep `home_team_id = NULL`; reports use `TeamMembershipPeriod` reconstruction (same as today, with the safer fallback).
- New saves and imports stamp `home_team_id`.
- Optional later: one-off backfill from periods for NULL snapshots — **not** required to preserve history.

---

## Reporting impact

| Surface | Change |
|---------|--------|
| Monthly/weekly designer team timesheet | Prefer snapshot; stop current-team fallback when a stint timeline exists |
| Detailed timesheet export | Same |
| Cross-team hours | Prefer snapshot as home |
| Project / customer / workstream reports | Unchanged (project FKs) |
| Dashboard project hours | Unchanged (`Project.actual_hours` / project team) |
| Permission / team scope | Unchanged (membership windows) |

---

## Backward compatibility risks

- Low: nullable column; NULL means “use reconstruction.”
- Medium: removing `user.team_id` fallback for **gapped** timelines may show blank team on a few legacy rows instead of wrongly moving them to CAD — preferred.
- Team-scoped reports still include **all hours booked on days the person was on that team**, including work on another team’s project (shown as cross-team). Those hours stay on the **project** for customer/project reports.

---

## Target scenario (tests)

John: Mold Jan–Jul (10h training + 100h Customer A Mold project) → CAD in August → Sep (5h training + 30h Customer B CAD project).

| Team report | Training | Customer work |
|-------------|----------|----------------|
| Mold | 10 | 100 (Customer A / Mold project) |
| CAD | 5 | 30 (Customer B / CAD project) |

CAD-only data scope must not see January–July hours. Live `User.team_id` = CAD must not move July training onto CAD.

---

## Implementation (incremental, this change)

- Nullable `timesheet_entries.home_team_id` (phase 79). Existing rows stay NULL.
- New/edited entries and historical imports stamp home as of `entry_date`.
- Reports resolve: snapshot → membership timeline → **never** live `User.team_id` when a stint history exists.
- Customer/project delivery team remains `Project.team_id`. Post-transfer work on a Mold project stays on that project/customer and is cross-team vs CAD home.

