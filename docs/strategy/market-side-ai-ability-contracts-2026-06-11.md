# 市场端 AI 能力契约草案（2026-06-11）

## 说明

本文定义 `product_image_set`、`model_scene_image`、`promo_video` 三个正式市场端能力的契约草案，并补充 `product_3d_render_video` 作为独立确定性视频能力。前三者偏 AI 生成和营销素材规划；`product_3d_render_video` 偏受控模型、贴图、相机和场景渲染，不属于 KIE/Vidu 大模型视频。

短期试验仍可通过 `product_commercialization` 聚合入口验证产品视频素材包；产品文案入口已暂停，只保留历史试验记录，后续按 `product_copy_package` 独立能力重新设计。长期业务方、客户端和 Agent Runtime 应调用独立能力，避免把文案、组图、模特图和视频混成一个大接口。

共同原则：

- 产品图 / 设计图是最高优先级事实源。
- 产品导出 JSON 是可选补充说明，不是必填字段。
- AI 首次产物是中间稿，进入高成本生成前必须有确认门。
- 所有成本动作返回统一 `runId`，查询统一走 `/api/business/runs/get`。
- 外部供应商结果必须沉淀到自有 OSS 后再作为正式输出。
- 失败必须返回错误码、失败阶段、可重试建议和已成功资产。
- 确定性 3D 渲染能力必须保留场景资产、模型资产、材质槽、镜头方案和 OSS manifest 证据，不能只返回一个视频 URL。

## 1. `product_image_set` 商品组图 / 营销套图

### 定位

面向产品生产完成后的上架和营销图片资产包，不是单张随机配图。它负责生成一组有用途、有画幅、有质量标签的商品图片。

### 典型场景

| 场景 | 输出资产 |
| --- | --- |
| `marketplace_listing` | 上架主图、白底图、细节图、尺寸/包装图、材质图 |
| `detail_page` | 详情页卖点图、材质细节图、使用场景图、对比图 |
| `social_ad` | 社媒封面、广告主视觉、节日活动图 |
| `brand_collection` | 同系列多风格主图、套装/系列展示图 |

### 建议入口

```text
POST /api/business/product-image-set/plan
POST /api/business/product-image-set/runs
POST /api/business/runs/get
```

`plan` 可同步返回资产计划，不触发成本动作；`runs` 只在用户确认计划后提交真实生成任务。

### 请求字段

```json
{
  "productImageUrl": "https://example.com/product.png",
  "designImageUrl": "https://example.com/design.png",
  "productFields": {},
  "marketRegion": "US",
  "commercePlatform": "Amazon",
  "outputLanguage": "en-US",
  "assetPackageType": "marketplace_listing",
  "visualScenes": ["listing-main", "detail-closeup", "social-ad-cover"],
  "aspectRatios": {
    "listing-main": "1:1",
    "social-ad-cover": "4:5"
  },
  "styleReferenceImages": [],
  "forbiddenElements": ["text", "watermark", "logo", "price tag"],
  "clientContextId": "client-product-001",
  "requestId": "product-image-set-001"
}
```

字段规则：

- `productImageUrl` 必填。
- `designImageUrl` 可选，用于说明产品来源或图案来源。
- `productFields` 可选，只作为事实补充。
- `visualScenes` 为空时按 `assetPackageType` 给默认场景。
- 多图输入必须声明角色：产品图是主体真源，风格图只提供质感/光线/氛围。

### 计划输出

```json
{
  "businessKey": "product_image_set",
  "status": "plan_ready",
  "resolvedProductFacts": {},
  "assetPlan": {
    "packageType": "marketplace_listing",
    "items": [
      {
        "assetKey": "listing-main",
        "displayName": "上架主图",
        "purpose": "marketplace listing hero image",
        "aspectRatio": "1:1",
        "prompt": "Create a clean ecommerce hero image...",
        "requiredInputs": ["product_image"],
        "confirmationRequired": true
      }
    ]
  },
  "review": {
    "warnings": [],
    "manualChecks": ["product identity", "material consistency", "no embedded text"]
  }
}
```

