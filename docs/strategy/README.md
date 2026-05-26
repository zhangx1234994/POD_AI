# 战略工作区

本目录只承载平台级方向、当前执行清单和治理规则。接口细节、模块说明、测试报告不放在这里展开。

## 当前必读

1. `project-current-review-2026-05-22.md`
2. `project-half-year-review-2026-05-26.md`
3. `platform-polish-v0.5-decision-plan.md`
4. `output-quality-review-v0.5.md`
5. `todo-master-2026q2.md`
6. `business-stability-observability-v0.4.1-plan.md`
7. `business-orchestration-workbench-v0.4-plan.md`
8. `control-point-and-file-index-2026-05-19.md`
9. `business-control-point-matrix-2026-05-19.md`
10. `doc-cleanup-inventory-2026-05-18.md`

## 当前阶段

- 当前阶段：`v0.5 平台打磨版`。
- 当前目标：把已经跑通的中台、管理端、测评端和核心业务能力打磨到业务方愿意持续使用。
- 当前重点：业务流可视化、流程监控、出图效果复盘、分流/LoRA 候选治理、管理端/测评端视觉降噪和业务方试用动线。
- 当前非目标：新增大业务能力、完整低代码平台、客户端重构、正式支付、为单台 ComfyUI 机器写业务特判。

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
- `docs/strategy/project-half-year-review-2026-05-26.md`
- `docs/strategy/platform-polish-v0.5-decision-plan.md`
- `docs/strategy/output-quality-review-v0.5.md`
- `docs/strategy/todo-master-2026q2.md`
- `docs/standards/release-sop.md`

## 使用规则

1. 新任务先进入 `todo-master-2026q2.md`，否则不算当前任务。
2. 新方案必须说明目标、范围、非目标、验收标准和测试计划。
3. 已完成阶段方案保留，但不得继续当成待办清单。
4. 文档冲突时，按“当前回顾 -> 唯一 TODO -> 当前方案 -> 标准规范 -> 历史资料”的顺序判断。
5. 每轮重要开发结束后，更新 `project-current-review-YYYY-MM-DD.md` 或当前回顾文档。

最后更新：2026-05-26
