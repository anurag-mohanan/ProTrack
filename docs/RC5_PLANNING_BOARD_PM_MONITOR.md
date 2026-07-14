# Planning Board RC5 — Program Manager operations monitor

## Ops / Engineering Manager brainstorm → Senior developer decision

Wall monitors (Planning Board role) and Program Managers need a **single glance** surface that answers:

1. Are we on track this week? (KPIs)
2. What is due / late? (Deliveries coming up + Late)
3. What is live **by team**? (Team-wise live projects)
4. Where is capacity / who is overloaded?
5. What just released / who owns customer load?

### Approved layout (top → bottom)
| Zone | Content |
|------|---------|
| Chrome | Company **logo**, **Home** button, title, signed-in user, Sign out |
| KPI strip | Active projects, utilization, late milestones, hours, capacity, health G/Y/R |
| Deliveries | Two equal panels: coming up (≤7 days) \| late (past due) with tool / customer / team / designer / due / health |
| Team live | Always-visible team boards (no accordion) with live + on-hold tools (red/yellow first) |
| Footer row | Capacity snapshot \| Recent releases (30d) \| Customer load |

Read-only; 60s refresh; no assignment edits from monitor account.

**Giant-screen visual system:** navy wall chrome, oversized KPIs, color-coded delivery panels, LIVE pulse — see `docs/RC5_PLANNING_BOARD_WALL_VISUAL.md`.

### Code touched
- `app/schemas/ai.py` — `WallProjectCard`, `WallTeamLiveBlock`, wall fields
- `app/services/ai/modules/executive_wall.py` — builds `teams_live`, `upcoming_deliveries`, `late_deliveries`
- `frontend/src/layouts/PlanningBoardLayout.tsx` — wall chrome (logo plate, LIVE, Home)
- `frontend/src/pages/PlanningBoardPage.tsx` — distance-readable PM sections
- `frontend/src/types/Ai.ts` — wall types

## Testing team

| # | Check | Pass |
|---|--------|------|
| 1 | Login as Planning Board | Logo visible on white plate in header |
| 2 | Home button | Returns to role home (`/planning-board` for PB; dashboard for other roles) |
| 3 | KPI strip | Six metrics populate; readable from ~4m |
| 4 | Deliveries coming up | Large rows for due-soon tools (or empty message) |
| 5 | Late deliveries | Past-due tools listed; visually distinct (red) panel |
| 6 | Team-wise live | Team boards always open; tools show designer/due/health |
| 7 | Capacity / releases / customers | Footer panels load |
| 8 | Auto refresh | Data refreshes ~60s without edit controls |
| 9 | Write blocked | Assign / admin users still 403 |

## QC before UAT

- [ ] Logo + Home present  
- [ ] Team sections and delivery panels match live data  
- [ ] No edit controls on monitor  
- [ ] Deploy API + `frontend/dist`  
- [ ] Sign-off → user testing  
