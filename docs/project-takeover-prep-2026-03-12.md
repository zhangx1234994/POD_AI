# 项目接手准备清单（2026-03-12）

> 2026-04-30 更新：本文是历史接手记录，保留用于追溯当时认知，不再作为当前执行真源。当前入口以 `docs/README.md`、`docs/strategy/todo-master-2026q2.md`、`AGENTS.md` 为准。
> 目的：给新接手同学一个“先看什么、现在什么是真的、先核对什么”的统一入口。
> 结论优先：当前真正稳定的主链路是 **账号密码登录 + 统一能力调用 + AbilityTask 异步任务 + OSS 媒资沉淀 + 管理端配置/测试**。
> 大量身份、钱包、通用任务编排、工作流平台能力仍处于规划或半落地状态，接手时必须区分“现状”与“规划”。

## 1. 先认准真源文档

### 当前实现真源
- 架构总览：`docs/architecture.md`
- 文档索引：`docs/README.md`
- API 入口：`docs/api/INDEX.md`
- 统一能力接口：`docs/api/abilities.md`
- 错误码：`docs/standards/error-catalog.md`
- 错误契约：`docs/standards/error-contract.md`
- 状态/结果一致性：`docs/standards/interface-consistency.md`
- 开发与部署：`docs/development-guide.md`、`docs/DEPLOYMENT.md`、`docs/deploy-checklist.md`、`docs/release-preflight.md`
- 战略与待办唯一入口：`docs/strategy/README.md`、`docs/strategy/todo-master-2026q2.md`

### 历史或规划参考
- 历史路线图：`docs/TODO_PLATFORM.md`
- 历史错误码草案：`docs/error-codes.md`
- 架构规划背景：`后端架构与业务模型.md`、`架构实施计划.md`
- 需求规划稿：`docs/workflow-platform-requirements.md`

## 2. 当前系统真实边界

- 后端 `backend/`：FastAPI + Celery，负责能力调用、异步任务、媒资落盘、日志追踪、厂商适配。
- 管理端 `podi-admin-web/`：执行节点、能力、工作流、绑定、API Key、能力测试、调用记录、ComfyUI 管理。
- 评测端 `podi-eval-web/`：工作流评测、批量评测、回归验证、结果展示。
- 外部集成：Coze、ComfyUI、Baidu、Volcengine、KIE。
- 历史客户端 `podi-design-web-dev/` 已移除，不能再按旧客户端文档理解当前前端结构。

## 3. 当前主链路

### 已落地主链路
1. 用户登录：`/api/auth/login`
2. 获取能力清单：`GET /api/abilities`
3. 同步调用能力：`POST /api/abilities/{abilityId}/invoke`
4. 异步能力任务：`POST /api/ability-tasks` + `GET /api/ability-tasks/{id}`
5. 结果媒资统一沉淀到 OSS
6. 管理端完成执行节点/能力/工作流/绑定配置与测试

### 仍属规划或半落地
- 统一 SSO / 多身份体系
- 钱包、充值、完整计费闭环
- 通用 Task/Job 编排平台
- 可视化 DAG 工作流平台
- 自动化健康巡检与 SLA 面板

## 4. 必须遵守的工程约束

- 固定端口：后端 `8099`，管理端 `8199`，评测端 `8200`
- 端口冲突先杀进程，不临时改端口
- 新改接口必须同时补：请求、响应、错误、错误码总表、关键错误路径测试
- 错误码总表唯一真源：`docs/standards/error-catalog.md`
- 状态语义必须遵守：`submit_status` / `callback_status` / `final_status`
- “任务成功”与“预览已回填”是两回事，展示层必须区分
- 任何外链/上游返回 `url` 或 `base64`，最终都要转成自有 OSS 地址

## 5. 接手首轮核对清单

### A. 环境与启动
- 核对 `backend/.env`
- 执行 `cd backend && alembic upgrade head`
- 确认固定端口未漂移
- 确认前端部署/联调方式不是线上 `npm run dev`

### B. 配置与依赖
- 核对 `config/executors.yaml` 是否与数据库一致
- 核对能力是否有默认 `executor_id` / `workflow_id`
- 核对 Coze / KIE / Volcengine / Baidu / OSS 关键环境变量
- 核对 ComfyUI 节点是否 active 且可从 `8099` 所在主机访问

### C. 文档与实现一致性
- 以 `docs/api/INDEX.md` 和 `docs/api/modules/*.md` 为 API 真源
- 以 `docs/standards/*` 为状态/错误真源
- 对“历史/规划”文档加区分，不把未落地内容当成现状

### D. 回归基线
- 后端契约测试至少跑状态/错误相关用例
- 管理端至少跑 TypeScript 检查
- 评测端至少跑一次构建
- 发版前跑 `scripts/deploy_preflight.sh`

## 6. 本次接手时的快速检查结果

- 已阅读核心架构、API、标准、策略、ComfyUI、Coze、测试与复盘文档
- `backend` 状态/错误相关测试通过：
  - `cd backend && python3 -m pytest tests/test_task_status_contract.py tests/test_ability_task_status_mapping.py -q`
- 管理端类型检查通过：
  - `cd podi-admin-web && npm run lint`
- 评测端构建通过：
  - `cd podi-eval-web && npm run build`

### 当前观察到的风险
- 工作区已有未提交改动，接手开发时需避免误覆盖：
  - `backend/app/services/ability_task_service.py`
  - `backend/app/services/eval_seed.py`
  - `docs/api/modules/eval.md`
  - `docs/eval/eval-platform.md`
  - `docs/standards/issue-improvement-log.md`
  - `podi-eval-web/src/App.tsx`
  - `docs/api/assistant-skill-integration.md`
- `backend/app/core/config.py` 存在一组 Pydantic v2 `Field(..., env=...)` 弃用警告，暂不影响运行，但建议后续统一清理
- 评测端构建产物存在大 chunk 告警，后续可考虑按页面或能力模块拆包
- 本地环境真值检查结果：
  - `backend/.env` 存在
  - Alembic 当前已到最新 head：`20260304_add_task_cost_snapshots`
  - 数据库当前核心记录数：
    - `users=2`
    - `executors=6`
    - `abilities=25`
    - `workflows=4`
    - `workflow_bindings=4`
    - `eval_workflow_version=31`
    - `wallet_accounts=0`
  - 真实数据库进一步核对结果：
    - `ability_invocation_logs` 总量：`11470`
    - 当前 `pending` 日志：`0`
    - `ability_tasks` 总量：`7257`
    - 当前活跃中的异步任务：`0`
  - 评测工作流分类分布：
    - 四方/两方连续图类：active `1`
    - 图延伸类：active `2`
    - 图裂变：active `4`，inactive `1`
    - 花纹提取类：active `4`，inactive `2`
    - 通用类：active `14`，inactive `3`
  - 本机服务当前都没启动：
    - `8099` 后端：未监听
    - `8199` 管理端：未监听
    - `8200` 评测端：未监听
