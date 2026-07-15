# RC5 — Top-bar project title + workorder PDF autofill

> **Superseded for import formats:** see [RC5_WORKORDER_MULTI_CUSTOMER.md](./RC5_WORKORDER_MULTI_CUSTOMER.md)
> (PDF + Excel, Part description priority, WO number optional, CMT/ABC/B&B heuristics).

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
| 4a | If toast says pdfplumber missing: on **API host** `pip install -r requirements.txt` then restart API | |
| 5 | Fields autofill into edit form; Save persists | |
| 6 | Scanned/image-only PDF shows clear error (no text) | |
| 7 | Non-editors do not see Import / Edit | |

## Staging note (`192.168.20.254`)

The toast appears when the **API host Python** lacks PDF packages (local conda may have them while IIS/service Python does not).

1. Deploy latest backend code (includes stdlib fallback so many text PDFs work even without packages).
2. On the API host, from the deploy folder: `.\scripts\install_pdf_deps.ps1`
3. Restart API / app pool
4. Retry Import workorder PDF
