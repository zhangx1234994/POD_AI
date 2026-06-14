# 业务能力接口

## 用途

业务能力接口是给业务方、Coze、客户端、MCP/技能复用的稳定入口。
第一阶段开放核心业务：花纹提取、图裂变、产品设计、产品商业化、图编辑、对话改图、文字强化裂变、裂变生成图评估、扩图；底层仍复用统一能力任务、商业模型、KIE/Vidu 视频能力和 ComfyUI workflow，但对外不暴露节点、workflow、executor 等实现细节。

核心约定：

- 对外统一是 `提交业务任务 -> 返回 runId -> 轮询结果`。
- `runId` 是业务任务 ID，业务方只需要保存它。
- `taskId` 是底层能力任务 ID，仅用于排查和链路关联，不要求业务方理解。
- 业务版本由中台切默认版本；Coze 工具箱和业务方入参尽量保持不变。
- 图裂变 2026-05-12 交付的两个裂变版本和裂变评分接口，统一参考 `docs/api/examples/fission-delivery-contract-2026-05-12.md`；其中包含类图、队列/轮询兼容关系和参数聚合规则。

## 鉴权

- 业务方推荐使用 `X-PODI-API-Key: <业务 API Key>`。中台会记录 Key、业务、runId、状态码和耗时，作为后续计费、配额和排障基础。
- 兼容 `Authorization: Bearer <业务 API Key>`；系统巡检和 Coze 内部调用仍可使用 `Authorization: Bearer <SERVICE_API_TOKEN>`。
- Coze 同机/可信内网调用可通过 `COZE_TRUSTED_IPS` 或内网地址放行。
- 管理端业务能力接口仍要求管理员权限。
- 业务方登录账号调用时，只能使用账号绑定的 `tenantId/clientId`。如果传入其他业务方范围，会返回 `BUSINESS_USER_SCOPE_FORBIDDEN`；如果业务方账号没有绑定 `tenantId`，会返回 `BUSINESS_USER_SCOPE_REQUIRED`。
- 管理员和服务 Token 可显式指定 `tenantId/clientId`，用于 Coze 工具箱、巡检脚本和后台代业务方提交。
- 当前 API Key 先做身份识别和审计，不强制限流；业务方并发、日次数和额度限制仍优先走业务方配置。
- 如果业务 API Key 已绑定 `tenantId/clientId`，业务方请求体里不要再传其他租户或客户端；否则会被业务范围校验拦截为 `BUSINESS_USER_SCOPE_FORBIDDEN`。这属于权限保护，不是生图链路异常。

---

## 0) 业务方快速接入口径

业务方只需要理解四件事：

1. 提交任务后保存 `runId`。
2. 用 `runId` 轮询 `/api/business/runs/get`。
3. Coze/内网工具箱兼容场景下，也可以把 `runId` 填到旧轮询接口 `/api/coze/podi/tasks/get` 的 `taskId` 字段。
4. 终态优先看 `status/taskStatus/imageUrls/videoUrls/texts/error`。默认查询结果保持轻量，结构化评分会在无图片输出时返回轻量 `resultPayload`；需要 `routeInfo/steps/flowSummary` 等排障字段时，查询接口传 `detail=full`。

提交成功判断必须同时满足：HTTP 2xx、响应体有真实 `runId`、`status/taskStatus` 为 `queued` 或 `running`、没有 `ERR|...`、没有 `errorCode`。如果响应里出现 `ERR|Q1001|...`、`ERR|Q1002|COMFYUI_EXECUTOR_UNAVAILABLE...`、`errorCode` 或 `status=failed`，都不能视为提交成功。

`Q1001` 表示 ComfyUI 队列已满；`Q1002` 表示 ComfyUI 执行器不可用或没有兼容可用节点。`Q1002` 不等同于排队等待，业务方应提示“节点暂不可用，稍后重试或联系中台排查”，不要保存为正常待轮询任务。

这条链路不要求业务方传 Coze 工作流 ID。Coze 可以继续作为接入入口，但业务 API 本身已经能完成“提交任务 -> 查询结果”的闭环；灰度或默认版本命中可先用 `route-preview` 验证。

当前对外业务入口：

| 业务 | 提交接口 | 必填字段 | 常用可调字段 | 终态输出 | 业务说明 |
| --- | --- | --- | --- | --- | --- |
| 花纹提取 | `POST /api/business/pattern-extract/runs` | `imageUrl` | `prompt`、`negative_prompt`、`width`、`height`、`batch`、`lora` | `imageUrls` | 从原图中提取可复用花纹资产，通常是后续裂变和扩图的上游。 |
| 图裂变 | `POST /api/business/fission/runs` | `imageUrl` | ComfyUI 颜色锁定版：`bili`(`80%` 默认)、`width`、`height`、`profile`、`reference_lock`、`color_lock`；GPT Image 2 版：`variation_strength`、`quality`、`size`、`maskUrl`；历史 ComfyUI 版本仍兼容 `prompt/image_desc/batch_size/steps/cfg` | `imageUrls` | 基于原图生成变化图；版本可在中台切换，业务方仍调用同一个入口。`bili` 是重绘幅度/裂变幅度，越高变化越明显。 |
| 产品设计 | `POST /api/business/product-design/runs` | `imageUrl`、`designBrief` | `productType`、`scene`、`referenceImages`、`clientContextId`、`inputAssetIds`、`quality`、`size` | `imageUrls` | 把素材/花纹上到指定产品载体，输出产品设计图。它是独立业务能力，不是图编辑内部模式；客户端可把它编排进端到端链路。 |
| 产品推广视频素材包 | 规划 `POST /api/business/promo-video/plan`；首尾帧 `POST /api/business/promo-video/keyframes/runs`；分段视频 `POST /api/business/promo-video/runs`；可选合成 `POST /api/business/promo-video/compose/runs`；查询 `POST /api/business/runs/get` | 核心输入为 `productImageUrl` 或 `productImages`；`productFields` 是可选说明材料，不是必填事实源；成本动作必须至少有一张产品图 | `productImages`、`videoScenario`、`durationSeconds`、`targetDurationSeconds`、`aspectRatio`、`executorId`、`extraPrompt`、`videoPlanningContext`、`videoPromptOverride`、`keyframeShotScope`、`confirmedVideoKeyframes` | 规划返回 `videoPlan`、`videoAssetPackagePlan`、`resolvedProductFacts`、`review`；执行返回 `runId` 且 `businessKey=promo_video`，终态查询返回 `imageUrls`、`videoUrls` 或 `resultPayload.videoAssetPackage` | 正式产品视频能力入口，拆成规划、首尾帧、分段视频和可选合成四层。MVP 内部沿用 `product_commercialization` 编排服务和计费/轮询链路，但业务方不再需要自己传 `action`，也不再看到旧聚合业务键。 |
| 产品商业化（兼容聚合） | 视频预览 `POST /api/business/product-commercialization/preview` 且 `action=video_preview`；首尾帧/视频执行 `POST /api/business/product-commercialization/runs`；查询 `POST /api/business/runs/get` | 同上 | 视频：`action=video_preview/video_keyframes/video_generate` 等；文案入口已从测评端撤下，后续按 `product_copy_package` 独立重做 | 同上 | 试验/兼容聚合入口。新业务接入优先使用 `promo-video` 拆分入口，避免把文案、组图、视频和合成混在一个大接口里。 |
| 3D 渲染视频 | 能力目录 `GET /api/business/product-3d-render-video/catalog`；方案预览 `POST /api/business/product-3d-render-video/preview`；服务端渲染任务 `POST /api/business/product-3d-render-video/runs`；查询 `POST /api/business/runs/get` | `modelKey`；服务端生成必须提供贴图 `textureImageUrl` 或 `textureSlots` | `materialSlot`、`cameraPreset`、`cameraDistance`、`scenePreset`、`cameraPlan`、兼容 `motionPath`、`durationSeconds`、`aspectRatio`、`extraPrompt` | catalog 返回模型/材质槽/场景资产、`sceneAssetSources` 来源治理、镜头/远近档位；预览返回 `model`、`assetReadiness`、`renderPlan`、`review`；测评端需先播放并确认镜头，再本地导出 MP4/WebM 预览或提交服务端 MP4/OSS；`/runs` 返回标准 `runId`，终态查询返回 `videoUrls/imageUrls/resultPayload.renderAssetPackage` | 独立于 KIE/Vidu 的 3D 模型渲染视频能力。当前测评端已接入客户端 GLB/UV 预览、场景布景、镜头远近、预设镜头/自定义开始结束镜头确认、本地录制和服务端轻量 MP4/OSS 输出；商品固定，镜头驱动相机运动；高保真 Blender/headless Three.js worker 后续替换。 |
| 文字强化裂变（文生图） | `POST /api/business/text-fission/prompts` + `POST /api/business/text-fission/runs` | 第一步 `imageUrl`；第二步 `imageUrl`、`editable_prompt` | `editable_negative_prompt`、`width`、`height`、`promptDraftId` | `imageUrls` | 先用 VL 生成可编辑提示词，用户确认后再走 ComfyUI 文生图。适合原图文字要求强、图生图改不干净的场景。采样步数、提示词强度、随机种子由中台控制，不作为业务方输入。 |
| 裂变生成图评估 | `POST /api/business/fission-evaluate/runs` | `originalImageUrl`、`generatedImageUrl` | `context` | `texts/resultPayload` | 输入原图和裂变结果图，判断是否通过、是否建议二次裂变；只评分，不自动二次裂变。 |
| 扩图 | `POST /api/business/outpaint/runs` | `imageUrl` | `prompt`、`expand_left`、`expand_right`、`expand_top`、`expand_bottom`、`width`、`height` | `imageUrls` | 在原图四周扩展画面，适合补构图、补背景和素材延展。 |
| AI 图片助手 | `POST /api/business/image-edit-chat/sessions` + `POST /api/business/image-edit-chat/sessions/{sessionId}/confirm` | 会话可先传 `message`；执行前必须有 `imageUrl` | `quality`、`size`、`referenceImages`、`selectionHints`、`routingPreference` | `messages` + `plan` + `run.runId` | 独立于直接图编辑 API 的 Agent 入口；当前默认 GPT-5.5 规划 + GPT Image 2 执行，批量/快速/低成本时再分流专项能力。 |

规划中、尚未开放的市场端正式能力：

| 业务 | 计划入口 | 当前状态 | 说明 |
| --- | --- | --- | --- |
| 商品组图 / 营销套图 `product_image_set` | `POST /api/business/product-image-set/plan` + `/runs` | 待实现 | 契约草案见 `docs/strategy/market-side-ai-ability-contracts-2026-06-11.md`。当前不要直接调用该路径；可用 `product_commercialization action=visual_generate` 做试验。 |
| 模特 / 场景图 `model_scene_image` | `POST /api/business/model-scene-image/plan` + `/runs` | 待实现 | 重点是参考图角色、身份锚点、主体真源和质量标签；当前未开放线上接口。 |
| 产品推广视频素材包 `promo_video` | `POST /api/business/promo-video/plan` + `/keyframes/runs` + `/runs` + `/compose/runs` | 已开放 MVP | 对业务方已经拆成规划、关键帧、分段视频和可选合成四个入口；运行任务业务键为 `promo_video`，内部实现仍复用产品商业化编排服务。 |

产品商业化视频执行补充口径：

- Vidu 固定画幅试点不再直接把原始 Vidu 段作为唯一最终交付。后端会先用 GPT Image 2 生成商业首帧，再确定性归一化到目标画幅，然后把归一化首帧交给 Vidu 生成动态素材段。
- 当 `resultPayload.videoAssetPackage.deliveryStatus=composed_ready` 时，`videoUrls[0]` 是后端 ffmpeg 组合后的推荐成片，`videoUrls[1...]` 是保留的原始分段素材。
- `resultPayload.videoAssetPackage.composition.output.mode=opening_hold_plus_vidu_segment` 表示“完整商品开场 + Vidu 动态细节段”；常见字段包括 `introHoldSeconds`、`transitionSeconds`、`tailSeconds`、`sourceFirstFrameUrl`、`sourceSegmentVideoUrl`。
- 成本动作会同时记录 `openai.gpt_image_2.image`、`vidu.viduq3_turbo.video`、`ffmpeg.compose`。其中 ffmpeg 是自有后处理，不代表第三方视频模型再次扣费。
- 原始 Vidu 段可能快速推进到局部细节，不适合作为唯一验收口径；业务方如只需要素材包，可读取 `resultPayload.videoAssetPackage.segmentVideos`。

调用上下文兼容接口：

- 中台主概念是能力、版本、路由、调用、结果、质量和成本；客户端的项目、工单、订单、素材夹、业务流程由客户端自行组装。
- 现存 `/api/business/projects/*` 是 v0.6 兼容调用上下文接口，用于旧链路回溯 run、资产和选择证据，不应作为新的中台产品主线。
- 新业务提交优先使用 `clientContextId/inputAssetIds/clientRequestId` 关联客户端侧链路；只有兼容旧链路时才使用 `projectId/flowStepKey`。
- 中台记录的是调用证据和输出资产，不负责客户端项目 CRUD 的业务语义。

### 0.1) 最小调用示例

业务方拿到 `X-PODI-API-Key` 后，可以直接按下面两步接入。示例中的 Key 是占位符，不要把真实 Key 写入仓库或公开文档。

提交图裂变：

```bash
curl -X POST "$PODI_BACKEND/api/business/fission/runs" \
  -H "X-PODI-API-Key: $PODI_BUSINESS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "imageUrl": "https://example.com/input.png",
    "prompt": "保持主体结构，生成同系列变化图",
    "source": "partner-api",
    "channel": "open-api",
    "traceId": "biz_trace_001",
    "callbackUrl": "https://your-service.example.com/podi/callback"
  }'
```

查询结果：

```bash
curl -X POST "$PODI_BACKEND/api/business/runs/get" \
  -H "X-PODI-API-Key: $PODI_BUSINESS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "runId": "提交接口返回的 runId"
  }'
```

管理员开通业务 Key：

```bash
curl -X POST "$PODI_BACKEND/api/admin/business/api-keys" \
  -H "Authorization: Bearer $PODI_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "业务方 A · 开放接口",
    "key": "podi_live_xxx",
    "status": "active",
    "tenantId": "tenant-a",
    "clientId": "open-api",
    "allowedBusinessKeys": ["fission", "text_fission", "fission_evaluate", "outpaint", "pattern_extract", "image_edit", "image_edit_chat", "product_design", "product_commercialization", "promo_video"],
    "expireAt": "2026-12-31T23:59:59+08:00"
  }'
```

管理端“API 开放”页也可以直接生成、创建、停用业务 Key，并查看每个 Key 的调用记录。

### 0.2) AI 图片助手

AI 图片助手是独立 Agent 业务入口，治理 key 为 `image_edit_chat`；直接图编辑仍是 `image_edit`，接口仍为 `/api/business/image-edit/runs`。两者共享 runId、资产和排障证据，但调用方式、产品入口和用户心智必须拆开：助手负责像聊天一样收集诉求、调用 GPT-5.5 / Responses API 或规则 planner 生成结构化 JSON 计划，再由后端按白名单、schema、置信度、风险和成本校验后创建业务 run。当前阶段采用质量优先主路径：普通单张图片任务默认走 `business.image_edit`，即 GPT Image 2；专项能力主要用于批量、速度、低成本或固定 SOP。

当前白名单工具：

| 工具 | 业务 run | 适用意图 |
| --- | --- | --- |
| `business.image_edit` | `image_edit` | GPT Image 2 质量优先主路径：开放式单张生成/改图、局部修补、换色、参考图迁移、扩图式编辑、单张高质量花纹提取。 |
| `business.pattern_extract` | `pattern_extract` | 专项加速路径：用户明确要求批量、快速、低成本或固定花纹提取 SOP 时使用。 |

`confirm` 是历史接口名，本质是后端幂等执行边界；产品语言不要做成二次确认按钮。前端可以在计划满足执行条件后自动调用；低置信、缺图、高风险或后续高成本多阶段能力才需要停下来追问或人工复核。

会话边界和幂等规则：

- 新建会话必须调用 `POST /api/business/image-edit-chat/sessions`；不传 `sessionId` 时不会隐式续聊旧会话。
- 创建会话建议传 `requestId`；同一 `agentKey + requestId + tenantId + clientId` 重复提交会复用原会话，避免网络重试创建多个方案。
- 创建会话如果带首轮 `message`，也可以同时传 `editSkill`、`quality`、`size`、`outputFormat`、`maskUrl`、`referenceImages`、`selectionHints`；这些字段和追加消息接口的语义一致。
- 追加消息必须显式带 `sessionId`，每次追加都会生成新的最新计划；旧计划不能再提交执行。
- 执行边界只允许提交当前会话的最新 `awaiting_confirmation` 计划；提交中会进入 `confirming`，成功后为 `executed` 并返回业务 `runId`。
- 已执行计划重复提交会返回原来的 `runId`，不会重复创建业务任务。

创建会话并生成首条 AI 图片助手回复：

```bash
curl -X POST "$PODI_BACKEND/api/business/image-edit-chat/sessions" \
  -H "X-PODI-API-Key: $PODI_BUSINESS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "imageUrl": "https://example.com/input.png",
    "message": "把这张图改得更高级一些，适合连衣裙面料，保持主花型不变。",
    "source": "partner-api",
    "channel": "image-edit-chat",
    "requestId": "image-edit-chat-session-20260602-001"
  }'
```

响应摘要：

```json
{
  "session": {
    "id": "ags_xxx",
    "agentKey": "agent.image_edit_assistant",
    "status": "awaiting_confirmation",
    "imageUrl": "https://example.com/input.png",
    "latestPlanId": "agp_xxx"
  },
  "plan": {
    "id": "agp_xxx",
    "status": "awaiting_confirmation",
    "toolName": "business.image_edit",
    "estimatedCostLevel": "low",
    "riskLevel": "low",
    "toolPayload": {
      "imageUrl": "https://example.com/input.png",
      "editSkill": "local_modify",
      "quality": "preview",
      "size": "auto",
      "output_format": "png",
      "instruction": "..."
    }
  }
}
```

普通单张花纹提取类诉求默认走 GPT Image 2 质量优先主路径，示例响应摘要：

```json
{
  "plan": {
    "id": "agp_xxx",
    "intent": "image_edit",
    "toolName": "business.image_edit",
    "routeEvidence": {
      "routeType": "image2_quality_first",
      "targetAbility": "business.image_edit",
      "targetBusinessKey": "image_edit",
      "primaryExecutionEngine": "gpt-image-2",
      "specializedAbilityCandidate": {
        "targetAbility": "business.pattern_extract",
        "targetBusinessKey": "pattern_extract"
      },
      "confidence": 0.84,
      "routeReason": "用户目标可由花纹提取专项能力覆盖，但当前 AI 图片助手采用 GPT-5.5 规划 + GPT Image 2 质量优先主路径。"
    },
    "toolPayload": {
      "imageUrl": "https://example.com/tablecloth.png",
      "instruction": "把这个桌布的花纹提取出来。执行约束：使用 GPT Image 2 做单张质量优先处理...",
      "editSkill": "local_modify",
      "quality": "preview",
      "size": "auto",
      "output_format": "png"
    }
  }
}
```

如果用户明确要求“批量快速提取”“低成本跑一批”“走花纹提取能力”，才会分流到 `business.pattern_extract`，`routeType=ability_accelerated`，payload 使用 `prompt/batch/size`，不会带 `editSkill`。

追加消息生成新方案：

```bash
curl -X POST "$PODI_BACKEND/api/business/image-edit-chat/sessions/ags_xxx/messages" \
  -H "X-PODI-API-Key: $PODI_BUSINESS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "requestId": "image-edit-chat-message-002",
    "message": "再偏复古一点，但不要改变构图。",
    "quality": "preview",
    "size": "auto"
  }'
```

`messages` 的 `requestId` 是消息级幂等键：同一 `sessionId + requestId` 只生成一张方案卡。网络重试应复用同一个 `requestId`；新的改图诉求必须换新的 `requestId`。

提交最新计划并创建业务 run：

```bash
curl -X POST "$PODI_BACKEND/api/business/image-edit-chat/sessions/ags_xxx/confirm" \
  -H "X-PODI-API-Key: $PODI_BUSINESS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "requestId": "image-edit-chat-confirm-agp-001",
    "overrides": {
      "quality": "production"
    }
  }'
```

执行边界响应会返回 `run.runId`，之后继续用 `/api/business/runs/get` 查询结果。需要严格提交某个方案版本时，也可调用兼容接口 `POST /api/business/image-edit-chat/sessions/{sessionId}/plans/{planId}/confirm`；旧 `/api/business/agents/image-edit/*` 路径仅作为技术兼容入口，不作为新接入文档推荐。

错误：

| 错误码 | HTTP | 处理方式 |
| --- | --- | --- |
| `AGENT_CAPABILITY_NOT_FOUND` | 404 | 检查 Agent key，当前只支持 `agent.image_edit_assistant`。 |
| `AGENT_MESSAGE_REQUIRED` | 400 | 补充用户改图诉求。 |
| `AGENT_MESSAGE_DUPLICATE_IN_PROGRESS` | 409 | 同一消息 `requestId` 正在处理中，稍后查询会话或重试同一请求。 |
| `AGENT_IMAGE_URL_INVALID` | 400 | 图片必须是 HTTP(S) URL。 |
| `AGENT_IMAGE_URL_REQUIRED` | 400 | 执行前上传或传入主图。 |
| `AGENT_SESSION_NOT_FOUND` | 404 | 检查 `sessionId`。 |
| `AGENT_SESSION_FORBIDDEN` | 403 | 检查业务 API Key 的租户/客户端范围。 |
| `AGENT_PLAN_REQUIRED` | 400 | 当前会话还没有可执行计划，请先发送一条消息生成计划。 |
| `AGENT_PLAN_NOT_FOUND` | 404 | 检查 `planId` 是否属于当前会话。 |
| `AGENT_PLAN_STALE` | 409 | 当前提交的计划不是会话最新计划，拉取会话后提交最新计划。 |
| `AGENT_PLAN_CONFIRM_IN_PROGRESS` | 409 | 计划正在提交执行中，稍后查询会话或重试同一请求。 |
| `AGENT_PLAN_REQUIRES_CLARIFICATION` | 409 | 当前计划仍需补充目标、保留项或处理范围，前端继续对话，不创建下游 run。 |
| `AGENT_PLAN_NOT_CONFIRMABLE` | 409 | 计划已执行或状态不可提交，重新生成计划。 |
| `AGENT_TOOL_CALL_FAILED` | 502/500 | 查看返回错误和对应业务 run/能力日志。 |

通用追踪字段：

- `source`：调用来源，例如 `coze`、`client`、`partner-api`。
- `channel`：具体入口，例如 `coze-workflow`、`open-api`、`eval`。
- `traceId`：跨系统排查 ID，建议业务方生成并传入。
- `requestId`：业务方请求 ID。AI 图片助手创建会话时同一 `agentKey + requestId + tenantId + clientId` 会复用原会话；执行边界请求会把该值传递到底层业务 run，网络重试应复用稳定值。
- `tenantId/clientId`：租户和客户端标识，用于灰度、配额、统计和隔离。业务方通常不需要传，优先由业务 API Key 绑定；显式传入时必须与 Key 或登录账号范围一致。
- `userId`：业务方自己的用户标识，只作为外部上下文和排查字段保留；不会直接写入平台用户外键，也不会替代平台登录用户。
- `callbackUrl`：可选 Webhook。配置后任务终态会通知业务方；即使 Webhook 失败，业务方仍可用 `runId` 轮询查询结果。常规业务链路是“提交后拿 `runId` 轮询”，不要把这个和 Webhook 回调混为一谈。

状态约定：

- `queued/running`：任务还在排队或执行，业务方继续轮询。
- `succeeded`：任务成功，读取 `imageUrls/videoUrls/texts`；结构化评分优先读取 `texts` 或轻量 `resultPayload`，完整链路证据用 `detail=full` 查询。
- `failed/cancelled/timeout`：任务不可继续，读取 `error/errorMessage` 并按错误码处理。

### 0.2) 与管理端 API 开放页对齐

管理端“API 开放”页展示的业务接口必须和本文档保持一致：

| 页面名称 | 接口 | 文档位置 | 必填/核心字段 | 冒烟口径 |
| --- | --- | --- | --- | --- |
| 业务 OpenAPI | `GET /api/business/openapi.json` | 8) OpenAPI 工具箱 | 无 | 返回 200，且包含业务提交、路由预览、任务查询工具。 |
| 花纹提取 | `POST /api/business/pattern-extract/runs` | 2) 提交花纹提取 | `imageUrl` | 可先用 route-preview 验证版本命中；真实出图必须确认 `runId/status/imageUrls`。 |
| 图裂变 | `POST /api/business/fission/runs` | 3) 提交图裂变 | `imageUrl` | 可先用 route-preview 验证版本命中；真实出图必须确认 `runId/status/imageUrls`。 |
| 产品设计 | `POST /api/business/product-design/runs` | 3.3) 产品设计能力 | `imageUrl`、`designBrief` | 可先用 route-preview 验证版本命中；真实出图必须确认 `runId/status/imageUrls`。 |
| 文字强化裂变（文生图）提示词 | `POST /api/business/text-fission/prompts` | 3.1) 文字强化裂变（文生图）两步接口 | `imageUrl` | 真实调用必须确认 `editablePrompt/promptDraftId`，并由用户确认或修改。 |
| 文字强化裂变（文生图）生图 | `POST /api/business/text-fission/runs` | 3.1) 文字强化裂变（文生图）两步接口 | `imageUrl`、`editable_prompt` | 真实出图必须确认 `runId/status/imageUrls`；固定一次生成 1 张图。 |
| 裂变生成图评估 | `POST /api/business/fission-evaluate/runs` | 4) 提交裂变生成图评估 | `originalImageUrl`、`generatedImageUrl` | 真实提交必须确认 `runId/status/texts/resultPayload`。 |
| 扩图 | `POST /api/business/outpaint/runs` | 5) 提交扩图 | `imageUrl` | 可先用 route-preview 验证版本命中；真实出图必须确认 `runId/status/imageUrls`。 |
| 查询业务任务 | `POST /api/business/runs/get` | 6) 查询业务任务 | `runId` | 使用不存在的 `runId` 时应返回 `BUSINESS_RUN_NOT_FOUND` 或等价 404，不应返回 500。 |
| 兼容调用上下文 | `POST /api/business/projects` | 0.4) 兼容调用上下文 | `name` | 仅兼容旧链路；新接入优先用 `clientContextId/inputAssetIds/clientRequestId` 关联调用证据。 |

维护规则：

- 页面新增业务接口时，本文档必须同步新增请求、响应和错误说明。
- 本文档新增业务接口时，管理端“API 开放”页必须同步露出或说明暂不露出的原因。
- 业务方默认只需要使用提交接口和查询接口；路由预览属于上线、灰度和排障工具。

### 0.3) 业务 API 错误处理口径

