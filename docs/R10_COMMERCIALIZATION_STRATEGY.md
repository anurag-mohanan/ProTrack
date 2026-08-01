# ProTrack R10 — Commercialization Strategy (Master Pack)

**Status:** Board review complete — awaiting executive sign-off  
**Date:** 2026-08-01  
**Principle:** One codebase · Prosohm production uninterrupted · Tenant-ready spine before external logos  

Interactive board canvas: open beside chat in Cursor — `protrack-r10-commercialization-review.canvas.tsx`

---

## Executive verdict

**Product identity:** Option **D — Engineering Operations Platform**  
(Deep engineering project management + capacity + commercial control + people ops for tooling / engineering service firms. Not full ERP. Not full PLM.)

**Non-negotiables**

1. Prosohm production never pauses for SaaS work.  
2. No rewrite / no product fork.  
3. Introduce `tenant_id` before first external customer.  
4. Prosohm-specific rules become tenant configuration.  
5. Heuristics remain when AI is off or offline.

---

## 1. Commercialization readiness assessment

| Domain | Maturity | Notes |
|--------|----------|-------|
| Projects / milestones / templates | Strong | Core differentiator |
| Timesheets / approvals / reports | Strong | Customer hour packs matter commercially |
| Finance / quotes / P&L | Strong–partial | Multi-currency present; tax/billing SaaS missing |
| HR / performance / exit | Strong–partial | Differentiator vs generic PM |
| Capacity / planning board | Good | Keep performance sacred |
| Permissions / audit | Good | SSO reserved, not live |
| Branding | Partial | Branding page exists; packs incomplete |
| Multi-tenant / licensing | Weak | Blocker for SaaS |
| Integrations / webhooks | Weak | Internal API only |
| AI | Early | Lessons; no commercial AI pack |
| Portals / marketplace | Absent | After tenant + trust |

**Overall:** Excellent internal Engineering Operations product; **not yet SaaS-sellable** without tenant spine, editions, and branding extraction.

---

## 2. Current gaps analysis

See canvas § Readiness. Highest-risk gap: selling before row-level tenancy.

---

## 3. Product vision

| Option | Decision |
|--------|----------|
| A Engineering ERP | Reject |
| B Eng Project Management | Core subset only |
| C PLM-lite | Partner later |
| **D Eng Operations Platform** | **Adopt** |
| E Combination | Marketing umbrella for D |

**ICP (first):** Injection mold design, fixture/jig, automotive engineering services, plastic product development — 25–250 seats.

**Differentiation:** Tool/stream numbering, engineering timesheets + customer packs, planning board, quote→fee→P&L, HR exit/rehire — not Jira, not SAP.

---

## 4. Architecture recommendations

**Deployment modes (one image):**

| Mode | Isolation |
|------|-----------|
| Single company | Default tenant |
| Multi-company / BU | `org_unit_id` within tenant |
| Multi-tenant SaaS | Row-level `tenant_id` (+ optional RLS) |
| On-prem enterprise | Dedicated deploy, same binary |
| Hybrid | Auth/billing cloud; data regional (later) |

**Spine changes:** tenant column + middleware · feature flags · OpenAPI public v1 · Postgres primary · AI behind flags with heuristic fallback.

---

## 5. Industry generalization strategy

Common abstraction: Customer → Engagement → Project(Job/Tool) → Milestones → Effort → Commercial terms.  
Industry packs = labels + templates + default stages + sample data. Never industry-specific core tables.

**First packs:** Injection molds, Fixtures/jigs. Then automotive ES, medical tooling (audit-heavy).

---

## 6. Commercial feature roadmap

| Priority | Features |
|----------|----------|
| **Must** | Tenant spine, feature flags/editions, branding/theme pack, numbering policies, SSO OIDC, backups, observability |
| **Should** | Stage-gate/approval config, public API + webhooks, import wizards, localization, tax packs, trials, customer portal v1 |
| **Nice** | Slack/Teams, calendar, e-sign, mobile approvals, vendor portal |
| **Future** | CAD plugins, ERP marketplace, offline desktop, SCIM, multi-region AA |

---

## 7. Migration plan (Prosohm live → commercial)

