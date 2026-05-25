# 接口：图编辑 · GPT Image 2 通用改图

## 用途

输入一张主图，中台按 `editSkill`、编辑指令、软标注、参考图或 mask 编译编辑请求，再调用 GPT Image 2 生成结果图。该接口适合局部修改、参考图替换、删除修补、补色校正和扩展画布。

权威口径：参数枚举以 `docs/standards/business-api-enums.md` 为准，错误码以 `docs/standards/error-catalog.md` 为准。本页只保留业务方可直接使用的摘要和示例。

## 接口

| 项 | 内容 |
| --- | --- |
| 提交 | `POST /api/business/image-edit/runs` |
| 查询 | `POST /api/business/runs/get` |
| 鉴权 | 请求头 `X-PODI-API-Key` |
| 固定版本 | `gpt-image2-editor-v1` |
| 输出数量 | 一次请求固定 1 张图 |

业务方需要新的编辑结果时应重新提交，得到新的 `runId`。不要传 `count`、`n` 或 `batch_size`。

## 提交请求 JSON

```json
{
  "imageUrl": "https://example.com/edit-input.png",
  "version": "gpt-image2-editor-v1",
  "editSkill": "local_modify",
  "instruction": "把杯子上的蓝色花纹改成红色，保持杯子形状和背景不变",
  "selectionHints": [
    {
      "type": "box",
      "label": "杯子花纹区域",
      "x": 0.36,
      "y": 0.42,
      "width": 0.28,
      "height": 0.22
    }
  ],
  "referenceImages": [],
  "maskUrl": null,
  "quality": "preview",
  "size": "auto",
  "image_edit.output_format": "png",
  "source": "partner-api",
  "channel": "open-api",
  "requestId": "biz-image-edit-001",
  "traceId": "trace-image-edit-001"
}
```

## 参数说明

| 参数 | 必填 | 默认值 | 类型 | 说明 |
| --- | --- | --- | --- | --- |
| `imageUrl` | 是 | 无 | string | 主图 URL，必须能被中台访问。 |
| `version` | 否 | 当前默认版本 | string | 固定使用本接口时传 `gpt-image2-editor-v1`。 |
| `editSkill` | 否 | `local_modify` | enum | 改图技能，见枚举说明。 |
| `instruction` | 条件必填 | 空 | string | 普通改图指令；`canvas_outpaint` 可省略。 |
| `selectionHints` | 否 | `[]` | array | 点选、框选、圆选等软标注；坐标建议使用 0-1 相对值。 |
| `referenceImages` | 条件必填 | `[]` | array | 参考图列表；参考图替换和补色校正必须传。 |
| `maskUrl` | 否 | 空 | string/null | 单个最终 Alpha mask；尺寸必须与主图一致。 |
| `quality` | 否 | `preview` | enum | 质量档位，见枚举说明。 |
| `size` | 否 | `auto` | enum/string | 输出尺寸。可用预设或满足约束的自定义 `宽x高`。 |
| `image_edit.output_format` | 否 | `png` | enum | 输出格式，兼容字段为 `output_format`。 |
| `callbackUrl` | 否 | 空 | string | 终态回调地址；不传则轮询查询。 |
| `source` | 否 | `partner-api` | string | 调用来源标识，用于统计。 |
| `channel` | 否 | `open-api` | string | 调用渠道标识。 |
| `requestId` | 否 | 中台生成 | string | 业务方请求 ID，建议每次唯一。 |
| `traceId` | 否 | 中台生成 | string | 链路 ID，便于跨系统排查。 |

## 枚举说明

`editSkill`：

| 值 | 含义 | 额外要求 |
| --- | --- | --- |
| `local_modify` | 局部修改。 | 需要 `instruction`；建议传 `selectionHints` 或 `maskUrl`。 |
| `reference_element_transfer` | 参考图替换。 | 必须传 `referenceImages`。 |
| `remove_inpaint` | 删除修补。 | 必须传 `selectionHints` 或 `maskUrl`。 |
| `color_reference_correction` | 补色校正。 | 必须传 `referenceImages`。 |
| `canvas_outpaint` | 扩展画布。 | 可传 `expand_left/right/top/bottom` 或 `targetWidth/targetHeight`。 |

`quality`：

| 值 | 含义 |
| --- | --- |
| `auto` | 自动档。 |
| `preview` | 快速预览档。 |
| `production` | 正式候选档。 |
| `premium` | 高质量档，成本更高。 |

`size`：

