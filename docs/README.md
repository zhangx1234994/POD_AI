# POD AI Studio 文档索引

本文件是项目文档的总入口。目标只有两个：

1. 让人快速找到**当前有效文档**
2. 明确区分**现行真源**、**模块说明**、**历史资料**

## 阅读顺序

新同学或恢复开发时，建议按这个顺序阅读：

1. `docs/PLATFORM_SURFACES.md`
2. `docs/strategy/platform-vision-and-goals-2026.md`
3. `docs/strategy/strategy-one-page-2026q2.md`
4. `docs/architecture.md`
5. `docs/BUSINESS_MODEL.md`
6. `docs/api/INDEX.md`
7. 对应模块文档：
   - 评测端：`docs/eval/eval-platform.md`
   - Coze：`docs/coze/toolbox-inventory.md`
   - ComfyUI：`docs/comfyui/README.md`
   - 第三方模型 Key：`docs/admin/integration-dashboard.md`
8. 想回看阶段过程，再看：`docs/weekly/README.md`
9. 需要回看历史客户端资料时，再看：`docs/client/README.md`

## 当前运行基线（2026-04-27）

- Coze、backend、管理端、测评端已收口到 Coze 主机：`114.55.0.56`。
- Coze 工具箱统一指向 backend，不再以 `117.50.80.158:8099` 作为现行工具箱入口。
- `117.50.80.158` 当前作为能力执行服务器使用，承载 image-ops 与 vendor-api-ops 等执行面；旧 backend 不再作为 Coze 工具箱主入口。
- backend 是控制面，只负责能力目录、路由、任务、回调、OSS、日志与 OpenAPI；不承载高清放大、ComfyUI 或第三方 API 重执行。
- 当前仓库不包含客户端代码目录；`docs/client/` 只作为历史客户端资料入口，不再代表当前开发主线。
- 2026-04-27 发生 Coze 工具箱 `INTERNAL_ONLY` 事故，已记录复盘：`docs/retrospectives/2026-04-27-coze-toolbox-internal-only-incident.md`。
- 更新服务后先在 114/Coze 主机内执行 `backend/scripts/podi_release_smoke.py`，确认工具箱入口、内部任务查询和 ComfyUI 队列都可达。
- 发版后必须执行 `backend/scripts/patrol_eval_workflows.py` 做全量测评巡检。
- ComfyUI 单机 10、双机 20 不能只看配置，必须通过 `backend/scripts/comfyui_capacity_probe.py` 验证实际队列喂入和任务分布。

## 现行真源

以下文档优先级最高，视为当前平台口径：

- `docs/PLATFORM_SURFACES.md`
- `docs/strategy/platform-vision-and-goals-2026.md`
- `docs/strategy/strategy-one-page-2026q2.md`
- `docs/strategy/coze-mid-platform-migration-v1.md`
- `docs/strategy/coze-control-plane-migration-pack-v1.md`
- `docs/strategy/coze-migration-status-summary-2026-04-24.md`
- `docs/strategy/coze-migration-config-matrix-v1.md`
- `docs/strategy/coze-host-cutover-sequence-v1.md`
- `docs/strategy/coze-migration-inventory-v1.md`
- `docs/strategy/coze-host-reference-phasing-v1.md`
- `docs/strategy/coze-desktop-centerurl-cutover-v1.md`
- `docs/strategy/coze-server-layout-v1.md`
- `docs/strategy/image-ops-service-split-v1.md`
- `docs/strategy/remote-image-ops-158-plan-v1.md`
- `docs/architecture.md`
- `docs/BUSINESS_MODEL.md`
- `docs/api/INDEX.md`
- `docs/admin/integration-dashboard.md`
- `docs/eval/eval-platform.md`
- `docs/coze/toolbox-inventory.md`
- `docs/comfyui/README.md`
- `docs/weekly/README.md`
- `docs/standards/error-catalog.md`
- `docs/standards/error-contract.md`
- `docs/standards/interface-consistency.md`
- `docs/standards/ability-presentation-layer.md`
- `docs/standards/eval-workflow-presentation-layer.md`
- `docs/standards/eval-workflow-usage-layer.md`
- `docs/standards/document-maintenance.md`

