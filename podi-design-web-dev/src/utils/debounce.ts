/**
 * 防抖函数工具
 */

// 存储防抖函数的映射
const debouncedFunctions = new Map<string, () => void>();

// 创建或获取防抖函数
export function getDebouncedFunction(
  key: string,
  func: () => void,
  delay: number = 500
): () => void {
  let timeoutId: NodeJS.Timeout | null = null;

  const debouncedFunc = () => {
    if (timeoutId) {
      clearTimeout(timeoutId);
    }

    timeoutId = setTimeout(() => {
      func();
    }, delay);
  };

  debouncedFunctions.set(key, debouncedFunc);
  return debouncedFunc;
}

// 触发防抖函数
export function triggerDebouncedFunction(key: string): void {
  const func = debouncedFunctions.get(key);
  if (func) {
    func();
  }
}

// 清除防抖函数
export function clearDebouncedFunction(key: string): void {
  debouncedFunctions.delete(key);
}

// 触发任务列表刷新的防抖函数
export function triggerRefreshTaskListDebounced(
  taskId?: string,
  params?: any,
  delay: number = 500
): void {
  // 构建事件详情
  const eventDetail: any = {
    useStoredParams: false, // 改为false，使用传入的参数而不是存储的参数
    forceRefresh: true, // 确保强制刷新，新任务显示在顶部
  };

  // 合并传入的参数
  if (params) {
    Object.assign(eventDetail, params);
  }

  // 如果有taskId，只添加到事件详情中，不直接添加到轮询管理器
  // 让轮询管理器在获取任务列表时自行处理任务ID的添加
  if (taskId) {
    eventDetail.taskId = taskId;
  }

  // 使用防抖函数
  const debouncedRefresh = getDebouncedFunction(
    'refreshTaskList',
    () => {
      // 触发刷新事件
      window.dispatchEvent(
        new CustomEvent('refreshTaskList', {
          detail: eventDetail,
        })
      );
    },
    delay
  );

  // 触发刷新
  debouncedRefresh();
}

// 创建refreshTrigger对象
export function createRefreshTrigger(taskId: string): { taskId: string; timestamp: number } {
  return {
    taskId,
    timestamp: Date.now(),
  };
}

export default {
  getDebouncedFunction,
  triggerDebouncedFunction,
  clearDebouncedFunction,
  triggerRefreshTaskListDebounced,
  createRefreshTrigger,
};