# RC5 — Finance quarterly math, skill fee bands, renewals in budget, quote Prepared For AI

**Status:** Implemented  
**Locks:** 1B (Annual Plan = 4 quarters only), 2A (skill fee bands on Team commercial)

## What shipped

| Area | Change |
|------|--------|
| People costs | **Hourly cost** column removed; save still posts `hourly_cost: 0` |
| Annual Plan | UI Q1–Q4 only; even-split to `month_01`–`12`; **Sync software renewals** |
| Overview | Quarterly revenue/opex signals; known renewals FY total |
| Budgets | Q1–Q4 allocated + forecast; forecast += renewals in quarter |
| Team commercial | Skill fee bands (beginner…expert + default); Σ rate×count |
| Quote import | Looser Prepared For extract + customer directory recovery |

## Pipeline

Dev → Senior Tester → Testing → Senior Tester → QC → UAT. Restart API + frontend before UAT; publish `frontend/dist`.

### ST / Testing matrix

- [ ] People costs has no Hourly column; monthly salary still saves
- [ ] Annual Plan shows 4 quarter columns; edit persists; Sync renewals creates expense lines
- [ ] Overview quarterly cards change when salary / fees change
- [ ] Budget create with FY total splits to Q1–Q4; forecast ≥ allocated when renewals exist
- [ ] Retainer: skill bands change monthly fee signal vs flat rate
- [ ] QT PDF with same-line `Prepared For:` imports; layout mismatch recovers customer from directory
- [ ] Regression: golden Sybridge QT sample still imports

### Pre-UAT ops

Restart backend and frontend after deploy; hard-refresh browser.
