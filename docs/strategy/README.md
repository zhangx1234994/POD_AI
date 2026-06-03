# 战略工作区

本目录只承载平台级方向、当前执行清单和治理规则。接口细节、模块说明、测试报告不放在这里展开。

## 当前必读

1. `mid-platform-completeness-v0.6-plan.md`
2. `ability-governance-operating-model-v0.6.md`
3. `ability-definition-v0.6.md`
4. `ability-api-gap-v0.6.md`
5. `business-agent-runtime-v0.6.md`
6. `client-parallel-preview-v0.6-handoff.md`
7. `todo-master-2026q2.md`
8. `project-half-year-review-2026-05-26.md`
9. `platform-polish-v0.5-decision-plan.md`
10. `output-quality-review-v0.5.md`
11. `project-current-review-2026-05-22.md`

## 当前阶段

- 当前阶段：`v0.6 中台能力治理与客户端支撑底座版`。
- 当前目标：把中台从单次业务任务扩展为可管理、可封装、可优化、可迭代、可控的业务能力体系。
- 当前重点：能力 API 完整性、能力版本治理、路由和质量证据、资产沉淀、业务 run 与客户端步骤关联、调用上下文证据、客户端并行交接、Agent Runtime MVP 整改。
- 当前新增试点：对话式图编辑 Agent 作为中台高级能力接入，先生成方案卡片，确认后调用 `image_edit` 业务 run；它是 Agent Runtime 最小样板，不是前端聊天框。
- 当前新增约束：Agent MVP 可以先小范围上线，但必须提前具备后端会话、上下文压缩、能力路由证据、方法论版本预留、异步队列、幂等、成本/Key 治理和稳定性回归。
- 当前非目标：低代码工作流编辑器、一次全自动端到端承诺、客户端直连原子能力、正式支付、全品类一次性覆盖、重型通用 Agent 平台。

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
- `docs/strategy/mid-platform-completeness-v0.6-plan.md`
- `docs/strategy/ability-governance-operating-model-v0.6.md`
- `docs/strategy/ability-definition-v0.6.md`
- `docs/strategy/ability-api-gap-v0.6.md`
- `docs/strategy/business-agent-runtime-v0.6.md`
- `docs/strategy/client-parallel-preview-v0.6-handoff.md`
- `docs/strategy/todo-master-2026q2.md`
- `docs/standards/release-sop.md`

兼容调用上下文的历史实现记录可查 `docs/strategy/project-context-backend-design-v0.6.md` 和 `docs/strategy/end-to-end-business-object-api-v0.6.md`。这两份文档不再作为中台主视角入口，后续新方案统一以能力和调用上下文表述。

## 使用规则

1. 新任务先进入 `todo-master-2026q2.md`，否则不算当前任务。
2. 新方案必须说明目标、范围、非目标、验收标准和测试计划。
3. 已完成阶段方案保留，但不得继续当成待办清单。
4. 文档冲突时，按“当前回顾 -> 唯一 TODO -> 当前方案 -> 标准规范 -> 历史资料”的顺序判断。
5. 每轮重要开发结束后，更新 `project-current-review-YYYY-MM-DD.md` 或当前回顾文档。

最后更新：2026-06-03
