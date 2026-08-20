# IT Operations Module — Architecture & Design

> **Status:** Draft for stakeholder review
> **Module key:** `it_operations`
> **Routes prefix:** `/it`

---

## 1. Stakeholder Review Summary

### IT Department
- Centralize asset tracking (laptops, monitors, peripherals, servers) replacing spreadsheets
- Automated asset numbering and computer naming conventions
- Network and IP address pool management with allocation history
- Employee IT provisioning linked to onboarding checklists
- IT request management via existing Help Desk, extended with IT-specific workflows

### Operations / Engineering
- Self-service view of assigned IT assets and accounts
- Visibility into IT provisioning status during onboarding
- No disruption to existing project, timesheet, or workload modules

### Finance / Administration
- Asset register with purchase date, cost, warranty, and depreciation-readiness
- License pool tracking for software compliance
- Exportable IT asset and cost reports

### Cybersecurity / Governance
- No plaintext credential storage anywhere (DB, logs, exports, audit rows)
- Credential generator returns one-time values; only metadata is persisted
- Object-level authorization on all IT resources
- Full audit trail on asset assignments, IP allocations, and account lifecycle
- Transactional uniqueness for asset numbers, computer names, IP allocations, and usernames

### HR
- Onboarding checklist IT items (already seeded: workstation, email, Teams, domain user, OneDrive) link to IT provisioning tasks
- Exit/offboarding hooks for IT deprovisioning (asset return, account deactivation)
- Employee IT profile visible from the HR employee detail view

---

## 2. MVP vs Phase 2 vs Future Scope

### MVP (this implementation)
- IT navigation, permissions, and module scaffolding
- IT Dashboard with summary cards
- Asset types (configurable) and asset register with CRUD
- Computer register (1:1 extension of Asset) with generated computer names
- Server-side asset number generator with uniqueness guarantees
- Network and IP pool management with transactional allocation/release
- Asset assignment and transfer history (append-only)
- Employee IT profile panel (assets, IPs, accounts assigned to user)
- IT requests via existing ticketing system (`category = "it"`)
- Audit logging for all IT actions
- Basic IT reports (asset register, assigned assets, open IT requests, IP allocation)
- IT Settings page for naming/numbering/network conventions

### Phase 2 (deferred)
- Software catalog and license pool management with concurrent usage tracking
- Maintenance scheduling and warranty tracking
- Advanced SLA engine for IT requests
- QR/barcode generation and scanning workflows
- Asset depreciation and accounting engine

### Future
- Vendor integrations (M365, Active Directory, domain automation)
- Full password vault / secrets platform
- Endpoint management (RMM/MDM/SIEM)
- Mobile app for IT field operations

---

## 3. Permission Model

### Module Gate
A single module key `it_operations` controls sidebar visibility and route access.

### Special Permissions (new)
| Key | Label | Sensitivity | Description |
|-----|-------|-------------|-------------|
| `view_it_operations` | View IT Operations | Normal | Read-only access to IT dashboard, assets, networks |
| `manage_it_assets` | Manage IT Assets | Normal | Create, edit, archive, delete assets and asset types |
| `assign_it_assets` | Assign IT Assets | Normal | Assign/transfer/return assets to/from employees |
| `manage_it_networks` | Manage IT Networks | Elevated | Create/edit networks, manage IP pools |
| `allocate_it_ips` | Allocate IT IPs | Elevated | Allocate/release IP addresses |
| `manage_it_accounts` | Manage IT Accounts | Elevated | Create/deactivate IT user account records |
| `generate_it_credentials` | Generate IT Credentials | Sensitive | Generate one-time passwords (never stored) |
| `manage_it_requests` | Manage IT Requests | Normal | Manage IT-category tickets beyond own requests |
| `view_it_reports` | View IT Reports | Normal | Access IT-specific reports |
| `manage_it_settings` | Manage IT Settings | Elevated | Configure naming conventions, numbering rules, network ranges |

### Self-Service Access
All authenticated employees can:
- View their own IT profile (assigned assets, IP, accounts)
- Submit IT requests (existing ticket system, `category = "it"`)
- View status of their own IT requests

### Role Defaults
- **Admin:** All IT permissions (via existing Admin-gets-all-specials pattern)
- **Director of IT:** `view_it_operations`, `manage_it_assets`, `assign_it_assets`, `manage_it_networks`, `allocate_it_ips`, `manage_it_accounts`, `manage_it_requests`, `view_it_reports`, `manage_it_settings`
- **IT Manager / System Administrator:** Same as Director of IT minus `manage_it_settings`
- **IT Executive / IT Support Engineer:** `view_it_operations`, `assign_it_assets`, `manage_it_requests`
- **Executive tier (MD, Directors):** `view_it_operations`, `view_it_reports`
- **Other roles:** No IT permissions by default (configurable per user)

