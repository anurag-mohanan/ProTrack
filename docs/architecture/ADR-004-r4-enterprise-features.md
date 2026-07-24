# ADR-004: R4 Enterprise Features

## Status

Accepted (2026-07-24)

## Context

R3 delivered business-management controls. R4 adds enterprise foundations without
redesigning Projects, Performance, or Company Settings UX.

## Decision

1. **Optional QA gate** — `Project.qa_gate_enabled` (opt-in). Completing a milestone
   requires `qa_acknowledged=true` when the gate is on; UI confirms before complete.
2. **DMS metadata** — `document_assets` stores entity-linked metadata + local object
   path under upload dir (object-storage backend field ready; not a full DMS).
3. **Learning plans** — plans/items seeded from skill-matrix gaps; Performance → Skills
   shows create-from-gaps and item status.
4. **Multi-entity prep** — `legal_entities` table + settings API; default entity ensured;
   operations remain single-tenant.

## Consequences

- Full DMS (versioning, ACL, retention) and multi-book accounting remain later releases.
- QA gate is soft process control (acknowledgement), not an external QA system integration.
