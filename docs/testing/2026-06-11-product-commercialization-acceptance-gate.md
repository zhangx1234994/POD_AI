# 产品商业化能力验收门禁（2026-06-11）

## 目标

产品商业化能力当前不再按“接口能跑通”判定完成，而按“商家是否能理解、运营是否能复核、工程师是否能追踪、接入方是否能稳定调用”判定。

本门禁当前覆盖两个独立能力：

- 产品视频素材包：产品图 + 可选产品导出字段 -> 模型画像约束下的脚本、分镜、首尾帧/关键帧、KIE/Vidu 分段视频任务、可选合成、OSS 回填。
- 3D 渲染视频：受控 3D 模型 + 材质槽贴图 -> 场景布景、镜头远近、镜头轨迹确认、本地预览视频或服务端 MP4/OSS 视频。商品固定，轨迹驱动相机运动；当前轻量服务端 worker 已接入，高保真 Blender/headless Three.js worker 仍是后续替换项。

产品文案内容包已从当前测评端主入口撤下，后续按独立 `product_copy_package` 能力重新设计，不再作为本门禁的当前交付项。

## 验收前提

- 文案、产品视频、3D 渲染视频必须是不同能力入口，不共享前端隐藏状态。
- 产品图是最高优先级视觉事实源，导出 JSON 是可选说明材料；没有 JSON 不阻断主流程。
- 预览不偷偷触发成本动作；配图和视频必须显式点击。
- 商业配图默认走 `openai_gpt_image_2_edit` / GPT Image 2，除非用户或策略显式要求低成本、批量或特定模型；当前不作为产品视频主路径。
- 视频时长由模型画像决定，不允许把某一个模型的 8 秒限制写成全局规则。
- 视频最终合成片不是唯一交付物；脚本、分镜、首尾帧、分段视频都要作为可复用素材验收。
- 视频脚本 / 分镜是 AI 中间稿，不是只读调试文本；用户编辑或参数变更后必须重新确认，未确认不得触发视频成本动作。

## 目标逐项验收矩阵