- 远端执行节点连通性摸底：
  - 百度默认节点：可访问（返回 403，说明地址通但需要鉴权）
  - 火山默认节点：可访问（返回 401，说明地址通但需要鉴权）
  - KIE 默认节点：可访问（返回 404，说明域名通）
    - 两台正式 ComfyUI：`system_stats` 都返回 200
  - 钱包初始化脚本 dry-run 结果：
    - 缺少钱包账号用户数：`2`
- 还发现一个需要警惕的执行节点：
  - `executor_mock_history_history_success_no_images_62359`
  - 类型是 `comfyui`，地址是 `127.0.0.1:62359`
  - 很像测试遗留或本地 mock 节点，后续现场联调时要确认它是否应该存在
- 这说明：
  - 能力平台和评测基础数据已经落库
  - 当前库里确实已有激活的管理员账号，不是“只有 service token 能用”的状态
  - 钱包表结构大概率已经迁好，但钱包账号初始化还没有做
  - 正式远端资源看起来大体可达，但本机开发服务目前没起
  - 当前数据库里没有正在挂住的能力异步任务，历史任务与日志已经积累到可观规模

## 6.1 本轮实操冒烟结果

### 已经实际跑通的
- 后端服务可手动启动：`python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8099`
- 管理端和评测端可手动启动：
  - `npm run dev -- --host 127.0.0.1 --port 8199`
  - `npm run dev -- --host 127.0.0.1 --port 8200`
- 健康检查通过：`GET /health`
- 能力清单可正常返回：`GET /api/abilities`
- 管理端受保护接口可通过 `SERVICE_API_TOKEN` 正常访问：
  - `GET /api/admin/workflows`
  - `GET /api/admin/dashboard/metrics`
- 评测工作流公开清单可正常返回：
  - `GET /api/evals/workflow-versions?status=active`
- Coze OpenAPI 可正常返回：
  - `GET /api/coze/podi/openapi.json`
- **同步能力调用已实际跑通**
  - 能力：`podi_set_dpi`
  - 输入：本地 PNG 图片转 Base64
  - 结果：返回 `200`，`status=succeeded`，并且有 `images=1`、`assets=1`

### 本轮暴露出的明确问题
- **异步能力任务 + service token 的 bug 已定位并修复**
  - 原现象：`POST /api/ability-tasks` 返回 `500 Internal Server Error`
  - 原根因：当用 `SERVICE_API_TOKEN` 调用时，系统会构造虚拟用户 `service`
  - 旧逻辑会把 `user_id='service'` 直接写进 `ability_tasks`
  - 但数据库 `users` 表里没有这条用户，于是触发外键错误
  - 当前修法：
    - 对 service user 不再写 `ability_tasks.user_id`
    - 仍保留正常用户的 `user_id`
  - 结果：
    - 同步调用链路可用
    - service token 下的异步任务链路现在也已跑通

### 本轮遇到但暂不判成系统 bug 的情况
- 用外部图片 URL 调 `podi_set_dpi` 时出现过 `IMAGE_DOWNLOAD_FAILED`
- 改用本地图片 Base64 后同步调用成功
- 这更像是“外部图片可达性/下载链路”问题，暂不直接定性为能力本身失败

### 本轮修复验证结果
- 新增回归测试：
  - `backend/tests/test_ability_task_owner.py`
- 已通过测试：
  - `cd backend && python3 -m pytest tests/test_ability_task_owner.py tests/test_ability_task_status_mapping.py -q`
- 已重新冒烟验证：
  - `POST /api/ability-tasks` 在 `SERVICE_API_TOKEN` 下可成功创建任务
  - 随后 `GET /api/ability-tasks/{id}` 可查询到 `succeeded`

## 7. 代码结构速览

### 后端入口与主模块
- 应用入口：`/Volumes/MAC 1/pod_codex/backend/app/main.py`
- 启动时会预热两个后台服务：
  - `get_ability_task_service()`
  - `get_eval_service()`
- 路由主要分为：
  - `auth.py`：登录、refresh
  - `abilities.py`：能力清单、能力调用
  - `ability_tasks.py`：异步能力任务
  - `admin_integrations.py`：执行节点/工作流/API Key/ComfyUI 管理/能力测试
  - `admin_abilities.py`：能力目录、模板、日志、指标
  - `evals_public.py`：评测端公开/内部接口
  - `coze_podi_plugin.py`：Coze OpenAPI、工具箱、任务查询
  - `agent_management.py`：桌面 Agent 与 ComfyUI 服务器管理
  - `media.py`、`wallet.py`、`tasks.py`、`notify.py`

### 后端关键服务
- `ability_invocation.py`：统一能力目录与同步调用核心，负责执行器选择、参数归一、日志、回调
- `ability_task_service.py`：异步任务队列、恢复、回填、队列上限控制
- `integration_test.py`：管理端能力测试统一入口
- `eval_service.py`：评测运行、批量评测、状态恢复
- `media_ingest.py` + `oss.py`：媒资下载/转换/落 OSS
- `wallet.py`：钱包、冻结、支出、账单

### 数据模型中心
- `models/integration.py`：Executor / Workflow / WorkflowBinding / Ability / ApiKey / ComfyUI 目录
- `models/eval.py`：评测工作流、运行记录、批次、素材、评审
- `models/user.py`：用户与登录
- `models/wallet.py`：钱包与流水

### 前端真实结构
- 管理端几乎是单页控制台：
  - 入口：`/Volumes/MAC 1/pod_codex/podi-admin-web/src/App.tsx`
  - 主壳：`/Volumes/MAC 1/pod_codex/podi-admin-web/src/layouts/AdminShell.tsx`
  - 核心页面：`/Volumes/MAC 1/pod_codex/podi-admin-web/src/pages/IntegrationDashboard.tsx`
- 评测端也是单页控制台：
  - 入口：`/Volumes/MAC 1/pod_codex/podi-eval-web/src/App.tsx`
  - 主壳：`/Volumes/MAC 1/pod_codex/podi-eval-web/src/layouts/EvalShell.tsx`
  - API 封装：`/Volumes/MAC 1/pod_codex/podi-eval-web/src/api.ts`

