# IT IMPORT CLEANUP PREVIEW (DRY RUN)

> **Status:** Dry-run complete. Confirmed target = local `protrack.db`.
> **Follow-up (2026-08-20):** Session cache purged only (`uploads/it_migration/*.json` → 0 files). **No DB rows deleted.**
> **Database:** `C:\Users\anumoh\Documents\Coding\ProTrack\protrack.db`

## Schema: IT-related tables

| Table | Rows |
| --- | ---: |
| `asset_assignments` | 0 |
| `asset_customer_returns` | 0 |
| `asset_types` | 10 |
| `assets` | 0 |
| `computers` | 0 |
| `document_assets` | 0 |
| `exit_interviews` | 0 |
| `inventory_items` | 0 |
| `ip_addresses` | 0 |
| `ip_assignment_history` | 0 |
| `it_settings` | 1 |
| `it_suppliers` | 0 |
| `it_user_accounts` | 0 |
| `networks` | 0 |
| `software_assignments` | 0 |
| `software_catalog` | 0 |
| `software_license_pools` | 0 |
| `team_membership_periods` | 4 |

## Import batch columns on `assets`

**No `import_batch_id` / `source_system` / `source_file` columns on `assets`.** Identification must use activity logs + deterministic field fingerprints.

Full `assets` columns: `id`, `asset_number`, `asset_type_id`, `serial_number`, `make`, `model`, `status`, `purchase_date`, `purchase_cost`, `warranty_expiry`, `location`, `notes`, `is_deleted`, `created_at`, `updated_at`, `tenant_id`, `legacy_asset_number`, `description`, `service_tag`, `purchased_by`, `owner_customer_id`, `customer_used_for_id`, `supplier_id`, `invoice_number`, `condition`

## Import / migration activity log

Found **18** migration analyze/import activity rows.

| # | Action | Created at | User | Payload summary |
| ---: | --- | --- | --- | --- |
| 1 | `it_migration_analyzed` | 2026-08-20 11:07:41 | `aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` | `{"filename": "PP-INF-FO-7_IT_RECORDS.xlsx", "source_type": "hardware", "session_id": "5dbb1c65-e7c3-4f8b-9ce1-00df4b982262"}` |
| 2 | `it_migration_analyzed` | 2026-08-20 11:07:41 | `aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` | `{"filename": "PP-INF-FO-7_IT_RECORDS.xlsx", "source_type": "accounts", "session_id": "aa3b68ef-06d1-4f58-ab4c-78d42b237ea1"}` |
| 3 | `it_migration_analyzed` | 2026-08-20 11:07:41 | `aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` | `{"filename": "PP-INF-FO-7_IT_RECORDS.xlsx", "source_type": "software", "session_id": "7d22fe7b-8fc3-4bb2-9b0b-8a8a829fcc89"}` |
| 4 | `it_migration_analyzed` | 2026-08-20 11:07:41 | `aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` | `{"filename": "PP-Asset-Inventory.xlsx", "source_type": "inventory", "session_id": "7efe0071-65f4-424c-b739-a1c0569e0fd7"}` |
| 5 | `it_migration_analyzed` | 2026-08-20 11:07:41 | `aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` | `{"filename": "PP-Asset-Inventory.xlsx", "source_type": "consumables", "session_id": "cf821e32-5459-4883-abb1-3798c01f18d5"}` |
| 6 | `it_migration_analyzed` | 2026-08-20 11:07:41 | `aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` | `{"filename": "PP-Asset-Inventory.xlsx", "source_type": "suppliers", "session_id": "49a19f9b-fd4a-4b1f-937f-1de7737774f9"}` |
| 7 | `it_migration_analyzed` | 2026-08-20 11:08:33 | `aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` | `{"filename": "PP-INF-FO-7_IT_RECORDS.xlsx", "source_type": "hardware", "session_id": "7e25c790-cad8-49ec-bfb0-9f3bfc4836a5"}` |
| 8 | `it_migration_analyzed` | 2026-08-20 11:08:33 | `aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` | `{"filename": "PP-INF-FO-7_IT_RECORDS.xlsx", "source_type": "accounts", "session_id": "861b973a-5121-4997-8cc7-3e98514e2807"}` |
| 9 | `it_migration_analyzed` | 2026-08-20 11:08:33 | `aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` | `{"filename": "PP-INF-FO-7_IT_RECORDS.xlsx", "source_type": "software", "session_id": "d3daab8a-a2b2-4179-bf3a-348c48551ef6"}` |
| 10 | `it_migration_analyzed` | 2026-08-20 11:08:33 | `aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` | `{"filename": "PP-Asset-Inventory.xlsx", "source_type": "inventory", "session_id": "07f19469-b396-488f-859e-81fd60da8889"}` |
| 11 | `it_migration_analyzed` | 2026-08-20 11:08:33 | `aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` | `{"filename": "PP-Asset-Inventory.xlsx", "source_type": "consumables", "session_id": "fc2be9f9-b76c-4b1c-b7a4-649160b80e02"}` |
| 12 | `it_migration_analyzed` | 2026-08-20 11:08:33 | `aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` | `{"filename": "PP-Asset-Inventory.xlsx", "source_type": "suppliers", "session_id": "6d1787a0-c330-4f9c-b2f0-34ae36eed510"}` |
| 13 | `it_migration_analyzed` | 2026-08-20 11:33:43 | `aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` | `{"filename": "PP-INF-FO-7_IT_RECORDS.xlsx", "source_type": "hardware", "session_id": "956ff73e-ccc3-4d9e-9116-76e30fa4afdc"}` |
| 14 | `it_migration_analyzed` | 2026-08-20 11:33:43 | `aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` | `{"filename": "PP-INF-FO-7_IT_RECORDS.xlsx", "source_type": "accounts", "session_id": "13b343bf-b49a-4f28-bdd1-9518620a15c4"}` |
| 15 | `it_migration_analyzed` | 2026-08-20 11:33:43 | `aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` | `{"filename": "PP-INF-FO-7_IT_RECORDS.xlsx", "source_type": "software", "session_id": "baa77486-ec80-4047-bea9-28ea28454d01"}` |
| 16 | `it_migration_analyzed` | 2026-08-20 11:33:43 | `aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` | `{"filename": "PP-Asset-Inventory.xlsx", "source_type": "inventory", "session_id": "f992491e-d35f-4a35-b769-d0ae274e2670"}` |
| 17 | `it_migration_analyzed` | 2026-08-20 11:33:43 | `aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` | `{"filename": "PP-Asset-Inventory.xlsx", "source_type": "consumables", "session_id": "34420291-4f00-434f-8f4a-90e125af483a"}` |
| 18 | `it_migration_analyzed` | 2026-08-20 11:33:43 | `aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` | `{"filename": "PP-Asset-Inventory.xlsx", "source_type": "suppliers", "session_id": "3a1ccba5-eed5-4d7d-8c61-b5caf239dee5"}` |

