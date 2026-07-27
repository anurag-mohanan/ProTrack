# Finance Scenarios / Planning v2 — Leadership Brainstorm

**Status:** Gate 0 input — workshop transferred to Development  
**Date:** 2026-07-27  
**Participants (represented):** Head of Finance · CEO · Senior Finance Consultant · Head of Engineering · CTO (observer)

**v1 shipped (client-only):** Finance tab **Scenarios / Planning** — overhead pool deltas, hire lines on existing teams, software lines, CPR reallocation, break-even hints. Draft saved in browser `localStorage` only; does not change live books.

**v2 goal:** Model **new delivery teams** and full expansion economics (people, management, space, software, working model, revenue/fixed fee), **persist scenarios** for board / later implementation, and keep simulation strictly separate from live P&L until an explicit “apply” workflow (future phase).

---

## 1. Problem (why v2)

| Stakeholder | Pain today | Desired outcome |
|-------------|------------|-----------------|
| **Head of Finance** | Board asks “what if we stand up a new IoT team?” — rebuilt in Excel each time | One worksheet: headcount, mgmt layer, rent, tools, fee model → margin & CPR impact |
| **CEO** | Cannot compare 2–3 expansion options side-by-side with consistent tax and overhead rules | Named scenarios (Base / Stretch / Conservative) saved and reopened |
| **Senior Finance Consultant** | v1 only tweaks **existing** teams; no working-model-driven revenue | Revenue driver tied to `retainer` vs `project_based` vs `time_materials`; fixed fee vs pipeline assumptions explicit |
| **Head of Engineering** | Hiring plan ignores billable FTE → CPR drift | Billable vs non-billable hires; mgmt hires flagged for HQ pool |
| **CTO** | Must not corrupt production finance data | Persist scenario JSON in DB; **no** auto-create Team/Expense without approved apply flow |

---

## 2. Workshop decisions (consensus)

### 2.1 Scenario worksheet structure

Each saved scenario is a **snapshot + deltas** against a chosen **baseline as-of date** (default: today’s Finance Overview).

| Block | Fields | Notes |
|-------|--------|-------|
| **Header** | Name, description, scenario type (`expansion` / `downsize` / `what_if`), status (`draft` / `approved` / `archived`), baseline `as_of` | Status for workflow only; v2 does not enforce approval gates in code |
| **New team** (0–N rows) | Proposed name, working model, expected monthly revenue **or** fixed fee + billing period, delivery headcount, avg salary, billable flag | Hypothetical `team_id` = `new_*` until apply |
| **Management hires** | Count, role label, monthly salary each, attach to **new team** or **HQ/Corporate** | HQ mgmt → overhead pool; team-attached mgmt → team direct Op Cost (align with live Management team rules) |
| **Space & utilities** | Category (`rent` / `utilities` / `facilities` / `other`), monthly or yearly amount, assign **HQ shared** vs **team-specific** | Shared → pool; team → team OpEx |
| **Software** | Name, monthly/yearly cost, team assignment | Same as v1 software lines |
| **Existing team tweaks** | Optional hire/software lines on current teams (v1 behaviour retained) | |
| **Overhead pool tweak** | Extra HQ salary, shared OpEx, shared CapEx (v1) | Yearly ÷ 12 toggle kept |

### 2.2 Working model → revenue driver (Finance + Consultant lock)

Uses existing `WorkingModelCode` values:

| Code | Scenario revenue input | Cost side |
|------|------------------------|-----------|
| `retainer` | **Fixed fee** + period (monthly / quarterly / annual → normalized monthly INR) | Delivery salaries + software + allocated CPR |
| `project_based` | **Expected monthly revenue** (awards-style) **or** quote pipeline assumption with win-rate % (stretch) | Include **estimated delivery cost** % or flat per head |
| `time_materials` | Expected billable hours × blended rate **or** flat expected monthly revenue | Same as project_based |
| `overheads` | Revenue = 0 (internal) | Full cost to company / HQ |

**CEO preference:** Default UI shows **one primary revenue number** per new team (“Expected monthly revenue INR”) with an **Advanced** expander for fee period, win-rate, and hours×rate.

### 2.3 Management & overhead treatment (no double-count)

