# RC5 — Card padding & overflow (no clipped content)

## Ops + Engineering Manager brainstorm → Senior decision

### Problem
Dashboard cards (especially **Resource Availability**) clipped the last row at the panel bottom. Hours Burn showed **NaN%**. AI Assistant insight rows and the sticky right rail felt edge-tight. Root causes: fixed `height: 300` panels with `overflow: hidden` and no body scroll; Decimal hours arriving as JSON strings (string concat → NaN pct); tight AI alert padding.

### Ideas considered
| Idea | Verdict |
|------|---------|
| Remove fixed heights; let all chart cards grow | Rejected — uneven grid / jumps layout |
| Shrink Resource Availability `limit` only | Partial — still clips under header + bar |
| Soft expand + “Show more” per card | Parked for later |
| **Body scroll on height-constrained `DashboardPanel` + list scroll inside Resource Availability; coerce hours to number; pad AI/rail** | **Locked** |

### Locked rules
1. **Never clip mid-row** — height-constrained panels scroll inside the body (`overflowY: auto`, `minHeight: 0`).
2. **List-heavy cards** keep the summary chrome visible; only the list scrolls when needed.
3. **Numeric hours** from the API must be coerced with `Number()` before aggregation/percentage math.
4. **Rail / AI cards** keep ≥ ~12–16px inner padding; rail sticky area has bottom padding so the last card isn’t flush to the viewport.

## Senior-approved code

| File | Change |
|------|--------|
| `frontend/src/components/ui/design-system/DashboardPanel.tsx` | Body `overflowY: auto` when `height` set; consistent bottom padding |
| `frontend/src/components/dashboard/ResourceAvailabilityPanel.tsx` | Fill height; “Ready now” list scrolls; tighter row spacing |
| `frontend/src/components/dashboard/DashboardCharts.tsx` | `toHours` / `hoursPct` — fix Hours Burn **NaN%** from Decimal strings |
| `frontend/src/components/dashboard/DesignerUtilizationList.tsx` | Scroll inside constrained panel height |
| `frontend/src/components/dashboard/DashboardLayout.tsx` | Sidebar `pb`, gutter so last rail card fully visible |
| `frontend/src/components/ai/AiOperationsPanel.tsx` | More padding on panel + insight rows; text not jammed into dismiss |
| `frontend/src/pages/DashboardPage.tsx` | Slight rail stack bottom padding |

## Testing checklist

| # | Check | Pass |
|---|--------|------|
| 1 | Resource Availability: last “Open” name fully visible (scroll inside card if many open) | |
| 2 | Hours Burn: percentages are numbers (**not** `NaN%`) when billable/NP hours present | |
| 3 | Designer Utilization: names/% not vertically clipped at card bottom | |
| 4 | Customer Workload / Stage / Health: no mid-legend cutoff | |
| 5 | Right rail: scroll to bottom — Collaboration + AI last lines not cut by viewport | |
| 6 | AI insights: title/detail readable with clear gap from dismiss (×) | |
| 7 | Desktop 1280 / 1440 / 1920 and laptop height ~768 — no hard edge clipping on chart grid | |
| 8 | Mobile: rail stacks under main; no horizontal overflow from cards | |

## Testing lead → QC

- [ ] Smoke EM + Design Leader + Designer dashboards after deploy
- [ ] Deploy `frontend/dist`, hard refresh
- [ ] Confirm Hours Burn with live Decimal/string payload still shows finite %
- [ ] Sign-off → user testing
