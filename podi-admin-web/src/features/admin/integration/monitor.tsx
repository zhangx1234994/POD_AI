import { Button, Card, Col, Row, Space, Table, Typography } from 'tdesign-react';
import type { ComfyuiQueueSummary, DashboardMetrics, Executor } from '../../../types/admin';
import { StatusBadge } from '../shared/ui';
import { formatDateTime } from './formatters';

function MetricCard({ label, value, sub }: { label: string; value: number | string; sub?: string }) {
  return (
    <Card bordered className="podi-metric-card">
      <Space direction="vertical" size="small">
        <Typography.Text theme="secondary">{label}</Typography.Text>
        <Typography.Title level="h2" style={{ margin: 0 }}>
          {value}
        </Typography.Title>
        {sub ? <Typography.Text theme="secondary">{sub}</Typography.Text> : null}
      </Space>
    </Card>
  );
}

function StatusPill({ status }: { status: string }) {
  return <StatusBadge status={status} />;
}

type QueueOverviewRow = {
  key: string;
  label: string;
  pending: number;
  running: number;
  note?: string;
};

type MonitorPanelProps = {
  dashboardMetrics: DashboardMetrics;
  pendingQueueTotal: number;
  pendingQueueSub: string;
  runningQueueTotal: number;
  runningQueueSub: string;
  pendingBatchValue: number;
  pendingBatchSub: string;
  queueOverviewRows: QueueOverviewRow[];
  comfyExecutors: Executor[];
  comfyQueueSummary?: ComfyuiQueueSummary | null;
  comfyQueueSummaryLoading: boolean;
  executors: Executor[];
  onRefreshComfyQueue: () => void;
};

