# Advanced Team Expenses — Department Heads Brainstorm

Workshop notes for Development (Gate 0). Participants: **Finance**, **Engineering**,
**Operations**.

## Problem

Expenses already require a `team_id`, but the Expenses tab shows a **flat list**. Leaders
cannot see spend by delivery team vs shared HQ. Without that grouping, **team P&L**
(direct OpEx on each team) is hard to explain from the expense screen.

## Decisions from discussion

| Department | Need | Outcome |
|------------|------|---------|
| **Finance** | Clear team OpEx vs shared HQ for P&L | Keep real `team_id`; label Corporate / Management as **Common** in advanced view |
| **Engineering** | Delivery teams see their software/tools spend | Group expense lines by team when viewing All teams |
| **Operations** | Shared facilities/admin not dumped onto one delivery team | Shared → **Common** (Corporate / Management home) |
| **All** | Don’t break existing P&L math | No multi-team split; CPR stays analytical on Overheads — delivery nets stay **direct** costs only |

## Product rules (v1)

1. Every expense stays attributed to **one** team (API already requires `team_id`).  
2. **Common** = Corporate / Management (and legacy corporate names). UI may show “Common (shared HQ)”.  
3. **Advanced mode** on Expenses: group by team (Common first), show team chip + Prosohm Σ per group.  
4. Simple mode remains flat (optional toggle defaults to Advanced when All teams).  
5. Team filter still scopes to one team; advanced grouping mainly for All teams.  
6. Team P&L Overview continues to use `Expense.team_id` — correct Common vs delivery attribution feeds P&L.

## Out of scope v1

- Splitting one invoice across multiple teams  
- Null `team_id` / separate common table  
- Auto-allocating Common OpEx into delivery nets (CPR already covers analytical view)
