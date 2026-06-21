# Repository Guidelines

## 项目结构与模块组织
`backend/` 是 FastAPI 服务，`app/routers` 暴露任务、调度、管理端接口，`app/models`/`schemas` 定义任务、执行器、能力（`Ability`）等 ORM/DTO，`app/services`/`workers` 实现业务逻辑与 Celery 任务，数据库迁移位于 `backend/alembic/`。`podi-eval-web/` 为内部“能力评测”站点；`podi-admin-web/` 为独立管理端（端口 8199），负责执行节点、能力、密钥、评测配置的维护。历史客户端（`podi-design-web-dev/`）已移除，后续将以新的客户端形态重构。顶层 `docs/`、`架构实施计划.md`、`后端架构与业务模型.md` 记录决策与路线图。

### Git 远程与接管约定
- 当前仓库采用双远程：`github=https://github.com/zhangx1234994/POD_AI` 作为外部上游，只用于 `fetch/pull/merge`；`origin=http://192.168.2.210:8888/podi1/pod_ai.git` 作为局域网主仓库，用于日常分支、提交和推送。
- 开发前先执行 `git remote -v`、`git branch --show-current`、`git status --short`，确认当前分支和远程方向；不要把 `D:\01_Dev\Podi` 根目录的状态当作本仓库状态。
- 没有明确授权时不要向 `github` 推送。需要吸收外部更新时，先 `git fetch github --prune`，再把 `github/main` 合并到局域网 `origin` 的目标分支，冲突处理完成后只推送到 `origin`。
- 涉及 Podi 主项目联动时，同步更新 `D:\01_Dev\Podi\documents\AI_WORKFLOW_HANDOFF_SUMMARY.md` 和 `D:\01_Dev\Podi\documents\podi_ai` 下的接管文档。

### 图案拼接多工序编码前置
- 图案拼接进入多工序按非 Coze business API 设计，不走 Coze workflow；正式编码前先梳理 `backend/` 与 `image-ops-service/`、`vendor-api-ops/`、`podi-admin-web/`、`podi-eval-web/` 的调用关系。
- 本机必须先启动 `backend/` 并跑通一次非 Coze 调用：提交 `/api/business/*/runs` 获得 `runId`，再用 `/api/business/runs/get` 查询到稳定状态。直接 curl 可用 `Authorization: Bearer SERVICE_API_TOKEN`，模拟 Podi Java 链路必须使用 `X-PODI-API-Key`。
- 图片处理实现不得把大图 base64 放进业务 API JSON；优先传 URL、服务端下载、处理、上传 OSS，再返回自有 OSS URL。

### 运行事实与回归防错（必须先看）
- 处理服务器、端口、GPU、executor、ComfyUI 模型/插件、图片尺寸、DPI、OSS 前处理或发布门禁问题时，先阅读 `docs/standards/runtime-facts-and-regression-guardrails.md`。
- 沟通和记录里禁止只写“117 服务器”；必须写清 `158/5090/117.50.80.158` 或 `233/4090/117.50.216.233`。
- 图片尺寸相关改动必须同时核对请求参数、实际 ability payload、metadata、最终图片像素和页面展示；任务成功不代表尺寸正确。

### 客户端版本说明（重要）
- 当前仓库已不再包含 `podi-client-web/`、`podi-client-v2/`、`podi-design-web-dev/` 等客户端目录。
- `docs/client/` 与 `docs/handover/` 下的客户端资料仅作为历史参考，不再代表当前开发主线。
- 现阶段主要维护范围是：`backend/`、`podi-admin-web/`、`podi-eval-web/`、`image-ops-service/`、`vendor-api-ops/` 与相关文档。

