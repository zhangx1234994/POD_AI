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
  VendorModelBulkActionType,
  VendorModelFormState,
  VendorProvider,
  VendorUsageSummaryItem,
} from '../../../types/admin';
import { toDisplayErrorMessage } from '../../../utils/errorMessageMap';
import { GuidanceQueueCard, OperationFlowCard, StatusBadge, type GuidanceQueueItem } from '../shared/ui';
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

const parseJsonObjectText = (value?: string | null): Record<string, unknown> => {
  const raw = String(value || '').trim();
  if (!raw) return {};
  try {
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed as Record<string, unknown> : {};
  } catch {
    return {};
  }
};

const compactJsonObject = (value: Record<string, unknown>) => {
  const out: Record<string, unknown> = {};
  Object.entries(value).forEach(([key, item]) => {
    if (item === undefined || item === null || item === '') return;
    out[key] = item;
  });
  return out;
};

const isVendorUsageFailed = (item: VendorUsageSummaryItem): boolean => {
  const status = String(item.status || '').toLowerCase();
  if (Boolean(item.errorCode)) return true;
  return ['failed', 'failure', 'error', 'timeout', 'canceled', 'cancelled'].includes(status);
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

const releaseGateTheme = (status?: string): VendorModelProfileTheme => {
  if (status === 'ready') return 'success';
  if (status === 'warning') return 'warning';
  if (status === 'blocked') return 'danger';
  return 'default';
};

const releaseGateText = (model: VendorModel): string => {
  const gate = model.releaseGate;
  if (!gate) return '未检查';
  if (gate.label) return gate.label;
  if (gate.status === 'ready') return '可上线';
  if (gate.status === 'warning') return '需复核';
  if (gate.status === 'blocked') return '暂不能上线';
  return '未检查';
};

const getAcceptanceText = (model: VendorModel): string => {
  const latest = model.latestAcceptance;
  if (!latest || typeof latest !== 'object' || Array.isArray(latest)) return '未验收';
  const status = String((latest as Record<string, unknown>).status || '');
  if (status === 'passed') return '已验收';
  if (status === 'failed') return '验收失败';
  if (status === 'warning') return '带风险';
  if (status === 'waived') return '已豁免';
  return status || '未验收';
};

type VendorModelProfileTheme = 'default' | 'primary' | 'success' | 'warning' | 'danger';

type VendorModelProfile = {
  label: string;
  theme: VendorModelProfileTheme;
  detail: string;
  tags: Array<{ label: string; theme?: VendorModelProfileTheme }>;
  suggestions: string[];
};

const hasTokenLike = (tokens: string[], keywords: string[]) =>
  tokens.some((token) => keywords.some((keyword) => token.includes(keyword)));

const resolveVendorModelProfile = (model: VendorModel): VendorModelProfile => {
  const apiTypes = (model.apiTypes || []).map((item) => String(item || '').toLowerCase()).filter(Boolean);
  const tags: VendorModelProfile['tags'] = [];
  const suggestions: string[] = [];

  let label = '通用模型';
  let theme: VendorModelProfileTheme = 'default';
  let detail = '需要补齐能力范围后再绑定到业务能力。';

  if (model.supportsVideo || hasTokenLike(apiTypes, ['video'])) {
    label = '视频模型';
    theme = 'warning';
    detail = '适合生视频、图生视频或视频处理，任务耗时和成本通常更高。';
  } else if (hasTokenLike(apiTypes, ['vision', 'vl'])) {
    label = '图像理解';
    theme = 'primary';
    detail = '适合看图分析、图片描述、质检和提示词辅助。';
  } else if (hasTokenLike(apiTypes, ['image', 'edit']) || model.supportsMask || model.supportsMultipleImages) {
    label = '图片模型';
    theme = 'success';
    detail = '适合文生图、图生图、图片编辑或图片处理。';
  } else if (model.supportsText || hasTokenLike(apiTypes, ['chat', 'text', 'response'])) {
    label = '文字/多模态';
    theme = 'primary';
    detail = '适合文本生成、改写、对话或多模态推理。';
  }

  apiTypes.slice(0, 4).forEach((item) => {
    tags.push({ label: getReadableTokenLabel(item, apiTypeLabels) });
  });
  if (apiTypes.length > 4) tags.push({ label: `还有 ${apiTypes.length - 4} 类` });
  if (model.supportsMask) tags.push({ label: '支持蒙版', theme: 'success' });
  if (model.supportsMultipleImages) tags.push({ label: '支持多图', theme: 'success' });
  if (model.supportsVideo) tags.push({ label: '支持视频', theme: 'warning' });
  if (model.supportsText) tags.push({ label: '支持文字', theme: 'primary' });
  tags.push({
    label: model.requiresGlobalEgress ? '需要出网' : '国内直连',
    theme: model.requiresGlobalEgress ? 'warning' : 'success',
  });
  tags.push({
    label: hasJsonContent(model.costPolicy) ? '已配计价' : '缺计价',
    theme: hasJsonContent(model.costPolicy) ? 'success' : 'warning',
  });

  if (!apiTypes.length) suggestions.push('先补能力范围，否则业务绑定时容易选错模型。');
  if (!hasJsonContent(model.costPolicy)) suggestions.push('上线前补计价策略，避免后续账单无法核算。');
  if (model.requiresGlobalEgress) suggestions.push('发布前必须做带密钥出网检查。');
  if (model.status !== 'active') suggestions.push('当前未启用，不能作为业务默认模型。');

  return { label, theme, detail, tags, suggestions };
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
  const lastCheck = item.metadata?.lastCheck;
  if (!lastCheck || typeof lastCheck !== 'object' || Array.isArray(lastCheck)) {
    return { theme: 'warning', label: '未验证', suggestion: '上线前先做一次单条密钥验证。' };
  }
  if ((lastCheck as Record<string, unknown>).success === false) {
    return { theme: 'danger', label: '验证失败', suggestion: '先替换密钥或检查上游账号状态，不要直接放量。' };
  }
  const checkedAt = Date.parse(String((lastCheck as Record<string, unknown>).checkedAt || ''));
  if (!Number.isFinite(checkedAt) || Date.now() - checkedAt > 7 * 24 * 60 * 60 * 1000) {
    return { theme: 'warning', label: '验证过期', suggestion: '最近验证超过 7 天，发布前重新做带密钥检查。' };
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

const getVendorKeyLastCheck = (item: VendorKey): Record<string, unknown> | null => {
  const value = item.metadata?.lastCheck;
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  return value as Record<string, unknown>;
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

const getModelGateIssues = (model: VendorModel): string[] => [
  ...(model.releaseGate?.blockers || []),
  ...(model.releaseGate?.warnings || []),
];

const resolveModelPrimaryAction = (
  model: VendorModel,
): { theme: 'success' | 'warning' | 'danger' | 'default'; label: string; action: string; issue?: string } => {
  const gate = model.releaseGate;
  if (gate?.primaryAction || gate?.primaryActionLabel || gate?.primaryIssue) {
    const severity = String(gate.primarySeverity || '').trim();
    const fallbackTheme = releaseGateTheme(gate.status);
    const theme =
      severity === 'danger' || severity === 'warning' || severity === 'success' || severity === 'default'
        ? severity
        : fallbackTheme === 'primary'
          ? 'default'
          : fallbackTheme;
    return {
      theme,
      label: String(gate.primaryActionLabel || releaseGateText(model) || '待检查'),
      action: String(gate.primaryAction || gate.suggestions?.[0] || '刷新弹药库后查看模型门禁结果。'),
      issue: gate.primaryIssue || undefined,
    };
  }
  const issues = getModelGateIssues(model);
  const has = (code: string) => issues.some((item) => item.startsWith(code));
  if (has('VENDOR_MODEL_INACTIVE')) {
    return {
      theme: 'danger',
      label: '未启用',
      issue: 'VENDOR_MODEL_INACTIVE',
      action: '启用模型，或把业务能力切到其他已启用模型。',
    };
  }
  if (has('VENDOR_MODEL_RUNTIME_KEY_MISSING')) {
    return {
      theme: 'danger',
      label: '补密钥',
      issue: 'VENDOR_MODEL_RUNTIME_KEY_MISSING',
      action: '先配置该厂商可用密钥，再做带密钥检查。',
    };
  }
  if (has('VENDOR_MODEL_KEY_CHECK_FAILED') || has('VENDOR_MODEL_KEY_CHECK_PARTIAL_FAILED')) {
    return {
      theme: 'danger',
      label: '查密钥',
      issue: 'VENDOR_MODEL_KEY_CHECK_FAILED',
      action: '最近密钥验证失败，先替换密钥或确认厂商账号状态。',
    };
  }
  if (has('VENDOR_MODEL_KEY_NEVER_CHECKED') || has('VENDOR_MODEL_KEY_CHECK_STALE')) {
    return {
      theme: 'warning',
      label: '重验密钥',
      issue: 'VENDOR_MODEL_KEY_CHECK_STALE',
      action: '上线前重新做一次单条密钥验证。',
    };
  }
  if (has('VENDOR_MODEL_API_TYPES_MISSING') || has('VENDOR_MODEL_EXECUTION_MODE_MISSING')) {
    return {
      theme: 'warning',
      label: '补边界',
      issue: 'VENDOR_MODEL_API_TYPES_MISSING',
      action: '补齐模型能做什么、如何返回结果，避免业务同学选错。',
    };
  }
  if (has('VENDOR_MODEL_GLOBAL_EGRESS_REQUIRED')) {
    return {
      theme: 'warning',
      label: '查出网',
      issue: 'VENDOR_MODEL_GLOBAL_EGRESS_REQUIRED',
      action: '确认该模型实际走有国际出口的能力服务节点，并做带密钥出网验证。',
    };
  }
  if (has('VENDOR_MODEL_ACCEPTANCE_REQUIRED')) {
    return {
      theme: 'danger',
      label: '先验收',
      issue: 'VENDOR_MODEL_ACCEPTANCE_REQUIRED',
      action: '先用能力测试或测评端跑一条真实任务，确认结果回填正常后，点击“记验收”。',
    };
  }
  if (has('VENDOR_MODEL_COST_POLICY_MISSING')) {
    return {
      theme: 'warning',
      label: '补计价',
      issue: 'VENDOR_MODEL_COST_POLICY_MISSING',
      action: '补齐计费单位、币种、单价和定价版本，避免上线后账单不准。',
    };
  }
  if (model.releaseGate?.status === 'ready') {
    return { theme: 'success', label: '可上线', action: '基础门禁通过，可进入业务绑定和小流量验证。' };
  }
  return { theme: 'default', label: '待检查', action: '刷新弹药库后查看模型门禁结果。' };
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

function VendorModelProfileSummary({ model }: { model: VendorModel }) {
  const profile = resolveVendorModelProfile(model);
  return (
    <div
      style={{
        border: '1px solid var(--td-border-level-1-color)',
        borderRadius: 10,
        padding: 12,
        background: 'var(--td-bg-color-secondarycontainer)',
      }}
    >
      <Space direction="vertical" size={6} style={{ width: '100%' }}>
        <Space size={8} align="center" style={{ flexWrap: 'wrap' }}>
          <Tag theme={profile.theme} variant="light">
            {profile.label}
          </Tag>
          <Typography.Text>{profile.detail}</Typography.Text>
        </Space>
        <Space size={4} style={{ flexWrap: 'wrap' }}>
          {profile.tags.map((item) => (
            <Tag key={`profile-${model.provider}-${model.model}-${item.label}`} theme={item.theme} variant="light">
              {item.label}
            </Tag>
          ))}
        </Space>
        {profile.suggestions.length ? (
          <Space direction="vertical" size={2}>
            {profile.suggestions.map((item) => (
              <Typography.Text key={`suggestion-${model.provider}-${model.model}-${item}`} theme="warning" style={{ fontSize: 12 }}>
                {item}
              </Typography.Text>
            ))}
          </Space>
        ) : (
          <Typography.Text theme="success" style={{ fontSize: 12 }}>
            基础信息完整，可进入能力绑定和小流量测试。
          </Typography.Text>
        )}
      </Space>
    </div>
  );
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
  onModelBulkAction: (action: VendorModelBulkActionType, models: VendorModel[]) => void;
  onModelAccept: (model: VendorModel) => void;
  onModelReset: () => void;
  onModelSubmit: () => void;
  onKeyFormChange: (next: VendorKeyFormState) => void;
  onKeyCheck: (keyId: string) => void;
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
  onModelBulkAction,
  onModelAccept,
  onModelReset,
  onModelSubmit,
  onKeyFormChange,
  onKeyCheck,
  onKeySubmit,
  onKeyReset,
}: VendorModelsPanelProps) {
  const [selectedModelSeed, setSelectedModelDetail] = useState<VendorModel | null>(null);
  const [modelGateFilter, setModelGateFilter] = useState<string>('needs_action');
  const activeKeyCount = keys.filter((item) => item.status === 'active').length;
  const egressProviderCount = providers.filter((item) => item.requiresGlobalEgress).length;
  const readyModels = models.filter((item) => item.releaseGate?.status === 'ready');
  const blockedModels = models.filter((item) => item.releaseGate?.status === 'blocked');
  const warningModels = models.filter((item) => item.releaseGate?.status === 'warning');
  const modelProfiles = models.map((model) => ({ model, profile: resolveVendorModelProfile(model) }));
  const modelTypeSummary = [
    {
      key: 'image',
      title: '图片模型',
      count: modelProfiles.filter((item) => item.profile.label === '图片模型').length,
      detail: '文生图、图生图、图片编辑、蒙版和多图能力。',
      action: '优先绑定图裂变、扩图、花纹处理类业务。',
      theme: 'success' as const,
    },
    {
      key: 'video',
      title: '视频模型',
      count: modelProfiles.filter((item) => item.profile.label === '视频模型').length,
      detail: '文生视频、图生视频或视频处理，通常耗时和成本更高。',
      action: '后续独立做并发、成本和超时策略。',
      theme: 'warning' as const,
    },
    {
      key: 'text',
      title: '文字/多模态',
      count: modelProfiles.filter((item) => item.profile.label === '文字/多模态').length,
      detail: '文本生成、改写、对话和多模态推理。',
      action: '用于提示词、标题、描述和业务文案能力。',
      theme: 'primary' as const,
    },
    {
      key: 'vl',
      title: '图像理解',
      count: modelProfiles.filter((item) => item.profile.label === '图像理解').length,
      detail: '看图分析、图片描述、质检和提示词辅助。',
      action: '作为 VL 弹药库，给裂变、扩图和审核流程复用。',
      theme: 'primary' as const,
    },
    {
      key: 'general',
      title: '待确认',
      count: modelProfiles.filter((item) => item.profile.label === '通用模型').length,
      detail: '能力范围还不够明确，接业务前需要补充模型能力说明。',
      action: '先补能力类型、输入输出和计价口径。',
      theme: 'default' as const,
    },
  ];
  const unacceptedModels = models.filter((item) => item.releaseGate?.acceptancePassed !== true);
  const missingKeyModels = models.filter((item) => getModelGateIssues(item).some((issue) => issue.startsWith('VENDOR_MODEL_RUNTIME_KEY_MISSING')));
  const unpricedModels = models.filter((item) => getModelGateIssues(item).some((issue) => issue.startsWith('VENDOR_MODEL_COST_POLICY_MISSING')));
  const inactiveModels = models.filter((item) => String(item.status || '').toLowerCase() !== 'active');
  const visibleModels = models.filter((item) => {
    if (modelGateFilter === 'all') return true;
    if (modelGateFilter === 'ready') return item.releaseGate?.status === 'ready';
    if (modelGateFilter === 'blocked') return item.releaseGate?.status === 'blocked';
    if (modelGateFilter === 'warning') return item.releaseGate?.status === 'warning';
    if (modelGateFilter === 'unaccepted') return item.releaseGate?.acceptancePassed !== true;
    return item.releaseGate?.status !== 'ready';
  });
  const modelActionItems = models
    .map((item) => ({ model: item, action: resolveModelPrimaryAction(item) }))
    .filter((item) => item.action.theme !== 'success')
    .sort((a, b) => {
      const rank = { danger: 0, warning: 1, default: 2, success: 3 };
      return rank[a.action.theme] - rank[b.action.theme];
    })
    .slice(0, 8);
  const selectedModelDetail = selectedModelSeed?.id
    ? models.find((item) => item.id === selectedModelSeed.id) || selectedModelSeed
    : selectedModelSeed;
  const failedUsageItems = usageItems.filter(isVendorUsageFailed).slice(0, 8);
  const riskyKeys = keys
    .map((item) => ({ key: item, risk: resolveVendorKeyRisk(item) }))
    .filter((item) => item.risk.theme !== 'success')
    .slice(0, 8);
  const acceptanceItems = vendorAcceptanceTargets.map((target) =>
    buildVendorAcceptanceItem(target, providers, models, keys, usageItems),
  );
  const costPolicyDraft = parseJsonObjectText(modelForm.costPolicyText);
  const updateCostPolicy = (patch: Record<string, unknown>) => {
    const next = compactJsonObject({ ...costPolicyDraft, ...patch });
    onModelFormChange({ ...modelForm, costPolicyText: JSON.stringify(next, null, 2) });
  };
  const guidanceItems: GuidanceQueueItem[] = [];
  if (activeKeyCount === 0) {
    guidanceItems.push({
      key: 'no-active-key',
      theme: 'danger',
      title: '先配置可用密钥',
      detail: '没有 active 密钥时，商业模型无法真实调用，业务默认版本也无法稳定上线。',
      action: '到密钥池新增或启用密钥',
    });
  }
  if (missingKeyModels.length > 0) {
    guidanceItems.push({
      key: 'missing-key-models',
      theme: 'danger',
      title: '模型缺可用密钥',
      detail: `${missingKeyModels.length} 个模型没有可用运行密钥，真实调用和验收都会失败。`,
      action: '查看需处理模型',
      onClick: () => setModelGateFilter('needs_action'),
    });
  }
  if (blockedModels.length > 0) {
    guidanceItems.push({
      key: 'blocked-models',
      theme: 'danger',
      title: '模型暂不能上线',
      detail: `${blockedModels.length} 个模型存在阻塞项，先不要绑定到业务默认版本。`,
      action: '查看阻塞模型',
      onClick: () => setModelGateFilter('blocked'),
    });
  }
  if (unacceptedModels.length > 0) {
    guidanceItems.push({
      key: 'unaccepted-models',
      theme: 'warning',
      title: '补模型验收记录',
      detail: `${unacceptedModels.length} 个模型还没有验收通过记录，发布门禁会拦住业务默认版本。`,
      action: '查看未验收模型',
      onClick: () => setModelGateFilter('unaccepted'),
    });
  }
  if (unpricedModels.length > 0) {
    guidanceItems.push({
      key: 'unpriced-models',
      theme: 'warning',
      title: '补计价策略',
      detail: `${unpricedModels.length} 个模型缺计价，成功任务会进入未定价风险。`,
      action: '查看需处理模型',
      onClick: () => setModelGateFilter('needs_action'),
    });
  }
  if (usageFailed > 0) {
    guidanceItems.push({
      key: 'usage-failed',
      theme: 'warning',
      title: '先看失败样本',
      detail: `近 ${usageWindowHours} 小时有 ${usageFailed} 次第三方调用失败，切业务默认版本前要先确认原因。`,
      action: '查看失败样本',
    });
  }
  if (guidanceItems.length === 0) {
    guidanceItems.push({
      key: 'vendor-ready',
      theme: 'success',
      title: '模型治理当前可推进',
      detail: '密钥、模型上线判断、验收和计价没有明显阻塞，可继续接入新模型或做小流量测试。',
      action: '继续绑定业务能力并做测评',
    });
  }

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
          <MetricCard label="模型可上线" value={readyModels.length} sub={`阻塞 ${blockedModels.length} / 复核 ${warningModels.length}`} />
        </Col>
        <Col xs={12} lg={4}>
          <MetricCard label="未验收模型" value={unacceptedModels.length} sub="业务默认版本会被门禁拦住" />
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

      <OperationFlowCard
        title="模型接入闭环"
        description="商业模型先确认风险，再补模型信息、绑定能力，最后用小流量验证。"
        summary="密钥、出网、计价或验收有缺口时，不要直接把模型绑定到主业务默认版本。"
        summaryTheme={blockedModels.length || missingKeyModels.length || unacceptedModels.length ? 'warning' : 'success'}
        style={{ marginTop: 12 }}
        steps={[
          {
            key: 'vendor-risk',
            title: '先看风险',
            detail: '密钥、出网、余额、失败样本是商业模型能否使用的前置条件。',
            action: '有红色或黄色风险时，先处理密钥、出网和失败样本。',
            done: '风险清楚',
            theme: blockedModels.length || missingKeyModels.length ? 'warning' : 'success',
          },
          {
            key: 'vendor-model-contract',
            title: '补齐模型口径',
            detail: '确认模型目录、能力范围、输出类型、执行方式和计价口径。',
            action: '图片、视频、文字、图像理解要分开记录，不要都按生图理解。',
            done: '模型可读',
            theme: 'primary',
          },
          {
            key: 'vendor-bind-ability',
            title: '再绑能力',
            detail: '模型稳定后再绑定到原子能力或业务版本。',
            action: '让业务能力引用模型，不让业务方直接理解厂商接口。',
            done: '能力承接',
            theme: 'primary',
          },
          {
            key: 'vendor-small-traffic',
            title: '最后小流量',
            detail: '用能力测试和测评端跑通，再逐步放量。',
            action: '记录验收通过、成功样本和失败归因，再考虑切默认版本。',
            done: '可灰度',
            theme: unacceptedModels.length ? 'warning' : 'success',
          },
        ]}
      />

      <Card bordered title="模型类型总览" style={{ marginTop: 12 }}>
        <Typography.Text theme="secondary">
          不再把所有第三方模型都当成生图模型；后续图片、视频、文字、图像理解会走不同的业务能力和测试标准。
        </Typography.Text>
        <Row gutter={[12, 12]} style={{ marginTop: 12 }}>
          {modelTypeSummary.map((item) => (
            <Col key={item.key} xs={12} md={4} xl={2}>
              <Card bordered size="small" style={{ height: '100%' }}>
                <Space direction="vertical" size={4} style={{ width: '100%' }}>
                  <Space align="center" style={{ justifyContent: 'space-between', width: '100%', gap: 8 }}>
                    <Typography.Text strong>{item.title}</Typography.Text>
                    <Tag theme={item.theme} variant="light">
                      {item.count}
                    </Tag>
                  </Space>
                  <Typography.Text theme="secondary">{item.detail}</Typography.Text>
                  <Typography.Text theme="secondary">建议：{item.action}</Typography.Text>
                </Space>
              </Card>
            </Col>
          ))}
        </Row>
      </Card>

      <GuidanceQueueCard items={guidanceItems} style={{ marginTop: 12 }} />

      <Card bordered title="模型上线处理队列" style={{ marginTop: 16 }}>
        <Space direction="vertical" size="small" style={{ width: '100%' }}>
          <Typography.Text theme="secondary">
            只看模型级门禁，不看底层技术字段。这里有红色项时，先不要把模型绑定到业务默认版本。
          </Typography.Text>
          <Space size="small" style={{ flexWrap: 'wrap' }}>
            <Button
              size="small"
              variant="outline"
              disabled={!unacceptedModels.length}
              onClick={() => onModelBulkAction('record_acceptance', unacceptedModels)}
            >
              批量记验收 {unacceptedModels.length}
            </Button>
            <Button
              size="small"
              variant="outline"
              disabled={!inactiveModels.length}
              onClick={() => onModelBulkAction('enable', inactiveModels)}
            >
              批量启用 {inactiveModels.length}
            </Button>
            <Button
              size="small"
              variant="outline"
              disabled={!blockedModels.length}
              onClick={() => onModelBulkAction('disable', blockedModels)}
            >
              批量停用阻塞 {blockedModels.length}
            </Button>
            <Button
              size="small"
              variant="outline"
              disabled={!unpricedModels.length || !hasJsonContent(costPolicyDraft)}
              onClick={() => onModelBulkAction('apply_cost_policy', unpricedModels)}
            >
              用表单计价批量补齐 {unpricedModels.length}
            </Button>
            <Typography.Text theme="secondary" style={{ fontSize: 12 }}>
              批量操作会写入模型审计记录；计价批量应用使用下方表单里的“计价策略”。
            </Typography.Text>
          </Space>
          <Row gutter={[12, 12]}>
            <Col xs={12} md={3}>
              <Alert
                theme={blockedModels.length ? 'warning' : 'success'}
                message={blockedModels.length ? `有 ${blockedModels.length} 个模型暂不能上线。` : '没有模型级阻塞。'}
              />
            </Col>
            <Col xs={12} md={3}>
              <Alert
                theme={unacceptedModels.length ? 'warning' : 'success'}
                message={unacceptedModels.length ? `有 ${unacceptedModels.length} 个模型缺少验收记录。` : '模型验收记录已补齐。'}
              />
            </Col>
            <Col xs={12} md={3}>
              <Alert
                theme={missingKeyModels.length ? 'warning' : 'success'}
                message={missingKeyModels.length ? `有 ${missingKeyModels.length} 个模型缺少可用密钥。` : '模型密钥基础可用。'}
              />
            </Col>
            <Col xs={12} md={3}>
              <Alert
                theme={unpricedModels.length ? 'warning' : 'success'}
                message={unpricedModels.length ? `有 ${unpricedModels.length} 个模型缺少计价。` : '模型计价基础完整。'}
              />
            </Col>
          </Row>
          <Table
            size="small"
            rowKey="modelActionKey"
            data={modelActionItems.map(({ model, action }) => ({
              modelActionKey: `${model.provider}-${model.model}-${action.label}`,
              model,
              action,
            }))}
            columns={[
              {
                colKey: 'model',
                title: '模型',
                minWidth: 220,
                cell: ({ row }) => (
                  <Space direction="vertical" size={2}>
                    <Typography.Text strong>{row.model.displayName}</Typography.Text>
                    <Typography.Text theme="secondary" style={{ fontSize: 12 }}>
                      {row.model.provider} / {row.model.model}
                    </Typography.Text>
                  </Space>
                ),
              },
              {
                colKey: 'action',
                title: '当前要做',
                width: 140,
                cell: ({ row }) => (
                  <Tag theme={row.action.theme} variant="light">
                    {row.action.label}
                  </Tag>
                ),
              },
              {
                colKey: 'reason',
                title: '原因',
                minWidth: 180,
                cell: ({ row }) => (
                  <Typography.Text theme="secondary">
                    {row.action.issue ? getVendorIssueLabel(row.action.issue) : releaseGateText(row.model)}
                  </Typography.Text>
                ),
              },
              {
                colKey: 'next',
                title: '处理动作',
                minWidth: 300,
                cell: ({ row }) => <Typography.Text>{row.action.action}</Typography.Text>,
              },
              {
                colKey: 'ops',
                title: '操作',
                width: 160,
                cell: ({ row }) => (
                  <Space size={4}>
                    <Button size="small" variant="text" onClick={() => setSelectedModelDetail(row.model)}>
                      看详情
                    </Button>
                    <Button size="small" variant="text" onClick={() => onModelEdit(row.model)}>
                      编辑
                    </Button>
                  </Space>
                ),
              },
            ]}
            empty={<Alert theme="success" message="当前没有模型级待处理项。仍建议在切业务默认版本前跑一条真实任务。" />}
          />
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
          这里是厂商级粗看：厂商是否接入、密钥是否可用、模型目录是否存在、最近是否跑通过。具体模型能否上线以上方“模型上线处理队列”和下方“模型目录”为准。
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
                      {row.uncheckedKeyCount > 0 ? (
                        <Tag theme="warning" variant="light">
                          未验证 {row.uncheckedKeyCount}
                        </Tag>
                      ) : null}
                      {row.staleKeyCheckCount > 0 ? (
                        <Tag theme="warning" variant="light">
                          验证过期 {row.staleKeyCheckCount}
                        </Tag>
                      ) : null}
                      {row.failedKeyCheckCount > 0 ? (
                        <Tag theme="danger" variant="light">
                          验证失败 {row.failedKeyCheckCount}
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
                        {safeNumber(row.queuedCalls) > 0 ? `，排队 ${safeNumber(row.queuedCalls)}` : ''}
                        {safeNumber(row.runningCalls) > 0 ? `，运行 ${safeNumber(row.runningCalls)}` : ''}
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
          <Card bordered title="模型目录与上线判断">
            <Space align="center" style={{ justifyContent: 'space-between', width: '100%', flexWrap: 'wrap', marginBottom: 12 }}>
              <Typography.Text theme="secondary">
                默认只看待处理模型；需要全量维护时再切到“全部模型”。
              </Typography.Text>
              <Select
                size="small"
                value={modelGateFilter}
                style={{ width: 180 }}
                onChange={(value) => setModelGateFilter(String(value))}
                options={[
                  { label: `待处理 ${models.length - readyModels.length}`, value: 'needs_action' },
                  { label: `暂不能上线 ${blockedModels.length}`, value: 'blocked' },
                  { label: `需复核 ${warningModels.length}`, value: 'warning' },
                  { label: `未验收 ${unacceptedModels.length}`, value: 'unaccepted' },
                  { label: `可上线 ${readyModels.length}`, value: 'ready' },
                  { label: `全部模型 ${models.length}`, value: 'all' },
                ]}
              />
            </Space>
            <Table
              size="small"
              rowKey="model"
              data={visibleModels}
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
                  title: '适合场景',
                  minWidth: 300,
                  cell: ({ row }) => {
                    const profile = resolveVendorModelProfile(row);
                    return (
                      <Space direction="vertical" size={4}>
                        <Space size={6} align="center">
                          <Tag theme={profile.theme} variant="light">
                            {profile.label}
                          </Tag>
                          <Typography.Text theme="secondary" style={{ fontSize: 12 }}>
                            {profile.detail}
                          </Typography.Text>
                        </Space>
                        <Space size={4} style={{ flexWrap: 'wrap' }}>
                          {profile.tags.slice(0, 7).map((item) => (
                            <Tag key={`${row.provider}-${row.model}-${item.label}`} theme={item.theme} variant="light">
                              {item.label}
                            </Tag>
                          ))}
                        </Space>
                        {profile.suggestions[0] ? (
                          <Typography.Text theme="warning" style={{ fontSize: 12 }}>
                            {profile.suggestions[0]}
                          </Typography.Text>
                        ) : null}
                      </Space>
                    );
                  },
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
                  colKey: 'releaseGate',
                  title: '上线判断',
                  minWidth: 180,
                  cell: ({ row }) => (
                    <Space direction="vertical" size={2}>
                      <Space size={4}>
                        <Tag theme={releaseGateTheme(row.releaseGate?.status)} variant="light">
                          {releaseGateText(row)}
                        </Tag>
                        <Tag theme={row.releaseGate?.acceptancePassed ? 'success' : 'warning'} variant="light">
                          {getAcceptanceText(row)}
                        </Tag>
                        {row.requiresGlobalEgress ? (
                          <Tag theme={row.releaseGate?.egressVerified ? 'success' : 'warning'} variant="light">
                            {row.releaseGate?.egressVerified ? '出网已验' : '需验出网'}
                          </Tag>
                        ) : null}
                      </Space>
                      {row.releaseGate?.suggestions?.[0] ? (
                        <Typography.Text theme="secondary" style={{ fontSize: 12 }}>
                          {row.releaseGate.suggestions[0]}
                        </Typography.Text>
                      ) : null}
                    </Space>
                  ),
                },
                {
                  colKey: 'actions',
                  title: '操作',
                  width: 220,
                  cell: ({ row }) => (
                    <Space size={4}>
                      <Button size="small" variant="text" onClick={() => setSelectedModelDetail(row)}>
                        详情
                      </Button>
                      <Button size="small" variant="text" onClick={() => onModelEdit(row)}>
                        编辑
                      </Button>
                      <Button size="small" variant="text" onClick={() => onModelAccept(row)}>
                        记验收
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
                  <VendorModelProfileSummary model={selectedModelDetail} />
                  <div
                    style={{
                      border: '1px solid var(--td-border-level-1-color)',
                      borderRadius: 10,
                      padding: 12,
                      background: 'var(--td-bg-color-secondarycontainer)',
                    }}
                  >
                    <Space direction="vertical" size={6} style={{ width: '100%' }}>
                      <Space align="center" style={{ justifyContent: 'space-between', width: '100%', flexWrap: 'wrap' }}>
                        <Space size={6}>
                          <Tag theme={releaseGateTheme(selectedModelDetail.releaseGate?.status)} variant="light">
                            {releaseGateText(selectedModelDetail)}
                          </Tag>
                          <Tag theme={selectedModelDetail.releaseGate?.acceptancePassed ? 'success' : 'warning'} variant="light">
                            {getAcceptanceText(selectedModelDetail)}
                          </Tag>
                          {selectedModelDetail.requiresGlobalEgress ? (
                            <Tag theme={selectedModelDetail.releaseGate?.egressVerified ? 'success' : 'warning'} variant="light">
                              {selectedModelDetail.releaseGate?.egressVerified ? '出网已验' : '需验出网'}
                            </Tag>
                          ) : null}
                        </Space>
                        <Button size="small" variant="outline" onClick={() => onModelAccept(selectedModelDetail)}>
                          记录验收通过
                        </Button>
                      </Space>
                      {selectedModelDetail.latestAcceptance &&
                      typeof selectedModelDetail.latestAcceptance === 'object' &&
                      !Array.isArray(selectedModelDetail.latestAcceptance) ? (
                        <Typography.Text theme="secondary" style={{ fontSize: 12 }}>
                          最近验收：{String((selectedModelDetail.latestAcceptance as Record<string, unknown>).note || '未填写说明')}
                          {(selectedModelDetail.latestAcceptance as Record<string, unknown>).createdAt
                            ? ` · ${formatDateTime(String((selectedModelDetail.latestAcceptance as Record<string, unknown>).createdAt))}`
                            : ''}
                        </Typography.Text>
                      ) : (
                        <Typography.Text theme="warning" style={{ fontSize: 12 }}>
                          还没有人工验收通过记录，业务能力引用时会被上线门禁拦住。
                        </Typography.Text>
                      )}
                      {[...(selectedModelDetail.releaseGate?.blockers || []), ...(selectedModelDetail.releaseGate?.warnings || [])]
                        .slice(0, 6)
                        .map((item) => (
                          <Typography.Text key={`model-gate-${selectedModelDetail.id}-${item}`} theme="warning" style={{ fontSize: 12 }}>
                            {getVendorIssueLabel(item)}
                          </Typography.Text>
                        ))}
                      {(selectedModelDetail.releaseGate?.suggestions || []).slice(0, 3).map((item) => (
                        <Typography.Text key={`model-suggestion-${selectedModelDetail.id}-${item}`} theme="secondary" style={{ fontSize: 12 }}>
                          {item}
                        </Typography.Text>
                      ))}
                      {selectedModelDetail.auditRecords?.length ? (
                        <div
                          style={{
                            borderTop: '1px solid var(--td-border-level-1-color)',
                            paddingTop: 8,
                            marginTop: 4,
                          }}
                        >
                          <Space direction="vertical" size={4} style={{ width: '100%' }}>
                            <Typography.Text theme="secondary" style={{ fontSize: 12 }}>
                              最近处理记录
                            </Typography.Text>
                            {selectedModelDetail.auditRecords.slice(0, 3).map((record, index) => (
                              <Typography.Text
                                key={`model-audit-${selectedModelDetail.id}-${String(record.id || index)}`}
                                theme="secondary"
                                style={{ fontSize: 12 }}
                              >
                                {String(record.action || '处理')}
                                {record.note ? `：${String(record.note)}` : ''}
                                {record.createdAt ? ` · ${formatDateTime(String(record.createdAt))}` : ''}
                              </Typography.Text>
                            ))}
                          </Space>
                        </div>
                      ) : null}
                    </Space>
                  </div>
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
                    {selectedModelDetail.supportsText ? <Tag theme="primary" variant="light">支持文字</Tag> : null}
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
                <Alert
                  theme="info"
                  message="先确认模型适合图片、视频、文字还是图像理解，再绑定到具体业务能力；需要出网或缺计价的模型不要直接设为默认版本。"
                />
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
                    <Typography.Text theme="secondary">文字/多模态</Typography.Text>
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
                    <Row gutter={[12, 12]}>
                      <Col xs={12} sm={4} lg={2}>
                        <Typography.Text theme="secondary">计费单位</Typography.Text>
                        <Select
                          value={String(costPolicyDraft.billingUnit || '')}
                          options={[
                            { label: '按任务', value: 'run' },
                            { label: '按图片', value: 'image' },
                            { label: '按视频', value: 'video' },
                            { label: '按秒', value: 'second' },
                            { label: '按令牌', value: 'token' },
                            { label: '按字符', value: 'character' },
                            { label: '按请求', value: 'request' },
                          ]}
                          onChange={(v) => updateCostPolicy({ billingUnit: String(v || '') })}
                        />
                      </Col>
                      <Col xs={12} sm={4} lg={2}>
                        <Typography.Text theme="secondary">币种</Typography.Text>
                        <Select
                          value={String(costPolicyDraft.currency || 'CNY')}
                          options={[
                            { label: '人民币', value: 'CNY' },
                            { label: '美元', value: 'USD' },
                          ]}
                          onChange={(v) => updateCostPolicy({ currency: String(v || 'CNY') })}
                        />
                      </Col>
                      <Col xs={12} sm={4} lg={2}>
                        <Typography.Text theme="secondary">单价</Typography.Text>
                        <Input
                          value={costPolicyDraft.unitPrice === undefined ? '' : String(costPolicyDraft.unitPrice)}
                          placeholder="例如 0.3"
                          onChange={(v) => updateCostPolicy({ unitPrice: String(v || '').trim() ? Number(v) : undefined })}
                        />
                      </Col>
                      <Col xs={12} sm={4} lg={2}>
                        <Typography.Text theme="secondary">套餐消耗</Typography.Text>
                        <Input
                          value={costPolicyDraft.quotaUnits === undefined ? '' : String(costPolicyDraft.quotaUnits)}
                          placeholder="例如 1"
                          onChange={(v) => updateCostPolicy({ quotaUnits: String(v || '').trim() ? Number(v) : undefined })}
                        />
                      </Col>
                      <Col xs={12} sm={4} lg={2}>
                        <Typography.Text theme="secondary">数量字段</Typography.Text>
                        <Input
                          value={String(costPolicyDraft.quantityField || '')}
                          placeholder="可空，例如 output_count"
                          onChange={(v) => updateCostPolicy({ quantityField: String(v || '').trim() || undefined })}
                        />
                      </Col>
                      <Col xs={12} sm={4} lg={2}>
                        <Typography.Text theme="secondary">定价版本</Typography.Text>
                        <Input
                          value={String(costPolicyDraft.pricingVersion || '')}
                          placeholder="v1"
                          onChange={(v) => updateCostPolicy({ pricingVersion: String(v || '').trim() || undefined })}
                        />
                      </Col>
                    </Row>
                    <Alert
                      theme="warning"
                      message="上线前必须补计价：否则成功任务会进入“未定价”，无法自动扣套餐或钱包。下面的原始 JSON 会跟随上方表单自动更新，也可手工微调。"
                    />
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
                  title: '最近验证 / 使用',
                  minWidth: 220,
                  cell: ({ row }) => {
                    const lastCheck = getVendorKeyLastCheck(row);
                    const checkSuccess = lastCheck ? Boolean(lastCheck.success) : null;
                    return (
                      <Space direction="vertical" size={2}>
                        {lastCheck ? (
                          <Space size={4} style={{ flexWrap: 'wrap' }}>
                            <Tag theme={checkSuccess ? 'success' : 'warning'} variant="light">
                              {checkSuccess ? '验证通过' : '验证未通过'}
                            </Tag>
                            <Typography.Text theme="secondary" style={{ fontSize: 12 }}>
                              {lastCheck.checkedAt ? formatDateTime(String(lastCheck.checkedAt)) : '未记录时间'}
                            </Typography.Text>
                          </Space>
                        ) : (
                          <Typography.Text theme="secondary">未验证</Typography.Text>
                        )}
                        <Typography.Text theme="secondary" style={{ fontSize: 12 }}>
                          最近使用：{row.lastUsedAt ? formatDateTime(row.lastUsedAt) : '—'}
                        </Typography.Text>
                      </Space>
                    );
                  },
                },
                {
                  colKey: 'actions',
                  title: '操作',
                  width: 160,
                  cell: ({ row }) => (
                    <Space size={4}>
                      <Button size="small" variant="text" disabled={loading} onClick={() => onKeyCheck(row.id)}>
                        验证
                      </Button>
                      <Button size="small" variant="text" onClick={() => onKeyFormChange({ ...row })}>
                        编辑
                      </Button>
                    </Space>
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
              <Alert theme="info" message="这里写入中台密钥池；保存后只展示隐藏后的预览，Coze、前端和能力服务都不会长期持有明文。" />
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
                  保存到中台密钥池
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
