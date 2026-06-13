# 产品商业化收费能力质量复测（2026-06-12）

## 结论

本轮收费链路不是只验“能不能调用”，而是同时检查功能、结果质量、提示词污染和流程稳定性。

- GPT Image 2 配图：功能跑通，OSS 回填正常；社媒封面商业感可用，但不适合作为严格商品证明图。发现提示词曾混入旧商品身份，已修复并补回归测试。
- Vidu 视频：旧链路功能跑通但暴露比例缺陷，实际输出为竖版 `692x1328`；已改为“GPT Image 2 生成商业首帧 -> 后端确定性归一到目标画幅 -> Vidu 生成原始动态段 -> 后端 ffmpeg 组合完整商品开场 + Vidu 细节段”。最终真实 run 输出推荐成片 `1280x720`、`8.000000s`，`videoUrls[0]` 为组合推荐成片，`videoUrls[1]` 为 Vidu 原始素材段。

## 真实运行证据

| 能力 | runId | 状态 | OSS 结果 |
| --- | --- | --- | --- |
| GPT Image 2 配图 | `6afeae4282434df2b00eed723fa54021` | `succeeded` | `https://podiaidesign.oss-cn-hangzhou.aliyuncs.com/test/abilities/system/20260612/b02f8a99-1781240355.png` |
| Vidu 单段视频 | `888b187fed8e45709c7ab4ab54b9f0bd` | `succeeded` | `https://podiaidesign.oss-cn-hangzhou.aliyuncs.com/test/abilities/admin-vidu/20260612/b6f31a6a-1781234483.mp4` |
| GPT Image 2 配图修复后复测 | `cf049080925d42bea578037d276a90b3` | `succeeded` | `https://podiaidesign.oss-cn-hangzhou.aliyuncs.com/test/abilities/system/20260612/b047cb51-1781242404.png` |
| Vidu 首帧归一化修复后复测 | `22ee421e56704a6db851f4fb677360d2` | `succeeded` | `https://podiaidesign.oss-cn-hangzhou.aliyuncs.com/test/abilities/admin-vidu/20260612/a23688d2-1781245503.mp4` |
| Vidu 组合成片验证 | `33a03256b67e41708eafda850d2b45e4` | `succeeded` | `https://podiaidesign.oss-cn-hangzhou.aliyuncs.com/test/abilities/service/20260612/f53b0001-1781250262.mp4` |
| Vidu 3 秒完整商品开场验证 | `791e9900cc354b9fb8a3c936afdfec66` | `succeeded` | `https://podiaidesign.oss-cn-hangzhou.aliyuncs.com/test/abilities/service/20260612/529256c7-1781251282.mp4` |
| Vidu 淡入过渡最终验证 | `da48605620cf4f4e90f0d69fea2c7206` | `succeeded` | `https://podiaidesign.oss-cn-hangzhou.aliyuncs.com/test/abilities/service/20260612/75e16dfc-1781252337.mp4` |

本地证据：

- `output/quality/product-commercialization-20260612/manual-live-visual-6afe-20260612.json`
- `output/quality/product-commercialization-20260612/manual-live-video-888b-20260612.json`
- `output/quality/product-commercialization-20260612/assets/visual_source_default.jpg`
- `output/quality/product-commercialization-20260612/assets/visual_result_imageUrls.png`
- `output/quality/product-commercialization-20260612/assets/visual_result_after_letterbox_fix_cf04.png`
- `output/quality/product-commercialization-20260612/assets/video_result_videoUrls.mp4`
- `output/quality/product-commercialization-20260612/video-contact-sheet.jpg`
- `output/quality/product-commercialization-20260612/video-ffprobe.json`
- `output/quality/product-commercialization-20260612/live-video-after-first-frame-normalization.json`
- `output/quality/product-commercialization-20260612/live-video-after-first-frame-normalization-run-get.json`
- `output/quality/product-commercialization-20260612/live-video-after-first-frame-normalization-summary.json`
- `output/quality/product-commercialization-20260612/normalized-first-frame-1.png`
- `output/quality/product-commercialization-20260612/normalized-vidu-segment-1.mp4`
- `output/quality/product-commercialization-20260612/normalized-video-contact-sheet.jpg`
- `output/quality/product-commercialization-20260612/final-live-video-after-xfade-report.json`
- `output/quality/product-commercialization-20260612/final-live-video-after-xfade-run-get.json`
- `output/quality/product-commercialization-20260612/final-xfade-normalized-first-frame.png`
- `output/quality/product-commercialization-20260612/final-xfade-composed.mp4`
- `output/quality/product-commercialization-20260612/final-xfade-vidu-segment-1.mp4`
- `output/quality/product-commercialization-20260612/final-xfade-composed-time-contact-sheet.jpg`
- `output/quality/product-commercialization-20260612/final-xfade-vidu-time-contact-sheet.jpg`