| 原始目标 | 当前实现证据 | 自动化/文档门禁 | 未完成或仍需人工复测 |
| --- | --- | --- | --- |
| 3D 加入场景模型，让商品贴图后能和场景融合 | `GET /api/business/product-3d-render-video/catalog` 返回 `scenePresets[].asset`、`scenePresets[].fusion`、`sceneAssetSources[].candidateAssets`；`POST /api/business/product-3d-render-video/preview` 返回 `renderPlan.scene.asset/fusion`；`/runs` manifest 保留 `sceneAsset/sceneFusion` | `backend/tests/test_product_commercialization.py` 校验 `desktop_lifestyle/gift_table/retail_shelf` 场景、CC0 候选来源、具体候选资产 `Wood095/blue_photo_studio/industrial_coffee_table/wooden_display_shelves_01/steel_frame_shelves_01` 和 `sceneAssetSources.candidateAssets`；默认巡检校验场景预设、来源治理、候选资产和融合证据；`--include-live-3d-render` 额外校验 `/runs` 的 MP4、封面和 manifest OSS 回填 | 当前是 `mvp_procedural` 程序化场景，可用于流程和交互验收；商用品质仍需引入受控高保真 Blender/headless Three.js 场景资产 |
| 3D 能控制镜头和镜头远近，避免商品显示不全 | 后端 `CAMERA_PRESETS` + `CAMERA_DISTANCE_PRESETS` 提供镜头模板和 `wide/standard/close`；`renderPlan.camera.framing.mode=fit_product_safe_bounds`；前端 STEP 4 提供镜头、镜头远近、时长和比例选择 | 后端测试校验非法 `cameraDistance` 报错；服务端轻量渲染测试用 `close + detail_sweep + 极端镜头轨迹` 逐帧检查商品主体像素安全边距；UI 测试校验镜头远近和安全取景信息；接口文档要求默认 `wide` 优先完整入画 | 仍需线上真实视频逐个场景看成片是否裁切；近景只允许作为补充细节镜头，不应作为唯一交付镜头 |
| 3D 通过镜头轨迹确认后生成视频 | 前端 `CameraPathEditor` 支持在预览区拖动镜头轨迹；商品固定在场景中。用户必须先点击“播放并确认镜头轨迹”，确认后才能导出本地预览或提交服务端 `/runs`；后端主字段为 `cameraPlan`，`motionPath` 仅作旧调用兼容 | 后端测试覆盖非法路径；UI 测试模拟选择 `slow_push_in/close`、拖动画出新轨迹、先播放确认，再生成本地预览和服务端 MP4/OSS，断言 preview 与 server run payload 均携带 `cameraPlan.productMotion=fixed`、`cameraPlan.cameraMotion=path_playback` 和兼容 `motionPath`；巡检校验 manifest 的 `cameraPlan` 和兼容路径点 | 仍需真实浏览器人工复测用户自定义镜头轨迹后的输出视频质量，确认取景节奏、画面裁切和贴图方向正常 |
| 产品视频的用户人群、镜头偏好等核心要素应由 VL/JSON 自动回填，用户可修改 | 测评端 `videoPlanningFields` 由 `resolvedProductFacts/videoPlan.directorBrief/storyboard` 推导并标注“模型回填/人工调整/默认约束”；请求持续携带 `videoPlanningContext`；后端把该对象写入视频导演模型上下文 | UI 测试校验模型回填人群和镜头偏好进入 `promo-video/runs` payload；后端测试校验规划 prompt 能看到结构化上下文；OpenAPI 和业务文档包含 `videoPlanningContext` | 第一次规划后自动回填，用户需要返回策略页调整后再重新规划；真实 VL/LLM 回填质量仍需多商品 golden case |
| 脚本输出后，收尾帧需要用户确认，不合理可二次生成 | 确认页按 `videoAssetPackagePlan.shotPackages` 分组展示脚本意图、视频提示词、首尾帧提示词、生成数量和确认状态；可按 `keyframeShotScope` 只重生成某个镜头；提交视频前要求已确认关键帧 | UI 测试覆盖单镜头关键帧生成、确认前视频按钮禁用、确认后提交；确认后再次点击“重生成本镜头首尾帧”会清除该镜头确认状态、重新禁用视频成本按钮，复核后才允许提交；接口文档说明 `keyframeShotScope` 和 `confirmedVideoKeyframes`；巡检脚本在同时开启 `--include-live-keyframes --include-live-video` 时会从关键帧 run 提取确认帧并传给视频 run，无法提取时跳过视频扣费动作并判门禁失败 | 本机因 vendor-api 白名单无法验证真实首尾帧质量；必须在 114 或已加白后端环境跑 GPT Image 2 首尾帧链路 |
| 脚本、收尾帧、对应提示词按列表组呈现后再生成视频 | 前端 `storyboard-groups` 每个镜头集中展示 `goal/videoPrompt/keyframeNeeds/generatedKeyframes`；后端 `shotPackages` 是业务方主消费结构 | UI 测试断言镜头组、脚本、关键帧、首尾帧提示词和生成状态可见；文档要求业务方优先消费 `shotPackages` | 真实 KIE/Vidu 多段素材包仍需线上复测，确认每段视频能和对应镜头组/关键帧正确关联 |
| 最终向业务方提供拆分能力接口 | 正式入口已拆为 `promo-video/plan`、`promo-video/keyframes/runs`、`promo-video/runs`、`promo-video/compose/runs`；3D 拆为 `product-3d-render-video/catalog`、`preview`、`runs` | OpenAPI 测试校验固定 action、请求 schema、错误码和 catalog schema；接口文档列出请求、响应、错误和查询口径 | 旧 `product-commercialization` 聚合入口仍保留为兼容调试，不应作为新业务方主接入口 |

## P0 门禁

