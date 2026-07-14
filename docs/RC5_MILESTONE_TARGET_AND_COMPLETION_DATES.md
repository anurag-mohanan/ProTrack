# RC5 — Per-milestone Target dates + Completion on Complete

## Ops + Engineering Manager brainstorm → Senior decision

### Problem
Project schedule cannot be a single end date. On Milestones (e.g. project 2649), **Target** showed `—` for every row, and completion dates were not clearly tied to when status became **Completed**.

### Ideas → locked

| Idea | Verdict |
|------|---------|
| Keep one project `due_date` as the only schedule | Rejected — phases need independent deadlines |
| Soft-sync project due date = max(milestone targets) | Parked for later |
| **Editable `due_date` (Target) on every milestone** | **Locked** |
| **Stamp `completed_date` / `completed_at` when status first becomes Completed; clear when reopened** | **Locked** |
| Assignees with progress-only rights may edit Target | **Locked** (`due_date` in progress-only fields) |

## Senior-approved code

| File | Change |
|------|--------|
| `app/services/milestone_workspace_service.py` | `apply_progress_rules(..., previous_status=)` stamps/clears completion |
| `app/crud/milestone.py` | Passes `previous_status` into progress rules |
| `app/api/v1/milestones.py` | Progress-only patch may include `due_date` |
| `frontend/.../ProjectMilestoneGridRow.tsx` | Inline Target date field; Completed shows label + completion date |
| `frontend/.../ProjectMilestoneGrid.tsx` | Copy clarifies Target vs Completion |

## Testing checklist

| # | Check | Pass |
|---|--------|------|
| 1 | Restart API + hard refresh frontend | |
| 2 | Open project Milestones: Target column is an editable date (not blank `—` only) | |
| 3 | Set different Target dates on 2+ milestones; reload — values persist | |
| 4 | Change status **→ Completed**: completion date = today under Status; Target unchanged | |
| 5 | Change status **away from Completed**: completion date clears | |
| 6 | Progress 100% auto-completes and stamps completion date | |
| 7 | Progress-only user can edit Target + status without full project edit rights | |
| 8 | Clearing Target (empty date) saves as no target | |

## Testing lead → QC

- [ ] Smoke Milestones on an active tool (target + complete/reopen)
- [ ] Confirm project-level due date (if shown) is not required for milestone planning
- [ ] Sign-off → user testing