旧视频媒体信息：

- codec：`h264`
- 分辨率：`692x1328`
- 时长：`8.041667s`
- 文件大小：`11560747 bytes`

首帧归一化后视频媒体信息：

- 首帧：`1280x720`
- 视频分辨率：`1280x720`
- 视频帧率：`24 fps`
- 视频时长：`8.041667s`
- 视频文件大小：`7924721 bytes`
- `resultPayload.videoPlan.aspectPolicy.mode`：`normalized_first_frame`
- `resultPayload.videoPlan.aspectPolicy.generatedFirstFrameUrls[0]`：`https://podiaidesign.oss-cn-hangzhou.aliyuncs.com/test/abilities/service/20260612/4da9664b-1781245405.png`
- `resultPayload.execution.costActions`：`openai.gpt_image_2.image`、`vidu.viduq3_turbo.video`

## 质量评估

| 项目 | 功能 | 质量 | 一致性 | 结论 |
| --- | --- | --- | --- | --- |
| GPT Image 2 社媒封面 | 5/5 | 4/5 | 3.5/5 | 可作为营销封面样例；不能当作商品证明图。 |
| Vidu + 后端组合视频 | 5/5 | 4.1/5 | 4.6/5 | 可作为产品展示短视频试点交付；完整商品开场由后端确定性保障，Vidu 原始段作为动态细节素材保留。 |

配图质量观察：

- 优点：画面干净，场景明确，主体突出，无文字、水印、价格标签，适合社媒封面或广告封面。
- 风险：花纹和布局存在重绘，不适合详情页材质证明、版权严肃证明或严格商品一致性场景。
- 流程问题：结果 prompt 同时包含了正确的手提袋商品事实，以及旧模板中的 `Floral printed lightweight hooded jacket`。该问题已定位为样例字段与配图 brief 商品身份污染。

视频质量观察：

- 优点：主体稳定，运镜平滑，产品材质和图案有一定展示价值。
- 已修复风险：Vidu 单参考图生视频会跟随参考图/首帧比例，旧链路不能把 `aspectRatio` 当成已强执行的模型参数。当前流程要求先通过 `video_keyframes` 生成并归一化首帧，由用户确认后再把该帧通过 `confirmedVideoKeyframes` 传给 Vidu 视频任务。
- 当前质量观察：最终推荐成片为横版 `1280x720`，没有黑边或竖版漂移；开头约 `3.04s` 完整稳定展示商品，并用约 `0.35s` 淡入过渡到 Vidu 动态细节段。Vidu 原始段仍会快速进入局部裁切，因此不能把原始段直接当唯一交付；它应作为可复用素材保留。
- 首帧观察：归一化首帧比例正确，但 GPT Image 2 原始构图有时会出现类似白色画框/留白。已继续收紧首帧 prompt，要求全画幅商业场景、禁止 smaller framed picture / white mat / inset image / large empty padding。

## 已完成修复

1. `backend/scripts/patrol_product_commercialization.py`
   - 巡检样例字段从旧的外套商品改为当前手提袋商品，避免质量复测样例自身制造冲突。

2. `backend/app/services/product_commercialization.py`
   - `_build_visual_prompt` 不再拼接 raw `visual_brief.prompt`。
   - 配图 prompt 只继承 brief 的场景用途，不继承商品身份、品类、材质和卖点。
   - 增加规则：商品身份、形状、花纹和材质以产品图与解析事实为准。

3. `backend/tests/test_product_commercialization.py`
   - 新增回归断言：即使 brief 内有错误商品名，最终 GPT Image 2 prompt 也不能包含该错误商品身份。

4. 2026-06-12 发布后复测 runId `919f59edeeb943c08908c821df7e7eaf`
   - Prompt 污染已消失：不再包含 `Floral printed lightweight hooded jacket` 或 `Brief hint`。
   - 新发现质量问题：结果图为 `679x679`，画面内容带上下黑边。该图不能作为合格营销图交付。
   - 已继续补充 prompt 硬约束：画面必须填满画布，禁止 letterboxing / black bars / frames / borders。

5. 2026-06-12 最终复测 runId `cf049080925d42bea578037d276a90b3`
   - Prompt 校验通过：不包含旧商品身份或 `Brief hint`，包含 `no letterboxing`、`black bars`、`frames, or borders` 和 `Do not inherit product identity`。
   - 结果图 `679x679`，视觉检查未见上下黑边；主体填满画布，适合作为社媒营销封面样例。
   - 质量仍需标注为“营销封面可用”，不是严格商品证明图；花纹细节仍可能存在模型重绘。

