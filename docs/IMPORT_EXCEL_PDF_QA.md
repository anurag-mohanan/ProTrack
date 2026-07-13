# Excel + PDF Import Defaults — QA / QC / UAT Gate

**Last updated:** 2026-07-13  
**QC decision:** Conditional Internal UAT **GO**

## Scope delivered

- Default formats for live data imports: **Excel (.xlsx / .xlsm)** and **PDF (tabular)**
- CSV retained where already supported (quotes, row timesheet API)
- Legacy **.xls** rejected on quote import (convert to .xlsx)
- Shared policy: `app/services/import_file_formats.py`
- PDF table extract → Excel: `app/services/pdf_table_import.py` (`pdfplumber`)
- Frontend accept/labels: `frontend/src/config/importFormats.ts`

## Surfaces updated

| Surface | Path | Formats |
|---------|------|---------|
| Historical Projects | Admin → Imports → Historical Projects | Excel + PDF |
| Master Historical Timesheets | Admin → Imports → Historical Timesheets | Excel + PDF |
| Quote import | Business Modules → Financial Planning → Import Quote | Excel + PDF + CSV |
| Row timesheet API | `/api/v1/imports/historical-timesheets/upload` | Excel + PDF + CSV |
| Folder timesheet API | `/folder/upload` | Excel + PDF (+ xlsm) |

## Testing

### Level 1 — Senior tester
- Shared formats, PDF conversion, quote PDF, `.xls` reject: **PASS**
- Folder nested PDF path preservation: **fixed** after review (`Designer/file.pdf` → `Designer/file.xlsx`)

### Level 2 — Regression
- Logo upload remains image-only: **PASS**
- Quote CSV still works: **PASS**
- Unsupported type → HTTP 400: **PASS**
- Coming-soon bulk imports remain stubs: **PASS**
- Automated: `tests/test_import_file_formats.py` + historical/master/folder + EBMP finance suites green
- Residual: `test_duplicate_week_skip` fails independently of this change (pre-existing skip behavior); do not treat as format regression

## Known limits (UAT rules)

- PDF must be **text-based** with a clear **header row** table (no OCR / scanned images)
- First usable table in the PDF is imported (wrong layout → validation errors or wrong mapping)
- Multi-sheet Excel fidelity is **not** reconstructed from PDF
- Coming-soon Users/Customers bulk import stubs unchanged

## Manual UAT smoke

1. Historical Projects: upload `.xlsx` and a 1-table `.pdf` with matching headers  
2. Historical Timesheets (master): Excel + PDF  
3. Financial Planning → Import Quote: Excel + PDF + CSV  
4. Bad PDF (no table) → clear error  
5. Quote `.xls` → clear convert-to-xlsx message  

## Deploy note

Rebuild `frontend/dist` after this change and publish to `192.168.20.254` so other PCs see the new accept/help text. Backend on that host must also have `pdfplumber` installed and restarted.
