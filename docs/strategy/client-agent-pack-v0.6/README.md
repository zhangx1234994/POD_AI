# PODI Studio Preview v0.6 Client Agent Pack

Last updated: 2026-06-02

This package is for the new client-side agent. It starts a fresh client effort named **PODI Studio Preview**.

The client is an ability-driven business production workspace. It assembles user-facing flows by consuming mid-platform business APIs. It must not become an admin console, an ability marketplace, a project-management product, or a direct caller of ComfyUI/vendor/internal services.

## Files

| File | Purpose |
| --- | --- |
| `01-agent-brief.md` | One-page mission, boundaries, and first tasks for the new agent. |
| `02-product-mvp.md` | Product scope, users, MVP workflow, and non-goals. |
| `03-ui-flow.md` | Page map, screen responsibilities, and interaction requirements. |
| `04-api-contract.md` | Allowed APIs, invocation context fields, run flow, and current gaps. |
| `05-acceptance-checklist.md` | MVP acceptance checklist and regression expectations. |
| `06-gap-log-template.md` | Template for client-to-mid-platform API gaps. |
| `START_PROMPT.md` | Prompt to paste into the new agent thread. |

## Source Of Truth

The current mid-platform and client boundary is documented in:

- `docs/strategy/mid-platform-completeness-v0.6-plan.md`
- `docs/strategy/client-parallel-preview-v0.6-handoff.md`
- `docs/strategy/ability-governance-operating-model-v0.6.md`
- `docs/api/modules/business.md`
- `docs/standards/business-api-enums.md`

`docs/strategy/end-to-end-business-object-api-v0.6.md` and `docs/strategy/project-context-backend-design-v0.6.md` are compatibility implementation notes. Use them only when wiring `/api/business/projects/*`; do not use them as the client product model.

The old client folders and old client docs are historical only. Do not revive old client code without a separate architecture review.

## Current Decision

- v0.6 remains a mid-platform version.
- The client work runs in parallel as a new codebase.
- The client assembles business flow around ability actions.
- The mid-platform governs abilities and provides business APIs, invocation context, assets, run evidence, selection records, and export package evidence.
- `clientContextId/workItemId` is the client's primary context. `projectId` is only a compatibility mapping when the client temporarily uses `/api/business/projects/*`.
