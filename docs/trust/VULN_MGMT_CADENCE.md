# Vulnerability Management Cadence

| Activity | Cadence | Owner |
|----------|---------|-------|
| Dependency review (`pip` / `npm audit`) | Monthly | Eng |
| OS / host patches | Monthly | Ops |
| External pen-test | Annual (pre-SOC2) | Eng + vendor |
| Critical CVE emergency patch | 72 hours | Eng |

## Tracking

Log findings in issue tracker with severity; SEV mapping aligns with IR runbook.

## Pre-external-tenant bar

No open Critical findings on auth, tenancy isolation, or secret handling.
