# 能力平台队列与错误编号规范

> 目的：统一队列上限、报错方式、错误编号格式，避免业务接入时理解不一致。

---

## 1. 队列上限（统一标准）

- **ComfyUI 单台服务器队列上限：10**
  - 判断依据：`running + pending`（ComfyUI /queue/status）
  - 路由选择时还必须计入中台内部已选中该执行节点但尚未进入 ComfyUI `/queue` 的 `queued` 任务，避免突发请求集中打到同一台空队列机器。
  - 队列诊断必须同时展示 ComfyUI 侧队列和中台内部任务队列；如果中台有待下发任务但 ComfyUI 仍有空闲容量，应标记 `COMFYUI_FEED_GAP`。
  - 如果中台显示执行中但 ComfyUI 队列为空，应标记 `COMFYUI_BACKEND_RUNNING_NOT_VISIBLE`，优先排查下发、promptId 记录和结果回填。
  - 若能力已声明多个兼容执行节点并使用 `auto/queue/round_robin/weight` 策略，`COMFYUI_DEFAULT_EXECUTOR_ID` 不能压过该多节点路由，只能作为单节点应急/固定能力的兜底。
  - 超过或等于 10：直接返回错误（不再提交任务）

- **商业模型（Volcengine/KIE）单台服务器等待上限：10**
  - 判断依据：PODI 内部 `AbilityTask` 队列（queued + running）
  - 超过或等于 10：直接返回错误（不再提交任务）

---

## 2. 错误编号规范

| 场景 | 错误编号 | 说明 |
| --- | --- | --- |
| ComfyUI 队列已满 | `Q1001` | 单台 ComfyUI 队列 >= 10 |
| ComfyUI 执行器不可用 | `Q1002` | 没有可用且兼容的 ComfyUI 节点，或已选节点不可连通且无可切换节点 |
| 商业模型队列已满 | `Q2001` | 单台商业模型队列 >= 10 |

---

## 3. Coze 返回格式要求（重要）

> **Coze 侧统一读取 `taskId` 字段**，因此所有队列类错误必须写入 `taskId`。

### 3.1 错误 taskId 格式
```
ERR|<错误编号>|<错误说明>
```

### 3.2 示例
```
ERR|Q1001|COMFYUI_QUEUE_FULL(limit=10, current=12)
ERR|Q1002|COMFYUI_EXECUTOR_UNAVAILABLE: executor_x 当前不可连通，且没有其他兼容节点
ERR|Q2001|COMMERCIAL_QUEUE_FULL(limit=10, current=11)
```

---

## 4. 错误提示策略

- **必须返回 HTTP 200**（避免 Coze 直接判为接口失败）
- **taskStatus = failed**
- **taskId 填写错误编号 + 说明**
- text/texts 可同步输出错误说明（非强制）

`Q1002` 不是队列满。调用方收到后应把任务视为提交失败，优先检查节点健康、能力绑定、路由候选和短时网络波动，不要进入正常轮询。

---

## 5. 维护位置

- 本规范文件：`docs/standards/queue-and-error-standards.md`
- **错误契约总规范**：`docs/standards/error-contract.md`
- **错误码总表**：`docs/standards/error-catalog.md`
- 修改该标准时需同步更新：
  - Coze 插件返回逻辑
  - 业务接入文档
  - 错误码总表
