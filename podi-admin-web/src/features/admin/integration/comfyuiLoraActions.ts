import { useCallback } from 'react';
import type { Dispatch, SetStateAction } from 'react';
import { adminApi } from '../../../services/adminApi';
import type { ComfyuiLora, ComfyuiLoraCatalogResponse } from '../../../types/admin';

type RefreshOptions = { silent?: boolean; includeUntracked?: boolean };

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

const formatTextList = (value?: string[] | null) => {
  if (!value || value.length === 0) return '';
  return value.join(', ');
};

const resolveLoraBaseModels = (record?: { base_models?: string[] | null; base_model?: string | null }) => {
  const normalized = normalizeTextList(record?.base_models ?? record?.base_model);
  return Array.from(new Set(normalized));
};

interface ComfyuiLoraActionsParams {
  comfyLoraExecutorId: string;
  comfyLoraForm: Partial<ComfyuiLora>;
  comfyLoraSearch: string;
  comfyLoraStatusFilter: string;
  comfyLoraTagsInput: string;
  comfyLoraTriggersInput: string;
  comfyLoraUntrackedLoaded: boolean;
  setComfyLoraCatalog: Dispatch<SetStateAction<ComfyuiLoraCatalogResponse | null>>;
  setComfyLoraDialogOpen: Dispatch<SetStateAction<boolean>>;
  setComfyLoraError: Dispatch<SetStateAction<string | null>>;
  setComfyLoraForm: Dispatch<SetStateAction<Partial<ComfyuiLora>>>;
  setComfyLoraFormError: Dispatch<SetStateAction<string | null>>;
  setComfyLoraLoading: Dispatch<SetStateAction<boolean>>;
  setComfyLoraSaving: Dispatch<SetStateAction<boolean>>;
  setComfyLoraTagsInput: Dispatch<SetStateAction<string>>;
  setComfyLoraTriggersInput: Dispatch<SetStateAction<string>>;
  setComfyLoraUntrackedLoaded: Dispatch<SetStateAction<boolean>>;
}

export const useComfyuiLoraActions = ({
  comfyLoraExecutorId,
  comfyLoraForm,
  comfyLoraSearch,
  comfyLoraStatusFilter,
  comfyLoraTagsInput,
  comfyLoraTriggersInput,
  comfyLoraUntrackedLoaded,
  setComfyLoraCatalog,
  setComfyLoraDialogOpen,
  setComfyLoraError,
  setComfyLoraForm,
  setComfyLoraFormError,
  setComfyLoraLoading,
  setComfyLoraSaving,
  setComfyLoraTagsInput,
  setComfyLoraTriggersInput,
  setComfyLoraUntrackedLoaded,
}: ComfyuiLoraActionsParams) => {
  const refreshComfyuiLoraCatalog = useCallback(
    async (options?: RefreshOptions) => {
      const silent = Boolean(options?.silent);
      const includeUntracked = Boolean(options?.includeUntracked);
      if (includeUntracked && !comfyLoraExecutorId) {
        setComfyLoraError('请先选择 ComfyUI 执行节点');
        return;
      }
      if (!silent) {
        setComfyLoraLoading(true);
      }
      setComfyLoraError(null);
      try {
        const resp = await adminApi.listComfyuiLoras({
          executorId: includeUntracked ? comfyLoraExecutorId : undefined,
          q: comfyLoraSearch.trim() || undefined,
          status: comfyLoraStatusFilter !== 'all' ? comfyLoraStatusFilter : undefined,
          includeUntracked,
        });
        setComfyLoraCatalog(resp);
        setComfyLoraUntrackedLoaded(includeUntracked);
      } catch (error: any) {
        console.error('Failed to load ComfyUI LoRA catalog:', error);
        setComfyLoraError(error?.message || '获取 LoRA 清单失败');
      } finally {
        if (!silent) {
          setComfyLoraLoading(false);
        }
      }
    },
    [
      comfyLoraExecutorId,
      comfyLoraSearch,
      comfyLoraStatusFilter,
      setComfyLoraCatalog,
      setComfyLoraError,
      setComfyLoraLoading,
      setComfyLoraUntrackedLoaded,
    ],
  );

  const resetComfyLoraForm = useCallback(
    (seed?: Partial<ComfyuiLora>) => {
      const next = { status: 'active', ...(seed || {}) };
      const baseModels = resolveLoraBaseModels(next);
      setComfyLoraForm({ ...next, base_models: baseModels });
      setComfyLoraTagsInput(formatTextList(next.tags));
      setComfyLoraTriggersInput(formatTextList(next.trigger_words));
      setComfyLoraFormError(null);
    },
    [
      setComfyLoraForm,
      setComfyLoraFormError,
      setComfyLoraTagsInput,
      setComfyLoraTriggersInput,
    ],
  );

  const handleComfyLoraSave = useCallback(async () => {
    const fileName = String(comfyLoraForm.file_name || '').trim();
    const displayName = String(comfyLoraForm.display_name || '').trim();
    if (!fileName) {
      setComfyLoraFormError('请填写服务器上的 LoRA 文件名');
      return;
    }
    if (!displayName) {
      setComfyLoraFormError('请填写对外展示名称');
      return;
    }
    const payload: Partial<ComfyuiLora> = {
      file_name: fileName,
      display_name: displayName,
      description: String(comfyLoraForm.description || '').trim() || undefined,
      status: String(comfyLoraForm.status || 'active'),
    };
    const baseModels = resolveLoraBaseModels(comfyLoraForm);
    if (baseModels.length > 0) {
      payload.base_models = baseModels;
      if (baseModels.length === 1) {
        payload.base_model = baseModels[0];
      }
    }
    const tags = normalizeTextList(comfyLoraTagsInput);
    const triggers = normalizeTextList(comfyLoraTriggersInput);
    if (tags.length > 0) payload.tags = tags;
    if (triggers.length > 0) payload.trigger_words = triggers;

    setComfyLoraSaving(true);
    setComfyLoraFormError(null);
    try {
      if (comfyLoraForm.id) {
        await adminApi.updateComfyuiLora(Number(comfyLoraForm.id), payload);
      } else {
        await adminApi.createComfyuiLora(payload);
      }
      setComfyLoraDialogOpen(false);
      resetComfyLoraForm();
      await refreshComfyuiLoraCatalog({ includeUntracked: comfyLoraUntrackedLoaded });
    } catch (error: any) {
      console.error('save comfyui lora failed', error);
      setComfyLoraFormError(error?.message || '保存失败，请检查网络或参数');
    } finally {
      setComfyLoraSaving(false);
    }
  }, [
    comfyLoraForm,
    comfyLoraTagsInput,
    comfyLoraTriggersInput,
    comfyLoraUntrackedLoaded,
    refreshComfyuiLoraCatalog,
    resetComfyLoraForm,
    setComfyLoraDialogOpen,
    setComfyLoraFormError,
    setComfyLoraSaving,
  ]);

  const handleComfyLoraDelete = useCallback(
    async (id: number) => {
      if (!id) return;
      try {
        await adminApi.deleteComfyuiLora(id);
        await refreshComfyuiLoraCatalog({ silent: true, includeUntracked: comfyLoraUntrackedLoaded });
      } catch (error: any) {
        console.error('delete comfyui lora failed', error);
        setComfyLoraError(error?.message || '删除 LoRA 失败');
      }
    },
    [comfyLoraUntrackedLoaded, refreshComfyuiLoraCatalog, setComfyLoraError],
  );

  return {
    handleComfyLoraDelete,
    handleComfyLoraSave,
    refreshComfyuiLoraCatalog,
    resetComfyLoraForm,
  };
};
