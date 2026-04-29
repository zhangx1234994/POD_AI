import { Alert, Button, Card, Popup, Space, Switch, Table, Tag, Typography } from 'tdesign-react';
import type { Ability, AbilityInvocationLog } from '../../../types/admin';
import { toDisplayErrorMessage } from '../../../utils/errorMessageMap';
import {
  getAbilityLogCallbackStageTag,
  getAbilityLogSubmitTag,
  isAbilityLogSuccessful,
  resolveLogDurationMs,
  resolveLogOutputSummary,
} from './abilityLogs';
import { formatDateTime } from './formatters';

const abilitySourceLabels: Record<string, string> = {
  'admin-test': '控制台测试',
  workflow: '工作流',
  task: '任务调度',
  'ability-api': '能力接口',
  'ability-task': '异步任务',
  ability_api: '能力接口',
  ability_task: '异步任务',
};

const formatAbilitySource = (value?: string | null) => {
  if (!value) return '未知来源';
  return abilitySourceLabels[value] ?? value;
};

const getAbilitySourceTagTheme = (value?: string | null) => {
  const v = value || '';
  if (v === 'admin-test') return 'primary' as const;
  if (v === 'ability-api' || v === 'ability_api') return 'warning' as const;
  if (v === 'ability-task' || v === 'ability_task') return 'default' as const;
  if (v === 'workflow') return 'success' as const;
  if (v === 'task') return 'warning' as const;
  return 'default' as const;
};

