# Employee Training — Department Heads Brainstorm

Workshop notes transferred to Development (Gate 0 input). Participants represented:
HR, Engineering, IT/Admin, Finance/Accounts, Operations (Design Leaders).

## Problem

New-hire onboarding checklists mention training in free text ("GreytHR training",
"Timesheet access & training") but there is no structured course library, no
completion proof, and Process Audit cannot tell who skipped mandatory training.
Ad-hoc refreshers (security, process changes) also need assignment without waiting
for the next hire cohort.

## Decisions from discussion

| Department | Need | Outcome |
|------------|------|---------|
| **HR** | Common induction for every employee; auditability | Mandatory **common** courses auto-assigned at onboarding start; Process Audit flag when overdue |
| **Engineering / Design Leaders** | Timesheet + ProTrack basics before productive work | Seed course: ProTrack timesheets & project basics |
| **IT / Admin** | Security, passwords, data handling | Seed course: IT security & acceptable use |
| **Finance / Accounts** | Awareness of expense / quote touchpoints for non-finance | Optional later; not blocking v1 common set |
| **All heads** | New courses over time without code deploy | HR can **create courses** and **assign** to people/teams; soft notify by due date |
| **All heads** | Do not confuse with Performance skill-gap plans | Keep R4 **learning plans** separate (skill matrix). Training = compliance / ops induction |

## Common courses (seed — all new hires)

1. **Company orientation & code of conduct** (HR) — ~30 min
2. **IT security & data handling** (IT) — ~20 min
3. **ProTrack basics: timesheets & projects** (Engineering/Ops) — ~45 min
4. **Leave & payslips (GreytHR / HRIS)** (HR) — ~20 min
5. **Workplace health & safety overview** (Admin/HR) — ~15 min

## Ad-hoc / ongoing trainings

- HR creates course (`is_required_for_onboarding=false`)
- Assign to users or “all active” with **due date** (availability = soft due date, not calendar block)
- In-app (+ email when template exists) notification; reminders while incomplete
- Appears on employee Training list and Process Audit if past due

## Out of scope v1

- SCORM / video LMS hosting (use description + external URL + acknowledge complete)
- Department-specific mandatory packs beyond the common five (can add as courses later)
- Automatic calendar free/busy scheduling

## Handoff

→ Development: implement per `docs/employee-training-decisions.md`  
→ Testing: debug per UAT Gate 4 scenarios  
→ QC: Gate 3 audit before UAT/UVT release  
