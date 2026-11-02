# ProTrack Phase 6 — AI Engineering Management Assistant

Status: Stages 1–6 complete. Backend, frontend, migration and tests are in place; see section 10 for results and section 11 for what is not done.

## 1. Readiness findings (Stage 1)

Checked against the repository on 2026-10-30, not against earlier prompts.

### 1.1 Phase 0–5 status

| Phase | Evidence in the repository | Status |
| --- | --- | --- |
| 0 Quote-to-delivery audit | `docs/PHASE0_QUOTE_TO_DELIVERY_AUDIT.md` (baseline: 12 known failing tests) | Present |
| 1 Engineering metrics, stage delivery, quote-to-delivery report | `app/services/engineering_metrics_service.py`, `app/services/reporting/engineering_performance.py`, `quote_to_delivery.py`, docs `PHASE1_STEP1..3` | Present |
| 2 Control Tower | `app/services/control_tower_service.py`, `app/models/control_tower.py`, `phase108` migration, `/control-tower` API | Present |
| 3 Forecasting | `app/services/forecasting/{effort,capacity,finance}.py`, `/forecasts` API, `docs/PHASE3_FORECASTING.md` | Present |
| 4 Engineering skills | `app/services/skills/*`, `phase109` migration, `docs/PHASE4_SKILLS.md` | Present |
| 5 Template reconciliation and workflow automation | `app/services/template_reconciliation.py`, `app/services/automation/*`, `phase110` migration, `/automation` API, `docs/PHASE5_WORKFLOW.md` | Present. Commit `caffb65` holds most of it; `app/schemas/template_reconciliation.py`, `frontend/src/api/automation.ts`, `frontend/src/pages/admin/AutomationPage.tsx` and the lifecycle-filter edits are still uncommitted although the commit imports them. |

### 1.2 Reliable sources the assistant reuses (no second calculation)

| Question area | Authoritative service | Access rule reused |
| --- | --- | --- |
| Project hours (quoted, original and current approved estimate, actual split by timesheet status, remaining, variance), milestone readiness, delivery dates and variance | `engineering_metrics_service.build_engineering_metrics_batch` (read-only) | `project_visibility_clause`; quote details only with Finance view |
| Risks and outstanding actions | `control_tower_service.list_findings`, `build_summary`, `latest_runs`, `control_tower_state` | `can_view_reports` + `resolve_report_scope` (same `FindingScope` as the API) |
| Delivery and stage-hours performance by period | `reporting.engineering_performance.build_engineering_performance` | `can_view_reports` + report scope + visibility clause |
| Remaining-effort forecast | `forecasting.effort.build_engineering_forecast` | `can_view_reports` |
| Capacity (shifts, holidays, employment dates, availability status, allocation %) | `forecasting.capacity.build_capacity_forecast` | `skills.access.can_view_capacity` + `resolve_team_scope` |
| Candidate matching (verified vs claimed skills, availability) | `skills.matching.recommend_candidates` | `SkillAccess.can_match_resources` |
| Skill coverage gaps | `skills.gaps.build_gap_report` | `SkillAccess.can_view_others` / `visible_user_ids` |
| Awarded, invoiced, remaining-to-invoice, collected, outstanding per quote | `finance.customer_financial_service.list_quote_financial_snapshots` → `quote_cash_ledger_service.calculate_awarded_quote_financial_status` (read-only) | Finance module `view` |
| Receivables aging by due date | `finance.receivables_service.build_receivables_aging` (read-only) | Finance module `view` |
| FY month-on-month billing and collection | `finance.fy_turnover_service.build_fy_turnover_control` | Finance module `view` |
| Billing and collection forecast with assumptions | `forecasting.finance.build_finance_forecast` | Finance module `view` |

### 1.3 Incomplete or unreliable data