`shotPackages` 是业务接口的主消费结构：每个镜头把脚本目标、视频提示词、首尾帧提示词、所需素材、确认状态和执行状态放在同一对象里。`storyboard` 与全局 `keyframeNeeds` 只用于兼容和排障，不再要求业务方自行拼装镜头上下文。

### 执行输出

```json
{
  "runId": "br_xxx",
  "status": "succeeded",
  "imageUrls": ["https://podi.oss-cn-hangzhou.aliyuncs.com/...png"],
  "resultPayload": {
    "assetPackage": {
      "businessKey": "product_image_set",
      "deliveryStatus": "assets_ready",
      "items": [
        {
          "assetKey": "listing-main",
          "status": "succeeded",
          "imageUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/...png",
          "prompt": "...",
          "model": "gpt-image-2",
          "qualityLabels": ["needs_manual_review"]
        }
      ],
      "failedItems": []
    }
  }
}
```

### 最小成功口径

- `assetPlan.items` 非空。
- 至少一个目标资产生成成功并回填 OSS。
- 每个失败资产有 `errorCode/errorMessage/retryable`。

### 错误码

| 错误码 | 场景 |
| --- | --- |
| `PRODUCT_IMAGE_REQUIRED` | 未提供产品图。 |
| `PRODUCT_IMAGE_SET_PLAN_FAILED` | 组图计划生成失败。 |
| `PRODUCT_IMAGE_SET_ASSET_FAILED` | 单个资产生成失败。 |
| `PRODUCT_IMAGE_SET_NO_ASSET_SUCCEEDED` | 所有目标资产都失败。 |
| `PRODUCT_IMAGE_FIELD_CONFLICT` | 产品图与字段冲突，需要人工复核。 |

### 首批 golden cases

| 样例 | 场景 | 必须覆盖 |
| --- | --- | --- |
| 服饰/配件 | `marketplace_listing` + `social_ad` | 主图、细节、社媒封面；检查花纹/材质不漂移。 |
| 家居软装 | `detail_page` | 材质细节、使用场景；检查尺寸和图案连续性。 |
| 节日营销图 | `social_ad` | 礼品/节日氛围；禁止文字、水印、价格标签。 |

## 2. `model_scene_image` 模特 / 穿搭 / 使用场景图

### 定位

面向服饰、配件、家居、宠物、礼品等需要人体、空间或生活场景展示的商品图。它不是普通换背景；核心是把产品主体和场景/模特角色分开控制。

### 典型场景

| 场景 | 输出资产 |
| --- | --- |
| `apparel_model` | 服装上身图、正侧背、局部细节 |
| `accessory_styling` | 包、袜子、饰品穿搭场景 |
| `home_lifestyle` | 家居软装在真实空间中的展示 |
| `pet_or_family_scene` | 宠物/家庭使用场景 |

### 建议入口

```text
POST /api/business/model-scene-image/plan
POST /api/business/model-scene-image/runs
POST /api/business/runs/get
```

### 请求字段

```json
{
  "productImageUrl": "https://example.com/product.png",
  "productFields": {},
  "sceneType": "apparel_model",
  "modelProfile": {
    "genderPresentation": "female",
    "ageRange": "25-35",
    "regionStyle": "US casual"
  },
  "posePreset": "standing_back_view",
  "sceneDescription": "bright casual indoor lifestyle scene",
  "identityReferenceImages": [],
  "styleReferenceImages": [],
  "outputCount": 3,
  "aspectRatio": "4:5",
  "requestId": "model-scene-001"
}
```

字段规则：

- 产品图仍是主体真源。
- `identityReferenceImages` 只决定人物身份、发型、肤色、体态，不决定商品本体。
- `styleReferenceImages` 只提供光线、摄影风格、场景氛围。
- 如果商品不是可穿戴或可放入场景的品类，必须返回低置信或不可执行建议。

### 计划输出

