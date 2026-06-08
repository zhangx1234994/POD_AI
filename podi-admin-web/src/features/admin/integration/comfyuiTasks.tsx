import { Alert, Button, Card, Col, Dialog, Input, Row, Select, Space, Switch, Typography } from 'tdesign-react';
import type {
  ComfyuiAgentManifest,
  ComfyuiAgentTask,
  ComfyuiAgentTaskEvent,
  ComfyuiMonitoringSummary,
  ComfyuiQueueSummary,
  ComfyuiWorkflowCompatibility,
  ComfyuiWorkflowCompatibilityServer,
} from '../../../types/admin';
import { toDisplayErrorMessage } from '../../../utils/errorMessageMap';
import { GuidanceQueueCard, StatusBadge, type GuidanceQueueItem } from '../shared/ui';
import { formatDateTime } from './formatters';

type SelectOption = {
  label: string;
  value: string;
};

type ComfyAgentTaskFormState = {
  taskId: string;
  agentId: string;
  manifestId: string;
  manifestUrl: string;
  actions: string;
  expiresAt: string;
};

type TaskFormPatch = Partial<ComfyAgentTaskFormState>;
type ComfyuiActionItem = GuidanceQueueItem;

type ComfyuiTasksPanelProps = {
  taskForm: ComfyAgentTaskFormState;
  agentOptions: SelectOption[];
  manifestOptions: SelectOption[];
  pushAfterCreate: boolean;
  formError?: string | null;
  saving: boolean;
  advancedOpen: boolean;
  monitoringWindowHours: number;
  monitoringSummary?: ComfyuiMonitoringSummary | null;
  monitoringLoading: boolean;
  monitoringError?: string | null;
  queueSummary?: ComfyuiQueueSummary | null;
  queueSummaryLoading: boolean;
  queueSummaryError?: string | null;
  queueSummaryUpdatedAt?: string | null;
  workflowCompatibility?: ComfyuiWorkflowCompatibility | null;
  workflowCompatibilityLoading: boolean;
  workflowCompatibilityError?: string | null;
  workflowCompatibilityUpdatedAt?: string | null;
  taskAgentFilter: string;
  taskStatusFilter: string;
  tasks: ComfyuiAgentTask[];
  tasksLoading: boolean;
  tasksError?: string | null;
  manifests: ComfyuiAgentManifest[];
  taskPushLoading: Record<string, boolean>;
  runningTaskCount: number;
  taskEventsDialogOpen: boolean;
  taskEventsTaskId?: string | null;
  taskEvents: ComfyuiAgentTaskEvent[];
  taskEventsLoading: boolean;
  taskEventsError?: string | null;
  formatActions: (actions?: string[] | null) => string;
  onTaskFormPatch: (patch: TaskFormPatch) => void;
  onPushAfterCreateChange: (value: boolean) => void;
  onCreateTask: () => void;
  onMonitoringWindowChange: (hours: number) => void;
  onRefreshMonitoring: () => void;
  onRefreshQueueSummary: () => void;
  onRefreshWorkflowCompatibility: () => void;
  onTaskAgentFilterChange: (agentId: string) => void;
  onTaskStatusFilterChange: (status: string) => void;
  onRefreshTasks: () => void;
  onPushTask: (taskId: string) => void;
  onOpenTaskEvents: (taskId: string) => void;
  onCloseTaskEvents: () => void;
};

function summarizeCompatibilityIssue(server?: ComfyuiWorkflowCompatibilityServer): string {
  if (!server) return '路由配置需统一';
  if (!server.reachable) return `执行机 ${server.executorId} 不可访问，请先检查 ComfyUI 服务和网络。`;
  const missingNodes = (server.missingNodes || [])
    .slice(0, 3)
    .map((item) => item.classType || item.nodeId)
    .filter(Boolean);
  const missingModels = (server.missingModels || [])
    .slice(0, 3)
    .map((item) => item.value || item.inputName)
    .filter(Boolean);
  const parts: string[] = [];
  if (missingNodes.length > 0) {
    parts.push(`缺节点：${missingNodes.join('、')}`);
  }
  if (missingModels.length > 0) {
    parts.push(`缺模型：${missingModels.join('、')}`);
  }
  if (parts.length === 0 && server.message) {
    parts.push(server.message);
  }
  return parts.length > 0 ? `${server.executorId} · ${parts.join('；')}` : `${server.executorId} · 不兼容`;
}

function formatSeconds(value?: number | null): string {
  if (typeof value !== 'number' || Number.isNaN(value)) return '—';
  if (value < 60) return `${Math.max(0, Math.floor(value))} 秒`;
  const minutes = Math.floor(value / 60);
  const seconds = Math.floor(value % 60);
  if (minutes < 60) return seconds ? `${minutes} 分 ${seconds} 秒` : `${minutes} 分钟`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest ? `${hours} 小时 ${rest} 分` : `${hours} 小时`;
}

