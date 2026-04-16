# 客户端正式测试包说明

> 结论：**当前客户端版本已具备集中测试条件。**  
> 用途：作为正式开始测试前的总入口文档。
> 文档状态：阶段测试包文档。
> 以上结论对应 2026-03-17 当时的测试准备状态，当前是否仍按此执行，以最新开发通知为准。

## 1. 本次要测的是什么

本次测试对象是：

- `podi-client-web/`
- 面向业务使用者的客户端前台

不是：

- `podi-admin-web/` 管理端
- `podi-eval-web/` 测评端

---

## 2. 当前测试结论

### 可以开始集中测试

原因：

- 页面骨架完整
- 高概率入口大部分已收口
- 任务 / 素材 / 钱包闭环已接通
- 本地自动化回归通过
- 远端真实样本回归通过

### 但仍不是最终发布版

所以建议测试重点放在：

- 页面与交互是否顺
- 链路是否通
- 闭环是否完整

而不是一上来就把所有 AI 效果按最终商业效果验死。

---

## 3. 当前回归基线

### 本地

- `npm run selfcheck:local`：通过
- 本地 UI smoke：`18 / 18`

### 远端

- `npm run selfcheck:full`：通过
- 百度同步样本：通过
- 火山同步样本：通过
- KIE 异步样本：通过
- ComfyUI 异步样本：通过

远端报告：

- `/Volumes/MAC 1/pod_codex/podi-client-web/reports/client-remote-selftest-latest.json`

---

## 4. 建议你测试时直接用这 3 份文档

### 测试前先看

- `/Volumes/MAC 1/pod_codex/docs/client/plans/2026-03-17-style3d-client-ready-for-test.md`
- `/Volumes/MAC 1/pod_codex/docs/client/plans/2026-03-17-style3d-client-start-testing.md`
- `/Volumes/MAC 1/pod_codex/docs/client/plans/2026-03-17-style3d-client-release-notes.md`

### 开始测试时按这个顺序走

- `/Volumes/MAC 1/pod_codex/docs/client/plans/2026-03-17-style3d-client-test-runbook.md`

### 测出问题后按这个格式记

- `/Volumes/MAC 1/pod_codex/docs/client/plans/2026-03-17-style3d-client-bug-report-template.md`
- `/Volumes/MAC 1/pod_codex/docs/client/plans/2026-03-17-style3d-client-issue-log-template.md`

### 测试时顺手参考这份已知边界

- `/Volumes/MAC 1/pod_codex/docs/client/plans/2026-03-17-style3d-client-known-risks.md`

---

## 5. 当前建议测试重点

优先级从高到低：

1. 首页 / 工作台 / 顶部搜索
2. 工具箱主链路
3. 研发设计主链路
4. 商拍主链路
5. 任务中心 / 素材库闭环
6. 钱包 / 充值回流
7. 项目详情页

---

## 6. 当前版本边界

### 可以按正式产品思路测的

- 门面观感
- 页面结构
- 导航与入口
- 任务状态
- 结果回填
- 素材继续创作
- 钱包前台回流

### 不建议按最终商业成品硬验的

- 第一版复用链路的最终效果质量
- 完整支付闭环
- 后端项目归档能力
- 全量高压业务测试

---

## 7. 当前目标

这一版的目标不是“直接上线”，而是：

- 先完成一轮高质量集中测试
- 先把问题结构化收集回来
- 再做最后一轮问题收口
