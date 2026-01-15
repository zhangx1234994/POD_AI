# ComfyUI Workflow Handbook

本目录记录当前托管在仓库内的 ComfyUI 工作流，便于排查与版本控制。每个条目包含：

- workflow_key / ability key / action
- 默认执行节点（服务器/端口）
- 关键节点编号与功能说明
- 默认参数、LoRA 版本与超时配置
- 运维/调试备注

> 修改 workflow 或能力时请同步更新本文档，并在 PR 描述中说明节点调整、LoRA 更换或默认参数变化，确保与 backend/app/workflows/comfyui/*.json 及 backend/app/constants/abilities.py 一致。

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

## 印花提取 · ComfyUI (workflow_key: yinhua_tiqu)

| 项目 | 说明 |
| --- | --- |
| 能力 ID | comfyui.yinhua_tiqu |
| Action | pattern_extract |
| 执行节点 | executor_comfyui_pattern_extract_158 → http://117.50.80.158:8079 |
| Workflow 文件 | backend/app/workflows/comfyui/yinhua_tiqu.json |
| 超时设置 | 420 秒 (defaults.timeout) |
| 核心模型 | UNETLoader: qwen_image_edit_2511_fp8mixed.safetensors、CLIP: qwen_2.5_vl_7b_fp8_scaled.safetensors、VAE: qwen_image_vae.safetensors、LoRA(节点 390) 默认 印花提取-YinHuaTiQu-Qwen-Image-Edit-LoRA_V1.safetensors |

**关键节点**

| 节点 | 描述 |
| --- | --- |
| 393 · LoadImagesFromURL.url | 实物照片 URL（管理端上传→OSS 时自动填写）。 |
| 111 · TextEncodeQwenImageEditPlus.prompt | 正向提示词，包含“还原设计稿”规范。支持在表单 prompt 字段覆盖。 |
| 110 · TextEncodeQwenImageEditPlus.prompt | 反向提示词（negative_prompt）。 |
| 390 · LoraLoaderModelOnly | LoRA 文件名（lora_name），更换版本需在本文档记录。 |
| 400 · LatentUpscale | 最终输出尺寸（output_width/output_height）。 |
| 421 · SaveImageWithDPI | 保存 PNG，DPI=150，文件前缀 DPI_Image，最终由后端上传 OSS（输入来自节点 8 解码结果）。 |

**默认参数**

- prompt: 文档内“高保真设计稿”模板（见能力 schema）。
- negative_prompt: 长串低质量/错误特征黑名单（保持与 workflow JSON 同步）。
- output_width/output_height: 1800
- lora_name: 印花提取-YinHuaTiQu-Qwen-Image-Edit-LoRA_V1.safetensors

**调试备注**

- 该版本已移除遮罩/预览分支，所有尺寸控制集中在节点 400。若需裁切或添加遮罩，可在 ComfyUI 端单独分支并记录新的 workflow 版本。
- 替换 LoRA 时请同步更新 workflow JSON、abilities.py defaults 及本文档的“核心模型/默认参数”。

## 版本更新指引

1. Workflow JSON：修改 backend/app/workflows/comfyui/<workflow_key>.json 并在本文档记录关键变化。
2. 能力 Schema：更新 backend/app/constants/abilities.py 中对应 schema/metadata，保持字段描述与节点号一致。
3. 执行节点：新增服务器或端口时修改 config/executors.yaml，运行 ensure_default_executors 写入数据库。
4. Workflow/Binding 种子：若 workflow_key 或 action 有调整，务必同步 backend/app/services/workflow_seed.py。
5. 数据库刷新：修改完成后执行 ensure_default_executors/workflows/bindings/abilities（见 AGENTS.md），让管理端同步最新配置。
6. 验证：在管理端“能力测试”上传样例，确认获得 storedUrl，必要时附图存档。

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
| `GET /api/admin/comfyui/models?executorId=...` | 由 admin API 代理 `/object_info`，并解析到 `UNETLoader/CLIPLoader/VAELoader/LoraLoaderModelOnly` 字段。管理端在渲染 schema 时会将 `component=select` 的字段改为下拉，并允许“自定义 LoRA”回退到手动输入。 |
| `GET /api/admin/comfyui/queue-status?executorId=...` | 由 admin API 代理 `/queue/status`，统一展示 `runningCount/pendingCount/queueMaxSize`。测试面板会自动轮询（15s）并提供手动刷新，方便排查串行 worker 是否被拖慢。 |

> 注意：ComfyUI 默认单线程顺序执行，`pendingCount`>0 时说明上一张仍在处理，新的请求会等待。必要时请切换到另一台 executor 或扩大 worker 数量后再在 config/executors.yaml 中声明。
