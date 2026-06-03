# 客户端文档唯一入口

> 当前状态：客户端已重新进入方案与机制建设阶段。历史客户端资料仍保留，但当前主线以 **PODI Studio Preview / 能力驱动业务生产工作台** 为准。
> 代码目录是否新建、命名和工程细节以后续实现为准；旧 `podi-client-web/`、`podi-client-v2/` 不自动恢复为正式主线。

## 0. 当前主线先看这里

当前客户端主开发机制入口：

1. `docs/client/operating/README.md`
2. `docs/client/operating/01-product-reasoning.md`
3. `docs/client/operating/02-development-rhythm.md`
4. `docs/client/operating/03-document-governance.md`
5. `docs/client/operating/04-acceptance-and-regression.md`
6. `docs/client/operating/05-gap-and-decision-log.md`
7. `docs/client/operating/06-delivery-report-template.md`

当前 v0.6 客户端方案入口：

1. `docs/strategy/ability-governance-operating-model-v0.6.md`
2. `docs/strategy/client-agent-pack-v0.6/README.md`
3. `docs/strategy/client-agent-pack-v0.6/01-agent-brief.md`
4. `docs/strategy/client-agent-pack-v0.6/02-product-mvp.md`
5. `docs/strategy/client-agent-pack-v0.6/03-ui-flow.md`
6. `docs/strategy/client-agent-pack-v0.6/04-api-contract.md`
7. `docs/strategy/client-agent-pack-v0.6/05-acceptance-checklist.md`
8. `docs/strategy/client-agent-pack-v0.6/06-gap-log-template.md`

当前执行口径：

- 客户端是能力驱动的业务生产工作台。
- `/workbench` 是产品主入口。
- `projectId` 是后端证据容器，不是客户端主产品视角。
- 第一阶段按单能力真实闭环优先推进。
- 历史客户端文档只用于回溯，不直接作为当前执行口径。

## 1. 如果需要回看历史客户端资料，先看哪几份

这是历史资料的最小阅读顺序：

1. `docs/PLATFORM_SURFACES.md`
   - 先确认客户端和管理端、测评端的边界
2. `docs/client/DOC_STATUS.md`
   - 先判断文档属于历史入口、历史基线，还是阶段测试包
3. `docs/client/plans/README.md`
   - 先区分历史 plans、历史基线和测试包
4. `docs/client/plans/2026-04-16-client-phase1-operating-model.md`
   - 看当时客户端按什么产品经营模型推进
5. `docs/client/plans/2026-03-17-style3d-client-current-status.md`
   - 看当时客户端做到哪一步
6. `docs/plans/2026-03-19-style3d-client-rearchitecture-design.md`
   - 看当时客户端按什么骨架继续收口

如果只是要找页面入口，再看：

7. `docs/client/CORE_TEST_PATHS.md`

## 2. 历史客户端方案的判断标准

当时的客户端定位：

- 正式业务前台
- 第一阶段对标 `Style3D` 这类竞品工作台
- 不暴露管理端/测评端逻辑
- 不把对话式助手当当前主入口

后续如果重新启动客户端，应先重新立项，不要直接沿用旧文档。重新启动时默认先问 3 件事：

1. 现在的页面结构是不是更像竞品工作台
2. 用户是不是更快进入输入、结果和下一步动作
3. 文档是不是能明确告诉人“哪份是现在有效的”

## 3. 文档怎么分

客户端文档只按下面 3 类理解：

### A. 历史入口

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

## 4. 如果继续推进当前客户端，真正需要维护的入口

以后客户端有变化，优先同步这几类：

1. `docs/client/README.md`
2. `docs/client/DOC_STATUS.md`
3. `docs/client/operating/`
4. `docs/strategy/client-agent-pack-v0.6/`
5. `docs/strategy/ability-governance-operating-model-v0.6.md`
6. `docs/api/modules/business.md`
7. `docs/standards/error-catalog.md`

历史 plans 只有在需要回溯旧方案时才更新。

## 5. 当前代码位置

当前新客户端工程目录：

- `podi-studio-preview/`

本地开发端口：

- `http://localhost:8230/workbench`

旧文档中提到的 `podi-client-web/`、`podi-client-v2/`、`podi-design-web-dev/` 默认只作为历史参考，不作为当前主线。

*最后更新: 2026-06-02*
