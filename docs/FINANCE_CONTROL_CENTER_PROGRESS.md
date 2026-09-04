# Finance Control Center — Progress

Date: 2026-09-04

## Delivered

### Phase 1 — P&L vs cash foundation
- FY MoM turnover (invoice date) + average monthly billing (zeros count)
- Overview `FinanceFyTurnoverSection`

### Phase 2 — Treasury registers
- Loans / OD / investments / cash position (manual)
- Principal ≠ P&L; interest = finance cost

### Phase 3 — Cash control + monthly P&L
- Cash-flow forecast + runway
- Monthly P&L + drill-down
- CapEx ↔ IT `asset_id`

### Phase 4 — Smart invoice PDF import
- Extract → review → confirm (never auto-saves)
- `POST /finance/invoices/pdf/extract` + `.../confirm`
- Parser with confidence / needs_review; no invented dates
- Customer + quote matching suggestions
- Duplicate detection (invoice # in notes / amount+date)
- Optional original PDF stored on `DocumentAsset` (`entity_type=quote`)
- UI: Projects & revenue **Import Invoice PDF** + cash ledger **Import PDF**
- Manual Add invoice remains
- OCR for scanned PDFs: deferred (clear message; text PDF only for now)
- Tests: `tests/test_finance_invoice_pdf_import.py` (5 passed)

## Still open
- Phase 4b: OCR for scanned invoices
- Phase 5: Full business scenarios + financial health indicators
- Quote PDF review-before-save (quote import still auto-saves today)
- Receivables aging report