* All 24 projects in the working database copy have no project type or template (Phase 5 migration check), so template-based answers are unavailable for existing projects.
* There is no separate Project Manager field. The Design Leader is the accountable lead and is reported as such.
* Planned leave is not recorded. Capacity uses shifts, holidays, employment dates, availability status and allocation percentage only, so availability is indicative.
* Actual payment lead time is not available. `aggregate_customer_financial_summary.average_days_to_payment` measures invoice date to due date (contract terms), not when money arrived. The assistant reports payment lead time as unavailable rather than computing a new figure.
* Control Tower findings exist only after an evaluation has run. The assistant passes on the "never evaluated" / "stale" state instead of reporting "no risks".
* Actual hours: draft and rejected timesheet hours are shown separately, as the metrics service does. Whether they should count is still an open business decision from Phase 1.

### 1.4 Services that must not be exposed

* `payment_schedule_service.summarize_quote_payment_schedule` writes milestone trigger status while reading. `aggregate_customer_financial_summary` calls it, so neither is exposed.
* Any create/update service (invoices, payments, timesheets, projects, milestones, assignments). The assistant has read tools only.

### 1.5 Existing AI layer and security findings

* `app/services/ai/providers` already provides an OpenAI-compatible client configured through `AI_PROVIDER`, `AI_API_KEY`, `AI_BASE_URL` and `AI_MODEL` (environment only), with an offline heuristic fallback. Phase 6 extends this rather than adding a second integration.
* `POST /ai/chat` (regex router over org-wide data) has no permission check, so any signed-in user could read designer utilisation and project lists. Phase 6 restricts it to the manager roles used by the other `/ai/*` endpoints.
* `/ai/quote/{project_id}`, `/ai/health` and `/ai/knowledge` also skip project scoping. They are recorded here and left unchanged in this phase.

### 1.6 Persistence

Conversation history, messages, recommendations and tool-execution audit need new tables. The additive migration pattern (`create_all` for new tables plus `phaseNNN_*_schema_sync` for enum values) supports this without touching existing tables.

## 2. Architecture (Stage 1)

```
Assistant page (React)                       frontend/src/pages/AssistantPage.tsx
   │  REST, JSON only (no keys)
   ▼
Conversation API                             app/api/v1/assistant.py
   │  owner check, rate limit, input limits
   ▼
Orchestrator                                 app/services/assistant/orchestrator.py
   │  bounded tool loop, untrusted-data framing, offline mode
   ├──► Provider adapter                     app/services/ai/providers/openai_compat.py (chat_with_tools)
   │                                         app/services/assistant/provider.py
   ├──► Tool registry (read-only)            app/services/assistant/tools/*.py
   │        │  permission check per tool, before any data is read
   │        ▼
   │    Existing calculation services        (section 1.2)
   ├──► Recommendations                      app/services/assistant/recommendations.py
   └──► Audit                                ai_tool_executions, Activity (ai_recommendation_decided)
Persistence                                  app/models/assistant.py
```

Principles:

1. The model never sees the database. It can only call named tools; each tool has a JSON schema, a permission check run against the signed-in user, and a handler that calls an existing service.
2. Permissions are checked in the backend before data is read, and only permitted data is sent to the provider.
3. Tool results are wrapped as untrusted data. Text inside records is never treated as an instruction.
4. No tool writes business data. The only write available to the model is creating a recommendation record with status New.
5. Earlier answers are not reused as facts. Each turn sends prior user and assistant text for context only; figures are fetched again through tools.
6. Without a configured provider, ProTrack keeps working: the page shows a configuration message and suggested questions still run their bound tool directly, showing data tables without generated prose.

## 3. Provider integration (Stage 2)

No live provider or credential was available or assumed. The integration extends the existing OpenAI-compatible client instead of adding a second one.