export function AbilityRecentLogsPanel({
  selectedAbility,
  logs,
  total,
  loading,
  error,
  autoRefresh,
  updatedAt,
  hasMore,
  onAutoRefreshChange,
  onRefresh,
  onLoadMore,
  onOpenDetail,
}: {
  selectedAbility?: Ability | null;
  logs: AbilityInvocationLog[];
  total?: number | null;
  loading: boolean;
  error?: string | null;
  autoRefresh: boolean;
  updatedAt?: string | null;
  hasMore: boolean;
  onAutoRefreshChange: (value: boolean) => void;
  onRefresh: () => void;
  onLoadMore: () => void;
  onOpenDetail: (row: AbilityInvocationLog) => void;
}) {
  if (!selectedAbility) {
    return <Alert theme="info" message="请选择能力后查看最近的调用记录。" />;
  }

  return (
    <Card
      bordered
      title={
        <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
          <div>
            <Typography.Text strong>最近调用记录</Typography.Text>
            <div>
              <Typography.Text theme="secondary">
                已加载 {logs.length}
                {typeof total === 'number' ? ` / ${total}` : ''} 条 · 自动刷新仅更新最近一页
              </Typography.Text>
            </div>
          </div>
          <Space>
            <Space align="center" size="small">
              <Typography.Text theme="secondary">自动刷新</Typography.Text>
              <Switch value={autoRefresh} onChange={(value) => onAutoRefreshChange(Boolean(value))} />
            </Space>
            {updatedAt ? <Typography.Text theme="secondary">更新：{formatDateTime(updatedAt)}</Typography.Text> : null}
            <Button variant="outline" loading={loading} onClick={onRefresh}>
              刷新
            </Button>
          </Space>
        </Space>
      }
    >
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        {error ? <Alert theme="error" message={error} /> : null}
        <Table
          size="small"
          rowKey="id"
          loading={loading}
          data={logs}
          empty={<Typography.Text theme="secondary">暂无历史记录，运行一次测试即可自动写入。</Typography.Text>}
          columns={[
            {
              colKey: 'created_at',
              title: '时间',
              width: 180,
              cell: ({ row }) => <Typography.Text>{formatDateTime(row.created_at)}</Typography.Text>,
            },
            {
              colKey: 'source',
              title: '来源',
              width: 120,
              cell: ({ row }) => (
                <Tag theme={getAbilitySourceTagTheme(row.source)} variant="light">
                  {formatAbilitySource(row.source)}
                </Tag>
              ),
            },
            {
              colKey: 'executor',
              title: '节点',
              width: 220,
              cell: ({ row }) => <Typography.Text theme="secondary">{row.executor_name || row.executor_id || '—'}</Typography.Text>,
            },
            {
              colKey: 'status',
              title: '提交',
              width: 160,
              cell: ({ row }) => {
                const durationMs = resolveLogDurationMs(row);
                const submitTag = getAbilityLogSubmitTag(row);
                return (
                  <Space direction="vertical" size={2}>
                    <Tag theme={submitTag.theme} variant="light">
                      {submitTag.text}
                    </Tag>
                    {typeof durationMs === 'number' ? (
                      <Typography.Text theme="secondary" style={{ fontSize: 12 }}>
                        {durationMs}ms
                      </Typography.Text>
                    ) : null}
                  </Space>
                );
              },
            },
            {
              colKey: 'callback',
              title: '回调阶段',
              width: 160,
              cell: ({ row }) => {
                const callbackTag = getAbilityLogCallbackStageTag(row);
                return (
                  <Space direction="vertical" size={2}>
                    <Tag theme={callbackTag.theme} variant="light">
                      {callbackTag.text}
                    </Tag>
                    {typeof row.callback_http_status === 'number' ? (
                      <Typography.Text theme="secondary" style={{ fontSize: 12 }}>
                        HTTP {row.callback_http_status}
                      </Typography.Text>
                    ) : null}
                    {row.callback_finished_at ? (
                      <Typography.Text theme="secondary" style={{ fontSize: 12 }}>
                        {formatDateTime(row.callback_finished_at)}
                      </Typography.Text>
                    ) : null}
                  </Space>
                );
              },
            },
            {
              colKey: 'result',
              title: '结果',
              minWidth: 240,
              cell: ({ row }) => {
                const output = resolveLogOutputSummary(row);
                return (
                  <Space size="small">
                    {output.primaryUrl ? (
                      output.primaryKind === 'image' ? (
                        <Popup
                          trigger="hover"
                          placement="left"
                          content={<img src={output.primaryUrl} alt="preview" style={{ maxWidth: 360, maxHeight: 360, display: 'block' }} />}
                        >
                          <Button size="small" variant="text">
                            预览图片
                          </Button>
                        </Popup>
                      ) : (
                        <Button size="small" variant="text" onClick={() => window.open(output.primaryUrl, '_blank', 'noreferrer')}>
                          {output.primaryKind === 'video' ? '打开视频' : '打开资源'}
                        </Button>
                      )
                    ) : null}
                    {!output.primaryUrl && output.textPreview ? (
                      <Typography.Text theme="secondary">{output.textPreview}</Typography.Text>
                    ) : null}
                    {output.hasOutput ? <Typography.Text theme="secondary">{output.label}</Typography.Text> : null}
                    <Button size="small" variant="text" onClick={() => onOpenDetail(row)}>
                      详情
                    </Button>
                    {row.error_message ? <Typography.Text theme="error">{toDisplayErrorMessage(row.error_message)}</Typography.Text> : null}
                    {!output.hasOutput && !row.error_message ? (
                      <Typography.Text theme="secondary">{isAbilityLogSuccessful(row.status) ? '输出回填中' : '—'}</Typography.Text>
                    ) : null}
                  </Space>
                );
              },
            },
          ]}
        />
        <div className="flex items-center justify-between">
          <Typography.Text theme="secondary">{updatedAt ? `最近刷新：${formatDateTime(updatedAt)}` : '尚未刷新'}</Typography.Text>
          {hasMore ? (
            <Button variant="outline" loading={loading} onClick={onLoadMore}>
              加载更多
            </Button>
          ) : (
            <Typography.Text theme="secondary">已加载全部</Typography.Text>
          )}
        </div>
      </Space>
    </Card>
  );
}
