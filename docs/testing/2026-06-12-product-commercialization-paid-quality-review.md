# 产品商业化收费能力质量复测（2026-06-12）

## 结论

本轮收费链路不是只验“能不能调用”，而是同时检查功能、结果质量、提示词污染和流程稳定性。

- GPT Image 2 配图：功能跑通，OSS 回填正常；社媒封面商业感可用，但不适合作为严格商品证明图。发现提示词曾混入旧商品身份，已修复并补回归测试。
- Vidu 视频：功能跑通，OSS 回填正常；画面稳定性尚可，但实际输出为竖版 `692x1328`，与用户选择/分镜文案中的 `16:9` 不一致。该问题不应靠提示词硬写比例解决，下一步应增加首帧归一化或把“跟随参考图比例”作为明确执行策略。

## 真实运行证据

| 能力 | runId | 状态 | OSS 结果 |
| --- | --- | --- | --- |
| GPT Image 2 配图 | `6afeae4282434df2b00eed723fa54021` | `succeeded` | `https://podiaidesign.oss-cn-hangzhou.aliyuncs.com/test/abilities/system/20260612/b02f8a99-1781240355.png` |
| Vidu 单段视频 | `888b187fed8e45709c7ab4ab54b9f0bd` | `succeeded` | `https://podiaidesign.oss-cn-hangzhou.aliyuncs.com/test/abilities/admin-vidu/20260612/b6f31a6a-1781234483.mp4` |
| GPT Image 2 配图修复后复测 | `cf049080925d42bea578037d276a90b3` | `succeeded` | `https://podiaidesign.oss-cn-hangzhou.aliyuncs.com/test/abilities/system/20260612/b047cb51-1781242404.png` |

本地证据：

- `output/quality/product-commercialization-20260612/manual-live-visual-6afe-20260612.json`
- `output/quality/product-commercialization-20260612/manual-live-video-888b-20260612.json`
- `output/quality/product-commercialization-20260612/assets/visual_source_default.jpg`
- `output/quality/product-commercialization-20260612/assets/visual_result_imageUrls.png`
- `output/quality/product-commercialization-20260612/assets/visual_result_after_letterbox_fix_cf04.png`
- `output/quality/product-commercialization-20260612/assets/video_result_videoUrls.mp4`
- `output/quality/product-commercialization-20260612/video-contact-sheet.jpg`
- `output/quality/product-commercialization-20260612/video-ffprobe.json`

视频媒体信息：

- codec：`h264`
- 分辨率：`692x1328`
- 时长：`8.041667s`
- 文件大小：`11560747 bytes`

## 质量评估

| 项目 | 功能 | 质量 | 一致性 | 结论 |
| --- | --- | --- | --- | --- |
| GPT Image 2 社媒封面 | 5/5 | 4/5 | 3.5/5 | 可作为营销封面样例；不能当作商品证明图。 |
| Vidu 单段视频 | 5/5 | 3.5/5 | 3.5/5 | 可作为短视频素材；比例策略和首帧控制需要整改。 |

配图质量观察：

- 优点：画面干净，场景明确，主体突出，无文字、水印、价格标签，适合社媒封面或广告封面。
- 风险：花纹和布局存在重绘，不适合详情页材质证明、版权严肃证明或严格商品一致性场景。
- 流程问题：结果 prompt 同时包含了正确的手提袋商品事实，以及旧模板中的 `Floral printed lightweight hooded jacket`。该问题已定位为样例字段与配图 brief 商品身份污染。

视频质量观察：

- 优点：主体稳定，运镜平滑，产品材质和图案有一定展示价值。
- 风险：输出比例为竖版，和脚本中的 `16:9` 不一致；局部花纹在后段镜头有重绘感。
- 流程问题：Vidu 单参考图生视频更接近“跟随首帧/参考图比例”，不能把 `aspectRatio` 当成已强执行的模型参数。

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

## 后续优化项

P0：

- 视频执行前增加首帧策略：
  - 用户需要固定 `16:9` / `9:16` / `1:1` 时，先生成或裁切归一化首帧，再把首帧交给 Vidu/KIE。
  - 如果不生成首帧，页面和 API 必须明确展示 `aspectPolicy=input_image_ratio`，不能让用户以为模型会强制输出目标比例。
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
