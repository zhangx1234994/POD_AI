import {
  Alert,
  Button,
  Card,
  Col,
  Input,
  InputNumber,
  Row,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  Textarea,
  Typography,
} from 'tdesign-react';
import { useState } from 'react';
import type {
  VendorEgressCheckResponse,
  VendorGovernanceSummaryResponse,
  VendorKey,
  VendorKeyFormState,
  VendorModel,
  VendorModelFormState,
  VendorProvider,
  VendorUsageSummaryItem,
} from '../../../types/admin';
import { toDisplayErrorMessage } from '../../../utils/errorMessageMap';
import { StatusBadge } from '../shared/ui';
import { apiKeyStatusOptions } from './formOptions';
import { formatDateTime, formatDurationMs } from './formatters';
import { getVendorIssueLabel, getVendorProviderState } from './vendor';

const hasJsonContent = (value: unknown): boolean => {
  if (!value) return false;
  if (typeof value === 'string') {
    const trimmed = value.trim();
    return trimmed.length > 0 && trimmed !== '{}';
  }
  if (Array.isArray(value)) return value.length > 0;
  if (typeof value === 'object') return Object.keys(value).length > 0;
  return false;
};

const formatJsonPanelValue = (value: unknown): string => {
  if (value === null || value === undefined || value === '') return '未配置';
  if (typeof value === 'string') return value;
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
};

const isVendorUsageFailed = (item: VendorUsageSummaryItem): boolean => {
  const status = String(item.status || '').toLowerCase();
  return Boolean(item.errorCode) || !['success', 'succeeded', 'ok', 'completed'].includes(status);
};

const apiTypeLabels: Record<string, string> = {
  chat: '文字/多模态对话',
  chat_completions: '文字/多模态对话',
  image: '图片',
  image_edit: '图片编辑',
  image_edits: '图片编辑',
  image_generation: '文生图',
  image_process: '图片处理',
  text_to_image: '文生图',
  image_to_image: '图生图',
  image_to_video: '图生视频',
  market_image_to_image: '图生图',
  market_text_to_video: '文生视频',
  multimodal: '多模态',
  responses: '多模态生成/编辑',
  text: '文本',
  text_generation: '文本生成',
  text_to_video: '文生视频',
  video: '视频',
  video_generation: '视频生成',
  vision: '图像理解',
  vision_language: '图像理解',
  vl: '图像理解',
};

const executionModeLabels: Record<string, string> = {
  callback: '厂商回调',
  async: '后台异步',
  async_submit_poll: '提交后轮询',
  polling: '持续查询',
  sync: '立即返回',
  sync_then_store: '同步后入库',
};

const getReadableTokenLabel = (value?: string | null, labels: Record<string, string> = {}) => {
  const raw = String(value || '').trim();
  if (!raw) return '未配置';
  return labels[raw] || raw.replace(/_/g, ' ');
};

const getEgressModeLabel = (requiresGlobalEgress?: boolean) => (requiresGlobalEgress ? '需要出网节点' : '国内直连');

const getVendorSourceLabel = (source?: string | null) => {
  const value = String(source || '').trim();
  if (!value) return '手动维护';
  if (value === 'backend-admin') return '管理端维护';
  if (value === 'volcengine-sync') return '火山同步';
  if (value === 'seed') return '系统预置';
  return value.replace(/_/g, ' ');
};

const resolveVendorFailureSuggestion = (item: VendorUsageSummaryItem): string => {
  const code = String(item.errorCode || item.status || '').toUpperCase();
  if (code.includes('KEY') || code.includes('AUTH') || code.includes('401') || code.includes('403')) {
    return '先检查密钥是否启用、是否过期，再做带密钥出网检查。';
  }
  if (code.includes('RATE') || code.includes('429') || code.includes('CONCURRENCY') || code.includes('QUOTA')) {
    return '先降并发或切备用密钥，确认额度恢复后再放量。';
  }
  if (code.includes('TIMEOUT') || code.includes('EGRESS') || code.includes('NETWORK') || code.includes('CONNECT')) {
    return '先检查出网节点和代理，不要直接切业务默认版本。';
  }
  if (code.includes('MODEL') || code.includes('NOT_SUPPORTED') || code.includes('INVALID')) {
    return '先核对模型目录和能力字段，确认参数没有漂移。';
  }
  return '先展开调用日志确认上游返回，再决定是否切换模型或回滚业务版本。';
};

const resolveVendorKeyRisk = (item: VendorKey): { theme: 'success' | 'warning' | 'danger' | 'default'; label: string; suggestion: string } => {
  if (item.status !== 'active') {
    return { theme: 'danger', label: '已停用', suggestion: '如仍被业务使用，需要启用或替换为新密钥。' };
  }
  if (item.cooldownUntil) {
    return { theme: 'warning', label: '冷却中', suggestion: `等待到 ${formatDateTime(item.cooldownUntil)}，或切备用密钥。` };
  }
  if (item.lastError) {
    return { theme: 'warning', label: '最近报错', suggestion: toDisplayErrorMessage(item.lastError) };
  }
  if (item.dailyQuota && item.usageCount >= item.dailyQuota) {
    return { theme: 'danger', label: '日配额用完', suggestion: '补充额度、切备用密钥，或降低该模型流量。' };
  }
  if (item.dailyQuota && item.usageCount >= item.dailyQuota * 0.8) {
    return { theme: 'warning', label: '接近日配额', suggestion: '建议准备备用密钥，避免业务高峰时失败。' };
  }
  return { theme: 'success', label: '可用', suggestion: '暂无明显风险。' };
};

const vendorAcceptanceTargets = [
  { provider: 'openai', aliases: ['openai', 'openai_compatible'], label: 'OpenAI / 中转站' },
  { provider: 'kie', aliases: ['kie'], label: 'KIE' },
  { provider: 'volcengine', aliases: ['volcengine'], label: '火山' },
  { provider: 'baidu', aliases: ['baidu'], label: '百度' },
];