```json
{
  "businessKey": "model_scene_image",
  "status": "plan_ready",
  "scenePlan": {
    "sceneType": "apparel_model",
    "shots": [
      {
        "shotKey": "back-view",
        "purpose": "show full floral pattern and silhouette",
        "prompt": "Use product image as garment truth...",
        "referenceRoles": [
          {"role": "product_truth", "source": "productImageUrl"},
          {"role": "identity_anchor", "source": "identityReferenceImages"}
        ]
      }
    ]
  },
  "review": {
    "manualChecks": ["product fit", "identity consistency", "pattern consistency"]
  }
}
```

### 最小成功口径

- 计划里明确每张参考图角色。
- 至少一张场景图成功回填 OSS。
- 质量标签必须覆盖 `identity_drift`、`product_drift`、`pose_error`、`scene_mismatch`。

### 错误码

| 错误码 | 场景 |
| --- | --- |
| `MODEL_SCENE_UNSUPPORTED_PRODUCT` | 商品不适合当前场景类型。 |
| `MODEL_SCENE_PLAN_FAILED` | 模特/场景计划失败。 |
| `MODEL_SCENE_REFERENCE_ROLE_MISSING` | 多图输入缺少角色声明。 |
| `MODEL_SCENE_GENERATION_FAILED` | 场景图生成失败。 |
| `MODEL_SCENE_NO_ASSET_SUCCEEDED` | 没有成功场景图。 |

## 3. `promo_video` 产品推广视频素材包

### 定位

面向产品展示、详情讲解、社媒广告和活动营销的视频素材包能力。它不是“单图生成一条视频”的包装，而是脚本、分镜、关键帧、分段视频和可选合成的多阶段能力。

### 当前视频类型 / 资产类型

| 类型字段 | 输出资产 |
| --- | --- |
| `product_showcase_short` | 商品多角度展示素材，强调主体、轮廓、材质和基础角度 |
| `social_ad_short` | 广告转化短片，强调开头吸引力和快节奏 |
| `detail_explainer` | 细节卖点讲解素材，强调材质、结构、使用方式和详情页说明 |
| `campaign_video` | 待补齐：节日/活动营销素材，可能多段 |
| `reference_remix` | 待补齐：参考视频复刻，后置且需合规控制 |

说明：当前 API 兼容字段名仍为 `videoScenario`，但业务含义按“视频类型/资产类型”理解；使用场景、平台、市场和用户补充要求应进入规划上下文，不应替代视频类型。

### 建议入口

```text
POST /api/business/promo-video/plan
POST /api/business/promo-video/keyframes/runs
POST /api/business/promo-video/runs
POST /api/business/promo-video/compose/runs
POST /api/business/runs/get
```

2026-06-13：以上入口已开放 MVP。对业务方已经按能力拆分，固定 action，不再要求接入方自己传 `video_preview/video_keyframes/video_generate/compose_video`；运行任务业务键为 `promo_video`。当前内部仍复用 `product_commercialization` 编排服务、计费、轮询和错误契约。

### 能力拆分

| 能力 | 责任 | 成本动作 |
| --- | --- | --- |
| `promo_video.plan` | VL/LLM 读取产品图组和可选字段，输出商品理解、脚本、分镜、模型画像拆段、首尾帧需求和风险检查。 | 不触发图片/视频生成。 |
| `promo_video.keyframes` | 按已确认脚本和分镜生成首帧、尾帧或关键帧，回填 OSS，供用户逐镜头确认。 | 调用 GPT Image 2 或后续指定图片模型。 |
| `promo_video.segment_video` | 按每个分镜调用 KIE/Vidu 等视频模型，生成一段或多段视频素材。 | 调用视频供应商，按片段计量。 |
| `promo_video.compose` | 在用户确认分段素材后做可选合成、裁剪和转码。 | 本地/服务端转码成本，不替代分段素材交付。 |

前端交互必须对应这四层：先填写或由 VL 回填核心要素，生成脚本分镜；再按镜头列表展示脚本、首尾帧提示词和结果；用户必须逐镜头确认首尾帧，不满意时只重生成对应镜头并清除该镜头确认状态，所有必需镜头确认后再触发视频段成本动作。后端同样必须做角色级确认校验：`confirmedVideoKeyframes` 不只是数量校验，而是逐项匹配 `shot/segmentIndex/role`；例如同一镜头返回两张首帧但缺尾帧时，视频接口必须拒绝并返回缺失的 `last_frame`。

