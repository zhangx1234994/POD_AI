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
  - `aspect_ratio`
  - `resolution`
  - 多图上限与字段名（`url/image_urls`）
  - 若模型不支持该参数，必须明确“忽略/不生效”
