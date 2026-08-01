# ADR R10-006 — Azure AD OIDC spike

**Status:** Implemented (testing mode + production path)  
**Date:** 2026-08-01  
**Related:** [R10_COMMERCIALIZATION_STRATEGY.md](./R10_COMMERCIALIZATION_STRATEGY.md)

## Goal

Microsoft Entra ID (Azure AD) OpenID Connect for ProTrack **without** replacing local password auth.

## Shipped

1. Env: `OIDC_ENABLED`, `OIDC_ISSUER`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`, `OIDC_REDIRECT_URI`, optional `OIDC_SCOPES`, `OIDC_FRONTEND_LANDING`.
2. `OIDC_TESTING=true` — fake IdP for automated tests / local demos.
3. Routes: `GET /api/v1/auth/oidc/status|login|callback` (+ `testing-authorize`).
4. Link-only: match `sso_subject` or email; bind subject on first success; **no auto-provision**.
5. Gated by env **and** feature flag `feature.sso`.
6. Login UI: “Sign in with Microsoft” when status.enabled; complete via `/login/sso#access_token=…`.
7. Audit: `user_logged_in` with `module=auth.oidc`.

## Entra app registration (manual)

- Redirect URI = `OIDC_REDIRECT_URI` (e.g. `https://api…/api/v1/auth/oidc/callback`)
- ID token claims: email (or preferred_username), oid/sub
- Issuer example: `https://login.microsoftonline.com/{tenant-id}/v2.0`

## Exit criteria

- [x] Config + login/callback routes behind `OIDC_ENABLED`
- [x] Link-only to existing Prosohm users (`sso_subject`)
- [x] Audit log on SSO login
- [x] Rollback: env/flag off → password-only UI
- [x] Manual Entra smoke checklist + dry-run script (`docs/R10_ENTRA_SSO_SMOKE.md`, `scripts/entra_oidc_smoke.py`)

## Non-goals (still)

- SCIM, multi-IdP, disabling password auth
