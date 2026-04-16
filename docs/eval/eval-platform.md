# 评测平台（podi-eval-web）功能说明

> 版本：2026-03-05  
> 定位：内部回归验证与打分，不替代生产调用。

## 1. 页面结构

评测端导航固定为 5 个业务分类 + 功能页：

- **通用类 / 花纹提取类 / 图延伸类 / 四方/两方连续图类 / 图裂变**：工具选择与试运行
- **LoRA 批测**：独立批量回归页（不属于上述 5 个分类），仅展示含 LoRA 字段的工作流
- **任务**：查看最近运行记录
- **文档**：自动生成的工作流文档（结构化 + Markdown）
- **管理**：管理员维护能力名称/备注/状态（使用评测端专用 `EVAL_ADMIN_TOKEN`，非管理端 JWT）

## 2. 关键行为（交互）

### 2.1 工具试运行

- 选择工具后自动加载默认参数（来自 `parameters_schema`）
- 图片输入统一字段 `url`
- 运行后写入评测 run，并在列表中轮询刷新

### 2.2 运行记录

- 运行列表每 2s 自动刷新（用于及时看到回调结果）
- 支持筛选（状态/评分/未评分）与关键词搜索
- 错误提示统一走“错误码映射”展示（可读文案 + 原错误码），减少联调歧义
- 状态口径统一为三段：
  - `submit_status`：提交阶段
  - `callback_status`：回调/回填阶段
  - `final_status`：最终结果阶段（用于页面主状态）

### 2.3 LoRA 批测

- 入口：顶部导航 `LoRA批测`
- 二级页签：
  - **生成任务**：上传、提交、执行进度、失败统计
  - **结果标注**：分页标注、断点续标、CSV 导出
- 参数：
  - 工作流：仅可选“参数 schema 含 LoRA 字段且含 `url` 字段”的工作流
  - LoRA：优先读取 schema options；若未配置枚举值则允许手动输入
  - 提示词：若该工作流支持 `prompt` 字段则可填写；不支持时输入框置灰
  - 其他入参：按 workflow schema 动态展示（可选/必填），不支持的字段置灰提示
  - 测试次数：每张图重复提交次数（用于降低随机性）
  - 并发提交：批次提交并发数（建议 1~4）
  - 输出尺寸策略：
    - 原图大小：不下发尺寸字段（保持工作流默认）
    - 推荐 1K：优先下发 `resolution=1K`；若工作流只有 `width/height`，则按原图比例换算为“最长边=1024”
    - 自定义：可选画幅比例与分辨率
- 行为：
  - 任务口径：一次“上传图片 + 点击提交”定义为一个测试任务（批次）（可包含多张图）
  - 批量上传后，评测端先完成整批 OSS 上传，再按“每图 * 次数”统一提交 `POST /api/evals/runs`（两阶段解耦）
  - 单批上限 5000 条（图片数 * 测试次数），超过需分批执行
  - 提交进度卡展示：样本图片数、每图测试次数、计划执行条数、已提交执行、已完成执行、有图完成
  - 上传进度可视化：新增“文件进度 + 字节进度”显示，实时看到成功数/失败数/上传中数量，便于定位大批量上传卡点
  - 批次会记录期望值（图片数/重复次数/计划条数）；若“计划条数 > 已入库执行”，页面会提示“未入库”数量
  - 批次保留：历史批次会保留在页面中，可通过“查看批次”切换，不会因“清空图片”被删除
  - 批次列表不再跟随“当前工作流”筛选，避免切换工作流后找不到历史批次
  - 批次列表默认展示“全部批次”（非仅当前浏览器会话），避免因 Cookie 变化导致历史批次消失
  - 批次历史来源：页面优先从后端批次接口加载，不依赖当前浏览器内存；刷新页面后仍可查看历史批次
  - 弱网处理：批次列表/明细均提供“刷新”按钮，并显示最近一次加载失败原因
  - 批次停止：支持“停止本批次”，会把该批次未完成任务置为失败，避免继续占用服务器资源
  - 自动做必填默认值检查：缺少默认参数时阻止提交并提示补齐能力配置
  - 后端调度隔离：ComfyUI 与商业模型（KIE/火山）分开并发池执行，互不占用执行槽位
  - 页面状态分离：
    - 已提交：仅表示 run 创建成功
    - 已完成：表示 run 状态已变为 succeeded/failed
    - 有图完成：表示 succeeded 且 `result_image_urls_json` 非空
  - 结果标注（批次结束后开启）：
    - 标注页固定 **每页 20 组**（组=原图素材），只拉当前页，不再一次性加载全量
    - 页面展示全部组（含无结果/失败组），但仅结果图可标注
    - 标注策略改为**仅标记不满意**（默认满意），并可填写原因/备注
    - 支持“本页完成”，会写入 `current_page/completed_page`，刷新后自动续标
    - 标注与进度都持久化到数据库
    - 支持导出 CSV（全部对照集 / 仅不满意样本）
      - 有不满意记录：`不满意`
      - 无不满意且页已完成：`满意(默认)`
      - 无不满意且页未完成：`未标注`
      - 无结果图：`无结果`