---

## 4. Data Model

### Reused Entities (no changes)
- `User` — employee identity, team, role, manager
- `Team`, `OrgDepartment` — organizational structure
- `Ticket`, `TicketComment`, `TicketCategoryRoute` — IT request handling
- `Activity` — audit logging
- `OnboardingChecklist`, `OnboardingChecklistItem` — IT provisioning tasks
- `Role` — permission resolution

### New Entities

#### `AssetType`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| code | varchar(20) | Unique per tenant. e.g. `LAPTOP`, `MONITOR` |
| name | varchar(100) | Display name |
| category | varchar(40) | `computer`, `peripheral`, `network_equipment`, `other` |
| is_active | bool | Soft-disable |
| numbering_prefix | varchar(10) | e.g. `PRO-LT` for asset number generation |

#### `Asset`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| asset_number | varchar(40) | Unique per tenant, server-generated |
| asset_type_id | UUID FK → asset_types | |
| serial_number | varchar(100) | Optional, unique per tenant if provided |
| make | varchar(100) | Manufacturer |
| model | varchar(100) | Model name |
| status | varchar(20) | `available`, `assigned`, `maintenance`, `retired`, `disposed` |
| purchase_date | date | |
| purchase_cost | decimal(12,2) | |
| warranty_expiry | date | |
| location | varchar(120) | Physical location |
| notes | text | |
| is_deleted | bool | Soft delete |

#### `Computer` (1:1 extension of Asset)
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| asset_id | UUID FK → assets | Unique |
| computer_name | varchar(40) | Unique per tenant, server-generated |
| os | varchar(60) | Operating system |
| processor | varchar(100) | |
| ram_gb | int | |
| storage_type | varchar(20) | `SSD`, `HDD`, `NVMe` |
| storage_gb | int | |
| domain_joined | bool | |
| mac_address | varchar(17) | |

#### `AssetAssignment` (append-only history)
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| asset_id | UUID FK → assets | |
| assigned_to_user_id | UUID FK → users | |
| assigned_by_user_id | UUID FK → users | Who performed the assignment |
| assigned_date | date | |
| returned_date | date | NULL if currently assigned |
| return_condition | varchar(40) | `good`, `damaged`, `needs_repair` |
| notes | text | |

#### `Network`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| name | varchar(100) | e.g. `Office LAN`, `Guest WiFi` |
| cidr | varchar(18) | e.g. `192.168.1.0/24` |
| gateway | varchar(15) | |
| dns_primary | varchar(15) | |
| dns_secondary | varchar(15) | |
| vlan_id | int | Optional |
| description | text | |
| is_active | bool | |

#### `IPAddress`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| network_id | UUID FK → networks | |
| address | varchar(15) | Unique per tenant |
| status | varchar(20) | `available`, `allocated`, `reserved`, `disabled` |
| allocation_type | varchar(20) | `static`, `dhcp_reserved` |

#### `IPAssignmentHistory` (append-only)
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| ip_address_id | UUID FK → ip_addresses | |
| assigned_to_asset_id | UUID FK → assets | Optional |
| assigned_to_user_id | UUID FK → users | Optional |
| assigned_by_user_id | UUID FK → users | |
| hostname | varchar(60) | |
| assigned_date | date | |
| released_date | date | NULL if current |
| notes | text | |

#### `ITUserAccount` (metadata only — no secrets stored)
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| user_id | UUID FK → users | Employee |
| account_type | varchar(40) | `domain`, `email`, `vpn`, `application` |
| username | varchar(120) | |
| display_name | varchar(200) | |
| status | varchar(20) | `active`, `suspended`, `deactivated` |
| created_date | date | |
| deactivated_date | date | |
| notes | text | |

#### `ITSettings` (singleton per tenant)
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| asset_numbering_pattern | varchar(100) | Template, e.g. `{prefix}-{seq:04d}` |
| computer_naming_pattern | varchar(100) | Template, e.g. `{org}-{type}{seq:03d}` |
| default_domain | varchar(100) | |
| default_email_domain | varchar(100) | |
| ip_allocation_strategy | varchar(20) | `sequential`, `manual` |
| next_asset_seq | int | Atomic counter |
| next_computer_seq | int | Atomic counter |
| settings_json | text | Extensible JSON for future settings |

---

## 5. Asset Lifecycle & History Rules

