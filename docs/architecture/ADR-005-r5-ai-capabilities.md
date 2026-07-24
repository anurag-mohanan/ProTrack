# ADR-005: R5 AI Capabilities

## Status

Accepted (2026-07-24)

## Context

R4 delivered enterprise foundations (QA gate, DMS metadata, learning plans, multi-entity prep).
The enterprise roadmap’s R5 focus is **AI capabilities**: a pluggable LLM provider while
keeping ProTrack’s existing heuristic AI modules as the default offline path.

ProTrack already has an in-process AI engine (`app/services/ai`) with deterministic modules
(dashboard insights, quoting assistant, report insights, etc.). R5 must not break offline
operation or require an external API key for core workflows.

## Decision

1. **Heuristic default** — `AI_PROVIDER=heuristic` is the default. All AI modules continue to
   return rule/pattern-based results without calling an LLM.
2. **Pluggable LLM enrichment** — An `LlmProvider` protocol may optionally enrich narratives
   (short text). Failures always soft-fail to `None`; callers keep the heuristic payload.
3. **OpenAI-compatible optional path** — `AI_PROVIDER=openai` uses env `AI_API_KEY`,
   `AI_BASE_URL`, and `AI_MODEL`. Missing key or HTTP errors degrade to heuristic-only.
4. **Surfaces in R5 foundation** — Wire enrichment into **report insights** and **quoting
   assistant** only. No core module UX redesign.
5. **Status API** — `GET /api/v1/ai/provider` exposes provider name, model, and whether LLM
   mode is effectively available (for ops / Analytics chip).
6. **Additive API only** — No `/api/v2`; existing `/api/v1/ai/*` endpoints remain stable.

## Consequences

- Production can stay fully offline with zero LLM config.
- Enabling LLM is opt-in and never blocks quote/report responses.
- Broader AI UX (chat rewrite, multi-tenant quotas) remains later releases.
- Full DMS / multi-book accounting remain later releases (unchanged from ADR-004).
