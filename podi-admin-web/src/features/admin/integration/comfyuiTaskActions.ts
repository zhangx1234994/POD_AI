import { useCallback } from 'react';
import type { Dispatch, SetStateAction } from 'react';
import { adminApi } from '../../../services/adminApi';
import type {
  ComfyuiAgentTask,
  ComfyuiAgentTaskEvent,
  ComfyuiMonitoringSummary,
  ComfyuiQueueSummary,
  ComfyuiWorkflowCompatibility,
  Executor,
} from '../../../types/admin';

type RefreshOptions = { silent?: boolean };

export interface ComfyuiAgentTaskFormState {
  taskId: string;
  agentId: string;
  manifestId: string;
  manifestUrl: string;
  actions: string;
  expiresAt: string;
}

const emptyTaskForm = (agentId = ''): ComfyuiAgentTaskFormState => ({
  taskId: '',
  agentId,
  manifestId: '',
  manifestUrl: '',
  actions: '',
  expiresAt: '',
});

const normalizeTagList = (value: unknown): string[] => {
  const out: string[] = [];
  if (!value) return out;
  if (Array.isArray(value)) {
    value.forEach((item) => {
      if (typeof item === 'string') {
        const trimmed = item.trim();
        if (trimmed) out.push(trimmed);
      } else if (item !== null && item !== undefined) {
        const trimmed = String(item).trim();
        if (trimmed) out.push(trimmed);
      }
    });
    return out;
  }
  if (typeof value === 'string') {
    value
      .replace(/;/g, ',')
      .split(',')
      .map((item) => item.trim())
      .filter(Boolean)
      .forEach((item) => out.push(item));
    return out;
  }
  const trimmed = String(value).trim();
  if (trimmed) out.push(trimmed);
  return out;
};

const normalizeTextList = (value: unknown): string[] => {
  if (typeof value === 'string') {
    return normalizeTagList(value.replace(/[\n，]/g, ','));
  }
  return normalizeTagList(value);
};

interface ComfyuiTaskActionsParams {
  comfyAgentTaskAgentFilter: string;
  comfyAgentTaskForm: ComfyuiAgentTaskFormState;
  comfyAgentTaskPushAfterCreate: boolean;
  comfyAgentTaskStatusFilter: string;
  comfyExecutors: Executor[];
  comfyMonitoringWindowHours: number;
  setComfyAgentTaskEvents: Dispatch<SetStateAction<ComfyuiAgentTaskEvent[]>>;
  setComfyAgentTaskEventsDialogOpen: Dispatch<SetStateAction<boolean>>;
  setComfyAgentTaskEventsError: Dispatch<SetStateAction<string | null>>;
  setComfyAgentTaskEventsLoading: Dispatch<SetStateAction<boolean>>;
  setComfyAgentTaskEventsTaskId: Dispatch<SetStateAction<string>>;
  setComfyAgentTaskForm: Dispatch<SetStateAction<ComfyuiAgentTaskFormState>>;
  setComfyAgentTaskFormError: Dispatch<SetStateAction<string | null>>;
  setComfyAgentTaskPushLoading: Dispatch<SetStateAction<Record<string, boolean>>>;
  setComfyAgentTaskSaving: Dispatch<SetStateAction<boolean>>;
  setComfyAgentTasks: Dispatch<SetStateAction<ComfyuiAgentTask[]>>;
  setComfyAgentTasksError: Dispatch<SetStateAction<string | null>>;
  setComfyAgentTasksLoading: Dispatch<SetStateAction<boolean>>;
  setComfyMonitoringError: Dispatch<SetStateAction<string | null>>;
  setComfyMonitoringLoading: Dispatch<SetStateAction<boolean>>;
  setComfyMonitoringSummary: Dispatch<SetStateAction<ComfyuiMonitoringSummary | null>>;
  setComfyQueueSummary: Dispatch<SetStateAction<ComfyuiQueueSummary | null>>;
  setComfyQueueSummaryError: Dispatch<SetStateAction<string | null>>;
  setComfyQueueSummaryLoading: Dispatch<SetStateAction<boolean>>;
  setComfyQueueSummaryUpdatedAt: Dispatch<SetStateAction<string | null>>;
  setComfyWorkflowCompatibility: Dispatch<SetStateAction<ComfyuiWorkflowCompatibility | null>>;
  setComfyWorkflowCompatibilityError: Dispatch<SetStateAction<string | null>>;
  setComfyWorkflowCompatibilityLoading: Dispatch<SetStateAction<boolean>>;
  setComfyWorkflowCompatibilityUpdatedAt: Dispatch<SetStateAction<string | null>>;
}

