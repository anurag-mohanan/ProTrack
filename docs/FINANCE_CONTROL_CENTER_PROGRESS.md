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

### Phase 5 — Scenarios + financial health
- What-if engine (`schema_version` 4): opening cash, collections realization, loan EMI, OD interest, investment income, CapEx cash → ending cash / scenario runway + warnings
- Live health strip: `GET /finance/health` composing runway, collections vs turnover, receivables, debt/OD, liquidity
- UI: `FinanceHealthStrip` on Overview + Scenarios; cash section in `FinanceWhatIfPanel`
- Planning payloads preserve `schema_version` ≥ 2 and optional `what_if` (no longer force v2)
- What-if seeds from Treasury cash + active EMI when draft has no saved what-if
- Tests: `tests/test_finance_phase5_health_scenarios.py`

## Still open
- Phase 4b: OCR for scanned invoices
- Quote PDF review-before-save (quote import still auto-saves today)
- Receivables aging report (detail beyond health strip)
- Optional: wire expansion CPR scenarios more tightly to what-if cash case presets
