# Planning Board — Active then On hold subsections

## Ops + Engineering Manager brainstorm → Senior decision

Walk-by viewers need to see **running work first**, then parked tools, without mixing them.

### Approved layout (per team column)
1. **Active** — `currently_being_worked_on` + `planning` (health-sorted within)
2. **On hold** — `on_hold` subcategory underneath (slightly muted rows)

Team header chips: `N active` · `M hold` (hold chip only when M > 0).

### Code
- `app/schemas/ai.py` — `on_hold_count` on `WallTeamLiveBlock`
- `app/services/ai/modules/executive_wall.py` — counts + Active-then-Hold ordering
- `frontend/src/pages/PlanningBoardPage.tsx` — subcategory labels
- `frontend/src/types/Ai.ts`

## Testing team

| # | Check | Pass |
|---|--------|------|
| 1 | Active tools listed under **Active** heading | |
| 2 | On-hold tools under **On hold** below Active | |
| 3 | Header shows active + hold counts | |
| 4 | No on-hold tools → On hold section omitted | |
| 5 | Only on-hold → Active omitted; On hold still shown | |
| 6 | Room filter / placeholders still work | |

## QC before UAT
- [ ] Visual check on office TV  
- [ ] Deploy API + frontend dist  
- [ ] Sign-off → user testing  