export function MonitorPanel({
  dashboardMetrics,
  pendingQueueTotal,
  pendingQueueSub,
  runningQueueTotal,
  runningQueueSub,
  pendingBatchValue,
  pendingBatchSub,
  queueOverviewRows,
  comfyExecutors,
  comfyQueueSummary,
  comfyQueueSummaryLoading,
  executors,
  onRefreshComfyQueue,
}: MonitorPanelProps) {
  return (
    <>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="累计任务" value={dashboardMetrics.totals.total_tasks} sub="历史累计" />
        <MetricCard label="排队中" value={pendingQueueTotal} sub={pendingQueueSub} />
        <MetricCard label="执行中（含回调）" value={runningQueueTotal} sub={runningQueueSub} />
        <MetricCard label="批次待处理" value={pendingBatchValue} sub={pendingBatchSub} />
        <MetricCard label="失败任务" value={dashboardMetrics.totals.failed_tasks} sub="含错误待复盘" />
        <MetricCard
          label="ComfyUI 排队"
          value={comfyQueueSummary ? comfyQueueSummary.totalPending : '—'}
          sub={
            comfyExecutors.length === 0
              ? '未配置 ComfyUI 节点'
              : comfyQueueSummaryLoading
                ? '加载中'
                : comfyQueueSummary
                  ? `执行中 ${comfyQueueSummary.totalRunning}`
                  : '等待刷新'
          }
        />
      </div>

      <Row gutter={[16, 16]}>
        <Col span={12}>
          <Card title="状态分布" bordered>
            <Typography.Text theme="secondary">统计所有任务的最新状态，便于评估调度堵塞点。</Typography.Text>
            <div style={{ marginTop: 12 }}>
              <Table
                rowKey="status"
                size="small"
                data={dashboardMetrics.status_buckets}
                columns={[
                  { colKey: 'status', title: '状态', width: 220 },
                  { colKey: 'count', title: '数量' },
                ]}
              />
            </div>
          </Card>
        </Col>
        <Col span={12}>
          <Card title="今日任务" bordered>
            <Typography.Text theme="secondary">按东八区自然日统计。</Typography.Text>
            <div style={{ marginTop: 12 }} className="grid gap-4 sm:grid-cols-3">
              <MetricCard label="新建" value={dashboardMetrics.today.created} />
              <MetricCard label="完成" value={dashboardMetrics.today.completed} />
              <MetricCard label="失败" value={dashboardMetrics.today.failed} />
            </div>
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col span={24}>
          <Card title="队列总览" bordered>
            <Typography.Text theme="secondary">
              排队包含新建、等待、已入队状态；执行包含运行中与回调中。批次任务显示“待处理批次 / 剩余任务数”。
            </Typography.Text>
            <div style={{ marginTop: 12 }}>
              <Table
                rowKey="key"
                size="small"
                data={queueOverviewRows}
                columns={[
                  { colKey: 'label', title: '类型', width: 180 },
                  { colKey: 'pending', title: '排队中', width: 140 },
                  { colKey: 'running', title: '执行中', width: 140 },
                  {
                    colKey: 'total',
                    title: '合计',
                    width: 140,
                    cell: ({ row }) => (row.pending || 0) + (row.running || 0),
                  },
                  {
                    colKey: 'note',
                    title: '备注',
                    cell: ({ row }) => row.note || '—',
                  },
                ]}
              />
            </div>
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col span={24}>
          <Card
            title={
              <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
                <Space align="center">
                  <span>ComfyUI 队列</span>
                  <Typography.Text theme="secondary">跨节点汇总</Typography.Text>
                </Space>
                <Button
                  size="small"
                  variant="outline"
                  onClick={onRefreshComfyQueue}
                  loading={comfyQueueSummaryLoading}
                  disabled={comfyExecutors.length === 0}
                >
                  刷新
                </Button>
              </Space>
            }
            bordered
          >
            <Typography.Text theme="secondary">该队列来自 ComfyUI 节点自身的 /queue 状态，与内部任务队列分开统计。</Typography.Text>
            <div style={{ marginTop: 12 }} className="grid gap-4 sm:grid-cols-3">
              <MetricCard label="执行中" value={comfyQueueSummary?.totalRunning ?? '—'} />
              <MetricCard label="等待中" value={comfyQueueSummary?.totalPending ?? '—'} />
              <MetricCard label="合计" value={comfyQueueSummary?.totalCount ?? '—'} />
            </div>
            <div style={{ marginTop: 12 }}>
              <Table
                rowKey="executorId"
                size="small"
                data={comfyQueueSummary?.servers || []}
                columns={[
                  {
                    colKey: 'executorId',
                    title: '节点',
                    cell: ({ row }) => {
                      const ex = executors.find((item) => item.id === row.executorId);
                      return (
                        <Space direction="vertical" size={2}>
                          <Typography.Text>{ex?.name || row.executorId}</Typography.Text>
                          <Typography.Text theme="secondary">{row.executorId}</Typography.Text>
                        </Space>
                      );
                    },
                  },
                  {
                    colKey: 'baseUrl',
                    title: '服务地址',
                    ellipsis: true,
                  },
                  { colKey: 'runningCount', title: '执行中', width: 120 },
                  { colKey: 'pendingCount', title: '等待中', width: 120 },
                  {
                    colKey: 'queueMaxSize',
                    title: '队列上限',
                    width: 100,
                    cell: ({ row }) => (typeof row.queueMaxSize === 'number' ? row.queueMaxSize : '—'),
                  },
                  {
                    colKey: 'supported',
                    title: '支持',
                    width: 100,
                    cell: ({ row }) => (row.supported === false ? '否' : '是'),
                  },
                  {
                    colKey: 'message',
                    title: '备注',
                    ellipsis: true,
                    cell: ({ row }) => (row.message ? <Typography.Text theme="warning">{row.message}</Typography.Text> : '—'),
                  },
                ]}
                empty={
                  comfyQueueSummaryLoading ? (
                    <Typography.Text theme="secondary">加载中…</Typography.Text>
                  ) : (
                    <Typography.Text theme="secondary">暂无队列数据。</Typography.Text>
                  )
                }
              />
            </div>
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col span={12}>
          <Card
            title={
              <Space align="center">
                <span>最近任务</span>
                <Typography.Text theme="secondary">最新 8 条</Typography.Text>
              </Space>
            }
            bordered
          >
            <Table
              rowKey="id"
              size="small"
              data={dashboardMetrics.recent_tasks}
              columns={[
                {
                  colKey: 'tool_action',
                  title: '任务',
                  ellipsis: true,
                  cell: ({ row }) => (
                    <Space direction="vertical" size={2}>
                      <Typography.Text>{row.tool_action}</Typography.Text>
                      <Typography.Text theme="secondary">{row.id}</Typography.Text>
                    </Space>
                  ),
                },
                { colKey: 'channel', title: '渠道', width: 160, ellipsis: true },
                { colKey: 'status', title: '状态', width: 140, cell: ({ row }) => <StatusPill status={row.status} /> },
                {
                  colKey: 'created_at',
                  title: '时间',
                  width: 220,
                  cell: ({ row }) => <Typography.Text theme="secondary">{formatDateTime(row.created_at)}</Typography.Text>,
                },
              ]}
            />
          </Card>
        </Col>
        <Col span={12}>
          <Card title="节点健康" bordered>
            <Table
              rowKey="id"
              size="small"
              data={dashboardMetrics.executor_health}
              columns={[
                {
                  colKey: 'name',
                  title: '节点',
                  ellipsis: true,
                  cell: ({ row }) => (
                    <Space direction="vertical" size={2}>
                      <Typography.Text>{row.name}</Typography.Text>
                      <Typography.Text theme="secondary">{row.id}</Typography.Text>
                    </Space>
                  ),
                },
                { colKey: 'status', title: '状态', width: 120, cell: ({ row }) => <StatusPill status={row.status} /> },
                { colKey: 'health_status', title: '健康', width: 120, ellipsis: true },
                { colKey: 'max_concurrency', title: '并发', width: 80 },
                { colKey: 'weight', title: '权重', width: 80 },
                {
                  colKey: 'last_heartbeat_at',
                  title: '心跳',
                  width: 220,
                  cell: ({ row }) =>
                    row.last_heartbeat_at ? (
                      <Typography.Text theme="secondary">{formatDateTime(row.last_heartbeat_at)}</Typography.Text>
                    ) : (
                      <Typography.Text theme="secondary">—</Typography.Text>
                    ),
                },
              ]}
              empty={<Typography.Text theme="secondary">暂无节点数据。</Typography.Text>}
            />
          </Card>
        </Col>
      </Row>
    </>
  );
}
