# RC5 — Planning Board is not a capacity resource

## Ops + Engineering Manager brainstorm → Senior decision

### Problem
The **Planning Board** account (wall TV / monitor login) appeared on Dashboard **Resource Availability** as “PB Planning Board · Open”, and could enter utilization, workload, and resource-planning pools. It is a **virtual viewing user**, not a billable or assignable engineer.

### Ideas considered
| Idea | Verdict |
|------|---------|
| Rename display only / hide “PB” in the UI | Rejected — still counted in Open/Assigned totals |
| Soft-delete the Planning Board user | Rejected — wall login required |
| Frontend filter on name “Planning Board” | Rejected — fragile; misses other APIs |
| **Central `NON_CAPACITY_RESOURCE_ROLES` exclusion on all KPI/capacity user queries + fix operational-role infer (was defaulting PB → engineering with all KPI flags on) + startup backfill clears flags** | **Locked** |

### Locked rules
1. **Planning Board never counts** as a designer / open capacity / utilization / workload / resource-planning row.
2. Same rule for other virtual/monitor accounts: Admin, Read Only, HR, Office Administrator (aligned with timesheet-exempt roles).
3. KPI defaults: Planning Board maps to **administration** operational type (all capacity KPIs **false**), never engineering.
4. Defense in depth: even if flags were wrongly set `True`, role filter excludes them from pools.

## Senior-approved code

| File | Change |
|------|--------|
| `app/core/timesheet_eligibility.py` | `NON_CAPACITY_RESOURCE_ROLES`, `role_is_non_capacity_resource()` |
| `app/services/kpi_participation.py` | Exclude those roles from all `users_for_kpi_flag` / subqueries; clear flags on apply defaults |
| `app/db/phase14_kpi_schema_sync.py` | Infer Planning Board → administration; backfill clears capacity KPI flags |
| `tests/test_planning_board.py` | Assert PB absent from summary availability, workload, planning grid, utilization pools |

Surfaces covered via shared pools: Dashboard Resource Availability & Designer Utilization, Workload, Resource Planning grid, AI capacity insights (`engineering_productivity_users` / utilization).

## Testing checklist

| # | Check | Pass |
|---|--------|------|
| 1 | Dashboard → Resource Availability: no “Planning Board” / “PB” row | |
| 2 | Open / Assigned counts exclude Planning Board | |
| 3 | Designer Utilization list has no Planning Board | |
| 4 | Workload heatmap / designer table: no Planning Board | |
| 5 | Resource Planning grid: no Planning Board designer | |
| 6 | AI insight “X has available capacity” never cites Planning Board | |
| 7 | Planning Board login still reaches `/planning-board` wall | |
| 8 | Restart API once so phase14 backfill clears stale KPI flags in DB | |

## Testing lead → QC

- [ ] Smoke EM Dashboard + Workload + Resource Planning + Planning Board wall login  
- [ ] Deploy API + hard refresh front-end if needed  
- [ ] Confirm Open count dropped by 1 where PB was previously “Open”  
- [ ] Sign-off → user testing  
