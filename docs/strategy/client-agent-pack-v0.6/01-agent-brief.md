# 01. Agent Brief

## Mission

Build the first usable **PODI Studio Preview** client: a clean ability-driven production workspace that helps a business user move from source material to reusable design assets and a delivery package.

The first version should prove the flow, not the full SaaS product.

## Product Boundary

The client owns:

- User-facing ability workflow and page sequence.
- User actions and next-step guidance.
- Uploading or registering source assets.
- Calling mid-platform business APIs.
- Displaying run status, results, errors, and `runId`.
- Letting users select candidate results for the next step.
- Preparing export package experience.
- Using `clientContextId/workItemId` as the client context while treating `projectId` only as a compatibility mapping when needed.

The client does not own:

- Ability management.
- Workflow editing.
- Executor routing.
- LoRA, model, key, or vendor configuration.
- Admin dashboards.
- Eval dashboards.
- Direct ComfyUI, vendor-api, image-ops, Coze, or atomic ability calls.

## Hard API Boundary

Allowed:

- `/api/business/*`
- `/api/business/projects/*` only for compatibility evidence APIs such as asset registration, selections, and exports.
- `/api/media/*` for controlled upload and media flow

Forbidden:

- `/api/admin/*`
- `/api/evals/*`
- `/api/abilities/*`
- `/api/ability-tasks/*`
- `/api/coze/*`
- ComfyUI node URLs
- vendor-api-ops URLs
- image-ops-service internal URLs

## First Build Scope

Build only the first business production flow:

```text
Workbench
  -> Create or open a work item
  -> Pick an ability action
  -> Upload or register source material
  -> Pattern extraction
  -> Fission candidates
  -> Select candidate
  -> Product image or image set placeholder
  -> Export package draft
```

If a downstream ability is missing, implement the UI state and record a gap. Do not bypass the mid-platform. Do not redesign the client as a project-management app; keep the main experience focused on production actions such as extract, fission, edit, product image, model shot, video, and export.

## Working Rule

If the client cannot complete a user action because the mid-platform API is missing or insufficient, write a gap using `06-gap-log-template.md` and continue with a mock or disabled state.
