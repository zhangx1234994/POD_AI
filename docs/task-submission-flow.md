# 任务提交与交互事件流程

本文档详细描述了PODI设计平台中任务的提交流程、状态管理以及用户交互事件的处理机制。

## 1. 任务提交流程概述

在PODI设计平台中，任务提交流程主要包括以下几个关键环节：

1. **任务生成**：创建新的任务ID
2. **参数准备**：收集任务所需的工作流参数
3. **API调用**：提交任务到后端服务
4. **状态反馈**：显示任务提交成功提示
5. **列表刷新**：更新任务列表显示

## 2. 核心组件与功能

### 2.1 DashboardTaskList组件

`DashboardTaskList`是管理任务列表显示、任务操作和状态展示的核心组件。

#### 主要功能

- 显示用户的任务列表（支持分页）
- 展示任务状态（等待中、处理中、成功、失败、取消）
- 提供任务操作（预览、下载、重绘）
- 响应任务状态更新

#### 任务状态定义

```typescript
type TaskStatusType = 'completed' | 'processing' | 'pending' | 'failed' | 'canceled';
```

## 3. 任务提交实现细节

### 3.1 重绘任务提交流程

当用户点击"重绘"按钮时，触发以下流程：

1. **参数校验**：检查是否已有重绘任务在执行，验证任务是否包含workflowParams
2. **任务ID生成**：使用`generateTaskId()`生成新的任务ID
3. **参数准备**：整理重绘所需的参数，包括action、userId、原taskId、新taskId和workflowParams
4. **API调用**：调用`rerunTask()`函数提交重绘任务
5. **结果处理**：
   - 成功：设置当前任务ID并显示成功对话框，刷新任务列表
   - 失败：显示错误提示信息

### 3.2 核心代码实现

#### 重绘任务处理函数

```typescript
const handleRegenerate = async (task: Task, e?: any): Promise<void> => {
  e?.stopPropagation();
  
  if (isRegenerating) {
    toast.error('正在重绘中，请稍候');
    return;
  }
  
  if (!task.workflowParams) {
    toast.error('缺少重绘参数，无法重绘');
    return;
  }
  
  try {
    setIsRegenerating(true);
    const userId = getUserId();
    const newTaskId = generateTaskId();
    
    // 处理特殊的action类型
    let action = task.action || '';
    if (action === 'outpaint' && task.workflowParams?.outpaintMode) {
      action = task.workflowParams.outpaintMode;
    }
    
    const result = await rerunTask(
      action,
      userId,
      task.id,
      newTaskId,
      task.workflowParams
    );
    
    if (result.success) {
      // 设置当前任务ID并显示成功提示
      setCurrentTaskId(newTaskId);
      setShowSuccessDialog(true);
      // 直接刷新任务列表以显示新任务
      refreshData();
    } else {
      toast.error(result.message || '重绘失败，请稍后重试');
    }
  } catch (error) {
    console.error('重绘失败:', error);
    toast.error('重绘失败，请稍后重试');
  } finally {
    setIsRegenerating(false);
  }
};
```

#### 任务提交API调用

```typescript
export async function rerunTask(
  action: string,
  userId: string,
  originalTaskId: string,
  newTaskId: string,
  workflowParams?: any
): Promise<{ success: boolean; message?: string }> {
  try {
    // 构建重绘请求参数
    const payload = {
      userId,
      originalTaskId,
      taskId: newTaskId,
      action,
      workflowParams
    };
    
    // 调用重绘接口
    const response = await http.post(`/image-regenerate`, payload);
    
    return { success: true };
  } catch (error) {
    console.error('提交重绘任务失败:', error);
    return { success: false, message: '重绘失败，请稍后重试' };
  }
}
```

## 4. 后端任务调度与执行

> 详见 `docs/ai-integration-management.md`，此处强调与提交流程紧密相关的环节，方便前端联调。

1. **调度入口**：`TaskDispatcherService` 会拉取 `status in (pending, queued)` 的任务（默认 5 条），依据 `workflow_bindings` + `executors` 的配置挑选可用节点。开发阶段可手动调用 `POST /api/tasks/v1/dispatch?limit=5` 触发；上线后接 Celery/定时任务。
2. **运行状态**：命中绑定后任务会被标记为 `running` 并写入 `task_events`，执行器适配层（当前为 `MockExecutorAdapter`）会将 `workflow.definition + input_payload` 组合后“执行”，同步返回结果。
3. **成功回写**：任务成功后写入 `result_payload`（包括执行器信息、预览图等），状态置为 `completed`，并调用 `wallet_service.confirm` 扣减冻结积分，再通过 `notify_service.broadcast` 推送 `task.status` 与 `wallet.points` 事件，前端仪表盘与任务中心即可更新。
4. **失败/阻塞处理**：若找不到可用绑定或执行失败，任务状态将被标记为 `blocked`/`failed`，`wallet_service.release` 会还原积分，并同样推送通知，方便用户及时处理配置问题。

