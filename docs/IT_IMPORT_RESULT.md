# IT Import Result

> Last automated smoke analyze: 2026-08-20 (preview only — no production commit from this agent run)

## Original source files analyzed successfully

| Source file | Section | Records read | Notes |
|-------------|---------|--------------|-------|
| `PP-INF-FO-7_IT_RECORDS.xlsx` | hardware | 30 | IDs preserved (`PP-SVR-01`, `SY-IT031`, …); ownership unknown (no Purchased By column); secrets excluded |
| `PP-INF-FO-7_IT_RECORDS.xlsx` | accounts | 39 | Passwords excluded; metadata only |
| `PP-INF-FO-7_IT_RECORDS.xlsx` | software | 26 | Uses `PURCHASED BY` |
| `PP-Asset-Inventory.xlsx` | inventory | 546 rows scanned | `IT - 001` preserved exactly; `CUST PAID` drives ownership when present |
| `PP-Asset-Inventory.xlsx` | consumables | 151 / ~10 named | Empty shells skipped on import |
| `PP-Asset-Inventory.xlsx` | suppliers | 0 | Sheet empty — expected |

## Fidelity checks (analyze)

- No `EX-HAR-…` / `OWNERSHIP_UNCLEAR` / `SERIAL_MISSING` in mapped asset number or serial fields
- Validation codes appear only in the exceptions list
- Windows license / TeamViewer / password columns excluded

## Production commit

Run Analyze → review mapped preview → Confirm import in IT Settings when ready.  
Each successful commit overwrites this report with live counts.
