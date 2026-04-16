# 客户端 Plans 索引

> 目的：把 `docs/client/plans/` 里的现行文档、历史基线、阶段测试包分开，避免直接在目录里猜哪份该看。

## 1. 当前优先看哪几份

如果你是继续开发、整理页面、或判断客户端现在做到哪一步，按这个顺序看：

1. `docs/client/plans/2026-04-16-client-phase1-operating-model.md`
2. `docs/client/plans/2026-03-17-style3d-client-current-status.md`
3. `docs/plans/2026-03-19-style3d-client-rearchitecture-design.md`

这 3 份分别回答：

- 当前客户端按什么经营模型推进
- 当前版本做到哪一步
- 当前页面骨架按什么方向继续收口

## 2. 当前目录怎么分

### A. 现行真源 / 现行状态

- `docs/client/plans/2026-04-16-client-phase1-operating-model.md`
- `docs/client/plans/2026-03-17-style3d-client-current-status.md`

### B. 历史基线 / 第一轮规划资料

主要是：

- `docs/client/plans/2026-03-16-style3d-client-*.md`

用途：

- 回看第一轮对标分析、产品骨架、交互、测试范围和实施拆分

不要这样理解：

- 不要把其中的页面结构、路由、阶段边界直接当成当前事实

### C. 阶段测试包

主要是：

- `docs/client/plans/2026-03-17-style3d-client-ready-for-test.md`
- `docs/client/plans/2026-03-17-style3d-client-start-testing.md`
- `docs/client/plans/2026-03-17-style3d-client-formal-test-package.md`
- `docs/client/plans/2026-03-17-style3d-client-test-runbook.md`
- `docs/client/plans/2026-03-17-style3d-client-test-handoff.md`
- `docs/client/plans/2026-03-17-style3d-client-release-notes.md`
- 以及 bug / issue / risk / template 这批文档

用途：

- 服务某一轮集中测试和问题回收

不要这样理解：

- 不要看到 “ready for test / start testing” 就默认今天已经重新开放正式集中测试

## 3. 当前维护规则

客户端有明显变化时，优先同步：

1. `docs/client/README.md`
2. `docs/client/DOC_STATUS.md`
3. `docs/client/plans/README.md`
4. `docs/client/plans/2026-04-16-client-phase1-operating-model.md`
5. `docs/client/plans/2026-03-17-style3d-client-current-status.md`
6. `docs/plans/2026-03-19-style3d-client-rearchitecture-design.md`

如果这几份没有一起更新，客户端文档默认不算整理完成。

*最后更新: 2026-04-16*
