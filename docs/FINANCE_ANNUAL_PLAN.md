# Finance Annual Plan (Excel Reference)

**Status:** Implemented (Sales + Expenses + computed P&L)  
**Data entry:** Manual only — no workbook/CSV import on this tab

## Where to open

Business Modules → **Financial Planning** → tab **Annual Plan**

## How to use (current FY from April)

1. Click **Create Plan** (defaults to the FY that started this April, e.g. July 2026 → FY **2026-27**).
2. Confirm tax % / provision % if needed, then Create.
3. Type monthly amounts into the **Sales** and **Expenses** grids (Apr–Mar). Values save when you leave a cell.
4. Read the **Summary** card for Gain/Loss, after tax, and provision.

Row labels are pre-seeded from the old Excel (ABC-mold, Sybridge, Wages, etc.) so you can fill them by hand; you do not import the old file.

## Mapping to legacy workbook

| Excel section | This release |
|---------------|--------------|
| Sales (monthly Apr–Mar streams) | Editable Sales grid (seeded ABC-mold, ABC-programming, Lanko-mold, Sybridge) |
| Expenses (monthly) | Editable Expenses grid (Capex depreciation, Wages, NX Mach 3/2, Overhead) |
| Tax / provision | Plan settings (default 30% / 20%) |
| GAIN/LOSS summary | Computed Summary card |
| Resources (headcount/hours) | Out of scope — next slice |
| CAPEX asset register | Out of scope — depreciation is a manual expense line for now |
| Commission / NP fund | Out of scope |
| Import old Excel | Not in this release — manual entry only |

## API

- `GET/POST /api/v1/finance/plans`
- `GET/PATCH /api/v1/finance/plans/{id}`
- `POST/PUT/DELETE /api/v1/finance/plans/{id}/lines/...`

## Notes

- FY months: `month_01`=Apr … `month_12`=Mar
- Amounts display with Indian number grouping in the UI
- Creating a plan for an FY label that already exists returns 400
