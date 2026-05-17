# 接口 2：图裂变 · ComfyUI 颜色锁定版

## 用途

输入一张原图，中台先生成 VL 图案风险控制卡，再调用 ComfyUI 智能路由裂变工作流。该接口适合验证“对象级变化”和“原图配色、疏密、结构稳定性”。

权威口径：参数枚举以 `docs/standards/business-api-enums.md` 为准，错误码以 `docs/standards/error-catalog.md` 为准。本页只保留业务方可直接使用的摘要和示例。

## 接口

| 项 | 内容 |
| --- | --- |
| 提交 | `POST /api/business/fission/runs` |
| 查询 | `POST /api/business/runs/get` |
| 鉴权 | 请求头 `X-PODI-API-Key` |
| 固定版本 | `comfyui-vl-control-v2` |
| 输出数量 | 一次请求固定 1 张图 |

如果需要多张结果图，请提交多次。不要传 `count`、`n`、`batch_size`。

## 提交请求 JSON

```json
{
  "imageUrl": "https://example.com/input.png",
  "version": "comfyui-vl-control-v2",
  "bili": "80%",
  "width": 2000,
  "height": 2000,
  "profile": "pattern_risk_routed_v4",
  "variation_preset": "default-high",
  "reference_lock": 0.42,
  "color_lock": 0.9,
  "prompt": "保持原图主色，不要改成新的色系",
  "source": "partner-api",
  "channel": "open-api",
  "requestId": "biz-comfyui-colorlock-001",
  "traceId": "trace-comfyui-colorlock-001"
}
```

## 参数说明

| 参数 | 必填 | 默认值 | 类型 | 说明 |
| --- | --- | --- | --- | --- |
| `imageUrl` | 是 | 无 | string | 原图 URL，必须能被中台和 ComfyUI 访问。 |
| `version` | 否 | 当前默认版本 | string | 固定使用本接口时传 `comfyui-vl-control-v2`。 |
| `bili` | 否 | `80%` | string/number | 重绘幅度，不是相似度。值越大变化越明显。只做建议区间，不做硬限制。 |
| `width` | 否 | 跟随原图 | number | 输出宽度。手动填写时只填数字，不带 `px`。 |
| `height` | 否 | 跟随原图 | number | 输出高度。手动填写时只填数字，不带 `px`。 |
| `profile` | 否 | `pattern_risk_routed_v4` | enum | 裂变路由配置，枚举见下表。 |
| `variation_preset` | 否 | `default-high` | enum | 便于测评和业务选参数组合，枚举见下表。 |
| `reference_lock` | 否 | `0.42` | number | 原图结构保留度。越高越像原图，裂变感更弱；建议 0.34-0.50，不做硬限制。 |
| `color_lock` | 否 | `0.90` | number | 颜色锁定强度。越高越不容易偏色；建议 0.75-1.00，不做硬限制。 |
| `prompt` | 否 | 空 | string | 额外要求。不要写“放开配色”或“重新设计色彩”类要求，除非明确要测试偏色风险。 |
| `callbackUrl` | 否 | 空 | string | 终态回调地址；不传则轮询查询。 |
| `source` | 否 | `partner-api` | string | 调用来源标识，用于统计。 |
| `channel` | 否 | `open-api` | string | 调用渠道标识，用于区分业务系统、测评端或脚本。 |
| `requestId` | 否 | 中台生成 | string | 业务方请求 ID，建议每次唯一。 |
| `traceId` | 否 | 中台生成 | string | 链路 ID，便于跨系统排查。 |

## 枚举说明

`profile`：

| 值 | 含义 | 建议 |
| --- | --- | --- |
| `pattern_risk_routed_v4` | 智能风险路由，按 VL 判断图案类型和风险后选择控制策略。 | 默认推荐。 |
| `pattern_color_lock_v2` | 颜色锁定基础版。 | 老样本对照或回归测试。 |
| `pattern_color_lock_strict_v2` | 更严格的颜色锁定。 | 颜色漂移明显的样本。 |

`variation_preset`：

| 值 | 对应组合 | 使用场景 |
| --- | --- | --- |
| `default-high` | `bili=80%`、`reference_lock=0.42`、`color_lock=0.90` | 高幅度默认，适合对象可分离的图案。 |
| `safe` | `bili=30%`、`reference_lock=0.50`、`color_lock=1.00` | 保守稳定，更接近原图。 |
| `object-strong` | `bili=100%`、`reference_lock=0.34`、`color_lock=0.90` | 对象变化更强，适合探索明显裂变方向。 |
| `color-free` | `bili=80%`、`reference_lock=0.42`、`color_lock=0.75` | 配色更自由，用于测试颜色变化空间。 |

