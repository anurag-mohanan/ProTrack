# Planning Board RC5 — Program Manager operations monitor

## Ops / Engineering Manager brainstorm → Senior developer decision

Wall monitors need a **single glance** surface focused on live team work:

1. Are we on track? (lean KPIs)
2. What is live **by team**, at what **stage**, with which **designers**, and what **% complete**?
3. What is late / due soon? (compact right rail)

### Approved layout (top → bottom / main + rail)
| Zone | Content |
|------|---------|
| Chrome | Company **logo**, **Home**, LIVE, clock, Sign out |
| Lean KPI strip | Active · Late milestones · Late deliveries · Due in 7 days · Health G/Y/R |
| **Hero** | **Team-wise live** — Active then **On hold**; stage, designer/surfacer, **Q/A/variance %**, progress |
| **Right rail** | Compact Late deliveries · Coming up (≤7 days) |

**Removed:** capacity snapshot, recent releases, customer load.

Read-only; 60s refresh; no assignment edits from monitor account.

**Giant-screen visual:** `docs/RC5_PLANNING_BOARD_WALL_VISUAL.md`  
**Team-hero redesign:** `docs/RC5_PLANNING_BOARD_TEAM_HERO.md`  
**No-scroll single screen:** `docs/RC5_PLANNING_BOARD_NO_SCROLL.md` — locked `100dvh`, auto-fit rows, `+N more`  
**Room team filter:** `docs/RC5_PLANNING_BOARD_ROOM_TEAMS.md` — per-display team selection + empty placeholders

### Code touched
- `app/schemas/ai.py` — `progress_percent`, `contributor_names` on `WallProjectCard`
- `app/services/ai/modules/executive_wall.py` — progress + contributors in teams_live
- `frontend/src/layouts/PlanningBoardLayout.tsx` — wall chrome
- `frontend/src/pages/PlanningBoardPage.tsx` — team hero + delivery rail
- `frontend/src/types/Ai.ts` — wall types

## Testing team

| # | Check | Pass |
|---|--------|------|
| 1 | Login as Planning Board | Logo visible on white plate |
| 2 | Home button | Returns to role home |
| 3 | KPI strip | Lean five metrics populate |
| 4 | Team-wise hero | Stage + designers + progress bar on cards |
| 5 | Right rail | Late + Coming up compact lists |
| 6 | Removed panels | Capacity / releases / customer load absent |
| 7 | Read-only | Assign / write endpoints still 403 |

## QC before UAT
- [ ] Testing matrix PASS on office TV  
- [ ] Progress & stage readable from ~4m  
- [ ] Deploy API + frontend dist  
- [ ] Sign-off → user testing  
