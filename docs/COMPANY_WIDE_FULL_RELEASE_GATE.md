# ProTrack — Company-Wide Full Release Gate

**Purpose:** Full company deployment (not a pilot). Every department uses ProTrack for its live workstreams.  
**Date opened:** 2026-07-22  
**Release type:** Company-wide GA  
**UAT / UVT:** User Acceptance Testing (final gate before production cutover)

---

## Process overview (mandatory sequence)

```text
① Department Heads smoke        → capture bugs / improvements
② Development                   → fix & document in CHANGELOG / PR
③ Testing team                  → feature-by-feature inspection
④ QC team                       → audit + sign-off (GO / NO-GO)
⑤ Dept UAT (2 people / dept)    → live-path validation
⑥ If any fail                   → back to ② → ③ → ④ → ⑤
⑦ QC final GO                   → UAT / UVT complete → Deploy
```

**Rule:** No stage may be skipped. QC must sign off before department UAT. Department UAT failures reopen Testing → QC.

---

## Gate 0 — Pre-conditions (DevOps / Admin)

| # | Check | Owner | Pass? |
|---|--------|-------|-------|
| 0.1 | API health on deploy host (`/health` via localhost, not SPA rewrite) | DevOps | ☐ |
| 0.2 | `.\scripts\check_release_health.ps1 -BaseUrl <host>` → `RESULT: PASS` | DevOps | ☐ |
| 0.3 | Latest `frontend/dist` published | Dev | ☐ |
| 0.4 | Help Desk category routing configured (HR / Admin / IT / Facility / Other) | Admin | ☐ |
| 0.5 | Seed accounts available for each persona below | Admin | ☐ |
| 0.6 | Responsive shell: hamburger nav works &lt; 900px width | Testing | ☐ |

---

## Gate 1 — Department Heads kickoff (feature ownership)

