# Coze 工具箱开发准则（PODI）

> 版本：2026-03-01  
> 适用范围：`/api/coze/podi/*` 下所有 OpenAPI 与工具接口

## 1. 设计目标

- 面向非技术同学可直接使用，默认“少参数、可空参、可读错误”。
- 保证 Coze 导入稳定：OpenAPI 合法、字段描述完整、响应结构稳定。
- 与平台错误契约一致：状态词和错误码口径统一。

## 2. 接口分层规则（必须）

- 查询类工具箱：用于“拉配置/拉目录/拉参数”，不执行任务。
- 执行类工具箱：用于提交任务与轮询结果。
- 新模型优先“一模型一执行工具箱 + 一模型一参数查询工具箱”。

## 3. 入参规则（必须）

- 所有字段必须有 `description`（中文 + English）。
- 必填字段必须在 `required` 中声明。
- 可选字段必须给默认值或明确“可不传”。
- 查询类默认入口必须支持空请求体；同时提供可选默认参数（兼容 Coze 调试器）。
- 图片字段统一外部契约：
  - 主图：`url`
  - 参考图：`image_urls`

## 4. 出参规则（必须）

- 禁止返回 `null` 字段（Coze 对空值兼容性差）。
- 返回结构必须固定，字段命名不可随意漂移。
- 异步任务统一输出：`taskId`、`taskStatus`、`imageUrl/imageUrls`、`debugResponse`。

## 5. OpenAPI 规范（必须）

- 每个工具必须有：
  - `summary`
  - `description`
  - `requestBody`（可选/必选要准确）
  - `responses.200.schema`
- 查询类工具箱的“默认入口”需在 OpenAPI 首屏可见（避免误选高级接口）。

## 6. 错误与状态（必须）

- 状态仅使用：`queued/running/succeeded/failed`。
- 错误码必须可追踪：
  - 参数缺失/格式错误
  - 队列满
  - 上游失败
  - 回填失败
- 错误描述必须给出下一步动作建议（重试、检查参数、换工具等）。

## 7. 发布前检查清单（必须全过）

1. OpenAPI 可导入（线上地址验证）。
2. Coze 调试页空参调用通过（查询类默认接口）。
3. 默认参数调用通过（例如 `status=active`）。
4. 响应中无 `null` 字段。
5. 文档同步更新：
   - `docs/api/modules/coze.md`
   - `docs/coze/toolbox-inventory.md`
   - `docs/coze/toolbox-contracts.md`
   - `docs/README.md`（总索引）
6. 回归测试通过（至少覆盖 Coze/KIE/ComfyUI 相关测试集）。

## 8. 禁止事项

- 禁止“只改接口不改文档”。
- 禁止“新增字段无描述”。
- 禁止“查询工具箱依赖必填参数才可运行”。
- 禁止“返回结构含随机字段或 null 字段”。

## 9. 输出归类与文档目录（必须）

- 新增/改造工具前，必须先归类输出类型：
  - `callback_task_id`：返回 taskId，需统一走 `/api/coze/podi/tasks/get`
  - `image_url`：直接返回图片 URL
  - `json_output`：直接返回结构化 JSON（如 `items/lora_names`、标签结果）
- 评测端展示规则必须与输出类型一致，禁止“JSON 工具按图片工具渲染”。
- 文档必须按目录同步：
  - 接口明细：`docs/api/modules/*.md`
  - 工具箱清单：`docs/coze/toolbox-inventory.md`
  - 契约说明：`docs/coze/toolbox-contracts.md`
  - 规范准则：`docs/standards/*.md`
- 模型参数枚举必须按“模型维度”列清楚（不可只写“通用支持”），至少覆盖：
  - **展示文案与真实传值必须分开写**：如 `跟随原图（默认）/原图比例（默认）` 只能作为 UI label，真实传值必须是空字符串、`omit` 或模型枚举值。
  - `aspect_ratio`
  - `resolution`
  - 多图上限与字段名（`url/image_urls`）
  - 若模型不支持该参数，必须明确“忽略/不生效”

## 10. 新工具上线门径管理标准（六步法）

> 目的：统一 ComfyUI / KIE / 自研工具从后端开发到 Coze 工作流上线再到评测端落地的完整流程，避免“代码已合但工作流未配、评测未接”的断档。

### Step 1 — 后端本地测试（开发/交接人）
- 覆盖范围：单元测试 +  schema 测试 + OpenAPI 生成测试 + workflow seed / binding 测试。
- 关键动作：
  - 确认新工具的能力 schema、workflow JSON、executor 输入映射已对齐；
  - 运行 `pytest` 并确保新增测试与回归测试全部通过（允许记录与本次无关的既有失败）；
  - 若具备 ComfyUI/KIE 运行环境，执行实际图片生成与回填验证；若本地无环境，至少保证 mock / stub 测试通过，并标注“待线上补跑端到端”。

### Step 2 — 提交代码并同步文档（开发/交接人）
- 关键动作：
  - `git add` 涉及的全部文件（workflow JSON、abilities、executor 适配、seed、router、测试、文档）；
  - 撰写简洁提交信息，说明新增工具名称与影响面；
  - 同步更新 `docs/coze/toolbox-inventory.md`、`docs/comfyui/README.md`、`docs/standards/coze-toolbox-development-standard.md` 等门径文档。

### Step 3 — 服务器部署更新（运维/负责人）
- 关键动作：
  - 在目标环境拉取最新代码并重启服务；
  - 验证 OpenAPI 地址可正常访问（至少能返回合法 JSON）；
  - 若涉及新 workflow，确认 workflow JSON 已同步到执行器节点（ComfyUI 服务器）。

### Step 4 — Coze 工作流配置（业务/联调人）
- 关键动作：
  - 按 `toolbox-inventory.md` 中的独立导入地址，在 Coze 中导入对应工具箱；
  - 将新工具节点接入业务工作流，配置输入参数与下游回调/轮询逻辑；
  - 在 Coze 调试页发起空参/默认参/真实参调用，确认任务可正常进入队列并返回 `taskId`。

### Step 5 — 工作流入参出参对齐与二次测试（业务 + 开发）
- 关键动作：
  - 业务侧将 Coze 工作流最终确定的入参出参文档化并同步给开发；
  - 开发侧根据最终参数补全/修正：abilities schema、executor 映射、回归测试、评测端展示契约；
  - 再次执行端到端测试（真实图片生成 → 回填 → 结果解析），确保整条链路无漂移。

### Step 6 — 评测端功能开发（开发）
- 关键动作：
  - 按已固化的输入输出契约，在评测平台补充对应能力的测试模板、批量任务支持、结果展示与标注逻辑；
  - 回归评测端相关测试，确保新工具在评测平台可正常发起、轮询、展示、导出。

### 门禁说明
- 每步完成后必须在内部同步状态（IM / 站会 / 任务单评论），下一位负责人方可接手；
- 若某一步出现阻塞，必须回退一步检查上一步产出（参数/schema/部署），禁止跳步强推；
- 文档未同步 = 该步骤未完成。
