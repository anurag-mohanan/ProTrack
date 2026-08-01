# Audit Log Retention

**Policy:** Activity / audit records are retained for the number of days configured in Security policy (`audit_retention_days`, default **365**).

**Location:** Admin → Security settings (and Commercial Readiness summary).

**Purge:** Ops job / future scheduled cleanup should respect this value; until automated purge ships, retention is the stated target for backups and log archives.

**Related control:** SOC2 S7.
