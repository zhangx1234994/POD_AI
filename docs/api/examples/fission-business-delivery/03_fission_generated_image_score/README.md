# 接口 3：裂变生成图评估

## 用途

输入裂变前原图和裂变后结果图，让中台判断生成质量、逻辑合理性和是否建议二次裂变。

该接口只评分，不自动二次裂变。业务方如果需要“评分不通过就再裂变”，应在自己的业务逻辑中再次调用裂变接口。

权威口径：参数枚举以 `docs/standards/business-api-enums.md` 为准，错误码以 `docs/standards/error-catalog.md` 为准。本页只保留业务方可直接使用的摘要和示例。

## 接口

| 项 | 内容 |
| --- | --- |
| 提交 | `POST /api/business/fission-evaluate/runs` |
| 兼容提交 | `POST /api/business/fission/evaluate/runs` |
| 查询 | `POST /api/business/runs/get` |
| 鉴权 | 请求头 `X-PODI-API-Key` |
| 输出 | 文本评分 + 轻量结构化 `resultPayload` |

## 提交请求 JSON

```json
{
  "originalImageUrl": "https://example.com/original.png",
  "generatedImageUrl": "https://example.com/generated.png",
  "context": {
    "business": "fission",
    "version": "comfyui-vl-control-v2",
    "prompt": "保持系列感，元素要明显变化",
    "bili": "80%",
    "profile": "pattern_risk_routed_v4"
  },
  "source": "partner-api",
  "channel": "open-api",
  "requestId": "biz-fission-score-001",
  "traceId": "trace-fission-score-001"
}
```

## 参数说明

| 参数 | 必填 | 默认值 | 类型 | 说明 |
| --- | --- | --- | --- | --- |
| `originalImageUrl` | 是 | 无 | string | 裂变前原图 URL。 |
| `generatedImageUrl` | 是 | 无 | string | 裂变后的结果图 URL。 |
| `context` | 否 | `{}` | object/string | 业务上下文，建议传裂变版本、提示词、重绘幅度、profile。 |
| `callbackUrl` | 否 | 空 | string | 终态回调地址；不传则轮询查询。 |
| `source` | 否 | `partner-api` | string | 调用来源标识，用于统计。 |
| `channel` | 否 | `open-api` | string | 调用渠道标识，用于区分业务系统、测评端或脚本。 |
| `requestId` | 否 | 中台生成 | string | 业务方请求 ID，建议每次唯一。 |
| `traceId` | 否 | 中台生成 | string | 链路 ID，建议与对应裂变任务共用或可关联。 |

## 评分枚举说明

`decision`：

| 值 | 含义 | 业务方处理 |
| --- | --- | --- |
| `pass` | 通过。 | 可以进入业务验收或后续流程。 |
| `needs_refission` | 建议二次裂变。 | 可再次调用裂变接口，或人工复核。 |
| `reject` | 不通过。 | 不建议继续使用该结果图。 |

`next_action.type`：

| 值 | 含义 |
| --- | --- |
| `accept` | 接受当前结果。 |
| `refission_repeat` | 建议重复裂变。 |
| `reject` | 拒绝当前结果。 |

## 提交返回 JSON

```json
{
  "runId": "run_score_001",
  "taskId": "t1.fission_evaluate.auto.7a12",
  "businessKey": "fission_evaluate",
  "version": "generated-image-eval-v1",
  "status": "queued",
  "taskStatus": "queued",
  "traceId": "trace-fission-score-001",
  "requestId": "biz-fission-score-001",
  "debugUrl": null,
  "debugResponse": null,
  "retryAfterSeconds": 10,
  "error": null,
  "errorMessage": null,
  "errorCode": null,
  "createdAt": "2026-05-14T10:00:00"
}
```

## 查询请求 JSON

```json
{
  "runId": "run_score_001"
}
```

## 查询返回：排队中