### 请求字段

```json
{
  "productImageUrl": "https://example.com/product.png",
  "productImages": [
    {"url": "https://example.com/front.png", "role": "front", "label": "正面", "isPrimary": true},
    {"url": "https://example.com/back.png", "role": "back", "label": "背面"},
    {"url": "https://example.com/detail.png", "role": "detail", "label": "材质细节"}
  ],
  "productFields": {},
  "videoScenario": "product_showcase_short",
  "targetDurationSeconds": 15,
  "aspectRatio": "16:9",
  "providerPreference": "vidu",
  "modelProfile": "vidu.viduq3-turbo",
  "generationMode": "segment_package",
  "keyframeMode": "auto_first_frame",
  "videoPlanningContext": {
    "coreMessage": "show the full product shape and print first",
    "targetAudience": "US gift buyers and marketplace shoppers",
    "usageScene": "clean tabletop ecommerce scene",
    "shotPreference": "gentle orbit first, then slow push-in without cropping product edges",
    "avoid": "no text, watermark, logo, price tag, product deformation",
    "fields": [
      {
        "id": "custom_note",
        "label": "补充要素",
        "value": "keep the handle visible in the first shot",
        "source": "manual"
      }
    ]
  },
  "scriptOverride": "",
  "storyboardOverride": [],
  "requestId": "promo-video-001"
}
```

字段规则：

- `targetDurationSeconds` 是目标素材包时长，不等于每个供应商都能直接执行。
- 后端根据模型画像拆分分镜，例如 Vidu 3/5/8 秒，KIE 8 秒。
- `productImageUrl` 是兼容主图字段；`productImages` 用于多角度、细节、材质和场景图输入。规划层可以使用图组，但当前 KIE/Vidu 执行仍按每段一张参考图调用。
- `videoPlanningContext` 是业务方和测评端传递核心信息、目标人群、使用场景、镜头偏好、禁止内容和自定义要素的结构化入口。测评端可先由 VL/LLM 根据产品图、图组和可选 JSON 回填空白项，用户修改后再重新规划；后端必须把该对象传入视频导演模型上下文，不能只拼成不可追踪的长文本。
- `plan` 必须返回 `planner.method/provider/model/fallback/evidence`，不能把模板兜底伪装成大模型规划。`fallback=true` 时只允许用于排障和交互验证，不作为最终方法论验收。
- 每个分镜必须包含 `scene/cameraMovement/composition/prompt/firstFramePrompt/lastFramePrompt/negativePrompt/referenceImage`，否则不允许触发视频成本动作。
- 固定画幅如果供应商跟随输入图比例，必须先生成或归一化首帧。
- `generationMode=compose_required` 才把合成片作为顶层成功条件；默认是 `segment_package`。

### 计划输出

