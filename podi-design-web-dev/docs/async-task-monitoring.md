# 异步任务监控配置说明

## 概述

异步任务监控功能用于实时跟踪和更新任务状态，提供更好的用户体验。默认优先使用 WebSocket 推送，在不可用时降级为轮询。

## 功能说明

### 异步任务监控功能

1. **WebSocket 推送**：优先连接后端 `/api/notify/v1/stream`，处理 `task.status` 与 `wallet.points` 事件。
2. **轮询兜底**：WebSocket 不可用或断线时，自动切换到定时轮询接口。
3. **页面可见性检测**：当页面可见时恢复推送/轮询，隐藏时暂停以节省资源。
4. **任务集合管理**：自动管理需要监控的任务ID集合，添加或移除任务ID。
5. **事件回调**：支持任务状态变化和任务列表更新的回调处理。

## 相关文件

以下文件包含与异步任务监控相关的代码和配置：

1. **taskDynamicCollectionManager.ts**: 管理任务集合与轮询定时器。
2. **taskMonitoringEventSystem.ts**: 负责事件回调和 UI 更新。
3. **NotificationClient.ts**（待新增）: 封装 WebSocket 连接、重连和消息分发。
4. **DashboardTaskList.tsx**: 初始化/清理监控系统，监听推送事件。

## 性能考虑

- WebSocket 推送避免了高频轮询；若连接断开将回退到轮询机制。
- 在大量任务同时进行时，客户端仍需控制渲染频率，可通过节流处理事件。
- 轮询频率已优化，尽量在 5s~15s 之间，根据活跃任务数量自动调整。

## 建议使用场景

### 适用场景

- 生产环境中需要实时反馈任务状态
- 用户需要及时了解任务完成情况
- 任务执行时间较长，用户可能离开页面后返回

## 注意事项

1. 监控功能自动管理任务集合，无需手动干预；但新增 WebSocket 时需要在 `useTaskMonitoring` 中确保连接唯一。
2. 当页面不可见时，监控功能会自动暂停推送（关闭 WebSocket）或停止轮询。
3. 若需禁用 WebSocket，可在配置中关闭或捕获连接错误后强制回落轮询。

## WebSocket 集成指南

### 连接配置
- URL：`${API_BASE_WS || API_BASE_HTTP.replace('http', 'ws')}/api/notify/v1/stream`
- 鉴权：目前为匿名调试接口，后续将携带 JWT 或 Query token。
- 重连策略：指数退避（初始 1s，最大 30s），重连成功后调用 `/api/notify/v1/replay`（待实现）或依赖服务端缓存。

### 消息格式
```json
{
  "type": "task.status",
  "payload": {"taskId": "tsk_123", "status": "processing", "progress": 40}
}
```
或
```json
{
  "type": "wallet.points",
  "payload": {"taskId": "tsk_123", "status": "deducted", "balance": 420}
}
```

### 前端处理建议
- 在 `taskMonitoringEventSystem` 中新增 `handleWebSocketEvent`，根据 `type` 更新任务列表或 PointsContext。
- 当 WebSocket 可用时，暂停轮询；若收到 `close`/异常事件，则重启轮询。
- UI 反馈：任务状态变化时触发 toast/动画；积分事件驱动 Points 动画/数值刷新。
