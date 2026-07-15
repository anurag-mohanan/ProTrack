# RC5 — Salary eligibility (People costs)

## HOD lock

| Decision | Lock |
|----------|------|
| Control | Per-user **Requires salary (People costs)** on Admin → Users (mirrors Requires timesheet) |
| Field | `users.requires_salary` — True = headcount on Finance People costs / salary rollups |
| Role defaults | **Admin**, **Planning Board** → False; all other roles → True (override wins) |
| Roster | Default = required only; **Show salary-exempt** to inspect; Missing salary ignores exempt |
| Rollups | Salary totals exclude exempt users even if an old cost profile exists |
| Write | `POST /finance/employee-costs` for exempt user → **400** |

## Click map

| What | Where |
|------|--------|
| Toggle | Admin → Users → Requires salary (People costs) |
| People costs list | `/finance` → People costs (team filter + optional Show salary-exempt) |

## Pipeline

1. Development → 2. Senior Tester verify → 3. Testing debug → 4. Senior Tester approve → 5. QC → 6. UAT

### Senior Tester / Testing matrix

- [ ] New Admin → requires_salary false; not on default People costs; not Missing salary
- [ ] New Planning Board → same
- [ ] New Designer → requires_salary true; Missing salary until saved
- [ ] Admin Requires salary ON → on roster; can save; Overview salary ↑
- [ ] Designer OFF → off default roster; profile excluded from Overview; POST salary → 400
- [ ] Team filter still scopes headcount (Rebuild 2)
- [ ] Designer 403 on finance APIs
- [ ] Rebuild 1/2 regression (renewals, paid_by, team commercial)

### QC

- [ ] Users toggle + roster + Overview consistent
- [ ] No salary/exempt leakage on Ops-only routes
- [ ] Docs match UI; deploy `app/` + `frontend/dist`; restart API (phase24)

## Related

- [RC5_FINANCE_TEAM_SCOPE.md](./RC5_FINANCE_TEAM_SCOPE.md)
- [RC5_FINANCE_REBUILD.md](./RC5_FINANCE_REBUILD.md)