| ID | 项目 | 验收动作 | 通过标准 | 当前状态 |
| --- | --- | --- | --- | --- |
| PCG-01 | 视觉与主路径 | 桌面端、移动端打开产品视频和 3D 渲染视频 | 首屏没有内部版本词；接口信息默认不抢占主路径；无横向溢出；输入区和输出区主次清楚 | 本地通过，待线上复测 |
| PCG-02 | 文案入口暂停 | 打开测评端主导航和产品视频分类 | 不出现可验收的产品文案主入口；如历史接口仍返回 `copyPackage`，页面不得把它展示成当前交付能力 | 当前前端仅从产品视频入口进入 `ProductCommercializationWorkbench mode=video` |
| PCG-03 | 无 JSON 主流程 | 只传产品图，不传 `productFields`，生成视频规划 | 不阻断；结果含 `resolvedProductFacts`、缺失字段/推断来源和置信度；不要求用户必须补 JSON | 114 预览巡检通过 |
| PCG-04 | 图片/JSON 错配 | 用明显不匹配的产品图和 JSON 生成视频规划 | 结果区展示冲突；`resolvedProductFacts` 以产品图为准；视频提示需要人工确认风险 | 114 预览巡检通过；兜底冲突提示已补 |
| PCG-05 | 3D 本地视频闭环 | 选择模型、逐槽位贴图、选择场景/镜头/远近、划线路径并导出本地视频 | 页面提供明确生成入口；输出区显示真实格式、播放器和下载；场景卡必须有可视化缩略、商品落点、道具遮挡规则和完整入画说明；不伪装成服务端 OSS 视频 | 本地通过，待线上复测 |
| PCG-06 | 视频规划 | 分别选择 KIE 和 Vidu，生成 8 秒、13/15 秒规划 | 页面和接口返回所选模型画像；KIE 按 8 秒片段，Vidu 按 3/5/8 秒片段；Vidu 必须返回 `aspectPolicy=input_image_ratio`，不伪装成直接支持固定比例；规划结果含 `planner/directorBrief/videoAssetPackagePlan.script/storyboard/shotPackages/keyframeNeeds/compositionPlan`；业务方优先按 `shotPackages` 消费每个镜头的脚本、视频提示词、首尾帧提示词、确认状态和所需素材；每个分镜必须含 `scene/cameraMovement/firstFramePrompt/lastFramePrompt/negativePrompt`；脚本可编辑，编辑后确认状态失效 | 本地通过，待线上真实页面复测 |
| PCG-07 | 视频素材包执行 | 提交 KIE 单段、Vidu 单段、多段素材包任务 | 未确认脚本/分镜时不能提交；有首尾帧需求时必须逐镜头生成并确认，重生成某镜头会清除该镜头确认；确认后提交成功返回统一 runId；查询口径仍是 `/api/business/runs/get`；成功后 `resultPayload.videoAssetPackage` 展示脚本、关键帧、分段视频、可选合成片；Vidu 出片比例按首帧策略验收 | 114 Vidu 8 秒单段真实 runId 通过；KIE/多段仍待复测 |
| PCG-08 | 合成失败保留素材 | 模拟或构造合成失败，但分段视频已成功 | 顶层状态按模式判断；`composition.status=failed`，已成功 `segmentVideos` 仍可下载、可复用、可追踪 | 后端结构已补，待构造线上故障复测 |
| PCG-09 | 状态与失败 | 模拟缺产品图、非法 JSON、旧结果过期、上游失败 | 按错误码返回；按钮禁用或提示原因明确；不暴露异常栈和密钥；可重新提交 | 部分通过，待专项复测 |
| PCG-10 | 文档一致 | 检查业务 API、错误码、测试用例、TODO | 参数、错误码、模型口径、默认配图路线、视频素材包口径四处一致 | 本轮已修旧口径，持续检查 |

## 视觉走查记录

本地 Playwright 当前应覆盖：

- `产品视频` 桌面端：无横向溢出，接口口径不抢占主路径，视频模型说明、脚本分镜、首尾帧确认和成本按钮层级清楚。
- `产品视频` 移动端：无横向溢出，输入区可继续向下滚动。
- `3D 渲染视频` 桌面端：模型预览、槽位列表、场景选择、镜头远近、镜头轨迹确认和本地视频输出不互相遮挡。
- `3D 渲染视频` 移动端：槽位绑定和视频输出可向下完成，不依赖横向滚动。

截图目录：

- `output/visual-audit-after/video-desktop.png`
- `output/visual-audit-after/video-mobile.png`
- `output/playwright/product-commercialization-2026-06-12/product-3d-desktop.png`
- `output/playwright/product-commercialization-2026-06-12/product-3d-mobile.png`

## 真实业务复测顺序

1. 产品视频 preview：正常商品图 + 正常 JSON。
2. 产品视频 preview：只有商品图，没有 JSON。
3. 产品视频 preview：商品图与 JSON 明显不一致。
4. 视频规划：确认返回商品理解、脚本、分镜、首尾帧/关键帧需求和可选合成策略；`核心信息/目标人群/使用场景/镜头偏好/禁止内容` 应基于产品图/VL/JSON 自动回填来源，用户修改后标记为人工调整，重新规划时作为输入。
5. 分镜确认：确认页必须按 `videoAssetPackagePlan.shotPackages` 镜头组展示脚本意图、视频提示词、首尾帧提示词、计划关键帧数量和已生成数量；旧字段只做兼容回退；修改脚本后确认状态应变为待确认。
6. 首尾帧：确认脚本和分镜后，提交 `action=video_keyframes`，结果必须在当前工作台按镜头回填图片和 runId；用户需要逐镜头确认首尾帧，不满意时只重生成对应镜头，重生成后该镜头确认状态失效；所有必需镜头未确认前不能提交视频成本动作。
7. 视频：确认脚本、分镜和首尾帧后，提交 KIE 8 秒单段素材包；线上巡检建议同时打开 `--include-live-keyframes --include-live-video`，让脚本把关键帧结果转成 `confirmedVideoKeyframes` 后再提交视频任务。
8. 视频：Vidu 3/5/8 秒单段素材包各一条，确认参数不同；若输入图不是目标比例，验收时按“比例随首帧/归一首帧”判断，不把 `aspectRatio` 当成 Vidu 直接执行参数。
9. 视频：Vidu 13 秒或 KIE 15 秒多段素材包；合成只作为后续可选动作。
10. 接口拆分：正式接入口径必须覆盖 `POST /api/business/promo-video/plan`、`/promo-video/keyframes/runs`、`/promo-video/runs`、`/promo-video/compose/runs`，并确认后端固定 action；`product-commercialization` 只作为兼容聚合入口。
11. 3D 渲染视频：杯子和背包各跑一遍逐槽位贴图、场景切换、镜头远近、镜头轨迹播放确认、本地视频导出和下载。
12. 3D 场景融合：至少切换 `clean_studio/desktop_lifestyle/retail_shelf` 三类场景，确认页面显示场景缩略、落地区、道具层级和遮挡规则；`/preview` 的 `renderPlan.scene.fusion` 与 `/runs` 的 manifest `sceneFusion` 必须保留同一套证据。
13. 3D 场景候选治理：检查 `desktop_lifestyle/gift_table/retail_shelf` 的 `externalCandidates`，确认 `industrial_coffee_table`、`wooden_display_shelves_01`、`steel_frame_shelves_01` 仍处于 staging/candidate 状态，并包含授权、hash、下载日期、worker 导入和无文字/无遮挡/近景安全取景等晋级门禁；不得把候选场景 URL 当作业务入参直接执行。
14. 错误路径：缺产品图、非法 JSON、旧结果过期、上游失败、分段失败、合成失败或超时。

