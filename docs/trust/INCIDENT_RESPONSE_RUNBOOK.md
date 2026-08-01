# Incident Response Runbook

**Owner:** Ops lead  
**Severity matrix**

| Sev | Definition | Response target | Example |
|-----|------------|-----------------|---------|
| SEV1 | Active data breach / total outage of production | 15 min page | Confirmed unauthorized cross-tenant access |
| SEV2 | Major degradation / security control failure | 1 hour | Auth outage, backup failure |
| SEV3 | Limited impact | Next business day | Single-user access bug |
| SEV4 | Informational | Backlog | Dependency CVE no exploit |

## Process

1. **Detect** — monitoring, user report, security alert.  
2. **Triage** — assign SEV; declare incident channel.  
3. **Contain** — revoke keys/sessions, disable SSO flag, isolate host as needed.  
4. **Eradicate / recover** — patch, restore from backup if required.  
5. **Notify** — for personal data breach: begin customer/regulator clock (aim ≤72h awareness).  
6. **Postmortem** — within 5 business days for SEV1/2; file under change management evidence.

## Contacts

| Role | Primary | Backup |
|------|---------|--------|
| Incident commander | *(fill)* | *(fill)* |
| Engineering | *(fill)* | *(fill)* |
| Legal / privacy | *(fill)* | *(fill)* |

## Useful commands / locations

- API logs: `protrack.api` logger / host log path  
- Revoke sessions: Security Center → sessions  
- Disable public API / webhooks: Commercial feature flags  
- SSO break-glass: `PROTRACK_SSO_BREAK_GLASS=true` (temporary)