### 管理端页面真相
- 管理端不是 React Router 多页应用，而是：
  - `LoginGate` + `IntegrationDashboard`
  - 再通过 hash 参数 `#nav=...` 控制左侧模块切换
- 核心导航包括：
  - 总体概览
  - 能力目录
  - 能力评测
  - 执行节点
  - 能力调用
  - ComfyUI 管理
  - API Keys
  - 调度监控
  - 系统配置
- `能力测试` 现在主要已经并入 `能力目录 -> 能力详情 -> 实时测试`，不是独立主页面
- 真正独立拆出的页面只有 `AbilityEvaluationPage`

### 评测端页面真相
- 评测端也不是 Router 应用，而是：
  - 单个 `App.tsx`
  - 用 URL 查询参数 `?view=&category=&tool=` 做视图状态切换
- 顶部主视图是：
  - 功能评测
  - 批量回归
  - 任务追踪
  - 接口文档
  - 维护配置
- 当前评测端真实主业务流不是统一能力 API 前台，而是：
  - `workflow_version -> eval_run -> 结果查看 -> 评分/备注`
- 批量回归是围绕评测 run 做的大样本扩展，不是独立任务系统

## 8. 代码层面的当前判断

### 实际上已经跑起来的实现
- `/api/auth/login` + JWT
- `/api/abilities` 公开能力清单
- `/api/abilities/{id}/invoke` 需要鉴权
- `/api/ability-tasks` 异步任务主链路
- 管理端能力目录、执行节点、ComfyUI 管理、能力调用日志
- 评测端 workflow runs + batch + review 流程
- Coze OpenAPI 与工具箱任务查询

### 代码结构上的真实情况
- 后端虽然分了 routers/services/models，但核心逻辑仍高度集中在少数超大文件中：
  - `backend/app/routers/evals_public.py`：2502 行
  - `backend/app/routers/coze_podi_plugin.py`：2232 行
  - `backend/app/services/ability_invocation.py`：2043 行
  - `backend/app/services/eval_service.py`：1497 行
  - `backend/app/services/ability_task_service.py`：1023 行
- 前端两端都还没有完全模块化：
  - `podi-admin-web/src/pages/IntegrationDashboard.tsx`：14903 行
  - `podi-eval-web/src/App.tsx`：6237 行
- 这说明当前系统功能是“能用的”，但前端和部分后端都存在明显的大文件/高耦合维护成本

### 文档与代码对照后确认的几点
- `GET /api/abilities` 确实是公开接口；`POST /api/abilities/{id}/invoke` 与 `/api/ability-tasks*` 需要登录
- `wallet.py` 已不是纯空壳占位，已经有冻结、支出、充值单、账单、usage summary 等接口
- `tasks.py` 这条历史 `/api/tasks/v1/*` 兼容链路仍然在代码里，不应误判为完全删除
- 评测端并不是“很轻的文档页”，而是已经包含较重的批量评测、结果标注、上传、分页续标逻辑
- 管理端真实上是“单页控制台 + 超大 IntegrationDashboard”，文档里若把它理解成多页面会失真
- 评测端真实上是“工作流评测台”，不是 repo 其他部分文档里暗示的“统一能力接口前台”

## 9. 环境与运维入口

### 配置来源
- 主配置文件：`/Volumes/MAC 1/pod_codex/backend/app/core/config.py`
- 示例环境变量：`/Volumes/MAC 1/pod_codex/backend/.env.example`
- 执行节点 YAML：`/Volumes/MAC 1/pod_codex/config/executors.yaml`
- `executor_seed` 会读取 `backend/.env` 并把 `${ENV_VAR}` 展开到执行节点配置里

### 当前关键环境变量分组
- 数据库：`DATABASE_URL`
- OSS：`OSS_*`、`UPLOAD_TOKEN_*`
- JWT / Service Token：`JWT_*`、`SERVICE_API_TOKEN`
- Agent：`AGENT_*`
- 钱包：`WALLET_*`
- Coze：`COZE_*`
- 评测：`EVAL_*`
- ComfyUI：`COMFYUI_*`
- 厂商凭证：`BAIDU_*`、`VOLCENGINE_*`、`KIE_*`

### 当前配置特点
- `Settings` 会强制读取 `backend/.env`，不依赖当前 shell 是否手动 `source`
- `config/executors.yaml` 支持 `${ENV_VAR}` 占位；`executor_seed` 会额外读取 `backend/.env` 来展开这些值
- `main.py` 不会在 startup 自动跑 Alembic，也不会自动把所有 seed 全量写库
- 默认 seed 更像“懒修复/懒初始化”：
  - 能力：访问能力相关链路时触发
  - 执行节点：访问 executor 相关链路或 seed 逻辑时触发
  - 工作流/绑定：访问对应链路时触发

### 本地开发脚本
- 一键重启：`/Volumes/MAC 1/pod_codex/scripts/dev_restart_all.sh`
- 后端重启：`/Volumes/MAC 1/pod_codex/scripts/dev_restart_backend.sh`
- 前端重启：`/Volumes/MAC 1/pod_codex/scripts/dev_restart_web.sh`
- 端口/健康检查：`/Volumes/MAC 1/pod_codex/scripts/dev_status.sh`

### 部署/发版脚本
- 无 Docker prod-like：`/Volumes/MAC 1/pod_codex/scripts/deploy_prodlike_nodocker.sh`
- 发布前检查：`/Volumes/MAC 1/pod_codex/scripts/deploy_preflight.sh`
- 后端预检查脚本：`/Volumes/MAC 1/pod_codex/backend/scripts/preflight_run.py`

### 运维层面的真实情况
- `main.py` startup 不会自动做迁移，也不会强制全量 seed
- 默认执行节点 / 能力 / 工作流写库，更多是通过懒加载 seed 触发
- 本地开发脚本仍然会直接跑 Vite dev server；正式部署脚本走静态产物 + prod-like

### 正式部署链路
1. 后端：`scripts/prodlike_restart_backend.sh`
   - 建 venv
   - `pip install -e backend`
   - `alembic upgrade head`
   - 启动 `uvicorn app.main:app --host 0.0.0.0 --port 8099`
2. 前端：`scripts/prodlike_restart_web_static.sh`
   - `npm ci`
   - `npm run build`
   - 用 `scripts/node_static_proxy.mjs` 提供静态文件 + `/api` 同源反代
3. 发版前：`scripts/deploy_preflight.sh`
4. 状态/错误专项回归：`scripts/status_error_regression.sh`

## 10. 文档与实现的典型偏差