## 自动化门禁脚本

新增专项脚本：

```bash
python3 backend/scripts/patrol_product_commercialization.py \
  --base-url http://127.0.0.1:8099 \
  --request-timeout 180 \
  --compact-json \
  --report output/product-commercialization-patrol.json
```

默认只跑非成本预览校验，覆盖：

- 正常产品图 + 正常字段。
- 仅产品图、无导出 JSON。
- 产品图与导出字段明显不一致。
- 结构字段：`resolvedProductFacts`、`contentPackage/copyPackage`、`visualAssetPlan`、`videoAssetPackagePlan.script/storyboard/keyframeNeeds/compositionPlan`。
- 正式产品视频规划接口：`POST /api/business/promo-video/plan`，校验 `businessKey=promo_video`、`planner` 证据、`shotPackages`、首尾帧提示词、镜头运动和 `videoPlanningContext` 非成本规划链路。
- 3D 渲染视频非成本接口：`GET /api/business/product-3d-render-video/catalog` 与 `POST /api/business/product-3d-render-video/preview`，校验模型目录、场景预设、`sceneAssetSources` 来源治理、`renderElements` 场景模型结构、镜头远近、场景融合证据、材质槽贴图和安全取景策略。

如果只想临时复查旧聚合预览，可加 `--skip-ability-preview`；封版门禁不建议跳过。

线上允许付费复测时再显式打开成本动作：

```bash
python3 backend/scripts/patrol_product_commercialization.py \
  --base-url http://127.0.0.1:8099 \
  --include-live-visual \
  --include-live-keyframes \
  --include-live-video \
  --include-live-3d-render \
  --video-executor executor_kie_market_default \
  --target-duration 8 \
  --timeout 1200 \
  --report output/product-commercialization-live-patrol.json
```

其中 `--include-live-3d-render` 不调用第三方视频生成模型，但会提交服务端 3D 渲染业务 run，并轮询 `/api/business/runs/get detail=full`，校验 `videoUrls`、`imageUrls`、`resultPayload.renderAssetPackage.manifest.sceneAsset/sceneFusion/framingPolicy/textureApplication/cameraPlan/motionPath`。

如通过公网业务接口执行，必须使用受控业务 Key 或服务令牌，不把真实 Key 写进命令、文档或报告；优先使用环境变量 `PODI_BUSINESS_API_KEY` / `SERVICE_API_TOKEN`。

## 本地走查记录