**Goal:** Each head exercises their department’s features and files findings for Development.  
**Duration:** 1–2 business days.  
**Output:** Completed sheets in [Appendix A](#appendix-a--department-head-findings) (one per department).

### Who must attend / assign testers

| Department | Head (or delegate) | Primary persona(s) |
|------------|--------------------|--------------------|
| Engineering / Design | Eng. Manager / Design Leader | EM, DL, Designer |
| Human Resources | Director of HR / HR Manager | HR, Office Admin |
| Administration / Facilities | Office Administrator | Office Admin |
| IT | IT Manager / Admin | Admin, IT agent |
| Accounts / Finance | Accounts / Finance lead | EM/Exec with finance access |
| Executive | MD / Director | Executive (no System Admin) |

### Kickoff agenda (60–90 min)

1. Confirm this is **full release**, not pilot — data and workflows are production-bound.
2. Walk Gate 0 health (login must work).
3. Assign each head their **smoke checklist** (below).
4. Collect bugs with severity using [Appendix B](#appendix-b--bug--improvement-report-to-development).
5. Development receives the batch → Gate 2.

---

## Gate 1 smoke checklists (by department)

### A. Engineering Operations (Design / EM / DL)

| ID | Feature | Path | Pass criteria |
|----|---------|------|---------------|
| E1 | Login + Dashboard | `/login` → `/dashboard` | KPIs/widgets load; no error boundary |
| E2 | Projects list + workspace | `/projects`, `/projects/:id` | Open project; milestones/timesheet tab visible |
| E3 | Create / edit project (EM/DL) | Projects | Save succeeds; appears in list |
| E4 | Timesheet entry + submit | `/timesheets` | Draft → submit; hours persist |
| E5 | Timesheet approve (DL/EM) | `/timesheets` | Approve/reject works |
| E6 | Workload | `/workload` | Heatmap loads for team |
| E7 | Resource Planning (EM) | `/resource-planning` | Timeline loads; panels usable |
| E8 | Calendar | `/calendar` | Gantt/calendar renders |
| E9 | Planning Board (room) | `/planning-board` | Wall view; no ops leakage |
| E10 | Help Desk create | `/help-desk` | Ticket created; number shown |
| E11 | Responsive (&lt; md) | any | Hamburger opens nav; content usable |

### B. Human Resources

| ID | Feature | Path | Pass criteria |
|----|---------|------|---------------|
| H1 | HR Dashboard | `/hr` | Teams + attention list; link to Onboarding |
| H2 | Start onboarding | `/hr/onboarding` | Create with dept/team/role/manager |
| H3 | Auto-routing | Onboarding + Help Desk | 4 dept tickets (HR/Admin/IT/Accounts); manager items owned by manager |
| H4 | Complete checklist items | Onboarding detail | Done/N/A updates progress |
| H5 | My items filter | Onboarding | Filters to user’s pending work |
| H6 | Timesheet chase (no own entry) | `/timesheets` | Can view compliance; cannot enter own if HR-only |
| H7 | Performance | `/performance` | Page loads for HR role |
| H8 | Org chart (if entitled) | `/organization` | Chart loads |
| H9 | Help Desk HR queue | `/help-desk` | HR category tickets visible to HR agent |

### C. Administration / Facilities

| ID | Feature | Path | Pass criteria |
|----|---------|------|---------------|
| A1 | Help Desk Admin/Facility | `/help-desk` | Category create + agent queue |
| A2 | Onboarding Admin items | `/hr/onboarding` (if access) or via ticket | Admin section items / ticket actionable |
| A3 | Holidays (Admin) | `/admin/...` holidays | Calendar view/edit (Admin) |

### D. IT

| ID | Feature | Path | Pass criteria |
|----|---------|------|---------------|
| I1 | Ticket routing config | `/admin/ticket-routing` | Set contact per category; save |
| I2 | IT queue | `/help-desk` | IT tickets assignable/closable |
| I3 | Onboarding IT ticket | Auto from hire | Workstation/email tasks listed |
| I4 | System health / diagnostics | Admin audit | Health page loads (Admin) |

### E. Accounts / Finance

| ID | Feature | Path | Pass criteria |
|----|---------|------|---------------|
| F1 | Financial Planning | `/finance` | Dashboard opens for entitled roles |
| F2 | Quotes / costs (as entitled) | Finance tabs | Create/view without 403 |
| F3 | Onboarding Accounts ticket | Help Desk | Payroll/docs tasks listed |
| F4 | Designer blocked | `/finance` as Designer | No nav + API 403 |

### F. Executive

| ID | Feature | Path | Pass criteria |
|----|---------|------|---------------|
| X1 | Cross-section visibility | Dashboard, Finance, HR, Analytics | Sees modules; **no** System Administration |
| X2 | Approvals / oversight | Timesheets / Finance | Can view; no day-to-day CRUD required |

### G. System Administration (Admin only)

| ID | Feature | Path | Pass criteria |
|----|---------|------|---------------|
| S1 | Users / roles / teams | `/admin/users` etc. | Create user; assign role + modules |
| S2 | Ticket routing | `/admin/ticket-routing` | Config persists |
| S3 | Imports / settings / audit | Admin hubs | Spot-check open without error |

---

## Gate 2 — Development

**Input:** Appendix B reports from department heads.  
**Actions:**
1. Triage: Blocker / Major / Minor / Improvement.
2. Fix Blockers + Majors before Testing; Minors by agreement.
3. Automated regression: at minimum  
   `pytest tests/test_onboarding.py tests/test_responsive_shell.py tests/test_nav_active_match.py`  
   plus any suite covering the fixed area.
4. Rebuild `frontend/dist`; restart API on deploy host.
5. Hand to Testing with: list of tickets fixed, known deferred items, build/commit id.

**Dev exit criteria:** No open Blockers; Majors fixed or accepted by QC with documented waiver.

---

## Gate 3 — Testing team (thorough inspection)

**Method:** Walk **every** feature ID in Gate 1 checklists (A–G), not only “happy path.”  
**Also verify:**

| Area | Inspection |
|------|------------|
| Auth | Wrong password message; forced password change if enabled |
| Permissions | Designer cannot create onboarding / finance / admin |
| Help Desk | Routing contact receives category tickets |
| Onboarding | Delete checklist does **not** delete Help Desk tickets |
| Responsive | 1366×768 @ 100%/125%/150%; &lt;900px hamburger |
| Regression | Projects, Timesheets, Reports after recent HR/shell changes |

**Output:** Testing sign-off sheet ([Appendix C](#appendix-c--testing-sign-off)) → QC.

---

## Gate 4 — QC audit & deployment readiness

QC confirms:

- [ ] Gate 0 health PASS on production/staging host  
- [ ] Testing Appendix C complete; no open Blockers  
- [ ] Security: role/module gates spot-checked (Designer / HR / EM / Admin)  
- [ ] Data: onboarding + tickets integrity; soft-delete paths intact  
- [ ] UX: responsive shell + primary flows usable on standard laptops  
- [ ] Known limitations documented (Leave = GreytHR; Future Modules disabled; Finance AI placeholders)  
- [ ] **QC SIGN-OFF: Ready for department UAT** — Name ______ Date ______  

**If NO-GO:** return to Gate 2 with defect list. Do not start Gate 5.

---

## Gate 5 — Department UAT (2 people per department)

| Department | Tester 1 | Tester 2 | Features in scope | Result |
|------------|----------|----------|-------------------|--------|
| Engineering / Design | | | E1–E11 | ☐ Pass ☐ Fail |
| Human Resources | | | H1–H9 | ☐ Pass ☐ Fail |
| Administration | | | A1–A3 | ☐ Pass ☐ Fail |
| IT | | | I1–I4 | ☐ Pass ☐ Fail |
| Accounts / Finance | | | F1–F4 | ☐ Pass ☐ Fail |
| Executive (optional) | | | X1–X2 | ☐ Pass ☐ Fail |

**Fail rule:** Any Blocker or Major → file Appendix B → Gate 2 → Gate 3 → Gate 4 → re-run **failed department’s** Gate 5 (and any overlapping areas Testing flags).

**Pass rule:** All assigned departments Pass → proceed to final UAT/UVT cutover checklist.

---

## Gate 6 — Final UAT / UVT & deploy

| # | Item | Owner | Pass? |
|---|------|-------|-------|
| U1 | All Gate 5 departments Pass | Release manager | ☐ |
| U2 | QC reconfirms no reopen Blockers | QC | ☐ |
| U3 | Production health script PASS | DevOps | ☐ |
| U4 | Comms sent to all departments (go-live date, support channel, Help Desk) | Release manager | ☐ |
| U5 | Rollback plan documented (previous `dist` + API tag) | DevOps | ☐ |
| U6 | **GO LIVE** | MD / Release sponsor | ☐ |

---

## Known deferred (do not treat as release blockers)

| Item | Status |
|------|--------|
| Leave / attendance in ProTrack | Deferred — GreytHR |
| Future Modules (Customer Portal, Sales, Procurement, …) | Placeholder only |
| Bulk admin imports “Coming Soon” | Hidden |
| Finance AI forecast | Placeholder / non-live |
| Knowledge Base nav stub vs `/knowledge` reports page | Documented; not a GA blocker |

---

## Appendix A — Department head findings

| Dept | Head | Date | Feature IDs tested | Bugs filed (#) | Improvements (#) | Ready for Dev? |
|------|------|------|--------------------|----------------|------------------|----------------|
| | | | | | | ☐ |

---

## Appendix B — Bug / improvement report to Development

| Field | Value |
|-------|-------|
| ID | BUG-YYYYMMDD-## |
| Reporter / Dept | |
| Severity | Blocker / Major / Minor / Improvement |
| Feature ID | e.g. H3 |
| Steps to reproduce | |
| Expected | |
| Actual | |
| Screenshot / ticket # | |
| Environment | URL, browser, zoom %, screen size |
| Dev fix commit / PR | |
| Testing verified | ☐ |

---

## Appendix C — Testing sign-off

| Suite | Tester | Date | Result |
|-------|--------|------|--------|
| Engineering (E*) | | | ☐ Pass ☐ Fail |
| HR (H*) | | | ☐ Pass ☐ Fail |
| Admin/IT/Accounts/Exec (A/I/F/X/S*) | | | ☐ Pass ☐ Fail |
| Responsive matrix | | | ☐ Pass ☐ Fail |
| **Overall Testing GO** | | | ☐ |

---

## Appendix D — QC deployment certificate

> We confirm ProTrack has completed Gates 0–4, department UAT (Gate 5) has passed (or is authorized to begin), and the build identified below is approved for company-wide deployment subject to Gate 6.

| Field | Value |
|-------|-------|
| Build / commit | |
| Deploy host | |
| QC lead | |
| Date | |
| Decision | ☐ GO for Dept UAT · ☐ GO for Production · ☐ NO-GO |

Signature: ______________________