## 构建、测试与开发命令
后端：`cd backend && uv sync`（或 `pip install -r requirements.txt`），再运行 `alembic upgrade head` 初始化 MySQL 表，命令 `uvicorn app.main:app --reload --port 8099` 启动 API，后台任务使用 `celery -A app.core.celery_app worker -l info`。前端：`podi-admin-web/`、`podi-eval-web/` 分别执行 `npm install && npm run dev`（必要时加 `-- --port <port>`）；管理端另有 `npm run lint`（纯 TypeScript 类型检查）可做快速静态校验。常用诊断：`curl :8099/health`、`python -m pytest backend/tests -q`、`npm run test -- --runInBand`（Vitest）。

### 端口占用处理
开发阶段如遇 `uvicorn` 或 Vite 端口被占用，优先清理旧进程：`lsof -i tcp:<port>` 查 PID，确认无关后直接 `kill <pid>` 并重启对应服务，避免长期切换端口导致前后端配置不一致。

## 编码风格与命名
Python 代码遵循 Black + Ruff（4 空格、snake_case 模块、PascalCase Pydantic 模型），REST 路径统一 `/api/{domain}/{resource}`。TypeScript/React 依赖 ESLint + Prettier，使用函数式组件、camelCase hooks，Tailwind 类名按布局→尺寸→颜色排序。工作流、能力、执行器等枚举常量集中保存在 `app/models/integration.py` 与 `podi-admin-web/src/pages/IntegrationDashboard.tsx` 的映射中。

## 测试准则
新增服务需在 `backend/tests` 编写 pytest 覆盖（优先覆盖任务调度状态流转、Aliyun OSS 上传、能力测试服务 `IntegrationTestService`）。前端使用 Vitest/React Testing Library 校验表单、任务中心刷新以及能力管理交互。管理端还需手动验证：登录后台→“能力管理”中新增条目→“能力测试”选择厂商→上传示例图运行。

## 质量与回归准则（必须遵守）
- **功能做得好不是结束，而是开始**：交互必须顺滑、可预测，覆盖高频和极端输入场景。
- **一次报错足以毁掉信任**：上线前必须做回归测试并输出报告，明确“已覆盖的错误场景清单”和“仍未覆盖的风险”。
- 评测平台/管理端/文档/接口四处一致是硬性要求；任何参数变更必须同步。
- 图片类能力的 `width/height/size/DPI/画布/后处理` 是高风险字段；显式目标尺寸不能静默回退原图尺寸，DPI 元数据不能替代像素尺寸验收。

## 错误契约与文档硬性规范（必须执行）
- **所有新增/修改接口必须枚举错误**：至少包含缺参/依赖失败/超时/并发限制等路径。
- **文档必须包含请求 + 响应 + 错误**：评测端文档需同时包含“错误码总表 + 单功能错误列表”。
- **必须更新错误码总表**：见 `docs/standards/error-catalog.md`（缺失即视为流程问题）。
- **必须遵循错误契约规范**：见 `docs/standards/error-contract.md`。
- **必须遵循接口一致性准则**：见 `docs/standards/interface-consistency.md`（状态词、错误处理、结果回填口径统一）。
- **测试必须覆盖关键错误路径**：缺参 / 依赖失败 / 队列或并发限制 / 超时。

## 提交与 PR
沿用 Conventional Commits（如 `feat: add ability catalog api`、`fix: refresh task center polling`），涉及模型/表结构须与 Alembic 迁移同一 PR 提交。PR 说明中列出变更摘要、配置/环境调整、手工测试步骤（含管理端截图），如修改凭证需在描述中同步文档。

