# R5 AI Provider — UAT checklist

Decisions: `docs/architecture/ADR-005-r5-ai-capabilities.md`.

## Gate — Foundation

- [ ] With default env (no `AI_PROVIDER` / key), `GET /api/v1/ai/provider` returns
      `provider=heuristic`, `mode=offline`, `llm_available=false`.
- [ ] `GET /api/v1/ai/insights` still returns a list (heuristic).
- [ ] Quote assistant on a project still returns suggested hours (heuristic).
- [ ] Report insights still generate without LLM.
- [ ] Set `AI_PROVIDER=openai` **without** `AI_API_KEY` → still `llm_available=false`;
      insights/quote endpoints remain 200 with heuristic data.
- [ ] Analytics hub AI Insights tile shows offline / heuristic chip (or equivalent).
- [ ] Nested HR / Projects / Admin pages show module home button; homes do not.

**QC result:** ________  **Date:** ________  **Signer:** ________

## Optional LLM smoke (when key provisioned)

- [ ] With valid key + model, provider status shows `mode=llm`, `llm_available=true`.
- [ ] Report insights may include one extra narrative line; quote rationale may append LLM text.
- [ ] Kill/network-block the LLM host → endpoints still return heuristic payloads (no 5xx).
