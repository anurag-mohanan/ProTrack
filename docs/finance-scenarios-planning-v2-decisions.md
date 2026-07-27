# Finance Scenarios / Planning v2 — Decisions (Gate 0 → Development)

**Status:** Approved for implementation  
**Date:** 2026-07-27  
**Input:** `finance-scenarios-planning-v2-brainstorm.md`  
**Supersedes:** v1 “localStorage only” as the **only** persistence path once v2 ships (localStorage remains optional draft buffer).

---

## 1. Scope summary

| # | Capability | Layer |
|---|------------|-------|
| S1 | **Persist scenarios** — CRUD API + DB model | Backend + UI |
| S2 | **New team simulation** — hypothetical team rows with working model | UI + calc |
| S3 | **Management hires** — HQ pool vs team direct | UI + calc |
| S4 | **Space / utilities / facilities** — categorized overhead lines | UI + calc |
| S5 | **Software purchases** — extend v1 lines (name, CapEx vs OpEx) | UI + calc |
| S6 | **Expected revenue / fixed fee** per new team (working-model aware) | UI + calc |
| S7 | **Results** — company + team simulated P&L (pre/post tax, break-even) | UI + calc |
| S8 | **Saved scenarios list** — load, clone, delete | UI |
| S9 | **Compare two saved scenarios** (summary KPIs) | UI (P1 if timeboxed) |

**Out of scope v2:** Apply/Implement (create real Team, expenses), approval workflow, PDF export, AI narrative.

---

## 2. Data model

### 2.1 Table `finance_planning_scenarios`

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `name` | string(120) | Unique per org optional; warn on duplicate |
| `description` | text nullable | |
| `scenario_type` | enum | `expansion`, `downsize`, `what_if` |
| `status` | enum | `draft`, `approved`, `archived` — default `draft` |
| `baseline_as_of` | date | Snapshot date used when created/last refreshed |
| `payload` | JSONB | Full worksheet (see §3) |
| `created_by_user_id` | FK users | Audit |
| `updated_by_user_id` | FK users | |
| `created_at` / `updated_at` | timestamps | |

**Payload is source of truth** for lines; no normalized child tables in v2 (keeps iteration fast). Version field inside payload: `schema_version: 2`.

### 2.2 ACL

Same module as Finance dashboard: `financial_planning` **read** for list/get; **write** for create/update/delete.  
Activity log: `finance_planning_scenario.created|updated|deleted`.

---

## 3. Payload schema (`schema_version: 2`)

```json
{
  "schema_version": 2,
  "overhead": {
    "extra_hq_salary_monthly": 0,
    "extra_shared_opex_monthly": 0,
    "extra_shared_capex_monthly": 0,
    "opex_yearly": false,
    "capex_yearly": false
  },
  "new_teams": [
    {
      "id": "new_abc",
      "name": "IoT Delivery",
      "working_model_code": "retainer",
      "revenue_mode": "fixed_fee",
      "fixed_fee_amount": 500000,
      "fixed_fee_period": "monthly",
      "expected_monthly_revenue": 500000,
      "expected_monthly_cost": 120000,
      "delivery_headcount": 5,
      "salary_monthly_each": 80000,
      "billable": true
    }
  ],
  "management_hires": [
    {
      "id": "mgr_1",
      "label": "Delivery Manager",
      "headcount": 1,
      "salary_monthly_each": 150000,
      "attribution": "hq",
      "team_id": null
    }
  ],
  "facility_lines": [
    {
      "id": "fac_1",
      "category": "rent",
      "label": "Extra floor",
      "amount_monthly": 250000,
      "yearly": false,
      "attribution": "hq"
    }
  ],
  "expansion": {
    "hires": [],
    "software": []
  }
}
```

**Attribution:** `hq` → overhead pool; `team` → `team_id` (existing UUID or `new_*` id).

**Working model codes:** `project_based`, `time_materials`, `retainer`, `overheads` (enum parity).

**Revenue modes:** `fixed_fee` (normalize via billing period), `expected_revenue` (flat monthly INR), `pipeline` (optional: `pipeline_monthly`, `win_rate_percent`).

---

## 4. Calculation methodology (lock with Finance)

Reuse v1 engine in `financeScenarios.ts`; extend:

### 4.1 Baseline

From `GET /finance/dashboard` (same as v1 panel): `overhead_pool`, `billable_fte`, `cpr`, `company_operating`, `corporate_tax_percent`, `by_team[]`.

### 4.2 New teams