1. Document Prosohm as Tenant Config Pack.  
2. Add `tenant_id` nullable → backfill → NOT NULL.  
3. Bind session to tenant (invisible to Prosohm).  
4. Move seeds/branding/numbering to config APIs.  
5. Edition flags default **Enterprise/ON** for Prosohm.  
6. Billing only for external tenants.

**Contract:** Additive schema · no breaking APIs · flags default ON · rollback = prior image + flag off.

---

## 8. Product editions

Trial · Starter · Professional · Business · Enterprise · On-Premise · Academic (year-2).  
See canvas for feature cuts.

---

## 9. Pricing strategy (directional)

- SaaS: per active seat / month by edition (annual discount).  
- AI pack: add-on.  
- Implementation packages for import + industry pack + training.  
- On-prem: term or perpetual + maintenance.  
- List prices after 3 design-partner wins.

---

## 10. Risk register

| Risk | Mitigation |
|------|------------|
| Tenant retrofit after sales | Spine before logos |
| ERP scope creep | Vision D product gate |
| Prosohm velocity drop | Cap commercial capacity (~30% Y1) |
| Security pre-SOC2 | Pen-test + logging Must |
| AI overpromise | Heuristic fallback; premium labeling |
| Fork temptation | Same image + license key only |

---

## 11. Three-year roadmap

- **Y1:** Tenant, flags, branding packs, SSO, public API, 3 design partners.  
- **Y2:** Billing, SOC2, portal v1, approval builder, industry packs, EU region.  
- **Y3:** Integrations hub, AI pack GA, partner marketplace, hybrid.

---

## 12. Five-year vision

Default operating system for mid-market tooling and engineering service companies: industry packs in a day, capacity + commercial control, optional AI, ERP/CAD via integrations — still one codebase, still Prosohm’s production platform.

---

## 13. Immediate action items (90 days)

### Engineering progress (M0 + M1 columns)

- [x] ADR R10-001 tenant + flags (`docs/ADR_R10_TENANT_AND_FEATURE_FLAGS.md`)
- [x] `tenants` + `feature_flags` (phase69); Prosohm seeded as enterprise
- [x] Request context `X-Tenant-Id` (default Prosohm)
- [x] API `/api/v1/commercial/*` + Admin **Commercial / Tenancy** UI
- [x] M1: `tenant_id` on business tables + Prosohm backfill (phase70, ADR R10-002)
- [x] M1b: unique constraints → `(tenant_id, …)` (phase71, ADR R10-003)
- [x] M1c: query-time tenant filters (ADR R10-004) — PG RLS optional later
- [x] Optional PG RLS layer (ADR R10-009, phase74; `PROTRACK_ENABLE_PG_RLS`)
- [x] Tenant config pack: branding façade + terminology/numbering (ADR R10-005)
- [x] OIDC spike plan + config stub (ADR R10-006)
- [x] OIDC login/callback + testing mode + Login SSO button (ADR R10-006 implemented)
- [x] Public API + webhooks draft (ADR R10-007)
- [x] Expand public API + webhook retries (ADR R10-008, phase73)
- [x] Entra SSO smoke checklist + dry-run script (`docs/R10_ENTRA_SSO_SMOKE.md`)
- [x] SOC2 gap assessment (`docs/R10_SOC2_GAP_ASSESSMENT.md`)
- [x] Vision D one-pager for CEO/CTO sign-off (`docs/R10_VISION_D_ONE_PAGER.md`)
- [x] Design-partner LOI templates — mold / fixture / auto (`docs/R10_LOI_DESIGN_PARTNER_*.md`)
- [x] Commercial readiness hub + trust pack + admin SSO gate (ADR R10-010, phase75)

### Remaining (90 days)

1. Vision D / trust attestations **recorded in hub** (and wet-ink copies as needed).  
2. Manual Entra browser smoke — mark `entra_smoke_passed` sign-off after live IdP test.  
3. Countersign design-partner LOIs (track status in hub).  
4. Continue weekly Prosohm ops shipping (~70% capacity).  
5. Close remaining SOC2 must-fix items in hub before first external production tenant.

---

## Master sequence (optimize for stated goals)

```text
Config extraction → Tenant spine → Editions/flags → SSO/API → Billing
→ Portals → Ecosystem
While: Prosohm ops features remain majority capacity
```

**Final recommendation:** Commercialize by **configuration and tenancy** on the existing ProTrack spine. Sell Engineering Operations to tooling ICPs. Never fork. Never pause Prosohm.
