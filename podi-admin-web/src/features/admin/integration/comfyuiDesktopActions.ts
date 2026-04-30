import { useCallback } from 'react';
import type { Dispatch, SetStateAction } from 'react';
import { adminApi } from '../../../services/adminApi';
import type { ComfyuiDesktopRelease, ComfyuiEnrollCode, JsonRecord } from '../../../types/admin';

type RefreshOptions = { silent?: boolean };

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

interface ComfyuiDesktopActionsParams {
  comfyDesktopReleaseForm: Partial<ComfyuiDesktopRelease>;
  comfyDesktopReleasePayloadInput: string;
  comfyDesktopReleaseStatusFilter: string;
  comfyEnrollCodeMaxUses: number;
  comfyEnrollCodeNote: string;
  comfyEnrollCodeRole: string;
  comfyEnrollCodeTtlSeconds: number;
  setComfyDesktopReleaseDialogOpen: Dispatch<SetStateAction<boolean>>;
  setComfyDesktopReleaseForm: Dispatch<SetStateAction<Partial<ComfyuiDesktopRelease>>>;
  setComfyDesktopReleaseFormError: Dispatch<SetStateAction<string | null>>;
  setComfyDesktopReleasePayloadInput: Dispatch<SetStateAction<string>>;
  setComfyDesktopReleases: Dispatch<SetStateAction<ComfyuiDesktopRelease[]>>;
  setComfyDesktopReleasesError: Dispatch<SetStateAction<string | null>>;
  setComfyDesktopReleasesLoading: Dispatch<SetStateAction<boolean>>;
  setComfyDesktopReleaseSaving: Dispatch<SetStateAction<boolean>>;
  setComfyEnrollCodeCreating: Dispatch<SetStateAction<boolean>>;
  setComfyEnrollCodeNote: Dispatch<SetStateAction<string>>;
  setComfyEnrollCodes: Dispatch<SetStateAction<ComfyuiEnrollCode[]>>;
  setComfyEnrollCodesError: Dispatch<SetStateAction<string | null>>;
  setComfyEnrollCodesLoading: Dispatch<SetStateAction<boolean>>;
}

