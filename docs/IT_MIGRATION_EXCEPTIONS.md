# IT Migration Exceptions

> **Status:** Populated from live spreadsheet analysis (2026-08-20)  
> **Sources analyzed:**
> - `PP-INF-FO-7_IT_RECORDS.xlsx`
> - `PP-Asset-Inventory.xlsx`
>
> Paths: see `docs/migration-sources/README.md`  
> Resolution policy: **do not silently guess** ownership, customer, serial, or status.

---

## How to use

Each exception needs: ID, source sheet/row, severity, category, source key, detail, suggested action, resolution.

### Category codes

`DUPLICATE_STRONG` · `DUPLICATE_WEAK` · `CROSS_FILE_OVERLAP` · `LEGACY_ID_COLLISION` · `OWNERSHIP_UNCLEAR` · `CUSTOMER_UNKNOWN` · `CUSTOMER_AMBIGUOUS` · `USER_UNKNOWN` · `USER_INACTIVE` · `DEPT_UNKNOWN` · `STATUS_UNMAPPED` · `DATE_INVALID` · `SERIAL_MISSING` · `SUPPLIER_AMBIGUOUS` · `SENSITIVE_EXCLUDED` · `RETURNED_UNCONFIRMED` · `QTY_INCONSISTENT` · `SHEET_EMPTY` · `HEADER_LAYOUT` · `PRODUCT_KEY_EXCLUDED`

---

## A. File / sheet level

| ID | Severity | Category | Detail | Action |
|----|----------|----------|--------|--------|
| EX-SYS-0010 | Info | `HEADER_LAYOUT` | Inventory sheets use multi-row headers; real columns are on **row 4**. Sheet names have trailing spaces (`INVENTORY LIST `, `SUPPLIER LIST `). | Parser must use explicit header row |
| EX-SYS-0011 | Warning | `SHEET_EMPTY` | `SUPPLIER LIST ` has headers but **no supplier data** | Seed suppliers from inventory `SUPPLIER` column |
| EX-SYS-0012 | Blocker (security) | `SENSITIVE_EXCLUDED` | `2.USER_CREDENTIALS` has plaintext columns: PWD, PWA & DC pwd., PWD2, PWD3, PWD4 | Never import/preview/log; mark accounts migration_required |
| EX-SYS-0013 | Blocker (security) | `SENSITIVE_EXCLUDED` | `1.HARDWARES.Teamviewer ID/pwd` filled on 14/30 rows | Exclude entirely |
| EX-SYS-0014 | Review | `PRODUCT_KEY_EXCLUDED` | `WINDOWS LICENSE #` present on most hardware rows | Do not store in cleartext asset fields / UI |

---

## B. Hardware (`1.HARDWARES`) — 30 rows

| ID | Severity | Category | Source key | Detail | Action |
|----|----------|----------|------------|--------|--------|
| EX-HW-0001 | Blocker | `LEGACY_ID_COLLISION` | `IT-136` | Two rows share ID with different service tags (`DQVGZL2` vs `CQ9DFN2`) | Split IDs or admin chooses survivors before import |
| EX-HW-0002 | Review | `OWNERSHIP_UNCLEAR` | `IT-*` (10 rows) | Prefix does not encode owner; `CUSTOMER USED FOR` is usage | Cross-match inventory `CUST PAID ?` / admin review |
| EX-HW-0003 | Review | `OWNERSHIP_UNCLEAR` | `PP-*` + `CUSTOMER USED FOR=Sybridge` | Likely organization-owned, used for Sybridge | Confirm; do not set owner=Sybridge from usage alone |
| EX-HW-0004 | Review | `OWNERSHIP_UNCLEAR` | `SY-*` (15 rows) | Strong customer-owned *candidate* via GUIDE/prefix | Confirm owner=Sybridge before commit |
| EX-HW-0005 | Review | `USER_UNKNOWN` | various | CURRENT USER values: `SERVPROSOHM`, `XGS 116w`, `All`, `Open`, `Conference room`, `Planning board`, `Eng Planning Board`, `Prosohm Eng Team` | Not all are people — skip assignment or map as location/role |
| EX-HW-0006 | Warning | `SERIAL_MISSING` | `PP-WS-16` | Empty SERVICE TAG | Require serial or accept exception |
| EX-HW-0007 | Warning | `DATE_INVALID` | `PP-FW-01` | Warranty valid upto `2099-12-31` | Treat as sentinel / clear |
| EX-HW-0008 | Review | `CUSTOMER_UNKNOWN` | `Generic`, `Prosohm Admin`, `Prosohm Eng` | Not ProTrack Customer records | Map to internal labels / null customer_used_for + exception |
| EX-HW-0009 | Info | — | all | CURRENT STATUS only `WORKING` in live sheet | DATASHEET still lists NOT WORKING / SCRAPPED for future rows |

---

## C. Cross-file overlaps (Hardware ↔ Inventory)

