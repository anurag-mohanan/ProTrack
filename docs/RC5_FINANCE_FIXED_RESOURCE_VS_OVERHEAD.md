# RC5 — Fixed resource vs Prosohm overhead headcount (role-aware)

## Problem (UAT)

Teams list **Members** (e.g. 10 / 6 / 2) includes Office Administrator, Planning Board, Design Leader, Engineering Manager, etc. Those people were treated like customer-paid **fixed resources** for retainer / commercial planning. They must be **Prosohm overhead** — company-paid — while only **delivery engineers** drive customer fixed / retainer resource cost.

## HOD lock

| Class | Roles (default) | Commercial |
|-------|-----------------|------------|
| **Fixed resource (customer)** | Senior Designer, Designer, Junior Designer, Surfacer | `is_billable_headcount=true` on delivery teams → retainer rate × N; salary in delivery-team operating cost when primary |
| **Overhead (Prosohm)** | Admin, Office Administrator, Planning Board, Design Leader, Engineering Manager, HR, Read Only (+ legacy Project Manager) | `is_billable_headcount=false`; excluded from customer fee N; excluded from delivery-team salary rollup |
| **Corporate / Shared Services** | All members | Always non-billable; strategy **overheads**; fee 0 |

Admin may still toggle Billable per membership for an edge case on a **designer**; management/overhead roles are **forced non-billable on API restart** (phase31). Prefer primary team = Corporate for pure managers.

## Where developed

| Area | Path |
|------|------|
| Role rules | `app/core/fixed_resource_eligibility.py` |
| Backfill | `app/db/phase31_overhead_role_billable_backfill.py` (+ `main.py` startup) |
| Add-member defaults | `app/crud/team.py`, `app/services/user_team_service.py` |
| Retainer N | `billable_salary_headcount` (unchanged gate; data corrected) |
| Delivery salary | `dashboard_service._user_ids_for_team` — primary ∩ billable on delivery teams |
| Teams API | `TeamRead.billable_member_count` |
| UI | `TeamsPage` — **Billable / Members** column; role-aware checkbox defaults |

## Pipeline

```mermaid
flowchart LR
  Dev[Development] --> ST1[Senior_Tester_verify]
  ST1 --> Test[Testing_team_debug]
  Test --> ST2[Senior_Tester_approve]
  ST2 --> QC[QC_final_audit]
  QC --> UAT[UAT]
```

1. **Development** — this package; tests; deploy `app/` + `frontend/dist`; restart API (phase31) + frontend.  
2. **Senior Tester** — Teams Billable/Members; Sybridge retainer N; Design Leader off.  
3. **Testing** — debug real rosters.  
4. **Senior Tester** — re-approve.  
5. **QC** — docs ↔ UI ↔ fee math.  
6. **UAT** — Head of Finance / HOD.

### Senior Tester matrix

- [ ] Design Leader / EM / Planning Board / Office Admin on Sybridge → **not** in billable count / retainer N  
- [ ] Designer / Surfacer → **in** billable count when Billable on  
- [ ] Teams grid shows **billable / total** (e.g. `4 / 10`)  
- [ ] Corporate row billable = 0  
- [ ] Overview delivery team salary excludes non-billable primaries  
- [ ] Designer 403 finance write regression  

### Pre-UAT ops

Restart **backend** and **frontend** after deploy so phase31 backfill and Vite/`dist` pick up the UI.

## Related

- [RC5_FINANCE_MANAGEMENT_OVERHEAD.md](./RC5_FINANCE_MANAGEMENT_OVERHEAD.md)  
- [RC5_FINANCE_EDITABLE_FEE_MODELS.md](./RC5_FINANCE_EDITABLE_FEE_MODELS.md)  
- [RC5_SALARY_ELIGIBILITY.md](./RC5_SALARY_ELIGIBILITY.md)  
