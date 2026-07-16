# RC5 — Annual Plan Sales from awarded quotes

**Status:** CTO-approved Phase F — Internal UAT  
**Date:** 2026-07-16  
**Stakeholders:** Head of Finance · Head of Engineering · Head of Sales · CEO · President · CTO

---

## 1. What the Sales / Expenses grids do today

Annual Plan is a **fiscal-year workbook** (Indian Eng FY Apr–Mar).

| Section | Purpose | Why it looked “empty” |
|---------|---------|------------------------|
| **Sales** | Planned revenue by line × quarter (stored as even monthly split) | Seeded with legacy Excel labels (`ABC-mold`, …) at **0** — **manual entry only**; no link to Quotes |
| **Expenses** | Planned cost by line × quarter | Same zeros until user edits, **Seed wages & overhead**, or **Sync software renewals** |

**Re-seed wages & overhead** fills only expense codes `wages` and `overhead` from live people/overhead costs. It does **not** touch Sales.

---

## 2. Brainstorm lock

| Stakeholder | Verdict |
|-------------|---------|
| **Head of Finance** | Sales must reflect **awarded quote revenue** in the **FY quarter of the quoted date**, not static Excel labels. Manual override of cells remains allowed after sync. |
| **Head of Sales** | Every awarded quote needs a **Quoted date** so revenue lands in the correct quarter for pipeline → plan. |
| **Head of Engineering** | One sync action (like renewals); keep calc in services; no LLM. |
| **CEO / President** | Annual Plan Sales should not stay blank while Quotes already hold won revenue. |
| **CTO** | Add `quotes.quoted_date`; `POST …/sync-sales-from-quotes`; upsert sales lines per quote; skip quotes without a date (or outside FY). |

### Visual vs background

| Data | Visual? | Role |
|------|---------|------|
| Sales quarterly grid | **Yes** | Decision workbook — auto-filled from awards, still editable |
| Legacy ABC-/Lanko-/Sybridge seed rows | Background labels | Keep for manual planning; sync adds **Award:** lines from quotes |
| Quote amounts / FX INR | Background | Feed sync via current revision `base_quoted_revenue_inr` |
| Quoted date | **Yes** on Quotes form + list | Drives quarter placement |

---

## 3. CTO-approved scope

| # | Change |
|---|--------|
| F1 | Schema: `quotes.quoted_date` (nullable Date) + startup sync |
| F2 | Manual create / PATCH / import: accept & expose `quoted_date` (PDF `start_date` → quoted_date when missing) |
| F3 | `POST /finance/plans/{id}/sync-sales-from-quotes` — upsert sales lines `awarded_{quoteId}` into FY quarter of quoted date |
| F4 | UI: Quoted date on Quotes; **Sync sales from awarded quotes** on Annual Plan |
| F5 | Tests + dist rebuild + restart → UAT |

**Out of scope:** Bid/pipeline statuses; deleting legacy seed sales labels; auto-sync on every quote save (explicit button only).

---

## 4. Pipeline

1. Dev → 2. CTO approve → 3. Senior Tester → 4. Regression → 5. ST approve → 6. QC → 7. Restart → **UAT**

### ST matrix

- [x] Manual quote create/edit accepts Quoted date; list shows it  
- [x] Sync places INR revenue in Q1–Q4 matching quoted date within plan FY  
- [x] Quote outside FY or missing date does not corrupt other lines  
- [x] Seed wages & overhead / sync renewals / cell edit still work (annual plan + quote tests)  
- [x] Designer still forbidden from finance plans  

**QC:** Direction doc + implementation + tests green + `frontend/dist` rebuilt + Vite/API available for UAT.

---

## Related

- [FINANCE_ANNUAL_PLAN.md](./FINANCE_ANNUAL_PLAN.md)  
- [RC5_QUOTE_MANUAL_ENTRY.md](./RC5_QUOTE_MANUAL_ENTRY.md)  
- [RC5_FINANCE_AWARDED_QUOTE_IMPORT.md](./RC5_FINANCE_AWARDED_QUOTE_IMPORT.md)  
