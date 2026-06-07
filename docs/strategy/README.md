# 战略工作区

本目录只承载平台级方向、当前执行清单和治理规则。接口细节、模块说明、测试报告不放在这里展开。

## 当前必读

1. `todo-master-2026q2.md`
2. `v0.6-closure-standardization-plan.md`
3. `v0.6-closure-inventory-2026-06-07.md`
4. `v0.6.3-control-plane-hardening-plan.md`
5. `mid-platform-completeness-v0.6-plan.md`
6. `ability-governance-operating-model-v0.6.md`
7. `ability-definition-v0.6.md`
8. `ability-api-gap-v0.6.md`
9. `business-agent-runtime-v0.6.md`
10. `client-parallel-preview-v0.6-handoff.md`
11. `../standards/version-acceptance-template.md`
12. `../standards/agent-runtime-regression-matrix.md`
13. `../standards/eval-ability-interaction-state-model.md`
14. `project-half-year-review-2026-05-26.md`
15. `platform-polish-v0.5-decision-plan.md`
16. `output-quality-review-v0.5.md`

## 当前阶段

- 当前阶段：`v0.6 收口整改与标准化版`。
- 当前目标：补齐 v0.6 之前缺失的能力、样例、接口文档和错误契约，整改不合理交互和业务边界，梳理业务逻辑和处理机制，形成可继续迭代的标准底座。
- 当前重点：全量缺失盘点、业务处理机制标准化、交互治理、接口文档与错误契约补齐、能力缺口和样例质量补齐、全链路回归和收口复盘。
- 当前基线：`88d48dce` 完成 Agent 与控制面补充验收，`6ba720e3` 完成测评端能力首页收口并已上线；这些作为 v0.6 收口基础，不代表进入 v0.7。
- 当前 Agent 约束：对话式改图可暂时归在图编辑分类下，但长期归宿是 Agent Runtime；可视化/画布式图编辑和对话式 Agent 改图必须保持命名、交互、API 边界和能力定义拆分。
- 当前非目标：启动 v0.7 开发主线、低代码工作流编辑器、一次全自动端到端承诺、客户端直连原子能力、正式支付、全品类一次性覆盖、重型通用 Agent 平台、在本仓库实现新客户端。

## 阶段记录

这些文档保留为背景，不直接作为当前任务清单：

- `business-orchestration-workbench-v0.3-plan.md`
- `business-orchestration-workbench-v0.4-plan.md`
- `business-control-plane-v0.2-plan.md`
- `business-orchestration-control-plane-v1.md`
- `mid-platform-gap-and-roadmap-2026-05-07.md`
- `mid-platform-detailed-execution-plan-2026-05-07.md`
- `core-business-chain-review-2026-05-03.md`

## 迁移和历史方案

以下文档仅用于追溯当时决策：

- `coze-*.md`
- `image-ops-service-split-v1.md`
- `remote-image-ops-158-plan-v1.md`

当前执行优先看：

- `docs/README.md`
- `docs/strategy/v0.6-closure-standardization-plan.md`
- `docs/strategy/v0.6-closure-inventory-2026-06-07.md`
- `docs/strategy/v0.6.3-control-plane-hardening-plan.md`
- `docs/strategy/mid-platform-completeness-v0.6-plan.md`
- `docs/strategy/ability-governance-operating-model-v0.6.md`
- `docs/strategy/ability-definition-v0.6.md`
- `docs/strategy/ability-api-gap-v0.6.md`
- `docs/strategy/business-agent-runtime-v0.6.md`
- `docs/strategy/client-parallel-preview-v0.6-handoff.md`
- `docs/strategy/todo-master-2026q2.md`
- `docs/standards/release-sop.md`
- `docs/standards/version-acceptance-template.md`
- `docs/standards/agent-runtime-regression-matrix.md`
- `docs/standards/eval-ability-interaction-state-model.md`

兼容调用上下文的历史实现记录可查 `docs/strategy/project-context-backend-design-v0.6.md` 和 `docs/strategy/end-to-end-business-object-api-v0.6.md`。这两份文档不再作为中台主视角入口，后续新方案统一以能力和调用上下文表述。

## 使用规则

1. 新任务先进入 `todo-master-2026q2.md`，否则不算当前任务。
2. 新方案必须说明目标、范围、非目标、验收标准和测试计划。
3. 已完成阶段方案保留，但不得继续当成待办清单。
4. 文档冲突时，按“当前回顾 -> 唯一 TODO -> 当前方案 -> 标准规范 -> 历史资料”的顺序判断。
5. 每轮重要开发结束后，更新 `project-current-review-YYYY-MM-DD.md` 或当前回顾文档。

最后更新：2026-06-07