For each `new_teams` row:

- `direct_delta` = headcount × salary_monthly_each + team-attributed software + team-attributed facility  
- `billable_fte_delta` = billable ? headcount : 0  
- `revenue` = from working model (see brainstorm §2.2)  
- `estimated_cost` = `expected_monthly_cost` or default 0  
- Append to simulated team list with synthetic `team_id`

### 4.3 Management hires

- `attribution === 'hq'` → add to `extra_hq_salary_monthly` (or dedicated mgmt pool field summed into pool)  
- `attribution === 'team'` → add to that team’s direct salary delta (no billable FTE unless flagged)

### 4.4 Facility lines

- `hq` → add to shared OpEx monthly (utilities/rent) or CapEx if category `capex`  
- `team` → team OpEx delta

### 4.5 Pool, CPR, allocation

Same as v1:

```
pool = baseline.pool + overhead extras + hq mgmt + hq facilities + hq software
fte = baseline.billable_fte + extra billable from hires + new teams
cpr = pool / fte (0 if fte=0)
team allocated OH = cpr × team billable FTE (simulated)
team operating = simulated direct + allocated OH
team net = revenue - estimated_cost - operating
after_tax = net × (1 - tax%)
```

### 4.6 Company rollup

```
company_simulated_operating = baseline.company_operating
  + sum(direct deltas on all teams)
  + (pool - baseline.pool)
```

Do **not** add allocated OH again at company level (already in team directs + pool mechanics).

### 4.7 Parity tests

Extend `tests/test_finance_scenario_formulas.py` with Python mirrors for new-team, mgmt, and facility lines. CI must keep TS/Python aligned.

---

## 5. API

| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/v1/finance/planning-scenarios` | List (filter status, type) |
| POST | `/api/v1/finance/planning-scenarios` | Create; embed payload |
| GET | `/api/v1/finance/planning-scenarios/{id}` | |
| PATCH | `/api/v1/finance/planning-scenarios/{id}` | Partial name/status/payload |
| DELETE | `/api/v1/finance/planning-scenarios/{id}` | Soft-delete optional; hard OK for v2 |
| POST | `/api/v1/finance/planning-scenarios/{id}/clone` | New row, name suffix “(copy)” |

Optional compute-only endpoint (no persist):

| POST | `/api/v1/finance/planning-scenarios/compute` | payload + optional `as_of` → returns `ScenarioResult` JSON |

Frontend may keep client-side compute for snappy UX; API compute for audit/regression.

---

## 6. UI (`FinanceScenariosPanel` + helpers)

| Area | Change |
|------|--------|
| Sub-nav | Workbench \| Saved |
| New teams | Add row dialog: name, working model select (from `/working-models`), revenue fields, headcount, salary, billable |
| Management | Table: label, count, salary, HQ vs team select |
| Facilities | Table: category, label, amount, yearly toggle, HQ vs team |
| Software | Add `expense_kind`: `opex` \| `capex` |
| Actions | Save, Save as new, Load, Clone, Delete |
| Stale baseline | Banner if `baseline_as_of` < today |

Fetch working models: existing `GET /api/v1/working-models` (active only).

---

## 7. Dev file map

| Layer | Files (new or extend) |
|-------|----------------------|
| Model | `app/models/finance.py` — `FinancePlanningScenario` |
| Migration | `app/db/phase*.py` or alembic per project convention |
| Schema | `app/schemas/finance.py` |
| Service | `app/services/finance/planning_scenario_service.py` |
| API | `app/api/v1/finance.py` |
| Frontend utils | `frontend/src/utils/financeScenarios.ts` |
| Frontend UI | `frontend/src/components/finance/FinanceScenariosPanel.tsx` |
| Tests | `tests/test_finance_planning_scenarios.py`, extend `tests/test_finance_scenario_formulas.py` |

---

## 8. Acceptance criteria (Development done)

- [ ] Create scenario with new team + mgmt + facility lines; reload persists  
- [ ] Simulated CPR and team margins match formula doc §4  
- [ ] Saved scenario does not alter Overview / Team P&L / Annual Plan  
- [ ] ACL: designer 403; finance role 200  
- [ ] Activity rows on create/update/delete  
- [ ] Frontend build + pytest green  

---

## Related

- Brainstorm: `finance-scenarios-planning-v2-brainstorm.md`  
- UAT: `finance-scenarios-planning-v2-uat-checklist.md`  
- v1 implementation: `FinanceScenariosPanel.tsx`, `financeScenarios.ts`
