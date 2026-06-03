# v0.6 兼容调用上下文后端实施记录

最后更新：2026-06-03

> 兼容说明：本文记录 `/api/business/projects/*` 和 `BusinessProject*` 历史命名实现，不是当前 v0.6 中台主线。当前主线以能力、能力版本、路由、调用、结果、质量、成本和错误为核心；新接入优先使用 `clientContextId/inputAssetIds/clientRequestId`。

本文把 `docs/strategy/end-to-end-business-object-api-v0.6.md` 的兼容草案拆成后端实施任务。核心原则不变：中台主语是业务能力，兼容调用上下文只是能力调用闭环的证据容器。客户端组装业务流程，中台记录上下文、资产、业务 run 关联、选择和交付包证据；中台不做固定流程引擎，也不把项目管理作为核心产品方向。

## 1. 复用现有主干

现有主干已经具备：

- `BusinessRun`：单次业务运行主表。
- `BusinessRunStep`：业务能力内部执行步骤。
- `BusinessCapability`：业务能力版本和配方。
- `BusinessOutputReview`：输出质量复盘。
- `BusinessQualitySample`：固定样例。
- `BusinessQualityActionRule`：质量治理台账。
- `BusinessApiKeyUsageLog`：接口调用证据。

v0.6 不新建第二套任务系统。兼容调用上下文应作为业务 run 的旁路证据层，挂在 `BusinessRun` 之外；能力治理仍以 `BusinessCapability`、版本、路由、质量和调用证据为主。

## 2. 数据模型

建议新增模型仍放在 `backend/app/models/integration.py`，便于与现有业务模型共用迁移、鉴权和查询。

### 2.1 BusinessProject

表名：`business_projects`

| 字段 | 类型建议 | 说明 |
| --- | --- | --- |
| `id` | `String(64)` PK | 对外 `projectId`。 |
| `name` | `String(128)` | 项目名称。 |
| `scenario` | `String(64)` | 客户端声明的业务场景。 |
| `status` | `String(32)` | `draft/active/paused/ready_to_export/exported/archived`。 |
| `tenant_id` | `String(64)` index | 租户范围。 |
| `client_id` | `String(64)` index | 客户端或业务方范围。 |
| `owner_user_id` | `String(64)` index nullable | 创建人。 |
| `owner_user_name` | `String(128)` nullable | 创建人展示名。 |
| `current_flow_step_key` | `String(64)` nullable | 客户端写入的当前步骤。 |
| `flow_template_id` | `String(64)` nullable | 客户端模板 ID。 |
| `metadata` | `JSON` nullable | 业务扩展，禁止密钥和内部 URL。 |
| `created_at/updated_at` | `DateTime` | 时间。 |

索引：

- `(tenant_id, client_id, updated_at)`
- `(scenario, status, updated_at)`
- `(owner_user_id, updated_at)`

### 2.2 BusinessProjectAsset

表名：`business_project_assets`

| 字段 | 类型建议 | 说明 |
| --- | --- | --- |
| `id` | `String(64)` PK | 资产 ID。 |
| `project_id` | FK -> `business_projects.id` | 所属项目。 |
| `asset_type` | `String(32)` | `input_image/pattern/variant/product_image/angle_image/model_image/video/text/other`。 |
| `url` | `String(1024)` nullable | 自有 OSS 或受控存储 URL。 |
| `content_type` | `String(64)` nullable | MIME 类型。 |
| `file_name` | `String(255)` nullable | 原始文件名。 |
| `source_run_id` | FK -> `business_runs.id` nullable | 来源 run。 |
| `source_business_key` | `String(64)` nullable | 来源业务能力。 |
| `source_flow_step_key` | `String(64)` nullable | 客户端声明的来源步骤。 |
| `source_output_index` | `Integer` nullable | 来源输出序号。 |
| `quality_grade` | `String(32)` nullable | 质量档位。 |
| `input_tags/issue_tags` | `JSON` nullable | 标签。 |
| `selected` | `Boolean` | 是否被选择过。 |
| `metadata` | `JSON` nullable | 尺寸、格式、参数摘要。 |
| `created_at/updated_at` | `DateTime` | 时间。 |

索引：

- `(project_id, asset_type, created_at)`
- `(project_id, selected, updated_at)`
- `(source_run_id, source_output_index)`

### 2.3 BusinessProjectRunLink

表名：`business_project_run_links`

| 字段 | 类型建议 | 说明 |
| --- | --- | --- |
| `id` | `String(64)` PK | 关联 ID。 |
| `project_id` | FK -> `business_projects.id` | 所属项目。 |
| `run_id` | FK -> `business_runs.id` unique | 对应业务 run。 |
| `business_key` | `String(64)` | 业务能力 key。 |
| `flow_step_key` | `String(64)` nullable | 客户端声明步骤。 |
| `flow_step_name` | `String(128)` nullable | 客户端步骤名。 |
| `flow_template_id` | `String(64)` nullable | 客户端模板 ID。 |
| `input_asset_ids` | `JSON` nullable | 输入资产 ID 列表。 |
| `output_asset_ids` | `JSON` nullable | 输出资产 ID 列表。 |
| `client_request_id` | `String(128)` nullable | 客户端幂等或排查 ID。 |
| `asset_sync_status` | `String(32)` | `pending/succeeded/failed/skipped`。 |
| `asset_sync_error` | `Text` nullable | 资产沉淀失败原因。 |
| `metadata` | `JSON` nullable | 参数摘要。 |
| `created_at/updated_at` | `DateTime` | 时间。 |

