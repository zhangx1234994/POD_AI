# 05. Acceptance Checklist

## Functional MVP

- [ ] A user can open `/workbench`.
- [ ] A user can create or open a work item.
- [ ] A user can upload or register one source image as `input_image`.
- [ ] Work item detail shows available ability actions, assets, runs, selections, and export packages.
- [ ] Pattern extraction can be submitted with `clientContextId` and `flowStepKey=pattern_extract`; `projectId` is used only when compatibility asset evidence is enabled.
- [ ] The client stores and displays the returned `runId`.
- [ ] The client polls until `queued/running/succeeded/failed`.
- [ ] A successful pattern extraction result appears in work item assets.
- [ ] Fission can be submitted from a saved work item asset with `flowStepKey=variant_fission`.
- [ ] Fission result grid can render multiple images.
- [ ] A user can select at least one candidate result.
- [ ] Selection writes `targetFlowStepKey=product_design`.
- [ ] Product design step handles missing API as a clear gap or disabled state.
- [ ] Export package draft can be created from selected assets.
- [ ] Export package screen shows manifest summary.

## Interaction Quality

- [ ] No first-screen marketing hero.
- [ ] No admin-only terms in the primary user path.
- [ ] Empty work item state leads to create work item.
- [ ] Empty asset state leads to upload/register asset.
- [ ] Running state explains what is happening and when to refresh.
- [ ] Failure state shows business message and `runId`.
- [ ] Advanced parameters are collapsed by default.
- [ ] Asset cards have stable dimensions and do not jump while loading.
- [ ] Buttons and labels fit on desktop and mobile widths.
- [ ] The user can always return to the workbench overview.
- [ ] The primary UI does not look like a project-management system.

## API Boundary

- [ ] No calls to `/api/admin/*`.
- [ ] No calls to `/api/evals/*`.
- [ ] No calls to `/api/abilities/*`.
- [ ] No calls to `/api/ability-tasks/*`.
- [ ] No calls to `/api/coze/*`.
- [ ] No direct ComfyUI/vendor/image-ops URLs.
- [ ] Every missing backend requirement is recorded in the gap log.

## Error Coverage

- [ ] Missing work item name.
- [ ] Invalid asset URL.
- [ ] Missing image URL for a business run.
- [ ] Work item or compatibility evidence container not found.
- [ ] Asset not found or foreign asset.
- [ ] Business run failed.
- [ ] Run polling returns not found.
- [ ] Export with no selected assets.

## Evidence To Report

When the new agent reports completion, include:

- Local URL.
- Screenshots for `/workbench`, work item detail, an ability action workspace, a running task, success result, failure state, and export draft.
- List of APIs called.
- List of API gaps.
- Test commands run.
- Remaining risks.
