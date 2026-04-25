# 客户端测试交接摘要

> 用途：真正开始集中测试时，直接看这份就够。
> 目标：把“测什么、怎么测、问题怎么回收”压缩成最短路径。
> 文档状态：阶段测试包文档。
> 这是某一轮测试交接摘要，不代表今天仍默认按这份交接内容执行。

## 1. 现在的结论

当前客户端版本：

- 已具备集中测试条件
- 不等于最终商业发布版
- 但已经适合做一轮系统测试，把问题结构化收回来

---

## 2. 你开测前只需要看 3 份文档

### 先看边界

- `/Volumes/MAC 1/pod_codex/docs/client/plans/2026-03-17-style3d-client-ready-for-test.md`

### 再按顺序执行

- `/Volumes/MAC 1/pod_codex/docs/client/plans/2026-03-17-style3d-client-test-runbook.md`

### 测出问题后按模板记

- `/Volumes/MAC 1/pod_codex/docs/client/plans/2026-03-17-style3d-client-bug-report-template.md`

---

## 3. 当前版本最值得优先测的部分

优先级从高到低：

1. 首页 / 工作台 / 顶部搜索
2. AI工具箱
3. AI研发设计
4. AI视觉商拍
5. 任务中心 / 素材库闭环
6. 钱包 / 充值回流
7. 项目详情页

---

## 4. 当前回归基线

- `npm run selfcheck:full`：通过
- 本地 UI smoke：`18 / 18`
- 远端同步样本：通过
- 远端异步样本：通过

远端报告：

- `/Volumes/MAC 1/pod_codex/podi-client-web/reports/client-remote-selftest-latest.json`

---

## 5. 你反馈问题时，最重要的是写清楚这几项

- 页面
- 功能
- 操作步骤
- 实际现象
- 预期现象
- 是否稳定复现
- 是否影响业务

这样我能最快回收并修。
