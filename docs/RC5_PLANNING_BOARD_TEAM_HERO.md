# Planning Board — Team-hero wall (Ops / EM redesign)

## Ops + Engineering Manager brainstorm → Senior developer decision

**Problem:** Footer panels (capacity snapshot, recent releases, customer load) and equal-weight delivery tables diluted the wall. Walk-by viewers need to see **who is on which tool, what stage it is in, and how complete it is**.

### Approved layout
| Zone | Role |
|------|------|
| Lean KPI strip | Active · Late milestones · Late deliveries · Due in 7 days · Health G/Y/R |
| **Hero (left ~75%)** | **Team-wise live projects** — tool, customer, **stage**, **designers** (designer / leader / surfacer), **progress bar** |
| **Right rail (~25%)** | Compact **Late deliveries** then **Coming up** lists |

Removed from Planning Board UI: capacity snapshot, recent releases, customer load, resource-planning capacity query.

### Backend (wall card enrichment)
`WallProjectCard` adds:
- `progress_percent` — milestone completion % via `batch_calculate_progress`
- `contributor_names` — ordered unique designer, design leader, surfacer

Code: `app/schemas/ai.py`, `app/services/ai/modules/executive_wall.py`  
UI: `frontend/src/pages/PlanningBoardPage.tsx`, `frontend/src/types/Ai.ts`

## Testing team

| # | Check | Pass |
|---|--------|------|
| 1 | Team-wise section dominates the board | |
| 2 | Each live card shows stage + designers + progress % bar | |
| 3 | Late / Coming up appear as compact lists on the right (stack under hero on narrow) | |
| 4 | Capacity / releases / customer load **not** shown | |
| 5 | KPI strip is lean (no hours / team capacity) | |
| 6 | 60s refresh; data matches teams with live tools | |
| 7 | API cards include `progress_percent` and `contributor_names` | |

## QC before UAT
- [ ] Functional + visual checklist PASS on office TV  
- [ ] Progress bars readable at distance; stage/designer text clear  
- [ ] Deploy API + `frontend/dist`  
- [ ] Sign-off → user testing  

Companion visual QA: `docs/RC5_PLANNING_BOARD_WALL_VISUAL.md`  
No-scroll wall QA: `docs/RC5_PLANNING_BOARD_NO_SCROLL.md`
