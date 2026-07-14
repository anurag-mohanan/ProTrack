# Planning Board — Single-screen / no-scroll wall

## Ops + Engineering Manager brainstorm → Senior developer decision

**Constraint:** Fixed office TV. Viewers must understand the board **at a single glance** with **no scrolling**.

### Approved approach
| Rule | Implementation |
|------|----------------|
| Locked viewport | Layout uses `100dvh` + `overflow: hidden` |
| Compact chrome | 56px header (logo · title · LIVE · clock · Home) |
| Lean KPI strip | One horizontal row of 5 metrics (not tall tiles) |
| Hero fits height | Team columns fill remaining height |
| Auto-fit rows | `ResizeObserver` shows only as many project/delivery rows as fit |
| Overflow signal | `+N more` / `+N teams` when content exceeds viewport |
| Risk first | Teams sorted by red/yellow; projects already health-sorted |

### Removed / reduced for glanceability
- Page scroll
- Tall KPI cards and large padding
- Showing all projects when they would force scroll

### Code
- `frontend/src/layouts/PlanningBoardLayout.tsx`
- `frontend/src/pages/PlanningBoardPage.tsx`

## Testing team — wall TV QA

| # | Check | Pass |
|---|--------|------|
| 1 | Page does **not** scroll vertically at 1080p / office TV resolution | |
| 2 | Entire board readable without mouse wheel or remote scroll | |
| 3 | Team columns show stage, designers, progress in dense rows | |
| 4 | Late / Coming up rail visible on the right (desktop/TV width) | |
| 5 | `+N more` appears when more tools exist than fit | |
| 6 | 60s refresh keeps layout stable (no jump to scroll) | |
| 7 | Hard-refresh after deploy shows new bundle | |

## QC before UAT
- [ ] No-scroll checklist PASS on the real room display  
- [ ] Single-glance: priority tools (red/yellow) visible first  
- [ ] Deploy API + `frontend/dist`  
- [ ] Sign-off → user testing  
