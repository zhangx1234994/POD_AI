# v0.6 对话改图 ChatBot Runtime 方案

日期：2026-06-02

## 结论

对话改图作为独立 ChatBot 产品入口接入，不改造中台主架构，不绕开现有业务能力 API。P0 底层仍复用 `agent.image_edit_assistant` Runtime：多轮对话理解、生成可确认建议、用户确认、调用 `image_edit` 业务 run。

## 边界

- ChatBot 可以调用中台白名单工具，当前只有 `business.image_edit`。
- ChatBot 不直接调用 OpenAI 图像接口、ComfyUI、KIE、火山或百度。
- GPT-5.5 / Responses API 只作为 planner 可选实现；未配置 Key 或调用失败时使用规则 planner 兜底。
- 高成本执行必须先进入 `awaiting_confirmation`，确认后才创建业务 run。
- 会话必须显式创建和显式续聊；`requestId` 只做同一租户/客户端下的创建幂等，不做跨会话自动合并。
- 只能确认当前会话最新方案；旧方案返回 `AGENT_PLAN_STALE`，确认中的方案返回 `AGENT_PLAN_CONFIRM_IN_PROGRESS`。
- 已执行方案重复确认返回原 `runId`，不重复创建下游图编辑任务。
- 最终结果仍通过 `/api/business/runs/get` 查询，资产、成本、质量和调用证据继续复用现有中台链路。

## 后端对象

| 表 | 用途 |
| --- | --- |
| `business_agent_sessions` | 一次 ChatBot 会话，保存底层 Agent key、状态、主图、租户/客户端、trace。 |
| `business_agent_messages` | 用户、助手、工具消息。 |
| `business_agent_plans` | 结构化方案卡片，保存意图、步骤、工具 payload、成本和风险。 |
| `business_agent_tool_calls` | ChatBot 调用中台能力的证据，关联 `runId`。 |

## API

| 接口 | 说明 |
| --- | --- |
| `POST /api/business/image-edit-chat/sessions` | 创建会话；可带首条 `message` 直接生成 ChatBot 回复和最新建议。 |
| `GET /api/business/image-edit-chat/sessions/{sessionId}` | 查询会话、消息、方案和工具调用。 |
| `POST /api/business/image-edit-chat/sessions/{sessionId}/messages` | 追加消息并生成新建议。 |
| `POST /api/business/image-edit-chat/sessions/{sessionId}/confirm` | 确认当前最新建议并提交 `image_edit` 业务 run。 |
| `POST /api/business/image-edit-chat/sessions/{sessionId}/plans/{planId}/confirm` | 严格确认指定方案版本；主要给高级调用方和回归测试使用。 |

## 会话设计

- 测评端或客户端要展示“新会话/当前会话”，主图切换时默认开启新会话，避免把新图挂在旧方案上下文下执行。
- 网络重试只复用带相同 `requestId` 的创建请求；追加消息和确认执行都必须显式带 `sessionId`。
- 每条新消息生成一个新建议，并更新 `latestPlanId`；默认确认接口确认当前最新建议。
- 确认接口先把方案置为 `confirming` 再调用业务 run，便于排查“提交中”与“下游失败”的分界。

## 测评端交互

入口与图编辑工作台拆分展示，但可互相协作：

1. 用户上传或粘贴主图。
2. 用户在 ChatBot 消息框里自然表达改图诉求。
3. ChatBot 以消息形式回复，并附带可执行建议卡，展示步骤、执行指令、成本、风险和 warnings。
4. 用户可继续追问，也可一键把建议应用到精确图编辑器，继续手动标注或补参考图。
5. 用户确认执行后，ChatBot 显示 `runId`、轮询状态和输出缩略图。

## 后续升级门槛

暂不引入 LangGraph 等重型框架。满足任一条件再评估：

- 单个 Agent 要连续执行 5 步以上。
- 中间需要多次暂停、人工复核、恢复和回滚。
- 需要多 Agent 分工，例如设计方案 Agent、质量评估 Agent、视频脚本 Agent。
- 需要把花纹提取、裂变、产品图、模特图、视频串成长流程。

届时可把当前 Runtime 的 session/plan/tool_call 表作为迁移基础，保留 API 和测评端交互不变。
