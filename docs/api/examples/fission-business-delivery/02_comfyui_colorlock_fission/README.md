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