在前端页面测试时，只需确保存在 `workflow + executor (type=mock, status=active) + binding(enabled=true)`，然后提交任务并调用 `dispatch` 接口即可看到状态流转。

## 5. 用户交互事件

### 4.1 主要交互事件处理

#### 任务点击

- 点击已完成的任务卡片或缩略图可查看任务详情预览
- 实现代码：
  ```typescript
  const handleTaskClick = (task: Task, e?: any): void => {
    if (task.status !== 'completed') return;
    setSelectedTask(task);
    setShowPreview(true);
  };
  ```

#### 任务下载

- 点击"下载"按钮可下载任务结果图片
- 实现代码：
  ```typescript
  const handleDownload = async (task: Task, e?: any): Promise<void> => {
    if (onDownload) {
      onDownload(task);
      return;
    }
    
    const url = task.imgUrl || task.imageUrl || task.thumbnail || '';
    if (!url) {
      toast.error('没有可下载的图片');
      return;
    }
    
    try {
      // 解析真实图片URL并触发下载
      // ...
    } catch (error) {
      console.error('下载失败:', error);
      toast.error('下载失败，请稍后重试');
    }
  };
  ```

#### 任务刷新

- 支持手动刷新和自动刷新
- 实现代码：
  ```typescript
  const refreshData = useCallback(() => {
    // 防止频繁刷新
    const now = Date.now();
    if (now - lastRefreshTimeRef.current < 1000) {
      return;
    }
    lastRefreshTimeRef.current = now;
    
    debouncedRefresh(() => {
      fetchTasks();
    }, 300);
  }, [fetchTasks, debouncedRefresh]);
  ```

### 4.2 交互反馈

#### 成功对话框

任务提交成功后，会显示`SuccessDialog`组件提供反馈：

- 显示任务ID和状态信息
- 提供倒计时自动关闭功能（默认3秒）
- 可选择继续提交新任务

#### 状态指示

- 使用Badge组件显示任务状态（成功、处理中、等待中、失败、取消）
- 处理中的任务显示进度条
- 使用颜色编码区分不同状态

## 6. 任务状态管理

### 5.1 Reducer模式

使用reducer模式管理任务数据状态：

```typescript
const taskReducer = (state: TaskDataState, action: TaskActionType): TaskDataState => {
  switch (action.type) {
    case 'SET_TASKS':
      return { tasks: action.payload.tasks || [], version: state.version + 1, hasMore: action.payload.hasMore ?? false };
    case 'UPDATE_TASK':
      return { ...state, tasks: state.tasks.map(task => task.id === action.payload.id ? action.payload : task), version: state.version + 1 };
    case 'ADD_TASKS':
      // 添加新任务，支持去重和前置/后置添加
      // ...
    case 'UPDATE_TASKS':
      return { ...state, tasks: Array.isArray(action.payload) ? action.payload : [], version: state.version + 1 };
    default:
      return state;
  }
};
```

### 5.2 数据获取与刷新机制

- 分页加载任务数据
- 防抖处理刷新请求，避免频繁调用API
- 监听外部`refreshTrigger`变化，实现组件间的联动更新

## 7. 代码优化建议

### 6.1 性能优化

- **图片URL处理优化**：目前多处重复解析图片URL的逻辑，可以抽离为统一的工具函数
- **状态管理优化**：考虑使用状态管理库（如Redux或Zustand）统一管理任务状态，减少props drilling
- **内存优化**：实现图片URL的缓存机制，避免重复解析和请求

### 6.2 代码结构优化

- **组件拆分**：将`DashboardTaskList`拆分为更小的组件（如`TaskCard`、`TaskPreview`等）
- **错误处理增强**：实现更细粒度的错误处理，针对不同API错误提供更具体的反馈
- **类型定义完善**：增强TypeScript类型定义，特别是API响应数据的类型

### 6.3 用户体验优化

- **任务状态实时更新**：实现WebSocket连接或轮询机制，实时更新任务状态
- **批量操作支持**：添加批量下载、批量取消等功能
- **加载状态优化**：为所有异步操作提供明确的加载状态指示

## 8. 安全考虑

- 任务ID生成使用随机字符串，避免可预测性
- 后端接口调用使用统一的HTTP工具，便于添加认证和错误处理
- 图片URL处理进行了异常捕获，避免页面崩溃

## 9. 总结

PODI设计平台的任务提交流程采用了清晰的组件化结构，通过React Hooks管理状态和副作用，使用Reducer模式处理复杂的状态更新逻辑。用户交互事件处理遵循了React最佳实践，提供了良好的用户反馈机制。

通过优化建议的实施，可以进一步提升代码质量、性能和用户体验，使整个任务管理流程更加高效和稳定。
