# Timesheet Tool Number dropdown — Testing / QC / UAT checklist

**Bug:** Active tool numbers missing from Timesheets “Tool Number” search; typing in the field reset the Add Entry section.

**Fix shipped:** form no longer resets when tool options refresh; full loggable project list loads once and filters client-side; **planning** projects are included with currently-being-worked-on and on-hold.

---

## Testing team — validation

- [ ] Open **Timesheets** (own month view with Add Entry form visible).
- [ ] Open **Tool Number** dropdown without typing — list shows **MY ASSIGNED**, **RECENTLY USED**, **ALL ACTIVE PROJECTS**, and **NON PRODUCTIVE**.
- [ ] Confirm a project in **Planning** status appears (create/set one if needed).
- [ ] Confirm projects **Currently being worked on** and **On hold** appear.
- [ ] Confirm **Completed** / **Cancelled** / archived projects do **not** appear.
- [ ] Type a known tool number (e.g. digits from an existing entry) — filter narrows; **Date / Hours / Notes do not clear**.
- [ ] Clear the search text — full list returns; form fields still intact.
- [ ] Select a project tool, pick Task, enter Hours, Add Entry — succeeds.
- [ ] Select an NP code (e.g. C500), enter Hours, Add Entry — succeeds.
- [ ] Edit an existing entry via dialog — tool search behaves the same (no reset).
- [ ] Hard-refresh browser after deploy; re-check open dropdown + type-without-reset.

**Testing sign-off:** ________  **Date:** ________

---

## QC team — audit

- [ ] Change is limited to timesheet tool lookup / entry form (no unrelated nav/theme churn).
- [ ] Backend loggable statuses: `planning`, `currently_being_worked_on`, `on_hold` only.
- [ ] No server round-trip on each keystroke for tool search (client filter).
- [ ] Automated: `pytest tests/test_global_timesheet_entry.py -q` passes.
- [ ] Frontend build succeeds (`npm run build` in `frontend/`).
- [ ] Regression: NP reference panel still lists NP codes; monthly summary still updates after add.

**QC sign-off:** ________  **Date:** ________

---

## UVT / UAT

- [ ] Engineering Manager (or designer) can log time against active/planning tools without form reset.
- [ ] Existing month entries and approvals banner behaviour unchanged.
- [ ] No production data migration required (status filter only).

**UVT:** ________  **UAT:** ________  **Release:** ________
