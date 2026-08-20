# IT Data Migration Mapping

> **Status:** Mapped from live source files (2026-08-20)  
> **Sources:**
> 1. `PP-INF-FO-7_IT_RECORDS.xlsx` (OneDrive Master Documents / Infrastructue / RECORDS)
> 2. `PP-Asset-Inventory.xlsx` (OneDrive Administration_OD / Infrastructure)
>
> Working copies (gitignored): `docs/migration-sources/`

---

## 1. Target ProTrack entities (reuse first)

| Concept | ProTrack entity | Notes |
|---------|-----------------|-------|
| Employee / user | `User` | Match email, username, employee code, or name |
| Team / department | `Team` / `OrgDepartment` | Source “Design - Mobility” etc. need normalization |
| Customer | `Customer` | Match Sybridge / Platinum; **do not auto-create** |
| Audit | `Activity` | No secrets in payloads |

### New / extended IT entities

| Entity | Purpose |
|--------|---------|
| `Asset` + ownership fields | Serialized assets (IT + other categories as needed) |
| `Computer` | Hardware extension |
| `AssetAssignment` | Who uses the asset |
| `AssetCustomerReturn` | Customer-owned return events |
| `InventoryItem` | Consumables / stock qty |
| `ITSupplier` | Vendor master (seed from inventory SUPPLIER column — sheet is empty) |
| `SoftwareCatalog` / license pool / assignment | From softwares sheet |
| `ITUserAccount` | Account metadata only |
| `Network` / `IPAddress` | From hardware IP columns |

---

## 2. Critical separations

| Concept | Field(s) | Source signal (examples) |
|---------|----------|--------------------------|
| **Ownership** | `purchased_by` + `owner_customer_id` | Software `PURCHASED BY`; inventory `CUST PAID ?`; ID prefix `SY-` / GUIDE `SY`/`PL`/`PS` |
| **Usage** | `AssetAssignment` | `CURRENT USER` / `Current Designer / user` |
| **Customer work** | `customer_used_for_id` | Hardware `CUSTOMER USED FOR` (Generic / Prosohm Admin / Prosohm Eng / Sybridge) |
| **Location** | `location` | `ROOM` / storage location |
| **Org place** | dept/team | Inventory `Department` is often **customer/site label**, not HR department — map carefully |

---

## 3. File 1 — `PP-INF-FO-7_IT_RECORDS.xlsx`

### Sheets observed

| Sheet | Role | Rows (approx) |
|-------|------|----------------|
| `TITLE_PAGE` | Summary lists | Skip import |
| `1.HARDWARES` | Serialized IT hardware | **30** data rows |
| `2.USER_CREDENTIALS` | Accounts + **plaintext passwords** | **39** rows |
| `3.SOFTWARES_&_LICENSES` | Licenses + purchased-by | **26** rows |
| `DATASHEET` | Dropdown reference values | Normalize only — do not dump |

### 3.1 `1.HARDWARES` → Asset + Computer (+ IP)

| Source column | Target | Transform |
|---------------|--------|-----------|
| SL NO | import metadata | |
| ID | `legacy_asset_number` | Preserve exactly (`PP-SVR-01`, `SY-IT031`, `IT-120`, …) |
| DESCRIPTION | `description` / notes | |
| CUSTOMER USED FOR | `customer_used_for_id` | Match Customer / internal labels; **not** ownership alone |
| TYPE | `AssetType` | Firewall, Laptop, Printer, Server, Workstation |
| CURRENT USER | current assignment | Match `User`; values like `SERVPROSOHM`, `All`, `Open`, room names → exception |
| MAKE / MODEL | make / model | |
| CURRENT STATUS | status | Observed live data: all `WORKING` → `available`/`assigned`. DATASHEET also has `NOT WORKING`, `SCRAPPED` |
| WARRANTY / WARRANTY VALID UPTO | warranty note + `warranty_expiry` | Placeholder `2099-12-31` → review |
| DATE OF PURCHASE | `purchase_date` | |
| NO. OF YEARS IN USE | skip / derive | |
| NAME | `Computer.computer_name` or description | Product marketing name often, not hostname |
| IP ADDRESS | IP allocate / notes | May contain **multiple IPs** (newlines) |
| 2ND IP ADDRESS | secondary IP / notes | Rare (1/30) |
| RAM / VIDEO* / CPU | Computer fields + `hardware_json` | |
| WINDOWS LICENSE # | **do not store as secret in clear UI**; optional hashed/vault later or skip | Treat as sensitive product key |
| SERVICE TAG# | `service_tag` + serial candidate | Strong duplicate key |
| MAC Address | `mac_address` | |
| OS | `os` | |
| Teamviewer ID/pwd | **NEVER IMPORT** | Sensitive |
| remarks | notes | |

