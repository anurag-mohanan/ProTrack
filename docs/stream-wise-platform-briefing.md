# Stream-wise projects — engineering service platform briefing

**Status:** APPROVED for Phase A → Development → Testing → QC → UVT/UAT  
**Approved:** 2026-08-04 (leadership)  
**Owner (product):** Operations + Engineering (joint)  
**Platform context:** ProTrack today is strong on mold delivery teams; Streams already exist in data (`Project.stream_id`, task types, skill matrices, numbering) but product UX still reads as a single mold-centric command center.

---

## 1. Approved decision

Treat ProTrack as a **company-wide engineering services platform** organized primarily by **Stream** (business line), with Teams remaining the delivery / capacity unit inside each stream.

| Stream | Intent |
|--------|--------|
| Mold Design | Current core (tooling, surfacing, design review) |
| CAD Development | Upcoming CAD / product design / digital engineering work |
| *(future)* | Additional fields as Prosohm expands (e.g. CAM, inspection, consulting) |

### Approved addition — relevant stream / team scope per user

Users must be able to **view only projects relevant to them**:

1. **My stream(s)** — projects in streams tied to the user (primary stream and any assigned streams).
2. **My team(s)** — projects on teams they belong to / lead (existing team access).
3. **Leaders / admins** — optional **All streams** / org-wide view when they already have company or multi-team scope.
4. Default for designers and most operators: land on **My stream + My team** filter, not the full company list.

This is a **Phase A requirement**, not deferred to Phase B.

---

## 2. Stakeholder perspectives (aligned)

### Head of Operations
- Portfolio per stream without mixing mold KPIs with CAD WIP.
- Cross-stream support stays visible.
- Cutover must not break mold numbering, templates, or timesheets.
- Staff only see the queues they own (stream/team scope).

### Head of Engineering
- Task types, templates, and skills stay stream-owned.
- CAD taxonomy separate from mold stages / jargon.
- Engineers default to their stream so CAD and mold work do not collide in one list.

### CEO
- Platform narrative: multi-stream engineering services.
- Stream metrics comparable for growth; company roll-up for leadership only.

---

## 3. Current state (what already exists)

- **Stream** master data with optional project prefix / numbering.
- **Projects** already carry `stream_id` (nullable).
- **Task types** and **stream skills** are stream-scoped.
- Team-scoped project access already exists for many roles.
- Projects UI still groups primarily **by team**; stream is a form field / filter, not a first-class navigation axis.
- Seed / templates heavily biased to **Mold Design**.

---

## 4. Approved product model

```
Company (tenant)
 └── Stream (Mold | CAD | …)     ← primary portfolio / KPI axis
      └── Team(s)                ← capacity & membership (existing)
           └── Project           ← always has stream_id (required going forward)
                └── Timesheets / milestones / docs
```

**Rules of thumb**
1. Every new project **must** have a stream.
2. Command center: **Stream tabs / sections**, then Team groups.
3. **Default scope = relevant streams + teams for the signed-in user**; “All” only for entitled roles.
4. Reports / Excel: `Prosohm_<Subject>_<Month>_<Year>` — include stream when scoped.
5. Cross-stream hours surface like today’s cross-team support badges.
6. Templates / task types / skills stay stream-specific.

---

## 5. Development — Phase A (UVT candidate) — APPROVED

- Make `stream_id` required on project create; backfill existing projects to Mold Design where null.
- Projects command center: **Stream tabs / sections** (Mold | CAD | All*), keep team grouping inside.
- **Relevant-scope controls (required):**
  - Toggle / default: **My stream(s)** | **My team(s)** | **All** (All gated by permission).
  - Resolve “my streams” from `User.stream_id` plus any explicit stream assignments (if none, derive from projects/teams the user can already access).
  - Persist preference (last used scope) per user.
- Soften mold-only labels when stream ≠ Mold.
- Seed CAD Development stream + starter task types.
- Export names include stream when report is stream-scoped.
- Automated tests for scope defaults (designer sees only relevant; admin can see All).

\* “All” visible only to roles that already have org-wide / multi-team project access.

### Phase B / C (deferred until Phase A UAT)
- Stream dashboards, stream report catalog filters, stream-level viewer roles, stream-specific stages, stream P&L tagging.

**Non-goals for Phase A:** finance formula rewrite, multi-tenant SaaS branding, forcing org-chart team hierarchy under stream.

---

## 6. Risks & mitigations

| Risk | Mitigation |
|------|------------|
| Null / wrong `stream_id` on legacy projects | Backfill to Mold + audit before UAT |
| CAD forced into mold fields | Stream-aware field requirements & copy |
| Users see other streams’ WIP | Default My stream/team; All permission-gated |
| Double-counting across stream views | Same membership-dating discipline; home vs support |
| Scope creep into finance | Phase A UI + data integrity + access only |

---

## 7. Gate path (APPROVED — Development in progress)

```
Leadership sign-off (Ops + Eng + CEO)     ← DONE 2026-08-04
        ↓
Development (Phase A build + unit/API tests)  ← IN PROGRESS
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
- [x] `stream_id` required on create; legacy backfill script + dry-run report
- [x] Projects UI stream sections/tabs; mold regression unchanged for Eng teams
- [x] **Relevant stream/team scope default; All permission-gated; preference persisted**
- [x] CAD stream seeded; create project in CAD without mold-only hard fails
- [x] Automated tests for stream filter, backfill, user scope defaults, export naming
- [ ] Feature flag for stream tabs if staged rollout preferred

### Testing team exit criteria
- [ ] Script: Mold vs CAD list separation and team grouping
- [ ] Designer (single stream) cannot browse other stream’s full portfolio by default
- [ ] Leader/admin with All can switch to company view
- [ ] Transfer / timesheet attribution regressions still pass
- [ ] Export filenames include stream when scoped
- [ ] Wrong-stream template apply blocked or warned

### QC audit exit criteria
- [ ] 0 projects with null stream after backfill (or documented exceptions)
- [ ] No mold jargon on CAD create path
- [ ] Access audit: scoped users vs All viewers
- [ ] Test evidence pack for UVT
- [ ] Rollback plan documented

### UVT / UAT exit criteria
- [ ] Ops walks stream portfolio + confirms staff only see relevant queues
- [ ] Eng creates sample CAD project end-to-end
- [ ] CEO reviews company roll-up vs stream split
- [ ] Written UAT sign-off before production

---

## 8. Open questions (remaining)

1. Launch streams: **Mold Design + CAD Development** only for Phase A? *(Recommended: yes)*
2. Are delivery teams **exclusive** to a stream, or shared with a primary stream affinity?
3. CAD project identifier: separate numbering prefix (e.g. `CAD-####`) vs shared tool number space?
4. Who owns stream master data day-to-day — Ops Admin or Engineering Admin?

**Resolved**
- Workflow / Phase A gate path: **approved**.
- Users must view **only relevant stream and/or team projects** by default: **approved**.
- Stream on users: **yes for relevance** (`User.stream_id` + assignments used for “My stream(s)”).

---

## 9. Meeting outcome (recorded)

**Approved Phase A** with Mold + CAD streams, required `stream_id`, stream-first projects UX, **per-user relevant stream/team project scope**, and the gate path above. Defer Phase B/C until UAT of Phase A is signed. Development may proceed.
