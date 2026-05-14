# 接口 1：图裂变 · GPT Image 2 + VL 受控版

## 用途

输入一张原图，中台先做 VL 图像理解和提示词编译，再调用 GPT Image 2 生成同系列裂变图。该接口适合商业模型裂变测试和业务方快速接入。

## 接口

| 项 | 内容 |
| --- | --- |
| 提交 | `POST /api/business/fission/runs` |
| 查询 | `POST /api/business/runs/get` |
| 鉴权 | 请求头 `X-PODI-API-Key` |
| 固定版本 | `gpt-image2-vl-v2` |
| 输出数量 | 一次请求固定 1 张图 |

如果需要 3 张图，请提交 3 次，得到 3 个独立 `runId`。不要传 `count`、`n`、`batch_size`。

## 提交请求 JSON

```json
{
  "imageUrl": "https://example.com/input.png",
  "version": "gpt-image2-vl-v2",
  "prompt": "保留系列感，元素要明显变化",
  "variation_strength": "same_series",
  "quality": "preview",
  "size": "auto",
  "maskUrl": null,
  "source": "partner-api",
  "channel": "open-api",
  "requestId": "biz-gpt-image2-fission-001",
  "traceId": "trace-gpt-image2-fission-001"
}
```

## 参数说明

| 参数 | 必填 | 默认值 | 类型 | 说明 |
| --- | --- | --- | --- | --- |
| `imageUrl` | 是 | 无 | string | 原图 URL，必须能被中台访问。 |
| `version` | 否 | 当前默认版本 | string | 固定使用本接口时传 `gpt-image2-vl-v2`。 |
| `prompt` | 否 | 空 | string | 额外要求。不传也会使用 VL 分析结果和系统提示词运行。 |
| `variation_strength` | 否 | `same_series` | enum | 裂变幅度，枚举见下表。 |
| `quality` | 否 | `preview` | enum | 质量档位，枚举见下表。 |
| `size` | 否 | `auto` | enum | 默认按原图尺寸；只有传固定尺寸才改变画布。 |
| `maskUrl` | 否 | 空 | string/null | 蒙版图 URL；需要局部编辑时才传。 |
| `callbackUrl` | 否 | 空 | string | 终态回调地址；不传则轮询查询。 |
| `source` | 否 | `partner-api` | string | 调用来源标识，用于统计。 |
| `channel` | 否 | `open-api` | string | 调用渠道标识，用于区分业务系统、测评端或脚本。 |
| `requestId` | 否 | 中台生成 | string | 业务方请求 ID，建议每次唯一。 |
| `traceId` | 否 | 中台生成 | string | 链路 ID，便于跨系统排查。 |

## 枚举说明

`variation_strength`：

| 值 | 含义 | 建议 |
| --- | --- | --- |
| `conservative` | 保守裂变，尽量接近原图。 | 质量回归、低风险客户样本。 |
| `same_series` | 同系列裂变，保持风格同时有明显变化。 | 默认推荐。 |
| `creative_same_series` | 更开放的同系列变化。 | 探索新方向时使用。 |

`quality`：

| 值 | 含义 | 建议 |
| --- | --- | --- |
| `preview` | 快速预览档。 | 内部测试和批量初筛。 |
| `candidate` | 候选质量档。 | 需要交给业务方看效果时使用。 |
| `premium` | 高质量档。 | 成本更高，正式样张或重点样本使用。 |

`size`：

| 值 | 含义 |
| --- | --- |
| `auto` | 默认值，尽量跟随原图尺寸和比例。 |
| `1024x1024` | 正方形 1K。 |
| `1536x1024` | 横图。 |
| `1024x1536` | 竖图。 |
| `2048x2048` | 正方形 2K。 |
| `2048x1152` | 16:9 横图。 |
| `3840x2160` | 4K 横图。 |
| `2160x3840` | 4K 竖图。 |

## 提交返回 JSON

