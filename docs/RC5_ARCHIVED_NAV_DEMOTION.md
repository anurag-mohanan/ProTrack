# RC5 — Demote archived items from Engineering Operations nav

## Ops + Engineering Manager brainstorm → Senior decision

### Question
Should **Archived Projects** (and other archived catalogues) sit in the Engineering Operations sidebar next to day-to-day work?

### Answer (locked)
**No.** Archived work is infrequent recovery/review — not a primary ops destination. It clutters the portal strip.

| Surface | Keep in Engineering ops nav? | Where instead |
|---------|------------------------------|---------------|
| Archived Projects | **No** | Projects page **Archived** button; Projects “Show archived” / quick filter; Admin → **Archived Records** |
| Archived customers / users / NP codes | Already **not** in ops nav | Admin management screens only |
| Route `/projects/archived` | Keep | Module-gated; Admin hub link unchanged |
| Module `archived_projects` defaults | Keep for EM/DL/Admin | Access preserved; not promoted in sidebar |

### Engineering Operations strip (after change)
Dashboard → Projects → Timesheets → Workload → Resource Planning → Calendar  
(+ Planning Board only when that module/role applies)

## Senior-approved code

| File | Change |
|------|--------|
| `frontend/src/utils/permissions.ts` | Remove Archived Projects from `NAV_MODULE_CONFIG` |
| `frontend/src/pages/ProjectsPage.tsx` | Secondary **Archived** action for users with the module |
| `docs/RC5_PROJECTS_WALL_AND_CALENDAR_GANTT.md` | Nav decision updated to match |

## Testing checklist

| # | Check | Pass |
|---|--------|------|
| 1 | Engineering Operations sidebar has **no** “Archived Projects” item | |
| 2 | Dashboard → Projects → Timesheets order still correct | |
| 3 | EM/DL Projects page shows **Archived** button → `/projects/archived` | |
| 4 | Designer without archive module: no Archived sidebar item, no Archived button | |
| 5 | Admin → Audit/Records → Archived Records still opens archived projects | |
| 6 | Direct URL `/projects/archived` still works for permitted roles | |
| 7 | Projects “Show archived” / Archived quick filter still works on Projects | |
| 8 | No “Archived Customers” (or similar) appears under Engineering Operations | |

## Testing lead → QC

- [ ] Smoke EM + Designer + Admin sidebars  
- [ ] Deploy `frontend/dist`, hard refresh  
- [ ] Sign-off → user testing  
