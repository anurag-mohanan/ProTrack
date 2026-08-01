# Subprocessors

**Last updated:** 2026-08-01  
**Owner:** Legal / Ops

| Subprocessor | Purpose | Data | Region (typical) |
|--------------|---------|------|------------------|
| *(Hosting provider — fill)* | App + DB hosting | Tenant application data | *(fill)* |
| *(Backup storage — fill)* | Encrypted backups | DB snapshots | *(fill)* |
| Microsoft Entra ID | Optional SSO (Customer tenant) | Auth assertions / email | Customer Entra region |
| *(Email relay — fill)* | Transactional email | Email addresses, message metadata | *(fill)* |

## Notes

- On-prem / customer-hosted deployments may have an empty SaaS subprocessor list beyond Customer’s own IdP.  
- Design partners: confirm hosting row before production data.  
- Changes: notify customers with ≥30 days notice for material additions where contractually required.
