# 03. UI Flow

## Page Map

Build only six pages first. Use a workbench and ability-action mental model; `clientContextId/workItemId` is the client context, while `projectId` is only a compatibility mapping when using `/api/business/projects/*`.

| Route | Purpose |
| --- | --- |
| `/workbench` | Ability action entry, recent work items, recent tasks, and source material. |
| `/workbench/:workItemId` | Work item overview, available ability actions, current action, recent assets and runs. |
| `/workbench/:workItemId/abilities/:abilityKey` | Ability action workspace: input, submit, waiting state, result view, selection. |
| `/assets` | Asset browser for reusable materials and generated outputs. |
| `/tasks` | Business run history grouped by ability, work item, and client step. |
| `/exports/:packageId` | Export package draft, manifest, download placeholder. |

## Recommended Step Keys

The client owns these keys. The mid-platform records them but does not enforce order.

| Step Key | Display Name | Initial Ability |
| --- | --- | --- |
| `upload_assets` | Upload source material | Media/work-item asset registration |
| `pattern_extract` | Pattern extraction | `/api/business/pattern-extract/runs` |
| `variant_fission` | Candidate fission | `/api/business/fission/runs` |
| `candidate_selection` | Select candidates | Compatibility: `/api/business/projects/{projectId}/selections` when asset evidence is enabled |
| `product_design` | Product design | Gap: `product_design` business API |
| `product_image_set` | Image set and angles | Gap: `product_image_set` business API |
| `model_shot` | Model shot | Gap: `model_shot` business API |
| `promo_video` | Promo video | Gap: `promo_video` business API |
| `export_package` | Export package | Compatibility: `/api/business/projects/{projectId}/exports` when package evidence is enabled |

## Work Item Overview

Must show:

- Work item name and status.
- Available ability actions.
- Next recommended action.
- Latest successful assets.
- Latest running or failed runs.
- Delivery readiness.

Must not show by default:

- Executor names.
- Workflow IDs.
- LoRA filenames.
- Raw vendor response.
- Internal URLs.

## Step Workspace Pattern

Each step should use the same structure:

1. Input assets and core parameters.
2. Primary action button.
3. Running status with `runId` after submit.
4. Result grid.
5. Select result action when applicable.
6. Error state with business message and `runId`.
7. Secondary details collapsed by default.

## Visual Direction

This is an operational tool, not a marketing website.

- Dense but calm layout.
- Clear stage progress.
- Asset grids with stable dimensions.
- Short labels.
- No oversized hero section.
- No decorative gradient-heavy UI.
- Use cards only for repeated assets, tasks, and modal-like panels.
- Avoid nested cards.
- Keep advanced controls collapsed.

## Empty States

Every empty state must provide a concrete action:

| Empty State | Action |
| --- | --- |
| No work items | Create work item |
| No assets | Upload source image |
| No pattern result | Run pattern extraction |
| No fission result | Run fission |
| No selected candidate | Select a candidate |
| Missing downstream ability | Show disabled step and log API gap |

## Task Status

Use the public business states:

- `queued`
- `running`
- `succeeded`
- `failed`

If the backend returns older internal states, normalize them to the public states before rendering.