- `backend/README.md` 仍把部分钱包/任务链写成占位，但代码里钱包已是可用实现
- 文档常把 `/api/tasks/v1/*` 说成历史/规划；代码里它仍挂载且可访问
- `docs/api/abilities.md` 里部分说法偏旧，例如同步 `invoke` 的 `status` 并不总是固定 `succeeded`
- 文档里常把“能力测试”理解为独立页；现在管理端实际上已合并进能力目录详情区
- 评测文档若把前台理解为能力接口客户端，会和代码现状不一致；真实主链还是 workflow eval

## 11. 现行主链路 vs 历史兼容链路

### 现行主链路（接手时优先关注）
- 登录：`/api/auth/login`
- 统一能力同步调用：`/api/abilities/*`
- 统一能力异步任务：`/api/ability-tasks/*`
- 管理端能力测试：`/api/admin/tests/*`
- Coze 插件：`/api/coze/podi/*`
- 评测平台：`/api/evals/*`
- Agent/ComfyUI 管理：`/api/agent/*`、`/api/admin/comfyui/*`

### 仍在代码里，但不要误当主链
- 历史任务中心：`/api/tasks/v1/*`
- 历史 points/mock：`/api/op/v1/*`、`/api/os/v1/*`
- 通用 `TaskDispatcherService`
  - 当前只有 `baidu`、`comfyui` adapter 是真实实现
  - `openai`、`volcengine`、`aliyun` 默认还是 mock/fallback

### 为什么这很重要
- 如果后面排问题时把 `/api/tasks/v1/*` 当主链，会误判很多实现状态
- 如果后面做重构时没有区分新旧链路，容易在旧代码上继续叠逻辑，导致更难维护
- 接手阶段应优先围绕：
  - AbilityInvocationService
  - AbilityTaskService
  - EvalService
  - admin/tests
  - Coze plugin
  - ComfyUI/Agent 管理
- 另外有一个很重要的真相：
  - 现在数据库里的 `abilities` 记录，大多数并没有直接写死 `executor_id` / `workflow_id`
  - 也就是说系统更多依赖“按 provider 自动挑默认执行节点”或“按 workflow binding 去路由”
  - 所以后面如果你看到某个能力表里 `executor_id` 是空的，不一定代表它不能跑

## 12. 当前值得重点警惕的风险

- `backend/app/core/config.py` 里有一些对外默认值偏“内部环境优先”，比如 `EVAL_ADMIN_TOKEN` 默认值；正式环境必须核对是否被覆盖
- seed 采用懒加载，意味着“数据库里没有数据”与“代码里有默认定义”不是一回事，排障时要分别看代码、YAML、DB 三处
- 正式 prod-like 脚本会自动迁移，但本地直接手动跑 `uvicorn` 不会迁移；容易出现“本地能起但接口报字段不存在”
- 历史兼容链路仍在代码里，会增加理解成本，也会让文档显得前后矛盾
- 前后端主页面都极大，后续接手改动时要非常小心局部变更对全局状态的影响
- 钱包服务是“数据库优先 + 内存回退”模式，测试环境和正式环境的行为可能不完全一样
- 通知服务目前还是内存版 WebSocket 广播，不是完整的持久化消息系统

## 13. 数据库 / 迁移 / Seed 关系

### 主要数据域
- 用户与认证：`users`
- 能力平台：`executors`、`workflows`、`workflow_bindings`、`api_keys`、`abilities`
- 能力调用：`ability_invocation_logs`、`ability_tasks`
- 评测：`eval_workflow_version`、`eval_run`、`eval_annotation`、`eval_batch_*`
- Agent / ComfyUI 运维：`agents`、`agent_manifests`、`agent_tasks`、`agent_task_events`、`agent_alerts`、`comfyui_repair_*`
- 钱包计费：`wallet_accounts`、`wallet_holds`、`wallet_ledger`、`recharge_orders`、`task_cost_snapshots`
- 历史任务中心：`task_batches`、`tasks`、`task_assets`、`task_events`

### 迁移演进的大致顺序
1. `users`
2. `abilities`
3. `ability_invocation_logs`
4. `ability_tasks`
5. ability 模型扩展、cost snapshots、callback 字段
6. ComfyUI 目录相关表
7. eval 相关表 + eval batch / output review
8. agent / bootstrap / repair / runtime policy
9. wallet / billing / task_cost_snapshots

### 迁移层面的真实情况
- Alembic 主入口：`/Volumes/MAC 1/pod_codex/backend/alembic/env.py`
- Alembic 会优先读环境变量 `DATABASE_URL`；没有时再尝试从 `backend/.env` 里取
- 仓库里存在多个 merge migration，说明历史上有多分支并行演进
- 还专门放了兼容 revision `f310ca291324`，用来处理远端已有 revision 但本仓库缺文件的情况
- 还提供了修复脚本：`/Volumes/MAC 1/pod_codex/backend/scripts/db_upgrade.py`

### Seed 与迁移的关系
- 迁移负责“表结构存在”
- seed 负责“默认记录存在”
- 即使表已经迁完，也不代表默认能力 / 执行节点 / 工作流 / 绑定已经在数据库里
- 反过来，代码里有 seed 定义，也不代表 DB 当前一定已经写入成功

### 当前推荐检查顺序
1. 先看 Alembic 是否到 head
2. 再看数据库里核心表是否存在
3. 再看 executors / abilities / workflows / bindings 是否已有默认数据
4. 最后再判断是“代码问题”还是“环境/seed 未生效”

## 14.5 能力清单速记（当前已知）

### 已预置的能力大类
- 百度图像处理：7 个
  - 无损放大、老照片上色、摩尔纹去除、拉伸修复、去雾增强、对比度增强、去噪净化
- 火山多模态/文本：2 个
- 火山图片生成：2 个
- 火山视频生成：1 个
- KIE：4 个
  - 主要是图生图、文生视频
- ComfyUI：6 个
  - 四方连续、印花提取、花纹扩图、极速处理版、中速提质版、多图融合
- PODI 自有工具：3 个
  - 扩边占位图、设置 DPI、高质量缩放

### 怎么理解这些能力
- 百度 / 火山 / KIE：主要是“调第三方真实接口”
- ComfyUI：主要是“调自己的工作流节点”
- PODI 工具：主要是“平台自己做的一些图片处理小工具”

### 当前数据库里的能力绑定现状
- 百度、火山、KIE、PODI 工具能力：
  - 大多没有在能力表里直接绑定 `executor_id`
  - 更像是运行时按 provider 去找默认执行节点
