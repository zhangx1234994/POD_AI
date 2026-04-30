import { useCallback } from 'react';
import type { Dispatch, SetStateAction } from 'react';
import { adminApi } from '../../../services/adminApi';
import type {
  ComfyuiModelCatalogItem,
  ComfyuiPluginCatalogItem,
  ComfyuiVersionCatalogItem,
} from '../../../types/admin';

type RefreshOptions = { silent?: boolean };

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

interface ComfyuiResourceCatalogActionsParams {
  comfyModelCatalogSearch: string;
  comfyModelCatalogStatus: string;
  comfyModelCatalogType: string;
  comfyModelForm: Partial<ComfyuiModelCatalogItem>;
  comfyModelFormTags: string;
  comfyPluginCatalogSearch: string;
  comfyPluginCatalogStatus: string;
  comfyPluginForm: Partial<ComfyuiPluginCatalogItem>;
  comfyPluginFormTags: string;
  comfyVersionCatalogSearch: string;
  comfyVersionCatalogStatus: string;
  comfyVersionForm: Partial<ComfyuiVersionCatalogItem>;
  setComfyModelCatalogError: Dispatch<SetStateAction<string | null>>;
  setComfyModelCatalogItems: Dispatch<SetStateAction<ComfyuiModelCatalogItem[]>>;
  setComfyModelCatalogLoading: Dispatch<SetStateAction<boolean>>;
  setComfyModelDialogOpen: Dispatch<SetStateAction<boolean>>;
  setComfyModelForm: Dispatch<SetStateAction<Partial<ComfyuiModelCatalogItem>>>;
  setComfyModelFormError: Dispatch<SetStateAction<string | null>>;
  setComfyModelFormTags: Dispatch<SetStateAction<string>>;
  setComfyModelSaving: Dispatch<SetStateAction<boolean>>;
  setComfyPluginCatalogError: Dispatch<SetStateAction<string | null>>;
  setComfyPluginCatalogItems: Dispatch<SetStateAction<ComfyuiPluginCatalogItem[]>>;
  setComfyPluginCatalogLoading: Dispatch<SetStateAction<boolean>>;
  setComfyPluginDialogOpen: Dispatch<SetStateAction<boolean>>;
  setComfyPluginForm: Dispatch<SetStateAction<Partial<ComfyuiPluginCatalogItem>>>;
  setComfyPluginFormError: Dispatch<SetStateAction<string | null>>;
  setComfyPluginFormTags: Dispatch<SetStateAction<string>>;
  setComfyPluginSaving: Dispatch<SetStateAction<boolean>>;
  setComfyVersionCatalogError: Dispatch<SetStateAction<string | null>>;
  setComfyVersionCatalogItems: Dispatch<SetStateAction<ComfyuiVersionCatalogItem[]>>;
  setComfyVersionCatalogLoading: Dispatch<SetStateAction<boolean>>;
  setComfyVersionDialogOpen: Dispatch<SetStateAction<boolean>>;
  setComfyVersionForm: Dispatch<SetStateAction<Partial<ComfyuiVersionCatalogItem>>>;
  setComfyVersionFormError: Dispatch<SetStateAction<string | null>>;
  setComfyVersionSaving: Dispatch<SetStateAction<boolean>>;
  setComfyVersionSyncing: Dispatch<SetStateAction<boolean>>;
}

