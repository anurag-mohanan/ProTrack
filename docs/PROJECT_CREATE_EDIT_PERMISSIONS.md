# Project create / edit permission control

**Does not rewrite existing user rows.** Users with `special_permissions = NULL` keep role defaults below.

## Model (existing, not a second system)

| Capability | Key | Layer |
|------------|-----|--------|
| View Projects | `projects` | Module access |
| Create Projects | `create_projects` | Special permission |
| Edit Projects | `edit_projects` | Special permission |
| Delete Projects | `delete_projects` | Special permission |
| Archive Projects | `archive_projects` | Special permission |
| Manage Project Settings | `manage_project_settings` | Special (Admin default; project types/templates remain under System Administration) |

Create and Edit are independent. Module access does **not** imply either write action.

Team / department / workstream / data scope is unchanged (`data_scope` + `team_access`). Create/Edit never grant company-wide records.

## Safe defaults (NULL `special_permissions`)

| Role | View | Create | Edit | Delete |
|------|:----:|:------:|:----:|:------:|
| Admin | yes | yes | yes | yes |
| Engineering Manager | yes | yes | yes | no |
| Design Leader | yes | yes | yes | no |
| Senior Designer | yes | yes | yes | no |
| Designer / Junior / Surfacer | yes | **no** | **no** | no |
| Read Only / Planning Board / HR | per modules | no | no | no |
| Executives (MD / Directors) | yes | **no** | **no** | no |

Designer previously showed an Edit control from a default special, but the API already rejected Designer edits. The default special was removed so UI matches the API. Grant **Edit Projects** on the user to get User C behaviour.

Senior Designer already had Create+Edit in specials (UI). The API now honours that, so Senior Designers with defaults can create (previously role-gated off).

Admins always retain Create/Edit/Delete even if a stored specials list is incomplete.

## Scope

- **Create:** special + Projects module + `team_id` in the user's data-scope teams. Unrestricted actors (Admin, unscoped EM, executives) may omit `team_id`.
- **Edit:** special + `can_read_project` (team portfolio or personal assignment). Moving `team_id` onto another team also requires that team to be in scope.
- **Clone:** Create + can read source + same team rule as create.

## Admin assignment

Users → Access Control → Special Permissions. Examples:

- User A: View module + Create + Edit
- User B: View module only
- User C: View module + Edit (no Create)

## Audit

`activities` rows: `project_created` / `project_updated` with actor (`user_id`), timestamp, module `projects`, and field snapshots (create: code/tool/team/stream; update: changed fields old/new).
