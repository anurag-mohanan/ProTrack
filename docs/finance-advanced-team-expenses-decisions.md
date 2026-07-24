# Advanced Team Expenses — Decisions (Gate 0)

Brainstorm: `docs/finance-advanced-team-expenses-brainstorm.md`.

| Topic | Decision |
|-------|----------|
| Attribution | Keep required `Expense.team_id`; no new common entity. |
| Common pool | `is_common` when team is Corporate / Management (legacy names included). |
| API | `ExpenseRead` adds `team_name`, `is_common`, `display_group` (`Common` or team name). |
| UI | Expenses tab: **Advanced** toggle — group lines by `display_group`; Common section first. |
| Form | Team select labels Common home as `Common (Corporate / Management)`. |
| P&L | No change to rollup formulas; attribution correctness is the lever. |
| Delete confirm | Include team / Common label. |
