# ProTrack — Vision D one-pager (Engineering Operations Platform)

**Document ID:** R10-VISION-D  
**Date:** 2026-08-01  
**Status:** Draft ready for CEO / CTO signature  

---

## Product we are building

**ProTrack** is an **Engineering Operations Platform** for mid-market tooling and engineering service firms (injection molds, fixtures/jigs, automotive ES, plastic product development — typically 25–250 seats).

It is **not** a full ERP, **not** a full PLM, and **not** a generic project tool. It unifies engineering delivery, capacity, commercial control, and people ops on **one codebase**.

## Why now

Prosohm already runs ProTrack in production. Commercialization is **configuration + tenancy** on that spine — not a rewrite and not a fork. External customers get editions and packs; Prosohm keeps Enterprise defaults and never pauses for SaaS work.

## Non-negotiables (board)

1. Prosohm production never pauses for commercial work.  
2. No rewrite / no product fork.  
3. `tenant_id` before first external logo.  
4. Prosohm-specific rules become **tenant configuration**.  
5. Heuristics remain when AI is off or offline.

## What we sell in year one

- Tenant-ready Engineering Operations (projects, milestones, timesheets, planning, quotes/P&L, HR exit/rehire).  
- Industry packs (terminology, numbering, templates) — molds first, then fixtures, then auto ES.  
- SSO (Entra OIDC), public API + webhooks, feature flags / editions.  
- Design-partner path (3 LOIs) before list pricing.

## What we explicitly defer

Billing SaaS, customer portal GA, SOC2 Type II (assessment starts now), multi-region, SCIM, CAD plugins.

## Capacity rule

Commercial spine ≈ **≤30%** engineering capacity in Y1; majority remains Prosohm ops shipping.

## Decision requested

Approve **Option D — Engineering Operations Platform** as the product identity and authorize continued execution of the R10 90-day spine (tenant, SSO, API, design partners).

| Role | Name | Signature | Date |
|------|------|-----------|------|
| CEO | | | |
| CTO | | | |

**Reference:** `docs/R10_COMMERCIALIZATION_STRATEGY.md`
