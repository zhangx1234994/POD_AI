# 能力平台队列与错误编号规范

> 目的：统一队列上限、报错方式、错误编号格式，避免业务接入时理解不一致。

---

## 1. 队列上限（统一标准）

- **ComfyUI 单台服务器队列上限：10**
  - 判断依据：`running + pending`（ComfyUI /queue/status）
  - 超过或等于 10：直接返回错误（不再提交任务）

- **商业模型（Volcengine/KIE）单台服务器等待上限：10**
  - 判断依据：PODI 内部 `AbilityTask` 队列（queued + running）
  - 超过或等于 10：直接返回错误（不再提交任务）

---

## 2. 错误编号规范

| 场景 | 错误编号 | 说明 |
| --- | --- | --- |
| ComfyUI 队列已满 | `Q1001` | 单台 ComfyUI 队列 >= 10 |
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
ERR|Q2001|COMMERCIAL_QUEUE_FULL(limit=10, current=11)
```

---

## 4. 错误提示策略

- **必须返回 HTTP 200**（避免 Coze 直接判为接口失败）
- **taskStatus = failed**
- **taskId 填写错误编号 + 说明**
- text/texts 可同步输出错误说明（非强制）

---

## 5. 维护位置

- 本规范文件：`docs/standards/queue-and-error-standards.md`
- 修改该标准时需同步更新：
  - Coze 插件返回逻辑
  - 业务接入文档
