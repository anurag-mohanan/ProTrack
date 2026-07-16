# RC5 — Overheads multi-entry category layout

**Status:** CTO-approved Phase H — Internal UAT  
**Date:** 2026-07-16  
**Stakeholders:** Head of Finance · Head of Engineering · Head of Sales · CEO · President · Creative Head · CTO  
**Supersedes (layout only):** single-amount placeholders in [RC5_FINANCE_OVERHEADS_COCKPIT_UX.md](./RC5_FINANCE_OVERHEADS_COCKPIT_UX.md)

---

## 1. Problem

Phase G showed **one amount field per cost centre** (e.g. one “Software licenses” box). Real HQ OpEx has **many lines per category**:

- Software licenses → NX Mach 3, NX Mach 2, AutoCAD, SolidWorks, …
- Rent → HQ lease, annex, parking  
- Utilities → power, water, diesel genset  

A 1:1 placeholder overwrites or hides siblings. Need a **category → many lines** layout.

---

## 2. Brainstorm lock

| Stakeholder | Verdict |
|-------------|---------|
| **Head of Finance** | Accordion (or section) **per cost centre**. Inside: table of named lines + **Add line**. Category header shows **line count + category total**. Pool/CPR math unchanged. |
| **Creative Head** | Keep cockpit chrome (hero, KPI strip, pool mix). Categories as expandable sections — scannable, not a wall of identical cards. |
| **Head of Engineering** | Still `POST/PATCH/DELETE /expenses` with `cost_centre_id`; no new tables. Match by centre id, never force one row per code. |
| **Head of Sales** | CPR stays prominent; detail stays on Overheads. |
| **CEO / President** | See which categories drive OpEx (totals) without opening every line. |
| **CTO** | UI-only Phase H; remove 1:1 draft overwrite behaviour. |

### Layout

```text
[Hero + KPI strip + Pool mix]
[Category: Software licenses · 4 lines · ₹…]  ▾
   | Name | Amount | Freq | Actions |
   | NX Mach 3 | … | yearly | Update Delete |
   | + Add line (name, amount, vendor?) |
[Category: Rent · …]
[Other OpEx]
[Custom form — advanced]
```

---

## 3. CTO-approved scope

| # | Change |
|---|--------|
| H1 | Category accordion with **multiple** expense rows per cost centre |
| H2 | Add / update / delete line within category |
| H3 | Category subtotal + count in header |
| H4 | Keep hero, KPIs, pool mix, custom escape hatch |
| H5 | Regression + dist rebuild + restart → UAT |

**Out of scope:** Changing CPR formula; DB seed of default expense rows; CapEx in pool.

---

## 4. Pipeline

1. Dev → 2. CTO → 3. Senior Tester → 4. Regression → 5. ST → 6. QC → 7. Restart → **UAT**

### ST matrix

- [x] Two+ software license lines can coexist under SW_LICENSES  
- [x] Category total = sum of lines; pool/CPR refresh after save  
- [x] Update/Delete per line; Add line with distinct name  
- [x] Empty category still shows Add line  
- [x] Existing overhead dashboard / P&L tests green  

**QC:** Multi-entry accordion layout + tests + `frontend/dist` + API/Vite restart for UAT.

---

## Related

- [RC5_FINANCE_OVERHEADS_COCKPIT_UX.md](./RC5_FINANCE_OVERHEADS_COCKPIT_UX.md)  
- [RC5_FINANCE_MANAGEMENT_TEAM_LAST_DAY.md](./RC5_FINANCE_MANAGEMENT_TEAM_LAST_DAY.md)  
