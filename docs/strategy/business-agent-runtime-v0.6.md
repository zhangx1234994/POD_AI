# v0.6 AI 图片助手 Agent Runtime 方案

日期：2026-06-02
最后更新：2026-06-08

## 结论

对话式图片任务作为独立 Agent 入口接入，不改造中台主架构，不绕开现有业务能力 API。P0 底层复用 `agent.image_edit_assistant` Runtime：多轮对话理解、生成结构化 JSON 计划、后端白名单路由、调用匹配的业务 run。当前阶段采用“质量优先主路径”：GPT-5.5 / Responses API 负责规划，默认通过 `business.image_edit` 调用 GPT Image 2 完成单张高质量生成或改图；中台专项能力作为批量、速度、低成本或固定 SOP 的分流路径。

命名和归类口径：当前测评端可以把它暂时放在“图编辑”分类下，帮助用户从改图场景进入；但它不是可视化图编辑器的子模式。可视化图编辑器解决“看图、圈选、参考图、精确提交”，对话改图解决“像聊天一样表达目标、多轮追改、由 Agent 调用能力”。长期看，对话改图归入 Agent 体系，并会逐步扩展到更多白名单业务能力。

MVP 交付口径：v0.6 可以先只做单图多轮对话改图，但必须按 Agent Runtime 样板交付，不能只做一个前端聊天框或一次性任务表单。MVP 可以小，架构方向不能歪。

## MVP 原则

- 前端负责聊天体验、图片预览、新任务/继续任务、状态反馈和历史查看；不能在前端决定底层能力路由、直接调用厂商接口或保存不可审计上下文。
- 后端负责会话状态、上下文压缩、意图识别、能力路由、方法论阶段、参数抽取、任务队列、Key 池、成本控制、错误契约和审计日志。
- 大模型可以参与意图理解和路由建议，但不能自由调用工具；所有工具调用必须经过后端白名单、schema、置信度、成本和风险校验。
- 方法论不是一段临时 prompt，而是可版本化的流水线模板；每个模板必须描述阶段、输入输出、可调用能力、人工确认点、失败兜底和验收证据。
- 对话式图片 Agent 当前开放 `business.image_edit` 和 `business.pattern_extract` 两个白名单工具；默认 `business.image_edit` 作为 GPT Image 2 质量优先路径，`business.pattern_extract` 作为明确批量/快速/低成本/专项花纹提取时的加速路径。字段、日志和测试必须继续为裂变、产品设计、组图、模特图、推广视频等业务能力预留。

## 边界

- AI 图片助手可以调用中台白名单工具，当前允许 `business.image_edit` 和 `business.pattern_extract`。普通自然语言图片任务默认走 `business.image_edit`，即 GPT Image 2 质量优先主路径；只有用户明确要求批量、快速、低成本或专项能力时才分流到 `business.pattern_extract` 等专项能力。
- AI 图片助手不直接调用 OpenAI 图像接口、ComfyUI、KIE、火山或百度。
- AI 图片助手与可视化图编辑工作台是两个产品方向；可以互相跳转、共享资产和 runId 证据，但不能共用同一个交互模型或把会话续改做成一次性任务表单。
- GPT-5.5 / Responses API 只作为 planner 可选实现；未配置 Key 或调用失败时使用规则 planner 兜底。
- `confirm` 接口是后端幂等执行边界，不等于用户界面必须出现确认按钮。低置信、缺图、高风险或高成本能力需要停下来追问或人工复核；普通单步图片能力可以在规划后由前端自动调用执行边界。
- 会话必须显式创建和显式续聊；`requestId` 只做同一租户/客户端下的创建幂等，不做跨会话自动合并。
- 只能提交当前会话最新方案；旧方案返回 `AGENT_PLAN_STALE`，执行中的方案返回 `AGENT_PLAN_CONFIRM_IN_PROGRESS`。
- 已执行方案重复提交返回原 `runId`，不重复创建下游业务任务。
- 最终结果仍通过 `/api/business/runs/get` 查询，资产、成本、质量和调用证据继续复用现有中台链路。

## 后端对象

| 表 | 用途 |
| --- | --- |
| `business_agent_sessions` | 一次 AI 图片助手会话，保存底层 Agent key、状态、主图、租户/客户端、trace。 |
| `business_agent_messages` | 用户、助手、工具消息。 |
| `business_agent_plans` | 结构化方案卡片，保存意图、步骤、工具 payload、成本和风险。 |
| `business_agent_tool_calls` | AI 图片助手调用中台能力的证据，关联 `runId`。 |

## API

| 接口 | 说明 |
| --- | --- |
| `POST /api/business/image-edit-chat/sessions` | 创建会话；可带首条 `message` 直接生成 AI 图片助手回复和最新计划。 |
| `GET /api/business/image-edit-chat/sessions/{sessionId}` | 查询会话、消息、方案和工具调用。 |
| `POST /api/business/image-edit-chat/sessions/{sessionId}/messages` | 追加消息并生成新计划。 |
| `POST /api/business/image-edit-chat/sessions/{sessionId}/confirm` | 提交当前最新计划进入后端执行边界，按路由结果创建业务 run。 |
| `POST /api/business/image-edit-chat/sessions/{sessionId}/plans/{planId}/confirm` | 严格提交指定方案版本；主要给高级调用方和回归测试使用。 |

## 路由、上下文与方法论

Agent 的稳定性不能靠“模型更聪明”兜底，而要靠中台把模型输出约束进能力契约、上下文状态和路由证据链。

推荐链路：

```text
用户消息 -> LLM/规则理解 -> 结构化 JSON 计划 -> 质量优先/专项加速路由 -> 后端校验 -> 低置信追问/人工复核 -> 创建业务 run
```

