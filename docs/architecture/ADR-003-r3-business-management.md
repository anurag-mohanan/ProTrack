# ADR-003: R3 Business Management

## Status

Accepted (2026-07-24)

## Context

R2 delivered operational gates. R3 adds business-management controls without redesigning
Resource Planning, Finance quotes, or Projects UX.

## Decision

1. **Capacity what-if** — client-side overlay on Resource Planning (extra designers / hours
   delta) recalculating scenario utilization; no persistence in V1.
2. **Portfolio dimensions** — optional `Team.business_unit` (phase 58) + Projects filter.
3. **Billing readiness** — `billing_ready` / `billing_gaps` on quote reads; chip in Finance
   quotes table (team, project link, currency, quoted date, invoiced date when marked).
4. **Finance export adapter stub** — `GET /finance/exports/erp-journal.csv` generic journal
   layout for manual ERP import (not live sync).

## Consequences

- Multi-legal-entity books and live QBO/Xero remain later releases.
- What-if scenarios are exploratory only until a saved-scenario API is needed.
