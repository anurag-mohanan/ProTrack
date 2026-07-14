# Planning Board — Room team filter (Ops / EM)

## Ops + Engineering Manager brainstorm → Senior decision

**Problem:** Wall TVs in different rooms need different team views. Empty teams disappeared entirely, so rooms could not see “their” team columns until work was assigned.

### Approved approach
| Capability | Implementation |
|------------|----------------|
| Placeholders | API returns **all active company teams** (or filtered set), including zero-project columns |
| Room picker | **Room teams** dialog on the Planning Board — multi-select teams + optional room name |
| Persistence | `localStorage` on that display + bookmarkable `?teams=id1,id2` URL |
| API filter | `GET /ai/executive-wall?team_ids=<uuid>&team_ids=<uuid>` |
| Future multi-room | Each TV bookmarks its URL / saves its own local selection |

### Code
- `app/services/ai/modules/executive_wall.py` — empty team columns + `team_ids` filter
- `app/api/v1/ai.py` — `team_ids` query
- `frontend/src/pages/PlanningBoardPage.tsx` — Room teams control
- `frontend/src/components/planningBoard/RoomTeamsDialog.tsx`
- `frontend/src/utils/planningBoardRoom.ts`

## Testing team

| # | Check | Pass |
|---|--------|------|
| 1 | Default (no filter) shows **all active teams**, including empty placeholders | |
| 2 | Empty team shows “No live tools — waiting for assigned work” | |
| 3 | **Room teams** dialog lists company teams; save filters columns | |
| 4 | Reload keeps filter (localStorage); URL `?teams=` also drives filter | |
| 5 | Filtered room only shows selected teams; Late/Coming up scoped | |
| 6 | Page remains single-screen / no full-page scroll | |

## QC before UAT
- [ ] Room A / Room B simulated with two team selections  
- [ ] Deploy API + frontend dist  
- [ ] Sign-off → user testing  