## OSS 与能力目录注意事项
自定义上传配置通过 `aliyun.oss.*` 环境变量注入：`endpoint` 决定区域（默认 `oss-cn-hangzhou.aliyuncs.com`），`access-key-id`/`access-key-secret` 为 RAM 凭证，`bucket`=`podi`，`public-domain`=`https://podi.oss-cn-hangzhou.aliyuncs.com`，`root-prefix` 用于按任务隔离；前端可下发 STS，但务必分配用户级可失效的临时 Key。管理端“能力测试”模块会先调用 `/api/media/v1/upload-key`+`/v1/sts` 将所有样例图统一落盘到 OSS（`podi/<user>/YYYYMMDD/`），若被测接口只接受 Base64 会在后端自动转换；`Ability.input_schema.fields` 现已驱动前端动态渲染输入表单（text/select/textarea/switch/image），标签/描述均以“中文 + English”呈现，便于非技术同学理解。例如 Doubao Seed 1.8 会展示“提示词 Prompt”“图片 URL Image URL”，Seedream 4.5 会展示“输出尺寸 Output Size”等控件。`docs/CREDENTIALS.md` 只记录凭证配置清单与轮换规则，不允许写入真实密钥；真实凭证通过服务器环境变量、中台 `api_keys` 表、受控密钥系统或本地忽略文件 `docs/CREDENTIALS.local.md` 管理。后端通过 `config/executors.yaml` 读取多台服务器共用的默认执行节点（百度、火山、KIE、vendor-api 等），运维只需在每台机器放置相同配置文件即可保持一致。百度图像处理能力使用 `BAIDU_API_KEY/SECRET/ACCESS_KEY` 环境变量或中台 Key 池，需绑定 `type=baidu` 的执行节点方可调用；火山引擎使用 `VOLCENGINE_API_KEY`，节点配置只允许引用环境变量。能力目录已预置百度 7 项图像处理与火山 Doubao（Seed 1.8 多模态对话、Seed 1.6 Lite 轻量多模态、Seedream 4.5/4.0 文生图、Seedance 1.5 Pro 图生视频），并在 `metadata` 中写入 `model_id/api_type/supports_vision` 供工作流及 UI 识别；能力测试会按 `metadata.api_type` 自动切换 `/api/admin/tests/baidu/image-process`、`/tests/volcengine/chat` 或 `/tests/volcengine/image`（视频接口完成后也会自动适配），并在结果区同时预览文本与图片/视频链接。火山“模型列表同步”已接入管理端：`POST /api/admin/vendor-api/models/sync/volcengine` 会读取 `VOLCENGINE_API_KEY` 并调用 Ark 模型列表接口写入 `vendor_model_catalog`。新增能力时：① 在“能力管理”填写 provider/capability_key/默认参数/Schema；② 在 `config/executors.yaml` 或后台页面创建匹配标签的执行节点；③ 回到“能力测试”中选择厂商→能力→节点完成自检。**TODO：** 现有 RAM 信任策略仍允许主账号任意 AssumeRole，需在下阶段收紧主体范围、配置 CLTZ 角色 MFA，并在 `docs/` 中补充失效 Key 流程。

已上线 KIE 中转能力：`config/executors.yaml` 新增 `executor_kie_market_default`（API Key 通过 `KIE_API_KEY` 或中台 Key 池提供，Base URL `https://api.kie.ai`），种子能力覆盖 Nano Banana Pro/Flux-2 Pro 图生图与 Sora2 Pro 文生视频，`metadata` 内记录 `request_endpoint/input_array_target/seed_version` 等信息。管理端“能力测试”在 provider=KIE 时会读取 Schema 渲染中英双语表单（提示词、图像 URL 列表、分辨率、角色 ID 等），自动将多行文本拆分为 `input.image_input`/`input.input_urls` 数组，并调用 `/api/admin/tests/kie/market`：先向 `/api/v1/jobs/createTask` 创建任务，再轮询 `/api/v1/jobs/recordInfo` 获取 `state/resultUrls`，UI 会显示任务 ID、状态、所有结果链接并在左侧预览首个链接。KIE 任务执行已适配旧工作流 dispatcher，异步返回 `running/queued` 时不会被误标记为完成；后续如需扩展其他 KIE 模型，只需在 `app/constants/abilities.py` 填写默认参数+Schema，并在 `metadata` 中约定 `api_type/input_array_target`。TODO：补充 KIE API 积分/速率监控与失败重试策略。