索引：

- `(project_id, flow_step_key, created_at)`
- `(project_id, client_request_id)`
- `(business_key, created_at)`

约束：

- `run_id` 唯一，避免一个 run 绑定多个项目。
- `client_request_id` 不做全局唯一；首版只作为查询和排查字段，避免误伤业务方重试。

### 2.4 BusinessProjectSelection

表名：`business_project_selections`

| 字段 | 类型建议 | 说明 |
| --- | --- | --- |
| `id` | `String(64)` PK | 选择记录 ID。 |
| `project_id` | FK -> `business_projects.id` | 所属项目。 |
| `asset_id` | FK -> `business_project_assets.id` | 被选择资产。 |
| `source_run_id` | FK -> `business_runs.id` nullable | 来源 run。 |
| `source_flow_step_key` | `String(64)` nullable | 来源步骤。 |
| `target_flow_step_key` | `String(64)` nullable | 客户端声明目标步骤。 |
| `selected_by_user_id` | `String(64)` nullable | 操作人。 |
| `selected_by_user_name` | `String(128)` nullable | 操作人展示名。 |
| `note` | `Text` nullable | 备注。 |
| `metadata` | `JSON` nullable | 业务扩展。 |
| `created_at` | `DateTime` | 时间。 |

索引：

- `(project_id, created_at)`
- `(asset_id, created_at)`

### 2.5 BusinessExportPackage

表名：`business_export_packages`

| 字段 | 类型建议 | 说明 |
| --- | --- | --- |
| `id` | `String(64)` PK | 对外 `packageId`。 |
| `project_id` | FK -> `business_projects.id` | 所属项目。 |
| `status` | `String(32)` | `pending/building/ready/failed`。 |
| `asset_ids` | `JSON` | 包含资产。 |
| `run_ids` | `JSON` nullable | 包含 run 证据。 |
| `download_url` | `String(1024)` nullable | 下载地址。 |
| `manifest` | `JSON` nullable | 首版交付清单。 |
| `summary` | `JSON` nullable | 摘要。 |
| `error_code` | `String(128)` nullable | 错误码。 |
| `error_message` | `Text` nullable | 错误描述。 |
| `created_at/updated_at` | `DateTime` | 时间。 |

索引：

- `(project_id, created_at)`
- `(status, updated_at)`

## 3. 请求字段

现有 `BusinessRunCreateRequest` 建议新增顶层字段，并保留 snake_case 兼容字段：

| 字段 | 说明 |
| --- | --- |
| `projectId` / `project_id` | 项目 ID。 |
| `flowStepKey` / `flow_step_key` | 客户端声明的步骤 key。 |
| `flowStepName` / `flow_step_name` | 客户端声明的步骤名。 |
| `flowTemplateId` / `flow_template_id` | 客户端模板 ID。 |
| `inputAssetIds` / `input_asset_ids` | 输入项目资产 ID 列表。 |
| `clientRequestId` / `client_request_id` | 客户端请求 ID。 |

推荐决策：

- 字段放在顶层，便于客户端接入和 OpenAPI 展示。
- 后端同时把这些字段镜像到 `request_payload["_projectContext"]` 和能力调用 `metadata.projectContext`，便于排障。
- 中台只校验项目、资产和权限，不根据 `flowStepKey` 判断下一步。

## 4. API 路径

全部位于业务前缀，避免客户端接触 admin/evals/abilities。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `POST` | `/api/business/projects` | 创建项目。 |
| `GET` | `/api/business/projects` | 项目列表。 |
| `GET` | `/api/business/projects/{projectId}` | 项目详情。 |
| `PATCH` | `/api/business/projects/{projectId}` | 更新项目名称、状态、当前步骤和 metadata。 |
| `POST` | `/api/business/projects/{projectId}/assets` | 登记手工上传或外部资产。 |
| `GET` | `/api/business/projects/{projectId}/assets` | 查询资产。 |
| `GET` | `/api/business/projects/{projectId}/runs` | 查询项目关联 run。 |
| `POST` | `/api/business/projects/{projectId}/selections` | 记录候选选择。 |
| `POST` | `/api/business/projects/{projectId}/exports` | 创建交付包。 |
| `GET` | `/api/business/projects/{projectId}/exports/{packageId}` | 查询交付包。 |

管理端只增加观察入口：

- `GET /api/admin/business/projects`
- `GET /api/admin/business/projects/{projectId}`

管理端不编辑客户端流程模板。

## 5. 服务拆分

建议新增 `backend/app/services/business_projects.py`。

主要方法：

