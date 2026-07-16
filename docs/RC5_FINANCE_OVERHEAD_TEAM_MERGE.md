# RC5 — Merge Corporate / Shared Services + Management into one overhead team

**Status:** CTO-approved Phase L — shipped to UAT  
**Date:** 2026-07-16  
**Stakeholders:** Head of Engineering · Head of Sales · CEO · President · Creative Head · CTO  

---

## 1. Problem

Two overhead homes (**Corporate / Shared Services** for facilities OpEx + **Management** for leadership salaries) force duplicate team pickers, split KPIs, and ongoing dual maintenance. Leadership wants the merge **now**, before deeper FP&A work.

Supersedes the two-team lock in [RC5_FINANCE_MANAGEMENT_TEAM_LAST_DAY.md](./RC5_FINANCE_MANAGEMENT_TEAM_LAST_DAY.md) § Corporate team remains separate.

---

## 2. Brainstorm lock

| Stakeholder | Verdict |
|-------------|---------|
| **CEO / President** | One HQ home for people + shared OpEx — stop choosing between Management vs Corporate. |
| **Head of Engineering** | Migrate FKs once (expenses, members, users, commercial, quotes/projects); soft-deactivate legacy **Management**. |
| **Head of Sales** | Delivery teams unchanged; retainer N still excludes the single overhead home. |
| **Creative Head** | Overheads UI: one team chip, “Overhead salaries” KPI, no dual team dropdown. |
| **CTO** | Canonical name **`Corporate / Management`**; pool math unchanged (salary + Prosohm OpEx ÷ delivery FTE). |

### Canonical model

```text
Team: Corporate / Management   (single overhead home)
  ← people (Design Leader, EM, OA, Admin, …)
  ← facilities / shared OpEx (rent, utilities, licenses…)
Pool = salaries on this team + Prosohm OpEx on this team
CPR  = pool ÷ delivery billable FTE (excludes this team)
```

Legacy names (migrate then deactivate/rename):
- `Corporate / Shared Services` → rename to canonical
- `Management` → reassign FKs → `is_active=False`

---

## 3. CTO-approved scope

| # | Change |
|---|--------|
| L1 | Phase35 merge + rename; update phase23/33 helpers |
| L2 | Dashboard overhead payload: one team id (mgmt id = corp id for compat) |
| L3 | Overheads / Teams / Users UI copy + remove dual picker |
| L4 | Regression + dist + restart → UAT |

**Out of scope:** Changing CPR formula; deleting historical expense rows.

---

## 4. Pipeline

1. Dev → 2. CTO → 3. ST → 4. Regression → 5. QC → 6. Restart → **UAT**

### Shipped (2026-07-16)

| Gate | Result |
|------|--------|
| L1–L3 | Phase35 merge; unified `Corporate / Management`; Overheads UI single home |
| Regression | `test_overhead_team_merge` + finance suite — **46 passed** (merge slice) |
| Dist / restart | `frontend/dist` OK · API `:8000` · Vite `:5173` |

---

## Related

- [RC5_FINANCE_MANAGEMENT_TEAM_LAST_DAY.md](./RC5_FINANCE_MANAGEMENT_TEAM_LAST_DAY.md) (superseded on team split)  
- [RC5_FINANCE_OVERHEADS_COCKPIT_UX.md](./RC5_FINANCE_OVERHEADS_COCKPIT_UX.md)  
