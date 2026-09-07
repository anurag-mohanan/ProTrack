# Connected ProTrack — Progress

Date: 2026-09-07

## Wave 1 — Finance closeout
| Item | Status |
|------|--------|
| FY switcher (`fy_start_year`) | Done |
| Business position strip | Done |
| Receivables aging | Done + tests |
| CapEx `asset_id` picker | Done + tests |
| Quote PDF extract→review→confirm | Done + tests |
| Dead-control audit | Partial (PDF batch rejects; further UI audit ongoing) |

## Wave 2 — IT Software SoT
| Item | Status |
|------|--------|
| Catalog / pools / assignments / requirements / expiry | Done |
| Dashboard KPIs | Done |
| `manage_it_software` enforcement | Done |

## Wave 3 — Shifts in Resource Planning
| Item | Status |
|------|--------|
| Shift master + assignments + `get_employee_shift` | Done (API/service/tests) |
| RP UI Shifts tab | Done (`ResourcePlanningShiftsPanel`) |
| Capacity integration | Partial (`shift_hours_for_range` ready) |

## Wave 4 — RP ↔ IT gaps / matrix
| Item | Status |
|------|--------|
| Gap + matrix services/APIs | Done |
| RP IT readiness UI | Done (`ResourcePlanningItReadinessPanel`) |

## Wave 5 — Cross-module + OCR
| Item | Status |
|------|--------|
| Hire → Finance impact | Done (`GET /finance/hire-impact`) |
| Profile enrichment (read SoT) | Partial (gap service snapshot) |
| Optional OCR (`pytesseract`) | Soft-dep helper wired into invoice/quote PDF |

## IT master data (parallel)
| Item | Status |
|------|--------|
| Cascading Category→Type→Make→Model | Done |
| Highest+1 asset numbers | Done |
| Deactivate / merge / list filters / bulk next-N | In progress |

## Tests
- `tests/test_finance_wave1_closeout.py`
- `tests/test_finance_quote_pdf_import.py`
- `tests/test_it_master_data_numbering.py`
