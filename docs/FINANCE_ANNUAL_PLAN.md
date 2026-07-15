# Finance Annual Plan (Excel Reference)

**Status:** Implemented — **quarterly edit surface** (Q1–Q4) with month storage underneath  
**Data entry:** Manual quarterly cells + **Sync software renewals** — no workbook/CSV import on this tab

## Where to open

Business Modules → **Financial Planning** → tab **Annual Plan**

## How to use (current FY from April)

1. Click **Create Plan** (defaults to the FY that started this April, e.g. July 2026 → FY **2026-27**).
2. Confirm tax % / provision % if needed, then Create.
3. Type **quarterly** amounts into the **Sales** and **Expenses** grids (Q1 Apr–Jun … Q4 Jan–Mar). Values save when you leave a cell (stored as an even split across the three months).
4. Optionally click **Sync software renewals** to pull known `Expense.next_renewal_date` amounts into expense lines for the correct quarter.
5. Read the **Summary** card for Gain/Loss, after tax, and provision.

Row labels are pre-seeded from the old Excel (ABC-mold, Sybridge, Wages, etc.).

## Mapping to legacy workbook

| Excel section | This release |
|---------------|--------------|
| Sales (monthly Apr–Mar streams) | Editable Sales grid as **4 quarters** (months kept in DB) |
| Expenses (monthly) | Editable Expenses grid as **4 quarters** + renewals sync |
| Tax / provision | Plan settings (default 30% / 20%) |
| GAIN/LOSS summary | Computed Summary card |
| Resources / CAPEX register | Out of scope as before |

## API

- `GET/POST /api/v1/finance/plans`
- `GET/PATCH /api/v1/finance/plans/{id}`
- `POST/PUT/DELETE /api/v1/finance/plans/{id}/lines/...` (accepts `q1`–`q4` and/or `month_01`–`month_12`)
- `POST /api/v1/finance/plans/{id}/sync-renewals`

## Notes

- FY months still in DB: `month_01`=Apr … `month_12`=Mar
- API/UI primary edit fields: `q1`–`q4`
