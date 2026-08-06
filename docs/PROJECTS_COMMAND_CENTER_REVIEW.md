# Projects Command Center — Architecture Review

**Status:** Approved approach (Workstream new + keep Stream; reuse Teams)  
**Date:** 2026-08-05  
**Related:** [stream-wise-platform-briefing.md](./stream-wise-platform-briefing.md)

---

## 1. Decisions

| Topic | Decision |
|-------|----------|
| Workstream | **New** configurable entity + project M2M + optional ownership/hours |
| Stream | **Keep** as business-line axis (numbering, task types, skills, Phase A scope) |
| Teams | **Reuse** existing `Team` / `TeamMember` / lead — no second team system |

---

## 2. Current architecture (reuse)

### Project model (`app/models/models.py`)

- Single `stream_id` (business line), optional `team_id`
- Assignees: `designer_id`, `design_leader_id`, `surfacer_id`
- Hours: `quoted_hours`, `current_planned_hours`, `actual_hours`
- Status: `execution_status`, `project_stage`, `health`, `priority`
- Progress: computed in `project_metrics` (not a stored project column)

### Stream (business line)

- Master data with numbering; task types and skills are stream-scoped
- Phase A: required on create, CAD seed, portfolio scope prefs (`projects_portfolio_scope`)
- Projects UI: stream cards + team rail (client-heavy filters today)

### Teams

- Multi-membership via `TeamMember`; access via `team_access.get_accessible_team_ids`
- Project visibility: team portfolio **or** personal assignment

### Projects page today

- [`frontend/src/pages/ProjectsPage.tsx`](../frontend/src/pages/ProjectsPage.tsx)
- Hybrid: API loads up to 500 rows; search/health/priority/stream/team multi-select filtered client-side
- Session persistence for filters; no named saved views yet

---

## 3. Gaps vs Command Center brief

| Need | Gap |
|------|-----|
| Multi workstream per project | Only single `stream_id` |
| Workstream ownership / hours | None |
| Saved views | Session + one enum pref only |
| Server-side rich filters | Limited; health/search client-only |
| Grouped / card layouts | List + stream/team grouping only |
| Configurable card groups | Partial (stream/team cards) |

---

## 4. Target model

```
Stream (business line) ──1── Project.stream_id
Team (delivery) ──0..1── Project.team_id
Workstream (configurable) ──M── ProjectWorkstream ──M── Project
                              └── optional team_id, lead_id, hours, dates, health…
ProjectSavedView (per user / system)
```

Timesheets and task types remain **Stream**-scoped. Workstream is portfolio/ops taxonomy and capacity prep — not a timesheet axis in this initiative.

---

## 5. Risks & mitigations

| Risk | Mitigation |
|------|------------|
| Confusing Stream vs Workstream | Distinct admin labels; UI copy: “Business stream” vs “Workstream” |
| Fork Stream/Team | Explicit decision: never duplicate |
| Client 500-row limit | Phase 6 server filters + pagination |
| Breaking legacy projects | Workstreams optional (zero rows OK) |
| Hardcoded Prosohm names | Seed catalog is data; UI never hardcodes |

---

## 6. Phased delivery

1. Schema scaffolding  
2. Workstream CRUD + admin + seed  
3. Team cards on existing teams  
4. Project↔Workstream API + form  
5. View control cards  
6. Server filters / summary / pagination  
7. Saved views + URL state  
8. Grouped / card layouts + chips  
9. Workstream hours visibility  
10. Polish, indexes, tests  

---

## 7. Out of scope

Full capacity engine, drag-and-drop reassignment, SaaS multi-tenant beyond `TenantMixin`, milestone/finance rewrites.

---

## 8. EM 5-second answers checklist (Phase 10)

| Question | Where |
|----------|--------|
| What’s active this week? | KPI strip + Due Soon view / status cards |
| What’s overdue / at risk? | Summary endpoint + Overdue / At Risk cards |
| Which workstreams are loaded? | Workstream **sections** (default layout) with per-section hours |
| What’s my team carrying? | My Team scope + team cards |
| Can I share this view? | Saved views + URL query params (non-sensitive) |

### Workstream sections (R10 enhancement)

- Default Projects layout groups by **Workstream** (admin `display_order`, `is_active`, `icon`, `color`).
- Multi-workstream projects **appear in each** matching section (same project object; no DB duplication).
- Detection: explicit `project_workstreams` first; else **Project Type → `default_workstream_id`**.
- Section header KPIs: Projects, Hours, Progress, Risk, Due soon, Overdue.
- User prefs (localStorage `protrack.projects.workstreamSectionPrefs.v1`): collapse, hide, pin, reorder.
- Filters (customer, team, PM, designer, priority, health, due, status) apply **before** sectioning.
- Capacity / resource loading / AI: consume `project_workstreams` hour + ownership fields — no redesign required.
- New workstreams from admin appear automatically — no frontend hardcoding of Mold/CAD/etc.
