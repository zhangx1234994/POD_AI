# 市场端 AI 能力技术方案（2026-06-11）

## 目标

把市场端能力从“文案接口 + 视频接口 demo”升级为可持续迭代的中台业务能力体系。第一阶段不追求一次性做完整客户端，而是先把中台能力、接口契约、状态模型、素材资产包和验收口径定稳。

核心原则：

- 产品图 / 设计图是最高优先级事实源。
- 产品导出 JSON 是可选说明材料，不是必填入口。
- AI 规划结果、脚本、分镜、图片 brief 和视频 prompt 都先视为可编辑中间稿；只有用户或上游系统显式确认后，才能进入高成本生成动作。
- 视频能力先交付脚本、分镜、首帧、尾帧、分段视频等可复用素材，再做可选合成。
- 中台主语保持业务能力、版本、runId、step、原子能力、结果资产、质量、成本、错误和审计。
- 客户端可以组装项目和业务流程，中台不新增项目主语。

## 当前问题

### 产品导出 JSON 限制业务

当前产品商业化页面和接口仍容易给人一种“必须上传产品导出 JSON”的心智。这会限制真实业务：

- 很多场景只有产品图或设计图，没有完整导出字段。
- 导出字段可能缺失、过期或和图片不匹配。
- 如果让 JSON 成为主事实源，会把错误商品名、错误材质、错误分类带入文案、配图和视频。

修正：

- `productImageUrl` / 产品图必填。
- `productFields` / 导出 JSON 可选。
- 后端生成 `resolvedProductFacts` 时必须以图片为准。
- JSON 只进入 `sourceFacts` 和 `fieldEvidence`，不能压过图片事实。
- JSON 缺失不阻断预览、文案、组图或视频规划。

### 视频能力不能只交付最终片

当前视频生成如果只盯最终合成片，会导致两个问题：

- 成本高：视频模型一次失败成本明显高于文案和图片。
- 损耗大：合成片有问题时，脚本、首尾帧和单段视频这些中间素材仍可能有价值，不应该全部废掉。

修正：

视频能力交付物改为 `videoAssetPackage`：

- `script`：可编辑脚本。
- `storyboard`：分镜计划。
- `keyframes`：首帧、尾帧、关键帧。
- `segmentVideos`：单段视频素材。
- `composition`：可选最终合成片。
- `qualityReview`：质量标签和复核建议。

最终合成片不是唯一成功口径。合成失败时，只要脚本、关键帧或分段素材已经成功，就要保留并回填为可用资产。

## 中台架构匹配

市场端能力必须继续落在现有业务主线里：

```text
调用方
  -> 业务入口 /api/business/*
    -> BusinessRun.runId
      -> BusinessVersion / recipe
        -> steps
          -> 原子能力 / 第三方供应商 / ComfyUI / image-ops / ffmpeg
        -> result_payload / image_urls / video_urls / texts
      -> cost / quality / error / audit
```

不得把旧 AI 摄影棚项目里的“项目 / 工坊 / 批次 / 工作台”搬成中台核心对象。它们只作为测评端或客户端交互参考。

### 旧项目方法论映射

从 `/Volumes/MAC 1/shipin/` 仅吸收方法论，并映射到当前中台对象：

| 旧项目方法论 | 中台落点 | 测评端落点 |
| --- | --- | --- |
| 商品棚拍组图 | `product_image_set` 业务能力；按 asset plan 逐张 run/step 回填 | 展示组图计划、逐张状态、重试和打包下载 |
| 模特/穿搭精修 | `model_scene_image` 业务能力；显式身份/主体/风格参考角色 | 上传主体图和参考图，先确认角色再生成 |
| 多角度展品 | `product_multi_angle` 业务能力；角度参数进入 schema | 角度预设和当前角度结果网格 |
| 转化讲解视频 | `promo_video` 的脚本/分镜/分段视频路线 | 脚本可编辑、分镜确认、再生成视频 |
| 15 秒短片 | `promo_video` 的短节奏版本；仍按素材包保存 | 节奏方案确认后提交候选视频 |
| AI 中间稿原则 | `draft/confirmed/derived` 状态写入 result payload 或 step metadata | 草稿和最终交付态视觉区分 |
| 统一轮询和进度 | `BusinessRun` + steps + provider task polling | 前端只查中台 runId，不直查第三方 |

