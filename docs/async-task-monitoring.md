# 异步任务 & 能力监控说明

> 覆盖传统任务 (`/api/tasks`) 与 AbilityTask (`/api/ability-tasks`) 的监听、轮询与 UI 联动策略。版本：2026-01-15。

## 1. 概述

监控目标：
- 实时获取 AbilityTask `queued/running/succeeded/failed` 状态；
- 同步能力调用（`/api/abilities/{id}/invoke`）结束后刷新日志/成本；
- 捕获积分冻结/释放事件；
- 感知 ComfyUI 队列、能力日志等辅助信号。

策略：优先 WebSocket (`/api/notify/v1/stream`)，无法使用时回退到轮询（任务 1~3s，AbilityTask 1~5s，自适应调节）。

## 2. 功能说明
1. **WebSocket 推送**：后端广播 `task.status`、`ability-task.status`、`wallet.points`，必要时扩展为 `ability-log.created`。
2. **轮询兜底**：`useTaskListPolling`、`useAbilityTaskPolling` 在 WS 断开或浏览器不支持时接管；滚动窗口内仅对活跃任务请求。
3. **集合管理**：`taskDynamicCollectionManager.ts`、`abilityTaskCollectionManager.ts` 维护活跃 ID，新增/删除自动调节轮询节奏与暂停策略。
4. **页面可见性**：`useTaskSummaryData` & `useAbilityTaskPolling` 监听 `visibilitychange`，隐藏页面暂停轮询 + WS，重新可见时触发立即刷新。
5. **日志同步**：管理端能力详情页基于 `logId` 高亮新记录，失败/成功都会调用 `fetchAbilityLogs`，展示 Raw Response/成本。

## 3. 相关文件
1. `src/utils/taskDynamicCollectionManager.ts`：传统任务集合及节流策略。
2. `src/utils/abilityTaskCollectionManager.ts`：AbilityTask 集合、缓存、上次更新时间记录。
3. `src/utils/taskMonitoringEventSystem.ts`：封装事件派发（`podi:task-status`、`podi:ability-task-status`、`podi:wallet-points`）。
4. `src/hooks/useTaskSummaryData.ts`：消费任务事件，驱动列表与轮询。
5. `src/hooks/useAbilityTaskPolling.ts`：AbilityTask 专用 Hook，负责轮询 + 成功/失败回调。
6. `src/hooks/useRealtimeNotifications.ts`：WebSocket 客户端，处理认证、重连、事件节流。
7. `src/contexts/PointsContext.tsx`：监听积分事件，刷新余额并触发动画。

## 4. 性能考虑
- WebSocket 重连采用指数退避（1s → 30s），失败超过阈值后切换为纯轮询，待下一次手动刷新再尝试重连。
- AbilityTask 轮询间隔：活跃任务 <3 ⇒ 1s；3~10 ⇒ 2s；>10 ⇒ 5s，并在完成后立即移除。
- 所有事件经 500ms 节流后推送到 UI，避免密集刷新；滚动窗口中只刷新最近 N 条记录。

## 5. WebSocket 集成

### 连接
- URL：`ws(s)://<API_BASE>/api/notify/v1/stream`
- Header：`Authorization: Bearer <accessToken>`，`useRealtimeNotifications` 已封装。
- 重连：指数退避，组件卸载或 token 失效时主动关闭。

### 消息格式
```json
{
  "type": "ability-task.status",
  "payload": {
    "taskId": "abt_123",
    "abilityId": "comfyui_yinhua_tiqu",
    "status": "running",
    "logId": 4567,
    "executorId": "executor_comfyui_pattern_extract_158",
    "updatedAt": "2026-01-15T11:32:00Z"
  }
}
```
或
```json
{
  "type": "task.status",
  "payload": {
    "taskId": "tsk_123",
    "status": "processing",
    "progress": 40,
    "points": 50
  }
}
```
以及
```json
{
  "type": "wallet.points",
  "payload": {
    "taskId": "abt_123",
    "status": "released",
    "balance": 420
  }
}
```

### 前端处理
- `useRealtimeNotifications` 将消息派发为 `CustomEvent`：`podi:task-status`、`podi:ability-task-status`、`podi:wallet-points`（常量位于 `src/constants/events.ts`）。
- `useTaskSummaryData` 监听传统任务事件，`useAbilityTaskPolling`/`AbilityTaskContext` 监听 AbilityTask 事件，必要时触发立即轮询以获取最新 `resultPayload`。
- `PointsProvider` 监听积分事件并更新余额。
- 管理端 Ability Logs 抽屉通过 `logId` 匹配最新记录，实时 highlight。

## 6. 注意事项
1. `useRealtimeNotifications` 仅在顶层调用一次（`App.tsx` 中已处理），避免重复连接。
2. SSR 环境需判断 `typeof window !== 'undefined'` 后再注册事件监听。
3. 可以通过环境变量禁用 WebSocket（`VITE_DISABLE_WS=true`），此时仅依赖轮询。
4. AbilityTask 对 ComfyUI 的排队非常敏感，建议同时展示 `/api/admin/comfyui/queue-status` 结果以提升可见性。
5. 对接外部系统时，可监听 AbilityTask 回调（`callbackUrl`）并在 UI 中附带 traceId，便于跨系统追踪。
