# IT Import Source Mapping

> **Source of truth (only):**  
> 1. `PP-INF-FO-7_IT_RECORDS.xlsx`  
> 2. `PP-Asset-Inventory.xlsx`  
>  
> Working copies: `docs/migration-sources/` (xlsx gitignored)  
> Inspected: 2026-08-20  
> Do **not** use `ProTrack_IT_Import*.xlsx` as mapping authority.

---

## Template A — `PP-INF-FO-7_IT_RECORDS.xlsx`

**Detected by sheets:** `1.HARDWARES`, `2.USER_CREDENTIALS`, `3.SOFTWARES_&_LICENSES`  
**Skip:** `TITLE_PAGE` (summary), `DATASHEET` (dropdown lists only)

### Sheet inventory

| Sheet | Rows (file) | Header row (0-based) | Data rows (approx) | Role |
|-------|-------------|----------------------|--------------------|------|
| `TITLE_PAGE` | 19 | n/a | summary only | Lookup / cover — **do not import** |
| `1.HARDWARES` | 500 | **1** (row after title) | **30** filled | Serialized hardware |
| `2.USER_CREDENTIALS` | 41 | **1** | **39** | Account metadata (+ secrets) |
| `3.SOFTWARES_&_LICENSES` | 28 | **1** | **26** | Software / licenses |
| `DATASHEET` | 11 | 0 | lists | Config / validation lists — **do not import as records** |

---

### A1. `1.HARDWARES` → Asset (+ Computer when TYPE is computer-like)

**Title row 0:** `HARDWARES LIST`  
**Header row 1 columns (27):**

| # | Source column | ProTrack field | Notes |
|---|---------------|----------------|-------|
| 0 | SL NO | import metadata only | |
| 1 | **ID** | `asset_number` **and** `legacy_asset_number` | Preserve exactly (`PP-SVR-01`, `SY-IT031`, `IT-120`, …). Never rewrite to `EX-HAR-…` |
| 2 | DESCRIPTION | `description` | Verbatim |
| 3 | CUSTOMER USED FOR | `customer_used_for_id` | Usage only — **not ownership**. Values: Generic, Prosohm Admin, Prosohm Eng, Sybridge |
| 4 | TYPE | `asset_type` | Firewall, Laptop, Printer, Server, Workstation |
| 5 | CURRENT USER | assignment → User | Match employee; else leave unassigned + `USER_UNKNOWN` |
| 6 | MAKE | `make` | |
| 7 | MODEL | `model` | |
| 8 | CURRENT STATUS | `status` / `condition` | Live data: WORKING → current. Map SCRAPPED/DISPOSED/NOT WORKING from DATASHEET vocabulary when present |
| 9 | WARRANTY | note / condition text | Do not invent return |
| 10 | WARRANTY VALID UPTO | `warranty_expiry` | `2099-12-31` → null + warning |
| 11 | DATE OF PURCHASE | `purchase_date` | |
| 12 | NO. OF YEARS IN USE | metadata / ignore | |
| 13 | NAME | `Computer` display / product name | Often marketing name, not hostname |
| 14 | IP ADDRESS | metadata / future IP link | May contain newlines / multiple IPs |
| 15 | 2ND IP ADDRESS | metadata | Rare |
| 16 | RAM (GB) | `Computer.ram_gb` | Parse int when possible |
| 17–19 | VIDEO MFG / CARD / RAM | computer metadata | |
| 20 | WINDOWS LICENSE # | **never store plaintext** | `PRODUCT_KEY_EXCLUDED` warning only |
| 21 | SERVICE TAG# | `service_tag` | Blank → **NULL** + optional `SERIAL_MISSING` warning (do not copy into serial) |
| 22 | MAC Address | `Computer.mac_address` | |
| 23 | OS | `Computer.os` | |
| 24 | CPU (Ghz) | `Computer.processor` | |
| 25 | Teamviewer ID/pwd | **never import** | Sensitive |
| 26 | remarks | `notes` (source remarks only) | No validation codes |

**Ownership on this sheet:** There is **no** Purchased By / Customer Paid column.  
→ `purchased_by = unknown` (or null) + `OWNERSHIP_UNCLEAR` review warning.  
→ Do **not** infer from `PP-` / `SY-` / `IT-` prefixes.  
→ Do **not** treat CUSTOMER USED FOR as owner.

**Sample source IDs:** `PP-SVR-01`, `PP-FW-01`, `SY-IT031`, `IT-083`, …  
**In-file duplicate:** `IT-136` appears twice (different service tags) → detect, do not auto-rename.

---

### A2. `2.USER_CREDENTIALS` → `ITUserAccount` metadata only

| Source column | Import? | Target |
|---------------|---------|--------|
| EMPLOYEE NAME | yes | match User |
| CUSTOMER ASSIGNED TO | yes | metadata / notes (not asset ownership) |
| DEPARTMENT / DESIGNATION / STATUS | yes | metadata / account status |
| USERNAME | yes | `ITUserAccount.username` |
| EMAIL / MS TEAMS ID / CUSTOMER MS TEAMS ID | yes | account rows / notes |
| Phone number / PWA / Data complete | optional metadata | |
| **PWD, PWA & DC pwd., PWD2, PWD3, PWD4** | **NEVER** | exclude; `credential_status=migration_required` |

