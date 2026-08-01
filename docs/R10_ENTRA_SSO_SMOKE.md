# R10 — Microsoft Entra ID (OIDC) smoke test

**Related:** [ADR_R10_OIDC_SPIKE.md](./ADR_R10_OIDC_SPIKE.md)  
**Script:** `python scripts/entra_oidc_smoke.py`

## Prerequisites

1. Entra app registration (single-tenant or multi-tenant as required).  
2. Redirect URI exact match to `OIDC_REDIRECT_URI`  
   (e.g. `https://api.protrack.example.com/api/v1/auth/oidc/callback`).  
3. Client secret created; ID token optional claims: email / preferred_username; `oid` or `sub`.  
4. Env on API host:

```text
OIDC_ENABLED=true
OIDC_TESTING=false
OIDC_ISSUER=https://login.microsoftonline.com/<tenant-id>/v2.0
OIDC_CLIENT_ID=<app-id>
OIDC_CLIENT_SECRET=<secret>
OIDC_REDIRECT_URI=https://<api-host>/api/v1/auth/oidc/callback
OIDC_FRONTEND_LANDING=https://<ui-host>/login/sso
feature.sso = ON (Commercial settings; Prosohm enterprise default ON)
```

5. Target user already exists in ProTrack with matching email (link-only; no auto-provision).

## Automated dry-run (no browser)

```bash
# From repo root — validates status + discovery when credentials present
python scripts/entra_oidc_smoke.py

# Local testing IdP path (no Entra)
set OIDC_ENABLED=true
set OIDC_TESTING=true
python scripts/entra_oidc_smoke.py --testing
```

## Manual browser smoke (real Entra)

| # | Step | Expected |
|---|------|----------|
| 1 | Open Login → **Sign in with Microsoft** | Redirect to `login.microsoftonline.com` |
| 2 | Authenticate as linked user | Callback hits API `/auth/oidc/callback` |
| 3 | Land on `/login/sso#access_token=…` | UI stores token and enters app |
| 4 | Check Activities / audit | `user_logged_in` with `module=auth.oidc` |
| 5 | Confirm `users.sso_subject` set | Bound on first success |
| 6 | Unknown email | Clear error; no new user created |
| 7 | Set `OIDC_ENABLED=false` (or flag off) | SSO button hidden; password login works |

## Sign-off

| Role | Result (pass/fail) | Date | Notes |
|------|--------------------|------|-------|
| Ops | | | |
| Engineering | | | |

## Rollback

Unset `OIDC_ENABLED` or disable `feature.sso`. Password auth remains the default path.
