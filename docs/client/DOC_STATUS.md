# 客户端文档状态说明

> 当前状态：本仓库已不再包含客户端代码目录。`docs/client/` 只保留历史方案、阶段测试包和复盘资料，不代表当前开发主线。

## 1. 状态分类

客户端相关文档统一按 3 类理解：

### A. 历史入口

这些文档用于帮助读者判断历史资料怎么读，但不代表客户端正在本仓库内继续开发：

- `docs/client/README.md`
- `docs/client/DOC_STATUS.md`
- `docs/client/plans/README.md`
- `docs/client/CORE_TEST_PATHS.md`
- `docs/client/tech-review-2026-04-16/`
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

这些文档服务于“某一轮正式测试启动、交付、回归”的历史场景。它们默认不代表今天已经重新开放正式集中测试：

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

如果只是回看历史客户端资料，按这个顺序看：

1. `docs/PLATFORM_SURFACES.md`
2. `docs/client/README.md`
3. `docs/client/DOC_STATUS.md`
4. `docs/client/plans/README.md`
5. `docs/client/tech-review-2026-04-16/README.md`
6. `docs/client/plans/2026-04-16-client-phase1-operating-model.md`
7. `docs/client/plans/2026-03-17-style3d-client-current-status.md`
8. `docs/plans/2026-03-19-style3d-client-rearchitecture-design.md`
9. `docs/client/CORE_TEST_PATHS.md`

## 3. 当前最重要的判断规则

### 不要这样理解

- 不要看到“ready for test”就默认现在已经重新进入正式测试。
- 不要看到历史文档里的客户端目录，就认为当前仓库仍存在对应代码。
- 不要把历史规划里的页面骨架、路由、阶段边界当成当前事实。

### 要这样理解

- 历史规划文档回答的是“当时为什么这样设计”。
- 历史状态文档回答的是“当时做到哪一步”。
- 当前有效开发主线以 `backend/`、`podi-admin-web/`、`podi-eval-web/`、`image-ops-service/`、`vendor-api-ops/` 为准。

## 4. 后续维护规则

1. 新增客户端文档时，必须在标题或开头明确写明它属于：`历史入口 / 历史基线 / 阶段测试包 / 草案`。
2. 如果未来重新启动客户端，必须先重新确认代码目录、产品主线、接口边界，再更新本目录入口文档。
3. 正式重新开放集中测试前，必须先更新测试包文档，不允许直接沿用旧“ready for test”结论。

*最后更新: 2026-04-30*