6. 2026-06-12 Vidu 首帧归一化复测 runId `22ee421e56704a6db851f4fb677360d2`
   - `videoPlan.aspectPolicy.mode=normalized_first_frame`，说明执行层没有继续使用原始竖图直接提交 Vidu。
   - GPT Image 2 生成并归一化首帧 `1280x720`，OSS：`https://podiaidesign.oss-cn-hangzhou.aliyuncs.com/test/abilities/service/20260612/4da9664b-1781245405.png`。
   - Vidu 输出视频 `1280x720`、`8.041667s`，OSS：`https://podiaidesign.oss-cn-hangzhou.aliyuncs.com/test/abilities/admin-vidu/20260612/a23688d2-1781245503.mp4`。
   - `execution.costActions` 同时记录 `openai.gpt_image_2.image` 和 `vidu.viduq3_turbo.video`，成本证据完整。
   - 继续补充首帧 prompt 约束，避免白色画框、画中画、留白和边框布局。

   2026-06-13 口径更新：上述复测证据保留为质量样例，但执行流程已改为硬门禁：视频生成阶段不再自动补首帧。业务方或测评端必须先生成并确认首尾帧/关键帧，再调用 `video_generate`；否则返回 `PRODUCT_COMMERCIALIZATION_KEYFRAMES_UNCONFIRMED`，不会触发 KIE/Vidu 视频扣费。

7. 2026-06-12 Vidu 原始段不可控裁切复盘与组合成片修复
   - 复测发现即使首帧 `1280x720`，Vidu 原始段仍会在 0.5-1.5 秒内快速推进到局部纹理，无法稳定保障“完整商品先看清楚”。
   - 后端新增 `opening_hold_plus_vidu_segment` 组合策略：使用归一化首帧生成完整商品开场，再拼接 Vidu 动态细节段，组合成片排在 `videoUrls[0]`，原始 Vidu 段排在 `videoUrls[1]`。
   - runId `33a03256b67e41708eafda850d2b45e4` 验证组合入链：`provider=vidu+ffmpeg`，`deliveryStatus=composed_ready`，组合视频 `1280x720`、约 `7.958333s`。
   - runId `791e9900cc354b9fb8a3c936afdfec66` 验证开场时长：`introHoldSeconds=3.04`，`tailSeconds=4.96`，组合视频 `1280x720`、`8.000000s`。
   - runId `da48605620cf4f4e90f0d69fea2c7206` 验证最终淡入过渡：`introHoldSeconds=3.04`、`transitionSeconds=0.35`、`tailSeconds=4.96`，组合视频 `1280x720`、`8.000000s`、192 帧。
   - `execution.costActions` 最终记录 `openai.gpt_image_2.image`、`vidu.viduq3_turbo.video`、`ffmpeg.compose`，能清楚解释成本构成和处理链路。

## 后续优化项

P0：

- 视频首帧策略已落地到 Vidu 固定画幅链路：
  - 用户需要固定 `16:9` / `9:16` / `1:1` 且选择 Vidu 时，先生成归一化首帧，再把首帧交给 Vidu。
  - Vidu 原始段不再作为唯一成功口径；后端默认组合完整商品开场 + 动态细节素材，最终推荐成片放在 `videoUrls[0]`。
  - 后续需要把同样策略抽象到正式 `promo_video` 能力契约，并决定 KIE / 其他供应商是否也统一使用首尾帧模式。
- 付费提交前增加 prompt 质量门禁：
  - 检查 prompt 内是否出现冲突商品名。
  - 检查 prompt 是否包含“填满画布、禁止黑边/边框”约束。
  - 检查产品名、材质、品类是否来自 `resolvedProductFacts`。
  - 检查场景 brief 是否只作为场景，不携带商品身份。
- 输出质量报告增加结构化字段：
  - `promptConflict=false`
  - `productConsistencyScore`
  - `aspectPolicyObserved`
  - `sourceImageType`
  - `recommendedUse`
- 视频耗时体验需要进入观测：
  - 本轮真实 Vidu 任务从提交到终态约 204-222 秒，脚本侧等待更长；页面必须按异步任务心智展示阶段和预计等待，不应让用户误以为按钮无响应。
  - 后续按供应商、模型、时长、输入图类型统计 P50/P90，作为是否默认 Vidu 或分流其他视频能力的依据。

P1：

- 对源图类型做提示：信息图、带大量文字/尺寸标注的图可用于事实识别，但不适合作为视频/营销图直接参考。
- 建立 golden case：至少覆盖托特包、服饰、杯子、家纺四类商品，每类保存原图、prompt、结果图、视频抽帧和人工评分。
- 把“营销图”和“商品证明图”拆成不同质量标准：前者允许场景化重绘，后者必须更严格保持产品结构和图案。