- ComfyUI 能力：
  - 也大多没有直接在能力表里写 `workflow_id`
  - 主要靠 `workflow_bindings` 做动作到工作流、工作流到执行节点的映射
- 当前已确认的 ComfyUI 绑定关系：
  - 四方连续 -> `executor_comfyui_seamless_117`
  - 花纹扩图 -> `executor_comfyui_seamless_117`
  - 印花提取 -> `executor_comfyui_pattern_extract_158`
  - 多图融合 -> `executor_comfyui_pattern_extract_158`

## 14. 口语化项目说明（方便复述）

如果要用一句话介绍这个项目，可以这样说：

“这是一个 AI 能力中台，后端统一接各种模型和 ComfyUI，管理端负责配节点、配能力、做测试和运维，评测端负责跑工作流评测和批量回归；当前真正跑得最稳的是统一能力调用、异步任务、OSS 落盘、Coze 插件和评测主链，认证扩展、钱包商业化、通用工作流平台还在继续补。”

如果要分 3 层讲，可以这样说：

1. **底层是能力接入层**
   - 把 Baidu / Volcengine / KIE / ComfyUI / Coze 接成统一能力
   - 核心入口是 `/api/abilities` 和 `/api/ability-tasks`

2. **中间是治理与运维层**
   - 管理端维护执行节点、能力、工作流、绑定、API Key、ComfyUI 服务器和 Agent
   - 还能直接做能力测试、看调用日志、看错误和队列

3. **上层是评测与业务验证层**
   - 评测端主要不是给最终用户跑生产任务，而是给内部做 workflow 验证、打分、批量回归和结果标注

如果要提醒别人“哪里最容易误解”，可以补一句：

“仓库里还保留了一些历史任务中心和 mock 积分接口，所以看代码时一定要分清现行主链和兼容旧链，别在旧链路上继续叠逻辑。”

## 14.1 核心地图（一眼看懂版）

如果把这个项目画成最简单的地图，可以这样看：

### 第一层：能力来源
- 百度
- 火山
- KIE
- ComfyUI
- Coze
- PODI 自己的小工具

### 第二层：PODI 后端
- 统一接住上面的能力
- 统一做参数处理
- 统一写日志
- 统一做异步任务
- 统一把结果存到 OSS

### 第三层：两个前台
- 管理后台
  - 给管理员和运维用
  - 负责配置、测试、看日志、看节点状态
- 评测平台
  - 给内部验证效果用
  - 负责跑 workflow、打分、批量回归、结果标注

### 第四层：外部接入
- Coze 会把 PODI 当成一组工具来调用

一句话记忆：

“PODI 后端像个总调度台，左边接各种 AI 能力，右边接管理后台、评测平台和 Coze。”

## 14.2 术语翻译表（以后尽量都按这个说）

### 你会经常看到的英文名
- `ability`
  - 中文：能力 / 功能
  - 人话：一个具体 AI 功能，比如印花提取、文生图、去雾

- `invoke`
  - 中文：调用 / 执行
  - 人话：让系统真的去跑这个功能

- `ability task`
  - 中文：能力任务
  - 人话：那种不会立刻出结果、需要后台慢慢跑的任务

- `executor`
  - 中文：执行节点
  - 人话：真正干活的机器或接口入口

- `workflow`
  - 中文：工作流
  - 人话：一套处理流程，尤其常见于 ComfyUI 和 Coze

- `binding`
  - 中文：绑定关系 / 路由关系
  - 人话：告诉系统“哪个动作该走哪个工作流、再走哪台机器”

- `eval`
  - 中文：评测
  - 人话：内部测试效果、回归验证、人工打分

- `callback`
  - 中文：回调
  - 人话：任务跑完以后，系统反过来通知结果

- `ingest`
  - 中文：落盘 / 入库 / 接收沉淀
  - 人话：把外面的图片或结果统一收进自己的 OSS

## 14.3 如果以后排问题，先按这个思路找

### 1. 问题像“功能为什么跑不起来”
先看：
- 能力有没有
- 对应执行节点有没有
- 执行节点通不通
- 凭证有没有过期

### 2. 问题像“任务为什么一直没结果”
先看：
- 是同步功能还是异步任务
- 当前状态是排队、运行中、失败，还是只是结果没回填
- 对应日志有没有写明错误码

### 3. 问题像“后台为什么看到能力是空的”
先看：
- 表结构有没有迁移好
- seed 有没有真正写进数据库
- 不是只看代码里有没有默认定义

### 4. 问题像“评测平台为什么结果不对”
先看：
- 是 workflow 配置问题
- 是 Coze 返回问题
- 还是后端回调/轮询没有收口

### 5. 问题像“ComfyUI 为什么不出图”
先看：
- 工作流绑定是否正确
- 对应节点机器是否在线
- `/system_stats` 是否正常
- 是否命中了错误的测试型执行节点

## 15. 主要业务链路（人话版）

### A. “能力中心”这条线是怎么跑的

你可以把它理解成：

“有人想用一个 AI 功能，系统先找到这个功能，再决定让哪台机器或哪个第三方去执行，最后把结果统一存回来。”

具体步骤：

1. 前端或别的系统先问一句：
   - “你这里都有哪些 AI 功能可用？”
   - 对应接口就是 `GET /api/abilities`

2. 用户选中一个能力后发起调用：
   - 比如“印花提取”“四方连续”“KIE 图生图”
   - 对应接口是 `POST /api/abilities/{abilityId}/invoke`

3. 后端会做几件事：
   - 把默认参数和用户输入合并
   - 处理图片输入（链接、Base64、多张图）
   - 决定用哪个执行节点（哪台 ComfyUI、哪个厂商接口）
   - 先记一条调用日志

4. 然后后端真正去执行：
   - 百度能力 -> 调百度接口
   - 火山能力 -> 调火山接口
   - KIE 能力 -> 调 KIE 接口
   - ComfyUI 能力 -> 调 ComfyUI 工作流
   - Coze 能力 -> 调 Coze workflow

5. 拿到结果后：
   - 如果第三方给的是图片链接或 Base64，系统会先转存到自己的 OSS
   - 然后统一返回结果
   - 同时更新日志

一句话理解：

“`abilities` 就是功能目录，`invoke` 就是实际执行这个功能。”

### B. “能力任务”这条线是怎么跑的

这条线是给“执行比较慢的功能”用的。

你可以把它理解成：

“这个功能一下子跑不完，那系统先帮你建一个任务编号，你过一会儿再回来查。”

具体步骤：

1. 提交一个异步任务：
   - 接口：`POST /api/ability-tasks`
   - 返回的是一个任务 ID，不一定立刻有最终结果

