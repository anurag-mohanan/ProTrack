# R4 Enterprise Features — UAT checklist

## Optional QA gate

- [ ] Project edit → enable **Require QA acknowledgement before completing milestones**
- [ ] Complete a milestone → confirmation dialog appears
- [ ] Acknowledge & complete succeeds; completing without ack is blocked by API when gate is on
- [ ] Disable gate → Complete works without confirmation

## Documents (DMS metadata)

- [ ] Project edit → Files section lists documents
- [ ] Upload a file → appears in list
- [ ] Download retrieves the uploaded file

## Learning plans

- [ ] Performance → Skills Matrix shows **Learning plans**
- [ ] Select a person → Create from gaps creates a plan from skill gaps
- [ ] Mark item done / reopen updates status

## Legal entities (multi-entity prep)

- [ ] Admin → Company Information → Legal entities shows default entity
- [ ] Default entity code/name/currency visible; operations remain single-tenant
