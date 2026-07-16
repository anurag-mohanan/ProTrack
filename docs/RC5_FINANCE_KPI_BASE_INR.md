# RC5 — Finance entry KPI base-INR (FX) correctness

**Status:** CTO-approved Phase K — shipped to UAT  
**Date:** 2026-07-16  
**Stakeholders:** Head of Engineering · Head of Sales · CEO · President · Creative Head · CTO  

---

## 1. Problem (UAT)

**Revenue / quotes → Booked revenue Σ** shows e.g. **53,075 INR** while quotes are entered in **USD** (and mixed currencies). The Phase J KPI strip **sums native `quoted_revenue` and labels the total as INR** — no FX conversion.

Same class of bug on **Expenses** KPI strips (Prosohm / customer Σ).

Company rule ([RC5_FINANCE_CUSTOMER_CURRENCY_FX.md](./RC5_FINANCE_CUSTOMER_CURRENCY_FX.md)): Overview and any **base-INR KPI** must sum stored **`base_*_inr`**, never live-reconvert or sum source amounts.

---

## 2. Brainstorm lock

| Stakeholder | Verdict |
|-------------|---------|
| **Head of Sales** | Booked revenue must match Overview / Annual Plan (base INR). Row lines still show native currency. |
| **Head of Engineering** | Expose `base_quoted_revenue_inr` on quote list; frontend KPIs sum base fields only. |
| **Creative Head** | KPI subtitle: “Base INR · FX at quote/purchase”; chip when mixed currencies present. |
| **CEO / President** | One number language across cockpit — always base INR for Σ cards. |
| **CTO** | No FX formula change; use existing `to_base_amount` snapshots; regression on quote USD + expense paths. |

---

## 3. CTO-approved scope

| # | Change |
|---|--------|
| K1 | `QuoteRead` (+ list) expose `base_quoted_revenue_inr` (from current revision) |
| K2 | Quotes panel KPI sums `base_quoted_revenue_inr`; UX copy for base INR |
| K3 | Expenses panel KPI sums `base_amount_inr` |
| K4 | Test: USD quote list returns converted base; KPI fields present |
| K5 | Dist + restart → UAT |

**Out of scope:** Rewriting historical FX; changing Overview dashboard math (already uses `base_quoted_revenue_inr`).

---

## 4. Pipeline

1. Dev → 2. CTO → 3. ST → 4. Regression → 5. QC → 6. Restart → **UAT**

### Shipped (2026-07-16)

| Gate | Result |
|------|--------|
| K1–K3 | Quote list exposes `base_quoted_revenue_inr`; Quotes + Expenses KPIs sum base INR |
| Regression | `test_finance_kpi_base_inr` + finance suite — **39 passed** |
| Dist / restart | `frontend/dist` OK · API `:8000` · Vite `:5173` |

---

## Related

- [RC5_FINANCE_CUSTOMER_CURRENCY_FX.md](./RC5_FINANCE_CUSTOMER_CURRENCY_FX.md)  
- [RC5_FINANCE_ENTRY_TABS_COCKPIT.md](./RC5_FINANCE_ENTRY_TABS_COCKPIT.md)  
