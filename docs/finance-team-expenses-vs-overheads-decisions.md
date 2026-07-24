# Team Expenses vs Company Overheads — Decisions (Gate 0)

## Product split

| Section | Owns | Attribution |
|---------|------|-------------|
| **Expenses & subscriptions** | Team-wise spend only: software, hardware CapEx, travel/training dedicated to a team, other team OpEx | Delivery `team_id` (never Corporate) |
| **Overheads** | Company-wide shared HQ: rent, utilities, internet, office, maintenance, insurance, taxes, misc shared | Corporate / Management home only |

## Rules

1. Same `expenses` table; split by **team** (corporate = overhead, else = team expense).
2. API `scope=team|overhead|all` on `GET /finance/expenses`.
3. Expense reads include `cost_centre_code`, `cost_centre_name`, `spend_category`
   (`software` | `hardware_capex` | `other` | `shared`).
4. Expenses UI groups by **team**, then by category (Software / Hardware CapEx / Other).
5. Overheads UI catalogue is facilities/HQ only — SW/HW belong on Expenses.
6. P&L formulas unchanged: delivery OpEx/CapEx vs overhead pool still follow `team_id`.

## Out of scope

- Splitting one invoice across teams
- Auto-allocating overhead into delivery net (CPR remains analytical)