## 分阶段实现路线

### Phase 0：文档和契约固化

本阶段先做文档，不动生产逻辑：

- 固化市场端能力规划。
- 固化本技术方案。
- 同步业务 API 文档和 TODO。
- 明确下一步代码改造的验收条件。

### Phase 1：修正当前 product_commercialization

目的：在不拆接口的前提下，先把现有入口修到不误导、不丢资产。

改造点：

1. `productFields` 改为明确可选。
2. `resolvedProductFacts` 严格图片优先。
3. `preview` 输出不再把 JSON 字段当成事实主语。
4. 视频规划输出 `videoAssetPackagePlan`。
5. 视频输入支持 `productImages` 图组；主图决定商品身份，多角度/细节图用于 VL 理解、脚本分镜和每段参考图选择。
6. 视频执行结果保存分段素材，不只保存合成片。
7. 页面从“生成视频”改为“生成视频素材包”心智。
8. 合成动作变成可选后续动作。
9. 产品文案测评入口先撤下，后续按 `product_copy_package` 独立能力重做；当前不再把文案和视频放在同一个可见工作台里让业务方混用。
10. 视频规划区改成“客户目标时长 + 可选关键要素表单”。目标时长由客户需求决定，不用 KIE/Vidu 的单段枚举限制；模型画像只用于执行拆段、裁剪和合成策略。
11. `action=video_preview` 必须跳过文案生成链路，只返回视频规划、素材包策略和审核提示；`copyGeneration.method=skipped_for_video_preview` 只是兼容旧响应结构。

### Phase 2：拆正式业务能力

当 Phase 1 验证稳定后，拆出正式能力：

| 能力 | 入口 | 说明 |
| --- | --- | --- |
| `product_market_strategy` | `POST /api/business/product-market-strategy/preview` | 商品理解、事实解析、策略规划。 |
| `product_copy_package` | `POST /api/business/product-copy-package/preview` 或 `/runs` | 文案内容包。 |
| `product_image_set` | `POST /api/business/product-image-set/runs` | 商品组图、详情图、社媒图。 |
| `model_scene_image` | `POST /api/business/model-scene-image/runs` | 模特/场景图。 |
| `product_multi_angle` | `POST /api/business/product-multi-angle/runs` | 多角度/多视图。 |
| `promo_video` | `POST /api/business/promo-video/runs` | 视频素材包和可选合成片。 |
| `product_3d_render_video` | `POST /api/business/product-3d-render-video/preview`，后续 `/runs` | 3D 模型贴图、预设场景和镜头路径渲染视频；独立于 KIE/Vidu 大模型视频。 |
| `marketing_agent` | `POST /api/business/marketing-agent/sessions` | 后续方法论编排，不直接替代底层能力。 |

`product_commercialization` 后续退化为聚合演示入口或兼容入口，不作为长期业务主语。

## 请求结构

### 通用市场端输入

```json
{
  "productImageUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/example/product.png",
  "productFields": {
    "产品名称": "可选字段",
    "材质": "可选字段"
  },
  "marketRegion": "US",
  "commercePlatform": "Amazon",
  "outputLanguage": "en-US",
  "targetAudience": "gift buyers",
  "sellingAngle": "practical gift",
  "forbiddenClaims": ["medical claim", "guaranteed results"],
  "clientContextId": "optional-client-side-context",
  "clientRequestId": "optional-idempotency-key"
}
```

字段规则：

- `productImageUrl`：市场端能力默认必填。
- `productFields`：可选；允许空对象或不传。
- `marketRegion/platform/language`：影响文案、画面和视频策略。
- `clientContextId/clientRequestId`：只做调用链路关联和幂等，不代表中台项目。

### 商品事实解析输出

