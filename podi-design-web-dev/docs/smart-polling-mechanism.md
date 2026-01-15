# 智能轮询机制详细文档

## 概述

本文档详细介绍了项目中实现的智能轮询机制，该机制用于高效监控异步任务状态，同时优化资源使用和用户体验。智能轮询系统由三个核心组件构成：智能轮询管理器、任务管理器和任务动态集合管理器。

## 核心组件

### 1. 智能轮询管理器 (SmartPollingManager)

**文件位置**: `src/utils/smartPollingManager.ts`

智能轮询管理器是整个轮询系统的核心，负责动态调整轮询间隔、管理轮询状态以及处理各种页面状态变化。

#### 主要功能

1. **动态轮询间隔调整**
   - 基于高优先级任务数量和连续失败次数自动调整轮询频率
   - 三种轮询策略：
     - 快速间隔：5秒（有高优先级任务时）
     - 退避策略：失败次数越多，间隔越长（最大30秒）
     - 基础间隔：10秒（默认情况）

2. **智能状态管理**
   - 页面可见性检测：页面不可见时暂停轮询
   - 用户交互检测：用户活跃时暂停轮询
   - 防抖动控制：避免频繁启停轮询

3. **资源管理**
   - 自动清理资源，防止内存泄漏
   - 提供全局禁用/启用轮询的静态方法

#### 关键方法

- `calculatePollingInterval()`: 计算动态轮询间隔
- `executePolling()`: 执行轮询逻辑
- `triggerImmediatePoll()`: 立即触发一次轮询
- `updateConfig()`: 更新轮询配置
- `startPolling()`/`stopPolling()`: 启动/停止轮询
- `cleanup()`: 清理资源

### 2. 任务管理器 (TaskManager)

**文件位置**: `src/utils/taskManager.ts`

任务管理器负责维护活跃任务集合，并与智能轮询管理器协作，提供任务状态更新和轮询配置功能。

#### 主要功能

1. **活跃任务管理**
   - 维护当前活跃任务ID集合
   - 添加/移除任务时自动启停轮询

2. **轮询配置管理**
   - 提供默认轮询配置（基础10秒/快速5秒/慢速20秒）
   - 支持动态更新轮询参数

3. **页面类型管理**
   - 区分不同页面类型的轮询需求
   - 为不同页面构建特定的刷新参数

#### 关键方法

- `initializeActiveTasks()`: 初始化活跃任务集合并启动轮询
- `addTaskId()`/`removeTaskId()`: 添加/移除任务ID
- `initializeSmartPolling()`: 初始化智能轮询管理器
- `pollingCallback()`: 轮询回调函数
- `buildPageSpecificRefreshParams()`: 构建页面特定刷新参数

### 3. 任务动态集合管理器 (TaskDynamicCollectionManager)

**文件位置**: `src/utils/taskDynamicCollectionManager.ts`

任务动态集合管理器提供另一种任务监控方式，使用固定间隔监控任务状态，并与智能轮询管理器协同工作。

#### 主要功能

1. **任务状态监控**
   - 使用15秒固定间隔监控任务状态
   - 维护状态为PENDING(0)和RUNNING(1)的任务ID集合

2. **页面可见性处理**
   - 监听页面可见性变化
   - 页面不可见时自动暂停监控

3. **与智能轮询管理器协作**
   - 活跃任务为空时通过事件通知智能轮询管理器
   - 支持立即触发监控功能

#### 关键方法

- `initializePageVisibilityListener()`: 初始化页面可见性监听
- `addTaskId()`/`removeTaskId()`: 管理任务ID
- `executeMonitoring()`: 执行监控逻辑
- `triggerImmediateMonitoring()`: 立即执行监控
- `cleanup()`: 清理资源

## 组件集成方式

### DashboardTaskList组件

**文件位置**: `src/components/DashboardTaskList.tsx`

```typescript
// 初始化智能轮询管理器
smartPollingManager.initialize({
  pollingCallback: async () => {
    // 轮询回调逻辑
  },
  userId: user.id,
  operationParams: {},
  pageType: 'dashboard',
  maxInterval: 15000, // 最大15秒
  minInterval: 5000,  // 最小5秒
  enableVisibilityCheck: true,
  enableUserActivityCheck: true
});

// 监听轮询状态变化
const handlePollingStatusChange = (isActive: boolean) => {
  // 更新UI状态
};

// 监听任务列表刷新事件
const handleTaskListRefresh = () => {
  // 刷新任务列表
};

// 组件卸载时清理资源
useEffect(() => {
  return () => {
    smartPollingManager.stopPolling();
    // 其他清理逻辑
  };
}, []);
```