- `create_project`
- `list_projects`
- `get_project_detail`
- `update_project`
- `create_asset`
- `list_assets`
- `link_run_to_project`
- `sync_run_outputs_to_project_assets`
- `create_selection`
- `create_export_package`
- `get_export_package`

业务 run 创建时调用：

1. `_validate_project_context`
2. `_create_project_run_link`
3. `_mirror_project_context_to_request_payload`

业务 run 终态同步时调用：

1. `_extract_urls` 已经可从 `images/assets/resultUrls/imageUrls/videoUrls` 提取输出。
2. 复用该提取结果创建 ProjectAsset。
3. 更新 ProjectRunLink 的 `output_asset_ids` 和 `asset_sync_status`。

## 6. 资产沉淀策略

推荐决策：

- 输出资产沉淀失败时，不把已成功的业务 run 改成 `failed`。
- `BusinessRun.status` 保持底层真实结果。
- `BusinessProjectRunLink.asset_sync_status` 标记为 `failed`，管理端提供重试或排查入口。
- 公共查询仍返回 `runId` 原始结果，项目详情中展示“资产沉淀失败”。

理由：

- 业务生成成功和项目资产回填失败是两个不同故障面。
- 将生成成功的 run 改失败会让客户端误判结果不可用。
- 管理端需要看见回填故障，但不应掩盖原始出图成功。

## 7. 鉴权和租户

首版规则：

- 项目归属 `tenant_id/client_id/owner_user_id`。
- 业务 API Key 只能访问同租户、同 client 或允许范围内项目。
- `inputAssetIds` 必须全部属于同一项目。
- 业务 run 的 `tenantId/clientId` 若与项目归属冲突，返回 `PROJECT_FORBIDDEN`。
- 管理员可在管理端观察所有项目，但公共业务 API 不允许跨租户访问。

## 8. 错误码

本设计对应的错误码已同步到 `docs/standards/error-catalog.md`。实现时接口文档还需在 `docs/api/modules/business.md` 增加每个端点的请求、响应和错误表。

首批错误码：

- `PROJECT_NAME_REQUIRED`
- `PROJECT_SCENARIO_INVALID`
- `PROJECT_NOT_FOUND`
- `PROJECT_FORBIDDEN`
- `PROJECT_STATUS_INVALID`
- `PROJECT_ASSET_URL_REQUIRED`
- `PROJECT_ASSET_TYPE_INVALID`
- `PROJECT_ASSET_URL_INVALID`
- `PROJECT_ASSET_NOT_FOUND`
- `PROJECT_ASSET_FORBIDDEN`
- `PROJECT_RUN_LINK_INVALID`
- `PROJECT_SELECTION_ASSET_REQUIRED`
- `PROJECT_SELECTION_ASSET_INVALID`
- `PROJECT_SELECTION_TARGET_REQUIRED`
- `PROJECT_EXPORT_ASSETS_EMPTY`
- `PROJECT_EXPORT_ASSET_INVALID`
- `PROJECT_EXPORT_BUILD_FAILED`

## 9. 测试计划

后端测试建议新增 `backend/tests/test_business_project_context.py`。

必须覆盖：

- 创建项目缺少名称。
- 非法 `scenario`。
- 非法状态。
- 登记资产缺少 URL。
- 登记非受控 URL。
- 查询不存在项目。
- 跨租户访问项目。
- 业务 run 传入不存在 `projectId`。
- 业务 run 传入非本项目 `inputAssetIds`。
- 业务 run 成功后创建 ProjectRunLink。
- 业务 run 成功后输出自动沉淀为 ProjectAsset。
- 资产沉淀失败时 run 不被改成 failed，link 标记 `asset_sync_status=failed`。
- 选择非本项目资产失败。
- 空资产创建交付包失败。

文档和门禁：

- 更新 `docs/api/modules/business.md`。
- 更新 `docs/standards/error-catalog.md`。
- 更新 `docs/standards/business-api-enums.md` 中的业务公共字段。
- 运行 `python3 scripts/check_doc_entry_references.py`。
- 运行 `python3 scripts/check_error_catalog.py`。
- 运行后端相关 pytest。

## 10. 实施顺序

1. Alembic 迁移和 SQLAlchemy 模型。
2. Pydantic schemas。
3. `BusinessProjectService`。
4. `/api/business/projects/*` 公共 API。
5. `BusinessRunCreateRequest` 上下文字段。
6. `BusinessRunService._create_run_internal` 写 ProjectRunLink。
7. 业务 run 终态同步 ProjectAsset。
8. 管理端只读观察 API。
9. 文档、错误码、测试和 smoke。

## 11. 非目标

- 不实现客户端流程模板编辑器。
- 不在中台判断阶段顺序。
- 不把 `ProjectRunLink` 当成 `BusinessRunStep`。
- 不允许客户端调用 `/api/admin/*`、`/api/evals/*`、`/api/abilities/*`、ComfyUI 或 vendor-api。
- 不在首版交付包里暴露内部 workflow JSON、executor、密钥、厂商原始响应。
