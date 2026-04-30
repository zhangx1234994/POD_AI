import { useCallback } from 'react';
import type { Dispatch, SetStateAction } from 'react';
import { adminApi } from '../../../services/adminApi';
import type { ComfyuiAgent, JsonRecord } from '../../../types/admin';

type RefreshOptions = { silent?: boolean; status?: string };

const parseJSON = (value?: string | JsonRecord): JsonRecord => {
  if (!value) return {};
  if (typeof value === 'object') return value;
  try {
    return JSON.parse(value);
  } catch {
    return {};
  }
};

const safeParseJSON = (value?: string | JsonRecord): { ok: boolean; value: JsonRecord } => {
  if (!value) return { ok: true, value: {} };
  if (typeof value === 'object') return { ok: true, value };
  try {
    return { ok: true, value: JSON.parse(value) };
  } catch {
    return { ok: false, value: {} };
  }
};

const stringifyJSON = (value?: string | JsonRecord) => {
  if (!value) return '';
  if (typeof value === 'string') return value;
  return JSON.stringify(value, null, 2);
};

interface ComfyuiAgentActionsParams {
  comfyAgentConfigInput: string;
  comfyAgentForm: Partial<ComfyuiAgent>;
  comfyAgentList: ComfyuiAgent[];
  comfyAgentStatusFilter: string;
  setComfyAgentConfigInput: Dispatch<SetStateAction<string>>;
  setComfyAgentDialogOpen: Dispatch<SetStateAction<boolean>>;
  setComfyAgentError: Dispatch<SetStateAction<string | null>>;
  setComfyAgentForm: Dispatch<SetStateAction<Partial<ComfyuiAgent>>>;
  setComfyAgentFormError: Dispatch<SetStateAction<string | null>>;
  setComfyAgentList: Dispatch<SetStateAction<ComfyuiAgent[]>>;
  setComfyAgentLoading: Dispatch<SetStateAction<boolean>>;
  setComfyAgentPrimarySaving: Dispatch<SetStateAction<Record<string, boolean>>>;
  setComfyAgentSaving: Dispatch<SetStateAction<boolean>>;
  setComfyAgentTokenAgentId: Dispatch<SetStateAction<string>>;
  setComfyAgentTokenDialogOpen: Dispatch<SetStateAction<boolean>>;
  setComfyAgentTokenError: Dispatch<SetStateAction<string | null>>;
  setComfyAgentTokenExpiresAt: Dispatch<SetStateAction<string>>;
  setComfyAgentTokenLoading: Dispatch<SetStateAction<boolean>>;
  setComfyAgentTokenValue: Dispatch<SetStateAction<string>>;
}