| 场景 | 常见错误码 | 业务方动作 | 平台动作 |
| --- | --- | --- | --- |
| 缺少主图或 runId | `BUSINESS_IMAGE_URL_REQUIRED`、`BUSINESS_RUN_ID_REQUIRED` | 修正入参后重新提交，不建议自动重试。 | 前端表单必须提前提示必填项。 |
| 鉴权或业务方范围不允许 | `AUTHORIZATION_REQUIRED`、`BUSINESS_USER_SCOPE_REQUIRED`、`BUSINESS_USER_SCOPE_FORBIDDEN` | 检查 Token、账号绑定的业务方范围或接入配置。 | 管理端账号权限页和业务方配置页给出中文处理建议。 |
| 业务版本或配方不可用 | `BUSINESS_CAPABILITY_NOT_FOUND`、`BUSINESS_RECIPE_INVALID`、`BUSINESS_RECIPE_ABILITY_NOT_AVAILABLE` | 暂停调用该业务版本，保留 `traceId/requestId` 给平台排查。 | 检查默认版本、配方步骤、能力启停、模型门禁和回滚版本。 |
| 业务方额度或并发限制 | `BUSINESS_CLIENT_DISABLED`、`BUSINESS_CLIENT_BUSINESS_NOT_ALLOWED`、`BUSINESS_CLIENT_CONCURRENCY_LIMITED`、`BUSINESS_CLIENT_DAILY_RUN_LIMITED`、`BUSINESS_CLIENT_DAILY_QUOTA_LIMITED` | 不要高频重试；等并发释放或联系平台调整策略。 | 管理端业务方配置页必须能看到限制来源。 |
| 执行节点、队列或上游失败 | `COMFYUI_IMAGE_REQUIRED`、`COMFYUI_TIMEOUT`、`ABILITY_TASK_FAILED`、`VENDOR_API_EXECUTION_FAILED` | 可按业务策略稍后重试一次；连续失败时保留 `runId/taskId` 排查。 | 检查执行节点健康、队列、模型 Key、出网、OSS 回填和能力调用日志。 |
| 查询不到任务 | `BUSINESS_RUN_NOT_FOUND`、`BUSINESS_RUN_FORBIDDEN` | 确认 `runId` 是否属于当前业务方，不要把底层 `taskId` 当 `runId` 使用。 | 排查租户隔离、任务写入和历史数据迁移。 |
| 查询临时不可用 | `BUSINESS_RUN_TEMPORARY_UNAVAILABLE` | 稍后重试查询，不需要重新提交任务；持续出现时把 `runId/traceId` 发给平台。 | 检查数据库、索引、连接池和业务步骤查询链路，禁止把 SQL 原文返回给业务方。 |
| 兼容调用上下文非法 | `PROJECT_NOT_FOUND`、`PROJECT_FORBIDDEN`、`PROJECT_RUN_LINK_INVALID` | 旧链路检查 `projectId/inputAssetIds/tenantId/clientId` 是否属于同一个业务方；新链路优先改用 `clientContextId`。 | 任务提交前拦截，不允许把跨上下文资产串到同一个 run。 |
| 兼容资产或交付包非法 | `PROJECT_ASSET_TYPE_INVALID`、`PROJECT_ASSET_URL_REQUIRED`、`PROJECT_ASSET_URL_INVALID`、`PROJECT_SELECTION_ASSET_REQUIRED`、`PROJECT_EXPORT_ASSETS_EMPTY` | 修正资产类型、URL 或候选资产后重试。 | 文档、客户端表单和服务端枚举必须保持一致。 |

---

### 0.4) 兼容调用上下文

用途：兼容旧客户端把“上下文 -> 资产 -> 业务 run -> 候选选择 -> 交付清单”串起来的轻量证据底座。中台主线仍是能力，不负责客户端项目/工单/订单语义；新接入优先在业务提交接口传 `clientContextId/inputAssetIds/clientRequestId`。

#### POST /api/business/projects

请求：

```json
{
  "name": "夏季花纹工作单",
  "scenario": "pattern_to_product",
  "flowTemplateId": "pattern_to_product_v1",
  "currentFlowStepKey": "upload_assets",
  "metadata": {
    "clientProjectNo": "P-20260602-001"
  }
}
```

响应：

```json
{
  "id": "proj_xxx",
  "name": "夏季花纹工作单",
  "scenario": "pattern_to_product",
  "status": "draft",
  "tenantId": "tenant-a",
  "clientId": "studio",
  "currentFlowStepKey": "upload_assets",
  "flowTemplateId": "pattern_to_product_v1",
  "assetCount": 0,
  "runCount": 0,
  "createdAt": "2026-06-02T15:30:00"
}
```

常见错误：

- `PROJECT_NAME_REQUIRED`
- `PROJECT_SCENARIO_INVALID`
- `BUSINESS_USER_SCOPE_REQUIRED`
- `BUSINESS_USER_SCOPE_FORBIDDEN`

#### GET /api/business/projects

查询参数：

- `scenario`：可选，按业务场景过滤。
- `status`：可选，按兼容上下文状态过滤。
- `limit/offset`：分页参数，`limit` 最大 100。

响应：

