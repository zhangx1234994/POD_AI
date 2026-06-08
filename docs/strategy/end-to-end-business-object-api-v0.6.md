# v0.6 兼容调用上下文与能力证据 API 草案

最后更新：2026-06-03

> 兼容说明：本文是 `/api/business/projects/*` 兼容实现背景，不是当前 v0.6 中台主线。当前主线以 `docs/strategy/mid-platform-completeness-v0.6-plan.md`、`docs/strategy/ability-governance-operating-model-v0.6.md` 和 `docs/strategy/ability-definition-v0.6.md` 为准。中台主对象是能力；`projectId` 只作为历史兼容字段，新接入优先使用 `clientContextId/inputAssetIds/clientRequestId`。

本文定义 v0.6 中台给客户端提供的兼容调用上下文、资产和调用证据 API。它不是中台端到端流程引擎设计，也不是把项目变成中台主对象的设计。中台主对象仍是业务能力；兼容调用上下文只是能力调用闭环的证据容器。业务流程由客户端组装；中台记录上下文、资产、业务 run、选择和交付包证据，以便追踪能力调用、质量、成本和交付。

## 1. 设计原则

- `runId` 仍然是单次业务运行的第一排障主键。
- `clientContextId` 是新接入的客户端上下文；`projectId` 只在复用兼容证据 API 时作为技术映射，不是能力治理主键。
- `flowStepKey` 是客户端声明的业务步骤，不是中台固定阶段字典。
- 中台不校验行业流程顺序，只校验业务能力、资产权限和数据一致性。
- 资产不只是 URL，必须记录来源 run、来源能力、来源客户端步骤、类型、质量和选择状态。
- 客户端可以用同一套业务 API 自由组装流程，但不能绕过业务 API 直连原子能力。

## 2. 核心对象

### 2.1 Project

项目是客户端业务流程的证据容器，不是中台工作流模板，也不是中台能力治理的主视角。

建议字段：

| 字段 | 说明 |
| --- | --- |
| `id` | 项目 ID，对外为 `projectId`。 |
| `name` | 项目名称。 |
| `scenario` | 客户端声明的业务场景，例如 `pattern_to_product`。 |
| `status` | `draft` / `active` / `paused` / `ready_to_export` / `exported` / `archived`。 |
| `owner_user_id` | 项目创建人。 |
| `tenant_id` / `client_id` | 租户和客户范围。 |
| `current_flow_step_key` | 客户端写入的当前步骤，可为空。 |
| `flow_template_id` | 客户端模板 ID，可为空。 |
| `created_at` / `updated_at` | 创建和更新时间。 |
| `metadata` | 业务扩展字段，不能放密钥和内部 URL。 |

### 2.2 ProjectAsset

资产代表项目素材或结果。

建议字段：

| 字段 | 说明 |
| --- | --- |
| `id` | 资产 ID。 |
| `project_id` | 所属项目。 |
| `asset_type` | `input_image` / `pattern` / `variant` / `product_image` / `angle_image` / `model_image` / `video` / `text` / `other`。 |
| `url` | 自有 OSS 或受控存储地址。 |
| `source_run_id` | 来源业务 `runId`，手工上传时为空。 |
| `source_business_key` | 来源业务能力。 |
| `source_flow_step_key` | 客户端声明的来源步骤。 |
| `source_output_index` | 来源输出序号。 |
| `quality_grade` | 质量档位，可为空。 |
| `input_tags` / `issue_tags` | 输入标签和问题标签。 |
| `selected` | 是否被选择过。 |
| `metadata` | 参数摘要、尺寸、格式等。 |

### 2.3 ProjectRunLink

ProjectRunLink 只负责把一次业务 run 关联到项目和客户端步骤。它不是中台阶段执行器。

建议字段：

