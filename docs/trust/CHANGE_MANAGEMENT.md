# Change Management (lightweight)

**Owner:** Engineering

## For each production release

1. Summary of changes (PR list / release notes).  
2. Risk / rollback (prior image + flag off for commercial features).  
3. Test evidence (pytest subset / smoke).  
4. Approver (CTO or delegate) for high-risk changes.

## Evidence folder suggestion

`ops/releases/YYYY-MM-DD/` — notes.md, test log, approver email.

## Commercial spine changes

Flag-gated (`feature.*`); default ON for Prosohm Enterprise. Document any `PROTRACK_*` env toggles (OIDC, PG RLS, SSO break-glass).