## 模块入口

| 主题 | 入口文档 | 说明 |
| --- | --- | --- |
| 平台边界 | `docs/PLATFORM_SURFACES.md` | 管理端 / 测评端 / 客户端 / 对话式助手边界 |
| 战略规划 | `docs/strategy/README.md` | 平台愿景、路线、待办、治理 |
| API | `docs/api/INDEX.md` | 全量接口模块入口 |
| 历史客户端资料 | `docs/client/README.md` | 当前仓库已无客户端代码，仅保留历史方案和测试包 |
| 管理端 | `docs/admin/integration-dashboard.md` | 执行节点、能力、第三方模型 Key、测试与日志 |
| 评测端 | `docs/eval/eval-platform.md` | 评测平台功能与约束 |
| Coze 工具箱 | `docs/coze/toolbox-inventory.md` | 当前工具箱清单与契约 |
| Coze 切换清单 | `docs/coze/current-routing-and-toolbox-cutover-inventory-2026-04-24.md` | 当前能力路由、executor、OpenAPI 可导入状态与切换顺序 |
| ComfyUI | `docs/comfyui/README.md` | Workflow、节点映射、执行节点说明 |
| 周报归档 | `docs/weekly/README.md` | 按周汇总过程记录与阶段结论 |
| 工程规范 | `docs/standards/` | 错误契约、接口一致性、文档维护等规范 |
| 测试计划 | `docs/testing/README.md` | 回归计划、线上 smoke 清单、迁移 runbook |
| 复盘记录 | `docs/retrospectives/` | 复盘、风险、后续动作 |
| 事故复盘 | `docs/retrospectives/2026-04-27-coze-toolbox-internal-only-incident.md` | Coze 工具箱不可用事故、巡检与并发整改项 |
| 发布门禁 | `docs/release-preflight.md` | 发版前必须执行的业务链路巡检、ComfyUI 队列验证和构建测试 |

## 历史资料与阶段记录

以下内容保留，但不作为当前执行口径：

- `docs/client/README.md`
- `docs/client/plans/README.md`
- `docs/client/tech-review-2026-04-16/*`
- `docs/client/plans/2026-03-16-*`
- `docs/client/plans/2026-03-17-*`
- `docs/client/START_HERE.md`
- `docs/client/OPEN_TEST_NOW.md`
- `docs/client/REVIEW_NOW.md`
- `docs/handover/README.md`
- `docs/async-task-monitoring.md`
- `docs/smart-polling-mechanism.md`
- `docs/error-codes.md`
- `docs/TODO_PLATFORM.md`
- `docs/COZE_INTEGRATION_GUIDE.md`

阅读这些文档时，默认按“历史基线 / 阶段记录”理解，不能直接当作当前实现依据。

## 模块目录说明

| 目录 | 作用 |
| --- | --- |
| `docs/api/` | 接口模块说明与契约 |
| `docs/client/` | 客户端历史方案、计划与阶段测试包 |
| `docs/handover/` | 历史交接、阶段评审与修复计划 |
| `docs/plans/` | 平台级方案与跨模块计划文档 |
| `docs/comfyui/` | ComfyUI workflow 与执行节点维护 |
| `docs/coze/` | Coze 工具箱、工作流、插件契约 |
| `docs/eval/` | 评测端说明 |
| `docs/strategy/` | 战略、待办、治理 |
| `docs/standards/` | 工程和文档规范 |
| `docs/testing/` | 测试计划与回归清单 |
| `docs/retrospectives/` | 复盘记录 |
| `docs/weekly/` | 周报归档与阶段过程汇总 |
| `docs/wip/` | 草案与未定稿内容 |

## 文档维护规则

文档治理统一按 `docs/standards/document-maintenance.md` 执行。最低要求：

1. 新增功能时，必须同步更新对应模块入口文档。
2. 参数、状态词、错误码变更时，必须同步更新接口文档和规范文档。
3. 历史文档保留可以，但必须在入口文档里明确其“历史”身份。
4. 模块入口文档要尽量短，只负责“带路”和“定口径”，不要堆长篇过程记录。
5. 周期性整理时，优先修总索引、模块索引和真源文档，再处理深层细节文档。
