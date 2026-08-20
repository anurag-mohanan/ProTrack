# docs/migration-sources/

Local working copies of Prosohm IT / inventory spreadsheets used for migration design.

## Split import package (preferred)

Use the sequential **IT Data Import** UI (`/it/data-import`) with files under `split/`:

| File | Import type | Canonical sheet |
| --- | --- | --- |
| `01_Assets.xlsx` | Assets | `Assets` (not `hardware`) |
| `02_Computers.xlsx` | Computers | `Computers` |
| `03_IP_Addresses.xlsx` | IP Addresses | `IP_Addresses` |
| `04_Inventory_Items.xlsx` | Inventory | `Inventory_Items` |
| `05_Software_Licenses.xlsx` | Software | `Software_Licenses` |
| `06_User_Accounts.xlsx` | User Accounts | `User_Accounts` |
| `07_Suppliers.xlsx` | Suppliers | `Suppliers` |
| `08_Migration_Exceptions.xlsx` | Review only | `Migration_Exceptions` |

Workflow: select type → upload → inspect → preview (first 10) → confirm → commit. Do not auto-run the next file.

## Source of truth (OneDrive)


1. `PP-Asset-Inventory.xlsx`  
   `…\Prosohm Admin's files - Administration_OD\Infrastructure\PP-Asset-Inventory.xlsx`

2. `PP-INF-FO-7_IT_RECORDS.xlsx`  
   `…\Prosohm Admin's files - Administration_OD\Master Documents\Infrastructue\RECORDS\PP-INF-FO-7_IT_RECORDS.xlsx`  
   (folder name spelling: **Infrastructue**)

## Security

`PP-INF-FO-7_IT_RECORDS.xlsx` contains **plaintext passwords** and TeamViewer credentials.

- Do **not** commit `.xlsx` files from this folder to git (ignored).
- Do **not** paste password cells into tickets, chat, or docs.
- Import pipeline must exclude all password / TeamViewer / product-key secret columns.

## Analyzer scripts

- `_analyze_sources.py` / `_analyze_sources2.py` — local inspection only; they redact sensitive columns in printed samples.