```json
{
  "resolvedProductFacts": {
    "sourcePriority": ["product_image", "product_fields", "user_context"],
    "productName": "floral hooded jacket",
    "category": "apparel",
    "visibleMaterials": ["lightweight fabric"],
    "visiblePattern": "floral print",
    "confidence": 0.82,
    "inferredFacts": [
      {
        "field": "material",
        "value": "lightweight fabric",
        "source": "image_inference",
        "confidence": 0.7
      }
    ],
    "fieldConflicts": [
      {
        "field": "productName",
        "productFieldValue": "Women's knitted woolen socks",
        "imageObservedValue": "floral hooded jacket",
        "adoptedValue": "floral hooded jacket",
        "severity": "review_required"
      }
    ]
  },
  "sourceFacts": {
    "productFields": {}
  }
}
```

要求：

- 冲突字段保留原值，但下游 prompt 和脚本使用 `adoptedValue`。
- 缺字段允许推断，但必须标注 `source=image_inference` 和置信度。
- 成本动作前展示冲突和低置信提示。

## 视频素材包契约

### 规划输出

```json
{
  "videoAssetPackagePlan": {
    "scenario": "product_showcase",
    "providerProfile": {
      "provider": "vidu",
      "model": "viduq3-turbo",
      "supportedSegmentDurations": [3, 5, 8],
      "aspectPolicy": "input_image_ratio",
      "supportsFirstFrame": true,
      "supportsLastFrame": false,
      "supportsReferenceImages": true
    },
    "script": {
      "editable": true,
      "language": "en-US",
      "text": "Open with a clean product reveal, show the floral pattern, then close with a lifestyle-ready detail shot."
    },
    "storyboard": [
      {
        "segmentIndex": 1,
        "durationSeconds": 5,
        "goal": "clean product reveal",
        "prompt": "Slow camera push-in on the product, preserve floral pattern and hood shape.",
        "requiredAssets": ["first_frame"]
      },
      {
        "segmentIndex": 2,
        "durationSeconds": 5,
        "goal": "detail texture highlight",
        "prompt": "Close-up movement across the floral print and fabric texture.",
        "requiredAssets": ["first_frame", "last_frame"]
      }
    ],
    "compositionPlan": {
      "enabled": false,
      "reason": "Generate segment assets first; composition is optional after review."
    }
  }
}
```

### 执行结果

```json
{
  "videoAssetPackage": {
    "deliveryStatus": "assets_ready",
    "script": {
      "status": "succeeded",
      "text": "..."
    },
    "keyframes": [
      {
        "id": "kf_001",
        "role": "first_frame",
        "status": "succeeded",
        "imageUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/..."
      }
    ],
    "segmentVideos": [
      {
        "segmentIndex": 1,
        "status": "succeeded",
        "durationSeconds": 5,
        "videoUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/...",
        "providerTaskId": "vidu_xxx"
      },
      {
        "segmentIndex": 2,
        "status": "failed",
        "errorCode": "VIDEO_PROVIDER_FAILED",
        "errorMessage": "provider returned failed state"
      }
    ],
    "composition": {
      "enabled": false,
      "status": "skipped",
      "reason": "Review segment assets before composing."
    },
    "qualityReview": {
      "labels": ["needs_manual_review"],
      "notes": ["Segment 2 failed; segment 1 remains reusable."]
    }
  }
}
```

`deliveryStatus` 建议值：

| 值 | 含义 |
| --- | --- |
| `plan_ready` | 只生成了脚本和分镜。 |
| `keyframes_ready` | 首尾帧或关键帧已生成。 |
| `assets_ready` | 至少有一个分段素材可用。 |
| `composed_ready` | 最终合成片可用。 |
| `failed` | 没有任何可交付素材。 |

注意：不要新增业务 run 顶层状态 `partial_success`。顶层状态仍使用统一 `queued/running/succeeded/failed/cancelled`；局部成功写入 `resultPayload.videoAssetPackage.deliveryStatus`。

## 状态和成功口径

### 顶层 BusinessRun

- `queued`：业务 run 已创建。
- `running`：至少一个处理步骤在执行。
- `succeeded`：达到该能力定义的最小交付标准。
- `failed`：没有达到最小交付标准，或必需步骤失败。
- `cancelled`：用户或系统取消。

### 视频最小交付标准

不同模式的最小成功口径不同：

