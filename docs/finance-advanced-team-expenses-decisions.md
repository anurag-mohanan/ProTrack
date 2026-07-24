# Advanced Team Expenses — Decisions (Gate 0)

**Superseded for product split by** `docs/finance-team-expenses-vs-overheads-decisions.md`.

Shared company spend now lives on **Overheads** (Corporate / Management).  
**Expenses & subscriptions** is delivery-team only, grouped by team + category.

| Topic | Decision (historical) |
|-------|----------|
| Attribution | Keep required `Expense.team_id`; no new common entity. |
| Common pool | Corporate / Management → Overheads section (not Expenses Advanced). |
| API | `scope=team|overhead|all`; `spend_category` on reads. |
| UI | Expenses: team + Software / CapEx / Other. Overheads: shared HQ catalogue. |
| P&L | No change to rollup formulas; attribution correctness is the lever. |