### AIToolsPageV2组件

**文件位置**: `src/components/AIToolsPageV2.tsx`

```typescript
// 初始化智能轮询
const initializeSmartPolling = useCallback(() => {
  const pollingCallback = async () => {
    // 构建请求参数
    const params = {
      userId: user.id,
      ...refreshParams
    };
    
    // 获取任务状态
    const response = await getTaskStatus(params);
    
    // 更新活跃任务集合
    if (response.data && response.data.activeTaskIds) {
      setActiveTaskIds(new Set(response.data.activeTaskIds));
    }
    
    // 触发刷新事件
    window.dispatchEvent(new CustomEvent('refreshTaskList', {
      detail: { pageType: 'drawing-tool' }
    }));
  };

  smartPollingManager.initialize({
    pollingCallback,
    userId: user.id,
    operationParams: refreshParams,
    pageType: 'drawing-tool',
    maxInterval: 8000, // 最大8秒
    minInterval: 1500, // 最小1.5秒
    enableVisibilityCheck: true,
    enableUserActivityCheck: true
  });
}, [user.id, refreshParams]);
```

## 轮询策略

### 动态间隔调整

智能轮询系统根据以下因素动态调整轮询间隔：

1. **高优先级任务**
   - 当存在高优先级任务时，使用快速间隔（5秒）
   - 确保关键任务及时更新状态

2. **连续失败次数**
   - 连续失败时采用退避策略
   - 失败次数越多，轮询间隔越长（最大30秒）
   - 避免对服务器造成过大压力

3. **页面状态**
   - 页面不可见时暂停轮询
   - 用户活跃时暂停轮询
   - 页面重新可见或用户不活跃时恢复轮询

### 资源优化

1. **防抖动控制**
   - 使用防抖机制避免频繁启停轮询
   - 减少不必要的资源消耗

2. **全局控制**
   - 提供全局禁用/启用轮询的静态方法
   - 便于在特定场景下统一控制轮询行为

3. **资源清理**
   - 组件卸载时自动清理轮询资源
   - 防止内存泄漏和无效请求

## 最佳实践

1. **组件集成**
   - 在组件挂载时初始化轮询
   - 在组件卸载时清理轮询资源
   - 监听轮询状态变化并更新UI

2. **错误处理**
   - 在轮询回调中添加适当的错误处理
   - 避免因单个请求失败影响整个轮询系统

3. **性能优化**
   - 合理设置最大和最小轮询间隔
   - 避免过于频繁的轮询请求
   - 使用页面可见性和用户活动检测减少无效请求

4. **状态管理**
   - 保持活跃任务集合的准确性
   - 及时移除已完成或失败的任务
   - 避免无效任务影响轮询频率

## 故障排除

### 常见问题

1. **轮询未启动**
   - 检查是否正确初始化智能轮询管理器
   - 确认活跃任务集合是否非空
   - 验证轮询配置参数是否正确

2. **轮询过于频繁**
   - 检查最小轮询间隔设置
   - 确认是否有任务持续处于高优先级状态
   - 验证退避策略是否正常工作

3. **轮询停止工作**
   - 检查页面可见性状态
   - 确认是否有全局禁用轮询的设置
   - 验证轮询回调中是否有未捕获的异常

### 调试技巧

1. 使用浏览器开发者工具监控网络请求
2. 检查控制台是否有轮询相关的错误日志
3. 使用`smartPollingManager.getStatus()`获取当前轮询状态
4. 监听`pollingStatusChanged`事件了解轮询状态变化

## 总结

智能轮询机制通过动态调整轮询间隔、智能状态管理和资源优化，实现了高效的任务状态监控，同时保证了良好的用户体验和系统性能。三个核心组件协同工作，提供了灵活、可靠的轮询解决方案，适用于各种异步任务监控场景。

正确使用和配置智能轮询系统，可以显著提升应用响应速度，减少服务器负载，并为用户提供更加流畅的交互体验。