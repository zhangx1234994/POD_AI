import { Alert, Button, Card, Col, Dialog, Input, InputNumber, Popup, Row, Select, Space, Tag, Textarea, Typography } from 'tdesign-react';
import type { ComfyuiServerDiffLog, Executor } from '../../../types/admin';
import { GuidanceQueueCard, StatusBadge, type GuidanceQueueItem } from '../shared/ui';
import { formatDateTime } from './formatters';

type SelectOption = {
  label: string;
  value: string;
};

type ComfyServerFormState = {
  name: string;
  base_url: string;
  status?: string;
  weight: number;
  max_concurrency: number;
};

type ComfyServerDiffSnapshot = {
  baseline?: unknown;
  server?: unknown;
  missing: {
    unet: string[];
    clip: string[];
    vae: string[];
    lora: string[];
    nodes: string[];
  };
  missing_repo_groups?: {
    repos?: unknown[];
    missingRepoNodes?: unknown[];
  };
  [key: string]: unknown;
};

type ComfyuiServersPanelProps = {
  executors: Executor[];
  baselineExecutor?: Executor | null;
  modelCache: Record<string, Record<string, string[]>>;
  baseModelCache: Record<string, string[]>;
  nodeCache: Record<string, string[]>;
  systemCache: Record<string, Record<string, unknown>>;
  systemLoadingByExecutor: Record<string, boolean>;
  modelLoadingByExecutor: Record<string, boolean>;
  systemErrorByExecutor: Record<string, string | undefined>;
  modelErrorByExecutor: Record<string, string | undefined>;
  serverRefreshing: boolean;
  diffSaving: boolean;
  assistOpen: boolean;
  serverForm: ComfyServerFormState;
  serverFormError?: string | null;
  serverSaving: boolean;
  statusOptions: SelectOption[];
  diffLogs: ComfyuiServerDiffLog[];
  diffLogsLoading: boolean;
  diffLogsError?: string | null;
  diffDialogOpen: boolean;
  diffDialogTitle?: string | null;
  diffDialogText: string;
  diffDialogPayload?: unknown;
  buildServerDiff: (executor: Executor) => ComfyServerDiffSnapshot;
  buildDiffSnapshot: () => unknown;
  onBaselineExecutorChange: (executorId: string) => void;
  onRefreshAllServers: () => void;
  onRefreshExecutor: (executorId: string) => void;
  onSaveDiffSnapshot: () => void;
  onCreateServer: () => void;
  onServerFormChange: (patch: Partial<ComfyServerFormState>) => void;
  onRefreshDiffLogs: () => void;
  onOpenDiffDialog: (title: string, payload: unknown) => void;
  onDownloadJson: (payload: unknown, filename: string) => void;
  onCopyText: (text: string) => void;
  onCloseDiffDialog: () => void;
};

const extractVersionInfo = (executor?: Executor | null, system?: Record<string, unknown> | null) => {
  if (system && typeof system === 'object') {
    const pickSystem = (key: string) => (typeof system[key] === 'string' ? String(system[key]).trim() : '');
    const pickSystemAny = (keys: string[]) => {
      for (const key of keys) {
        const value = pickSystem(key);
        if (value) return value;
      }
      return '';
    };
    return {
      version: pickSystemAny(['comfyui_version', 'version', 'comfyuiVersion']),
      customNodes: pickSystemAny(['installed_templates_version', 'custom_nodes_version']),
    };
  }
  const config = (executor?.config || {}) as Record<string, unknown>;
  const pick = (keys: string[]) => {
    for (const key of keys) {
      const value = config[key];
      if (typeof value === 'string' && value.trim()) return value.trim();
    }
    return '';
  };
  return {
    version: pick(['comfyui_version', 'comfyuiVersion', 'version']),
    customNodes: pick(['custom_nodes_version', 'customNodesVersion', 'custom_nodes']),
  };
};

const extractModelCounts = (catalog?: Record<string, string[]>) => {
  const count = (key: string) => (Array.isArray(catalog?.[key]) ? catalog?.[key]?.length || 0 : 0);
  return {
    unet: count('unet'),
    clip: count('clip'),
    vae: count('vae'),
    lora: count('lora'),
  };
};

