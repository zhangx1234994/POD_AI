# 接口 2：图裂变 · ComfyUI 颜色锁定版

## 用途

输入一张原图，中台先生成 VL 颜色控制卡，再调用 ComfyUI 颜色锁定裂变工作流。适合希望保留原图配色、边框和主体关系的图案裂变测试。

## 接口

- 提交：`POST /api/business/fission/runs`
- 查询：`POST /api/business/runs/get`
- 鉴权：`X-PODI-API-Key`
- 固定版本：`comfyui-vl-control-v2`
- 输出：一次请求 1 张图。

## 参数

| 参数 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `imageUrl` | 是 | 无 | 原图 URL，必须能被中台和 ComfyUI 访问。 |
| `version` | 否 | 当前默认版本 | 固定使用本接口时传 `comfyui-vl-control-v2`。 |
| `bili` | 否 | `15%` | 重绘幅度，不是相似度。值越大变化越明显；颜色锁定版建议 0%-20%。 |
| `width` | 否 | 跟随原图 | 输出宽度。手动填写时只填数字，不带 px。 |
| `height` | 否 | 跟随原图 | 输出高度。手动填写时只填数字，不带 px。 |
| `profile` | 否 | `pattern_color_lock_v2` | 颜色锁定配置；严格保色可传 `pattern_color_lock_strict_v2`。 |
| `prompt` | 否 | 空 | 额外要求。不要写“放开配色”或“重新设计色彩”类要求。 |
| `callbackUrl` | 否 | 空 | 终态回调地址；不传则用轮询查询结果。 |
| `source` | 否 | `partner-api` | 调用来源标识，便于中台统计。 |
| `channel` | 否 | `open-api` | 调用渠道标识，便于区分业务系统、测评端或脚本。 |
| `requestId` | 否 | 自动生成 | 业务方请求 ID，建议每次唯一。 |
| `traceId` | 否 | 自动生成 | 业务方链路 ID，便于排查。 |

## 返回字段

提交接口返回：

| 字段 | 说明 |
| --- | --- |
| `runId` | 业务任务 ID。后续轮询、排障和回调关联都用它。 |
| `status` / `taskStatus` | 当前状态。提交成功时通常是 `queued` 或 `running`。 |
| `taskId` | 底层 ComfyUI 工作流任务 ID，可能稍后才生成；业务方不需要依赖。 |
| `requestId` / `traceId` | 业务请求和链路 ID，用于把调用日志串起来。 |
| `debugUrl` | 可选的中台排障链接，没有则为空。 |

查询接口默认返回：

| 字段 | 说明 |
| --- | --- |
| `status` / `taskStatus` | `queued/running` 继续轮询；`succeeded` 表示可取图；`failed` 表示失败。 |
| `imageUrl` | 第一张结果图 URL。该接口固定一次返回 1 张。 |
| `imageUrls` | 结果图列表。业务方建议统一按数组处理。 |
| `expectedImageCount` | 预计出图数量，当前通常为 1。 |
| `error` / `errorMessage` | 失败原因。中台已脱敏，不会返回密钥或 SQL 原文。 |
| `errorCode` | 标准错误码，例如缺图、队列超时、ComfyUI 执行失败。 |
| `debugResponse` | 给业务方看的简短排障提示。 |
| `retryAfterSeconds` | 建议下次轮询等待秒数；为空时每 5-10 秒查一次。 |
| `durationMs` | 任务耗时，单位毫秒。 |

## 运行 Demo

```bash
export PODI_BACKEND=http://114.55.0.56:8099
export PODI_API_KEY=业务方实际 Key
export PODI_IMAGE_URL=https://example.com/input.png
python3 demo.py
```

## 常见错误

| 错误 | 处理 |
| --- | --- |
| `BUSINESS_IMAGE_URL_REQUIRED` | 补 `imageUrl` 后重新提交。 |
| `BUSINESS_API_KEY_BUSINESS_NOT_ALLOWED` | 当前 Key 未授权图裂变。 |
| `COMFYUI_TIMEOUT` | 稍后重试或联系中台查看 ComfyUI 队列。 |
| `COMFYUI_IMAGE_REQUIRED` | 确认原图 URL 可访问。 |
| `ABILITY_TASK_FAILED` | 记录 `runId/requestId/traceId` 给中台排查。 |
