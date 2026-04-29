import { Alert, Button, Card, Col, Dialog, Input, Row, Select, Space, Switch, Typography } from 'tdesign-react';
import type {
  ComfyuiAgentManifest,
  ComfyuiAgentTask,
  ComfyuiAgentTaskEvent,
  ComfyuiMonitoringSummary,
  ComfyuiQueueSummary,
} from '../../../types/admin';
import { toDisplayErrorMessage } from '../../../utils/errorMessageMap';
import { StatusBadge } from '../shared/ui';
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
  onTaskAgentFilterChange: (agentId: string) => void;
  onTaskStatusFilterChange: (status: string) => void;
  onRefreshTasks: () => void;
  onPushTask: (taskId: string) => void;
  onOpenTaskEvents: (taskId: string) => void;
  onCloseTaskEvents: () => void;
};

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
  const mapAlertTheme = (level?: string | null): 'success' | 'info' | 'warning' | 'error' => {
    if (level === 'danger') return 'error';
    if (level === 'warning') return 'warning';
    if (level === 'success') return 'success';
    return 'info';
  };
  const feedGapCount = queueSummary?.feedGapServers ?? 0;
  const blockedCount = queueSummary?.backendBlockedServers ?? 0;
  const queueRiskText = blockedCount > 0
    ? `疑似卡住 ${blockedCount} 条`
    : feedGapCount > 0
      ? `下发偏慢 ${feedGapCount} 条`
      : '暂无明显风险';

  return (
    <div className="space-y-4">
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
          <div className="grid gap-3 md:grid-cols-4">
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
              <div className="text-xs text-slate-500">风险判断</div>
              <div
                className={
                  blockedCount > 0
                    ? 'mt-1 text-lg font-semibold text-rose-600'
                    : feedGapCount > 0
                      ? 'mt-1 text-lg font-semibold text-amber-600'
                      : 'mt-1 text-lg font-semibold text-emerald-600'
                }
              >
                {queueSummary ? queueRiskText : queueSummaryLoading ? '读取中…' : '—'}
              </div>
              <div className="mt-1 text-xs text-slate-500">
                下发偏慢 {feedGapCount} · 疑似卡住 {blockedCount}
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
                  <th className="px-3 py-2">判断</th>
                </tr>
              </thead>
              <tbody>
                {!queueSummary?.servers?.length ? (
                  <tr>
                    <td colSpan={5} className="px-4 py-6 text-center text-slate-500">
                      {queueSummaryLoading ? '加载中…' : '暂无 ComfyUI 线路诊断'}
                    </td>
                  </tr>
                ) : (
                  queueSummary.servers.map((server) => (
                    <tr key={`comfy-queue-diagnosis-${server.executorId}`} className="border-t border-slate-100 dark:border-slate-800">
                      <td className="px-3 py-2 text-slate-700 dark:text-slate-300">
                        <div className="font-semibold text-slate-900 dark:text-white">{server.executorId}</div>
                        <div className="mt-1 max-w-[260px] truncate text-[11px] text-slate-500">{server.baseUrl}</div>
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
                        {server.feedDiagnosis || server.diagnosis || '—'}
                      </td>
                    </tr>
                  ))
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