export function ComfyuiTasksPanel({
  taskForm,
  agentOptions,
  manifestOptions,
  pushAfterCreate,
  formError,
  saving,
  advancedOpen,
  monitoringWindowHours,
  monitoringSummary,
  monitoringLoading,
  monitoringError,
  queueSummary,
  queueSummaryLoading,
  queueSummaryError,
  queueSummaryUpdatedAt,
  workflowCompatibility,
  workflowCompatibilityLoading,
  workflowCompatibilityError,
  workflowCompatibilityUpdatedAt,
  taskAgentFilter,
  taskStatusFilter,
  tasks,
  tasksLoading,
  tasksError,
  manifests,
  taskPushLoading,
  runningTaskCount,
  taskEventsDialogOpen,
  taskEventsTaskId,
  taskEvents,
  taskEventsLoading,
  taskEventsError,
  formatActions,
  onTaskFormPatch,
  onPushAfterCreateChange,
  onCreateTask,
  onMonitoringWindowChange,
  onRefreshMonitoring,
  onRefreshQueueSummary,
  onRefreshWorkflowCompatibility,
  onTaskAgentFilterChange,
  onTaskStatusFilterChange,
  onRefreshTasks,
  onPushTask,
  onOpenTaskEvents,
  onCloseTaskEvents,
}: ComfyuiTasksPanelProps) {
  const formatPercent = (value?: number | null) => {
    if (typeof value !== 'number' || Number.isNaN(value)) return '—';
    return `${Math.round(value * 100)}%`;
  };
  const formatServerIdentity = (server: NonNullable<ComfyuiQueueSummary['servers']>[number]) => {
    let host = '';
    try {
      host = server.baseUrl ? new URL(server.baseUrl).hostname : '';
    } catch {
      host = server.baseUrl || '';
    }
    const tags = Array.isArray(server.tags) ? server.tags.map((item) => String(item || '').trim()).filter(Boolean) : [];
    const gpuTag = tags.find((item) => item.toLowerCase().startsWith('gpu:'));
    const hostTag = tags.find((item) => item.toLowerCase().startsWith('host:'));
    const gpu = gpuTag ? gpuTag.replace(/^gpu:/i, '') : host === '117.50.80.158' ? '5090' : host === '117.50.216.233' ? '4090' : '';
    const hostHint = hostTag
      ? hostTag.replace(/^host:/i, '')
      : host === '117.50.80.158'
        ? '158'
        : host === '117.50.216.233'
          ? '233'
          : '';
    const parts = [
      hostHint ? `${hostHint} 机器` : host,
      gpu ? `${gpu} 显卡` : '',
      `并发 ${server.maxConcurrency ?? server.capacityTarget ?? '—'}`,
    ].filter(Boolean);
    return parts.join(' · ');
  };
  const mapAlertTheme = (level?: string | null): 'success' | 'info' | 'warning' | 'error' => {
    if (level === 'danger') return 'error';
    if (level === 'warning') return 'warning';
    if (level === 'success') return 'success';
    return 'info';
  };
  const feedGapCount = queueSummary?.feedGapServers ?? 0;
  const blockedCount = queueSummary?.backendBlockedServers ?? 0;
  const settlingCount = queueSummary?.backendRunningSettlingServers ?? 0;
  const invisibleCount = queueSummary?.backendRunningInvisibleServers ?? 0;
  const staleGraceSeconds = queueSummary?.backendRunningStaleGraceSeconds ?? 300;
  const routeMissingCount = queueSummary?.recentRouteMissingServers ?? 0;
  const routeEvidenceWindowHours = queueSummary?.routeEvidenceWindowHours ?? 24;
  const queueRiskText = blockedCount > 0
    ? `疑似卡住 ${blockedCount} 台`
    : settlingCount > 0
      ? `观察中 ${settlingCount} 台`
    : routeMissingCount > 0
      ? `未命中 ${routeMissingCount} 台`
      : feedGapCount > 0
        ? `下发偏慢 ${feedGapCount} 台`
        : '暂无明显风险';
  const compatibilityRiskText = workflowCompatibility?.failedCount
    ? `不可运行 ${workflowCompatibility.failedCount} 个`
    : workflowCompatibility?.warningCount
      ? `需关注 ${workflowCompatibility.warningCount} 个`
      : workflowCompatibility
        ? '全部可运行'
        : workflowCompatibilityLoading
          ? '读取中…'
          : '—';
  const compatibilityRiskClass = workflowCompatibility?.failedCount
    ? 'mt-1 text-lg font-semibold text-rose-600'
    : workflowCompatibility?.warningCount
      ? 'mt-1 text-lg font-semibold text-amber-600'
      : 'mt-1 text-lg font-semibold text-emerald-600';
  const compatibilityProblemWorkflows = (workflowCompatibility?.workflows || [])
    .filter((item) => item.status !== 'ok')
    .slice(0, 6);
  const topActionItems: ComfyuiActionItem[] = [];
  if (!queueSummary && !queueSummaryLoading && !queueSummaryError) {
    topActionItems.push({
      key: 'queue-not-loaded',
      theme: 'primary',
      title: '先刷新队列诊断',
      detail: '还没有读取中台和 ComfyUI 队列，无法判断 GPU 是否吃满或任务是否卡住。',
      action: '点击刷新诊断',
      onClick: onRefreshQueueSummary,
      loading: queueSummaryLoading,
    });
  }
  if (queueSummaryError) {
    topActionItems.push({
      key: 'queue-error',
      theme: 'danger',
      title: '队列诊断读不到',
      detail: '当前无法确认任务是否正常分流，先检查后端到 ComfyUI 机器的网络和执行节点状态。',
      action: '重新读取队列',
      onClick: onRefreshQueueSummary,
      loading: queueSummaryLoading,
    });
  } else if (blockedCount > 0) {
    topActionItems.push({
      key: 'queue-blocked',
      theme: 'danger',
      title: '有任务疑似卡住',
      detail: `中台执行中已超过 ${formatSeconds(staleGraceSeconds)}，但 ComfyUI 队列没有对应执行证据，涉及 ${blockedCount} 台线路。`,
      action: '打开下方线路，按任务详情、ComfyUI history、OSS 回填顺序排查',
    });
  } else if (settlingCount > 0) {
    topActionItems.push({
      key: 'queue-settling',
      theme: 'warning',
      title: '有任务处于回填观察窗口',
      detail: `中台执行中但 ComfyUI 队列暂未显示，仍在 ${formatSeconds(staleGraceSeconds)} 宽限窗口内，涉及 ${settlingCount} 台线路。`,
      action: '等待一个刷新周期后复查，超过宽限窗口再按卡住处理',
    });
  } else if (routeMissingCount > 0 && (queueSummary?.routeEvidenceTotal || 0) > 0) {
    topActionItems.push({
      key: 'route-evidence-missing',
      theme: 'warning',
      title: '有机器最近没被打到',
      detail: `近 ${routeEvidenceWindowHours} 小时已有 ComfyUI 任务，但 ${routeMissingCount} 台机器没有命中记录。`,
      action: '检查路由和工作流绑定',
    });
  } else if (feedGapCount > 0) {
    topActionItems.push({
      key: 'queue-feed-gap',
      theme: 'warning',
      title: '有空闲但下发偏慢',
      detail: `ComfyUI 仍有空闲容量，但中台还有待下发任务，涉及 ${feedGapCount} 条线路。`,
      action: '先看下方待下发线路',
    });
  }
  if (!workflowCompatibility && !workflowCompatibilityLoading && !workflowCompatibilityError) {
    topActionItems.push({
      key: 'compat-not-loaded',
      theme: 'primary',
      title: '再刷新能力对齐',
      detail: '还没有检查各台机器是否都具备相同节点、模型和路由配置。',
      action: '点击刷新对齐',
      onClick: onRefreshWorkflowCompatibility,
      loading: workflowCompatibilityLoading,
    });
  }
  if (workflowCompatibilityError) {
    topActionItems.push({
      key: 'compat-error',
      theme: 'warning',
      title: '能力对齐暂时读不到',
      detail: '如果某台机器离线或依赖查询超时，先不要直接判断本次可发版。',
      action: '重新检查对齐',
      onClick: onRefreshWorkflowCompatibility,
      loading: workflowCompatibilityLoading,
    });
  } else if ((workflowCompatibility?.failedCount || 0) > 0) {
    topActionItems.push({
      key: 'compat-failed',
      theme: 'danger',
      title: '有能力不可运行',
      detail: `${workflowCompatibility?.failedCount || 0} 个 ComfyUI 能力在目标机器上缺节点、缺模型或路由不完整。`,
      action: '先修复能力对齐',
    });
  } else if ((workflowCompatibility?.warningCount || 0) > 0) {
    topActionItems.push({
      key: 'compat-warning',
      theme: 'warning',
      title: '部分机器需关注',
      detail: `${workflowCompatibility?.warningCount || 0} 个能力存在部分机器依赖不一致，上线前要确认是否接受。`,
      action: '查看异常机器清单',
    });
  }
  if (
    topActionItems.length === 0 &&
    queueSummary &&
    workflowCompatibility &&
    !queueSummaryError &&
    !workflowCompatibilityError
  ) {
    topActionItems.push({
      key: 'all-clear',
      theme: 'success',
      title: '线路当前可用',
      detail: '队列衔接和能力对齐没有明显阻塞，可以继续做真实业务巡检或发布前门禁。',
      action: '继续跑业务巡检',
    });
  }

  return (
    <div className="space-y-4">
      <GuidanceQueueCard items={topActionItems} />

      <Card bordered title="任务衔接诊断">
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Space align="center" style={{ justifyContent: 'space-between', width: '100%', flexWrap: 'wrap' }}>
            <Typography.Text theme="secondary">
              这里对比“中台待处理任务”和“ComfyUI 实际队列”，用于判断 GPU 没吃满到底是执行侧容量问题，还是中台下发节奏问题。
            </Typography.Text>
            <Space>
              <Button size="small" variant="outline" loading={queueSummaryLoading} onClick={onRefreshQueueSummary}>
                刷新诊断
              </Button>
              <Typography.Text theme="secondary">
                {queueSummary?.timestamp || queueSummaryUpdatedAt ? `更新：${formatDateTime(queueSummary?.timestamp || queueSummaryUpdatedAt)}` : '暂无刷新时间'}
              </Typography.Text>
            </Space>
          </Space>
          {queueSummaryError ? <Alert theme="error" message={`队列诊断读取失败：${queueSummaryError}`} /> : null}
          <div className="grid gap-3 md:grid-cols-5">
            <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 dark:border-slate-800 dark:bg-slate-950/40">
              <div className="text-xs text-slate-500">中台积压</div>
              <div className="mt-1 text-lg font-semibold text-slate-900 dark:text-white">
                {queueSummary ? queueSummary.backendActiveTotal ?? 0 : queueSummaryLoading ? '读取中…' : '—'}
              </div>
              <div className="mt-1 text-xs text-slate-500">
                待下发 {queueSummary?.backendQueuedTotal ?? 0} · 执行中 {queueSummary?.backendRunningTotal ?? 0}
              </div>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 dark:border-slate-800 dark:bg-slate-950/40">
              <div className="text-xs text-slate-500">ComfyUI 队列</div>
              <div className="mt-1 text-lg font-semibold text-slate-900 dark:text-white">
                {queueSummary ? `${queueSummary.totalCount}/${queueSummary.totalCapacity ?? '—'}` : queueSummaryLoading ? '读取中…' : '—'}
              </div>
              <div className="mt-1 text-xs text-slate-500">
                执行 {queueSummary?.totalRunning ?? 0} · 等待 {queueSummary?.totalPending ?? 0}
              </div>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 dark:border-slate-800 dark:bg-slate-950/40">
              <div className="text-xs text-slate-500">空闲容量</div>
              <div className="mt-1 text-lg font-semibold text-slate-900 dark:text-white">
                {queueSummary ? queueSummary.totalIdleSlots ?? '—' : queueSummaryLoading ? '读取中…' : '—'}
              </div>
              <div className="mt-1 text-xs text-slate-500">使用率 {formatPercent(queueSummary?.utilization)}</div>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 dark:border-slate-800 dark:bg-slate-950/40">
              <div className="text-xs text-slate-500">真实命中</div>
              <div
                className={
                  routeMissingCount > 0 && (queueSummary?.routeEvidenceTotal || 0) > 0
                    ? 'mt-1 text-lg font-semibold text-amber-600'
                    : 'mt-1 text-lg font-semibold text-slate-900 dark:text-white'
                }
              >
                {queueSummary
                  ? `${queueSummary.routeEvidenceCoveredServers ?? 0}/${queueSummary.supportedServers ?? 0}`
                  : queueSummaryLoading
                    ? '读取中…'
                    : '—'}
              </div>
              <div className="mt-1 text-xs text-slate-500">
                近 {routeEvidenceWindowHours} 小时任务 {queueSummary?.routeEvidenceTotal ?? 0}
              </div>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 dark:border-slate-800 dark:bg-slate-950/40">
              <div className="text-xs text-slate-500">风险判断</div>
              <div
                className={
                  blockedCount > 0
                    ? 'mt-1 text-lg font-semibold text-rose-600'
                    : routeMissingCount > 0 && (queueSummary?.routeEvidenceTotal || 0) > 0
                      ? 'mt-1 text-lg font-semibold text-amber-600'
                    : feedGapCount > 0
                      ? 'mt-1 text-lg font-semibold text-amber-600'
                      : 'mt-1 text-lg font-semibold text-emerald-600'
                }
              >
                {queueSummary ? queueRiskText : queueSummaryLoading ? '读取中…' : '—'}
              </div>
              <div className="mt-1 text-xs text-slate-500">
                不可见 {invisibleCount} · 观察 {settlingCount} · 疑似卡住 {blockedCount}
              </div>
            </div>
          </div>
          {queueSummary?.diagnostics?.length ? (
            <Space direction="vertical" size="small" style={{ width: '100%' }}>
              {queueSummary.diagnostics.map((item) => (
                <Alert key={`${item.code}-${item.level}`} theme={mapAlertTheme(item.level)} message={item.message} />
              ))}
            </Space>
          ) : null}
          <div className="max-h-[260px] overflow-auto rounded-2xl border border-slate-200/70 dark:border-slate-800">
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-slate-50 text-[11px] text-slate-600 dark:bg-slate-900/80 dark:text-slate-400">
                <tr className="text-left">
                  <th className="px-3 py-2">运行线路</th>
                  <th className="px-3 py-2">ComfyUI 队列</th>
                  <th className="px-3 py-2">容量</th>
                  <th className="px-3 py-2">中台任务</th>
                  <th className="px-3 py-2">最近命中</th>
                  <th className="px-3 py-2">判断</th>
                </tr>
              </thead>
              <tbody>
                {!queueSummary?.servers?.length ? (
                  <tr>
                    <td colSpan={6} className="px-4 py-6 text-center text-slate-500">
                      {queueSummaryLoading ? '加载中…' : '暂无 ComfyUI 线路诊断'}
                    </td>
                  </tr>
                ) : (
                  queueSummary.servers.map((server) => (
                    <tr key={`comfy-queue-diagnosis-${server.executorId}`} className="border-t border-slate-100 dark:border-slate-800">
                      <td className="px-3 py-2 text-slate-700 dark:text-slate-300">
                        <div className="font-semibold text-slate-900 dark:text-white">{server.executorName || server.executorId}</div>
                        <div className="mt-1 text-[11px] text-slate-500">{formatServerIdentity(server)}</div>
                        <div className="mt-1 max-w-[260px] truncate text-[11px] text-slate-400">{server.executorId} · {server.baseUrl}</div>
                      </td>
                      <td className="px-3 py-2 text-slate-700 dark:text-slate-300">
                        执行 {server.runningCount} · 等待 {server.pendingCount}
                      </td>
                      <td className="px-3 py-2 text-slate-700 dark:text-slate-300">
                        {server.totalCount ?? server.runningCount + server.pendingCount}/{server.capacityTarget ?? '—'}
                        <div className="mt-1 text-[11px] text-slate-500">
                          空闲 {server.idleSlots ?? '—'} · {formatPercent(server.utilization)}
                        </div>
                      </td>
                      <td className="px-3 py-2 text-slate-700 dark:text-slate-300">
                        待下发 {server.backendQueued ?? 0} · 执行中 {server.backendRunning ?? 0}
                        {server.backendOldestQueuedAt ? (
                          <div className="mt-1 text-[11px] text-amber-600">最早等待：{formatDateTime(server.backendOldestQueuedAt)}</div>
                        ) : null}
                        {server.backendOldestRunningAt ? (
                          <div
                            className={
                              server.feedDiagnosisLevel === 'danger'
                                ? 'mt-1 text-[11px] text-rose-600'
                                : server.feedDiagnosisLevel === 'warning'
                                  ? 'mt-1 text-[11px] text-amber-600'
                                  : 'mt-1 text-[11px] text-slate-500'
                            }
                          >
                            最早执行：{formatDateTime(server.backendOldestRunningAt)}
                            {typeof server.backendOldestRunningAgeSeconds === 'number'
                              ? ` · 已 ${formatSeconds(server.backendOldestRunningAgeSeconds)}`
                              : ''}
                          </div>
                        ) : null}
                      </td>
                      <td
                        className={
                          server.routeDiagnosisLevel === 'warning'
                            ? 'px-3 py-2 text-amber-600'
                            : server.routeDiagnosisLevel === 'danger'
                              ? 'px-3 py-2 text-rose-600'
                              : 'px-3 py-2 text-slate-700 dark:text-slate-300'
                        }
                      >
                        <div>
                          总 {server.routeEvidence?.recentTotal ?? 0} · 成功 {server.routeEvidence?.recentSucceeded ?? 0} · 失败 {server.routeEvidence?.recentFailed ?? 0}
                        </div>
                        <div className="mt-1 text-[11px] text-slate-500">
                          运行 {server.routeEvidence?.recentRunning ?? 0} · 排队 {server.routeEvidence?.recentQueued ?? 0}
                        </div>
                        {server.routeEvidence?.latestTaskAt ? (
                          <div className="mt-1 text-[11px] text-slate-500">最近：{formatDateTime(server.routeEvidence.latestTaskAt)}</div>
                        ) : null}
                        {server.routeDiagnosis ? (
                          <div className="mt-1 text-[11px]">{server.routeDiagnosis}</div>
                        ) : null}
                      </td>
                      <td
                        className={
                          server.feedDiagnosisLevel === 'danger'
                            ? 'px-3 py-2 text-rose-600'
                            : server.feedDiagnosisLevel === 'warning'
                              ? 'px-3 py-2 text-amber-600'
                              : 'px-3 py-2 text-slate-600 dark:text-slate-400'
                        }
                      >
                        <div>{server.feedDiagnosis || server.diagnosis || '—'}</div>
                        {server.feedAction ? (
                          <div className="mt-1 text-[11px] text-slate-500 dark:text-slate-400">下一步：{server.feedAction}</div>
                        ) : null}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </Space>
      </Card>

      <Card bordered title="能力对齐检查">
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Space align="center" style={{ justifyContent: 'space-between', width: '100%', flexWrap: 'wrap' }}>
            <Typography.Text theme="secondary">
              检查每个线上 ComfyUI 能力在各台执行机器上是否缺节点、缺模型，以及路由配置是否一致。用于避免“只打到一台机器”或“换机器后工作流失败”。
            </Typography.Text>
            <Space>
              <Button size="small" variant="outline" loading={workflowCompatibilityLoading} onClick={onRefreshWorkflowCompatibility}>
                刷新对齐
              </Button>
              <Typography.Text theme="secondary">
                {workflowCompatibility?.checkedAt || workflowCompatibilityUpdatedAt ? `更新：${formatDateTime(workflowCompatibility?.checkedAt || workflowCompatibilityUpdatedAt)}` : '暂无刷新时间'}
              </Typography.Text>
            </Space>
          </Space>
          {workflowCompatibilityError ? (
            <Alert
              theme="warning"
              message={`暂时无法完成能力对齐检查：${workflowCompatibilityError}。页面可继续使用，请稍后刷新，或先检查对应 ComfyUI 机器是否在线。`}
            />
          ) : null}
          <div className="grid gap-3 md:grid-cols-4">
            <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 dark:border-slate-800 dark:bg-slate-950/40">
              <div className="text-xs text-slate-500">检查能力</div>
              <div className="mt-1 text-lg font-semibold text-slate-900 dark:text-white">
                {workflowCompatibility ? workflowCompatibility.totalWorkflows : workflowCompatibilityLoading ? '读取中…' : '—'}
              </div>
              <div className="mt-1 text-xs text-slate-500">active ComfyUI 能力</div>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 dark:border-slate-800 dark:bg-slate-950/40">
              <div className="text-xs text-slate-500">可运行</div>
              <div className="mt-1 text-lg font-semibold text-emerald-600">
                {workflowCompatibility ? workflowCompatibility.okCount : workflowCompatibilityLoading ? '读取中…' : '—'}
              </div>
              <div className="mt-1 text-xs text-slate-500">路由机器依赖完整</div>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 dark:border-slate-800 dark:bg-slate-950/40">
              <div className="text-xs text-slate-500">需关注</div>
              <div className="mt-1 text-lg font-semibold text-amber-600">
                {workflowCompatibility ? workflowCompatibility.warningCount : workflowCompatibilityLoading ? '读取中…' : '—'}
              </div>
              <div className="mt-1 text-xs text-slate-500">部分机器缺依赖或配置不一致</div>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 dark:border-slate-800 dark:bg-slate-950/40">
              <div className="text-xs text-slate-500">风险判断</div>
              <div className={compatibilityRiskClass}>{compatibilityRiskText}</div>
              <div className="mt-1 text-xs text-slate-500">
                不可运行 {workflowCompatibility?.failedCount ?? 0} · 检查机器 {workflowCompatibility?.servers?.length ?? 0}
              </div>
            </div>
          </div>
          <div className="max-h-[260px] overflow-auto rounded-2xl border border-slate-200/70 dark:border-slate-800">
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-slate-50 text-[11px] text-slate-600 dark:bg-slate-900/80 dark:text-slate-400">
                <tr className="text-left">
                  <th className="px-3 py-2">能力</th>
                  <th className="px-3 py-2">可运行机器</th>
                  <th className="px-3 py-2">异常机器</th>
                  <th className="px-3 py-2">原因</th>
                </tr>
              </thead>
              <tbody>
                {!workflowCompatibility ? (
                  <tr>
                    <td colSpan={4} className="px-4 py-6 text-center text-slate-500">
                      {workflowCompatibilityLoading ? '加载中…' : '暂无能力对齐检查'}
                    </td>
                  </tr>
                ) : compatibilityProblemWorkflows.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="px-4 py-6 text-center text-emerald-600">
                      当前检查范围内没有发现缺节点、缺模型或路由不一致。
                    </td>
                  </tr>
                ) : (
                  compatibilityProblemWorkflows.map((item) => {
                    const firstProblem = item.servers.find((server) => !server.compatible);
                    const reason = firstProblem
                      ? summarizeCompatibilityIssue(firstProblem)
                      : item.diagnostics?.[0]?.message || '路由配置需统一';
                    return (
                      <tr key={`comfy-workflow-compat-${item.abilityId}`} className="border-t border-slate-100 dark:border-slate-800">
                        <td className="px-3 py-2">
                          <div className="font-semibold text-slate-900 dark:text-white">{item.displayName}</div>
                          <div className="mt-1 text-[11px] text-slate-500">{item.workflowKey}</div>
                        </td>
                        <td className="px-3 py-2 text-emerald-600">{item.compatibleExecutorIds.join('、') || '无'}</td>
                        <td className="px-3 py-2 text-rose-600">{item.incompatibleExecutorIds.join('、') || '无'}</td>
                        <td className="px-3 py-2 text-slate-600 dark:text-slate-400">{reason}</td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </Space>
      </Card>

      <div id="comfy-task-create-card">
        <Card bordered title="任务下发">
          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
            <Row gutter={[12, 12]}>
              <Col span={12}>
                <Typography.Text theme="secondary">代理服务</Typography.Text>
                <Select
                  value={taskForm.agentId}
                  onChange={(value) => onTaskFormPatch({ agentId: String(value) })}
                  options={[{ label: '请选择代理服务', value: '' }, ...agentOptions]}
                />
              </Col>
              <Col span={12}>
                <Typography.Text theme="secondary">同步清单</Typography.Text>
                <Select
                  value={taskForm.manifestId}
                  onChange={(value) => onTaskFormPatch({ manifestId: String(value) })}
                  options={[{ label: '不绑定（手填 URL）', value: '' }, ...manifestOptions]}
                />
              </Col>
            </Row>
            <Row gutter={[12, 12]}>
              <Col span={12}>
                <Typography.Text theme="secondary">清单地址</Typography.Text>
                <Input
                  value={taskForm.manifestUrl}
                  onChange={(value) => onTaskFormPatch({ manifestUrl: String(value) })}
                  placeholder="可选：自定义清单地址"
                />
              </Col>
              <Col span={12}>
                <Typography.Text theme="secondary">任务编号（可选）</Typography.Text>
                <Input
                  value={taskForm.taskId}
                  onChange={(value) => onTaskFormPatch({ taskId: String(value) })}
                  placeholder="留空自动生成"
                />
              </Col>
            </Row>
            <Row gutter={[12, 12]}>
              <Col span={12}>
                <Typography.Text theme="secondary">动作列表</Typography.Text>
                <Input
                  value={taskForm.actions}
                  onChange={(value) => onTaskFormPatch({ actions: String(value) })}
                  placeholder="sync_models, sync_plugins, sync_workflows, restart"
                />
                <div className="mt-2 text-xs text-slate-500">
                  动作对照：sync_models=同步模型，sync_plugins=同步插件，sync_workflows=同步工作流，restart=重启服务。
                </div>
              </Col>
              <Col span={12}>
                <Typography.Text theme="secondary">过期时间（可选）</Typography.Text>
                <Input
                  value={taskForm.expiresAt}
                  onChange={(value) => onTaskFormPatch({ expiresAt: String(value) })}
                  placeholder="2026-02-05T23:59:59Z"
                />
              </Col>
            </Row>
            <Space align="center" size="small">
              <Switch value={pushAfterCreate} onChange={(value) => onPushAfterCreateChange(Boolean(value))} />
              <Typography.Text theme="secondary">创建后立即推送</Typography.Text>
            </Space>
            {formError ? <Alert theme="error" message={formError} /> : null}
            <Button theme="primary" loading={saving} onClick={onCreateTask}>
              创建任务
            </Button>
            <div className="text-xs text-slate-500">动作列表将按逗号/换行分割；未设置过期时间时默认 60 分钟。</div>
          </Space>
        </Card>
      </div>

      {advancedOpen ? (
        <>
          <Card bordered title="链路监控汇总">
            <Space direction="vertical" size="small" style={{ width: '100%' }}>
              <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
                <Space align="center" size="small">
                  <Select
                    value={String(monitoringWindowHours)}
                    onChange={(value) => onMonitoringWindowChange(Number(value) || 24)}
                    options={[
                      { label: '最近 24 小时', value: '24' },
                      { label: '最近 72 小时', value: '72' },
                      { label: '最近 168 小时', value: '168' },
                    ]}
                  />
                  <Button size="small" variant="outline" onClick={onRefreshMonitoring}>
                    刷新
                  </Button>
                </Space>
                <Typography.Text theme="secondary">
                  {monitoringSummary?.generatedAt ? `更新时间：${formatDateTime(monitoringSummary.generatedAt)}` : '暂无数据'}
                </Typography.Text>
              </Space>
              {monitoringError ? <Alert theme="error" message={monitoringError} /> : null}
              <div className="max-h-[260px] overflow-auto rounded-2xl border border-slate-200/70 dark:border-slate-800">
                <table className="w-full text-xs">
                  <thead className="sticky top-0 bg-slate-50 text-[11px] text-slate-600 dark:bg-slate-900/80 dark:text-slate-400">
                    <tr className="text-left">
                      <th className="px-3 py-2">队列</th>
                      <th className="px-3 py-2">总量</th>
                      <th className="px-3 py-2">排队</th>
                      <th className="px-3 py-2">执行中</th>
                      <th className="px-3 py-2">成功</th>
                      <th className="px-3 py-2">失败</th>
                      <th className="px-3 py-2">失败率</th>
                      <th className="px-3 py-2">平均等待(s)</th>
                      <th className="px-3 py-2">重试次数</th>
                    </tr>
                  </thead>
                  <tbody>
                    {!monitoringSummary?.lanes?.length ? (
                      <tr>
                        <td colSpan={9} className="px-4 py-6 text-center text-slate-500">
                          {monitoringLoading ? '加载中…' : '暂无监控数据'}
                        </td>
                      </tr>
                    ) : (
                      monitoringSummary.lanes.map((lane) => (
                        <tr key={`monitor-lane-${lane.lane}`} className="border-t border-slate-100 dark:border-slate-800">
                          <td className="px-3 py-2 text-slate-700 dark:text-slate-300">{lane.lane}</td>
                          <td className="px-3 py-2 text-slate-700 dark:text-slate-300">{lane.total}</td>
                          <td className="px-3 py-2 text-slate-700 dark:text-slate-300">{lane.queued}</td>
                          <td className="px-3 py-2 text-slate-700 dark:text-slate-300">{lane.running}</td>
                          <td className="px-3 py-2 text-emerald-600 dark:text-emerald-400">{lane.succeeded}</td>
                          <td className="px-3 py-2 text-rose-600 dark:text-rose-400">{lane.failed}</td>
                          <td className="px-3 py-2 text-slate-700 dark:text-slate-300">
                            {Number.isFinite(lane.failureRate) ? `${(lane.failureRate * 100).toFixed(2)}%` : '—'}
                          </td>
                          <td className="px-3 py-2 text-slate-700 dark:text-slate-300">
                            {Number.isFinite(lane.avgWaitSeconds) ? lane.avgWaitSeconds.toFixed(2) : '—'}
                          </td>
                          <td className="px-3 py-2 text-slate-700 dark:text-slate-300">{lane.retryCount}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </Space>
          </Card>

          <Card bordered title="最近任务">
            <Space direction="vertical" size="small" style={{ width: '100%' }}>
              <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
                <Space align="center" size="small">
                  <Select
                    value={taskAgentFilter}
                    onChange={(value) => onTaskAgentFilterChange(String(value))}
                    options={[{ label: '全部代理服务', value: 'all' }, ...agentOptions]}
                  />
                  <Select
                    value={taskStatusFilter}
                    onChange={(value) => onTaskStatusFilterChange(String(value))}
                    options={[
                      { label: '全部状态', value: 'all' },
                      { label: '排队中', value: 'pending' },
                      { label: '执行中', value: 'running' },
                      { label: '成功', value: 'success' },
                      { label: '失败', value: 'failed' },
                      { label: '已拒绝', value: 'rejected' },
                    ]}
                  />
                  <Button size="small" variant="outline" onClick={onRefreshTasks}>
                    刷新
                  </Button>
                </Space>
                <Typography.Text theme="secondary">{tasks.length ? `共 ${tasks.length} 条` : '暂无任务'}</Typography.Text>
              </Space>
              {tasksError ? <Alert theme="error" message={tasksError} /> : null}
              <div className="max-h-[420px] overflow-auto rounded-2xl border border-slate-200/70 dark:border-slate-800">
                <table className="w-full text-xs">
                  <thead className="sticky top-0 bg-slate-50 text-[11px] text-slate-600 dark:bg-slate-900/80 dark:text-slate-400">
                    <tr className="text-left">
                      <th className="px-3 py-2">任务编号</th>
                      <th className="px-3 py-2">代理服务</th>
                      <th className="px-3 py-2">提交阶段</th>
                      <th className="px-3 py-2">回调阶段</th>
                      <th className="px-3 py-2">最终状态</th>
                      <th className="px-3 py-2">动作</th>
                      <th className="px-3 py-2">清单</th>
                      <th className="px-3 py-2">过期</th>
                      <th className="px-3 py-2">更新时间</th>
                      <th className="px-3 py-2">失败原因</th>
                      <th className="px-3 py-2 text-right">操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {tasks.length === 0 ? (
                      <tr>
                        <td colSpan={11} className="px-4 py-6 text-center text-slate-500">
                          {tasksLoading ? '加载中…' : '暂无任务'}
                        </td>
                      </tr>
                    ) : (
                      tasks.map((task) => {
                        const manifest = task.manifestId ? manifests.find((item) => item.id === task.manifestId) : null;
                        const manifestLabel = manifest ? `${manifest.role} · ${manifest.version}` : task.manifestUrl || '—';
                        return (
                          <tr key={`comfy-agent-task-${task.id}`} className="border-t border-slate-100 dark:border-slate-800">
                            <td className="px-3 py-2 text-slate-900 dark:text-white">{task.id}</td>
                            <td className="px-3 py-2 text-slate-700 dark:text-slate-300">{task.agentId}</td>
                            <td className="px-3 py-2">
                              <StatusBadge status={task.submitStatus || task.status} />
                            </td>
                            <td className="px-3 py-2">
                              <StatusBadge status={task.callbackStatus || 'waiting'} />
                            </td>
                            <td className="px-3 py-2">
                              <StatusBadge status={task.finalStatus || task.status} />
                            </td>
                            <td className="px-3 py-2 text-slate-600 dark:text-slate-400">{formatActions(task.actions)}</td>
                            <td className="px-3 py-2 text-slate-600 dark:text-slate-400">{manifestLabel}</td>
                            <td className="px-3 py-2 text-slate-600 dark:text-slate-400">{formatDateTime(task.expiresAt)}</td>
                            <td className="px-3 py-2 text-slate-600 dark:text-slate-400">{formatDateTime(task.updated_at)}</td>
                            <td className="px-3 py-2 text-slate-600 dark:text-slate-400">
                              {task.errorMessage ? toDisplayErrorMessage(task.errorMessage) : '—'}
                            </td>
                            <td className="px-3 py-2 text-right space-x-2">
                              <button
                                className="text-sky-400"
                                disabled={Boolean(taskPushLoading[task.id])}
                                onClick={() => onPushTask(task.id)}
                              >
                                推送
                              </button>
                              <button className="text-slate-500" onClick={() => onOpenTaskEvents(task.id)}>
                                事件
                              </button>
                            </td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>
            </Space>
          </Card>
        </>
      ) : (
        <Alert
          theme="info"
          message={`监控与历史已折叠：运行中 ${runningTaskCount} 条，总任务 ${tasks.length} 条。可在顶部“展开监控与历史”查看详情。`}
        />
      )}

      <Dialog
        header={`任务事件 · ${taskEventsTaskId || ''}`}
        visible={taskEventsDialogOpen}
        width={720}
        confirmBtn={{ content: '关闭' }}
        onClose={onCloseTaskEvents}
        onConfirm={onCloseTaskEvents}
      >
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          {taskEventsError ? <Alert theme="error" message={taskEventsError} /> : null}
          <div className="max-h-[360px] overflow-auto rounded-2xl border border-slate-200/70 dark:border-slate-800">
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-slate-50 text-[11px] text-slate-600 dark:bg-slate-900/80 dark:text-slate-400">
                <tr className="text-left">
                  <th className="px-3 py-2">时间</th>
                  <th className="px-3 py-2">级别</th>
                  <th className="px-3 py-2">内容</th>
                </tr>
              </thead>
              <tbody>
                {taskEvents.length === 0 ? (
                  <tr>
                    <td colSpan={3} className="px-4 py-6 text-center text-slate-500">
                      {taskEventsLoading ? '加载中…' : '暂无事件'}
                    </td>
                  </tr>
                ) : (
                  taskEvents.map((event) => (
                    <tr key={`comfy-agent-task-event-${event.id}`} className="border-t border-slate-100 dark:border-slate-800">
                      <td className="px-3 py-2 text-slate-600 dark:text-slate-400">
                        {formatDateTime(event.created_at || event.eventTime)}
                      </td>
                      <td className="px-3 py-2 text-slate-700 dark:text-slate-300">{event.level}</td>
                      <td className="px-3 py-2 text-slate-700 dark:text-slate-300">{event.message}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </Space>
      </Dialog>
    </div>
  );
}
