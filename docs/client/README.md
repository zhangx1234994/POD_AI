# 客户端文档唯一入口

> 结论先说：客户端文档以后只从这里进，不要在 `docs/client/` 里自己猜哪份先看。

## 1. 现在先看哪几份

这是当前最小有效阅读顺序：

1. `docs/PLATFORM_SURFACES.md`
   - 先确认客户端和管理端、测评端的边界
2. `docs/client/DOC_STATUS.md`
   - 先判断文档属于现行真源、历史基线，还是阶段测试包
3. `docs/client/plans/README.md`
   - 先区分现行 plans、历史基线和测试包
4. `docs/client/plans/2026-04-16-client-phase1-operating-model.md`
   - 看当前客户端按什么产品经营模型推进
5. `docs/client/plans/2026-03-17-style3d-client-current-status.md`
   - 看当前客户端做到哪一步
6. `docs/plans/2026-03-19-style3d-client-rearchitecture-design.md`
   - 看当前客户端按什么骨架继续收口

如果只是要找页面入口，再看：

7. `docs/client/CORE_TEST_PATHS.md`

## 2. 当前客户端的唯一判断标准

当前客户端定位：

- 正式业务前台
- 第一阶段对标 `Style3D` 这类竞品工作台
- 不暴露管理端/测评端逻辑
- 不把对话式助手当当前主入口

当前继续开发时，默认只问 3 件事：

1. 现在的页面结构是不是更像竞品工作台
2. 用户是不是更快进入输入、结果和下一步动作
3. 文档是不是能明确告诉人“哪份是现在有效的”

## 3. 文档怎么分

客户端文档只按下面 3 类理解：

### A. 现行真源

- `docs/client/DOC_STATUS.md`
- `docs/client/plans/README.md`
- `docs/client/plans/2026-04-16-client-phase1-operating-model.md`
- `docs/client/plans/2026-03-17-style3d-client-current-status.md`
- `docs/plans/2026-03-19-style3d-client-rearchitecture-design.md`
- `docs/client/CORE_TEST_PATHS.md`

### B. 历史基线

主要是 `docs/client/plans/2026-03-16-*.md`

用途：

- 回看第一轮为什么这么设计
- 回看当时怎么拆任务、怎么做对标、怎么做测试基线

不要这样用：

- 不要把它们当成今天的实时结构说明
- 不要把里面的路由、状态、边界直接当成当前事实

### C. 阶段测试包

主要是：

- `docs/client/START_HERE.md`
- `docs/client/OPEN_TEST_NOW.md`
- `docs/client/REVIEW_NOW.md`
- `docs/client/plans/2026-03-17-style3d-client-*.md` 里那批 ready/start/package/runbook/handoff/template

用途：

- 服务某一轮正式测试启动和问题回收

不要这样用：

- 不要看到 `ready-for-test` 就默认今天已经重新开放正式测试

## 4. 当前真正需要维护的入口

以后客户端有变化，优先同步这几份：

1. `docs/client/README.md`
2. `docs/client/DOC_STATUS.md`
3. `docs/client/plans/README.md`
4. `docs/client/plans/2026-04-16-client-phase1-operating-model.md`
5. `docs/client/CORE_TEST_PATHS.md`
6. `docs/client/plans/2026-03-17-style3d-client-current-status.md`
7. `docs/plans/2026-03-19-style3d-client-rearchitecture-design.md`

如果这 7 份没更新，其他客户端文档默认都不算整理完成。

## 5. 当前代码位置

- 前端项目：`podi-client-web/`

客户端和下面两个前端分离维护：

- `podi-admin-web/`
- `podi-eval-web/`

*最后更新: 2026-04-16*