```json
{
  "runId": "run_gpt_image2_001",
  "taskId": "t1.fission.auto.8f7d2a",
  "businessKey": "fission",
  "version": "gpt-image2-vl-v2",
  "status": "queued",
  "taskStatus": "queued",
  "traceId": "trace-gpt-image2-fission-001",
  "requestId": "biz-gpt-image2-fission-001",
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
  "runId": "run_gpt_image2_001"
}
```

## 查询返回：排队中

```json
{
  "runId": "run_gpt_image2_001",
  "taskId": "t1.fission.auto.8f7d2a",
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
  "expectedImageCount": 1,
  "traceId": "trace-gpt-image2-fission-001",
  "requestId": "biz-gpt-image2-fission-001",
  "durationMs": null,
  "createdAt": "2026-05-14T10:00:00",
  "startedAt": "2026-05-14T10:00:02",
  "finishedAt": null
}
```

## 查询返回：成功

```json
{
  "runId": "run_gpt_image2_001",
  "taskId": "t1.fission.auto.8f7d2a",
  "status": "succeeded",
  "taskStatus": "succeeded",
  "imageUrl": "https://podiaidesign.oss-cn-hangzhou.aliyuncs.com/result-gpt-image2.png",
  "imageUrls": ["https://podiaidesign.oss-cn-hangzhou.aliyuncs.com/result-gpt-image2.png"],
  "videoUrl": null,
  "videoUrls": [],
  "text": "succeeded",
  "texts": [],
  "resultPayload": null,
  "error": null,
  "errorMessage": null,
  "errorCode": null,
  "debugResponse": null,
  "retryAfterSeconds": null,
  "expectedImageCount": 1,
  "traceId": "trace-gpt-image2-fission-001",
  "requestId": "biz-gpt-image2-fission-001",
  "durationMs": 62000,
  "createdAt": "2026-05-14T10:00:00",
  "startedAt": "2026-05-14T10:00:02",
  "finishedAt": "2026-05-14T10:01:02"
}
```

## 查询返回：失败

```json
{
  "runId": "run_gpt_image2_001",
  "taskId": "t1.fission.auto.8f7d2a",
  "status": "failed",
  "taskStatus": "failed",
  "imageUrl": null,
  "imageUrls": [],
  "videoUrl": null,
  "videoUrls": [],
  "text": "failed",
  "texts": [],
  "error": "上游商业模型执行失败，请稍后重试或联系中台排查。",
  "errorMessage": "上游商业模型执行失败，请稍后重试或联系中台排查。",
  "errorCode": "VENDOR_API_EXECUTION_FAILED",
  "debugResponse": "上游商业模型执行失败，请稍后重试或联系中台排查。",
  "retryAfterSeconds": null,
  "expectedImageCount": 1,
  "traceId": "trace-gpt-image2-fission-001",
  "requestId": "biz-gpt-image2-fission-001",
  "durationMs": 18000,
  "createdAt": "2026-05-14T10:00:00",
  "startedAt": "2026-05-14T10:00:02",
  "finishedAt": "2026-05-14T10:00:20"
}
```

## 常见错误

| 错误码 | 含义 | 处理 |
| --- | --- | --- |
| `BUSINESS_IMAGE_URL_REQUIRED` | 缺少 `imageUrl`。 | 补图后重新提交。 |
| `BUSINESS_API_KEY_INACTIVE` | Key 未启用。 | 联系中台启用或更换 Key。 |
| `BUSINESS_API_KEY_EXPIRED` | Key 已过期。 | 联系中台换 Key。 |
| `BUSINESS_API_KEY_BUSINESS_NOT_ALLOWED` | Key 未授权 `fission`。 | 联系中台调整授权范围。 |
| `BUSINESS_RUN_TEMPORARY_UNAVAILABLE` | 查询临时失败。 | 等待 5-10 秒后用同一 `runId` 重试查询，不要重复提交。 |
| `VENDOR_API_EXECUTION_FAILED` | GPT Image 2 执行失败。 | 记录 `runId/requestId/traceId` 给中台排查。 |
