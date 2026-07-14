# RC5 — Dashboard right rail (My Projects + Collaboration above AI)

## Ops + Engineering Manager brainstorm → Senior decision

### Problem
On the EM dashboard, **My Projects** and **Collaboration Activity** occupied a wide mid-page band while often showing little content (empty assignment list + three summary lines). That pushed Customer Workload / Utilization charts down and left a sparse hole.

### Locked layout
| Zone | Content |
|------|---------|
| Main column | KPI overview → engineering charts (Customer Workload, Utilization, Hours Burn) → role-specific widgets |
| Right rail (top → bottom) | **My Projects** (compact) → **Collaboration Activity** (compact) → **AI Assistant** |

Rail shows whenever any of those panels is allowed (not only when AI is on).

### Ideas parked
- Merge My Projects + Collaboration into one “Personal” card  
- Hide My Projects on EM when empty (show only for staff with assignments)

## Senior-approved code

| File | Change |
|------|--------|
| `frontend/src/pages/DashboardPage.tsx` | Move widgets into stacked right rail above AI |
| `frontend/src/components/dashboard/MyProjectsWidget.tsx` | `compact` list for narrow rail |
| `frontend/src/components/dashboard/CollaborationActivityWidget.tsx` | `compact` metrics-only mode |

## Testing checklist

| # | Check | Pass |
|---|--------|------|
| 1 | EM Dashboard: My Projects is **not** a full-width card under KPIs | |
| 2 | My Projects sits in the **right column above** AI Assistant | |
| 3 | Collaboration Activity sits between My Projects and AI (or above AI if no projects panel) | |
| 4 | Charts (Customer Workload / Utilization / Hours Burn) sit higher / fuller in main column | |
| 5 | Empty My Projects still readable in the rail | |
| 6 | Collaboration metrics still show the three headline numbers | |
| 7 | AI insights + View More still work | |
| 8 | Staff with many assigned tools: compact list + click opens project | |
| 9 | Mobile: rail stacks under main content without horizontal overflow | |

## Testing lead → QC

- [ ] Smoke EM + Design Leader + Designer dashboards  
- [ ] Deploy `frontend/dist`, hard refresh  
- [ ] Sign-off → user testing  