2. 后台线程开始执行
   - 它会把这个任务放进内部队列
   - 如果是 ComfyUI、KIE 这类长任务，还会做排队数量控制，避免把节点打爆

3. 如果任务要跑很久：
   - 系统不会傻等
   - 会先把任务状态记成“排队中 / 运行中”
   - 后台再继续轮询结果

4. 跑完以后：
   - 更新任务状态
   - 回填结果
   - 记日志
   - 如果开启了费用结算，还会顺手记成本、扣积分

一句话理解：

“`ability-tasks` 就是长任务中心，用来处理不能秒回的 AI 功能。”

### C. “管理后台测试”这条线是怎么跑的

这个最适合你理解成：

“管理员在后台点一下，直接测某个能力能不能跑通。”

具体步骤：

1. 管理员在后台选一个能力
2. 填参数、上传图片、选执行节点
3. 后台调用对应测试接口，例如：
   - 百度测试
   - 火山测试
   - KIE 测试
   - ComfyUI 工作流测试
4. 后端直接去调真实上游
5. 把结果存到 OSS，再把结果和原始响应一起回给后台页面

一句话理解：

“`admin-tests` 不是假测试，而是直接打真实接口的联调入口。”

### D. “评测平台”这条线是怎么跑的

这条线不是“正式生产给客户下任务”，而是：

“内部拿来验证某个工作流效果好不好、稳定不稳定。”

具体步骤：

1. 先选一个工作流版本
2. 上传测试图片、填写参数
3. 提交一次评测运行
4. 后端去调用 Coze 工作流
5. 如果 Coze 返回的是一个长任务 ID，系统会继续轮询
6. 最后拿到结果图或结果数据
7. 评测人员再给分、写备注

一句话理解：

“`evals` 就是内部评测台，核心是验证 workflow，不是普通用户日常生产入口。”

### E. “Coze 接入”这条线是怎么跑的

你可以把它理解成：

“PODI 把自己包装成一组 Coze 可以调用的工具。”

具体步骤：

1. Coze 通过 `/api/coze/podi/openapi.json` 读取工具说明
2. Coze 工作流里调用某个工具
3. 后端把 Coze 传来的参数翻译成 PODI 自己的能力调用格式
4. 如果这是个快能力，就直接执行并返回
5. 如果这是个慢能力，就先创建异步任务
6. 后续 Coze 再通过 `/api/coze/podi/tasks/get` 查结果

一句话理解：

“Coze 看到的是工具箱，PODI 内部其实还是在调用自己的能力中心和任务中心。”

## 15.5 测试覆盖现状（目前看起来比较清楚）

### 已有较明确自动化覆盖的方向
- 能力状态与结果映射
- Coze 返回与字段兼容
- ComfyUI 输入与路由
- 评测批次状态、标注分页与契约
- 钱包 API
- Agent token

### 当前测试分布给人的感觉
- “状态/错误口径”这块重视程度比较高
- Coze / ComfyUI / eval 这些主链路都有一定测试
- 钱包测试目前数量不算多，但至少已经有基础 API 覆盖
- 更偏运维和现场联调的东西，还是要靠手工验证
- 从历史数据量看：
  - 项目不是空壳，已经实际跑过不少任务
  - 所以后面排问题时要有“兼容历史数据”的意识，不能只看新逻辑

## 15.6 凭证与敏感信息边界

### 我已经确认的点
- 仓库里有 `docs/CREDENTIALS.md`
- 这个文档按厂商分了章节：
  - 阿里云
  - 百度智能云
  - 火山引擎
  - KIE 中转
- 2026-04-30 校正：`docs/CREDENTIALS.md` 现在只作为去敏配置清单和轮换规则，不再作为“凭证登记册”；真实凭证应在服务器环境变量、中台 Key 池、受控密钥系统或本地忽略文件中维护。

### 我刻意没有直接展开的内容
- 我没有在笔记里抄任何具体密钥、密码、Token、AK/SK
- 后续如果继续做接手记录，也应保持这个习惯：
  - 只记“有没有配置”
  - 只记“配置的是哪一类”
  - 不把敏感值再次散落到别的笔记里

## 15.7 目前我认为“已经搞清楚”的事

- 这个项目的三层结构：能力中台 / 管理后台 / 评测平台
- 当前真正的主链路是什么
- 哪些接口是现行主链，哪些只是历史兼容
- 管理端和评测端都属于“超大单页应用”
- 数据库迁移已经到最新，核心种子数据已经在库里
- 钱包账号还没初始化
- 正式部署走 prod-like 静态代理，不建议把 dev server 当线上方案

## 15.8 目前仍然需要“现场验证”的事

这些不是靠读代码就能 100% 确认的，需要后面到真实环境里核：

- Coze 当前配置的 workflow 是否都还能正常跑
- 每台 ComfyUI 节点现在是否都能连通、插件是否齐
- 百度 / 火山 / KIE 的真实凭证是否仍有效
- OSS 上传、回填、外网访问是否正常
- 钱包初始化后，费用结算链路是否与现网口径一致
- Agent / 桌面端链路现在是否真的有人在用，还是只是已开发未常用
- 管理端和评测端页面里，有没有“代码写了但业务方其实不用”的区块
- `executor_mock_history_history_success_no_images_62359` 这种测试型节点要不要清理或下线

## 15.9 代码和文档里明确挂着的未完成项

这些不是我猜的，是仓库里已经明确写着“还没完”的内容：

### 平台能力层
- 能力定价 `metadata.pricing` 还需要继续补齐
- 自动健康巡检还没真正做完
- SLA / 最近一次成功 / 最近一次失败这类治理信息还没完全打通到后台
- 2026-04-30 校正：执行节点标签路由已经落地，`config/executors.yaml` 与调度器支持 `tags`、`required_tags`、`required_executor_tags`；剩余问题是核心能力的标签覆盖率和管理端提示还要继续补齐。

### ComfyUI 层
- 资源清单（模型、插件、版本、下载地址）还要继续补全
- 一键同步 / 一键修复还不完整
- 四方连续“中心留白”这个历史问题文档里仍然保留为重点风险

### 媒资与安全层
- `/api/media/v1/oss-callback` 还没有真正做完签名校验和落库
- OSS AssumeRole 安全策略还没完全收紧
- 凭证失效、轮换、权限最小化这块还有运维工作没做透

### 工作流 / 编排层
- 通用任务调度平台不是现行主链，很多还是规划
- 可视化工作流平台还在路线图里，没有真正成型

