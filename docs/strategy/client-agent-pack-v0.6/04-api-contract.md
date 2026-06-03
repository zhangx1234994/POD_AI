# 04. API Contract

## Authentication

Use the business API authentication configured by the environment.

Preferred header:

```http
X-PODI-API-Key: <business api key>
```

Do not hardcode keys in source code, docs, fixtures, screenshots, or examples.

## Work Item Context APIs

Use `clientContextId/workItemId` as the client-side context for normal business runs. The backend path `/api/business/projects/*` is a compatibility evidence API for asset registration, selections, and export packages. Do not design the product as a project-management app.

### Compatibility: Create Work Item Evidence

`POST /api/business/projects`

Request:

```json
{
  "name": "Summer Pattern Project",
  "scenario": "pattern_to_product",
  "flowTemplateId": "pattern_to_product_v1",
  "currentFlowStepKey": "upload_assets",
  "metadata": {
    "clientProjectNo": "P-001"
  }
}
```

Required:

- `name`

Common errors:

- `PROJECT_NAME_REQUIRED`
- `PROJECT_SCENARIO_INVALID`
- `BUSINESS_USER_SCOPE_REQUIRED`
- `BUSINESS_USER_SCOPE_FORBIDDEN`

### Compatibility: Work Item Evidence Detail

`GET /api/business/projects/{projectId}`

Returns:

- `project`
- `assets`
- `runs`
- `selections`
- `exportPackages`

### Compatibility: Register Work Item Asset

`POST /api/business/projects/{projectId}/assets`

Request:

```json
{
  "assetType": "input_image",
  "url": "https://podi.oss-cn-hangzhou.aliyuncs.com/input.png",
  "contentType": "image/png",
  "fileName": "input.png",
  "flowStepKey": "upload_assets",
  "inputTags": ["fabric"],
  "metadata": {
    "source": "client-upload"
  }
}
```

Allowed `assetType` values:

- `input_image`
- `pattern`
- `variant`
- `product_image`
- `angle_image`
- `model_image`
- `video`
- `text`
- `other`

Common errors:

- `PROJECT_NOT_FOUND`
- `PROJECT_FORBIDDEN`
- `PROJECT_ASSET_TYPE_INVALID`
- `PROJECT_ASSET_URL_REQUIRED`
- `PROJECT_ASSET_URL_INVALID`

### Compatibility: List Work Item Assets

`GET /api/business/projects/{projectId}/assets`

Query:

- `assetType`
- `selected`
- `limit`
- `offset`

### Compatibility: List Work Item Runs

`GET /api/business/projects/{projectId}/runs`

Use this to render the task timeline and ability-action status.

### Compatibility: Select Candidates

`POST /api/business/projects/{projectId}/selections`

Request:

```json
{
  "assetIds": ["asset_variant"],
  "sourceFlowStepKey": "variant_fission",
  "targetFlowStepKey": "product_design",
  "note": "Selected for product design"
}
```

Common errors:

- `PROJECT_SELECTION_ASSET_REQUIRED`
- `PROJECT_SELECTION_ASSET_INVALID`
- `PROJECT_SELECTION_TARGET_REQUIRED`

### Compatibility: Create Export Package

`POST /api/business/projects/{projectId}/exports`

Current behavior: creates a `ready` ZIP package. The ZIP contains `manifest.json`, `summary.json`, `assets.json`, `run_ids.json`, and `README.txt`. Media binaries are not copied into the ZIP yet; media is referenced through controlled URLs.

Request:

```json
{
  "assetIds": ["asset_variant", "asset_product"],
  "includeRunEvidence": true,
  "includeQualitySummary": true
}
```

Common errors:

- `PROJECT_EXPORT_ASSETS_EMPTY`
- `PROJECT_EXPORT_ASSET_INVALID`
- `PROJECT_EXPORT_BUILD_FAILED`
- `PROJECT_EXPORT_FILE_NOT_FOUND`

## Business Run Context

Every business run can include optional invocation context. Prefer `clientContextId`; pass `projectId` only when the client has created or reused a compatibility evidence container:

```json
{
  "clientContextId": "work_item_xxx",
  "flowStepKey": "variant_fission",
  "flowStepName": "Candidate fission",
  "flowTemplateId": "pattern_to_product_v1",
  "inputAssetIds": ["asset_input"],
  "clientRequestId": "client_req_001"
}
```

Compatibility payload when using `/api/business/projects/*`:

```json
{
  "clientContextId": "work_item_xxx",
  "projectId": "proj_xxx",
  "flowStepKey": "variant_fission",
  "inputAssetIds": ["asset_input"],
  "clientRequestId": "client_req_001"
}
```

The same fields can also be placed inside `metadata.projectContext` if a client wrapper requires it, but top-level fields are preferred.

Mid-platform behavior:

- Creates a normal business run.
- Links the run to client context and, when provided, the compatibility evidence container.
- Stores the client step metadata.
- Validates that `inputAssetIds` belong to the compatibility evidence container when `projectId` is provided.
- On successful terminal state, stores output `imageUrls/videoUrls` as asset evidence when compatibility asset sync is enabled.
- Does not decide the next step.

## Existing Business APIs To Use First

| Business Ability | Endpoint | Required Input | Output |
| --- | --- | --- | --- |
| Pattern extraction | `POST /api/business/pattern-extract/runs` | `imageUrl` | `imageUrls` |
| Fission | `POST /api/business/fission/runs` | `imageUrl` | `imageUrls` |
| Product design | `POST /api/business/product-design/runs` | `imageUrl`, `designBrief` | `imageUrls` |
| Outpaint | `POST /api/business/outpaint/runs` | `imageUrl` | `imageUrls` |
| Image edit | `POST /api/business/image-edit/runs` | `imageUrl`, instruction fields | `imageUrls` |
| Image edit chat | `POST /api/business/image-edit-chat/sessions` | `imageUrl`, `message` | session, messages, proposed plan |
| Fission evaluate | `POST /api/business/fission-evaluate/runs` | `originalImageUrl`, `generatedImageUrl` | `texts/resultPayload` |
| Query run | `POST /api/business/runs/get` | `runId` | status/result/error |

## Current API Gaps

Record these as gaps if needed. Do not bypass the mid-platform.

| Gap | Needed For |
| --- | --- |
| `product_image_set` business API | Multi-angle or grouped product images |
| `model_shot` business API | Model wearing/use-case image |
| `promo_video` business API | Promotional video generation |
| Export media binary packaging | Copy final image/video files into the ZIP instead of URL-only manifest references |

## Public Status Contract

Render only these states:

- `queued`
- `running`
- `succeeded`
- `failed`

On failure, show:

- Business-readable error.
- `runId`.
- Suggested retry or next action.

Do not show raw stack traces or internal service names in the primary UI.
