# 图裂变业务接口交付材料模板

本目录是给业务方交付包的 Git 内模板，不包含真实 Key。正式交付时复制本目录到交付目录，补充受控的 `business_api_key.env`，再压缩给业务方。

权威口径：

- 参数枚举以 `docs/standards/business-api-enums.md` 为准。
- 错误码以 `docs/standards/error-catalog.md` 为准。
- 如果本交付包与上述两份文档不一致，先修正真源和交付包，再发给业务方。

## 交付内容

| 目录 | 接口 | 说明 |
| --- | --- | --- |
| `01_gpt_image2_controlled_fission/` | `POST /api/business/fission/runs` | GPT Image 2 + VL 受控裂变，一次请求固定生成 1 张图。 |
| `02_comfyui_colorlock_fission/` | `POST /api/business/fission/runs` | ComfyUI 颜色锁定裂变，按 VL 图案类型智能路由，一次请求固定生成 1 张图。 |
| `03_fission_generated_image_score/` | `POST /api/business/fission-evaluate/runs` | 裂变生成图评分，只评分，不自动二次裂变。 |

## 统一接入方式

业务方只需要理解两个动作：

1. 调用提交接口，保存返回的 `runId`。
2. 每 5-10 秒调用 `POST /api/business/runs/get` 查询结果，直到 `status` 变成 `succeeded` 或 `failed`。

鉴权请求头：

```http
X-PODI-API-Key: <业务 Key>
```

Key 授权范围：

| 接口 | 需要授权 |
| --- | --- |
| GPT Image 2 + VL 受控裂变 | `fission` |
| ComfyUI 颜色锁定裂变 | `fission` |
| 裂变生成图评分 | `fission_evaluate` |

## 统一状态

| 状态 | 含义 | 业务方处理 |
| --- | --- | --- |
| `queued` | 已进入队列，尚未执行。 | 继续轮询。 |
| `running` | 正在执行或等待底层能力返回。 | 继续轮询。 |
| `succeeded` | 已成功完成。 | 读取 `imageUrls`、`texts` 或 `resultPayload`。 |
| `failed` | 执行失败。 | 记录 `runId/requestId/traceId/errorCode` 给中台排查。 |

## 统一提交返回

```json
{
  "runId": "run_20260514_xxx",
  "taskId": "t1.fission.auto.xxx",
  "businessKey": "fission",
  "version": "comfyui-vl-control-v2",
  "status": "queued",
  "taskStatus": "queued",
  "traceId": "trace-demo-001",
  "requestId": "req-demo-001",
  "debugUrl": null,
  "debugResponse": null,
  "retryAfterSeconds": 10,
  "error": null,
  "errorMessage": null,
  "errorCode": null,
  "createdAt": "2026-05-14T10:00:00"
}
```

| 字段 | 说明 |
| --- | --- |
| `runId` | 业务任务 ID。业务方必须保存，用它查询结果、排查问题和关联回调。 |
| `taskId` | 兼容旧 Coze 轮询的任务 ID。业务方可以不依赖它，优先保存 `runId`。 |
| `businessKey` | 业务类型，例如 `fission`、`fission_evaluate`。 |
| `version` | 本次命中的业务版本。 |
| `status` / `taskStatus` | 当前任务状态，含义一致。 |
| `traceId` | 调用链路 ID，用于跨系统排查。 |
| `requestId` | 业务方请求 ID，建议每次唯一。 |
| `retryAfterSeconds` | 建议下次轮询等待秒数。 |
| `error/errorMessage/errorCode` | 失败时才有值；提交成功通常为空。 |

提交接口默认不会返回 `routeInfo`、`steps`、`requestPayload`、`costBreakdown` 等内部排障字段。

## 统一查询请求

```json
{
  "runId": "run_20260514_xxx"
}
```

兼容字段：

| 字段 | 说明 |
| --- | --- |
| `runId` | 推荐字段。 |
| `taskId` | 兼容旧链路；可以把 `runId` 填到这里查询。 |
| `detail` | 普通业务不要传；传 `full` 会返回底层步骤和排障细节，返回体会变大。 |
| `includeDebug` | 普通业务不要传；`true` 等同于完整排障模式。 |

旧 Coze 轮询兼容：`/api/coze/podi/tasks/get` 也可以用业务 `runId` 查询，但正式交付文档推荐使用 `/api/business/runs/get`。

## 统一查询返回

```json
{
  "runId": "run_20260514_xxx",
  "taskId": "t1.fission.auto.xxx",
  "status": "succeeded",
  "taskStatus": "succeeded",
  "imageUrl": "https://podiaidesign.oss-cn-hangzhou.aliyuncs.com/result.png",
  "imageUrls": ["https://podiaidesign.oss-cn-hangzhou.aliyuncs.com/result.png"],
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
  "traceId": "trace-demo-001",
  "requestId": "req-demo-001",
  "durationMs": 82000,
  "createdAt": "2026-05-14T10:00:00",
  "startedAt": "2026-05-14T10:00:02",
  "finishedAt": "2026-05-14T10:01:22"
}
```

| 字段 | 说明 |
| --- | --- |
| `imageUrl` | 第一张结果图 URL。两个裂变接口固定一次 1 张。 |
| `imageUrls` | 结果图数组。建议业务方统一按数组处理。 |
| `texts` | 文本结果数组。评分接口优先读取这里。 |
| `resultPayload` | 轻量结构化结果。评分接口会返回 `decision/score/problem_tags/reason/next_action`。 |
| `debugResponse` | 给业务方看的轻量排障提示，不包含密钥、SQL 原文或大段内部响应。 |
| `expectedImageCount` | 预计结果数量。两个裂变接口当前固定为 1。 |

## 单图输出约定

两个裂变生成接口都固定为“一个请求、一个 `runId`、一张结果图”。如果业务方要测 3 张图，需要提交 3 次，得到 3 个独立 `runId`。不要传 `count`、`n`、`batch_size`、`generateCount`、`variantCount` 等批量字段；中台执行层会忽略这些字段。

## 文档规范

后续交付业务方的接口材料必须包含：

- 提交请求 JSON。
- 查询请求 JSON。
- 提交返回 JSON。
- 查询排队中、成功、失败三种返回 JSON。
- 参数表：字段名、是否必填、默认值、类型、说明。
- 枚举表：每个枚举值的中文含义和使用建议。
- 错误码表：业务方可自行处理的动作。

默认不再给业务方交付 Python 脚本。需要可运行脚本时另开“调试工具包”，不能混进正式接口材料里。
