import { useCallback } from 'react';
import type { Dispatch, SetStateAction } from 'react';
import { adminApi } from '../../../services/adminApi';
import type {
  ComfyuiAgent,
  ComfyuiAgentManifest,
  ComfyuiManifestDriftResponse,
  ComfyuiRepairJob,
  ComfyuiRepairPlan,
  JsonRecord,
} from '../../../types/admin';

type RefreshOptions = { silent?: boolean };
type ManifestEditorMode = 'wizard' | 'json';

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

const isRolePrimaryAgent = (agent: ComfyuiAgent) => {
  const config = (agent.config || {}) as JsonRecord;
  return Boolean(config?.rolePrimary);
};

interface ComfyuiManifestActionsParams {
  comfyManifestContentInput: string;
  comfyManifestEditorMode: ManifestEditorMode;
  comfyManifestForm: Partial<ComfyuiAgentManifest>;
  comfyManifestDriftContext: { manifestId: number; agentId: string } | null;
  comfyManifestRoleFilter: string;
  comfyManifestStatusFilter: string;
  comfyManifestWizardPreview: JsonRecord;
  comfyRepairPlan: ComfyuiRepairPlan | null;
  visibleComfyAgentList: ComfyuiAgent[];
  setComfyManifestActionLoading: Dispatch<SetStateAction<Record<number, boolean>>>;
  setComfyManifestContentInput: Dispatch<SetStateAction<string>>;
  setComfyManifestDialogOpen: Dispatch<SetStateAction<boolean>>;
  setComfyManifestDriftContext: Dispatch<SetStateAction<{ manifestId: number; agentId: string } | null>>;
  setComfyManifestDriftData: Dispatch<SetStateAction<ComfyuiManifestDriftResponse | null>>;
  setComfyManifestDriftDialogOpen: Dispatch<SetStateAction<boolean>>;
  setComfyManifestDriftError: Dispatch<SetStateAction<string | null>>;
  setComfyManifestDriftLoading: Dispatch<SetStateAction<boolean>>;
  setComfyManifestDriftTitle: Dispatch<SetStateAction<string>>;
  setComfyManifestEditorMode: Dispatch<SetStateAction<ManifestEditorMode>>;
  setComfyManifestError: Dispatch<SetStateAction<string | null>>;
  setComfyManifestForm: Dispatch<SetStateAction<Partial<ComfyuiAgentManifest>>>;
  setComfyManifestFormError: Dispatch<SetStateAction<string | null>>;
  setComfyManifestIncludeInactive: Dispatch<SetStateAction<boolean>>;
  setComfyManifestList: Dispatch<SetStateAction<ComfyuiAgentManifest[]>>;
  setComfyManifestLoading: Dispatch<SetStateAction<boolean>>;
  setComfyManifestSaving: Dispatch<SetStateAction<boolean>>;
  setComfyRepairJobLoading: Dispatch<SetStateAction<boolean>>;
  setComfyRepairJobs: Dispatch<SetStateAction<ComfyuiRepairJob[]>>;
  setComfyRepairPlan: Dispatch<SetStateAction<ComfyuiRepairPlan | null>>;
  setComfyRepairPlanLoading: Dispatch<SetStateAction<boolean>>;
}

