# Employee Training — QC / Dual-user / UAT gates

Decisions: `docs/employee-training-decisions.md`. Brainstorm: `docs/employee-training-brainstorm.md`.

## Gate 3 — QC audit checklist

- [ ] Five common courses seeded and marked required for onboarding.
- [ ] Starting onboarding with linked user auto-creates required training assignments.
- [ ] Completing all checklist items **blocked** until required trainings completed (clear 422/message).
- [ ] Employee can list own assignments and mark complete.
- [ ] HR can create a new optional course and assign to a user with due date → notification created.
- [ ] Process Audit shows `incomplete_training` for overdue assignments; clears when completed.
- [ ] Deep link opens `/hr/training`.
- [ ] Learning plans (Performance) unchanged / separate.
- [ ] Non-HR cannot create courses (403).

**QC result:** ________  **Date:** ________  **Signer:** ________

## Gate 4 — Two-user peer check (Testing thorough debug)

| Step | User A (HR) | User B (New hire / Designer) | Pass? |
|------|-------------|------------------------------|-------|
| 1 | Start onboarding for B | — | |
| 2 | Open Training — see B’s required courses | Sees own Training list | |
| 3 | — | Completes 4 of 5 courses | |
| 4 | Try force-complete checklist — blocked | Completes 5th course | |
| 5 | Checklist can complete | — | |
| 6 | Create ad-hoc course; assign to B due tomorrow | Gets notification | |
| 7 | Move due date to yesterday (or wait) | Audit flags incomplete_training | |
| 8 | B completes ad-hoc | Flag clears | |

**Peer / Testing result:** ________  **Date:** ________  **A:** ________  **B:** ________

## Gate 5 — UAT / UVT

1. Happy path: onboarding + all common trainings → checklist complete.
2. Ad-hoc training notify + complete.
3. Audit overdue training visible to HR.
4. Regression: Onboarding UI, Process Audit existing flags, Performance learning plans.

**UAT result:** ________  **UVT result:** ________  **Date:** ________

**Release rule:** QC Gate 3 signed before department UAT/UVT.