export const useComfyuiResourceCatalogActions = ({
  comfyModelCatalogSearch,
  comfyModelCatalogStatus,
  comfyModelCatalogType,
  comfyModelForm,
  comfyModelFormTags,
  comfyPluginCatalogSearch,
  comfyPluginCatalogStatus,
  comfyPluginForm,
  comfyPluginFormTags,
  comfyVersionCatalogSearch,
  comfyVersionCatalogStatus,
  comfyVersionForm,
  setComfyModelCatalogError,
  setComfyModelCatalogItems,
  setComfyModelCatalogLoading,
  setComfyModelDialogOpen,
  setComfyModelForm,
  setComfyModelFormError,
  setComfyModelFormTags,
  setComfyModelSaving,
  setComfyPluginCatalogError,
  setComfyPluginCatalogItems,
  setComfyPluginCatalogLoading,
  setComfyPluginDialogOpen,
  setComfyPluginForm,
  setComfyPluginFormError,
  setComfyPluginFormTags,
  setComfyPluginSaving,
  setComfyVersionCatalogError,
  setComfyVersionCatalogItems,
  setComfyVersionCatalogLoading,
  setComfyVersionDialogOpen,
  setComfyVersionForm,
  setComfyVersionFormError,
  setComfyVersionSaving,
  setComfyVersionSyncing,
}: ComfyuiResourceCatalogActionsParams) => {
  const resetComfyModelForm = useCallback(
    (seed?: Partial<ComfyuiModelCatalogItem>) => {
      const next = seed || { status: 'active', model_type: 'unet' };
      setComfyModelForm(next);
      setComfyModelFormTags(formatTextList(next.tags));
      setComfyModelFormError(null);
    },
    [setComfyModelForm, setComfyModelFormError, setComfyModelFormTags],
  );

  const refreshComfyModelCatalog = useCallback(
    async (options?: RefreshOptions) => {
      const silent = Boolean(options?.silent);
      if (!silent) setComfyModelCatalogLoading(true);
      setComfyModelCatalogError(null);
      try {
        const resp = await adminApi.listComfyuiModelCatalog({
          q: comfyModelCatalogSearch.trim() || undefined,
          type: comfyModelCatalogType !== 'all' ? comfyModelCatalogType : undefined,
          status: comfyModelCatalogStatus !== 'all' ? comfyModelCatalogStatus : undefined,
        });
        setComfyModelCatalogItems(resp.items || []);
      } catch (error: any) {
        console.error('Failed to load ComfyUI model catalog:', error);
        setComfyModelCatalogError(error?.message || '获取模型清单失败');
      } finally {
        if (!silent) setComfyModelCatalogLoading(false);
      }
    },
    [
      comfyModelCatalogSearch,
      comfyModelCatalogStatus,
      comfyModelCatalogType,
      setComfyModelCatalogError,
      setComfyModelCatalogItems,
      setComfyModelCatalogLoading,
    ],
  );

  const handleComfyModelSave = useCallback(async () => {
    const fileName = (comfyModelForm.file_name || '').trim();
    const displayName = (comfyModelForm.display_name || '').trim();
    const modelType = (comfyModelForm.model_type || '').trim() || 'unet';
    if (!fileName || !displayName) {
      setComfyModelFormError('请填写模型文件名与对外名称');
      return;
    }
    setComfyModelSaving(true);
    setComfyModelFormError(null);
    try {
      const payload: Partial<ComfyuiModelCatalogItem> = {
        file_name: fileName,
        display_name: displayName,
        model_type: modelType,
        description: comfyModelForm.description,
        source_url: comfyModelForm.source_url,
        download_url: comfyModelForm.download_url,
        status: comfyModelForm.status || 'active',
        tags: normalizeTextList(comfyModelFormTags),
      };
      if (comfyModelForm.id) {
        await adminApi.updateComfyuiModelCatalog(comfyModelForm.id, payload);
      } else {
        await adminApi.createComfyuiModelCatalog(payload);
      }
      setComfyModelDialogOpen(false);
      resetComfyModelForm();
      void refreshComfyModelCatalog({ silent: true });
    } catch (error: any) {
      console.error('save comfyui model catalog failed', error);
      setComfyModelFormError(error?.message || '保存失败');
    } finally {
      setComfyModelSaving(false);
    }
  }, [
    comfyModelForm,
    comfyModelFormTags,
    refreshComfyModelCatalog,
    resetComfyModelForm,
    setComfyModelDialogOpen,
    setComfyModelFormError,
    setComfyModelSaving,
  ]);

  const handleComfyModelDelete = useCallback(
    async (id: number) => {
      await adminApi.deleteComfyuiModelCatalog(id);
      void refreshComfyModelCatalog({ silent: true });
    },
    [refreshComfyModelCatalog],
  );

  const resetComfyVersionForm = useCallback(
    (seed?: Partial<ComfyuiVersionCatalogItem>) => {
      const next = seed || { status: 'active' };
      setComfyVersionForm(next);
      setComfyVersionFormError(null);
    },
    [setComfyVersionForm, setComfyVersionFormError],
  );

  const refreshComfyVersionCatalog = useCallback(
    async (options?: RefreshOptions) => {
      const silent = Boolean(options?.silent);
      if (!silent) setComfyVersionCatalogLoading(true);
      setComfyVersionCatalogError(null);
      try {
        const resp = await adminApi.listComfyuiVersionCatalog({
          q: comfyVersionCatalogSearch.trim() || undefined,
          status: comfyVersionCatalogStatus !== 'all' ? comfyVersionCatalogStatus : undefined,
        });
        setComfyVersionCatalogItems(resp.items || []);
      } catch (error: any) {
        console.error('Failed to load ComfyUI version catalog:', error);
        setComfyVersionCatalogError(error?.message || '获取版本清单失败');
      } finally {
        if (!silent) setComfyVersionCatalogLoading(false);
      }
    },
    [
      comfyVersionCatalogSearch,
      comfyVersionCatalogStatus,
      setComfyVersionCatalogError,
      setComfyVersionCatalogItems,
      setComfyVersionCatalogLoading,
    ],
  );

  const handleComfyVersionSave = useCallback(async () => {
    const version = (comfyVersionForm.version || '').trim();
    if (!version) {
      setComfyVersionFormError('请填写版本号');
      return;
    }
    setComfyVersionSaving(true);
    setComfyVersionFormError(null);
    try {
      const payload: Partial<ComfyuiVersionCatalogItem> = {
        version,
        commit_sha: comfyVersionForm.commit_sha || undefined,
        repo_url: comfyVersionForm.repo_url || undefined,
        source_url: comfyVersionForm.source_url || undefined,
        download_url: comfyVersionForm.download_url || undefined,
        released_at: comfyVersionForm.released_at || undefined,
        notes: comfyVersionForm.notes || undefined,
        status: comfyVersionForm.status || 'active',
      };
      if (comfyVersionForm.id) {
        await adminApi.updateComfyuiVersionCatalog(comfyVersionForm.id, payload);
      } else {
        await adminApi.createComfyuiVersionCatalog(payload);
      }
      setComfyVersionDialogOpen(false);
      resetComfyVersionForm();
      void refreshComfyVersionCatalog({ silent: true });
    } catch (error: any) {
      console.error('save comfyui version catalog failed', error);
      setComfyVersionFormError(error?.message || '保存失败');
    } finally {
      setComfyVersionSaving(false);
    }
  }, [
    comfyVersionForm,
    refreshComfyVersionCatalog,
    resetComfyVersionForm,
    setComfyVersionDialogOpen,
    setComfyVersionFormError,
    setComfyVersionSaving,
  ]);

  const handleComfyVersionDelete = useCallback(
    async (id: number) => {
      await adminApi.deleteComfyuiVersionCatalog(id);
      void refreshComfyVersionCatalog({ silent: true });
    },
    [refreshComfyVersionCatalog],
  );

  const handleComfyVersionSync = useCallback(async () => {
    setComfyVersionSyncing(true);
    setComfyVersionCatalogError(null);
    try {
      const resp = await adminApi.syncComfyuiVersionCatalog();
      await refreshComfyVersionCatalog({ silent: true });
      window.alert(`已同步：新增 ${resp.created} 条，更新 ${resp.updated} 条（共 ${resp.total} 条）`);
    } catch (error: any) {
      console.error('sync comfyui version catalog failed', error);
      setComfyVersionCatalogError(error?.message || '同步失败');
    } finally {
      setComfyVersionSyncing(false);
    }
  }, [refreshComfyVersionCatalog, setComfyVersionCatalogError, setComfyVersionSyncing]);

  const resetComfyPluginForm = useCallback(
    (seed?: Partial<ComfyuiPluginCatalogItem>) => {
      const next = seed || { status: 'active' };
      setComfyPluginForm(next);
      setComfyPluginFormTags(formatTextList(next.tags));
      setComfyPluginFormError(null);
    },
    [setComfyPluginForm, setComfyPluginFormError, setComfyPluginFormTags],
  );

  const refreshComfyPluginCatalog = useCallback(
    async (options?: RefreshOptions) => {
      const silent = Boolean(options?.silent);
      if (!silent) setComfyPluginCatalogLoading(true);
      setComfyPluginCatalogError(null);
      try {
        const resp = await adminApi.listComfyuiPluginCatalog({
          q: comfyPluginCatalogSearch.trim() || undefined,
          status: comfyPluginCatalogStatus !== 'all' ? comfyPluginCatalogStatus : undefined,
        });
        setComfyPluginCatalogItems(resp.items || []);
      } catch (error: any) {
        console.error('Failed to load ComfyUI plugin catalog:', error);
        setComfyPluginCatalogError(error?.message || '获取插件清单失败');
      } finally {
        if (!silent) setComfyPluginCatalogLoading(false);
      }
    },
    [
      comfyPluginCatalogSearch,
      comfyPluginCatalogStatus,
      setComfyPluginCatalogError,
      setComfyPluginCatalogItems,
      setComfyPluginCatalogLoading,
    ],
  );

  const handleComfyPluginSave = useCallback(async () => {
    const nodeKey = (comfyPluginForm.node_key || '').trim();
    const displayName = (comfyPluginForm.display_name || '').trim();
    if (!nodeKey || !displayName) {
      setComfyPluginFormError('请填写节点 key 与对外名称');
      return;
    }
    setComfyPluginSaving(true);
    setComfyPluginFormError(null);
    try {
      const payload: Partial<ComfyuiPluginCatalogItem> = {
        node_key: nodeKey,
        display_name: displayName,
        package_name: comfyPluginForm.package_name,
        version: comfyPluginForm.version,
        description: comfyPluginForm.description,
        source_url: comfyPluginForm.source_url,
        download_url: comfyPluginForm.download_url,
        status: comfyPluginForm.status || 'active',
        tags: normalizeTextList(comfyPluginFormTags),
      };
      if (comfyPluginForm.id) {
        await adminApi.updateComfyuiPluginCatalog(comfyPluginForm.id, payload);
      } else {
        await adminApi.createComfyuiPluginCatalog(payload);
      }
      setComfyPluginDialogOpen(false);
      resetComfyPluginForm();
      void refreshComfyPluginCatalog({ silent: true });
    } catch (error: any) {
      console.error('save comfyui plugin catalog failed', error);
      setComfyPluginFormError(error?.message || '保存失败');
    } finally {
      setComfyPluginSaving(false);
    }
  }, [
    comfyPluginForm,
    comfyPluginFormTags,
    refreshComfyPluginCatalog,
    resetComfyPluginForm,
    setComfyPluginDialogOpen,
    setComfyPluginFormError,
    setComfyPluginSaving,
  ]);

  const handleComfyPluginDelete = useCallback(
    async (id: number) => {
      await adminApi.deleteComfyuiPluginCatalog(id);
      void refreshComfyPluginCatalog({ silent: true });
    },
    [refreshComfyPluginCatalog],
  );

  return {
    handleComfyModelDelete,
    handleComfyModelSave,
    handleComfyPluginDelete,
    handleComfyPluginSave,
    handleComfyVersionDelete,
    handleComfyVersionSave,
    handleComfyVersionSync,
    refreshComfyModelCatalog,
    refreshComfyPluginCatalog,
    refreshComfyVersionCatalog,
    resetComfyModelForm,
    resetComfyPluginForm,
    resetComfyVersionForm,
  };
};
