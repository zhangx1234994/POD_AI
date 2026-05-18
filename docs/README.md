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
6. `docs/standards/business-mainline-contract.md`
7. `docs/strategy/business-orchestration-workbench-v0.3-plan.md`
8. `docs/strategy/business-control-plane-v0.2-plan.md`
9. `docs/standards/version-control-rules.md`
10. `docs/strategy/todo-master-2026q2.md`
11. `docs/api/INDEX.md`
12. 对应模块文档：
   - 评测端：`docs/eval/eval-platform.md`
   - Coze：`docs/coze/toolbox-inventory.md`
   - ComfyUI：`docs/comfyui/README.md`
   - 第三方模型 Key：`docs/admin/integration-dashboard.md`
13. 每日早检：`docs/standards/morning-ops-check.md`
14. 样本包导出：`docs/standards/business-sample-pack-export.md`
15. 逐功能上线检查：`docs/standards/per-feature-release-checklist.md`
16. 清理治理：`docs/standards/cleanup-governance.md`
17. 发布与上线：`docs/standards/release-sop.md`
18. 需要回看阶段过程，再看：`docs/weekly/README.md`
19. 需要回看历史客户端资料时，再看：`docs/client/README.md`

## 当前运行基线（2026-05-19）

- 当前线上稳定基线为 `v0.1.x`，已验证生产提交 `0f977db5`。
- `origin/main` 是唯一发版真源；后续版本按 `docs/standards/version-control-rules.md` 管理。
- Coze、backend、管理端、测评端已收口到 Coze 主机：`114.55.0.56`。
- Coze 工具箱统一指向 backend，不再以 `117.50.80.158:8099` 作为现行工具箱入口。
- `117.50.80.158` 与 `117.50.216.233` 当前作为 ComfyUI / image-ops / vendor-api-ops 等执行面，不承载中台控制面。
- backend 是控制面，只负责业务入口、能力目录、路由、任务、回调、OSS、日志、OpenAPI 和版本证据；不承载高清放大、ComfyUI 或第三方 API 重执行。
- 当前仓库不包含客户端代码目录；`docs/client/` 只作为历史客户端资料入口，不再代表当前开发主线。
- 业务主线已固定：一次业务调用以 `runId` 为主线，VL、ComfyUI、OpenAI、评分、回填、回调、计费都归入这次业务调用下的处理步骤或证据；标准见 `docs/standards/business-mainline-contract.md`。
- v0.2 业务控制面收敛版已完成本地开发和验证，保留为已完成阶段记录。
- 下一阶段目标是 v0.3 业务编排工作台与控制点去重版：减少业务链条里的重复控制单元，把业务组件、草稿编排、版本发布、runId 排障和上线门禁串成一个可维护工作台；规划见 `docs/strategy/business-orchestration-workbench-v0.3-plan.md`。
- 114 控制面发布统一走 `docs/standards/release-sop.md` 和 `scripts/release_114_control_plane.sh`，不再临时手工拼 tar/ssh/restart。
- 发版前必须执行逐功能上线检查、ComfyUI 队列验证、业务接口回归和线上 smoke；标准见 `docs/standards/per-feature-release-checklist.md`。
- 旧迁移方案、旧客户端资料和阶段过程文档不再作为当前执行入口；清理台账见 `docs/strategy/doc-cleanup-inventory-2026-05-18.md`。

## 现行真源

以下文档优先级最高，视为当前平台口径：

- `docs/PLATFORM_SURFACES.md`
- `docs/strategy/platform-vision-and-goals-2026.md`
- `docs/strategy/strategy-one-page-2026q2.md`
- `docs/strategy/todo-master-2026q2.md`
- `docs/strategy/business-orchestration-workbench-v0.3-plan.md`
- `docs/strategy/business-control-plane-v0.2-plan.md`
- `docs/strategy/doc-cleanup-inventory-2026-05-18.md`
- `docs/architecture.md`
- `docs/BUSINESS_MODEL.md`
- `docs/api/INDEX.md`
- `docs/standards/business-mainline-contract.md`
- `docs/standards/version-control-rules.md`
- `docs/standards/per-feature-release-checklist.md`
- `docs/admin/integration-dashboard.md`
- `docs/eval/eval-platform.md`
- `docs/coze/toolbox-inventory.md`
- `docs/comfyui/README.md`
- `docs/standards/error-catalog.md`
- `docs/standards/error-contract.md`
- `docs/standards/interface-consistency.md`
- `docs/standards/business-interface-taxonomy.md`
- `docs/standards/delivery-methodology.md`
- `docs/standards/document-maintenance.md`
- `docs/standards/morning-ops-check.md`
- `docs/standards/business-sample-pack-export.md`
- `docs/standards/cleanup-governance.md`
- `docs/standards/release-sop.md`
- `docs/testing/ABILITY_TEST_LEDGER.md`
- `docs/releases/retrospectives/2026-05-18-business-control-plane-retrospective.md`
- `docs/releases/CHANGELOG.md`

以下文档降级为阶段记录，不再放入“当前真源”列表：Coze 迁移过程文档、旧客户端资料、旧中台差距分析、旧临时执行清单。需要追溯时从 `docs/strategy/doc-cleanup-inventory-2026-05-18.md` 进入。

