import { Button, Card, Space, Table, Tag, Typography } from 'tdesign-react';
import type { DispatchLogEntry } from '../../../types/admin';
import { StatusBadge } from '../shared/ui';
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
  return (
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
  );
}
