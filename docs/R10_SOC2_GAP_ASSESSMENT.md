# R10 — SOC 2 gap assessment (Type I readiness scan)

**Date:** 2026-08-01  
**Scope:** ProTrack / Prosohm Engineering Operations Platform (commercial spine)  
**Purpose:** Identify control gaps before design-partner data and external tenants.  
**Not:** A formal audit opinion. Use as the backlog for Y2 SOC2 Type I/II.

## Trust services focus

Security, Availability, Confidentiality (Processing Integrity / Privacy later).

## Current strengths

| Area | Evidence |
|------|----------|
| AuthN | Password + lockout; OIDC Entra path; sessions |
| AuthZ | Roles / module permissions / team scope |
| Tenancy | `tenant_id`, ORM filters; optional PG RLS |
| Audit | Activity log; request logging middleware |
| Transport | HSTS / CORS / trusted hosts (prod flags) |
| Secrets | Env-based secrets; encryption key hook |
| Integrations | API keys hashed; webhook HMAC signatures |

## Gap register

| ID | Control theme | Gap | Severity | Owner | Target |
|----|---------------|-----|----------|-------|--------|
| S1 | Access reviews | No quarterly access attestation workflow | High | Ops/HR | Y1 Q4 |
| S2 | MFA | Password path lacks enforced MFA (SSO optional) | High | Eng | Y1 |
| S3 | Change management | Informal release notes; no CAB evidence pack | Med | Eng | Y1 |
| S4 | Backup / restore | Backups exist ops-side; restore drill not documented in-app | High | Ops | Y1 |
| S5 | Incident response | No published IR runbook + severity matrix | High | Ops | Y1 |
| S6 | Vendor inventory | No formal subprocessor list for SaaS mode | Med | Legal | Pre-logo |
| S7 | Logging retention | Request/audit retention policy not stated | Med | Eng/Ops | Y1 |
| S8 | Vulnerability mgmt | No scheduled dependency/pen-test cadence | High | Eng | Y1 |
| S9 | Encryption at rest | Relies on host/volume; app-level field crypto limited | Med | Eng | Y2 |
| S10 | HR offboarding IT | Strong product offboard; OS/IdP revoke checklist external | Med | Ops | Y1 |
| S11 | Customer data isolation test | Automated ORM tests exist; PG RLS opt-in; no continuous cross-tenant probe in CI on PG | Med | Eng | Pre-tenant-2 |
| S12 | Privacy | No public DPA / privacy notice for SaaS tenants | High | Legal | Pre-logo |
| S13 | Availability SLO | No published uptime SLO / status page | Low | Ops | Y2 |
| S14 | Secure SDLC | Tests strong; SAST/secret scan not mandatory in CI | Med | Eng | Y1 |

## Must-fix before first external production tenant

1. DPA + subprocessor list (S6, S12).  
2. Backup restore drill evidence (S4).  
3. IR runbook draft (S5).  
4. MFA for admin roles **or** mandatory Entra SSO for that tenant (S2).  
5. Cross-tenant isolation test on the target DB (S11) — enable PG RLS if Postgres.

## Nice-to-have before SOC2 Type I kickoff

- Access review calendar (S1)  
- Pen-test + dependency scanning in CI (S8, S14)  
- Log retention written into ops policy (S7)

## Recommended next engagement

Engage a SOC2 readiness consultant with this register as the kickoff agenda; map each gap to TSC criteria (CC6, CC7, A1, C1).

## Sign-off (internal)

| Role | Reviewed | Date |
|------|----------|------|
| CTO | | |
| Ops lead | | |
