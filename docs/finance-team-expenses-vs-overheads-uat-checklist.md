# Team Expenses vs Overheads — UAT checklist

Decisions: `docs/finance-team-expenses-vs-overheads-decisions.md`.

## Gate 2 — Automated

- [x] `scope=team` excludes Corporate; `scope=overhead` includes only Corporate
- [x] `spend_category` software / hardware_capex / other / shared on reads

## Gate 3 — QC

- [ ] Expenses tab: delivery teams only; groups by team → Software / Hardware CapEx / Other
- [ ] Overheads tab: rent/utilities/etc only; locked to Corporate / Management
- [ ] Software license on Design → Expenses (Design) + Design P&L OpEx; not Overheads list
- [ ] HQ rent on Corporate → Overheads + overhead pool; not Expenses team list
- [ ] Cost type picker prefers SW / HW / Cloud / Training / Travel / Misc

## Gate 5 — UAT / UVT

1. Record NX license under Design on Expenses.
2. Record HQ rent under Overheads.
3. Confirm Overview Team P&L and Overhead KPIs separately.

**Signer:** ________  **Date:** ________