function renderDiffTag(options: { baselineReady: boolean; targetReady: boolean; missing: string[]; okLabel?: string }) {
  const okLabel = options.okLabel || '齐全';
  if (!options.baselineReady) {
    return (
      <Tag theme="warning" variant="light">
        主服务器未拉取
      </Tag>
    );
  }
  if (!options.targetReady) {
    return (
      <Tag theme="warning" variant="light">
        未拉取
      </Tag>
    );
  }
  if (options.missing.length === 0) {
    return (
      <Tag theme="success" variant="light">
        {okLabel}
      </Tag>
    );
  }
  return (
    <Popup
      trigger="hover"
      placement="right"
      content={<div className="max-w-xs text-xs leading-5">{options.missing.join('、')}</div>}
    >
      <Tag theme="danger" variant="light">
        缺失 {options.missing.length}
      </Tag>
    </Popup>
  );
}

const countMissingItems = (snapshot?: ComfyServerDiffSnapshot | null) => {
  if (!snapshot) return 0;
  return (
    snapshot.missing.unet.length +
    snapshot.missing.clip.length +
    snapshot.missing.vae.length +
    snapshot.missing.lora.length +
    snapshot.missing.nodes.length
  );
};

const getServerStatusText = (executor: Executor) => {
  if (executor.status === 'active') return '可接任务';
  if (executor.status === 'disabled') return '已停用';
  return '暂不可用';
};

const withTimestamp = (prefix: string) => `${prefix}-${new Date().toISOString().replace(/[:.]/g, '-')}.json`;

