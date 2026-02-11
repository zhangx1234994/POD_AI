# ComfyUI 路由与排队机制（技术版）

> 适用对象：后端/平台/运维/工具链开发
> 本文描述实际代码中的路由顺序、策略分支、队列读取与并发门控。

---

## 1. 路由决策总览（实际代码顺序）

以下为当前服务端 `AbilityInvocationService._pick_comfyui_executor_id` 的真实流程：

1. **请求显式传 executorId** → 直接使用
2. **环境变量强制**：`COMFYUI_DEFAULT_EXECUTOR_ID`（必须 active & type=comfyui）
3. **Ability.metadata.allowed_executor_ids**
   - 过滤 active + tags
   - 按 routing_policy 选
   - 若为空且 `fallback_to_default=false` → 报错 `COMFYUI_EXECUTOR_NOT_MATCHED`
4. **WorkflowBinding by action**
   - 取最高 priority 的绑定
   - 再做 tags 过滤 + routing_policy 选
5. **历史兼容 fallback（少量 legacy workflow）**
   - `sifang_lianxu / huawen_kuotu` → `executor_comfyui_seamless_117`
   - `yinhua_tiqu / jisu_chuli / zhongsu_tisheng` → `executor_comfyui_pattern_extract_158`
6. **默认执行节点**（fallback_to_default=true 时）
   - 选择 type=comfyui 中 weight 最大的 active 节点

> 代码位置：`backend/app/services/ability_invocation.py`

---

## 2. Ability 路由相关 metadata 约定

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| allowed_executor_ids | list[str] | 允许的 ComfyUI 节点列表（最高优先级） |
| required_tags | list[str] / string | 节点必须包含的 tags（config.tags） |
| routing_policy | string | 路由策略：auto / queue / weight / round_robin / fixed |
| fallback_to_default | bool | 无匹配时是否回退默认节点 |
| workflow_key / action | string | 用于绑定/路由识别 |

> tags 取自 executor.config.tags（允许 string/list）

---

## 3. 路由策略（routing_policy）实现

| 策略 | 实现逻辑 |
| --- | --- |
| fixed | 固定取第一个候选（按 allowed_executor_ids 或 binding 顺序） |
| weight | 按 executor.weight 加权随机 |
| round_robin | 以 ability 为粒度轮询 |
| queue | 读取 ComfyUI queue 状态，取 running+pending 最小 |
| auto | 若 `COMFYUI_ROUTE_BY_QUEUE=true` 等同 queue；否则取第一个 |

关键配置：
- `COMFYUI_ROUTE_BY_QUEUE`：是否在 auto 时启用 queue 策略
- `COMFYUI_QUEUE_BATCH_SIZE`：queue 路由中“优先池”阈值（小于该值优先）

---

## 4. 排队机制（双层）

### 4.1 平台内并发门控
- 每个 executor 有 `max_concurrency`
- 超过并发后请求进入内部等待
- 等待超时（120s）返回 `429 EXECUTOR_BUSY`

实现位置：
- `AbilityInvocationService._dispatch_provider`

### 4.2 ComfyUI 自身队列
- 由 ComfyUI `/queue` / `/queue/status` 返回
- 路由策略为 queue 时会拉取此状态
- 取 `runningCount + pendingCount` 作为负载依据

实现位置：
- `IntegrationTestService.get_comfyui_queue_status`

---

## 5. 队列上限与超时策略（关键）

### 5.1 队列上限（平台侧保护）
- 平台会统计 **同一 executor 的 queued + running** 数量。
- 达到上限后直接拒绝新任务（默认 10），返回 `429` 与错误码 `Q1001`。
- 该上限是保护 ComfyUI 机器不被打爆的硬规则。

实现位置：
- `AbilityTaskService.enqueue`（`MAX_QUEUE_PER_EXECUTOR`）

### 5.2 ComfyUI 不做硬超时失败
- ComfyUI 是自建可观测服务，排队与执行时间可监控。  
- **超时仅代表“同步等待的轮询上限”**，不会把任务判失败。  
- 如果轮询超时但 ComfyUI 仍处于 queued/running，结果会返回 `status=running`，由后续轮询收敛。  

实现位置：
- `ComfyUIExecutorAdapter._poll_history` + `execute`（轮询超时返回 running）

### 5.3 第三方能力仍保留硬超时
- KIE/Volcengine/Baidu 等不可控，硬超时仍然保留。  
- 例如 `KIE_TASK_TIMEOUT_SECONDS` 超时后直接失败。  

配置位置：
- `backend/app/core/config.py`

---

## 6. 队列查询接口

### 6.1 Admin 接口
- 单台：`GET /api/admin/comfyui/queue-status?executorId=xxx`
- 汇总：`GET /api/admin/comfyui/queue-summary?executorIds=...`
  - 返回 `totalRunning / totalPending / totalCount / timestamp / servers[]`

### 6.2 Coze 工具箱接口
- `POST /api/coze/podi/comfyui/queue-summary`
  - body 可为空，可选 `executorIds`
  - 返回字段同上

> 注意：Coze schema 对类型严格，服务端保证 `queueMaxSize` 不为 null。

---

## 7. 返回结果中的 executor 信息

所有能力调用（Ability API / Coze 插件 / Admin 测试）都会在响应里携带：
- `executorId`：实际执行节点
- `baseUrl`：该节点的 ComfyUI 地址

用于链路追踪、性能判断、机器定位。

---

## 8. 兼容行为与注意事项

- 若 `fallback_to_default=false` 且无匹配节点 → 直接报错
- WorkflowBinding 只对 action 生效，且只取最高 priority
- allowed_executor_ids 优先级高于 binding
- 当前 Workflow metadata 的 allowed_executor_ids 仅作为配置存储
  - 运行期仍以 Ability metadata / Binding 为准（后续可统一）

---

## 9. 推荐配置模板

### 9.1 Executor（示例）
```json
{
  "type": "comfyui",
  "base_url": "http://117.50.80.158:8079",
  "weight": 2,
  "max_concurrency": 2,
  "config": {
    "tags": ["gpu:4090", "region:hz", "comfyui-158"]
  }
}
```

### 9.2 Ability metadata（示例）
```json
{
  "routing_policy": "queue",
  "allowed_executor_ids": ["executor_comfyui_pattern_extract_158"],
  "required_tags": ["gpu:4090"],
  "fallback_to_default": true,
  "workflow_key": "yinhua_tiqu",
  "action": "pattern_extract"
}
```

---

如需补充：
- 路由流程图（mermaid）
- 绑定优先级与路由案例
- API 返回结构样例
请直接告诉我。
