# 异步任务监控配置说明

## 概述
异步任务监控用于实时跟踪任务及积分状态，默认优先使用 WebSocket 推送（`/api/notify/v1/stream`），当连接不可用时自动回退到定时轮询。

## 功能说明
1. **WebSocket 推送**：接收后端 `task.status` 与 `wallet.points` 事件并分发给前端。
2. **轮询兜底**：在 WebSocket 断开或不支持的场景，继续使用 `useTaskListPolling` 的定时刷新。
3. **任务集合管理**：`taskDynamicCollectionManager.ts` 维护需要监控的任务 ID，新增/移除自动触发轮询策略调整。
4. **页面可见性检测**：隐藏页面时暂停轮询与推送，重新可见时恢复；支持用户活动触发即时刷新。
5. **事件回调**：`taskMonitoringEventSystem.ts`/`useTaskSummaryData` 负责将事件映射到 UI、通知提示等。

## 相关文件
1. `src/utils/taskDynamicCollectionManager.ts`：管理活跃任务集合与轮询节奏。
2. `src/utils/taskMonitoringEventSystem.ts`：定义事件回调与界面更新逻辑。
3. `src/hooks/useTaskSummaryData.ts`：消费任务事件并刷新列表，同时驱动轮询。
4. `src/hooks/useRealtimeNotifications.ts`：WebSocket 客户端，向 `podi:task-status` / `podi:wallet-points` 事件派发自定义事件。
5. `src/contexts/PointsContext.tsx`：监听积分事件并刷新统计、触发动画。

## 性能考虑
- WebSocket 可大幅减少轮询请求；若连接频繁断开，指数退避到 30s 内的重连周期。
- 轮询频率默认 1~3s，根据活跃任务自动调整；可通过 `alwaysPoll` 参数强制持续轮询。
- 事件处理使用轻量节流（500ms）避免短时间内多次触发全量刷新。

## WebSocket 集成指南
### 连接
- URL：`ws(s)://<API_BASE>/api/notify/v1/stream`，客户端通过 `hooks/useRealtimeNotifications` 建立连接。
- 重连：指数退避（1s 起，最大 30s），组件卸载时关闭连接。

### 消息格式
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
或
```json
{
  "type": "wallet.points",
  "payload": {
    "taskId": "tsk_123",
    "status": "released",
    "balance": 420
  }
}
```

### 前端处理
- `useRealtimeNotifications` 将消息派发为 `CustomEvent`：`podi:task-status` 和 `podi:wallet-points`（常量位于 `src/constants/events.ts`）。
- `useTaskSummaryData` 监听 `podi:task-status`，在 500ms 内节流刷新任务列表，必要时触发轮询。
- `PointsProvider` 监听 `podi:wallet-points`，调用 `fetchPointsStatistics` 更新余额并驱动动画。
- UI 可根据事件显示 toast/横幅，或结合 `NotificationContext` 自定义提示。

## 注意事项
1. 确保 `useRealtimeNotifications` 仅在顶层调用一次（`App.tsx` 中已处理），避免重复连接。
2. 自定义事件仅在浏览器环境可用；服务端渲染需判断 `typeof window !== 'undefined'`。
3. 如需禁用 WebSocket，可设置环境变量或在 Hook 中短路，此时仅依赖轮询机制。
4. 当引入身份鉴权后，记得为 WebSocket 携带 Token（可通过 Query/Headers 扩展 `useRealtimeNotifications`）。
