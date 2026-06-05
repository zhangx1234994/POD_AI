# Agent Runtime 回归矩阵

最后更新：2026-06-05

本文定义 Agent Runtime 的最低回归矩阵。当前落地点是 AI 改图助手，但规则面向后续可调用更多中台能力的 Agent。

核心原则：

- Agent 是独立能力，不是普通图编辑表单。
- 前端负责对话、图片预览、状态、历史和确认；后端负责会话、上下文、路由、schema、成本、Key、幂等和审计。
- 大模型可以协助判断意图，但不能授权最终工具调用；工具调用必须经过后端白名单、schema 校验、置信度、风险和用户确认。
- 回归不只看“能不能出图”，还要看续改、隔离、路由证据、错误契约、并发和观测链路。

## 1. 必测维度

| 维度 | 目标 |
| --- | --- |
| 会话状态 | 新会话、续聊、新任务隔离都可追溯 |
| 上下文压缩 | 历史约束能进入 working memory，不无限塞完整对话 |
| 资产状态 | 原图、上一轮输出、参考图和当前基准图清晰 |
| 能力路由 | 候选能力、拒绝原因、置信度和 routeReason 可见 |
| 工具控制 | 后端白名单和 schema 决定最终可调用能力 |
| 确认执行 | 高成本或真实执行必须先确认 |
| 幂等 | 网络重试、重复发送、重复确认不重复扣费或重复创建 run |
| 错误契约 | 缺参、低置信、旧方案、依赖失败、队列限制都有明确错误码 |
| 观测链路 | plan、tool call、runId、接口调用、结果和 OSS 回填能串起来 |

## 2. MVP Golden Cases

当前 AI 改图助手最低保留 5 组 golden cases。每次改 Agent 相关代码、planner、路由或前端对话流，都必须跑。

| 编号 | 案例 | 输入 | 期望 | 阻断条件 |
| --- | --- | --- | --- | --- |
| A1 | 首轮改图 | 有主图 + 明确改图目标 | 生成 plan，确认后创建一个 `image_edit` run，结果成功回填；`baseImageRole=source_image` | 没有 runId、重复创建 run、无结果图、无路由证据 |
| A2 | 二轮续改 | 在 A1 成功后继续说“基于刚才那张再...” | 默认基于上一轮成功输出；记录 `parentRunId`；`baseImageRole=previous_result` | 又拿原图改、丢失 parentRunId、结果沉底不可见 |
| A3 | 新任务隔离 | 点击新任务或换主图后发新诉求 | 新 session 或明确 task boundary；不带旧 working memory 的执行约束 | 新图继承旧图约束、旧会话 latestPlan 被污染 |
| A4 | 模糊意图追问 | 只有“改一下”“变好看”等低信息输入 | `requiresClarification=true` 或阻断确认；`missingFields` 可见；不创建下游 run | 低置信仍执行、创建 queued 脏任务、扣费 |
| A5 | requestId 幂等 | 同一 `sessionId + requestId` 重复追加消息或确认 | 返回同一 plan/run，不重复创建 | 重复 plan、重复 run、状态互相覆盖 |

## 3. 扩展回归矩阵

当 Agent 从只调用 `business.image_edit` 扩展到更多能力时，新增以下矩阵。

| 场景 | 期望路由 | 必查字段 | 说明 |
| --- | --- | --- | --- |
| 用户要求提取花纹 | `business.pattern_extract` | `targetAbility/rejectedAbilities/routeReason/confidence` | 必须确认源图可用，不能误路由到图编辑 |
| 用户要求生成裂变候选 | `business.fission` | `variationStrength/quality/size` | 需要说明候选数量和风格约束 |
| 用户要求做产品设计图 | `business.product_design` | `productType/material/style/scene` | 低信息时追问产品载体 |
| 用户要求出组图 | `business.product_image_set` | `viewAngles/count/layout` | 该能力未接入前必须明确不可执行或给候选方案 |
| 用户要求模特图 | `business.model_shot` | `modelStyle/pose/garmentMask` | 涉及人物和品牌风险时必须人工确认 |
| 用户要求推广视频 | `business.promo_video` | `duration/aspectRatio/storyboard` | 高成本多阶段能力必须分阶段确认 |

未接入能力不能由模型自由编造结果。返回策略只能是：