export const useComfyuiTaskActions = ({
  comfyAgentTaskAgentFilter,
  comfyAgentTaskForm,
  comfyAgentTaskPushAfterCreate,
  comfyAgentTaskStatusFilter,
  comfyExecutors,
  comfyMonitoringWindowHours,
  setComfyAgentTaskEvents,
  setComfyAgentTaskEventsDialogOpen,
  setComfyAgentTaskEventsError,
  setComfyAgentTaskEventsLoading,
  setComfyAgentTaskEventsTaskId,
  setComfyAgentTaskForm,
  setComfyAgentTaskFormError,
  setComfyAgentTaskPushLoading,
  setComfyAgentTaskSaving,
  setComfyAgentTasks,
  setComfyAgentTasksError,
  setComfyAgentTasksLoading,
  setComfyMonitoringError,
  setComfyMonitoringLoading,
  setComfyMonitoringSummary,
  setComfyQueueSummary,
  setComfyQueueSummaryError,
  setComfyQueueSummaryLoading,
  setComfyQueueSummaryUpdatedAt,
  setComfyWorkflowCompatibility,
  setComfyWorkflowCompatibilityError,
  setComfyWorkflowCompatibilityLoading,
  setComfyWorkflowCompatibilityUpdatedAt,
}: ComfyuiTaskActionsParams) => {
  const refreshComfyAgentTasks = useCallback(
    async (options?: RefreshOptions) => {
      const silent = Boolean(options?.silent);
      if (!silent) setComfyAgentTasksLoading(true);
      setComfyAgentTasksError(null);
      try {
        const resp = await adminApi.listComfyuiAgentTasks({
          agentId: comfyAgentTaskAgentFilter !== 'all' ? comfyAgentTaskAgentFilter : undefined,
          status: comfyAgentTaskStatusFilter !== 'all' ? comfyAgentTaskStatusFilter : undefined,
          limit: 50,
        });
        setComfyAgentTasks(resp || []);
      } catch (error: any) {
        console.error('Failed to load ComfyUI tasks:', error);
        setComfyAgentTasksError(error?.message || '获取任务列表失败，请稍后重试');
      } finally {
        if (!silent) setComfyAgentTasksLoading(false);
      }
    },
    [
      comfyAgentTaskAgentFilter,
      comfyAgentTaskStatusFilter,
      setComfyAgentTasks,
      setComfyAgentTasksError,
      setComfyAgentTasksLoading,
    ],
  );

  const refreshComfyMonitoringSummary = useCallback(
    async (options?: RefreshOptions) => {
      const silent = Boolean(options?.silent);
      if (!silent) setComfyMonitoringLoading(true);
      setComfyMonitoringError(null);
      try {
        const summary = await adminApi.getComfyuiMonitoringSummary(comfyMonitoringWindowHours);
        setComfyMonitoringSummary(summary);
      } catch (error: any) {
        console.error('load comfyui monitoring summary failed', error);
        setComfyMonitoringError(error?.message || '获取监控汇总失败，请稍后重试');
      } finally {
        if (!silent) setComfyMonitoringLoading(false);
      }
    },
    [
      comfyMonitoringWindowHours,
      setComfyMonitoringError,
      setComfyMonitoringLoading,
      setComfyMonitoringSummary,
    ],
  );

  const handleComfyAgentTaskCreate = useCallback(async () => {
    const agentId = comfyAgentTaskForm.agentId.trim();
    if (!agentId) {
      setComfyAgentTaskFormError('请选择代理服务');
      return;
    }
    const actions = normalizeTextList(comfyAgentTaskForm.actions);
    if (actions.length === 0) {
      setComfyAgentTaskFormError('请至少填写一个动作（同步模型/同步插件/同步工作流/重启服务）');
      return;
    }
    const manifestId = comfyAgentTaskForm.manifestId ? Number(comfyAgentTaskForm.manifestId) : null;
    const manifestUrl = comfyAgentTaskForm.manifestUrl.trim();
    const payload = {
      agentId,
      actions,
      manifestId: manifestId || undefined,
      manifestUrl: manifestUrl || undefined,
      expiresAt: comfyAgentTaskForm.expiresAt.trim() || undefined,
      taskId: comfyAgentTaskForm.taskId.trim() || undefined,
    };
    setComfyAgentTaskSaving(true);
    setComfyAgentTaskFormError(null);
    try {
      await adminApi.createComfyuiAgentTask(payload, { push: comfyAgentTaskPushAfterCreate });
      setComfyAgentTaskForm(emptyTaskForm(agentId));
      void refreshComfyAgentTasks({ silent: true });
    } catch (error: any) {
      console.error('create comfyui task failed', error);
      setComfyAgentTaskFormError(error?.message || '创建任务失败，请稍后重试');
    } finally {
      setComfyAgentTaskSaving(false);
    }
  }, [
    comfyAgentTaskForm,
    comfyAgentTaskPushAfterCreate,
    refreshComfyAgentTasks,
    setComfyAgentTaskForm,
    setComfyAgentTaskFormError,
    setComfyAgentTaskSaving,
  ]);

  const handleComfyAgentTaskPush = useCallback(
    async (taskId: string) => {
      setComfyAgentTaskPushLoading((prev) => ({ ...prev, [taskId]: true }));
      try {
        await adminApi.pushComfyuiAgentTask(taskId);
        void refreshComfyAgentTasks({ silent: true });
      } catch (error) {
        console.error('push comfyui task failed', error);
      } finally {
        setComfyAgentTaskPushLoading((prev) => ({ ...prev, [taskId]: false }));
      }
    },
    [refreshComfyAgentTasks, setComfyAgentTaskPushLoading],
  );

  const openComfyAgentTaskEvents = useCallback(
    async (taskId: string) => {
      setComfyAgentTaskEventsTaskId(taskId);
      setComfyAgentTaskEventsDialogOpen(true);
      setComfyAgentTaskEventsLoading(true);
      setComfyAgentTaskEventsError(null);
      try {
        const resp = await adminApi.listComfyuiAgentTaskEvents(taskId, 50);
        setComfyAgentTaskEvents(resp || []);
      } catch (error: any) {
        console.error('load comfyui task events failed', error);
        setComfyAgentTaskEventsError(error?.message || '获取任务事件失败');
      } finally {
        setComfyAgentTaskEventsLoading(false);
      }
    },
    [
      setComfyAgentTaskEvents,
      setComfyAgentTaskEventsDialogOpen,
      setComfyAgentTaskEventsError,
      setComfyAgentTaskEventsLoading,
      setComfyAgentTaskEventsTaskId,
    ],
  );

  const refreshComfyQueueSummary = useCallback(
    async (options?: RefreshOptions) => {
      const silent = Boolean(options?.silent);
      const executorIds = comfyExecutors.map((ex) => ex.id).filter(Boolean);
      if (!executorIds.length) {
        setComfyQueueSummary(null);
        setComfyQueueSummaryError(null);
        setComfyQueueSummaryUpdatedAt(null);
        if (!silent) setComfyQueueSummaryLoading(false);
        return;
      }
      if (!silent) {
        setComfyQueueSummaryLoading(true);
      }
      try {
        const response = await adminApi.getComfyuiQueueSummary(executorIds);
        setComfyQueueSummary(response);
        setComfyQueueSummaryError(null);
        setComfyQueueSummaryUpdatedAt(response.timestamp || new Date().toISOString());
      } catch (error) {
        console.error('load ComfyUI queue summary failed', error);
        setComfyQueueSummaryError(error instanceof Error ? error.message : '获取 ComfyUI 队列汇总失败');
      } finally {
        if (!silent) {
          setComfyQueueSummaryLoading(false);
        }
      }
    },
    [
      comfyExecutors,
      setComfyQueueSummary,
      setComfyQueueSummaryError,
      setComfyQueueSummaryLoading,
      setComfyQueueSummaryUpdatedAt,
    ],
  );

  const refreshComfyWorkflowCompatibility = useCallback(
    async (options?: RefreshOptions) => {
      const silent = Boolean(options?.silent);
      const executorIds = comfyExecutors.map((ex) => ex.id).filter(Boolean);
      if (!executorIds.length) {
        setComfyWorkflowCompatibility(null);
        setComfyWorkflowCompatibilityError(null);
        setComfyWorkflowCompatibilityUpdatedAt(null);
        if (!silent) setComfyWorkflowCompatibilityLoading(false);
        return;
      }
      if (!silent) {
        setComfyWorkflowCompatibilityLoading(true);
      }
      try {
        const response = await adminApi.getComfyuiWorkflowCompatibility(executorIds);
        setComfyWorkflowCompatibility(response);
        setComfyWorkflowCompatibilityError(null);
        setComfyWorkflowCompatibilityUpdatedAt(response.checkedAt || new Date().toISOString());
      } catch (error) {
        const message = error instanceof Error ? error.message : '获取 ComfyUI 能力对齐检查失败';
        setComfyWorkflowCompatibilityError(message);
      } finally {
        if (!silent) {
          setComfyWorkflowCompatibilityLoading(false);
        }
      }
    },
    [
      comfyExecutors,
      setComfyWorkflowCompatibility,
      setComfyWorkflowCompatibilityError,
      setComfyWorkflowCompatibilityLoading,
      setComfyWorkflowCompatibilityUpdatedAt,
    ],
  );

  return {
    handleComfyAgentTaskCreate,
    handleComfyAgentTaskPush,
    openComfyAgentTaskEvents,
    refreshComfyAgentTasks,
    refreshComfyMonitoringSummary,
    refreshComfyQueueSummary,
    refreshComfyWorkflowCompatibility,
  };
};