| Spend type | Pool | Team P&L |
|------------|------|----------|
| Delivery hire (billable) | — | Direct salary; increases billable FTE → higher allocated OH |
| Delivery hire (non-billable) | — | Direct salary; no FTE bump |
| Management hire on **Corporate/Management** | HQ salary in pool | Corporate team excluded from delivery ranking |
| Management hire **assigned to new delivery team** | — | Team direct; consultant flagged “mgmt” for reporting only |
| Shared rent / utilities | HQ OpEx in pool | — |
| Team-dedicated space | — | Team OpEx |
| Team software | — | Team OpEx/CapEx by category |
| Corporate software | HQ CapEx/OpEx in pool | — |

Align with live rules documented in `RC5_FINANCE_OVERHEADS_PNL.md` and CPR allocation tests.

### 2.4 Save, compare, implement later

| Action | v2 scope | Later (v3) |
|--------|----------|------------|
| **Save scenario** | `POST/GET/PATCH/DELETE` API; list on Scenarios tab | |
| **Compare 2 scenarios** | Side-by-side summary KPIs (company Op Cost, net, after-tax) | Full Anaplan-style grid |
| **Clone scenario** | Duplicate JSON under new name | |
| **Implement / Apply** | **Out of scope v2** — button disabled with tooltip “Creates Team, commercial terms, expense stubs — requires approval workflow” | HR + Finance sign-off |
| **Link to Annual Plan** | Optional “Export summary to plan notes” (copy-only) | Auto-seed plan lines |

### 2.5 Additional ideas from the room (prioritized)

| Priority | Idea | Owner |
|----------|------|-------|
| **P0** | Persisted scenarios with audit (who created, when) | Dev |
| **P0** | New-team block with working model + revenue/fixed fee | Dev |
| **P0** | Management hire line type (HQ vs team) | Dev |
| **P0** | Space/utilities categorized overhead lines | Dev |
| **P1** | Scenario compare (pick 2 saved) | Dev |
| **P1** | Sensitivity slider: salary ±10%, revenue ±10% | Dev |
| **P1** | “Time to break-even” months given ramp curve | Finance spec follow-up |
| **P2** | PDF board pack per scenario | Backlog |
| **P2** | Approval workflow + Apply → create Team | v3 |
| **P2** | AI narrative (“margin compresses because CPR rises 12%”) | R5 AI |

---

## 3. UX sketch (Finance cockpit)

1. **Scenarios / Planning** tab (existing) gains sub-views: **Workbench** (v1 + v2 fields) · **Saved scenarios** (table).  
2. Workbench sections: **Baseline** (read-only chips from Overview) · **New teams** · **Management** · **Space & utilities** · **Software** · **Existing team expansion** (v1) · **HQ pool extras** (v1).  
3. **Save scenario** → name dialog; stores server-side.  
4. **Load scenario** → replaces workbench; baseline re-fetched from current Overview (warn if `as_of` stale).  
5. Results: company KPI row + per-team table (current vs simulated, Δ Op Cost, Δ net, after-tax, break-even revenue).

---

## 4. Non-goals (explicit)

- Changing live Team P&L, expenses, or Annual Plan without explicit Apply (v3).  
- GL, invoicing, or payroll integration.  
- Multi-entity consolidation.  
- Automatic FX for hypothetical foreign fees (INR only in v2; currency field backlog).

---

## 5. Pipeline handoff

| Gate | Artifact | Audience |
|------|----------|----------|
| **0** | `finance-scenarios-planning-v2-decisions.md` | Development |
| **1** | Implementation + `tests/test_finance_scenario_formulas.py` extended + API tests | Development |
| **2** | Automated test matrix | Testing team |
| **3** | QC audit checklist | QC |
| **4** | Peer dual-user debug | Finance + Ops |
| **5** | UAT / UVT sign-off | Head of Finance + CEO delegate |

See `finance-scenarios-planning-v2-uat-checklist.md`.

---

## Related

- v1 formulas: `frontend/src/utils/financeScenarios.ts`, `tests/test_finance_scenario_formulas.py`  
- FP&A Phase A: `RC5_FINANCE_PLANNING_FPA_IMPROVEMENT.md`  
- Overheads / CPR: `RC5_FINANCE_OVERHEADS_PNL.md`  
- Working models: `app/models/enums.py` (`WorkingModelCode`)
