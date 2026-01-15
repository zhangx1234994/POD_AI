# AI 能力接入与管理方案

本文档梳理当前 `executors/workflows/workflow_bindings/api_keys` 数据模型的用途，并规划后续需要落地的任务执行链路、ComfyUI 管理能力、多厂商 API 适配、管控端页面与安全策略，作为后端与前端开发的统一参考。

## 目标

1. **多厂商统一抽象**：支持 OpenAI、火山引擎、阿里云百炼、百度智能云、ComfyUI 自建算力等多源 AI 能力，通过配置即可扩展。
2. **运行时灵活调度**：任务提交后，调度器根据 action/工作流/执行节点状态选择最合适的 executor，并监控执行结果。
3. **可视化管理**：独立的 Admin 页面管理工作流、执行节点、API Key、ComfyUI 工作流版本，使运营同学无需改代码即可切换产能。
4. **密钥安全与可回滚**：支持 RAM 角色、STS、API Key 失效检测，提供配额跟踪与自动降级策略。

## 数据实体与职责

| 表 | 关键字段 | 说明 |
|----|---------|------|
| `executors` | `type`、`base_url`、`max_concurrency`、`config` | 描述执行节点，可对应一个 ComfyUI 服务、某厂商 API Endpoint、或内部推理集群。`config` 存放认证方式、可用模型列表。 |
| `workflows` | `action`、`definition`、`metadata` | 定义“业务动作”与底层工作流（ComfyUI JSON / Prompt 模板 / API 参数），支持多版本管理。 |
| `workflow_bindings` | `action`、`workflow_id`、`executor_id`、`priority` | 将用户触发的 action 绑定到某个工作流 + 执行节点，可按优先级或 AB Test 切换。 |
| `api_keys` | `provider`、`key`、`usage_count`、`expire_at` | 存储第三方密钥，供 executor 在发起请求时选择；同一 provider 可配置多把 key 并自动轮询。 |

## 任务执行流程（拟定）

1. **任务入库**：`/api/tasks/v1/submit` 已落库任务与输入图片，并冻结积分。
2. **调度器拉取**：新增 `task_dispatcher`（可由 Celery Beat/后台循环驱动）查找 `status=pending` 的任务。
3. **解析 action**：根据任务的 `tool_action`：  
   a. 查找 `workflow_bindings` -> 过滤 `enabled=true`、`executor.status=active`；  
   b. 根据 `priority`、`weight`、`max_concurrency` 与健康状态选择 executor；  
   c. 选择匹配版本的 `workflow.definition`。
4. **准备上下文**：组合 `workflow.definition` + `task.input_payload` + API Key（若 executor 需要）+ 媒体资源（OSS URL）。
5. **执行**：按 executor `type` 分发：  
   - `openai`: 直接调用 OpenAI/同规范接口。  
   - `volcengine` / `aliyun` / `baidu`: 通过 provider SDK/HTTP 适配器。  
   - `comfyui`: 通过 REST/WebSocket 调用 `prompt`，必要时先检测 workflow 是否需要上传到节点。  
6. **状态回写**：实时更新 `tasks.status/progress`，写入 `task_events`，生成输出 `task_assets` 并设置 `result_payload` 中的展示 URL。失败时写入 error_code，释放积分。
7. **通知前端**：`notify_service` 广播任务状态、任务中心刷新信号。

## ComfyUI 管理规划

- **工作流版本库**：`workflows.definition` 存放 ComfyUI workflow JSON，`metadata` 记录节点哈希、依赖 checkpoint。Admin UI 需支持上传 `.json` 或直接编辑文本，版本号自动递增。
- **节点同步**：新增后台接口 `/api/admin/workflows/{id}/deploy`，将 workflow 推送到目标 executor（通过其 `base_url` 和授权 token）。记录最近一次部署时间与校验结果。
- **参数映射**：Workflow 可设置 `metadata.paramMapping`（如 `{ "prompt": "input.prompt", "image": "assets[0].url" }`），调度器据此把任务参数注入 ComfyUI 节点。

## 管控端页面需求

