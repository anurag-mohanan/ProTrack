# Performance Cycle Dossier — QC / Dual-user / UAT gates

Decisions: `docs/performance-cycle-dossier-decisions.md`. Brainstorm: `docs/performance-cycle-dossier-brainstorm.md`.

## Gate 3 — QC audit checklist

- [ ] Dossier defaults to current review year (Jul–Jun bounds correct).
- [ ] Individual can open own Cycle dossier; sees projects, hours, leave disclaimer, prior goals/score when present.
- [ ] Team Leader opens roster → teammate dossier (200); non-managed peer → 403.
- [ ] Months over expected and leave days match timesheet math for a known fixture month.
- [ ] Owned project shows quoted vs actual; supported projects listed separately.
- [ ] GreytHR leave balances not claimed as ProTrack data.
- [ ] Analytics / Annual Reviews sections still work (no regression).

**QC result:** ________  **Date:** ________  **Signer:** ________

## Gate 4 — Two-user peer check (Testing)

| Step | User A (TL / EM) | User B (Designer) | Pass? |
|------|------------------|-------------------|-------|
| 1 | Open Cycle dossier roster | Opens own dossier | |
| 2 | Opens B’s dossier | Sees same headline numbers as A for B | |
| 3 | Confirms projects B worked Jul–Jun | Confirms hours / leave days | |
| 4 | Tries unrelated employee (if any) | — | 403 |

**Peer / Testing result:** ________  **Date:** ________  **A:** ________  **B:** ________

## Gate 5 — UAT / UVT

1. Happy path: self dossier + TL roster + drill-in.  
2. Empty year (new hire): empty projects / zero months — no crash.  
3. Prior review goals/score visible when an acknowledged sheet exists.  
4. Regression: Dashboard, Annual Reviews, Skills, Analytics.

**UAT / UVT result:** ________  **Date:** ________  **Signer:** ________