**Observed ID prefixes (30 rows):** `PP`×5, `SY`×15, `IT`×10.

**Ownership inference (review queue — do not auto-commit):**

| Signal | Suggested `purchased_by` |
|--------|---------------------------|
| ID starts with `SY-` | `customer` + owner Sybridge (confirm) |
| ID starts with `PP-` | `organization` (confirm); `CUSTOMER USED FOR` stays usage |
| ID starts with `IT-` | Unclear — use inventory cross-match / admin review |
| `CUSTOMER USED FOR` alone | **Never** sole ownership proof |

**Internal duplicate:** `IT-136` appears **twice** with different service tags → `LEGACY_ID_COLLISION`.

### 3.2 `2.USER_CREDENTIALS` → ITUserAccount (+ User match)

| Source | Target | Notes |
|--------|--------|-------|
| EMPLOYEE NAME | User match | |
| CUSTOMER ASSIGNED TO | notes / customer association | Admin / Prosohm Eng / Sybridge |
| DEPARTMENT / DESIGNATION | profile — do not overwrite blindly | |
| STATUS | account / user lifecycle hint | Current (12), Ex-Employee (22), Hardware (5) |
| USERNAME | `ITUserAccount.username` | |
| EMAIL / MS TEAMS ID / CUSTOMER MS TEAMS ID | account identifiers | Multiple account types per person |
| Phone number | User phone if empty | |
| **PWD, PWA & DC pwd., PWD2, PWD3, PWD4** | **NEVER IMPORT** | Mark `credential_status=migration_required` |
| PWA / Data complete | usernames only if non-secret | |

### 3.3 `3.SOFTWARES_&_LICENSES`

| Source | Target |
|--------|--------|
| SOFTWARE | `SoftwareCatalog.name` (NX GLOBAL, SOLIDWORKS*, OFFICE 365, …) |
| PURCHASED BY | `purchased_by`: PROSOHM→`organization`, SYBRIDGE→`customer`+Sybridge (**14** Sybridge / **12** Prosohm) |
| NO OF USER\LICENSE | seat count |
| LICENSE VALID UPTO | expiry |
| RENEWAL MODE | renewal_mode |
| USER | assignment → User |
| DEPARTMENT / COMMENTS | notes |

### 3.4 `DATASHEET`

Reference vocab only. Notable status values for hardware: `WORKING`, `NOT WORKING`, `SCRAPPED`. Purchased-by: `PROSOHM`, `SYBRIDGE`.

---

## 4. File 2 — `PP-Asset-Inventory.xlsx`

### Sheets observed

| Sheet | Role | Notes |
|-------|------|-------|
| `INVENTORY LIST ` (trailing space) | Main register | Header on **row 4**; ~277 named items |
| `CONSUMABLES` | Stock / consumables | Header row 4; ~10 real items + empty shells |
| `SUPPLIER LIST ` | Vendor template | **Empty** (row numbers only) |
| `GUIDE` | Prefix / category legend | PS=PROSOHM, SY=SYBRIDGE, PL=PLATINUM; IT/FU/UP/KT |

### 4.1 `INVENTORY LIST` (row 4 headers)

| Source | Target | Notes |
|--------|--------|-------|
| Name | description / InventoryItem.name | |
| Description | description | |
| ID Tag | `legacy_asset_number` | Preserve spacing variants (`IT - 001`) |
| Category | type / inventory class | IT (179), FURNITURE (60), TOOLS (15), UPS (9), BATTERY (10), KITCHEN (3) |
| Department | **often customer/site** (Prosohm / Sybridge / platinum) — not HR dept | Map to owner or location context with review |
| ROOM | `location` | Normalize free text |
| Current Designer / user | assignment | Sparse (38); free-text names + workstation codes |
| DATE | purchase_date | |
| SUPPLIER | `ITSupplier` | **Primary supplier seed** (16 distinct names) |
| Service/Serial | service_tag / serial | Sparse |
| WARRANTY/EXPIRATION | warranty_expiry | |
| CONDITION | condition/status | WORKING (265), DISPOSED (8) → disposed/historical |
| QTY / IN USE / AVAILABLE | qty fields | Serialized IT usually qty=1 |
| VALUE | purchase_cost | |
| MODEL NUMBER / SERIAL NUMBER / INVOICE NO | model, serial, invoice | Serial rarely filled (4) |
| CUST PAID ? | **ownership** when set | Values are customer names: SYBRIDGE (60), PLATINUM (39) — not Yes/No |
| REMARKS/NOTES | notes | |
| CUSTOMER LIST | **dropdown list helper column** — not per-row owner | Ignore as row field |

