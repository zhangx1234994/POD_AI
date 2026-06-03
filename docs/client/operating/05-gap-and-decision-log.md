# 05. Gap 与决策日志机制

最后更新：2026-06-02

## 1. Gap 记录原则

客户端不能因为中台 API 不完整就绕过边界。

发现以下情况必须记录 gap：

- 没有业务 API。
- 业务 API 字段不够。
- 状态无法轮询。
- 结果无法沉淀资产。
- 错误原因不可读。
- 计费/余额数据缺失。
- 导出包不完整。

## 2. 禁止绕过

客户端禁止用以下方式“临时解决”：

- 调 `/api/admin/*`
- 调 `/api/evals/*`
- 调 `/api/abilities/*`
- 调 `/api/ability-tasks/*`
- 调 `/api/coze/*`
- 直接调 ComfyUI
- 直接调 vendor-api/image-ops 内部服务
- 在客户端暴露内部 URL

## 3. Gap 记录位置

当前统一记录到：

```text
docs/client/runs/YYYY-MM-DD-短标题/gap-log.md
```

如果 gap 属于长期策略，也同步到：

```text
docs/strategy/ability-api-gap-v0.6.md
```

## 4. Gap 模板

```md
### GAP-YYYYMMDD-NN: 标题

Status: open
Priority: P0 / P1 / P2
Client Page:
User Action:

Expected Client Behavior:

Needed API/Data:

Current API Limitation:

Suggested Mid-Platform API:

Temporary Client Behavior:

Evidence:
- Screenshot:
- Request/response:
- Related workItemId/projectId/runId:
```

## 5. 决策日志

重大产品/技术取舍必须记录：

```md
### DECISION-YYYYMMDD-NN: 标题

Decision:

Why:

Rejected Options:

Impact:

Follow-up:
```

## 6. 当前已确认决策

### DECISION-20260602-01: 客户端采用能力工作台视角

Decision:
客户端主视角是能力驱动的业务生产工作台，不是项目管理系统。

Why:
当前中台能力闭环尚未完全成熟，按项目制完整闭环推进会导致大量占位和假流程。单能力真实闭环更适合验证能力质量和用户体验。

Rejected Options:
- 以 `/projects` 作为第一入口。
- 继续修旧 `podi-client-web` 作为正式主线。
- 让客户端绕过中台直接调用内部能力。

Impact:
首版入口使用 `/workbench`，`projectId` 作为后端证据容器隐藏在业务上下文里。

Follow-up:
优先实现花纹提取真实闭环，再扩展裂变、选择和导出草稿。

