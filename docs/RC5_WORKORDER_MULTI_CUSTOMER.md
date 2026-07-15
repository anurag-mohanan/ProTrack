# RC5 — Multi-customer workorder import (PDF + Excel)

## Ops / Engineering lock

| Field | Required? | Notes |
|-------|-----------|--------|
| **Part description** | **Yes — priority** | CMT `Part Description`, ABC `PART NAME`, B&B `Part Name` |
| Work order number | **Not required** | Optional if present; UI labels it optional |
| Press tonnage | If present | e.g. `2200T Press 308`, `Press Tonnage Primary \| 500T` |
| Plastic material | If present | ABC resin line; B&B `Plastic Type (Main)` |
| Cavity count | If present | `1+1 Cavity` → 2; `# Cav.: 4`; `Cavitation \| One` → 1 |
| Tool type | If present | B&B `Tool Type` |
| Customer specs | Catch-all | Tool #, program, shrink, notes |

**Accepted files:** `.pdf`, `.xlsx`, `.xlsm`  
**Save model:** extract → review form → user Save (no silent DB write)

## Sample formats audited

1. CMT Intermediate Design Review PDF — spaced labels, cavity in part description, tonnage in General Notes  
2. ABC Shop Order PDF — `PART NAME`, `# Cav.`, `MAT'L/... RESIN -`  
3. B&B Outsource Kick Off Excel — label/value column pairs  

Customer files are **not** committed; unit tests use synthetic text/Excel mirroring those layouts.

## Implementation

| Area | Change |
|------|--------|
| `app/services/workorder_pdf_extract.py` | PDF + Excel extract; CMT/ABC/B&B heuristics; part-first |
| `POST /projects/{id}/workorder-pdf/extract` | Accepts pdf/xlsx/xlsm |
| Overview panel | **Import workorder**; Accept PDF+Excel; WO optional label |
| Tests | `tests/test_workorder_pdf_extract.py` |

## Pipeline checklist

### Senior developer (approve before Testing)

- [ ] Part description preferred over WO number in code paths and UI copy  
- [ ] Excel path uses openpyxl; clear error if missing on API host  
- [ ] No silent save — extract only suggestions  
- [ ] Unit tests green for CMT/ABC/B&B fixture styles  

### Testing team → Testing lead

- [ ] CMT-style PDF: part description cleaned of `N+N Cavity`; cavity numeric; press from notes  
- [ ] ABC-style PDF: PART NAME, cavity, resin grade  
- [ ] B&B-style xlsx: Part Name, tool type, cavitation word→number, plastic, primary tonnage  
- [ ] Invalid extension rejected; empty/corrupt file shows usable error  
- [ ] Review → Cancel leaves project unchanged; Save persists  

### QC final audit before UAT

- [ ] Docs match UI strings (Import workorder, optional WO)  
- [ ] Staging API has `pdfplumber`/`pypdf`/`openpyxl` (or stdlib PDF scrape still works)  
- [ ] No customer source PDFs/XLSX in the git tree  

## UAT prompt ideas

1. Import each customer sample on a sandbox project; confirm Part description is filled correctly.  
2. Confirm missing WO number does **not** block Save.  
3. Confirm you can edit any autofilled field before Save.
