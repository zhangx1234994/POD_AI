import type { Dispatch, SetStateAction } from 'react';
import { Alert, Button, Card, Col, Input, InputNumber, Row, Select, Space, Textarea, Tooltip, Typography } from 'tdesign-react';
import type { ComfyuiQueueStatus, ComfyuiQueueSummary, Executor, ExecutorFormState, JsonRecord } from '../../../types/admin';
import { ActionBar, StatusBadge } from '../shared/ui';

type ExecutorsView = 'list' | 'channels';

type ExecutorTraffic = {
  count: number;
  success: number;
  failed: number;
  successRate: number | null;
  lastSuccessAt?: string | null;
  lastFailedAt?: string | null;
  p95Ms?: number | null;
};

type ExecutorTrafficTotals = {
  totalCalls: number;
  failedCalls: number;
  successRate: number | null;
};

type IntegrationSummary = {
  executors: number;
  activeExecutors: number;
};

type ExecutorConfigTemplate = {
  key: string;
  label: string;
  hint: string;
  placeholder?: string;
};

type ComfyuiModelCounts = {
  unet: number;
  clip: number;
  vae: number;
  lora: number;
};

type ComfyuiVersionInfo = {
  version: string;
  commit: string;
  customNodes: string;
  modelsHash: string;
  loraHash: string;
  syncRole: string;
  lastSyncAt: string;
};

type ExecutorsPanelProps = {
  comfyExecutors: Executor[];
  comfyModelCache: Record<string, Record<string, string[]>>;
  comfyModelErrorByExecutor: Record<string, string>;
  comfyModelLoadingByExecutor: Record<string, boolean>;
  comfyQueueByExecutor: Record<string, ComfyuiQueueStatus>;
  comfyQueueSummary: ComfyuiQueueSummary | null;
  comfyQueueSummaryError: string | null;
  comfyQueueSummaryLoading: boolean;
  comfyQueueSummaryUpdatedAt: string | null;
  comfySystemCache: Record<string, Record<string, unknown>>;
  comfySystemErrorByExecutor: Record<string, string>;
  comfySystemLoadingByExecutor: Record<string, boolean>;
  executorConfigJsonInvalid: string | null;
  executorConfigRecord: JsonRecord;
  executorConfigTemplates: ExecutorConfigTemplate[];
  executorForm: ExecutorFormState;
  executorFormError: string | null;
  executorInlineConcurrency: Record<string, number>;
  executorInlineError: Record<string, string>;
  executorInlineSaving: Record<string, boolean>;
  executorTraffic: Record<string, ExecutorTraffic>;
  executorTrafficError: string | null;
  executorTrafficLoading: boolean;
  executorTrafficTotals: ExecutorTrafficTotals;
  executors: Executor[];
  executorsView: ExecutorsView;
  extractComfyuiModelCounts: (catalog?: Record<string, string[]>) => ComfyuiModelCounts;
  extractComfyuiVersionInfo: (executor?: Executor | null, system?: Record<string, unknown> | null) => ComfyuiVersionInfo;
  extractExecutorTags: (executor: Executor) => string[];
  formatDate: (value: string) => string;
  formatDateTime: (value?: string | null) => string;
  getExecutorChannelLabel: (executor: Executor) => string;
  handleDelete: (kind: 'executor' | 'workflow' | 'binding' | 'apikey', id: string) => void | Promise<void>;
  handleExecutorSubmit: () => void | Promise<void>;
  refreshComfyQueueSummary: () => void | Promise<void>;
  refreshComfyuiModelCatalog: (executorId: string) => void | Promise<void>;
  refreshComfyuiSystemStats: (executorId: string) => void | Promise<void>;
  refreshExecutorTraffic: () => void | Promise<void>;
  saveExecutorConcurrency: (executorId: string) => void | Promise<void>;
  setExecutorConfigField: (key: string, value: string) => void;
  setExecutorForm: Dispatch<SetStateAction<ExecutorFormState>>;
  setExecutorFormError: Dispatch<SetStateAction<string | null>>;
  setExecutorInlineConcurrency: Dispatch<SetStateAction<Record<string, number>>>;
  setExecutorsView: Dispatch<SetStateAction<ExecutorsView>>;
  stringifyJSON: (value?: string | JsonRecord) => string;
  summary: IntegrationSummary;
};

const formatQueuePercent = (value?: number | null) => {
  if (typeof value !== 'number' || Number.isNaN(value)) return '—';
  return `${Math.round(value * 100)}%`;
};

const mapDiagnosticTheme = (level?: string | null): 'success' | 'info' | 'warning' | 'error' => {
  if (level === 'danger') return 'error';
  if (level === 'warning') return 'warning';
  if (level === 'success') return 'success';
  return 'info';
};

const defaultExecutorForm: ExecutorFormState = { status: 'inactive', weight: 1, max_concurrency: 1 };

function StatusPill({ status }: { status: string }) {
  return <StatusBadge status={status} />;
}

