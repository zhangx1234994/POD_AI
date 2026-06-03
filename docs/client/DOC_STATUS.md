# 客户端文档状态说明

> 当前状态：客户端已重新进入 v0.6 方案与机制建设阶段。`docs/client/operating/` 是当前主开发机制；旧 plans 和测试包仍为历史资料。

## 1. 状态分类

客户端相关文档统一按 4 类理解：

### A. 当前执行机制

这些文档是当前客户端负责人后续推进工作的机制口径：

- `docs/client/operating/README.md`
- `docs/client/operating/01-product-reasoning.md`
- `docs/client/operating/02-development-rhythm.md`
- `docs/client/operating/03-document-governance.md`
- `docs/client/operating/04-acceptance-and-regression.md`
- `docs/client/operating/05-gap-and-decision-log.md`
- `docs/client/operating/06-delivery-report-template.md`

### B. 当前 v0.6 方案资料

这些文档是当前客户端产品边界、能力边界和接口边界：

- `docs/strategy/ability-governance-operating-model-v0.6.md`
- `docs/strategy/client-agent-pack-v0.6/README.md`
- `docs/strategy/client-agent-pack-v0.6/01-agent-brief.md`
- `docs/strategy/client-agent-pack-v0.6/02-product-mvp.md`
- `docs/strategy/client-agent-pack-v0.6/03-ui-flow.md`
- `docs/strategy/client-agent-pack-v0.6/04-api-contract.md`
- `docs/strategy/client-agent-pack-v0.6/05-acceptance-checklist.md`
- `docs/strategy/client-agent-pack-v0.6/06-gap-log-template.md`

### C. 历史入口

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

### D. 历史基线 / 阶段记录

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

### E. 阶段测试包

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

如果看当前客户端主线，按这个顺序看：

1. `docs/client/README.md`
2. `docs/client/operating/README.md`
3. `docs/strategy/ability-governance-operating-model-v0.6.md`
4. `docs/strategy/client-agent-pack-v0.6/README.md`
5. `docs/strategy/client-agent-pack-v0.6/03-ui-flow.md`
6. `docs/strategy/client-agent-pack-v0.6/04-api-contract.md`
7. `docs/client/operating/04-acceptance-and-regression.md`

如果只是回看历史客户端资料，再看：

1. `docs/PLATFORM_SURFACES.md`
2. `docs/client/plans/README.md`
3. `docs/client/tech-review-2026-04-16/README.md`
4. `docs/client/plans/2026-04-16-client-phase1-operating-model.md`
5. `docs/client/plans/2026-03-17-style3d-client-current-status.md`
6. `docs/plans/2026-03-19-style3d-client-rearchitecture-design.md`
7. `docs/client/CORE_TEST_PATHS.md`

## 3. 当前最重要的判断规则

### 不要这样理解

- 不要看到“ready for test”就默认现在已经重新进入正式测试。
- 不要看到历史文档里的客户端目录，就认为当前仓库仍存在对应代码。
- 不要把历史规划里的页面骨架、路由、阶段边界当成当前事实。

### 要这样理解

- 历史规划文档回答的是“当时为什么这样设计”。
- 历史状态文档回答的是“当时做到哪一步”。
- 当前客户端有效机制以 `docs/client/operating/` 和 `docs/strategy/client-agent-pack-v0.6/` 为准。
- 当前客户端产品口径是能力驱动的业务生产工作台，`projectId` 是后端证据容器。
- 当前新客户端工程目录是 `podi-studio-preview/`，默认本地端口 `8230`。

## 4. 后续维护规则

1. 新增客户端文档时，必须在标题或开头明确写明它属于：`历史入口 / 历史基线 / 阶段测试包 / 草案`。
2. 如果未来重新启动客户端，必须先重新确认代码目录、产品主线、接口边界，再更新本目录入口文档。
3. 正式重新开放集中测试前，必须先更新测试包文档，不允许直接沿用旧“ready for test”结论。

*最后更新: 2026-06-02*
