import { Alert, Button, Col, Input, Popup, Row, Select, Space, Switch, Table, Tag, Typography } from 'tdesign-react';
import type { AbilityInvocationLog } from '../../../types/admin';
import { toDisplayErrorMessage } from '../../../utils/errorMessageMap';
import {
  getAbilityLogCallbackStageTag,
  getAbilityLogStatusTag,
  getAbilityLogSubmitTag,
  isAbilityLogSuccessful,
  resolveLogDurationMs,
  resolveLogOutputSummary,
} from './abilityLogs';
import { formatDateTime, formatPriceValue, formatUnitLabel } from './formatters';
import { ActionBar } from '../shared/ui';

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

const formatTaskMarker = (value?: string | null) => {
  if (!value) return '';
  const trimmed = value.trim();
  if (trimmed.length <= 16) return trimmed;
  return `${trimmed.slice(0, 8)}…${trimmed.slice(-4)}`;
};

const truncateText = (value?: string | null, max = 60) => {
  if (!value) return '';
  const trimmed = value.trim();
  if (trimmed.length <= max) return trimmed;
  return `${trimmed.slice(0, max)}…`;
};

type SelectOption = {
  label: string;
  value: string | number;
};

type AbilityPricing = {
  currency?: string;
  unit?: string;
  listPrice?: number;
  discountPrice?: number;
};