export function ComfyuiServersPanel({
  executors,
  baselineExecutor,
  modelCache,
  baseModelCache,
  nodeCache,
  systemCache,
  systemLoadingByExecutor,
  modelLoadingByExecutor,
  systemErrorByExecutor,
  modelErrorByExecutor,
  serverRefreshing,
  diffSaving,
  assistOpen,
  serverForm,
  serverFormError,
  serverSaving,
  statusOptions,
  diffLogs,
  diffLogsLoading,
  diffLogsError,
  diffDialogOpen,
  diffDialogTitle,
  diffDialogText,
  diffDialogPayload,
  buildServerDiff,
  buildDiffSnapshot,
  onBaselineExecutorChange,
  onRefreshAllServers,
  onRefreshExecutor,
  onSaveDiffSnapshot,
  onCreateServer,
  onServerFormChange,
  onRefreshDiffLogs,
  onOpenDiffDialog,
  onDownloadJson,
  onCopyText,
  onCloseDiffDialog,
}: ComfyuiServersPanelProps) {
  const baselineCatalog = baselineExecutor?.id ? modelCache[baselineExecutor.id] : null;
  const baselineUnetReady =
    Array.isArray(baselineCatalog?.unet) ||
    Boolean(baselineExecutor?.id && (baseModelCache[baselineExecutor.id] || []).length > 0);
  const baselineClipReady = Array.isArray(baselineCatalog?.clip);
  const baselineVaeReady = Array.isArray(baselineCatalog?.vae);
  const baselineLoraReady = Array.isArray(baselineCatalog?.lora);
  const baselineNodesReady = Boolean(baselineExecutor?.id && (nodeCache[baselineExecutor.id] || []).length > 0);
  const hasBaseline = Boolean(baselineExecutor?.id);
  const activeExecutors = executors.filter((executor) => executor.status === 'active');
  const inactiveExecutors = executors.filter((executor) => executor.status !== 'active');
  const loadingServerCount = executors.filter(
    (executor) => systemLoadingByExecutor[executor.id] || modelLoadingByExecutor[executor.id],
  ).length;
  const unrefreshedExecutors = executors.filter((executor) => {
    const hasSystem = Boolean(systemCache[executor.id]);
    const hasModel = Boolean(modelCache[executor.id] && Object.keys(modelCache[executor.id]).length > 0);
    return !hasSystem && !hasModel && !systemLoadingByExecutor[executor.id] && !modelLoadingByExecutor[executor.id];
  });
  const errorExecutors = executors.filter((executor) => systemErrorByExecutor[executor.id] || modelErrorByExecutor[executor.id]);
  const diffProblemCount =
    hasBaseline && baselineExecutor?.id
      ? executors.filter((executor) => executor.id !== baselineExecutor.id && countMissingItems(buildServerDiff(executor)) > 0).length
      : 0;
  const serverActionItems: GuidanceQueueItem[] = [];
  if (executors.length === 0) {
    serverActionItems.push({
      key: 'no-server',
      theme: 'danger',
      priority: '阻塞',
      title: '还没有服务器',
      detail: '当前没有可路由的 ComfyUI 节点，生图任务无法进入执行侧。',
      action: '先新增 ComfyUI 服务器',
    });
  } else if (!hasBaseline) {
    serverActionItems.push({
      key: 'no-baseline',
      theme: 'warning',
      priority: '先处理',
      title: '未选择主服务器',
      detail: '没有基准机器时，无法判断其它机器是否缺模型、缺 LoRA 或缺插件节点。',
      action: '先选择一台稳定机器作为主服务器',
    });
  }
  if (errorExecutors.length > 0) {
    serverActionItems.push({
      key: 'server-error',
      theme: 'danger',
      priority: '需处理',
      title: '有服务器读不到',
      detail: `${errorExecutors.length} 台服务器状态或模型列表读取失败，路由前要先确认机器和端口是否正常。`,
      action: '打开对应服务器卡片查看错误',
    });
  }
  if (unrefreshedExecutors.length > 0) {
    serverActionItems.push({
      key: 'server-unrefreshed',
      theme: 'primary',
      priority: '建议',
      title: '状态还未刷新',
      detail: `${unrefreshedExecutors.length} 台服务器还没有拉取模型/插件信息，差异判断可能不完整。`,
      action: '点击“刷新所有服务器”',
      onClick: onRefreshAllServers,
      loading: serverRefreshing,
    });
  }
  if (diffProblemCount > 0) {
    serverActionItems.push({
      key: 'server-diff',
      theme: 'warning',
      priority: '需确认',
      title: '资源不完全一致',
      detail: `${diffProblemCount} 台服务器相对主服务器存在模型、LoRA 或插件节点缺失。`,
      action: '先处理缺失项，再放开全量路由',
    });
  }
  if (inactiveExecutors.length > 0) {
    serverActionItems.push({
      key: 'server-inactive',
      theme: 'warning',
      priority: '关注',
      title: '有服务器未启用',
      detail: `${inactiveExecutors.length} 台服务器当前不是 active，不会作为正常执行节点使用。`,
      action: '确认是主动下线还是配置遗漏',
    });
  }
  if (serverActionItems.length === 0) {
    serverActionItems.push({
      key: 'server-ok',
      theme: 'success',
      priority: '可用',
      title: '服务器纳管正常',
      detail: '当前服务器可接任务，主服务器已选择，暂未发现读取失败或明显资源差异。',
      action: '继续做业务链路巡检',
    });
  }

  return (
    <div className="space-y-4">
      <GuidanceQueueCard items={serverActionItems} maxItems={4} />
      <Card bordered title="服务器健康总览">
        <div className="grid gap-3 md:grid-cols-5">
          <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 dark:border-slate-800 dark:bg-slate-950/40">
            <div className="text-xs text-slate-500">纳管服务器</div>
            <div className="mt-1 text-lg font-semibold text-slate-900 dark:text-white">{executors.length}</div>
            <div className="mt-1 text-xs text-slate-500">当前记录的 ComfyUI 节点</div>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 dark:border-slate-800 dark:bg-slate-950/40">
            <div className="text-xs text-slate-500">可接任务</div>
            <div className="mt-1 text-lg font-semibold text-slate-900 dark:text-white">{activeExecutors.length}</div>
            <div className="mt-1 text-xs text-slate-500">未启用 {inactiveExecutors.length}</div>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 dark:border-slate-800 dark:bg-slate-950/40">
            <div className="text-xs text-slate-500">主服务器</div>
            <div className="mt-1 truncate text-lg font-semibold text-slate-900 dark:text-white">
              {baselineExecutor?.name || '未选择'}
            </div>
            <div className="mt-1 text-xs text-slate-500">{baselineExecutor?.id || '先选基准再做资源对齐'}</div>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 dark:border-slate-800 dark:bg-slate-950/40">
            <div className="text-xs text-slate-500">资源差异</div>
            <div className="mt-1 text-lg font-semibold text-slate-900 dark:text-white">
              {hasBaseline ? diffProblemCount : '—'}
            </div>
            <div className="mt-1 text-xs text-slate-500">相对主服务器缺模型/插件的机器</div>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 dark:border-slate-800 dark:bg-slate-950/40">
            <div className="text-xs text-slate-500">读取状态</div>
            <div className="mt-1 text-lg font-semibold text-slate-900 dark:text-white">
              {errorExecutors.length > 0 ? `${errorExecutors.length} 异常` : loadingServerCount > 0 ? `${loadingServerCount} 读取中` : '正常'}
            </div>
            <div className="mt-1 text-xs text-slate-500">状态接口和模型列表读取结果</div>
          </div>
        </div>
      </Card>
      <div className="text-sm text-slate-600 dark:text-slate-400">
        选择一台“主服务器”作为基准，其它服务器会对比模型/插件是否缺失。差异只做提示，不会自动同步。
      </div>
      <div className="grid gap-6 lg:grid-cols-[2fr_1fr] lg:items-start">
        <Card bordered title="服务器对比" style={{ width: '100%' }}>
          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
            <Space align="center" size="small" style={{ justifyContent: 'space-between', width: '100%' }}>
              <Space align="center" size="small">
                <div style={{ width: 'min(100%, 280px)' }}>
                  <Select
                    value={baselineExecutor?.id || ''}
                    onChange={(value) => onBaselineExecutorChange(String(value))}
                    options={[
                      { label: '请选择主服务器', value: '' },
                      ...executors.map((executor) => ({
                        label: `${executor.name} · ${executor.id}`,
                        value: executor.id,
                      })),
                    ]}
                  />
                </div>
                <Button variant="outline" disabled={serverRefreshing || executors.length === 0} onClick={onRefreshAllServers}>
                  {serverRefreshing ? '刷新中…' : '刷新所有服务器'}
                </Button>
                <Button
                  variant="outline"
                  disabled={!baselineExecutor?.id}
                  onClick={() => baselineExecutor?.id && onRefreshExecutor(baselineExecutor.id)}
                >
                  刷新主服务器
                </Button>
                <Button
                  variant="outline"
                  disabled={!baselineExecutor?.id}
                  onClick={() => {
                    const snapshot = buildDiffSnapshot();
                    if (!snapshot) return;
                    onOpenDiffDialog('ComfyUI 服务器差异汇总', snapshot);
                  }}
                >
                  查看差异汇总
                </Button>
                <Button
                  variant="outline"
                  disabled={!baselineExecutor?.id}
                  onClick={() => {
                    const snapshot = buildDiffSnapshot();
                    if (!snapshot) return;
                    onDownloadJson(snapshot, withTimestamp('comfyui-diff'));
                  }}
                >
                  导出差异
                </Button>
                <Button theme="primary" loading={diffSaving} disabled={!baselineExecutor?.id} onClick={onSaveDiffSnapshot}>
                  保存对齐结果
                </Button>
              </Space>
              {baselineExecutor ? (
                <div className="text-xs text-slate-500">
                  主服务器：{baselineExecutor.name} · {baselineExecutor.id}
                </div>
              ) : null}
            </Space>

            {executors.length === 0 ? (
              <Alert theme="warning" message="还没有 ComfyUI 执行节点，请先新增服务器。" />
            ) : (
              <div className="space-y-3">
                {executors.map((executor) => {
                  const isBaseline = executor.id === baselineExecutor?.id;
                  const modelCatalog = modelCache[executor.id];
                  const modelCounts = extractModelCounts(modelCatalog);
                  const modelLoaded = Boolean(modelCatalog && Object.keys(modelCatalog).length > 0);
                  const nodeKeys = nodeCache[executor.id] || [];
                  const nodesLoaded = nodeKeys.length > 0;
                  const diffSnapshot = buildServerDiff(executor);
                  const missingUnet = diffSnapshot.missing.unet;
                  const missingClip = diffSnapshot.missing.clip;
                  const missingVae = diffSnapshot.missing.vae;
                  const missingLora = diffSnapshot.missing.lora;
                  const missingNodes = diffSnapshot.missing.nodes;
                  const missingTotal = countMissingItems(diffSnapshot);
                  const systemInfo = systemCache[executor.id];
                  const versionInfo = extractVersionInfo(executor, systemInfo);
                  const systemLoading = Boolean(systemLoadingByExecutor[executor.id]);
                  const modelLoading = Boolean(modelLoadingByExecutor[executor.id]);
                  const systemError = systemErrorByExecutor[executor.id];
                  const modelError = modelErrorByExecutor[executor.id];
                  return (
                    <div
                      key={`comfy-server-${executor.id}`}
                      className="rounded-2xl border border-slate-200/70 bg-white/80 p-4 dark:border-slate-800 dark:bg-slate-900/40"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <div className="truncate font-semibold text-slate-900 dark:text-white">{executor.name}</div>
                            <StatusBadge status={executor.status} />
                            {isBaseline ? (
                              <Tag theme="primary" variant="light">
                                主服务器
                              </Tag>
                            ) : null}
                          </div>
                          <div className="mt-1 truncate text-xs text-slate-600 dark:text-slate-400">
                            {executor.base_url || '—'}
                          </div>
                          <div className="mt-1 text-xs text-slate-500">
                            并发/权重：{executor.max_concurrency}/{executor.weight}
                          </div>
                          <div className="mt-2 flex flex-wrap gap-2 text-[11px]">
                            <Tag theme={executor.status === 'active' ? 'success' : 'warning'} variant="light">
                              {getServerStatusText(executor)}
                            </Tag>
                            <Tag theme={modelLoaded || nodesLoaded ? 'success' : 'warning'} variant="light">
                              {modelLoaded || nodesLoaded ? '已拉取资源' : '待刷新资源'}
                            </Tag>
                            {!isBaseline && hasBaseline ? (
                              <Tag theme={missingTotal > 0 ? 'danger' : 'success'} variant="light">
                                {missingTotal > 0 ? `缺 ${missingTotal} 项` : '资源对齐'}
                              </Tag>
                            ) : null}
                          </div>
                        </div>
                        <div className="shrink-0 text-right text-xs text-slate-500">
                          <button
                            className="rounded border border-slate-300 bg-white px-2 py-1 text-[11px] text-slate-700 hover:bg-slate-50 disabled:opacity-60 dark:border-slate-700 dark:bg-slate-950/60 dark:text-slate-200 dark:hover:bg-slate-900/60"
                            onClick={() => onRefreshExecutor(executor.id)}
                            disabled={systemLoading || modelLoading}
                          >
                            {systemLoading || modelLoading ? '刷新中…' : '刷新'}
                          </button>
                        </div>
                      </div>

                      <div className="mt-3 grid gap-2 sm:grid-cols-3">
                        <div className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700 dark:border-slate-800 dark:bg-slate-950/40 dark:text-slate-300">
                          <div className="text-[10px] uppercase tracking-widest text-slate-500">版本</div>
                          <div className="mt-1 text-sm font-semibold text-slate-900 dark:text-white">
                            {versionInfo?.version || '—'}
                          </div>
                          <div className="mt-1 text-[11px] text-slate-500">插件节点：{nodeKeys.length || '—'}</div>
                          {versionInfo?.customNodes ? (
                            <div className="mt-1 text-[11px] text-slate-500">插件版本：{versionInfo.customNodes}</div>
                          ) : null}
                          {systemError ? <div className="mt-1 text-[11px] text-rose-500">{systemError}</div> : null}
                        </div>
                        <div className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700 dark:border-slate-800 dark:bg-slate-950/40 dark:text-slate-300">
                          <div className="text-[10px] uppercase tracking-widest text-slate-500">模型 / LoRA</div>
                          <div className="mt-1 text-sm font-semibold text-slate-900 dark:text-white">
                            {modelLoaded ? `${modelCounts.unet}/${modelCounts.lora}` : '—'}
                          </div>
                          <div className="mt-1 text-[11px] text-slate-500">unet/lora</div>
                          {modelError ? <div className="mt-1 text-[11px] text-rose-500">{modelError}</div> : null}
                        </div>
                        <div className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700 dark:border-slate-800 dark:bg-slate-950/40 dark:text-slate-300">
                          <div className="text-[10px] uppercase tracking-widest text-slate-500">差异提示</div>
                          <div className="mt-1 text-[11px] text-slate-500">
                            {isBaseline ? '主服务器无需对比' : '对比模型 + 插件'}
                          </div>
                          <div className="mt-2 space-y-1 text-[11px] text-slate-600 dark:text-slate-400">
                            <div className="flex items-center justify-between">
                              <span>UNET</span>
                              {isBaseline ? (
                                <Tag theme="success" variant="light">
                                  主服务器
                                </Tag>
                              ) : (
                                renderDiffTag({ baselineReady: baselineUnetReady, targetReady: modelLoaded, missing: missingUnet })
                              )}
                            </div>
                            <div className="flex items-center justify-between">
                              <span>CLIP</span>
                              {isBaseline ? (
                                <Tag theme="success" variant="light">
                                  主服务器
                                </Tag>
                              ) : (
                                renderDiffTag({ baselineReady: baselineClipReady, targetReady: modelLoaded, missing: missingClip })
                              )}
                            </div>
                            <div className="flex items-center justify-between">
                              <span>VAE</span>
                              {isBaseline ? (
                                <Tag theme="success" variant="light">
                                  主服务器
                                </Tag>
                              ) : (
                                renderDiffTag({ baselineReady: baselineVaeReady, targetReady: modelLoaded, missing: missingVae })
                              )}
                            </div>
                            <div className="flex items-center justify-between">
                              <span>LoRA</span>
                              {isBaseline ? (
                                <Tag theme="success" variant="light">
                                  主服务器
                                </Tag>
                              ) : (
                                renderDiffTag({ baselineReady: baselineLoraReady, targetReady: modelLoaded, missing: missingLora })
                              )}
                            </div>
                            <div className="flex items-center justify-between">
                              <span>插件节点</span>
                              {isBaseline ? (
                                <Tag theme="success" variant="light">
                                  主服务器
                                </Tag>
                              ) : (
                                renderDiffTag({
                                  baselineReady: baselineNodesReady,
                                  targetReady: nodesLoaded,
                                  missing: missingNodes,
                                  okLabel: '对齐',
                                })
                              )}
                            </div>
                          </div>
                        </div>
                      </div>
                      {!isBaseline && (
                        <div className="mt-3 flex flex-wrap gap-2 text-[11px]">
                          <button
                            className="rounded border border-slate-300 bg-white px-2 py-1 text-slate-600 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-950/60 dark:text-slate-300 dark:hover:bg-slate-900/60"
                            onClick={() =>
                              onOpenDiffDialog(`${executor.name} · 差异明细`, {
                                ...diffSnapshot,
                                generatedAt: new Date().toISOString(),
                              })
                            }
                          >
                            查看差异清单
                          </button>
                          <button
                            className="rounded border border-slate-300 bg-white px-2 py-1 text-slate-600 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-950/60 dark:text-slate-300 dark:hover:bg-slate-900/60"
                            onClick={() =>
                              onDownloadJson(
                                { ...diffSnapshot, generatedAt: new Date().toISOString() },
                                withTimestamp(`comfyui-diff-${executor.id}`),
                              )
                            }
                          >
                            导出差异清单
                          </button>
                          <button
                            className="rounded border border-slate-300 bg-white px-2 py-1 text-slate-600 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-950/60 dark:text-slate-300 dark:hover:bg-slate-900/60"
                            onClick={() =>
                              onDownloadJson(
                                {
                                  generatedAt: new Date().toISOString(),
                                  baseline: diffSnapshot.baseline,
                                  server: diffSnapshot.server,
                                  repos: diffSnapshot.missing_repo_groups?.repos || [],
                                  missing_repo_nodes: diffSnapshot.missing_repo_groups?.missingRepoNodes || [],
                                },
                                withTimestamp(`comfyui-repo-diff-${executor.id}`),
                              )
                            }
                          >
                            导出仓库清单
                          </button>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </Space>
        </Card>
        {assistOpen ? (
          <div className="space-y-4">
            <Card bordered title="新增 ComfyUI 服务器" style={{ width: '100%' }}>
              <Space direction="vertical" size="small" style={{ width: '100%' }}>
                <Input
                  value={serverForm.name}
                  onChange={(value) => onServerFormChange({ name: String(value) })}
                  placeholder="服务器名称（如 ComfyUI-158）"
                />
                <Input
                  value={serverForm.base_url}
                  onChange={(value) => onServerFormChange({ base_url: String(value) })}
                  placeholder="服务地址（例如 http://117.50.80.158:8079）"
                />
                <Row gutter={[12, 12]}>
                  <Col span={12}>
                    <Typography.Text theme="secondary">并发</Typography.Text>
                    <InputNumber
                      min={1}
                      max={50}
                      value={Number(serverForm.max_concurrency)}
                      onChange={(value) => onServerFormChange({ max_concurrency: Number(value) || 1 })}
                    />
                  </Col>
                  <Col span={12}>
                    <Typography.Text theme="secondary">权重</Typography.Text>
                    <InputNumber
                      min={1}
                      max={999}
                      value={Number(serverForm.weight)}
                      onChange={(value) => onServerFormChange({ weight: Number(value) || 1 })}
                    />
                  </Col>
                </Row>
                <div>
                  <Typography.Text theme="secondary">状态</Typography.Text>
                  <Select
                    value={serverForm.status || 'active'}
                    onChange={(value) => onServerFormChange({ status: String(value) })}
                    options={statusOptions}
                  />
                </div>
                {serverFormError ? <Alert theme="error" message={serverFormError} /> : null}
                <Button theme="primary" loading={serverSaving} onClick={onCreateServer}>
                  新增服务器
                </Button>
                <div className="text-xs text-slate-500">新增后会出现在“执行节点”列表中，可再配置权重/并发。</div>
              </Space>
            </Card>
            <Card bordered title="最近对齐记录" style={{ width: '100%' }}>
              <Space direction="vertical" size="small" style={{ width: '100%' }}>
                <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
                  <Typography.Text theme="secondary">最近保存的对齐快照（最多 12 条）。</Typography.Text>
                  <Button size="small" variant="outline" onClick={onRefreshDiffLogs}>
                    刷新
                  </Button>
                </Space>
                {diffLogsError ? <Alert theme="error" message={diffLogsError} /> : null}
                <div className="max-h-[320px] overflow-auto rounded-2xl border border-slate-200/70 dark:border-slate-800">
                  <table className="w-full text-xs">
                    <thead className="sticky top-0 bg-slate-50 text-[11px] text-slate-600 dark:bg-slate-900/80 dark:text-slate-400">
                      <tr className="text-left">
                        <th className="px-3 py-2">时间</th>
                        <th className="px-3 py-2">主服务器</th>
                        <th className="px-3 py-2 text-right">操作</th>
                      </tr>
                    </thead>
                    <tbody>
                      {diffLogs.length === 0 ? (
                        <tr>
                          <td colSpan={3} className="px-4 py-6 text-center text-slate-500">
                            {diffLogsLoading ? '加载中…' : '暂无记录'}
                          </td>
                        </tr>
                      ) : (
                        diffLogs.map((item) => (
                          <tr key={`comfy-diff-log-${item.id}`} className="border-t border-slate-100 dark:border-slate-800">
                            <td className="px-3 py-2 text-slate-600 dark:text-slate-400">
                              {item.created_at ? formatDateTime(item.created_at) : '—'}
                            </td>
                            <td className="px-3 py-2 text-slate-600 dark:text-slate-400">{item.baseline_executor_id}</td>
                            <td className="px-3 py-2 text-right space-x-2">
                              <button
                                className="text-sky-400"
                                onClick={() => onOpenDiffDialog('对齐记录详情', item.payload || {})}
                              >
                                查看
                              </button>
                              <button
                                className="text-slate-500"
                                onClick={() =>
                                  onDownloadJson(item.payload || {}, withTimestamp(`comfyui-diff-log-${item.id}`))
                                }
                              >
                                导出
                              </button>
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </Space>
            </Card>
          </div>
        ) : (
          <Alert
            theme="info"
            message={`辅助面板已折叠：当前节点 ${executors.length} 台，对齐记录 ${diffLogs.length} 条。需要新增服务器或查看历史对齐时，可在顶部“展开辅助面板”。`}
          />
        )}
      </div>
      <Dialog
        header={diffDialogTitle || '差异明细'}
        visible={diffDialogOpen}
        width={720}
        confirmBtn={{ content: '关闭' }}
        onClose={onCloseDiffDialog}
        onConfirm={onCloseDiffDialog}
      >
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Space align="center" size="small" style={{ justifyContent: 'space-between', width: '100%' }}>
            <Typography.Text theme="secondary">导出/复制差异清单，方便给开发对齐服务器。</Typography.Text>
            <Space size="small">
              <Button size="small" variant="outline" disabled={!diffDialogText} onClick={() => onCopyText(diffDialogText)}>
                复制原始数据
              </Button>
              <Button
                size="small"
                variant="outline"
                disabled={!diffDialogPayload}
                onClick={() => diffDialogPayload && onDownloadJson(diffDialogPayload, withTimestamp('comfyui-diff'))}
              >
                导出原始数据
              </Button>
            </Space>
          </Space>
          <Textarea value={diffDialogText} readonly autosize={{ minRows: 12, maxRows: 20 }} className="font-mono text-xs" />
        </Space>
      </Dialog>
    </div>
  );
}
