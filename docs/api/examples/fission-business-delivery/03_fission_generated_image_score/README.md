# 接口 3：裂变生成图评估

## 用途

输入裂变前原图和裂变后结果图，让中台判断生成质量、逻辑合理性和是否建议二次裂变。

该接口只评分，不自动二次裂变。业务方如果需要“评分不通过就再裂变”，应在自己的业务逻辑中再次调用裂变接口。

## 接口

- 提交：`POST /api/business/fission-evaluate/runs`
- 查询：`POST /api/business/runs/get`
- 鉴权：`X-PODI-API-Key`
- 输出：结构化评分结果，通常读取 `resultPayload` 或 `texts`。

## 参数

| 参数 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `originalImageUrl` | 是 | 无 | 裂变前原图 URL。 |
| `generatedImageUrl` | 是 | 无 | 裂变后的结果图 URL。 |
| `context` | 否 | `{}` | 业务上下文，建议传裂变版本、提示词、重绘幅度、profile。 |
| `callbackUrl` | 否 | 空 | 终态回调地址；不传则用轮询查询结果。 |
| `requestId` | 否 | 自动生成 | 业务方请求 ID，建议每次唯一。 |
| `traceId` | 否 | 自动生成 | 业务方链路 ID，便于把评分和裂变任务关联。 |

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

