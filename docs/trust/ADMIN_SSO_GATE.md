# Admin SSO Gate

**Control:** S2 — privileged password login disabled when `require_sso_for_admins` is enabled.

## Behavior

- Setting stored on `security_policy_settings.require_sso_for_admins`.  
- Toggle: Commercial Readiness hub or Security policy API.  
- Roles blocked from password login: `Admin`, `System Admin`.  
- Use Microsoft Entra OIDC (`OIDC_ENABLED` + `feature.sso`).  
- Break-glass: `PROTRACK_SSO_BREAK_GLASS=true` (temporary ops only; audit when used).

## Verification

1. Enable require SSO for admins.  
2. Password login as admin → 403 with SSO message.  
3. SSO login succeeds for linked admin user.  
4. Disable setting or use break-glass to recover if IdP down.
