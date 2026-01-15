import { useState, useEffect, useRef, useCallback } from 'react';

interface UseTaskListPollingParams {
  fetchTasks: (isPolling?: boolean) => Promise<any[] | void>;
  pollingEnabled?: boolean;
  checkInterval?: number; // 轮询间隔，默认1000ms
  // 如果为 true，则即使没有活跃任务也持续轮询
  alwaysPoll?: boolean;
  // 如果为 true，则在检测到用户活动（mousemove/keydown/visibility 等）时，
  // 先触发一次即时刷新，然后在短延迟后恢复周期轮询（避免双重立即请求）。
  enableActivityResume?: boolean;
}

export const useTaskListPolling = ({
  fetchTasks,
  pollingEnabled = true,
  checkInterval = 1000,
  alwaysPoll = false,
  // 如果为 true，则在检测到用户活动（mousemove/keydown/visibility 等）时，
  // 先触发一次即时刷新，然后在短延迟后恢复周期轮询（避免双重立即请求）。
  enableActivityResume = false,
}: UseTaskListPollingParams) => {
  const [isPolling, setIsPolling] = useState(false);
  const isPollingRef = useRef<boolean>(false);
  const pollingTimerRef = useRef<NodeJS.Timeout | null>(null);
  const isMountedRef = useRef(true);
  const retryCountRef = useRef(0);
  const MAX_RETRIES = 5;

  // 使用 ref 保存 fetchTasks，确保在轮询时总是调用最新的函数
  const fetchTasksRef = useRef(fetchTasks);
  useEffect(() => {
    fetchTasksRef.current = fetchTasks;
  }, [fetchTasks]);

  // 检查是否有活跃任务
  const hasActiveTasks = useCallback((tasks: any[]) => {
    if (!tasks || !Array.isArray(tasks) || tasks.length === 0) return false;

    return tasks.some((task) => {
      const status = task.originalStatus ?? task.status;
      // 检查是否为非终态
      // 终态: completed(2), failed(3), canceled(4)
      // 活跃: pending(0), processing(1), running

      if (typeof status === 'number') {
        return status === 0 || status === 1 || status === 100 || status === 200;
      }

      if (typeof status === 'string') {
        const s = status.toLowerCase();
        return ['pending', 'processing', 'running', 'queued', 'waiting'].includes(s);
      }

      return false;
    });
  }, []);

  // 清除定时器
  const clearPollingTimer = useCallback(() => {
    if (pollingTimerRef.current) {
      clearTimeout(pollingTimerRef.current);
      pollingTimerRef.current = null;
    }
  }, []);

  // helper to set polling state in both ref and state
  const setPollingState = useCallback((v: boolean) => {
    isPollingRef.current = v;
    setIsPolling(v);
  }, []);

  // 清除定时器
  // 执行轮询逻辑
  const executePolling = useCallback(async () => {
    if (!isMountedRef.current || !pollingEnabled) return;

    try {
      // 执行请求，标记为轮询请求
      const result = await fetchTasksRef.current(true);

      // 如果组件已卸载，停止后续逻辑
      if (!isMountedRef.current) return;

      const tasks = Array.isArray(result) ? result : [];

      // 重置重试计数
      retryCountRef.current = 0;

      // 检查是否需要继续轮询。若 `alwaysPoll` 为 true，则即使没有活跃任务也继续轮询。
      if (hasActiveTasks(tasks) || alwaysPoll) {
        setPollingState(true);
        pollingTimerRef.current = setTimeout(executePolling, checkInterval);
      } else {
        setPollingState(false);
      }
    } catch (error) {
      console.error('Task list polling failed:', error);

      // 错误重试机制
      if (retryCountRef.current < MAX_RETRIES) {
        retryCountRef.current++;
        pollingTimerRef.current = setTimeout(executePolling, checkInterval);
      } else {
        console.log('Max polling retries reached, stopping polling');
        setIsPolling(false);
      }
    }
  }, [pollingEnabled, checkInterval, hasActiveTasks, alwaysPoll]);

  // 启动轮询
  const startPolling = useCallback(() => {
    if (!pollingEnabled) return;

    // 避免重复启动
    if (isPollingRef.current) return;

    clearPollingTimer();
    setPollingState(true);
    retryCountRef.current = 0;
    executePolling();
  }, [pollingEnabled, clearPollingTimer, executePolling]);

  // 停止轮询
  const stopPolling = useCallback(() => {
    clearPollingTimer();
    setPollingState(false);
    retryCountRef.current = 0;
  }, [clearPollingTimer]);

  // 组件挂载/卸载处理
  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      clearPollingTimer();
    };
  }, [clearPollingTimer]);

  // 合并：监听页面可见性与用户活动
  // - 在页面不可见时暂停轮询并记录之前的轮询状态
  // - 在页面可见或检测到用户活动时：若启用了 activity resume，则触发一次即时刷新，
  //   并在短延迟后恢复周期轮询；否则如果之前在轮询则恢复轮询
  useEffect(() => {
    let resumeTimer: NodeJS.Timeout | null = null;
    let lastCalled = 0;
    const THROTTLE_MS = 2000;
    const POLLING_DELAY = Math.max(1000, checkInterval);
    let wasPollingBeforeHidden = false;

    const scheduleResume = () => {
      if (resumeTimer) clearTimeout(resumeTimer);
      resumeTimer = setTimeout(() => {
        try {
          if (!isPollingRef.current && pollingEnabled) startPolling();
        } catch (e) {
          // ignore
        }
      }, POLLING_DELAY);
    };

    const activityHandler = () => {
      try {
        if (isPollingRef.current) return;
        const now = Date.now();
        if (now - lastCalled < THROTTLE_MS) return;
        lastCalled = now;

        // 触发一次即时刷新（非轮询标记）
        try {
          void fetchTasksRef.current(false);
        } catch (e) {
          // ignore
        }

        scheduleResume();
      } catch (e) {
        // ignore
      }
    };

    const handleVisibilityChange = () => {
      if (document.hidden) {
        // 记录当前是否在轮询，便于在可见时恢复
        wasPollingBeforeHidden = isPollingRef.current;
        stopPolling();
        if (resumeTimer) {
          clearTimeout(resumeTimer);
          resumeTimer = null;
        }
      } else {
        // 页面可见：优先使用 activity resume 行为
        if (enableActivityResume) {
          activityHandler();
        } else if (wasPollingBeforeHidden) {
          try {
            startPolling();
          } catch (e) {
            // ignore
          }
        }
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);

    if (enableActivityResume) {
      const events: Array<keyof WindowEventMap> = ['mousemove', 'keydown', 'touchstart', 'scroll', 'pointerdown'];
      events.forEach((ev) => window.addEventListener(ev, activityHandler, { passive: true } as any));

      return () => {
        events.forEach((ev) => window.removeEventListener(ev, activityHandler as any));
        document.removeEventListener('visibilitychange', handleVisibilityChange);
        if (resumeTimer) clearTimeout(resumeTimer);
      };
    }

    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      if (resumeTimer) clearTimeout(resumeTimer);
    };
  }, [startPolling, stopPolling, enableActivityResume, checkInterval, pollingEnabled]);

  return {
    isPolling,
    startPolling,
    stopPolling,
  };
};