### Asset States
```
available → assigned → maintenance → available (cycle)
                    → retired → disposed
```

### Assignment History
- Every assign/transfer/return creates a new `AssetAssignment` row
- The `returned_date` on the previous assignment is set when the asset moves
- Asset `status` is updated atomically with the assignment record
- Transfer = return from user A + assign to user B in a single transaction

### Computer Name Generation
- Pattern: `{ORG_CODE}-{TYPE_CODE}{SEQ}` (configurable via `ITSettings`)
- Sequence is atomic (SELECT FOR UPDATE on `ITSettings.next_computer_seq`)
- Names are immutable once assigned

### Asset Number Generation
- Pattern: `{PREFIX}-{SEQ}` where prefix comes from `AssetType.numbering_prefix`
- Atomic sequence from `ITSettings.next_asset_seq`
- Numbers are immutable once assigned

---

## 6. Employee Onboarding, Transfer, and Exit Workflows

### Onboarding
Existing onboarding checklist already has 5 IT items (order 16–20):
1. Workstation, 3D mouse & license ready
2. Email ID created & set up
3. Teams account created
4. Domain user created
5. OneDrive access provided

The IT module connects to these by:
- When an onboarding checklist is published, the IT Dashboard shows pending IT provisioning tasks
- IT staff can mark checklist items complete from the IT Dashboard or from the checklist itself
- Completing an IT checklist item can optionally auto-create `ITUserAccount` records

### Transfer
- When an employee transfers teams (via `team_transfer_service`), the IT profile view updates to show the new team
- Asset assignments persist across transfers (assets follow the person, not the team)
- IP assignments may need review (flagged in IT Dashboard)

### Exit / Offboarding
- When `employee_offboard_service` schedules an exit, IT deprovisioning tasks are generated:
  - Return all assigned assets (update `AssetAssignment.returned_date`)
  - Deactivate IT user accounts (update `ITUserAccount.status`)
  - Release allocated IP addresses (update `IPAssignmentHistory.released_date`)
- These appear as actionable items in the IT Dashboard
- Audit trail captures who performed each deprovisioning action

---

## 7. Network & IP Workflows

### Network Setup
1. Admin creates a `Network` with CIDR, gateway, DNS
2. System generates `IPAddress` rows for the usable range (excluding network/broadcast)
3. All IPs start as `available`

### IP Allocation
1. IT admin selects an available IP from a network pool
2. Transaction: IP status → `allocated`, new `IPAssignmentHistory` row created
3. Previous assignment (if any) gets `released_date` set in same transaction
4. Uniqueness enforced: one active allocation per IP address

### IP Release
1. IT admin releases an IP
2. Transaction: IP status → `available`, current `IPAssignmentHistory.released_date` set
3. Full history preserved for audit

---

## 8. Credential Generation

### Security Constraints
- **No plaintext passwords are stored** in any table, log, export, or audit record
- Credential generator produces a one-time value displayed only at generation time
- Only metadata is persisted: account type, username, creation date
- Audit log records "credential generated for {username}" without the credential value
- Generated credentials are never included in API responses after the initial generation call

### Generation Flow
1. IT admin with `generate_it_credentials` permission triggers generation
2. Server generates a secure random password meeting configured complexity rules
3. Response contains the password exactly once
4. `ITUserAccount` record is created/updated with metadata only
5. Audit log entry created (no credential in payload)
6. UI displays the credential with a copy button and a warning that it won't be shown again

---

## 9. API Architecture

### Router Structure
```
/api/v1/it/
├── dashboard          GET     — IT dashboard summary
├── asset-types        CRUD    — Asset type management
├── assets             CRUD    — Asset register
├── assets/{id}/assign POST    — Assign asset to user
├── assets/{id}/return POST    — Return asset from user
├── assets/{id}/transfer POST  — Transfer asset between users
├── computers          CRUD    — Computer register
├── networks           CRUD    — Network management
├── networks/{id}/ips  GET     — List IPs in network
├── ips/allocate       POST    — Allocate an IP
├── ips/{id}/release   POST    — Release an IP
├── accounts           CRUD    — IT user account metadata
├── accounts/generate-credential POST — One-time credential generation
├── profile/me         GET     — Current user's IT profile
├── profile/{user_id}  GET     — Employee IT profile (IT admin)
├── reports/{report_key} GET   — IT reports
└── settings           GET/PUT — IT settings
```

### Service Layer
- `ITAssetService` — asset CRUD, numbering, assignment workflows
- `ITNetworkService` — network CRUD, IP generation, allocation/release
- `ITAccountService` — account metadata, credential generation
- `ITDashboardService` — aggregation for dashboard cards
- `ITReportService` — report data queries
- `ITSettingsService` — settings CRUD with validation

