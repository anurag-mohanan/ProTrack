# IT Import Root Cause Analysis

> **Date:** 2026-08-20  
> **Status:** Analysis complete — do not treat exception IDs as source data  
> **Primary code:** `app/services/it_migration_service.py`  
> **UI:** `frontend/src/components/it/ITMigrationPanel.tsx`  
> **API:** `GET/POST /api/v1/it/migration/*` in `app/api/v1/it_operations.py`

---

## 1. What the user observed

Preview / exception tables showed identifiers such as:

- `EX-HAR-0001-OWNERSHIP_UNCLEAR`
- `EX-HAR-0001-SERIAL_MISSING`

with messages like:

> `ID IT - 001 does not encode ownership; requires admin review.`

Those values look like asset IDs / field values, but they are **not** rows from the Excel source.

---

## 2. End-to-end import path (current)

| Layer | Location | Role |
|-------|----------|------|
| Import UI | `ITMigrationPanel.tsx` on IT Settings | Pick `source_type`, upload `.xlsx`, Analyze, Confirm |
| API | `it_operations.py` → `/it/migration/analyze`, `/import` | Multipart upload + session commit |
| Session store | `UPLOAD_DIR/it_migration/{uuid}.json` | Cached sanitized rows after analyze |
| Workbook reader | `openpyxl.load_workbook` in `_read_sheet_rows` | Sheet pick + header + row dicts |
| Sheet detection | `_SHEET_HINTS` + substring match | Per `source_type`, not per file template |
| Column access | `_get(row, *candidates)` | Exact then **substring** header match |
| Validation | Inline in `analyze_upload` | Builds `exceptions[]` with synthetic IDs |
| Preview | First 15 raw source rows (non-empty cells) | Not a mapped ProTrack preview |
| Insert | `commit_import` → `it_asset_service.create_asset` | Auto-generates `asset_number` |
| Ownership | `_infer_purchased_by` | Invents from `SY-` prefix / defaults to org |
| Secrets | Header regex strips password/license/TeamViewer cols | Correct intent; license never stored |

---

## 3. Root causes (ranked)

### RC-1 — Exception IDs are presented as if they were records (primary UX/data confusion)

In `analyze_upload`:

```python
"id": f"EX-{source_type[:3].upper()}-{idx:04d}-{exc['code']}"
```

Examples:

- `hardware` → `EX-HAR-0001-OWNERSHIP_UNCLEAR`
- Codes like `SERIAL_MISSING` / `OWNERSHIP_UNCLEAR` are **validation codes**, not source values.

The UI table header labels this column **“ID”** next to Severity / Code / Detail. That makes exception synthetic IDs look like imported Asset / Legacy IDs.

**Important:** `commit_import` does **not** write `EX-HAR-…` into `Asset.asset_number` or `serial_number`. The synthetic ID lives only in the analyze response / docs. Users reasonably mistook them for imported data because of labeling and because real ProTrack asset numbers are separately auto-generated (`LAPTOP-0001`, etc.), so the source ID is not what they see first in the grid.

### RC-2 — Source asset IDs are not used as ProTrack `asset_number`

`create_asset` always calls `next_asset_number()` and stores the Excel `ID` / `ID Tag` only in `legacy_asset_number`.

Acceptance requires:

- Source `IT-001` / `IT - 001` / `PP-SVR-01` preserved as the business identifier (`asset_number` and/or `legacy_asset_number` exactly as sourced).
- Internal UUID remains `Asset.id`.

Current behavior transforms identity into a new numbering scheme → **data fidelity failure**.

### RC-3 — Ownership is inferred from ID prefixes and defaults

`_infer_purchased_by`:

- If inventory `CUST PAID ?` matches a customer → customer-owned (OK when explicit).
- Else if legacy starts with `SY-` → treat as customer (FORBIDDEN inference).
- Else → `organization` (invents Prosohm ownership when source is silent).

Hardware sheet has **no** Purchased By / Customer Paid column. The importer still forces `purchased_by='organization'` and flags `IT-*` with `OWNERSHIP_UNCLEAR` while continuing to import as org-owned.

`CUSTOMER USED FOR` must never become ownership; current path mostly separates them, but fuzzy customer match + notes stuffing muddies the result.

### RC-4 — Validation messages can be written into asset `notes`

On commit:

```python
notes="; ".join(x for x in [desc, note, remarks] if x)
```

where `note` comes from ownership inference (`"SY- prefix suggests…"`, `"customer owner unresolved"`). That mixes **Layer 2 validation** into **Layer 1 data**.

### RC-5 — Serial / service tag coalescing invents serial values

```python
if not serial and service and source_type == "hardware":
    serial = service
```

Service tag is copied into `serial_number`. Missing serial should stay `NULL` with a separate `SERIAL_MISSING` warning — never a code string, and never an alias fill unless explicitly approved.

### RC-6 — Fragile / wrong column binding via substring `_get`

`_get(..., "Name")` is used as a fallback for `MAKE` on hardware/inventory. Inventory rows have `Name` but not `MAKE`, so **item name becomes `make`**.

