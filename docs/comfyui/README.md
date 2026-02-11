# ComfyUI Workflow Handbook

本目录记录当前托管在仓库内的 ComfyUI 工作流，便于排查与版本控制。每个条目包含：

- workflow_key / ability key / action
- 默认执行节点（服务器/端口）
- 关键节点编号与功能说明
- 默认参数、LoRA 版本与超时配置
- 运维/调试备注

> 修改 workflow 或能力时请同步更新本文档，并在 PR 描述中说明节点调整、LoRA 更换或默认参数变化，确保与 backend/app/workflows/comfyui/*.json 及 backend/app/constants/abilities.py 一致。

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
- **ComfyUI 不做硬超时失败**：排队等待属于正常状态，轮询超时只代表“同步等待上限”，会返回 `running` 继续由后续轮询收敛。  
- **第三方能力仍有硬超时**：KIE/Volcengine 等不可控能力保持硬超时策略。  

更多细节请参见：
- `docs/comfyui-routing-business.md`
- `docs/comfyui-routing-technical.md`

## 待办 / 风险记录

- LoRA 可能适用于多个基座模型：已新增 `base_models` 多选字段，旧 `base_model` 仅用于兼容。
- “服务器”页已支持基准服务器（baseline）对比：缺失模型/插件时提示差异列表（插件以 `/object_info` 返回的节点名对比）。
- TODO：提供一键同步/修复能力（模型/插件/配置），并补充更细粒度的插件版本校验规则。
- TODO：持续补齐资源清单中的下载地址/来源/版本信息，便于对齐与运维追踪。

## 四方连续 · ComfyUI (workflow_key: sifang_lianxu)

| 项目 | 说明 |
| --- | --- |
| 能力 ID | comfyui.sifang_lianxu |
| Action | seamless |
| 执行节点 | executor_comfyui_seamless_117 → http://117.50.216.233:8079 |
| Workflow 文件 | backend/app/workflows/comfyui/sifang_lianxu.json |
| 超时设置 | 480 秒 (defaults.timeout) |
| 核心模型 | UNETLoader: 四方连续.safetensors、DualCLIPLoader: t5xxl_fp8_e4m3fn_scaled.safetensors + clip_l.safetensors、VAE: ae.safetensors |

**关键节点**

| 节点 | 描述 |
| --- | --- |
| 42 · StringConcatenate.string_a | 主提示词（能力表单 prompt）。 |
| 96 · LoadImagesFromURL.url | 参考图 URL（上传后端会自动回填）。 |
| 104 · easy loadImageBase64.base64_data | Base64 输入；若只提供 URL，Executor 会先下载后写入，避免中心留白。 |
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

- 若管理端回显“中心留白”，重点检查节点 96 是否拿到公网可访问的 URL、以及节点 104 是否被正确写入（后端日志会打印）。
- Base64 默认值不要在 JSON 中清空；任何临时修改需记录在本文档。

## 花纹扩图 · ComfyUI (workflow_key: huawen_kuotu)

| 项目 | 说明 |
| --- | --- |
| 能力 ID | comfyui.huawen_kuotu |
| Action | pattern_expand |
| 执行节点 | executor_comfyui_pattern_extract_158 / executor_comfyui_seamless_117（均部署 Qwen Image Edit 2511） |
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
- `output_long_side` 控制最终缩放尺寸（长边），若素材要求高分，请在能力表单中调高。
- ControlNet/LoRA 组合对图案延展极为敏感，如需替换模型必须同步更新 workflow 与 `metadata.lora_presets`。

## 印花提取 · ComfyUI (workflow_key: yinhua_tiqu)

| 项目 | 说明 |
| --- | --- |
| 能力 ID | comfyui.yinhua_tiqu |
| Action | pattern_extract |
| 执行节点 | executor_comfyui_pattern_extract_158 → http://117.50.80.158:8079 |
| Workflow 文件 | backend/app/workflows/comfyui/yinhua_tiqu.json |
| 超时设置 | 420 秒 (defaults.timeout) |
| 核心模型 | UNETLoader: qwen_image_edit_2509_fp8_e4m3fn.safetensors、CLIP: qwen_2.5_vl_7b_fp8_scaled.safetensors、VAE: qwen_image_vae.safetensors、LoRA(节点 390) 默认 `杯子1124.safetensors`（可切换 T-Shirt / 毛毯 / 杯子等） |

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
| `GET /api/admin/comfyui/queue-summary?executorIds=...` | 汇总多台 ComfyUI 节点的队列状态，返回 `totalRunning/totalPending/servers[]`，用于“调度监控/执行节点”看板。 |
| `GET /api/admin/comfyui/system-stats?executorId=...` | 代理 `/system_stats`，返回 ComfyUI 版本与设备信息（用于服务器对齐）。 |
| `POST /api/admin/comfyui/server-diff` | 保存服务器对齐快照（基准节点 + 差异清单）。 |
| `GET /api/admin/comfyui/server-diff` | 读取最近对齐记录（默认 10 条）。 |

> 注意：ComfyUI 默认单线程顺序执行，`pendingCount`>0 时说明上一张仍在处理，新的请求会等待。必要时请切换到另一台 executor 或扩大 worker 数量后再在 config/executors.yaml 中声明。

### 能力级 LoRA 绑定规则（metadata）

为避免 LoRA 误用，ComfyUI 能力可在 metadata 中配置以下字段（管理端已提供表单）：

- `allowed_lora_files`: 允许的 LoRA 文件名列表（文件名为准）。
- `allowed_lora_tags`: 允许的 LoRA 标签列表（来自 LoRA 目录）。
- `allowed_lora_base_models`: 允许的基座模型列表（匹配 LoRA 的 base_models/base_model）。
- `default_lora`: 默认 LoRA（当未传入或不匹配时使用）。
- `lora_policy`: 不匹配处理策略，`fallback`（回退默认）/`ignore`（直接忽略）。

后端会在调用 ComfyUI 前自动校验/回退，确保线上调用不受误配置影响。