### 认证 / 计费层
- 登录现在只有账号密码主链
- 注册、邀请码、SSO、完整会话治理还没成型
- 钱包表和接口虽然已经不少，但“商用级计费闭环”还没完全稳定

## 15.10 接手后建议优先和你们确认的问题

这些问题不是代码能自己回答的，最好后面由你们来拍板：

### 业务侧
- 现在最重要的业务主线，到底是“管理后台接入能力”还是“评测平台跑 workflow”？
- 目前最常用、最不能挂的 3 个功能是什么？
- 哪些页面是业务同学天天用的，哪些只是留着备用？

### 技术侧
- 现在真正在线上长期使用的是哪几台执行节点？
- 那个本地测试型执行节点要不要清理？
- Agent / 桌面端链路是不是在真实使用？
- 钱包体系现在是准备正式启用，还是先保留技术预备状态？

### 运维侧
- 真实凭证在服务器环境变量、中台 Key 池、受控密钥系统或本地忽略文件里是否最新？
- Coze / 百度 / 火山 / KIE 的当前账号和权限有没有变动？
- 现在线上部署到底主要靠哪套脚本，团队有没有私下约定但没写进文档？

## 15.11 我目前的接手状态判断

如果按“了解程度”打分，我现在大概是：

- 对项目整体结构：已经比较清楚
- 对主链路：已经比较清楚
- 对前后端代码形态：已经比较清楚
- 对数据库与迁移关系：已经比较清楚
- 对真实线上使用习惯：还需要你们口头补充
- 对运维口径和业务优先级：还需要你们确认

换句话说：

“我现在已经能看懂这个项目、也能开始接手技术工作了；但要做到和你们完全默契，还需要补上‘你们实际怎么用、最在乎什么’这层信息。”

## 21. 带宽异常审查（第一轮）

你提到的现象是：

- 线上没人用
- 带宽却经常很高，甚至打满

这个我已经开始按“代码 + 部署方式 + 主链路”去审。

### 目前已经排查到的高风险点

#### 1. 异步任务后台回填线程
- 文件：`backend/app/services/ability_task_service.py`
- 现状：
  - 服务启动后会常驻两个后台线程
  - 其中一个每 **8 秒** 扫一次运行中的 ComfyUI / KIE 任务
- 判断：
  - 如果系统里真有“长期 running 的任务”或状态没收口的脏数据，就会持续对外轮询
  - 这类轮询是最像“没人操作但后台一直跑流量”的候选原因之一

#### 2. 评测后台的 Coze / 回调轮询
- 文件：`backend/app/services/eval_service.py`
- 现状：
  - 评测 run 会调用 Coze
  - 如果是回调型任务，还会继续轮询 AbilityTask 或 callback workflow
- 判断：
  - 如果评测 run 长期卡在 running，或者有批量评测没收口，也可能持续占用带宽

#### 3. 外部图片下载 -> OSS 落盘链路
- 文件：
  - `backend/app/services/media_ingest.py`
  - `backend/app/services/podi_image_tools.py`
  - `backend/app/services/integration_test.py`
- 现状：
  - 系统经常会先下载外部图片，再上传 OSS
  - 某些能力还会再次下载 OSS 图片做处理后重新上传
- 判断：
  - 如果有任务重复失败重试，或者外部图片很大，这块会非常吃带宽

#### 4. 前端轮询很勤
- 文件：
  - `podi-eval-web/src/App.tsx`
  - `podi-admin-web/src/pages/IntegrationDashboard.tsx`
- 现状：
  - 评测端和管理端都有定时轮询
  - 评测端里甚至有 **2 秒一次** 的轮询
- 判断：
  - 这会造成“有人开着页面不操作，也在持续打接口”
  - 但如果真的是“完全没人用”，那它不是第一嫌疑

#### 5. 部署方式如果用错，会放大流量问题
- 风险点：
  - 如果线上误跑 `npm run dev`
  - 或者前端不是静态产物 + 代理，而是 dev server
- 判断：
  - 虽然这不一定直接导致“带宽打满”
  - 但会让线上资源请求、HMR、调试链路变得更不可控

### 当前排除或暂时没那么像的

#### 1. 通知服务
- `backend/app/services/notify.py`
- 目前是内存版 WebSocket 广播
- 如果没人连，不会自己疯狂跑流量

#### 2. Agent 心跳
- `agent heartbeat` 默认会有定时上报
- 但从代码看数据量不大，更像“小而持续”，不像“直接打满带宽”

#### 3. Coze / 回归脚本 / 压测脚本
- 仓库里有很多 smoke / regression / load test 脚本
- 它们本身是高风险流量源
- 但更像“有人在后台跑脚本”而不是服务天然就会自己跑

### 第二轮补充判断

#### 更像“空闲时也会持续吃带宽”的点
- `AbilityTaskService` 的后台回填线程
  - 每 8 秒扫一次
  - 只要库里还有 `running` 的 ComfyUI / KIE 任务，就会持续打外部接口
- `EvalService` 的评测轮询
  - 会持续轮询 Coze history、callback workflow、AbilityTask
  - 如果某批评测 run 没收口，也会一直跑
- 评测前端的高频轮询
  - `tool` 视图：2 秒一次，只要有 `queued/running`
  - `tasks` 视图：固定 2 秒一次
  - LoRA 批量页：10 秒 / 20 秒轮询批次与明细

#### 不太像“完全没人用也能打满”的点
- 管理端能力日志自动刷新
  - 10 秒 / 12 秒一次，但只在特定页面开着时触发
- 通知 WebSocket
  - 没有连接就不会自己刷
- 静态资源服务本身
  - `node_static_proxy.mjs` 给 `assets/*` 做了长缓存
  - 如果按推荐的 prod-like 静态部署，静态文件本身不太像元凶

#### 我现在最怀疑的组合
- “数据库里有没收口的 running 任务” + “后台 8 秒轮询回填”
- “评测批次或 callback 任务没收口” + “评测服务继续轮询”
- “线上有人长期开着评测页/任务页” + “前端 2 秒轮询”
- “有人在跑 smoke / regression 脚本” + “大图下载 / 回填 / 再上传”

### 这轮实际排查到的数据库现状
- `ability_tasks`
  - 当前状态分布：
    - `succeeded=6960`
    - `failed=306`
  - **没有** `queued/running` 的活跃任务
- `eval_runs`
  - 当前状态分布：
    - `succeeded=4305`
    - `failed=38`
  - **没有** `queued/running` 的活跃评测运行
- `eval_batches`
  - 当前状态分布：
    - `succeeded=3`
    - `failed=5`
  - **没有** 长时间 active 的批次