结构化计划至少保留以下字段：

| 字段 | 用途 |
| --- | --- |
| `intent` | 用户本轮真实意图，例如局部修改、整体风格优化、继续上一轮结果、新任务。 |
| `routeType` | 路由类型：`image2_quality_first`、`ability_accelerated`、`clarification_required`。 |
| `targetAbility` | 候选业务能力，当前只允许 `business.image_edit`、`business.pattern_extract`。 |
| `confidence` | 路由置信度；低于阈值必须追问，不能直接执行。 |
| `missingFields` | 缺失输入，例如主图、区域、风格、参考图或输出规格。 |
| `baseImageRole` | 本轮基准图来源：`source_image`、`previous_result` 或明确指定的历史结果。 |
| `parentRunId` | 如果基于上一轮输出继续改，必须记录上一轮 run。 |
| `methodologyId` / `methodologyVersion` | 后续方法论流水线版本；MVP 可为空，但字段必须预留。 |
| `routeReason` | 为什么选这个能力和参数。普通单张任务要说明为何走 GPT Image 2 质量优先；专项分流要说明用户的批量、速度或成本诉求。 |
| `rejectedAbilities` | 被排除的候选能力及原因，避免路由漂移无法复盘。 |
| `riskLevel` | 成本、越权、破坏原图主体、低置信等风险等级。 |

上下文分 4 层保存和压缩：

1. `rawMessages`：完整原始消息，只用于审计和必要回放。
2. `workingMemory`：从历史对话压缩出的长期约束，例如保留主体、品牌偏好、风格偏好、禁改项。
3. `assetState`：当前基准图、原始主图、参考图、历史输出、选中版本和 parent run。
4. `toolTrace`：每次工具调用的计划、参数、runId、状态、结果和错误。

每次模型调用只注入最近消息、`workingMemory`、当前 `assetState`、可用工具 schema 和上一轮工具结果摘要；不把完整历史对话无限塞回模型。

## 会话设计

- 测评端或客户端要展示“新会话/当前会话”，主图切换时默认开启新会话，避免把新图挂在旧方案上下文下执行。
- 网络重试只复用带相同 `requestId` 的创建请求；追加消息和执行边界请求都必须显式带 `sessionId`。
- 追加消息也必须支持消息级幂等：同一 `sessionId + requestId` 只生成一张方案卡；网络重试复用同一个 `requestId`，新诉求必须换新 `requestId`，避免重复方案污染 `latestPlanId`。
- 每条新消息生成一个新计划，并更新 `latestPlanId`；默认执行边界接口提交当前最新计划。
- 执行边界接口先把方案置为 `confirming` 再调用业务 run，便于排查“提交中”与“下游失败”的分界。

## 执行与并发策略

对话改图和未来方法论 Agent 都按长任务处理，不在前端同步等待第三方能力完成。

- 前端只提交消息、触发后端执行边界和订阅状态；出图、视频、评估、回填均由后端任务和 worker 完成。
- 后端创建业务 run 后进入队列，按能力、租户、用户、执行节点和供应商限流。
- 同一会话执行边界接口必须幂等；重复点击或网络重试不能重复扣费或重复创建下游 run。
- 路由时要读取执行节点健康、队列长度、并发上限和最近失败情况；不能只按固定节点或模型名称派发。
- 队列拥堵、节点不可用、供应商超时、Key 额度不足都必须进入错误契约和前端可理解状态。
- 高成本能力和多阶段方法论必须支持人工确认点；未经确认不得自动进入下一阶段。

## 测评端交互

入口与图编辑工作台拆分展示，但可互相协作：

1. 用户上传或粘贴主图。
2. 用户在 AI 图片助手消息框里自然表达图片任务诉求。
3. AI 图片助手以消息形式回复，并附带可执行计划卡，只展示标题、摘要、关键步骤、执行状态和结果，不展示完整 JSON、routeReason 或内部参数。
4. 用户可继续追问；如果路由到直接图编辑，也可一键把计划应用到精确图编辑器，继续手动标注或补参考图。
5. 计划满足执行条件后，前端触发后端执行边界；AI 图片助手显示 `runId`、轮询状态和输出缩略图。

## MVP 稳定性门禁

对话改图不能只验证“能出一张图”。进入封版前至少覆盖：

1. 单图首轮计划、后端执行、结果回填。
2. 同一会话二轮继续修改时，默认基于上一轮成功输出，而不是原始主图。
3. 新任务必须隔离上下文，不能污染旧会话。
4. 用户表达模糊时能追问或给出低置信提示，不能乱路由。
5. 每次计划都能在排障详情看到 `routeType`、`targetAbility`、`confidence`、`baseImageRole`、`parentRunId`、`routeReason` 等证据；普通用户界面只展示必要节点。
6. 依赖失败、超时、队列满、并发限制、供应商错误时，错误可读、可重试、可排查。
7. 同一批 golden cases 多次运行时，路由结果稳定；模型 planner 和规则兜底都要进入回归。
8. 并发提交时状态不串会话、不丢结果、不重复扣费。

## 后续升级门槛

暂不引入 LangGraph 等重型框架。满足任一条件再评估：

- 单个 Agent 要连续执行 5 步以上。
- 中间需要多次暂停、人工复核、恢复和回滚。
- 需要多 Agent 分工，例如设计方案 Agent、质量评估 Agent、视频脚本 Agent。
- 需要把花纹提取、裂变、产品图、模特图、视频串成长流程。

届时可把当前 Runtime 的 session/plan/tool_call 表作为迁移基础，保留 API 和测评端交互不变。