* `OpenAiCompatLlmProvider.chat_with_tools(messages, tools, temperature, max_tokens, timeout_seconds)` sends a standard `/chat/completions` request with function tools and returns `{content, tool_calls, usage, model}`. It works with any endpoint that implements the OpenAI chat-completions tool-calling format (OpenAI, Azure OpenAI through a compatible gateway, local servers such as vLLM or Ollama's OpenAI endpoint).
* Failures raise `LlmProviderError(kind, message)` with kind `timeout`, `auth`, `rate_limited`, `unavailable` or `bad_response`. Messages never include the key or the request body.
* `app/services/assistant/provider.py` chooses the provider: none when the assistant is disabled; the OpenAI-compatible provider when `AI_PROVIDER=openai` and `AI_API_KEY` is set; otherwise none (offline mode). Tests inject a scripted provider through `set_provider_override`; no test calls a network API.
* `GET /assistant/status` reports `enabled`, `configured`, `mode` (`disabled`, `offline`, `llm`), provider name and model. It never returns the key or the endpoint URL.

Configuration (server environment only; never in the database or the frontend):

| Variable | Default | Meaning |
| --- | --- | --- |
| `AI_ASSISTANT_ENABLED` | `true` | `false` hides answers and shows "switched off" |
| `AI_PROVIDER` | `heuristic` | `openai` enables the OpenAI-compatible provider |
| `AI_API_KEY` | empty | Provider key or gateway token (a secret reference resolved by the deployment) |
| `AI_BASE_URL` | `https://api.openai.com/v1` | Endpoint for compatible providers |
| `AI_MODEL` | `gpt-4o-mini` | Model name; must support tool calling |
| `AI_TEMPERATURE_PERCENT` | `10` | Temperature × 100 (0.10) |
| `AI_MAX_TOKENS` | `1200` | Completion token limit per call (200–4000) |
| `AI_TIMEOUT_SECONDS` | `30` | Per-call timeout (5–120) |
| `AI_MAX_TOOL_ROUNDS` | `4` | Tool-call rounds per question (1–8); the last round is forced to answer |
| `AI_RATE_LIMIT_PER_MINUTE` | `10` | Questions per user per minute |
| `AI_MAX_INPUT_CHARS` | `2000` | Maximum question length |

## 4. Services reused and tools exposed (Stages 3–4)

The model can call 15 tools and nothing else. Each tool validates its arguments against a strict schema (unknown keys, wrong types, out-of-range numbers and unknown enum values are refused), checks the user's permission before reading anything, calls the service listed in section 1.2, and returns data, sources (record links), display tables and limitations.

| Tool | Module | Permission | Service |
| --- | --- | --- | --- |
| `find_projects` | Projects | Project visibility | `build_engineering_metrics_batch` |
| `get_project_summary` | Projects | Project visibility; findings only with reports access | metrics batch, Control Tower `list_findings` |
| `list_project_milestones` | Projects | Project visibility | metrics batch (milestone readiness) |
| `list_risk_findings` | Management | `can_view_reports` + report scope | Control Tower `list_findings`, `control_tower_state` |
| `get_capacity_overview` | Resources | `can_view_capacity` + team scope | `build_capacity_forecast` |
| `find_resource_candidates` | Resources | `can_match_resources` | `skills.matching.recommend_candidates` |
| `get_skill_gaps` | Resources | `can_view_others` | `skills.gaps.build_gap_report` |
| `list_billing_status` | Finance | Finance view | `list_quote_financial_snapshots` |
| `get_receivables_aging` | Finance | Finance view | `build_receivables_aging` |
| `get_fy_billing` | Finance | Finance view | `build_fy_turnover_control` |
| `get_finance_forecast` | Finance | Finance view | `build_finance_forecast` |
| `get_delivery_performance` | Management | `can_view_reports` + report scope | `build_engineering_performance` |
| `get_control_tower_summary` | Management | `can_view_reports` + report scope | Control Tower `build_summary` |
| `get_effort_forecast` | Management | `can_view_reports` | `build_engineering_forecast` |
| `record_recommendation` | Recommendations | Category-dependent (finance categories need finance view) | Writes one `ai_recommendations` row, status New |

Rules carried in the tool output rather than left to the model:

* Hours: quoted, original approved estimate, current approved estimate, actual (approved, submitted, draft, rejected shown separately), remaining and variance come straight from the metrics service. Missing actual hours are returned as null with "missing, not zero". A project with only quoted hours is labelled as such.
* Finance: awarded (current quote revision), invoiced, remaining to invoice, collected and outstanding are separate fields. Totals are per currency and never summed across currencies. Finance treats every active quote as awarded; this is stated in the tool output.
* Resources: capacity never assumes 8 hours a day; it uses shifts, holidays, employment dates, availability and allocation. Leave is not recorded. Suitability uses verified skill levels only; self-declared levels are shown as claims. Skills are never inferred from past assignments. Candidate output says nobody is assigned.
* Insights: delivery performance with fewer than 5 completed projects in the period sets `insufficient_sample` and returns rates as null, so no trend can be stated. Each insight carries its period and record count.
* Risk: the Control Tower is the only risk source. If it has never been evaluated, or the last run is stale, the tool says so instead of returning an empty "no risks" list.
* A project outside the user's scope gets the same "not found among the projects you can access" message as a project that does not exist.

The readback against a migrated copy of the working database (section 10) ran every read tool for each role found there without errors.

## 5. Entities and migration (Stage 2)

New tables (created by `Base.metadata.create_all`; all have UUID keys, timestamps and `tenant_id`):

| Table | Purpose |
| --- | --- |
| `ai_conversations` | Owner, title, module, optional project, last message time, soft-delete flag |
| `ai_messages` | Role, content, status (`ok`, `data`, `offline`, `error`), error code, sources, tables, limitations, follow-ups, tool-call summary, provider, model, token counts, latency, feedback |
| `ai_recommendations` | Conversation and message, creator, project, module, category, title, description, evidence (source keys), suggested action and owner, priority, status, decision and completion actors and times, resolution notes |
| `ai_tool_executions` | Per tool call: user, conversation, message, tool, validated arguments, status (`ok`, `denied`, `invalid`, `error`), record count, duration, short detail. No record contents. |

`app/db/phase111_ai_assistant_schema_sync.py` adds two enum values on PostgreSQL only (`activity_action.ai_recommendation_decided`, `entity_type.ai_recommendation`) with `ADD VALUE IF NOT EXISTS`. SQLite stores enums as text, so nothing is needed there. No existing table, column, enum or relationship is changed or dropped.

## 6. Frontend (Stage 6)

* Navigation: "Assistant" entry in the main navigation for users with the Dashboard module (route `/assistant`, breadcrumb "ProTrack Assistant"). What each user can ask is decided by the backend tools, not by the menu.
* `frontend/src/pages/AssistantPage.tsx` with two tabs:
  * **Ask**: conversation list (new, rename, delete), status banner (configuration message when offline, notice when disabled), suggested questions grouped by category, message list, question box (Enter sends, Shift+Enter new line, character counter near the limit), loading state ("Checking ProTrack data…") and error alerts (rate limit, input limit, network).
  * **Recommendations**: list with status filter and paging, evidence chips linking to the records, decision buttons limited to the allowed transitions, optional note, and a link to the related workflow.
* `components/assistant/AssistantMessageView.tsx` renders each answer: text, data tables (missing values shown as "—"), source chips that open the project, quote or report, collapsible data limitations, follow-up questions, recorded recommendations, copy and helpful/not-helpful feedback.
* `frontend/src/api/assistant.ts` is the typed client. No key, endpoint or prompt is held in the browser.
* Responses are not streamed. The status endpoint reports `streaming: false`, and the UI shows a progress bar while waiting.

## 7. Question categories

Suggested questions appear only when the user's permissions allow the bound tool and the data exists (for example, finance suggestions need at least one quote; skill suggestions need skills in the taxonomy).

| Category | Suggested questions |
| --- | --- |
| Projects | Projects due in the next 14 days; overdue open projects; projects over their approved estimate; most severe open risks |
| Resources | Capacity over the next four weeks; critical skill coverage gaps |
| Finance | Quotes with work to invoice or payments outstanding; overdue invoices; billing this financial year; collections forecast for six months |
| Management | Delivery performance this quarter; Control Tower summary; open projects with the most remaining effort |

Free-text questions (provider configured) can also ask for a single project's summary or milestones, people for a skill, and combinations of the above.

## 8. Security

* Every tool checks the signed-in user's permission in the backend before reading data, using the same rules as the matching ProTrack page (section 1.2). Data is filtered before it is sent to the provider. Hiding menu items and prompt instructions are not relied on.
* The model has no SQL, no HTTP and no generic data access. Unknown tool names and unexpected arguments are refused and audited.
* Retrieved records are passed as untrusted data inside a fixed frame; the system prompt says text inside records is never an instruction. A test plants an instruction in a project note and checks it stays inside the frame.
* Personal data is minimised: people are referred to by name only; email addresses, phone numbers and salary-related fields are never included in tool output. A test checks that the provider payload has no email addresses or secrets.
* Keys stay in the server environment. They are not returned by any endpoint, stored in the database, or written to logs. The assistant and provider code have no logging of prompts or responses; tool errors are recorded by exception type only.
* Each tool call is audited in `ai_tool_executions` (who, which tool, arguments, status, record count, duration). Administrators can read this at `GET /assistant/audit/tool-executions`.
* Limits: per-user rate limit, input length limit, token limit, call timeout, and a bounded number of tool rounds per question.
* Conversations are visible only to their owner (404 for anyone else, including on feedback). Deleting a conversation hides it from the owner; messages, recommendations and the access audit are kept.
* `POST /ai/chat` (the older dashboard widget) is now limited to manager roles.

## 9. Recommendation workflow (Stage 5)

1. During an answer, the model may call `record_recommendation` (at most 3 per question). The evidence must be source keys returned by tools in the same question; otherwise the call is refused. A suggested owner is kept only if that person is on the project (design leader, designer or surfacer).
2. The recommendation is stored with status **New**. Nothing in ProTrack is changed.
3. The owner of the conversation, or an administrator, decides in the Recommendations tab:
   * New → Accepted, Rejected or Deferred
   * Deferred → Accepted or Rejected
   * Accepted → Completed or Deferred
   * Rejected and Completed are final. Other transitions return 409.
4. Each decision records who decided and when (`decided_by`, `decided_at`, `completed_by`, `completed_at`, note) and writes an Activity entry (`ai_recommendation_decided`) with the previous and new values. These appear in the Phase 5 Decision Audit as kind `ai_recommendation`, filterable by project.
5. Accepting a recommendation does not execute it. The user carries out the action in the linked workflow (project page, Control Tower, resource planning or finance).

## 10. Test results

`tests/test_ai_assistant.py`: 27 tests, all passing, using a scripted provider only (no network, no tokens).

| Brief test | Covered by |
| --- | --- |
| 1, 2, 15 Provider configured / missing / failing | `test_status_without_provider_is_offline_and_never_exposes_the_key`, `test_free_text_without_provider_returns_configuration_message_and_protrack_keeps_working`, `test_disabled_assistant_reports_disabled`, `test_suggested_question_without_provider_answers_from_the_tool_directly`, `test_provider_timeout_is_reported_and_the_question_is_kept` |
| 3, 4 Answers use existing calculations | `test_project_summary_reuses_engineering_metrics_and_cites_sources`, `test_overdue_milestones_match_the_metrics_service`, `test_missing_actual_hours_are_never_reported_as_zero`, `test_finance_tool_returns_finance_service_values_for_finance_users`, `test_overdue_receivables_come_from_the_aging_service` |
| 5, 6, 7, 12 Permissions | `test_designer_cannot_reach_finance_capacity_or_matching_tools`, `test_projects_outside_scope_look_the_same_as_projects_that_do_not_exist` |
| 6, 7, 8 Resources and insights | `test_capacity_and_candidates_state_their_basis`, `test_insights_refuse_trends_from_small_samples`, `test_unevaluated_control_tower_is_not_reported_as_no_risk` |
| 13, 14 No SQL, no arbitrary calls, no writes | `test_unknown_tools_and_extra_arguments_are_refused`, `test_only_read_tools_and_recommendation_recording_are_registered`, `test_injected_instructions_in_records_stay_inside_the_untrusted_data_frame`, `test_tool_loop_is_bounded` |
| 8, 11 Privacy and persistence | `test_provider_payload_contains_no_email_addresses_or_secrets`, `test_previous_answers_are_context_only_and_data_is_fetched_again`, `test_conversations_are_private_renamable_and_soft_deleted`, `test_rate_and_input_limits` |
| 9, 10 Recommendations | `test_recommendation_is_recorded_from_cited_evidence_and_decisions_are_audited`, `test_recommendation_without_evidence_from_this_turn_is_refused` |
| 16 Audit and regression | `test_tool_execution_audit_is_admin_only_and_holds_no_record_contents`, `test_legacy_ai_chat_requires_manager_access`, full suite below |

Other checks run:

* Full backend suite: 1369 passed, 12 failed, 1 skipped (41 minutes). The 12 failures are exactly the baseline failures listed in `docs/PHASE0_QUOTE_TO_DELIVERY_AUDIT.md`; none are new. (Phase 5 run: 1342 passed; the difference is the new assistant tests and other additions since.)
* Frontend: `npx tsc -b` clean; `npm run build` succeeds (`AssistantPage` chunk 31 kB); ESLint clean on all new and changed files except a pre-existing `react-refresh/only-export-components` error in `AppBreadcrumbs.tsx` (the exported `useBreadcrumbTitle` hook), which this phase did not introduce.
* Ruff (`F`, `E9`) clean on the new backend code.
* Migration check on a copy of `protrack.db` (never the original): 166 existing tables unchanged by row count and content hash; the four `ai_*` tables created; no columns added; a second run made no changes. A second copy taken through the full application startup chain then ran every read tool for each role in the data (Admin and Engineering Manager: 14 tools; Designer, Senior Designer, Surfacer: 3 project tools; Junior Designer: no visible projects, so no suggestions) with no errors. The original database's last write time is unchanged (2026-10-29 12:20:48).
* No browser check was run, as agreed; verification relies on tests and the build.

## 11. Limitations

* No live provider was tested. Free-text answers depend on a model that supports OpenAI-style tool calling; quality varies by model.
* Responses are not streamed.
* The rate limit is held in memory per server process. With several workers, each has its own counter.
* Recommendations are visible to their creator and administrators only. There is no team-level sharing yet.
* Actual payment lead time, planned leave, project type and template (all current projects) are unavailable, so related questions are answered as "not recorded".
* Whether draft and rejected hours count toward actuals is still an open business decision; they are shown separately.
* `/ai/quote/{id}`, `/ai/health` and `/ai/knowledge` remain without project scoping (section 1.5).
* `build_receivables_aging` still reads `project.name`, which does not exist (Phase 0 audit, item B0.x). No quote in the working data is linked to a project, so it works today. Once a quote is linked, `get_receivables_aging` will fail in the same way as the Finance receivables page; the assistant rolls back, records the failure in the audit and tells the user the data could not be retrieved. The Finance service was not changed in this phase.
* Previous answers are not re-validated. Each new question fetches data again, but older messages keep the values they had when written.
* The assistant does not answer questions about timesheet entries of individual people, HR records or IT assets; no tools exist for them.

## 12. Setup

1. Deploy the code. On startup, `create_all` creates the four `ai_*` tables and `phase111` adds the PostgreSQL enum values. No manual migration is needed.
2. Without further configuration the assistant runs in offline mode: the page explains that no provider is configured and suggested questions show ProTrack data directly.
3. To enable free-text answers, set in the server environment (not in `.env` files committed to the repository): `AI_PROVIDER=openai`, `AI_API_KEY=<secret from the deployment's secret store>`, and optionally `AI_BASE_URL` and `AI_MODEL`. Restart the API. `GET /api/v1/assistant/status` should then show `"mode": "llm"`.
4. To switch the assistant off, set `AI_ASSISTANT_ENABLED=false`.
5. Run the tests with `python -m pytest tests/test_ai_assistant.py`; no key is needed.

## 13. Next increment

* Streaming responses (server-sent events) once a provider is chosen.
* Shared rate limiting (database or cache) for multi-worker deployments.
* Team-level visibility of recommendations for engineering managers, using report scope.
* Tools for timesheet compliance and project timeline events, with the same permission model.
* Scoping fixes for the remaining `/ai/*` endpoints.
* Evaluation set of real questions with expected tool calls, run against the chosen model before enabling it for all users.