const buildVendorAcceptanceItem = (
  target: (typeof vendorAcceptanceTargets)[number],
  providers: VendorProvider[],
  models: VendorModel[],
  keys: VendorKey[],
  usageItems: VendorUsageSummaryItem[],
) => {
  const aliases = new Set(target.aliases);
  const providerRows = providers.filter((item) => aliases.has(item.provider));
  const modelRows = models.filter((item) => aliases.has(item.provider));
  const keyRows = keys.filter((item) => aliases.has(item.provider));
  const activeKeys = keyRows.filter((item) => item.status === 'active');
  const usageRows = usageItems.filter((item) => aliases.has(item.provider));
  const failedCount = usageRows.filter(isVendorUsageFailed).reduce((total, item) => total + Number(item.count || 0), 0);
  const totalCount = usageRows.reduce((total, item) => total + Number(item.count || 0), 0);
  if (!providerRows.length) {
    return { ...target, status: 'missing_provider', theme: 'danger' as const, labelText: '未接入', suggestion: '先确认能力服务已返回该厂商。', modelCount: 0, activeKeyCount: 0, totalCount, failedCount };
  }
  if (!activeKeys.length) {
    return { ...target, status: 'missing_key', theme: 'warning' as const, labelText: '缺密钥', suggestion: '先配置可用密钥，再做带密钥出网检查。', modelCount: modelRows.length, activeKeyCount: 0, totalCount, failedCount };
  }
  if (!modelRows.length) {
    return { ...target, status: 'missing_model', theme: 'warning' as const, labelText: '缺模型', suggestion: '补模型目录和能力范围，否则业务无法稳定引用。', modelCount: 0, activeKeyCount: activeKeys.length, totalCount, failedCount };
  }
  if (failedCount > 0) {
    return { ...target, status: 'needs_retest', theme: 'warning' as const, labelText: '需复测', suggestion: '先处理失败样本，再做一次小流量测试。', modelCount: modelRows.length, activeKeyCount: activeKeys.length, totalCount, failedCount };
  }
  if (totalCount > 0) {
    return { ...target, status: 'passed', theme: 'success' as const, labelText: '已跑通', suggestion: '可继续接入业务能力，但发布前仍需测评端抽测。', modelCount: modelRows.length, activeKeyCount: activeKeys.length, totalCount, failedCount };
  }
  return { ...target, status: 'not_tested', theme: 'default' as const, labelText: '待测试', suggestion: '先在能力测试跑一次真实调用，确认回填和计费。', modelCount: modelRows.length, activeKeyCount: activeKeys.length, totalCount, failedCount };
};

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

const safeNumber = (value: unknown): number => Number(value || 0);

type VendorModelsPanelProps = {
  baseUrl: string;
  providers: VendorProvider[];
  models: VendorModel[];
  keys: VendorKey[];
  usageItems: VendorUsageSummaryItem[];
  governanceSummary?: VendorGovernanceSummaryResponse | null;
  usageTotal: number;
  usageFailed: number;
  usageSuccessRate: number | null;
  usageWindowHours: number;
  governanceIssueCount: number;
  loading: boolean;
  error?: string;
  notice?: string;
  egressChecks: Record<string, VendorEgressCheckResponse>;
  modelForm: VendorModelFormState;
  modelFormError?: string | null;
  keyForm: VendorKeyFormState;
  onRefresh: () => void;
  onSyncVolcengine: () => void;
  onEgressCheck: (provider: string, includeAuth?: boolean) => void;
  onModelFormChange: (next: VendorModelFormState) => void;
  onModelEdit: (model: VendorModel) => void;
  onModelReset: () => void;
  onModelSubmit: () => void;
  onKeyFormChange: (next: VendorKeyFormState) => void;
  onKeySubmit: () => void;
  onKeyReset: () => void;
};