`bili` 推荐口径：

| 值 | 含义 |
| --- | --- |
| `30%` | 低重绘，变化小。 |
| `60%` | 中等重绘。 |
| `80%` | 高重绘，默认推荐。 |
| `100%` 或更高 | 极高重绘，变化更明显，稳定性风险也更高。 |

## 提交返回 JSON

```json
{
  "runId": "run_comfyui_001",
  "taskId": "t1.fission.auto.3c8d2a",
  "businessKey": "fission",
  "version": "comfyui-vl-control-v2",
  "status": "queued",
  "taskStatus": "queued",
  "traceId": "trace-comfyui-colorlock-001",
  "requestId": "biz-comfyui-colorlock-001",
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
  "runId": "run_comfyui_001"
}
```

## 查询返回：排队中

```json
{
  "runId": "run_comfyui_001",
  "taskId": "t1.fission.auto.3c8d2a",
  "status": "queued",
  "taskStatus": "queued",
  "imageUrl": null,
  "imageUrls": [],
  "videoUrl": null,
  "videoUrls": [],
  "text": "queued",
  "texts": [],
  "error": null,
  "errorMessage": null,
  "errorCode": null,
  "debugResponse": null,
  "retryAfterSeconds": 10,
  "expectedImageCount": 1,
  "traceId": "trace-comfyui-colorlock-001",
  "requestId": "biz-comfyui-colorlock-001",
  "durationMs": null,
  "createdAt": "2026-05-14T10:00:00",
  "startedAt": null,
  "finishedAt": null
}
```

## 查询返回：成功

```json
{
  "runId": "run_comfyui_001",
  "taskId": "t1.fission.auto.3c8d2a",
  "status": "succeeded",
  "taskStatus": "succeeded",
  "imageUrl": "https://podiaidesign.oss-cn-hangzhou.aliyuncs.com/result-comfyui.png",
  "imageUrls": ["https://podiaidesign.oss-cn-hangzhou.aliyuncs.com/result-comfyui.png"],
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
  "traceId": "trace-comfyui-colorlock-001",
  "requestId": "biz-comfyui-colorlock-001",
  "durationMs": 91000,
  "createdAt": "2026-05-14T10:00:00",
  "startedAt": "2026-05-14T10:00:02",
  "finishedAt": "2026-05-14T10:01:31"
}
```

## 查询返回：失败

```json
{
  "runId": "run_comfyui_001",
  "taskId": "t1.fission.auto.3c8d2a",
  "status": "failed",
  "taskStatus": "failed",
  "imageUrl": null,
  "imageUrls": [],
  "videoUrl": null,
  "videoUrls": [],
  "text": "failed",
  "texts": [],
  "error": "ComfyUI 当前排队或执行失败，请稍后重试。",
  "errorMessage": "ComfyUI 当前排队或执行失败，请稍后重试。",
  "errorCode": "COMFYUI_TIMEOUT",
  "debugResponse": "ComfyUI 当前排队或执行失败，请稍后重试。",
  "retryAfterSeconds": null,
  "expectedImageCount": 1,
  "traceId": "trace-comfyui-colorlock-001",
  "requestId": "biz-comfyui-colorlock-001",
  "durationMs": 480000,
  "createdAt": "2026-05-14T10:00:00",
  "startedAt": "2026-05-14T10:00:02",
  "finishedAt": "2026-05-14T10:08:00"
}
```

## 常见错误

| 错误码 | 含义 | 处理 |
| --- | --- | --- |
| `BUSINESS_IMAGE_URL_REQUIRED` | 缺少 `imageUrl`。 | 补图后重新提交。 |
| `BUSINESS_API_KEY_BUSINESS_NOT_ALLOWED` | Key 未授权 `fission`。 | 联系中台调整授权范围。 |
| `COMFYUI_TIMEOUT` | ComfyUI 队列或执行超时。 | 稍后重试；若连续出现，给中台 `runId/requestId/traceId`。 |
| `COMFYUI_IMAGE_REQUIRED` | 原图无法访问或下载失败。 | 确认图片 URL 是公网可访问地址。 |
| `ABILITY_TASK_FAILED` | 底层能力执行失败。 | 记录 `runId/requestId/traceId` 给中台排查。 |
