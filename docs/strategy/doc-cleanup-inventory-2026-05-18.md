# 文档清理台账（2026-05-18）

目的：把当前有效文档、历史资料和阶段记录分开，减少开发和上线时被过期信息误导。

## 1. 清理原则

1. 不优先物理删除历史文档，先通过总索引降噪、明确“历史身份”来降低误读风险。
2. 当前执行只认 `docs/README.md`、`docs/strategy/README.md` 和 `docs/strategy/todo-master-2026q2.md` 三个入口。
3. 旧迁移方案、旧客户端资料、旧临时交接材料保留追溯价值，但不能作为当前开发依据。
4. 每次新增方案都必须同步唯一 TODO，否则视为未进入执行。
5. 每次改接口、参数、状态词、错误码，都必须同步接口文档、错误码总表和测评/管理端展示。

## 2. 当前真源

这些文档仍作为当前执行依据：

| 类型 | 文档 | 说明 |
| --- | --- | --- |
| 总入口 | `docs/README.md` | 当前有效文档总索引 |
| 战略入口 | `docs/strategy/README.md` | 平台级方向、方案和治理入口 |
| 唯一 TODO | `docs/strategy/todo-master-2026q2.md` | 当前任务池 |
| v0.2 方案 | `docs/strategy/business-control-plane-v0.2-plan.md` | 下一版本执行方案 |
| 业务主线 | `docs/standards/business-mainline-contract.md` | `runId`、版本、步骤、回填、计费口径 |
| 版本规则 | `docs/standards/version-control-rules.md` | 版本升级、新功能、回滚规则 |
| 发布 SOP | `docs/standards/release-sop.md` | 114 控制面发布与验证 |
| 逐功能检查 | `docs/standards/per-feature-release-checklist.md` | 功能上线前检查 |
| 接口索引 | `docs/api/INDEX.md` | API 模块入口 |
| 错误契约 | `docs/standards/error-contract.md` | 错误返回规范 |
| 错误码总表 | `docs/standards/error-catalog.md` | 错误码清单 |
| 接口一致性 | `docs/standards/interface-consistency.md` | 状态词、返回体和兼容口径 |

## 3. 阶段记录

这些文档保留为阶段记录，读取时必须结合当前真源判断：

| 文档 | 当前处理 |
| --- | --- |
| `docs/strategy/business-orchestration-control-plane-v1.md` | 作为 v0.2 的上层背景，不再直接当执行清单 |
| `docs/strategy/mid-platform-gap-and-roadmap-2026-05-07.md` | 保留为差距分析背景 |
| `docs/strategy/mid-platform-detailed-execution-plan-2026-05-07.md` | 保留为已拆解过的历史执行清单 |
| `docs/strategy/core-business-chain-review-2026-05-03.md` | 保留为三条核心业务链路体检记录 |
| `docs/strategy/coze-*.md` | 保留为 Coze 迁移过程文档，当前执行优先看 Coze 工具箱清单和发布 SOP |
| `docs/strategy/image-ops-service-split-v1.md` | 保留为 image-ops 拆分背景 |
| `docs/strategy/remote-image-ops-158-plan-v1.md` | 保留为 158 执行面部署背景 |

## 4. 历史资料

这些资料不代表当前主线：

| 文档或目录 | 当前处理 |
| --- | --- |
| `docs/client/` | 历史客户端资料，当前仓库已无客户端代码 |
| `docs/handover/` | 历史交接资料，仅作追溯 |
| `docs/archive/` | 已归档资料，不参与当前开发判断 |
| `docs/wip/` | 草稿区，未进入 TODO 前不作为执行依据 |
| `docs/weekly/` | 周报和阶段过程记录，不作为接口或版本真源 |

## 5. 本轮已清理动作

| 动作 | 结果 |
| --- | --- |
| 更新总索引当前基线 | 从 2026-05-16 / `904f9a2a` 调整到 2026-05-18 / `0f977db5` |
| 新增 v0.2 方案入口 | `business-control-plane-v0.2-plan.md` 成为下一版本执行方案 |
| 更新战略索引 | v0.2 方案置于战略文档清单前列 |
| 更新唯一 TODO 当前焦点 | 当前执行单切换到 v0.2 业务控制面收敛版 |
| 历史执行单降级 | 2026-05-14 稳定化执行单保留为历史记录 |

## 6. 后续可继续清理

暂不在本轮直接删除以下内容，后续确认无引用后再处理：

1. `docs/strategy/coze-*.md` 中的迁移过程文档，可汇总成一个 Coze 阶段归档索引。
2. `docs/client/` 下早期测试入口文档，可继续保留但不要出现在总索引阅读顺序里。
3. `docs/wip/` 中未进入 TODO 的草案，可按月整理到 archive 或删除。
4. 旧发布记录和旧巡检报告保留审计价值，不做物理删除。

## 7. 判断规则

遇到文档冲突时，按以下优先级判断：

1. `docs/standards/*` 中的当前规范。
2. `docs/strategy/todo-master-2026q2.md` 的当前执行单。
3. 具体模块入口文档。
4. 阶段记录。
5. 历史资料和归档资料。