Substring matching also risks wrong columns when headers share tokens (`ID` inside `ID Tag` is intended; other collisions are possible).

### RC-7 — Inventory multi-row headers need exact row 4; sheet names have trailing spaces

Original `PP-Asset-Inventory.xlsx`:

- Sheets: `INVENTORY LIST `, `SUPPLIER LIST ` (trailing spaces)
- Real column headers are Excel **row 4** (`Name`, `Description`, `ID Tag`, `CUST  PAID  ?`, …)
- Row 3 is a group banner (`REV001`, `LOCATION`, …)

Override `inventory: 3` (0-based) is correct **only if** that override is used. Auto header detection without override would bind the wrong row and produce garbage keys (`REV001`, `2022-23`), which matches the “normalized/processed workbook” failure mode.

### RC-8 — No true template model; operator picks a flat `source_type`

Operator chooses `hardware` | `inventory` | … and the service searches sheet-name hints. There is no:

- Detect `PP-INF-FO-7` vs `PP Asset Inventory` from workbook structure
- Normalized internal record model distinct from Excel layout
- Mapped preview (source → ProTrack fields → import action)

Compatible / renamed workbooks were a workaround for sheet-hint fragility — **not** the fix.

### RC-9 — Duplicate handling skips or conflicts; does not preserve IDs for admin decision

Strong duplicates skip when `skip_duplicates=true`. In-file duplicate `IT-136` is only flagged as `LEGACY_ID_COLLISION` in exceptions; commit still may insert both or fail uniqueness depending on path. IDs are never silently renamed today (`IT-136-2`), but there is also no admin choose/skip/review per duplicate pair in the UI.

### RC-10 — Idempotency is weak

Duplicate detection uses normalized legacy / serial / service tag against existing assets. There is no durable `(source_system, source_record_id)` on `Asset`. Re-import safety depends on legacy matching after the first import stored legacy correctly.

### RC-11 — Secrets handling is mostly correct but licenses are dropped silently

Password / TeamViewer / Windows license columns are excluded from row dicts (good). Product keys should remain **excluded from DB** with an explicit `PRODUCT_KEY_EXCLUDED` warning — not stored as plaintext.

---

## 4. What is *not* the root cause

- Adding more sheet aliases (`hardwares`, `1.hardwares`, …) will not fix identity/ownership/serial fidelity.
- `ProTrack_IT_Import.xlsx` / compatible workbooks are not the source of truth.
- Exception codes in `docs/IT_MIGRATION_EXCEPTIONS.md` are analysis artifacts, not Excel cells.

---

## 5. Required architectural fix (summary)

```
SOURCE EXCEL (original)
  → template detect + exact sheet/header map
  → Layer 1 SourceRecord (verbatim fields, null if blank)
  → Layer 2 ValidationIssue (codes never written into fields)
  → mapped preview + import_action (import | skip | review)
  → confirm
  → write ProTrack entities (asset_number = source ID when present)
  → migration report
```

Acceptance hinges on **data fidelity**, not on generating another intermediate workbook.

---

## 6. Likely bad prior import fingerprint (for Part 38)

Suspect rows to **analyze** (not auto-delete):

| Signal | Why |
|--------|-----|
| `asset_number` like `LAPTOP-####` / `DESKTOP-####` with `legacy_asset_number` set from Excel | Normal current importer behavior |
| `notes` containing `SY- prefix suggests` / `customer owner unresolved` | Validation leaked into data |
| `serial_number == service_tag` with empty distinct serial in source | Coalesce bug |
| `purchased_by=organization` on `SY-*` or blank-CUST-PAID rows | Invented ownership |
| Any `asset_number` / `serial_number` / `make` equal to `OWNERSHIP_UNCLEAR`, `SERIAL_MISSING`, or `EX-HAR-*` | Would indicate a different bug or manual edit — **query before delete** |

Recommend a read-only audit query / report before any rollback.

---

## 8. Prior-import cleanup policy (Part 38)

Do **not** delete production IT assets without a read-only audit.

Recommended SQL / admin checks:

1. Any asset where `asset_number`, `serial_number`, `service_tag`, `make`, or `notes` contain `OWNERSHIP_UNCLEAR`, `SERIAL_MISSING`, or `EX-HAR-` / `EX-INV-`.
2. Notes containing `SY- prefix suggests` or `customer owner unresolved` (old inference leak).
3. `serial_number = service_tag` where source had only a service tag.

For each hit: review assignments / computers / returns, then choose archive, correct, or leave. Prefer re-import with skip_duplicates after correction.

---

## 9. Fix status (this change set)

| Issue | Fix |
|-------|-----|
| Exception IDs shown as “ID” | UI: Exception # + source_key; codes never written to assets |
| Auto `LAPTOP-####` over source ID | `create_asset(asset_number=source ID)` |
| Ownership from `SY-` / default org | `purchased_by=unknown` unless explicit CUST PAID / PURCHASED BY |
| Serial ← service tag | Removed; blanks stay null |
| Validation in `notes` | Notes = source remarks only |
| Substring `_get` inventing Make from Name | Exact header match only |
| Preview of raw cells only | Mapped preview columns for hardware/inventory |