| 字段 | 说明 |
| --- | --- |
| `id` | 关联记录 ID。 |
| `project_id` | 所属项目。 |
| `run_id` | 业务运行 ID。 |
| `business_key` | 业务能力 key。 |
| `flow_step_key` | 客户端声明的步骤 key。 |
| `flow_step_name` | 客户端声明的步骤名称。 |
| `flow_template_id` | 客户端模板 ID。 |
| `input_asset_ids` | 输入资产。 |
| `output_asset_ids` | 输出资产。 |
| `client_request_id` | 客户端请求 ID。 |
| `created_at` / `updated_at` | 时间。 |
| `metadata` | 参数、模板、候选版本等摘要。 |

### 2.4 ProjectSelection

选择记录代表用户在客户端选择某个候选结果。

建议字段：

| 字段 | 说明 |
| --- | --- |
| `id` | 选择记录 ID。 |
| `project_id` | 所属项目。 |
| `asset_id` | 被选择的资产。 |
| `source_run_id` | 来源业务 runId。 |
| `source_flow_step_key` | 来源客户端步骤。 |
| `target_flow_step_key` | 目标客户端步骤。 |
| `selected_by` | 操作人。 |
| `note` | 选择备注。 |
| `created_at` | 选择时间。 |

### 2.5 ExportPackage

导出包代表项目最终交付物。中台负责打包和脱敏，客户端负责决定放入哪些资产。

建议字段：

| 字段 | 说明 |
| --- | --- |
| `id` | 导出包 ID。 |
| `project_id` | 所属项目。 |
| `status` | `pending` / `building` / `ready` / `failed`。 |
| `asset_ids` | 包含的资产。 |
| `run_ids` | 包含的业务运行证据。 |
| `download_url` | 下载地址。 |
| `summary` | 交付摘要。 |
| `error_code` / `error_message` | 导出失败原因。 |
| `created_at` / `updated_at` | 时间。 |

## 3. 业务运行上下文

现有业务提交接口建议增加可选字段：

`POST /api/business/{business}/runs`

新增可选上下文：

```json
{
  "projectId": "proj_xxx",
  "flowStepKey": "variant_fission",
  "flowStepName": "裂变候选",
  "flowTemplateId": "pattern_to_product_v1",
  "inputAssetIds": ["asset_xxx"],
  "clientRequestId": "client_req_xxx"
}
```

中台行为：

- 创建业务 run。
- 记录 ProjectRunLink。
- 任务成功后将输出沉淀为 ProjectAsset。
- 不根据 `flowStepKey` 判断下一步。
- 不要求 flow step 必须来自中台固定字典。

## 4. API 草案

所有项目上下文接口建议位于业务层：`/api/business/projects/*`。

### 4.1 创建项目

`POST /api/business/projects`

请求：

```json
{
  "name": "夏季花纹商品图项目",
  "scenario": "pattern_to_product",
  "flowTemplateId": "pattern_to_product_v1",
  "metadata": {
    "productType": "服装",
    "note": "客户端样板链路"
  }
}
```

响应：

```json
{
  "projectId": "proj_xxx",
  "status": "draft",
  "createdAt": "2026-06-02T00:00:00Z"
}
```

错误：

| 错误码 | 场景 |
| --- | --- |
| `PROJECT_NAME_REQUIRED` | 缺少项目名称 |
| `PROJECT_SCENARIO_INVALID` | 场景非法 |
| `BUSINESS_AUTH_REQUIRED` | 未鉴权 |

### 4.2 查询项目

`GET /api/business/projects/{projectId}`

响应应包含：

- 项目基础信息。
- 资产摘要。
- 关联业务 run 摘要。
- 选择记录摘要。
- 交付包摘要。

不返回：

- executor。
- workflow 原始 JSON。
- 厂商原始响应。
- 内部密钥或内网地址。

### 4.3 登记项目资产

`POST /api/business/projects/{projectId}/assets`

请求：

```json
{
  "assetType": "input_image",
  "url": "https://podi.oss-cn-hangzhou.aliyuncs.com/...",
  "flowStepKey": "upload_assets",
  "metadata": {
    "fileName": "source.png"
  }
}
```

错误：

