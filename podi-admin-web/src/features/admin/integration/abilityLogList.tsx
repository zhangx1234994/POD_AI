import { Alert, Button, Col, Input, Popup, Row, Select, Space, Switch, Table, Tag, Typography } from 'tdesign-react';
import type { AbilityInvocationLog } from '../../../types/admin';
import { toDisplayErrorMessage } from '../../../utils/errorMessageMap';
import {
  buildAbilityLogTroubleSummary,
  resolveAbilityLogAction,
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

type LogOutputKind = 'image' | 'video' | 'text' | 'structured' | 'asset' | 'none';

const outputKindMeta: Record<LogOutputKind, { label: string; detail: string; theme: 'success' | 'warning' | 'primary' | 'default' }> = {
  image: { label: '图片输出', detail: '生图、修图、抠图、扩图等图片结果', theme: 'success' },
  video: { label: '视频输出', detail: '生视频或视频处理结果', theme: 'warning' },
  text: { label: '文字输出', detail: '文字增强、提示词、文案等文本结果', theme: 'primary' },
  structured: { label: '结构化结果', detail: 'VL 分析、质检、标签、JSON 判断', theme: 'success' },
  asset: { label: '资源输出', detail: '文件、链接或暂未归类资源', theme: 'default' },
  none: { label: '未回填', detail: '执行中、失败或暂未解析到输出', theme: 'default' },
};

const resolveLogOutputKind = (row: AbilityInvocationLog): LogOutputKind => {
  const output = resolveLogOutputSummary(row);
  if (!output.hasOutput) return 'none';
  if (output.imageCount > 0 || output.primaryKind === 'image') return 'image';
  if (output.videoCount > 0 || output.primaryKind === 'video') return 'video';
  if (output.textCount > 0 || output.primaryKind === 'text') return 'text';
  if (output.structuredCount > 0 || output.primaryKind === 'structured') return 'structured';
  return 'asset';
};

const buildOutputKindStats = (rows: AbilityInvocationLog[]) =>
  rows.reduce(
    (acc, row) => {
      acc[resolveLogOutputKind(row)] += 1;
      return acc;
    },
    { image: 0, video: 0, text: 0, structured: 0, asset: 0, none: 0 } as Record<LogOutputKind, number>,
  );

export function AbilityLogListPanel({
  logs,
  filteredLogs,
  total,
  loading,
  exporting,
  error,
  updatedAt,
  page,
  pageSize,
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
  onPageChange,
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
  page: number;
  pageSize: number;
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
  onPageChange: (page: number) => void;
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
  const safePageSize = Math.max(1, pageSize || 1);
  const totalCount = typeof total === 'number' ? total : logs.length;
  const totalPages = Math.max(1, Math.ceil(totalCount / safePageSize));
  const currentPage = Math.min(Math.max(1, page || 1), totalPages);
  const pageStart = totalCount === 0 ? 0 : (currentPage - 1) * safePageSize + 1;
  const pageEnd = totalCount === 0 ? 0 : Math.min(currentPage * safePageSize, totalCount);
  const canGoPrev = currentPage > 1;
  const canGoNext = currentPage < totalPages;
  const outputStats = buildOutputKindStats(filteredLogs);
  const troubleSummary = buildAbilityLogTroubleSummary(filteredLogs);
  const troubleCount = troubleSummary
    .filter((item) => !['healthy', 'needs_evidence'].includes(item.key))
    .reduce((sum, item) => sum + item.count, 0);
  const primaryTrouble = troubleSummary.find((item) => item.count > 0 && item.key !== 'healthy') ?? troubleSummary.find((item) => item.key === 'healthy');

  const handleTroubleFilter = (key: string) => {
    if (key === 'execution_failed') {
      onStatusChange('failed');
      return;
    }
    if (key === 'callback_failed') {
      onOnlyCallbackFailedChange(true);
      return;
    }
    if (key === 'active') {
      const activeStatus = ['queued', 'pending', 'running', 'processing', 'in_progress', 'created'].find((item) => statuses.includes(item));
      if (activeStatus) onStatusChange(activeStatus);
      return;
    }
    if (key === 'healthy') {
      const successStatus = ['success', 'succeeded', 'completed', 'done', 'ok'].find((item) => statuses.includes(item));
      if (successStatus) onStatusChange(successStatus);
    }
  };

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <ActionBar>
        <Space align="center" style={{ justifyContent: 'space-between', width: '100%', flexWrap: 'wrap' }}>
          <div>
            <Typography.Text strong>能力调用清单</Typography.Text>
            <div>
              <Typography.Text theme="secondary">
                第 {currentPage} / {totalPages} 页 · 当前页 {logs.length} 条
                {typeof total === 'number' ? ` · 符合条件共 ${total} 条` : ''} · 筛选会查询全量历史
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

      <div className="podi-trouble-summary-card">
        <Space direction="vertical" size={10} style={{ width: '100%' }}>
          <Space align="center" style={{ justifyContent: 'space-between', width: '100%', flexWrap: 'wrap' }}>
            <div>
              <Typography.Text strong>能力调用排障总览</Typography.Text>
              <div>
                <Typography.Text theme="secondary">
                  当前页先按问题优先级聚类，线上回归时先处理红色，再看黄色；详情用于复制追踪编号和原始响应。
                </Typography.Text>
              </div>
            </div>
            <Space>
              <Tag theme={troubleCount > 0 ? 'warning' : 'success'} variant="light">
                待处理 {troubleCount} 条
              </Tag>
              {primaryTrouble ? (
                <Tag theme={primaryTrouble.theme} variant="light">
                  当前重点：{primaryTrouble.title}
                </Tag>
              ) : null}
            </Space>
          </Space>
          <div className="podi-trouble-summary-grid">
            {troubleSummary.map((item) => {
              const canFilter = ['execution_failed', 'callback_failed', 'active', 'healthy'].includes(item.key);
              return (
                <div key={item.key} className={`podi-trouble-summary-item podi-trouble-summary-item--${item.theme}`}>
                  <Space direction="vertical" size={6} style={{ width: '100%' }}>
                    <Space align="center" style={{ justifyContent: 'space-between', width: '100%', gap: 8 }}>
                      <Tag theme={item.theme} variant="light" size="small">
                        {item.title}
                      </Tag>
                      <Typography.Title level="h3" style={{ margin: 0 }}>
                        {item.count}
                      </Typography.Title>
                    </Space>
                    <Typography.Text theme="secondary">{item.detail}</Typography.Text>
                    <Typography.Text style={{ fontSize: 12 }}>{item.action}</Typography.Text>
                    {canFilter && item.count > 0 ? (
                      <Button size="small" variant="text" onClick={() => handleTroubleFilter(item.key)}>
                        {item.key === 'execution_failed'
                          ? '只看失败'
                          : item.key === 'callback_failed'
                            ? '只看回调异常'
                            : item.key === 'active'
                              ? '只看排队/执行'
                              : '只看已回填'}
                      </Button>
                    ) : null}
                  </Space>
                </div>
              );
            })}
          </div>
        </Space>
      </div>

      <div className="podi-output-summary-card">
        <Space direction="vertical" size={8} style={{ width: '100%' }}>
          <Space align="center" style={{ justifyContent: 'space-between', width: '100%', flexWrap: 'wrap' }}>
            <div>
              <Typography.Text strong>输出类型概览</Typography.Text>
              <div>
                <Typography.Text theme="secondary">
                  当前筛选结果按输出类型分布。图片、视频、文字/VL 分开看，避免把所有能力都当成生图处理。
                </Typography.Text>
              </div>
            </div>
            <Tag theme="default" variant="light">
              当前页 {filteredLogs.length} 条
            </Tag>
          </Space>
          <div className="podi-output-summary-grid">
            {(Object.keys(outputKindMeta) as LogOutputKind[]).map((kind) => {
              const meta = outputKindMeta[kind];
              return (
                <div key={kind} className="podi-output-summary-item">
                  <Space direction="vertical" size={2}>
                    <Tag theme={meta.theme} variant="light" size="small">
                      {meta.label}
                    </Tag>
                    <Typography.Title level="h3" style={{ margin: 0 }}>
                      {outputStats[kind]}
                    </Typography.Title>
                    <Typography.Text theme="secondary">{meta.detail}</Typography.Text>
                  </Space>
                </div>
              );
            })}
          </div>
        </Space>
      </div>

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
            colKey: 'action',
            title: '当前要做',
            width: 220,
            cell: ({ row }) => {
              const action = resolveAbilityLogAction(row);
              return (
                <Space direction="vertical" size={2}>
                  <Tag theme={action.theme} variant="light">
                    {action.title}
                  </Tag>
                  <Typography.Text theme="secondary" style={{ fontSize: 12 }}>
                    {action.detail}
                  </Typography.Text>
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
              const outputKind = resolveLogOutputKind(row);
              const outputMeta = outputKindMeta[outputKind];
              return (
                <Space size="small">
                  <Tag theme={outputMeta.theme} variant="light" size="small">
                    {outputMeta.label}
                  </Tag>
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
        <div className="flex items-center justify-between gap-3">
          <Typography.Text theme="secondary">
            {updatedAt ? `最近刷新：${formatDateTime(updatedAt)}` : '尚未刷新'} · 显示 {pageStart}-{pageEnd} / {totalCount}
          </Typography.Text>
          <Space>
            <Button variant="outline" disabled={currentPage === 1 || loading} onClick={() => onPageChange(1)}>
              第一页
            </Button>
            <Button variant="outline" disabled={!canGoPrev || loading} onClick={() => onPageChange(currentPage - 1)}>
              上一页
            </Button>
            <Typography.Text theme="secondary">
              第 {currentPage} / {totalPages} 页
            </Typography.Text>
            <Button variant="outline" disabled={!canGoNext || loading} onClick={() => onPageChange(currentPage + 1)}>
              下一页
            </Button>
            <Button variant="outline" disabled={currentPage === totalPages || loading} onClick={() => onPageChange(totalPages)}>
              最后一页
            </Button>
          </Space>
        </div>
      </div>
    </Space>
  );
}