```json
{
  "items": [
    {
      "id": "proj_xxx",
      "name": "夏季花纹工作单",
      "status": "active",
      "assetCount": 8,
      "runCount": 5,
      "latestRunStatus": "succeeded"
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

常见错误：

- `PROJECT_STATUS_INVALID`
- `PROJECT_SCENARIO_INVALID`
- `BUSINESS_USER_SCOPE_REQUIRED`
- `BUSINESS_USER_SCOPE_FORBIDDEN`

#### GET /api/business/projects/{projectId}

用途：返回兼容上下文、资产、run 关联、候选选择和交付包摘要，供客户端恢复工作台和渲染流程监控。

响应：

```json
{
  "project": {
    "id": "proj_xxx",
    "name": "夏季花纹工作单",
    "currentFlowStepKey": "variant_fission",
    "assetCount": 8,
    "runCount": 5
  },
  "assets": [
    {
      "id": "asset_xxx",
      "assetType": "variant",
      "url": "https://podi.oss-cn-hangzhou.aliyuncs.com/output.png",
      "sourceRunId": "run_xxx",
      "sourceFlowStepKey": "variant_fission",
      "selected": true
    }
  ],
  "runs": [
    {
      "runId": "run_xxx",
      "businessKey": "fission",
      "status": "succeeded",
      "flowStepKey": "variant_fission",
      "inputAssetIds": ["asset_input"],
      "outputAssetIds": ["asset_xxx"],
      "assetSyncStatus": "succeeded"
    }
  ],
  "selections": [],
  "exportPackages": []
}
```

常见错误：

- `PROJECT_NOT_FOUND`
- `PROJECT_FORBIDDEN`

#### PATCH /api/business/projects/{projectId}

请求：

```json
{
  "name": "夏季花纹工作单 A 版",
  "status": "active",
  "currentFlowStepKey": "variant_fission",
  "metadata": {
    "operatorNote": "已进入候选筛选"
  }
}
```

响应：同 `POST /api/business/projects`。

常见错误：

- `PROJECT_NOT_FOUND`
- `PROJECT_FORBIDDEN`
- `PROJECT_STATUS_INVALID`

#### POST /api/business/projects/{projectId}/assets

请求：

```json
{
  "assetType": "input_image",
  "url": "https://podi.oss-cn-hangzhou.aliyuncs.com/input.png",
  "contentType": "image/png",
  "fileName": "input.png",
  "flowStepKey": "upload_assets",
  "tags": ["fabric", "summer"],
  "metadata": {
    "source": "client-upload"
  }
}
```

响应：

```json
{
  "id": "asset_xxx",
  "projectId": "proj_xxx",
  "assetType": "input_image",
  "url": "https://podi.oss-cn-hangzhou.aliyuncs.com/input.png",
  "sourceFlowStepKey": "upload_assets",
  "selected": false,
  "createdAt": "2026-06-02T15:35:00"
}
```

常见错误：

- `PROJECT_NOT_FOUND`
- `PROJECT_FORBIDDEN`
- `PROJECT_ASSET_TYPE_INVALID`
- `PROJECT_ASSET_URL_REQUIRED`
- `PROJECT_ASSET_URL_INVALID`

#### GET /api/business/projects/{projectId}/assets

查询参数：

- `assetType`：可选，按资产类型过滤。
- `selected`：可选，`true/false`。
- `limit/offset`：分页参数。

响应：

```json
{
  "items": [
    {
      "id": "asset_xxx",
      "assetType": "variant",
      "url": "https://podi.oss-cn-hangzhou.aliyuncs.com/output.png",
      "selected": true
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

常见错误：

- `PROJECT_NOT_FOUND`
- `PROJECT_FORBIDDEN`
- `PROJECT_ASSET_TYPE_INVALID`

#### 带兼容调用上下文提交业务 run

任一业务提交接口都可以增加以下字段。字段也可放在 `metadata.projectContext`，用于兼容不同客户端封装；新接入优先使用 `clientContextId`。

```json
{
  "imageUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/input.png",
  "projectId": "proj_xxx",
  "flowStepKey": "variant_fission",
  "flowStepName": "候选裂变",
  "flowTemplateId": "pattern_to_product_v1",
  "inputAssetIds": ["asset_input"],
  "clientRequestId": "client_req_001"
}
```

响应仍以业务 run 提交接口为准。中台额外写入兼容上下文 run 关联；run 成功终态后会将 `imageUrls/videoUrls` 自动登记为资产证据，`assetSyncStatus` 可在兼容上下文 run 列表中查看。

常见错误：

- `PROJECT_NOT_FOUND`
- `PROJECT_FORBIDDEN`
- `PROJECT_RUN_LINK_INVALID`
- 原业务提交接口已有错误码，例如 `BUSINESS_IMAGE_URL_REQUIRED`、`BUSINESS_CLIENT_CONCURRENCY_LIMITED`、`ABILITY_TASK_FAILED`

#### GET /api/business/projects/{projectId}/runs

响应：

```json
{
  "items": [
    {
      "runId": "run_xxx",
      "businessKey": "fission",
      "status": "succeeded",
      "flowStepKey": "variant_fission",
      "inputAssetIds": ["asset_input"],
      "outputAssetIds": ["asset_variant"],
      "assetSyncStatus": "succeeded",
      "errorCode": null,
      "errorMessage": null
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

常见错误：

- `PROJECT_NOT_FOUND`
- `PROJECT_FORBIDDEN`

#### POST /api/business/projects/{projectId}/selections

用途：记录用户从候选池中选中的资产，供后续步骤读取。

请求：

```json
{
  "assetIds": ["asset_variant"],
  "sourceFlowStepKey": "variant_fission",
  "targetFlowStepKey": "product_design",
  "note": "进入产品图生成"
}
```

响应：

```json
[
  {
    "id": "sel_xxx",
    "projectId": "proj_xxx",
    "assetId": "asset_variant",
    "sourceFlowStepKey": "variant_fission",
    "targetFlowStepKey": "product_design",
    "note": "进入产品图生成"
  }
]
```

常见错误：

- `PROJECT_NOT_FOUND`
- `PROJECT_FORBIDDEN`
- `PROJECT_SELECTION_ASSET_REQUIRED`
- `PROJECT_SELECTION_ASSET_INVALID`
- `PROJECT_SELECTION_TARGET_REQUIRED`

#### POST /api/business/projects/{projectId}/exports

当前版本生成可下载 ZIP。ZIP 内包含 `manifest.json`、`summary.json`、`assets.json`、`run_ids.json` 和 `README.txt`；媒体文件暂不下载进包内，仍通过自有 OSS URL 引用。

请求：

```json
{
  "assetIds": ["asset_variant", "asset_product"],
  "includeRunEvidence": true,
  "includeQualitySummary": true,
  "metadata": {
    "purpose": "business-review"
  }
}
```

响应：

```json
{
  "id": "pkg_xxx",
  "projectId": "proj_xxx",
  "status": "ready",
  "assetIds": ["asset_variant", "asset_product"],
  "runIds": ["run_xxx"],
  "downloadUrl": "https://podi.example.com/api/business/projects/proj_xxx/exports/pkg_xxx/download",
  "manifest": {
    "projectId": "proj_xxx",
    "assets": []
  },
  "summary": {
    "assetCount": 2,
    "runCount": 1
  }
}
```

常见错误：

- `PROJECT_NOT_FOUND`
- `PROJECT_FORBIDDEN`
- `PROJECT_EXPORT_ASSETS_EMPTY`
- `PROJECT_EXPORT_ASSET_INVALID`
- `PROJECT_EXPORT_BUILD_FAILED`
- `PROJECT_EXPORT_FILE_NOT_FOUND`

#### GET /api/business/projects/{projectId}/exports/{packageId}

响应：同 `POST /api/business/projects/{projectId}/exports`。

常见错误：

- `PROJECT_NOT_FOUND`
- `PROJECT_FORBIDDEN`

#### GET /api/business/projects/{projectId}/exports/{packageId}/download

用途：下载兼容上下文交付 ZIP。

响应：

- `200 application/zip`
- 文件名格式：`<context-name>-<packageId>.zip`

常见错误：

- `PROJECT_NOT_FOUND`
- `PROJECT_FORBIDDEN`
- `PROJECT_EXPORT_FILE_NOT_FOUND`

## 1) 业务能力清单

### GET /api/business/capabilities

用途：返回当前可用业务能力版本、发布时间、默认状态和底层配方。

响应示例：

```json
{
  "items": [
    {
      "id": "biz_fission_v1_flux_strong_hq_softstyle",
      "businessKey": "fission",
      "version": "v1",
      "displayName": "图裂变 · FLUX Strong HQ Softstyle",
      "status": "active",
      "isDefault": true,
      "releaseTime": "2026-04-24T00:00:00",
      "recipe": {
        "primaryAbilityId": "comfyui_flux_strong_hq_softstyle_fission"
      },
      "inputSchema": { "fields": [] },
      "metadata": { "entry": "business-api", "seed_version": 1 },
      "primaryAbilityId": "comfyui_flux_strong_hq_softstyle_fission",
      "primaryAbilityName": "图裂变 · 高质量多元素花纹",
      "vendorModelId": null,
      "vendorModelName": null,
      "recipeSteps": [
        {
          "order": 1,
          "id": "primary",
          "type": "ability_task",
          "role": "primary",
          "enabled": true,
          "abilityId": "comfyui_flux_strong_hq_softstyle_fission",
          "abilityName": "图裂变 · 高质量多元素花纹",
          "abilityProvider": "comfyui"
        }
      ]
    }
  ]
}
```

常见错误：

- `AUTHORIZATION_REQUIRED`

---

## 1.1) 业务配方结构

业务配方用于描述一个业务版本背后调用哪些原子能力。第一阶段已经支持配置校验、前端摘要展示、运行步骤记录，以及 VL 辅助步骤的真实提交和状态追踪。

执行边界：

- `primaryAbilityId` 对应的主能力仍是出图真源，决定业务任务的最终 `status/imageUrls/error`。
- `vlAssist.enabled=true` 时，业务层会把 VL 步骤作为伴随任务提交并记录在 `steps` 中。
- 默认模式下，VL 不阻塞主能力，适合先做观测和结果积累。
- 如果配方设置 `mode=vl_then_primary`，或设置 `vlAssist.waitForResult=true` / `vlAssist.applyToPrimary=true`，业务层会先提交 VL，等 VL 成功后再提交主能力。
- 阻塞式 VL 串联默认会把 `promptCard.imageDesc` 回填到图裂变 `image_desc`，把 `promptCard.positivePrompt` 回填到花纹提取/图裂变/扩图 `prompt`；只有原请求未填写这些字段时才自动回填。
- GPT Image 2 图裂变新版使用专用编译器：VL 输出 `vlCard` 后，中台会编译成英文图片编辑提示词，并映射 `quality/size/output_format/n=1` 等 OpenAI 参数；业务方不用理解 VL 卡片和模型参数。该业务版固定一个请求生成一张图，需要多张时由业务方发起多次请求，分别获得多个 `runId`。
- ComfyUI VL 控制卡裂变新版使用 `vl_fission_control_card` 作为统一 VL 组件，输出 `fissionControlCard` 后再传给 `comfyui_flux_strong_hq_softstyle_fission_control_v1`；后续更换 VL 模型时优先改这个组件的默认 provider。
- ComfyUI 颜色锁定裂变版使用版本 `comfyui-vl-control-v2`，主能力为 `comfyui_flux_strong_hq_softstyle_fission_colorlock_v2`。VL 输出必须包含 `palette_card`，中台会把颜色卡和硬负向约束拼进 `image_desc`。`denoise` 不写死，继续按 `bili` 约定映射；其他颜色锁定强度按交付包固定。
- 图裂变业务入口兼容 `size=1536x1024` 这类尺寸预设：GPT Image 2 线路会原样传递 `size`，ComfyUI 默认线/VL 控制卡线/颜色锁定线会在后端转为 `width/height` 后再调用工作流；若调用方已显式传入 `width/height`，以后者为准。
- ComfyUI 颜色锁定裂变版内置“比例重构”分支：当业务方传入的 `width/height` 与原图比例明显不一致时，先由 VL 判断是否为满版密集小元素图案；允许时后端生成目标比例引导图，再调用同一个 ComfyUI 工作流。若不适合比例重构，后端会保留用户目标画布走直接出图，并在 `metadata.fissionAspectRecompose.route=direct_target_size` 中记录原因，不再静默回退到原图尺寸。ComfyUI 线路会按 16 像素安全倍数归一，例如 `228x1350` 会进入 `224x1344`。
- 文字强化裂变（文生图）使用两步式业务接口：第一步 `text-fission/prompts` 只生成可编辑提示词；第二步 `text-fission/runs` 只接收用户最终确认后的 `editable_prompt` 并提交 ComfyUI 文生图。第二步不再二次调用 VL，固定一次生成 1 张图。
- 裂变生成图评估底层仍是原子能力 `vl_fission_generated_image_evaluate`，但已经提供业务包装入口 `/api/business/fission-evaluate/runs`。它只输出 `pass / needs_refission / reject` 和问题标签，不在业务层自动二次裂变；业务方可按自己的策略决定是否再次调用图裂变。

推荐结构：

```json
{
  "mode": "pipeline",
  "primaryAbilityId": "ability_openai_fission",
  "vlAssist": {
    "enabled": true,
    "abilityId": "vl_analyze_image"
  },
  "steps": [
    {
      "id": "vl",
      "type": "vl_analyze",
      "role": "preprocess",
      "abilityId": "vl_analyze_image"
    },
    {
      "id": "primary",
      "type": "ability_task",
      "role": "primary",
      "abilityId": "ability_openai_fission"
    }
  ]
}
```

阻塞式串联结构：

```json
{
  "mode": "vl_then_primary",
  "primaryAbilityId": "ability_openai_fission",
  "vlAssist": {
    "enabled": true,
    "abilityId": "vl_analyze_image",
    "waitForResult": true,
    "applyToPrimary": true
  },
  "steps": [
    {
      "id": "vl",
      "type": "vl_analyze",
      "role": "preprocess",
      "abilityId": "vl_analyze_image"
    },
    {
      "id": "primary",
      "type": "ability_task",
      "role": "primary",
      "abilityId": "ability_openai_fission"
    }
  ]
}
```

校验规则：

- `primaryAbilityId` 必须指向存在的原子能力。
- `steps` 中启用的执行步骤必须配置 `abilityId`，且能力必须存在。
- `vlAssist.enabled=true` 时默认使用 `vl_analyze_image`，也可以显式指定其他 VL 能力；提交业务任务时可在 `inputs.vl_provider`、`inputs.coze_workflow_id`、`inputs.vl_prompt` 覆盖 VL 来源和分析要求。
- 阻塞式 VL 串联中，VL 失败时主能力不会提交，业务任务直接进入 `failed`，错误会保留在 `steps[0].error` 和业务任务 `error` 中。
- 未知步骤类型会被拒绝，避免把不可执行配置带到线上。

管理端已提供“VL 前置分析”开关和能力选择框；普通运营只需要切换表单，不需要直接编辑 JSON。

---

## 2) 提交花纹提取

### POST /api/business/pattern-extract/runs

请求体：

```json
{
  "imageUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/demo/input.png",
  "prompt": "提取主体花纹，保留清晰边缘和面料纹理",
  "negative_prompt": "不要背景、不要阴影、不要文字水印",
  "width": 1800,
  "height": 1800,
  "batch": 1,
  "lora": "杯子1124.safetensors",
  "source": "coze",
  "channel": "coze-workflow",
  "traceId": "trace-pattern-001",
  "requestId": "req-pattern-001",
  "tenantId": "tenant-a",
  "clientId": "coze-main-workflow",
  "metadata": {
    "grayKey": "tenant-a"
  }
}
```

响应体同图裂变。

常见错误：

- `BUSINESS_IMAGE_URL_REQUIRED`
- `BUSINESS_CAPABILITY_NOT_FOUND`
- `BUSINESS_RECIPE_INVALID`
- `BUSINESS_RECIPE_ABILITY_NOT_AVAILABLE`
- `BUSINESS_CLIENT_DISABLED`
- `BUSINESS_CLIENT_BUSINESS_NOT_ALLOWED`
- `BUSINESS_USER_SCOPE_REQUIRED`
- `BUSINESS_USER_SCOPE_FORBIDDEN`
- `BUSINESS_CLIENT_CONCURRENCY_LIMITED`
- `BUSINESS_CLIENT_DAILY_RUN_LIMITED`
- `BUSINESS_CLIENT_DAILY_QUOTA_LIMITED`
- `COMFYUI_IMAGE_REQUIRED`
- `COMFYUI_TIMEOUT`

说明：

- 新接入建议把 `prompt/negative_prompt/width/height/batch/lora/timeout` 直接作为顶层字段传入。
- 旧调用仍兼容把同名参数放在 `inputs` 内。
- LoRA 为空时使用当前默认业务版本内置配置；切换默认版本由中台完成，业务方不需要替换底层 workflow。

---

## 3) 提交图裂变

### POST /api/business/fission/runs

请求体：

```json
{
  "imageUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/demo/input.png",
  "prompt": "保持原始花型主体，生成更适合服装面料的变体",
  "version": null,
  "bili": 65,
  "width": 1024,
  "height": 1024,
  "image_desc": "蓝白色植物纹样，中心构图",
  "source": "coze",
  "channel": "coze-workflow",
  "traceId": "trace-demo-001",
  "requestId": "req-demo-001",
  "tenantId": "tenant-a",
  "clientId": "coze-main-workflow",
  "inputs": {
    "兼容说明": "旧调用仍可继续把参数放在 inputs 内；新调用建议使用顶层字段"
  },
  "callbackUrl": "https://example.com/podi/callback",
  "metadata": {
    "source": "coze",
    "traceId": "trace-demo-001",
    "grayKey": "tenant-a"
  }
}
```

`bili` 口径：

- 所有图裂变业务入口里的 `bili` 都按“重绘幅度/裂变幅度”理解，0-100，值越大变化越明显。
- 后端按既定比例换算到 ComfyUI `denoise`：低值更保守，高值重绘更强；例如 `50%` 是中等幅度。
- GPT Image 2 受控版不使用 `bili`，使用 `variation_strength` 控制变化幅度；默认 `same_series`，固定一次请求生成 1 张图。

GPT Image 2 受控版请求示例：

```json
{
  "imageUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/demo/input.png",
  "version": "gpt-image2-vl-v2",
  "variation_strength": "same_series",
  "quality": "preview",
  "prompt": "保留系列感，元素要明显变化",
  "source": "partner-api",
  "channel": "open-api",
  "traceId": "trace-gpt-image2-001"
}
```

说明：该版本会先调用 `vl_analyze_image` 生成客观识别卡，再由中台归一化图案类型、编译定量提示词，最后调用 `openai_gpt_image_2_edit`。`quality=preview/candidate/premium` 会分别映射为 OpenAI 的 `low/medium/high`。`size` 不传或传 `auto` 时，中台按原图尺寸回填最终 OSS 图片；只有业务方明确传固定尺寸（如 `1024x1024`、`1536x1024`）时才改变输出画布。当前业务交付口径固定单次输出 1 张图；如果业务需要 3 张图，请提交 3 次，每次有独立 `runId`、轮询结果和回调。

ComfyUI 颜色锁定版请求示例：

```json
{
  "imageUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/demo/input.png",
  "version": "comfyui-vl-control-v2",
  "bili": "80%",
  "width": 2000,
  "height": 2000,
  "profile": "pattern_risk_routed_v4",
  "reference_lock": 0.42,
  "color_lock": 0.9,
  "source": "partner-api",
  "channel": "open-api",
  "traceId": "trace-comfyui-vl-001"
}
```

响应体：

```json
{
  "runId": "d7f2f7f37d1d47ad8dd2a9d7d3cb3d39",
  "businessKey": "fission",
  "version": "v1",
  "status": "queued",
  "taskStatus": "queued",
  "traceId": "trace-demo-001",
  "requestId": "req-demo-001",
  "taskId": "t1.fission.default.xxx",
  "retryAfterSeconds": 10,
  "error": null,
  "errorMessage": null,
  "errorCode": null,
  "debugUrl": null
}
```

常见错误：

- `BUSINESS_IMAGE_URL_REQUIRED`
- `BUSINESS_CAPABILITY_NOT_FOUND`
- `BUSINESS_RECIPE_INVALID`
- `BUSINESS_RECIPE_ABILITY_NOT_AVAILABLE`
- `BUSINESS_REQUEST_PAYLOAD_INVALID`
- `BUSINESS_VL_PREPROCESS_FAILED`
- `BUSINESS_CLIENT_DISABLED`
- `BUSINESS_CLIENT_BUSINESS_NOT_ALLOWED`
- `BUSINESS_USER_SCOPE_REQUIRED`
- `BUSINESS_USER_SCOPE_FORBIDDEN`
- `BUSINESS_CLIENT_CONCURRENCY_LIMITED`
- `BUSINESS_CLIENT_DAILY_RUN_LIMITED`
- `BUSINESS_CLIENT_DAILY_QUOTA_LIMITED`
- `BUSINESS_API_KEY_INACTIVE`
- `BUSINESS_API_KEY_EXPIRED`
- `BUSINESS_API_KEY_BUSINESS_NOT_ALLOWED`
- `ABILITY_TASK_FAILED`
- `COMFYUI_TIMEOUT`

说明：

- 新接入建议把 `bili/width/height/profile/prompt` 等业务字段直接作为顶层字段传入，业务方不用理解 `inputs`；`batch_size/steps/cfg` 仅作为旧 ComfyUI 版本兼容字段保留。`bili` 统一按重绘幅度理解。
- 旧调用仍兼容 `inputs.bili`、`inputs.width` 等格式；顶层字段不会破坏现有 Coze 工作流。
- 提交接口默认只返回轻量回执，业务方保存 `runId` 后调用 `/api/business/runs/get` 轮询结果；底层路由、步骤、成本、排障证据不在提交阶段返回。
- `traceId/requestId/tenantId/clientId/channel/source` 会进入业务运行记录，并继续透传到底层能力任务，后续用于排查、灰度、成本和配额统计。

---

## 3.1) 文字强化裂变（文生图）两步接口

### POST /api/business/text-fission/prompts

用途：第一步，输入原图，让 VL 生成用户可编辑的文生图提示词。这个接口不生图，只返回草稿。

请求体：

```json
{
  "imageUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/demo/text-input.png",
  "prompt": "可选：希望突出包袋上的英文和热带元素",
  "source": "partner-api",
  "channel": "open-api",
  "traceId": "trace-text-fission-prompt-001",
  "requestId": "req-text-fission-prompt-001"
}
```

响应体：

```json
{
  "promptDraftId": "0b4b3d8c2f8d4a92b6a1122334455667",
  "status": "succeeded",
  "imageUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/demo/text-input.png",
  "editablePrompt": "A clean flat textile print design with clear readable English text HAPPY SUMMER, tropical flowers and shells around the text, balanced commercial illustration style, white background.",
  "editablePromptCn": "生成一张干净的平面纺织印花图案，保留清晰可读的英文 HAPPY SUMMER，周围有热带花朵和贝壳元素，商业插画风格，白色背景。",
  "editableNegativePrompt": "blurry, low quality, broken composition, watermark, mockup, photo of a shirt, dirty grunge, muddy colors, extra instruction words, unrelated objects",
  "editableNegativePromptCn": "模糊、低质量、构图破碎、水印、服装实拍、脏污颗粒、颜色浑浊、额外说明文字、无关物体",
  "textContent": "HAPPY SUMMER",
  "textItems": [
    {
      "index": 1,
      "text": "HAPPY SUMMER",
      "role": "main_title",
      "keep": true
    }
  ],
  "routeDecision": "text2img_rebuild",
  "routeReason": "短文字装饰图，适合进入文生图重绘。",
  "canUseText2Img": true,
  "textCount": 1,
  "promptProfile": "text_allowed",
  "layoutCard": {},
  "paletteCard": {},
  "riskNotes": [],
  "vlResult": {
    "editable_prompt": "A clean flat textile print design..."
  },
  "traceId": "trace-text-fission-prompt-001"
}
```

参数说明：

| 参数 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `imageUrl` | 是 | 无 | 原图 URL。用于 VL 识别文字、主体、风格和构图。 |
| `prompt` | 否 | 空 | 业务补充说明；不填也会使用系统提示词生成草稿。 |
| `source/channel` | 否 | 空 | 调用来源，建议传 `partner-api/open-api` 或 `eval-web/eval`。 |
| `traceId/requestId` | 否 | 自动生成 | 跨系统排障字段。 |

关键响应字段：

| 字段 | 说明 |
| --- | --- |
| `editablePrompt` | 英文生成提示词，给第二步的 `editable_prompt` 使用。 |
| `editablePromptCn` | 中文可读提示词，方便业务和测试人员理解并修改。 |
| `editableNegativePrompt` | 英文反向提示词；默认不会禁止文字、字母、数字和排版。 |
| `editableNegativePromptCn` | 中文可读反向提示词。 |
| `textItems` | VL 识别出的文字清单，一条文字一项；用户可在测评端修改后带回第二步。 |
| `routeDecision` | 推荐路由：`text2img_rebuild` / `deterministic_text_rebuild` / `general_pattern_fission` / `reject_text2img`。 |
| `routeReason` | 路由原因，给测试和排障使用。 |
| `canUseText2Img` | 是否建议进入 Qwen 文生图链路。 |
| `textCount` | 识别文字数量。 |

常见错误：

- `BUSINESS_IMAGE_URL_REQUIRED`
- `VL_IMAGE_REQUIRED`
- `VL_IMAGE_UNREACHABLE`
- `VL_PROVIDER_FAILED`
- `TEXT_FISSION_PROMPT_EMPTY`
- `TEXT_FISSION_PROMPT_PREPARE_FAILED`
- `BUSINESS_API_KEY_INACTIVE`
- `BUSINESS_API_KEY_EXPIRED`
- `BUSINESS_API_KEY_BUSINESS_NOT_ALLOWED`

### POST /api/business/text-fission/runs

用途：第二步，提交用户确认或修改后的提示词，创建 ComfyUI 文生图任务并返回 `runId`。这个接口不会再次调用 VL。

链路说明：

- 第一步 `/api/business/text-fission/prompts` 已经完成 VL 识别和提示词草稿生成。
- 第二步只把用户确认后的 `editable_prompt`、`editable_negative_prompt`、可选 `routeDecision/textItems` 送入 ComfyUI 文生图能力。
- 第二步返回的业务步骤中，`prompt_draft` 只作为“已确认草稿”的记录步骤，状态应为 `succeeded/confirmed`，不会再生成新的 VL 能力任务；真正出图步骤是 `primary`。
- 如果看到第二步又出现新的 VL 排队任务，说明控制点回归，应按 Bug 处理。

请求体：

```json
{
  "imageUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/demo/text-input.png",
  "version": "qwen2512-text2img-v1",
  "editable_prompt": "A clean flat textile print design with clear readable English text HAPPY SUMMER, tropical flowers and shells around the text, balanced commercial illustration style, white background.",
  "editable_negative_prompt": "blurry, low quality, broken composition, watermark, mockup, photo of a shirt, dirty grunge, muddy colors, extra instruction words, unrelated objects",
  "routeDecision": "text2img_rebuild",
  "textItems": [
    {
      "index": 1,
      "text": "HAPPY SUMMER",
      "role": "main_title",
      "keep": true
    }
  ],
  "promptDraftId": "0b4b3d8c2f8d4a92b6a1122334455667",
  "source": "partner-api",
  "channel": "open-api",
  "traceId": "trace-text-fission-run-001",
  "requestId": "req-text-fission-run-001"
}
```

响应体同图裂变提交接口。提交成功后用 `/api/business/runs/get` 轮询：

```json
{
  "runId": "提交接口返回的 runId"
}
```

参数说明：

| 参数 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `imageUrl` | 是 | 无 | 原图 URL，用于链路关联和测评对比；第二步生图主输入是提示词。 |
| `editable_prompt` | 是 | 无 | 用户最终确认后的生成提示词；会原样送入 ComfyUI 正向提示词节点。 |
| `editable_negative_prompt` | 否 | 系统默认负向词 | 反向提示词；默认不会禁止文字、字母、数字、排版。 |
| `routeDecision` | 否 | 第一步推荐值 | 推荐路由，允许值：`text2img_rebuild`、`deterministic_text_rebuild`、`general_pattern_fission`、`reject_text2img`。 |
| `textItems` | 否 | 第一步识别结果 | 用户确认后的文字清单；每项至少包含 `text`，建议保留 `index/role/keep` 便于后续排障。 |
| `width` | 否 | 跟随原图宽度 | 输出宽度。只在业务方明确传入时覆盖；底层会按 8 像素安全倍数归一。 |
| `height` | 否 | 跟随原图高度 | 输出高度。只在业务方明确传入时覆盖；底层会按 8 像素安全倍数归一。 |
| `promptDraftId` | 否 | 空 | 第一步返回的草稿 ID，用于排障和关联。 |

质量说明：该能力本质是文生图，原图只用于第一步 VL 提示词草稿和尺寸/对比。文字密集图片的中文逐字复刻稳定性仍取决于 ComfyUI 工作流与提示词策略；若业务目标是“保留原图文字并精确改版”，后续应走 OCR/版式叠字或质量门禁方案。

常见错误：

- `BUSINESS_IMAGE_URL_REQUIRED`
- `TEXT_FISSION_PROMPT_REQUIRED`
- `COMFYUI_PROMPT_REQUIRED`
- `BUSINESS_CAPABILITY_NOT_FOUND`
- `BUSINESS_RECIPE_INVALID`
- `BUSINESS_RECIPE_ABILITY_NOT_AVAILABLE`
- `BUSINESS_CLIENT_CONCURRENCY_LIMITED`
- `COMFYUI_QUEUE_FULL`
- `COMFYUI_TIMEOUT`
- `ABILITY_TASK_FAILED`

说明：

- 一次请求固定生成 1 张图；如果需要多张，请提交多次，每次保存独立 `runId`。
- `editable_prompt` 是唯一必须由用户确认的生成内容。前端/业务方可以展示第一步返回的草稿，但不要在第二步自动追加新的系统描述。
- 不需要传 `bili/count/batch_size/n/steps/cfg/seed`；这些字段会被忽略或由中台默认策略控制，避免用户理解底层采样参数。
- 2026-05-19 线上验证：`promptDraftId=2ddcef208ba6417eb19623149ee15860`，`runId=557ac9b903b84e8f9a2622aadf48c818`，`primary` 出图成功；同时验证了 API Key 绑定范围不匹配时会返回 `BUSINESS_USER_SCOPE_FORBIDDEN`。

---

## 3.2) 图编辑组件型业务

业务名：图编辑。业务标识固定为 `image_edit`，当前默认版本为 `gpt-image2-editor-v1`。

图编辑不是单个裸接口，而是“组件工作台 + 中台业务 API + GPT Image 2 编辑能力”的组合业务。业务方可以接入我们托管的组件，也可以拿源码组件放进自己的页面；两种方式都必须调用中台，不允许业务方直接调用 OpenAI。当前托管组件路径为 `/image-edit`，内部测试可直接打开该路径进入图编辑工作台。

### GET /api/business/image-edit/component-config

用途：组件启动时读取当前版本、可用技能、尺寸、质量档位、输出格式和页面文案。

请求头：

```http
X-PODI-API-Key: podi_xxx
```

响应体：

```json
{
  "businessKey": "image_edit",
  "version": "gpt-image2-editor-v1",
  "component": {
    "type": "image-edit-workbench",
    "hostedMode": true,
    "sourceMode": true,
    "auth": "business_api_key",
    "title": "图编辑",
    "defaultSkill": "local_modify",
    "defaultSize": "auto",
    "defaultQuality": "auto"
  },
  "skills": [
    {
      "value": "local_modify",
      "label": "局部修改",
      "description": "对主图中指定对象或区域做小范围改动。"
    }
  ],
  "sizes": ["auto", "1024x1024", "1536x1024", "1024x1536", "2048x2048", "2048x1152", "3840x2160", "2160x3840"],
  "customSizeConstraints": {
    "max_edge": 3840,
    "multiple_of": 16,
    "max_aspect_ratio": 3,
    "min_pixels": 655360,
    "max_pixels": 8294400
  },
  "qualityLevels": ["auto", "preview", "production", "premium"],
  "outputFormats": ["png", "jpeg", "webp"]
}
```

### POST /api/business/image-edit/runs

用途：提交一次图编辑任务。一次请求固定生成 1 张图；业务方需要多张图时请多次提交，每次保存独立 `runId`。

最小请求：

```json
{
  "imageUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/demo/edit-input.png",
  "editSkill": "local_modify",
  "instruction": "把杯子上的蓝色花纹改成红色，保持杯子形状和背景不变",
  "size": "auto",
  "quality": "preview",
  "output_format": "png",
  "source": "partner-api",
  "channel": "open-api",
  "traceId": "trace-image-edit-001",
  "requestId": "req-image-edit-001"
}
```

带标注和参考图请求：

```json
{
  "imageUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/demo/edit-input.png",
  "editSkill": "reference_element_transfer",
  "instruction": "把主图中框选的花朵替换成参考图里的蓝色蝴蝶结，整体光影和视角保持一致",
  "selectionHints": [
    {
      "type": "box",
      "label": "要替换的花朵",
      "x": 0.32,
      "y": 0.41,
      "width": 0.28,
      "height": 0.24
    }
  ],
  "referenceImages": [
    {
      "url": "https://podi.oss-cn-hangzhou.aliyuncs.com/demo/reference.png",
      "role": "element_reference",
      "label": "蓝色蝴蝶结参考"
    }
  ],
  "size": "1536x1024",
  "quality": "production",
  "output_format": "png",
  "traceId": "trace-image-edit-002"
}
```

蒙版请求：

```json
{
  "imageUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/demo/edit-input.png",
  "maskUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/demo/edit-mask.png",
  "editSkill": "remove_inpaint",
  "instruction": "删除蒙版区域内的文字水印，并自然补齐背景纹理",
  "size": "auto",
  "quality": "preview",
  "traceId": "trace-image-edit-mask-001"
}
```

参数说明：

| 参数 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `imageUrl` | 是 | 无 | 主图 URL，必须可被中台访问。 |
| `instruction` | 是 | 无 | 用户编辑指令。组件可通过点选/框选/参考图辅助生成，但最终必须提交清晰文字。 |
| `editSkill` | 否 | `local_modify` | 改图技能：`local_modify`、`reference_element_transfer`、`remove_inpaint`、`color_reference_correction`。 |
| `selectionHints` | 否 | `[]` | 点选、框选、圆选等软标注，只用于告诉模型关注哪里。坐标建议使用 0-1 相对值。 |
| `referenceImages` | 条件必填 | `[]` | 参考图列表；参考图替换、补色校正必须提供。 |
| `maskUrl` | 否 | 空 | 单个最终合并后的 Alpha mask；尺寸必须和主图一致。 |
| `size` | 否 | `auto` | 输出尺寸。可用预设或满足官方约束的自定义 `宽x高`。 |
| `quality` | 否 | `auto` | `auto/preview/production/premium`，分别用于自动、快速预览、正式候选、高质量。 |
| `output_format` | 否 | `png` | `png/jpeg/webp`。 |
| `traceId/requestId` | 否 | 自动生成 | 业务排障字段，建议业务后端传入。 |

尺寸约束：

- 推荐默认 `auto`，页面显示为“跟随原图/自动”。
- 常用预设：`1024x1024`、`1536x1024`、`1024x1536`、`2048x2048`、`2048x1152`、`3840x2160`、`2160x3840`。
- 自定义尺寸：最大边不超过 3840；边长必须是 16 的倍数；长短边不超过 3:1；总像素在 655,360 到 8,294,400 之间。
- 2K 和 4K 属于高成本/高耗时，组件默认不作为普通推荐。

提交响应体：

```json
{
  "runId": "d7f2f7f37d1d47ad8dd2a9d7d3cb3d39",
  "businessKey": "image_edit",
  "version": "gpt-image2-editor-v1",
  "status": "queued",
  "taskStatus": "queued",
  "traceId": "trace-image-edit-001",
  "requestId": "req-image-edit-001",
  "taskId": "t1.image_edit.default.xxx",
  "retryAfterSeconds": 10,
  "error": null,
  "errorMessage": null,
  "errorCode": null,
  "debugUrl": null
}
```

轮询请求：

```json
{
  "runId": "提交接口返回的 runId"
}
```

轮询成功响应重点字段：

```json
{
  "runId": "d7f2f7f37d1d47ad8dd2a9d7d3cb3d39",
  "businessKey": "image_edit",
  "version": "gpt-image2-editor-v1",
  "status": "succeeded",
  "taskStatus": "succeeded",
  "imageUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/result/image-edit-output.png",
  "imageUrls": ["https://podi.oss-cn-hangzhou.aliyuncs.com/result/image-edit-output.png"],
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

常见错误：

- `BUSINESS_IMAGE_URL_REQUIRED`
- `IMAGE_EDIT_INSTRUCTION_REQUIRED`
- `IMAGE_EDIT_SKILL_INVALID`
- `IMAGE_EDIT_REFERENCE_REQUIRED`
- `IMAGE_EDIT_TARGET_REQUIRED`
- `IMAGE_EDIT_SIZE_INVALID`
- `IMAGE_EDIT_CANVAS_TOO_SMALL`
- `IMAGE_EDIT_CANVAS_PLACEMENT_INVALID`
- `IMAGE_EDIT_CANVAS_BUILD_FAILED`
- `IMAGE_EDIT_MASK_SIZE_MISMATCH`
- `IMAGE_EDIT_MASK_ALPHA_REQUIRED`
- `IMAGE_EDIT_QUALITY_INVALID`
- `IMAGE_EDIT_OUTPUT_FORMAT_INVALID`
- `BUSINESS_CAPABILITY_NOT_FOUND`
- `BUSINESS_RECIPE_INVALID`
- `BUSINESS_RECIPE_ABILITY_NOT_AVAILABLE`
- `BUSINESS_CLIENT_CONCURRENCY_LIMITED`
- `BUSINESS_API_KEY_INACTIVE`
- `BUSINESS_API_KEY_EXPIRED`
- `BUSINESS_API_KEY_BUSINESS_NOT_ALLOWED`
- `BUSINESS_ABILITY_EXECUTION_FAILED`

说明：

- 默认查询返回轻量结果，不包含大段底层 payload。
- 只有 `detail=full` 或调试场景才返回编译提示词、步骤详情、GPT Image 2 执行摘要、成本和错误详情。
- 组件源码接入和托管组件接入必须使用同一套接口和同一套 API Key 权限。
- 内部客户前端直连只限受控页面；更推荐业务方后端持有 API Key 调用中台。

---

## 3.3) 产品设计能力

业务名：产品设计。业务标识固定为 `product_design`，当前默认版本为 `product-design-gpt-image2-v1`。

产品设计是独立业务能力，不是图编辑的内部模式。客户端可以把它放进“花纹提取 -> 裂变 -> 产品设计 -> 组图/模特图/视频”的端到端链路；中台只负责能力定义、版本路由、调用证据、结果回填和质量治理。

### POST /api/business/product-design/runs

用途：提交一次产品设计任务。一次请求固定生成 1 张图；业务方需要多方案时请多次提交，每次保存独立 `runId`。

最小请求：

```json
{
  "imageUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/demo/pattern.png",
  "productType": "apparel",
  "designBrief": "把主图花纹应用到一款适合夏季电商展示的连衣裙产品图，保持花纹识别度和商业质感。",
  "scene": "studio_product",
  "quality": "production",
  "size": "auto",
  "output_format": "png",
  "source": "partner-api",
  "channel": "open-api",
  "clientContextId": "client-flow-001",
  "requestId": "req-product-design-001"
}
```

带参考图请求：

```json
{
  "imageUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/demo/floral-pattern.png",
  "productType": "home_textile",
  "designBrief": "生成一张抱枕产品设计图，图案自然铺在面料上，保留原花纹颜色关系和层次。",
  "scene": "print_mockup",
  "referenceImages": [
    {
      "url": "https://podi.oss-cn-hangzhou.aliyuncs.com/demo/pillow-shape.png",
      "label": "抱枕版型参考"
    }
  ],
  "quality": "preview",
  "size": "1024x1024"
}
```

参数说明：

| 参数 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `imageUrl` | 是 | 无 | 素材/花纹/参考主图 URL，必须可被中台访问。 |
| `designBrief` | 是 | 无 | 产品设计要求，说明目标产品、风格、必须保留或避免的内容。 |
| `productType` | 否 | `apparel` | `apparel/home_textile/bag/shoe/stationery/packaging/generic`。 |
| `scene` | 否 | `studio_product` | `studio_product/flat_lay/ecommerce/lifestyle/print_mockup/generic`。 |
| `referenceImages` | 否 | `[]` | 参考图列表，用于补充版型、材质或风格；不替代主图素材。 |
| `clientContextId` | 否 | 空 | 客户端调用上下文 ID，用于跨能力链路回溯和排查。 |
| `inputAssetIds` | 否 | `[]` | 客户端侧输入资产 ID 列表，用于回溯。 |
| `size` | 否 | `auto` | 输出尺寸，沿用图编辑尺寸约束。 |
| `quality` | 否 | `production` | `auto/preview/production/premium`。 |
| `output_format` | 否 | `png` | `png/jpeg/webp`。 |

提交响应体：

```json
{
  "runId": "7f1d0c3b7f6d4c4f8897122bbdcf1a20",
  "businessKey": "product_design",
  "version": "product-design-gpt-image2-v1",
  "status": "queued",
  "taskStatus": "queued",
  "retryAfterSeconds": 10,
  "error": null,
  "errorMessage": null,
  "errorCode": null
}
```

轮询成功响应重点字段：

```json
{
  "runId": "7f1d0c3b7f6d4c4f8897122bbdcf1a20",
  "businessKey": "product_design",
  "version": "product-design-gpt-image2-v1",
  "status": "succeeded",
  "taskStatus": "succeeded",
  "imageUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/result/product-design-output.png",
  "imageUrls": ["https://podi.oss-cn-hangzhou.aliyuncs.com/result/product-design-output.png"],
  "expectedImageCount": 1,
  "errorCode": null,
  "errorMessage": null
}
```

常见错误：

- `BUSINESS_IMAGE_URL_REQUIRED`
- `PRODUCT_DESIGN_BRIEF_REQUIRED`
- `PRODUCT_DESIGN_PRODUCT_TYPE_INVALID`
- `PRODUCT_DESIGN_SCENE_INVALID`
- `IMAGE_EDIT_SIZE_INVALID`
- `IMAGE_EDIT_QUALITY_INVALID`
- `IMAGE_EDIT_OUTPUT_FORMAT_INVALID`
- `BUSINESS_CAPABILITY_NOT_FOUND`
- `BUSINESS_RECIPE_ABILITY_NOT_AVAILABLE`
- `BUSINESS_CLIENT_CONCURRENCY_LIMITED`
- `BUSINESS_API_KEY_BUSINESS_NOT_ALLOWED`
- `ABILITY_TASK_FAILED`

---

## 3.4) 产品商业化能力

业务名：产品商业化。业务标识固定为 `product_commercialization`，当前 MVP 版本为 `product-commercialization-mvp-v1`。

它是产品设计之后的试验入口，不负责花纹提取、裂变或产品设计本身。当前测评端先撤下产品文案入口，集中验证**产品视频素材包**；产品文案后续按 `product_copy_package` 独立能力重新设计。历史接口仍可能返回 `copyGeneration/contentPackage/copyPackage`，但这些字段暂不作为当前测评端交付面。

当前测评端先集中验证“产品视频素材包”：主流程为“上传产品图组 -> 核对商品事实并设置视频策略 -> 确认脚本分镜 -> 生成并确认首尾帧 -> 生成视频素材 -> 交付追踪”。商品事实核对和视频策略设置必须在同一屏完成：`productFields`/导出 JSON 只是可选说明材料，产品图仍是最高优先级事实源；用户在同一步选择视频场景、供应商、目标时长和补充规划要素。`action=video_preview` 会跳过文案生成，响应中的 `copyGeneration.method=skipped_for_video_preview` 只用于兼容旧响应结构，不代表文案能力已完成。产品文案后续按 `product_copy_package` 独立能力重做。

视频规划要素的 UI 口径：`core_message/target_audience/usage_scene/shot_preference/avoid` 由后端在 `videoPlan.editablePlanningFields` 中返回，字段包含 `value/source/sourceLabel/editable/confidence`，页面必须标注“模型回填 / 人工调整 / 默认约束”等来源状态；用户手动修改后应作为下一次规划输入。旧客户端可以继续从 `resolvedProductFacts`、`videoPlan.directorBrief` 和 `videoPlan.storyboard` 兼容推断，但新接入以 `editablePlanningFields` 为准。确认页必须展示这些要素的快照，避免用户只看脚本和分镜而忽略目标人群、镜头偏好或禁止项。脚本、视频提示词、首尾帧提示词和生成出的首尾帧必须按镜头分组展示；有首尾帧需求时，必须逐镜头生成并确认，未生成或未确认的镜头不得提交视频成本动作；重生成某个镜头会清除该镜头确认状态，不影响其他已确认镜头。确认不是“图片数量够”即可，必须覆盖该镜头规划的每个 `role`，例如要求 `first_frame + last_frame` 时，传两张 `first_frame` 仍会被视为缺少 `last_frame`。

当前测评端配图生成的最小安全实现是：先调用 `preview` 得到文案和配图计划，再由用户显式点击配图生成按钮，前端提交 `POST /api/business/product-commercialization/runs` 且传 `action=visual_generate`，用返回的 `runId` 轮询 `/api/business/runs/get`，最终展示自有 OSS 图片。也就是说，`visualSupportMode=generate` 不等于预览接口自动生图，它只表示“本次计划允许后续显式生成配图”。

统一任务口径：

- 正式产品视频规划：`POST /api/business/promo-video/plan`，固定等价于 `action=video_preview`，同步返回 `videoPlan/videoAssetPackagePlan/review`，不触发文案模型、不生成图片、不生成视频。
- 正式产品视频首尾帧：`POST /api/business/promo-video/keyframes/runs`，固定等价于 `action=video_keyframes`，立即返回 `runId` 且 `businessKey=promo_video`；终态查询返回 `imageUrls` 和 `resultPayload.videoAssetPackage.keyframes`。可选传 `keyframeShotScope` 只重生成某个镜头，便于用户对单个不满意镜头二次生成，不必整包重跑。
- 正式产品视频素材包：`POST /api/business/promo-video/runs`，固定等价于 `action=video_generate`，必须在 `confirmedVideoKeyframes` 中传入已人工确认的首尾帧/关键帧；若规划中存在 `keyframeNeeds` 但未按 `shot/segmentIndex/role` 全部确认，返回 `PRODUCT_COMMERCIALIZATION_KEYFRAMES_UNCONFIRMED`，不会触发 KIE/Vidu 视频扣费。提交成功后立即返回 `runId` 且 `businessKey=promo_video`；终态查询返回分段视频素材包。
- 正式产品视频可选合成：`POST /api/business/promo-video/compose/runs`，固定等价于 `action=compose_video`，立即返回 `runId` 且 `businessKey=promo_video`；只在业务方明确需要合成片时调用。
- 视频规划预览：`POST /api/business/product-commercialization/preview` 且 `action=video_preview`，同步返回 `videoPlan/videoAssetPackagePlan/review`，不触发文案模型、不生成图片、不生成视频。
- 执行配图：`POST /api/business/product-commercialization/runs` 且 `action=visual_generate`，当前不作为测评端主入口；后续组图能力会独立整理。
- 执行视频首尾帧：`POST /api/business/product-commercialization/runs` 且 `action=video_keyframes`，立即返回 `runId`，终态查询返回 `resultPayload.videoAssetPackage.deliveryStatus=keyframes_ready` 和 `keyframes[]`。该动作默认调用 GPT Image 2，并做目标画幅归一化；成功后仍需人工确认，不能等同于视频已完成。
- 执行视频素材包：`POST /api/business/product-commercialization/runs` 且 `action=video_generate` 或不传 `action`，必须传入已确认的 `confirmedVideoKeyframes`；缺少任一规划中的首尾帧/关键帧会返回 `PRODUCT_COMMERCIALIZATION_KEYFRAMES_UNCONFIRMED` 和 `missingKeyframes`，错误详情同时返回 `requiredCount/confirmedCount/matchedCount`，用于区分“传入数量”和“真正匹配到的需求数量”。不在提交阶段偷偷生成首帧，也不触发视频扣费。校验通过后立即返回 `runId`/`status`/`retryAfterSeconds`，不在提交接口等待视频生成完成。视频素材包包含脚本、分镜、首尾帧/关键帧、分段视频和可选合成片。
- 多产品图：`productImageUrl` 是兼容主图字段；`productImages[]` 可传 `primary/front/back/side/detail/texture/lifestyle/reference` 等角色。规划层会把图组交给 VL/LLM 上下文，并在 `videoPlan.referenceImageSet` 和每个 `storyboard[].referenceImage` 中记录参考图选择。当前 KIE/Vidu 执行仍按每段一张参考图调用，不伪装成厂商原生多图视频能力。
- 查询结果：`POST /api/business/runs/get`，请求体传 `{ "runId": "..." }` 或 `{ "taskId": "..." }`。视频查询不能只看最终合成片，必须同时查看 `resultPayload.videoAssetPackage.deliveryStatus/script/keyframes/segmentVideos/composition`；首尾帧成功标准是查询到 `status=succeeded` 且 `imageUrls` 非空；视频成功标准是 `videoUrls` 或 `resultPayload.videoAssetPackage.segmentVideos[].videoUrl` 非空；失败原因看 `errorMessage/errorCode`。
- 计费口径：MVP 阶段关键帧按图片计量，`action=video_keyframes` 每张图记 `quotaUnits=1`，`billingUnit` 例如 `openai.gpt_image_2.image`；视频按生成片段计量，每个视频片段记 `quotaUnits=1`，`billingUnit` 会按真实供应商成本动作派生，例如 `kie_veo3_fast_video_segment` 或 `vidu_viduq3_turbo_video_segment`。当前先记录 quota 和成本证据，不虚构第三方货币单价，正式价格表后续接入模型成本策略。
- 兼容调试：`/product-commercialization/video-keyframes`、`/product-commercialization/video` 与 `/product-commercialization/video-compose` 暂时保留给内部联调，不作为正式业务方接入口径。

### POST /api/business/product-commercialization/preview

用途：生成产品理解、视频素材包规划和审核提示。产品图是最高优先级事实源；产品导出字段 JSON 是可选说明材料。`productImageUrl` 和 `productImages` 可以同时传，系统会把 `productImageUrl` 作为主图兼容字段，并合并去重到 `productCard.sourceFacts.productImages`。没有 `productFields` 不阻塞预览，系统会在 `productCard.missingFields`、`productCard.inferredFacts` 或 `resolvedProductFacts.inferredFacts` 中标记推断来源和置信度。

注意：当前 MVP 复用同一个 `product_commercialization` 服务，但测评端必须传 `action=video_preview`。该动作不会调用文案模型，`copyPackage/contentPackage` 仅保留兼容占位；视频验收只看 `videoPlan/videoAssetPackagePlan/review`。产品文案入口已撤下，后续按独立能力验收。

最小请求：

```json
{
  "action": "video_preview",
  "productImageUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/demo/product-socks.png",
  "productImages": [
    {
      "url": "https://podi.oss-cn-hangzhou.aliyuncs.com/demo/product-socks-front.png",
      "role": "front",
      "label": "正面",
      "isPrimary": true
    },
    {
      "url": "https://podi.oss-cn-hangzhou.aliyuncs.com/demo/product-socks-back.png",
      "role": "back",
      "label": "背面"
    },
    {
      "url": "https://podi.oss-cn-hangzhou.aliyuncs.com/demo/product-socks-detail.png",
      "role": "detail",
      "label": "材质细节"
    }
  ],
  "productFields": {
    "模板名称": "女款长袜（3D打印）",
    "英文名称": "Women's knitted woolen socks",
    "产品材质": "包纱、涤纶、尼龙、橡筋",
    "生产工艺": "3D印花",
    "具体成分": "65%涤纶，15%氨纶，20%尼龙",
    "二级分类": "穿搭配件",
    "建议售价": "10"
  },
  "outputLanguage": "en-US",
  "marketRegion": "US",
  "extraPrompt": "核心信息：突出材质纹理和商品轮廓。目标人群：海外电商买家。镜头偏好：慢速转圈和材质特写。禁止内容：不要文字、水印、Logo、价格标签。",
  "videoScenario": "product_showcase_short",
  "durationSeconds": 8,
  "targetDurationSeconds": 15,
  "aspectRatio": "16:9",
  "requestId": "req-product-commercialization-001"
}
```

参数说明：

| 参数 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `productImageUrl` | 文案预览建议必传；配图/视频与 `productImages` 二选一 | 空 | 产品设计完成后的商品主图 URL。它是最高优先级事实源；没有产品图时只能做低置信文案草稿，不应触发配图或视频成本动作。 |
| `productImages` | 否 | 空 | 可选产品图组。每项至少包含 `url`，可带 `role/label/isPrimary/source/weight`。视频规划会使用主图确定商品身份，用背面/侧面/细节图辅助分镜和参考图选择。当前厂商执行仍按每段一张参考图调用。 |
| `designImageUrl` | 否 | 空 | 可选设计稿/印花图 URL，用于辅助理解商品来源。 |
| `productFields` | 否 | `{}` | 可选产品导出字段 JSON；字段名可用中文或英文别名。有则作为说明材料使用，没有则继续执行。字段和图片冲突时以下游 `resolvedProductFacts` 的图片优先结论为准。 |
| `extraPrompt` | 否 | 空 | 业务方额外要求，例如“偏节日礼品场景，避免夸张承诺”。 |
| `outputLanguage` | 否 | `en-US` | `en-US/zh-CN/bilingual`。POD 海外销售默认建议 `en-US`；`bilingual` 返回中英双语结构。 |
| `marketRegion` | 否 | `US` | `US/UK/EU/global`，用于影响措辞和审核提示。 |
| `commercePlatform` | 否 | `marketplace` | 目标平台/渠道，例如 `amazon_marketplace`、`shopify_independent_site`、`etsy_gift`、`tiktok_shop_social`、`global_marketplace`；用于控制标题长度、语气和渠道建议。 |
| `copyTone` | 否 | `natural_professional` | 文案语气，例如 `natural_professional`、`warm_gift`、`premium`、`playful_social`、`concise_conversion`。 |
| `targetAudience` | 否 | 通用买家 | 目标人群，例如“海外礼品买家”“季节上新受众”“日常穿搭人群”。 |
| `sellingAngle` | 否 | 商品卖点和礼品场景 | 本轮主打角度，例如 `everyday_utility`、`giftable_moment`、`material_comfort`、`pattern_design`、`seasonal_collection`。 |
| `forbiddenClaims` | 否 | 空 | 禁用或谨慎使用的声明，支持字符串或数组，例如环保认证、医疗功效、品牌词、物流时效承诺。 |
| `copyScenarios` | 否 | 空 | 仅后续 `copy_preview/product_copy_package` 使用。当前 `video_preview` 不传该字段，后端会跳过文案生成。 |
| `visualSupportMode` | 否 | `recommendation` | `none/recommendation/generate`。`generate` 只表示允许后续显式生成配图，预览接口不自动生图。 |
| `action` | 预览建议必传；执行接口否 | 预览建议 `video_preview`；执行默认 `video_generate` | 预览支持 `video_preview/copy_preview`，当前测评端只用 `video_preview`。执行支持空值/`video_keyframes`/`video_generate`/`compose_video`/`visual_generate`；非法值返回 `PRODUCT_COMMERCIALIZATION_ACTION_INVALID`，不会静默回退。 |
| `visualScenes` | 否 | 空 | 仅 `action=visual_generate` 使用。可传 `listing-main/social-ad-cover/detail-closeup` 等配图场景 ID；不传时按模型产出的前三个配图 brief 执行。 |
| `videoPlanningContext` | 否 | 空 | 视频规划结构化上下文，建议包含 `coreMessage/targetAudience/usageScene/shotPreference/avoid/fields`。测评端会用产品图、VL 识别和可选 JSON 自动回填空白要素，用户可修改后重新规划；业务方也可以直接传该对象，避免把人群、镜头偏好等关键要求埋在长文本里。 |
| `videoPromptOverride` | 否 | 空 | 仅视频执行使用。测评端生成规划后允许用户编辑执行脚本；如果传入该字段，视频模型按用户编辑后的脚本生成，原始规划只作为参考。 |
| `keyframeShotScope` | 否 | 空 | 仅 `action=video_keyframes` 使用。传镜头序号（如 `1`、`2`）时只生成/重生成该镜头的首帧、尾帧或关键帧；不传则按 `videoAssetPackagePlan.keyframeNeeds` 生成全部关键帧。若没有匹配项返回 `PRODUCT_COMMERCIALIZATION_KEYFRAME_SCOPE_EMPTY`，不能静默改成全量生成。 |
| `confirmedVideoKeyframes` | 条件必填 | 空 | 仅 `action=video_generate` 使用。测评端或业务方把已经人工确认过的关键帧传入，后端按 `shot/segmentIndex/role` 匹配对应镜头并优先作为视频参考图；当 `videoAssetPackagePlan.keyframeNeeds` 非空时，该字段必须覆盖所有镜头的首尾帧/关键帧，否则返回 `PRODUCT_COMMERCIALIZATION_KEYFRAMES_UNCONFIRMED`。数量不是通过条件，角色也必须匹配；例如同一镜头两张 `first_frame` 不能替代缺失的 `last_frame`。已确认帧不会被当成需要再次生成的图片扣费项。 |
| `videoScenario` | 否 | `product_showcase_short` | `product_showcase_short/social_ad_short/detail_explainer`。 |
| `durationSeconds` | 否 | 模型默认 | 期望单段视频执行时长。合法值由所选 `executorId` 的模型画像决定，例如 KIE Veo3.1 Fast 当前按 8 秒片段执行，Vidu viduq3-turbo 当前按 3/5/8 秒片段规划。 |
| `targetDurationSeconds` | 否 | 模型默认 | 客户目标视频素材包时长，允许 1-60。该值以客户需求为主，不按 KIE/Vidu 单段枚举限制；预览会先围绕目标时长规划脚本和分镜，再根据模型画像拆成 8 秒或 3/5/8 秒片段。正式 `/runs` 默认交付单段或多段视频素材包，显式 `action=compose_video` 才要求合成片。 |
| `aspectRatio` | 否 | `16:9` | 视频目标画幅。KIE 当前作为厂商执行参数传入；Vidu `img2video` 不接受独立画幅参数，实际画幅跟随上传产品图/首帧，若必须稳定输出 16:9/9:16，需要先生成或补边对应比例首帧再执行。响应中的 `videoPlan.aspectPolicy` 会说明真实执行策略。 |
| `executorId` | 否 | 默认 KIE | 视频供应商执行节点。当前可执行：`executor_kie_market_default`（KIE Veo3.1 Fast）、`executor_vidu_default`（Vidu viduq3-turbo）。 |

产品导出字段如果存在，建议包含：模板名称/编号/主体编码/产品型号、英文名称、一级/二级分类、工厂、重量、生产工艺、材质、成分、包装尺寸、包装重量、关键词和其他描述。字段缺失不阻塞预览；缺失项会进入 `missingFields`，由 VL/LLM 基于图片推断的内容必须标记置信度和来源。

图片和 JSON 一致性：产品图是最高优先级视觉事实源，导出 JSON 是对产品图的可选结构化说明。VL 会在 `contentPackage.imageFactAssessment` 输出图像主判断、字段冲突、缺失字段推断、采用口径和置信度。若图片与 JSON 冲突，响应会写入 `review.issues[].code=PRODUCT_IMAGE_FIELD_CONFLICT`，并生成 `resolvedProductFacts` 作为文案、配图和视频的下游事实源；原始导出字段仍保留在 `productCard.sourceFacts` 供人工复核。测评端在触发配图或视频这类成本动作前必须让用户确认“按产品图识别结果继续”。

响应重点字段：

```json
{
  "requestId": "req-product-commercialization-001",
  "businessKey": "promo_video",
  "version": "promo-video-mvp-v1",
  "status": "previewed",
  "outputLanguage": "en-US",
  "marketRegion": "US",
	  "productCard": {
    "sourceFacts": {
      "productNameEn": "Women's knitted woolen socks",
      "material": "包纱、涤纶、尼龙、橡筋"
    },
    "inferredFacts": {},
    "missingFields": [],
	    "confidence": 0.82
	  },
	  "resolvedProductFacts": {
	    "source": "product_image_primary",
	    "summary": "Floral hooded lightweight jacket",
	    "confidence": "low",
	    "fieldConflicts": [
	      "Exported JSON says Women's knitted woolen socks, but the uploaded product image appears to show a floral hooded jacket."
	    ],
	    "facts": {
	      "productNameEn": "Floral hooded lightweight jacket",
	      "visualFeatures": ["floral all-over print", "hooded outerwear silhouette"],
	      "keywords": ["floral hooded jacket", "lightweight outerwear", "POD apparel"]
	    }
	  },
  "copyPackage": {
    "listingTitle": "Women's knitted woolen socks - Custom POD Design, Comfortable Everyday Style",
    "bulletPoints": ["..."],
    "detailDescription": "...",
    "adShortCopy": ["..."],
    "keywordPack": ["Women's knitted woolen socks", "穿搭配件", "POD"]
  },
  "copyGeneration": {
    "method": "volcengine_chat",
    "provider": "volcengine",
    "model": "doubao-seed-1-6",
    "fallback": false,
    "evidence": "Volcengine VL chat generated structured ecommerce content package."
  },
  "contentPackage": {
    "commercePositioning": {
      "coreAngle": "Gift-ready patterned socks for overseas ecommerce buyers.",
      "targetCustomers": ["gift shoppers", "daily outfit buyers"],
      "purchaseOccasions": ["birthday gifting", "seasonal collection"],
      "sellingPoints": ["original pattern", "soft material", "POD-ready listing"],
      "factBoundaries": ["Do not claim certification", "Do not invent shipping speed"]
    },
    "imageBriefs": [
      {
        "id": "social-ad-cover",
        "label": "社媒广告封面",
        "usage": "搭配广告短文案使用",
        "linkedCopy": ["adShortCopy"],
        "prompt": "Create a clean lifestyle ad cover using the product image as factual reference.",
        "riskNotes": ["No embedded text or unsupported claims."]
      }
    ],
    "channelUsageGuide": [
      {
        "channel": "Amazon",
        "howToUse": "Use listing title, bullet points and listing-main visual together.",
        "assets": ["listingTitle", "bulletPoints", "listing-main"]
      }
    ]
  },
	  "visualAssetPlan": {
    "mode": "recommendation",
    "hasProductImage": true,
    "recommendedScenes": [
      {
        "id": "social-ad-cover",
        "neededFor": ["ad_short_copy"],
        "generateByDefault": false
      }
    ],
	    "generationPolicy": {
	      "requiresExplicitAction": true,
	      "candidateRoute": "business.product_commercialization.visual_generate",
	      "factSource": "resolvedProductFacts"
	    }
	  },
  "videoPlan": {
    "provider": "kie",
    "model": "veo3_fast",
    "targetDurationSeconds": 15,
    "durationSeconds": 8,
    "singleSegmentSeconds": 8,
    "segmentCount": 2,
    "totalGeneratedSeconds": 16,
    "requiresComposition": true,
    "aspectRatio": "16:9",
    "editablePlanningFields": [
      {
        "id": "target_audience",
        "label": "目标人群",
        "value": "overseas ecommerce gift buyers",
        "source": "auto",
        "sourceLabel": "导演 brief / 市场推断",
        "editable": true,
        "confidence": 0.86
      },
      {
        "id": "shot_preference",
        "label": "镜头偏好",
        "value": "full-product hero hold, then restrained material push-in",
        "source": "auto",
        "sourceLabel": "分镜镜头规划",
        "editable": true,
        "confidence": 0.86
      }
    ],
    "planningFieldContract": {
      "mode": "backend_structured_suggestions",
      "frontendEditable": true,
      "manualChangesRequireReplan": true,
      "fields": ["core_message", "target_audience", "usage_scene", "shot_preference", "avoid"]
    },
    "storyboard": [
      {"shot": 1, "durationSeconds": 8, "keepSeconds": 8, "label": "Opening product hero"},
      {"shot": 2, "durationSeconds": 8, "keepSeconds": 7, "label": "Material and print detail"}
    ],
    "assetNeeds": [{"asset": "product_image", "required": true, "available": true}],
    "videoPrompt": "Create an 8-second POD product showcase video...",
    "compositionPlan": {
      "status": "planned_ready_for_compose_endpoint",
      "composeEngine": "ffmpeg",
      "executionReady": true,
      "targetDurationSeconds": 15,
      "trimPlan": [
        {"segment": 1, "sourceDurationSeconds": 8, "keepSeconds": 8},
        {"segment": 2, "sourceDurationSeconds": 8, "keepSeconds": 7}
      ],
      "transition": {"type": "cut", "durationSeconds": 0},
      "costActionPreview": ["kie.veo3_fast.video", "kie.veo3_fast.video", "ffmpeg.compose"]
    }
  },
  "videoAssetPackagePlan": {
    "deliveryMode": "segment_package",
    "script": {
      "editable": true,
      "text": "Open with a clean product reveal, show the visible pattern and material, then close with a detail shot."
    },
    "storyboard": [
      {
        "segmentIndex": 1,
        "durationSeconds": 8,
        "goal": "Product reveal",
        "prompt": "Slow camera movement on the product. Preserve visible shape, color and pattern.",
        "requiredAssets": ["first_frame"]
      }
    ],
    "shotPackages": [
      {
        "shotNo": 1,
        "segmentIndex": 1,
        "label": "Opening product hero",
        "durationSeconds": 8,
        "keepSeconds": 8,
        "goal": "Product reveal",
        "scene": "clean studio ecommerce set",
        "cameraMovement": "slow push-in",
        "videoPrompt": "Slow camera movement on the product. Preserve visible shape, color and pattern.",
        "firstFramePrompt": "Create the opening product hero frame...",
        "lastFramePrompt": "Create the stable ending product frame...",
        "keyframeNeeds": [
          {
            "role": "first_frame",
            "required": true,
            "available": false,
            "prompt": "Create the opening product hero frame..."
          }
        ],
        "confirmationRequired": true,
        "executionState": "needs_keyframes"
      }
    ],
    "keyframeNeeds": [
      {
        "role": "first_frame",
        "required": true,
        "reason": "Anchor the product before video generation."
      }
    ],
    "compositionPlan": {
      "enabled": false,
      "reason": "Generate segment assets first; compose after review."
    }
  },
  "review": {
    "profile": "default_pod_profile",
    "score": 82,
    "issues": [],
    "videoReady": true
  },
  "execution": {
    "copyGenerated": true,
    "imageGenerated": false,
    "videoGenerated": false,
    "costActions": []
  }
}
```

`videoAssetPackagePlan.shotPackages` 是正式业务方优先使用的镜头级素材包。旧的 `storyboard` 与 `keyframeNeeds` 会继续保留用于兼容，但业务方不应再自行把脚本、首尾帧和结果按镜头二次拼装。

### POST /api/business/product-commercialization/runs

用途：显式提交产品商业化成本动作，并将生成结果保存到自有 OSS。该接口会复用同一套产品理解、文案和规划逻辑，但属于成本动作，必须由业务方明确触发。

请求体与 `preview` 相同，但必须提供 `productImageUrl`，或在 `productImages` 中提供至少一张可用产品图。`action=visual_generate` 时执行产品商业化配图，支持 `visualScenes` 指定 `listing-main/social-ad-cover/detail-closeup` 等场景，结果通过 `imageUrls/resultPayload.imageResult` 返回。配图默认走中台 GPT Image 2 图片编辑能力 `openai_gpt_image_2_edit`，以商品图作为事实锚点，默认 `size=auto`；只有后续显式指定低成本、批量或特定模型策略时才分流到其他图片能力。

`action=video_keyframes` 时只生成视频首尾帧/关键帧，不生成视频。后端会复用 `video_preview` 的脚本和分镜，按 `videoAssetPackagePlan.keyframeNeeds` 调用 GPT Image 2 生成图片，并做目标画幅归一化后上传 OSS。`videoPlan.keyframePlan` 只是导演模型原始建议，业务方不应直接拿它当执行清单；最终执行清单以资产包为准，因为后端会按供应商规则补齐必需素材，例如 Vidu 固定画幅执行前必须补 `normalized_first_frame`。该动作成功后返回 `deliveryStatus=keyframes_ready`，业务方或测评端必须逐镜头人工确认关键帧是否合理；不合理时可传 `keyframeShotScope` 只重生成对应镜头，重生成后该镜头确认状态应失效，合理后再调用 `video_generate`。

`action=video_generate` 或不传 `action` 时执行视频素材包；后端先按 `executorId` 解析模型画像，再围绕 `targetDurationSeconds` 规划脚本、分镜、首尾帧/关键帧需求和分段视频。客户目标时长不是供应商单段枚举：例如客户要求 15 秒，规划层必须规划 15 秒脚本，执行层再按 KIE 8 秒或 Vidu 3/5/8 秒片段拆解、保留和可选合成。默认交付目标是 `segment_package`：先保留脚本、关键帧和分段视频素材，最终合成是可选动作，不是唯一成功口径。用户如在测评端编辑了视频脚本，前端会把当前脚本写入 `videoPromptOverride`，后端必须按该脚本调用 KIE/Vidu。用户已确认的首尾帧或关键帧必须通过 `confirmedVideoKeyframes` 传入 `video_generate`；后端按镜头序号和角色优先使用确认帧作为该段参考图，不能在用户确认后又回退原始产品图，也不能对已确认帧重复触发 GPT Image 2 首帧生成成本动作。若缺少任一规划中的首尾帧/关键帧，返回 `PRODUCT_COMMERCIALIZATION_KEYFRAMES_UNCONFIRMED`，响应包含 `missingKeyframes/requiredCount/confirmedCount/matchedCount`，并且不会调用 KIE/Vidu。`confirmedCount` 只是传入的有效图片数量，`matchedCount` 才是按镜头和角色命中的需求数量；两者不一致时必须优先看 `missingKeyframes`。可选 `executorId` 指定 KIE 或 Vidu 节点；不传使用默认 KIE 执行节点。第三方返回的临时外链都必须先沉淀到自有 OSS，对外结果以自有 OSS URL 为准。注意：Vidu 单参考图生视频的实际比例由输入图/首帧决定；`aspectRatio` 不会作为无效厂商参数直接下发。若使用 Vidu 且目标画幅为固定比例，业务方必须先通过 `video_keyframes` 生成并确认归一化首帧，再把该帧传入 `confirmedVideoKeyframes`；后端不会在视频生成阶段自动补首帧。

同步调试入口 `/video-keyframes`、`/video`、`/video-compose` 如果遇到上游白名单、Key、供应商任务等错误，响应会优先暴露上游 `detail.errorCode`，并用 `detail.businessErrorCode` 标记当前业务阶段。例如本地未加白访问 vendor-api-ops 时返回：

```json
{
  "detail": {
    "errorCode": "VENDOR_API_CLIENT_FORBIDDEN",
    "businessErrorCode": "PRODUCT_COMMERCIALIZATION_KEYFRAME_GENERATION_FAILED",
    "message": "vendor-api-ops only accepts requests from backend allowlisted hosts.",
    "suggestion": "Route calls through the backend service or add the backend host to VENDOR_API_ALLOWED_CLIENTS."
  }
}
```

业务方判断时先看 `detail.errorCode` 定位根因，再看 `detail.businessErrorCode` 判断失败发生在哪个产品商业化阶段。

当前视频供应商和模型口径：

| `executorId` | 当前模型 | 状态 | 说明 |
| --- | --- | --- | --- |
| `executor_kie_market_default` | Veo3.1 Fast | 可执行 | 当前按 8 秒片段规划；长视频默认通过多个 8 秒片段形成素材包。首尾帧由 `action=video_keyframes` 单独生成和确认，不和视频提交混在一个按钮里。 |
| `executor_vidu_default` | viduq3-turbo | 可执行 | 当前按 3/5/8 秒片段规划。Vidu 图生视频比例跟随输入图/首帧；固定画幅必须先通过首尾帧任务生成并确认归一化首帧，再把确认帧作为视频参考图。`aspectRatio` 不会作为无效厂商参数下发。 |
| 待定 | Vidu 一键营销成片 Agent | 待接入 | 需要单独接口/参数，不混入当前单段视频按钮。 |
| 待定 | Vidu 视频复刻 Agent | 待接入 | 需要参考视频输入、复刻策略和版权/风格风险提示。 |
| 待定 | viduq3-ad / reference2video | 待接入 | 需要多参考图和广告模型参数，不伪装为当前已完成能力。 |

视频素材包字段口径：

| 字段 | 含义 |
| --- | --- |
| `resultPayload.videoAssetPackage.deliveryStatus` | 视频素材包交付阶段：`plan_ready/keyframes_ready/assets_ready/composed_ready/failed`。 |
| `resultPayload.videoAssetPackage.script` | 可编辑脚本及其生成状态。 |
| `resultPayload.videoAssetPackage.keyframes` | 首帧、尾帧或关键帧图片资产。 |
| `resultPayload.videoAssetPackage.segmentVideos` | 分段视频素材，单段成功和失败必须分别记录。 |
| `resultPayload.videoAssetPackage.composition` | 可选合成片状态。合成失败不得覆盖已成功的分段素材。 |
| `videoUrls` | 兼容字段，包含已成功的视频素材或合成片 URL；业务方需要完整结构时读取 `resultPayload.videoAssetPackage`。 |

Vidu 固定画幅执行补充字段：

| 字段 | 含义 |
| --- | --- |
| `resultPayload.videoPlan.aspectPolicy.mode` | 执行后为 `normalized_first_frame`，表示已用归一化首帧驱动视频生成。 |
| `resultPayload.videoPlan.aspectPolicy.generatedFirstFrameUrls` | 本次执行生成并上传 OSS 的首帧 URL。 |
| `resultPayload.videoAssetPackage.keyframes[].source` | 当前为 `gpt_image_2_plus_canvas_normalization`，表示 GPT Image 2 生成后又经过画布归一化。 |
| `resultPayload.videoAssetPackage.segmentVideos[].referenceImageUrl` | 实际提交给视频供应商的参考图。Vidu 固定画幅时应为归一化首帧 URL，而不是原始产品图。 |

提交成功响应只代表任务已进入中台统一运行表：

```json
{
  "runId": "c0887c163edc44b1b4408d421ff7f332",
  "taskId": "c0887c163edc44b1b4408d421ff7f332",
  "businessKey": "product_commercialization",
  "version": "product-commercialization-mvp-v1",
  "status": "queued",
  "taskStatus": "queued",
  "retryAfterSeconds": 10,
  "requestId": "req-product-commercialization-001"
}
```

口径说明：正式产品视频任务的业务键是 `promo_video`。当前内部仍复用产品商业化编排服务，不额外暴露底层任务表；对外 `taskId` 等同 `runId`，业务方可用 `runId` 或 `taskId` 调用 `/api/business/runs/get` 查询同一条任务数据。

查询：

```json
{
  "runId": "c0887c163edc44b1b4408d421ff7f332",
  "taskId": "c0887c163edc44b1b4408d421ff7f332",
  "status": "succeeded",
  "billingStatus": "billable",
  "billingUnit": "kie_veo3_fast_video_segment",
  "quotaUnits": 1,
  "videoUrls": ["https://podi.oss-cn-hangzhou.aliyuncs.com/result/product-video-segment-1.mp4"],
  "costBreakdown": {
    "pricingVersion": "product-commercialization-mvp-v1",
    "pricingStatus": "quota_only_mvp",
    "policy": "one_quota_per_generated_video_segment",
    "primaryCostAction": "kie.veo3_fast.video"
  },
  "resultPayload": {
    "businessKey": "promo_video",
    "status": "succeeded",
    "videoAssetPackage": {
      "deliveryStatus": "assets_ready",
      "script": {
        "status": "succeeded",
        "text": "Open with a clean product reveal, show the visible pattern and material, then close with a detail shot."
      },
      "keyframes": [
        {
          "role": "first_frame",
          "status": "succeeded",
          "imageUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/result/product-video-first-frame.png"
        }
      ],
      "segmentVideos": [
        {
          "segmentIndex": 1,
          "status": "succeeded",
          "durationSeconds": 8,
          "videoUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/result/product-video-segment-1.mp4",
          "providerTaskId": "kie_xxx"
        }
      ],
      "composition": {
        "enabled": false,
        "status": "skipped",
        "reason": "Segment assets are ready; composition is optional after review."
      }
    },
    "videoResult": {
      "provider": "kie+ffmpeg",
      "model": "veo3_fast",
      "videoUrls": ["https://podi.oss-cn-hangzhou.aliyuncs.com/result/product-video-segment-1.mp4"]
    }
  }
	}
	```

配图任务成功查询示例：

```json
{
  "runId": "pc-visual-001",
  "taskId": "pc-visual-001",
  "status": "succeeded",
  "billingStatus": "billable",
  "billingUnit": "openai.gpt_image_2.image",
  "quotaUnits": 1,
  "imageUrls": ["https://podi.oss-cn-hangzhou.aliyuncs.com/result/product-social-cover.png"],
  "resultPayload": {
    "businessKey": "product_commercialization",
    "status": "succeeded",
    "imageResult": {
      "provider": "openai",
      "model": "gpt-image-2",
      "imageUrls": ["https://podi.oss-cn-hangzhou.aliyuncs.com/result/product-social-cover.png"]
    }
  }
}
```

### POST /api/business/product-commercialization/video

兼容/内部调试同步入口。正式业务接入不要依赖这个接口；请使用 `/api/business/product-commercialization/runs` 提交，再用 `/api/business/runs/get` 查询。

### POST /api/business/product-commercialization/video-compose

兼容/内部调试同步入口。正式业务接入不要依赖这个接口；默认 `/api/business/product-commercialization/runs` 交付视频素材包，只有显式 `action=compose_video` 才要求合成片。

常见错误：

- `PRODUCT_COMMERCIALIZATION_CONTEXT_INVALID`
- `PRODUCT_COMMERCIALIZATION_ACTION_INVALID`
- `PRODUCT_COMMERCIALIZATION_BUSINESS_KEY_INVALID`
- `PRODUCT_COMMERCIALIZATION_LANGUAGE_INVALID`
- `PRODUCT_COMMERCIALIZATION_MARKET_INVALID`
- `PRODUCT_COMMERCIALIZATION_COPY_SCENARIO_INVALID`
- `PRODUCT_COMMERCIALIZATION_VISUAL_MODE_INVALID`
- `PRODUCT_COMMERCIALIZATION_VIDEO_SCENARIO_INVALID`
- `PRODUCT_COMMERCIALIZATION_TARGET_DURATION_INVALID`
- `PRODUCT_COMMERCIALIZATION_IMAGE_REQUIRED`
- `PRODUCT_COMMERCIALIZATION_KEYFRAME_SCOPE_EMPTY`
- `PRODUCT_COMMERCIALIZATION_IMAGE_BRIEF_MISSING`
- `PRODUCT_COMMERCIALIZATION_VISUAL_PROMPT_EMPTY`
- `PRODUCT_COMMERCIALIZATION_VISUAL_GENERATION_FAILED`
- `PRODUCT_COMMERCIALIZATION_VIDEO_PROMPT_REQUIRED`
- `PRODUCT_COMMERCIALIZATION_VIDEO_ASSET_PLAN_FAILED`
- `PRODUCT_COMMERCIALIZATION_KEYFRAME_GENERATION_FAILED`
- `PRODUCT_COMMERCIALIZATION_VIDEO_ASPECT_REQUIRES_KEYFRAME`
- `PRODUCT_COMMERCIALIZATION_FIRST_FRAME_GENERATION_FAILED`
- `PRODUCT_COMMERCIALIZATION_COMPOSE_NOT_READY`
- `PRODUCT_COMMERCIALIZATION_PREVIEW_FAILED`
- `PRODUCT_COMMERCIALIZATION_VIDEO_GENERATION_FAILED`
- `PRODUCT_COMMERCIALIZATION_SEGMENT_GENERATION_FAILED`
- `PRODUCT_COMMERCIALIZATION_COMPOSE_DOWNLOAD_FAILED`
- `PRODUCT_COMMERCIALIZATION_FFMPEG_MISSING`
- `PRODUCT_COMMERCIALIZATION_COMPOSE_TIMEOUT`
- `PRODUCT_COMMERCIALIZATION_COMPOSE_FAILED`
- `EXECUTOR_TYPE_NOT_KIE`
- `EXECUTOR_TYPE_NOT_VIDU`
- `KIE_API_KEY_MISSING`
- `VIDU_API_KEY_MISSING`
- `VIDU_IMAGE_REQUIRED`
- `VIDU_TASK_CREATE_FAILED`
- `VIDU_TASK_ID_MISSING`
- `VIDU_RESPONSE_INVALID`
- `VIDU_STATUS_ERROR`
- `VIDU_TIMEOUT`
- `VIDU_TASK_FAILED`
- `BUSINESS_API_KEY_BUSINESS_NOT_ALLOWED`

---

## 3.5) 3D 模型渲染视频预览能力

业务名：3D 渲染视频。业务标识固定为 `product_3d_render_video`。它和 `product_commercialization` 的 KIE/Vidu 大模型视频生成是两条路线：这里不调用视频生成模型，也不通过文字提示词生成画面，而是把用户上传的贴图应用到 3D 模型的固定材质槽 / UV 区域，再通过场景、灯光和镜头运动生成可控商品动效。

当前版本开放三个清晰入口：能力目录、方案预览和服务端轻量渲染任务。

- 能力目录：`GET /api/business/product-3d-render-video/catalog`
- 接口：`POST /api/business/product-3d-render-video/preview`
- 服务端渲染任务入口：`POST /api/business/product-3d-render-video/runs`
- 当前模型：`cup_1660`（1660 杯子）、`backpack_2551`（2551 笔记本电脑背包）
- 当前状态：`/preview` 只返回 `model/assetReadiness/renderPlan/review`，不触发服务端视频生成，不产生第三方成本。`/runs` 已接入 `lightweight_scene_renderer_v1`：创建统一 `BusinessRun`，后台生成 MP4、封面帧和 manifest，并回填自有 OSS；高保真 Blender/headless Three.js worker 后续可在不改 API 的前提下替换。
- 边界：客户端负责 GLB/UV/材质槽的实时 WYSIWYG 预览和本地录制；服务端负责可查询、可回调、可沉淀的 MP4、封面帧、manifest 和 OSS 回填。批量导出或高保真渲染时应独立扩容渲染 executor 池，不能混入 KIE/Vidu 队列。
- 当前验收口径：可以验证模型是否进入受控目录、材质槽是否合法、UV 是否存在、贴图 URL 是否齐备、客户端贴图方向是否可接受、渲染参数是否可解释、场景融合规则是否明确、预设镜头或自定义多段关键帧镜头是否遵循 `fit_product_safe_bounds` 完整入画规则、`/runs` 是否返回标准 runId、任务完成后是否有 OSS 视频/封面/manifest。
- 后续执行形态：将 `lightweight_scene_renderer_v1` 替换为 Three.js headless 或 Blender 高保真渲染 worker，保持 `/runs` -> `/api/business/runs/get` 的任务契约不变。
- 能力拆分口径：
  1. `product_3d_render_video.preview`：当前已开放，负责模型、贴图槽、场景、镜头、时长和输出物的方案校验。
  2. `product_3d_render_video.catalog`：当前已开放，只读返回模型、材质槽、场景资产、镜头模板、镜头远近、默认镜头运动和渲染器边界，供业务方构建 UI。
  3. `product_3d_render_video.local_preview_export`：仅测评端/客户端能力，负责浏览器本地预览录制，不作为业务 API 交付。
  4. `product_3d_render_video.render_run`：业务 API `POST /api/business/product-3d-render-video/runs`，负责异步渲染、封面帧、manifest、OSS 回填和任务查询；当前使用轻量服务端渲染器，高保真 worker 后续替换。

能力目录响应摘要：

```json
{
  "businessKey": "product_3d_render_video",
  "version": "product-3d-render-video-catalog-v1",
  "status": "active",
  "defaults": {
    "modelKey": "cup_1660",
    "materialSlot": "front",
    "cameraPreset": "orbit_360",
    "cameraDistance": "wide",
    "scenePreset": "clean_studio",
    "durationSeconds": 6,
    "aspectRatio": "16:9",
    "motionPath": [
      { "x": 0.22, "y": 0.66 },
      { "x": 0.5, "y": 0.5 },
      { "x": 0.78, "y": 0.42 }
    ],
    "cameraPlan": {
      "version": "camera-plan-v1",
      "template": "orbit_360",
      "productMotion": "fixed",
      "cameraMotion": "path_playback",
      "customMode": "preset_template",
      "playbackConfirmed": false,
      "confirmationRequiredBeforeRender": true,
      "path": {
        "coordinateSpace": "normalized_camera_path_preview",
        "points": [
          { "x": 0.22, "y": 0.66 },
          { "x": 0.5, "y": 0.5 },
          { "x": 0.78, "y": 0.42 }
        ],
        "pointCount": 3
      },
      "constraints": {
        "productFixed": true,
        "keepFullProductInFrame": true,
        "avoidTextureDistortion": true
      }
    }
  },
  "models": [
    {
      "modelKey": "cup_1660",
      "displayName": "1660 杯子",
      "recommendedMaterialSlot": "front",
      "materialSlots": ["front", "mouth", "cover", "bottom", "handshank", "else", "else1"],
      "hasUv": true
    }
  ],
  "scenePresets": [
    {
      "key": "clean_studio",
      "asset": {
        "assetId": "podi.scene.procedural.clean_studio.v1",
        "assetStatus": "ready",
        "renderFidelity": "mvp_procedural",
        "externalCandidates": [
          {
            "provider": "Poly Haven",
            "kind": "studio HDRI",
            "license": "CC0",
            "licenseUrl": "https://polyhaven.com/license",
            "ingestStage": "staging_candidate",
            "assetVersion": "to_be_recorded",
            "downloadDate": "not_downloaded",
            "fileHash": "to_be_recorded",
            "downloadRequired": true,
            "workerReadiness": {
              "browserPreview": "not_ingested",
              "serverLightweightRenderer": "not_ingested",
              "highFidelityWorker": "requires_asset_import_test"
            },
            "licenseReview": {
              "required": false,
              "commercialUse": true,
              "licenseUrl": "https://polyhaven.com/license"
            },
            "requiredValidation": [
              "license_and_commercial_use",
              "no_text_logo_watermark_or_brand_props",
              "scene_fusion_no_occlusion",
              "safe_framing_with_close_camera",
              "browser_preview_performance",
              "server_worker_render_smoke"
            ]
          }
        ]
      },
      "fusion": {
        "landingZone": "center_ellipse_floor_zone",
        "occlusionPolicy": "no foreground props may cross the product silhouette"
      },
      "sceneVisualAcceptance": {
        "status": "mvp_ready",
        "summary": "Current procedural scene is ready for preview and lightweight MP4/OSS output; high-fidelity external scene candidates remain staging-only until visual/import gates pass.",
        "checks": [
          {
            "code": "CURRENT_SCENE_ASSET_READY",
            "label": "当前场景资产可执行",
            "status": "passed",
            "evidence": "podi.scene.procedural.clean_studio.v1 · mvp_procedural"
          },
          {
            "code": "SAFE_FRAMING",
            "label": "镜头完整入画",
            "status": "passed",
            "evidence": "wide · frame 56% · margin 7%"
          },
          {
            "code": "HIGH_FIDELITY_IMPORT_SMOKE",
            "label": "高保真候选待入库",
            "status": "planned",
            "evidence": "2 candidates need staging/import smoke before promotion"
          }
        ],
        "candidateSummary": {
          "total": 2,
          "cc0Count": 2,
          "readyCount": 0,
          "blockedCount": 2
        }
      }
    }
  ],
  "sceneAssetSources": [
    {
      "provider": "Poly Haven",
      "sourceType": "hdri_and_3d_models",
      "sourceUrl": "https://polyhaven.com",
      "license": "CC0",
      "licenseUrl": "https://polyhaven.com/license",
      "commercialUse": true,
      "candidateAssets": [
        {
          "assetId": "blocky_photo_studio",
          "displayName": "Blocky Photo Studio",
          "sourceUrl": "https://polyhaven.com/a/blocky_photo_studio",
          "targetScenePresets": ["clean_studio", "marketplace_white"],
          "use": "calibrated studio HDRI for soft commercial product lighting",
          "ingestStage": "staging_candidate",
          "assetVersion": "to_be_recorded",
          "downloadDate": "not_downloaded",
          "fileHash": "to_be_recorded",
          "downloadRequired": true,
          "workerReadiness": {
            "browserPreview": "not_ingested",
            "serverLightweightRenderer": "not_ingested",
            "highFidelityWorker": "requires_asset_import_test"
          },
          "licenseReview": {
            "required": false,
            "commercialUse": true,
            "licenseUrl": "https://polyhaven.com/license"
          },
          "requiredValidation": [
            "license_and_commercial_use",
            "no_text_logo_watermark_or_brand_props",
            "scene_fusion_no_occlusion",
            "safe_framing_with_close_camera",
            "browser_preview_performance",
            "server_worker_render_smoke"
          ]
        },
        {
          "assetId": "blue_photo_studio",
          "displayName": "Blue Photo Studio",
          "sourceUrl": "https://polyhaven.com/a/blue_photo_studio",
          "targetScenePresets": ["desktop_lifestyle"],
          "use": "indoor studio HDRI for lifestyle tabletop depth"
        },
        {
          "assetId": "metal_office_desk",
          "displayName": "Metal Office Desk",
          "sourceUrl": "https://polyhaven.com/a/metal_office_desk",
          "targetScenePresets": ["desktop_lifestyle"],
          "kind": "scene_model",
          "use": "real desk scene model candidate for desktop lifestyle product placement",
          "ingestStage": "staging_candidate",
          "workerReadiness": {
            "browserPreview": "not_ingested",
            "serverLightweightRenderer": "not_ingested",
            "highFidelityWorker": "requires_asset_import_test"
          },
          "requiredValidation": [
            "license_and_commercial_use",
            "scene_fusion_no_occlusion",
            "safe_framing_with_close_camera",
            "server_worker_render_smoke"
          ]
        },
        {
          "assetId": "wooden_display_shelves_01",
          "displayName": "Wooden Display Shelves 01",
          "sourceUrl": "https://polyhaven.com/a/wooden_display_shelves_01",
          "targetScenePresets": ["retail_shelf", "desktop_lifestyle"],
          "kind": "scene_model",
          "use": "non-branded cubby shelf model candidate for retail display and lifestyle product placement",
          "ingestStage": "staging_candidate",
          "workerReadiness": {
            "browserPreview": "not_ingested",
            "serverLightweightRenderer": "not_ingested",
            "highFidelityWorker": "requires_asset_import_test"
          },
          "requiredValidation": [
            "license_and_commercial_use",
            "no_text_logo_watermark_or_brand_props",
            "scene_fusion_no_occlusion",
            "safe_framing_with_close_camera",
            "server_worker_render_smoke"
          ]
        }
      ],
      "ingestStatus": "candidate_source"
    },
    {
      "provider": "ambientCG",
      "sourceType": "pbr_materials_and_models",
      "sourceUrl": "https://ambientcg.com",
      "license": "CC0 1.0 Universal",
      "licenseUrl": "https://docs.ambientcg.com/license/",
      "commercialUse": true,
      "candidateAssets": [
        {
          "assetId": "Wood095",
          "displayName": "Wood 095",
          "sourceUrl": "https://ambientcg.com/a/Wood095",
          "targetScenePresets": ["desktop_lifestyle"],
          "use": "minimal light wood tabletop PBR material"
        },
        {
          "assetId": "Paper006",
          "displayName": "Paper 006",
          "sourceUrl": "https://ambientcg.com/a/Paper006",
          "targetScenePresets": ["gift_table", "marketplace_white"],
          "use": "neutral paper surface for backdrops and gift props"
        },
        {
          "assetId": "Metal037",
          "displayName": "Metal 037",
          "sourceUrl": "https://ambientcg.com/a/Metal037",
          "targetScenePresets": ["retail_shelf", "desktop_lifestyle"],
          "use": "neutral steel/fixture PBR material candidate for shelf and desk frame surfaces"
        }
      ],
      "ingestStatus": "candidate_source"
    }
  ],
  "renderers": {
    "browserPreview": { "status": "ready" },
    "serverLightweight": { "status": "ready", "worker": "lightweight_scene_renderer_v1" },
    "highFidelity": { "status": "planned", "worker": "blender_or_headless_threejs" }
  }
}
```

`sceneAssetSources` 是平台侧场景资产治理字段，业务方通常只读不写。它用于说明后续高保真场景模型、HDRI、PBR 材质可以从哪些来源进入受控资产库，以及每类来源的授权、入库状态和验收门禁。`candidateAssets` 是资产级候选清单，只代表“可入库调研对象”，不是当前渲染直接下载的远程资产。执行请求仍然只传 `scenePreset`，不能让业务方直接传任意第三方模型 URL 绕过授权、性能和内容风险检查。候选资产必须携带 `ingestStage/assetVersion/downloadDate/fileHash/workerReadiness/licenseReview/requiredValidation`，用于资产下载、授权复核、视觉验收和渲染 worker 导入测试。`scenePresets[].renderElements` 与 `/runs` manifest 的 `sceneElements` 是当前场景模型结构，描述背景、台面、道具、层级和遮挡规则；它是平台输出和 worker 输入契约，不是业务方可任意改写的入参。`sceneVisualAcceptance` 是场景可用性验收合同：`status=mvp_ready` 只代表当前程序化/轻量渲染链路可执行；外部高保真候选仍需通过授权、无文字水印、融合遮挡、安全取景、浏览器预览性能和服务端导入 smoke 后，才可以替换成正式场景资产。

最小请求：

```json
{
  "modelKey": "cup_1660",
  "textureImageUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/demo/floral-pattern.png",
  "textureSlots": [
    {
      "materialSlot": "front",
      "imageUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/demo/floral-front.png",
      "label": "杯身正面"
    },
    {
      "materialSlot": "bottom",
      "imageUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/demo/floral-bottom.png",
      "label": "底部"
    }
  ],
  "materialSlot": "front",
  "cameraPreset": "orbit_360",
  "scenePreset": "clean_studio",
  "durationSeconds": 6,
  "aspectRatio": "16:9",
  "outputMode": "plan_only",
  "requestId": "req-product-3d-video-001"
}
```

参数说明：

| 参数 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `modelKey` | 是 | `cup_1660` | `cup_1660/backpack_2551`。 |
| `textureImageUrl` | 兼容字段 | 空 | 单贴图兼容入口。新交互优先使用 `textureSlots`，只传该字段时会按 `materialSlot` 绑定到当前槽位。 |
| `textureImageUrls` | 兼容字段 | 空 | 多贴图 URL 兼容入口。后续正式渲染以 `textureSlots` 的槽位映射为准。 |
| `textureSlots` | 建议 | 空 | 按材质槽绑定的贴图清单，每项包含 `materialSlot/imageUrl/label`。这是 3D WYSIWYG 预览和服务端渲染 worker 的主输入。轻量服务端 MP4/OSS 当前只稳定支持 PNG/JPG/JPEG/WebP；SVG 可用于浏览器本地预览，但提交服务端前需转成栅格图。历史 SVG URL 如果存在同名 `.png/.jpg/.jpeg/.webp` 伴随图，服务端会尝试读取伴随图用于复测恢复，但新请求仍应直接传栅格图 URL。 |
| `materialSlot` | 否 | 模型推荐槽 | 3D 模型的固定材质槽 / UV 区域。1660 杯子推荐 `front`；2551 背包推荐 `front`。非法槽返回 `PRODUCT_3D_RENDER_VIDEO_MATERIAL_SLOT_INVALID`。 |
| `cameraPreset` | 否 | `orbit_360` | `orbit_360/hero_turntable/slow_push_in/detail_sweep/top_reveal/social_arc`。 |
| `cameraDistance` | 否 | `wide` | `wide/standard/close`。默认 `wide`，优先保证商品完整入画。三档都会写入 `renderPlan.camera.framing.mode=fit_product_safe_bounds` 和 `renderPlan.framingSafety`，服务端轻量渲染会按安全取景合同约束镜头运动，避免镜头过近或运动变化导致主体裁切。`close` 会标记为细节补充镜头，不建议作为唯一最终交付视频。非法值返回 `PRODUCT_3D_RENDER_VIDEO_CAMERA_DISTANCE_INVALID`。 |
| `scenePreset` | 否 | `clean_studio` | `clean_studio/marketplace_white/premium_dark/desktop_lifestyle/gift_table/retail_shelf`。每个预设都会绑定 `renderPlan.scene.asset`，包含 `assetId/assetType/license/renderFidelity/materialPolicy`；同时返回 `renderPlan.scene.fusion` 说明商品落点、比例、道具层级、遮挡规则和阴影策略，并返回 `renderPlan.sceneVisualAcceptance` 用于判断当前场景能否执行、候选场景模型卡在哪些入库门禁。测评端会将这些场景以 Three.js 基础场景模型和缩略图呈现，不只是文字说明。 |
| `cameraPlan` | 建议 | 默认镜头方案 | 镜头方案主字段，描述 `productMotion=fixed`、`cameraMotion`、焦点、取景约束和 `playbackConfirmed`。模板镜头使用 `customMode=preset_template`；手动镜头使用 `customMode=manual_keyframe_capture`，并携带 `keyframes/segments/timeline`：每个 keyframe 保存相机位置、焦点、距离、方位角和俯仰角；每段 segment 保存 `seconds` 与 `motion=smooth/orbit`，避免所有动作被平均分配时长。`customShots.start/end` 仍保留为首尾关键帧兼容字段。测评端必须先播放并确认镜头，`/runs` 建议携带 `playbackConfirmed=true`，避免未经确认的镜头直接触发服务端视频生成。 |
| `motionPath` | 兼容字段 | 默认轻微弧线 | 兼容旧调用的镜头运动点数组，每项 `{x,y}` 且范围 0-1；至少 2 点，最多取前 12 点。商品保持固定，不表示商品位移。新接入优先使用 `cameraPlan`；响应里的 `framingSafety.motionPathBounds` 记录镜头运动范围，`appliedMotionScale` 记录轻量渲染器的取景缩放。非法值返回 `PRODUCT_3D_RENDER_VIDEO_MOTION_PATH_INVALID`。 |
| `durationSeconds` | 否 | `6` | 1-30 秒；`/preview` 只进入方案，`/runs` 用于服务端 MP4 帧数和时长。 |
| `aspectRatio` | 否 | `16:9` | 目标画幅。 |
| `outputMode` | 否 | `plan_only` | `/preview` 只允许 `plan_only`。`/runs` 会强制使用 `render_video` 并返回统一业务 runId。 |
| `extraPrompt` | 否 | 空 | 内部渲染备注；不作为大模型提示词，不决定贴图槽或视频内容。测评端默认不展示。 |

服务端渲染任务入口请求与预览一致，但固定使用：

```json
{
  "modelKey": "cup_1660",
  "textureSlots": [
    {
      "materialSlot": "front",
      "imageUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/demo/floral-front.png"
    }
  ],
  "cameraDistance": "wide",
  "scenePreset": "clean_studio",
  "motionPath": [
    { "x": 0.22, "y": 0.66 },
    { "x": 0.5, "y": 0.5 },
    { "x": 0.78, "y": 0.42 }
  ],
  "cameraPlan": {
    "version": "camera-plan-v1",
    "template": "orbit_360",
    "productMotion": "fixed",
    "cameraMotion": "path_playback",
    "playbackConfirmed": true,
    "confirmationRequiredBeforeRender": true,
    "path": {
      "coordinateSpace": "normalized_camera_path_preview",
      "points": [
        { "x": 0.22, "y": 0.66 },
        { "x": 0.5, "y": 0.5 },
        { "x": 0.78, "y": 0.42 }
      ],
      "pointCount": 3
    },
    "constraints": {
      "productFixed": true,
      "keepFullProductInFrame": true,
      "avoidTextureDistortion": true
    }
  },
  "durationSeconds": 6,
  "outputMode": "render_video",
  "requestId": "req-product-3d-render-run-001"
}
```

当前响应：

```json
{
  "runId": "b8e0f0a5d7f14f1a9b9b1d0ad9a7c001",
  "taskId": "b8e0f0a5d7f14f1a9b9b1d0ad9a7c001",
  "businessKey": "product_3d_render_video",
  "version": "p3d-render-video-v1",
  "status": "queued",
  "taskStatus": "queued",
  "retryAfterSeconds": 10
}
```

`version` 是业务 run 版本，长度受 `business_runs.version` 字段限制；轻量渲染器的具体版本保留在 `resultPayload.version`、`costBreakdown.pricingVersion` 和 manifest 里。随后调用 `/api/business/runs/get` 查询。若要读取完整 `resultPayload.renderAssetPackage.manifest`，请求体传 `detail=full`；默认轻量响应会保留 `videoUrls/imageUrls`，但不会展开大型结构化 payload：

```json
{
  "runId": "b8e0f0a5d7f14f1a9b9b1d0ad9a7c001",
  "taskId": "b8e0f0a5d7f14f1a9b9b1d0ad9a7c001",
  "businessKey": "product_3d_render_video",
  "version": "p3d-render-video-v1",
  "status": "succeeded",
  "videoUrls": ["https://podi.oss-cn-hangzhou.aliyuncs.com/.../p3d_xxx.mp4"],
  "imageUrls": ["https://podi.oss-cn-hangzhou.aliyuncs.com/.../p3d_xxx-cover.png"],
  "resultPayload": {
    "renderAssetPackage": {
      "deliveryStatus": "assets_ready",
      "renderer": "lightweight_scene_renderer_v1",
      "videoUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/.../p3d_xxx.mp4",
      "coverFrameUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/.../p3d_xxx-cover.png",
      "manifestUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/.../p3d_xxx-manifest.json",
      "textureApplication": {
        "mode": "slot_texture_mapping",
        "activeMaterialSlot": "front",
        "textureSlotCount": 2,
        "primaryTextureUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/demo/floral-front.png",
        "textureSlots": [
          {
            "materialSlot": "front",
            "imageUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/demo/floral-front.png",
            "label": "杯身正面"
          },
          {
            "materialSlot": "bottom",
            "imageUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/demo/floral-bottom.png",
            "label": "底部"
          }
        ]
      },
      "manifest": {
        "textureApplication": {
          "mode": "slot_texture_mapping",
          "activeMaterialSlot": "front",
          "textureSlotCount": 2,
          "primaryTextureUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/demo/floral-front.png",
          "preserveUv": true
        },
        "sceneAsset": {
          "assetId": "podi.scene.procedural.clean_studio.v1",
          "assetType": "procedural_scene_model",
          "renderFidelity": "mvp_procedural",
          "license": {
            "type": "internal_procedural",
            "commercialUse": true
          },
          "materialPolicy": "neutral matte materials only; no readable labels or brand props"
        },
        "sceneFusion": {
          "landingZone": "center_ellipse_floor_zone",
          "productScale": "56-70% frame height",
          "occlusionPolicy": "no foreground props may cross the product silhouette",
          "propDepth": "lighting cards and backdrop stay behind the product",
          "shadowPolicy": "soft contact shadow under product footprint"
        },
        "sceneVisualAcceptance": {
          "status": "mvp_ready",
          "currentAsset": {
            "assetId": "podi.scene.procedural.clean_studio.v1",
            "assetStatus": "ready",
            "renderFidelity": "mvp_procedural"
          },
          "candidateSummary": {
            "total": 2,
            "readyCount": 0,
            "blockedCount": 2
          },
          "promotionPolicy": {
            "currentRendererCanExecute": true,
            "businessInput": "scenePreset only; external asset URLs are not accepted at execution time"
          }
        },
        "sceneElements": [
          {
            "elementId": "cyclorama_backdrop",
            "type": "seamless_backdrop",
            "depthLayer": "background",
            "zone": "full_frame",
            "occlusion": "never_cross_product_silhouette"
          },
          {
            "elementId": "matte_floor",
            "type": "floor_plane",
            "depthLayer": "surface",
            "zone": "bottom_20_percent",
            "occlusion": "shadow_receiver_only"
          }
        ],
        "framingSafety": {
          "mode": "fit_product_safe_bounds",
          "cameraDistance": "wide",
          "frameHeightRatio": 0.56,
          "safeMarginRatio": 0.07,
          "motionPathBounds": {
            "minX": 0.22,
            "maxX": 0.78,
            "minY": 0.42,
            "maxY": 0.66,
            "spanX": 0.56,
            "spanY": 0.24
          },
          "appliedMotionScale": {
            "xFrameRatio": 0.22,
            "yFrameRatio": 0.16
          },
          "fullProductFitRequired": true,
          "finalDeliveryRecommended": true
        }
      }
    }
  }
}
```

响应摘要：

```json
{
  "businessKey": "product_3d_render_video",
  "status": "previewed",
  "model": {
    "modelKey": "cup_1660",
    "preferredFile": "1660.glb",
    "materialSlots": ["front", "mouth", "cover", "bottom", "handshank", "else", "else1"],
    "hasUv": true
  },
  "assetReadiness": {
    "score": 92,
    "modelReady": true,
    "uvReady": true,
    "textureProvided": true,
    "textureSlotCount": 2,
    "renderWorkerReady": true,
    "renderWorker": "lightweight_scene_renderer_v1",
    "highFidelityWorkerReady": false,
    "highFidelityWorker": "planned"
  },
  "renderPlan": {
    "pipeline": "threejs_or_blender_render_worker",
    "executionStatus": "preview_only",
    "textureApplication": {
      "mode": "slot_texture_mapping",
      "activeMaterialSlot": "front",
      "materialSlot": "front",
      "textureImageUrls": ["https://podi.oss-cn-hangzhou.aliyuncs.com/demo/floral-pattern.png"],
      "textureSlots": [
        {
          "materialSlot": "front",
          "imageUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/demo/floral-front.png",
          "label": "杯身正面"
        },
        {
          "materialSlot": "bottom",
          "imageUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/demo/floral-bottom.png",
          "label": "底部"
        }
      ],
      "textureSlotCount": 2,
      "preserveUv": true,
      "previewBoundary": "client_threejs_wysiwyg_preview_then_server_render_worker"
    },
    "camera": {
      "preset": "orbit_360",
      "distance": {
        "key": "wide",
        "frameHeightRatio": 0.58
      },
      "framing": {
        "mode": "fit_product_safe_bounds",
        "safety": {
          "fullProductFitRequired": true,
          "cameraPathCannotOverrideSafeBounds": true
        }
      }
    },
    "framingSafety": {
      "mode": "fit_product_safe_bounds",
      "cameraDistance": "wide",
      "frameHeightRatio": 0.56,
      "safeMarginRatio": 0.07,
      "motionPathBounds": {
        "spanX": 0.56,
        "spanY": 0.24
      },
      "finalDeliveryRecommended": true
    },
    "cameraPlan": {
      "version": "camera-plan-v1",
      "template": "orbit_360",
      "productMotion": "fixed",
      "cameraMotion": "path_playback",
      "playbackConfirmed": true,
      "path": {
        "coordinateSpace": "normalized_camera_path_preview",
        "points": [
          { "x": 0.22, "y": 0.66 },
          { "x": 0.5, "y": 0.5 },
          { "x": 0.78, "y": 0.42 }
        ],
        "pointCount": 3
      },
      "constraints": {
        "productFixed": true,
        "keepFullProductInFrame": true,
        "avoidTextureDistortion": true
      }
    },
    "motionPath": {
      "mode": "legacy_camera_path_points",
      "points": [
        { "x": 0.22, "y": 0.66 },
        { "x": 0.5, "y": 0.5 },
        { "x": 0.78, "y": 0.42 }
      ]
    },
    "scene": {
      "preset": "clean_studio"
    },
    "sceneVisualAcceptance": {
      "status": "mvp_ready",
      "candidateSummary": {
        "total": 2,
        "readyCount": 0,
        "blockedCount": 2
      },
      "checks": [
        { "code": "CURRENT_SCENE_ASSET_READY", "status": "passed" },
        { "code": "SAFE_FRAMING", "status": "passed" },
        { "code": "HIGH_FIDELITY_IMPORT_SMOKE", "status": "planned" }
      ]
    },
    "deliverables": ["rendered_video_mp4", "cover_frame_png", "render_manifest_json"]
  }
}
```

常见错误：

- `PRODUCT_3D_RENDER_VIDEO_MODEL_INVALID`
- `PRODUCT_3D_RENDER_VIDEO_MATERIAL_SLOT_INVALID`
- `PRODUCT_3D_RENDER_VIDEO_CAMERA_PRESET_INVALID`
- `PRODUCT_3D_RENDER_VIDEO_CAMERA_DISTANCE_INVALID`
- `PRODUCT_3D_RENDER_VIDEO_SCENE_PRESET_INVALID`
- `PRODUCT_3D_RENDER_VIDEO_MOTION_PATH_INVALID`
- `PRODUCT_3D_RENDER_VIDEO_EXECUTION_NOT_READY`
- `PRODUCT_3D_RENDER_VIDEO_TEXTURE_REQUIRED`
- `PRODUCT_3D_RENDER_VIDEO_TEXTURE_LOAD_FAILED`
- `PRODUCT_3D_RENDER_VIDEO_CONTEXT_INVALID`
- `PRODUCT_3D_RENDER_VIDEO_FFMPEG_MISSING`
- `PRODUCT_3D_RENDER_VIDEO_RENDER_RUN_NOT_READY`（历史/兼容，当前轻量渲染器已接入）
- `PRODUCT_3D_RENDER_VIDEO_RENDER_RUN_FAILED`
- `PRODUCT_3D_RENDER_VIDEO_PREVIEW_FAILED`
- `PRODUCT_3D_RENDER_VIDEO_CATALOG_FAILED`

非阻断 issue code：

- `PRODUCT_3D_RENDER_VIDEO_TEXTURE_MISSING`：未提供贴图 URL，接口仍返回方案，但不能验最终贴图效果。
- `PRODUCT_3D_RENDER_VIDEO_UV_MISSING`：模型缺少 UV，接口仍返回方案，但真实贴图前需要修复模型。

---

## 4) 提交裂变生成图评估

### POST /api/business/fission-evaluate/runs

请求体：

```json
{
  "originalImageUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/demo/original.png",
  "generatedImageUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/demo/generated.png",
  "context": {
    "business": "fission",
    "version": "gpt-image2-vl-v2",
    "prompt": "保持原图系列感，生成同系列变化图",
    "bili": "80%"
  },
  "source": "partner-api",
  "channel": "open-api",
  "traceId": "trace-fission-eval-001",
  "requestId": "req-fission-eval-001"
}
```

响应体：

```json
{
  "id": "a0e199ae4b0d476a8294e1ee91bbebda",
  "runId": "a0e199ae4b0d476a8294e1ee91bbebda",
  "businessKey": "fission_evaluate",
  "version": "v1",
  "status": "queued",
  "taskId": "t1.fission_evaluate.default.xxx",
  "imageUrls": [],
  "texts": [],
  "error": null
}
```

轮询成功后重点读取 `resultPayload`、`flowSummary.output` 或 `texts` 中的评分结论：

```json
{
  "runId": "a0e199ae4b0d476a8294e1ee91bbebda",
  "businessKey": "fission_evaluate",
  "status": "succeeded",
  "resultPayload": {
    "decision": "pass",
    "score": 86,
    "problem_tags": [],
    "reason": "图案逻辑与原图一致，质量可用",
    "next_action": "accept"
  }
}
```

参数说明：

| 参数 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `originalImageUrl` | 是 | 无 | 裂变前原图 URL，必须能被中台访问。 |
| `generatedImageUrl` | 是 | 无 | 裂变后生成图 URL，必须能被中台访问。 |
| `context` | 否 | `{}` | 业务上下文。建议传裂变版本、提示词、重绘幅度、profile 等，帮助评分模型判断是否符合目标。 |
| `callbackUrl` | 否 | 无 | 终态回调地址；即使回调失败也可继续用 `runId` 轮询。 |
| `traceId/requestId` | 否 | 自动生成 | 业务链路追踪字段，建议传。 |

常见错误：

- `VL_EVAL_IMAGE_REQUIRED`
- `BUSINESS_CAPABILITY_NOT_FOUND`
- `BUSINESS_RECIPE_ABILITY_NOT_AVAILABLE`
- `BUSINESS_CLIENT_DISABLED`
- `BUSINESS_CLIENT_BUSINESS_NOT_ALLOWED`
- `BUSINESS_API_KEY_INACTIVE`
- `BUSINESS_API_KEY_EXPIRED`
- `BUSINESS_API_KEY_BUSINESS_NOT_ALLOWED`
- `ABILITY_TASK_FAILED`

说明：

- 该接口只做评分，不会自动二次裂变。
- 该接口已经使用业务 API Key 和 `runId` 轮询，不再要求业务方理解评测端 `evalRunId`。
- 如需继续兼容旧 Coze 轮询，可把 `runId` 填入 `/api/coze/podi/tasks/get` 的 `taskId` 字段查询。

---

## 5) 提交扩图

### POST /api/business/outpaint/runs

请求体：

```json
{
  "imageUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/demo/input.png",
  "prompt": "向左右扩展，保持背景纹理、边缘走势和色彩密度一致",
  "source": "partner-api",
  "channel": "open-api",
  "traceId": "trace-outpaint-001",
  "expand_left": 408,
  "expand_right": 408,
  "expand_top": 0,
  "expand_bottom": 0,
  "width": 1024,
  "height": 1024,
  "inputs": {
    "兼容说明": "旧调用仍可继续把参数放在 inputs 内；新调用建议使用顶层字段"
  }
}
```

响应体同图裂变。

常见错误：

- `BUSINESS_IMAGE_URL_REQUIRED`
- `BUSINESS_CAPABILITY_NOT_FOUND`
- `BUSINESS_RECIPE_ABILITY_NOT_AVAILABLE`
- `BUSINESS_CLIENT_DISABLED`
- `BUSINESS_CLIENT_BUSINESS_NOT_ALLOWED`
- `BUSINESS_USER_SCOPE_REQUIRED`
- `BUSINESS_USER_SCOPE_FORBIDDEN`
- `BUSINESS_CLIENT_CONCURRENCY_LIMITED`
- `BUSINESS_CLIENT_DAILY_RUN_LIMITED`
- `BUSINESS_CLIENT_DAILY_QUOTA_LIMITED`
- `COMFYUI_IMAGE_REQUIRED`
- `COMFYUI_TIMEOUT`

说明：

- 新接入建议把 `expand_left/expand_right/expand_top/expand_bottom/width/height/timeout` 直接作为顶层字段传入。
- 旧调用仍兼容 `inputs.expand_left` 等格式。

---

## 6) 查询业务任务

### POST /api/business/pattern-extract/route-preview

### POST /api/business/fission/route-preview

### POST /api/business/outpaint/route-preview

用途：在不提交真实任务、不消耗额度的情况下，预览某个业务方标识会命中哪个业务版本。主要用于默认版本切换前、灰度白名单验证、比例灰度验证。

请求体示例：

```json
{
  "tenantId": "tenant-a",
  "clientId": "coze-main-workflow",
  "metadata": {
    "grayKey": "tenant-a"
  }
}
```

响应体示例：

```json
{
  "businessKey": "fission",
  "requestedVersion": null,
  "selectedCapabilityId": "biz_fission_v2_gray",
  "selectedVersion": "v2",
  "selectedDisplayName": "图裂变 · GPT Image 2 灰度版",
  "selectedStatus": "active",
  "selectedIsDefault": false,
  "selectedBy": "rollout_allowlist",
  "routeInfo": {
    "businessVersionId": "biz_fission_v2_gray",
    "version": "v2",
    "selectedBy": "rollout_allowlist",
    "routeKeyHash": "6f8d7a9c21ab",
    "rolloutPercent": 10
  },
  "defaultCapabilityId": "biz_fission_v1_default",
  "defaultVersion": "v1",
  "activeVersions": [
    {
      "id": "biz_fission_v2_gray",
      "version": "v2",
      "displayName": "图裂变 · GPT Image 2 灰度版",
      "isDefault": false,
      "hasRollout": true
    }
  ]
}
```

说明：

- 预览接口不会创建 `BusinessRun`，不会提交底层能力任务，也不会触发 Coze/ComfyUI/vendor 调用。
- 灰度命中优先级：明确传 `version` > 灰度白名单 > 灰度比例 > 默认版本。
- 灰度标识优先读取 `metadata.grayKey`、`metadata.tenantId`、`inputs.grayKey`，也支持顶层 `tenantId/clientId/traceId/requestId`。
- 对外只返回 `routeKeyHash`，不返回业务方原始灰度标识。

常见错误：

- `AUTHORIZATION_REQUIRED`
- `BUSINESS_CAPABILITY_NOT_FOUND`

---

### GET /api/business/runs/{runId}

用途：查询单个业务任务。

### POST /api/business/runs/get

用途：Coze 工具箱友好的查询接口。

请求体：

```json
{
  "runId": "d7f2f7f37d1d47ad8dd2a9d7d3cb3d39"
}
```

默认返回轻量结果，字段与 Coze 轮询口径保持一致。排障时可追加：

```json
{
  "runId": "d7f2f7f37d1d47ad8dd2a9d7d3cb3d39",
  "detail": "full"
}
```

也兼容 `includeDebug: true`。只有完整模式才返回 `routeInfo/steps/flowSummary/requestPayload/resultPayload/costBreakdown` 等内部排障字段。

Coze 旧工具箱兼容查询：

```json
{
  "taskId": "d7f2f7f37d1d47ad8dd2a9d7d3cb3d39"
}
```

调用 `/api/coze/podi/tasks/get` 后返回 `taskStatus/imageUrls/debugResponse`。该入口主要给 Coze 或同机内网工具箱使用；外部业务默认使用 `/api/business/runs/get`。

默认轻量终态响应示例：

```json
{
  "runId": "d7f2f7f37d1d47ad8dd2a9d7d3cb3d39",
  "taskId": "t1.outpaint.default.xxx",
  "status": "succeeded",
  "taskStatus": "succeeded",
  "imageUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/results/outpaint.png",
  "imageUrls": [
    "https://podi.oss-cn-hangzhou.aliyuncs.com/results/outpaint.png"
  ],
  "videoUrl": null,
  "videoUrls": [],
  "text": "succeeded",
  "texts": [],
  "error": null,
  "errorMessage": null,
  "errorCode": null,
  "debugResponse": null,
  "debugUrl": null,
  "retryAfterSeconds": null,
  "expectedImageCount": null,
  "traceId": "trace-outpaint-001",
  "requestId": "d7f2f7f37d1d47ad8dd2a9d7d3cb3d39",
  "durationMs": 126000,
  "createdAt": "2026-05-14T10:00:00",
  "finishedAt": "2026-05-14T10:02:06"
}
```

默认轻量响应字段说明：

| 字段 | 类型 | 含义 | 业务方处理建议 |
| --- | --- | --- | --- |
| `runId` | string | 中台业务任务 ID，也是业务方保存和轮询的主 ID。 | 提交成功后必须保存；查询 `/api/business/runs/get` 时继续传这个值。 |
| `taskId` | string/null | 兼容任务 ID。普通原子能力任务可能是底层任务 ID；`product_commercialization`、`promo_video`、`product_3d_render_video` 等组合业务中等同 `runId`。 | 业务系统优先保存 `runId`；如果历史系统只保存 `taskId`，也可用它调用 `/api/business/runs/get` 查询同一条任务。 |
| `status` | string | 中台业务状态，取值通常为 `queued/running/succeeded/failed/cancelled/timeout`。 | 判断任务是否结束的主字段。 |
| `taskStatus` | string | 兼容 Coze 旧轮询口径的状态字段。 | 老调用方可以继续读这个字段；含义与 `status` 保持一致。 |
| `imageUrl` | string/null | 第一张结果图的 OSS 地址。 | 只需要单张结果时读取这个字段。 |
| `imageUrls` | string[] | 全部结果图 OSS 地址。 | 裂变、扩图、花纹提取优先读取这个字段。 |
| `videoUrl` | string/null | 第一个视频结果地址。 | 当前三个裂变交付接口通常为空，后续视频能力会使用。 |
| `videoUrls` | string[] | 全部视频结果地址。 | 当前三个裂变交付接口通常为空。 |
| `text` | string/null | 第一条文本结果；没有文本结果时通常为当前状态词。 | 评分接口可能是 JSON 字符串；普通生图接口可忽略。 |
| `texts` | string[] | 全部文本结果。 | 评分接口可读取第一条并按 JSON 解析；普通生图接口通常为空数组。 |
| `resultPayload` | object/null | 结构化结果。默认轻量响应只在评分等无图片输出场景返回关键结构。 | 裂变评分优先读取 `decision/score/problem_tags/reason/next_action`。 |
| `error` | string/null | 失败摘要。 | 只在失败时读取；用于日志和人工排查。 |
| `errorMessage` | string/null | 面向调用方的失败说明。 | 展示给业务或测试同学时优先用这个字段。 |
| `errorCode` | string/null | 标准错误码。 | 程序判断失败类型时优先用这个字段，不要解析错误文案。 |
| `debugResponse` | string/object/null | 脱敏后的调试信息。 | 只用于排障，不作为业务逻辑判断依据。 |
| `debugUrl` | string/null | 中台内部排障链接。 | 内部人员使用；外部业务可忽略。 |
| `retryAfterSeconds` | number/null | 建议下次轮询间隔。 | `queued/running` 时按该值延迟重试，避免高频轮询。 |
| `expectedImageCount` | number/null | 预计出图数量。 | 可用于前端展示进度；为空时不要当作失败。 |
| `logId` | number/null | 能力调用记录 ID。 | 中台排查使用；业务方可随问题单一起提供。 |
| `traceId` | string/null | 调用方传入或中台生成的链路追踪 ID。 | 建议业务方每次提交主动传入，方便跨系统查日志。 |
| `requestId` | string/null | 调用方请求 ID。 | 建议用于业务侧幂等和排障关联。 |
| `durationMs` | number/null | 任务耗时，单位毫秒。 | 终态后用于统计耗时；排队中通常为空。 |
| `createdAt` | string/null | 任务创建时间。 | ISO 时间字符串。 |
| `startedAt` | string/null | 任务实际开始时间。 | 可用于判断排队等待时长。 |
| `finishedAt` | string/null | 任务结束时间。 | 终态后出现。 |

裂变评分 `resultPayload` 字段说明：

| 字段 | 类型 | 含义 | 业务方处理建议 |
| --- | --- | --- | --- |
| `decision` | string | 总结论，常见值为 `pass`、`needs_refission`、`reject`。 | `pass` 可直接使用；`needs_refission` 可再次调用裂变；`reject` 建议人工复核或丢弃。 |
| `score` | number | 0-100 的综合分。 | 可作为排序或阈值判断；最终动作仍以 `decision` 为准。 |
| `scores` | object | 分项评分，例如形状、材质、比例、逻辑。 | 为空或 null 时不视为接口异常。 |
| `problem_tags` | string[] | 问题标签列表。 | 用于二次裂变策略或人工筛选。 |
| `reason` | string | 模型给出的判定原因。 | 可展示给测试/运营，用于解释为什么通过或不通过。 |
| `next_action` | object | 建议动作，例如 `{"type":"accept"}`。 | 可按 `type` 做业务分流。 |
| `eval_json` | object | 更详细的评估证据。 | 默认不要求业务方解析，主要用于质量复盘。 |
| `route_json` | object | 路由或修复建议。 | 需要自动二次裂变时可参考；普通接入可忽略。 |

`detail=full` 排障响应示例：

```json
{
  "runId": "d7f2f7f37d1d47ad8dd2a9d7d3cb3d39",
  "businessKey": "outpaint",
  "version": "v1",
  "status": "succeeded",
  "source": "partner-api",
  "channel": "open-api",
  "traceId": "trace-outpaint-001",
  "requestId": "d7f2f7f37d1d47ad8dd2a9d7d3cb3d39",
  "tenantId": null,
  "clientId": null,
  "abilityId": "comfyui_flux2_klein_9b_outpaint",
  "abilityName": "扩图 · FLUX2-Klein 9B",
  "vendorModelId": null,
  "vendorModelName": null,
  "routeInfo": {
    "businessVersionId": "biz_outpaint_v1_flux2_klein_9b",
    "version": "v1",
    "selectedBy": "default",
    "routeKeyHash": "6f8d7a9c21ab"
  },
	  "flowSummary": {
	    "total": 2,
    "succeeded": 2,
    "failed": 0,
    "running": 0,
    "queued": 0,
    "progressPercent": 100,
    "message": "业务链路执行成功",
    "nextAction": "结果已回填，可继续检查回调状态",
    "route": {
      "businessKey": "outpaint",
      "businessVersionId": "biz_outpaint_v1_flux2_klein_9b",
      "version": "v1",
      "selectedBy": "default"
    },
    "ability": {
      "id": "comfyui_flux2_klein_9b_outpaint",
      "name": "扩图 · FLUX2-Klein 9B",
      "taskId": "task_xxx",
      "logId": 1234
    },
    "executor": {
      "id": "executor_comfyui_pattern_extract_158",
      "name": "ComfyUI 5090 · 158 · 117.50.80.158",
      "type": "comfyui",
      "abilityLogId": 1234
    },
    "output": {
      "hasOutput": true,
      "hasOssOutput": true,
      "imageCount": 1,
      "videoCount": 0,
      "textCount": 0,
      "firstImageUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/results/outpaint.png"
    },
    "callback": {
      "status": null,
      "httpStatus": null,
      "error": null
	    }
	  },
	  "agentTrace": {
	    "source": "image-edit-chat",
	    "agentKey": "agent.image_edit_assistant",
	    "sessionId": "ags_xxx",
	    "sessionStatus": "executed",
	    "planId": "agp_xxx",
	    "planStatus": "executed",
	    "planTitle": "保留花纹主体并增强产品展示质感",
	    "planSummary": "Agent 已按白名单路由调用图片业务能力创建本次业务 run。",
	    "plannerMode": "rule",
	    "plannerModel": "rule-fallback",
	    "toolCallId": "agtc_xxx",
	    "toolName": "business.image_edit",
	    "toolCallStatus": "submitted",
	    "runId": "d7f2f7f37d1d47ad8dd2a9d7d3cb3d39",
	    "requestId": "agent-confirm-agp-001",
	    "traceId": "trace-outpaint-001",
	    "instruction": "把图片改成更适合电商商品图的质感，保持主体花纹不变",
	    "editSkill": "product-retouch",
	    "quality": "high",
	    "size": "auto",
	    "outputFormat": "png",
	    "confirmedAt": "2026-06-02T10:00:00",
	    "executedAt": "2026-06-02T10:00:01"
	  },
	  "steps": [
    {
      "order": 1,
      "stepType": "vl_analyze",
      "role": "preprocess",
      "displayName": "VL 图像理解",
      "status": "succeeded",
      "abilityId": "vl_analyze_image",
      "abilityName": "VL · 图像结构化分析",
      "abilityTaskId": "t1.outpaint.auto.vl_xxx",
      "executorId": "executor_vendor_api_default",
      "executorName": "第三方 API 通道",
      "executorType": "vendor-api",
      "executionEvidence": {
        "abilityLogId": 1233,
        "executorId": "executor_vendor_api_default",
        "executorName": "第三方 API 通道",
        "executorType": "vendor-api",
        "status": "succeeded",
        "hasOssOutput": false,
        "assetCount": 0
      },
      "durationMs": 1830,
      "costAmount": 0.01,
      "currency": "USD",
      "resultSummary": {
        "summary": "蓝白植物图案，主体为连续花纹",
        "imageDesc": "蓝白色植物纹样，中心构图，可用于裂变和扩图提示词",
        "positivePrompt": "蓝白植物连续花型，清新手绘风格"
      }
    },
    {
      "order": 2,
      "stepType": "ability_task",
      "role": "primary",
      "displayName": "主执行能力",
      "status": "succeeded",
      "abilityId": "comfyui_flux2_klein_9b_outpaint",
      "abilityName": "扩图 · FLUX2-Klein 9B",
      "abilityTaskId": "t1.outpaint.auto.xxx",
      "executorId": "executor_comfyui_pattern_extract_158",
      "executorName": "ComfyUI 5090 · 158 · 117.50.80.158",
      "executorType": "comfyui",
      "executionEvidence": {
        "abilityLogId": 1234,
        "executorId": "executor_comfyui_pattern_extract_158",
        "executorName": "ComfyUI 5090 · 158 · 117.50.80.158",
        "executorType": "comfyui",
        "status": "succeeded",
        "storedUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/results/outpaint.png",
        "hasOssOutput": true,
        "assetCount": 1
      }
    }
  ],
  "taskId": "t1.outpaint.default.xxx",
  "imageUrls": [
    "https://podi.oss-cn-hangzhou.aliyuncs.com/results/outpaint.png"
  ],
  "videoUrls": [],
  "texts": [],
  "error": null,
  "durationMs": 126000,
  "costAmount": 0.18,
  "currency": "USD",
  "quotaUnits": 1,
  "debugUrl": null
}
```

常见错误：

- `BUSINESS_RUN_ID_REQUIRED`
- `BUSINESS_RUN_NOT_FOUND`
- `BUSINESS_RUN_FORBIDDEN`

说明：

- 默认轻量响应只返回业务方真正需要处理的字段，避免把 VL 卡片、原子能力原始响应、执行节点证据和 SQL 排障信息一次性返回给业务方。
- `steps` 只在 `detail=full` 或 `includeDebug=true` 时返回，是业务配方步骤状态。当前版本至少记录主执行能力；启用 VL 辅助后会额外提交并记录 VL 步骤。
- `flowSummary` 只在完整模式返回，是给管理端和排障使用的链路证据：包含业务版本、原子能力、实际执行节点、输出回填和回调状态。业务方正常轮询只需要关注 `status/taskStatus/imageUrls/videoUrls/texts/error`。
- `flowSummary.output` 会按 `imageCount/videoCount/textCount/structuredCount/resourceCount` 分开展示，管理端不得继续把所有结果都当图片处理。
- `agentTrace` 只在该 run 由 AI 图片助手创建时返回，用于从普通业务 `runId` 反查聊天会话、计划卡片、工具调用、执行边界时间和实际下发参数；非 Agent 入口该字段为 `null` 或不存在。
- `steps[].executorId/executorName/executionEvidence` 来自能力调用日志，用于确认任务是否真的打到预期机器，以及结果是否已经落 OSS。
- 默认情况下最终出图仍以主执行能力为准，VL 伴随步骤用于链路观测和结果积累。
- 阻塞式 VL 串联开启后，主能力会等 VL 成功后再提交；查询时可能先看到 VL 运行中、主能力仍是 `planned`。
- `steps[].resultSummary` 只返回安全摘要，例如 VL 图片描述、提示词建议、图片/视频数量，不返回完整第三方原始响应或大字段。
- 结果 URL 提取同时兼容 `storedUrl/stored_url/ossUrl/url/sourceUrl`，避免底层已落 OSS 但业务层没有回填。
- `durationMs/costAmount/currency/quotaUnits` 是成本与配额字段。优先读取底层能力日志和厂商返回；若厂商未返回成本，则回退读取模型目录 `costPolicy` 或能力元数据 `pricing/costPolicy` 自动估算。

---

## 7) VL 图像理解原子能力

VL 进入统一能力弹药库，能力 ID：

- `vl_analyze_image`

调用方式仍走统一能力接口：

- `POST /api/abilities/vl_analyze_image/invoke`
- 后续也可通过业务配方把 VL 作为花纹提取/图裂变/扩图的前置分析步骤。

请求体示例：

```json
{
  "inputs": {
    "image_url": "https://podi.oss-cn-hangzhou.aliyuncs.com/demo/input.png",
    "provider": "volcengine_vl",
    "prompt": "分析图片主体、风格、颜色、构图，并输出适合裂变的提示词建议"
  }
}
```

结构化结果字段：

- `description`：图片描述
- `subjects`：主体
- `style`：风格
- `colors`：颜色
- `composition`：构图
- `textElements`：文字元素
- `riskFlags`：风险提示
- `promptCard`：可用于裂变/扩图的提示词建议

常见错误：

- `VL_IMAGE_REQUIRED`
- `VL_PROVIDER_ABILITY_NOT_FOUND`
- `VL_COZE_WORKFLOW_NOT_CONFIGURED`
- `VL_PROVIDER_UNSUPPORTED`

---

## 8) OpenAPI 工具箱

### GET /api/business/openapi.json

用途：给 Coze 导入“业务层工具箱”。
当前包含：

- `podi_business_fission_run`
- `podi_business_outpaint_run`
- `podi_business_product_design_run`
- `podi_business_pattern_extract_run`
- `podi_business_fission_route_preview`
- `podi_business_outpaint_route_preview`
- `podi_business_product_design_route_preview`
- `podi_business_pattern_extract_route_preview`
- `podi_business_run_get`

OpenAPI 内每个工具都会枚举错误响应：

- `400`：缺少必要参数或业务配方非法，例如 `BUSINESS_IMAGE_URL_REQUIRED`、`BUSINESS_RUN_ID_REQUIRED`。
- `401`：缺少服务 Token 或不在可信内网，例如 `AUTHORIZATION_REQUIRED`。
- `403/404`：业务任务不可访问或不存在，例如 `BUSINESS_RUN_FORBIDDEN`、`BUSINESS_RUN_NOT_FOUND`。
- `429`：队列或并发限制。
- `503`：查询链路临时不可用，例如 `BUSINESS_RUN_TEMPORARY_UNAVAILABLE`，业务方可稍后重试查询。
- `403/429`：命中业务方配置限制，例如业务方停用、未开通该业务、日调用或并发达到上限。
- `500`：底层能力、ComfyUI 或第三方模型执行失败，例如 `COMFYUI_TIMEOUT`、`VENDOR_API_EXECUTION_FAILED`。

原则：

- Coze 新工作流优先调用业务 API，而不是在 Coze 内继续手搓底层编排。
- 旧 Coze workflow 不立即下线，继续保障当前业务接入稳定。
- 底层版本切换优先在中台改默认业务版本，避免业务方频繁换 workflow ID。

---

## 9) 管理端接口

### GET /api/admin/business/clients

用途：查看业务方接入配置。业务方配置用于把 `tenantId/clientId` 从“松散日志字段”升级为可启停、可限额、可限制业务范围的管理对象。

可选查询参数：

- `tenant_id`：按业务方过滤。
- `client_id`：按客户端/应用过滤。
- `status`：按状态过滤，例如 `active`、`disabled`。

### POST /api/admin/business/clients

用途：新增业务方配置。配置存在时，业务任务提交会先执行策略检查；未配置的历史调用暂时保持兼容，不强制阻断。

请求体：

```json
{
  "tenantId": "tenant-a",
  "clientId": "coze-main",
  "displayName": "业务方 A · Coze 主工作流",
  "status": "active",
  "allowedBusinessKeys": ["fission", "text_fission", "fission_evaluate", "outpaint", "image_edit", "image_edit_chat", "product_design"],
  "dailyRunLimit": 200,
  "dailyQuotaUnits": 200,
  "concurrentRunLimit": 5,
  "metadata": {
    "owner": "business-a"
  }
}
```

字段说明：

- `tenantId` 是业务方 ID，必填。
- `clientId` 是具体应用或工作流 ID，可为空；为空时表示该 `tenantId` 的默认策略。
- `allowedBusinessKeys` 为空表示不限制业务能力；填值后只允许调用这些业务，例如 `fission/text_fission/fission_evaluate/outpaint/image_edit/image_edit_chat/product_design`。
- `dailyRunLimit` 限制当日提交次数。
- `dailyQuotaUnits` 按估算额度限制当日用量；当前每次提交默认按 1 个额度估算，后续会接正式计费。
- `concurrentRunLimit` 限制该业务方同时处于排队/运行中的任务数。

常见错误：

- `BUSINESS_CLIENT_TENANT_REQUIRED`
- `BUSINESS_CLIENT_DISPLAY_NAME_REQUIRED`
- `BUSINESS_CLIENT_STATUS_INVALID`
- `BUSINESS_CLIENT_DUPLICATED`

### PATCH /api/admin/business/clients/{clientConfigId}

用途：更新业务方配置，例如临时停用、放大额度、只开放部分业务能力。

请求体可只传要修改的字段：

```json
{
  "status": "disabled",
  "dailyRunLimit": 50
}
```

常见错误：

- `BUSINESS_CLIENT_NOT_FOUND`
- `BUSINESS_CLIENT_STATUS_INVALID`
- `BUSINESS_CLIENT_DUPLICATED`

### GET /api/admin/business/api-keys

用途：查看业务 API Key。这里管理的是业务方调用 `/api/business/*` 时使用的 Key，不是第三方模型 Key。

响应字段：

- `keyPreview`：脱敏后的 Key。
- `tenantId/clientId`：Key 绑定的业务方范围。
- `allowedBusinessKeys`：允许调用的业务；为空表示允许全部业务。
- `usageCount`：累计鉴权通过次数。
- `expireAt`：过期时间，可为空。

### POST /api/admin/business/api-keys

用途：创建业务 API Key。当前先用于身份识别和调用审计，暂不强制限流。

请求体：

```json
{
  "name": "业务方 A · 开放接口",
  "key": "podi_live_xxx",
  "status": "active",
  "tenantId": "tenant-a",
  "clientId": "open-api",
  "allowedBusinessKeys": ["fission", "text_fission", "fission_evaluate", "outpaint", "image_edit", "image_edit_chat", "product_design"],
  "expireAt": "2026-12-31T23:59:59"
}
```

常见错误：

- `BUSINESS_API_KEY_DUPLICATED`

### PATCH /api/admin/business/api-keys/{keyId}

用途：更新业务 API Key，例如停用、延期、调整可调用业务。

常见错误：

- `BUSINESS_API_KEY_NOT_FOUND`

### GET /api/admin/business/api-key-usage

用途：查看业务 API Key 调用中心。每次 Key 调用业务提交、路由预览、任务查询或回调相关接口都会写入，管理端可据此判断业务方是否调用了正确接口、是否频繁轮询、失败码是什么。

记录口径：

- 提交、路由预览、任务查询都会记录。
- 成功和失败都会记录；缺参、任务不存在等错误也会保留请求里的 `requestId`、`traceId`、`tenantId`、`clientId`，方便按业务方请求号反查。
- 真实结果轮询建议业务方每 5-10 秒查询一次，过密轮询会在按任务聚合里提示 `POLLING_TOO_FREQUENT`。

可选查询参数：

- `api_key_id`
- `business_key`
- `tenant_id`
- `client_id`
- `method`
- `path`
- `endpoint_kind`：`submit` / `poll` / `callback`
- AI 图片助手的 `confirm` 是提交/执行边界，接口调用中心按 `submit` 统计；否则成功任务会被误判为“只有轮询没有提交”。
- `status_code`
- `status_group`：`success` / `error`
- `error_code`
- `run_id`
- `request_id`
- `trace_id`
- `window_hours`：默认 24；传 0 表示不限制时间窗口。
- `offset` / `limit`：分页参数，`limit` 默认 50，最大 200。
- `group_limit`：按 `runId` 聚合返回数量，默认 30，传 0 表示不返回聚合。

响应结构：

- `items`：分页后的调用明细，字段包括 Key 名称、接口路径、状态码、业务标识、runId、requestId、traceId、tenantId/clientId、错误码和耗时。
- `total` / `offset` / `limit`：兼容旧前端的分页字段。
- `pagination`：明确分页对象，包含 `total`、`offset`、`limit`、`hasMore`、`nextOffset`；新页面优先使用该对象。
- `summary`：当前筛选范围内的总调用、成功、异常、提交、轮询、回调、去重 runId、平均耗时。
- `groups`：按 `runId` 聚合的链路视图，包含提交次数、轮询次数、回调次数、异常次数和最近调用时间。
- `groups[].needsAttention`：是否需要关注。
- `groups[].issueCode`：当前可能值为 `HAS_ERROR`、`POLL_WITHOUT_SUBMIT`、`POLLING_TOO_FREQUENT`。
- `groups[].issueHint`：给管理端展示的人类可读处理提示。

响应示例：

```json
{
  "items": [],
  "total": 128,
  "offset": 0,
  "limit": 50,
  "pagination": {
    "total": 128,
    "offset": 0,
    "limit": 50,
    "hasMore": true,
    "nextOffset": 50
  },
  "summary": {
    "total": 128,
    "successCount": 124,
    "errorCount": 4,
    "submitCount": 16,
    "pollCount": 112,
    "callbackCount": 0,
    "uniqueRunCount": 16,
    "averageDurationMs": 72.5
  },
  "groups": []
}
```

### GET /api/admin/business/api-key-usage/export

用途：导出业务 API Key 调用记录 CSV，供日常排查、交付给业务方核对或早检归档。

查询参数与 `/api/admin/business/api-key-usage` 基本一致，不支持 `offset/group_limit`；`limit` 默认 5000，最大 10000。

导出列包括：时间、接口动作、方法、路径、状态码、业务、`run_id`、`request_id`、`trace_id`、Key 名称、租户、客户端、错误码、耗时、IP、User-Agent。

### GET /api/admin/business/component-catalog

用途：返回业务编排工作台可使用的受控组件目录。这个接口不是业务方调用入口，而是管理端渲染业务链路图、草稿编辑器和上线门禁的组件真源。

当前组件类型：

| 组件类型 | 页面名称 | 用途 |
| --- | --- | --- |
| `input` | 业务入口 | 接收业务参数，生成 `runId`，记录鉴权和调用审计。 |
| `vl` | 图像理解 | 输出图片描述、提示词卡片或业务控制卡。 |
| `comfyui` | 自有 GPU 生图 | 调用 ComfyUI 执行节点完成裂变、扩图等 GPU 任务。 |
| `vendor_api` | 第三方模型 | 调用 OpenAI、火山、KIE、Qwen 等商业模型。 |
| `image_ops` | 图像处理 | 调用自研放大、DPI、尺寸修复等处理服务。 |
| `score` | 质量评估 | 输出评分、判定和问题标签。 |
| `result` | 结果整理 | 归一图片、视频、文本和结构化结果。 |
| `callback` | 业务通知 | 任务终态后通知业务方系统。 |
| `billing` | 成本记录 | 记录内部成本、免计费和后续收费证据。 |
| `acceptance` | 验收证据 | 记录真实样本、人工验收和发布门禁。 |

响应示例：

```json
{
  "version": "2026-05-19.v1",
  "source": "backend.app.constants.business_components",
  "rules": {
    "defaultVersionReadonly": true,
    "draftOnlyEditing": true,
    "noArbitraryCode": true,
    "noArbitraryHttp": true,
    "businessLanguageFirst": true,
    "internalIdsAsDebugOnly": true,
    "heavyExecutionMustBeExternal": true
  },
  "componentTypes": [
    {
      "type": "comfyui",
      "label": "自有 GPU 生图",
      "summary": "调用 ComfyUI 执行节点完成裂变、扩图、抠图等 GPU 任务。",
      "stage": "generation",
      "owner": "backend",
      "draftEditable": true,
      "inputs": [
        {
          "key": "imageUrl",
          "label": "原图",
          "description": "ComfyUI 工作流输入图。",
          "required": true
        }
      ],
      "outputs": [
        {
          "key": "imageUrls",
          "label": "结果图",
          "description": "落到自有 OSS 后返回的图片地址。",
          "required": true
        }
      ],
      "routing": {
        "mode": "executor_tags",
        "description": "通过 required_executor_tags、allowed_executor_ids、健康状态和队列容量选择执行节点。"
      },
      "editableFields": [
        {
          "key": "bili",
          "label": "重绘幅度",
          "type": "number",
          "description": "越高变化越明显；后端按约定映射 denoise。",
          "required": false
        }
      ],
      "lockedFields": [
        {
          "key": "workflowJson",
          "label": "工作流 JSON",
          "reason": "工作流文件由能力目录和交付包管理，草稿只改受控字段。"
        }
      ],
      "errors": [
        {
          "code": "COMFYUI_QUEUE_FULL",
          "label": "队列已满",
          "action": "稍后重试或检查节点容量。"
        }
      ]
    }
  ]
}
```

维护规则：

- 管理端业务编排节点必须优先读取该接口，不再各自写死组件类型和可编辑字段。
- 新增组件类型时，必须同步补输入、输出、错误、路由、可编辑字段和不可编辑字段。
- 线上默认版本仍只读；该目录只说明草稿允许编辑哪些受控字段，不代表可以绕过发布门禁。

### POST /api/admin/business/capabilities/{capabilityId}/drafts

用途：从一个已有业务版本复制出草稿。草稿用于调整编排配方和受控参数，不影响线上默认版本。

请求示例：

```json
{
  "note": "调整图裂变的重绘幅度默认值"
}
```

可选字段：

| 字段 | 是否必填 | 说明 |
| --- | --- | --- |
| `version` | 否 | 指定草稿版本号；不传时后端自动生成，例如 `v1-draft`、`v1-draft-2`。 |
| `displayName` | 否 | 草稿展示名；不传时沿用原版本名称并追加“草稿”。 |
| `note` | 否 | 创建原因，会写入 `draftInfo` 和版本血缘。 |
| `metadata` | 否 | 管理端补充元数据；不要放密钥或敏感信息。 |

响应重点：

```json
{
  "id": "biz_fission_v1-draft_ab12cd34",
  "businessKey": "fission",
  "version": "v1-draft",
  "status": "draft",
  "isDefault": false,
  "recipe": {
    "mode": "single_ability_task",
    "primaryAbilityId": "ability_comfyui_fission"
  },
  "metadata": {
    "draftInfo": {
      "sourceCapabilityId": "biz_fission_v1",
      "sourceVersion": "v1",
      "note": "调整图裂变的重绘幅度默认值"
    },
    "versionLineage": {
      "parentVersionId": "biz_fission_v1",
      "decision": "version_upgrade"
    }
  }
}
```

错误：

| 错误码 | 场景 |
| --- | --- |
| `BUSINESS_CAPABILITY_NOT_FOUND` | 原业务版本不存在。 |
| `BUSINESS_CAPABILITY_VERSION_DUPLICATED` | 指定的草稿版本号已存在。 |
| `BUSINESS_VERSION_REQUIRED` | 指定版本号为空。 |
| `BUSINESS_RECIPE_INVALID` | 原版本配方非法，不能复制为可编辑草稿。 |
| `BUSINESS_RECIPE_ABILITY_NOT_AVAILABLE` | 原版本配方引用的原子能力不可用。 |

### PATCH /api/admin/business/capability-drafts/{draftId}/recipe

用途：保存草稿的受控编排配方。该接口只能修改 `status=draft` 且 `isDefault=false` 的业务版本；线上默认版本和历史 active 版本不能直接改。

请求示例：

```json
{
  "note": "增加 VL 分析步骤，再进入 ComfyUI 裂变",
  "recipe": {
    "mode": "vl_then_primary",
    "primaryAbilityId": "ability_comfyui_fission",
    "steps": [
      {
        "id": "vl",
        "type": "vl_analyze_image",
        "role": "preprocess",
        "abilityId": "ability_vl_analyze_image"
      },
      {
        "id": "primary",
        "type": "ability_task",
        "role": "primary",
        "abilityId": "ability_comfyui_fission"
      }
    ]
  }
}
```

可选字段：

| 字段 | 是否必填 | 说明 |
| --- | --- | --- |
| `recipe` | 是 | 完整业务配方，必须包含可执行步骤。 |
| `primaryAbilityId` | 否 | 兼容字段；传入时会覆盖 `recipe.primaryAbilityId`。 |
| `note` | 否 | 本次修改说明，会写入 `draftInfo.recipeChangeHistory`。 |

响应重点：

- `recipe`：保存后的草稿配方。
- `metadata.draftInfo.lastRecipeDiff`：后端生成的本次变更摘要。
- `metadata.draftInfo.recipeChangeHistory`：最近 20 次草稿配方修改记录。

错误：

| 错误码 | 场景 |
| --- | --- |
| `BUSINESS_CAPABILITY_NOT_FOUND` | 草稿不存在。 |
| `BUSINESS_DRAFT_ONLY_EDITABLE` | 目标不是草稿，或已经是线上默认版本。 |
| `BUSINESS_RECIPE_INVALID` | 配方缺少主能力、步骤非法或步骤结构不合法。 |
| `BUSINESS_RECIPE_ABILITY_NOT_AVAILABLE` | 配方引用的原子能力不可用。 |
| `VENDOR_MODEL_NOT_FOUND` | 配方间接依赖的第三方模型目录不存在。 |

### POST /api/admin/business/capability-drafts/{draftId}/validate

用途：发布前校验草稿是否具备切默认条件。这个接口只做判断，不修改线上默认版本。

校验内容：

| 校验项 | 阻断规则 |
| --- | --- |
| 草稿身份 | 目标必须是 `status=draft` 且 `isDefault=false`。 |
| 编排可用 | 必须有主执行能力，且底层能力、模型、密钥和执行节点没有阻断项。 |
| 真实测试 | 最近一次该草稿业务调用必须成功，并产生图片、视频或文字结果。 |
| 人工验收 | 必须有最近一次 `passed` 验收记录。 |
| 近期失败 | 最近一次调用存在错误时作为警告，不建议发布。 |

响应示例：

```json
{
  "canPublish": false,
  "diffSummary": ["处理步骤数量：1 -> 2", "新增步骤：vl"],
  "releaseGate": {
    "status": "blocked",
    "label": "草稿暂不能发布",
    "canPublish": false,
    "blockers": ["BUSINESS_DRAFT_REAL_RUN_PASSED", "BUSINESS_DRAFT_ACCEPTANCE_PASSED"],
    "warnings": []
  },
  "nextAction": "先用该草稿跑一次真实测试，确认结果能正常回填。"
}
```

错误：

| 错误码 | 场景 |
| --- | --- |
| `BUSINESS_CAPABILITY_NOT_FOUND` | 草稿不存在。 |
| `BUSINESS_DRAFT_ONLY_EDITABLE` | 目标不是草稿，或已经是线上默认版本。 |

### POST /api/admin/business/capability-drafts/{draftId}/publish

用途：草稿通过发布前校验后，将草稿启用并切为该业务入口的默认版本。发布失败时不会改变默认版本。

请求示例：

```json
{
  "note": "草稿验证通过，发布为默认版本"
}
```

发布规则：

- 必须先通过 `validate` 的阻断校验。
- 必须已有真实测试成功样本。
- 必须已有最近一次人工验收通过记录。
- 发布成功后，原默认版本会自动取消默认；草稿变为 `active + isDefault=true`。

错误：

| 错误码 | 场景 |
| --- | --- |
| `BUSINESS_CAPABILITY_NOT_FOUND` | 草稿不存在。 |
| `BUSINESS_DRAFT_ONLY_EDITABLE` | 目标不是草稿。 |
| `BUSINESS_RELEASE_GATE_BLOCKED` | 草稿仍有发布阻断项，例如未真实测试或缺验收证据。 |
| `BUSINESS_ACCEPTANCE_REQUIRED` | 发布过程中发现验收记录缺失。 |

### GET /api/admin/business/capabilities

用途：管理端展示业务能力版本、发布时间、默认版本、配方来源。

响应会额外解析底层来源，便于非技术同学判断“这个业务版本到底在调用什么”：

- `primaryAbilityId` / `primaryAbilityName`：配方中的主原子能力。
- `vendorModelId` / `vendorModelName`：主原子能力绑定的模型目录项；没有绑定时为空。
- `governanceStatus`：上线前体检状态，`ready` 表示底层就绪，`blocker` 表示默认入口存在阻塞，`warning` 表示可测试但需要补治理信息。
- `governanceIssues` / `governanceSuggestions`：体检发现的问题和建议，例如主能力不存在、模型未启用、第三方密钥不可用、模型成本未配置。
- `runtimeKeyConfigured`：第三方模型所需密钥是否可用；非第三方能力可能为空。
- `modelCostConfigured`：第三方模型成本策略是否已配置；非第三方能力可能为空。
- `egressVerified`：需要出网的第三方模型是否在最近 7 天内有 active Key 带密钥出网检查成功；非出网模型可能为空。
- `latestAcceptance` / `acceptanceRecords`：人工验收记录；默认版本切换前必须有最近一次 `passed`。
- `releaseGate`：上线判断摘要，包含 `status`、`label`、`canRelease`、`canRequestDefault`、`blockers`、`warnings`、`suggestions`。管理端以它判断是否能申请默认切换。
- `latestRun`：该业务版本最近一次调用摘要，包含状态、时间、结果数量和错误摘要，供管理端快速判断版本健康度。
- `runMetrics`：该业务版本近 24 小时运行统计，包含总调用、成功、失败、排队、运行中、成功率，供默认版本切换前判断风险。
- `versionFamily`：业务版本族摘要，管理端优先使用它展示业务入口、版本名称、线上/草稿/历史状态、版本路线、父版本、替代版本、归属判断和更新说明，避免前端再次按技术名推断。

业务治理提示码：

| 提示码 | 含义 | 建议动作 |
| --- | --- | --- |
| `BUSINESS_GOVERNANCE_PRIMARY_ABILITY_MISSING` | 业务版本未绑定主能力 | 编辑业务版本，绑定真实主能力后再测试或设为默认。 |
| `BUSINESS_GOVERNANCE_PRIMARY_ABILITY_NOT_FOUND` | 主能力编号在能力目录中不存在 | 修正配方，或恢复对应能力。 |
| `BUSINESS_GOVERNANCE_PRIMARY_ABILITY_INACTIVE` | 主能力未启用 | 先启用主能力，或切换到已启用能力。 |
| `BUSINESS_GOVERNANCE_EXECUTABLE_STEP_MISSING` | 配方没有可执行步骤 | 补齐可执行步骤，避免只剩配置壳。 |
| `BUSINESS_GOVERNANCE_VENDOR_MODEL_NOT_FOUND` | 绑定的第三方模型目录不存在 | 修正模型绑定或重新同步模型目录。 |
| `BUSINESS_GOVERNANCE_VENDOR_MODEL_INACTIVE` | 绑定的第三方模型未启用 | 启用模型，或切到其他可用模型。 |
| `BUSINESS_GOVERNANCE_VENDOR_MODEL_ACCEPTANCE_REQUIRED` | 第三方模型缺少验收通过记录 | 在模型弹药库跑通能力测试或测评端样例，并记录模型验收通过。 |
| `BUSINESS_GOVERNANCE_VENDOR_MODEL_COST_MISSING` | 第三方模型缺少成本策略 | 正式收费或对外开放前补成本口径。 |
| `BUSINESS_GOVERNANCE_VENDOR_KEY_MISSING` | 第三方模型没有可用密钥 | 到模型弹药库配置并验证密钥。 |
| `BUSINESS_GOVERNANCE_VENDOR_EGRESS_NOT_VERIFIED` | 出网模型缺少最近一次带密钥出网验证成功记录 | 在模型弹药库对该厂商 Key 执行验证，确认网络、Key 和上游账号都可用。 |

### POST /api/admin/business/capabilities

用途：新增一个业务版本，例如图裂变 v2、扩图 v2。新增后可以选择是否立即设为默认版本。

请求体：

```json
{
  "businessKey": "fission",
  "version": "v2",
  "displayName": "图裂变 · GPT Image 2 测试版",
  "description": "用于灰度验证蒙版裂变能力",
  "status": "active",
  "isDefault": false,
  "releaseTime": "2026-04-25T10:00:00",
  "primaryAbilityId": "ability_openai_fission",
  "recipe": {
    "mode": "single_ability_task"
  },
  "inputSchema": { "fields": [] },
  "outputSchema": { "fields": [] },
  "metadata": {
    "release_note": "先灰度，不直接替换默认版本",
    "rollout": {
      "enabled": true,
      "percent": 10,
      "allowlist": ["tenant-a"]
    }
  }
}
```

说明：

- `primaryAbilityId` 是必填的业务主能力；后端会自动写入 `recipe.primaryAbilityId` 和第一步配方。
- `isDefault=true` 时，后端会把同一个 `businessKey` 下其它版本改成非默认。
- 默认版本必须是 `active` 状态，并且必须通过完整上线门禁：业务验收通过、底层治理无阻断、第三方模型有验收、计价、可用 Key，出网模型还需要最近 7 天带密钥出网验证成功。
- 预置业务版本只负责初始化和补齐字段，不会在后续刷新时覆盖管理端已经切换的默认版本或启停状态。
- 核心业务必须至少保留一个可回滚保底版本；“可回滚”不只看 active 非默认，还要有最近一次验收通过、最近成功真实样本且有输出、上线门禁不阻塞。图裂变预置 `biz_fission_rollback_e7_flux2_liebian`，扩图预置 `biz_outpaint_rollback_huawen_kuotu`，用于默认版本异常时快速切回。
- `metadata.rollout` 是灰度规则；业务方不指定 `version` 时才会生效。
- 灰度命中优先级：明确传 `version` > 灰度白名单 > 灰度比例 > 默认版本。
- 灰度使用 `metadata.grayKey`、`metadata.tenantId`、`metadata.userId`、顶层 `tenantId/clientId/traceId/requestId`、用户 ID 或图片 URL 做稳定分流；对外只返回 `routeKeyHash`，不直接暴露原始标识。

常见错误：

- `BUSINESS_KEY_REQUIRED`
- `BUSINESS_VERSION_REQUIRED`
- `BUSINESS_DISPLAY_NAME_REQUIRED`
- `BUSINESS_CAPABILITY_VERSION_DUPLICATED`
- `BUSINESS_RECIPE_INVALID`
- `BUSINESS_RECIPE_ABILITY_NOT_AVAILABLE`
- `BUSINESS_DEFAULT_VERSION_MUST_BE_ACTIVE`
- `BUSINESS_ACCEPTANCE_REQUIRED`
- `BUSINESS_RELEASE_GATE_BLOCKED`
- `VENDOR_MODEL_NOT_FOUND`

### PATCH /api/admin/business/capabilities/{capabilityId}

用途：编辑业务版本，常用场景是切默认版本、替换底层原子能力、修改发布时间/说明。

请求体可以只传要修改的字段：

```json
{
  "status": "active",
  "isDefault": true,
  "primaryAbilityId": "ability_openai_fission"
}
```

常见错误同新增接口。

当本次编辑会把版本设为默认，或修改现有默认版本的状态/配方/主能力时，同样会执行完整上线门禁；未通过时返回 `BUSINESS_ACCEPTANCE_REQUIRED` 或 `BUSINESS_RELEASE_GATE_BLOCKED`。

### POST /api/admin/business/capabilities/{capabilityId}/acceptance-records

用途：记录业务版本的人工验收结论。它不改变业务流量，只把“测评端真实链路是否通过、回调和 OSS 回填是否正常”等证据写入版本元数据，方便后续切默认、灰度和回滚时有依据。

请求体：

```json
{
  "status": "passed",
  "note": "测评端真实链路通过，回调和结果回填正常。",
  "evidenceRunId": "run_xxx",
  "evidenceUrl": "https://example.com/report",
  "checklist": {
    "businessFlow": true,
    "callback": true,
    "resultAssets": true
  }
}
```

响应：返回更新后的业务版本，新增字段包括：

- `latestAcceptance`：最近一次验收记录。
- `acceptanceRecords`：最近 5 条验收记录摘要。
- `releaseGate`：会同步更新；`status=ready` 才表示没有明显上线阻断。
- `metadata.latestAcceptance` / `metadata.acceptanceRecords`：完整元数据记录，最多保留 20 条。

常见错误：

- `ADMIN_ONLY`
- `BUSINESS_CAPABILITY_NOT_FOUND`
- `BUSINESS_ACCEPTANCE_STATUS_INVALID`

自动化入口：真实业务巡检通过后，可以用 `backend/scripts/patrol_business_api.py --mode live --record-acceptance` 自动写入验收记录。脚本会把 `runId`、实际执行节点证据、输出数量和巡检来源写入 `metadata`，后续发布门禁读取同一份验收结论。

### POST /api/admin/business/capabilities/{capabilityId}/promote

用途：把某个业务版本切为默认版本，并写入版本事件。相比直接 PATCH `isDefault=true`，这个接口语义更明确，适合管理端按钮、发布记录和后续审计。

请求体：

```json
{
  "activate": true,
  "note": "灰度验证通过，切为默认版本"
}
```

规则：

- `activate=true` 时，如果目标版本当前未启用，会先启用再设为默认。
- `activate=false` 且目标版本未启用时，返回 `BUSINESS_DEFAULT_VERSION_MUST_BE_ACTIVE`。
- 目标版本必须先记录最近一次 `passed` 验收，否则返回 `BUSINESS_ACCEPTANCE_REQUIRED`。
- 目标版本还必须通过完整上线门禁；第三方模型缺计价、缺模型验收、缺可用 Key、出网未验证等都会返回 `BUSINESS_RELEASE_GATE_BLOCKED`。
- 成功后同一个 `businessKey` 下其它版本会自动取消默认。
- 后端会在 `metadata.releaseEvents` 追加 `promote_default` 事件，记录切换原因、操作者和时间。

常见错误：

- `ADMIN_ONLY`
- `BUSINESS_CAPABILITY_NOT_FOUND`
- `BUSINESS_DEFAULT_VERSION_MUST_BE_ACTIVE`
- `BUSINESS_ACCEPTANCE_REQUIRED`
- `BUSINESS_RELEASE_GATE_BLOCKED`

### POST /api/admin/business/rollback/{businessKey}

用途：把某个业务入口回滚到上一默认版本。管理端优先使用这个接口处理线上异常，而不是让运营手工查版本、再点“设为默认”。

请求体：

```json
{
  "activate": true,
  "note": "线上失败，回滚上一稳定版"
}
```

也可以指定明确的回滚目标：

```json
{
  "targetCapabilityId": "biz_fission_v1_default",
  "activate": true,
  "note": "指定回滚到 v1"
}
```

规则：

- 不传 `targetCapabilityId` 时，后端优先读取当前默认版本 `metadata.releaseEvents` 中记录的上一默认版本。
- 如果当前默认版本没有切换记录，则退到同一 `businessKey` 下最近的 active 非默认版本。
- 回滚成功后，目标版本会成为默认版本，其它版本自动取消默认。
- 后端会在目标版本 `metadata.releaseEvents` 追加 `rollback_default` 事件，记录回滚原因、操作者和回滚前默认版本。
- 如果没有可回滚版本，返回 `BUSINESS_ROLLBACK_TARGET_NOT_FOUND`。
- 发版前必须执行 `backend/scripts/business_version_safety_audit.py`，确认花纹提取、图裂变、扩图都有 active 默认版本和 active 保底版本。

常见错误：

- `ADMIN_ONLY`
- `BUSINESS_KEY_REQUIRED`
- `BUSINESS_CAPABILITY_NOT_FOUND`
- `BUSINESS_ROLLBACK_TARGET_NOT_FOUND`
- `BUSINESS_DEFAULT_VERSION_MUST_BE_ACTIVE`

### POST /api/admin/business/route-preview/{businessKey}

用途：管理端灰度命中预览。它和公开 `route-preview` 一样不提交真实任务，只用于验证某个 `tenantId/clientId/grayKey` 会命中哪个版本。

请求体示例：

```json
{
  "tenantId": "tenant-a",
  "metadata": {
    "grayKey": "tenant-a"
  }
}
```

常见错误：

- `ADMIN_ONLY`
- `BUSINESS_CAPABILITY_NOT_FOUND`

### GET /api/admin/business/runs

参数：

- `business_key`：可选，`pattern_extract` / `fission` / `product_design` / `text_fission` / `fission_evaluate` / `outpaint` / `image_edit` / `image_edit_chat`
- `version`：可选，按业务版本过滤，例如 `v1`
- `status`：可选，按运行状态过滤，常见值为 `queued` / `running` / `succeeded` / `failed` / `cancelled`
- `billing_status`：可选，按计费状态过滤，取值为 `billable` / `unpriced` / `no_charge` / `billing_pending`
- `callback_status`：可选，按回调状态过滤，取值为 `success` / `failed` / `running`
- `issue_category`：可选，按链路问题过滤，取值为 `executor` / `output` / `callback` / `billing` / `parameter` / `version` / `none`
- `source`：可选，按调用来源过滤，例如 `coze` / `client` / `partner-api`
- `tenant_id`：可选，按租户/业务方过滤
- `client_id`：可选，按客户端/应用过滤
- `trace_id`：可选，按调用链路 ID 精确查询
- `limit`：默认 50，最大 200

用途：查看最近业务运行记录，为后续统计、计费、灰度分析打基础。

记录字段：

- `traceId/requestId/tenantId/clientId/channel/source`：定位一次业务调用来自哪里、属于哪个业务方或客户端。
- `durationMs`：业务任务主链路耗时，终态后回填。
- `costAmount/currency/quotaUnits/costBreakdown`：底层能力返回的成本和用量，保留做排查与成本测算。
- `billingStatus/chargeable/noChargeReason`：业务计费口径。`billable` 表示成功且有成本或额度，可进入正式账单；`no_charge` 表示失败、取消或超时，不向业务方计费；`billing_pending` 表示任务未终态；`unpriced` 表示成功但缺少定价，需要先补成本规则。
- `issueCategory/issueLabel/issueAction/issueEvidence`：链路问题分类。用于管理端快速区分执行节点、结果回填、业务回调、计费扣减、参数、版本/路由等问题。
- `retestSourceRunId/retestAttempts/retestLatestRunId/retestLatestStatus/retestRecovered/retestSummary`：复测追踪字段。原问题任务会显示复测次数、最新复测任务和是否恢复；复测任务会显示来源任务，便于从“发现问题”追到“确认恢复”。
- `traceSummary`：一次业务调用的父子链路视图，固定包含业务入口、处理步骤、结果回填、业务回调和成本记录节点；管理端排障优先按这个字段渲染，不再把 VL、ComfyUI/OpenAI、回调和计费平铺混看。
- `agentTrace`：仅 Agent 创建的业务 run 返回，包含 `sessionId/planId/toolCallId`、方案摘要、工具状态和执行边界时间；管理端排障时可从 run 详情直接回到“用户说了什么、Agent 规划了什么、最终调用了什么”。

`traceSummary` 示例：

```json
{
  "runId": "run_xxx",
  "rootId": "business_entry",
  "status": "succeeded",
  "summary": "业务链路执行成功",
  "failedNodeId": null,
  "activeNodeId": null,
  "nodes": [
    { "id": "business_entry", "type": "business_entry", "label": "业务入口", "status": "succeeded" },
    { "id": "step_1_primary", "parentId": "business_entry", "type": "generation", "label": "ComfyUI 图裂变", "status": "succeeded" },
    { "id": "result_fill", "parentId": "step_1_primary", "type": "result", "label": "结果回填", "status": "succeeded" }
  ],
  "edges": [
    { "from": "business_entry", "to": "step_1_primary" },
    { "from": "step_1_primary", "to": "result_fill" }
  ]
}
```

### GET /api/admin/business/usage-summary

用途：按当前筛选统计业务调用量、成功率、失败样本、平均耗时、成本和额度消耗，给默认版本切换、灰度观察、后续收费报表使用。

参数：

- `window_hours`：统计窗口，默认 24，范围 1-2160。
- `business_key`：可选，`pattern_extract` / `fission` / `product_design` / `text_fission` / `fission_evaluate` / `outpaint` / `image_edit` / `image_edit_chat`。
- `version`：可选，按业务版本过滤。
- `status`：可选，按运行状态过滤。
- `issue_category`：可选，按链路问题过滤，取值同 `/api/admin/business/runs`。
- `source`：可选，按调用来源过滤，例如 `coze` / `client` / `partner-api`。
- `tenant_id`：可选，按租户/业务方过滤。
- `client_id`：可选，按客户端/应用过滤。
- `trace_id`：可选，按调用链路 ID 精确过滤。

响应示例：

```json
{
  "windowHours": 24,
  "filters": {
    "business_key": "fission",
    "source": "coze",
    "tenant_id": "tenant-a"
  },
  "total": 12,
  "succeeded": 10,
  "failed": 2,
  "running": 0,
  "queued": 0,
  "cancelled": 0,
  "successRate": 0.8333,
  "avgDurationMs": 128000,
  "costByCurrency": {
    "USD": 2.4
  },
  "actualCostByCurrency": {
    "USD": 2.6
  },
  "quotaUnits": 12,
  "actualQuotaUnits": 13,
  "billable": 10,
  "unpriced": 0,
  "noCharge": 2,
  "billingPending": 0,
  "byBusiness": [
    {
      "key": "fission",
      "label": "fission",
      "total": 12,
      "succeeded": 10,
      "failed": 2,
      "running": 0,
      "queued": 0,
      "cancelled": 0,
      "successRate": 0.8333,
      "avgDurationMs": 128000,
      "costByCurrency": { "USD": 2.4 },
      "actualCostByCurrency": { "USD": 2.6 },
      "quotaUnits": 12,
      "actualQuotaUnits": 13,
      "billable": 10,
      "unpriced": 0,
      "noCharge": 2,
      "billingPending": 0,
      "latestAt": "2026-04-25T10:00:00"
    }
  ],
  "bySource": [],
  "byTenant": [],
  "byClient": [],
  "byVersion": [],
  "byIssue": [
    {
      "key": "executor",
      "label": "执行节点问题",
      "total": 2,
      "succeeded": 0,
      "failed": 2,
      "running": 0,
      "queued": 0,
      "cancelled": 0,
      "severity": "danger",
      "action": "检查执行节点连通性、队列、模型依赖和能力日志。"
    }
  ],
  "unresolvedIssues": [
    {
      "key": "executor",
      "label": "执行节点问题",
      "total": 1,
      "failed": 1,
      "running": 0,
      "queued": 0,
      "cancelled": 0,
      "retested": 1,
      "retestAttempts": 2,
      "severity": "danger",
      "action": "检查执行节点连通性、队列、模型依赖和能力日志。"
    }
  ],
  "recentUnresolvedIssues": [
    {
      "id": "run_xxx",
      "runId": "run_xxx",
      "businessKey": "fission",
      "version": "v2",
      "status": "failed",
      "source": "coze",
      "tenantId": "tenant-a",
      "clientId": "coze-main",
      "traceId": "trace-demo-001",
      "issueCategory": "executor",
      "issueLabel": "执行节点问题",
      "issueAction": "检查执行节点连通性、队列、模型依赖和能力日志。",
      "retestAttempts": 2,
      "retestLatestRunId": "run_retest_xxx",
      "retestLatestStatus": "failed",
      "createdAt": "2026-04-25T10:00:00"
    }
  ],
  "recentFailures": [
    {
      "id": "run_xxx",
      "runId": "run_xxx",
      "businessKey": "fission",
      "version": "v2",
      "status": "failed",
      "source": "coze",
      "channel": "coze-workflow",
      "tenantId": "tenant-a",
      "clientId": "coze-main",
      "traceId": "trace-demo-001",
      "error": "TASK_FAILED",
      "createdAt": "2026-04-25T10:00:00"
    }
  ],
  "flowEvidence": {
    "stageEvidence": [
      {
        "key": "primary",
        "label": "主执行",
        "total": 12,
        "succeeded": 10,
        "failed": 2,
        "running": 0,
        "queued": 0,
        "cancelled": 0,
        "successRate": 0.8333,
        "avgDurationMs": 128000,
        "p95DurationMs": 180000,
        "latestAt": "2026-04-25T10:00:00",
        "evidence": {
          "durationSamples": 12,
          "sampleRunIds": ["run_xxx"],
          "top": {
            "selectedBy": [{ "key": "quality_rule", "total": 3 }],
            "loraName": [{ "key": "candidate-lora.safetensors", "total": 3 }],
            "workflowKey": [{ "key": "fission_workflow_v2", "total": 3 }]
          }
        }
      }
    ],
    "routeHits": [
      {
        "key": "quality_rule",
        "label": "quality_rule",
        "total": 3,
        "succeeded": 3,
        "failed": 0,
        "running": 0,
        "queued": 0,
        "cancelled": 0,
        "avgDurationMs": 120000,
        "p95DurationMs": 150000
      }
    ],
    "candidateHits": [],
    "loraHits": [],
    "workflowHits": []
  }
}
```

计费口径：

- `costByCurrency/quotaUnits` 只统计 `billable` 的成功任务，用于后续正式账单。
- `actualCostByCurrency/actualQuotaUnits` 统计底层实际返回的所有成本和用量，用于内部排查和供应商成本复盘。
- 失败、取消、超时任务即使底层返回了成本，也会进入 `noCharge`，不进入业务方正式账单。
- 内部巡检、免计费或测试来源的成功任务也会进入 `noCharge`。典型巡检标识为 `source=business-api-patrol`、`tenantId=podi-internal-patrol`、`metadata.patrol=true`；这类任务仍保留成本用于内部复盘，但不进入业务收费账单。
- `unresolvedIssues/recentUnresolvedIssues` 会排除已经复测成功且有业务结果回填的原问题任务；复测任务本身不会重复计入原问题清单。
- `flowEvidence.stageEvidence` 固定按七阶段返回：`entry`、`version`、`preprocess`、`routing`、`primary`、`output`、`callback-billing`。阶段耗时来自 `business_run_steps.duration_ms`，主执行缺少 step 耗时时会退回 `business_runs.duration_ms`；没有真实耗时样本时 `avgDurationMs/p95DurationMs` 为空。
- `flowEvidence.routeHits/candidateHits/loraHits/workflowHits` 只做观察统计，不会自动改变线上路由、LoRA 或 workflow。候选命中主要来自 `selectedBy=quality_rule/admin_draft/rollout_*` 等非默认分流标识。

常见错误：

- `AUTHORIZATION_REQUIRED`
- `ADMIN_ONLY`

### GET /api/admin/business/runs/export

用途：按当前筛选导出业务运行 CSV，便于把“执行节点问题 / 结果回填问题 / 业务回调问题”等清单交给运维或业务方复核。

参数同 `/api/admin/business/runs`，其中 `limit` 默认 1000、最大 1000。导出内容包含业务、版本、状态、链路问题、处理建议、入口、业务方、客户端、排障编号、能力、输出数量、计费状态、回调状态和错误信息。

常见错误：

- `AUTHORIZATION_REQUIRED`
- `ADMIN_ONLY`

### POST /api/admin/business/runs/{runId}/retest

用途：按旧任务的原始入参创建一条新的复测任务。复测不会修改旧任务状态，也不会沿用旧任务的业务回调地址，避免管理端测试误回调业务方。

处理规则：

- 保留原业务、版本、租户、客户端和主要业务参数。
- 新任务来源固定为 `admin-retest`，渠道固定为 `manual-retest`。
- 新任务 `metadata.adminRetest` 会记录原 `runId/traceId/requestId/status`，便于复盘。
- 旧任务仍处于 `queued/running` 时不允许复测。

常见错误：

- `AUTHORIZATION_REQUIRED`
- `ADMIN_ONLY`
- `BUSINESS_RUN_NOT_FOUND`
- `BUSINESS_RUN_NOT_FINISHED`
- `BUSINESS_RUN_RETEST_PAYLOAD_INVALID`

### POST /api/admin/business/runs/bulk/retest

用途：批量复测当前已加载的问题任务。管理端默认只对失败、取消或链路问题分类不为 `none` 的记录发起复测。

请求体示例：

```json
{
  "runIds": ["run_a", "run_b"],
  "onlyFailed": true
}
```

响应示例：

```json
{
  "action": "retest",
  "total": 2,
  "succeeded": 1,
  "failed": 1,
  "items": [
    { "runId": "run_a", "newRunId": "run_new", "ok": true, "status": "queued", "message": "已创建新的复测任务。" },
    { "runId": "run_b", "ok": false, "status": "skipped", "message": "当前记录没有明显链路问题，已跳过。" }
  ]
}
```

常见错误：

- `AUTHORIZATION_REQUIRED`
- `ADMIN_ONLY`
- `BUSINESS_RUN_IDS_REQUIRED`
- `BUSINESS_RUN_BULK_LIMIT_EXCEEDED`

### POST /api/admin/business/runs/{runId}/callback/retry

用途：单条重试业务终态回调。仅用于任务已终态且配置了 `callbackUrl` 的记录；回调成功后会刷新 `callbackStatus/callbackHttpStatus/callbackError`。

常见错误：

- `AUTHORIZATION_REQUIRED`
- `ADMIN_ONLY`
- `BUSINESS_RUN_NOT_FOUND`
- `BUSINESS_CALLBACK_NOT_CONFIGURED`
- `BUSINESS_RUN_NOT_FINISHED`

### POST /api/admin/business/runs/{runId}/billing/retry

用途：对单条业务任务重试计费扣减。用于“成功且可计费，但套餐/钱包扣减缺失或失败”的记录。

处理规则：

- 仅允许已终态且 `billingStatus=billable` 的任务扣费。
- 缺少平台用户 `userId` 时拒绝扣费，避免无法归属到账户；业务方外部 `userId` 不等同于平台钱包账户。
- 有可用套餐时优先按 `quotaUnits` 扣套餐，幂等键为 `business_run_package:{runId}`。
- 无可用套餐时再按 `costAmount + currency` 换算钱包点数；`USD` 按 `WALLET_POINTS_PER_USD` 换算；缺少成本时可退到 `quotaUnits`，幂等键为 `business_run:{runId}`。
- 结果写回 `costBreakdown.billingSettlement`；套餐路径同时写 `packageSettlement`，钱包路径同时写 `walletSettlement`。
- 同时写 `business_operation_logs`，方便审计是谁触发了重试。

常见错误：

- `AUTHORIZATION_REQUIRED`
- `ADMIN_ONLY`
- `BUSINESS_RUN_NOT_FOUND`
- `BUSINESS_RUN_NOT_FINISHED`
- `BUSINESS_RUN_NOT_BILLABLE`
- `BUSINESS_RUN_UNPRICED`
- `BUSINESS_RUN_USER_REQUIRED`

### POST /api/admin/business/runs/{runId}/billing/refund

用途：对已扣费的业务任务执行套餐或钱包退回。用于“失败任务被误扣费”或人工确认需要退款的场景。

处理规则：

- 套餐扣减优先退回套餐，幂等键为 `business_run_package_refund:{runId}`。
- 钱包扣费通过钱包调账接口写正向流水，幂等键为 `business_run_refund:{runId}`。
- 不删除原扣减流水，保留完整审计链。
- 结果写回 `costBreakdown.billingSettlement.status=refunded`，并同步更新 `packageSettlement` 或 `walletSettlement`。
- 同时写 `business_operation_logs`。

常见错误：

- `AUTHORIZATION_REQUIRED`
- `ADMIN_ONLY`
- `BUSINESS_RUN_NOT_FOUND`
- `BUSINESS_RUN_NOT_FINISHED`
- `BUSINESS_RUN_USER_REQUIRED`
- `BUSINESS_WALLET_SETTLEMENT_NOT_FOUND`
- `BUSINESS_PACKAGE_SETTLEMENT_NOT_FOUND`
- `BUSINESS_PACKAGE_SETTLEMENT_INVALID`

### POST /api/admin/business/runs/bulk/callback-retry

用途：批量重试当前筛选出的回调失败任务。管理端默认只对 `callbackStatus=failed` 或存在 `callbackError` 的已加载记录发起批量重试。

请求体示例：

```json
{
  "runIds": ["run_a", "run_b"],
  "onlyFailed": true
}
```

响应示例：

```json
{
  "action": "callback_retry",
  "total": 2,
  "succeeded": 1,
  "failed": 1,
  "items": [
    { "runId": "run_a", "ok": true, "status": "success" },
    { "runId": "run_b", "ok": false, "status": "skipped", "message": "当前不是回调失败状态，已跳过。" }
  ]
}
```

常见错误：

- `AUTHORIZATION_REQUIRED`
- `ADMIN_ONLY`
- `BUSINESS_RUN_IDS_REQUIRED`
- `BUSINESS_RUN_BULK_LIMIT_EXCEEDED`

### POST /api/admin/business/runs/bulk/mark-ignored

用途：把一批已人工确认的问题记录标记为“无需处理”。该操作不修改真实任务状态，只在结果载荷中写入管理侧处理结论，后续链路问题分类会显示为“已标记无需处理”。

请求体示例：

```json
{
  "runIds": ["run_a", "run_b"],
  "note": "已人工确认，本轮暂不继续处理。"
}
```

常见错误：

- `AUTHORIZATION_REQUIRED`
- `ADMIN_ONLY`
- `BUSINESS_RUN_IDS_REQUIRED`
- `BUSINESS_RUN_BULK_LIMIT_EXCEEDED`

### POST /api/admin/business/runs/issue-checklist

用途：把当前已加载的问题任务生成排障清单，供值班、复盘或交给执行节点维护同学处理。该接口只读任务状态，不重试任务、不改业务结果。

请求体示例：

```json
{
  "runIds": ["run_a", "run_b"],
  "onlyFailed": true
}
```

响应示例：

```json
{
  "generatedAt": "2026-05-06T10:00:00",
  "total": 2,
  "issueCount": 1,
  "skippedCount": 1,
  "byCategory": { "executor": 1 },
  "bySeverity": { "danger": 1 },
  "markdown": "# 业务运行排障清单\n...",
  "items": [
    {
      "runId": "run_a",
      "businessKey": "fission",
      "status": "failed",
      "issueCategory": "executor",
      "issueLabel": "执行节点问题",
      "issueSeverity": "danger",
      "recommendedActions": ["检查执行节点健康、队列长度、模型文件和工作流依赖。"],
      "diagnostics": ["任务状态：failed", "执行节点：ComfyUI 4090"]
    }
  ]
}
```

常见错误：

- `AUTHORIZATION_REQUIRED`
- `ADMIN_ONLY`
- `BUSINESS_RUN_IDS_REQUIRED`
- `BUSINESS_RUN_BULK_LIMIT_EXCEEDED`

说明：

- 统计接口只读业务运行记录，不触发任何任务重试。
- `costByCurrency/quotaUnits` 当前来自底层能力日志、任务结果回填或模型/能力成本规则估算；如果三者都没有成本信息，对应任务会进入 `unpriced`。
- 管理端“业务能力”页的统计卡片、业务分布、来源/业务方分布和最近失败列表均来自该接口。
