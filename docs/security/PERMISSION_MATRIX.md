# ProTrack Permission Matrix

Roles are normalized via `ROLE_ALIASES` (e.g. standardized Engineering roles map
to their permission-bearing equivalents). Access is evaluated as
**role → module → action**, with optional per-user overrides.

## Modules by role (defaults)

| Role | Dashboard | Projects | Timesheets | Workload | Resource Plng | Reports | Financial Plng | HR | Reports/Analytics | Perf. | System Admin |
|------|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| Admin | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Engineering Manager | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — | ✅ | ✅ | — |
| Design Leader | ✅ | ✅ | ✅ | ✅ | — | — | — | — | ✅ | ✅ | — |
| Designer / Senior / Junior / Surfacer | ✅ | ✅ | ✅ | — | — | — | — | — | — | ✅ | — |
| Read Only | ✅ | ✅ | — | — | — | — | — | — | ✅ | ✅ | — |
| HR | ✅ | — | ✅ | — | — | — | — | ✅ | ✅ | ✅ | — |
| Office Administrator | ✅ | — | ✅ | — | — | — | — | ✅ | ✅ | ✅ | — |
| Planning Board | — (planning board only) |

## Module actions

`view`, `create`, `edit`, `delete`, `approve`, `export`, `import`, `configure`
(plus performance-specific `edit_reviews`, `manage_templates`, `calibrate`,
`open_cycles`). `view` is implied by module access; other actions default per
role and can be overridden per user (persisted in `users.module_actions`).

## Special permissions

Project/timesheet: `create_projects`, `edit_projects`, `archive_projects`,
`delete_projects`, `approve_projects`, `approve_timesheets`, `import_timesheets`,
`export_reports`, `view_reports`, `view_resource_planning`,
`manage_customers`, `manage_contacts`, `manage_teams`, `manage_users`,
`manage_company_settings`, `manage_project_settings`.

Field-level & governance (security foundation): `view_salary`,
`view_financial_cost`, `view_budget`, `view_profitability`,
`financial_approval`, `budget_approval`, `manage_permissions`.

## Guards

- `require_roles(*roles)` — legacy role gate (still used for admin-only routes).
- `require_module_action(module, action)` — enterprise action gate.
- `require_special(permission)` — special-permission gate.
- CRUD factory read routes accept an optional `read_module` gate (opt-in).