| 模式 | 最小成功口径 |
| --- | --- |
| `script_only` | `script.status=succeeded` 且 `storyboard` 非空。 |
| `keyframe_package` | 脚本/分镜成功，且至少一张关键帧成功。 |
| `segment_package` | 脚本/分镜成功，且至少一个 `segmentVideos.status=succeeded`。 |
| `compose_required` | 最终 `composition.status=succeeded`。 |

默认模式应是 `segment_package` 或 `keyframe_package`，不是 `compose_required`。

### 合成失败处理

- 如果 `composition` 是可选动作：合成失败不能让整个 run 失败；写入 `composition.status=failed` 和 `warnings`。
- 如果用户明确选择“必须合成”：合成失败可以让 run 失败，但仍必须保留脚本、关键帧和分段素材。
- 查询结果必须能看到每个素材的状态和错误。

## 后端改造点

### Service 层

当前优先改 `backend/app/services/product_commercialization.py`：

1. 输入解析：
   - `productFields` 可选。
   - 缺 JSON 时生成空 `sourceFacts.productFields`。
   - 图片事实优先写入 `resolvedProductFacts`。

2. 文案/策略：
   - prompt 中明确 `product image is the primary source of truth`。
   - 输出 schema 保留 `fieldConflicts`、`missingFields`、`inferredFacts`。

3. 视频规划：
   - 增加 `videoAssetPackagePlan`。
   - `script.editable=true`。
   - 根据 `VIDEO_MODEL_PROFILES` 规划 `storyboard.durationSeconds`。
   - Vidu 的 `aspectRatio` 只作为目标规划字段；固定画幅需要先生成归一化首帧。

4. 视频执行：
   - 按分镜逐段创建供应商任务。
   - 每段独立保存 `providerTaskId/status/videoUrl/error`。
   - OSS 回填后写入 `videoAssetPackage.segmentVideos`。
   - 可选执行 `video_composition`。

5. 结果回填：
   - 顶层 `videoUrls` 可保留所有成功段和合成片，便于旧查询兼容。
   - 结构化结果必须写入 `resultPayload.videoAssetPackage`。

### Router / Schema

当前优先改 `backend/app/routers/business.py` 的文档 schema：

- `productFields` 从“建议传/产品导出字段”改为“可选说明材料”。
- `productImageUrl` 是文案、配图、视频规划的核心输入。
- 增加 `videoAssetPackagePlan` 和 `videoAssetPackage` 响应说明。
- 错误列表增加视频素材包相关错误。

### Business Version / Recipe

短期可以继续在代码中维护 `VIDEO_MODEL_PROFILES`，但正式拆能力后需要沉淀到业务版本或配方：

```json
{
  "businessKey": "promo_video",
  "version": "v0.7.0",
  "recipeSteps": [
    "product_fact_resolution",
    "strategy_planning",
    "video_script_planning",
    "keyframe_generation",
    "video_generation",
    "media_ingest",
    "quality_review",
    "optional_video_composition"
  ],
  "modelProfiles": {
    "vidu.viduq3-turbo": {
      "supportedSegmentDurations": [3, 5, 8],
      "aspectPolicy": "input_image_ratio"
    },
    "kie.veo3.1-fast": {
      "supportedSegmentDurations": [8],
      "aspectPolicy": "provider_parameter"
    }
  }
}
```

## 前端改造点

### 产品文案

- 当前测评端入口先撤下，避免业务方继续验收未打磨好的文案 demo。
- 后续按 `product_copy_package` 独立能力重做，输入区只要求产品图，JSON 区作为可选补充信息。
- 冲突提示必须明确：图片优先，字段仅供复核。
- 输出区展示商家可用文案包，不默认展示 raw JSON。

### 产品视频

页面步骤改为：

1. 上传产品图 / 选择产品图。
2. 可选填写产品字段、市场、平台、语言、场景。
3. 填写客户目标时长、用户对视频的自由补充要求，以及可选规划要素：核心信息、目标人群、使用场景、镜头偏好、禁止内容，可通过“添加更多”扩展。
4. 生成视频规划：脚本 + 分镜 + 素材需求。
5. 用户可编辑脚本和分镜。
6. 生成首尾帧 / 关键帧。
7. 生成分段视频素材。
8. 可选合成最终视频。

