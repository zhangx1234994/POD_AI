# 平台 Plans 索引

> 目的：给 `docs/plans/` 里的平台级方案文档一个清晰入口，区分“当前仍有效的设计文档”和“专项技术计划”。

## 1. 当前目录中的现行重点

### A. 客户端现行骨架

- `docs/plans/2026-03-19-style3d-client-rearchitecture-design.md`

用途：

- 说明客户端当前页面骨架、路由和工作台结构按什么方向收口
- 与 `docs/client/plans/2026-04-16-client-phase1-operating-model.md`、`docs/client/plans/2026-03-17-style3d-client-current-status.md` 配合使用

### B. 专项技术计划

- `docs/plans/2026-03-13-concurrency-routing-plan.md`

用途：

- 记录并发与路由策略的一轮专项方案

## 2. 当前阅读建议

如果你在看客户端，优先顺序是：

1. `docs/client/README.md`
2. `docs/client/plans/README.md`
3. `docs/plans/2026-03-19-style3d-client-rearchitecture-design.md`

如果你在看中台并发/路由，直接看：

1. `docs/plans/2026-03-13-concurrency-routing-plan.md`

## 3. 维护规则

- `docs/plans/` 只放平台级或跨模块设计文档，不放日常模块操作手册。
- 若某份计划仍然指导当前实现，必须在对应模块入口文档里被明确引用。
- 若某份计划只保留回溯价值，应在入口文档中明确其“历史 / 专项方案”身份。

*最后更新: 2026-04-16*
