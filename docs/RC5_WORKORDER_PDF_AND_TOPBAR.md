# RC5 — Top-bar project title + workorder PDF autofill

## Ops + Engineering Manager brainstorm → Senior decision

### Problems
1. Top bar showed `Project 106cdb81…` (truncated UUID) with role underneath — not the tool identity.
2. Workorder details needed manual entry; customers send **PDF workorders in different layouts**.

### Ideas → locked

| Idea | Verdict |
|------|---------|
| Keep UUID crumb | Rejected |
| Show **tool number · part description** in top bar / breadcrumbs | **Locked** |
| Full per-customer PDF template engine in RC5 | Parked |
| OCR for scanned PDFs | Parked |
| **Heuristic text (+ table cell) extract → fill form → user Saves** | **Locked** |
| Extract must not auto-write DB without review | **Locked** |

## Senior-approved code

| File | Change |
|------|--------|
| `frontend/.../AppBreadcrumbs.tsx` | Resolve project title from command-center cache |
| `frontend/.../AppTopBar.tsx` | Ellipsis long titles |
| `app/services/workorder_pdf_extract.py` | pdfplumber text + label heuristics |
| `app/api/v1/projects.py` | `POST /{id}/workorder-pdf/extract` |
| `frontend/.../ProjectWorkorderDetailsPanel.tsx` | Import PDF button → edit → Save |
| `tests/test_workorder_pdf_extract.py` | Heuristic unit tests |

## Testing checklist

| # | Check | Pass |
|---|--------|------|
| 1 | Restart API + hard refresh | |
| 2 | Open project workspace: top bar shows `2649 · Frt Door…` (not UUID) | |
| 3 | Role chip under title still shows (e.g. Engineering Manager) | |
| 4 | Overview → **Import workorder PDF** on a text PDF with WO / tonnage / material labels | |
| 5 | Fields autofill into edit form; Save persists | |
| 6 | Scanned/image-only PDF shows clear error (no text) | |
| 7 | Non-editors do not see Import / Edit | |

## Testing lead → QC

- [ ] Smoke top-bar title on project 2649  
- [ ] Smoke PDF import with one real/sample customer WO PDF  
- [ ] Sign-off → user testing  
