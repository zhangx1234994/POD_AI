# 接口 3：裂变生成图评估

## 用途

输入裂变前原图和裂变后结果图，让中台判断生成质量、逻辑合理性和是否建议二次裂变。

该接口只评分，不自动二次裂变。业务方如果需要“评分不通过就再裂变”，应在自己的业务逻辑中再次调用裂变接口。

## 接口

- 提交：`POST /api/business/fission-evaluate/runs`
- 查询：`POST /api/business/runs/get`
- 鉴权：`X-PODI-API-Key`
- 输出：结构化评分结果，优先读取 `texts`；如果返回了轻量 `resultPayload`，可读取其中的 `decision/score/problem_tags/reason/next_action`。完整排障字段用查询参数 `"detail": "full"`。

## 参数

| 参数 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `originalImageUrl` | 是 | 无 | 裂变前原图 URL。 |
| `generatedImageUrl` | 是 | 无 | 裂变后的结果图 URL。 |
| `context` | 否 | `{}` | 业务上下文，建议传裂变版本、提示词、重绘幅度、profile。 |
| `callbackUrl` | 否 | 空 | 终态回调地址；不传则用轮询查询结果。 |
| `source` | 否 | `partner-api` | 调用来源标识，便于中台统计。 |
| `channel` | 否 | `open-api` | 调用渠道标识，便于区分业务系统、测评端或脚本。 |
| `requestId` | 否 | 自动生成 | 业务方请求 ID，建议每次唯一。 |
| `traceId` | 否 | 自动生成 | 业务方链路 ID，便于把评分和裂变任务关联。 |

## 返回字段

提交接口返回：

| 字段 | 说明 |
| --- | --- |
| `runId` | 业务任务 ID。后续轮询、排障和回调关联都用它。 |
| `status` / `taskStatus` | 当前状态。提交成功时通常是 `queued` 或 `running`。 |
| `taskId` | 底层 VL 评分能力任务 ID，可能稍后才生成；业务方不需要依赖。 |
| `requestId` / `traceId` | 业务请求和链路 ID，用于把裂变任务和评分任务关联起来。 |
| `debugUrl` | 可选的中台排障链接，没有则为空。 |

查询接口默认返回：

| 字段 | 说明 |
| --- | --- |
| `status` / `taskStatus` | `queued/running` 继续轮询；`succeeded` 表示可读评分；`failed` 表示失败。 |
| `texts` | 评分文本或结构化评分摘要，业务方优先读取。 |
| `text` | 第一段评分文本，便于简单接入。 |
| `resultPayload` | 轻量结构化结果，通常包含 `decision/score/problem_tags/reason/next_action`。 |
| `imageUrls` | 当前评分接口通常为空，保留统一任务模型。 |
| `error` / `errorMessage` | 失败原因。中台已脱敏，不会返回密钥或 SQL 原文。 |
| `errorCode` | 标准错误码，例如缺少原图、缺少生成图、VL 评分失败。 |
| `debugResponse` | 给业务方看的简短排障提示。 |
| `retryAfterSeconds` | 建议下次轮询等待秒数；为空时每 5-10 秒查一次。 |
| `durationMs` | 任务耗时，单位毫秒。 |

## 评分结果

重点字段：

- `decision`：`pass`、`needs_refission`、`reject`。
- `score`：综合分。
- `problem_tags`：问题标签。
- `reason`：中文解释。
- `next_action`：建议动作。

## 运行 Demo

```bash
export PODI_BACKEND=http://114.55.0.56:8099
export PODI_API_KEY=业务方实际 Key
export PODI_IMAGE_URL=https://example.com/original.png
export PODI_GENERATED_IMAGE_URL=https://example.com/generated.png
python3 demo.py
```

## 常见错误

| 错误 | 处理 |
| --- | --- |
| `VL_EVAL_IMAGE_REQUIRED` | 补齐 `originalImageUrl` 和 `generatedImageUrl`。 |
| `BUSINESS_API_KEY_BUSINESS_NOT_ALLOWED` | 当前 Key 未授权裂变评分。 |
| `BUSINESS_RUN_TEMPORARY_UNAVAILABLE` | 稍后重试查询。 |
| `ABILITY_TASK_FAILED` | 记录 `runId/requestId/traceId` 给中台排查。 |
