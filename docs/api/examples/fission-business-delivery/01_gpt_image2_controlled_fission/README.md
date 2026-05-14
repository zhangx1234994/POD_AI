# 接口 1：图裂变 · GPT Image 2 受控版

## 用途

输入一张原图，先由中台做 VL 图像理解和提示词编译，再调用 GPT Image 2 生成同系列裂变图。

## 接口

- 提交：`POST /api/business/fission/runs`
- 查询：`POST /api/business/runs/get`
- 鉴权：`X-PODI-API-Key`
- 固定版本：`gpt-image2-vl-v2`
- 输出：一次请求固定 1 张图。如果要 3 张图，请提交 3 次，得到 3 个独立 `runId`。

## 参数

| 参数 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `imageUrl` | 是 | 无 | 原图 URL，必须能被中台访问。 |
| `version` | 否 | 当前默认版本 | 固定使用本接口时传 `gpt-image2-vl-v2`。 |
| `prompt` | 否 | 空 | 额外要求。不传也会用 VL 和系统提示词运行。 |
| `variation_strength` | 否 | `same_series` | 裂变幅度：`conservative`、`same_series`、`creative_same_series`。 |
| `quality` | 否 | `preview` | 质量档位：`preview`、`candidate`、`premium`。 |
| `size` | 否 | `auto` | 默认按原图尺寸回填；只有传固定尺寸才改变画布。 |
| `maskUrl` | 否 | 空 | 蒙版图 URL，需要局部编辑时传。 |
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
| `taskId` | 底层 OpenAI 图片编辑能力任务 ID，可能稍后才生成；业务方不需要依赖。 |
| `requestId` / `traceId` | 业务请求和链路 ID，用于把调用日志串起来。 |
| `debugUrl` | 可选的中台排障链接，没有则为空。 |

查询接口默认返回：

| 字段 | 说明 |
| --- | --- |
| `status` / `taskStatus` | `queued/running` 继续轮询；`succeeded` 表示可取图；`failed` 表示失败。 |
| `imageUrl` | 第一张结果图 URL。该接口固定一次返回 1 张。 |
| `imageUrls` | 结果图列表。业务方建议统一按数组处理。 |
| `error` / `errorMessage` | 失败原因。中台已脱敏，不会返回密钥或 SQL 原文。 |
| `errorCode` | 标准错误码，例如缺图、Key 无权限、上游失败。 |
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
| `BUSINESS_API_KEY_INACTIVE` / `BUSINESS_API_KEY_EXPIRED` | 联系中台启用或更换 Key。 |
| `BUSINESS_API_KEY_BUSINESS_NOT_ALLOWED` | 当前 Key 未授权图裂变。 |
| `BUSINESS_RUN_TEMPORARY_UNAVAILABLE` | 稍后重试查询，不要重新提交。 |
| `ABILITY_TASK_FAILED` / `VENDOR_API_EXECUTION_FAILED` | 记录 `runId/requestId/traceId` 给中台排查。 |
