# RC5 — Project Overview workorder details + searchable metadata

## Ops + Engineering Manager brainstorm → Senior decision

### Problem
When many tools are completed, Ops needs to find past projects by **part description keywords**, **press tonnage**, **plastic material**, and other workorder facts. Customer workorders arrive as **PDFs with different layouts per customer**, but share the same core facts. Overview today only showed timeline + contributors.

### Ideas → locked

| Idea | Verdict |
|------|---------|
| Store everything only in free-text `notes` | Rejected — hard to search consistently |
| Build per-customer PDF extractors first | Parked (**Phase B**) — layouts differ; needs templates + review UI |
| OCR scanned PDFs in RC5 | Rejected for now — current PDF stack is tabular text only |
| **Phase A: structured fields on Project + Overview panel + project search haystack** | **Locked** |
| Manual capture on Overview / Create-Edit form until PDF extract exists | **Locked** |

### Locked fields

| Field | Purpose |
|-------|---------|
| `work_order_number` | Customer WO reference (≠ tool number) |
| `press_tonnage` | e.g. `650T` (string — formats vary) |
| `plastic_material` | e.g. PP GF30 |
| `cavity_count` | Cavities |
| `tool_type` | Classification |
| `customer_specs` | Other searchable workorder text |
| `part_description` | Already existed — still primary search text |

## Senior-approved code

| File | Change |
|------|--------|
| `app/models/models.py` | New Project columns |
| `app/db/phase21_project_workorder_schema_sync.py` | Column ensure on startup |
| `app/schemas/project.py` | Create/Update/Read fields |
| `app/main.py` | Register phase21 sync |
| `frontend/.../ProjectWorkorderDetailsPanel.tsx` | Overview display + edit |
| `frontend/.../ProjectWorkspace.tsx` | Overview + Files messaging |
| `frontend/.../ProjectFormDialog.tsx` | Workorder / tooling section |
| `frontend/src/utils/projectCommandCenter.ts` | Search haystack includes new fields |
| `frontend/.../WorkflowTimeline.tsx` | Due dates use DD-MM-YYYY |

## Phase B (parked)

- Per-customer PDF workorder parsers / field mapping
- Review screen for low-confidence extracts
- Auto-fill Overview fields from uploaded WO PDF

## Testing checklist

| # | Check | Pass |
|---|--------|------|
| 1 | Restart API (schema sync) + hard refresh frontend | |
| 2 | Overview shows Workorder / tooling details panel | |
| 3 | Edit & save tonnage / material / WO # / cavity / tool type / specs | |
| 4 | Reload — values persist | |
| 5 | Projects search finds tool by material or tonnage keyword | |
| 6 | Create/Edit project form has Workorder / tooling section | |
| 7 | Timeline dues show DD-MM-YYYY (not YYYY-MM-DD) | |
| 8 | Files tab mentions future PDF extract | |

## Testing lead → QC

- [ ] Smoke Overview on project 2649 — enter sample material/tonnage and search from Projects
- [ ] Confirm API starts cleanly (phase21)
- [ ] Sign-off → user testing