All services use the existing `activity_service.log_activity()` for audit and enforce permissions via `user_holds_special()`.

---

## 10. UI Architecture

### Page Structure
| Route | Page | Pattern |
|-------|------|---------|
| `/it` | `ITDashboardPage` | Dashboard hub (like `DashboardPage`) |
| `/it/assets` | `ITAssetsPage` | List + detail drawer (like `UsersPage`) |
| `/it/computers` | `ITComputersPage` | List + detail drawer |
| `/it/networks` | `ITNetworksPage` | List + IP allocation panel |
| `/it/requests` | `ITRequestsPage` | Filtered view of Help Desk (like `HelpDeskPage`) |
| `/it/reports` | `ITReportsPage` | Report catalog (like `ReportsPage`) |
| `/it/settings` | `ITSettingsPage` | Form-based settings |

### Reused Components
- `ServerPaginatedDataGrid` for all list views
- `FormDrawer` for create/edit forms
- `RecordDetailDrawer` for asset/computer/network detail views
- `FilterToolbar` for list filtering
- `ConfirmDialog` for destructive actions
- `StatCard` / dashboard card components for IT Dashboard

### IT Dashboard Cards
- Total assets by status (pie/donut)
- Assets pending assignment
- Open IT requests count
- IP utilization by network
- Pending onboarding IT tasks
- Recently assigned/returned assets

---

## 11. Audit Logging

### New Entity Types
- `it_asset`
- `it_computer`
- `it_network`
- `it_ip_address`
- `it_account`
- `it_settings`

### New Activity Actions
- `it_asset_created`, `it_asset_updated`, `it_asset_deleted`
- `it_asset_assigned`, `it_asset_returned`, `it_asset_transferred`
- `it_computer_created`, `it_computer_updated`
- `it_network_created`, `it_network_updated`
- `it_ip_allocated`, `it_ip_released`
- `it_account_created`, `it_account_deactivated`
- `it_credential_generated` (no secret in payload)
- `it_settings_updated`

All actions follow the existing `{entity}_{verb_past_tense}` convention.

---

## 12. Configuration & Commercialization

### Configurable (not hardcoded)
- Asset type codes, names, categories, numbering prefixes
- Computer naming pattern
- Asset numbering pattern
- Network ranges and allocation strategy
- Default domains for email and directory accounts
- IT request category routing

### Tenant-Ready
- All new tables include `tenant_id` via `TenantMixin`
- All unique constraints are scoped to tenant
- `ITSettings` is per-tenant singleton
- Sequence counters are per-tenant

### Commercialization Notes
- Module is opt-in via `it_operations` module key
- No Prosohm-specific naming or conventions in code
- All configurable values have sensible defaults
- Feature can be disabled entirely by removing module access from all roles

---

## 13. Schema Sync Strategy

New schema sync file: `app/db/phase60_it_operations_schema_sync.py`

Creates tables in dependency order:
1. `it_settings`
2. `asset_types`
3. `assets`
4. `computers`
5. `asset_assignments`
6. `networks`
7. `ip_addresses`
8. `ip_assignment_history`
9. `it_user_accounts`

Seeds:
- Default `ITSettings` row with standard patterns
- Default asset types: Laptop, Desktop, Monitor, Keyboard, Mouse, Headset, Server, Network Switch, Router, Other

---

## 14. Implementation Phases

### Phase 0 — Architecture (this document) ✓
### Phase 1 — Platform Foundations
- Add `it_operations` module key to backend and frontend access control
- Add new special permission keys
- Add sidebar navigation and route wiring
- Create schema sync file with all tables
- Add empty dashboard/report placeholders

### Phase 2 — Asset Management MVP
- `AssetType` and `Asset` models, schemas, services, and CRUD API
- `Computer` model with name generation
- `AssetAssignment` model with assign/return/transfer workflows
- Asset list, detail, and form UI

### Phase 3 — Network & IP Management
- `Network` and `IPAddress` models with IP pool generation
- `IPAssignmentHistory` with allocation/release workflows
- Network and IP management UI

### Phase 4 — Employee IT Profile & Onboarding
- IT profile view (assets, IPs, accounts for a user)
- Onboarding checklist IT task visibility in IT Dashboard
- Exit/offboarding deprovisioning hooks

### Phase 5 — Requests, Reports & Settings
- IT request filtered view leveraging existing ticketing
- Basic IT reports (asset register, IP allocation, open requests)
- IT Settings page for naming/numbering/network configuration