- 2026-06-11：启动本地后端 `127.0.0.1:8099` 后，测评端 `127.0.0.1:8299` 产品文案 / 产品视频页面均不再出现“测评功能列表加载失败”；桌面和 390px 移动宽度无横向溢出。
- 2026-06-11：产品导出字段 JSON 默认空对象，页面提示“未填写，按产品图推断”，并提供“填入示例字段 / 清空字段，仅用产品图”；符合产品图优先、JSON 可选口径。
- 2026-06-11：产品视频页面按钮与阶段展示已从“分镜合成视频 / 多段合成”改为“单段视频素材 / 分段视频素材包”，并展示脚本、分镜、关键帧、分段视频、合成片五个阶段。
- 2026-06-11：补充 `backend/scripts/patrol_product_commercialization.py`，后续封版前必须至少跑默认预览门禁；线上验收窗口再打开 `--include-live-visual/--include-live-keyframes/--include-live-video` 做真实成本链路。
- 2026-06-11：本机执行默认预览巡检生成 `output/product-commercialization-patrol-local.json`，3 个用例均未通过。直接原因是本地请求超时；后端日志显示上游商品理解链路访问 vendor-api-ops 被拒绝：`VENDOR_API_CLIENT_FORBIDDEN`。该结果不能作为能力失败结论，只能说明当前本机不具备完整 vendor-api allowlist 条件；真实门禁必须在 114 或已加白的后端环境重跑。
- 2026-06-12：产品视频测评端修正为 4 步：`上传产品图组 -> 核对商品并规划视频素材包 -> 确认脚本分镜 -> 素材结果`，不再把“确认商品”和“设置视频策略”拆成两个页面。产品视频规划结果必须展示 `planner` 证据、`directorBrief`、分镜场景/镜头运动、首尾帧提示词和关键帧计划。
- 2026-06-12：3D 渲染视频测评端补齐本地闭环：STEP 4 主动作变为“生成本地预览视频”，结果区显示实际格式、播放器、大小和下载入口；浏览器不支持 MP4 MediaRecorder 时明确回退 WebM；`/preview` 返回 `renderPlan.camera.key` 与 `renderPlan.scene.key`，便于追踪选中的镜头和场景模板。
- 2026-06-12：系统 Chrome 真实页面复测 3D MP4 闭环通过：`127.0.0.1:8200` 选择 1660 杯子、绑定 `mug-front.svg`、检查方案、生成 6 秒视频后页面显示 `598 KB · MP4`，点击“下载 MP4”触发浏览器下载，文件名 `podi-3d-cup_1660-6s-*.mp4`，保存文件大小约 610KB。截图：`output/playwright/market-video-ux-remediation-20260612/product-3d-mp4-result.png`。
- 2026-06-12：本地验证通过：`python3 -m pytest backend/tests/test_product_commercialization.py -q` 为 38 passed；`podi-eval-web` `npm run lint`、`npm run build` 通过；`PODI_EVAL_USE_SYSTEM_CHROME=1 npm run test:ui -- tests/ui/product-video-workbench.spec.ts tests/ui/product-3d-render-video-workbench.spec.ts` 为 2 passed。截图证据目录：`podi-eval-web/output/playwright/product-commercialization-2026-06-12/`。
- 2026-06-12：收费能力质量复测见 `docs/testing/2026-06-12-product-commercialization-paid-quality-review.md`。真实 GPT Image 2 配图 runId `6afeae4282434df2b00eed723fa54021` 成功回填 OSS，真实 Vidu 单段视频 runId `888b187fed8e45709c7ab4ab54b9f0bd` 成功回填 OSS。质量结论：配图可作社媒营销封面，但曾出现旧商品身份污染 prompt；已修复为 brief 只提供场景用途，并补回归测试。二次复测 runId `cf049080925d42bea578037d276a90b3` 的 prompt 污染和黑边问题均通过检查。视频功能可用，但输出 `692x1328` 竖版，后续必须引入首帧归一化或明确按参考图比例验收。
- 2026-06-13：本地 `127.0.0.1:8099` 重新跑 `POST /api/business/product-commercialization/video-keyframes`，代码已进入新增首尾帧路由，但上游返回 `VENDOR_API_CLIENT_FORBIDDEN`，原因仍是本机不在 vendor-api-ops 白名单内。已修正同步调试入口的错误结构：响应现在为 `detail.errorCode=VENDOR_API_CLIENT_FORBIDDEN`，同时带 `detail.businessErrorCode=PRODUCT_COMMERCIALIZATION_KEYFRAME_GENERATION_FAILED` 和 `suggestion`，不再出现 `detail.detail.detail` 嵌套。真实首尾帧质量验收仍必须在 114 控制面或已加白后端环境重跑。
- 2026-06-13：本地浏览器复查产品视频和 3D 渲染视频。产品视频默认只展示视频素材包，不再露出“产品文案内容包”或“文案入口已暂停”的噪音；4 步流程、目标时长、视频规划要素和“添加更多”在同一策略屏。3D 渲染视频桌面/390px 移动端均无横向溢出；选择 1660 杯子、绑定 `mug-front.svg`、检查方案、生成本地预览视频后，页面出现 blob 视频、文件大小和下载按钮。后端 8099 为本地临时服务，检查后已停止。
- 2026-06-13：产品视频测评端继续补交互验收点：预览后会将 `resolvedProductFacts/videoPlan.directorBrief/storyboard` 推导出的核心信息、目标人群、使用场景、镜头偏好和禁止项回填到策略页，并标注“模型回填 / 人工调整 / 默认约束”；确认页新增“模型回填要素”快照，每个镜头展示计划首尾帧数量、已生成数量和“先生成首尾帧再提交视频”等门禁提示。该项为本地 UI 逻辑闭环，真实首尾帧质量仍需在 114 控制面或已加白后端环境重跑。
- 2026-06-13：正式产品视频接口拆分落地：新增 `promo-video/plan`、`promo-video/keyframes/runs`、`promo-video/runs`、`promo-video/compose/runs`，分别固定 `video_preview/video_keyframes/video_generate/compose_video`；正式运行任务返回 `businessKey=promo_video`。当前内部仍复用 `product_commercialization` 编排服务，业务方不再需要自己传 action，也不再把新视频任务混到旧聚合业务键里。
- 2026-06-13：补齐产品视频结构化规划上下文：测评端从可编辑的“核心信息/目标人群/使用场景/镜头偏好/禁止内容/自定义要素”生成 `videoPlanningContext`，并在预览、首尾帧和视频生成请求中持续携带；后端把该对象写入视频导演模型上下文，并保留在业务 API 文档/OpenAPI 中。回归已覆盖：模型回填的人群和镜头偏好最终进入 `promo-video/runs` payload，后端 Volcengine 规划 prompt 能看到结构化上下文。
- 2026-06-13：本地 8299 浏览器复测 3D 渲染视频：在 `http://127.0.0.1:8299/?view=tool&category=3D渲染视频` 选择 1660 杯子，绑定 `/samples/product-video/mug-front.svg` 到 `front` 槽后，本地预览与服务端 MP4 按钮均启用；点击“生成本地预览视频”后页面生成可回放 blob 视频且无录制错误。该次复测后端 8099 未启动，所以能力目录走本地兜底配置；线上仍需复核 catalog 和 `/runs` 的 OSS 回填。
- 2026-06-13：巡检脚本补充 `--include-live-3d-render`，用于显式提交服务端 3D 渲染业务 run，并校验 `videoUrls/imageUrls/resultPayload.renderAssetPackage.manifest` 中的场景资产、`sceneElements` 场景结构、融合策略、安全取景、镜头距离、贴图槽和镜头轨迹。默认巡检仍不触发服务端渲染。
- 2026-06-13：3D 渲染视频 UI 自动化补强：`product-3d-render-video-workbench.spec.ts` 不再只验证默认 `wide/orbit_360`，而是模拟用户选择 `slow_push_in`、`close`，并在“3D 镜头轨迹编辑器”里拖动画出新路径；测试断言 preview 和服务端 MP4/OSS run payload 都携带用户修改后的镜头远近和路径参数。
- 2026-06-13：产品视频 UI 自动化补强：`product-video-workbench.spec.ts` 覆盖单镜头首尾帧生成、确认、确认后重生成、确认状态失效、视频成本按钮重新禁用、再次确认后提交 `confirmedVideoKeyframes` 的完整路径，防止首尾帧二次生成被做成一次性任务表单。
- 2026-06-13：收费巡检链路补强：`patrol_product_commercialization.py` 在同时开启 `--include-live-keyframes --include-live-video` 时，先校验首尾帧任务 `deliveryStatus=keyframes_ready`，再从 `resultPayload.videoAssetPackage.keyframes` 提取已确认帧写入视频任务的 `confirmedVideoKeyframes`；如果关键帧失败或无法提取，脚本会跳过视频扣费动作并给出失败门禁，防止真实验收绕过“先确认帧再生视频”的业务定义。
- 2026-06-13：市场端工作台视觉降噪：产品视频和 3D 渲染视频不再在主内容顶部展示“测评功能列表加载失败”公共横幅；公共能力列表不可用时，主路径仍直接显示工作台，3D 页只在右侧“能力目录”提示本地兜底。普通能力页仍保留完整错误态。
- 2026-06-13：产品视频确认页补充成本动作提示：在“生成首尾帧 / 生成视频素材”按钮组下方明确说明这两个按钮都会提交异步任务并返回 runId，页面会轮询结果，也可以复制 runId 到任务追踪继续查询。该提示用于避免用户把预览规划和真实成本任务混淆。