```json
{
  "businessKey": "promo_video",
  "status": "plan_ready",
  "videoAssetPackagePlan": {
    "providerProfile": {
      "provider": "vidu",
      "model": "viduq3-turbo",
      "supportedSegmentDurations": [3, 5, 8],
      "aspectPolicy": "input_image_ratio"
    },
    "planner": {
      "method": "openai_responses",
      "provider": "openai",
      "model": "gpt-5.5",
      "fallback": false,
      "evidence": "LLM/VL generated structured video director plan."
    },
    "directorBrief": {
      "productUnderstanding": "Use visible product image facts as the source of truth.",
      "commercialGoal": "Create ecommerce product-showcase material.",
      "visualStyle": "Clean commercial product footage."
    },
    "script": {
      "editable": true,
      "text": "Open with a clean product reveal..."
    },
    "storyboard": [
      {
        "segmentIndex": 1,
        "durationSeconds": 5,
        "goal": "product reveal",
        "scene": "clean studio ecommerce set",
        "cameraMovement": "slow push-in with a slight side movement",
        "prompt": "Slow camera push-in...",
        "firstFramePrompt": "Create the opening product hero frame...",
        "lastFramePrompt": "Create the stable ending product frame...",
        "requiredAssets": ["first_frame"]
      }
    ],
    "shotPackages": [
      {
        "shotNo": 1,
        "segmentIndex": 1,
        "durationSeconds": 5,
        "goal": "product reveal",
        "scene": "clean studio ecommerce set",
        "cameraMovement": "slow push-in with a slight side movement",
        "videoPrompt": "Slow camera push-in...",
        "firstFramePrompt": "Create the opening product hero frame...",
        "lastFramePrompt": "Create the stable ending product frame...",
        "keyframeNeeds": [
          {
            "role": "first_frame",
            "reason": "lock aspect ratio and product identity"
          }
        ],
        "confirmationRequired": true,
        "executionState": "needs_keyframes"
      }
    ],
    "keyframeNeeds": [
      {
        "role": "first_frame",
        "reason": "lock aspect ratio and product identity"
      }
    ],
    "compositionPlan": {
      "enabled": false,
      "reason": "Review segment assets before composing."
    }
  }
}
```

### 执行输出

```json
{
  "runId": "br_xxx",
  "status": "succeeded",
  "videoUrls": ["https://podi.oss-cn-hangzhou.aliyuncs.com/...mp4"],
  "resultPayload": {
    "videoAssetPackage": {
      "businessKey": "promo_video",
      "deliveryStatus": "assets_ready",
      "script": {"status": "succeeded", "text": "..."},
      "keyframes": [],
      "segmentVideos": [
        {
          "segmentIndex": 1,
          "status": "succeeded",
          "durationSeconds": 5,
          "videoUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/...mp4",
          "provider": "vidu",
          "providerTaskId": "vidu_xxx"
        }
      ],
      "composition": {"enabled": false, "status": "skipped"}
    }
  }
}
```

### 最小成功口径

| 模式 | 顶层成功条件 |
| --- | --- |
| `script_only` | 脚本和分镜成功。 |
| `keyframe_package` | 至少一张关键帧成功。 |
| `segment_package` | 至少一段视频成功。 |
| `compose_required` | 合成片成功；但失败时仍保留所有中间素材。 |

### 错误码

| 错误码 | 场景 |
| --- | --- |
| `PROMO_VIDEO_PLAN_FAILED` | 脚本/分镜规划失败。 |
| `PROMO_VIDEO_MODEL_DURATION_UNSUPPORTED` | 目标时长无法按模型画像拆分。 |
| `PROMO_VIDEO_ASPECT_REQUIRES_KEYFRAME` | 固定画幅需要首帧归一化。 |
| `PROMO_VIDEO_KEYFRAME_FAILED` | 关键帧生成失败。 |
| `PROMO_VIDEO_SEGMENT_FAILED` | 某段视频生成失败。 |
| `PROMO_VIDEO_NO_SEGMENT_SUCCEEDED` | 没有任何可用视频段。 |
| `PROMO_VIDEO_COMPOSITION_FAILED` | 合成失败。 |

### 首批 golden cases

| 样例 | 模式 | 必须覆盖 |
| --- | --- | --- |
| 单产品展示 | `segment_package`，8 秒 | KIE/Vidu 单段对比，检查主体不变形。 |
| 15 秒社媒广告 | `segment_package`，多段 | 模型画像拆分、分段素材保留、可选合成。 |
| 材质详情讲解 | `keyframe_package` -> `segment_package` | 首帧/尾帧控制，材质和图案不漂移。 |

## 4. `product_3d_render_video` 3D 渲染视频

### 定位

面向有 3D 模型的 POD 商品，通过固定模型、材质槽 / UV 贴图、预设场景、灯光和镜头运动生成可控商品动效。它不是 KIE/Vidu 大模型视频生成的子模式，也不是“文字描述生成视频”；不能混在 `promo_video` 的供应商选择里。当前开放方案预览、测评端浏览器 Three.js 本地 MP4/WebM 录制，以及服务端 `/runs` 轻量 MP4/OSS 渲染任务；后续再把 `lightweight_scene_renderer_v1` 替换为 Blender/headless Three.js 高保真 worker。

