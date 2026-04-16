# 客户端文档状态说明

> 目的：解决客户端文档“历史计划、阶段测试包、当前真源”混在一起的问题。
> 结论：以后先看本文，再决定读哪一份。

## 1. 状态分类

客户端相关文档统一按 3 类理解：

### A. 现行真源

这些文档代表当前仍有效、仍在指导开发或认知的内容：

- `docs/client/README.md`
- `docs/client/CORE_TEST_PATHS.md`
- `docs/client/plans/README.md`
- `docs/client/plans/2026-04-16-client-phase1-operating-model.md`
- `docs/client/plans/2026-03-17-style3d-client-current-status.md`
- `docs/plans/2026-03-19-style3d-client-rearchitecture-design.md`
- `docs/PLATFORM_SURFACES.md`

### B. 历史基线 / 阶段记录

这些文档保留是为了回溯“当时如何分析、如何规划、如何测试”，不是为了说明“今天仍然按原文逐条执行”：

- `docs/client/plans/2026-03-16-style3d-client-analysis.md`
- `docs/client/plans/2026-03-16-style3d-client-build-plan.md`
- `docs/client/plans/2026-03-16-style3d-client-gap-audit.md`
- `docs/client/plans/2026-03-16-style3d-client-interaction-spec.md`
- `docs/client/plans/2026-03-16-style3d-client-phase1-tasklist.md`
- `docs/client/plans/2026-03-16-style3d-client-product-architecture.md`
- `docs/client/plans/2026-03-16-style3d-client-wireframe-spec.md`
- `docs/client/plans/2026-03-16-style3d-client-live-selftest-notes.md`
- `docs/client/plans/2026-03-16-style3d-client-smoke-report.md`
- `docs/client/plans/2026-03-16-style3d-client-test-*.md`
- `docs/client/plans/2026-03-16-style3d-client-version-boundary.md`

### C. 阶段测试包

这些文档服务于“某一轮正式测试启动、交付、回归”的场景。
如果当前还在持续重构，它们默认不代表“已经重新开放正式集中测试”：

- `docs/client/START_HERE.md`
- `docs/client/OPEN_TEST_NOW.md`
- `docs/client/REVIEW_NOW.md`
- `docs/client/plans/2026-03-17-style3d-client-ready-for-test.md`
- `docs/client/plans/2026-03-17-style3d-client-start-testing.md`
- `docs/client/plans/2026-03-17-style3d-client-formal-test-package.md`
- `docs/client/plans/2026-03-17-style3d-client-test-runbook.md`
- `docs/client/plans/2026-03-17-style3d-client-test-handoff.md`
- `docs/client/plans/2026-03-17-style3d-client-release-notes.md`
- `docs/client/plans/2026-03-17-style3d-client-bug-report-template.md`
- `docs/client/plans/2026-03-17-style3d-client-issue-log-template.md`
- `docs/client/plans/2026-03-17-style3d-client-known-risks.md`

## 2. 现在应该怎么读

如果你是新接手、继续开发、或者只是想知道“现在做到哪了”，按这个顺序看：

1. `docs/PLATFORM_SURFACES.md`
2. `docs/client/README.md`
3. `docs/client/plans/README.md`
4. `docs/client/plans/2026-04-16-client-phase1-operating-model.md`
5. `docs/client/plans/2026-03-17-style3d-client-current-status.md`
6. `docs/plans/2026-03-19-style3d-client-rearchitecture-design.md`
7. `docs/client/CORE_TEST_PATHS.md`

## 3. 当前最重要的判断规则

### 不要这样理解

- 不要看到“ready for test”就默认现在已经重新进入正式测试
- 不要看到 `2026-03-16` 的路由或结构，就认为今天页面仍完全按那个版本
- 不要把历史规划里的“建议聚合接口 / 建议模块结构 / 建议页面骨架”当成当前真实实现

### 要这样理解

- 历史规划文档回答的是“当时为什么这样设计”
- 当前状态文档回答的是“现在做到哪了”
- 重构设计文档回答的是“现在按什么方向继续收口”

## 4. 后续维护规则

1. 新增客户端文档时，必须在标题或开头明确写明它属于：`现行真源 / 历史基线 / 阶段测试包 / 草案`。
2. 一旦客户端主入口、主要路由、页面骨架发生明显变化，必须同步更新：
   - `docs/client/README.md`
   - `docs/client/plans/README.md`
   - `docs/client/plans/2026-04-16-client-phase1-operating-model.md`
   - `docs/client/CORE_TEST_PATHS.md`
   - `docs/client/plans/2026-03-17-style3d-client-current-status.md`
3. 正式重新开放集中测试前，必须先更新测试包文档，不允许直接沿用旧“ready for test”结论。

*最后更新: 2026-04-16*