| 值 | 含义 |
| --- | --- |
| `auto` | 跟随原图或由模型自动选择。 |
| `1024x1024` / `1536x1024` / `1024x1536` | 常用 1K 预设。 |
| `2048x2048` / `2048x1152` | 2K 预设。 |
| `3840x2160` / `2160x3840` | 4K 预设，高耗时高成本。 |
| 自定义 `宽x高` | 最大边不超过 3840，边长必须是 16 的倍数。 |

`image_edit.output_format`：

| 值 | 含义 |
| --- | --- |
| `png` | 默认输出格式。 |
| `jpeg` | 更小文件，不保留透明度。 |
| `webp` | 内部页面或支持 WebP 的业务可用。 |

## 提交返回 JSON

```json
{
  "runId": "run_image_edit_001",
  "taskId": "t1.image_edit.auto.8f7d2a",
  "businessKey": "image_edit",
  "version": "gpt-image2-editor-v1",
  "status": "queued",
  "taskStatus": "queued",
  "traceId": "trace-image-edit-001",
  "requestId": "biz-image-edit-001",
  "debugUrl": null,
  "debugResponse": null,
  "retryAfterSeconds": 10,
  "error": null,
  "errorMessage": null,
  "errorCode": null,
  "createdAt": "2026-05-25T10:00:00"
}
```

## 查询请求 JSON

```json
{
  "runId": "run_image_edit_001"
}
```

## 查询返回：排队或执行中

```json
{
  "runId": "run_image_edit_001",
  "taskId": "t1.image_edit.auto.8f7d2a",
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
  "traceId": "trace-image-edit-001",
  "requestId": "biz-image-edit-001",
  "durationMs": null,
  "createdAt": "2026-05-25T10:00:00",
  "startedAt": "2026-05-25T10:00:02",
  "finishedAt": null
}
```

## 查询返回：成功

```json
{
  "runId": "run_image_edit_001",
  "taskId": "t1.image_edit.auto.8f7d2a",
  "status": "succeeded",
  "taskStatus": "succeeded",
  "imageUrl": "https://podiaidesign.oss-cn-hangzhou.aliyuncs.com/result-image-edit.png",
  "imageUrls": ["https://podiaidesign.oss-cn-hangzhou.aliyuncs.com/result-image-edit.png"],
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
  "traceId": "trace-image-edit-001",
  "requestId": "biz-image-edit-001",
  "durationMs": 42000,
  "createdAt": "2026-05-25T10:00:00",
  "startedAt": "2026-05-25T10:00:02",
  "finishedAt": "2026-05-25T10:00:44"
}
```

## 查询返回：失败

```json
{
  "runId": "run_image_edit_001",
  "taskId": "t1.image_edit.auto.8f7d2a",
  "status": "failed",
  "taskStatus": "failed",
  "imageUrl": null,
  "imageUrls": [],
  "videoUrl": null,
  "videoUrls": [],
  "text": "failed",
  "texts": [],
  "error": "图编辑缺少参考图",
  "errorMessage": "图编辑缺少参考图",
  "errorCode": "IMAGE_EDIT_REFERENCE_REQUIRED",
  "debugResponse": "reference_element_transfer 或 color_reference_correction 必须传 referenceImages",
  "retryAfterSeconds": null,
  "expectedImageCount": 1,
  "traceId": "trace-image-edit-001",
  "requestId": "biz-image-edit-001",
  "durationMs": 120,
  "createdAt": "2026-05-25T10:00:00",
  "startedAt": "2026-05-25T10:00:00",
  "finishedAt": "2026-05-25T10:00:00"
}
```

## 常见错误

| 错误码 | 场景 | 业务方处理 |
| --- | --- | --- |
| `IMAGE_EDIT_INSTRUCTION_REQUIRED` | 普通改图未传 `instruction`。 | 补充明确编辑指令。 |
| `IMAGE_EDIT_SKILL_INVALID` | `editSkill` 不在允许枚举内。 | 改用本文档列出的技能。 |
| `IMAGE_EDIT_REFERENCE_REQUIRED` | 参考图替换或补色校正未传参考图。 | 补传 `referenceImages`。 |
| `IMAGE_EDIT_TARGET_REQUIRED` | 删除修补缺少目标区域。 | 补传 `selectionHints` 或 `maskUrl`。 |
| `IMAGE_EDIT_CANVAS_TOO_SMALL` | 扩展画布目标尺寸太小。 | 调整扩展边距或目标尺寸。 |
| `VENDOR_API_EXECUTION_FAILED` | GPT Image 2 执行失败。 | 可重试；持续失败时提供 `runId` 给中台排查。 |