export function AbilityLogListPanel({
  logs,
  filteredLogs,
  total,
  loading,
  exporting,
  error,
  updatedAt,
  hasMore,
  autoRefresh,
  onlyCallbackFailed,
  search,
  provider,
  source,
  status,
  templatePublished,
  capabilityKey,
  providers,
  sources,
  statuses,
  capabilityOptions,
  onAutoRefreshChange,
  onRefresh,
  onLoadMore,
  onExport,
  onOnlyCallbackFailedChange,
  onSearchChange,
  onProviderChange,
  onSourceChange,
  onStatusChange,
  onTemplatePublishedChange,
  onCapabilityKeyChange,
  onCopy,
  onOpenDetail,
  resolveLogPricing,
}: {
  logs: AbilityInvocationLog[];
  filteredLogs: AbilityInvocationLog[];
  total?: number | null;
  loading: boolean;
  exporting: boolean;
  error?: string | null;
  updatedAt?: string | null;
  hasMore: boolean;
  autoRefresh: boolean;
  onlyCallbackFailed: boolean;
  search: string;
  provider: string;
  source: string;
  status: string;
  templatePublished: string;
  capabilityKey: string;
  providers: string[];
  sources: string[];
  statuses: string[];
  capabilityOptions: SelectOption[];
  onAutoRefreshChange: (value: boolean) => void;
  onRefresh: () => void;
  onLoadMore: () => void;
  onExport: (format: 'csv' | 'json') => void;
  onOnlyCallbackFailedChange: (value: boolean) => void;
  onSearchChange: (value: string) => void;
  onProviderChange: (value: string) => void;
  onSourceChange: (value: string) => void;
  onStatusChange: (value: string) => void;
  onTemplatePublishedChange: (value: string) => void;
  onCapabilityKeyChange: (value: string) => void;
  onCopy: (value: string) => void;
  onOpenDetail: (row: AbilityInvocationLog) => void;
  resolveLogPricing: (row: AbilityInvocationLog) => AbilityPricing | null;
}) {
  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <ActionBar>
        <Space align="center" style={{ justifyContent: 'space-between', width: '100%', flexWrap: 'wrap' }}>
          <div>
            <Typography.Text strong>能力调用清单</Typography.Text>
            <div>
              <Typography.Text theme="secondary">
                已加载 {logs.length}
                {typeof total === 'number' ? ` / ${total}` : ''} 条 · 支持导出最近 24 小时
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
            {hasMore ? (
              <Button variant="outline" loading={loading} onClick={onLoadMore}>
                加载更多
              </Button>
            ) : (
              <Typography.Text theme="secondary">已加载全部</Typography.Text>
            )}
            <Button variant="outline" loading={exporting} onClick={() => onExport('csv')}>
              导出 CSV
            </Button>
            <Button variant="outline" loading={exporting} onClick={() => onExport('json')}>
              导出原始数据
            </Button>
          </Space>
        </Space>
      </ActionBar>

      {error ? <Alert theme="error" message={error} /> : null}

      <Space align="center" size="large">
        <Space align="center" size="small">
          <Switch value={status === 'failed'} onChange={(value) => onStatusChange(value ? 'failed' : 'all')} />
          <Typography.Text theme="secondary">只看失败</Typography.Text>
        </Space>
        <Space align="center" size="small">
          <Switch value={onlyCallbackFailed} onChange={(value) => onOnlyCallbackFailedChange(Boolean(value))} />
          <Typography.Text theme="secondary">只看回调异常</Typography.Text>
        </Space>
      </Space>

      <Row gutter={[12, 12]}>
        <Col flex="auto">
          <Input value={search} placeholder="搜索：能力名/能力标识/节点/追踪/任务/回调编号…" onChange={(value) => onSearchChange(String(value))} clearable />
        </Col>
        <Col flex="180px">
          <Select
            value={provider}
            onChange={(value) => onProviderChange(String(value))}
            options={[{ label: '全部厂商', value: 'all' }, ...providers.map((item) => ({ label: item, value: item }))]}
          />
        </Col>
        <Col flex="180px">
          <Select
            value={source}
            onChange={(value) => onSourceChange(String(value))}
            options={[{ label: '全部来源', value: 'all' }, ...sources.map((item) => ({ label: formatAbilitySource(item), value: item }))]}
          />
        </Col>
        <Col flex="180px">
          <Select
            value={status}
            onChange={(value) => onStatusChange(String(value))}
            options={[{ label: '全部状态', value: 'all' }, ...statuses.map((item) => ({ label: getAbilityLogStatusTag(item).text, value: item }))]}
          />
        </Col>
        <Col flex="180px">
          <Select
            value={templatePublished}
            onChange={(value) => onTemplatePublishedChange(String(value))}
            options={[
              { label: '模板状态：全部', value: 'all' },
              { label: '已发布模板', value: 'published' },
              { label: '未发布模板', value: 'unpublished' },
            ]}
          />
        </Col>
        <Col flex="260px">
          <Select
            value={capabilityKey}
            onChange={(value) => onCapabilityKeyChange(String(value))}
            disabled={provider === 'all'}
            options={[
              { label: provider === 'all' ? '请先选择厂商' : '全部能力', value: 'all' },
              ...capabilityOptions,
            ]}
          />
        </Col>
      </Row>

      <Table
        size="small"
        rowKey="id"
        loading={loading}
        data={filteredLogs}
        empty={<Typography.Text theme="secondary">暂无数据。</Typography.Text>}
        columns={[
          {
            colKey: 'created_at',
            title: '时间',
            width: 180,
            cell: ({ row }) => <Typography.Text>{formatDateTime(row.created_at)}</Typography.Text>,
          },
          {
            colKey: 'ability',
            title: '能力',
            minWidth: 240,
            cell: ({ row }) => (
              <Space direction="vertical" size={2}>
                <Typography.Text strong>{row.ability_name || row.capability_key || '—'}</Typography.Text>
                <Typography.Text theme="secondary">{row.ability_provider || '—'}</Typography.Text>
                {row.trace_id || row.workflow_run_id ? (
                  <Typography.Text theme="secondary" style={{ fontSize: 12 }}>
                    {row.trace_id ? (
                      <span style={{ marginRight: 12 }}>
                        追踪：<span style={{ fontFamily: 'monospace' }}>{formatTaskMarker(row.trace_id)}</span>
                      </span>
                    ) : null}
                    {row.workflow_run_id ? (
                      <span>
                        流程：<span style={{ fontFamily: 'monospace' }}>{formatTaskMarker(row.workflow_run_id)}</span>
                      </span>
                    ) : null}
                  </Typography.Text>
                ) : null}
              </Space>
            ),
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
            colKey: 'template',
            title: '模板版本',
            width: 220,
            cell: ({ row }) => (
              <Space direction="vertical" size={2}>
                {row.ability_current_template_id ? (
                  <Typography.Text style={{ fontFamily: 'monospace' }}>{formatTaskMarker(row.ability_current_template_id)}</Typography.Text>
                ) : (
                  <Typography.Text theme="secondary">未发布模板</Typography.Text>
                )}
                <Typography.Text theme="secondary" style={{ fontSize: 12 }}>
                  历史 {row.ability_template_history_count ?? 0} 个版本
                </Typography.Text>
              </Space>
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
            colKey: 'error_summary',
            title: '错误摘要',
            width: 220,
            cell: ({ row }) => {
              const message = row.error_message || row.callback_error || '';
              if (!message) return <Typography.Text theme="secondary">—</Typography.Text>;
              return (
                <Typography.Text theme="error" style={{ fontSize: 12 }}>
                  {truncateText(message, 80)}
                </Typography.Text>
              );
            },
          },
          {
            colKey: 'callback_id',
            title: '回调编号',
            width: 260,
            cell: ({ row }) => {
              if (!row.callback_id) return <Typography.Text theme="secondary">—</Typography.Text>;
              return (
                <Space size="small">
                  <Typography.Text theme="secondary" style={{ fontFamily: 'monospace', wordBreak: 'break-all' }}>
                    {row.callback_id}
                  </Typography.Text>
                  <Button size="small" variant="text" onClick={() => onCopy(row.callback_id || '')}>
                    复制
                  </Button>
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
            colKey: 'cost',
            title: '成本',
            width: 140,
            cell: ({ row }) => {
              const logPricing = resolveLogPricing(row);
              const primaryCost =
                logPricing && (logPricing.discountPrice ?? logPricing.listPrice) !== undefined
                  ? `${formatPriceValue(logPricing.discountPrice ?? logPricing.listPrice, logPricing.currency)}`
                  : null;
              return primaryCost ? (
                <Space direction="vertical" size={2}>
                  <Typography.Text>{primaryCost}</Typography.Text>
                  <Typography.Text theme="secondary" style={{ fontSize: 12 }}>
                    {formatUnitLabel(logPricing?.unit)}
                  </Typography.Text>
                </Space>
              ) : (
                <Typography.Text theme="secondary">—</Typography.Text>
              );
            },
          },
          {
            colKey: 'result',
            title: '结果',
            minWidth: 220,
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
                    <Typography.Text theme="secondary">{truncateText(output.textPreview, 80)}</Typography.Text>
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

      <div className="flex flex-col gap-2">
        <Typography.Text theme="secondary">{updatedAt ? `最近刷新：${formatDateTime(updatedAt)}` : '尚未刷新'}</Typography.Text>
        <div className="flex justify-center">
          {hasMore ? (
            <Button variant="outline" loading={loading} onClick={onLoadMore}>
              加载更多
            </Button>
          ) : (
            <Typography.Text theme="secondary">已加载全部</Typography.Text>
          )}
        </div>
      </div>
    </Space>
  );
}