| 错误码 | 场景 |
| --- | --- |
| `PROJECT_NOT_FOUND` | 项目不存在 |
| `PROJECT_ASSET_URL_REQUIRED` | 缺少资产 URL |
| `PROJECT_ASSET_TYPE_INVALID` | 资产类型非法 |
| `PROJECT_ASSET_URL_INVALID` | 非受控或非法 URL |

### 4.4 查询项目运行记录

`GET /api/business/projects/{projectId}/runs`

响应应包含：

- `runId`
- `businessKey`
- `status`
- `flowStepKey`
- `flowStepName`
- `inputAssetIds`
- `outputAssetIds`
- `errorCode`
- `errorMessage`
- `createdAt`
- `updatedAt`

### 4.5 选择候选结果

`POST /api/business/projects/{projectId}/selections`

请求：

```json
{
  "assetIds": ["asset_variant_1"],
  "sourceFlowStepKey": "variant_fission",
  "targetFlowStepKey": "product_design",
  "note": "选择结构最稳定的一张进入产品设计"
}
```

错误：

| 错误码 | 场景 |
| --- | --- |
| `PROJECT_SELECTION_ASSET_REQUIRED` | 缺少选择资产 |
| `PROJECT_SELECTION_ASSET_INVALID` | 资产不属于当前项目 |
| `PROJECT_SELECTION_TARGET_REQUIRED` | 缺少客户端目标步骤 |

### 4.6 生成交付包

`POST /api/business/projects/{projectId}/exports`

请求：

```json
{
  "assetIds": ["asset_product_1", "asset_model_1", "asset_video_1"],
  "includeRunEvidence": true,
  "includeQualitySummary": true
}
```

响应：

```json
{
  "packageId": "pkg_xxx",
  "projectId": "proj_xxx",
  "status": "pending"
}
```

错误：

| 错误码 | 场景 |
| --- | --- |
| `PROJECT_EXPORT_ASSETS_EMPTY` | 未选择交付资产 |
| `PROJECT_EXPORT_ASSET_INVALID` | 资产不可导出 |
| `PROJECT_EXPORT_BUILD_FAILED` | 导出包生成失败 |

## 5. 管理端视图要求

管理端可下钻查看客户端上下文和运行证据，但不组装客户端业务流程，也不把兼容上下文作为中台主对象。管理端主视角仍应优先围绕能力版本、路由、质量、成本和错误组织。

管理端需要展示：

- 客户端上下文列表。
- 上下文关联 run。
- 上下文资产。
- 客户端声明的 flow step。
- 失败 runId 和错误码。
- 质量标签。
- 交付包证据。

管理端不展示为主路径：

- 客户端行业模板编辑。
- 客户端下一步推荐配置。
- 客户端页面动线。

## 6. 测试要求

后端测试至少覆盖：

- 创建项目缺参。
- 非法 scenario。
- 登记非法资产 URL。
- 业务 run 写入非法 projectId。
- 选择非本项目资产。
- 导出包空资产。
- 鉴权和租户越权。
- 业务 run 成功后输出资产沉淀。

客户端联调测试至少覆盖：

- 创建项目到上传素材。
- 调用一个业务能力并写入 `projectId` 和 `flowStepKey`。
- 轮询 run 成功后项目资产出现输出图。
- 选择候选进入客户端下一步。
- 生成交付包草稿。

## 7. 当前推荐决策

实施拆解见 `docs/strategy/project-context-backend-design-v0.6.md`。

1. `projectId` 和 `flowStepKey` 放在顶层请求字段，同时镜像到 `metadata.projectContext` 便于排障。
2. 项目级 API 首版复用现有业务 API 鉴权和租户/client 范围，不新增独立 API Key scope；后续如项目共享复杂再补 scope。
3. 输出资产自动沉淀失败时，不把已成功的业务 run 改成 `failed`；ProjectRunLink 标记 `asset_sync_status=failed`，管理端提示重试或排查。
4. 交付包首版先生成脱敏 manifest JSON，ZIP 作为 P1 增强。
5. 客户端 flow template 仅允许只读登记或通过 `flowTemplateId/flowStepKey/flowStepName` 展示，不在中台编辑客户端流程。
