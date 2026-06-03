# 06. Gap Log Template

Use this file whenever the client cannot complete an ability action because the mid-platform does not yet expose enough business API or data.

Do not solve gaps by calling admin, eval, ability, Coze, ComfyUI, vendor, or image-ops internal APIs.

## Gap Entry

```md
### GAP-YYYYMMDD-NN: Short Title

Status: open
Priority: P0 / P1 / P2
Client Page: `/workbench/:workItemId/abilities/...`
User Action:

Expected Client Behavior:

Needed API/Data:

Current API Limitation:

Suggested Mid-Platform API:

Temporary Client Behavior:

Evidence:
- Screenshot:
- Request/response:
- Related workItemId/clientContextId/projectId/runId:
```

## Example

```md
### GAP-20260602-01: Product design downstream data missing

Status: open
Priority: P0
Client Page: `/workbench/:workItemId/abilities/product_design`
User Action:
User selects a fission candidate and wants to generate product design images.

Expected Client Behavior:
Submit a product image generation run using the selected asset, show running status, then store outputs as work item assets.

Needed API/Data:
`POST /api/business/product-design/runs` with `imageUrl`, `clientContextId`, `flowStepKey`, `inputAssetIds`, and product design parameters. Include `projectId` only if the compatibility evidence API is enabled.

Current API Limitation:
The mid-platform has the product design business wrapper, but the client may still need downstream asset grouping, image-set, or export evidence behavior for this step.

Suggested Mid-Platform API:
Clarify or add the missing business API/data contract without bypassing `/api/business/*`.

Temporary Client Behavior:
Show disabled product design step with "能力接入中" and keep selected assets visible.

Evidence:
- Related workItemId: `work_item_xxx`
- Related clientContextId: `work_item_xxx`
- Related projectId if compatibility evidence is enabled: `proj_xxx`
- Related selected asset: `asset_xxx`
```
