# HR Process Control — QC / Dual-user / UAT gates

Decisions: see `docs/hr-process-control-decisions.md`.

## Gate 3 — QC audit checklist

- [ ] Start onboarding with email → User created (Designer), checklist linked, temp password / must_change_password.
- [ ] Duplicate email returns clear 422; linking existing user does not create a second account.
- [ ] Team lead receives in-app notification (`new_hire_onboarding`) and email queue/template `new_hire_onboarding`.
- [ ] No Help Desk ticket created for the team leader specifically.
- [ ] Process Audit lists: incomplete onboarding (14d SLA), orphan placement, missing exit, exit-done-still-active.
- [ ] Completed / fixed cases drop off the audit list.
- [ ] Deep links open Onboarding / Exit / Users as expected.
- [ ] Non-HR roles cannot open `/hr/process-audit` (403).
- [ ] Email body contains only agreed fields (name, team, joining date, links) — no password.

**QC result:** ________  **Date:** ________  **Signer:** ________

## Gate 4 — Two-user peer check

| Step | User A (HR) | User B (Team Leader) | Pass? |
|------|-------------|----------------------|-------|
| 1 | Start onboarding for new hire with team | — | |
| 2 | Confirm User appears; audit clean for new hire until SLA | Receives in-app + email | |
| 3 | — | Opens Users, sets role/access | |
| 4 | Marks checklist progress | Completes manager items | |
| 5 | Confirm no permission leak on audit for B if B lacks HR | — | |

**Peer result:** ________  **Date:** ________  **A:** ________  **B:** ________

## Gate 5 — UAT / UVT

Scripted scenarios on staging (FreeFileSync `frontend/dist` + API restart):

1. Happy path: start → notify → role change → complete onboarding.
2. Duplicate email blocked.
3. Missing exit flagged for inactive / leaving_date user; disappears after completed exit.
4. Regression smoke: Timesheet Reports generate-before-download; Onboarding compact UI; Exit Process save/complete; Project templates filters.

**UAT result:** ________  **UVT result:** ________  **Date:** ________