- 追问缺失信息。
- 告知当前能力未开放。
- 推荐已开放的相近能力，并等待用户确认。

## 4. 路由稳定性测试

每个可路由意图至少准备 3 条不同表达，连续运行 3 轮，检查路由是否稳定。

| 意图 | 表达样例 | 允许波动 | 失败判断 |
| --- | --- | --- | --- |
| 局部修改 | “把背景换浅一点”“去掉左上角瑕疵”“只改边缘” | 置信度可浮动，能力不能变 | 误路由到裂变/扩图 |
| 整体优化 | “更高级”“适合服装面料”“整体更干净” | 可进入追问或 image_edit | 无主图仍执行 |
| 继续上一轮 | “基于刚才那张”“再柔和一点”“上一版继续” | 必须基于 previous_result | 回到 source_image |
| 新任务 | “换这张图重新来”“新开一个任务” | 必须隔离上下文 | 继承旧任务约束 |

记录字段：

```text
caseId：
sessionId：
messageRequestId：
planId：
targetAbility：
confidence：
baseImageRole：
parentRunId：
requiresClarification：
missingFields：
routeReason：
rejectedAbilities：
结论：
```

## 5. 并发与幂等

| 测试 | 做法 | 期望 |
| --- | --- | --- |
| 同一消息重复提交 | 同一 `requestId` 连续提交 2-3 次 | 返回同一 plan |
| 不同消息快速提交 | 不同 `requestId` 并发提交 | 每条消息有独立 plan，latestPlan 只指向最后一条 |
| 重复确认 | 同一 plan 并发确认 2-3 次 | 只有一个 run，后续返回同一 runId 或确认中状态 |
| 确认旧方案 | 先生成 plan1，再生成 plan2，再确认 plan1 | 返回 `AGENT_PLAN_STALE` |
| 确认需追问方案 | 模糊输入后直接 confirm | 返回 `AGENT_PLAN_REQUIRES_CLARIFICATION`，无 run |

## 6. 失败路径

| 场景 | 期望错误码 | 副作用要求 |
| --- | --- | --- |
| 无会话 | `AGENT_SESSION_NOT_FOUND` | 不创建消息、plan、run |
| 无主图 | `AGENT_IMAGE_REQUIRED` 或追问 | 不创建下游 run |
| 旧方案确认 | `AGENT_PLAN_STALE` | 不创建 run |
| 需要追问 | `AGENT_PLAN_REQUIRES_CLARIFICATION` | 不创建 run |
| 确认中重复点击 | `AGENT_PLAN_CONFIRM_IN_PROGRESS` 或返回同一 run | 不创建第二个 run |
| 非法能力 | `AGENT_CAPABILITY_NOT_FOUND` | 不调用工具 |
| 下游业务提交失败 | 业务错误码 + Agent tool call failed | 保留 plan/tool trace |
| 队列满/并发限制 | 标准队列/并发错误码 | 可重试，不污染会话 |

所有预期 4xx 必须在验收报告中明确标注来源和 requestId，避免接口调用中心把预期错误路径误判为异常。

## 7. 前端交互验收

| 检查项 | 合格标准 |
| --- | --- |
| 图片可见 | 上传或粘贴主图后，用户在同一页面能看到主图 |
| 消息瀑布 | 用户消息、Agent 回复、建议卡、执行状态、结果图按时间进入消息流 |
| 执行状态 | 确认后显示正在出图、等待时长、runId 或排障编号 |
| 结果图 | 输出图作为 Agent 消息进入流，不沉底、不脱离上下文 |
| 新任务 | 新任务按钮清晰，旧任务可回看，新任务不污染旧上下文 |
| 路由证据 | 给高级用户/排障保留折叠区，展示基准图、路由、置信度、parentRunId |
| 示例引导 | 空态给可点击示例，不要求用户删除硬编码文字 |

## 8. 封版证据要求

Agent 相关版本封版报告必须包含：

- golden case 报告路径。
- 每个真实执行的 runId。
- `baseImageRole`、`parentRunId` 和 route evidence。
- 预期错误路径产生的 4xx 归因。
- 接口调用中心 summary。
- 业务 usage summary。
- 页面走查截图或记录。
- 保留风险和下一版预防动作。
