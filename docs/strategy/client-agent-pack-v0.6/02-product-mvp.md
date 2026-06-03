# 02. Product MVP

## Product Name

**PODI Studio Preview**

## Positioning

PODI Studio Preview is an ability-driven business production workspace for design workflows. It is used when a business partner does not yet have a mature frontend, or when PODI needs a reference client for end-to-end workflows.

## Primary Users

| User | Needs |
| --- | --- |
| Business operator | Upload source material, generate candidates, choose results, package deliverables. |
| Design operator | Review result quality, compare variants, continue creating from selected assets. |
| Internal product/operator | Validate whether mid-platform ability APIs support real client workflows. |

## MVP Flow

1. Open the workbench and create or open a work item.
2. Upload or register at least one source image.
3. Choose an ability action and run pattern extraction with `clientContextId` and `flowStepKey`; pass `projectId` only if the compatibility evidence API is enabled.
4. Show run status and result assets.
5. Run fission from a selected or extracted asset.
6. Select one or more candidate results.
7. Move to product design or image-set step.
8. Generate an export package draft.

## MVP Non-Goals

- No marketing landing page.
- No template marketplace.
- No wallet or billing UI.
- No admin configuration.
- No raw workflow/node editor.
- No direct ability marketplace.
- No project-management-first product experience.
- No old client code revival.

## User Experience Principles

- First screen should show available production actions, active work item, and next action.
- Business words first; technical details only in secondary debug views.
- Every async run must show status, retry/refresh behavior, and `runId`.
- Every failure must show a business-readable reason and `runId`.
- Empty states must lead to a concrete action.
- Advanced parameters should be collapsed by default.
- Assets should always be reusable for the next step.

## First MVP Milestone

The first milestone is complete when a user can open the workbench, create a work item, run pattern extraction, run fission from a saved asset, select a candidate, and create a delivery manifest draft without reading admin or technical documentation. The product experience should stay focused on ability actions; backend compatibility containers must remain hidden behind `clientContextId/workItemId`.