export const useComfyuiDesktopActions = ({
  comfyDesktopReleaseForm,
  comfyDesktopReleasePayloadInput,
  comfyDesktopReleaseStatusFilter,
  comfyEnrollCodeMaxUses,
  comfyEnrollCodeNote,
  comfyEnrollCodeRole,
  comfyEnrollCodeTtlSeconds,
  setComfyDesktopReleaseDialogOpen,
  setComfyDesktopReleaseForm,
  setComfyDesktopReleaseFormError,
  setComfyDesktopReleasePayloadInput,
  setComfyDesktopReleases,
  setComfyDesktopReleasesError,
  setComfyDesktopReleasesLoading,
  setComfyDesktopReleaseSaving,
  setComfyEnrollCodeCreating,
  setComfyEnrollCodeNote,
  setComfyEnrollCodes,
  setComfyEnrollCodesError,
  setComfyEnrollCodesLoading,
}: ComfyuiDesktopActionsParams) => {
  const refreshComfyEnrollCodes = useCallback(
    async (options?: RefreshOptions) => {
      const silent = Boolean(options?.silent);
      if (!silent) setComfyEnrollCodesLoading(true);
      setComfyEnrollCodesError(null);
      try {
        const resp = await adminApi.listComfyuiEnrollCodes({ limit: 50 });
        setComfyEnrollCodes(resp || []);
      } catch (error: any) {
        console.error('load comfy enroll codes failed', error);
        setComfyEnrollCodesError(error?.message || '获取注册码失败');
      } finally {
        if (!silent) setComfyEnrollCodesLoading(false);
      }
    },
    [setComfyEnrollCodes, setComfyEnrollCodesError, setComfyEnrollCodesLoading],
  );

  const handleComfyEnrollCodeCreate = useCallback(async () => {
    setComfyEnrollCodeCreating(true);
    setComfyEnrollCodesError(null);
    try {
      await adminApi.createComfyuiEnrollCode({
        role: comfyEnrollCodeRole || 'full',
        ttlSeconds: Math.max(60, Math.min(7 * 24 * 3600, Number(comfyEnrollCodeTtlSeconds) || 600)),
        maxUses: Math.max(1, Math.min(99, Number(comfyEnrollCodeMaxUses) || 1)),
        note: comfyEnrollCodeNote.trim() || undefined,
      });
      setComfyEnrollCodeNote('');
      void refreshComfyEnrollCodes({ silent: true });
    } catch (error: any) {
      console.error('create comfy enroll code failed', error);
      setComfyEnrollCodesError(error?.message || '生成注册码失败');
    } finally {
      setComfyEnrollCodeCreating(false);
    }
  }, [
    comfyEnrollCodeMaxUses,
    comfyEnrollCodeNote,
    comfyEnrollCodeRole,
    comfyEnrollCodeTtlSeconds,
    refreshComfyEnrollCodes,
    setComfyEnrollCodeCreating,
    setComfyEnrollCodeNote,
    setComfyEnrollCodesError,
  ]);

  const refreshComfyDesktopReleases = useCallback(
    async (options?: RefreshOptions) => {
      const silent = Boolean(options?.silent);
      if (!silent) setComfyDesktopReleasesLoading(true);
      setComfyDesktopReleasesError(null);
      try {
        const resp = await adminApi.listComfyuiDesktopReleases({
          status: comfyDesktopReleaseStatusFilter !== 'all' ? comfyDesktopReleaseStatusFilter : undefined,
          limit: 100,
        });
        setComfyDesktopReleases(resp || []);
      } catch (error: any) {
        console.error('load comfy desktop releases failed', error);
        setComfyDesktopReleasesError(error?.message || '获取安装包列表失败');
      } finally {
        if (!silent) setComfyDesktopReleasesLoading(false);
      }
    },
    [
      comfyDesktopReleaseStatusFilter,
      setComfyDesktopReleases,
      setComfyDesktopReleasesError,
      setComfyDesktopReleasesLoading,
    ],
  );

  const resetComfyDesktopReleaseForm = useCallback(
    (seed?: Partial<ComfyuiDesktopRelease>) => {
      const next = seed || {
        channel: 'stable',
        osType: 'windows',
        arch: 'x64',
        status: 'active',
      };
      setComfyDesktopReleaseForm(next);
      setComfyDesktopReleasePayloadInput(stringifyJSON(next.payload as JsonRecord));
      setComfyDesktopReleaseFormError(null);
    },
    [
      setComfyDesktopReleaseForm,
      setComfyDesktopReleaseFormError,
      setComfyDesktopReleasePayloadInput,
    ],
  );

  const handleComfyDesktopReleaseSave = useCallback(async () => {
    const version = String(comfyDesktopReleaseForm.version || '').trim();
    const downloadUrl = String(comfyDesktopReleaseForm.downloadUrl || '').trim();
    const sha256 = String(comfyDesktopReleaseForm.sha256 || '').trim();
    if (!version || !downloadUrl || !sha256) {
      setComfyDesktopReleaseFormError('请填写版本号、下载地址、SHA256。');
      return;
    }
    const releasePayloadInput = comfyDesktopReleasePayloadInput.trim();
    if (releasePayloadInput) {
      const parsed = safeParseJSON(releasePayloadInput);
      if (!parsed.ok) {
        setComfyDesktopReleaseFormError('扩展参数格式不正确（需 JSON）。');
        return;
      }
    }
    setComfyDesktopReleaseSaving(true);
    setComfyDesktopReleaseFormError(null);
    try {
      const payload: Partial<ComfyuiDesktopRelease> = {
        channel: String(comfyDesktopReleaseForm.channel || 'stable').trim() || 'stable',
        version,
        osType: String(comfyDesktopReleaseForm.osType || 'windows').trim() || 'windows',
        arch: String(comfyDesktopReleaseForm.arch || 'x64').trim() || 'x64',
        status: String(comfyDesktopReleaseForm.status || 'active').trim() || 'active',
        downloadUrl,
        sha256,
        minAgentVersion: String(comfyDesktopReleaseForm.minAgentVersion || '').trim() || undefined,
        notes: String(comfyDesktopReleaseForm.notes || '').trim() || undefined,
      };
      if (releasePayloadInput) {
        payload.payload = parseJSON(releasePayloadInput);
      }
      if (comfyDesktopReleaseForm.id) {
        await adminApi.updateComfyuiDesktopRelease(comfyDesktopReleaseForm.id, payload);
      } else {
        await adminApi.createComfyuiDesktopRelease(payload);
      }
      setComfyDesktopReleaseDialogOpen(false);
      resetComfyDesktopReleaseForm();
      void refreshComfyDesktopReleases({ silent: true });
    } catch (error: any) {
      console.error('save comfy desktop release failed', error);
      setComfyDesktopReleaseFormError(error?.message || '保存安装包失败');
    } finally {
      setComfyDesktopReleaseSaving(false);
    }
  }, [
    comfyDesktopReleaseForm,
    comfyDesktopReleasePayloadInput,
    refreshComfyDesktopReleases,
    resetComfyDesktopReleaseForm,
    setComfyDesktopReleaseDialogOpen,
    setComfyDesktopReleaseFormError,
    setComfyDesktopReleaseSaving,
  ]);

  const handleToggleComfyDesktopReleaseStatus = useCallback(
    async (release: ComfyuiDesktopRelease) => {
      if (!release?.id) return;
      const nextStatus = release.status === 'active' ? 'inactive' : 'active';
      try {
        await adminApi.updateComfyuiDesktopRelease(release.id, { status: nextStatus });
        void refreshComfyDesktopReleases({ silent: true });
      } catch (error: any) {
        console.error('toggle comfy desktop release status failed', error);
        setComfyDesktopReleasesError(error?.message || '更新安装包状态失败');
      }
    },
    [refreshComfyDesktopReleases, setComfyDesktopReleasesError],
  );

  return {
    handleComfyDesktopReleaseSave,
    handleComfyEnrollCodeCreate,
    handleToggleComfyDesktopReleaseStatus,
    refreshComfyDesktopReleases,
    refreshComfyEnrollCodes,
    resetComfyDesktopReleaseForm,
  };
};
