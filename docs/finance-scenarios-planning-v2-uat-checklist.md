# Finance Scenarios / Planning v2 — Testing · QC · UAT

**Decisions:** `finance-scenarios-planning-v2-decisions.md`  
**Brainstorm:** `finance-scenarios-planning-v2-brainstorm.md`  

**Pipeline:** Leadership brainstorm → **Development** → **Testing** → **QC audit** → Peer debug → **UAT/UVT**

---

## Gate 1 — Development complete

Developer self-check before handoff to Testing:

- [ ] DB model + migration applied cleanly on fresh and existing DB  
- [ ] API CRUD + clone + (optional) compute endpoint  
- [ ] UI: Workbench sections + Saved list + Save/Load/Clone/Delete  
- [ ] `financeScenarios.ts` v2 calc + Python parity tests  
- [ ] No writes to `teams`, `expenses`, `annual_plan` from scenario actions  
- [ ] `frontend/dist` rebuilt if production serves static bundle  

**Dev sign-off:** ________  **Date:** ________

---

## Gate 2 — Testing (automated)

### 2.1 New test modules

- [ ] `tests/test_finance_planning_scenarios.py` — API CRUD, ACL, activity log  
- [ ] `tests/test_finance_scenario_formulas.py` — extended v2 cases:
  - [ ] New team (retainer fixed fee monthly)  
  - [ ] New team (project_based expected revenue + estimated cost)  
  - [ ] Management hire HQ → pool / CPR rise  
  - [ ] Management hire team → team direct only  
  - [ ] Facility HQ rent → pool  
  - [ ] Facility team → team OpEx  
  - [ ] Combined scenario (new team + v1 existing-team hire)  
  - [ ] Corporate tax 30% and 0% on after-tax columns  
  - [ ] `fte=0` edge → CPR = 0, no divide error  

### 2.2 Regression (must stay green)

- [ ] `tests/test_finance_corporate_tax.py`  
- [ ] `tests/test_finance_month_awards_pnl.py`  
- [ ] `tests/test_finance_cpr_allocation.py`  
- [ ] `tests/test_finance_overhead_capex_pool.py`  
- [ ] `tests/test_finance_plan_vs_actual.py`  
- [ ] Annual Plan edit, seed, clone  

**Testing sign-off:** ________  **Date:** ________

---

## Gate 3 — QC audit

### 3.1 Data integrity & security

- [ ] Scenario payload cannot inject SQL (JSONB only)  
- [ ] Finance ACL on all planning-scenario routes  
- [ ] Activity audit: create/update/delete attributable to user  
- [ ] Delete scenario does not delete unrelated finance data  
- [ ] Saved scenario load does not mutate live dashboard aggregates  

### 3.2 Formula audit (no double-count)

- [ ] HQ management + shared facilities increase **pool** only once  
- [ ] Team-assigned spend in **direct** only; allocated OH via CPR × FTE  
- [ ] Company simulated Op Cost formula matches decisions doc §4.6  
- [ ] Customer pass-through expenses still excluded from company Op Cost (unchanged)  
- [ ] Corporate / overhead-home team excluded from delivery ranking table  

### 3.3 UX / docs

- [ ] Tab label and help text state **simulation only** until Apply (v3)  
- [ ] Working model dropdown matches live Working Models admin  
- [ ] Stale baseline warning when `baseline_as_of` ≠ current month  
- [ ] Brainstorm + decisions docs match shipped UI fields  

**QC sign-off:** ________  **Date:** ________

---

## Gate 4 — Peer debug (dual user)

| Step | Finance user A | Finance user B / Ops | Pass? |
|------|----------------|----------------------|-------|
| 1 | Create “New IoT team” scenario: 5 billable, retainer fee | B opens Saved list, sees scenario | |
| 2 | Add HQ mgmt hire + extra rent | Simulated CPR increases; company Δ Op Cost shown | |
| 3 | Add team software (OpEx) on new team | Team direct ↑; break-even revenue updates | |
| 4 | Save, logout, login, reload | Worksheet restores | |
| 5 | Open Overview Team P&L | **No change** vs before scenario | |
| 6 | Clone scenario, edit name | Independent copy | |
| 7 | Delete scenario | Removed from list; no DB orphans | |

---

## Gate 5 — UAT / UVT (business acceptance)

**Participants:** Head of Finance (primary) · CEO or delegate · Senior Finance Consultant  

### 5.1 Happy paths

1. Model standing up a **new delivery team** with working model **retainer** and fixed monthly fee — verify margin and after-tax net.  
2. Same team under **project_based** with expected monthly revenue instead of fixed fee.  
3. Add **2 management hires** (1 HQ, 1 on team) — verify HQ affects CPR for all delivery teams.  
4. Add **space rent** (HQ) and **utilities** (team) — verify pool vs team split.  
5. **Save** scenario, return next week, **load** and adjust headcount — confirm persistence.  
6. Compare v1 behaviour: hire on **existing** team still works alongside new team block.  

### 5.2 Edge / negative

7. Zero billable FTE company-wide scenario — no crash; CPR shows 0.  
8. User without `financial_planning` — cannot access Scenarios tab or API.  
9. Hard refresh / new browser — Saved scenarios still available (server-side).  

### 5.3 Explicit non-requirements (confirm NOT expected in v2)

10. **Implement** button does not create Team or expenses.  
11. Annual Plan lines do not auto-update from scenario.  
12. Live Overview revenue still = actual month awards + retainer (not scenario).  

**UAT/UVT result:** GO / NO-GO  

**Sign-off:** ________  **Date:** ________

---

## Release note snippet (post-UAT)

- Finance → **Scenarios / Planning** v2: model new teams, management hires, facilities, software; working-model-based revenue; **save scenarios** to server for later review. Simulation does not change live books.

**Deploy:** restart API, rebuild `frontend/dist`, hard refresh browser.
