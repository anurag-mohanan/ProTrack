# ProTrack Security Architecture

This document describes the Secure-by-Design foundation implemented for ProTrack
and the enforcement model that protects sensitive engineering IP, customer data,
employee salaries, financial planning, and HR data.

## Enforcement pipeline

Every API request flows through the same layered controls:

```
Incoming request
  → Edge middleware (security headers, HSTS, body-size cap, trusted host)
  → Rate limiting (auth endpoints)
  → Authentication (JWT: signature, expiry, token_version, idle timeout)
  → Authorization (require_roles / require_module_action / require_special)
  → Handler
  → Field-level security (salary/cost/budget/profitability redaction)
  → Audit (log_activity: user, ip, device, outcome, old→new)
  → Response
```

## Components

### Secrets & configuration (`app/core/config.py`, `crypto.py`, `secret_encryption.py`)
- `PROTRACK_SECRET_KEY` (JWT signing) and `PROTRACK_ENCRYPTION_KEY` (Fernet) are
  environment-driven. In `PROTRACK_ENV=production` the app refuses to boot on the
  insecure development defaults (`assert_production_security`).
- Stored secrets (e.g. SMTP passwords) use authenticated **Fernet** encryption.
  Legacy XOR-obfuscated values are transparently decrypted and upgraded on next
  save.
- `.gitignore` excludes `.env*`, `*.db`, and `Backups/`; the live database and
  `.env.development` were untracked from source control.

### Edge hardening (`app/core/security_middleware.py`, `rate_limit.py`)
- `SecurityHeadersMiddleware`: `X-Content-Type-Options`, `X-Frame-Options`,
  `Referrer-Policy`, `Cross-Origin-Opener-Policy`, CSP (relaxed only for
  `/docs`), and HSTS when `PROTRACK_ENABLE_HSTS=true`.
- `BodySizeLimitMiddleware`: rejects oversized request bodies (413).
- `TrustedHostMiddleware`: optional Host allowlist from `PROTRACK_TRUSTED_HOSTS`.
- `slowapi` rate limiting on `/auth/login`, `/auth/token`, `/auth/change-password`.

### Authentication & sessions (`app/core/auth.py`, `app/api/v1/auth.py`, `auth_deps.py`)
- JWT embeds `iat` and `tv` (token_version) claims.
- `get_current_user` rejects tokens whose `tv` != `user.token_version`
  (stateless force-logout) and idle-expired tokens (issued-at older than the
  configured idle window).
- Automatic account lockout after N failed attempts (`locked_until`).
- Password history blocks reuse of the last N hashes; `password_changed_at`
  tracks age.
- `/auth/refresh` mints a fresh token; `/auth/logout-all-devices` and the
  Security Center bump `token_version` to revoke all sessions.
- `login_sessions` records active devices for visibility and remote termination.

### Authorization (`app/core/access_control.py`, `module_actions.py`, `auth_deps.py`)
- Role → module → action model. Reusable guards `require_module_action(module,
  action)` and `require_special(permission)`.
- Per-user `module_actions` overrides are now persisted and surfaced in `/me`.

### Field-level security (`app/core/field_security.py`)
- `can_view_salary/cost/budget/profitability` combine role, financial-planning
  module access, and explicit specials. Salary/cost are redacted from the
  employee-cost roster/profile and compensation reads for viewers who lack the
  permission — module access alone no longer implies full salary visibility.

### Audit trail (`app/services/activity_service.py`, phase 50)
- `activities` gained `ip_address`, `user_agent`, `outcome`, `module`.
- `log_activity` auto-captures request IP/UA via a contextvar populated by the
  request middleware. Logins, failed logins, exports, backup/restore, and policy
  changes record outcomes.

### Governance (`app/api/v1/security.py`, Security Center UI)
- `GET /admin/security/overview` computes a security score plus failed-login,
  lockout, active-session, export, and backup metrics.
- Admin-editable policy (`GET/PUT /admin/security/policy`) is persisted in the
  `security_policy_settings` singleton and feeds live enforcement (lockout,
  idle timeout, password history).
- Active-session listing and per-user remote termination.

## Path safety (`app/core/path_safety.py`)
Server-side path inputs (email attachments, folder imports) are confined to
allowlisted roots (`PROTRACK_ATTACHMENT_ROOTS`, `PROTRACK_IMPORT_SOURCE_ROOTS`),
preventing traversal and arbitrary-file access. Uploads enforce a size cap and
the company-logo allowlist excludes SVG (stored-XSS vector). The unauthenticated
`/uploads` static mount was removed; the logo is served via a permission-aware
API route.
