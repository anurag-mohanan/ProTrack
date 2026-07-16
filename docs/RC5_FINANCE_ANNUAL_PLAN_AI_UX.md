# RC5 — Annual Plan AI Copilot + Creative UX (Phase C)

**Status:** CTO-approved Phase C — Internal UAT  
**Date:** 2026-07-16  
**Stakeholders:** CEO · President · CFO · Creative Head · CTO  
*(Also informed: Head of Finance / Engineering / Sales from prior FP&A locks)*

---

## 1. Leadership brainstorm

| Stakeholder | Verdict |
|-------------|---------|
| **CFO** | Annual Plan is still a spreadsheet in a tab. Need **AI-assisted recommendations** with one-click apply, plus quarterly P&L clarity — not more empty cells. |
| **CEO** | Want a **copilot** that explains risk (margin, under-seeded wages, sales lag) in plain language for board prep. |
| **President** | Scenarios already exist; now need **guided actions** so Stretch/Downside are not manual busywork. |
| **Creative Head** | Elevate Annual Plan + People / Expenses / Commercial / Quotes with the same section language as Overview. **Do not restyle Overheads** (already improved). |
| **CTO** | Ship **deterministic AI** first (rules + live ProTrack data). No external LLM keys this phase. Label UI as “AI Assist (data-driven)”. Preserve all Phase A/B APIs. |

### Industry alignment

| Pattern | Source | Phase C |
|---------|--------|---------|
| AI plan suggestions / apply | Abacum, Adaptive | Insights + apply actions |
| Quarterly P&L visual | QBO, Xero, Prophix | Sales vs expenses by quarter chart |
| Copilot side panel | Modern FP&A UX | Right-rail AI Assist on Annual Plan |
| Section chrome consistency | Creative system | Hero + FinanceSection on non-Overheads tabs |

---

## 2. CTO-approved scope

| # | Deliverable |
|---|-------------|
| C1 | `GET /finance/plans/{id}/ai-insights` — ranked insights with severity, confidence, optional `action_code` |
| C2 | `POST /finance/plans/{id}/ai-apply` — apply `seed_from_live`, `fill_empty_quarters_from_q1`, `project_remaining_from_run_rate`, `uplift_remaining_sales` |
| C3 | Annual Plan UI — AI Assist panel, quarterly Sales vs Expenses chart, settings in FinanceSection, status chip |
| C4 | Creative UX — hero/section wrap for People costs, Expenses, Team commercial, Revenue/quotes (**skip Overheads**) |
| C5 | Tests + dist rebuild + API/Vite restart for UAT |

**Out of scope:** ChatGPT/OpenAI calls, editing Overheads tab chrome, GL/ERP, auto-approving budgets.

### AI methodology lock (CFO + CTO)

- Insights are **computed from plan lines + plan-vs-actual run rates + roster/overhead signals** — reproducible, auditable.  
- Every apply action is **opt-in** (user clicks Apply).  
- Confidence is a 0–100 heuristic from data completeness (plan cells filled, months elapsed, live costs present).  
- UI copy: **“AI Assist (data-driven)”** — never claim generative LLM.

---

## 3. Pipeline gates

1. Development (C1–C4)  
2. CTO approve (this doc)  
3. Senior Tester — AI apply side-effects, PVA math, seed/clone  
4. Testing — regression Overview / Overheads / Budgets / Quotes / People  
5. Senior Tester approve  
6. QC final audit  
7. Restart backend + frontend → **UAT**

### ST matrix

- [ ] Insights return for a plan with empty wages → seed action present  
- [ ] Apply `fill_empty_quarters_from_q1` fills blank Q2–Q4  
- [ ] Apply `uplift_remaining_sales` increases remaining sales quarters  
- [ ] Overheads tab visual unchanged vs Phase B  
- [ ] Designer without finance → 403 on new endpoints  
- [ ] Phase A PVA + Phase B Overview charts still work  

---

## 4. Dev map

| Layer | Path |
|-------|------|
| Direction | `docs/RC5_FINANCE_ANNUAL_PLAN_AI_UX.md` |
| AI service | `app/services/finance/plan_ai_service.py` |
| API | `app/api/v1/finance.py` |
| Schemas | `app/schemas/finance.py` |
| Annual Plan UI | `frontend/src/components/finance/AnnualPlanPanel.tsx` |
| Creative wraps | People / Expenses / Team commercial / Quotes panels |
| Tests | `tests/test_finance_plan_ai.py` |

---

## Related

- [RC5_FINANCE_PLANNING_FPA_IMPROVEMENT.md](./RC5_FINANCE_PLANNING_FPA_IMPROVEMENT.md)  
- [RC5_FINANCE_PLANNING_UX_COCKPIT.md](./RC5_FINANCE_PLANNING_UX_COCKPIT.md)  
- [FINANCE_ANNUAL_PLAN.md](./FINANCE_ANNUAL_PLAN.md)  