### 能力接入方法论 / 经验总结
- **执行节点**：所有厂商接入必须先在 `config/executors.yaml` 声明节点（API Key、Base URL、并发、权重），再通过 `ensure_default_executors` 写入数据库。鉴于后端经常在 `backend/` 目录启动，`executor_seed` 已支持向上寻找项目根避免路径失效；若管理端提示“缺少接入点”，99% 是 YAML 未被加载或节点被删，请先重新执行种子或手动创建节点。
- **能力定义**：`app/constants/abilities.py` 每个条目都需要 `defaults`（模型/尺寸等）、`input_schema`（动态表单字段，带中英标签）以及 `metadata.api_type` 等调度信息。图像输入字段统一使用 `image_url` 或 `image_urls/input_urls`，便于前端将多行文本拆成数组；`metadata.api_type` 必须与测试/执行逻辑中的分支一致（如 `market_image_to_image`），否则管理端会提示“不支持该类型”。
- **媒资沉淀**：无论第三方返回 `url` 还是 `b64_json`，`IntegrationTestService` 都会调用 `media_ingest_service` 先下载再上传到自有 OSS，并在响应中返回 `assets/storedUrl`。正式任务也应遵循“外链立即落地 → 对外只暴露自有 URL”的惯例，以免外部链接过期。
- **联调流程**：
  1. 在“执行节点”确认目标厂商节点 active，必要时直接编辑配置。
  2. 在“能力管理”核对 `provider/capability_key/default_params/input_schema/metadata`，缺失项立即补齐。
  3. “能力测试”上传样例图，检查 Schema 自动填充是否正确，再运行测试查看任务 ID、状态、结果 URL。如报错，展开 Raw Response 对照厂商文档定位问题。
- **常见问题 & 处理**：
  - 缺少接入点 → 重新跑种子或手动创建节点，让数据库存在 `executor_<provider>_*`。
  - 提示“暂不支持该类型” → 检查 `metadata.api_type` 是否缺失/拼写错误，并刷新前端缓存。
  - 接口成功但无预览 → 查看 Raw Response 是否包含 `resultUrls`/`b64_json`，必要时调整 `response_format` 或确保上传图片有公网 URL。

以上方法论遵循“节点配置 → 能力配置 → 管理端测试”的闭环，尽量在早期发现配置缺口，减少重复踩坑。

## 能力接入现状 & 优化记录
1. **能力元数据补全**  
   - ✅ 2026-01-08：`backend/app/constants/abilities.py` 现包含百度/火山/KIE 预置能力的 `input_schema`、`metadata`（含 `api_type/model_id/supports_vision/requires_image_input`），`ability_seed` 直接复用该文件成为唯一数据源。  
   - TODO：新接入能力必须同步维护 schema/metadata，并确保管理端映射（`IntegrationDashboard`）感知 `metadata.api_type`，否则无法测试。
2. **能力健康检查与自检报告**  
   - 管理端目前支持手动触发测试，但缺少自动化可用性检测。  
   - TODO：在后端增加定时自检任务（复用 `IntegrationTestService` 并记录结果），并在管理端展示最近一次成功/失败时间，避免上线后能力沉默。
3. **执行节点标签与能力绑定**  
   - `config/executors.yaml` 与执行节点已支持 `tags`，能力和任务可通过 `required_tags` / `required_executor_tags` 精准筛选执行节点。
   - TODO：继续补齐核心能力的标签覆盖率和管理端提示，避免新增节点只填 `provider/type` 导致路由不够精确。
4. **任务链路透出与文档习惯**  
   - 能力接入完成后，需立即在本文档更新现状/变更描述，形成“能力目录日志”。  
   - 每次新增能力或优化调度逻辑，最少记录：接入日期、依赖节点、默认参数、测试截图/结果摘要、是否加入自检计划。此习惯与“做完一项任务必须有记录”保持一致。