export function VendorModelsPanel({
  baseUrl,
  providers,
  models,
  keys,
  usageItems,
  governanceSummary,
  usageTotal,
  usageFailed,
  usageSuccessRate,
  usageWindowHours,
  governanceIssueCount,
  loading,
  error,
  notice,
  egressChecks,
  modelForm,
  modelFormError,
  keyForm,
  onRefresh,
  onSyncVolcengine,
  onEgressCheck,
  onModelFormChange,
  onModelEdit,
  onModelReset,
  onModelSubmit,
  onKeyFormChange,
  onKeySubmit,
  onKeyReset,
}: VendorModelsPanelProps) {
  const [selectedModelDetail, setSelectedModelDetail] = useState<VendorModel | null>(null);
  const activeKeyCount = keys.filter((item) => item.status === 'active').length;
  const egressProviderCount = providers.filter((item) => item.requiresGlobalEgress).length;
  const failedUsageItems = usageItems.filter(isVendorUsageFailed).slice(0, 8);
  const riskyKeys = keys
    .map((item) => ({ key: item, risk: resolveVendorKeyRisk(item) }))
    .filter((item) => item.risk.theme !== 'success')
    .slice(0, 8);
  const acceptanceItems = vendorAcceptanceTargets.map((target) =>
    buildVendorAcceptanceItem(target, providers, models, keys, usageItems),
  );

  return (
    <>
      <div className="podi-action-bar">
        <Space align="center" style={{ justifyContent: 'space-between', width: '100%', flexWrap: 'wrap' }}>
          <Space direction="vertical" size={4}>
            <Typography.Text strong>模型弹药库</Typography.Text>
            <Typography.Text theme="secondary">
              统一管理火山、OpenAI、中转站、KIE 等商业模型。先看密钥和出网，再看模型目录，最后绑定业务能力。
            </Typography.Text>
          </Space>
          <Space size="small" style={{ flexWrap: 'wrap' }}>
            <Tag variant="light">厂商 {providers.length}</Tag>
            <Tag variant="light">模型 {models.length}</Tag>
            <Tag variant="light">密钥 {keys.length}</Tag>
            <Button size="small" variant="outline" loading={loading} onClick={onSyncVolcengine}>
              同步火山模型
            </Button>
            <Button size="small" loading={loading} onClick={onRefresh}>
              刷新弹药库
            </Button>
          </Space>
        </Space>
      </div>
      {error ? <Alert theme="warning" message={error} /> : null}
      {notice ? <Alert theme="success" message={notice} /> : null}

      <Row gutter={[16, 16]}>
        <Col xs={12} lg={4}>
          <MetricCard label="可用厂商" value={providers.length} sub="OpenAI / 火山 / KIE 等" />
        </Col>
        <Col xs={12} lg={4}>
          <MetricCard label="可用密钥" value={activeKeyCount} sub="能力服务托管" />
        </Col>
        <Col xs={12} lg={4}>
          <MetricCard label="特殊出网" value={egressProviderCount} sub="需要代理或海外通道" />
        </Col>
        <Col xs={12} lg={4}>
          <MetricCard label="近24小时调用" value={usageTotal} sub={`窗口 ${usageWindowHours} 小时`} />
        </Col>
        <Col xs={12} lg={4}>
          <MetricCard
            label="近24小时成功率"
            value={usageSuccessRate === null ? '—' : `${usageSuccessRate}%`}
            sub={usageFailed > 0 ? `失败 ${usageFailed}` : '暂无失败记录'}
          />
        </Col>
      </Row>

      <Card bordered title="这个页面怎么用" style={{ marginTop: 12 }}>
        <Row gutter={[12, 12]}>
          {[
            ['1', '先看风险', '密钥、出网、失败样本有问题时，先处理这里，不急着接业务。'],
            ['2', '再看模型', '确认模型目录、能力范围、输出类型和计价口径是否完整。'],
            ['3', '再绑能力', '模型稳定后再绑定到原子能力或业务版本，避免业务默认版本踩坑。'],
            ['4', '最后小流量', '用能力测试和测评端跑通，再逐步放量。'],
          ].map(([index, title, body]) => (
            <Col key={index} xs={12} md={3}>
              <div
                style={{
                  border: '1px solid var(--td-border-level-1-color)',
                  borderRadius: 12,
                  padding: 12,
                  height: '100%',
                }}
              >
                <Space direction="vertical" size={4}>
                  <Tag theme="primary" variant="light">
                    {index}
                  </Tag>
                  <Typography.Text strong>{title}</Typography.Text>
                  <Typography.Text theme="secondary">{body}</Typography.Text>
                </Space>
              </div>
            </Col>
          ))}
        </Row>
      </Card>

      <Card bordered style={{ marginTop: 12 }}>
        <Space direction="vertical" size="small" style={{ width: '100%' }}>
          <Typography.Text strong>下一步建议</Typography.Text>
          <Row gutter={[12, 12]}>
            <Col xs={12} md={4}>
              <Alert
                theme={activeKeyCount > 0 ? 'success' : 'warning'}
                message={
                  activeKeyCount > 0
                    ? '密钥已配置：可以继续查看模型是否绑定到业务能力。'
                    : '先配置第三方密钥，否则模型能力无法真实调用。'
                }
              />
            </Col>
            <Col xs={12} md={4}>
              <Alert
                theme={governanceIssueCount > 0 ? 'warning' : 'success'}
                message={
                  governanceIssueCount > 0
                    ? `有 ${governanceIssueCount} 个厂商或模型需要处理，优先看下方“问题”列。`
                    : '厂商状态正常，可以继续接入或测试新模型。'
                }
              />
            </Col>
            <Col xs={12} md={4}>
              <Alert
                theme={usageFailed > 0 ? 'warning' : 'info'}
                message={
                  usageFailed > 0
                    ? `近 ${usageWindowHours} 小时有 ${usageFailed} 次失败，先看失败原因再切业务默认版本。`
                    : '最近没有第三方调用失败，可按业务需要做小流量测试。'
                }
              />
            </Col>
          </Row>
        </Space>
      </Card>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={12} lg={7}>
          <Card bordered title="最近失败样本">
            <Typography.Text theme="secondary">
              只展示最近窗口内的失败聚合，用来判断先处理密钥、出网、配额还是模型参数。
            </Typography.Text>
            <div style={{ marginTop: 12 }}>
              <Table
                size="small"
                rowKey="rowKey"
                data={failedUsageItems.map((item, index) => ({
                  ...item,
                  rowKey: `${item.provider}-${item.model || 'all'}-${item.status}-${item.errorCode || 'failed'}-${index}`,
                }))}
                columns={[
                  {
                    colKey: 'provider',
                    title: '厂商 / 模型',
                    minWidth: 180,
                    cell: ({ row }) => (
                      <Space direction="vertical" size={2}>
                        <Typography.Text strong>{row.provider}</Typography.Text>
                        <Typography.Text theme="secondary" style={{ fontSize: 12 }}>
                          {row.model || '通用'}
                        </Typography.Text>
                      </Space>
                    ),
                  },
                  {
                    colKey: 'error',
                    title: '失败原因',
                    minWidth: 220,
                    cell: ({ row }) => (
                      <Space direction="vertical" size={2}>
                        <Typography.Text theme="error">
                          {row.errorCode ? toDisplayErrorMessage(row.errorCode) : row.status}
                        </Typography.Text>
                        <Typography.Text theme="secondary" style={{ fontSize: 12 }}>
                          {row.count} 次{row.lastSeenAt ? ` · 最近 ${formatDateTime(row.lastSeenAt)}` : ''}
                        </Typography.Text>
                      </Space>
                    ),
                  },
                  {
                    colKey: 'suggestion',
                    title: '建议动作',
                    minWidth: 260,
                    cell: ({ row }) => (
                      <Typography.Text theme="secondary">{resolveVendorFailureSuggestion(row)}</Typography.Text>
                    ),
                  },
                ]}
                empty={<Typography.Text theme="secondary">最近没有失败样本。</Typography.Text>}
              />
            </div>
          </Card>
        </Col>
        <Col xs={12} lg={5}>
          <Card bordered title="密钥处理提示">
            <Typography.Text theme="secondary">
              只列出停用、冷却、报错或接近配额的密钥，避免上线前漏掉隐患。
            </Typography.Text>
            <Space direction="vertical" size="small" style={{ width: '100%', marginTop: 12 }}>
              {riskyKeys.length ? (
                riskyKeys.map(({ key, risk }) => (
                  <div
                    key={key.id}
                    style={{
                      border: '1px solid var(--td-border-level-1-color)',
                      borderRadius: 12,
                      padding: 12,
                    }}
                  >
                    <Space direction="vertical" size={4} style={{ width: '100%' }}>
                      <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
                        <Typography.Text strong>{key.alias}</Typography.Text>
                        <Tag theme={risk.theme} variant="light">
                          {risk.label}
                        </Tag>
                      </Space>
                      <Typography.Text theme="secondary" style={{ fontSize: 12 }}>
                        {key.provider}{key.model ? ` / ${key.model}` : ''} · {key.keyPreview}
                      </Typography.Text>
                      <Typography.Text theme="secondary">{risk.suggestion}</Typography.Text>
                    </Space>
                  </div>
                ))
              ) : (
                <Alert theme="success" message="当前密钥池没有明显风险。" />
              )}
            </Space>
          </Card>
        </Col>
      </Row>

      <Card bordered title="第三方能力验收标记" style={{ marginTop: 16 }}>
        <Typography.Text theme="secondary">
          这里先做自动判断：厂商是否接入、密钥是否可用、模型目录是否存在、最近是否跑通过。后续再补人工确认记录。
        </Typography.Text>
        <div style={{ marginTop: 12 }}>
          <Table
            size="small"
            rowKey="provider"
            data={acceptanceItems}
            columns={[
              {
                colKey: 'provider',
                title: '厂商',
                minWidth: 180,
                cell: ({ row }) => (
                  <Space direction="vertical" size={2}>
                    <Typography.Text strong>{row.label}</Typography.Text>
                    <Typography.Text theme="secondary" style={{ fontSize: 12 }}>
                      {row.aliases.join(' / ')}
                    </Typography.Text>
                  </Space>
                ),
              },
              {
                colKey: 'status',
                title: '验收状态',
                width: 130,
                cell: ({ row }) => (
                  <Tag theme={row.theme} variant="light">
                    {row.labelText}
                  </Tag>
                ),
              },
              {
                colKey: 'resources',
                title: '资源',
                width: 180,
                cell: ({ row }) => `模型 ${row.modelCount} / 可用密钥 ${row.activeKeyCount}`,
              },
              {
                colKey: 'calls',
                title: '最近调用',
                width: 170,
                cell: ({ row }) => `调用 ${row.totalCount} / 失败 ${row.failedCount}`,
              },
              {
                colKey: 'suggestion',
                title: '下一步',
                minWidth: 260,
                cell: ({ row }) => <Typography.Text theme="secondary">{row.suggestion}</Typography.Text>,
              },
            ]}
          />
        </div>
      </Card>

      <Card bordered title="厂商健康与风险" style={{ marginTop: 16 }}>
        <Space size="small" style={{ marginBottom: 12, flexWrap: 'wrap' }}>
          <Tag theme={governanceIssueCount > 0 ? 'warning' : 'success'} variant="light">
            {governanceIssueCount > 0 ? `需处理 ${governanceIssueCount}` : '状态正常'}
          </Tag>
          <Tag variant="light">窗口 {governanceSummary?.windowHours || usageWindowHours} 小时</Tag>
        </Space>
        {governanceSummary ? (
          <Space direction="vertical" style={{ width: '100%' }} size={12}>
            {governanceSummary.issues?.length ? (
              <Alert
                theme="warning"
                message={`治理摘要部分降级：${governanceSummary.issues.map(getVendorIssueLabel).join('；')}`}
              />
            ) : null}
            <Row gutter={[12, 12]}>
              <Col xs={12} lg={3}>
                <MetricCard label="厂商" value={safeNumber(governanceSummary.totals.providerCount)} sub="已纳入治理" />
              </Col>
              <Col xs={12} lg={3}>
                <MetricCard
                  label="模型"
                  value={safeNumber(governanceSummary.totals.modelCount)}
                  sub={`可用 ${safeNumber(governanceSummary.totals.activeModelCount)}`}
                />
              </Col>
              <Col xs={12} lg={3}>
                <MetricCard
                  label="能力"
                  value={safeNumber(governanceSummary.totals.abilityCount)}
                  sub={`可用 ${safeNumber(governanceSummary.totals.activeAbilityCount)}`}
                />
              </Col>
              <Col xs={12} lg={3}>
                <MetricCard
                  label="密钥池"
                  value={safeNumber(governanceSummary.totals.activeStoredKeyCount)}
                  sub={`环境密钥 ${safeNumber(governanceSummary.totals.envKeyProviderCount)}`}
                />
              </Col>
              <Col xs={12} lg={3}>
                <MetricCard
                  label="最近调用"
                  value={usageTotal}
                  sub={usageFailed > 0 ? `失败 ${usageFailed}` : '暂无失败'}
                />
              </Col>
              <Col xs={12} lg={3}>
                <MetricCard
                  label="待处理问题"
                  value={safeNumber(governanceSummary.totals.issueCount)}
                  sub="密钥 / 目录 / 调用"
                />
              </Col>
            </Row>
            <Table
              size="small"
              rowKey="provider"
              data={governanceSummary.providers}
              columns={[
                {
                  colKey: 'provider',
                  title: '厂商',
                  minWidth: 180,
                  cell: ({ row }) => (
                    <Space direction="vertical" size={2}>
                      <Space size={6}>
                        <Typography.Text strong>{row.displayName}</Typography.Text>
                        <Tag theme={getVendorProviderState(row).theme} variant="light">
                          {getVendorProviderState(row).label}
                        </Tag>
                      </Space>
                      <Typography.Text theme="secondary" style={{ fontSize: 12 }}>
                        排障代码：{row.provider}
                      </Typography.Text>
                    </Space>
                  ),
                },
                {
                  colKey: 'runtime',
                  title: '运行配置',
                  minWidth: 220,
                  cell: ({ row }) => (
                    <Space size={4} style={{ flexWrap: 'wrap' }}>
                      <Tag theme={row.envKeyConfigured ? 'success' : 'default'} variant="light">
                        环境密钥 {row.envKeyConfigured ? '已配' : '未配'}
                      </Tag>
                      <Tag theme={row.activeStoredKeyCount > 0 ? 'success' : 'default'} variant="light">
                        密钥池 {safeNumber(row.activeStoredKeyCount)}
                      </Tag>
                      {row.disabledKeyCount > 0 ? (
                        <Tag theme="warning" variant="light">
                          停用 {row.disabledKeyCount}
                        </Tag>
                      ) : null}
                      {row.cooldownKeyCount > 0 ? (
                        <Tag theme="warning" variant="light">
                          冷却中 {row.cooldownKeyCount}
                        </Tag>
                      ) : null}
                      {row.exhaustedKeyCount > 0 ? (
                        <Tag theme="danger" variant="light">
                          配额用完 {row.exhaustedKeyCount}
                        </Tag>
                      ) : null}
                      {row.errorKeyCount > 0 ? (
                        <Tag theme="warning" variant="light">
                          密钥报错 {row.errorKeyCount}
                        </Tag>
                      ) : null}
                    </Space>
                  ),
                },
                {
                  colKey: 'catalog',
                  title: '目录绑定',
                  width: 160,
                  cell: ({ row }) =>
                    `模型 ${safeNumber(row.activeModelCount)}/${safeNumber(row.modelCount)} · 能力 ${safeNumber(row.activeAbilityCount)}/${safeNumber(row.abilityCount)}`,
                },
                {
                  colKey: 'recent',
                  title: '最近调用',
                  minWidth: 220,
                  cell: ({ row }) => (
                    <Space direction="vertical" size={2}>
                      <Typography.Text>
                        成功 {safeNumber(row.succeededCalls)}，失败 {safeNumber(row.failedCalls)}
                      </Typography.Text>
                      <Typography.Text theme="secondary" style={{ fontSize: 12 }}>
                        耗时 {row.avgLatencyMs ? formatDurationMs(row.avgLatencyMs) : '—'}
                        {row.lastSeenAt ? ` · 最近 ${formatDateTime(row.lastSeenAt)}` : ''}
                      </Typography.Text>
                    </Space>
                  ),
                },
                {
                  colKey: 'suggestions',
                  title: '建议',
                  minWidth: 220,
                  cell: ({ row }) => (
                    <Space direction="vertical" size={2}>
                      {(row.suggestions || []).slice(0, 2).map((suggestion) => (
                        <Typography.Text key={`${row.provider}-${suggestion}`} theme="secondary">
                          {suggestion}
                        </Typography.Text>
                      ))}
                      {(row.suggestions || []).length === 0 ? <Typography.Text theme="success">暂无特殊处理</Typography.Text> : null}
                    </Space>
                  ),
                },
                {
                  colKey: 'issues',
                  title: '问题',
                  minWidth: 220,
                  cell: ({ row }) =>
                    row.issues?.length ? (
                      <Space direction="vertical" size={4}>
                        <Space size={4} style={{ flexWrap: 'wrap' }}>
                          {row.issues.map((issue) => (
                            <Tag key={`${row.provider}-${issue}`} theme="warning" variant="light">
                              {getVendorIssueLabel(issue)}
                            </Tag>
                          ))}
                        </Space>
                      </Space>
                    ) : (
                      <Typography.Text theme="success">暂无</Typography.Text>
                    ),
                },
              ]}
            />
          </Space>
        ) : (
          <Alert theme="info" message="暂未加载治理摘要，点击“刷新弹药库”后会显示各厂商可调用状态。" />
        )}
      </Card>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={12} lg={6}>
          <Card bordered title="厂商通道与能力范围">
            <Table
              size="small"
              rowKey="provider"
              data={providers}
              columns={[
                {
                  colKey: 'provider',
                  title: '厂商',
                  minWidth: 160,
                  cell: ({ row }) => (
                    <Space direction="vertical" size={2}>
                      <Typography.Text strong>{row.displayName}</Typography.Text>
                      <Typography.Text theme="secondary" style={{ fontSize: 12 }}>
                        排障代码：{row.provider}
                      </Typography.Text>
                    </Space>
                  ),
                },
                {
                  colKey: 'apiTypes',
                  title: '能力类型',
                  minWidth: 220,
                  cell: ({ row }) => (
                    <Space size={4} style={{ flexWrap: 'wrap' }}>
                      {(row.supportedApiTypes || []).map((item) => (
                        <Tag key={`${row.provider}-${item}`} variant="light">
                          {getReadableTokenLabel(item, apiTypeLabels)}
                        </Tag>
                      ))}
                    </Space>
                  ),
                },
                {
                  colKey: 'egress',
                  title: '出网',
                  width: 160,
                  cell: ({ row }) => {
                    const check = egressChecks[row.provider];
                    return (
                      <Space direction="vertical" size={2}>
                        <Tag theme={row.requiresGlobalEgress ? 'warning' : 'success'} variant="light">
                          {getEgressModeLabel(row.requiresGlobalEgress)}
                        </Tag>
                        {check ? (
                          <Typography.Text theme={check.success ? 'success' : 'error'} style={{ fontSize: 12 }}>
                            {check.success ? '可访问' : toDisplayErrorMessage(check.errorCode || '不可访问')} · {check.latencyMs ?? '—'}ms
                          </Typography.Text>
                        ) : null}
                      </Space>
                    );
                  },
                },
                {
                  colKey: 'actions',
                  title: '操作',
                  width: 180,
                  cell: ({ row }) => (
                    <Space size={4}>
                      <Button size="small" variant="text" onClick={() => onEgressCheck(row.provider, false)}>
                        连通性检查
                      </Button>
                      <Button size="small" variant="text" onClick={() => onEgressCheck(row.provider, true)}>
                        带密钥检查
                      </Button>
                    </Space>
                  ),
                },
              ]}
              empty={<Typography.Text theme="secondary">暂无厂商，请检查第三方能力服务。</Typography.Text>}
            />
          </Card>
        </Col>

        <Col xs={12} lg={6}>
          <Card bordered title="模型目录">
            <Table
              size="small"
              rowKey="model"
              data={models}
              columns={[
                {
                  colKey: 'model',
                  title: '模型',
                  minWidth: 220,
                  cell: ({ row }) => (
                    <Space direction="vertical" size={2}>
                      <Typography.Text strong>{row.displayName}</Typography.Text>
                      <Typography.Text theme="secondary" style={{ fontSize: 12 }}>
                        {row.provider} / {row.model}
                      </Typography.Text>
                    </Space>
                  ),
                },
                {
                  colKey: 'features',
                  title: '能力范围',
                  minWidth: 240,
                  cell: ({ row }) => (
                    <Space size={4} style={{ flexWrap: 'wrap' }}>
                      {row.apiTypes.map((item) => (
                        <Tag key={`${row.provider}-${row.model}-${item}`} variant="light">
                          {getReadableTokenLabel(item, apiTypeLabels)}
                        </Tag>
                      ))}
                      {row.supportsMask ? (
                        <Tag theme="success" variant="light">
                          蒙版
                        </Tag>
                      ) : null}
                      {row.supportsMultipleImages ? (
                        <Tag theme="success" variant="light">
                          多图
                        </Tag>
                      ) : null}
                      {row.supportsVideo ? (
                        <Tag theme="warning" variant="light">
                          视频
                        </Tag>
                      ) : null}
                    </Space>
                  ),
                },
                {
                  colKey: 'source',
                  title: '来源',
                  width: 120,
                  cell: ({ row }) => <Tag variant="light">{getVendorSourceLabel(row.source)}</Tag>,
                },
                {
                  colKey: 'costPolicy',
                  title: '计价',
                  width: 120,
                  cell: ({ row }) => (
                    <Tag theme={hasJsonContent(row.costPolicy) ? 'success' : 'warning'} variant="light">
                      {hasJsonContent(row.costPolicy) ? '已配置' : '缺少计价'}
                    </Tag>
                  ),
                },
                {
                  colKey: 'actions',
                  title: '操作',
                  width: 140,
                  cell: ({ row }) => (
                    <Space size={4}>
                      <Button size="small" variant="text" onClick={() => setSelectedModelDetail(row)}>
                        详情
                      </Button>
                      <Button size="small" variant="text" onClick={() => onModelEdit(row)}>
                        编辑
                      </Button>
                    </Space>
                  ),
                },
              ]}
              empty={<Typography.Text theme="secondary">暂无模型目录。</Typography.Text>}
            />
            {selectedModelDetail ? (
              <div
                style={{
                  border: '1px solid var(--td-border-level-1-color)',
                  borderRadius: 12,
                  marginTop: 16,
                  padding: 14,
                  background: 'var(--td-bg-color-container)',
                }}
              >
                <Space direction="vertical" size="small" style={{ width: '100%' }}>
                  <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
                    <Space direction="vertical" size={2}>
                      <Typography.Text strong>
                        {selectedModelDetail.displayName || selectedModelDetail.model}
                      </Typography.Text>
                      <Typography.Text theme="secondary" style={{ fontSize: 12 }}>
                        {selectedModelDetail.provider} / {selectedModelDetail.model}
                      </Typography.Text>
                    </Space>
                    <Space size={6}>
                      <Tag theme={selectedModelDetail.status === 'active' ? 'success' : 'default'} variant="light">
                        {selectedModelDetail.status}
                      </Tag>
                      <Button size="small" variant="text" onClick={() => setSelectedModelDetail(null)}>
                        收起
                      </Button>
                    </Space>
                  </Space>
                  <Space size={4} style={{ flexWrap: 'wrap' }}>
                    {(selectedModelDetail.apiTypes || []).map((item) => (
                      <Tag key={`detail-api-${item}`} variant="light">
                        {getReadableTokenLabel(item, apiTypeLabels)}
                      </Tag>
                    ))}
                    {(selectedModelDetail.executionModes || []).map((item) => (
                      <Tag key={`detail-mode-${item}`} theme="primary" variant="light">
                        {getReadableTokenLabel(item, executionModeLabels)}
                      </Tag>
                    ))}
                    {selectedModelDetail.supportsMask ? <Tag theme="success" variant="light">支持蒙版</Tag> : null}
                    {selectedModelDetail.supportsMultipleImages ? <Tag theme="success" variant="light">支持多图</Tag> : null}
                    {selectedModelDetail.supportsVideo ? <Tag theme="warning" variant="light">支持视频</Tag> : null}
                    {selectedModelDetail.requiresGlobalEgress ? <Tag theme="warning" variant="light">需要出网节点</Tag> : null}
                  </Space>
                  <Row gutter={[12, 12]}>
                    {[
                      ['路由策略', selectedModelDetail.routePolicy],
                      ['默认任务策略', selectedModelDetail.defaultTaskPolicy],
                      ['入参结构', selectedModelDetail.inputSchema],
                      ['计价策略', selectedModelDetail.costPolicy],
                      ['元信息', selectedModelDetail.metadata],
                    ].map(([label, value]) => (
                      <Col key={String(label)} xs={12} lg={6}>
                        <Typography.Text theme="secondary">{String(label)}</Typography.Text>
                        <pre
                          style={{
                            marginTop: 6,
                            maxHeight: 180,
                            overflow: 'auto',
                            border: '1px solid var(--td-border-level-1-color)',
                            borderRadius: 8,
                            padding: 10,
                            fontSize: 12,
                            lineHeight: 1.5,
                            background: 'var(--td-bg-color-secondarycontainer)',
                          }}
                        >
                          {formatJsonPanelValue(value)}
                        </pre>
                      </Col>
                    ))}
                  </Row>
                </Space>
              </div>
            ) : null}
            <div style={{ borderTop: '1px solid var(--td-border-level-1-color)', marginTop: 16, paddingTop: 16 }}>
              <Space direction="vertical" size="small" style={{ width: '100%' }}>
                <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
                  <Typography.Text strong>{modelForm.id ? '编辑模型配置' : '新增模型配置'}</Typography.Text>
                  {modelForm.id ? (
                    <Button size="small" variant="outline" onClick={onModelReset}>
                      新增模式
                    </Button>
                  ) : null}
                </Space>
                {modelFormError ? <Alert theme="error" message={modelFormError} /> : null}
                <Row gutter={[12, 12]}>
                  <Col span={4}>
                    <Typography.Text theme="secondary">厂商代码（排障用）</Typography.Text>
                    <Input
                      value={String(modelForm.provider || '')}
                      onChange={(v) => onModelFormChange({ ...modelForm, provider: String(v) })}
                      placeholder="openai"
                    />
                  </Col>
                  <Col span={4}>
                    <Typography.Text theme="secondary">模型编号</Typography.Text>
                    <Input
                      value={String(modelForm.model || '')}
                      onChange={(v) => onModelFormChange({ ...modelForm, model: String(v) })}
                      placeholder="gpt-image-2"
                    />
                  </Col>
                  <Col span={4}>
                    <Typography.Text theme="secondary">状态</Typography.Text>
                    <Select
                      value={modelForm.status || 'active'}
                      onChange={(v) => onModelFormChange({ ...modelForm, status: String(v) })}
                      options={apiKeyStatusOptions.map((item) => ({ ...item }))}
                    />
                  </Col>
                </Row>
                <div>
                  <Typography.Text theme="secondary">显示名称</Typography.Text>
                  <Input
                    value={String(modelForm.displayName || '')}
                    onChange={(v) => onModelFormChange({ ...modelForm, displayName: String(v) })}
                    placeholder="OpenAI · GPT Image 2"
                  />
                </div>
                <Row gutter={[12, 12]}>
                  <Col span={6}>
                    <Typography.Text theme="secondary">能力类型（逗号分隔）</Typography.Text>
                    <Input
                      value={modelForm.apiTypesText || ''}
                      onChange={(v) => onModelFormChange({ ...modelForm, apiTypesText: String(v) })}
                      placeholder="image_generation, image_edit"
                    />
                  </Col>
                  <Col span={6}>
                    <Typography.Text theme="secondary">返回方式（逗号分隔）</Typography.Text>
                    <Input
                      value={modelForm.executionModesText || ''}
                      onChange={(v) => onModelFormChange({ ...modelForm, executionModesText: String(v) })}
                      placeholder="sync, async_submit_poll"
                    />
                  </Col>
                </Row>
                <Space size="large" style={{ flexWrap: 'wrap' }}>
                  <Space size={4}>
                    <Switch
                      value={Boolean(modelForm.supportsMask)}
                      onChange={(v) => onModelFormChange({ ...modelForm, supportsMask: Boolean(v) })}
                    />
                    <Typography.Text theme="secondary">蒙版</Typography.Text>
                  </Space>
                  <Space size={4}>
                    <Switch
                      value={Boolean(modelForm.supportsMultipleImages)}
                      onChange={(v) => onModelFormChange({ ...modelForm, supportsMultipleImages: Boolean(v) })}
                    />
                    <Typography.Text theme="secondary">多图</Typography.Text>
                  </Space>
                  <Space size={4}>
                    <Switch
                      value={Boolean(modelForm.supportsVideo)}
                      onChange={(v) => onModelFormChange({ ...modelForm, supportsVideo: Boolean(v) })}
                    />
                    <Typography.Text theme="secondary">视频</Typography.Text>
                  </Space>
                  <Space size={4}>
                    <Switch
                      value={Boolean(modelForm.supportsText)}
                      onChange={(v) => onModelFormChange({ ...modelForm, supportsText: Boolean(v) })}
                    />
                    <Typography.Text theme="secondary">文本</Typography.Text>
                  </Space>
                  <Space size={4}>
                    <Switch
                      value={Boolean(modelForm.requiresGlobalEgress)}
                      onChange={(v) => onModelFormChange({ ...modelForm, requiresGlobalEgress: Boolean(v) })}
                    />
                    <Typography.Text theme="secondary">需要出网节点</Typography.Text>
                  </Space>
                </Space>
                <details
                  style={{
                    border: '1px solid var(--td-border-level-1-color)',
                    borderRadius: 12,
                    padding: 12,
                  }}
                >
                  <summary style={{ cursor: 'pointer', fontWeight: 600 }}>高级配置：计价和元信息</summary>
                  <Space direction="vertical" size="small" style={{ width: '100%', marginTop: 12 }}>
                    <Alert theme="info" message="普通接入只需要填厂商、模型编号、显示名称和能力范围。计价策略和元信息仅在做成本核算或特殊路由时调整。" />
                    <div>
                      <Typography.Text theme="secondary">计价策略</Typography.Text>
                      <Textarea
                        value={modelForm.costPolicyText || '{}'}
                        onChange={(v) => onModelFormChange({ ...modelForm, costPolicyText: String(v) })}
                        autosize={{ minRows: 2, maxRows: 6 }}
                        placeholder='例如 {"currency":"CNY","billingUnit":"image","unitPrice":0.3}'
                      />
                    </div>
                    <div>
                      <Typography.Text theme="secondary">元信息</Typography.Text>
                      <Textarea
                        value={modelForm.metadataText || '{}'}
                        onChange={(v) => onModelFormChange({ ...modelForm, metadataText: String(v) })}
                        autosize={{ minRows: 2, maxRows: 6 }}
                      />
                    </div>
                  </Space>
                </details>
                <Button theme="primary" onClick={onModelSubmit}>
                  保存模型配置
                </Button>
              </Space>
            </div>
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col span={12}>
          <Card bordered title="第三方调用统计">
            <Typography.Text theme="secondary">
              来自能力服务的最近 {usageWindowHours} 小时调用日志，用于判断密钥、模型和上游是否稳定。
            </Typography.Text>
            <div style={{ marginTop: 12 }}>
              <Table
                size="small"
                rowKey="rowKey"
                data={usageItems.map((item, index) => ({
                  ...item,
                  rowKey: `${item.provider}-${item.model || 'all'}-${item.status}-${item.errorCode || 'ok'}-${index}`,
                }))}
                columns={[
                  {
                    colKey: 'provider',
                    title: '厂商 / 模型',
                    minWidth: 220,
                    cell: ({ row }) => (
                      <Space direction="vertical" size={2}>
                        <Typography.Text>{row.provider}</Typography.Text>
                        <Typography.Text theme="secondary" style={{ fontSize: 12 }}>
                          {row.model || '通用'}
                        </Typography.Text>
                      </Space>
                    ),
                  },
                  {
                    colKey: 'status',
                    title: '状态',
                    width: 120,
                    cell: ({ row }) => <StatusPill status={row.status} />,
                  },
                  {
                    colKey: 'count',
                    title: '次数',
                    width: 90,
                  },
                  {
                    colKey: 'latency',
                    title: '平均耗时',
                    width: 120,
                    cell: ({ row }) => (
                      <Typography.Text theme="secondary">
                        {typeof row.avgLatencyMs === 'number' ? `${row.avgLatencyMs}ms` : '—'}
                      </Typography.Text>
                    ),
                  },
                  {
                    colKey: 'errorCode',
                    title: '错误',
                    minWidth: 180,
                    cell: ({ row }) =>
                      row.errorCode ? (
                        <Typography.Text theme="error">{toDisplayErrorMessage(row.errorCode)}</Typography.Text>
                      ) : (
                        <Typography.Text theme="secondary">—</Typography.Text>
                      ),
                  },
                  {
                    colKey: 'lastSeenAt',
                    title: '最近时间',
                    width: 180,
                    cell: ({ row }) => (
                      <Typography.Text theme="secondary">
                        {row.lastSeenAt ? formatDateTime(row.lastSeenAt) : '—'}
                      </Typography.Text>
                    ),
                  },
                ]}
                empty={<Typography.Text theme="secondary">暂无第三方调用统计。跑一次模型测试后会自动出现。</Typography.Text>}
              />
            </div>
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={12} lg={7}>
          <Card bordered title="第三方密钥池">
            <Table
              size="small"
              rowKey="id"
              data={keys}
              columns={[
                {
                  colKey: 'alias',
                  title: '密钥别名',
                  minWidth: 220,
                  cell: ({ row }) => (
                    <Space direction="vertical" size={2}>
                      <Typography.Text>{row.alias}</Typography.Text>
                      <Typography.Text theme="secondary" style={{ fontSize: 12 }}>
                        {row.provider} · {row.keyPreview}
                      </Typography.Text>
                    </Space>
                  ),
                },
                {
                  colKey: 'status',
                  title: '状态',
                  width: 110,
                  cell: ({ row }) => <StatusPill status={row.status} />,
                },
                {
                  colKey: 'usage',
                  title: '用量/并发',
                  width: 160,
                  cell: ({ row }) => (
                    <Typography.Text theme="secondary">
                      {row.usageCount}/{row.dailyQuota ?? '—'} · 并发 {row.maxConcurrency}
                    </Typography.Text>
                  ),
                },
                {
                  colKey: 'last',
                  title: '最近使用',
                  width: 160,
                  cell: ({ row }) => (
                    <Typography.Text theme="secondary">{row.lastUsedAt ? formatDateTime(row.lastUsedAt) : '—'}</Typography.Text>
                  ),
                },
                {
                  colKey: 'actions',
                  title: '操作',
                  width: 110,
                  cell: ({ row }) => (
                    <Button size="small" variant="text" onClick={() => onKeyFormChange({ ...row })}>
                      编辑
                    </Button>
                  ),
                },
              ]}
              empty={<Typography.Text theme="secondary">暂无第三方密钥。可在右侧新增。</Typography.Text>}
            />
          </Card>
        </Col>

        <Col xs={12} lg={5}>
          <Card bordered title={keyForm.id ? '编辑第三方密钥' : '新增第三方密钥'}>
            <Space direction="vertical" size="middle" style={{ width: '100%' }}>
              <Alert theme="info" message="这里写入第三方能力服务；保存后只展示隐藏后的预览，Coze 和前端不会接触明文。" />
              <Row gutter={[12, 12]}>
                <Col span={6}>
                  <Typography.Text theme="secondary">厂商</Typography.Text>
                  <Select
                    value={keyForm.provider || ''}
                    disabled={Boolean(keyForm.id)}
                    onChange={(v) => onKeyFormChange({ ...keyForm, provider: String(v) })}
                    options={[
                      { label: '请选择厂商…', value: '' },
                      ...providers.map((item) => ({ label: `${item.displayName} (${item.provider})`, value: item.provider })),
                    ]}
                  />
                </Col>
                <Col span={6}>
                  <Typography.Text theme="secondary">状态</Typography.Text>
                  <Select
                    value={keyForm.status || 'active'}
                    onChange={(v) => onKeyFormChange({ ...keyForm, status: String(v) })}
                    options={apiKeyStatusOptions.map((item) => ({ ...item }))}
                  />
                </Col>
              </Row>
              <div>
                <Typography.Text theme="secondary">别名</Typography.Text>
                <Input
                  value={keyForm.alias || ''}
                  onChange={(v) => onKeyFormChange({ ...keyForm, alias: String(v) })}
                  placeholder="例如 OpenAI-Global-主账号"
                />
              </div>
              {!keyForm.id ? (
                <div>
                  <Typography.Text theme="secondary">密钥</Typography.Text>
                  <Input
                    type="password"
                    value={keyForm.key || ''}
                    onChange={(v) => onKeyFormChange({ ...keyForm, key: String(v) })}
                    placeholder="粘贴第三方 API 密钥"
                  />
                </div>
              ) : (
                <div>
                  <Typography.Text theme="secondary">替换密钥（可选）</Typography.Text>
                  <Input
                    type="password"
                    value={keyForm.key || ''}
                    onChange={(v) => onKeyFormChange({ ...keyForm, key: String(v) })}
                    placeholder={`当前密钥：${keyForm.keyPreview || '***'}，不填则不更换`}
                  />
                </div>
              )}
              <div>
                <Typography.Text theme="secondary">限定模型（可选）</Typography.Text>
                <Input
                  value={keyForm.model || ''}
                  onChange={(v) => onKeyFormChange({ ...keyForm, model: String(v) })}
                  placeholder="例如 gpt-image-2；为空表示该厂商通用"
                />
              </div>
              <Row gutter={[12, 12]}>
                <Col span={6}>
                  <Typography.Text theme="secondary">日配额</Typography.Text>
                  <InputNumber
                    min={0}
                    value={keyForm.dailyQuota ?? undefined}
                    onChange={(v) =>
                      onKeyFormChange({ ...keyForm, dailyQuota: v === undefined || v === null ? undefined : Number(v) })
                    }
                  />
                </Col>
                <Col span={6}>
                  <Typography.Text theme="secondary">月配额</Typography.Text>
                  <InputNumber
                    min={0}
                    value={keyForm.monthlyQuota ?? undefined}
                    onChange={(v) =>
                      onKeyFormChange({ ...keyForm, monthlyQuota: v === undefined || v === null ? undefined : Number(v) })
                    }
                  />
                </Col>
              </Row>
              <Row gutter={[12, 12]}>
                <Col span={6}>
                  <Typography.Text theme="secondary">最大并发</Typography.Text>
                  <InputNumber
                    min={1}
                    value={keyForm.maxConcurrency ?? 1}
                    onChange={(v) => onKeyFormChange({ ...keyForm, maxConcurrency: Number(v || 1) })}
                  />
                </Col>
              </Row>
              <Space style={{ width: '100%' }}>
                <Button theme="primary" style={{ flex: 1 }} onClick={onKeySubmit}>
                  保存到能力服务
                </Button>
                {keyForm.id ? (
                  <Button variant="outline" onClick={onKeyReset}>
                    取消
                  </Button>
                ) : null}
              </Space>
            </Space>
          </Card>
        </Col>
      </Row>
    </>
  );
}