**IT subset:** 179 rows; 99 have `CUST PAID ?` filled → strong customer-owned candidates.

### 4.2 `CONSUMABLES` → InventoryItem

Real stock rows include HDMI cables, DP adapters, mouse, keyboard, power cables, pens, bottles, coffee/tea.

| Rule | Detail |
|------|--------|
| Entity | `InventoryItem` — not one Asset per unit |
| Qty | `total_qty`, `issued_qty`, `available_qty` |
| Math | Observed filled rows: QTY = IN USE + AVAILABLE (OK) |

Amenities (coffee, pens) may belong in **general inventory**, not IT Assets — configurable category filter.

### 4.3 `SUPPLIER LIST`

Sheet is empty. Seed suppliers by **deduplicating** `INVENTORY LIST.SUPPLIER` (normalize case: “Inspire infotech…” variants).

### 4.4 `GUIDE`

| Code | Meaning |
|------|---------|
| PS | PROSOHM (organization-owned sticker) |
| SY | SYBRIDGE |
| PL | PLATINUM |
| IT / FU / UP / KT | Category prefixes on tags |

Do not hardcode these strings in app logic — store as tenant config / migration lookup.

---

## 5. Duplicate detection (cross-file)

### Strong match

1. Exact `service_tag` / serial (normalized)
2. Exact `legacy_asset_number` after normalizing spaces (`IT-083` ↔ `IT - 083`)
3. Computer name uniqueness (when true hostname)

### Observed overlaps (2026-08-20 analysis)

| Finding | Detail |
|---------|--------|
| ID overlap | **9** hardware IDs also appear as inventory ID Tags: `IT-083`, `IT-120`, `IT-136`, `IT-147`, `IT-155`, `IT-156`, `IT-163`, `IT-164`, `IT-175` → merge/review |
| Service tag overlap | At least `DP5LM24`, `JMVMM24` present in both sources |
| Serial column sparse | Inventory SERIAL NUMBER rarely filled — prefer SERVICE TAG / Service/Serial |
| Internal HW duplicate | `IT-136` twice in HARDWARES |

No silent merge: emit `POSSIBLE_DUPLICATE` / `CROSS_FILE_OVERLAP`.

---

## 6. Status → Current inventory

| Source | ProTrack status | Current inventory? |
|--------|-----------------|--------------------|
| WORKING | available / assigned | Yes |
| NOT WORKING | damaged / maintenance | Configurable |
| SCRAPPED / DISPOSED | disposed | **No** |
| (future) returned to customer | returned_to_customer | **No** |

Default Current Assets filter excludes disposed/returned/deleted.

---

## 7. Credential & secret columns (non-negotiable)

| Column | Action |
|--------|--------|
| PWD, PWD2, PWD3, PWD4, PWA & DC pwd. | Exclude — never store/preview/log/export |
| Teamviewer ID/pwd | Exclude |
| WINDOWS LICENSE # | Exclude from normal columns; optional secure vault later |

Accounts import with `credential_status = migration_required`.

---

## 8. Import workflow

```
IT Settings → Data Migration
  → Select source (Hardware / Inventory / Software / Accounts / Suppliers)
  → Point at OneDrive or upload copy
  → Analyze → Map → Duplicate detection → Exceptions
  → Preview (no secrets) → Confirm → Commit
  → IT_MIGRATION_RESULT
```

Never overwrite existing ProTrack assets automatically.

---

## 9. Commercialization

Ownership option **codes** (`organization`, `customer`, …) are fixed; **labels** and customer names come from tenant settings / Customer master — not hardcoded Prosohm/Sybridge/Platinum in application logic.
