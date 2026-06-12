# 产品商业化收费能力质量复测（2026-06-12）

## 结论

本轮收费链路不是只验“能不能调用”，而是同时检查功能、结果质量、提示词污染和流程稳定性。

- GPT Image 2 配图：功能跑通，OSS 回填正常；社媒封面商业感可用，但不适合作为严格商品证明图。发现提示词曾混入旧商品身份，已修复并补回归测试。
- Vidu 视频：旧链路功能跑通但暴露比例缺陷，实际输出为竖版 `692x1328`；已改为“GPT Image 2 生成商业首帧 -> 后端确定性归一到目标画幅 -> Vidu 使用归一化首帧生成视频”。修复后真实 run 输出 `1280x720`、`8.041667s`，与 `16:9` 目标一致。

## 真实运行证据

| 能力 | runId | 状态 | OSS 结果 |
| --- | --- | --- | --- |
| GPT Image 2 配图 | `6afeae4282434df2b00eed723fa54021` | `succeeded` | `https://podiaidesign.oss-cn-hangzhou.aliyuncs.com/test/abilities/system/20260612/b02f8a99-1781240355.png` |
| Vidu 单段视频 | `888b187fed8e45709c7ab4ab54b9f0bd` | `succeeded` | `https://podiaidesign.oss-cn-hangzhou.aliyuncs.com/test/abilities/admin-vidu/20260612/b6f31a6a-1781234483.mp4` |
| GPT Image 2 配图修复后复测 | `cf049080925d42bea578037d276a90b3` | `succeeded` | `https://podiaidesign.oss-cn-hangzhou.aliyuncs.com/test/abilities/system/20260612/b047cb51-1781242404.png` |
| Vidu 首帧归一化修复后复测 | `22ee421e56704a6db851f4fb677360d2` | `succeeded` | `https://podiaidesign.oss-cn-hangzhou.aliyuncs.com/test/abilities/admin-vidu/20260612/a23688d2-1781245503.mp4` |

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
| Vidu 单段视频 | 5/5 | 3.8/5 | 4.5/5 | 修复后可作为横版短视频素材；比例策略已闭环，首帧商业构图仍需继续优化。 |

配图质量观察：

- 优点：画面干净，场景明确，主体突出，无文字、水印、价格标签，适合社媒封面或广告封面。
- 风险：花纹和布局存在重绘，不适合详情页材质证明、版权严肃证明或严格商品一致性场景。
- 流程问题：结果 prompt 同时包含了正确的手提袋商品事实，以及旧模板中的 `Floral printed lightweight hooded jacket`。该问题已定位为样例字段与配图 brief 商品身份污染。

视频质量观察：

- 优点：主体稳定，运镜平滑，产品材质和图案有一定展示价值。
- 已修复风险：Vidu 单参考图生视频会跟随参考图/首帧比例，旧链路不能把 `aspectRatio` 当成已强执行的模型参数。当前改为固定画幅先生成并归一化首帧，再把该首帧作为 Vidu 输入图。
- 当前质量观察：修复后视频为横版 `1280x720`，没有黑边或竖版漂移；运镜包含商品展示、近景和使用动作。仍有局部花纹重绘和手部动作引入，适合作为营销短视频素材，不应作为严格商品证明视频。
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

## 后续优化项

P0：

- 视频首帧策略已落地到 Vidu 固定画幅链路：
  - 用户需要固定 `16:9` / `9:16` / `1:1` 且选择 Vidu 时，先生成归一化首帧，再把首帧交给 Vidu。
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

P1：

- 对源图类型做提示：信息图、带大量文字/尺寸标注的图可用于事实识别，但不适合作为视频/营销图直接参考。
- 建立 golden case：至少覆盖托特包、服饰、杯子、家纺四类商品，每类保存原图、prompt、结果图、视频抽帧和人工评分。
- 把“营销图”和“商品证明图”拆成不同质量标准：前者允许场景化重绘，后者必须更严格保持产品结构和图案。
