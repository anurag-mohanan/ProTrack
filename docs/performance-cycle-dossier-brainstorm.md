# Performance Cycle Dossier — Department Heads Brainstorm

Workshop notes transferred to Development (Gate 0 input). Participants represented:
**HR**, **Engineering**, **Operations** (Design Leaders / Team Leaders).

## Problem

Annual reviews (July–June) already exist, but individuals and leaders lack a single
**quantified year view**: which projects someone worked on, capacity vs hours,
leave logged on timesheets, checking/support contributions, and last year’s score
and goals. Leaders need the same picture for their team (and managers for the
wider org) without opening every review sheet.

## Decisions from discussion

| Department | Need | Outcome |
|------------|------|---------|
| **HR** | Fair, auditable cycle signals aligned to review year | Dossier keyed to **review year** (1 Jul → 30 Jun); leave = **timesheet leave days** (GreytHR balances stay out of band) |
| **Engineering** | Projects + checking help + delivery load | List owned vs supported projects in period; hours per project; checking hours via task-type heuristic; actual vs quoted on owned projects |
| **Operations / Team Leaders** | See each direct report’s year at a glance | Team roster → open individual dossier; reuse managed-team access |
| **Managers / Dept heads** | Org-wide or multi-team view | Same roster API with broader `_managed_team_ids` / HR access |
| **Individuals** | Know how *they* are performing | Self dossier is default; no edit of metrics (read-only derived data) |

## Quantifiable signals (v1)

1. Period label + Jul–Jun bounds for selected review year  
2. Hours: worked / expected / productive / NP; months above expected (>100%)  
3. Leave days from timesheets (C500 / leave entries)  
4. Projects worked (owned + supported) with hours; checking hours estimate  
5. For owned projects: person’s hours, project quoted hours, project actual hours  
6. Prior acknowledged annual review: overall score, career goals, strengths, improvements, manager summary  
7. Skills snapshot (rated / proficient+)

## Visibility ladder

- **Self** — own dossier  
- **Team Leader / reviewer / EM on team** — members of managed teams  
- **HR / Admin / org-wide EM** — accessible teams (existing helpers)

## Out of scope v1

- GreytHR leave balances / leave types  
- Formal overtime entity  
- Structured OKRs (keep free-text `career_goals`)  
- Editable “dossier notes” (use review sheet)  
- Customer-facing / portal export
