# RC5 — Projects wall + Calendar Gantt + nav reorder

## Ops / Engineering Manager → Senior decisions

1. **Engineering ops nav:** Dashboard → Projects → Archived → Timesheets → Workload → Resource Planning → Calendar. Planning Board stays gated (PB role / explicit module grant), not in the shared ops strip for designers.
2. **Projects UI:** Planning Board–like compact rows (health edge, stage, designer/surfacer, Q/A/variance, progress, due). Visibility unchanged: `project_visibility_clause` (team + personally assigned).
3. **Calendar module:** Leaders (Engineering Manager, Design Leader, Admin) get `calendar` by default. Designer / Junior / Senior / Surfacer do **not**.
4. **Calendar = project Gantt:** Bars from `created_at` → `due_date` (or `completed_at`). Missing due shows TBD. Same visibility clause as projects.
5. **No Zoho quoting module** in this release.

## Code touchpoints

| Area | Paths |
|------|--------|
| Modules / nav | `app/core/access_control.py`, `frontend/src/config/accessControl.ts`, `frontend/src/utils/permissions.ts`, `frontend/src/App.tsx`, `frontend/src/utils/portalAccess.ts` |
| Projects wall | `frontend/src/components/projects/command-center/ProjectBoardList.tsx`, `ProjectListSection.tsx`, `ProjectsPage.tsx` |
| Gantt API | `GET /api/v1/calendar/project-timeline`, `app/services/calendar_service.py`, `app/schemas/calendar.py` |
| Gantt UI | `frontend/src/pages/EngineeringCalendarPage.tsx`, `frontend/src/api/calendar.ts` |

## Testing checklist

| # | Check | Pass |
|---|--------|------|
| 1 | Nav order: Dashboard → Projects → Archived → Timesheets → Workload → Resource Planning → Calendar | |
| 2 | Designer nav has no Calendar, no Planning Board | |
| 3 | EM / Design Leader nav includes Calendar | |
| 4 | Projects page shows compact wall rows (Active then On hold) | |
| 5 | Designer My Projects shows team + cross-util only | |
| 6 | Create project still works; new tool appears after refresh | |
| 7 | Calendar Gantt loads for EM/DL; bars click through to project | |
| 8 | Designer cannot open `/calendar` without module grant | |
| 9 | Timeline API hides other-team unassigned tools | |
| 10 | Planning Board still only for PB role / granted module | |

## QC before UAT

- [ ] Deploy API + `frontend/dist`
- [ ] Hard refresh browsers / TV stations
- [ ] Spot-check Designer, Design Leader, Engineering Manager accounts
- [ ] Sign-off → user testing