1. **执行节点列表**：展示健康状态、并发、已运行任务、心跳时间，提供“下线/上线/测试连通性”按钮。
2. **工作流管理**：支持创建/编辑、上传 JSON、比较版本、绑定执行节点、触发部署。
3. **分配策略**：以 action 为索引查看绑定链路，调整优先级、A/B 开关、流量配比。
4. **API Key 仓库**：显示 key 使用量、日配额、过期时间，允许启停、轮换、标记用途。
5. **运行监控**（后续）：展示任务成功率、平均耗时、每个 executor 的队列长度。

前端实现建议：将 `IntegrationDashboard` 拆分为独立的模块化组件，复用 `DataTable`，并通过 websocket/轮询获取心跳与用量数据。

目前 `/admin/integrations` 页面已实现基础仪表：顶部汇总执行节点/工作流/绑定/API Key 数量，中间各 Tab 提供列表 + 表单并支持创建、编辑、删除、切换绑定启用状态、录入工作流 JSON 与执行器配置。2026-01 起新增：

- **能力目录 & 统一接口信息**：卡片展示 Ability ID、所属 provider、默认执行节点、能力类型、成本（`metadata.pricing`），并通过“统一能力接口”说明组件生成可复制的 `curl` 示例。
- **实时测试 Tab**：根据能力 schema（含节点编号描述）渲染表单，支持上传图片、选择执行节点、覆盖默认参数。ComfyUI 能力会调用 `/api/admin/comfyui/models` 自动把 UNet/CLIP/VAE/LoRA 列表渲染为下拉框，避免手填。
- **调用记录 Tab**：嵌入 `/api/admin/abilities/{abilityId}/logs` 数据，展示最近 N 次调用的状态、耗时、输出 OSS 链接、失败原因、traceId。点击可展开 Raw Response，辅助排查。
- **ComfyUI 队列状态面板**：针对每个 ComfyUI 执行节点，展示 `running/pending/max` 以及错误提示（如 `COMFYUI_QUEUE_STATUS_ERROR`），并提供刷新按钮，帮助判断串行队列是否阻塞。
- **API Key 仓库**：提供列表 + 详情抽屉，支持录入、启用/禁用、备注限流策略；能力表单会检测 executor 是否缺少凭证并给出指引。
- **能力详情空位**：提前预留成本、自检、SLA 等信息位，即使数据暂缺亦有 placeholder，提醒后续需要补齐。

### 能力示例：百度智能云图像处理

- **执行节点**：在 `executors` 中新增 `id=baidu-image-cn`, `type=baidu`, `base_url=https://aip.baidubce.com`，`config` 需包含 `{"apiKey":"<API Key>", "secretKey":"<Secret Key>"}`。调度器将使用 `BaiduImageExecutorAdapter` 自动获取/缓存 `access_token`。
- **组件定义**（存入 `workflow.definition`）：
  ```json
  {
    "component": "baidu_quality_upgrade",
    "endpoint": "/rest/2.0/image-process/v1/quality_upgrade",
    "defaults": {
      "type": "auto",
      "resolution": "2k"
    },
    "timeout": 40
  }
  ```
  任务的 `workflowParams` 需提供 `image`（base64）或 `imageUrl`（后端会自动下载并转 base64），其余参数可覆盖 `defaults`。
- **流程**：TaskDispatcher 命中 action 后，构造 `ExecutionContext` -> Baidu executor 拉取 token -> 调用接口 -> 将返回的 base64 结果包装为 `data:image/png;base64,...` 写入 `result_payload.resultImage`，同时记录 `log_id` 供排障。
- **安全**：API Key/Secret Key 需写入 `executors.config` 或 `api_keys` 表时进行加密存储，前端管理端仅显示末四位。Access Token 自动缓存于内存，避免频繁鉴权。
- **管理端测试**：`podi-admin-web` 中已提供“功能测试”模块，可选择 type=baidu 的执行节点并上传图片，调用后台 `/api/admin/tests/baidu/quality-upgrade` 验证链路，无需经过任务调度；用于上线前快速排查凭证或网络问题。