### 能力目录更新日志
- 2026-01-08：能力常量补齐 schema/metadata（百度图像处理、火山 Doubao 全系列、KIE 市场模型），管理端 `requires_image_input` 逻辑改为读取 metadata，能力 Seed→数据库同步路径统一。
- 2026-01-08：新增 ComfyUI · 四方连续能力（workflow `sifang_lianxu`），配置 `executor_comfyui_seamless_117`、内置 workflow/binding seed，并提供 `/api/admin/tests/comfyui/workflow` 链路自检。管理员在“执行节点/工作流/绑定/能力”栏目刷新即可自动落库，再到“能力测试”选择 ComfyUI 进行回归。
- 2026-01-08：修复 `backend/app/workflows/comfyui/sifang_lianxu.json` Base64 字段导致的 JSON 解析问题，将默认值置空并保留 `image_output/save_prefix`，随后运行
  ```bash
  cd backend && python3 - <<'PY'
  from app.core.db import get_session
  from app.services.executor_seed import ensure_default_executors
  from app.services.workflow_seed import ensure_default_workflows, ensure_default_bindings
  from app.services.ability_seed import ensure_default_abilities
  with get_session() as session:
      ensure_default_executors(session)
      ensure_default_workflows(session)
      ensure_default_bindings(session)
      ensure_default_abilities(session)
  PY
  ```
  触发所有种子写入，确保管理端可见 ComfyUI 执行节点、工作流与能力。
- 2026-01-08：考虑到 ComfyUI 队列作业普遍耗时较长，`COMFYUI_ABILITIES.sifang_lianxu.defaults` 补充 `timeout: 480`，`IntegrationTestService.run_comfyui_workflow` 会从 `workflowParams.timeout` 读取并写入 workflow definition（60~900 秒之间），避免 180 秒默认超时导致“测试失败，请检查日志或参数”。
- 2026-01-08：`ComfyUIExecutorAdapter` 现在会为没有 `url` 字段的输出节点自动拼接 `{baseUrl}/view?filename=<>&subfolder=<>`，再调用 OSS 媒资沉淀，确保测试/正式任务都能得到可访问的 `storedUrl`。
- 2026-01-08：补充 ComfyUI 输出格式识别：workflow 可能返回 `images[].url`、`images[].base64`、或仅有 `{filename, subfolder, type}` 三种情况，Adapter 会依序尝试远程 URL、Base64、`/view` 下载，保证所有输出都能上传 OSS 并返回最终 `storedUrl`。
- 2026-01-08：`COMFYUI_ABILITIES` Schema 补充节点编号描述（如“节点 42 · StringConcatenate.string_a”），并将能力库里的 `input_schema` 更新至 seed_version=2，管理端测试表单刷新后会在每个字段旁提示对应 ComfyUI 节点，便于 Workflow 工程师快速定位。
- 2026-01-08：`ComfyUIExecutorAdapter._resolve_image_source` 若仅收到图片 URL（无 Base64），会主动下载并生成 Base64，保证节点 104（`easy loadImageBase64`）仍能拿到原图，避免输出中心出现空白块。
- 2026-01-09：管理端对 ComfyUI “四方连续” 能力测试仍然存在“中心留白”问题。当前 Workflow JSON 已锁定节点 104 Base64 默认值，其余节点沿用用户在 ComfyUI 中验证过的配置；后台测试时需重点关注节点 96（外部图片 URL）与 97（是否四方连续）的输入。近期调试结论：直接在 ComfyUI 中使用 OSS 图片链接效果正常，透过后端调用时需确认我们写回的 Base64 没有被覆盖，后续继续排查 `LoadImagesFromURL` → `ImageResize+` → `easy loadImageBase64` 的数据链路并对比原始 payload。
- 2026-01-09：新增 ComfyUI “印花提取” Workflow（`backend/app/workflows/comfyui/yinhua_tiqu.json`），执行节点 `executor_comfyui_pattern_extract_158` 指向 117.50.80.158:8079，`workflow_seed`/`binding_seed` 均已纳入；能力定义 `comfyui.yinhua_tiqu` 提供正/反向提示词、圆角遮罩、输出尺寸、LoRA 文件名等字段，并在 Schema 描述里标注节点号。为满足“LoRA 更换可追溯”的需求，`defaults` 与字段默认值均注明当前 LoRA：`印花提取-YinHuaTiQu-Qwen-Image-Edit-LoRA_V1.safetensors`，后续切换版本只需在能力表单中修改即可。
- 2026-01-09：整理 `docs/comfyui/README.md`，集中记录四方连续 & 印花提取 workflow 的执行节点、关键节点、默认参数与版本更新指引。后续任何 ComfyUI 工作流/LoRA/能力表单变更，都需同步更新该文档，方便非技术同学查阅与版本追踪。
- 2026-01-12：印花提取 workflow 精简为 `yinhua_tiqu` v2（去掉遮罩/预览，只保留核心链路），`abilities.py` schema 和 `ComfyUIExecutorAdapter` 均改写为映射节点 393/110/111/390/400；`docs/comfyui/README.md` 与 OSS 文件默认名同步更新。该版本默认输出 1800×1800 PNG，可在表单传入宽高和 LoRA 文件名控制结果。
- 2026-01-12：新增 `/api/admin/comfyui/models` 接口，通过 ComfyUI `/object_info` 自动列出目标执行节点的 `unet/clip/vae/lora` 选项，管理端后续可直接绑定下拉框，不再手填模型/LoRA 名称。
- 2026-01-12：上线统一原子能力 API：`GET /api/abilities` 列出全部激活能力，`POST /api/abilities/{abilityId}/invoke` 负责执行（字段包括 `inputs`、`images`、`metadata` 等，详见 `docs/api/abilities.md`）。该接口面向内部编排、测评端、管理端和高级开发；普通业务方正式接入优先使用 `/api/business/*`。所有调用自动写入 `ability_invocation_logs`，管理端“能力测试”与客户端调用共享同一条日志链路；“能力测试”页新增“统一能力接口”板块，可一键复制 Ability ID/cURL 示例，方便非技术同学验证。

