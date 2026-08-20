# docs/migration-sources/

Local working copies of Prosohm IT / inventory spreadsheets used for migration design.

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