---

### A3. `3.SOFTWARES_&_LICENSES` → SoftwareCatalog + LicensePool + Assignment

| Source column | Target |
|---------------|--------|
| SOFTWARE | catalog name (trim trailing spaces in header) |
| **PURCHASED BY** | explicit ownership: `PROSOHM` → organization; `SYBRIDGE` → customer + owner match |
| NO OF USER\LICENSE | seat_count |
| LICENSE VALID UPTO | expiry_date |
| RENEWAL MODE | renewal_mode |
| USER | assignment user match |
| DEPARTMENT | assignment department text |
| COMMENTS | notes |

---

## Template B — `PP-Asset-Inventory.xlsx`

**Detected by sheets:** `INVENTORY LIST `, `CONSUMABLES`, `SUPPLIER LIST `, `GUIDE`  
(Note trailing spaces on list sheet names.)

### Sheet inventory

| Sheet | Rows | Header row (0-based) | Real data | Role |
|-------|------|----------------------|-----------|------|
| `INVENTORY LIST ` | 550 | **3** (Excel row 4) | ~277 named items | Inventory / assets |
| `CONSUMABLES` | 155 | **3** | ~10 meaningful + empty shells | Stock qty |
| `SUPPLIER LIST ` | 155 | **3** | **0 suppliers** | Empty — import count 0 |
| `GUIDE` | 41 | n/a | prefix legend | Config only — **do not import** |

Row 2 on inventory/consumables is a **group banner**, not columns. Binding headers to row 2 produces keys like `REV001` / `2022-23` and corrupts the import.

---

### B1. `INVENTORY LIST ` (header row 3)

| Source column | ProTrack field | Notes |
|---------------|----------------|-------|
| Name | `description` or inventory name / asset description | Not `make` |
| Description | `description` (prefer longer text) | |
| **ID Tag** | `asset_number` + `legacy_asset_number` | Preserve exactly including spaces (`IT - 001`) |
| Category | route IT vs furniture/kitchen/tools | Policy filter; do not invent returns |
| Department | location/site label often (Sybridge/Prosohm) — **not** HR dept blindly | |
| ROOM | `location` | |
| Current Designer / user | assignment match | |
| DATE | `purchase_date` | |
| SUPPLIER | match/create supplier carefully | |
| Service/Serial | prefer `service_tag` if tag-like; else serial — **do not invent** | |
| WARRANTY/EXPIRATION | `warranty_expiry` | |
| CONDITION | status mapping (WORKING, DISPOSED, …) | |
| QTY / IN USE / AVAILABLE | inventory qty fields when non-serialized | |
| VALUE | `purchase_cost` | |
| MODEL NUMBER | `model` | |
| SERIAL NUMBER | `serial_number` | blank → NULL |
| INVOICE NO | `invoice_number` | |
| **CUST  PAID  ?** | ownership when **customer name present** | Values are names (SYBRIDGE, PLATINUM), not Yes/No. Blank → `purchased_by=unknown` + warning |
| REMARKS/NOTES | `notes` (source only) | |
| CUSTOMER LIST | validation list column — **ignore for row ownership** | |

**Ownership rules (inventory only):**

- `CUST  PAID  ?` = customer name matched → `purchased_by=customer`, `owner_customer_id=matched`  
- Blank / unmatched → `purchased_by=unknown`, warning — **do not default to organization**

---

### B2. `CONSUMABLES`

| Source | Target |
|--------|--------|
| Name | `InventoryItem.name` |
| Description | description |
| Category / STORAGE LOCATION / CONDITION | fields |
| QTY / IN USE / AVAILABLE | total / issued; warn if inconsistent |
| VALUE | unit_cost |

Empty name shells → skip (not fake rows).

---

### B3. `SUPPLIER LIST `

Headers present; **no supplier names filled**.  
Expected result: `0` imported, `SHEET_EMPTY` warning. Do not invent suppliers.

---

### B4. `GUIDE`

Documents ID prefix meaning (`PS`=PROSOHM, `SY`=SYBRIDGE, `PL`=PLATINUM).  
Useful for **human review hints only**. Must **not** auto-set ownership from prefix during import.

---

## Cross-file notes

Normalized ID overlaps exist between hardware `IT-083`… and inventory `IT - 083`-style tags. Treat as **possible duplicates** for admin review — do not silently merge or rename.

---

## Layer separation (mandatory)

| Layer | Contents |
|-------|----------|
| Source data | Exact Excel values; blanks → NULL |
| Validation | `OWNERSHIP_UNCLEAR`, `SERIAL_MISSING`, `USER_UNKNOWN`, … in exceptions / warnings only |
| ProTrack write | Mapped fields only; never write validation codes into serial/owner/asset_number |