## 114 线上复测记录

- 2026-06-11：发布 `c59fa6f4+workspace-product-commercialization-20260611` 到 114 控制面，`podi-backend`、`podi-admin-web`、`podi-eval-web` 均为 active，`/health` 返回 `{"status":"ok"}`，`scripts/deploy_preflight.sh` 结果 `PASS=5 FAIL=0`。
- 2026-06-11：首次 114 产品商业化真实巡检发现一个真实缺口：模型/VL 兜底时，产品图与导出字段未完成视觉核验，但模板包把 `fieldConflicts` 置空，导致错配场景没有稳定显示人工复核风险。已修复为：只要存在产品图和导出字段，但商品理解链路兜底或不可用，就保守输出 `PRODUCT_IMAGE_FIELD_CONFLICT`，并要求人工确认后再触发付费配图/视频动作；只有产品图、无导出字段时不误报冲突。
- 2026-06-11：修复后 114 默认预览巡检报告 `/srv/pod/reports/product-commercialization-preview-patrol-20260611-fixed2.json` 通过：`total=3 passed=3 failed=0`。覆盖正常产品图 + 字段、仅产品图无 JSON、产品图与字段明显不一致三类场景。
- 2026-06-11：114 真实 GPT Image 2 配图链路已通过，runId `83f4dd35a8e44d02b946e8a090ae49fd`，结果已回填 OSS：`https://podiaidesign.oss-cn-hangzhou.aliyuncs.com/test/abilities/system/20260611/96d9da72-1781154570.png`。
- 2026-06-11：114 真实 Vidu 单段视频素材包链路已通过，runId `24858339ccd94e588866018ab2c49963`，结果已回填 OSS：`https://podiaidesign.oss-cn-hangzhou.aliyuncs.com/test/abilities/admin-vidu/20260611/750a0574-1781154747.mp4`，`videoAssetPackage.deliveryStatus=assets_ready`。
- 2026-06-11：测评端产品文案 / 产品视频交互改为 AI 摄影棚式渐进工作台：`上传产品图 -> 确认商品事实 -> 设置文案/视频策略 -> 审核内容包/脚本分镜 -> 配图与下载/视频素材包结果`。旧左右堆叠表单已隐藏，产品图常驻右侧摘要；视频执行前必须在第 4 步确认脚本和分镜。线上 114 截图已留存：`output/product-commercialization-progressive-ui/copy-online-114-desktop.png`。
- 2026-06-12：产品视频规划门禁升级：`planner.fallback=true` 只能作为排障/交互验证，不允许作为最终验收；页面必须展示规划器证据、导演 brief、每个镜头的场景/镜头运动/首尾帧提示词。`product_3d_render_video` 当时只验收 Three.js 本地 MP4 预览和下载路径；该状态已在 2026-06-13 推进到轻量服务端 MP4/OSS 闭环。
- 2026-06-12：待下一次发布后复测 114 页面是否同步 4 步产品视频流程和 3D MP4 结果态；发布前不要再以 2026-06-11 的 5 步产品视频截图作为最新交互口径。
- 2026-06-13（历史阶段）：3D 渲染视频接口边界先补齐为受控 `/runs` 入口，未接 worker 时固定返回 `PRODUCT_3D_RENDER_VIDEO_RENDER_RUN_NOT_READY`，用于防止伪造 runId 或 OSS 视频；随后已在同日推进到轻量服务端闭环。
- 2026-06-13：3D 渲染视频从“受控未就绪入口”推进到轻量服务端闭环：`/runs` 创建标准 `BusinessRun`，后台 `lightweight_scene_renderer_v1` 生成 MP4、封面 PNG 和 manifest 并回填 OSS；测评端增加“生成服务端 MP4/OSS 视频”按钮和 runId 轮询。当前验收重点是接口闭环、状态可见、OSS 资产齐备和镜头不过近；高保真 Blender/headless Three.js 渲染仍为下一阶段替换项。
- 2026-06-13：3D 场景资产口径更新：`/preview` 的 `assetReadiness.renderWorkerReady=true` 代表轻量服务端 worker 可执行；`highFidelityWorkerReady=false` 代表商用品质渲染 worker 仍待替换。`renderPlan.scene.asset.externalCandidates` 只记录 Poly Haven / ambientCG 等 CC0 候选来源，不直接把第三方大文件打入仓库。
- 2026-06-13：3D 场景融合口径补齐：测评端场景卡增加可视化缩略，当前方案显示“融合检查”；后端 `renderPlan.scene.fusion` 与服务端 manifest `sceneFusion` 记录 `landingZone/productScale/occlusionPolicy/propDepth/shadowPolicy`。验收时不能只看是否换了背景，还要看商品落点、道具是否后置、贴图槽是否被遮挡、镜头轨迹是否仍完整入画。
- 2026-06-13：3D 服务端渲染参数传递补强：后端测试不再只验证默认 `clean_studio/wide/orbit_360`，而是用 `desktop_lifestyle/social_arc/close` 和自定义镜头轨迹捕获 `_draw_product_frame` 参数，证明场景、镜头、远近和路径会进入服务端逐帧渲染循环，并保留到 `renderAssetPackage.manifest`。
- 2026-06-13：3D 服务端安全取景测试补强：新增轻量 `/runs` 渲染路径的真实逐帧检查，不 mock `_draw_product_frame`，在 `close + detail_sweep + retail_shelf + 极端镜头轨迹` 下校验每帧商品主体仍保留左右和上下安全边距，并确认封面帧为 16:9 有效输出。
- 2026-06-13：3D 渲染视频交互口径修正：物品不再沿路径运动；前端改为 `CameraPathEditor`，路径代表相机运动轨迹。用户必须先播放并确认镜头轨迹，本地预览和服务端 MP4/OSS 按钮才可用。请求主字段新增 `cameraPlan`，其中 `productMotion=fixed`、`cameraMotion=path_playback`、`playbackConfirmed=true`；`motionPath` 保留为兼容路径点字段。
- 2026-06-13：3D 轻量渲染 MP4 编码补强：新增不 mock `_encode_mp4` 的回归测试，真实调用 ffmpeg 编码 1 秒 16:9 MP4，仅 mock 贴图下载和 OSS 上传。测试会校验上传对象包含 `video/mp4`、`image/png`、`application/json`，MP4 字节头含 `ftyp`，封面为 `960x540`，manifest 保留 `scenePreset/sceneAsset/framingPolicy/textureApplication`。这证明轻量 renderer 不只是返回结构，也能实际生成可交付视频字节。
- 2026-06-13：114 控制面候选包真实 `/api/business/product-3d-render-video/runs` 首次提交暴露 `business_runs.version` 字段长度问题：长渲染器版本 `product-3d-render-video-lightweight-v1` 写入 `String(32)` 导致 MySQL 1406。修复口径为拆分业务 run 版本和产物/渲染器版本：`business_runs.version=p3d-render-video-v1`，`resultPayload.version`、`costBreakdown.pricingVersion` 和 manifest 继续保留 `product-3d-render-video-lightweight-v1`。随后真实执行成功生成 MP4/封面但回填阶段又暴露 `business_runs.billing_unit=product_3d_render_video_lightweight` 超过 `String(32)`；同步收敛为 `p3d_render_video_lightweight`。已补接口轮询测试断言短版本和短计费单位长度均不超过 32。
- 2026-06-13：平台复测链路补齐 `product_3d_render_video` 专用分支：失败 run 复测时不再走通用 `create_run`，而是用原始 `textureSlots/scene/camera/cameraPlan/motionPath` 重建 `Product3DRenderVideoRequest` 并调用 3D `/runs` 同一执行路径；复测成功后通过 `BusinessOperationLog(action=retest_run)` 让 usage-summary 自动把原失败样本标记为 recovered，不手工改旧任务状态。
- 2026-06-13：usage-summary 计费口径与详情页统一：成功 run 若在 `request_payload.metadata/inputs` 或 `costBreakdown` 中标记 `billingMode=no_charge`，应归为免计费样本，不进入“缺少定价”未解决问题。该修复覆盖 3D 轻量服务端渲染这类内部无第三方成本能力。
- 2026-06-13：114 控制面最终真实复测通过。直接提交 3D `/runs` runId `59fc56abe9f24c23a2eee424771fbccf`，状态 `succeeded`，`version=p3d-render-video-v1`，`billingUnit=p3d_render_video_lightweight`，OSS 结果：MP4 `https://podiaidesign.oss-cn-hangzhou.aliyuncs.com/test/abilities/service/20260613/1ea3e9ac-1781301521.mp4`，封面 `https://podiaidesign.oss-cn-hangzhou.aliyuncs.com/test/abilities/service/20260613/e9e614c6-1781301521.png`，manifest `https://podiaidesign.oss-cn-hangzhou.aliyuncs.com/test/abilities/service/20260613/fcfe7100-1781301521.json`。对早先失败样本 `ad6a7e156d2f44e8a827fd2b61017f07` 使用标准 retest 生成 runId `1ec12834c58c415daf4bf3b5fc850a7d`，状态 `succeeded`，原失败样本 `retestRecovered=true`；114 `usage-summary` 复查 `failed=1/running=0/queued=0/unresolved=0`，完整 release smoke 通过。
- 2026-06-13：产品视频测评端修复“用模型填写”按钮交互：无已有规划结果时按钮不再禁用，点击后调用同一个 `POST /api/business/promo-video/plan` 让模型识别并回填核心信息、目标人群、使用场景等视频规划要素，同时停留在当前策略页供用户继续人工调整；已有新鲜规划结果时按钮仍作为“用模型结果重填”。已补 Playwright 回归，覆盖未生成规划前按钮可点击、字段回填和不跳转。
- 2026-06-13：测评端产品视频 / 3D 渲染视频的公共能力列表加载失败提示改为轻量状态条：后端目录、评分或最近记录暂不可用时，不再用大面积错误横幅压住主工作台；页面明确提示“当前工作台可继续使用”。UI 回归已模拟 `workflow-versions` 503，确认两个市场端工作台仍可见且提示高度受控。该项只影响离线/后端短暂不可达时的交互降噪，不改变能力接口。

## 暂不封版项

- GPT Image 2 配图已完成真实线上质量复测，但仍需扩展为多商品 golden case。
- 真实复测发现 Vidu 单段任务成功并回填 OSS，但实际比例会跟随参考图/首帧；本轮 8 秒样例输出 `692x1328`。这符合 Vidu 单参考图生视频“比例随首帧”的能力边界。上线前必须确认页面、接口文档和 `videoPlan.aspectPolicy` 已明确该约束，并补首帧归一化方案。
- 未完成真实线上统一 runId 视频素材包任务复测。
- 视频素材包结构化回填已进入本地实现：`script/storyboard/keyframes/segmentVideos/composition`；仍需线上真实链路确认。
- 未形成平台/语气/场景的 golden case 质量基线。
- 未形成产品组图 `product_image_set` 的独立能力契约。
