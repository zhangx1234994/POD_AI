# 现在开始测客户端

> 说明：本文档对应第一轮客户端集中测试包入口。
> 如果当前还处在持续重构阶段，请先看：
> - `/Volumes/MAC 1/pod_codex/docs/client/plans/2026-03-17-style3d-client-current-status.md`
> - `/Volumes/MAC 1/pod_codex/docs/plans/2026-03-19-style3d-client-rearchitecture-design.md`

如果你现在更想先看页面观感，而不是先测链路，请直接打开：

- `/Volumes/MAC 1/pod_codex/docs/client/REVIEW_NOW.md`

如果你现在就要开始测，按这个顺序来：

## 1. 先看这份

- `/Volumes/MAC 1/pod_codex/docs/client/plans/2026-03-17-style3d-client-start-testing.md`

## 2. 再看测试边界

- `/Volumes/MAC 1/pod_codex/docs/client/plans/2026-03-17-style3d-client-ready-for-test.md`

## 2.1 如果你想直接点页面

- `/Volumes/MAC 1/pod_codex/docs/client/CORE_TEST_PATHS.md`

## 3. 按执行清单测试

- `/Volumes/MAC 1/pod_codex/docs/client/plans/2026-03-17-style3d-client-test-runbook.md`

## 4. 记录问题

- `/Volumes/MAC 1/pod_codex/docs/client/plans/2026-03-17-style3d-client-bug-report-template.md`
- `/Volumes/MAC 1/pod_codex/docs/client/plans/2026-03-17-style3d-client-issue-log-template.md`

## 5. 如果想快速知道这版改了什么

- `/Volumes/MAC 1/pod_codex/docs/client/plans/2026-03-17-style3d-client-release-notes.md`

## 当前回归基线

- 本地 UI smoke：`18 / 18`
- `npm run selfcheck:full`：通过
- 远端同步 / 异步样本：通过

> 注意：以上基线来自 2026-03-16 ~ 2026-03-17 的阶段记录。是否重新进入正式测试，以当前开发通知为准。
