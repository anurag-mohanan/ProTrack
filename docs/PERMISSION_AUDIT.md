# ProTrack permission audit (Projects create / delete)

Date: 2026-08-19  
Scope: authorization architecture, Projects create/delete bugs, related action leaks.

This document describes the system **as implemented**, the **root causes** of the two confirmed bugs, related-record decisions for delete, and remaining module gaps.

---

## 1. Authorization architecture

Three independent layers:

| Layer | Stored on | Purpose |
| --- | --- | --- |
| Module access | `users.module_access` JSON list | Sidebar / route (e.g. `projects`) |
| Special permissions | `users.special_permissions` JSON list | Cross-cutting actions (create/edit/delete projects, approve timesheets, …) |
| Module actions | `users.module_actions` JSON map | Fine-grained EBMP actions (`finance.create`, `hr.edit`, …). **Not used for Projects CRUD.** |

Roles (`roles.name`) supply **defaults only**. Permission JSON is **per user**. `NULL` / blank means “use role defaults”. A stored `"[]"` is an explicit empty override (no fallback).

**Admin bypass (backend):** `user_holds_special` returns true for role name `Admin` even if stored specials omit the key. `resolve_user_modules` always grants every module to `Admin`.

**Admin bypass (frontend, before this fix):** modules yes; **specials no**. UI used `/me`’s resolved specials list as-is.

**Data scope** (`app/core/data_scope.py` + `team_access.py`) is separate from action permission. Create/edit/delete still require the project to be in the user’s team/assignment scope unless the actor is unrestricted (Admin / unscoped EM / executives).

**SoD** (`app/core/sod.py`): cannot hold both `delete_projects` and `approve_projects` on one user. This conflicts with backend Admin defaults (`ALL_SPECIAL_PERMISSIONS` includes both). Saving an Admin with “all specials” failed validation unless one of the pair was dropped.

---

## 2. Roles vs “System Administrator”

| Name | Meaning |
| --- | --- |
| **Admin** | Permission-bearing platform administrator (`is_admin()`, `require_roles("Admin")`). |
| **System Administrator** | IT hierarchy role (under IT Manager). **Not** aliased to Admin. Falls through to **Designer** module defaults and **empty** specials. |

Product copy that says “System Administrator” on timesheets refers to `isAdminRole` → role **`Admin`**.

If a person is assigned the IT **System Administrator** role expecting full project delete, the API will 403 unless `delete_projects` is granted on that user.

---

## 3. Project action keys (independent)

| Capability | Key | Type |
| --- | --- | --- |
| View Projects | `projects` | Module |
| Create Projects | `create_projects` | Special |
| Edit Projects | `edit_projects` | Special |
| Archive Projects | `archive_projects` | Special |
| Delete Projects | `delete_projects` | Special |
| Manage Project Settings | `manage_project_settings` | Special |
| Approve Projects | `approve_projects` | Special |

View must not imply Create/Edit/Delete. Clone uses Create + read source + team scope.

---

## 4. Project APIs

Router: `app/api/v1/projects.py` (JWT required; action checks in handlers).

| Method | Path | Permission | Effect |
| --- | --- | --- | --- |
| POST | `/projects` | Create + team scope | Insert |
| PATCH | `/projects/{id}` | Edit + read scope | Update |
| POST | `/{id}/clone` | Create + read source | Insert copy |
| POST | `/{id}/archive` | Archive + read | Flag |
| POST | `/{id}/restore` | **Edit** (not Archive) | Un-archive |
| POST | `/{id}/soft-delete` | Delete + read | Soft delete |
| DELETE | `/{id}` | Delete (no read check) | Soft delete (legacy) |
| POST | `/{id}/restore-deleted` | Admin only | Undo soft delete |
| DELETE | `/{id}/permanent` | Admin only | Hard delete if no blockers |

Soft delete: `is_deleted`, `deleted_at`, `deleted_by_id`. Does **not** cascade. Timesheets, milestones, and activities stay.

Hard delete: only after soft delete; blocked if any timesheet entries, milestones, or project activities exist.