| ID | Severity | Category | Detail | Action |
|----|----------|----------|--------|--------|
| EX-X-0001 | Review | `CROSS_FILE_OVERLAP` | Normalized ID match for: IT-083, IT-120, IT-136, IT-147, IT-155, IT-156, IT-163, IT-164, IT-175 | Single Asset after merge review; prefer richer hardware row for computer fields |
| EX-X-0002 | Review | `DUPLICATE_STRONG` | Service tags `DP5LM24`, `JMVMM24` appear in both files | Link as same asset |
| EX-X-0003 | Review | `DUPLICATE_WEAK` | Sophos firewall / Dell workstations described in both registers with different ID schemes (`PP-FW-01` vs inventory SOPHOS FIREWALL) | Manual match by serial/model |

---

## D. Inventory list — ~277 named rows

| ID | Severity | Category | Detail | Action |
|----|----------|----------|--------|--------|
| EX-INV-0001 | Review | `OWNERSHIP_UNCLEAR` | `CUST PAID ?` blank on many IT rows (80/179 IT) | Admin sets organization vs customer |
| EX-INV-0002 | Info | — | `CUST PAID ?` values are **customer names** (SYBRIDGE×60, PLATINUM×39), not Yes/No | Map to purchased_by=customer + owner_customer |
| EX-INV-0003 | Review | `DEPT_UNKNOWN` | `Department` values are Prosohm/Sybridge/platinum (site/customer), not HR departments | Do not write into OrgDepartment without mapping table |
| EX-INV-0004 | Warning | `SERIAL_MISSING` | Only 4 SERIAL NUMBER values filled; Service/Serial also sparse | Prefer tags; flag serialized IT without serial |
| EX-INV-0005 | Info | — | CONDITION `DISPOSED` ×8 | Import as disposed; exclude from Current Assets |
| EX-INV-0006 | Review | `USER_UNKNOWN` | Designer/user free text with nicknames / table labels | Fuzzy match Users; else exception |
| EX-INV-0007 | Warning | `SUPPLIER_AMBIGUOUS` | Supplier name casing variants (`Inspire infotech…`) | Normalize before insert |
| EX-INV-0008 | Info | — | Non-IT categories (FURNITURE, KITCHEN, TOOLS, UPS, BATTERY) | Route to General Inventory vs IT Assets per policy |
| EX-INV-0009 | Info | `HEADER_LAYOUT` | Column `CUSTOMER LIST` is a validation list (PLATINUM/SYBRIDGE), not row ownership | Ignore for per-row mapping |

---

## E. Consumables

| ID | Severity | Category | Detail | Action |
|----|----------|----------|--------|--------|
| EX-CON-0001 | Info | — | Qty identity holds on filled rows (QTY = IN USE + AVAILABLE) | Import as InventoryItem |
| EX-CON-0002 | Warning | — | Many empty shell rows (AVAILABLE=0 only) | Skip blank names |
| EX-CON-0003 | Review | — | Amenities (coffee, pens, bottles) mixed with IT cables | Separate IT vs facilities stock |

---

## F. Credentials (`2.USER_CREDENTIALS`) — 39 rows

| ID | Severity | Category | Detail | Action |
|----|----------|----------|--------|--------|
| EX-CR-0001 | Blocker | `SENSITIVE_EXCLUDED` | All password columns | Exclude; generate/reset later |
| EX-CR-0002 | Review | `USER_INACTIVE` | STATUS Ex-Employee ×22 | Import historical account metadata carefully; no active assignment |
| EX-CR-0003 | Review | `USER_UNKNOWN` | STATUS Hardware ×5 | Not employees — map to asset-linked accounts or skip |
| EX-CR-0004 | Review | `CUSTOMER_UNKNOWN` | CUSTOMER ASSIGNED TO = Admin / Prosohm Eng | Internal labels |

---

## G. Software — 26 rows

| ID | Severity | Category | Detail | Action |
|----|----------|----------|--------|--------|
| EX-SW-0001 | Info | — | PURCHASED BY only PROSOHM / SYBRIDGE | Map to organization / customer ownership |
| EX-SW-0002 | Review | `USER_UNKNOWN` | Assigned USER free text | Match Users |
| EX-SW-0003 | Warning | — | Some LICENSE VALID UPTO blank / possibly expired | Flag renewals |

---

## H. Customers to match in ProTrack (do not auto-create)

| Source label | Likely Customer | Notes |
|--------------|-----------------|-------|
| Sybridge / SYBRIDGE | Sybridge | Hardware usage, CUST PAID, software purchaser |
| Platinum / PLATINUM | Platinum | CUST PAID / GUIDE |
| Prosohm / PROSOHM / Prosohm Eng / Prosohm Admin | Organization (not customer) | Ownership label `organization` |
| Generic | none | Usage placeholder |

If Customer master lacks Sybridge or Platinum → `CUSTOMER_UNKNOWN` blocker for those owned rows.

---

## Resolution policy

| Severity | Import behavior |
|----------|-----------------|
| Blocker | Batch cannot complete until resolved or explicitly skipped |
| Review | Conflict queue; remainder may proceed after confirm |
| Warning / Info | Import allowed with flags in `IT_MIGRATION_RESULT` |

---

## Next step

Re-run analysis after admin decisions on EX-HW-0001, EX-X-0001, and Customer master matching; then proceed to import preview UI.
