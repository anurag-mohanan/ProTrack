# Planning Board — Quoted vs actual hours + variance

## Ops + Engineering Manager brainstorm → Senior decision

Team leaders need burnout/overrun signals on the wall without opening project detail.

### Approved metric line (per tool)
`Q {quoted}h · A {actual}h · {±variance%}`

| Signal | Meaning |
|--------|---------|
| Green % | Under quote (actual &lt; quoted) |
| Red % | Over quote (actual &gt; quoted) |
| `n/a` | No quoted hours to compute variance |

Variance = `(actual − quoted) / quoted × 100` when quoted &gt; 0 (same as team reports).

### Code
- `app/schemas/ai.py` — `quoted_hours`, `actual_hours`, `variance_hours`, `variance_percent`
- `app/services/ai/modules/executive_wall.py` — `_hours_metrics`
- `frontend/src/pages/PlanningBoardPage.tsx` — hours line under designer/surfacer
- `frontend/src/types/Ai.ts`

## Testing team

| # | Check | Pass |
|---|--------|------|
| 1 | Each live tool shows Q / A / variance % | |
| 2 | Over-quote tools show positive % in warning/red tone | |
| 3 | Under-quote tools show negative % in green tone | |
| 4 | Zero quoted hours → variance `n/a` | |
| 5 | Active / On hold sections still correct | |
| 6 | Single-screen / room filter still OK | |

## QC before UAT
- [ ] Spot-check 2–3 tools against project detail hours  
- [ ] Deploy API + frontend dist  
- [ ] Sign-off → user testing  