## 模块入口

| 主题 | 入口文档 | 说明 |
| --- | --- | --- |
| 平台边界 | `docs/PLATFORM_SURFACES.md` | 管理端 / 测评端 / 客户端 / 对话式助手边界 |
| 战略规划 | `docs/strategy/README.md` | 平台愿景、路线、待办、治理 |
| v0.3 版本方案 | `docs/strategy/business-orchestration-workbench-v0.3-plan.md` | 业务编排工作台、控制点去重、组件目录、草稿发布和 runId 父子步骤 |
| v0.2 阶段方案 | `docs/strategy/business-control-plane-v0.2-plan.md` | 已完成的业务控制面收敛、版本族、接口调用中心、上线门禁和文档降噪 |
| 核心业务链路 | `docs/strategy/core-business-chain-review-2026-05-03.md` | 花纹提取 / 图裂变 / 扩图的入口、路由、回填、测试和后续优先级 |
| 业务主线契约 | `docs/standards/business-mainline-contract.md` | 固定业务入口、runId、业务版本、处理步骤、回填、回调、计费和页面动线 |
| API | `docs/api/INDEX.md` | 全量接口模块入口 |
| 图裂变交付契约图 | `docs/api/examples/fission-delivery-contract-2026-05-12.md` | 两个裂变接口和裂变评分的排队轮询、类图关系、参数聚合规则 |
| 图裂变业务交付包模板 | `docs/api/examples/fission-business-delivery/README.md` | 给业务方交付的三个接口独立文档和 JSON 样例，不包含真实 Key |
| 业务接口分类 | `docs/standards/business-interface-taxonomy.md` | 业务分类、Coze/原生/原子能力/测评入口的统一归属 |
| 历史客户端资料 | `docs/client/README.md` | 当前仓库已无客户端代码，仅保留历史方案和测试包 |
| 管理端 | `docs/admin/integration-dashboard.md` | 执行节点、能力、第三方模型 Key、测试与日志 |
| 评测端 | `docs/eval/eval-platform.md` | 评测平台功能与约束 |
| Coze 工具箱 | `docs/coze/toolbox-inventory.md` | 当前工具箱清单与契约 |
| Coze 切换清单 | `docs/coze/current-routing-and-toolbox-cutover-inventory-2026-04-24.md` | 当前能力路由、executor、OpenAPI 可导入状态与切换顺序 |
| ComfyUI | `docs/comfyui/README.md` | Workflow、节点映射、执行节点说明 |
| 周报归档 | `docs/weekly/README.md` | 按周汇总过程记录与阶段结论 |
| 工程规范 | `docs/standards/` | 错误契约、接口一致性、文档维护等规范 |
| 交付方法论 | `docs/standards/delivery-methodology.md` | 业务理解、接口契约、测评闭环、发布与文档沉淀的统一执行方法 |
| 测试计划 | `docs/testing/README.md` | 回归计划、线上 smoke 清单、迁移 runbook |
| 能力测试台账 | `docs/testing/ABILITY_TEST_LEDGER.md` | 每个功能族的必测用例、必查链路和上线闸门 |
| 复盘记录 | `docs/retrospectives/` | 复盘、风险、后续动作 |
| 历史归档 | `docs/archive/README.md` | 已退出主入口的旧部署、旧 Coze、旧任务与旧错误文档 |
| 文档清理台账 | `docs/strategy/doc-cleanup-inventory-2026-05-18.md` | 当前真源、阶段记录、历史资料和后续清理顺序 |
| 事故复盘 | `docs/retrospectives/2026-04-27-coze-toolbox-internal-only-incident.md` | Coze 工具箱不可用事故、巡检与并发整改项 |
| 每日早检 SOP | `docs/standards/morning-ops-check.md` | 每天开发前先查前一天业务、能力、测评和 API Key 异常，并导出标准数据包 |
| 业务样本包导出 | `docs/standards/business-sample-pack-export.md` | 按业务版本、时间窗口和执行节点导出原图、结果图、VL 内容和过程信息 |
| 逐功能上线检查 | `docs/standards/per-feature-release-checklist.md` | 每个功能上线前逐项检查接口、参数、节点、回填、页面和错误展示 |
| 清理治理 | `docs/standards/cleanup-governance.md` | 项目文件、数据库和 OSS 清理的审计脚本、删除边界和保留策略 |
| 发布 SOP | `docs/standards/release-sop.md` | 114 控制面唯一发布入口、脚本参数、验证、回滚和记录 |
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
- `docs/archive/README.md`
- `docs/archive/202605/README.md`

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
| `docs/archive/` | 已归档历史文档，只用于追溯，不作为当前执行口径 |

## 文档维护规则

文档治理统一按 `docs/standards/document-maintenance.md` 执行。最低要求：

1. 新增功能时，必须同步更新对应模块入口文档。
2. 参数、状态词、错误码变更时，必须同步更新接口文档和规范文档。
3. 历史文档保留可以，但必须在入口文档里明确其“历史”身份。
4. 模块入口文档要尽量短，只负责“带路”和“定口径”，不要堆长篇过程记录。
5. 周期性整理时，优先修总索引、模块索引和真源文档，再处理深层细节文档。
