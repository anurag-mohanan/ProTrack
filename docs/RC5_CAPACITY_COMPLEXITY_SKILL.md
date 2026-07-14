# RC5 — Capacity accuracy + project complexity + designer skillset

## Ops + Engineering Manager brainstorm → Senior decision

### Problems
1. Designers with live tools still appeared as **Open** (Resource Availability / planning chips).
2. Resource Planning showed absurd util (183–499%), **NaN%** customer share, and still listed **Planning Board**.
3. Assigning work lacked **project complexity** and visible **designer skill level**.

### Ideas → locked

| Topic | Decision |
|-------|----------|
| Open vs Assigned | Anyone on `planning` / `currently_being_worked_on` / `on_hold` as designer **or** DL **or** surfacer is **not Open**. Manual `availability_status=allocated` also counts as Assigned. |
| Hours attribution | Primary **designer** owns 100% of remaining hours. Separate DL gets **15%** oversight only (not a second full copy). Surfacer gets **40%** when designer also set, else 100%. |
| Overdue / undated tools | Remaining hours spread over a **14-day** runway (not zero / crash on null due dates). |
| Status chip on RP | Derived from **load** (`open` / `allocated` / `overloaded` / `on_leave`), not stale User flag alone. |
| Customer Allocation NaN | Coerce hours with `toFiniteNumber`; dedupe tools. |
| Complexity | New `projects.complexity`: `low` \| `medium` \| `high` \| `expert` (default medium). |
| Skillset | Reuse `users.skill_level`; surface on RP left list + availability rows. |
| Planning Board | Already excluded via `NON_CAPACITY_RESOURCE_ROLES` (restart API for backfill). |

### Ideas parked
- Automatic skill ↔ complexity match score / “recommended assignee”
- Cap displayed util at 100% (rejected — EM wants overload truth visible)
- Separate capacity for Design Leaders’ own project load vs oversight

## Senior-approved code

| Area | Files |
|------|--------|
| Availability | `app/services/dashboard_service.py` |
| RP math / status / skill / complexity on blocks | `app/services/resource_planning_service.py`, `app/schemas/resource_planning.py` |
| Schema | `ProjectComplexity` enum, `projects.complexity`, `phase20_project_complexity_schema_sync.py` |
| Project APIs / form | `app/schemas/project.py`, `ProjectFormDialog.tsx`, `types/Project.ts` |
| Wall | `WallProjectCard.complexity`, Planning Board row label |
| NaN customer % | `ResourcePlanningRightPanel.tsx` |
| RP UI | `ResourcePlanningLeftPanel.tsx` status + skill chips |

## Testing checklist

| # | Check | Pass |
|---|--------|------|
| 1 | Restart API (phase20 + KPI backfill) | |
| 2 | Dashboard Resource Availability: no Open row for people with planning/CBW/on-hold tools | |
| 3 | Surfacers on live tools are Assigned, not Open | |
| 4 | RP left list: no Planning Board; Assigned/Overloaded chips match load | |
| 5 | Util % lower than before for Design Leaders who only oversee | |
| 6 | Customer Allocation: no `NaN%` | |
| 7 | Create/edit project: Complexity field saves and returns | |
| 8 | Admin user skill_level shows under RP designer secondary text | |
| 9 | Planning Board wall cards show complexity when set | |
| 10 | Hard refresh frontend after deploy | |

## Testing lead → QC

- [ ] Smoke Dashboard availability, Resource Planning weekly grid, Project form, Planning Board wall  
- [ ] Spot-check a DL who is not designer on many tools — util should drop vs old double-count  
- [ ] Sign-off → user testing  