### 能力调用记录 / Admin 日志（2026-01-12）
- 新建 `ability_invocation_logs` 表与 `AbilityLogService`，所有 `admin/tests/*` 调用都会写入能力 ID、执行节点、来源（默认 `admin-test`）、耗时、请求/响应摘要以及输出的 OSS 链接，再由 FastAPI 的 `/api/admin/abilities/{ability_id}/logs` 接口按时间倒序返回最近 N 条记录。
- 管理端“能力测试”页新增“最近调用记录”卡片，默认展示 12 条记录并支持手动刷新；记录里会自动跳过 Base64 正文，只保留 `storedUrl`、`resultUrls`、失败原因等关键信息，方便非技术同学在控制台追踪每次测试或排查失败原因。
- 若后续在正式任务/工作流中也需要追溯能力调用，可直接复用 `AbilityLogService.start_log/finish_*`，保持测试与生产链路的可观测性一致。

### 当前执行入口 / 恢复工作顺序
- 当前战略级待办唯一入口是 `docs/strategy/todo-master-2026q2.md`；旧 TODO、交接记录、客户端评审文档只作为历史参考。
- 新增任务或变更优先级时，先更新唯一待办池，再同步模块文档、接口文档和错误码规范。
- 当前恢复工作优先级：① 发版门禁与事故整改闭环；② 管理端信息架构与易用性降噪；③ 业务能力稳定化；④ 第三方能力治理；⑤ 测评端/客户端整体前端整改。
- 所有服务启停遵循“端口占用即杀死重启”规范：`lsof -i tcp:8099` -> `kill -9 <pid>` -> `python3 -m uvicorn app.main:app --reload --port 8099`，管理端/测评端同理。
