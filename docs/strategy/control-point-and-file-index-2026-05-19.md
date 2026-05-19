# 控制点收敛与文件索引（2026-05-19）

目的：把“一个问题应该先看哪里、真源在哪里、哪些地方只能派生”写清楚，避免后续继续靠全局搜索和聊天记忆排查。

适用范围：backend、管理端、测评端、ComfyUI 执行适配、业务 API、Coze 工具箱、对外交付文档。

## 1. 总原则

1. **先找真源，再改代码。**
   - 业务字段、枚举、默认值、状态词、错误码和展示名都必须有明确真源。
   - 前端只能做展示、交互和历史兼容兜底，不能成为业务规则真源。

2. **参数只允许在一个层级做最终解释。**
   - 业务 API 负责接收业务参数。
   - 业务版本负责声明字段和默认值。
   - 执行适配器负责把业务参数翻译成底层节点参数。
   - 测评端和交付文档只能读取或校验这些结果。

3. **新增能力默认先归入现有业务版本线。**
   - 如果只是模型、工作流、默认值、提示词或质量策略升级，优先视为同一业务的版本升级。
   - 只有业务目标明显不同，例如“四方连续裂变”同时具备新业务特性，才新建业务分类。
   - 不确定时必须先确认，不允许直接新建功能名。

4. **改一个参数时必须同步检查派生面。**
   - 管理端展示、测评端展示、OpenAPI、交付样例、发布 smoke、错误码文档都要确认是否由真源自动派生。
   - 不能自动派生的地方必须登记为短期静态控制点，并纳入发布检查。

## 2. 真源分层

| 内容 | 真源 | 派生或消费位置 | 规则 |
| --- | --- | --- | --- |
| 业务版本、默认版本、版本族、recipe | `business_capabilities` / `backend/app/services/business_seed.py` | 管理端业务能力页、测评端业务入口、业务 OpenAPI | 运行时以数据库为准，seed 只负责初始化 |
| 业务 API 参数、枚举、交付说明 | `backend/app/constants/business_api_contract.py` + `BusinessCapability.input_schema` | `docs/standards/business-api-enums.md`、交付包、测评端文档 | 枚举和可选配置优先从这里集中维护 |
| ComfyUI 节点参数翻译 | `backend/app/services/executors/comfyui.py` | ComfyUI workflow JSON、能力调用日志、业务 run steps | 最终节点写入逻辑只放执行适配器，不分散到前端或文档 |
| ComfyUI workflow 原始结构 | `backend/app/workflows/comfyui/*.json` | workflow seed、执行适配器 | 视为底层交付物，不承载业务默认值解释 |
| 测评端条目展示 | `backend/app/services/eval_workflow_presentation.py`、`backend/app/services/eval_workflow_response.py` | `podi-eval-web/src/App.tsx` | 后端 presentation 优先，前端兜底只能兼容旧数据 |
| 管理端业务工作台 | `backend/app/routers/admin_business.py`、`podi-admin-web/src/features/admin/integration/business.tsx` | 业务版本、接口调用、编排图 | 管理端负责操作动线，不重新定义业务参数 |
| 错误码与错误提示 | `docs/standards/error-catalog.md`、`docs/standards/error-contract.md`、后端异常映射 | 管理端、测评端、交付文档 | 新错误必须先进入错误码总表 |
| 发布检查 | `scripts/podi_release_smoke.py`、`docs/standards/per-feature-release-checklist.md` | 114 发布、线上 smoke | 检查派生关系，不再靠人工口头确认 |

## 3. 排查型文件索引

### 3.1 业务接口入参、出参、状态太重或字段不清楚

先看：

- `backend/app/routers/business.py`
- `backend/app/schemas/business.py`
- `backend/app/services/business_runs.py`
- `backend/app/constants/business_api_contract.py`
- `docs/api/modules/business.md`
- `docs/standards/business-api-enums.md`

判断顺序：

1. 接口路径和认证是否正确。
2. 返回字段是否属于对外契约，还是内部排障字段误暴露。
3. 状态枚举、错误码、轮询结果是否和 Coze 兼容口径一致。
4. 交付样例是否同步。

### 3.2 图裂变尺寸、重绘幅度、颜色锁定等参数没有生效

先看：

- `backend/app/services/business_runs.py`
- `backend/app/constants/business_api_contract.py`
- `backend/app/services/executors/comfyui.py`
- `backend/app/workflows/comfyui/*.json`
- `backend/tests/test_comfyui_new_toolbox_inputs.py`
- `backend/tests/test_comfyui_e7_flux2_liebian_inputs.py`

判断顺序：

1. 业务 run 的 `request_payload` 是否收到正确字段。
2. 业务 step 的 `request_payload` 是否把字段传给能力。
3. `ComfyUIExecutorAdapter` 是否把字段写到正确节点。
4. ComfyUI workflow 节点自身是否存在保持比例、裁剪、默认值覆盖等逻辑。
5. 结果图实际尺寸、OSS 地址和能力日志是否一致。

### 3.3 测评端名称、角标、参数文案、排序不对

先看：

- `backend/app/services/eval_seed.py`
- `backend/app/services/eval_workflow_presentation.py`
- `backend/app/services/eval_workflow_response.py`
- `backend/app/routers/evals_public.py`
- `podi-eval-web/src/App.tsx`
- `podi-eval-web/src/types.ts`

判断顺序：

1. 后端 presentation 是否已经给出业务名、版本名、角标、发布时间和参数说明。
2. 前端是否错误使用了技术名兜底。
3. 是否把版本升级误新增成功能卡片。
4. 裂变类参数是否统一叫“重绘幅度”，禁止再用“相似度”。

