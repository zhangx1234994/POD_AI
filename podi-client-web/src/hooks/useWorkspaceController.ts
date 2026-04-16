import { useEffect, useMemo, useRef, useState } from 'react';
import { MessagePlugin } from 'tdesign-react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../app/AuthContext';
import { demoRecentAssets } from '../config/clientDemoData';
import { toolRuntimeConfig } from '../config/toolConfigs';
import { abilityApi, uploadsToImages } from '../services/abilityApi';
import { listClientAssets, saveClientAsset, subscribeClientAssets } from '../services/assetLibrary';
import { clientApi } from '../services/clientApi';
import { trackClientEvent } from '../services/clientAnalytics';
import { readWorkspaceDraft, writeWorkspaceDraft } from '../services/workspaceDraft';
import { extractPreviewUrl, mapTaskStatus } from '../services/workspaceRuntime';
import { uploadClientFile } from '../utils/ossUploader';
import { getAbilityPresentationName } from '../utils/abilityPresentation';
import type { AbilityInfo } from '../types/api';
import type { UploadResult } from '../types/media';
import type { ResultState, WorkspaceLocationState, WorkspaceProps, WorkspaceSeedDraft } from '../types/workspace';

export function useWorkspaceController({ tool, mode }: WorkspaceProps) {
  const { auth, isAuthenticated } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const runtime = toolRuntimeConfig[tool.path.replace(/^\//, '')];

  const [abilities, setAbilities] = useState<AbilityInfo[]>([]);
  const [abilitiesLoading, setAbilitiesLoading] = useState(false);
  const [abilitiesError, setAbilitiesError] = useState<string | null>(null);
  const [uploads, setUploads] = useState<UploadResult[]>([]);
  const [uploading, setUploading] = useState(false);
  const [formValues, setFormValues] = useState<Record<string, string>>(() => runtime?.defaults || {});
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<ResultState>({ status: 'idle' });
  const [recentLibraryAssets, setRecentLibraryAssets] = useState(() => listClientAssets());
  const [balance, setBalance] = useState<number | null>(null);
  const [rechargeVisible, setRechargeVisible] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const lastSavedTaskRef = useRef<string | null>(null);

  function buildSeedDraft(overrides?: Partial<WorkspaceSeedDraft>): WorkspaceSeedDraft {
    return {
      uploads,
      formValues,
      result: result.status === 'idle' ? undefined : result,
      source: 'workspace',
      ...overrides,
    };
  }

  useEffect(() => {
    const draft = readWorkspaceDraft(tool.path);
    setFormValues(draft?.formValues || runtime?.defaults || {});
    setUploads(draft?.uploads || []);
    setResult({ status: 'idle' });
    lastSavedTaskRef.current = null;
  }, [runtime?.abilityKey, runtime?.defaults, tool.path]);

  useEffect(() => {
    const state = location.state as WorkspaceLocationState | null;
    if (!state?.seedAsset && !state?.seedTask && !state?.seedDraft) return;
    if (state.seedAsset) {
      setUploads([
        {
          url: state.seedAsset.image,
          objectKey: state.seedAsset.image,
          name: state.seedAsset.title,
          size: 0,
        },
      ]);
      setFormValues(runtime?.defaults || {});
      setResult({ status: 'idle' });
    }
    if (state.seedDraft) {
      setUploads(state.seedDraft.uploads || []);
      setFormValues({ ...(runtime?.defaults || {}), ...(state.seedDraft.formValues || {}) });
      setResult(state.seedDraft.result || { status: 'idle' });
      if (state.seedDraft.templateTitle) {
        MessagePlugin.success(`已带入模板：${state.seedDraft.templateTitle}`);
      }
    }
    if (state.seedTask) {
      setUploads(state.seedTask.uploads);
      setFormValues({ ...(runtime?.defaults || {}), ...state.seedTask.formValues });
      setResult(state.seedTask.result || { status: 'idle' });
    }
    navigate(location.pathname, { replace: true, state: null });
  }, [location.pathname, location.state, navigate]);

  useEffect(() => {
    if (!isAuthenticated) {
      setAbilities([]);
      setAbilitiesLoading(false);
      setAbilitiesError(null);
      return;
    }
    let cancelled = false;
    async function loadAbilities() {
      if (!cancelled) {
        setAbilitiesLoading(true);
      }
      try {
        const data = await clientApi.listAbilities(auth?.accessToken || undefined);
        if (!cancelled) {
          setAbilities(data.items);
          setAbilitiesError(null);
          setAbilitiesLoading(false);
        }
      } catch {
        if (!cancelled) {
          setAbilities([]);
          setAbilitiesError('能力配置暂时同步失败，请刷新页面后重试。');
          setAbilitiesLoading(false);
        }
      }
    }
    void loadAbilities();
    return () => {
      cancelled = true;
    };
  }, [auth?.accessToken, isAuthenticated]);

  useEffect(() => {
    const sync = () => setRecentLibraryAssets(listClientAssets());
    sync();
    return subscribeClientAssets(sync);
  }, []);

  useEffect(() => {
    writeWorkspaceDraft(tool.path, { formValues, uploads });
  }, [formValues, uploads, tool.path]);

  useEffect(() => {
    let cancelled = false;
    async function loadBalance() {
      if (!auth?.user.id) {
        setBalance(null);
        return;
      }
      try {
        const data = await clientApi.getWalletBalance(auth.user.id);
        if (!cancelled) setBalance(data.balance);
      } catch {
        if (!cancelled) setBalance(null);
      }
    }
    void loadBalance();
    return () => {
      cancelled = true;
    };
  }, [auth?.user.id, result.status]);

  const ability = useMemo(
    () => abilities.find((item) => item.capabilityKey === runtime?.abilityKey) || null,
    [abilities, runtime?.abilityKey],
  );
  const displayToolTitle = useMemo(() => getAbilityPresentationName(ability) || tool.title, [ability, tool.title]);

  useEffect(() => {
    if (!auth?.accessToken || !result.taskId || !['queued', 'running'].includes(result.status)) return;
    let cancelled = false;
    const timer = window.setInterval(async () => {
      try {
        const task = await abilityApi.getTask(result.taskId!, auth.accessToken);
        if (cancelled) return;
        const nextStatus = mapTaskStatus(task.status);
        const mediaUrl = extractPreviewUrl(task.resultPayload as Record<string, unknown> | null);
        setResult({
          status: nextStatus,
          taskId: task.id,
          message:
            nextStatus === 'running'
              ? `任务处理中${result.startedAtMs ? ` · 已等待 ${Math.max(1, Math.round((Date.now() - result.startedAtMs) / 1000))} 秒` : ''}，可切到任务中心继续查看。`
              : nextStatus === 'success'
                ? '任务处理完成，可下载结果或继续创作。'
                : task.errorMessage || `${task.provider || '任务'} · ${task.status}`,
          mediaUrl: mediaUrl && /^https?:/.test(mediaUrl) ? mediaUrl : undefined,
          text: mediaUrl && !/^https?:/.test(mediaUrl) ? mediaUrl : undefined,
          startedAtMs: result.startedAtMs,
          elapsedSeconds: result.startedAtMs ? Math.max(1, Math.round((Date.now() - result.startedAtMs) / 1000)) : undefined,
        });
        if (nextStatus === 'success' && mediaUrl && /^https?:/.test(mediaUrl) && lastSavedTaskRef.current !== task.id) {
          saveClientAsset({
            id: `${task.id}-${mediaUrl}`,
            title: `${task.abilityName || displayToolTitle} 结果`,
            source: task.abilityName || displayToolTitle,
            createdAt: new Date(task.updatedAt).toLocaleString('zh-CN'),
            image: mediaUrl,
            type: mode === 'shoot' && tool.key === 'image-to-video' ? 'video' : 'image',
            tags: ['结果', task.provider],
            origin: 'result',
            pathHint: tool.path,
            taskId: task.id,
            abilityKey: task.capabilityKey || runtime?.abilityKey,
            provider: task.provider,
          });
          lastSavedTaskRef.current = task.id;
        }
        if (['success', 'failed'].includes(nextStatus)) window.clearInterval(timer);
      } catch {
        if (!cancelled) {
          setResult((prev: ResultState) => ({ ...prev, status: 'failed', message: '任务查询失败，请去任务中心查看。' }));
          window.clearInterval(timer);
        }
      }
    }, 3000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [auth?.accessToken, displayToolTitle, mode, result.startedAtMs, result.status, result.taskId, tool.key, tool.path]);

  const recentCandidates = useMemo(() => {
    const source = recentLibraryAssets.length ? recentLibraryAssets : isAuthenticated ? [] : demoRecentAssets;
    return source.filter((asset) => asset.type !== 'video').slice(0, 4);
  }, [isAuthenticated, recentLibraryAssets]);

  const estimatedPoints = useMemo(() => {
    const pricing = ability?.metadata && typeof ability.metadata === 'object' ? (ability.metadata as Record<string, unknown>).pricing : null;
    const price = pricing && typeof pricing === 'object' ? Number((pricing as Record<string, unknown>).discount_price || 0) : 0;
    if (!price || Number.isNaN(price)) return null;
    return Math.max(1, Math.ceil(price * 100));
  }, [ability?.metadata]);

  const canSubmit = useMemo(() => {
    if (!runtime) return false;
    if (!isAuthenticated || !auth?.accessToken) return false;
    if (abilitiesLoading || submitting || uploading) return false;
    if (!ability) return false;
    if (runtime.requiresImage && !uploads.length) return false;
    return true;
  }, [ability, abilitiesLoading, auth?.accessToken, isAuthenticated, runtime, submitting, uploading, uploads.length]);

  const resultTitle = useMemo(() => {
    switch (result.status) {
      case 'submitting':
        return '正在提交';
      case 'queued':
        return '任务已进入队列';
      case 'running':
        return '任务处理中';
      case 'success':
        return '已生成结果';
      case 'failed':
        return '任务失败';
      default:
        return `${displayToolTitle} · 当前结果`;
    }
  }, [displayToolTitle, result.status]);

  async function handleFiles(files: FileList | null) {
    if (!files?.length) return;
    if (!auth?.user.id) {
      MessagePlugin.warning('请先登录，再上传到我们的 OSS。');
      return;
    }
    setUploading(true);
    try {
      const maxSlots = runtime?.imageSlots || 1;
      const selected = Array.from(files).slice(0, maxSlots);
      const nextUploads: UploadResult[] = [];
      for (const file of selected) {
        const upload = await uploadClientFile(file, auth.user.id, runtime?.action || 'client-upload');
        nextUploads.push(upload);
      }
      setUploads(nextUploads);
      nextUploads.forEach((upload) =>
        saveClientAsset({
          id: upload.objectKey,
          title: upload.name,
          source: displayToolTitle,
          createdAt: new Date().toLocaleString('zh-CN'),
          image: upload.url,
          type: 'image',
          tags: ['原图上传'],
          origin: 'upload',
          pathHint: tool.path,
          abilityKey: runtime?.abilityKey,
        }),
      );
      MessagePlugin.success(`已上传 ${nextUploads.length} 张图片`);
      trackClientEvent('workspace_upload_success', {
        path: tool.path,
        tool: tool.key,
        count: nextUploads.length,
      });
    } catch (error) {
      MessagePlugin.error(error instanceof Error ? error.message : '上传失败');
    } finally {
      setUploading(false);
      if (inputRef.current) inputRef.current.value = '';
    }
  }

  async function handleSubmit() {
    if (!runtime) return;
    if (!isAuthenticated || !auth?.accessToken) {
      MessagePlugin.warning('请先登录，再提交真实任务。');
      return;
    }
    if (!ability) {
      MessagePlugin.error('还没拿到能力清单，请稍后重试。');
      return;
    }
    if (typeof balance === 'number' && typeof estimatedPoints === 'number' && balance < estimatedPoints) {
      trackClientEvent('wallet_low_balance_intercept', {
        path: tool.path,
        tool: tool.key,
        balance,
        estimatedPoints,
      });
      setRechargeVisible(true);
      return;
    }
    if (runtime.requiresImage && !uploads.length) {
      MessagePlugin.warning('请先上传图片。');
      return;
    }

    setSubmitting(true);
    setResult({ status: 'submitting', message: '正在提交到中台...' });
    trackClientEvent('workspace_submit_started', {
      path: tool.path,
      tool: tool.key,
      mode,
      invokeMode: runtime.invokeMode,
    });
    try {
      const payload = {
        inputs: Object.fromEntries(
          Object.entries(formValues)
            .filter(([, value]) => value !== '')
            .map(([key, value]) => [key, /^\d+$/.test(value) ? Number(value) : value]),
        ),
        imageUrl: uploads[0]?.url,
        images: uploadsToImages(uploads),
      };

      if (runtime.invokeMode === 'sync') {
        const response = await abilityApi.invoke(ability.id, payload, auth.accessToken);
        const preview = extractPreviewUrl(response as unknown as Record<string, unknown>);
        setResult({
          status: response.status === 'failed' ? 'failed' : 'success',
          message: `请求已完成${response.durationMs ? ` · ${response.durationMs}ms` : ''}`,
          mediaUrl: preview && /^https?:/.test(preview) ? preview : undefined,
          text: preview && !/^https?:/.test(preview) ? preview : undefined,
          elapsedSeconds: response.durationMs ? Math.max(1, Math.round(response.durationMs / 1000)) : undefined,
        });
        if (preview && /^https?:/.test(preview)) {
          saveClientAsset({
            id: `${response.requestId}-${preview}`,
            title: `${displayToolTitle} 结果`,
            source: displayToolTitle,
            createdAt: new Date().toLocaleString('zh-CN'),
            image: preview,
            type: mode === 'shoot' && tool.key === 'image-to-video' ? 'video' : 'image',
            tags: ['结果'],
            origin: 'result',
            pathHint: tool.path,
            abilityKey: runtime.abilityKey,
          });
        }
        trackClientEvent('workspace_submit_succeeded', {
          path: tool.path,
          tool: tool.key,
          mode,
          invokeMode: 'sync',
        });
      } else {
        const task = await abilityApi.createTask(ability.id, payload, auth.accessToken);
        setResult({
          status: mapTaskStatus(task.status),
          taskId: task.id,
          message: task.errorMessage || '任务已创建，正在等待执行结果。',
          startedAtMs: Date.now(),
          elapsedSeconds: 0,
        });
        trackClientEvent('workspace_task_created', {
          path: tool.path,
          tool: tool.key,
          taskId: task.id,
        });
      }
      MessagePlugin.success('任务已提交');
    } catch (error) {
      const message = error instanceof Error ? error.message : '提交失败';
      setResult({ status: 'failed', message });
      MessagePlugin.error(message);
      trackClientEvent('workspace_submit_failed', {
        path: tool.path,
        tool: tool.key,
        message,
      });
    } finally {
      setSubmitting(false);
    }
  }

  function resetWorkspace() {
    setUploads([]);
    setResult({ status: 'idle' });
    setFormValues(runtime?.defaults || {});
  }

  function useRecentAsset(asset: { image: string; title: string }) {
    setUploads([
      {
        url: asset.image,
        objectKey: asset.image,
        name: asset.title,
        size: 0,
      },
    ]);
  }

  function applyRecentCandidate(asset: { image: string; title: string }) {
    useRecentAsset(asset);
    setFormValues((prev) => ({ ...prev, prompt: `${asset.title}：延续当前画面风格与主体视觉。` }));
    trackClientEvent('workspace_reuse_recent_asset', {
      path: tool.path,
      tool: tool.key,
      assetTitle: asset.title,
    });
  }

  function closeRechargeDialog() {
    setRechargeVisible(false);
  }

  function goRecharge() {
    setRechargeVisible(false);
    const requiredPoints = typeof estimatedPoints === 'number' ? estimatedPoints : null;
    const currentBalance = typeof balance === 'number' ? balance : null;
    const shortfallPoints =
      typeof requiredPoints === 'number' && typeof currentBalance === 'number'
        ? Math.max(0, requiredPoints - currentBalance)
        : null;
    const search = new URLSearchParams();
    search.set('returnTo', tool.path);
    search.set('returnLabel', displayToolTitle);
    if (typeof requiredPoints === 'number') search.set('requiredPoints', String(requiredPoints));
    if (typeof currentBalance === 'number') search.set('currentBalance', String(currentBalance));
    if (typeof shortfallPoints === 'number') search.set('shortfallPoints', String(shortfallPoints));
    navigate({
      pathname: '/wallet',
      search: `?${search.toString()}`,
    }, {
      state: {
        returnTo: tool.path,
        returnState: { seedDraft: buildSeedDraft({ source: 'wallet-return' }) },
        returnLabel: displayToolTitle,
        requiredPoints,
        currentBalance,
        shortfallPoints,
      },
    });
  }

  return {
    auth,
    isAuthenticated,
    navigate,
    runtime,
    uploads,
    uploading,
    formValues,
    submitting,
    result,
    recentCandidates,
    balance,
    rechargeVisible,
    inputRef,
    ability,
    abilitiesLoading,
    abilitiesError,
    displayToolTitle,
    estimatedPoints,
    resultTitle,
    canSubmit,
    setFormValues,
    handleFiles,
    handleSubmit,
    resetWorkspace,
    useRecentAsset,
    applyRecentCandidate,
    closeRechargeDialog,
    goRecharge,
    buildSeedDraft,
  };
}
