# 图编辑业务接口与组件接入说明（内部版）

适用对象：内部业务方、测试同学、中台维护人员。

业务名：图编辑  
业务 Key：`image_edit`  
当前版本：`gpt-image2-editor-v1`  
提交接口：`POST /api/business/image-edit/runs`  
查询接口：`POST /api/business/runs/get`

## 1. 这个能力解决什么

图编辑不是单个裸模型接口，而是“组件工作台 + 中台业务 API + GPT Image 2 图片编辑能力”的组合业务。

业务方不要直接调用 OpenAI。业务方只需要把主图、编辑指令、可选标注、可选参考图、可选蒙版提交给中台；中台负责编译提示词、调用 GPT Image 2、落 OSS、记录 runId、记录成本和错误。

第一版只做单图编辑，不做 Photoshop 式多图层画布。一次提交固定生成 1 张结果图；业务方需要多张结果时，多次提交并分别保存 runId。

## 2. API Key

生产环境不要把真实 Key 写进仓库或交付文档。上线前由中台生成只允许访问 `image_edit` 的业务 Key。

示例命令：

```bash
cd /srv/pod/backend
python scripts/create_business_api_key.py \
  --id biz_key_image_edit_internal_001 \
  --name "内部图编辑测试 Key" \
  --tenant-id internal \
  --client-id image-edit-internal \
  --allowed-business-key image_edit
```

请求头：

```http
X-PODI-API-Key: <中台生成的 key>
```

## 3. 组件接入边界

内部客户有两种接入方式：

| 方式 | 说明 | 当前建议 |
| --- | --- | --- |
| 中台托管组件 | 使用中台提供的图编辑工作台页面，统一升级和测试。 | 第一阶段优先用于内部测试和演示；托管路径为 `/image-edit`，会直接进入图编辑工作台并默认展开接入文档。 |
| 源码组件集成 | 业务方把图编辑组件嵌入自己的页面，但仍调用中台 API。 | 当前组件源码已收敛到 `podi-eval-web/src/features/image-edit/`，封版后按这个目录抽包交付。 |

组件负责收集用户交互：

- 主图
- 点选、框选、圆选等软标注
- 参考图
- 编辑指令
- 高级模式下的单个 alpha 蒙版
- 尺寸和质量档位

当前组件边界：

- `podi-eval-web/src/features/image-edit/model.ts` 是交互协议和枚举真源，包含改图模式、尺寸、质量、输出格式、区域标注序列化和任务摘要。
- `podi-eval-web/src/features/image-edit/ImageEditWorkbench.tsx` 是可嵌入工作台，只依赖调用方传入上传函数、提交函数和当前表单值。
- `podi-eval-web/src/features/image-edit/image-edit.css` 是组件样式边界，源码交付时必须一起提供，不能依赖测评端全局样式。
- `podi-eval-web/src/features/image-edit/README.md` 记录源码集成边界，封版交付前必须同步。
- 业务方拿源码集成时，只需要替换 `onUploadImage`、`onSubmit` 和 API Key 注入方式，不应改内部提示词编译规则。
- 测评端和 `/image-edit` 托管入口必须复用同一组件，避免托管版与源码版交互漂移。

中台负责处理：

- 参数校验
- 提示词编译
- 参考图过滤
- GPT Image 2 调用
- OSS 回填
- runId 追踪
- 错误和成本记录

源码集成最小示例：

