# 高频能力展示层补齐清单

## 1. 目标

先把客户端主路径与 Coze 高频能力补齐 `presentation`，不改接口、不改参数，只补：

- 对外名称
- 一句话价值
- 表单引导语
- 结果预期
- 高级参数标记
- 表面可见性

## 2. 第一批优先能力

### A. 新款设计

#### `doubao_seedream_4_5`

- 当前名：火山 · Doubao Seedream 4.5
- 对外名：以文生款
- 一句话价值：从一句设计意图快速生成可讨论的新款方向。
- 表单引导语：先描述款式、面料、风格和场景，不必写成技术提示词。
- 结果预期：产出 1 张新款方向图，可继续改款、提取图案或转入商拍。
- 表面：`client_enabled`、`admin_and_eval`

#### `nano_banana_pro_image_to_image`

- 当前名：KIE · Nano Banana Pro 图生图
- 对外名：以款生款
- 一句话价值：围绕参考款快速做改款和方向延展。
- 表单引导语：说明哪些部分要保留，哪些部分想变化。
- 结果预期：产出同风格变体，可继续进入套图或图案整理。
- 表面：`client_enabled`、`coze_enabled`

#### `duotu_ronghe`

- 当前名：ComfyUI · 多图融合
- 对外名：融合创款
- 一句话价值：把多张参考图的轮廓、花型、配色融合成一个新方向。
- 表单引导语：分别准备结构、风格、花型或配色参考图，再说明融合重点。
- 结果预期：产出 1 张融合方向图，可继续改款或做图案整理。
- 表面：`client_enabled`、`coze_enabled`

### B. 图案设计

#### `yinhua_tiqu`

- 当前名：ComfyUI · 印花提取
- 对外名：图案提取
- 一句话价值：把实拍图中的花型或纹样整理成可复用的干净设计稿。
- 表单引导语：上传原图后，只补充是否需要更干净、更完整或更适合连续化。
- 结果预期：产出干净花型稿，可继续做四方连续或清晰度增强。
- 表面：`client_enabled`、`coze_enabled`

#### `sifang_lianxu`

- 当前名：ComfyUI · 四方连续
- 对外名：四方连续
- 一句话价值：让图案变成可连续铺陈的面料纹理。
- 表单引导语：上传图案后，说明边缘是否要更自然、主花是否要保留。
- 结果预期：产出连续纹理，可继续做配色、工艺表达或营销展示。
- 表面：`client_enabled`、`admin_and_eval`

### C. 视觉商拍

#### `nano_banana_2_image_to_image`

- 当前名：KIE · Nano Banana 2 图生图
- 对外动作：
  - 裂变套图
  - 服装上身
  - 换背景
  - 换姿势
  - 图案上身
  - 面料上身
- 一句话价值：围绕已有图快速延展成更多展示场景。
- 表单引导语：不要解释模型，只提示“想保留什么、想变化什么、最终想用在哪”。
- 结果预期：按具体动作生成营销图、展示图或上身图。
- 表面：`client_enabled`、`coze_enabled`

#### `doubao_seedance_1_5_pro`

- 当前名：火山 · Doubao Seedance 1.5 Pro
- 对外名：图生视频
- 一句话价值：把已验证的静态图延展成动销短视频。
- 表单引导语：描述镜头运动、人物动作或画面节奏，不必关心模型参数。
- 结果预期：产出短视频，可回到素材中心继续沉淀和复用。
- 表面：`client_enabled`、`admin_and_eval`

#### `quality_upgrade`

- 当前名：百度 · 无损放大
- 对外动作：
  - AI超清
  - 细节图
- 一句话价值：把现有结果收口成更清晰、更适合交付或详情页展示的终稿。
- 表单引导语：只问用户更偏向提升整体清晰度，还是强调局部细节。
- 结果预期：产出高清图，可继续用于详情页、终稿或下载交付。
- 表面：`client_enabled`、`coze_enabled`

### D. 终稿处理

#### `huawen_kuotu`

- 当前名：ComfyUI · 花纹扩图
- 对外名：AI扩图
- 一句话价值：在不破坏原有风格的前提下延展画布和边缘。
- 表单引导语：说明向哪个方向扩、希望保持什么风格。
- 结果预期：产出更完整画面，可继续做 AI 超清或营销套图。
- 表面：`client_enabled`、`admin_and_eval`

#### `upscale_resize`

- 当前名：PODI · 高质量缩放
- 对外名：高质量缩放
- 一句话价值：快速把图调整到适合交付的像素尺寸。
- 表单引导语：只问目标长边和输出格式。
- 结果预期：产出统一尺寸结果，适合后续下载交付。
- 表面：`client_enabled`、`admin_and_eval`

#### `set_dpi`

- 当前名：PODI · 设置 DPI
- 对外名：DPI处理
- 一句话价值：把图片改成适合印刷或排版的输出参数。
- 表单引导语：只问目标 DPI，不讨论内部元数据。
- 结果预期：产出适合印刷/排版的终稿文件。
- 表面：`client_enabled`、`admin_and_eval`

## 3. 第二批能力

以下能力暂不建议直接作为主路径工具名，但应补齐展示层，供管理端、评测端和 Coze 使用：

- `yinhua_tiqu_lora_8step`
- `beijing_koutu`
- `toubu_kouxiang`
- `flux2_9b_liebian_sifang`
- `qwen2512_print_shape_text_enhance`
- `e7_flux2_liebian`
- `jisu_chuli`
- `zhongsu_tisheng`

## 4. 每个能力至少要补的 presentation 字段

建议最小集合：

- `name`
- `summary`
- `formIntro`
- `expectedOutput`
- `surfaces`
- `fields.<name>.label`
- `fields.<name>.description`
- `fields.<name>.placeholder`
- `fields.<name>.advanced`

## 5. 落地顺序

1. 先补第一批高频能力的 `presentation`
2. 再让客户端优先读取这些字段
3. 再让 Coze OpenAPI 摘要与参数提示统一走这套配置
4. 最后再清理前端里重复写死的字段标签与说明

## 6. 本轮不做的事

这份清单本轮不涉及：

- 改接口路径
- 改请求参数
- 改工作流调度
- 改真实任务链路
- 改数据库结构

它只负责把“技术能力”翻译成“用户可理解的产品动作”。