### 2.4 文档页

- 拉取 `GET /api/evals/docs/workflows`
- 支持结构化表格和 Markdown 视图切换

### 2.5 管理页

- 通过 `EVAL_ADMIN_TOKEN` 登录（本地存储，Header: `X-Eval-Admin-Token` 或 URL `?admin_token=`）
- 支持编辑：名称、备注、状态、分类、版本

## 3. 前端请求与接口映射

`podi-eval-web/src/api.ts`：

- `GET /api/evals/me`
- `GET /api/evals/workflow-versions?status=active`
- `POST /api/evals/runs`
- `GET /api/evals/runs`
- `POST /api/evals/batches/{batch_id}/reviews`
- `GET /api/evals/batches/{batch_id}/review-groups`
- `POST /api/evals/batches/{batch_id}/review-progress`
- `GET /api/evals/runs/batches`
- `POST /api/evals/runs/batches/{batch_id}/stop`
- `GET /api/evals/runs/{run_id}`
- `POST /api/evals/runs/{run_id}/annotations`
- `GET /api/evals/docs/workflows`
- `POST /api/evals/uploads`
- 管理接口：`/api/evals/admin/workflow-versions`

## 4. 参数契约

- 图片输入统一 `url`
- 像素参数必须为纯数字（禁止 `px`）
- 枚举参数必须传 value

### 4.1 多模型生图（`7602916576198656000`）参数约定

- `moxing`：`1=Banana Pro`、`2=Flux2 Pro`、`3=Seedream 4.5`、`4=Banana 2`
- `cankaotu`：参考图 URL 列表（每行一张或英文逗号分隔）
  - 仅模型 `1/2/4` 生效
  - 前端会兼容映射为 `image_urls`，保证历史调用不受影响
- `aspect_ratio`（按模型枚举）
  - **注意**：`原图比例（默认）` 只是前端展示文案，实际调用时应传空字符串或直接不传；不要把这段中文文案当成真实枚举值传给模型。
  - Banana Pro（`moxing=1`）：`auto, 1:1, 2:3, 3:2, 3:4, 4:3, 4:5, 5:4, 9:16, 16:9, 21:9`
  - Flux2 Pro（`moxing=2`）：`auto, 1:1, 4:3, 3:4, 16:9, 9:16, 3:2, 2:3`
  - Seedream 4.5（`moxing=3`）：忽略该参数（仅保留空值）
  - Banana 2（`moxing=4`）：`auto, 1:1, 2:3, 3:2, 3:4, 4:3, 4:5, 5:4, 9:16, 16:9, 21:9`
