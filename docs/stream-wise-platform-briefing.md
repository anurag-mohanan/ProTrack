# Stream-wise projects — engineering service platform briefing

**Status:** Proposal for leadership alignment → Development → Testing → QC → UVT/UAT  
**Date:** 2026-08-04  
**Owner (product):** Operations + Engineering (joint)  
**Platform context:** ProTrack today is strong on mold delivery teams; Streams already exist in data (`Project.stream_id`, task types, skill matrices, numbering) but product UX still reads as a single mold-centric command center.

---

## 1. Decision asked of leadership

Treat ProTrack as a **company-wide engineering services platform** organized primarily by **Stream** (business line), with Teams remaining the delivery / capacity unit inside each stream.

Proposed initial streams (illustrative — finalize with Ops/Eng):

| Stream | Intent |
|--------|--------|
| Mold Design | Current core (tooling, surfacing, design review) |
| CAD Development | Upcoming CAD / product design / digital engineering work |
| *(future)* | Additional fields as Prosohm expands (e.g. CAM, inspection, consulting) |

**Ask:** Approve the stream-first product model and a gated delivery plan below before UVT/UAT.

---

## 2. Stakeholder perspectives

### Head of Operations
- Needs **one portfolio view per stream** (load, WIP, delays) without mixing mold KPIs with CAD WIP.
- Resource moves across streams must stay visible (cross-stream support), not invisible “borrowed” hours.
- Customer packs / exports should be labelable by stream so client reporting stays clean.
- Careful cutover: existing mold projects must not break numbering, templates, or timesheets.

### Head of Engineering
- Task types, milestones, skill matrices, and templates are **stream-owned**, not global one-size-fits-all.
- Designers may work mostly in one stream but occasionally support another — same transfer / membership dating rules should apply at stream attribution where relevant.
- CAD stream will need different task taxonomy and possibly different project stages than mold.
- Avoid forcing mold stage language (“tool number”, “BOM”) onto CAD projects in UI copy and required fields.

### CEO
- Narrative shift: Prosohm is an **engineering services company**, not only a mold shop — the system should reflect that in navigation, reports, and board metrics.
- Stream P&L and utilization become comparable units for growth decisions (open CAD without diluting mold metrics).
- Low-risk path: reuse existing Stream entity; do not invent a parallel hierarchy.

---

## 3. Current state (what already exists)

- **Stream** master data with optional project prefix / numbering.
- **Projects** already carry `stream_id` (nullable).
- **Task types** and **stream skills** are stream-scoped.
- Projects UI still groups primarily **by team**; stream is a form field / filter, not a first-class navigation axis.
- Seed / templates heavily biased to **Mold Design**.

Implication: this is mostly a **product & reporting reframe** plus hardening of stream as a required, first-class dimension — not a greenfield rebuild.

---

## 4. Recommended product model

```
Company (tenant)
 └── Stream (Mold | CAD | …)     ← primary portfolio / KPI axis
      └── Team(s)                ← capacity & membership (existing)
           └── Project           ← always has stream_id (required going forward)
                └── Timesheets / milestones / docs
```

**Rules of thumb**
1. Every new project **must** have a stream.
2. Default project list / command center: **group or tab by Stream**, then by Team.
3. Reports & Excel names already use `Prosohm_<Subject>_<Month>_<Year>` — extend subject to include stream when scoped (e.g. `Prosohm_CAD_Development_July_2026`).
4. Cross-stream hours (person’s home stream ≠ project stream) surface like today’s cross-team support badges.
5. Templates, task types, and skill matrices stay stream-specific; no silent reuse of mold templates on CAD.

---

## 5. Ideas for the development team (phased)

### Phase A — Foundation (UVT candidate)
- Make `stream_id` required on project create; backfill existing projects to Mold Design where null.
- Projects command center: **Stream tabs / sections** (Mold | CAD | All), keep team grouping inside.
- Filters: stream sticky in URL; remember last stream per user.
- Soften mold-only labels when stream ≠ Mold (tool number optional / “Reference code”).
- Seed CAD Development stream + starter task types (no fake projects in prod without Ops sign-off).

### Phase B — Operating model
- Stream-scoped dashboards (utilization, WIP, leave) with company roll-up toggle.
- Report catalog: stream filter on designer/team timesheets and exports.
- Template picker filtered by stream; block wrong-stream template apply.
- Permissions: stream-level viewers (optional) without granting all teams.

### Phase C — Platform expansion
- Stream-specific workflow stages / milestone packs.
- Quote / commercial terms tagged by stream for P&L.
- Skills matrix UI defaulted to user’s primary stream with multi-stream view for leaders.

**Non-goals for Phase A:** rewriting finance formulas, multi-tenant SaaS branding, or forcing team hierarchy under stream in org chart (teams can remain org-wide with primary stream affinity).

---

## 6. Risks & mitigations

| Risk | Mitigation |
|------|------------|
| Null / wrong `stream_id` on legacy projects | One-time backfill to Mold + audit report before UAT |
| CAD forced into mold fields | Stream-aware field requirements & copy |
| Double-counting hours across stream views | Same membership-dating discipline as teams; clear “home vs support” |
| Report filename / customer pack confusion | Stream token in export names when filtered |
| Scope creep into finance rewrite | Keep Phase A UI + data integrity only |

---

## 7. Gate path (mandatory)

```
Leadership sign-off (Ops + Eng + CEO)
        ↓
Development (Phase A build + unit/API tests)
        ↓
Testing team (functional + regression script)
        ↓
QC team (final audit checklist)
        ↓
UVT / UAT (business acceptance)
        ↓
Production release
```

### Development exit criteria
- [ ] `stream_id` required on create; legacy backfill script + dry-run report
- [ ] Projects UI stream sections/tabs; mold regression unchanged for Eng teams
- [ ] CAD stream seeded; create project in CAD without mold-only hard fails
- [ ] Automated tests for stream filter, backfill, and export naming with stream subject
- [ ] Feature flag or config for “stream tabs” if staged rollout preferred

### Testing team exit criteria
- [ ] Script: create Mold vs CAD project; verify list separation and team grouping
- [ ] Transfer / cross-team cases still correct inside mold; CAD isolated
- [ ] Timesheets All Users + reports still pass prior July attribution cases
- [ ] Export filenames include stream when report scoped to one stream
- [ ] Negative: apply mold template to CAD project blocked or warned

### QC audit exit criteria
- [ ] Data audit: 0 projects with null stream after backfill (or documented exceptions)
- [ ] Copy/UI audit: no mold jargon on CAD create path
- [ ] Access audit: leaders see only permitted streams/teams
- [ ] Traceability: test evidence pack attached for UVT
- [ ] Rollback plan documented (flag off / revert tabs)

### UVT / UAT exit criteria
- [ ] Ops walks portfolio “by stream” and signs load visibility
- [ ] Eng creates sample CAD project end-to-end (tasks, timesheet entry)
- [ ] CEO reviews company roll-up vs stream split narrative
- [ ] Written UAT sign-off before production

---

## 8. Open questions for the leadership meeting

1. Confirm stream list for launch: **Mold Design + CAD Development** only, or more?
2. Are delivery teams **exclusive** to a stream, or shared with a primary stream affinity?
3. Should stream be **required** on users as well as projects?
4. CAD project identifier: separate numbering prefix (e.g. `CAD-####`) vs shared tool number space?
5. Who owns stream master data day-to-day — Ops Admin or Engineering Admin?

---

## 9. Suggested meeting outcome

**Approve Phase A** with Mold + CAD streams, required `stream_id`, stream-first projects UX, and the gate path above. Defer Phase B/C until UAT of Phase A is signed.