### 3.4 业务版本、版本族、继承关系、默认版本不清楚

先看：

- `backend/app/services/business_seed.py`
- `backend/app/services/business_capabilities.py`
- `backend/app/routers/admin_business.py`
- `podi-admin-web/src/features/admin/integration/business.tsx`
- `docs/standards/version-control-rules.md`
- `docs/strategy/business-control-point-matrix-2026-05-19.md`

判断顺序：

1. 当前版本是否属于已有业务入口。
2. `versionLine`、`versionLineage`、父版本、替代版本是否完整。
3. 默认版本是否只能通过发布门禁切换。
4. 管理端是否把技术名当成主标题。

### 3.5 接口调用中心、runId、业务任务和子能力链路不清楚

先看：

- `backend/app/services/business_api_usage.py`
- `backend/app/services/business_runs.py`
- `backend/app/services/ability_task_service.py`
- `backend/app/services/ability_log_service.py`
- `backend/app/routers/admin_business.py`
- `podi-admin-web/src/features/admin/integration/apiExposure.tsx`
- `podi-admin-web/src/features/admin/integration/business.tsx`

判断顺序：

1. 入口调用是否写入 API Key 使用记录。
2. 提交、查询、失败、回调是否按同一个 `runId` 聚合。
3. VL、ComfyUI、OpenAI、评分等是否作为子步骤证据下钻，而不是和业务任务平铺。
4. 列表是否只加载摘要，长请求响应是否按需展开。

### 3.6 ComfyUI 路由、队列、双机命中、节点缺失

先看：

- `config/executors.yaml`
- `backend/app/services/executor_seed.py`
- `backend/app/services/comfyui_queue_service.py`
- `backend/app/services/comfyui_compatibility_service.py`
- `backend/app/services/executors/comfyui.py`
- `docs/comfyui/README.md`
- `docs/comfyui/233-recovery-2026-05-16.md`

判断顺序：

1. 两台服务器是否健康、是否在白名单、是否有队列容量。
2. 能力是否明确绑定可替代的执行节点或标签。
3. 是否因为节点缺失、模型缺失、健康失败导致只命中单机。
4. 是否存在为了兼容单台机器而写死业务规则的风险。

### 3.7 第三方模型、VL、OpenAI、KIE、火山能力异常

先看：

- `vendor-api-ops/`
- `backend/app/services/vendor_api_client.py`
- `backend/app/services/ability_invocation.py`
- `backend/app/constants/abilities.py`
- `backend/app/constants/business_components.py`
- `docs/admin/integration-dashboard.md`
- `docs/standards/error-catalog.md`

判断顺序：

1. Key 是否在中台可见并可用。
2. provider/model 能力 schema 是否匹配。
3. 同步、异步、轮询、回调是否被统一包装成平台任务。
4. 错误提示是否泄露内部信息或误导用户。

### 3.8 发布、上线、回滚和门禁失败

先看：

- `docs/standards/release-sop.md`
- `docs/standards/per-feature-release-checklist.md`
- `docs/release-preflight.md`
- `scripts/release_114_control_plane.sh`
- `scripts/podi_release_smoke.py`
- `docs/releases/CHANGELOG.md`

判断顺序：

1. 当前提交是否已完成本地门禁。
2. 是否完成逐功能检查，而不是只看服务健康。
3. 是否有更新步骤、影响范围和回滚口径。
4. 线上 smoke 是否覆盖业务 API、Coze 工具箱、测评端和 ComfyUI 队列。

## 4. 本次反例：裂变尺寸 2925x2009 输出成 2000x2000

问题表现：

- 业务调用传入 `width=2925`、`height=2009`。
- 业务 run 和能力 step 都正确保存了这两个字段。
- 最终 OSS 图片实际尺寸为 `2000x2000`。

根因：

- 参数没有在业务层丢失。
- 执行适配器已把宽高写入 ComfyUI resize 节点。
- 但 workflow 节点使用了保持比例策略，源图为方图时会把目标画布收敛成方图输出。
- 因此真正的控制点在 `ComfyUIExecutorAdapter` 的节点翻译逻辑，而不是测评端、业务 API 或交付文档。

处理规则：

1. 用户显式传入 `width` 和 `height` 时，执行适配器必须把 resize 节点切换为目标画布策略。
2. 用户未传宽高时，默认跟随原图尺寸，不在前端写死。
3. 尺寸归一化到 ComfyUI 可接受的倍数属于执行适配器职责；普通 latent 流程多为 8 倍数，当前两条裂变目标画布链路按实测结果使用 16 倍数。
4. 不兼容用户拼错字段，例如 `heght`，避免继续扩散隐性控制点。

需要覆盖的测试：

- 显式宽高应写入目标画布策略。
- 宽高归一化应可解释，例如当前 ComfyUI 裂变目标画布会把 `2925x2009` 归一化为 `2912x2000`。
- 未显式传宽高时不应强行改为固定 `2000x2000`。

## 5. 后续执行要求

每次处理业务问题前，必须按下面顺序走：

1. 先在本文档按问题类型找到入口文件。
2. 找到真源文件，确认是否应该在那里改。
3. 只修改真源和必要派生逻辑；不要在前端、文档、seed、适配器多处重复写同一规则。
4. 补测试，测试名要能说明这次防止什么回归。
5. 更新 TODO 或模块文档，记录已改控制点和仍保留的短期兜底。