export const useComfyuiManifestActions = ({
  comfyManifestContentInput,
  comfyManifestEditorMode,
  comfyManifestForm,
  comfyManifestDriftContext,
  comfyManifestRoleFilter,
  comfyManifestStatusFilter,
  comfyManifestWizardPreview,
  comfyRepairPlan,
  visibleComfyAgentList,
  setComfyManifestActionLoading,
  setComfyManifestContentInput,
  setComfyManifestDialogOpen,
  setComfyManifestDriftContext,
  setComfyManifestDriftData,
  setComfyManifestDriftDialogOpen,
  setComfyManifestDriftError,
  setComfyManifestDriftLoading,
  setComfyManifestDriftTitle,
  setComfyManifestEditorMode,
  setComfyManifestError,
  setComfyManifestForm,
  setComfyManifestFormError,
  setComfyManifestIncludeInactive,
  setComfyManifestList,
  setComfyManifestLoading,
  setComfyManifestSaving,
  setComfyRepairJobLoading,
  setComfyRepairJobs,
  setComfyRepairPlan,
  setComfyRepairPlanLoading,
}: ComfyuiManifestActionsParams) => {
  const resetComfyManifestForm = useCallback(
    (seed?: Partial<ComfyuiAgentManifest>) => {
      const next = seed || { status: 'draft' };
      setComfyManifestForm(next);
      setComfyManifestContentInput(stringifyJSON(next.content as JsonRecord));
      setComfyManifestEditorMode(seed?.id ? 'json' : 'wizard');
      setComfyManifestIncludeInactive(false);
      setComfyManifestFormError(null);
    },
    [
      setComfyManifestContentInput,
      setComfyManifestEditorMode,
      setComfyManifestForm,
      setComfyManifestFormError,
      setComfyManifestIncludeInactive,
    ],
  );

  const handleComfyManifestGenerateFromWizard = useCallback(() => {
    setComfyManifestContentInput(stringifyJSON(comfyManifestWizardPreview));
    setComfyManifestForm((prev) => ({ ...prev, content: comfyManifestWizardPreview }));
    setComfyManifestEditorMode('json');
  }, [
    comfyManifestWizardPreview,
    setComfyManifestContentInput,
    setComfyManifestEditorMode,
    setComfyManifestForm,
  ]);

  const refreshComfyManifests = useCallback(
    async (options?: RefreshOptions) => {
      const silent = Boolean(options?.silent);
      if (!silent) setComfyManifestLoading(true);
      setComfyManifestError(null);
      try {
        const resp = await adminApi.listComfyuiManifests({
          role: comfyManifestRoleFilter.trim() || undefined,
          status: comfyManifestStatusFilter !== 'all' ? comfyManifestStatusFilter : undefined,
        });
        setComfyManifestList(resp || []);
      } catch (error: any) {
        console.error('Failed to load ComfyUI manifests:', error);
        setComfyManifestError(error?.message || '获取清单失败，请稍后重试');
      } finally {
        if (!silent) setComfyManifestLoading(false);
      }
    },
    [
      comfyManifestRoleFilter,
      comfyManifestStatusFilter,
      setComfyManifestError,
      setComfyManifestList,
      setComfyManifestLoading,
    ],
  );

  const handleComfyManifestSave = useCallback(async () => {
    const role = String(comfyManifestForm.role || '').trim();
    const version = String(comfyManifestForm.version || '').trim();
    if (!role || !version) {
      setComfyManifestFormError('请填写清单角色与版本号');
      return;
    }
    const contentInput = comfyManifestContentInput.trim();
    if (contentInput) {
      const parsed = safeParseJSON(contentInput);
      if (!parsed.ok) {
        setComfyManifestFormError('清单内容格式不正确（需 JSON）');
        return;
      }
    }
    setComfyManifestSaving(true);
    setComfyManifestFormError(null);
    try {
      const payload: Partial<ComfyuiAgentManifest> = {
        role,
        version,
        status: comfyManifestForm.status || 'draft',
        downloadUrl: comfyManifestForm.downloadUrl || comfyManifestForm.download_url || undefined,
        notes: comfyManifestForm.notes,
      };
      if (contentInput) {
        payload.content = parseJSON(contentInput);
      } else if (comfyManifestEditorMode === 'wizard') {
        payload.content = comfyManifestWizardPreview;
      }
      if (comfyManifestForm.id) {
        await adminApi.updateComfyuiManifest(comfyManifestForm.id, payload);
      } else {
        await adminApi.createComfyuiManifest(payload);
      }
      setComfyManifestDialogOpen(false);
      resetComfyManifestForm();
      void refreshComfyManifests({ silent: true });
    } catch (error: any) {
      console.error('save comfyui manifest failed', error);
      setComfyManifestFormError(error?.message || '保存失败，请检查必填项');
    } finally {
      setComfyManifestSaving(false);
    }
  }, [
    comfyManifestContentInput,
    comfyManifestEditorMode,
    comfyManifestForm,
    comfyManifestWizardPreview,
    refreshComfyManifests,
    resetComfyManifestForm,
    setComfyManifestDialogOpen,
    setComfyManifestFormError,
    setComfyManifestSaving,
  ]);

  const handleComfyManifestPublish = useCallback(
    async (manifestId: number) => {
      setComfyManifestActionLoading((prev) => ({ ...prev, [manifestId]: true }));
      setComfyManifestError(null);
      try {
        await adminApi.publishComfyuiManifest(manifestId);
        void refreshComfyManifests({ silent: true });
      } catch (error: any) {
        console.error('publish comfyui manifest failed', error);
        setComfyManifestError(error?.message || '发布清单失败，请稍后重试');
      } finally {
        setComfyManifestActionLoading((prev) => ({ ...prev, [manifestId]: false }));
      }
    },
    [refreshComfyManifests, setComfyManifestActionLoading, setComfyManifestError],
  );

  const handleComfyManifestRollback = useCallback(
    async (manifestId: number) => {
      setComfyManifestActionLoading((prev) => ({ ...prev, [manifestId]: true }));
      setComfyManifestError(null);
      try {
        await adminApi.rollbackComfyuiManifest(manifestId);
        void refreshComfyManifests({ silent: true });
      } catch (error: any) {
        console.error('rollback comfyui manifest failed', error);
        setComfyManifestError(error?.message || '回滚清单失败，请稍后重试');
      } finally {
        setComfyManifestActionLoading((prev) => ({ ...prev, [manifestId]: false }));
      }
    },
    [refreshComfyManifests, setComfyManifestActionLoading, setComfyManifestError],
  );

  const handleOpenComfyManifestDrift = useCallback(
    async (manifest: ComfyuiAgentManifest) => {
      const candidates = visibleComfyAgentList.filter((agent) => {
        if ((agent.allowed ?? true) === false) return false;
        if (!manifest.role) return true;
        return (agent.role || '').trim() === manifest.role;
      });
      const preferred = candidates.find((agent) => isRolePrimaryAgent(agent)) || candidates[0];
      if (!preferred) {
        setComfyManifestError('未找到可用代理服务，请先在“代理服务”中配置并启用对应角色。');
        return;
      }
      setComfyManifestDriftDialogOpen(true);
      setComfyManifestDriftError(null);
      setComfyManifestDriftData(null);
      setComfyRepairPlan(null);
      setComfyManifestDriftLoading(true);
      setComfyManifestDriftTitle(`${manifest.role} · ${manifest.version} · ${preferred.id}`);
      setComfyManifestDriftContext({ manifestId: manifest.id, agentId: preferred.id });
      try {
        const drift = await adminApi.getComfyuiManifestDrift(manifest.id, preferred.id);
        setComfyManifestDriftData(drift);
      } catch (error: any) {
        console.error('load comfyui manifest drift failed', error);
        setComfyManifestDriftError(error?.message || '拉取差异失败，请稍后重试');
      } finally {
        setComfyManifestDriftLoading(false);
      }
    },
    [
      setComfyManifestDriftContext,
      setComfyManifestDriftData,
      setComfyManifestDriftDialogOpen,
      setComfyManifestDriftError,
      setComfyManifestDriftLoading,
      setComfyManifestDriftTitle,
      setComfyManifestError,
      setComfyRepairPlan,
      visibleComfyAgentList,
    ],
  );

  const refreshComfyRepairJobs = useCallback(async () => {
    try {
      const jobs = await adminApi.listComfyuiRepairJobs({ limit: 20 });
      setComfyRepairJobs(jobs || []);
    } catch (error) {
      console.error('load comfyui repair jobs failed', error);
    }
  }, [setComfyRepairJobs]);

  const handleComfyGenerateRepairPlan = useCallback(
    async () => {
      if (!comfyManifestDriftContext) {
        setComfyManifestDriftError('请先选择一个清单和目标节点后再生成修复计划。');
        return;
      }
      setComfyRepairPlanLoading(true);
      setComfyManifestDriftError(null);
      try {
        const plan = await adminApi.createComfyuiRepairPlan(comfyManifestDriftContext.manifestId, {
          mode: 'additive',
          agentIds: [comfyManifestDriftContext.agentId],
        });
        setComfyRepairPlan(plan);
      } catch (error: any) {
        console.error('create comfyui repair plan failed', error);
        setComfyManifestDriftError(error?.message || '生成修复计划失败，请稍后重试。');
      } finally {
        setComfyRepairPlanLoading(false);
      }
    },
    [
      comfyManifestDriftContext,
      setComfyManifestDriftError,
      setComfyRepairPlan,
      setComfyRepairPlanLoading,
    ],
  );

  const handleComfyCreateRepairJob = useCallback(async () => {
    if (!comfyRepairPlan || !comfyRepairPlan.items?.length) {
      setComfyManifestDriftError('修复计划为空，请先生成计划。');
      return;
    }
    const executable = comfyRepairPlan.items.filter((item) => item.actions.length > 0);
    if (executable.length === 0) {
      setComfyManifestDriftError('当前节点无需修复，无需创建任务。');
      return;
    }
    setComfyRepairJobLoading(true);
    setComfyManifestDriftError(null);
    try {
      await adminApi.createComfyuiRepairJob({
        manifestId: comfyRepairPlan.manifestId,
        mode: comfyRepairPlan.mode,
        push: true,
        items: executable.map((item) => ({
          agentId: item.agentId,
          actions: item.actions,
          missingItems: item.missingItems,
        })),
      });
      await refreshComfyRepairJobs();
    } catch (error: any) {
      console.error('create comfyui repair job failed', error);
      setComfyManifestDriftError(error?.message || '创建修复任务失败，请稍后重试。');
    } finally {
      setComfyRepairJobLoading(false);
    }
  }, [
    comfyRepairPlan,
    refreshComfyRepairJobs,
    setComfyManifestDriftError,
    setComfyRepairJobLoading,
  ]);

  return {
    handleComfyCreateRepairJob,
    handleComfyGenerateRepairPlan,
    handleComfyManifestGenerateFromWizard,
    handleComfyManifestPublish,
    handleComfyManifestRollback,
    handleComfyManifestSave,
    handleOpenComfyManifestDrift,
    refreshComfyManifests,
    refreshComfyRepairJobs,
    resetComfyManifestForm,
  };
};
