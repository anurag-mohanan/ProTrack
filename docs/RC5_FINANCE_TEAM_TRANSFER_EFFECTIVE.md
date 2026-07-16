# RC5 — Dated team transfer (resource move with effective-from)

**Status:** Shipped — Phase M (UAT ready)  
**Date:** 2026-07-16  
**Stakeholders:** Head of Engineering · Head of Sales · CEO · President · Creative Head · CTO  

---

## 1. Problem

Moving someone (e.g. Sarath Babu K) from **Prosohm Eng → Redoe** today flips primary membership instantly. Finance then attributes the **entire** month’s salary to the new team. Needed: **effective from date** so costs count on the old team up to that date and on the new team from that date.

Example: effective **2026-07-20** (July = 31 days):

| Team | Days | Salary factor |
|------|------|---------------|
| Prosohm Eng | 1–19 | 19/31 |
| Redoe | 20–31 | 12/31 |

---

## 2. Brainstorm lock

| Stakeholder | Verdict |
|-------------|---------|
| **Head of Engineering** | Archive closed primary windows; live `team_members` stays current; salary uses history ∩ employment. |
| **Head of Sales** | Retainer N = point-in-time `as_of` (v1) — no fractional fee split. |
| **CEO / President** | Explicit **Move resource** action with date — not silent primary checkbox. |
| **Creative Head** | Modern dialog on Teams members panel (target team + effective from). |
| **CTO** | New `team_membership_periods` history; enhance `POST …/transfer`; reuse calendar-day proration. |

### Rules

```text
Last day on source team = effective_from − 1 (inclusive)
First day on target team = effective_from (inclusive)
Salary factor = days on team ∩ employment ∩ calendar month ÷ days_in_month
Retainer N (v1) = membership open on as_of with is_billable_headcount
```

---

## 3. CTO-approved scope

| # | Change |
|---|--------|
| M1 | `team_membership_periods` + `TeamMember.effective_from` (phase36) |
| M2 | Dated `transfer_member` + archive periods; sync `User.team_id` |
| M3 | Team salary attribution via period factors |
| M4 | Teams UI — Move resource dialog |
| M5 | Tests + dist + restart → UAT |

**Out of scope:** Fractional retainer fee mid-month; timesheet project reassignment.

---

## 4. Pipeline

1. Dev → 2. CTO → 3. ST → 4. Regression → 5. QC → 6. Restart → **UAT**

---

## Related

- [RC5_FINANCE_MANAGEMENT_TEAM_LAST_DAY.md](./RC5_FINANCE_MANAGEMENT_TEAM_LAST_DAY.md) (employment day proration)  
