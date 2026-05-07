# 平台 Plans 索引

> 目的：区分当前仍指导实现的专项计划与历史方案。当前仓库不再包含客户端代码；客户端相关计划只保留回溯价值，不代表当前开发主线。

## 1. 当前有效计划

### A. 管理端前端整理

- `docs/plans/2026-04-30-admin-frontend-cleanup-phase1.md`

用途：

- 记录管理端前端整理第一阶段的边界、已落地拆包范围和后续整改顺序。
- 作为管理端信息架构、页面降噪、功能入口暴露和前端大包体治理的当前执行参考。

### B. 并发与路由专项

- `docs/plans/2026-03-13-concurrency-routing-plan.md`

用途：

- 记录 ComfyUI 多执行节点、队列、分流和保底路由的一轮专项方案。
- 后续排查“任务是否打满 GPU / 是否只打到单台机器 / 失败后是否正确换线”时优先参考。

## 2. 历史方案

### A. 客户端历史方案

- `docs/plans/2026-03-19-style3d-client-rearchitecture-design.md`

说明：

- 该文档只作为历史客户端重构思路留档。
- 当前仓库已移除旧客户端目录，不应按该文档直接开展现行客户端开发。
- 后续如果重启客户端，需要先在 `docs/strategy/todo-master-2026q2.md` 登记新任务，再重新确认客户端形态、入口、业务边界和与中台的接口关系。

## 3. 当前阅读建议

如果你在看管理端前端整理，直接看：

1. `docs/plans/2026-04-30-admin-frontend-cleanup-phase1.md`

如果你在看 ComfyUI 并发、路由和队列利用率，直接看：

1. `docs/plans/2026-03-13-concurrency-routing-plan.md`

如果你在回顾旧客户端方案，先确认：

1. `docs/client/README.md`
2. `docs/client/plans/README.md`
3. `docs/plans/2026-03-19-style3d-client-rearchitecture-design.md`

## 4. 维护规则

- `docs/plans/` 只放平台级或跨模块设计文档，不放日常模块操作手册。
- 若某份计划仍然指导当前实现，必须在对应模块入口文档里被明确引用。
- 若某份计划只保留回溯价值，入口文档必须明确标注“历史方案”或“专项方案”身份。
- 客户端相关文档默认视为历史资料，除非战略待办池重新登记并明确进入当前开发范围。

*最后更新: 2026-05-07*
