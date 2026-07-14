# Planning Board — Giant-screen visual redesign (UI/UX lead)

## Visual team + Ops/EM brainstorm → Senior developer approval

**Context:** Displayed on a large office wall TV. Viewers stand 3–8 metres away. Primary audience: Program Manager, Operations, Engineering Manager walk-bys.

### Design principles approved
| Principle | Application |
|-----------|-------------|
| Distance readability | KPI numbers ~2.5–3rem; tool numbers ≥1.1rem; section titles ≥1.25rem |
| Instant status | Color-coded panels (blue upcoming / red late); health chips; team rows edged by G/Y/R |
| Brand first | Navy wall (`#0F172A`) matching Prosohm sidebar; logo on white plate; primary blue accents |
| No interaction required | Teams always expanded (no accordion hunting); auto refresh 60s |
| Calm motion | LIVE pulse + light fade-up on panels only (no noise) |
| High contrast | Light text on dark panels; muted secondary labels |

Avoided: purple glow, dense desktop tables, tiny captions, cluttered card chrome.

### Visual zones
1. **Chrome** — Logo plate · large title · LIVE pill · clock · Home · user  
2. **KPI strip** — Oversized tiles with left accent bars  
3. **Deliveries** — Twin spotlight panels (coming up / late) as large rows  
4. **Team-wise live** — Two-column team boards with health edge bars  
5. **Footer** — Capacity · Releases · Customer load as readable blocks  

### Code
- `frontend/src/layouts/PlanningBoardLayout.tsx`
- `frontend/src/pages/PlanningBoardPage.tsx`
- Spec companion: `docs/RC5_PLANNING_BOARD_PM_MONITOR.md`

## Testing team — visual QA on real wall / 1080p+

| # | Check | Pass |
|---|--------|------|
| 1 | From ~4m, KPI numbers readable without squinting | |
| 2 | LIVE pill visible; logo clear on white plate | |
| 3 | Late panel visually distinct from upcoming | |
| 4 | Team cards show tool + customer + health without opening controls | |
| 5 | Home / Sign out usable if walked up to screen | |
| 6 | 60s refresh; no layout jump / flicker storms | |
| 7 | Empty states still elegant (not broken-looking) | |
| 8 | Light text contrast OK under office lighting | |

## QC before UAT
- [ ] Wall look matches brand navy + Prosohm blue (not generic purple)  
- [ ] Giant-screen checklist PASS on office TV  
- [ ] Functional delivery/team data still correct  
- [ ] Deploy API + frontend dist  
- [ ] Sign-off → user testing  
