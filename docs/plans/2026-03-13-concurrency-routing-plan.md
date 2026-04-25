# Concurrency Routing Plan

> For Claude: REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 修正当前异步任务与 ComfyUI/KIE 并发控制，使系统行为符合既有业务约定：KIE 并发 10、ComfyUI 单机 10 且双机总承载 20，并按队列长短分流到更空闲的机器。

**Architecture:** 当前系统已经具备“按队列分流”的基础能力，但被三个问题削弱：全局异步 worker 过小、默认未完全启用 queue 分流、很多能力只有单机候选池。本方案不推翻现有结构，而是在现有 `AbilityTaskService`、`AbilityInvocationService`、`workflow_bindings`、`executors.yaml` 基础上，让“候选池 + 队列分流 + 单机上限保护”真正生效。

**Tech Stack:** FastAPI、SQLAlchemy、线程池、ComfyUI queue status、现有 executor/workflow/binding 配置体系。

---

## 1. 背景与当前问题

当前线上并发行为和约定不一致，主要体现在两点：

1. **异步任务全局总闸门太小**
- 当前 `ABILITY_TASK_MAX_WORKERS` 默认值为 `4`
- 结果是所有 `/api/ability-tasks` 先被全局 4 卡住
- 即使后面某些执行节点还有余量，任务也进不去

2. **ComfyUI 没有真正实现“双机总承载 20”**
- 当前单机限制逻辑是有的：每台机器最多 10 个 `queued + running`
- 但很多能力只有单机候选池，所以实际吃不到双机 20
- 虽然代码里已经有“按队列挑更空闲机器”的逻辑，但如果候选池只有 1 台，这个机制等于失效

3. **KIE 并发当前偏小**
- 现配置里 `executor_kie_market_default.max_concurrency = 4`
- 业务约定应改为 `10`

---

## 2. 目标状态

### 2.1 KIE
- KIE 单节点并发设置为 **10**
- 不再被全局 `ABILITY_TASK_MAX_WORKERS=4` 这种过小总闸门卡死

### 2.2 ComfyUI
- 每台服务器最多承接 **10 个 queued + running 任务**
- 两台服务器共同承接时，总可承载 **20 个**
- 新任务优先分配到：
  1. 队列更短的机器
  2. 若一样，则轮流分配
- 只有当候选池里的机器都满了，才拒绝新任务

### 2.3 路由约束
- 不是所有能力都自动双机分流
- 只有“确实能在两台机器都稳定执行”的能力，才能进入双机候选池
- 候选池必须可配置、可追溯

---

## 3. 推荐方案（已确认）

### 方案主线

采用：

**按能力候选池 + 按队列分流 + 按单机上限拒绝**

#### 核心原则

1. **总并发不再由 4 这个全局默认值决定**
2. **真正起作用的是每个平台/每台执行节点自己的并发规则**
3. **ComfyUI 只有在候选池里有多台机器时，才做分流**
4. **单机上限 10 继续保留**

---

## 4. 实现设计

### 4.1 调整全局异步 worker 的角色

**现状**
- `backend/app/core/config.py`
  - `ability_task_max_workers = 4`
- `AbilityTaskService.__init__`
  - `ThreadPoolExecutor(max_workers=ability_task_max_workers)`

**问题**
- 这个值现在变成了“真实吞吐上限”
- 它不应该比所有执行节点的总能力小那么多

**方案**
- 将 `ABILITY_TASK_MAX_WORKERS` 提高到一个更合理的值
- 它只作为“线程池资源保护”，不再成为业务并发主限制

**建议值**
- 起步建议：`20` 或 `24`
- 理由：
  - 至少能覆盖 ComfyUI 双机 20 的理论承载
  - 再给 KIE / 其他任务留一点空间

> 注意：这不是说系统永远同时执行 20+ 个真实上游请求，
> 真正是否放行，仍由每个 executor 的并发规则控制。

---

### 4.2 调整 KIE 节点并发

**文件**
- `config/executors.yaml`

**当前**
- `executor_kie_market_default.max_concurrency = 4`

**目标**
- 改成 `10`

**说明**
- 这符合当前业务约定
- KIE 自己是商业模型，和 ComfyUI 的“每机 10 队列保护”不是同一种机制
- 这里的 10 是我们平台侧对它的并发控制

---

### 4.3 启用 ComfyUI 队列分流

**现有代码**
- `AbilityInvocationService._pick_comfyui_executor_id`
- `AbilityInvocationService._pick_comfyui_executor_by_queue`
- `IntegrationTestService.get_comfyui_queue_status`

**现有逻辑能力**
- 能读每台 ComfyUI 当前队列
- 能选 `running + pending` 更少的机器
- 能在 tie 时做 round robin

