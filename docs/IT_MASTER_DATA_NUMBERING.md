# IT Master Data & Asset Numbering

Date: 2026-09-07

## Delivered

### Cascading master data (single SoT under IT)
- Tables: `it_asset_categories`, `it_asset_makes`, `it_asset_make_type_links`, `it_asset_models`
- Asset FKs: `assets.make_id`, `assets.model_id` (free-text `make`/`model` retained for display/history)
- Reuses existing `asset_types` and `it_suppliers`
- Phase sync: `app/db/phase88_it_master_data_schema_sync.py` (backfills from existing free-text)
- Service: `app/services/it_master_data_service.py` (normalize / dedupe / get-or-create / cascade validate)
- APIs: `GET|POST /it/master/categories|types|makes|models|suppliers`

### Asset number generation
- Central: `preview_next_asset_number` + `next_asset_number` in `it_asset_service.py`
- Rule: **highest existing sequence for prefix + 1** (does not fill gaps; includes disposed/retired)
- Locked via `ITSettings` `SELECT FOR UPDATE`; uniqueness still `uq_assets_tenant_asset_number`
- Concurrent clash returns clear error with suggested next number
- `GET /it/assets/next-number?asset_type_id=`
- Manual override requires `override_it_asset_number` (or `manage_it_settings`)

### UI
- Assets form: Category → Type → Make → Model → Supplier cascading + suggested number
- Master Data page: `/it/master-data` (Categories / Types / Makes / Models / Suppliers)
- Import: supplied numbers preserved; blank numbers allocated via generator

### Tests
- `tests/test_it_master_data_numbering.py` (5 passed)

## Notes / risks
- Existing free-text make/model preserved; masters learned non-destructively
- Global `next_asset_seq` is aligned to highest DB sequence per prefix when allocating
- Full inactive-master admin merge UI is basic (add + usage counts); deactivate/merge polish can follow
