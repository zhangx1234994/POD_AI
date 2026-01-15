import { useState, useCallback, useEffect } from 'react';
import { workflowApi } from '../services/workflowApi';
import { getUserId } from '../utils/http';
import { TaskSummaryItem } from '../types/task';
import { useTaskListPolling } from './useTaskListPolling';
import { mapActionToChinese, mapChineseToAction } from '../utils/taskUtils';
import { toast } from 'sonner';
import { TASK_STATUS_EVENT } from '@/constants/events';

// 辅助函数：判断任务列表中是否存在活跃状态（RUNNING 或 PENDING）
const hasActiveStatusInList = (items: any[]) => {
  return items.some((t) => {
    const s = String(t.status || '').toUpperCase();
    return s === 'RUNNING' || s === 'PENDING';
  });
};

// 辅助函数：判断任务摘要是否发生变化
const isSummaryChanged = (oldTask: TaskSummaryItem, newTask: TaskSummaryItem) => {
  return (
    oldTask.status !== newTask.status ||
    oldTask.successCount !== newTask.successCount ||
    oldTask.failedCount !== newTask.failedCount ||
    oldTask.runningCount !== newTask.runningCount ||
    oldTask.pendingCount !== newTask.pendingCount ||
    oldTask.subTaskCount !== newTask.subTaskCount
  );
};

// 辅助函数：判断任务列表是否发生变化
const hasSummaryListChanged = (oldList: TaskSummaryItem[], newList: TaskSummaryItem[]) => {
  if (oldList.length !== newList.length) return true;
  return newList.some((newItem, index) => {
    const oldItem = oldList[index];
    return oldItem.id !== newItem.id || isSummaryChanged(oldItem, newItem);
  });
};

interface UseTaskSummaryDataProps {
  initialPage?: number;
  initialSize?: number;
  action?: string;
  timeFilter?: string;
  startTime?: string;
  endTime?: string;
  pollingInterval?: number;
  enableGlobalRefreshListener?: boolean; // 控制是否启用全局刷新事件监听
  pollingAlwaysOn?: boolean; // 如果为 true，则即使没有活跃任务也持续轮询（用在 TaskCenterHover）
  sourceTimestamp?: string | number; // 可选：向后端标识请求来源的时间戳，仅 TaskCenter 会传入
  refreshTrigger?: number; // 外部触发刷新的信号
  status?: string;
  search?: string;
}
  