export const useComfyuiAgentActions = ({
  comfyAgentConfigInput,
  comfyAgentForm,
  comfyAgentList,
  comfyAgentStatusFilter,
  setComfyAgentConfigInput,
  setComfyAgentDialogOpen,
  setComfyAgentError,
  setComfyAgentForm,
  setComfyAgentFormError,
  setComfyAgentList,
  setComfyAgentLoading,
  setComfyAgentPrimarySaving,
  setComfyAgentSaving,
  setComfyAgentTokenAgentId,
  setComfyAgentTokenDialogOpen,
  setComfyAgentTokenError,
  setComfyAgentTokenExpiresAt,
  setComfyAgentTokenLoading,
  setComfyAgentTokenValue,
}: ComfyuiAgentActionsParams) => {
  const resetComfyAgentForm = useCallback(
    (seed?: Partial<ComfyuiAgent>) => {
      const next = seed || { status: 'active', allowed: true };
      setComfyAgentForm(next);
      setComfyAgentConfigInput(stringifyJSON(next.config as JsonRecord));
      setComfyAgentFormError(null);
    },
    [setComfyAgentConfigInput, setComfyAgentForm, setComfyAgentFormError],
  );

  const refreshComfyAgents = useCallback(
    async (options?: RefreshOptions) => {
      const silent = Boolean(options?.silent);
      const statusFilter = options?.status ?? comfyAgentStatusFilter;
      if (!silent) setComfyAgentLoading(true);
      setComfyAgentError(null);
      try {
        const resp = await adminApi.listComfyuiAgents({
          status: statusFilter !== 'all' ? statusFilter : undefined,
        });
        setComfyAgentList(resp || []);
      } catch (error: any) {
        console.error('Failed to load ComfyUI agents:', error);
        setComfyAgentError(error?.message || '获取代理服务列表失败');
      } finally {
        if (!silent) setComfyAgentLoading(false);
      }
    },
    [
      comfyAgentStatusFilter,
      setComfyAgentError,
      setComfyAgentList,
      setComfyAgentLoading,
    ],
  );

  const handleComfyAgentSave = useCallback(async () => {
    const id = String(comfyAgentForm.id || '').trim();
    if (!id) {
      setComfyAgentFormError('请填写代理服务ID');
      return;
    }
    const baseUrl = String(comfyAgentForm.baseUrl || '').trim();
    const configInput = comfyAgentConfigInput.trim();
    if (configInput) {
      const parsed = safeParseJSON(configInput);
      if (!parsed.ok) {
        setComfyAgentFormError('配置内容格式不正确（需 JSON）');
        return;
      }
    }
    setComfyAgentSaving(true);
    setComfyAgentFormError(null);
    try {
      const payload: Partial<ComfyuiAgent> & { id: string } = {
        id,
        name: comfyAgentForm.name ? String(comfyAgentForm.name).trim() : undefined,
        role: comfyAgentForm.role ? String(comfyAgentForm.role).trim() : undefined,
        host: comfyAgentForm.host ? String(comfyAgentForm.host).trim() : undefined,
        baseUrl: baseUrl || undefined,
        status: comfyAgentForm.status || 'active',
        allowed: typeof comfyAgentForm.allowed === 'boolean' ? comfyAgentForm.allowed : true,
      };
      if (configInput) {
        payload.config = parseJSON(configInput);
      }
      if (comfyAgentList.some((item) => item.id === id)) {
        await adminApi.updateComfyuiAgent(id, payload);
      } else {
        await adminApi.createComfyuiAgent(payload);
      }
      setComfyAgentDialogOpen(false);
      resetComfyAgentForm();
      void refreshComfyAgents({ silent: true });
    } catch (error: any) {
      console.error('save comfyui agent failed', error);
      setComfyAgentFormError(error?.message || '保存失败，请检查必填项');
    } finally {
      setComfyAgentSaving(false);
    }
  }, [
    comfyAgentConfigInput,
    comfyAgentForm,
    comfyAgentList,
    refreshComfyAgents,
    resetComfyAgentForm,
    setComfyAgentDialogOpen,
    setComfyAgentFormError,
    setComfyAgentSaving,
  ]);

  const handleComfyAgentDelete = useCallback(
    async (agentId: string) => {
      await adminApi.deleteComfyuiAgent(agentId);
      void refreshComfyAgents({ silent: true });
    },
    [refreshComfyAgents],
  );

  const handleComfyAgentSetPrimary = useCallback(
    async (agent: ComfyuiAgent) => {
      const role = String(agent.role || '').trim();
      if (!role) {
        setComfyAgentError('该代理服务未配置角色，无法设为主节点。');
        return;
      }
      setComfyAgentPrimarySaving((prev) => ({ ...prev, [agent.id]: true }));
      setComfyAgentError(null);
      try {
        await adminApi.setComfyuiRolePrimary(role, agent.id);
        void refreshComfyAgents({ silent: true });
      } catch (error: any) {
        console.error('set comfyui role primary failed', error);
        setComfyAgentError(error?.message || '设置主节点失败，请稍后重试');
      } finally {
        setComfyAgentPrimarySaving((prev) => ({ ...prev, [agent.id]: false }));
      }
    },
    [refreshComfyAgents, setComfyAgentError, setComfyAgentPrimarySaving],
  );

  const handleComfyAgentTokenIssue = useCallback(
    async (agentId: string) => {
      if (!agentId) return;
      setComfyAgentTokenLoading(true);
      setComfyAgentTokenError(null);
      try {
        const resp = await adminApi.issueComfyuiAgentToken(agentId);
        setComfyAgentTokenAgentId(resp.agentId || agentId);
        setComfyAgentTokenValue(resp.token || '');
        setComfyAgentTokenExpiresAt(resp.expiresAt || '');
        setComfyAgentTokenDialogOpen(true);
      } catch (error: any) {
        console.error('issue comfyui agent token failed', error);
        setComfyAgentTokenError(error?.message || '签发访问令牌失败');
      } finally {
        setComfyAgentTokenLoading(false);
      }
    },
    [
      setComfyAgentTokenAgentId,
      setComfyAgentTokenDialogOpen,
      setComfyAgentTokenError,
      setComfyAgentTokenExpiresAt,
      setComfyAgentTokenLoading,
      setComfyAgentTokenValue,
    ],
  );

  return {
    handleComfyAgentDelete,
    handleComfyAgentSave,
    handleComfyAgentSetPrimary,
    handleComfyAgentTokenIssue,
    refreshComfyAgents,
    resetComfyAgentForm,
  };
};
