# Team-based data security (Layer 2)

**Status:** Implemented on existing `team_access` + new `data_scope` facade  
**Related:** Projects Command Center, module ACL (`access_control`)

---

## Two layers

| Layer | Concern | Implementation |
|-------|---------|----------------|
| **1 — Module access** | Can the user open the module? | `access_control`, `module_actions`, role defaults |
| **2 — Data scope** | Which records inside the module? | `app.core.data_scope` → `team_access` |

Never gate only on Layer 1. Every list/detail query for operational data must apply Layer 2.

---

## Data scope levels

| Level | Who | Sees |
|-------|-----|------|
| `own` | Staff with no team portfolio | Personally assigned projects / own timesheets |
| `own_team` | Single-team member or leader | That team's portfolio + own assignments |
| `multiple_teams` | Multi-team membership / led teams | Union of those teams + own assignments |
| `department` | EM with org department (fallback) | Teams linked to department members |
| `company` | Executives, Planning Board, unscoped EM, compliance | Entire tenant |
| `administrator` | Admin | Unrestricted |

Team leaders automatically receive their led teams via `get_led_team_ids` / membership.  
Project managers / Design Leaders see **assigned projects plus team portfolio** (`project_visibility_clause`).

---

## Reusable API

```python
from app.core.data_scope import (
    resolve_data_scope,
    project_visibility_for_user,
    can_access_project,
    scoped_user_ids_for_actor,
    scoped_customer_ids,
    can_access_document_entity,
)
```

- **Projects / milestones / calendar / dashboard:** `project_visibility_clause` / `can_read_project`
- **Timesheets:** `get_timesheet_visible_user_ids` (overview) + `can_read_timesheet`
- **Reports:** `resolve_report_scope` / `report_authorization` (people + teams)
- **Lookups:** customers, users, teams filtered by scope (`?for_reports=true` for stricter report pickers)
- **Documents:** entity-linked access via `can_access_document_entity`
- **Notifications:** already user-owned (`Notification.user_id`)

`/auth/me` exposes `data_scope: { level, unrestricted, team_ids, … }` for UI awareness.

---

## Reports (timesheet + future packs)

Report **people/team** subjects use ``app.services.reporting.report_authorization``
(not raw ``get_accessible_team_ids``):

| Actor | Report subjects |
|-------|-----------------|
| Team member | Self only |
| Team leader | Led teams only |
| Department envelope | Department teams |
| Engineering Manager | Division portfolio / all teams when unscoped |
| Administrator / executives | Unrestricted |

`resolve_report_scope` and lookup `?for_reports=true` both call this framework.
Reuse it for Project, Productivity, Financial, Capacity, and Customer reports.

Audit: `log_report_generation` records who, filters, team, report type (activity `data_exported`).

---

## Future (no redesign)

- **Multi-company / tenant:** `DataScopeContext.tenant_id` + existing `TenantMixin`
- **Customer / vendor portals:** add portal actor type that resolves to a fixed customer_id / vendor_id filter in `resolve_data_scope`
- **Capacity / AI:** consume the same team_ids envelope

Do not scatter `if role == …` filters in new modules — call `resolve_data_scope` or the entity helpers above.
