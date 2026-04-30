import { useCallback } from 'react';
import type { Dispatch, SetStateAction } from 'react';
import { adminApi } from '../../../services/adminApi';
import type { ComfyuiAgentAlert, ComfyuiServerDiffLog, Executor } from '../../../types/admin';

type RefreshOptions = { silent?: boolean };
type CatalogRefreshOptions = { silent?: boolean; includeNodes?: boolean };

export type ComfyServerFormState = {
  name: string;
  base_url: string;
  max_concurrency: number;
  weight: number;
  status: string;
};

interface ComfyuiServerActionsParams {
  buildComfyDiffSnapshot: () => any | null;
  comfyAgentAlertsAgentFilter: string;
  comfyAgentAlertsLimit: number;
  comfyAgentAlertsTypeFilter: string;
  comfyExecutors: Executor[];
  comfyServerForm: ComfyServerFormState;
  load: () => Promise<void>;
  refreshComfyuiModelCatalog: (executorId: string, options?: CatalogRefreshOptions) => Promise<void>;
  refreshComfyuiSystemStats: (executorId: string, options?: RefreshOptions) => Promise<void>;
  setComfyAgentAlerts: Dispatch<SetStateAction<ComfyuiAgentAlert[]>>;
  setComfyAgentAlertsError: Dispatch<SetStateAction<string | null>>;
  setComfyAgentAlertsLoading: Dispatch<SetStateAction<boolean>>;
  setComfyDiffLogs: Dispatch<SetStateAction<ComfyuiServerDiffLog[]>>;
  setComfyDiffLogsError: Dispatch<SetStateAction<string | null>>;
  setComfyDiffLogsLoading: Dispatch<SetStateAction<boolean>>;
  setComfyDiffSaving: Dispatch<SetStateAction<boolean>>;
  setComfyServerForm: Dispatch<SetStateAction<ComfyServerFormState>>;
  setComfyServerFormError: Dispatch<SetStateAction<string | null>>;
  setComfyServerRefreshing: Dispatch<SetStateAction<boolean>>;
  setComfyServerSaving: Dispatch<SetStateAction<boolean>>;
}