交互要求：

- 一个阶段一个主 CTA。
- 每个素材卡片显示状态、runId/segmentId、OSS 链接、错误。
- 合成失败时页面仍展示已成功素材。
- 不再把按钮文案写成单一“生成视频”，应区分“生成规划 / 生成关键帧 / 生成分段视频 / 合成视频”。
- 不允许把供应商支持时长做成客户可选时长上限；例如客户填 15 秒，规划模型必须围绕 15 秒形成脚本，执行层再按 KIE 8 秒或 Vidu 3/5/8 秒片段拆解。
- 用户自由补充要求必须进入 `videoPlanningContext.userRequirement`，与产品图、目标时长、模型画像和结构化要素共同进入导演模型上下文；它不能覆盖产品图事实、安全约束或供应商能力边界。

## 错误契约

新增或补充错误码建议：

| 错误码 | 场景 | 是否阻断 |
| --- | --- | --- |
| `PRODUCT_IMAGE_REQUIRED` | 没有产品图。 | 是 |
| `PRODUCT_FACT_LOW_CONFIDENCE` | 图片事实低置信。 | 否，提示人工复核 |
| `PRODUCT_IMAGE_FIELD_CONFLICT` | 图片与 JSON 冲突。 | 否，成本动作前提示 |
| `VIDEO_SCRIPT_PLAN_FAILED` | 脚本/分镜规划失败。 | 是 |
| `VIDEO_KEYFRAME_GENERATION_FAILED` | 关键帧生成失败。 | 视模式而定 |
| `VIDEO_SEGMENT_GENERATION_FAILED` | 某个分段生成失败。 | 视模式而定 |
| `VIDEO_COMPOSITION_FAILED` | 合成失败。 | 默认否；compose_required 时是 |
| `VIDEO_MODEL_DURATION_UNSUPPORTED` | 目标时长无法被模型画像支持。 | 是 |
| `VIDEO_ASPECT_REQUIRES_KEYFRAME` | 固定画幅需要首帧归一化。 | 是 |

落代码时必须同步：

- `docs/standards/error-catalog.md`
- `docs/standards/error-contract.md` 如有新错误结构
- `docs/api/modules/business.md`
- 前端错误消息映射

## 测试用例

### 商品事实

1. 只有产品图，无 JSON：应能生成事实、文案和视频规划。
2. 产品图与 JSON 匹配：应正常采用字段补充说明。
3. 产品图与 JSON 冲突：下游 prompt 使用图片事实，页面提示冲突。
4. JSON 缺字段：不阻断，标注推断来源和置信度。

### 视频素材包

1. 生成脚本和分镜，不触发成本视频。
2. 用户编辑脚本后生成关键帧。
3. Vidu 3/5/8 秒分段规划正确。
4. KIE 仅按 8 秒分段规划。
5. 分段 1 成功、分段 2 失败：run 根据模式保留可用素材。
6. 合成失败：分段素材仍可下载。
7. 固定 16:9 + Vidu：必须提示需要首帧归一化，不能直接承诺 Vidu 输出 16:9。

### 前端

1. 无 JSON 也能完成主流程。
2. JSON 区不会抢占主路径。
3. 视频页面能看到脚本、分镜、关键帧、分段视频、合成片的独立状态。
4. 错误信息不裸露调试 JSON，调试区默认折叠。

## 开发顺序

1. 更新后端 schema 和文档，确认 `productFields` 可选。
2. 改商品事实解析 prompt/schema，确保图片优先。
3. 改 `preview` 的视频规划输出，新增 `videoAssetPackagePlan`。
4. 改视频执行结构，保存分段素材和可选合成结果。
5. 改测评端产品视频页面，按阶段展示和执行。
6. 补错误码和测试。
7. 跑本地真实链路和线上发布门禁。

## 不做事项

- 不把市场端做成中台项目系统。
- 不把导出 JSON 设为必填。
- 不把视频最终合成片作为唯一验收产物。
- 不在前端直连 KIE/Vidu/GPT Image 2。
- 不把 Vidu 一键成片、视频复刻、Ad 模型伪装成已完成能力。