```tsx
import { useState } from 'react';
import { ImageEditWorkbench } from './features/image-edit/ImageEditWorkbench';
import type { ImageEditWorkbenchValue } from './features/image-edit/ImageEditWorkbench';
import { serializeEditorSelectionHints } from './features/image-edit/model';

const API_BASE = 'https://你的中台域名';

export function ImageEditPage() {
  const [value, setValue] = useState<ImageEditWorkbenchValue>({
    imageUrl: '',
    editSkill: 'local_modify',
    instruction: '',
    marks: [],
    referenceUrls: [],
    maskUrl: '',
    size: 'auto',
    quality: 'preview',
    outputFormat: 'png',
  });

  const uploadImage = async (file: File) => {
    // 业务方可以接自己的上传接口，也可以接中台 OSS 上传接口。
    const form = new FormData();
    form.append('file', file);
    const resp = await fetch(`${API_BASE}/api/media/upload`, { method: 'POST', body: form });
    const data = await resp.json();
    return data.url;
  };

  const submit = async () => {
    // API Key 建议由业务方后端持有；内部受控页面直连时也必须限定能力和域名白名单。
    const resp = await fetch(`${API_BASE}/api/business/image-edit/runs`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-PODI-API-Key': '<业务 Key>',
      },
      body: JSON.stringify({
        imageUrl: value.imageUrl,
        editSkill: value.editSkill,
        instruction: value.instruction,
        selectionHints: serializeEditorSelectionHints(value.marks, { width: 0, height: 0 }),
        referenceImages: value.referenceUrls.map((url, index) => ({
          url,
          role: 'reference',
          label: `参考图${index + 1}`,
          mention: `#参考图${index + 1}`,
        })),
        maskUrl: value.maskUrl || undefined,
        size: value.size || 'auto',
        quality: value.quality || 'preview',
        output_format: value.outputFormat || 'png',
      }),
    });
    return resp.json();
  };

  return <ImageEditWorkbench value={value} onChange={setValue} onUploadImage={uploadImage} onSubmit={() => void submit()} />;
}
```

## 4. 提交任务

```bash
export PODI_BACKEND="http://114.55.0.56:8099"
export PODI_API_KEY="<中台生成的 key>"

curl -X POST "$PODI_BACKEND/api/business/image-edit/runs" \
  -H "Content-Type: application/json" \
  -H "X-PODI-API-Key: $PODI_API_KEY" \
  -d '{
    "imageUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/demo/edit-input.png",
    "editSkill": "local_modify",
    "instruction": "把杯子上的蓝色花纹改成红色，保持杯子形状和背景不变",
    "size": "auto",
    "quality": "preview",
    "output_format": "png",
    "source": "internal-client",
    "channel": "open-api",
    "traceId": "trace-image-edit-001",
    "requestId": "req-image-edit-001"
  }'
```

成功返回：

```json
{
  "runId": "d7f2f7f37d1d47ad8dd2a9d7d3cb3d39",
  "businessKey": "image_edit",
  "version": "gpt-image2-editor-v1",
  "status": "queued",
  "taskStatus": "queued",
  "taskId": null,
  "imageUrls": [],
  "error": null,
  "errorCode": null,
  "errorMessage": null,
  "retryAfterSeconds": 10
}
```

## 5. 查询结果

```bash
curl -X POST "$PODI_BACKEND/api/business/runs/get" \
  -H "Content-Type: application/json" \
  -H "X-PODI-API-Key: $PODI_API_KEY" \
  -d '{
    "runId": "d7f2f7f37d1d47ad8dd2a9d7d3cb3d39"
  }'