export const useComfyuiServerActions = ({
  buildComfyDiffSnapshot,
  comfyAgentAlertsAgentFilter,
  comfyAgentAlertsLimit,
  comfyAgentAlertsTypeFilter,
  comfyExecutors,
  comfyServerForm,
  load,
  refreshComfyuiModelCatalog,
  refreshComfyuiSystemStats,
  setComfyAgentAlerts,
  setComfyAgentAlertsError,
  setComfyAgentAlertsLoading,
  setComfyDiffLogs,
  setComfyDiffLogsError,
  setComfyDiffLogsLoading,
  setComfyDiffSaving,
  setComfyServerForm,
  setComfyServerFormError,
  setComfyServerRefreshing,
  setComfyServerSaving,
}: ComfyuiServerActionsParams) => {
  const refreshComfyAgentAlerts = useCallback(
    async (options?: RefreshOptions) => {
      const silent = Boolean(options?.silent);
      if (!silent) setComfyAgentAlertsLoading(true);
      setComfyAgentAlertsError(null);
      try {
        const resp = await adminApi.listComfyuiAgentAlerts({
          agentId: comfyAgentAlertsAgentFilter !== 'all' ? comfyAgentAlertsAgentFilter : undefined,
          alertType: comfyAgentAlertsTypeFilter.trim() || undefined,
          limit: Math.max(1, Math.min(200, Number(comfyAgentAlertsLimit) || 50)),
        });
        setComfyAgentAlerts(resp || []);
      } catch (error: any) {
        console.error('Failed to load ComfyUI alerts:', error);
        setComfyAgentAlertsError(error?.message || '获取告警失败，请稍后重试');
      } finally {
        if (!silent) setComfyAgentAlertsLoading(false);
      }
    },
    [
      comfyAgentAlertsAgentFilter,
      comfyAgentAlertsLimit,
      comfyAgentAlertsTypeFilter,
      setComfyAgentAlerts,
      setComfyAgentAlertsError,
      setComfyAgentAlertsLoading,
    ],
  );

  const refreshComfyDiffLogs = useCallback(
    async (options?: RefreshOptions) => {
      const silent = Boolean(options?.silent);
      if (!silent) setComfyDiffLogsLoading(true);
      setComfyDiffLogsError(null);
      try {
        const resp = await adminApi.listComfyuiServerDiff(12);
        setComfyDiffLogs(resp || []);
      } catch (error: any) {
        console.error('Failed to load comfyui diff logs', error);
        setComfyDiffLogsError(error?.message || '获取对齐记录失败');
      } finally {
        if (!silent) setComfyDiffLogsLoading(false);
      }
    },
    [setComfyDiffLogs, setComfyDiffLogsError, setComfyDiffLogsLoading],
  );

  const handleSaveComfyDiffSnapshot = useCallback(async () => {
    const snapshot = buildComfyDiffSnapshot();
    if (!snapshot) {
      alert('请先选择主服务器');
      return;
    }
    if (!snapshot.baseline?.id) {
      alert('缺少主服务器 ID');
      return;
    }
    setComfyDiffSaving(true);
    try {
      await adminApi.saveComfyuiServerDiff({
        baseline_executor_id: snapshot.baseline.id,
        payload: snapshot,
      });
      alert('已保存对齐结果');
    } catch (error: any) {
      console.error('save comfyui server diff failed', error);
      alert(error?.message || '保存失败');
    } finally {
      setComfyDiffSaving(false);
    }
  }, [buildComfyDiffSnapshot, setComfyDiffSaving]);

  const refreshComfyuiServers = useCallback(async () => {
    if (comfyExecutors.length === 0) return;
    setComfyServerRefreshing(true);
    try {
      await Promise.all(
        comfyExecutors.map(async (executor) => {
          await Promise.all([
            refreshComfyuiSystemStats(executor.id, { silent: true }),
            refreshComfyuiModelCatalog(executor.id, { silent: true, includeNodes: true }),
          ]);
        }),
      );
    } finally {
      setComfyServerRefreshing(false);
    }
  }, [
    comfyExecutors,
    refreshComfyuiModelCatalog,
    refreshComfyuiSystemStats,
    setComfyServerRefreshing,
  ]);

  const handleComfyuiServerCreate = useCallback(async () => {
    const name = comfyServerForm.name.trim();
    const baseUrl = comfyServerForm.base_url.trim();
    if (!name) {
      setComfyServerFormError('请填写服务器名称');
      return;
    }
    if (!baseUrl || !(baseUrl.startsWith('http://') || baseUrl.startsWith('https://'))) {
      setComfyServerFormError('服务地址需以 http:// 或 https:// 开头');
      return;
    }
    setComfyServerSaving(true);
    setComfyServerFormError(null);
    try {
      await adminApi.createExecutor({
        name,
        type: 'comfyui',
        base_url: baseUrl,
        status: comfyServerForm.status || 'active',
        weight: Math.max(1, Math.min(999, Number(comfyServerForm.weight) || 1)),
        max_concurrency: Math.max(1, Math.min(50, Number(comfyServerForm.max_concurrency) || 1)),
      });
      setComfyServerForm({ name: '', base_url: '', max_concurrency: 1, weight: 1, status: 'active' });
      await load();
    } catch (error: any) {
      console.error('create comfyui server failed', error);
      setComfyServerFormError(error?.message || '新增失败');
    } finally {
      setComfyServerSaving(false);
    }
  }, [
    comfyServerForm,
    load,
    setComfyServerForm,
    setComfyServerFormError,
    setComfyServerSaving,
  ]);

  return {
    handleComfyuiServerCreate,
    handleSaveComfyDiffSnapshot,
    refreshComfyAgentAlerts,
    refreshComfyDiffLogs,
    refreshComfyuiServers,
  };
};
