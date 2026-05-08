import { Button, Card, Space, Table, Tag, Typography } from 'tdesign-react';
import type { DispatchLogEntry } from '../../../types/admin';
import { OperationFlowCard, StatusBadge } from '../shared/ui';
import { formatDate } from './formatters';

function StatusPill({ status }: { status: string }) {
  return <StatusBadge status={status} />;
}

function previewPayload(payload?: Record<string, unknown> | null) {
  if (!payload) return '—';
  const json = JSON.stringify(payload);
  return json.length > 80 ? `${json.slice(0, 77)}…` : json;
}

export function DispatchLogsPanel({
  dispatchLogs,
  onOpenDetail,
}: {
  dispatchLogs: DispatchLogEntry[];
  onOpenDetail: (entry: DispatchLogEntry) => void;
}) {
  const abnormalCount = dispatchLogs.filter((entry) => /fail|error|timeout|异常|失败/i.test(String(entry.event_type || ''))).length;
  const dispatchSummary =
    dispatchLogs.length === 0
      ? '当前没有调度日志；如果业务刚运行过，先刷新页面或检查后端日志采集。'
      : abnormalCount > 0
        ? `最近 ${dispatchLogs.length} 条调度事件里有 ${abnormalCount} 条异常，先展开异常回执再回到任务详情。`
        : `最近 ${dispatchLogs.length} 条调度事件未发现明显异常，可用于核对任务动作和回执时间。`;

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <OperationFlowCard
        title="调度日志排障闭环"
        description="这里看任务动作和回执证据，不能只凭状态判断业务是否完成。"
        summary={dispatchSummary}
        summaryTheme={abnormalCount > 0 ? 'warning' : dispatchLogs.length > 0 ? 'success' : 'default'}
        steps={[
          {
            key: 'task',
            title: '先找任务 ID',
            detail: '用任务 ID 把调度事件、能力调用、业务运行记录串起来。',
            action: '复制 taskId 后回到能力调用或业务详情做交叉验证。',
            done: '任务可追',
          },
          {
            key: 'event',
            title: '看事件类型',
            detail: '事件类型说明当前是提交、回执、失败还是状态更新。',
            action: '异常事件优先展开详情，不直接重试业务。',
            done: abnormalCount > 0 ? '有异常' : '类型清楚',
            theme: abnormalCount > 0 ? 'warning' : 'primary',
          },
          {
            key: 'payload',
            title: '展开回执摘要',
            detail: '摘要只够快速判断，真正定位要打开详情查看完整 payload。',
            action: '点击“查看”确认上游 taskId、输出、错误码和时间。',
            done: '证据完整',
          },
          {
            key: 'next',
            title: '回到主链路处理',
            detail: '调度日志只负责定位，不在这里完成修复动作。',
            action: '按问题回到业务能力、能力调用、ComfyUI 或执行节点页面处理。',
            done: '回到归口',
          },
        ]}
      />
      <Card
        bordered
        title={
          <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
            <Space direction="vertical" size={2}>
              <Typography.Text strong>调度事件</Typography.Text>
              <Typography.Text theme="secondary">最新 25 条，包含任务动作、回执摘要与处理时间。</Typography.Text>
            </Space>
            <Tag variant="light">{dispatchLogs.length} 条</Tag>
          </Space>
        }
      >
        <Table
          size="small"
          rowKey="id"
          data={dispatchLogs}
          columns={[
            {
              colKey: 'id',
              title: 'ID',
              width: 80,
              cell: ({ row }) => <Typography.Text theme="secondary">{row.id}</Typography.Text>,
            },
            {
              colKey: 'task',
              title: '任务',
              minWidth: 260,
              cell: ({ row }) => (
                <Space direction="vertical" size={2}>
                  <Typography.Text strong>{row.tool_action}</Typography.Text>
                  <Typography.Text theme="secondary" style={{ fontSize: 12, fontFamily: 'monospace' }}>
                    {row.task_id}
                  </Typography.Text>
                </Space>
              ),
            },
            {
              colKey: 'event_type',
              title: '类型',
              width: 140,
              cell: ({ row }) => <StatusPill status={row.event_type} />,
            },
            {
              colKey: 'payload',
              title: '回执摘要',
              minWidth: 240,
              cell: ({ row }) => <Typography.Text theme="secondary">{previewPayload(row.payload)}</Typography.Text>,
            },
            {
              colKey: 'created_at',
              title: '时间',
              width: 180,
              cell: ({ row }) => <Typography.Text theme="secondary">{formatDate(row.created_at)}</Typography.Text>,
            },
            {
              colKey: 'actions',
              title: '详情',
              width: 100,
              cell: ({ row }) => (
                <Button size="small" variant="text" onClick={() => onOpenDetail(row)}>
                  查看
                </Button>
              ),
            },
          ]}
          empty={<Typography.Text theme="secondary">暂无日志。</Typography.Text>}
        />
      </Card>
    </Space>
  );
}