```json
{
  "runId": "run_score_001",
  "taskId": "t1.fission_evaluate.auto.7a12",
  "status": "running",
  "taskStatus": "running",
  "imageUrl": null,
  "imageUrls": [],
  "videoUrl": null,
  "videoUrls": [],
  "text": "running",
  "texts": [],
  "error": null,
  "errorMessage": null,
  "errorCode": null,
  "debugResponse": null,
  "retryAfterSeconds": 10,
  "expectedImageCount": null,
  "traceId": "trace-fission-score-001",
  "requestId": "biz-fission-score-001",
  "durationMs": null,
  "createdAt": "2026-05-14T10:00:00",
  "startedAt": "2026-05-14T10:00:02",
  "finishedAt": null
}
```

## 查询返回：成功

```json
{
  "runId": "run_score_001",
  "taskId": "t1.fission_evaluate.auto.7a12",
  "status": "succeeded",
  "taskStatus": "succeeded",
  "imageUrl": null,
  "imageUrls": [],
  "videoUrl": null,
  "videoUrls": [],
  "text": "{\"decision\":\"needs_refission\",\"score\":65,\"reason\":\"主体关系有偏移，建议二次裂变。\"}",
  "texts": [
    "{\"decision\":\"needs_refission\",\"score\":65,\"reason\":\"主体关系有偏移，建议二次裂变。\"}"
  ],
  "resultPayload": {
    "decision": "needs_refission",
    "score": 65,
    "scores": {
      "shape": 70,
      "material": 62,
      "scale": 66,
      "logic": 60
    },
    "problem_tags": ["结构偏移", "图案密度变化"],
    "reason": "主体关系有偏移，建议二次裂变。",
    "next_action": {
      "type": "refission_repeat",
      "repeat": 2,
      "route_action": "needs_refission"
    }
  },
  "error": null,
  "errorMessage": null,
  "errorCode": null,
  "debugResponse": null,
  "retryAfterSeconds": null,
  "expectedImageCount": null,
  "traceId": "trace-fission-score-001",
  "requestId": "biz-fission-score-001",
  "durationMs": 26000,
  "createdAt": "2026-05-14T10:00:00",
  "startedAt": "2026-05-14T10:00:02",
  "finishedAt": "2026-05-14T10:00:28"
}
```

## 查询返回：失败

```json
{
  "runId": "run_score_001",
  "taskId": "t1.fission_evaluate.auto.7a12",
  "status": "failed",
  "taskStatus": "failed",
  "imageUrl": null,
  "imageUrls": [],
  "videoUrl": null,
  "videoUrls": [],
  "text": "failed",
  "texts": [],
  "error": "裂变评分失败，请稍后重试或联系中台排查。",
  "errorMessage": "裂变评分失败，请稍后重试或联系中台排查。",
  "errorCode": "ABILITY_TASK_FAILED",
  "debugResponse": "裂变评分失败，请稍后重试或联系中台排查。",
  "retryAfterSeconds": null,
  "expectedImageCount": null,
  "traceId": "trace-fission-score-001",
  "requestId": "biz-fission-score-001",
  "durationMs": 12000,
  "createdAt": "2026-05-14T10:00:00",
  "startedAt": "2026-05-14T10:00:02",
  "finishedAt": "2026-05-14T10:00:14"
}
```

## 常见错误

| 错误码 | 含义 | 处理 |
| --- | --- | --- |
| `VL_EVAL_IMAGE_REQUIRED` | 缺少 `originalImageUrl` 或 `generatedImageUrl`。 | 补齐两张图后重新提交。 |
| `BUSINESS_API_KEY_BUSINESS_NOT_ALLOWED` | Key 未授权 `fission_evaluate`。 | 联系中台调整授权范围。 |
| `BUSINESS_RUN_TEMPORARY_UNAVAILABLE` | 查询临时失败。 | 等待 5-10 秒后用同一 `runId` 重试查询。 |
| `ABILITY_TASK_FAILED` | 评分能力执行失败。 | 记录 `runId/requestId/traceId` 给中台排查。 |
