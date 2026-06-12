# 市场端 AI 能力契约草案（2026-06-11）

## 说明

本文定义 `product_image_set`、`model_scene_image`、`promo_video` 三个正式市场端能力的契约草案。它们当前是 v0.7 待实现能力，不代表线上接口已经开放。

短期试验仍可通过 `product_commercialization` 聚合入口验证产品视频素材包；产品文案入口已暂停，只保留历史试验记录，后续按 `product_copy_package` 独立能力重新设计。长期业务方、客户端和 Agent Runtime 应调用独立能力，避免把文案、组图、模特图和视频混成一个大接口。

共同原则：

- 产品图 / 设计图是最高优先级事实源。
- 产品导出 JSON 是可选补充说明，不是必填字段。
- AI 首次产物是中间稿，进入高成本生成前必须有确认门。
- 所有成本动作返回统一 `runId`，查询统一走 `/api/business/runs/get`。
- 外部供应商结果必须沉淀到自有 OSS 后再作为正式输出。
- 失败必须返回错误码、失败阶段、可重试建议和已成功资产。

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

### 典型场景

| 场景 | 输出资产 |
| --- | --- |
| `product_showcase_short` | 3/5/8 秒商品展示短视频 |
| `social_ad_short` | 社媒广告短视频，节奏更快 |
| `detail_explainer` | 材质、功能、使用场景讲解素材 |
| `campaign_video` | 节日/活动营销素材，可能多段 |
| `reference_remix` | 参考视频复刻，后置且需合规控制 |

### 建议入口

```text
POST /api/business/promo-video/plan
POST /api/business/promo-video/runs
POST /api/business/promo-video/compose
POST /api/business/runs/get
```

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
  "scriptOverride": "",
  "storyboardOverride": [],
  "requestId": "promo-video-001"
}
```

字段规则：

- `targetDurationSeconds` 是目标素材包时长，不等于每个供应商都能直接执行。
- 后端根据模型画像拆分分镜，例如 Vidu 3/5/8 秒，KIE 8 秒。
- `productImageUrl` 是兼容主图字段；`productImages` 用于多角度、细节、材质和场景图输入。规划层可以使用图组，但当前 KIE/Vidu 执行仍按每段一张参考图调用。
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
    "script": {
      "editable": true,
      "text": "Open with a clean product reveal..."
    },
    "storyboard": [
      {
        "segmentIndex": 1,
        "durationSeconds": 5,
        "goal": "product reveal",
        "prompt": "Slow camera push-in...",
        "requiredAssets": ["first_frame"]
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

面向有 3D 模型的 POD 商品，通过固定模型、材质槽 / UV 贴图、预设场景、灯光和相机路径生成可控商品动效。它不是 KIE/Vidu 大模型视频生成的子模式，也不是“文字描述生成视频”；不能混在 `promo_video` 的供应商选择里。当前先开放方案预览，后续接 Three.js 画布和渲染 worker 后再开放异步 `/runs`。

### 建议入口

```text
POST /api/business/product-3d-render-video/preview
POST /api/business/product-3d-render-video/runs   # 待渲染 worker 接入后开放
POST /api/business/runs/get
```

### 请求字段

```json
{
  "modelKey": "cup_1660",
  "textureImageUrl": "https://example.com/pattern.png",
  "materialSlot": "front",
  "cameraPreset": "orbit_360",
  "scenePreset": "clean_studio",
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
- 当前 `preview` 只能验证模型、UV、材质槽和参数计划；在 Three.js 画布接入前，不能验收“贴图与 3D 模型是否真实重合”。
- 当前只允许 `outputMode=plan_only`；真实渲染必须等 worker 接入并统一走 runId 查询。

### 错误码

| 错误码 | 场景 |
| --- | --- |
| `PRODUCT_3D_RENDER_VIDEO_MODEL_INVALID` | 模型 key 非法。 |
| `PRODUCT_3D_RENDER_VIDEO_MATERIAL_SLOT_INVALID` | 材质槽不属于当前模型。 |
| `PRODUCT_3D_RENDER_VIDEO_CAMERA_PRESET_INVALID` | 镜头预设非法。 |
| `PRODUCT_3D_RENDER_VIDEO_SCENE_PRESET_INVALID` | 场景预设非法。 |
| `PRODUCT_3D_RENDER_VIDEO_EXECUTION_NOT_READY` | 当前未开放真实渲染执行。 |
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
