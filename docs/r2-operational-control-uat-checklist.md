# R2 Operational Control — UAT checklist

## Calendar (prior)

- [ ] Engineering calendar: date headers stay visible while scrolling project rows

## Stage gate

- [ ] Completing a project with open **required** milestones returns a clear validation error
- [ ] Completing after required milestones are done succeeds
- [ ] Setting stage to **final** with open required milestones is blocked

## Quote → project handoff

- [ ] Planning projects missing type/team/leader/due date/template show **Needs setup** chip
- [ ] Chip tooltip lists missing fields
- [ ] Fully configured planning projects do not show the chip

## Timesheet policy

- [ ] `GET /api/v1/settings/timesheet-policy` returns editable window + soft-lock flag
- [ ] Oldest editable month shows soft-lock warning banner
- [ ] Months older than the window remain hard-locked (admin can still edit)

## Approvals inbox

- [ ] Dashboard My Tasks **View all** opens `/approvals`
- [ ] Inbox lists approvals, milestones, and reviews
- [ ] Clicking a row navigates to the item href

## Pagination

- [ ] Admin Customers paginates server-side (25 default) and search filters by name/code
- [ ] Projects list still loads portfolio filters/KPIs (paginated fetch under the hood)