```

状态说明：

| 状态 | 说明 | 业务方动作 |
| --- | --- | --- |
| `queued` | 已进入队列，还没开始执行。 | 5-10 秒后继续查。 |
| `running` | 正在执行。 | 5-10 秒后继续查。 |
| `succeeded` | 已完成。 | 读取 `imageUrls`。 |
| `failed` | 失败。 | 读取 `errorCode/errorMessage`，带 runId 找中台排查。 |

成功结果示例：

```json
{
  "runId": "d7f2f7f37d1d47ad8dd2a9d7d3cb3d39",
  "businessKey": "image_edit",
  "version": "gpt-image2-editor-v1",
  "status": "succeeded",
  "taskStatus": "succeeded",
  "imageUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/result/image-edit-output.png",
  "imageUrls": [
    "https://podi.oss-cn-hangzhou.aliyuncs.com/result/image-edit-output.png"
  ],
  "assets": [
    {
      "type": "image",
      "url": "https://podi.oss-cn-hangzhou.aliyuncs.com/result/image-edit-output.png",
      "role": "output"
    }
  ],
  "errorCode": null,
  "errorMessage": null
}
```

排障时可传：

```json
{
  "runId": "d7f2f7f37d1d47ad8dd2a9d7d3cb3d39",
  "detail": "full"
}
```

`detail=full` 会返回处理步骤、编译提示词、底层能力任务等调试信息；普通业务流程不要默认打开，避免返回体过大。

## 6. 参数说明

| 参数 | 是否必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `imageUrl` | 是 | 无 | 主图 URL，必须可被中台访问。 |
| `instruction` | 是 | 无 | 用户编辑指令。描述要改哪里、改成什么。 |
| `editSkill` | 否 | `local_modify` | 改图技能，见下方枚举。 |
| `selectionHints` | 否 | `[]` | 点选、框选、圆选等软标注，只用于告诉模型关注哪里，不是硬蒙版；每条需要有 `mention`，例如 `@标注1`。 |
| `referenceImages` | 条件必填 | `[]` | 参考图列表。参考图替换、补色校正必须提供；每条需要有 `mention`，例如 `#参考图1`。 |
| `maskUrl` | 否 | 空 | 单个最终 alpha 蒙版。多个笔刷区域必须在前端合并成一个蒙版。 |
| `maskMeta` | 否 | 空 | 蒙版元信息，可包含 `sourceWidth/sourceHeight/width/height`，用于提前校验尺寸。 |
| `size` | 否 | `auto` | 输出尺寸。默认跟随原图/自动。 |
| `quality` | 否 | `auto` | 质量档位。 |
| `output_format` | 否 | `png` | 输出格式。 |
| `source` | 否 | 空 | 调用来源，如 `internal-client`。 |
| `channel` | 否 | 空 | 调用渠道，如 `open-api`。 |
| `traceId` | 否 | 自动生成 | 业务方自己的链路号，建议传。 |
| `requestId` | 否 | 自动生成 | 业务方自己的请求号，建议传。 |

## 7. 技能枚举

标注与引用规则：

- 前端每次点选、框选、圆选、手绘后，必须在页面上生成一条“标注区域”记录。
- 标注记录用 `@标注1`、`@标注2` 这类名称引用，不能只在图上显示一个点。
- 参考图用 `#参考图1`、`#参考图2` 这类名称引用。
- 用户在编辑指令里输入 `@` 应看到标注清单，输入 `#` 应看到参考图清单。
- 后端会把 `selectionHints[].mention`、`selectionHints[].geometryText`、`referenceImages[].mention` 编译进最终提示词。
- 非强依赖参考图的技能，只会把指令里明确引用的参考图传给模型，避免无关参考图干扰结果。

`selectionHints` 示例：

```json
[
  {
    "type": "point",
    "label": "标注1",
    "mention": "@标注1",
    "geometryText": "@point(560,610)",
    "points": [{ "x": 560, "y": 610 }]
  }
]
```

`referenceImages` 示例：

```json
[
  {
    "url": "https://podi.oss-cn-hangzhou.aliyuncs.com/demo/reference-1.png",
    "role": "reference",
    "label": "参考图1",
    "mention": "#参考图1"
  }
]
```

| `editSkill` | 中文名 | 是否需要参考图 | 是否需要标注或蒙版 | 说明 |
| --- | --- | --- | --- | --- |
| `local_modify` | 局部修改 | 否 | 否 | 改颜色、形态、局部细节。没有标注时模型按指令判断目标区域。 |
| `reference_element_transfer` | 参考图替换 | 是 | 否 | 用参考图的对象、材质或风格替换主图指定区域。 |
| `remove_inpaint` | 删除修补 | 否 | 是 | 删除指定对象并补齐背景。必须提供 `selectionHints` 或 `maskUrl`。 |
| `color_reference_correction` | 补色校正 | 是 | 否 | 按参考图修正主图颜色、明度、饱和度、冷暖关系。 |

参考图过滤规则：

- `reference_element_transfer` 和 `color_reference_correction` 默认传入参考图。
- 其他技能只传入编辑指令中明确引用的参考图，例如 `#参考图1`。
- 未传入模型的参考图仍会保留在调试信息里，方便排查。

## 8. 尺寸、质量和格式

尺寸：

