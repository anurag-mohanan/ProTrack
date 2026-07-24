# Advanced Team Expenses — QC / Dual-user / UAT

Decisions: `docs/finance-advanced-team-expenses-decisions.md`.

**Pipeline:** Finance/Eng/Ops brainstorm → Development → Testing → QC → UAT/UVT.

## Gate 2 — Testing (automated)

- [x] `tests/test_finance_advanced_team_expenses.py` — Common vs delivery `display_group` on create/list/patch.

## Gate 3 — QC

- [x] Expense list returns `team_name`, `is_common`, `display_group` (API tests).
- [ ] Advanced + All teams: groups by team; Common section first when Corporate expenses exist.
- [ ] Create with Corporate team → shows under Common.
- [ ] Create with delivery team → shows under that team; Team P&L OpEx moves with that team.
- [ ] One-team filter: list scoped; advanced still usable.
- [ ] Simple mode flat list still works.
- [ ] Delete confirm shows team/Common label.

**QC:** ________  **Date:** ________  **Signer:** ________

## Gate 4 — Peer debug

| Step | Finance user A | Ops/Eng B | Pass? |
|------|----------------|-----------|-------|
| 1 | Add Common (Corporate) expense | Sees under Common in Advanced | |
| 2 | Add Design team expense | Sees under Design group | |
| 3 | Open Overview Team P&L | Design OpEx includes B’s line; Common not in Design net | |

## Gate 5 — UAT / UVT

1. Advanced grouping happy path.  
2. Regression: create/edit/delete, paid-by defaults, FY filter, Overview KPIs.  
3. Confirm no claim that Common is auto-split into delivery P&L.

**UAT/UVT:** ________  **Date:** ________  **Signer:** ________