**问题**
- 默认 `COMFYUI_ROUTE_BY_QUEUE=false`
- 很多能力没有真正的双机候选池

**方案**

1. 打开 queue-aware routing
- 设置 `COMFYUI_ROUTE_BY_QUEUE=true`

2. 保持 `COMFYUI_QUEUE_BATCH_SIZE=10`
- 这个值继续作为“优先池阈值”

3. 在多机候选池中启用：
- `routing_policy = queue`
- 或在 `auto + COMFYUI_ROUTE_BY_QUEUE=true` 下使用 queue 策略

---

### 4.4 定义“能力候选池”

这是方案里最关键的部分。

**不是所有 ComfyUI 能力都能自动进双机池。**

必须先确认：
- 两台机器都有对应节点
- 两台机器都有对应模型 / LoRA / 工作流依赖
- 两台机器对该能力可互相替代

**推荐表达方式**
- 优先使用 `Ability.metadata.allowed_executor_ids`
- 辅助使用 `required_tags`
- 必要时配合 `workflow_bindings`

#### 建议分层

1. **单机固定能力**
- 继续只给 1 台候选机器
- 不做双机分流

2. **双机可替代能力**
- 明确写候选池为两台机器
- 开启 queue 路由

---

## 5. 代码改动范围

### 必改
- `backend/app/core/config.py`
  - 调整 `ABILITY_TASK_MAX_WORKERS` 默认值
  - 确认 `COMFYUI_ROUTE_BY_QUEUE` 默认值或部署值

- `config/executors.yaml`
  - 将 KIE 并发改到 `10`
  - 保持两台 ComfyUI `max_concurrency=10`

- `backend/app/services/ability_invocation.py`
  - 核查 `_pick_comfyui_executor_id` 的候选池选择逻辑
  - 确保双机池时实际会走 queue 策略

### 可能需要改
- `backend/app/constants/abilities.py`
  - 为支持双机分流的 ComfyUI 能力补 `allowed_executor_ids` / `routing_policy`

- `backend/app/services/ability_task_service.py`
  - 复核 `count_pending_by_executor()` 是否与预期一致
  - 确认“队列满则拒绝”的逻辑是按单机 10 生效，而不是被其他全局逻辑提前卡死

### 文档同步
- `docs/comfyui-routing-technical.md`
- `docs/architecture.md`
- `docs/standards/issue-improvement-log.md`

---

## 6. 测试与验证方案

### 6.1 KIE 并发验证
- 连续提交 10 条 KIE 任务
- 预期：
  - 前 10 条能进入执行/排队
  - 不再因为全局 4 被过早卡住

### 6.2 ComfyUI 双机分流验证
- 选择一个明确支持双机的 ComfyUI 能力
- 连续提交 12~20 条任务
- 预期：
  - 两台机器都被分配到任务
  - 队列更短的机器优先吃新任务
  - 任一单机达到 10 后，不再继续压到这台
  - 两台都到 10 后，返回明确拒绝

### 6.3 队列查询验证
- 调：
  - `/api/admin/comfyui/queue-status`
  - `/api/admin/comfyui/queue-summary`
- 预期：
  - 单机和汇总数量与后台任务分布一致

### 6.4 回归验证
- 同步能力调用不受影响
- 异步任务不受影响
- 评测 workflow 不受影响
- Coze 回调型 workflow 不受影响

---

## 7. 风险与注意事项

### 风险 1：双机并不真正等价
- 如果两台机器依赖不一致，开启双机池会放大失败率
- 所以必须先确认哪些能力能进双机池，不能一刀切

### 风险 2：全局 worker 放大后，日志与轮询压力也会增大
- 所以后续最好配合做更好的轮询日志与诊断能力

### 风险 3：业务侧预期和当前绑定关系可能不一致
- 需要你们确认哪些 ComfyUI 能力真的允许双机混跑

---

## 8. 推荐落地顺序

### 第一步（低风险）
1. 提高 `ABILITY_TASK_MAX_WORKERS`
2. KIE 并发改到 10
3. 打开 `COMFYUI_ROUTE_BY_QUEUE`

### 第二步（关键）
4. 为可双机运行的 ComfyUI 能力补候选池
5. 验证实际是否按队列分流

### 第三步（收口）
6. 文档同步
7. 后台增加诊断/日志观测点

---

## 9. 当前已达成的方案结论

本次方案已经确认：

- KIE 并发目标：**10**
- ComfyUI 单机上限：**10**
- 两台 ComfyUI 总承载目标：**20**
- 分流策略：**优先分配到更空闲、队列更短的机器**
- 拒绝条件：**候选池内所有机器都达到单机上限**
- 关键前提：**只有真正双机可替代的能力才进入双机候选池**