`it_asset_created` activities: **0** (first=None, last=None)

## Asset population

- Active (not deleted): **0**
- Including soft-deleted: **0**

## Deterministic fingerprints (active assets)

| Fingerprint | Count | Description |
| --- | ---: | --- |
| `has_legacy_asset_number` | 0 | Assets with legacy_asset_number set (importer always sets this) |
| `purchased_by_unknown` | 0 | Assets with purchased_by=unknown (migration ownership unclear) |
| `notes_migration_hints` | 0 | Assets with known bad migration note text |
| `auto_generated_numbers` | 0 | Assets with auto-generated type-prefix numbers (pre-fix importer) |
| `exception_tokens_in_fields` | 0 | Assets with exception tokens written into data fields (should be rare) |
| `serial_eq_service_tag` | 0 | Assets where serial_number == service_tag (old coalesce bug fingerprint) |
| `pp_prefix_ids` | 0 | Assets with PP- prefix IDs |
| `sy_prefix_ids` | 0 | Assets with SY- prefix IDs |
| `it_prefix_ids` | 0 | Assets with IT- / IT - prefix IDs (compatible workbook) |

## Proposed candidate asset set (conservative)

Primary rule: active assets with **legacy_asset_number set**, **purchased_by=unknown**, or known migration note/exception tokens.

**Candidate assets:** 0

- High confidence (delete candidates): **0**
- Review required (created near import window only): **0**

### High-confidence asset IDs (would delete)

_None_

## Dependent records for high-confidence assets

| Category | Count |
| --- | ---: |
| Computers | 0 |
| Asset assignments | 0 |
| Customer returns | 0 |
| IP assignment history rows | 0 |
| Distinct IP addresses referenced | 0 |

## Other IT import-like records

- Inventory items (unknown ownership / migration notes): **0**
- Software assignments (import/migration notes): **0**
- IT user accounts (migration_required / migration notes): **0**
- IT suppliers (all — do NOT auto-delete shared master): **0** — REVIEW
- Software catalog rows (all): **0** — REVIEW
- Software license pools (all): **0** — REVIEW

## High-confidence assets by created date

| Date | Count |
| --- | ---: |