### 这意味着什么
- 至少在我这次排查的时点上：
  - 不是“数据库里堆了大量 running 任务没收口”这种明显情况
  - 也不是“评测批次一直挂着没结束”这种明显情况
- 所以如果线上真的出现“空闲时带宽打满”：
  - 要么是问题具有时段性
  - 要么是脚本/页面/外部回调在某些时刻把流量拉高
  - 要么是有少量任务反复重试，但不会长期体现在 `running` 状态里

### 这轮发现的一个小异常
- 最近 24 小时里有 1 条 `KIE` 的 `pending` 能力日志
- 但没有查到对应的 `ability_task`
- 这更像是：
  - 日志状态没有收口
  - 或某次任务在日志层残留了 pending stub
- 它本身不太像“带宽打满”的主因，但说明日志收口仍有边角问题

### 对带宽问题的当前结论

如果线上“完全没人操作”但带宽还是长期满：

- 我第一优先怀疑后端后台轮询没收口
- 第二优先怀疑评测批次 / callback 链路
- 第三优先怀疑有人在后台跑脚本

如果线上“有人开着页面但没在点”时带宽高：

- 我会优先怀疑评测端 2 秒轮询和批量页轮询

### 我目前的判断

如果线上真出现“没人用但带宽持续很高”，我现在最怀疑的是这几类：

1. **有运行中任务没有真正收口，后台一直在轮询**
2. **有评测批次 / Coze callback / ComfyUI history 在后台持续补偿**
3. **有脚本或守护进程在定时打接口**
4. **有页面长期打开，前端轮询频率过高**
5. **某些图片下载/转存链路在失败重试时反复拉大文件**

### 接下来建议优先怎么查

#### P0：线上立刻查
- 看后端进程数和启动命令
- 看有没有 smoke / regression / load test 脚本在跑
- 看有没有大量 `running` 的 `ability_tasks` / `eval_run`
- 看日志里是不是在反复出现：
  - Coze history 轮询
  - ComfyUI `/history`
  - KIE 状态查询
  - 远程图片下载

#### P1：代码层尽快补
- 给后台轮询加更清楚的日志与计数
- 给长期 running 任务加更严格的收口策略
- 给大图片下载/重试链路加流量保护和限次
- 把前端高频轮询再收敛

### 当前结论

我现在还不能负责任地说“就是哪一行代码导致线上带宽打满”，
但我已经把最像的几个方向缩小到：

- 后台轮询没收口
- 批量评测/回调补偿没收口
- 图片下载/回填重试过多
- 线上存在脚本型流量

后面我会把这个作为正式接手后的重点审查项，而不是只盯功能开发。

## 16. 继续熟悉项目时的优先阅读顺序

1. `backend/app/main.py`
2. `backend/app/routers/abilities.py`
3. `backend/app/services/ability_invocation.py`
4. `backend/app/services/ability_task_service.py`
5. `backend/app/routers/admin_integrations.py`
6. `backend/app/routers/admin_abilities.py`
7. `backend/app/routers/evals_public.py`
8. `backend/app/services/eval_service.py`
9. `podi-admin-web/src/pages/IntegrationDashboard.tsx`
10. `podi-eval-web/src/App.tsx`

## 17. 推荐接手顺序

1. 先守住现有主链路：能力调用、异步任务、日志、OSS、管理端测试
2. 再清理状态/错误/回填口径，确保“可解释、可排障”
3. 然后补能力治理：pricing、health check、SLA、自检看板
4. 最后再动认证/计费/工作流平台等更大范围改造

## 18. 下一步建议

- 先做一次“环境真值检查”：把 `.env`、执行节点、数据库迁移、前端端口、上游可达性全部核对一遍
- 再做一次“主链路冒烟”：登录 -> 调一个能力 -> 查日志 -> 查 OSS 结果 -> 查异步任务
- 最后整理一份“现网/本地配置差异表”，避免后续排障时把环境问题误判成代码问题

## 20. 接手后的优先修复 / 确认清单

### P0：先确认和先修的

1. **修复异步能力任务 + service token 的外键错误**
- 现象：`POST /api/ability-tasks` 用 `SERVICE_API_TOKEN` 调用时报 500
- 根因：虚拟用户 `service` 不在 `users` 表，却被写进 `ability_tasks.user_id`
- 优先级最高，因为这会直接影响服务间异步调用

2. **初始化钱包账号**
- 当前 `wallet_accounts=0`
- 但库里已有 2 个用户
- 至少先跑 dry-run -> apply，把基础账号补齐

3. **确认并处理测试遗留执行节点**
- `executor_mock_history_history_success_no_images_62359`
- 先确认它是不是故意保留的
- 如果不是，应该标记/清理，避免后续误路由

### P1：接手后尽快核实的

4. **确认线上最关键的 3 个能力**
- 哪 3 个功能最常用、最不能挂
- 后续排障和回归先围绕它们做

5. **确认 ComfyUI / Coze / KIE / 火山 / 百度 的真实使用口径**
- 哪些节点常用
- 哪些 workflow 还在用
- 哪些只是历史遗留

6. **确认 Agent / 桌面端链路是不是活跃使用中**
- 如果只是预备功能，接手优先级可以后移
- 如果真在用，就要尽快把契约、告警、部署口径补齐

### P2：接手稳定后推进的

7. **补自动健康巡检**
- 能力最近一次成功/失败时间
- 自检结果看板

8. **补能力治理信息**
- pricing
- SLA
- success rate
- 最近自检状态

9. **继续清理历史文档和历史链路口径**
- 特别是 `/api/tasks/v1/*`、旧 points/mock、规划文档与现状的混淆

## 19. 接手前两天建议怎么推进

### 第一天：先把“项目能不能跑”搞清楚
- 看 `backend/.env` 有没有
- 确认数据库迁移是不是最新
- 确认执行节点、能力、工作流、绑定有没有默认数据
- 确认管理端和评测端都能起
- 确认上游（Coze / ComfyUI / KIE / 百度 / 火山）至少配置上了

### 第二天：再把“项目到底怎么跑”搞清楚
- 跟着主链路走一遍：
  - 登录
  - 查能力列表
  - 跑一个能力
  - 跑一个长任务
  - 看日志
  - 看 OSS 结果
  - 看后台测试
  - 看评测平台 run
- 把你自己心里这几个问题答清楚：
  - 哪条链是现行主链？
  - 哪条链只是历史兼容？
  - 哪些模块已经真实可用？
  - 哪些模块只是“有接口/有文档/有壳子”？