- `resolution`（按模型枚举）
  - **注意**：`跟随原图（默认）` 只是前端展示文案，实际调用时应传空字符串或直接不传；不要把这段中文文案当成真实枚举值传给模型。
  - Banana Pro（`moxing=1`）：`1K, 2K, 4K`
  - Flux2 Pro（`moxing=2`）：`1K, 2K`
  - Seedream 4.5（`moxing=3`）：忽略该参数（仅保留空值）
  - Banana 2（`moxing=4`）：`1K, 2K, 4K`

### 4.2 多图融合（`7615600173695107072`）参数约定

- 入参：
  - `url`：主图 URL（图1，必填）
  - `image_url_2`：辅图 1 URL（可选，映射图2）
  - `image_url_3`：辅图 2 URL（可选，映射图3）
  - `width` / `height`：可选，直接覆盖出图宽高；评测页留空时会自动读取主图尺寸后提交，绕过前端直调时则沿用 workflow 默认 `1024x1024`
  - `negative_prompt`：可选
  - `prompt`：可选
  - `seed`：可选，不填后端自动生成
  - 无 `lora` 入参
- 页面行为：
  - 通用类工具页支持主图上传 + 辅图 1 / 辅图 2 上传按钮
  - 当 `width` / `height` 留空时，评测页会先读取主图尺寸并自动补齐后再提交
  - 辅图未传时，后端会在提交前移除对应节点引用，而不是复用默认占位图
  - 若只传了一个辅图，不会强行补第三张；仅保留 `image2`
- 出参：
  - `output`：回调 task id
  - `prompt`：提示词反馈字符串

### 4.3 LoRA 查询（`7612002440056930304`）参数约定

- 入参：无
- 出参：
  - `items`：LoRA 详情列表（`fileName/displayName/status/baseModels/tags/installed`）
  - `lora_names`：LoRA 文件名数组
  - `loraNames`：`lora_names` 的 camelCase 兼容字段（两者等价）
- 展示规则：评测页点击该工作流任务后，直接渲染 JSON 结果（不走图片回填）。
- 业务接入建议：后续调用需要 LoRA 入参时，优先使用 `lora_names` 中的值。

### 4.4 新增 ComfyUI 工作流（2026-04-16）

- `7629023903431524352`（背景抠图 · `beijing_koutu`）
  - 分类：`通用类`
  - 入参：`url`
  - 出参：
    - `output`：回调 `task id`
    - `ip`：ComfyUI 执行节点 IP

- `7629023041988591616`（头部抠像 · `toubu_kouxiang`）
  - 分类：`通用类`
  - 入参：`url`
  - 出参：
    - `output`：回调 `task id`
    - `ip`：ComfyUI 执行节点 IP

- `7629024620879806464`（文字增强 · `qwen2512_print_shape_text_enhance`）
  - 分类：`图裂变`
  - 入参：
    - `url`
    - `prompt`
    - `bili`
    - `count`
  - 说明：
    - `bili` 为相似度百分比，默认 `50%`
    - `count` 为一次评测触发的 fan-out 子任务数，默认 `4`
  - 出参：
    - `output`：回调 `task id`
    - `prompt`：提示词反馈字符串
    - `ip`：ComfyUI 执行节点 IP

- `7629026792103215104`（四方连续裂变 · `flux2_9b_liebian_sifang`）
  - 分类：同时展示在 `图裂变` 和 `四方/两方连续图类`
  - 入参：
    - `url`
    - `prompt`
    - `count`
  - 说明：
    - `count` 为一次评测触发的 fan-out 子任务数，默认 `4`
  - 出参：
    - `output`：回调 `task id`
    - `prompt`：提示词反馈字符串
    - `ip`：ComfyUI 执行节点 IP

## 5. 注意事项

- 如开启 `EVAL_PUBLIC_TOKEN`，前端请求需带 `X-Eval-Token` 或 URL `?token=`（当前前端未内置 header，需通过 URL 注入）。
- 管理 token 会存于 `localStorage`，需妥善保管。

## 6. 问题与优化记录

详见 `docs/standards/issue-improvement-log.md`。
