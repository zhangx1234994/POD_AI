# 战略工作区

本目录只承载平台级方向、当前执行清单和治理规则。接口细节、模块说明、测试报告不放在这里展开。

## 当前必读

1. `project-current-review-2026-05-22.md`
2. `todo-master-2026q2.md`
3. `business-stability-observability-v0.4.1-plan.md`
4. `business-orchestration-workbench-v0.4-plan.md`
5. `control-point-and-file-index-2026-05-19.md`
6. `business-control-point-matrix-2026-05-19.md`
7. `doc-cleanup-inventory-2026-05-18.md`

## 当前阶段

- 当前阶段：`v0.4.1 稳定性监控与管理端降噪版`。
- 当前目标：在 v0.4.0 封版后补齐线上监控、发版门禁和页面可读性。
- 当前重点：连接池/线程治理、health-watch/live patrol 常态化、ComfyUI 状态收敛、管理端首页/业务能力/接口调用/资源页降噪。
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
- `docs/strategy/project-current-review-2026-05-22.md`
- `docs/strategy/todo-master-2026q2.md`
- `docs/standards/release-sop.md`

## 使用规则

1. 新任务先进入 `todo-master-2026q2.md`，否则不算当前任务。
2. 新方案必须说明目标、范围、非目标、验收标准和测试计划。
3. 已完成阶段方案保留，但不得继续当成待办清单。
4. 文档冲突时，按“当前回顾 -> 唯一 TODO -> 当前方案 -> 标准规范 -> 历史资料”的顺序判断。
5. 每轮重要开发结束后，更新 `project-current-review-YYYY-MM-DD.md` 或当前回顾文档。

最后更新：2026-05-26