## API 与服务层扩展

- **调度/执行接口**
  - `POST /api/tasks/v1/dispatch`（已实现）触发单次调度；后续可由 Celery 定时触发或监听消息队列。
  - `PATCH /api/tasks/v1/{id}` 支持更新 `status/progress/error`.
- **Executor 适配层**：新增 `app/services/executors/base.py` 定义统一接口（`prepare_payload`, `execute`, `poll_result`）。不同 provider 写子类，通过 `executor.type` + `executor.config` 动态加载。
- **健康检查**：Celery 周期任务 `executor_health_check` 调用每个节点的 `/health`，写回 `executors.health_status` 与 `last_heartbeat_at`。
- **API Key 轮转**：在执行前调用 `api_key_service.acquire(provider)`，内部选择 usage 最低且未过期的 key 并自增 `usage_count`，若达到 `daily_quota` 自动禁用。

## 安全与配置

- **OSS**：沿用直传策略，但在后台记录上传对象的 `root-prefix` + `taskId` 方便追踪，配合 RAM 角色 CLTZ (`acs:ram::1738589252389908:role/cltz`) 生成 STS，确保 key 失效可控。TODO：硬化信任策略，只允许指定应用角色 AssumeRole。
- **密钥加密**：`api_keys.key` 建议引入 `Fernet`/KMS 加密存储；展示时仅显示后四位。
- **多环境配置**：`settings.py` 中为各 provider 提供命名空间（如 `OpenAISettings`, `VolcanoSettings`），Admin 输入的 `base_url` 与 key 将覆盖默认值。

## 开发生命线

1. **第一阶段**：实现调度器骨架 + Executor 抽象 + OpenAI/ComfyUI/火山适配器；任务可从 pending -> completed。
2. **第二阶段**：补充 API Key 轮询、限流与健康检查；Admin UI 增强（部署按钮、节点指标）。
3. **第三阶段**：监控告警、工作流版本审计、ComfyUI 可视化编辑（后续可用 iframe 嵌入）。

每个阶段完成后需同步更新 `docs/task-submission-flow.md`、`docs/development-guide.md` 与 `AGENTS.md`，并在 Admin 页面增加内嵌帮助链接。

## 统一能力接口与日志（2026-01 更新）

为对外提供稳定的“原子能力中心”，后端新增了 `AbilityService` 及配套的日志/成本模型：

- `GET /api/abilities` / `POST /api/abilities/{id}/invoke`：向客户端暴露统一的调用入口，与管理端表单保持同一份 `input_schema` / `default_params`。所有能力都必须在 `app/constants/abilities.py` 中登记，缺失字段会被阻止发布。
- `POST /api/ability-tasks`：承载异步/批量请求；后台线程池遵循 `ABILITY_TASK_MAX_WORKERS` + `executors.max_concurrency`，必要时可在配置中按能力/节点限流。
- `ability_invocation_logs`：记录能力调用的 `request_id`、`executor_id`、`duration_ms`、`pricing`（对外价 & 折扣价）、`cost_amount`，并存储 OSS 输出列表。管理端“调用记录”即基于该表。
- `metadata.pricing`：能力成本模型，字段包括 `currency`、`unit`、`list_price`、`discount_price`。管理端展示“¥0.30 / 每张（折扣） / ¥0.50 / 每张（对外）”形式，并在日志中回写实际 cost。ComfyUI 默认 ¥0.30/张，可覆盖。
- `callbackUrl/callbackHeaders`：同步/异步调用均可附带回调，后端会在执行完毕后推送 `status/result/error/logId`，便于第三方系统解耦。
- `traceId/workflowRunId`：请求可在 metadata 中携带自定义 ID，后端随日志返回，用于串联上下游链路。未来工作流层会将 `workflow_run_nodes` 与能力日志打通。

通过上述机制，我们保证：① 客户端/管理端/工作流都使用统一接口；② 每次调用都有日志可查；③ 成本/队列/LoRA 这些运行时信息被显式暴露，利于运营和排障。
