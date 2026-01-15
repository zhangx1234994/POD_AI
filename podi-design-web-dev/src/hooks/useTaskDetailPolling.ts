import { useState, useEffect, useRef, useCallback } from 'react';

interface UseTaskDetailPollingParams {
  taskId: string;
  fetchDetail: (isPolling?: boolean) => Promise<string | null>;
  pollingEnabled?: boolean;
  checkInterval?: number;
}

export const useTaskDetailPolling = ({
  taskId,
  fetchDetail,
  pollingEnabled = true,
  checkInterval = 1000,
}: UseTaskDetailPollingParams) => {
  const [isPolling, setIsPolling] = useState(false);
  const isPollingRef = useRef<boolean>(false);
  const pollingTimerRef = useRef<NodeJS.Timeout | null>(null);
  const isMountedRef = useRef(true);
  const retryCountRef = useRef(0);
  const MAX_RETRIES = 5;

  const fetchDetailRef = useRef(fetchDetail);
  useEffect(() => {
    fetchDetailRef.current = fetchDetail;
  }, [fetchDetail]);

  const clearPollingTimer = useCallback(() => {
    if (pollingTimerRef.current) {
      clearTimeout(pollingTimerRef.current);
      pollingTimerRef.current = null;
    }
  }, []);

  const executePolling = useCallback(async () => {
    if (!isMountedRef.current || !pollingEnabled || !taskId) return;

    isPollingRef.current = true;
    if (!isPolling) setIsPolling(true);

    try {
      // 获取最新的状态
      const status = await fetchDetailRef.current(true);

      if (!isMountedRef.current) return;

      retryCountRef.current = 0;

      // 判断是否活跃
      const hasActive = status && ['pending', 'running'].includes(status.toLowerCase());

      if (hasActive) {
        // 继续轮询
        isPollingRef.current = true;
        setIsPolling(true);
        pollingTimerRef.current = setTimeout(executePolling, checkInterval);
      } else {
        // 无活跃任务，停止轮询
        isPollingRef.current = false;
        setIsPolling(false);
      }
    } catch (error) {
      console.error('Task detail polling failed:', error);

      if (retryCountRef.current < MAX_RETRIES) {
        retryCountRef.current++;
        pollingTimerRef.current = setTimeout(executePolling, checkInterval);
      } else {
        console.log('Max polling retries reached, stopping polling');
        isPollingRef.current = false;
        setIsPolling(false);
      }
    }
  }, [pollingEnabled, taskId, checkInterval, isPolling]);

  const startPolling = useCallback(() => {
    if (!pollingEnabled || !taskId) return;
    if (isPollingRef.current) return;

    clearPollingTimer();
    isPollingRef.current = true;
    setIsPolling(true);
    retryCountRef.current = 0;
    executePolling();
  }, [pollingEnabled, taskId, clearPollingTimer, executePolling]);

  const stopPolling = useCallback(() => {
    clearPollingTimer();
    isPollingRef.current = false;
    setIsPolling(false);
    retryCountRef.current = 0;
  }, [clearPollingTimer]);

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      clearPollingTimer();
    };
  }, [clearPollingTimer]);

  useEffect(() => {
    if (taskId && pollingEnabled) {
      // taskId 变化时停止旧的轮询
      stopPolling();
    }
  }, [taskId, pollingEnabled, stopPolling]);

  // 页面可见性处理
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.hidden) {
        stopPolling();
      } else if (taskId && pollingEnabled) {
        if (isPollingRef.current) {
          startPolling();
        }
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [startPolling, stopPolling, taskId, pollingEnabled]);

  return {
    isPolling,
    startPolling,
    stopPolling,
  };
};