### 建议入口

```text
POST /api/business/product-3d-render-video/preview
POST /api/business/product-3d-render-video/runs   # 创建统一业务 run；终态查询 videoUrls/imageUrls/renderAssetPackage
POST /api/business/runs/get
```

### 请求字段

```json
{
  "modelKey": "cup_1660",
  "textureImageUrl": "https://example.com/pattern.png",
  "materialSlot": "front",
  "cameraPreset": "hero_turntable",
  "cameraDistance": "wide",
  "scenePreset": "desktop_lifestyle",
  "cameraPlan": {
    "version": "camera-plan-v2",
    "template": "hero_turntable",
    "customMode": "preset_template",
    "productMotion": "fixed",
    "cameraMotion": "path_playback",
    "playbackConfirmed": false
  },
  "motionPath": [
    {"x": 0.22, "y": 0.66},
    {"x": 0.5, "y": 0.5},
    {"x": 0.78, "y": 0.42}
  ],
  "durationSeconds": 6,
  "aspectRatio": "16:9",
  "outputMode": "plan_only",
  "requestId": "product-3d-video-001"
}
```

字段规则：

- `modelKey` 当前试点 `cup_1660` 和 `backpack_2551`。
- 模型必须先进入受控模型目录；测评端上传 zip 只是资产检查，不代表生产可执行。
- `textureImageUrl` 是主贴图，必须贴到 `materialSlot` 对应的固定区域；`textureImageUrls` 用于后续多材质/多面贴图。
- `materialSlot` 是模型内真实材质槽 / UV 区域，不是自然语言区域描述。用户侧应该通过可视化区域选择，不应该让用户写一段文字描述要贴哪里。
- 当前 `preview` 只能验证模型、UV、材质槽和参数计划；测评端 Three.js 画布负责所见即所得预览和本地 MP4/WebM 录制，服务端 `/runs` 负责可查询、可回填 OSS 的 MP4 交付。
- `preview` 当前只允许 `outputMode=plan_only`；传 `render_video` 会返回 `PRODUCT_3D_RENDER_VIDEO_EXECUTION_NOT_READY`。
- `/runs` 是独立服务端渲染入口，固定接收 `outputMode=render_video`；当前返回标准 `runId/taskId`，并按统一 runId 查询 OSS 视频、封面和 manifest。
- 镜头预设包括 `orbit_360/hero_turntable/slow_push_in/detail_sweep/top_reveal/social_arc`；镜头远近包括 `wide/standard/close`，默认 `wide`，前端和服务端都必须遵守 `fit_product_safe_bounds`，保证商品主体完整入画。
- 自定义镜头不新增 `cameraPreset`。用户在 3D 画面中拖动模型/相机，依次保存开始画面、杯口、细节等多个镜头关键帧；前端写入 `cameraPlan.customMode=manual_keyframe_capture`、`cameraPlan.keyframes/segments/timeline`，每段 segment 单独记录秒数和 `smooth/orbit` 运动类型，`customShots.start/end` 仅作为首尾关键帧兼容字段，同时折算 `motionPath` 兼容轻量渲染器和旧链路。
- 场景预设包括 `clean_studio/marketplace_white/premium_dark/desktop_lifestyle/gift_table/retail_shelf`，每个场景必须定义商品摆放位置、比例、安全区、阴影和道具遮挡规则，并映射到 `renderPlan.scene.asset`。
- `renderPlan.scene.asset` 必须包含 `assetId/assetType/assetStatus/renderFidelity/source/license/geometry/materialPolicy/highFidelityTarget`。当前首版为 `mvp_procedural`，可用于交互和接口闭环；商用级效果要替换为高保真 worker 或经过授权的真实场景资产。
- `/preview` 必须返回 `renderPlan.scene.fusion`，`/runs` 输出的 `renderAssetPackage.manifest.sceneFusion` 必须沉淀场景融合证据，至少包括 `landingZone/productScale/occlusionPolicy/propDepth/shadowPolicy`。这用于证明商品落点、道具层级和遮挡规则，不允许把场景能力降级成“换背景枚举”。
- `/runs` 输出的 `renderAssetPackage.manifest.sceneAsset` 必须沉淀场景资产证据，不能只给视频 URL。业务方验收视频时要能追溯模型、贴图槽、相机、运动路径、场景资产和场景融合策略。
- 外部场景资产只允许引入授权明确的资源。优先用 CC0 来源做测试，例如 Poly Haven、ambientCG；BlenderKit 等混合授权库必须逐项记录 license、作者、来源 URL 和商用限制，不能直接塞进生产资产目录。