## Non-IT baseline (must remain unchanged after cleanup)

- users: **14**
- customers: **9**
- projects: **24**
- teams: **3**
- departments: **6**
- timesheet_entries: **2**
- roles: **37**
- asset_types: **10**
- networks: **0**

## TOTAL RECORDS TO DELETE (proposed, high-confidence only)

| Category | Count |
| --- | ---: |
| Assets | 0 |
| Computers | 0 |
| Asset assignments | 0 |
| Customer returns | 0 |
| IP assignment history | 0 |
| Inventory items | 0 |
| Software assignments | 0 |
| IT account metadata | 0 |
| **TOTAL** | **0** |

_Note: 0 distinct IP address rows are referenced by assignment history. Cleanup should release/history-delete those links; do **not** delete Network definitions._

### Explicitly NOT deleted in this plan

- Users / employees / auth
- Customers / teams / departments / projects / timesheets / roles / permissions
- Asset types, networks, IT settings
- IT suppliers / software catalog / license pools (REVIEW REQUIRED — may be shared)
- Review-required assets: 0

## Analyze session cache (`uploads/it_migration`)

These JSON files are **staging only** (analyze). They are deleted on successful commit. Presence means analyze ran but commit either never happened or used a different session.

Session files on disk: **34**

### Source: `PP-Asset-Inventory.xlsx`

| Session ID | Source type | Staged rows | Batch ID | Analyzed at |
| --- | --- | ---: | --- | --- |
| `07f19469-b396-488f-859e-81fd60da8889` | `inventory` | 546 | `` | 2026-08-20T11:08:33.123182Z |
| `34420291-4f00-434f-8f4a-90e125af483a` | `consumables` | 151 | `5a83a591-bf04-4f74-bace-6259a3f095b6` | 2026-08-20T11:33:43.693905Z |
| `3a1ccba5-eed5-4d7d-8c61-b5caf239dee5` | `suppliers` | 151 | `c261cdc6-14b1-4040-8880-d262ddcef74a` | 2026-08-20T11:33:43.722169Z |
| `49a19f9b-fd4a-4b1f-937f-1de7737774f9` | `suppliers` | 151 | `` | 2026-08-20T11:07:41.752438Z |
| `6d1787a0-c330-4f9c-b2f0-34ae36eed510` | `suppliers` | 151 | `` | 2026-08-20T11:08:33.238713Z |
| `7efe0071-65f4-424c-b739-a1c0569e0fd7` | `inventory` | 546 | `` | 2026-08-20T11:07:41.658356Z |
| `cf821e32-5459-4883-abb1-3798c01f18d5` | `consumables` | 151 | `` | 2026-08-20T11:07:41.727127Z |
| `f992491e-d35f-4a35-b769-d0ae274e2670` | `inventory` | 546 | `38eb563e-d74c-44e3-9a47-7ffd13fc4e55` | 2026-08-20T11:33:43.616042Z |
| `fc2be9f9-b76c-4b1c-b7a4-649160b80e02` | `consumables` | 151 | `` | 2026-08-20T11:08:33.212966Z |

### Source: `PP-INF-FO-7_IT_RECORDS.xlsx`

| Session ID | Source type | Staged rows | Batch ID | Analyzed at |
| --- | --- | ---: | --- | --- |
| `13b343bf-b49a-4f28-bdd1-9518620a15c4` | `accounts` | 39 | `02d62004-4633-4369-8837-d3138f4a9051` | 2026-08-20T11:33:43.453297Z |
| `5dbb1c65-e7c3-4f8b-9ce1-00df4b982262` | `hardware` | 30 | `` | 2026-08-20T11:07:41.548581Z |
| `7d22fe7b-8fc3-4bb2-9b0b-8a8a829fcc89` | `software` | 26 | `` | 2026-08-20T11:07:41.602477Z |
| `7e25c790-cad8-49ec-bfb0-9f3bfc4836a5` | `hardware` | 30 | `` | 2026-08-20T11:08:33.009910Z |
| `861b973a-5121-4997-8cc7-3e98514e2807` | `accounts` | 39 | `` | 2026-08-20T11:08:33.038500Z |
| `956ff73e-ccc3-4d9e-9116-76e30fa4afdc` | `hardware` | 30 | `dfd1f3ce-f44b-471f-b5ec-6b0d1b4b8ab3` | 2026-08-20T11:33:43.421166Z |
| `aa3b68ef-06d1-4f58-ab4c-78d42b237ea1` | `accounts` | 39 | `` | 2026-08-20T11:07:41.579725Z |
| `baa77486-ec80-4047-bea9-28ea28454d01` | `software` | 26 | `5577c8e7-529d-4d0e-baac-6ac08ba51f42` | 2026-08-20T11:33:43.476975Z |
| `d3daab8a-a2b2-4179-bf3a-348c48551ef6` | `software` | 26 | `` | 2026-08-20T11:08:33.063374Z |

