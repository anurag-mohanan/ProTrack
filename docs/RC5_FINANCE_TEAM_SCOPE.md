# RC5 — Finance Rebuild 2: Team-wise Costs & Who Pays

## HOD lock

| Decision | Lock |
|----------|------|
| Primary lens | Team filter (All / one team) on Financial Planning |
| Expenses | `team_id` **required**; shared HQ → **Corporate / Shared Services** |
| Commercial | One active terms row per team; `customer_pays_software` / `customer_pays_hardware` |
| Who pays defaults | SW_* / HARDWARE/SERVERS/CLOUD cost centres inherit team flags (overridable) |
| Salaries | Roster filter by primary team; salary-exempt via [RC5_SALARY_ELIGIBILITY.md](./RC5_SALARY_ELIGIBILITY.md) |
| Rollups | Team-scoped operating cost / pass-through / commercial fee |

## Click map

| What | Where |
|------|--------|
| Team filter | Top of `/finance` (persists in localStorage) |
| Who-pays flags | **Team commercial** → Customer pays software / hardware |
| Team on expense | **Expenses & subscriptions** → Team required; edit/delete per [RC5_FINANCE_EXPENSE_CRUD.md](./RC5_FINANCE_EXPENSE_CRUD.md) |
| Per-team Overview | **Overview** with filter; All teams shows breakdown |

## Pipeline

1. Development → 2. Senior Tester verify → 3. Testing debug → 4. Senior Tester approve → 5. QC → 6. UAT

### Senior Tester / Testing matrix

- [ ] Expense without team → 400/422
- [ ] Team A `customer_pays_software=true` → SW expense defaults customer; pass-through ↑
- [ ] Team B flags false → SW defaults Prosohm; team B opex ↑
- [ ] Filter Team A ↔ All ↔ Team B scopes Overview / expenses / roster / renewals
- [ ] Corporate rent under Corporate / All only
- [ ] Designer 403
- [ ] Rebuild 1 regression (renewals, budgets, quote import)

### QC

- [ ] Docs match UI
- [ ] Salary not on Ops routes
- [ ] Deploy `app/` + `frontend/dist`; restart API (phase23)

## Related

- Prior: [RC5_FINANCE_REBUILD.md](./RC5_FINANCE_REBUILD.md)
- Salary exempt: [RC5_SALARY_ELIGIBILITY.md](./RC5_SALARY_ELIGIBILITY.md)
- Expense edit/delete: [RC5_FINANCE_EXPENSE_CRUD.md](./RC5_FINANCE_EXPENSE_CRUD.md)
- Purchase date / FY cutover: [RC5_FINANCE_PURCHASE_DATE_FY.md](./RC5_FINANCE_PURCHASE_DATE_FY.md)
- Commercial UX + expense CRUD package: [RC5_FINANCE_COMMERCIAL_UX_EXPENSE_CRUD.md](./RC5_FINANCE_COMMERCIAL_UX_EXPENSE_CRUD.md)
- Editable lists + retainer/project fee rules: [RC5_FINANCE_EDITABLE_FEE_MODELS.md](./RC5_FINANCE_EDITABLE_FEE_MODELS.md)
- Customer currency + immutable FX + editable finance: [RC5_FINANCE_CUSTOMER_CURRENCY_FX.md](./RC5_FINANCE_CUSTOMER_CURRENCY_FX.md)
- Awarded quote import (team + PDF/Excel): [RC5_FINANCE_AWARDED_QUOTE_IMPORT.md](./RC5_FINANCE_AWARDED_QUOTE_IMPORT.md)
- Management / overhead vs billable headcount: [RC5_FINANCE_MANAGEMENT_OVERHEAD.md](./RC5_FINANCE_MANAGEMENT_OVERHEAD.md)
