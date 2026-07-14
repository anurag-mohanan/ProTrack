# RC5 — Projects readability + form dropdown label clarity

## Ops + Engineering Manager brainstorm → Senior decisions

### Problem (staging observed)
1. **Projects wall rows:** Designer/surfacer names and `Q/A/±%` hours painted on the same visual line (`Binil JR` + `Q 60h` → `Binil JRQ…`). High density rows also used a misleading **DONE** label on partial progress.
2. **Create/edit dropdowns:** Floating `InputLabel` overlapped selected values when tip icon markup was embedded in the label (notch width mismatch) or when shrink/notch were out of sync.

### Approved design decisions
| Area | Decision |
|------|----------|
| Projects meta | Three clear stacked lines: **stage · customer** → **people** → **Q · A · ±%** (own flex row, never inline with names) |
| Progress | Relabel **DONE** → **Progress**; keep % + bar |
| Dropdown labels | Plain string labels only; help tooltip sits **outside** the floating label |
| Notch / shrink | Sync `shrink` + `notched` whenever open, valued, or showing placeholder |
| Theme | Shrunk outlined labels get a small opaque pad; Select value ellipsizes instead of colliding |

### Ideas parked (next release, optional)
- Separate Designer / Surfacer columns for leaders on wide screens
- Compact chips for Q/A variance instead of text
- Always-shrunk labels on dense admin grids only

## Code (Senior-approved)

| File | Change |
|------|--------|
| `frontend/src/components/projects/command-center/ProjectBoardList.tsx` | Row readability layout |
| `frontend/src/components/ui/design-system/FormSelect.tsx` | Label/notch shrink sync; tooltip outside |
| `frontend/src/components/ui/design-system/FormField.tsx` | Same tooltip pattern for text fields |
| `frontend/src/theme/prosohmTheme.ts` | InputLabel / Select / FormControl clarity |
| `frontend/src/components/admin/UserTeamAssignments.tsx` | Relationship Select always notched |

## Testing checklist

| # | Check | Pass |
|---|--------|------|
| 1 | Projects Active rows: names on one line, Q/A/% on the next — no `NameQ` mash | |
| 2 | Designers and surfacers both visible without overwrite (e.g. Umesh · Logesh) | |
| 3 | Progress label says Progress (not DONE); % matches bar | |
| 4 | Create Project: Customer / Template / Team / Designer / Surfacer labels float cleanly with values | |
| 5 | Edit Project: prefilled selects — label above notch, value fully readable | |
| 6 | Searchable FormSelect (if used): selected option does not sit under label | |
| 7 | User admin team relationship dropdown still readable | |
| 8 | Mobile / narrow width: names truncate with ellipsis; hours still on own line | |

## Testing lead sign-off
- [ ] Desktop Chrome + Edge smoke on create + edit + Projects list  
- [ ] No new console errors on Project form open  

## QC before UAT
- [ ] Deploy API (no backend change required for this patch) + `frontend/dist`  
- [ ] Hard refresh EM account Projects + Create Project dialog  
- [ ] Spot-check Design Leader + Designer My work rows  
- [ ] Sign-off → user testing  