### Source: `PP-ProTrack_IT_Import_Compatible.xlsx`

| Session ID | Source type | Staged rows | Batch ID | Analyzed at |
| --- | --- | ---: | --- | --- |
| `2daa798e-7836-4bc0-b9c3-8900265e9e0e` | `hardware` | 3 | `4c239233-5467-4b76-bc7a-031517aaf31a` | 2026-08-20T11:33:11.875566Z |
| `9f8a2381-7015-4bf2-87b6-a0aab70c5154` | `hardware` | 3 | `cc23c0ab-33e2-4659-9cf4-b02e73ff9d06` | 2026-08-20T11:34:07.025959Z |

### Source: `hardware.xlsx`

| Session ID | Source type | Staged rows | Batch ID | Analyzed at |
| --- | --- | ---: | --- | --- |
| `0b7ffd59-2f7c-4885-bdf7-9eee0ae8bbd4` | `hardware` | 2 | `` | 2026-08-20T11:06:34.717448Z |
| `2c3ffde1-448e-4338-8ab6-f149ce974b8c` | `hardware` | 2 | `` | 2026-08-20T10:24:53.799117Z |
| `2d1511c1-cae2-4cda-a3ef-10ebb465e308` | `hardware` | 2 | `ae844032-de8b-42c6-948c-70937f317b97` | 2026-08-20T11:33:10.871875Z |
| `374a9332-346b-44c8-8b4b-4de71bc26533` | `hardware` | 2 | `` | 2026-08-20T10:15:10.157215Z |
| `3d8a7cfe-1d3a-4796-b0dc-c889d534fc69` | `hardware` | 2 | `9074213a-9bdc-4e7a-a05f-3f1c0a1184c2` | 2026-08-20T11:34:05.013679Z |
| `46e47fc8-31f5-46a4-983b-99bfe71be4e2` | `hardware` | 2 | `e5a2fb0b-322a-4ad2-85e0-4e151affddef` | 2026-08-20T11:34:06.055362Z |
| `6532c91b-193c-4c8f-9e38-5e6259984158` | `hardware` | 2 | `65cf4730-2020-461a-a949-e27bf587656b` | 2026-08-20T11:33:09.826202Z |
| `74d738c8-08c2-4e3c-baf0-12c0104a7eb5` | `hardware` | 2 | `` | 2026-08-20T10:15:45.350796Z |
| `791363d8-45d4-470a-8ff7-3e7b39ebaeee` | `hardware` | 2 | `` | 2026-08-20T11:06:33.631536Z |
| `7a1ad114-441d-4b80-a4a7-c6ff5dad4f93` | `hardware` | 2 | `` | 2026-08-20T10:15:46.426007Z |
| `8dd87130-2d06-4e15-bbd7-578a0a634670` | `hardware` | 2 | `` | 2026-08-20T11:08:26.982318Z |
| `9c92c86d-b0cd-4d1c-aa86-8216887216b1` | `hardware` | 2 | `` | 2026-08-20T10:24:54.871439Z |
| `bb6c6d09-d3f6-48f7-a950-7f74a41f29c9` | `hardware` | 2 | `` | 2026-08-20T10:15:11.284524Z |
| `ea84e4f0-2508-40b4-954c-e0b5b67565d9` | `hardware` | 2 | `` | 2026-08-20T11:08:28.034305Z |

Optional non-DB cleanup (safe, does not touch ProTrack entities): delete these session JSON files after confirmation.

## Identification notes

1. There is **no durable `import_batch_id` on asset rows**. Session `batch_id` exists only in analyze JSON / activity payloads and is not FK-linked to assets.
2. Importer always sets `legacy_asset_number` on committed hardware/inventory assets — this is the strongest durable marker for imported assets.
3. In this database: **zero** `it_migration_imported` activities and **zero** asset/inventory rows — historic imports appear to have been **analyze-only**, not committed.
4. Do **not** execute DB cleanup until this dry-run scope is confirmed (and until the correct environment DB is identified if imports live elsewhere).

---

**Next step:** Confirm whether this is the correct database. If yes, DB delete scope is empty; only session-cache cleanup may apply. If imports exist on another DB/host, re-run this dry-run there before any delete.