| 值 | 说明 |
| --- | --- |
| `auto` | 默认，跟随原图/自动。 |
| `1024x1024` | 1K 方图。 |
| `1536x1024` | 1K 横图。 |
| `1024x1536` | 1K 竖图。 |
| `2048x2048` | 2K 方图，高成本。 |
| `2048x1152` | 2K 横图，高成本。 |
| `3840x2160` | 4K 横图，高成本高耗时。 |
| `2160x3840` | 4K 竖图，高成本高耗时。 |

高级自定义尺寸必须同时满足：

- 最大边不超过 `3840`
- 宽高都是 `16` 的倍数
- 长边 / 短边不超过 `3:1`
- 总像素在 `655360` 到 `8294400` 之间

质量：

| 业务值 | 模型值 | 说明 |
| --- | --- | --- |
| `auto` | `auto` | 自动档。 |
| `preview` | `low` | 快速预览，成本较低。 |
| `production` | `medium` | 正式候选。 |
| `premium` | `high` | 高质量，高成本。 |

输出格式：

- `png`
- `jpeg`
- `webp`

## 9. 常见错误

| 错误码 | 含义 | 处理方式 |
| --- | --- | --- |
| `BUSINESS_IMAGE_URL_REQUIRED` | 缺少主图。 | 补传 `imageUrl`。 |
| `IMAGE_EDIT_INSTRUCTION_REQUIRED` | 缺少编辑指令。 | 补传 `instruction`。 |
| `IMAGE_EDIT_SKILL_INVALID` | 技能枚举非法。 | 使用本文档中的 `editSkill`。 |
| `IMAGE_EDIT_REFERENCE_REQUIRED` | 缺少参考图。 | 参考图替换或补色校正时补传 `referenceImages`。 |
| `IMAGE_EDIT_TARGET_REQUIRED` | 缺少目标区域。 | 删除修补时补传 `selectionHints` 或 `maskUrl`。 |
| `IMAGE_EDIT_SIZE_INVALID` | 输出尺寸非法。 | 使用预设尺寸或满足自定义尺寸约束。 |
| `IMAGE_EDIT_MASK_SIZE_MISMATCH` | 蒙版尺寸和主图不一致。 | 重新生成同尺寸蒙版。 |
| `IMAGE_EDIT_MASK_ALPHA_REQUIRED` | 蒙版缺少透明通道。 | 使用带 alpha 通道的 PNG/WebP 蒙版。 |
| `IMAGE_EDIT_QUALITY_INVALID` | 质量档位非法。 | 使用 `auto/preview/production/premium`。 |
| `IMAGE_EDIT_OUTPUT_FORMAT_INVALID` | 输出格式非法。 | 使用 `png/jpeg/webp`。 |

## 10. 封版前检查清单

- `POST /api/business/image-edit/runs` 四种技能均可提交。
- `POST /api/business/runs/get` 轻量结果可用，`detail=full` 可看到编译信息。
- 测评端“图编辑”分类只显示图编辑工作台，不混入 ComfyUI/Coze 旧链路文案。
- 管理端按 runId 能看到入口请求、GPT Image 2 调用、OSS 回填、成本和错误。
- 至少 8 条真实 GPT Image 2 样本完成导出：四种技能各 2 条。

内部巡检可以使用脚本显式执行，不纳入每日默认巡检，避免无意消耗 GPT Image 2 额度：

```bash
cd backend
PODI_BACKEND="https://你的中台域名" \
PODI_BUSINESS_API_KEY="业务 Key" \
python3 scripts/patrol_image_edit_business.py \
  --cases all \
  --repeat 2 \
  --quality preview \
  --detail full \
  --out-dir deliverables/image_edit_patrol
```

脚本会为每个模式导出：

| 文件 | 说明 |
| --- | --- |
| `request.json` | 本次提交给 `/api/business/image-edit/runs` 的请求。 |
| `submit.response.json` | 提交响应，重点看 `runId/taskId/status`。 |
| `poll.records.json` | 每次轮询 `/api/business/runs/get` 的过程记录。 |
| `final.response.json` | 最终结果，包含结果图、错误、调试信息。 |
| `summary.json` | 四种模式的整体结果汇总。 |
