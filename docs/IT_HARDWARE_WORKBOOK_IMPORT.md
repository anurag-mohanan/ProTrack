# IT Hardware Workbook Import

Reusable import type: **`hardware_workbook`** (label: IT Hardware Workbook)

## How to import

1. IT → Data Import
2. Select **IT Hardware Workbook**
3. Upload an `.xlsx` (or compatible) file whose sheet is named **IT Assets Import**
4. Analyze → review preview → Commit (with Skip duplicates on for safe re-import)

Reference sheets **Master Data Seed** / **Ownership Options** are never auto-selected.

## Column aliases (examples)

| Logical field | Recognized headers |
|---------------|--------------------|
| Asset Number | Asset Number, Asset Tag, IT Asset No, … |
| Category | Category, Asset Category |
| Asset Type | Asset Type, Type |
| Make | Make / Brand, Brand, Manufacturer |
| Model | Model, Model Number |
| PC Name | PC Name, Hostname |
| Parent Asset Number | Parent Asset Number (never mapped to Asset Number) |
| Hardware Owner Type / Owner | Hardware Owner Type, Hardware Owner |

## Business rules

- Supplied Asset Numbers are preserved **exactly** (no `IT164` → `IT-164`)
- Blank Asset Number → suggested via central generator (shown in preview)
- Duplicate Asset Numbers → skip by default
- Assigned User `Open` → unassigned / Available (not an employee)
- Blank ownership → `purchased_by=unknown` + OWNERSHIP_REQUIRED (filter later)
- 3D Mouse blank make/model → `3Dconnexion` / `SpaceMouse Compact`
- Parent links resolved in a second pass (order-independent)
- Workstations with PC/MAC/IP create Computer + IP records

## Schema

- `assets.parent_asset_id` (phase90)
