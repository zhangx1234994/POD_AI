# ComfyUI Workflow Handbook

本目录记录当前托管在仓库内的 ComfyUI 工作流，便于排查与版本控制。每个条目包含：

- workflow_key / ability key / action
- 默认执行节点（服务器/端口）
- 关键节点编号与功能说明
- 默认参数、LoRA 版本与超时配置
- 运维/调试备注

> 修改 workflow 或能力时请同步更新本文档，并在 PR 描述中说明节点调整、LoRA 更换或默认参数变化，确保与 backend/app/workflows/comfyui/*.json 及 backend/app/constants/abilities.py 一致。

## 当前有效工作流总表（优先看）

| workflow_key | ability / action | 推荐外部入参 | 最终输出节点 | 当前状态 |
| --- | --- | --- | --- | --- |
| `sifang_lianxu` | `comfyui.sifang_lianxu` / `seamless` | `prompt`、`patternType`、`resolution`、`width`、`height`、`url` | workflow 内置输出链路 | 线上在用；233/158 双机 |
| `huawen_kuotu` | `comfyui.huawen_kuotu` / `pattern_expand` | `url`、`prompt`、`negative_prompt`、扩展像素参数 | workflow 内置输出链路 | 线上在用；233/158 双机 |
| `duotu_ronghe` | `comfyui.duotu_ronghe` / `multi_image_fusion` | `url`、`image_url_2`、`image_url_3`、`width`、`height`、`prompt`、`negative_prompt`、`seed` | `60` | 线上在用 |
| `beijing_koutu` | `comfyui.beijing_koutu` / `background_remove` | `url` | `4` | 线上在用 |
| `toubu_kouxiang` | `comfyui.toubu_kouxiang` / `head_extract` | `url` | `140` | 线上在用 |
| `flux2_klein_9b_outpaint` | `comfyui.flux2_klein_9b_outpaint` / `outpaint` | `url`、`expand_left`、`expand_right`、`expand_top`、`expand_bottom` | `9` | 新增工具箱 |
| `flux_strong_hq_softstyle_fission` | `comfyui.flux_strong_hq_softstyle_fission` / `image_fission` | `url`、`prompt`、`image_desc`、`bili`、`width`、`height` | `31` | 高质量图裂变，158 / 233 均可按队列路由；颜色锁定 v2 复用该 workflow |
| `flux2_9b_liebian_sifang` | `comfyui.flux2_9b_liebian_sifang` / `image_fission` | `url`、`prompt` | `111` | 线上在用；233/158 双机 |
| `qwen2512_print_shape_text_enhance` | `comfyui.qwen2512_print_shape_text_enhance` / `text_enhance` | `url`、`prompt`、`bili` | `29` | 线上在用；上游 prompt 质量待优化 |
| `qwen2512_text2img_text_allowed` | `comfyui.qwen2512_text2img_text_allowed` / `text_to_image` | 对外业务只暴露 `editable_prompt`、`editable_negative_prompt`、`width`、`height`；`steps/cfg/seed` 由中台控制 | `21` | 2026-05-19 新增，文字强化裂变（文生图）两步式生图 |
| `yinhua_tiqu` | `comfyui.yinhua_tiqu` / `pattern_extract` | `url`、`prompt`、`negative_prompt`、`output_width`、`output_height`、`lora_name` | `421` | 线上在用 |

## 当前已知说明

- 业务链路统一先走 OSS URL，再交给 ComfyUI；不要把外部临时链接当正式输入口径。
- 233 白名单后同构恢复任务记录见 `docs/comfyui/233-recovery-2026-05-16.md`；该任务的原则是补齐服务器节点和模型，不为 233 单点问题长期增加平台特殊分支。
- `sifang_lianxu`、`huawen_kuotu`、`flux2_9b_liebian_sifang` 依赖 `String` 自定义节点。2026-05-16 233 已恢复 `String` 并强制跑通三条旧工作流，当前恢复 233/158 双机队列路由。
- `qwen2512_print_shape_text_enhance` 当前执行链路已验证可跑通，主要待优化点是上游 Coze/VL 提示词质量，不是中台或评测执行接口。
- 多图融合评测端在 `width/height` 留空时会先读取主图尺寸再提交；直接绕过前端调用工具箱时，不传尺寸仍沿用 workflow 默认 `1024x1024`。
- `背景抠图` 存在过程图，正式回填只认最终输出节点 `4`；`头部抠像` 正式回填只认 `140`；`FLUX2裂变+四方` 正式回填只认 `111`；`裂变文字强化` 正式回填只认 `29`；`文字强化文生图` 正式回填只认 `21`。
- `FLUX2-Klein 扩图` 的源图节点是 `76 · LoadImage.image`，后端会先把 OSS URL 上传到 ComfyUI input 目录，再回填文件名；不要直接把外部 URL 填进 workflow JSON。
- `多元素花纹裂变` 的源图节点是 `10 · LoadImage.image`，后端会先把 OSS URL 上传到 ComfyUI input 目录，再回填文件名；`bili` 为重绘幅度，映射到节点 `24.denoise`，默认 `90 ≈ 0.765`。2026-05-14 `comfyui-vl-control-v2` 按对象级裂变修补包升级：默认 `bili=80%`，后端用 `pattern_risk_type + bili` 路由实际 `denoise`；`reference_lock` 映射 IPAdapter 权重，建议 0.34-0.50；`color_lock` 映射 ColorMatch 强度，建议 0.75-1.00。建议区间只做文案提示，不做接口硬拦截。2026-05-04 已确认 233 机器补齐 CLIPVision/IPAdapter 后可完整出图并完成 OSS 回填，当前允许 158 / 233 双节点按队列路由。
- 233 承接 `flux_strong_hq_softstyle_fission` 依赖：
  - `ComfyUI/models/clip_vision/CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors`
  - `ComfyUI/models/ipadapter/ip-adapter-plus_sdxl_vit-h.safetensors`
  - 重启 ComfyUI 后需确认 `/object_info` 中 `CLIPVisionLoader.clip_name` 和 `IPAdapterModelLoader.ipadapter_file` 均能列出对应文件。
- 233 承接 `flux2_9b_liebian_sifang` / `toubu_kouxiang` / `qwen2512_print_shape_text_enhance` 的历史补齐记录（2026-05-04，仅作历史参考，2026-05-15 复核时 `String` 已缺失；2026-05-16 在白名单保护下已恢复必要节点，详见 `docs/comfyui/233-recovery-2026-05-16.md`）：
  - `custom_nodes/comfyui_bmad_nodes` 提供 `String` 等 Bmad 节点。
  - `custom_nodes/ComfyUI-LogicUtils` 提供 `ComposeRGBAImageFromMask`。
  - `models/controlnet/qwen-image/instantx/Qwen-Image-InstantX-ControlNet-Inpainting.safetensors` 为 Qwen 文字增强 ControlNet。
  - Linux 233 还需保留同 inode 硬链接 `models/controlnet/qwen-image\instantx\Qwen-Image-InstantX-ControlNet-Inpainting.safetensors`，兼容现有 workflow JSON 的反斜杠路径。
  - `models/diffusion_models/qwen-image-2512-fp8.safetensors` 为 Qwen 文字增强 UNet。
  - `custom_nodes/ComfyUI-QualityOfLifeSuit_Omar92` 提供花纹扩图使用的 `Text _O`。
  - `custom_nodes/masquerade-nodes-comfyui` 提供花纹扩图使用的 `Get Image Size`。
  - 2026-05-16 最新 `/object_info` 已确认 `String`、`ComposeRGBAImageFromMask`、`Text _O`、`Get Image Size` 均可见；114 release smoke 显示 `comfyui_workflow_compatibility total=16 ok=16 warnings=0 failed=0 servers=2`。
  - 2026-05-16 已强制 233 跑通 `toubu_kouxiang`，输出 OSS：`https://podiaidesign.oss-cn-hangzhou.aliyuncs.com/test/abilities/admin-comfyui/20260516/06413e32-1778887853.png`。
  - 2026-05-16 恢复后主线裂变已有多条自然流量命中 233 并成功回填，其中 `flux_strong_hq_softstyle_fission_colorlock_v2` ability log `41244` 成功。
  - 2026-05-16 已强制 233 跑通 `flux2_9b_liebian_sifang`、`huawen_kuotu`、`sifang_lianxu`，代码已恢复这些工作流的 233/158 双机队列路由。
- `FLUX2裂变+四方` 的节点 `104` 为 workflow 内部固定输入，不作为外部参数暴露，也不应在工具箱适配层覆盖。

## 管理端入口

- 管理端「ComfyUI 管理」统一收口：`素材库` 维护 LoRA/基座模型，`资源清单` 维护模型/插件下载信息，`服务器` 维护多台 ComfyUI 机器对比，`模板管理` 维护 workflow JSON 与节点映射。
- 对外原则：ComfyUI workflow 属于**原子能力**，能力配置与模板变更需同步记录本文档。
  - 服务器管理与 Agent 协议详见 `docs/comfyui/agent-management.md`。
  - 模板管理支持导入 ComfyUI UI JSON（含 nodes/links）或 Prompt Graph；UI JSON 保存时会自动转换为 Prompt Graph。
  - 资源清单字段约定：`download_url` 填国内镜像地址，`source_url` 填官方/原始来源。
  - 能力版本字段：`abilities.version` 默认 `v1`，新版本建议在 `capability_key` 上显式区分（例如 `_v2`），便于旧版本共存。
  - 模板管理支持“复制为新版本”，会自动生成新的 workflow_key（原 key + 版本号），保存后即可与旧版本并行。

## 服务器对齐与资源清单

- **资源清单**：模型/插件/版本元信息存于数据库（`comfyui_model_catalog` / `comfyui_plugin_catalog` / `comfyui_version_catalog`），用于补齐缺失项的下载/来源信息。
- **服务器对齐**：管理端“服务器”页会拉取 `/api/admin/comfyui/models?includeNodes=true` 与 `/system_stats` 获取模型与节点列表，并以“基准服务器”做差异对比。
- **对齐快照**：差异结果通过 `POST /api/admin/comfyui/server-diff` 入库，后台会标记基准服务器 `sync_role=master`，并在缺失为 0 时更新目标节点 `last_sync_at`。

> 说明：本仓库提供差异检测与记录能力，模型/插件的实际安装需由 ComfyUI 服务器侧执行（外部工具/脚本）。

## 并发与超时规则（必须知晓）

- **队列满则拒绝**：同一 ComfyUI 节点的 `queued + running` 达到上限（默认 10）会直接拒绝新任务。  
- **节点维护要自动绕开**：路由会先限定在“兼容候选节点”内，再检查队列和健康状态。某台服务器维护、重启或网络不可达时，会跳过该节点；如果提交阶段才发现连接失败，会把失败节点加入本次任务排除列表并重新选择一次。
- **不兼容不兜底**：如果一个 workflow 只兼容某一台机器，而这台机器不可用，系统会返回 `COMFYUI_EXECUTOR_UNAVAILABLE / Q1002`，不会为了可用性把任务发到缺模型、缺插件或缺自定义节点的机器。
- **队列利用率要可见**：`/api/admin/comfyui/queue-summary` 会同时返回目标容量、已用、空闲槽位、使用率和诊断文案。若业务仍在排队但 ComfyUI 总使用率偏低，优先检查中台下发节奏、路由筛选、上游限流和任务回填阻塞，而不是先加机器。
- **下发节奏要可见**：同一接口会把中台任务表里的 `queued/running` 按执行节点汇总到 ComfyUI 队列旁边。如果中台有待下发任务，但 ComfyUI 队列还有空位或为空，说明问题优先在中台 worker、路由筛选或任务卡死，而不是 GPU 机器数量。
- **真实命中要可追溯**：同一接口会返回近 24 小时真实任务命中证据，包括总命中数、已覆盖服务器数、未命中服务器清单以及每台机器的成功/失败/运行中数量。没有真实任务命中时，不能把“双机路由”判定为已验收。
- **依赖检查只阻断真实资源缺失**：工作流兼容性检查只把模型、LoRA、UNet、CLIP、VAE、IPAdapter、ControlNet、SAM、放大模型等资源字段作为缺失项；运行时输入图、方法选择和占位参数不应被误判为缺模型。
- **ComfyUI 不做硬超时失败**：排队等待属于正常状态，轮询超时只代表“同步等待上限”，会返回 `running` 继续由后续轮询收敛。  
- **第三方能力仍有硬超时**：KIE/Volcengine 等不可控能力保持硬超时策略。  

更多细节请参见：
- `docs/comfyui-routing-business.md`
- `docs/comfyui-routing-technical.md`

## 待办 / 风险记录

- LoRA 可能适用于多个基座模型：已新增 `base_models` 多选字段，旧 `base_model` 仅用于兼容。
- “服务器”页已支持基准服务器（baseline）对比：缺失模型/插件时提示差异列表（插件以 `/object_info` 返回的节点名对比）。
- 2026-05-04：已补 active 工作流兼容性检查接口和管理端展示，能发现缺节点、缺模型、路由绑定不一致；一键修复仍留在后续轻 Agent/集成包阶段。
- TODO：提供一键同步/修复能力（模型/插件/配置），并补充更细粒度的插件版本校验规则。
- TODO：持续补齐资源清单中的下载地址/来源/版本信息，便于对齐与运维追踪。

## 四方连续 · ComfyUI (workflow_key: sifang_lianxu)

| 项目 | 说明 |
| --- | --- |
| 能力 ID | comfyui.sifang_lianxu |
| Action | seamless |
| 执行节点 | executor_comfyui_seamless_117 / executor_comfyui_pattern_extract_158 |
| Workflow 文件 | backend/app/workflows/comfyui/sifang_lianxu.json |
| 超时设置 | 480 秒 (defaults.timeout) |
| 核心模型 | UNETLoader: 四方连续.safetensors、DualCLIPLoader: t5xxl_fp8_e4m3fn_scaled.safetensors + clip_l.safetensors、VAE: ae.safetensors |

**关键节点**

| 节点 | 描述 |
| --- | --- |
| 42 · StringConcatenate.string_a | 主提示词（能力表单 prompt）。 |
| 114 · easy string.value | 输入图 URL 字符串（同时供 96 与 113 使用）。 |
| 96 · LoadImagesFromURL.url | 参考图 URL（上传后端会自动回填）。 |
| 113 · DoubaoAPINode.image_url | 结构描述节点，使用同一张输入图生成辅助提示词。 |
| 97 · easy ifElse.boolean | 图案类型开关：true=四方连续、false=两方连续。 |
| 102 · ImageResize+ | 输出尺寸；resolution 选择器控制预设比例，width/height 可手动覆盖。 |
| 10 / 11 / 91 | ImageShift + MaskMath 组合，用于生成 seamless 条件区域。 |
| 72 / 73 / 74 / 75 | 输入图尺寸归一化（8 像素对齐）。 |

**默认参数**

- patternType: seamless
- resolution: 1:1（选项：1:2、2:1、original、auto）
- timeout: 480
- width/height: 为空时按 resolution 自动填入 2048×2048

**调试备注**

- 若管理端回显“中心留白”，优先检查节点 114/96 是否收到同一张可访问 URL，并确认节点 64 仍保持遮罩输入（104）。
- 节点 104 为固定遮罩输入，线上执行保持原样，不做覆盖或删除。
- 旧版 node 106（本地上传分支）已废弃，线上仅走 URL 分支（114 -> 96；102 读取 96）。
- 2026-05-16 已在 233 白名单保护下恢复 `String` / `StringConcatenate`，并强制 233 跑通，可恢复双机路由。

> 说明：执行节点与 URL 为当前快照，主服务器可能调整，请以管理端“执行节点”配置为准。

## 花纹扩图 · ComfyUI (workflow_key: huawen_kuotu)

| 项目 | 说明 |
| --- | --- |
| 能力 ID | comfyui.huawen_kuotu |
| Action | pattern_expand |
| 执行节点 | executor_comfyui_seamless_117 / executor_comfyui_pattern_extract_158 |
| Workflow 文件 | backend/app/workflows/comfyui/huawen_kuotu.json |
| 超时设置 | 420 秒（根据批次数/扩展像素自动放大） |
| 核心模型 | UNET: qwen_image_edit_2511_fp8mixed、CLIP: qwen_2.5_vl_7b_fp8_scaled、VAE: qwen_image_vae、ControlNet: Qwen InstantX Inpainting、LoRA: Qwen-Image-Edit Lightning |

**关键节点**

| 节点 | 描述 |
| --- | --- |
| 205 · LoadImagesFromURL.url | 输入原始图案/布料照片。 |
| 53 · ImageScaleByAspectRatio | 对输入图做长边缩放，默认 720 px。 |
| 185 · ImagePadForOutpaint | 控制上下左右扩展像素与羽化。 |
| 73 · GrowMaskWithBlur | 对扩展 mask 做膨胀/模糊，避免硬边。 |
| 74 / 72 | 正向/反向提示词，保证扩展区域与原图风格一致。 |
| 45 · LoRA 加载器 | 默认使用 Qwen Lightning，可切换其他印花 LoRA。 |
| 52 · ControlNetInpaintingAliMamaApply | 结合 ControlNet + mask 做局部重绘。 |
| 61 · ImpactInt | 控制输出长边，传递给节点 53/199 的 scale。 |
| 199 · ImageScale | 最终输出尺寸；width/height 由节点 193/196（输入图尺寸 + 扩展像素）提供。 |

**默认参数**

- prompt：描述保持风格/延续背景的扩图要求。
- negative_prompt：抑制文字、水印、低质噪点。
- expand_left/right/top/bottom：200/200/0/0。
- mask_expand：20，feathering：24。
- output_long_side：720。

**调试备注**

- 扩展像素越大、批次数越多，任务耗时越长；后端会自动按批次数放宽 timeout，但仍建议分批提交。
- 2026-05-16 已在 233 白名单保护下恢复依赖节点，并强制 233 跑通，可恢复双机路由。
- `output_long_side` 控制最终缩放尺寸（长边），若素材要求高分，请在能力表单中调高。
- ControlNet/LoRA 组合对图案延展极为敏感，如需替换模型必须同步更新 workflow 与 `metadata.lora_presets`。

## 多图融合 · ComfyUI (workflow_key: duotu_ronghe)

| 项目 | 说明 |
| --- | --- |
| 能力 ID | comfyui.duotu_ronghe |
| Action | multi_image_fusion |
| 执行节点 | executor_comfyui_pattern_extract_158（默认）/ executor_comfyui_seamless_117（可选） |
| Workflow 文件 | backend/app/workflows/comfyui/duotu_ronghe.json |
| 超时设置 | 360 秒 |
| 核心模型 | UNET: qwen_image_edit_2511_fp8mixed、CLIP: qwen_2.5_vl_7b_fp8_scaled、VAE: qwen_image_vae（无外部 LoRA 入参） |

**关键节点**

| 节点 | 描述 |
| --- | --- |
| 78 · LoadImage.image | 主图文件名（经后端上传到 ComfyUI input 后送入 390） |
| 106 · LoadImage.image | 辅图 1（image2，可选） |
| 108 · LoadImage.image | 辅图 2（image3，可选） |
| 111 / 110 · TextEncodeQwenImageEditPlus | 正/反提示词 |
| 112 · EmptySD3LatentImage | 输出宽度 / 高度 |
| 151 · CR Seed.seed | 随机种子 |
| 60 · SaveImage | 输出节点（工具箱默认只取 1 张） |

**默认参数**

- 主图：`image_url`（必填，对应节点 78）
- 辅图 1：`image_url_2`（可选，对应节点 106）
- 辅图 2：`image_url_3`（可选，对应节点 108）
- width / height：可覆盖节点 112 的输出宽高；不传则沿用 workflow 默认 `1024x1024`
- prompt / negative_prompt：可覆盖节点 111 / 110 默认文案
- seed：可选，不填由后端自动生成随机种子并写入节点 151
- 无外部 `lora` 入参

**调试备注**

- 工作流已切换到本地 `LoadImage` 节点；后端会先把主图/辅图上传到目标 ComfyUI 的 input 目录，再写入节点 78 / 106 / 108。
- 若辅图 1 / 辅图 2 未传，后端会在提交前移除 `111/110` 节点里的 `image2/image3` 引用，避免错误读取默认占位图。
- 当前 output node 改为 `60 · SaveImage`，工具箱/能力接口按 `output_node_ids=[60]` 抽取回填。

## 背景抠图 · ComfyUI (workflow_key: beijing_koutu)

| 项目 | 说明 |
| --- | --- |
| 能力 ID | comfyui.beijing_koutu |
| Action | background_remove |
| 执行节点 | executor_comfyui_seamless_117 / executor_comfyui_pattern_extract_158 |
| Workflow 文件 | backend/app/workflows/comfyui/beijing_koutu.json |
| 超时设置 | 240 秒 |

**关键节点**

| 节点 | 描述 |
| --- | --- |
| 5 · LoadImagesFromURL.url | 输入图片 URL |
| 2 · easy imageRemBg | 背景移除处理节点（中间过程图） |
| 4 · SaveImage | 最终输出节点，仅回填该节点结果 |

**默认参数**

- `url`：必填，业务统一使用 OSS URL

**调试备注**

- 节点 `2` 会产生中间过程图，工具箱/能力接口仅认 `4 · SaveImage`。
- 业务侧统一先把图片放到 OSS，再交给 workflow，避免外链兼容性差异。

## 头部抠像 · ComfyUI (workflow_key: toubu_kouxiang)

| 项目 | 说明 |
| --- | --- |
| 能力 ID | comfyui.toubu_kouxiang |
| Action | head_extract |
| 执行节点 | executor_comfyui_seamless_117 / executor_comfyui_pattern_extract_158 |
| Workflow 文件 | backend/app/workflows/comfyui/toubu_kouxiang.json |
| 超时设置 | 300 秒 |

**关键节点**

| 节点 | 描述 |
| --- | --- |
| 141 · LoadImagesFromURL.url | 输入图片 URL |
| 136 · DownloadAndLoadFlorence2Model | 固定加载 Florence-2-base |
| 134 · Florence2Run | 固定文案 `complete head and hair`，不作为外部参数暴露 |
| 139 · SegmentAnythingUltra V2 | 固定文案 `complete head and face` |
| 140 · SaveImage | 最终输出节点，仅回填该节点结果 |

**默认参数**

- `url`：必填，业务统一使用 OSS URL

**调试备注**

- 节点 `134/139` 的提示词和模型参数保持 workflow 内部默认值，不在工具箱暴露。
- 最终输出固定取 `140 · SaveImage`。

## FLUX2裂变+四方 · ComfyUI (workflow_key: flux2_9b_liebian_sifang)

| 项目 | 说明 |
| --- | --- |
| 能力 ID | comfyui.flux2_9b_liebian_sifang |
| Action | image_fission |
| 执行节点 | executor_comfyui_seamless_117 / executor_comfyui_pattern_extract_158 |
| Workflow 文件 | backend/app/workflows/comfyui/flux2_9b_liebian_sifang.json |
| 超时设置 | 420 秒 |

**关键节点**

| 节点 | 描述 |
| --- | --- |
| 141 · LoadImagesFromURL.url | 输入图片 URL |
| 132 · String.inStr | 主提示词，作为唯一外露文本参数 |
| 104 · easy loadImageBase64 | workflow 固定内部输入，保持原始默认值，不在工具箱侧覆盖 |
| 111 · SaveImage | 最终输出节点，仅回填该节点结果 |

**默认参数**

- `url`：必填
- `prompt`：必填

**调试备注**

- 2026-05-16：233 已恢复 `String` 自定义节点，并强制 233 跑通该 workflow，可恢复双机路由。
- 工具箱只覆写 `141.url` 和 `132.inStr`。
- 节点 `104`、`97`、`99`、`100`、`102`、`121`、`122`、`130`、`137` 等内部默认参数保持不变。
- 最终输出固定取 `111 · SaveImage`。

## 裂变文字强化 · ComfyUI (workflow_key: qwen2512_print_shape_text_enhance)

| 项目 | 说明 |
| --- | --- |
| 能力 ID | comfyui.qwen2512_print_shape_text_enhance |
| Action | text_enhance |
| 执行节点 | executor_comfyui_pattern_extract_158 / executor_comfyui_seamless_117 |
| Workflow 文件 | backend/app/workflows/comfyui/qwen2512_print_shape_text_enhance.json |
| 超时设置 | 420 秒 |

**关键节点**

| 节点 | 描述 |
| --- | --- |
| 141 · LoadImagesFromURL.url | 输入图片 URL |
| 13 · CR Text Concatenate.text1 | 外部 `prompt` 写入节点 |
| 27 · 基础采样节点 | `bili` / `similarity` 作为重绘幅度映射到 `denoise` |
| 29 · SaveImage | 最终输出节点，仅回填该节点结果 |

**默认参数**

- `url`：必填
- `prompt`：必填，来自上游 Coze/VL 生成链路
- `bili`：业务侧重绘幅度口径，当前映射 `0→0.45`、`50→0.625`、`100→0.80`，数值越大变化越大
- `steps` / `cfg` / `seed`：暂由中台默认值兜底

**调试备注**

- 该 workflow 的执行链路已验证正常；当前主要问题不是工具箱契约，而是上游生成的最终 `prompt` 质量与稳定性。
- 2026-04-17：修正节点 `16` 的负向提示词，移除了会直接压制文字生成的 `text`，改为 `illegible lettering / broken glyphs / duplicated characters / unwanted watermark` 这类坏字形约束。
- 业务侧若同时存在旧字段 `similarity`，后端仍兼容，但正式推荐口径统一使用 `bili`。

## 文字强化文生图 · ComfyUI (workflow_key: qwen2512_text2img_text_allowed)

| 项目 | 说明 |
| --- | --- |
| 能力 ID | comfyui.qwen2512_text2img_text_allowed |
| Action | text_to_image |
| 执行节点 | executor_comfyui_seamless_117 / executor_comfyui_pattern_extract_158 |
| Workflow 文件 | backend/app/workflows/comfyui/qwen2512_text2img_text_allowed.json |
| 交付包 | `19_2026-05-19_text2img_user_editable_vl_pack_v2.zip` |
| 超时设置 | 420 秒 |

**关键节点**

| 节点 | 描述 |
| --- | --- |
| 10 · CLIPTextEncode.text | 正向提示词。业务接口第二步的 `editable_prompt` 会原样写入。 |
| 11 · CLIPTextEncode.text | 反向提示词。默认负向词不包含 `text/letters/numbers/typography`，避免压制文字。 |
| 12 · EmptySD3LatentImage | 输出 `width` / `height` / `batch_size`；业务层固定 `batch_size=1`。 |
| 19 · KSampler | `seed` / `steps` / `cfg`，`denoise` 固定为 1.0。 |
| 21 · SaveImage | 最终输出节点，仅回填该节点结果。 |

**默认参数**

- `editable_prompt`：必填，来自第一步 VL 草稿并由用户确认或修改。
- `editable_negative_prompt`：可选；为空时使用系统默认负向词。
- `width` / `height`：不填时中台按原图尺寸补齐；手动填写时覆盖，并按 8 像素对齐。
- `steps`：默认 8；`cfg`：默认 2；`seed`：不填随机。

**调试备注**

- 该业务不是图生图。原图只用于第一步 VL 识别和测评对比，第二步 ComfyUI 主输入是 `editable_prompt`。
- 第二步不允许再次自动调用 VL；用户改过的提示词必须直接送入节点 10。
- 单个业务 run 固定 1 张图，批量测评由测评端创建多个独立 runId。
- 文字密集图的逐字准确性是当前工作流质量风险，不属于中台链路错误；后续如需精确保留中文，应追加 OCR/版式叠字或质量门禁方案。

## 印花提取 · ComfyUI (workflow_key: yinhua_tiqu)

| 项目 | 说明 |
| --- | --- |
| 能力 ID | comfyui.yinhua_tiqu |
| Action | pattern_extract |
| 执行节点 | executor_comfyui_pattern_extract_158 → http://117.50.80.158:8079（示例，实际以管理端配置为准） |
| Workflow 文件 | backend/app/workflows/comfyui/yinhua_tiqu.json |
| 超时设置 | 420 秒 (defaults.timeout) |
| 核心模型 | UNETLoader: qwen_image_edit_2509_fp8_e4m3fn.safetensors、CLIP: qwen_2.5_vl_7b_fp8_scaled.safetensors、VAE: qwen_image_vae.safetensors、LoRA(节点 390) 默认 `杯子1124.safetensors`（支持 T-Shirt / 毛毯 / 杯子 / 通用 QwenImageEdit2511 5000~8000） |

**关键节点**

| 节点 | 描述 |
| --- | --- |
| 393 · LoadImagesFromURL.url | 实物照片 URL（管理端上传→OSS 时自动填写）。 |
| 111 · TextEncodeQwenImageEditPlus.prompt | 默认正向提示词（通用高保真模板），管理端 schema 的 `prompt` 字段会写回该节点。 |
| 110 · TextEncodeQwenImageEditPlus.prompt | 反向提示词（negative_prompt）。 |
| 390 · LoraLoaderModelOnly | LoRA 文件名（lora_name），更换版本需在本文档记录。 |
| 400 · LatentUpscale | 最终输出尺寸（output_width/output_height）。 |
| 427/428/429/430 | 四组 TextEncodeQwenImageEditPlus，用于 T 恤 / 杯子 / 毛毯 / 通用 prompt 模板，供管理端自动回填或调试。 |
| 421 · SaveImageWithDPI | 保存 PNG，DPI=150，文件前缀 DPI_Image，最终由后端上传 OSS（输入来自节点 8 解码结果）。 |

**默认参数**

- prompt: 新的全品类高保真模板（`PATTERN_EXTRACT_POSITIVE_DEFAULT`）。
- negative_prompt: 长串低质量/错误特征黑名单（保持与 workflow JSON 同步）。
- output_width/output_height: 1800
- lora_name: 杯子1124.safetensors

**调试备注**

- 该版本移除了遮罩/预览分支，尺寸控制统一在节点 400。若需裁切或添加遮罩，请在 ComfyUI 端另行分支并记录新的 workflow 版本。
- 四套正向模板（节点 111/427/428/429/430）分别服务于通用、T 恤、杯子、毛毯与全局 fallback，默认由能力 schema / metadata 自动驱动，无需在 JSON 内手动改 prompt。
- 替换或新增 LoRA 时请同步更新 workflow JSON、`backend/app/constants/abilities.py` 中的 `PATTERN_EXTRACT_LORA_PRESETS`、`LORA_CATALOG.md` 以及本文档记录。
- 2026-03-04：新增 `印花提取-通用_QwenImageEdit2511_{5000,5500,6000,6500,7000,7500,8000}.safetensors`，已纳入能力 preset、批量测评下拉与 LoRA 资源库。

## 版本更新指引

1. Workflow JSON：修改 backend/app/workflows/comfyui/<workflow_key>.json 并在本文档记录关键变化。
2. 能力 Schema：更新 backend/app/constants/abilities.py 中对应 schema/metadata，保持字段描述与节点号一致。
3. 执行节点：新增服务器或端口时修改 config/executors.yaml，运行 ensure_default_executors 写入数据库。
4. Workflow/Binding 种子：若 workflow_key 或 action 有调整，务必同步 backend/app/services/workflow_seed.py。
5. 数据库刷新：修改完成后执行 ensure_default_executors/workflows/bindings/abilities（见 AGENTS.md），让管理端同步最新配置。
6. 验证：在管理端“能力测试”上传样例，确认获得 storedUrl，必要时附图存档。

## 冷启动脚本

当新环境需要快速落地 ComfyUI 清单时，可使用脚本拉取基准服务器快照并按需补齐模型/插件/LoRA 目录：

```bash
python3 scripts/comfyui_cold_start_seed.py --executor-id executor_comfyui_xxx
python3 scripts/comfyui_cold_start_seed.py --executor-id executor_comfyui_xxx --seed-models --seed-plugins
python3 scripts/comfyui_cold_start_seed.py --executor-id executor_comfyui_xxx --seed-loras
```

脚本会在 `reports/` 目录生成基准快照 JSON，模型/插件默认只补齐缺失条目，LoRA 元信息会按 file_name 自动补齐为「对外名称」。

如果需要把“已安装的节点/模型”自动对齐到资源清单（补充下载地址/来源），可使用以下参数：

```bash
python3 scripts/comfyui_cold_start_seed.py --executor-id executor_comfyui_xxx --seed-models \
  --model-source reports/comfyui_model_catalog_seed_20260205.json

python3 scripts/comfyui_cold_start_seed.py --executor-id executor_comfyui_xxx --seed-plugins \
  --plugin-list <custom-node-list.json> --node-map <extension-node-map.json>

python3 scripts/comfyui_cold_start_seed.py --executor-id executor_comfyui_xxx --seed-models --seed-plugins \
  --model-source reports/comfyui_model_catalog_seed_20260205.json \
  --plugin-list <custom-node-list.json> --node-map <extension-node-map.json> \
  --report reports/comfyui_missing_<executor>.json
```

> 说明：`custom-node-list.json` 与 `extension-node-map.json` 可来自外部插件清单项目；脚本仅更新当前服务器实际出现的节点/模型，并不会写入全量插件。生成的 `report` 会额外输出“按仓库聚合”的插件列表，便于下发任务时按仓库去重。

## 运维接口与诊断工具

### ComfyUI 原生 HTTP 接口

| Endpoint | 说明 |
| --- | --- |
| `POST /prompt` | 提交 workflow/prompt graph，返回 `prompt_id/prompt_id`。所有能力请求最终都会走该接口。 |
| `GET /history/{prompt_id}` | 查询指定 prompt 的执行结果，用于补充日志或排查输出丢失。 |
| `GET /view` | 静态文件目录，通常用于下载 ComfyUI 侧保存的 PNG（注意：生产环境统一由后端重新上传 OSS）。 |
| `GET /object_info` | 返回节点 → 输入字段 → 可选项（模型、LoRA、VAE 等）。管理端的 LoRA 下拉列表、模型缓存均来自该接口。 |
| `GET /queue/status` | 单 worker 队列状态，包含 `queue_running/queue_pending/queue_size_max`。 |

若远程服务器开启了鉴权/反向代理，请确保 API Key 限制、IP 白名单等与 backend executor 配置保持一致。

### 管理端封装 API

| Endpoint | 说明 |
| --- | --- |
| `GET /api/admin/comfyui/models?executorId=...&includeNodes=true` | 代理 `/object_info`，解析 `UNETLoader/CLIPLoader/VAELoader/LoraLoaderModelOnly` 字段；`includeNodes` 会额外返回 `nodeKeys/nodeCount`，用于服务器对齐对比。 |
| `GET /api/admin/comfyui/loras?executorId=...` | LoRA 目录（数据库）+ 节点实装列表合并，返回 `items` 与 `untrackedFiles`，便于补齐 LoRA 元信息。 |
| `POST /api/admin/comfyui/loras` | 新增/更新 LoRA 元信息（file_name/display_name/base_models/trigger_words 等）。 |
| `PUT /api/admin/comfyui/loras/{id}` | 编辑 LoRA 元信息（不允许修改 file_name）。 |
| `DELETE /api/admin/comfyui/loras/{id}` | 删除 LoRA 元信息。 |
| `GET /api/admin/comfyui/model-catalog` | 模型资源清单（UNET/CLIP/VAE/其他），用于补齐下载/来源信息。 |
| `POST /api/admin/comfyui/model-catalog` | 新增/更新模型资源条目。 |
| `PUT /api/admin/comfyui/model-catalog/{id}` | 编辑模型资源条目。 |
| `DELETE /api/admin/comfyui/model-catalog/{id}` | 删除模型资源条目。 |
| `GET /api/admin/comfyui/plugin-catalog` | 插件资源清单（节点名/包名/版本）。 |
| `POST /api/admin/comfyui/plugin-catalog` | 新增/更新插件资源条目。 |
| `PUT /api/admin/comfyui/plugin-catalog/{id}` | 编辑插件资源条目。 |
| `DELETE /api/admin/comfyui/plugin-catalog/{id}` | 删除插件资源条目。 |
| `GET /api/admin/comfyui/version-catalog` | ComfyUI 版本清单（tag/commit/下载地址）。 |
| `POST /api/admin/comfyui/version-catalog` | 新增/更新版本条目。 |
| `PUT /api/admin/comfyui/version-catalog/{id}` | 编辑版本条目。 |
| `DELETE /api/admin/comfyui/version-catalog/{id}` | 删除版本条目。 |
| `POST /api/admin/comfyui/version-catalog/sync` | 在线同步 ComfyUI 版本（默认 GitHub tag）。 |
| `GET /api/admin/comfyui/queue-status?executorId=...` | 由 admin API 代理 `/queue/status`，统一展示 `runningCount/pendingCount/queueMaxSize`。测试面板提供手动刷新，方便排查串行 worker 是否被拖慢。 |
| `GET /api/admin/comfyui/queue-summary?executorIds=...` | 汇总多台 ComfyUI 节点的队列状态、中台下发节奏和近 24 小时真实命中证据，返回 `totalRunning/totalPending/totalCapacity/backendQueuedTotal/backendRunningTotal/feedGapServers/routeEvidenceTotal/recentRouteMissingServers/diagnostics/servers[]`，用于“调度监控/执行节点”看板判断 GPU 是否被持续喂满，以及 158 / 233 是否都被真实任务命中。 |
| `GET /api/admin/comfyui/workflow-compatibility?executorIds=...` | 检查 active ComfyUI 能力在路由机器上是否缺自定义节点、缺模型文件或路由绑定不一致；管理端“任务衔接诊断”可直接看到可运行、需关注和不可运行数量。 |
| `GET /api/admin/comfyui/system-stats?executorId=...` | 代理 `/system_stats`，返回 ComfyUI 版本与设备信息（用于服务器对齐）。 |
| `POST /api/admin/comfyui/server-diff` | 保存服务器对齐快照（基准节点 + 差异清单）。 |
| `GET /api/admin/comfyui/server-diff` | 读取最近对齐记录（默认 10 条）。 |

> 注意：ComfyUI 默认单线程顺序执行，`pendingCount`>0 时说明上一张仍在处理，新的请求会等待。必要时请切换到另一台 executor 或扩大 worker 数量后再在 config/executors.yaml 中声明。

### 重启后节点自检

158 或 233 重启后，先跑无成本自检，再放真实业务：

```bash
python3 backend/scripts/check_comfyui_node_health.py \
  --backend-url http://127.0.0.1:8099 \
  --report "reports/comfyui-node-health_$(date +%Y%m%d_%H%M%S).json"
```

检查范围：

- 直接访问每台 ComfyUI 的 `/system_stats`，确认版本、内存和 GPU 设备可读。
- 直接访问 `/queue`，确认队列接口可读且不会卡住。
- 直接访问 `/object_info`，确认关键节点如 `KSampler`、`SaveImage`、`LoadImage` 存在。
- 访问中台 `/api/coze/podi/comfyui/queue-summary`，确认节点已被中台纳入路由、没有 `unsupportedServers` 或 `backendBlockedServers`。

该脚本不提交生图任务，不消耗第三方额度；它只能证明“节点可读、队列可读、依赖清单可读、路由可见”。正式发版或模型变更后，仍需要跑真实业务巡检确认回填闭环。

### 能力级 LoRA 绑定规则（metadata）

为避免 LoRA 误用，ComfyUI 能力可在 metadata 中配置以下字段（管理端已提供表单）：

- `allowed_lora_files`: 允许的 LoRA 文件名列表（文件名为准）。
- `allowed_lora_tags`: 允许的 LoRA 标签列表（来自 LoRA 目录）。
- `allowed_lora_base_models`: 允许的基座模型列表（匹配 LoRA 的 base_models/base_model）。
- `default_lora`: 默认 LoRA（当未传入或不匹配时使用）。
- `lora_policy`: 不匹配处理策略，`fallback`（回退默认）/`ignore`（直接忽略）。

后端会在调用 ComfyUI 前自动校验/回退，确保线上调用不受误配置影响。
