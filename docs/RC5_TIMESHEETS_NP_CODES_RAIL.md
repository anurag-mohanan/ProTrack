# RC5 — Timesheets NP codes right rail

## Ops + Engineering Manager brainstorm → Senior decision

### Question
Should Non-Productive Codes stay a full-width accordion above the entry form?

### Answer (locked)
**No.** It should be a **small, always-expanded cheat-sheet on the right** of the My Entries workspace so people can glance at codes while typing without a full-width expand/collapse bar.

| Idea | Decision |
|------|----------|
| Always expanded | Yes |
| Right side (~240px) | Yes (desktop/tablet `md+`) |
| Sticky while scrolling form area | Yes |
| Full-width accordion | Removed |
| Entries table | Stays **full width below** form + rail (needs horizontal room) |
| All Users view | No NP rail (monitoring only; no entry form) |
| Mobile | Compact card under form (same component, stacks) |

### Developer notes (Senior-approved)
- Rework `TimesheetNpReferencePanel` from Accordion → aside card
- Wrap entry form + quick actions + NP panel in a 2-column grid on `TimesheetsPage`
- Dense code/description rows; internal scroll if many codes

## Code

| File | Change |
|------|--------|
| `frontend/src/components/timesheets/TimesheetNpReferencePanel.tsx` | Compact always-open right rail |
| `frontend/src/pages/TimesheetsPage.tsx` | My Entries: form left, NP rail right |

## Testing checklist

| # | Check | Pass |
|---|--------|------|
| 1 | My Entries: no full-width NP accordion bar | |
| 2 | Desktop: NP Codes card on the right of the entry form | |
| 3 | Panel is always expanded (codes listed) | |
| 4 | Panel is clearly smaller than the form/table | |
| 5 | Long code list scrolls inside the panel | |
| 6 | Entries table still full width underneath | |
| 7 | All Users view has no NP rail | |
| 8 | Add Entry still works with NP tool numbers | |
| 9 | Narrow/mobile: NP card stacks under form, still readable | |

## Testing lead → QC

- [ ] Smoke My Entries on EM + Designer accounts  
- [ ] Deploy `frontend/dist`, hard refresh  
- [ ] Sign-off → user testing  
