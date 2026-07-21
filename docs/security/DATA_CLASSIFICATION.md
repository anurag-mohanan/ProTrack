# ProTrack Data Classification Matrix

| Data class | Examples | Classification | Who may view (field-level) | At-rest protection |
|------------|----------|----------------|----------------------------|--------------------|
| Salary | Monthly salary, base INR salary, hourly cost, compensation amounts | Highly Confidential | HR, Engineering Manager, Finance (financial-planning), System Admin, or `view_salary` | Planned: `EncryptedNumeric` (see below) |
| Cost | Employee hourly/contractor cost, run rates | Confidential | Finance/Engineering Manager or `view_financial_cost` | Planned: `EncryptedNumeric` |
| Budget | Project/annual budgets, fee bands | Confidential | Finance-capable roles or `view_budget` (hidden from designers) | DB access control |
| Profitability | Customer/project margins, P&L | Confidential | Financial-planning access or `view_profitability` | DB access control |
| Engineering IP | Work orders, drawings, imported workbooks | Confidential | Project members / delivery roles | Filesystem sandbox + access control |
| HR / PII | Contact details, performance reviews | Confidential | HR / Admin / managers | DB access control |
| Credentials | Password hashes, SMTP secrets, JWT/encryption keys | Secret | System only | bcrypt (passwords), Fernet (secrets), env (keys) |
| Audit | Activity log with IP/UA/outcome | Internal | Admin | DB access control |

## Field-level enforcement

Salary and cost fields are redacted in API responses (`employee-costs` roster
and profiles, compensation reads) for viewers lacking the corresponding
permission — see `app/core/field_security.py`. Module access alone does **not**
grant salary visibility.

## Designed, not yet built (future-ready)

### `EncryptedNumeric` (salary/cost at-rest encryption)
Strategy: a SQLAlchemy `TypeDecorator` wrapping the sensitive numeric columns
(`employee_cost_profiles.monthly_salary`, `base_monthly_salary_inr`,
`hourly_cost`, compensation amounts). On write it serializes the Decimal to a
string and encrypts with `app.core.crypto` (Fernet); on read it decrypts and
re-parses to Decimal. Because aggregation currently happens in Python service
code (not SQL `SUM`), encryption is compatible without query rewrites; any future
SQL-side aggregation of these columns must move to application code first. The
Fernet key is already provisioned (`PROTRACK_ENCRYPTION_KEY`), so enabling this
is additive and requires only a one-time migration to re-encrypt existing rows.

### MFA / SSO (future-ready columns)
`users.mfa_enabled`, `users.mfa_secret` (Fernet-encrypted TOTP seed),
`users.mfa_method`, and `users.sso_subject` are present (phase 50) but unused.
TOTP enrollment/verification and an SSO (Azure AD / Entra) subject mapping can be
layered on without a schema migration.

### Encrypted & verified backups
Strategy: pipe the SQLite backup file through Fernet encryption before writing to
the backup directory, storing a SHA-256 checksum alongside; restore verifies the
checksum and decrypts. The backup service already centralizes create/restore, so
this is an isolated change. Not enabled this pass.