### 错误码

| 错误码 | 场景 |
| --- | --- |
| `PRODUCT_3D_RENDER_VIDEO_MODEL_INVALID` | 模型 key 非法。 |
| `PRODUCT_3D_RENDER_VIDEO_MATERIAL_SLOT_INVALID` | 材质槽不属于当前模型。 |
| `PRODUCT_3D_RENDER_VIDEO_CAMERA_PRESET_INVALID` | 镜头预设非法。 |
| `PRODUCT_3D_RENDER_VIDEO_SCENE_PRESET_INVALID` | 场景预设非法。 |
| `PRODUCT_3D_RENDER_VIDEO_EXECUTION_NOT_READY` | `/preview` 收到 `render_video`，应改用 `/runs`。 |
| `PRODUCT_3D_RENDER_VIDEO_TEXTURE_REQUIRED` | 服务端生成缺少真实贴图 URL。 |
| `PRODUCT_3D_RENDER_VIDEO_TEXTURE_LOAD_FAILED` | 贴图下载或读取失败。 |
| `PRODUCT_3D_RENDER_VIDEO_CONTEXT_INVALID` | 后台任务上下文恢复失败。 |
| `PRODUCT_3D_RENDER_VIDEO_FFMPEG_MISSING` | 服务端缺少 ffmpeg 或 imageio-ffmpeg。 |
| `PRODUCT_3D_RENDER_VIDEO_RENDER_RUN_NOT_READY` | 历史/兼容错误码；当前轻量渲染器已接入。 |
| `PRODUCT_3D_RENDER_VIDEO_RENDER_RUN_FAILED` | 服务端渲染任务提交异常。 |
| `PRODUCT_3D_RENDER_VIDEO_PREVIEW_FAILED` | 方案预览异常。 |
| `PRODUCT_3D_RENDER_VIDEO_TEXTURE_MISSING` | 非阻断 issue code，缺少贴图时只验证模型和镜头方案。 |
| `PRODUCT_3D_RENDER_VIDEO_UV_MISSING` | 非阻断 issue code，模型缺少 UV 时需先修复资产。 |

## 5. 测评端交互标准

市场端能力的测评端页面必须遵循同一结构：

1. 首屏只展示业务输入、当前阶段、一个主 CTA。
2. 计划结果是可读卡片，不裸显大段 JSON。
3. Prompt、模型画像、接口文档默认折叠。
4. 每个成本动作明确显示 runId、状态、耗时、错误和 OSS 回填。
5. 结果按素材卡片展示，支持失败项单独重试。
6. 下载包是交付动作，不是调试按钮。

## 6. 实现优先级

| 优先级 | 能力 | 原因 |
| --- | --- | --- |
| P0 | `promo_video` 素材包契约落地 | 当前产品视频 demo 已暴露业务口径和交互问题，必须先收口。 |
| P0 | `product_image_set` 计划和单张/多张资产执行 | 文案配图、组图、营销套图都是市场端基础能力。 |
| P1 | `product_3d_render_video` 渲染 worker 接入 | 有 3D 模型时成本和可控性优于大模型视频，先从杯子/背包两个样例验证。 |
| P1 | `model_scene_image` | 需要更多样例和模型策略，先定义契约和参考图角色。 |
| P1 | `marketing_agent` 调用上述能力 | 等底层能力契约稳定后再做编排，不先做大而全 Agent。 |
