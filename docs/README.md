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
   - 客户端：`docs/client/README.md`
   - 评测端：`docs/eval/eval-platform.md`
   - Coze：`docs/coze/toolbox-inventory.md`
   - ComfyUI：`docs/comfyui/README.md`
8. 想回看阶段过程，再看：`docs/weekly/README.md`

## 现行真源

以下文档优先级最高，视为当前平台口径：

- `docs/PLATFORM_SURFACES.md`
- `docs/strategy/platform-vision-and-goals-2026.md`
- `docs/strategy/strategy-one-page-2026q2.md`
- `docs/strategy/coze-mid-platform-migration-v1.md`
- `docs/strategy/coze-control-plane-migration-pack-v1.md`
- `docs/strategy/coze-migration-config-matrix-v1.md`
- `docs/strategy/coze-host-cutover-sequence-v1.md`
- `docs/strategy/coze-migration-inventory-v1.md`
- `docs/strategy/coze-host-reference-phasing-v1.md`
- `docs/strategy/coze-desktop-centerurl-cutover-v1.md`
- `docs/strategy/coze-server-layout-v1.md`
- `docs/strategy/image-ops-service-split-v1.md`
- `docs/architecture.md`
- `docs/BUSINESS_MODEL.md`
- `docs/api/INDEX.md`
- `docs/client/README.md`
- `docs/client/plans/README.md`
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
| 客户端 | `docs/client/README.md` | 客户端唯一入口 |
| 客户端 Plans | `docs/client/plans/README.md` | 客户端现行计划 / 历史计划 / 测试包分层入口 |
| 评测端 | `docs/eval/eval-platform.md` | 评测平台功能与约束 |
| Coze 工具箱 | `docs/coze/toolbox-inventory.md` | 当前工具箱清单与契约 |
| ComfyUI | `docs/comfyui/README.md` | Workflow、节点映射、执行节点说明 |
| 周报归档 | `docs/weekly/README.md` | 按周汇总过程记录与阶段结论 |
| 工程规范 | `docs/standards/` | 错误契约、接口一致性、文档维护等规范 |
| 测试计划 | `docs/testing/README.md` | 回归计划、线上 smoke 清单、迁移 runbook |
| 复盘记录 | `docs/retrospectives/` | 复盘、风险、后续动作 |

## 历史资料与阶段记录

以下内容保留，但不作为当前执行口径：

- `docs/client/plans/2026-03-16-*`
- `docs/client/plans/2026-03-17-*`
- `docs/client/START_HERE.md`
- `docs/client/OPEN_TEST_NOW.md`
- `docs/client/REVIEW_NOW.md`
- `docs/async-task-monitoring.md`
- `docs/smart-polling-mechanism.md`
- `docs/error-codes.md`
- `docs/TODO_PLATFORM.md`

阅读这些文档时，默认按“历史基线 / 阶段记录”理解，不能直接当作当前实现依据。

## 模块目录说明

| 目录 | 作用 |
| --- | --- |
| `docs/api/` | 接口模块说明与契约 |
| `docs/client/` | 客户端现状、计划、阶段文档 |
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
