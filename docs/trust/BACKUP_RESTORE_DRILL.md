# Backup & Restore Drill

**Cadence:** Quarterly  
**Owner:** Ops

## Procedure

1. Identify latest verified backup (filename + timestamp).  
2. Restore to **non-production** host / scratch DB.  
3. Start API against restored DB; run `scripts/api_smoke_test.py` (or health + login).  
4. Confirm row counts for `users`, `projects`, `timesheet_entries` vs production snapshot notes.  
5. Record evidence below; destroy scratch environment.

## Evidence log

| Date | Backup ID | Restored env | Smoke result | Operator | Notes |
|------|-----------|--------------|--------------|----------|-------|
| | | | | | |

## Pass criteria

- Restore completes without error.  
- Admin can log in; projects list non-empty if production had data.  
- Duration and gaps documented.
