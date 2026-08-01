# ADR R10-010 — Commercial readiness (GTM / trust / sign-off)

**Status:** Accepted  
**Date:** 2026-08-01  
**Related:** [R10_COMMERCIALIZATION_STRATEGY.md](./R10_COMMERCIALIZATION_STRATEGY.md), [R10_SOC2_GAP_ASSESSMENT.md](./R10_SOC2_GAP_ASSESSMENT.md)

## Context

Engineering spine (tenant, SSO, public API) is in place. Remaining 90-day work is go-to-market, trust, and sign-off: Vision D attestations, design-partner LOIs, Entra smoke evidence, and SOC2 must-fix controls.

## Decision

1. **Commercial Readiness hub** (Admin): track sign-offs, design partners, trust control checks; surface OIDC status and audit retention.
2. **Tables** (phase75): `commercial_signoffs`, `design_partners`, `trust_control_checks` — tenant-scoped.
3. **Trust document pack** under `docs/trust/` (DPA, privacy, IR, backup drill, subprocessors, etc.) — linked from hub; completion is admin attestation, not auto.
4. **Admin SSO gate**: `security_policy_settings.require_sso_for_admins` — when true, Admin password login is rejected (use Entra SSO). Break-glass: `PROTRACK_SSO_BREAK_GLASS=true`.
5. **Access review export** for quarterly attestation (S1).
6. **Cross-tenant isolation probe** test remains in CI (S11).

## Non-goals

- DocuSign / wet-ink replacement  
- Full TOTP MFA UX  
- Public status page  

## Exit criteria

- [x] ADR + phase75 + models  
- [x] Readiness API + Admin UI  
- [x] Trust doc pack  
- [x] Admin SSO gate + tests  
- [x] Strategy checklist update  