---

## 5. Related-record decisions (do not cascade historical data)

| Related entity | Soft delete (Projects list “Delete”) | Permanent delete (Deleted Projects) |
| --- | --- | --- |
| Timesheet entries (incl. post-completion hours) | **RETAIN** (FK stays) | **PREVENT** |
| Milestones | **RETAIN** | **PREVENT** |
| Activity / audit | **RETAIN** (plus `project_deleted` activity) | **PREVENT** |
| Project workstreams / temp config | **RETAIN** with project row | CASCADE only if hard delete is allowed (no blockers) |
| Documents / folders (path fields) | **RETAIN** | With project row |
| Notifications | **RETAIN** | With project row |

**Completed projects with timesheets:** soft-delete allowed (removed from active lists; history kept). Hard delete forbidden. Do not destroy post-completion Additional Work / Rework rows.

---

## 6. Root cause — Create Project permission leak

### Primary (UI)

1. **Project drawer Duplicate is always shown** (`ProjectRecordDrawer.tsx`) with no `canCreateProject` check. Clone API still 403s, but the action is visible.
2. **Ctrl+N / dashboard `?create=1`** navigate to create without a permission check. `ProjectsPage` previously **ignored** `create=1`, so the dialog often did not open — but Help Center still advertises the shortcut.
3. **Role defaults:** Design Leader and Senior Designer get `create_projects` when `special_permissions` is NULL. Users given those roles without an explicit specials override **do** see Create. That is default policy, not module-implies-create — but it is easy to confuse with “Projects = YES”.
4. **Frontend Admin specials** did not auto-grant (unlike backend). Less relevant to the leak; relevant to Admin UI consistency.

### Backend

Create is independently enforced (`can_create_project_for_team`). Direct POST without `create_projects` is 403 **except**:

- **Admin** always passes `user_holds_special`.
- **Finance quote import** can insert a `Project` via finance module actions without `create_projects` (`ensure_project_for_quote_import`). Documented remaining risk.

Empty state copy mentioned “create a new project” even when the user cannot create (wording only).

---

## 7. Root cause — Delete Project fails for Administrator

Several stacked defects; not a missing button-only issue.

### A. Frontend treated “can delete projects” as “isAdmin”

`ProjectsPage` used `isAdmin = canDeleteRecords(access)` which is **`delete_projects` only**, with **no Admin specials bypass**. An Admin whose stored specials omit `delete_projects` (SoD, incomplete save, or Users-page defaults) **does not see Delete**, while the API would still allow it.

### B. Delete hidden on live rows in DataGrid

`ProjectTable` set `showDelete={canDelete && row.is_archived}`. Live Command Center lists are not archived, so the DataGrid path never offered Delete. Board/list menus could still show it.

### C. Archived page used role name only

`canSoftDeleteProject(user?.role_name)` ignores stored `/me` specials. Non-Admin with `delete_projects` looked like they had no delete; Admin relied on frontend Admin **defaults**, which are incomplete vs backend `ALL_SPECIAL_PERMISSIONS`.

### D. SoD vs Admin defaults

Backend Admin defaults include **both** `delete_projects` and `approve_projects`. Saving that set is rejected. Operators dropping `delete_projects` to save the user then lose the UI delete control.

### E. Permanent delete is not “Delete” on the live list

Live Delete is **soft-delete**. Permanent delete from Deleted Projects is blocked whenever timesheets, milestones, or activities exist — true of almost every real project. If Admin used permanent delete, it **correctly** fails to protect history. That must be a clear error, not a silent failure.

### F. IT role “System Administrator”

Not `Admin`. No default `delete_projects`. API 403.

---

## 8. Mutation table (Projects + similar)