export const useTaskSummaryData = ({
  initialPage = 0,
  initialSize = 10,
  action,
  timeFilter,
  startTime,
  endTime,
  status,
  search,
  pollingInterval = 3000,
  enableGlobalRefreshListener = false,
  pollingAlwaysOn = false,
  sourceTimestamp,
  refreshTrigger,
}: UseTaskSummaryDataProps = {}) => {
  const [tasks, setTasks] = useState<TaskSummaryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(initialPage);
  const [size, setSize] = useState(initialSize);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [hasNext, setHasNext] = useState(false);
  const [statusState, setStatusState] = useState<string | undefined>(undefined);

  const fetchTasks = useCallback(
    async (isPolling = false): Promise<TaskSummaryItem[]> => {
      if (!isPolling) setLoading(true);
      try {
        const userId = getUserId();
        const response = await workflowApi.getTaskSummary(userId, page, size, action, timeFilter, startTime, endTime, status, search, sourceTimestamp);

        if (response.data) {
          const newItemsRaw = response.data.items || [];
          // 为每个 task 补充 name 字段: "中文任务名 - taskId.slice(0,8)"
          const newItems = (newItemsRaw || []).map((it: any) => {
            const shortId = (it.taskId || it.id || '').toString().slice(0, 8);
            return {
              ...it,
              name: `${mapActionToChinese(it.action)} - ${shortId}`,
            };
          });
          const newTotal = response.data.total || 0;
          const newTotalPages = response.data.totalPages || 0;
          const newHasNext = response.data.hasNext || false;
          const respStatus = (response.data as any).status;

          if (!isPolling) {
            setTasks(newItems as TaskSummaryItem[]);
            setTotal(newTotal);
            setTotalPages(newTotalPages);
            setHasNext(newHasNext);
            setStatusState(respStatus);
          } else {
            // 无感更新逻辑 - 同时检测失败子任务变化以提示退款
            setTasks((prevTasks) => {
              if (!hasSummaryListChanged(prevTasks, newItems)) {
                return prevTasks;
              }

              try {
                // 对比每条任务的 failedCount，如果增加则提示用户并派发事件
                newItems.forEach((newItem: any) => {
                  const prev = prevTasks.find((p) => (p.taskId || p.id) === (newItem.taskId || newItem.id));
                  const prevFailed = Number(prev?.failedCount ?? 0);
                  const newFailed = Number(newItem?.failedCount ?? 0);
                  if (newFailed > prevFailed) {
                    // 子任务失败数增加，可能触发退款。优先使用后端返回的 refund 字段显示详细信息
                    const refund = newItem.refund ?? null;
                    if (refund) {
                      const total = refund.amount ?? refund.total ?? 0;
                      const temp = refund.temp ?? 0;
                      const recharge = refund.recharge ?? 0;
                      toast.info(`任务 ${newItem.name || newItem.taskId || ''} 有子任务失败，已自动退还 ${total} 积分（临时 ${temp}，充值 ${recharge}）`);
                      try {
                        window.dispatchEvent(new CustomEvent('points:refund', { detail: { taskId: newItem.taskId, total, temp, recharge } }));
                      } catch (e) {
                        // ignore
                      }
                    } else {
                      // 没有明确退款信息，仅提示子任务失败
                      toast.info(`任务 ${newItem.name || newItem.taskId || ''} 有子任务失败，请前往任务详情查看。`);
                    }
                  }
                });
              } catch (e) {
                // 防御性容错，避免因为提示逻辑影响数据更新
                console.error('Error while detecting failed subtasks for refund prompt', e);
              }

              return newItems;
            });
            // 更新分页信息
            setTotal((prev) => (prev !== newTotal ? newTotal : prev));
            setTotalPages((prev) => (prev !== newTotalPages ? newTotalPages : prev));
            setHasNext((prev) => (prev !== newHasNext ? newHasNext : prev));
            setStatusState((prev) => (prev !== respStatus ? respStatus : prev));
          }
          return newItems;
        }
        return [];
      } catch (error) {
        console.error('Failed to fetch task summary:', error);
        return [];
      } finally {
        if (!isPolling) setLoading(false);
      }
    },
    [page, size, action, timeFilter, startTime, endTime, status, search]
  );

  const { startPolling, stopPolling, isPolling } = useTaskListPolling({
    fetchTasks,
    pollingEnabled: true,
    checkInterval: pollingInterval,
    alwaysPoll: pollingAlwaysOn,
    // 如果 caller 希望始终保持轮询（如 TaskCenterHover），启用 activity resume
    enableActivityResume: Boolean(pollingAlwaysOn),
  });

  // 初始化加载和监听 refreshTrigger
  useEffect(() => {
    let mounted = true;

    // Initial fetch to populate UI quickly
    fetchTasks(false).then((fetchedTasks) => {
      if (!mounted) return;

      // If caller requests always-on polling (TaskCenterHover), start polling unconditionally
      if (pollingAlwaysOn) {
        startPolling();
        return;
      }

      // Otherwise start polling only if there are active tasks
      if (fetchedTasks && fetchedTasks.length > 0) {
        const hasActive = hasActiveStatusInList(fetchedTasks);
        if (hasActive) {
          startPolling();
        }
      }
    });

    // 当页面切换或刷新触发变动时，停止旧的轮询（新的轮询会由 startPolling 启动）
    return () => {
      mounted = false;
      stopPolling();
    };
  }, [fetchTasks, startPolling, stopPolling, refreshTrigger, pollingAlwaysOn]);

  // 当筛选（action 或 status 或 search）变化时，从第一页重新加载数据
  useEffect(() => {
    setPage(0);
  }, [action, status, search]);

  useEffect(() => {
    let debounce: ReturnType<typeof setTimeout> | null = null;
    const handler = () => {
      if (debounce) return;
      debounce = setTimeout(() => {
        fetchTasks(true);
        debounce = null;
      }, 500);
    };
    window.addEventListener(TASK_STATUS_EVENT, handler);
    return () => {
      window.removeEventListener(TASK_STATUS_EVENT, handler);
      if (debounce) clearTimeout(debounce);
    };
  }, [fetchTasks]);
  // 全局刷新事件监听
  useEffect(() => {
    if (!enableGlobalRefreshListener) return;

    const handleRefresh = (event: CustomEvent) => {
      const { action: eventAction, forceRefresh } = event.detail || {};

      // 侧边栏的筛选逻辑：如果是强制刷新，或者没有指定action，或者action匹配，则刷新
      if (forceRefresh || !eventAction || eventAction === action) {
        fetchTasks(false).then((fetchedTasks) => {
          if (fetchedTasks && fetchedTasks.length > 0) {
              const hasActive = hasActiveStatusInList(fetchedTasks);
              if (hasActive) {
                startPolling();
              }
            }
        });
      }
    };

    window.addEventListener('refreshTaskList', handleRefresh as EventListener);
    return () => {
      window.removeEventListener('refreshTaskList', handleRefresh as EventListener);
    };
  }, [enableGlobalRefreshListener, fetchTasks, action, startPolling]);

  // 手动刷新函数
  const refresh = useCallback(() => {
    return fetchTasks(false);
  }, [fetchTasks]);

  return {
    tasks,
    loading,
    pagination: {
      page,
      setPage,
      size,
      setSize,
      total,
      totalPages,
      hasNext,
    },
    refresh,
    startPolling,
    stopPolling,
    status: statusState,
    isPolling,
  };
};