export function ExecutorsPanel({
  comfyExecutors,
  comfyModelCache,
  comfyModelErrorByExecutor,
  comfyModelLoadingByExecutor,
  comfyQueueByExecutor,
  comfyQueueSummary,
  comfyQueueSummaryError,
  comfyQueueSummaryLoading,
  comfyQueueSummaryUpdatedAt,
  comfySystemCache,
  comfySystemErrorByExecutor,
  comfySystemLoadingByExecutor,
  executorConfigJsonInvalid,
  executorConfigRecord,
  executorConfigTemplates,
  executorForm,
  executorFormError,
  executorInlineConcurrency,
  executorInlineError,
  executorInlineSaving,
  executorTraffic,
  executorTrafficError,
  executorTrafficLoading,
  executorTrafficTotals,
  executors,
  executorsView,
  extractComfyuiModelCounts,
  extractComfyuiVersionInfo,
  extractExecutorTags,
  formatDate,
  formatDateTime,
  getExecutorChannelLabel,
  handleDelete,
  handleExecutorSubmit,
  refreshComfyQueueSummary,
  refreshComfyuiModelCatalog,
  refreshComfyuiSystemStats,
  refreshExecutorTraffic,
  saveExecutorConcurrency,
  setExecutorConfigField,
  setExecutorForm,
  setExecutorFormError,
  setExecutorInlineConcurrency,
  setExecutorsView,
  stringifyJSON,
  summary,
}: ExecutorsPanelProps) {
  return (
    <>
        <ActionBar>
          <Space align="center" style={{ justifyContent: 'space-between', width: '100%', flexWrap: 'wrap' }}>
            <Typography.Text theme="secondary">
              同一能力可配置多条运行线路（多中转站 / 多 ComfyUI 服务器），调度会基于优先级与健康度选择可用线路。
            </Typography.Text>
            <Space>
              <Button
                size="small"
                variant={executorsView === 'channels' ? 'base' : 'outline'}
                onClick={() => setExecutorsView('channels')}
              >
                线路视图
              </Button>
              <Button size="small" variant={executorsView === 'list' ? 'base' : 'outline'} onClick={() => setExecutorsView('list')}>
                详细编辑
              </Button>
              <Button
                size="small"
                variant="outline"
                onClick={() => refreshExecutorTraffic()}
                loading={executorTrafficLoading}
                title="刷新近 24h 调用指标（成功率/失败/耗时）"
              >
                刷新指标
              </Button>
              <Button
                size="small"
                variant="outline"
                onClick={() => refreshComfyQueueSummary()}
                loading={comfyQueueSummaryLoading}
                disabled={comfyExecutors.length === 0}
                title="刷新 ComfyUI 队列汇总"
              >
                刷新队列
              </Button>
            </Space>
          </Space>
        </ActionBar>

        <Card bordered style={{ marginBottom: 16 }}>
          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
            <div>
              <Typography.Text strong>运行线路判断</Typography.Text>
              <div className="mt-1 text-xs text-slate-500">
                普通用户先看这里：确认有可用线路、没有明显排队、最近调用没有集中失败，再进入“详细编辑”改配置。
              </div>
            </div>
            <div className="grid gap-3 md:grid-cols-6">
              <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 dark:border-slate-800 dark:bg-slate-950/40">
                <div className="text-sm font-semibold text-slate-900 dark:text-white">
                  可用线路 {summary.activeExecutors}/{summary.executors}
                </div>
                <div className="mt-1 text-xs text-slate-500">
                  {summary.executors === 0
                    ? '还没有运行线路，能力无法执行。'
                    : summary.activeExecutors === summary.executors
                      ? '全部线路可用。'
                      : `${summary.executors - summary.activeExecutors} 条线路不可用，建议进入详细编辑检查。`}
                </div>
              </div>
              <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 dark:border-slate-800 dark:bg-slate-950/40">
                <div className="text-sm font-semibold text-slate-900 dark:text-white">
                  图像执行线路 {comfyExecutors.length} 条
                </div>
                <div className="mt-1 text-xs text-slate-500">
                  {comfyExecutors.length > 0 ? 'ComfyUI 能力有独立执行线路。' : '未配置 ComfyUI 线路，图像工作流会不可用。'}
                </div>
              </div>
              <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 dark:border-slate-800 dark:bg-slate-950/40">
                <div className="text-sm font-semibold text-slate-900 dark:text-white">
                  {
                  comfyQueueSummary
                    ? `ComfyUI 等待 ${comfyQueueSummary.totalPending} · 执行 ${comfyQueueSummary.totalRunning}`
                    : comfyQueueSummaryLoading
                      ? '队列检查中'
                      : '队列待刷新'
                  }
                </div>
                <div className="mt-1 text-xs text-slate-500">
                  {
                  comfyQueueSummary
                    ? comfyQueueSummary.totalPending > 0
                      ? '有任务等待，优先观察是否持续堆积。'
                      : '当前没有明显排队。'
                    : '点击“刷新队列”获取实时状态。'
                  }
                </div>
              </div>
              <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 dark:border-slate-800 dark:bg-slate-950/40">
                <div className="text-sm font-semibold text-slate-900 dark:text-white">
                  {comfyQueueSummary
                    ? `中台待下发 ${comfyQueueSummary.backendQueuedTotal ?? 0}`
                    : comfyQueueSummaryLoading
                      ? '中台任务读取中'
                      : '中台任务待刷新'}
                </div>
                <div className="mt-1 text-xs text-slate-500">
                  {comfyQueueSummary
                    ? `执行中 ${comfyQueueSummary.backendRunningTotal ?? 0} · 积压 ${comfyQueueSummary.backendActiveTotal ?? 0}`
                    : '用于判断中台是否持续给 ComfyUI 下发任务。'}
                </div>
              </div>
              <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 dark:border-slate-800 dark:bg-slate-950/40">
                <div className="text-sm font-semibold text-slate-900 dark:text-white">
                  {comfyQueueSummary
                    ? `容量 ${comfyQueueSummary.totalCount}/${comfyQueueSummary.totalCapacity ?? '—'}`
                    : comfyQueueSummaryLoading
                      ? '容量计算中'
                      : '容量待刷新'}
                </div>
                <div className="mt-1 text-xs text-slate-500">
                  {comfyQueueSummary
                    ? `空闲 ${comfyQueueSummary.totalIdleSlots ?? '—'} · 使用率 ${formatQueuePercent(comfyQueueSummary.utilization)}`
                    : '用于判断 GPU 是否持续有任务可消费。'}
                </div>
              </div>
              <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 dark:border-slate-800 dark:bg-slate-950/40">
                <div className="text-sm font-semibold text-slate-900 dark:text-white">
                  {
                  executorTrafficLoading
                    ? '调用指标刷新中'
                    : executorTrafficTotals.totalCalls > 0
                      ? `近24小时 ${executorTrafficTotals.totalCalls} 次`
                      : '近24小时暂无调用'
                  }
                </div>
                <div className="mt-1 text-xs text-slate-500">
                  {
                  executorTrafficError
                    ? '调用指标读取失败，先确认后端监控接口。'
                    : executorTrafficTotals.totalCalls > 0
                      ? `成功率 ${executorTrafficTotals.successRate ?? '—'}%，失败 ${executorTrafficTotals.failedCalls} 次。`
                      : '没有调用记录时无法判断质量。'
                  }
                </div>
              </div>
            </div>
            {comfyQueueSummary?.diagnostics?.length ? (
              <Space direction="vertical" size="small" style={{ width: '100%' }}>
                {comfyQueueSummary.diagnostics.map((item) => (
                  <Alert
                    key={`${item.code}-${item.level}`}
                    theme={mapDiagnosticTheme(item.level)}
                    message={item.message}
                  />
                ))}
              </Space>
            ) : null}
          </Space>
        </Card>

        {executorsView === 'channels' ? (
          <div className="space-y-4">
            {executorTrafficError && (
              <Alert theme="error" message={executorTrafficError} />
            )}
            {comfyQueueSummaryError && (
              <Alert theme="error" message={`ComfyUI 队列：${comfyQueueSummaryError}`} />
            )}
            {(() => {
              const groups = new Map<string, Executor[]>();
              executors.forEach((ex: Executor) => {
                const key = ex.type || 'unknown';
                const list = groups.get(key) || [];
                list.push(ex);
                groups.set(key, list);
              });
              const entries = Array.from(groups.entries()).sort(([a], [b]) => a.localeCompare(b));
              if (entries.length === 0) {
                return <div className="text-sm text-slate-500">暂无运行线路，请先新增。</div>;
              }
              return (
                <div className="grid gap-4 lg:grid-cols-2">
                  {entries.map(([type, items]) => {
                    const activeCount = items.filter((x) => x.status === 'active').length;
                    const typeLower = (type || '').toLowerCase();
                    const isComfyGroup = typeLower.includes('comfyui');
                    const queueSummary = isComfyGroup ? comfyQueueSummary : null;
                    const queueSummaryTimestamp = queueSummary?.timestamp || comfyQueueSummaryUpdatedAt;
                    return (
                      <div
                        key={`channel-group-${type}`}
                        className="rounded-2xl border border-slate-200/70 bg-white/80 p-5 dark:border-slate-800 dark:bg-slate-900/40"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <div className="text-xs uppercase tracking-[0.35em] text-slate-500">线路类型</div>
                            <div className="mt-2 text-lg font-semibold text-slate-900 dark:text-white">{type}</div>
                            <div className="mt-1 text-xs text-slate-600 dark:text-slate-400">
                              {activeCount}/{items.length} 可用 · 建议至少 2 条线路做容灾（主/备）
                            </div>
                            {isComfyGroup && (
                              <div className="mt-2 text-xs text-slate-600 dark:text-slate-400">
                                {comfyQueueSummaryLoading
                                  ? 'ComfyUI 队列：加载中…'
                                  : queueSummary
                                    ? `ComfyUI 队列：执行中 ${queueSummary.totalRunning} · 等待 ${queueSummary.totalPending}`
                                    : 'ComfyUI 队列：—'}
                                {queueSummaryTimestamp ? (
                                  <span className="ml-2 text-[11px] text-slate-500">
                                    更新：{formatDateTime(queueSummaryTimestamp)}
                                  </span>
                                ) : null}
                              </div>
                            )}
                          </div>
                        </div>

                        <div className="mt-4 space-y-3">
                          {items
                            .slice()
                            .sort((a, b) => (b.weight || 0) - (a.weight || 0))
                            .map((ex) => {
                              const metric = executorTraffic[ex.id];
                              const isComfyExecutor = (ex.type || '').toLowerCase().includes('comfyui');
                              const queueStatus = isComfyExecutor ? comfyQueueByExecutor[ex.id] : null;
                              const modelCatalog = isComfyExecutor ? comfyModelCache[ex.id] : undefined;
                              const modelCounts = isComfyExecutor ? extractComfyuiModelCounts(modelCatalog) : null;
                              const systemInfo = isComfyExecutor ? comfySystemCache[ex.id] : undefined;
                              const versionInfo = isComfyExecutor ? extractComfyuiVersionInfo(ex, systemInfo) : null;
                              const modelLoading = Boolean(comfyModelLoadingByExecutor[ex.id]);
                              const modelError = comfyModelErrorByExecutor[ex.id];
                              const systemLoading = Boolean(comfySystemLoadingByExecutor[ex.id]);
                              const systemError = comfySystemErrorByExecutor[ex.id];
                              return (
                                <div
                                  key={`channel-${ex.id}`}
                                  className="rounded-2xl border border-slate-200 bg-slate-50/50 p-4 dark:border-slate-800 dark:bg-slate-950/20"
                                >
                                  <div className="flex items-start justify-between gap-3">
                                    <div className="min-w-0">
                                      <div className="flex items-center gap-2">
                                        <div className="truncate font-semibold text-slate-900 dark:text-white">
                                          {getExecutorChannelLabel(ex)}
                                        </div>
                                        <StatusPill status={ex.status} />
                                      </div>
                                      <div className="mt-1 truncate text-xs text-slate-600 dark:text-slate-400">
                                        {ex.base_url || '—'}
                                      </div>
                                      {extractExecutorTags(ex).length > 0 ? (
                                        <div className="mt-2 flex flex-wrap gap-1">
                                          {extractExecutorTags(ex).map((tag: string) => (
                                            <span
                                              key={`${ex.id}-tag-${tag}`}
                                              className="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[11px] text-slate-600 dark:border-slate-700 dark:bg-slate-950/40 dark:text-slate-300"
                                            >
                                              {tag}
                                            </span>
                                          ))}
                                        </div>
                                      ) : null}
                                    </div>
                                    <div className="shrink-0 text-right text-xs text-slate-600 dark:text-slate-400">
                                      <div>
                                        并发/权重：{ex.max_concurrency}/{ex.weight}
                                      </div>
                                      <div>心跳：{ex.last_heartbeat_at ? formatDate(ex.last_heartbeat_at) : '—'}</div>
                                    </div>
                                  </div>

                                  <div className="mt-3 grid gap-2 sm:grid-cols-3">
                                    <div className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700 dark:border-slate-800 dark:bg-slate-950/40 dark:text-slate-300">
                                      <div className="text-[10px] tracking-widest text-slate-500">近24小时调用</div>
                                      <div className="mt-1 text-sm font-semibold text-slate-900 dark:text-white">
                                        {metric ? metric.count : '—'}
                                      </div>
                                    </div>
                                    <div className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700 dark:border-slate-800 dark:bg-slate-950/40 dark:text-slate-300">
                                      <div className="text-[10px] tracking-widest text-slate-500">成功率</div>
                                      <div className="mt-1 text-sm font-semibold text-slate-900 dark:text-white">
                                        {metric && metric.successRate !== null ? `${Math.round(metric.successRate * 100)}%` : '—'}
                                      </div>
                                      {metric?.lastFailedAt && (
                                        <div className="mt-1 text-[11px] text-rose-700 dark:text-rose-300">
                                          最近失败：{formatDateTime(metric.lastFailedAt)}
                                        </div>
                                      )}
                                    </div>
                                    <div className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700 dark:border-slate-800 dark:bg-slate-950/40 dark:text-slate-300">
                                      <div className="text-[10px] tracking-widest text-slate-500">耗时 P95</div>
                                      <div className="mt-1 text-sm font-semibold text-slate-900 dark:text-white">
                                        {metric?.p95Ms ? `${Math.round(metric.p95Ms)}ms` : '—'}
                                      </div>
                                      <div className="mt-1 text-[11px] text-slate-500">
                                        路由：按“路由策略”优先级（后续支持失败/超时自动回退）
                                      </div>
                                    </div>
                                    {isComfyExecutor && (
                                      <div className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700 dark:border-slate-800 dark:bg-slate-950/40 dark:text-slate-300">
                                        <div className="text-[10px] tracking-widest text-slate-500">队列</div>
                                        <div className="mt-1 text-sm font-semibold text-slate-900 dark:text-white">
                                          {queueStatus
                                            ? `${queueStatus.runningCount}/${queueStatus.pendingCount}`
                                            : comfyQueueSummaryLoading
                                              ? '加载中…'
                                              : '—'}
                                        </div>
                                        <div className="mt-1 text-[11px] text-slate-500">执行中 / 等待中</div>
                                        {queueStatus?.message ? (
                                          <div className="mt-1 text-[11px] text-amber-600">{queueStatus.message}</div>
                                        ) : null}
                                      </div>
                                    )}
                                    {isComfyExecutor && (
                                      <div className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700 dark:border-slate-800 dark:bg-slate-950/40 dark:text-slate-300">
                                        <div className="text-[10px] tracking-widest text-slate-500">容量使用</div>
                                        <div className="mt-1 text-sm font-semibold text-slate-900 dark:text-white">
                                          {queueStatus
                                            ? `${queueStatus.totalCount ?? queueStatus.runningCount + queueStatus.pendingCount}/${queueStatus.capacityTarget ?? '—'}`
                                            : comfyQueueSummaryLoading
                                              ? '加载中…'
                                              : '—'}
                                        </div>
                                        <div className="mt-1 text-[11px] text-slate-500">
                                          空闲 {queueStatus?.idleSlots ?? '—'} · 使用率 {formatQueuePercent(queueStatus?.utilization)}
                                        </div>
                                        {queueStatus?.diagnosis ? (
                                          <div
                                            className={
                                              queueStatus.diagnosisLevel === 'danger'
                                                ? 'mt-1 text-[11px] text-rose-600'
                                                : queueStatus.diagnosisLevel === 'warning'
                                                  ? 'mt-1 text-[11px] text-amber-600'
                                                  : 'mt-1 text-[11px] text-slate-500'
                                            }
                                          >
                                            {queueStatus.diagnosis}
                                          </div>
                                        ) : null}
                                      </div>
                                    )}
                                    {isComfyExecutor && (
                                      <div className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700 dark:border-slate-800 dark:bg-slate-950/40 dark:text-slate-300">
                                        <div className="text-[10px] tracking-widest text-slate-500">中台任务</div>
                                        <div className="mt-1 text-sm font-semibold text-slate-900 dark:text-white">
                                          {queueStatus
                                            ? `${queueStatus.backendQueued ?? 0}/${queueStatus.backendRunning ?? 0}`
                                            : comfyQueueSummaryLoading
                                              ? '加载中…'
                                              : '—'}
                                        </div>
                                        <div className="mt-1 text-[11px] text-slate-500">待下发 / 执行中</div>
                                        {queueStatus?.backendOldestQueuedAt ? (
                                          <div className="mt-1 text-[11px] text-amber-600">
                                            最早等待：{formatDateTime(queueStatus.backendOldestQueuedAt)}
                                          </div>
                                        ) : null}
                                      </div>
                                    )}
                                    {isComfyExecutor && (
                                      <div className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700 dark:border-slate-800 dark:bg-slate-950/40 dark:text-slate-300">
                                        <div className="text-[10px] tracking-widest text-slate-500">下发判断</div>
                                        <div
                                          className={
                                            queueStatus?.feedDiagnosisLevel === 'danger'
                                              ? 'mt-1 text-sm font-semibold text-rose-600'
                                              : queueStatus?.feedDiagnosisLevel === 'warning'
                                                ? 'mt-1 text-sm font-semibold text-amber-600'
                                                : 'mt-1 text-sm font-semibold text-slate-900 dark:text-white'
                                          }
                                        >
                                          {queueStatus?.feedCode
                                            ? queueStatus.feedCode === 'COMFYUI_FEED_GAP'
                                              ? '下发偏慢'
                                              : queueStatus.feedCode === 'BACKEND_NOT_FEEDING_COMFYUI'
                                                ? '疑似卡住'
                                                : queueStatus.feedCode === 'EXECUTOR_CAPACITY_BOUND'
                                                  ? '执行侧满载'
                                                  : queueStatus.feedCode === 'COMFYUI_CONSUMING_SUBMITTED_QUEUE'
                                                    ? '正在消化'
                                                    : '正常'
                                            : comfyQueueSummaryLoading
                                              ? '加载中…'
                                              : '—'}
                                        </div>
                                        {queueStatus?.feedDiagnosis ? (
                                          <div
                                            className={
                                              queueStatus.feedDiagnosisLevel === 'danger'
                                                ? 'mt-1 text-[11px] text-rose-600'
                                                : queueStatus.feedDiagnosisLevel === 'warning'
                                                  ? 'mt-1 text-[11px] text-amber-600'
                                                  : 'mt-1 text-[11px] text-slate-500'
                                            }
                                          >
                                            {queueStatus.feedDiagnosis}
                                          </div>
                                        ) : (
                                          <div className="mt-1 text-[11px] text-slate-500">
                                            对比中台任务与 ComfyUI 队列。
                                          </div>
                                        )}
                                      </div>
                                    )}
                                  </div>
                                  {isComfyExecutor && (
                                    <div className="mt-3 grid gap-2 sm:grid-cols-3">
                                      <div className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700 dark:border-slate-800 dark:bg-slate-950/40 dark:text-slate-300">
                                        <div className="text-[10px] uppercase tracking-widest text-slate-500">ComfyUI 版本</div>
                                        <div className="mt-1 text-sm font-semibold text-slate-900 dark:text-white">
                                          {versionInfo?.version || '—'}
                                        </div>
                                        <div className="mt-1 text-[11px] text-slate-500">
                                          节点：{versionInfo?.customNodes || '—'}
                                        </div>
                                        {systemError ? (
                                          <div className="mt-1 text-[11px] text-rose-500">{systemError}</div>
                                        ) : null}
                                      </div>
                                      <div className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700 dark:border-slate-800 dark:bg-slate-950/40 dark:text-slate-300">
                                        <div className="text-[10px] uppercase tracking-widest text-slate-500">模型/LoRA</div>
                                        <div className="mt-1 text-sm font-semibold text-slate-900 dark:text-white">
                                          {modelCatalog ? `${modelCounts?.unet || 0}/${modelCounts?.lora || 0}` : '—'}
                                        </div>
                                        <div className="mt-1 text-[11px] text-slate-500">unet/lora</div>
                                        {modelError ? (
                                          <div className="mt-1 text-[11px] text-rose-500">{modelError}</div>
                                        ) : null}
                                      </div>
                                      <div className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700 dark:border-slate-800 dark:bg-slate-950/40 dark:text-slate-300">
                                        <div className="text-[10px] uppercase tracking-widest text-slate-500">同步标记</div>
                                        <div className="mt-1 text-sm font-semibold text-slate-900 dark:text-white">
                                          {versionInfo?.syncRole || '—'}
                                        </div>
                                        <div className="mt-1 text-[11px] text-slate-500">
                                          {versionInfo?.lastSyncAt ? `更新：${versionInfo.lastSyncAt}` : '未标记时间'}
                                        </div>
                                        <div className="mt-2 grid grid-cols-2 gap-2">
                                          <button
                                            className="rounded border border-slate-300 bg-white px-2 py-1 text-[11px] text-slate-700 hover:bg-slate-50 disabled:opacity-60 dark:border-slate-700 dark:bg-slate-950/60 dark:text-slate-200 dark:hover:bg-slate-900/60"
                                            onClick={() => refreshComfyuiSystemStats(ex.id)}
                                            disabled={systemLoading}
                                          >
                                            {systemLoading ? '同步中…' : '拉取版本'}
                                          </button>
                                          <button
                                            className="rounded border border-slate-300 bg-white px-2 py-1 text-[11px] text-slate-700 hover:bg-slate-50 disabled:opacity-60 dark:border-slate-700 dark:bg-slate-950/60 dark:text-slate-200 dark:hover:bg-slate-900/60"
                                            onClick={() => refreshComfyuiModelCatalog(ex.id)}
                                            disabled={modelLoading}
                                          >
                                            {modelLoading ? '同步中…' : '拉取模型'}
                                          </button>
                                        </div>
                                      </div>
                                    </div>
                                  )}
                                </div>
                              );
                            })}
                        </div>
                      </div>
                    );
                  })}
                </div>
              );
            })()}
          </div>
        ) : (
          <Space direction="vertical" size="large" style={{ width: '100%' }}>
            <Row gutter={[16, 16]}>
              <Col xs={12} lg={7}>
                <Card bordered title="线路列表" style={{ width: '100%' }}>
                  <Space direction="vertical" size="small" style={{ width: '100%' }}>
                    <Typography.Text theme="secondary">
                      小贴士：并发保存后会立即生效；建议从 1~4 起逐步放量。
                    </Typography.Text>
                    <div style={{ overflowX: 'auto' }}>
                      <table style={{ width: '100%' }}>
                        <thead>
                          <tr style={{ textAlign: 'left' }}>
                            <th style={{ padding: '8px 6px' }}>名称</th>
                            <th style={{ padding: '8px 6px' }}>线路类型</th>
                            <th style={{ padding: '8px 6px' }}>状态</th>
                            <th style={{ padding: '8px 6px', width: 220 }}>并发</th>
                            <th style={{ padding: '8px 6px', width: 140 }}>权重</th>
                            <th style={{ padding: '8px 6px', width: 160 }}>心跳</th>
                            <th style={{ padding: '8px 6px', width: 120 }} />
                          </tr>
                        </thead>
                        <tbody>
                          {executors.map((ex: Executor) => {
                            const draft = Number(executorInlineConcurrency[ex.id] ?? ex.max_concurrency ?? 1) || 1;
                            const changed = draft !== ex.max_concurrency;
                            const saving = Boolean(executorInlineSaving[ex.id]);
                            const err = executorInlineError[ex.id];
                            const isComfyExecutor = (ex.type || '').toLowerCase().includes('comfyui');
                            const systemInfo = isComfyExecutor ? comfySystemCache[ex.id] : undefined;
                            const versionInfo = isComfyExecutor ? extractComfyuiVersionInfo(ex, systemInfo) : null;
                            const modelCatalog = isComfyExecutor ? comfyModelCache[ex.id] : undefined;
                            const modelCounts = isComfyExecutor ? extractComfyuiModelCounts(modelCatalog) : null;
                            const modelLoading = Boolean(comfyModelLoadingByExecutor[ex.id]);
                            const systemLoading = Boolean(comfySystemLoadingByExecutor[ex.id]);
                            return (
                              <tr key={ex.id}>
                                <td style={{ padding: '10px 6px' }}>
                                  <div style={{ fontWeight: 600 }}>{ex.name}</div>
                                  <Typography.Text theme="secondary">{ex.base_url || '—'}</Typography.Text>
                                  {extractExecutorTags(ex).length > 0 ? (
                                    <div className="mt-1 text-[11px] text-slate-500">
                                      标签：{extractExecutorTags(ex).join(', ')}
                                    </div>
                                  ) : null}
                                  {isComfyExecutor && (
                                    <div className="mt-1 text-[11px] text-slate-500">
                                      版本：{versionInfo?.version || '—'} · 模型/LoRA：{modelCatalog ? `${modelCounts?.unet || 0}/${modelCounts?.lora || 0}` : '—'}
                                    </div>
                                  )}
                                </td>
                                <td style={{ padding: '10px 6px' }}>
                                  <Typography.Text theme="secondary">{ex.type}</Typography.Text>
                                </td>
                                <td style={{ padding: '10px 6px' }}>
                                  <StatusPill status={ex.status} />
                                </td>
                                <td style={{ padding: '10px 6px' }}>
                                  <Space direction="vertical" size={2}>
                                    <Space align="center" size="small">
                                      <InputNumber
                                        size="small"
                                        min={1}
                                        max={50}
                                        value={draft}
                                        onChange={(v) =>
                                          setExecutorInlineConcurrency((prev: Record<string, number>) => ({ ...prev, [ex.id]: Number(v) || 1 }))
                                        }
                                      />
                                      <Button
                                        size="small"
                                        theme="primary"
                                        disabled={!changed || saving}
                                        loading={saving}
                                        onClick={() => saveExecutorConcurrency(ex.id)}
                                      >
                                        保存
                                      </Button>
                                    </Space>
                                    {err ? (
                                      <Typography.Text theme="error" style={{ fontSize: 12 }}>
                                        {err}
                                      </Typography.Text>
                                    ) : null}
                                  </Space>
                                </td>
                                <td style={{ padding: '10px 6px' }}>
                                  <Typography.Text theme="secondary">{ex.weight}</Typography.Text>
                                </td>
                                <td style={{ padding: '10px 6px' }}>
                                  <Typography.Text theme="secondary">{ex.last_heartbeat_at || '—'}</Typography.Text>
                                </td>
                                <td style={{ padding: '10px 6px' }}>
                                  <Space size="small">
                                    <Button
                                      size="small"
                                      variant="text"
                                      onClick={() => {
                                        const { config, ...rest } = ex;
                                        setExecutorForm({ ...rest, config: stringifyJSON(config) });
                                        setExecutorFormError(null);
                                      }}
                                    >
                                      编辑
                                    </Button>
                                    {isComfyExecutor && (
                                      <>
                                        <Button
                                          size="small"
                                          variant="text"
                                          disabled={systemLoading}
                                          onClick={() => refreshComfyuiSystemStats(ex.id)}
                                        >
                                          {systemLoading ? '同步中…' : '拉取版本'}
                                        </Button>
                                        <Button
                                          size="small"
                                          variant="text"
                                          disabled={modelLoading}
                                          onClick={() => refreshComfyuiModelCatalog(ex.id)}
                                        >
                                          {modelLoading ? '同步中…' : '拉取模型'}
                                        </Button>
                                      </>
                                    )}
                                    <Button size="small" theme="danger" variant="text" onClick={() => handleDelete('executor', ex.id)}>
                                      删除
                                    </Button>
                                  </Space>
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </Space>
                </Card>
              </Col>

              <Col xs={12} lg={5}>
                <Card bordered title={executorForm.id ? '编辑线路' : '新增线路'} style={{ width: '100%' }}>
                  <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                    {executorFormError ? <Alert theme="error" message={executorFormError} /> : null}
                    <div>
                      <Typography.Text strong>名称</Typography.Text>
                      <div style={{ marginTop: 8 }}>
                        <Input value={String(executorForm.name || '')} onChange={(v) => setExecutorForm({ ...executorForm, name: String(v) })} placeholder="例如：KIE Market · 默认线路" />
                      </div>
                    </div>

                    <div>
                      <Space align="center" size="small">
                        <Typography.Text strong>线路类型</Typography.Text>
                        <Tooltip content="常用：comfyui / kie / volcengine / baidu。用于路由与能力测试分支。">
                          <Typography.Text theme="secondary">?</Typography.Text>
                        </Tooltip>
                      </Space>
                      <div style={{ marginTop: 8 }}>
                        <Input
                          value={String(executorForm.type || '')}
                          onChange={(v) => {
                            const nextType = String(v);
                            setExecutorForm((prev: ExecutorFormState) => {
                              const base = { ...prev, type: nextType };
                              const norm = nextType.trim().toLowerCase();
                              if (!base.base_url) {
                                if (norm.includes('kie')) base.base_url = 'https://api.kie.ai';
                                else if (norm.includes('volc') || norm.includes('ark')) base.base_url = 'https://ark.cn-beijing.volces.com';
                                else if (norm.includes('baidu')) base.base_url = 'https://aip.baidubce.com';
                              }
                              return base;
                            });
                          }}
                          placeholder="comfyui / kie / volcengine / baidu"
                        />
                      </div>
                      <div style={{ marginTop: 8 }}>
                        <Space size="small">
                          {['comfyui', 'kie', 'volcengine', 'baidu'].map((t) => (
                            <Button key={`ex-type-${t}`} size="small" variant="outline" onClick={() => setExecutorForm((prev: ExecutorFormState) => ({ ...prev, type: t }))}>
                              {t}
                            </Button>
                          ))}
                        </Space>
                      </div>
                    </div>

                    <div>
                      <Typography.Text strong>服务地址</Typography.Text>
                      <Typography.Text theme="secondary" style={{ marginLeft: 8 }}>
                        （可选：部分厂商也可在高级配置中填写）
                      </Typography.Text>
                      <div style={{ marginTop: 8 }}>
                        <Input
                          value={String(executorForm.base_url || '')}
                          onChange={(v) => setExecutorForm({ ...executorForm, base_url: String(v) })}
                          placeholder="http://<ip>:<port> 或 https://..."
                        />
                      </div>
                    </div>

                    <Row gutter={[12, 12]}>
                      <Col xs={6}>
                        <Typography.Text strong>状态</Typography.Text>
                        <div style={{ marginTop: 8 }}>
                          <Select
                            value={String(executorForm.status || 'inactive')}
                            options={[
                              { label: '可用', value: 'active' },
                              { label: '停用', value: 'inactive' },
                            ]}
                            onChange={(v) => setExecutorForm({ ...executorForm, status: String(v) })}
                          />
                        </div>
                      </Col>
                      <Col xs={6}>
                        <Typography.Text strong>权重</Typography.Text>
                        <div style={{ marginTop: 8 }}>
                          <InputNumber
                            min={1}
                            max={999}
                            value={Number(executorForm.weight ?? 1)}
                            onChange={(v) => setExecutorForm({ ...executorForm, weight: Number(v) || 1 })}
                          />
                        </div>
                      </Col>
                    </Row>

                    <div>
                      <Space align="center" size="small">
                        <Typography.Text strong>最大并发</Typography.Text>
                        <Tooltip content="1~50。并发越大越容易触发第三方限流/502，建议逐步放量。">
                          <Typography.Text theme="secondary">?</Typography.Text>
                        </Tooltip>
                      </Space>
                      <div style={{ marginTop: 8 }}>
                        <InputNumber
                          min={1}
                          max={50}
                          value={Number(executorForm.max_concurrency ?? 1)}
                          onChange={(v) => setExecutorForm({ ...executorForm, max_concurrency: Number(v) || 1 })}
                        />
                      </div>
                    </div>

                    <Card
                      bordered
                      title="接入配置（推荐用下方表单，不需要懂 JSON）"
                      style={{ background: 'var(--td-bg-color-secondarycontainer)' }}
                    >
                      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                        {executorConfigTemplates.map((item) => (
                          <div key={`ex-cfg-${item.key}`}>
                            <Space align="center" size="small">
                              <Typography.Text strong>{item.label}</Typography.Text>
                              <Typography.Text theme="secondary">{item.hint}</Typography.Text>
                            </Space>
                            <div style={{ marginTop: 8 }}>
                              <Input
                                value={String(executorConfigRecord?.[item.key] ?? '')}
                                placeholder={item.placeholder}
                                onChange={(v) => setExecutorConfigField(item.key, String(v))}
                              />
                            </div>
                          </div>
                        ))}
                        <div>
                          <Typography.Text theme="secondary">
                            高级：如需更多字段，可展开配置原文编辑器（保存时会校验格式）。
                          </Typography.Text>
                        </div>
                      </Space>
                    </Card>

                    <div>
                      <Space align="center" size="small">
                        <Typography.Text strong>配置原文（高级）</Typography.Text>
                        {executorConfigJsonInvalid ? (
                          <Typography.Text theme="error" style={{ fontSize: 12 }}>
                            JSON 无效
                          </Typography.Text>
                        ) : (
                          <Typography.Text theme="secondary" style={{ fontSize: 12 }}>
                            JSON 有效
                          </Typography.Text>
                        )}
                      </Space>
                      <div style={{ marginTop: 8 }}>
                        <Textarea
                          value={String(executorForm.config || '')}
                          onChange={(v) => setExecutorForm({ ...executorForm, config: String(v) })}
                          autosize={{ minRows: 5, maxRows: 10 }}
                          placeholder='例如：{"apiKey":"***","baseUrl":"https://api.kie.ai"}'
                        />
                      </div>
                    </div>

                    <Space style={{ width: '100%' }}>
                      <Button theme="primary" style={{ flex: 1 }} onClick={handleExecutorSubmit}>
                        保存
                      </Button>
                      {executorForm.id ? (
                        <Button variant="outline" onClick={() => { setExecutorForm(defaultExecutorForm); setExecutorFormError(null); }}>
                          取消
                        </Button>
                      ) : null}
                    </Space>
                  </Space>
                </Card>
              </Col>
            </Row>
          </Space>
        )}
    </>
  );
}