| Module | Action | Permission | Frontend guard (before) | Backend guard | Data scope | Status |
| --- | --- | --- | --- | --- | --- | --- |
| Projects | View | `projects` | Module route | Module / Admin | Team / assignment | OK |
| Projects | Create | `create_projects` | Toolbar yes; **drawer Duplicate no**; shortcut no | Yes | Team | **BUG** (UI leak) |
| Projects | Clone | Create | Detail page yes; drawer no | Yes | Team | **BUG** (UI) |
| Projects | Edit | `edit_projects` | List/detail mostly; **drawer Edit always rendered** | Yes | Read scope | **BUG** (UI) |
| Projects | Archive | `archive_projects` | Mostly | Yes | Read | OK-ish |
| Projects | Restore archive | Edit | Archived page **ungated** | Edit | — | **BUG** (UI) |
| Projects | Soft delete | `delete_projects` | Misnamed isAdmin; archived-only in grid; no Admin FE bypass | Yes (Admin bypass) | Read on POST | **BUG** |
| Projects | Permanent delete | Admin | Deleted Projects admin | Admin + blockers | — | OK (blockers) |
| Projects | Quote create | Finance edit | Finance UI | **No create_projects** | — | **GAP** |
| Timesheets | Write | timesheets + rules | Mixed | Mixed | Team | Audit later |
| Admin master data | Delete | `require_roles(Admin)` | `canDeleteRecords` = **delete_projects** | Admin role | — | **BUG** (wrong helper) |
| Reports | View | module or special | Mixed | Mixed | — | See matrix |
| Users | CRUD | Admin role | Admin portal | `require_roles(Admin)` | — | OK |
| Org dept assign | Admin | Admin | Admin | Overwrite, no period | — | Documented |

---

## 9. Negative test matrix (Projects)

| User | View | Create UI/API | Edit UI/API | Delete UI/API |
| --- | --- | --- | --- | --- |
| View only (`projects`, no specials) | Yes | No / 403 | No / 403 | No / 403 |
| View + Create | Yes | Yes / 201 in scope | No / 403 | No / 403 |
| View + Edit | Yes | No / 403 | Yes / 200 in scope | No / 403 |
| View + Delete | Yes | No / 403 | No / 403 | Yes / soft-delete in scope |
| Full project specials | Yes | Yes | Yes | Yes |
| No `projects` module | No route | 403 | 403 | 403 |
| Admin (`Admin` role) | Yes | Yes (bypass) | Yes | Yes (bypass + UI) |
| System Administrator (IT) | Designer modules | No unless granted | No unless granted | No unless granted |

---

## 10. Other modules (summary)

Action permissions for finance/HR/analytics live in `module_actions`. `view` is implied if the module is granted. Many admin pages use frontend `canDeleteRecords` (project delete special) to show delete buttons while APIs require `Admin` — UI can lie.

Timesheet approve/import SoD is real and should remain for non-Admin users.

Field-level specials (`view_salary`, …) exist on the backend list but are **not** all shown on UsersPage.

---

## 11. Fixes applied in this change set

See the implementation commit / files. Intent:

- Frontend specials: Admin matches backend (`userHasSpecial` true for Admin).
- Dedicated `canDeleteProject` (not “isAdmin”).
- Show Delete on live projects; keep soft-delete as the list action.
- Gate drawer Edit / Duplicate / Delete.
- Honour `?create=1` only with Create permission.
- Ctrl+N only with Create permission.
- SoD does not apply when saving an **Admin** user (platform owner is not a maker-checker pair).
- Clearer soft-delete confirmation (history retained; completed + hours called out).
- Archived delete uses access context, not role string alone.
- Tests for unauthorized create/delete and Admin soft-delete with empty stored specials.

---

## 12. Remaining risks / next improvements

1. Finance quote “create project if missing” still bypasses `create_projects`.
2. Restore-from-archive UI on Archived Projects is not gated by Edit/Archive.
3. `canDeleteRecords` still used as a proxy for Admin on master-data pages — split `canDeleteMasterData` = Admin role.
4. Milestone write still uses role sets (`can_write_milestones`), not `edit_projects`.
5. Permission changes require re-login / `/me` refresh (no push). Document for operators.
6. Do not alias IT **System Administrator** to **Admin** without an explicit product decision.
7. Permanent delete will remain blocked for projects with timesheet history — by design.
