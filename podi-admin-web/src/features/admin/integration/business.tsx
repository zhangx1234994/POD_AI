import { Alert, Button, Card, Col, Dialog, Input, InputNumber, Row, Select, Space, Switch, Table, Tag, Textarea, Typography } from 'tdesign-react';

import type {
  BusinessCapability,
  BusinessCapabilityCompareResponse,
  BusinessCapabilityFormState,
  BusinessDefaultApproval,
  BusinessOperationLog,
  BusinessRecipeStep,
  BusinessRun,
  BusinessRunStep,
  BusinessUsageSummaryResponse,
  JsonRecord,
} from '../../../types/admin';
import { GuidanceQueueCard, StatusBadge, type GuidanceQueueItem } from '../shared/ui';
import {
  businessRunBillingStatusOptions,
  businessRunCallbackStatusOptions,
  businessRunIssueCategoryOptions,
  businessRunStatusOptions,
  businessUsageWindowOptions,
  statusOptions,
} from './formOptions';
import {
  formatBucketDigest,
  formatCurrencyTotals,
  formatDurationMs as formatPanelDurationMs,
  formatPriceValue,
  formatRatePercent,
} from './formatters';
import {
  businessBillingStatusLabel,
  businessBillingStatusTheme,
  businessCapabilityLatestRunLabel,
  businessCapabilityRunMetricsLabel,
  businessKeyLabel,
  businessRunStepStatusLabel,
  coreBusinessKeys,
} from './businessLabels';
import {
  buildCoreBusinessReleaseEvidenceRows,
  businessCapabilityHasRollbackEvidence,
  businessCapabilityRollbackEvidenceLabel,
} from './businessReleaseEvidence';
export {
  businessBillingStatusLabel,
  businessBillingStatusTheme,
  businessCapabilityLatestRunLabel,
  businessCapabilityRunMetricsLabel,
  businessKeyLabel,
  businessRunStepStatusLabel,
  coreBusinessKeys,
} from './businessLabels';

const formatShortBusinessId = (value?: string | null) => {
  const text = String(value || '').trim();
  if (!text) return '—';
  if (text.length <= 18) return text;
  return `${text.slice(0, 8)}…${text.slice(-5)}`;
};

const businessSourceLabel = (value?: string | null) => {
  const text = String(value || '').trim();
  const normalized = text.toLowerCase();
  if (!text) return '业务接口';
  if (normalized === 'business-api' || normalized === 'business_api' || normalized === 'api') return '业务接口';
  if (normalized === 'coze' || normalized.includes('coze')) return 'Coze';
  if (normalized === 'admin' || normalized === 'admin-test') return '管理端';
  if (normalized === 'eval' || normalized === 'eval-web') return '测评端';
  if (normalized === 'client' || normalized === 'web') return '客户端';
  return text;
};

const businessGovernanceIssueLabel = (value?: string | null) => {
  const labels: Record<string, string> = {
    BUSINESS_GOVERNANCE_PRIMARY_ABILITY_MISSING: '未绑定主能力',
    BUSINESS_GOVERNANCE_PRIMARY_ABILITY_NOT_FOUND: '主能力不存在',
    BUSINESS_GOVERNANCE_PRIMARY_ABILITY_INACTIVE: '主能力未启用',
    BUSINESS_GOVERNANCE_EXECUTABLE_STEP_MISSING: '配方没有可执行步骤',
    BUSINESS_GOVERNANCE_VENDOR_MODEL_NOT_FOUND: '模型目录不存在',
    BUSINESS_GOVERNANCE_VENDOR_MODEL_INACTIVE: '模型未启用',
    BUSINESS_GOVERNANCE_VENDOR_MODEL_ACCEPTANCE_REQUIRED: '模型未验收',
    BUSINESS_GOVERNANCE_VENDOR_MODEL_COST_MISSING: '模型成本未配置',
    BUSINESS_GOVERNANCE_VENDOR_KEY_MISSING: '第三方密钥不可用',
    BUSINESS_GOVERNANCE_VENDOR_EGRESS_NOT_VERIFIED: '出网未验证',
  };
  return labels[value || ''] || value || '暂无风险';
};

const businessGovernanceStatusLabel = (value?: string | null) => {
  if (value === 'ready') return '底层就绪';
  if (value === 'blocker') return '底层阻塞';
  if (value === 'warning') return '需要补齐';
  return '未检查';
};

const businessGovernanceStatusTheme = (value?: string | null): 'success' | 'warning' | 'danger' | 'default' => {
  if (value === 'ready') return 'success';
  if (value === 'blocker') return 'danger';
  if (value === 'warning') return 'warning';
  return 'default';
};

const businessAcceptanceStatusLabel = (value?: string | null) => {
  if (value === 'passed') return '验收通过';
  if (value === 'failed') return '验收失败';
  if (value === 'warning') return '有风险';
  if (value === 'waived') return '暂不验收';
  return '未验收';
};

const businessAcceptanceStatusTheme = (value?: string | null): 'success' | 'warning' | 'danger' | 'default' => {
  if (value === 'passed') return 'success';
  if (value === 'failed') return 'danger';
  if (value === 'warning') return 'warning';
  return 'default';
};

const businessReleaseGateStatusTheme = (value?: string | null): 'success' | 'warning' | 'danger' | 'default' => {
  if (value === 'ready') return 'success';
  if (value === 'warning') return 'warning';
  if (value === 'blocked') return 'danger';
  return 'default';
};

const businessReleaseGateLabel = (value?: string | null) => {
  if (value === 'ready') return '可上线';
  if (value === 'warning') return '需复核';
  if (value === 'blocked') return '暂不能上线';
  return '未判断';
};

type BusinessActionTheme = 'success' | 'warning' | 'danger' | 'default';
type BusinessActionPriority = '必须先处理' | '上线前处理' | '建议处理' | '可继续推进';

interface BusinessActionItem {
  theme: BusinessActionTheme;
  priority: BusinessActionPriority;
  title: string;
  detail: string;
  action: string;
}

const buildBusinessActionItems = ({
  capabilities,
  pendingApprovals,
  summary,
}: {
  capabilities: BusinessCapability[];
  pendingApprovals: BusinessDefaultApproval[];
  summary?: BusinessUsageSummaryResponse | null;
}) => {
  const windowHours = Number(summary?.windowHours || 24);
  const defaultActiveByKey = new Set(
    capabilities
      .filter((item) => item.isDefault && item.status === 'active')
      .map((item) => item.businessKey),
  );
  const missingDefaults = coreBusinessKeys.filter((key) => !defaultActiveByKey.has(key));
  const inactiveDefaults = capabilities.filter((item) => item.isDefault && item.status !== 'active');
  const failedDefaults = capabilities.filter((item) => item.isDefault && Number(item.runMetrics?.failed || 0) > 0);
  const missingPrimary = capabilities.filter((item) => item.isDefault && !item.primaryAbilityId && !item.primaryAbilityName);
  const governanceBlockedDefaults = capabilities.filter((item) => item.isDefault && item.governanceStatus === 'blocker');
  const governanceWarningDefaults = capabilities.filter((item) => item.isDefault && item.governanceStatus === 'warning');
  const acceptanceMissingDefaults = capabilities.filter(
    (item) => item.isDefault && item.status === 'active' && item.releaseGate?.acceptancePassed === false,
  );
  const rollbackWeakKeys = coreBusinessKeys.filter((businessKey) => {
    const versions = capabilities.filter((item) => item.businessKey === businessKey);
    return versions.some((item) => item.isDefault && item.status === 'active') &&
      versions.filter((item) => item.status === 'active' && !item.isDefault).length === 0;
  });
  const totalRuns = Number(summary?.total || 0);
  const items: BusinessActionItem[] = [];

  if (missingDefaults.length > 0) {
    items.push({
      theme: 'danger',
      priority: '必须先处理',
      title: '主业务缺默认版本',
      detail: `先补齐 ${missingDefaults.map((key) => businessKeyLabel(key)).join('、')} 的可用默认版本。`,
      action: '新增或启用业务版本，并设为默认入口。',
    });
  }
  if (inactiveDefaults.length > 0) {
    items.push({
      theme: 'danger',
      priority: '必须先处理',
      title: '默认版本未启用',
      detail: `${inactiveDefaults.map((item) => `${businessKeyLabel(item.businessKey)} ${item.version}`).join('、')} 需要先启用或切换默认。`,
      action: '启用当前默认版本，或切换到已验证的启用版本。',
    });
  }
  if (governanceBlockedDefaults.length > 0) {
    items.push({
      theme: 'danger',
      priority: '必须先处理',
      title: '默认版本底层不可用',
      detail: governanceBlockedDefaults
        .map((item) => `${businessKeyLabel(item.businessKey)}：${businessGovernanceIssueLabel(item.governanceIssues?.[0])}`)
        .join('；'),
      action: '先补主能力、模型或第三方密钥，再做真实链路测试。',
    });
  }
  if (governanceWarningDefaults.length > 0) {
    items.push({
      theme: 'warning',
      priority: '上线前处理',
      title: '默认版本配置需补齐',
      detail: governanceWarningDefaults
        .map((item) => `${businessKeyLabel(item.businessKey)}：${businessGovernanceIssueLabel(item.governanceIssues?.[0])}`)
        .join('；'),
      action: '补齐成本、模型治理信息，再进入收费或对外 API 验收。',
    });
  }
  if (acceptanceMissingDefaults.length > 0) {
    items.push({
      theme: 'danger',
      priority: '必须先处理',
      title: '默认版本未验收',
      detail: acceptanceMissingDefaults
        .map((item) => `${businessKeyLabel(item.businessKey)} ${item.version}`)
        .join('、'),
      action: '先跑真实链路测试，并在业务版本卡片记录“验收通过”。',
    });
  }
  if (pendingApprovals.length > 0) {
    items.push({
      theme: 'warning',
      priority: '上线前处理',
      title: '有默认版本审批',
      detail: `${pendingApprovals.length} 个切换申请待处理，先审批再对外说明版本。`,
      action: '进入默认版本审批，确认测评通过后再审批。',
    });
  }
  if (Number(summary?.failed || 0) > 0 || failedDefaults.length > 0) {
    items.push({
      theme: 'warning',
      priority: '上线前处理',
      title: '最近存在失败',
      detail: `近 ${windowHours} 小时失败 ${summary?.failed || 0} 次，先看最近失败和业务流程卡点。`,
      action: '筛选失败运行记录，按“版本、执行节点、回填、回调”定位。',
    });
  }
  if (Number(summary?.callbackFailed || 0) > 0) {
    items.push({
      theme: 'warning',
      priority: '上线前处理',
      title: '回调失败需处理',
      detail: `${summary?.callbackFailed || 0} 个业务回调失败，优先重试或确认业务方回调地址。`,
      action: '先重试回调；仍失败时让业务方确认回调地址和鉴权。',
    });
  }
  if (Number(summary?.unpriced || 0) > 0) {
    items.push({
      theme: 'warning',
      priority: '建议处理',
      title: '存在待定价调用',
      detail: `${summary?.unpriced || 0} 次成功调用未定价，先登记成本口径；正式收费前再补完整计费策略。`,
      action: '补模型成本或业务定价，避免后续账单无法解释。',
    });
  }
  if (missingPrimary.length > 0) {
    items.push({
      theme: 'warning',
      priority: '必须先处理',
      title: '默认版本缺主能力',
      detail: `${missingPrimary.map((item) => businessKeyLabel(item.businessKey)).join('、')} 需要绑定主执行能力，避免只剩配置壳。`,
      action: '编辑默认版本，绑定真实执行能力后再测试。',
    });
  }
  if (rollbackWeakKeys.length > 0) {
    items.push({
      theme: 'warning',
      priority: '建议处理',
      title: '回滚安全垫不足',
      detail: `${rollbackWeakKeys.map((key) => businessKeyLabel(key)).join('、')} 只有默认入口，出问题时不能快速回退。`,
      action: '保留一个启用的非默认版本，作为灰度或回滚目标。',
    });
  }
  if (items.length === 0 && totalRuns <= 0) {
    items.push({
      theme: 'warning',
      priority: '上线前处理',
      title: '近期没有调用样本',
      detail: `近 ${windowHours} 小时没有业务调用，不能只看配置判断稳定。`,
      action: '先跑 route-preview，再跑一次真实链路巡检。',
    });
  }
  if (items.length === 0) {
    items.push({
      theme: 'success',
      priority: '可继续推进',
      title: '主业务当前可继续推进',
      detail: '默认版本、最近失败和回调没有明显阻塞，可继续做小流量测试或接入新版本。',
      action: '进入测评端或小流量业务验证，保留回滚目标。',
    });
  }
  return items.slice(0, 5);
};

export const BusinessActionPanel = ({
  capabilities,
  pendingApprovals,
  summary,
}: {
  capabilities: BusinessCapability[];
  pendingApprovals: BusinessDefaultApproval[];
  summary?: BusinessUsageSummaryResponse | null;
}) => {
  const actionItems = buildBusinessActionItems({ capabilities, pendingApprovals, summary });
  const guidanceItems: GuidanceQueueItem[] = actionItems.map((item) => ({
    key: `${item.priority}-${item.title}-${item.detail}`,
    theme: item.theme,
    priority: item.priority,
    title: item.title,
    detail: item.detail,
    action: item.action,
  }));
  return (
    <GuidanceQueueCard items={guidanceItems} maxItems={5} />
  );
};

export const BusinessReleaseGuardPanel = ({
  capabilities,
  pendingApprovals,
  summary,
}: {
  capabilities: BusinessCapability[];
  pendingApprovals: BusinessDefaultApproval[];
  summary?: BusinessUsageSummaryResponse | null;
}) => {
  const rows = coreBusinessKeys.map((businessKey) => {
    const versions = capabilities.filter((item) => item.businessKey === businessKey);
    const defaultVersion = versions.find((item) => item.isDefault);
    const rollbackVersions = versions.filter((item) => item.status === 'active' && !item.isDefault);
    const rollbackReadyVersions = rollbackVersions.filter(businessCapabilityHasRollbackEvidence);
    const hasPendingApproval = pendingApprovals.some((item) => item.businessKey === businessKey && item.status === 'pending');
    const failedCount = versions
      .filter((item) => item.isDefault)
      .reduce((total, item) => total + Number(item.runMetrics?.failed || 0), 0);
    const latestDefaultError = defaultVersion?.latestRun?.error || '';
    const governanceStatus = defaultVersion?.governanceStatus || 'unknown';
    const firstGovernanceIssue = defaultVersion?.governanceIssues?.[0] || '';
    const governanceBlocked = governanceStatus === 'blocker';
    const releaseGate = defaultVersion?.releaseGate || null;
    const acceptancePassed = defaultVersion ? releaseGate?.acceptancePassed === true : false;
    const defaultReady = Boolean(
      defaultVersion &&
      defaultVersion.status === 'active' &&
      (defaultVersion.primaryAbilityId || defaultVersion.primaryAbilityName) &&
      !governanceBlocked &&
      acceptancePassed &&
      releaseGate?.status !== 'blocked',
    );
    const rollbackReady = rollbackReadyVersions.length > 0;
    const blockedReason = !defaultVersion
      ? '缺少默认版本'
      : defaultVersion.status !== 'active'
        ? '默认版本未启用'
        : !(defaultVersion.primaryAbilityId || defaultVersion.primaryAbilityName)
          ? '默认版本缺主能力'
            : governanceBlocked
              ? businessGovernanceIssueLabel(firstGovernanceIssue) || '底层配置阻塞'
              : !acceptancePassed
                ? '默认版本未验收'
                : hasPendingApproval
                  ? '有切换审批待处理'
                  : failedCount > 0 || latestDefaultError
                    ? '默认版本最近失败'
                    : '';
    return {
      businessKey,
      name: businessKeyLabel(businessKey),
      defaultVersion,
      rollbackVersions,
      rollbackReadyVersions,
      hasPendingApproval,
      failedCount,
      latestDefaultError,
      defaultReady,
      rollbackReady,
      blockedReason,
      governanceStatus,
      firstGovernanceIssue,
      releaseGate,
      acceptancePassed,
    };
  });
  const blockedCount = rows.filter((row) => row.blockedReason).length;
  const rollbackMissingCount = rows.filter((row) => !row.rollbackReady).length;
  const callbackFailed = Number(summary?.callbackFailed || 0);
  const unpriced = Number(summary?.unpriced || 0);
  const canRelease = blockedCount === 0 && callbackFailed === 0;

  return (
    <Card
      bordered
      title={
        <Space align="center" style={{ justifyContent: 'space-between', width: '100%', flexWrap: 'wrap' }}>
          <div>
            <Typography.Text strong>上线 / 切换前检查</Typography.Text>
            <div>
              <Typography.Text theme="secondary">
                涉及默认版本、回滚、停用的动作都会影响业务入口；先看这里，再处理审批或回滚。
              </Typography.Text>
            </div>
          </div>
          <Tag theme={canRelease ? (rollbackMissingCount > 0 || unpriced > 0 ? 'warning' : 'success') : 'danger'} variant="light">
            {canRelease ? (rollbackMissingCount > 0 || unpriced > 0 ? '可小流量，需补安全垫' : '可进入测评') : `阻塞 ${blockedCount + (callbackFailed > 0 ? 1 : 0)}`}
          </Tag>
        </Space>
      }
    >
      <Space direction="vertical" size="small" style={{ width: '100%' }}>
        <Alert
          theme={canRelease ? 'info' : 'warning'}
          message={
            canRelease
              ? '默认入口没有明显阻塞。发布前仍需要跑测评端真实链路，确认 Coze 到中台再到能力服务的结果回填。'
              : '存在默认入口或回调风险。处理完成前，不建议切默认版本或对外说明新版本已可用。'
          }
        />
        <Table
          size="small"
          rowKey="businessKey"
          data={rows}
          columns={[
            {
              colKey: 'name',
              title: '主业务',
              width: 130,
              cell: ({ row }) => <Typography.Text strong>{row.name}</Typography.Text>,
            },
            {
              colKey: 'default',
              title: '默认入口',
              minWidth: 240,
              cell: ({ row }) => (
                <Space direction="vertical" size={2}>
                  <Space size={6}>
                    <Tag theme={row.defaultReady ? 'success' : 'danger'} variant="light">
                      {row.defaultReady ? '可用' : '需处理'}
                    </Tag>
                    <Typography.Text>
                      {row.defaultVersion ? `${row.defaultVersion.version} · ${row.defaultVersion.displayName}` : '未设置'}
                    </Typography.Text>
                  </Space>
                  <Typography.Text theme="secondary">
                    {row.defaultVersion?.primaryAbilityName || row.defaultVersion?.primaryAbilityId || '未绑定主能力'}
                  </Typography.Text>
                  {row.defaultVersion ? (
                    <Space size={6} breakLine>
                      <Tag theme={businessReleaseGateStatusTheme(row.releaseGate?.status)} variant="light">
                        {row.releaseGate?.label || businessReleaseGateLabel(row.releaseGate?.status)}
                      </Tag>
                      <Tag theme={businessGovernanceStatusTheme(row.governanceStatus)} variant="light">
                        {businessGovernanceStatusLabel(row.governanceStatus)}
                      </Tag>
                      <Tag theme={businessAcceptanceStatusTheme(row.defaultVersion.latestAcceptance?.status)} variant="light">
                        {businessAcceptanceStatusLabel(row.defaultVersion.latestAcceptance?.status)}
                      </Tag>
                      {row.firstGovernanceIssue ? (
                        <Typography.Text theme={row.governanceStatus === 'blocker' ? 'error' : 'warning'}>
                          {businessGovernanceIssueLabel(row.firstGovernanceIssue)}
                        </Typography.Text>
                      ) : null}
                    </Space>
                  ) : null}
                </Space>
              ),
            },
            {
              colKey: 'rollback',
              title: '回滚安全垫',
              minWidth: 260,
              cell: ({ row }) => (
                <Space direction="vertical" size={2}>
                  <Tag theme={row.rollbackReady ? 'success' : 'warning'} variant="light">
                    {row.rollbackReady
                      ? `${row.rollbackReadyVersions.length} 个可回滚`
                      : row.rollbackVersions.length > 0
                        ? `${row.rollbackVersions.length} 个备选待验收`
                        : '缺备选'}
                  </Tag>
                  <Typography.Text theme="secondary">
                    {row.rollbackVersions.length > 0
                      ? row.rollbackVersions.slice(0, 2).map((item: BusinessCapability) => businessCapabilityRollbackEvidenceLabel(item)).join('；')
                      : '建议保留一个启用的非默认版本'}
                  </Typography.Text>
                  {row.rollbackVersions.length > 2 ? (
                    <Typography.Text theme="secondary">还有 {row.rollbackVersions.length - 2} 个备选版本，进入版本卡片查看。</Typography.Text>
                  ) : null}
                </Space>
              ),
            },
            {
              colKey: 'risk',
              title: '当前风险',
              minWidth: 260,
              cell: ({ row }) => (
                <Space direction="vertical" size={2}>
                  <Tag theme={row.blockedReason ? 'warning' : 'success'} variant="light">
                    {row.blockedReason || '暂无阻塞'}
                  </Tag>
                  <Typography.Text theme={row.latestDefaultError ? 'error' : 'secondary'}>
                    {row.latestDefaultError ||
                      row.releaseGate?.suggestions?.[0] ||
                      (row.firstGovernanceIssue
                        ? businessGovernanceIssueLabel(row.firstGovernanceIssue)
                        : row.failedCount > 0
                          ? `近24小时失败 ${row.failedCount} 次`
                          : '默认版本最近无失败样本')}
                  </Typography.Text>
                  {row.hasPendingApproval ? <Typography.Text theme="warning">存在默认版本切换审批，请先处理。</Typography.Text> : null}
                </Space>
              ),
            },
            {
              colKey: 'action',
              title: '建议动作',
              minWidth: 260,
              cell: ({ row }) => {
                const suggestion = row.blockedReason
                  ? row.firstGovernanceIssue
                    ? '先补齐底层能力、模型、密钥或成本配置，再跑真实链路。'
                    : '先处理风险，再做版本切换。'
                  : row.rollbackReady
                    ? '可进入测评端做真实链路验证。'
                    : row.rollbackVersions.length > 0
                      ? '先给备选版本补验收通过和成功输出证据，再做默认切换。'
                      : '先补一个启用的备选版本，避免切换后无法快速回滚。';
                return <Typography.Text theme="secondary">{suggestion}</Typography.Text>;
              },
            },
          ]}
        />
        {(callbackFailed > 0 || unpriced > 0) ? (
          <Alert
            theme="warning"
            message={[
              callbackFailed > 0 ? `当前还有 ${callbackFailed} 次回调失败，业务方可能拿不到结果。` : '',
              unpriced > 0 ? `${unpriced} 次成功调用未定价，正式收费前需要补成本口径。` : '',
            ].filter(Boolean).join(' ')}
          />
        ) : null}
      </Space>
    </Card>
  );
};

export const businessOperationActionLabel = (action?: string | null) => {
  if (action === 'business_capability_create') return '新增版本';
  if (action === 'business_capability_update') return '修改配置';
  if (action === 'business_capability_set_default') return '设为默认';
  if (action === 'business_capability_status_change') return '启停版本';
  if (action === 'business_capability_rollback') return '回滚默认版';
  if (action === 'business_capability_default_approval_create') return '申请切默认';
  if (action === 'business_capability_default_approval_apply') return '审批通过';
  if (action === 'business_capability_default_approval_reject') return '审批驳回';
  if (action === 'record_acceptance') return '记录验收';
  return action || '操作';
};

export const businessOperationTargetLabel = (item: BusinessOperationLog) => {
  const payload = item.afterPayload || item.beforePayload || {};
  const nestedTarget = typeof payload.target === 'object' && payload.target !== null && !Array.isArray(payload.target)
    ? (payload.target as JsonRecord)
    : null;
  const snapshot = nestedTarget || payload;
  const version = typeof snapshot.version === 'string' ? snapshot.version : '';
  const displayName =
    typeof snapshot.displayName === 'string'
      ? snapshot.displayName
      : typeof snapshot.display_name === 'string'
        ? snapshot.display_name
        : '';
  return [businessKeyLabel(item.businessKey), version, displayName].filter(Boolean).join(' · ');
};

export const formatBusinessCompareValue = (value: unknown) => {
  if (value === null || value === undefined || value === '') return '—';
  if (typeof value === 'boolean') return value ? '是' : '否';
  if (typeof value === 'object') return JSON.stringify(value, null, 2);
  return String(value);
};

export const businessCompareFieldLabel = (field?: string | null) => {
  const labels: Record<string, string> = {
    business_key: '业务类型',
    version: '版本号',
    display_name: '版本名称',
    description: '说明',
    status: '状态',
    is_default: '默认版本',
    release_time: '发布时间',
    primary_ability_id: '主能力编号',
    primary_ability_name: '主能力名称',
    primary_ability_provider: '主能力厂商',
    vendor_model_id: '模型编号',
    vendor_model_name: '模型名称',
    vendor_model_provider: '模型厂商',
    recipe: '业务配方',
    input_schema: '入参表单',
    output_schema: '出参结构',
    extra_metadata: '发布策略',
  };
  return labels[field || ''] || field || '字段';
};

type BusinessOption = {
  label: string;
  value: string;
  disabled?: boolean;
};

const BusinessCompareValueBlock = ({ value }: { value: unknown }) => (
  <pre
    style={{
      margin: 0,
      padding: 10,
      borderRadius: 8,
      border: '1px solid var(--td-border-level-1-color)',
      background: 'var(--td-bg-color-secondarycontainer)',
      color: 'var(--td-text-color-primary)',
      fontSize: 12,
      lineHeight: 1.5,
      maxHeight: 140,
      overflow: 'auto',
      whiteSpace: 'pre-wrap',
      wordBreak: 'break-word',
    }}
  >
    {formatBusinessCompareValue(value)}
  </pre>
);

const BusinessMetricCard = ({ label, value, sub }: { label: string; value: number | string; sub?: string }) => (
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

export const BusinessUsageSummaryPanel = ({
  summary,
  windowHours,
  formatDateTime,
}: {
  summary?: BusinessUsageSummaryResponse | null;
  windowHours: number;
  formatDateTime: (value?: string | null) => string;
}) => (
  <Card
    bordered
    title={
      <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
        <div>
          <Typography.Text strong>业务调用统计</Typography.Text>
          <div>
            <Typography.Text theme="secondary">
              当前筛选 · {summary?.windowHours || windowHours} 小时窗口
            </Typography.Text>
          </div>
        </div>
        <Tag theme={Number(summary?.failed || 0) > 0 ? 'warning' : 'success'} variant="light">
          {Number(summary?.failed || 0) > 0 ? '存在失败样本' : '暂无失败样本'}
        </Tag>
      </Space>
    }
  >
    <Row gutter={[12, 12]}>
      <Col xs={12} sm={6} lg={2}>
        <BusinessMetricCard label="总调用" value={summary?.total ?? 0} sub="业务入口调用数" />
      </Col>
      <Col xs={12} sm={6} lg={2}>
        <BusinessMetricCard
          label="成功率"
          value={formatRatePercent(summary?.successRate)}
          sub={`失败 ${summary?.failed ?? 0} 次`}
        />
      </Col>
      <Col xs={12} sm={6} lg={2}>
        <BusinessMetricCard
          label="执行中"
          value={(summary?.running ?? 0) + (summary?.queued ?? 0)}
          sub={`排队 ${summary?.queued ?? 0}`}
        />
      </Col>
      <Col xs={12} sm={6} lg={2}>
        <BusinessMetricCard
          label="平均耗时"
          value={formatPanelDurationMs(summary?.avgDurationMs)}
          sub="仅统计已记录耗时"
        />
      </Col>
      <Col xs={12} sm={6} lg={2}>
        <BusinessMetricCard
          label="可计费成本"
          value={formatCurrencyTotals(summary?.costByCurrency)}
          sub={`实际 ${formatCurrencyTotals(summary?.actualCostByCurrency)} · 不计费 ${summary?.noCharge ?? 0}`}
        />
      </Col>
      <Col xs={12} sm={6} lg={2}>
        <BusinessMetricCard
          label="回调"
          value={summary?.callbackFailed ?? 0}
          sub={`失败 ${summary?.callbackFailed ?? 0} · 成功 ${summary?.callbackSuccess ?? 0}`}
        />
      </Col>
    </Row>
    {Number((summary?.unresolvedIssues || []).reduce((total, bucket) => total + Number(bucket.total || 0), 0)) > 0 ? (
      <Alert
        theme="warning"
        style={{ marginTop: 12 }}
        message={`仍有 ${Number((summary?.unresolvedIssues || []).reduce((total, bucket) => total + Number(bucket.total || 0), 0))} 条问题未确认恢复。优先筛选问题类型，批量复测后再看是否恢复。`}
      />
    ) : null}
    <Row gutter={[12, 12]} style={{ marginTop: 12 }}>
      <Col xs={12} lg={3}>
        <Card bordered>
          <Space direction="vertical" size="small" style={{ width: '100%' }}>
            <Typography.Text strong>业务分布</Typography.Text>
            {(summary?.byBusiness || []).slice(0, 4).map((bucket) => (
              <Space key={bucket.key} align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
                <Typography.Text>{businessKeyLabel(bucket.key)}</Typography.Text>
                <Typography.Text theme={bucket.failed > 0 ? 'warning' : 'secondary'}>
                  {formatBucketDigest(bucket)}
                </Typography.Text>
              </Space>
            ))}
            {(summary?.byBusiness || []).length === 0 ? (
              <Typography.Text theme="secondary">当前筛选下暂无调用。</Typography.Text>
            ) : null}
          </Space>
        </Card>
      </Col>
      <Col xs={12} lg={3}>
        <Card bordered>
          <Space direction="vertical" size="small" style={{ width: '100%' }}>
            <Typography.Text strong>来源 / 业务方</Typography.Text>
            {(summary?.bySource || []).slice(0, 3).map((bucket) => (
              <Space key={bucket.key} align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
                <Typography.Text>{bucket.label}</Typography.Text>
                <Typography.Text theme={bucket.failed > 0 ? 'warning' : 'secondary'}>
                  {formatBucketDigest(bucket)}
                </Typography.Text>
              </Space>
            ))}
            {(summary?.byTenant || []).slice(0, 3).map((bucket) => (
              <Space key={`tenant:${bucket.key}`} align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
                <Typography.Text theme="secondary">业务方：{bucket.label}</Typography.Text>
                <Typography.Text theme={bucket.failed > 0 ? 'warning' : 'secondary'}>
                  {formatBucketDigest(bucket)}
                </Typography.Text>
              </Space>
            ))}
            {(summary?.bySource || []).length === 0 && (summary?.byTenant || []).length === 0 ? (
              <Typography.Text theme="secondary">当前筛选下暂无来源数据。</Typography.Text>
            ) : null}
          </Space>
        </Card>
      </Col>
      <Col xs={12} lg={3}>
        <Card bordered>
          <Space direction="vertical" size="small" style={{ width: '100%' }}>
            <Typography.Text strong>链路问题</Typography.Text>
            {(summary?.byIssue || []).slice(0, 5).map((bucket) => (
              <Space key={bucket.key} align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
                <Space size={6}>
                  <Tag theme={businessIssueTheme(bucket.severity)} variant="light">
                    {businessIssueLabel(bucket.key, bucket.label)}
                  </Tag>
                </Space>
                <Typography.Text theme={bucket.failed > 0 ? 'warning' : 'secondary'}>
                  {formatBucketDigest(bucket)}
                </Typography.Text>
              </Space>
            ))}
            {(summary?.byIssue || []).length === 0 ? (
              <Typography.Text theme="secondary">当前筛选下暂无链路问题分类。</Typography.Text>
            ) : null}
            {(summary?.unresolvedIssues || []).slice(0, 4).map((bucket) => (
              <Space key={`unresolved:${bucket.key}`} align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
                <Typography.Text theme="warning">
                  未恢复：{businessIssueLabel(bucket.key, bucket.label)}
                </Typography.Text>
                <Typography.Text theme="warning">
                  {bucket.total} 条 · 已复测 {bucket.retested || 0}
                </Typography.Text>
              </Space>
            ))}
          </Space>
        </Card>
      </Col>
      <Col xs={12} lg={3}>
        <Card bordered>
          <Space direction="vertical" size="small" style={{ width: '100%' }}>
            <Typography.Text strong>最近失败</Typography.Text>
            {(summary?.recentFailures || []).slice(0, 4).map((item) => (
              <Space key={item.id} direction="vertical" size={2} style={{ width: '100%' }}>
                <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
                  <Typography.Text>{businessKeyLabel(item.businessKey)} · {item.version || '未标记版本'}</Typography.Text>
                  <Typography.Text theme="secondary">{formatDateTime(item.createdAt)}</Typography.Text>
                </Space>
                <Typography.Text theme="error">{item.error || '失败原因未记录'}</Typography.Text>
              </Space>
            ))}
            {(summary?.recentFailures || []).length === 0 ? (
              <Typography.Text theme="secondary">当前筛选下暂无失败记录。</Typography.Text>
            ) : null}
            {(summary?.recentUnresolvedIssues || []).slice(0, 3).map((item) => (
              <Space key={`unresolved:${item.id}`} direction="vertical" size={2} style={{ width: '100%' }}>
                <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
                  <Typography.Text theme="warning">
                    未恢复：{businessKeyLabel(item.businessKey)} · {businessIssueLabel(item.issueCategory, item.issueLabel)}
                  </Typography.Text>
                  <Typography.Text theme="secondary">{formatDateTime(item.createdAt)}</Typography.Text>
                </Space>
                <Typography.Text theme="secondary">
                  复测 {item.retestAttempts || 0} 次 · {businessRetestStatusLabel(item.retestLatestStatus)}
                </Typography.Text>
              </Space>
            ))}
          </Space>
        </Card>
      </Col>
    </Row>
  </Card>
);

type BusinessRunFilters = {
  windowHours: number;
  businessKey: string;
  version: string;
  status: string;
  billingStatus: string;
  callbackStatus: string;
  issueCategory: string;
  source: string;
  tenantId: string;
  clientId: string;
  traceId: string;
  limit: number;
};

type BusinessSelectOption = {
  label: string;
  value: string | number;
};

const formatJsonValue = (value?: unknown) => {
  if (value === undefined || value === null) return '';
  return JSON.stringify(value, null, 2);
};

const asJsonRecord = (value?: unknown): JsonRecord => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return {};
  return value as JsonRecord;
};

const recordText = (record: JsonRecord, key: string, fallback = '—') => {
  const value = record[key];
  if (value === undefined || value === null || value === '') return fallback;
  return String(value);
};

const businessBillingReasonLabel = (row?: BusinessRun | null) => {
  if (!row) return '';
  if (row.billingStatus === 'no_charge') {
    if (row.noChargeReason === 'failed') return '失败不扣费';
    if (row.noChargeReason === 'cancelled') return '取消不扣费';
    if (row.noChargeReason === 'timeout') return '超时不扣费';
    return row.noChargeReason ? `不计费：${row.noChargeReason}` : '不计费';
  }
  if (row.billingStatus === 'unpriced') return '成功但未配置价格';
  if (row.billingStatus === 'billing_pending') return '任务未结束，暂不计费';
  if (row.billingStatus === 'billable' && !getBusinessWalletSettlement(row) && row.userId) {
    return '待确认套餐或钱包扣减';
  }
  return '';
};

const businessIssueTheme = (severity?: string | null): 'success' | 'warning' | 'danger' | 'default' => {
  if (severity === 'danger') return 'danger';
  if (severity === 'warning') return 'warning';
  if (severity === 'success') return 'success';
  return 'default';
};

const businessIssueLabel = (category?: string | null, fallback?: string | null) => {
  if (fallback) return fallback;
  if (category === 'executor') return '执行节点问题';
  if (category === 'output') return '结果回填问题';
  if (category === 'callback') return '业务回调问题';
  if (category === 'billing') return '计费扣减问题';
  if (category === 'parameter') return '参数问题';
  if (category === 'version') return '版本/路由问题';
  if (category === 'none') return '暂无明显问题';
  return '未分类';
};

const businessRetestStatusLabel = (status?: string | null) => {
  const value = String(status || '').toLowerCase();
  if (value === 'succeeded') return '复测成功';
  if (value === 'failed') return '复测失败';
  if (value === 'running') return '复测执行中';
  if (value === 'queued') return '复测排队中';
  if (value === 'cancelled') return '复测已取消';
  return '暂未复测';
};

const businessRetestTheme = (row?: BusinessRun | null): 'success' | 'warning' | 'danger' | 'default' => {
  if (!row) return 'default';
  if (row.retestRecovered) return 'success';
  const status = String(row.retestLatestStatus || '').toLowerCase();
  if (status === 'failed' || status === 'cancelled') return 'danger';
  if (status === 'queued' || status === 'running') return 'warning';
  return Number(row.retestAttempts || 0) > 0 ? 'warning' : 'default';
};

const businessRunRouteLabel = (routeInfo?: JsonRecord | null) => {
  const route = (routeInfo || {}) as JsonRecord;
  const selectedBy = String(route.selectedBy || 'default');
  const percent = route.rolloutPercent;
  if (selectedBy === 'explicit') return '指定版本';
  if (selectedBy === 'rollout_allowlist') return '灰度名单';
  if (selectedBy === 'rollout_percent') return `灰度比例 ${percent ?? ''}%`;
  return '默认版本';
};

type BusinessRunFlowStageTheme = 'success' | 'warning' | 'danger' | 'primary' | 'default';

type BusinessRunFlowStage = {
  title: string;
  result: string;
  detail: string;
  hint?: string;
  theme: BusinessRunFlowStageTheme;
};

const hasBusinessEvidenceValue = (value?: unknown) => {
  if (value === undefined || value === null) return false;
  return String(value).trim() !== '';
};

const recordNumber = (record: JsonRecord, key: string, fallback = 0) => {
  const value = Number(record[key]);
  return Number.isFinite(value) ? value : fallback;
};

const businessRunIsFinished = (status?: string | null) => {
  const normalized = String(status || '').toLowerCase();
  return normalized === 'succeeded' || normalized === 'success' || normalized === 'completed';
};

const businessRunIsFailed = (status?: string | null) => {
  const normalized = String(status || '').toLowerCase();
  return normalized === 'failed' || normalized === 'error' || normalized === 'cancelled' || normalized === 'timeout';
};

const businessRunIsActive = (status?: string | null) => {
  const normalized = String(status || '').toLowerCase();
  return normalized === 'queued' || normalized === 'running' || normalized === 'pending';
};

const businessFlowStageColor = (theme: BusinessRunFlowStageTheme) => {
  if (theme === 'success') return 'var(--td-success-color)';
  if (theme === 'warning') return 'var(--td-warning-color)';
  if (theme === 'danger') return 'var(--td-error-color)';
  if (theme === 'primary') return 'var(--td-brand-color)';
  return 'var(--td-border-level-2-color)';
};

const buildBusinessRunFlowStages = (detail: BusinessRun): BusinessRunFlowStage[] => {
  const route = asJsonRecord(detail.flowSummary?.route);
  const ability = asJsonRecord(detail.flowSummary?.ability);
  const executor = asJsonRecord(detail.flowSummary?.executor);
  const output = asJsonRecord(detail.flowSummary?.output);
  const callback = asJsonRecord(detail.flowSummary?.callback);
  const finished = businessRunIsFinished(detail.status);
  const failed = businessRunIsFailed(detail.status);
  const active = businessRunIsActive(detail.status);

  const routeVersion = recordText(route, 'version', detail.version || '—');
  const routeCapabilityId = recordText(route, 'selectedCapabilityId', detail.abilityId || '');
  const routeOk = hasBusinessEvidenceValue(routeVersion) && routeVersion !== '—';

  const abilityName = recordText(ability, 'name', detail.abilityName || detail.abilityId || '');
  const abilityTaskId = recordText(ability, 'taskId', detail.abilityTaskId || detail.taskId || '');
  const abilityOk = hasBusinessEvidenceValue(abilityName) || hasBusinessEvidenceValue(abilityTaskId);

  const executorName = recordText(executor, 'name', '');
  const executorId = recordText(executor, 'id', '');
  const executorType = recordText(executor, 'type', '');
  const executorOk = hasBusinessEvidenceValue(executorName) || hasBusinessEvidenceValue(executorId);

  const imageCount = recordNumber(output, 'imageCount', detail.imageUrls?.length || 0);
  const videoCount = recordNumber(output, 'videoCount', detail.videoUrls?.length || 0);
  const textCount = recordNumber(output, 'textCount', detail.texts?.length || 0);
  const structuredCount = recordNumber(output, 'structuredCount', 0);
  const resourceCount = recordNumber(output, 'resourceCount', 0);
  const hasOutput = Boolean(output.hasOutput) || imageCount > 0 || videoCount > 0 || textCount > 0 || structuredCount > 0 || resourceCount > 0;
  const hasOssOutput = Boolean(output.hasOssOutput);

  const callbackStatus = recordText(callback, 'status', detail.callbackStatus || '');
  const callbackHttpStatus = recordText(callback, 'httpStatus', detail.callbackHttpStatus ? String(detail.callbackHttpStatus) : '');
  const callbackError = recordText(callback, 'error', detail.callbackError || '');
  const callbackConfigured =
    hasBusinessEvidenceValue(callbackStatus) || hasBusinessEvidenceValue(callbackHttpStatus) || hasBusinessEvidenceValue(callbackError);
  const callbackFailed =
    callbackStatus === 'failed' ||
    callbackError !== '' ||
    (hasBusinessEvidenceValue(callbackHttpStatus) && Number(callbackHttpStatus) >= 400);
  const settlement = getBusinessWalletSettlement(detail);
  const settlementStatus = String(settlement?.status || '').toLowerCase();
  const billingStatus = String(detail.billingStatus || '').toLowerCase();
  const billingSettled = settlementStatus === 'settled';
  const billingFailed = settlementStatus === 'failed';
  const billingPending = billingStatus === 'billing_pending' || (billingStatus === 'billable' && !settlement);
  const billingNoCharge = billingStatus === 'no_charge';
  const billingUnpriced = billingStatus === 'unpriced';

  return [
    {
      title: '版本选择',
      result: routeOk ? '已确定业务版本' : '未确认版本',
      detail: `${routeVersion} · ${businessRunRouteLabel(detail.routeInfo)}`,
      hint: routeCapabilityId ? `对应能力：${formatShortBusinessId(routeCapabilityId)}` : '需要确认默认版本是否生效。',
      theme: routeOk ? 'success' : failed ? 'danger' : 'warning',
    },
    {
      title: '能力下发',
      result: abilityOk ? '已下发到原子能力' : active ? '等待下发' : '未见能力任务',
      detail: abilityName || detail.abilityName || detail.abilityId || '未记录能力',
      hint: abilityTaskId ? `排障编号：${formatShortBusinessId(abilityTaskId)}` : '若任务已失败，先查业务版本是否绑定了能力。',
      theme: abilityOk ? 'success' : failed ? 'danger' : 'warning',
    },
    {
      title: '执行节点',
      result: executorOk ? '已命中执行节点' : abilityOk && active ? '等待调度节点' : '未见执行节点',
      detail: executorName || executorId || '未记录节点',
      hint: executorOk ? [formatShortBusinessId(executorId), executorType].filter(Boolean).join(' · ') : '需检查节点健康、标签、并发和路由规则。',
      theme: executorOk ? 'success' : failed && abilityOk ? 'danger' : abilityOk ? 'warning' : 'default',
    },
    {
      title: '输出回填',
      result: hasOutput ? (hasOssOutput ? '结果已回填' : '有结果，未确认自有链接') : finished ? '完成但无结果' : '等待结果',
      detail: `图 ${imageCount} · 视频 ${videoCount} · 文字 ${textCount} · 结构化 ${structuredCount} · 资源 ${resourceCount}`,
      hint: hasOutput
        ? hasOssOutput
          ? '业务侧可直接取结果。'
          : '有输出但未确认 OSS 回填，需防止外链过期。'
        : finished
          ? '完成状态没有结果，优先查输出解析和 OSS 回填。'
          : '未完成任务先看执行节点和队列状态。',
      theme: hasOutput ? (hasOssOutput ? 'success' : 'warning') : finished ? 'danger' : active ? 'warning' : 'default',
    },
    {
      title: '业务回调',
      result: callbackConfigured ? businessCallbackStatusLabel(callbackStatus) : '未配置回调',
      detail: callbackHttpStatus ? `HTTP ${callbackHttpStatus}` : callbackError || '无回调地址或无需回调',
      hint: callbackFailed ? '先重试回调；若仍失败，检查业务方地址和签名。' : '回调不影响已回填结果，但会影响业务方自动接收。',
      theme: callbackFailed ? 'danger' : callbackStatus === 'success' ? 'success' : callbackStatus === 'running' ? 'warning' : 'default',
    },
    {
      title: '计费扣减',
      result: billingSettled
        ? businessWalletStatusLabel(settlement)
        : billingFailed
          ? '扣减失败'
          : billingUnpriced
            ? '成功但未定价'
            : billingNoCharge
              ? '本次不计费'
              : billingPending
                ? '等待计费确认'
                : businessBillingStatusLabel(detail.billingStatus),
      detail: businessWalletSummary(settlement),
      hint: billingFailed
        ? settlement?.error || '先修复套餐或钱包扣减，再重试计费。'
        : billingUnpriced
          ? '先补模型成本或业务价格规则，否则无法进入收费闭环。'
          : billingPending
            ? '任务完成后会继续确认计费；如长期停留，检查业务结算日志。'
            : billingNoCharge
              ? businessBillingReasonLabel(detail) || '该业务按规则不收费。'
              : settlement?.traceId
                ? `流水：${formatShortBusinessId(settlement.traceId)}`
                : '未产生套餐或钱包流水。',
      theme: billingSettled
        ? 'success'
        : billingFailed
          ? 'danger'
          : billingUnpriced || billingPending
            ? 'warning'
            : 'default',
    },
  ];
};

const businessRunPriorityStage = (detail: BusinessRun) => {
  const stages = buildBusinessRunFlowStages(detail);
  return (
    stages.find((stage) => stage.theme === 'danger') ||
    stages.find((stage) => stage.theme === 'warning') ||
    stages.find((stage) => stage.theme === 'primary') ||
    stages[0]
  );
};

const businessRunPriorityStageMessage = (detail: BusinessRun) => {
  if (detail.issueCategory && detail.issueCategory !== 'none') {
    const theme =
      detail.issueSeverity === 'danger' ? 'error' : detail.issueSeverity === 'warning' ? 'warning' : 'info';
    return {
      theme: theme as 'error' | 'warning' | 'info',
      title: businessIssueLabel(detail.issueCategory, detail.issueLabel),
      message: [detail.issueEvidence, detail.issueAction].filter(Boolean).join('。') || '查看链路判断和步骤证据。',
    };
  }
  const stage = businessRunPriorityStage(detail);
  if (!stage) {
    return {
      theme: 'info' as const,
      title: '暂无链路证据',
      message: '这条业务调用还没有记录到足够的链路证据，先刷新运行记录或查看原始排障数据。',
    };
  }
  const theme: 'error' | 'warning' | 'success' =
    stage.theme === 'danger' ? 'error' : stage.theme === 'warning' ? 'warning' : 'success';
  return {
    theme,
    title: stage.theme === 'danger' ? `优先处理：${stage.title}` : stage.theme === 'warning' ? `需要确认：${stage.title}` : `链路正常：${stage.title}`,
    message: [stage.result, stage.detail, stage.hint].filter(Boolean).join('。'),
  };
};

function BusinessRunNextActionAlert({ detail }: { detail: BusinessRun }) {
  const item = businessRunPriorityStageMessage(detail);
  return <Alert theme={item.theme} message={`${item.title}：${item.message}`} />;
}

function BusinessRunFlowEvidenceBar({ detail }: { detail: BusinessRun }) {
  const stages = buildBusinessRunFlowStages(detail);
  return (
    <Card bordered title="业务链路判定">
      <Space direction="vertical" size="small" style={{ width: '100%' }}>
        <Typography.Text theme="secondary">
          按业务真实链路分段查看：红色优先处理，黄色表示等待或证据不足。
        </Typography.Text>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
            gap: 10,
          }}
        >
          {stages.map((stage, index) => (
            <div
              key={stage.title}
              style={{
                border: '1px solid var(--td-border-level-1-color)',
                borderTop: `3px solid ${businessFlowStageColor(stage.theme)}`,
                borderRadius: 12,
                padding: 12,
                background: 'var(--td-bg-color-container)',
                minHeight: 142,
              }}
            >
              <Space direction="vertical" size={6} style={{ width: '100%' }}>
                <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
                  <Typography.Text strong>{stage.title}</Typography.Text>
                  <Tag variant="light" theme={stage.theme as any}>
                    {index + 1}
                  </Tag>
                </Space>
                <Typography.Text>{stage.result}</Typography.Text>
                <Typography.Text theme="secondary">{stage.detail}</Typography.Text>
                {stage.hint ? (
                  <Typography.Text theme={stage.theme === 'danger' ? 'error' : 'secondary'}>
                    {stage.hint}
                  </Typography.Text>
                ) : null}
              </Space>
            </div>
          ))}
        </div>
      </Space>
    </Card>
  );
}

const businessRunStepTheme = (status?: string | null): BusinessRunFlowStageTheme => {
  const value = String(status || '').toLowerCase();
  if (value === 'succeeded' || value === 'success' || value === 'completed') return 'success';
  if (value === 'failed' || value === 'error' || value === 'timeout' || value === 'cancelled') return 'danger';
  if (value === 'running' || value === 'queued' || value === 'pending' || value === 'planned') return 'warning';
  if (value === 'skipped') return 'default';
  return 'default';
};

function BusinessRunStepEvidenceCards({ steps }: { steps?: BusinessRunStep[] | null }) {
  const visibleSteps = steps || [];
  if (visibleSteps.length === 0) {
    return <Typography.Text theme="secondary">暂无步骤记录。若任务已经执行，请刷新业务运行记录或查看能力调用日志。</Typography.Text>;
  }
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
        gap: 12,
        width: '100%',
      }}
    >
      {visibleSteps.map((step) => {
        const isPassiveStep = step.componentKind !== 'execution' && !step.abilityId;
        const isPassivePlanned = isPassiveStep && step.status === 'planned';
        const theme = isPassivePlanned ? 'default' : businessRunStepTheme(step.status);
        const label = step.componentLabel || businessRecipeStepLabel(step.stepType, step.role);
        const result =
          businessRunStepSummaryLabel(step.resultSummary) ||
          step.error ||
          (isPassiveStep ? '说明节点，无单独执行输出' : '暂无输出摘要');
        const executor = [step.executorName || step.executorId, step.executorType].filter(Boolean).join(' · ');
        const ability = step.abilityName || step.abilityId || '未绑定具体能力';
        return (
          <div
            key={step.id || `${step.order}-${step.stepId || step.abilityTaskId || step.stepType}`}
            style={{
              border: '1px solid var(--td-border-level-1-color)',
              borderTop: `3px solid ${businessFlowStageColor(theme)}`,
              borderRadius: 12,
              padding: 12,
              background: 'var(--td-bg-color-container)',
              minHeight: 184,
            }}
          >
            <Space direction="vertical" size={6} style={{ width: '100%' }}>
              <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
                <Tag variant="light" theme={theme as any}>
                  {step.order}. {isPassivePlanned ? '流程说明' : businessRunStepStatusLabel(step.status)}
                </Tag>
                <Typography.Text theme="secondary">{label}</Typography.Text>
              </Space>
              <Typography.Text strong>{step.displayName || ability}</Typography.Text>
              <Typography.Text theme="secondary">
                {step.componentDescription || `执行能力：${ability}`}
              </Typography.Text>
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: '80px 1fr',
                  gap: '4px 8px',
                }}
              >
                <Typography.Text theme="secondary">结果</Typography.Text>
                <Typography.Text theme={step.error ? 'error' : 'secondary'}>{result}</Typography.Text>
                <Typography.Text theme="secondary">节点</Typography.Text>
                <Typography.Text theme="secondary">{executor || '未记录执行节点'}</Typography.Text>
                <Typography.Text theme="secondary">耗时成本</Typography.Text>
                <Typography.Text theme="secondary">
                  {formatDurationMs(step.durationMs)} · {formatPriceValue(step.costAmount ?? undefined, step.currency ?? undefined)}
                  {typeof step.quotaUnits === 'number' ? ` · ${step.quotaUnits} 额度` : ''}
                </Typography.Text>
                <Typography.Text theme="secondary">排障</Typography.Text>
                <Typography.Text code>{formatShortBusinessId(step.abilityTaskId || step.id)}</Typography.Text>
              </div>
            </Space>
          </div>
        );
      })}
    </div>
  );
}

const businessRunNeedsRetest = (row: BusinessRun) => {
  const status = String(row.status || '').toLowerCase();
  return Boolean(row.issueCategory && row.issueCategory !== 'none') || status === 'failed' || status === 'cancelled';
};

const businessRunCallbackFailed = (row: BusinessRun) =>
  row.callbackStatus === 'failed' || Boolean(row.callbackError);

function BusinessRunRetestControlPanel({
  runs,
  isReadOnly,
  actionLoadingId,
  onBulkRetest,
  onBulkCallbackRetry,
  onBulkIgnoreIssues,
  onGenerateIssueChecklist,
}: {
  runs: BusinessRun[];
  isReadOnly: boolean;
  actionLoadingId?: string | null;
  onBulkRetest: () => void;
  onBulkCallbackRetry: () => void;
  onBulkIgnoreIssues: () => void;
  onGenerateIssueChecklist: () => void;
}) {
  const issueRuns = runs.filter((row) => row.issueCategory && row.issueCategory !== 'none');
  const failedRuns = runs.filter((row) => String(row.status || '').toLowerCase() === 'failed');
  const retestableRuns = runs.filter(businessRunNeedsRetest);
  const callbackFailedRuns = runs.filter(businessRunCallbackFailed);
  const recoveredRuns = runs.filter((row) => row.retestRecovered);
  const issueLabels = Array.from(new Set(issueRuns.map((row) => businessIssueLabel(row.issueCategory, row.issueLabel)))).slice(0, 4);
  const canGenerateChecklist = issueRuns.length > 0;
  const canRetest = retestableRuns.length > 0;
  const canRetryCallback = callbackFailedRuns.length > 0;
  const canIgnore = issueRuns.length > 0;

  return (
    <Card
      bordered
      style={{ marginBottom: 12 }}
      title={
        <Space align="center" style={{ justifyContent: 'space-between', width: '100%', flexWrap: 'wrap' }}>
          <div>
            <Typography.Text strong>业务复测闭环</Typography.Text>
            <div>
              <Typography.Text theme="secondary">
                先筛选三条主业务，再对当前已加载记录生成排障清单、批量复测或重试回调。
              </Typography.Text>
            </div>
          </div>
          <Tag theme={retestableRuns.length > 0 ? 'warning' : 'success'} variant="light">
            {retestableRuns.length > 0 ? `待复测 ${retestableRuns.length}` : '当前页暂无待复测'}
          </Tag>
        </Space>
      }
    >
      <Row gutter={[12, 12]}>
        <Col xs={12} lg={4}>
          <Card bordered>
            <Space direction="vertical" size="small">
              <Typography.Text strong>当前已加载问题</Typography.Text>
              <Typography.Title level="h2" style={{ margin: 0 }}>
                {issueRuns.length}
              </Typography.Title>
              <Typography.Text theme="secondary">
                失败 {failedRuns.length} · 回调失败 {callbackFailedRuns.length} · 已恢复 {recoveredRuns.length}
              </Typography.Text>
              <Space size={6} breakLine>
                {issueLabels.length > 0 ? (
                  issueLabels.map((label) => (
                    <Tag key={label} theme="warning" variant="light" size="small">
                      {label}
                    </Tag>
                  ))
                ) : (
                  <Tag theme="success" variant="light" size="small">
                    暂无明显问题
                  </Tag>
                )}
              </Space>
            </Space>
          </Card>
        </Col>
        <Col xs={12} lg={4}>
          <Card bordered>
            <Space direction="vertical" size="small" style={{ width: '100%' }}>
              <Typography.Text strong>本页可执行动作</Typography.Text>
              <Typography.Text theme="secondary">
                批量动作只作用于当前已加载记录。需要覆盖更多历史时，先放大“最近条数”或调整筛选。
              </Typography.Text>
              <Space size="small" breakLine>
                <Button
                  variant="outline"
                  loading={actionLoadingId === 'bulk:checklist'}
                  disabled={isReadOnly || !canGenerateChecklist}
                  onClick={onGenerateIssueChecklist}
                >
                  生成排障清单
                </Button>
                <Button
                  theme="primary"
                  variant="outline"
                  loading={actionLoadingId === 'bulk:retest'}
                  disabled={isReadOnly || !canRetest}
                  onClick={onBulkRetest}
                >
                  复测问题记录
                </Button>
                <Button
                  variant="outline"
                  loading={actionLoadingId === 'bulk:callback'}
                  disabled={isReadOnly || !canRetryCallback}
                  onClick={onBulkCallbackRetry}
                >
                  重试回调失败
                </Button>
                <Button
                  variant="outline"
                  loading={actionLoadingId === 'bulk:ignore'}
                  disabled={isReadOnly || !canIgnore}
                  onClick={onBulkIgnoreIssues}
                >
                  标记无需处理
                </Button>
              </Space>
            </Space>
          </Card>
        </Col>
        <Col xs={12} lg={4}>
          <Alert
            theme={retestableRuns.length > 0 ? 'warning' : 'info'}
            message={
              retestableRuns.length > 0
                ? '建议先生成排障清单留证，再批量复测。复测成功后回到版本卡片记录验收通过，形成上线证据。'
                : '当前页没有待复测问题。上线前仍需按花纹提取、图裂变、扩图分别跑一次真实链路。'
            }
          />
        </Col>
      </Row>
    </Card>
  );
}

export const BusinessRunHistoryPanel = ({
  runs,
  total,
  filters,
  businessOptions,
  versionOptions,
  isReadOnly,
  tenantId,
  clientId,
  actionLoadingId,
  detail,
  detailOpen,
  onFiltersChange,
  onRefresh,
  onExport,
  onBulkCallbackRetry,
  onBulkRetest,
  onBulkIgnoreIssues,
  onGenerateIssueChecklist,
  onOpenDetail,
  onCloseDetail,
  onCallbackRetry,
  formatDateTime,
}: {
  runs: BusinessRun[];
  total: number;
  filters: BusinessRunFilters;
  businessOptions: BusinessSelectOption[];
  versionOptions: BusinessSelectOption[];
  isReadOnly: boolean;
  tenantId?: string | null;
  clientId?: string | null;
  actionLoadingId?: string | null;
  detail?: BusinessRun | null;
  detailOpen: boolean;
  onFiltersChange: (updater: (prev: BusinessRunFilters) => BusinessRunFilters) => void;
  onRefresh: () => void;
  onExport: () => void;
  onBulkCallbackRetry: () => void;
  onBulkRetest: () => void;
  onBulkIgnoreIssues: () => void;
  onGenerateIssueChecklist: () => void;
  onOpenDetail: (row: BusinessRun) => void;
  onCloseDetail: () => void;
  onCallbackRetry: (row: BusinessRun) => void;
  formatDateTime: (value?: string | null) => string;
}) => (
  <>
    <Card
      bordered
      title={
        <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
          <div>
            <Typography.Text strong>最近业务调用</Typography.Text>
            <div>
              <Typography.Text theme="secondary">已加载 {runs.length} / {total} 条</Typography.Text>
            </div>
          </div>
          <Button variant="outline" onClick={onRefresh}>
            刷新
          </Button>
        </Space>
      }
    >
      <BusinessRunRetestControlPanel
        runs={runs}
        isReadOnly={isReadOnly}
        actionLoadingId={actionLoadingId}
        onBulkRetest={onBulkRetest}
        onBulkCallbackRetry={onBulkCallbackRetry}
        onBulkIgnoreIssues={onBulkIgnoreIssues}
        onGenerateIssueChecklist={onGenerateIssueChecklist}
      />

      <Space align="center" size="small" style={{ marginBottom: 12, width: '100%', flexWrap: 'wrap' }}>
        <Select
          style={{ width: 130 }}
          value={filters.windowHours}
          options={businessUsageWindowOptions}
          onChange={(value) =>
            onFiltersChange((prev) => ({
              ...prev,
              windowHours: Number(value || 24),
            }))
          }
        />
        <Select
          style={{ width: 160 }}
          value={filters.businessKey}
          options={businessOptions}
          onChange={(value) =>
            onFiltersChange((prev) => ({
              ...prev,
              businessKey: String(value),
              version: 'all',
            }))
          }
        />
        <Select
          style={{ width: 140 }}
          value={filters.version}
          options={versionOptions}
          onChange={(value) =>
            onFiltersChange((prev) => ({
              ...prev,
              version: String(value),
            }))
          }
        />
        <Select
          style={{ width: 140 }}
          value={filters.status}
          options={businessRunStatusOptions}
          onChange={(value) =>
            onFiltersChange((prev) => ({
              ...prev,
              status: String(value),
            }))
          }
        />
        <Select
          style={{ width: 130 }}
          value={filters.billingStatus}
          options={businessRunBillingStatusOptions}
          onChange={(value) =>
            onFiltersChange((prev) => ({
              ...prev,
              billingStatus: String(value),
            }))
          }
        />
        <Select
          style={{ width: 130 }}
          value={filters.callbackStatus}
          options={businessRunCallbackStatusOptions}
          onChange={(value) =>
            onFiltersChange((prev) => ({
              ...prev,
              callbackStatus: String(value),
            }))
          }
        />
        <Select
          style={{ width: 150 }}
          value={filters.issueCategory}
          options={businessRunIssueCategoryOptions}
          onChange={(value) =>
            onFiltersChange((prev) => ({
              ...prev,
              issueCategory: String(value),
            }))
          }
        />
        <Input
          style={{ width: 130 }}
          value={filters.source}
          placeholder="来源，如 coze"
          clearable
          onChange={(value) =>
            onFiltersChange((prev) => ({
              ...prev,
              source: String(value || ''),
            }))
          }
        />
        <Input
          style={{ width: 160 }}
          value={isReadOnly ? tenantId || '' : filters.tenantId}
          placeholder="租户/业务方"
          clearable
          disabled={isReadOnly}
          onChange={(value) =>
            onFiltersChange((prev) => ({
              ...prev,
              tenantId: String(value || ''),
            }))
          }
        />
        <Input
          style={{ width: 160 }}
          value={isReadOnly ? clientId || '' : filters.clientId}
          placeholder="客户端/应用"
          clearable
          disabled={isReadOnly}
          onChange={(value) =>
            onFiltersChange((prev) => ({
              ...prev,
              clientId: String(value || ''),
            }))
          }
        />
        <Input
          style={{ width: 180 }}
          value={filters.traceId}
          placeholder="排障编号"
          clearable
          onChange={(value) =>
            onFiltersChange((prev) => ({
              ...prev,
              traceId: String(value || ''),
            }))
          }
        />
        <Select
          style={{ width: 120 }}
          value={filters.limit}
          options={[
            { label: '最近 20 条', value: 20 },
            { label: '最近 50 条', value: 50 },
            { label: '最近 100 条', value: 100 },
            { label: '最近 200 条', value: 200 },
          ]}
          onChange={(value) =>
            onFiltersChange((prev) => ({
              ...prev,
              limit: Number(value || 20),
            }))
          }
        />
        <Button theme="primary" variant="outline" onClick={onRefresh}>
          应用筛选
        </Button>
        <Button variant="outline" loading={actionLoadingId === 'export:runs'} onClick={onExport}>
          导出调用记录
        </Button>
      </Space>
      <Table
        size="small"
        rowKey="id"
        data={runs}
        empty={<Typography.Text theme="secondary">暂无业务调用记录。</Typography.Text>}
        columns={[
          {
            colKey: 'createdAt',
            title: '时间',
            width: 180,
            cell: ({ row }) => <Typography.Text>{formatDateTime(row.createdAt)}</Typography.Text>,
          },
          {
            colKey: 'businessKey',
            title: '业务',
            cell: ({ row }) => <Typography.Text strong>{businessKeyLabel(row.businessKey)}</Typography.Text>,
          },
          {
            colKey: 'source',
            title: '入口',
            width: 180,
            cell: ({ row }) => (
              <Space direction="vertical" size={2}>
                <Typography.Text>{businessSourceLabel(row.source)}</Typography.Text>
                <Typography.Text theme="secondary">
                  {row.channel || '未标记渠道'}{row.tenantId ? ` · ${row.tenantId}` : ''}
                </Typography.Text>
                {row.traceId ? <Typography.Text theme="secondary">排障：{formatShortBusinessId(row.traceId)}</Typography.Text> : null}
              </Space>
            ),
          },
          {
            colKey: 'version',
            title: '版本',
            width: 100,
            cell: ({ row }) => <Tag variant="light">{row.version || '—'}</Tag>,
          },
          {
            colKey: 'route',
            title: '生效方式',
            width: 160,
            cell: ({ row }) => <Typography.Text theme="secondary">{businessRunRouteLabel(row.routeInfo)}</Typography.Text>,
          },
          {
            colKey: 'steps',
            title: '链路判断',
            minWidth: 300,
            cell: ({ row }) => {
              const steps = row.steps || [];
              const stage = businessRunPriorityStage(row);
              const summaryTheme =
                stage?.theme === 'danger' ? 'error' : stage?.theme === 'warning' ? 'warning' : 'secondary';
              return (
                <Space direction="vertical" size={4}>
                  <Space size={6} breakLine>
                    <Tag variant="light" theme={businessIssueTheme(row.issueSeverity)}>
                      {businessIssueLabel(row.issueCategory, row.issueLabel)}
                    </Tag>
                    {stage ? (
                      <Tag variant="light" theme={stage.theme as any}>
                        {stage.title}
                      </Tag>
                    ) : null}
                    {row.retestSourceRunId ? (
                      <Tag variant="light">复测来源 {formatShortBusinessId(row.retestSourceRunId)}</Tag>
                    ) : Number(row.retestAttempts || 0) > 0 ? (
                      <Tag variant="light" theme={businessRetestTheme(row)}>
                        {row.retestRecovered
                          ? '复测已恢复'
                          : `${businessRetestStatusLabel(row.retestLatestStatus)} · ${row.retestAttempts || 0} 次`}
                      </Tag>
                    ) : null}
                    <Typography.Text theme={summaryTheme}>
                      {stage ? stage.result : businessRunFlowSummaryLabel(row)}
                    </Typography.Text>
                  </Space>
                  <Typography.Text theme="secondary">
                    {row.issueAction || stage?.hint || businessRunFlowSummaryLabel(row)}
                  </Typography.Text>
                  <Space breakLine size={4}>
                    {steps.slice(0, 3).map((step) => {
                      const summaryLabel = businessRunStepSummaryLabel(step.resultSummary);
                      return (
                        <Tag
                          key={step.id}
                          variant="light"
                          theme={step.status === 'failed' ? 'danger' : step.status === 'succeeded' ? 'success' : 'default'}
                        >
                          {step.order}. {businessRecipeStepLabel(step.stepType, step.role)} · {businessRunStepStatusLabel(step.status)}
                          {summaryLabel ? ` · ${summaryLabel}` : ''}
                        </Tag>
                      );
                    })}
                    {steps.length === 0 ? <Tag variant="light">未记录步骤</Tag> : null}
                    {steps.length > 3 ? <Tag variant="light">+{steps.length - 3} 步</Tag> : null}
                  </Space>
                </Space>
              );
            },
          },
          {
            colKey: 'ability',
            title: '实际执行',
            width: 260,
            cell: ({ row }) => (
              <Space direction="vertical" size={2}>
                <Typography.Text>{row.abilityName || row.abilityId || '未记录'}</Typography.Text>
                <Typography.Text theme="secondary">
                  {row.vendorModelName || row.vendorModelProvider || '未绑定模型目录'}
                </Typography.Text>
              </Space>
            ),
          },
          {
            colKey: 'status',
            title: '状态',
            width: 120,
            cell: ({ row }) => (
              <Space direction="vertical" size={2}>
                <StatusBadge status={row.status} />
                {row.callbackStatus ? (
                  <Tag variant="light" theme={businessCallbackStatusTheme(row.callbackStatus)}>
                    {businessCallbackStatusLabel(row.callbackStatus)}
                  </Tag>
                ) : null}
              </Space>
            ),
          },
          {
            colKey: 'cost',
            title: '耗时/成本',
            width: 190,
            cell: ({ row }) => {
              const walletSettlement = getBusinessWalletSettlement(row);
              return (
                <Space direction="vertical" size={2}>
                  <Typography.Text>{formatDurationMs(row.durationMs)}</Typography.Text>
                  <Space size={4}>
                    <Tag variant="light" theme={businessBillingStatusTheme(row.billingStatus)}>
                      {businessBillingStatusLabel(row.billingStatus)}
                    </Tag>
                    {walletSettlement ? (
                      <Tag variant="light" theme={businessWalletStatusTheme(walletSettlement)}>
                        {businessWalletStatusLabel(walletSettlement)}
                      </Tag>
                    ) : row.billingStatus === 'billable' && row.userId ? (
                      <Tag variant="light" theme="warning">待扣费确认</Tag>
                    ) : null}
                  </Space>
                  <Typography.Text theme="secondary">
                    {formatPriceValue(row.costAmount ?? undefined, row.currency ?? undefined)}
                    {typeof row.quotaUnits === 'number' ? ` · ${row.quotaUnits} 额度` : ''}
                  </Typography.Text>
                  {walletSettlement ? (
                    <Typography.Text theme="secondary">{businessWalletSummary(walletSettlement)}</Typography.Text>
                  ) : businessBillingReasonLabel(row) ? (
                    <Typography.Text theme={row.billingStatus === 'no_charge' ? 'secondary' : 'warning'}>
                      {businessBillingReasonLabel(row)}
                    </Typography.Text>
                  ) : null}
                </Space>
              );
            },
          },
          {
            colKey: 'taskId',
            title: '排障编号',
            ellipsis: true,
            cell: ({ row }) => <Typography.Text theme="secondary">{formatShortBusinessId(row.taskId || row.abilityTaskId)}</Typography.Text>,
          },
          {
            colKey: 'outputs',
            title: '结果',
            width: 150,
            cell: ({ row }) => <Typography.Text>{businessRunOutputLabel(row)}</Typography.Text>,
          },
          {
            colKey: 'error',
            title: '错误',
            ellipsis: true,
            cell: ({ row }) => (
              <Typography.Text theme={row.error || row.errorMessage ? 'error' : 'secondary'}>
                {row.error || row.errorMessage || '—'}
              </Typography.Text>
            ),
          },
          {
            colKey: 'actions',
            title: '操作',
            width: 130,
            cell: ({ row }) => (
              <Space size={4}>
                <Button size="small" variant="text" onClick={() => onOpenDetail(row)}>
                  详情
                </Button>
                {!isReadOnly && row.callbackStatus === 'failed' ? (
                  <Button
                    size="small"
                    variant="text"
                    loading={actionLoadingId === `callback:${row.id}`}
                    onClick={() => onCallbackRetry(row)}
                  >
                    重试回调
                  </Button>
                ) : null}
              </Space>
            ),
          },
        ]}
      />
    </Card>
    <Dialog
      header="业务调用详情"
      visible={detailOpen}
      width={920}
      confirmBtn={null}
      cancelBtn="关闭"
      onClose={onCloseDetail}
      onCancel={onCloseDetail}
    >
      {detail ? (
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <BusinessRunNextActionAlert detail={detail} />
          <Row gutter={[12, 12]}>
            <Col span={6}>
              <Typography.Text theme="secondary">业务任务</Typography.Text>
              <Typography.Text code>{detail.runId || detail.id}</Typography.Text>
            </Col>
            <Col span={3}>
              <Typography.Text theme="secondary">业务</Typography.Text>
              <Typography.Text>{businessKeyLabel(detail.businessKey)}</Typography.Text>
            </Col>
            <Col span={3}>
              <Typography.Text theme="secondary">状态</Typography.Text>
              <StatusBadge status={detail.status} />
            </Col>
            <Col span={6}>
              <Typography.Text theme="secondary">入口 / 渠道</Typography.Text>
              <Typography.Text>
                {businessSourceLabel(detail.source)} · {detail.channel || '未标记渠道'}
              </Typography.Text>
            </Col>
            <Col span={6}>
              <Typography.Text theme="secondary">耗时 / 成本</Typography.Text>
              <Typography.Text>
                {formatDurationMs(detail.durationMs)} · {formatPriceValue(
                  detail.costAmount ?? undefined,
                  detail.currency ?? undefined,
                )}
                {typeof detail.quotaUnits === 'number' ? ` · ${detail.quotaUnits} 额度` : ''}
              </Typography.Text>
            </Col>
          </Row>
          <Row gutter={[12, 12]}>
            <Col span={6}>
              <Typography.Text theme="secondary">版本 / 生效方式</Typography.Text>
              <Typography.Text>
                {detail.version || '—'} · {businessRunRouteLabel(detail.routeInfo)}
              </Typography.Text>
            </Col>
            <Col span={6}>
              <Typography.Text theme="secondary">排障编号</Typography.Text>
              <Typography.Text>{formatShortBusinessId(detail.taskId || detail.abilityTaskId)}</Typography.Text>
            </Col>
            <Col span={6}>
              <Typography.Text theme="secondary">请求追踪</Typography.Text>
              <Typography.Text>{formatShortBusinessId(detail.traceId)}</Typography.Text>
            </Col>
            <Col span={6}>
              <Typography.Text theme="secondary">业务方 / 客户端</Typography.Text>
              <Typography.Text>
                {detail.tenantId || '—'} · {detail.clientId || '—'}
              </Typography.Text>
            </Col>
            <Col span={6}>
              <Typography.Text theme="secondary">回调状态</Typography.Text>
              <Space size={6}>
                <Tag variant="light" theme={businessCallbackStatusTheme(detail.callbackStatus)}>
                  {businessCallbackStatusLabel(detail.callbackStatus)}
                </Tag>
                <Typography.Text theme="secondary">
                  {detail.callbackHttpStatus ? `HTTP ${detail.callbackHttpStatus}` : ''}
                  {detail.callbackError ? ` · ${detail.callbackError}` : ''}
                </Typography.Text>
                {!isReadOnly && detail.callbackStatus === 'failed' ? (
                  <Button
                    size="small"
                    variant="outline"
                    loading={actionLoadingId === `callback:${detail.id}`}
                    onClick={() => onCallbackRetry(detail)}
                  >
                    重试回调
                  </Button>
                ) : null}
              </Space>
            </Col>
            <Col span={6}>
              <Typography.Text theme="secondary">计费状态</Typography.Text>
              <Space direction="vertical" size={2}>
                <Tag variant="light" theme={businessBillingStatusTheme(detail.billingStatus)}>
                  {businessBillingStatusLabel(detail.billingStatus)}
                </Tag>
                {businessBillingReasonLabel(detail) ? (
                  <Typography.Text theme={detail.billingStatus === 'no_charge' ? 'secondary' : 'warning'}>
                    {businessBillingReasonLabel(detail)}
                  </Typography.Text>
                ) : null}
                <Tag variant="light" theme={businessWalletStatusTheme(getBusinessWalletSettlement(detail))}>
                  {businessWalletStatusLabel(getBusinessWalletSettlement(detail))}
                </Tag>
                <Typography.Text theme="secondary">
                  {businessWalletSummary(getBusinessWalletSettlement(detail))}
                </Typography.Text>
                {getBusinessWalletSettlement(detail)?.traceId ? (
                  <Typography.Text code>{getBusinessWalletSettlement(detail)?.traceId}</Typography.Text>
                ) : null}
              </Space>
            </Col>
          </Row>
          <BusinessRunFlowEvidenceBar detail={detail} />
          {detail.retestSummary ? (
            <Card bordered title="复测追踪">
              {(() => {
                const retest = asJsonRecord(detail.retestSummary);
                const history = Array.isArray(retest.history) ? retest.history : [];
                return (
                  <Space direction="vertical" size="small" style={{ width: '100%' }}>
                    <Space breakLine>
                      {detail.retestSourceRunId ? (
                        <Tag variant="light">这是复测任务，来源 {formatShortBusinessId(detail.retestSourceRunId)}</Tag>
                      ) : (
                        <Tag variant="light" theme={businessRetestTheme(detail)}>
                          {detail.retestRecovered ? '复测已确认恢复' : `复测次数 ${detail.retestAttempts || 0}`}
                        </Tag>
                      )}
                      {detail.retestLatestRunId ? (
                        <Tag variant="light" theme={businessRetestTheme(detail)}>
                          最新复测 {formatShortBusinessId(detail.retestLatestRunId)} · {businessRetestStatusLabel(detail.retestLatestStatus)}
                        </Tag>
                      ) : null}
                      {recordText(retest, 'sourceIssueLabel') !== '—' ? (
                        <Tag variant="light" theme="warning">
                          原问题：{recordText(retest, 'sourceIssueLabel')}
                        </Tag>
                      ) : null}
                    </Space>
                    {history.length > 0 ? (
                      <Space direction="vertical" size={4} style={{ width: '100%' }}>
                        {history.slice(0, 5).map((item, index) => {
                          const record = asJsonRecord(item);
                          return (
                            <Space
                              key={`${recordText(record, 'runId')}-${index}`}
                              align="center"
                              style={{ justifyContent: 'space-between', width: '100%' }}
                            >
                              <Typography.Text code>{formatShortBusinessId(recordText(record, 'runId'))}</Typography.Text>
                              <Space size={6}>
                                <Tag variant="light" theme={record.recovered ? 'success' : record.status === 'failed' ? 'danger' : 'warning'}>
                                  {record.recovered ? '已恢复' : businessRetestStatusLabel(String(record.status || ''))}
                                </Tag>
                                <Typography.Text theme="secondary">
                                  {recordText(record, 'issueLabel', '暂无明显问题')}
                                </Typography.Text>
                              </Space>
                            </Space>
                          );
                        })}
                      </Space>
                    ) : (
                      <Typography.Text theme="secondary">
                        暂无复测记录。可以在列表中筛选问题后使用“复测问题记录”。
                      </Typography.Text>
                    )}
                  </Space>
                );
              })()}
            </Card>
          ) : null}
          {detail.flowSummary ? (
            <Card bordered title="链路证据">
              {(() => {
                const route = asJsonRecord(detail.flowSummary?.route);
                const ability = asJsonRecord(detail.flowSummary?.ability);
                const executor = asJsonRecord(detail.flowSummary?.executor);
                const output = asJsonRecord(detail.flowSummary?.output);
                const callback = asJsonRecord(detail.flowSummary?.callback);
                const hasOutput = Boolean(output.hasOutput);
                const hasOssOutput = Boolean(output.hasOssOutput);
                const structuredCount = recordText(output, 'structuredCount', '0');
                const resourceCount = recordText(output, 'resourceCount', '0');
                return (
                  <Row gutter={[12, 12]}>
                    <Col span={6}>
                      <Typography.Text theme="secondary">业务版本</Typography.Text>
                      <Space direction="vertical" size={2}>
                        <Typography.Text>
                          {recordText(route, 'version')} · {businessRunRouteLabel(detail.routeInfo)}
                        </Typography.Text>
                        <Typography.Text code>{recordText(route, 'selectedCapabilityId')}</Typography.Text>
                      </Space>
                    </Col>
                    <Col span={6}>
                      <Typography.Text theme="secondary">实际原子能力</Typography.Text>
                      <Space direction="vertical" size={2}>
                        <Typography.Text>{recordText(ability, 'name', detail.abilityName || detail.abilityId || '—')}</Typography.Text>
                        <Typography.Text code>{recordText(ability, 'taskId', formatShortBusinessId(detail.abilityTaskId))}</Typography.Text>
                      </Space>
                    </Col>
                    <Col span={6}>
                      <Typography.Text theme="secondary">命中执行节点</Typography.Text>
                      <Space direction="vertical" size={2}>
                        <Typography.Text>{recordText(executor, 'name')}</Typography.Text>
                        <Typography.Text theme="secondary">
                          {recordText(executor, 'id')} · {recordText(executor, 'type')}
                        </Typography.Text>
                      </Space>
                    </Col>
                    <Col span={6}>
                      <Typography.Text theme="secondary">结果回填</Typography.Text>
                      <Space direction="vertical" size={2}>
                        <Space size={4}>
                          <Tag variant="light" theme={hasOutput ? 'success' : 'warning'}>
                            {hasOutput ? '有业务结果' : '无业务结果'}
                          </Tag>
                          <Tag variant="light" theme={hasOssOutput ? 'success' : 'warning'}>
                            {hasOssOutput ? '已落 OSS' : '未见 OSS'}
                          </Tag>
                        </Space>
                        <Typography.Text theme="secondary">
                          图 {recordText(output, 'imageCount', '0')} · 视频 {recordText(output, 'videoCount', '0')} · 文字{' '}
                          {recordText(output, 'textCount', '0')} · 结构化 {structuredCount} · 资源 {resourceCount}
                        </Typography.Text>
                      </Space>
                    </Col>
                    <Col span={6}>
                      <Typography.Text theme="secondary">回调</Typography.Text>
                      <Typography.Text>
                        {businessCallbackStatusLabel(recordText(callback, 'status', ''))}
                        {recordText(callback, 'httpStatus', '') ? ` · HTTP ${recordText(callback, 'httpStatus')}` : ''}
                      </Typography.Text>
                    </Col>
                    <Col span={18}>
                      <Typography.Text theme="secondary">排查建议</Typography.Text>
                      <Typography.Text>
                        {detail.flowSummary.message || '—'}
                        {detail.flowSummary.nextAction ? `。${detail.flowSummary.nextAction}` : ''}
                      </Typography.Text>
                    </Col>
                  </Row>
                );
              })()}
            </Card>
          ) : null}
          <Card bordered title="业务闭环步骤">
            <Space direction="vertical" size="small" style={{ width: '100%' }}>
              {detail.flowSummary ? (
                <Alert
                  theme={Number(detail.flowSummary.failed || 0) > 0 ? 'warning' : 'info'}
                  message={[
                    businessRunFlowSummaryLabel(detail),
                    detail.flowSummary.nextAction,
                  ].filter(Boolean).join('。')}
                />
              ) : null}
              <Typography.Text theme="secondary">
                按执行顺序展示每一步做了什么、当前结果、命中的节点和排障编号；底层原始字段放在下方高级区。
              </Typography.Text>
              <BusinessRunStepEvidenceCards steps={detail.steps || []} />
            </Space>
          </Card>
          <details
            style={{
              border: '1px solid var(--td-border-level-1-color)',
              borderRadius: 12,
              padding: 12,
            }}
          >
            <summary style={{ cursor: 'pointer', fontWeight: 600 }}>步骤明细表</summary>
            <Table
              size="small"
              rowKey="id"
              data={detail.steps || []}
              empty={<Typography.Text theme="secondary">暂无步骤记录。</Typography.Text>}
              style={{ marginTop: 12 }}
              columns={[
                {
                  colKey: 'step',
                  title: '步骤',
                  minWidth: 180,
                  cell: ({ row }) => (
                    <Space direction="vertical" size={2}>
                      <Typography.Text>
                        {row.order}. {row.componentLabel || businessRecipeStepLabel(row.stepType, row.role)}
                      </Typography.Text>
                      <Typography.Text theme="secondary">
                        {row.displayName || row.abilityName || row.abilityId || row.componentDescription || '未绑定能力'}
                      </Typography.Text>
                    </Space>
                  ),
                },
                {
                  colKey: 'status',
                  title: '状态',
                  width: 120,
                  cell: ({ row }) => <StatusBadge status={row.status} />,
                },
                {
                  colKey: 'stepCost',
                  title: '耗时/成本',
                  width: 150,
                  cell: ({ row }) => (
                    <Space direction="vertical" size={2}>
                      <Typography.Text>{formatDurationMs(row.durationMs)}</Typography.Text>
                      <Typography.Text theme="secondary">
                        {formatPriceValue(row.costAmount ?? undefined, row.currency ?? undefined)}
                        {typeof row.quotaUnits === 'number' ? ` · ${row.quotaUnits} 额度` : ''}
                      </Typography.Text>
                    </Space>
                  ),
                },
                {
                  colKey: 'summary',
                  title: '结果摘要',
                  minWidth: 220,
                  cell: ({ row }) => (
                    <Typography.Text theme="secondary">
                      {businessRunStepSummaryLabel(row.resultSummary) || row.error || '—'}
                    </Typography.Text>
                  ),
                },
                {
                  colKey: 'executor',
                  title: '执行节点',
                  minWidth: 220,
                  cell: ({ row }) => (
                    <Space direction="vertical" size={2}>
                      <Typography.Text>{row.executorName || row.executorId || '未记录'}</Typography.Text>
                      <Typography.Text theme="secondary">
                        {row.executorId || '—'} · {row.executorType || '—'}
                      </Typography.Text>
                    </Space>
                  ),
                },
                {
                  colKey: 'task',
                  title: '步骤排障编号',
                  minWidth: 220,
                  ellipsis: true,
                  cell: ({ row }) => <Typography.Text theme="secondary">{formatShortBusinessId(row.abilityTaskId)}</Typography.Text>,
                },
              ]}
            />
          </details>
          <details
            style={{
              border: '1px solid var(--td-border-level-1-color)',
              borderRadius: 12,
              padding: 12,
            }}
          >
            <summary style={{ cursor: 'pointer', fontWeight: 600 }}>高级排障数据</summary>
            <Row gutter={[12, 12]} style={{ marginTop: 12 }}>
              <Col span={6}>
                <Typography.Text theme="secondary">请求参数</Typography.Text>
                <Textarea
                  value={formatJsonValue(detail.requestPayload || {})}
                  readonly
                  autosize={{ minRows: 5, maxRows: 10 }}
                  className="font-mono text-xs"
                />
              </Col>
              <Col span={6}>
                <Typography.Text theme="secondary">输出 / 错误</Typography.Text>
                <Textarea
                  value={formatJsonValue({
                    result: detail.resultPayload || {},
                    imageUrls: detail.imageUrls || [],
                    videoUrls: detail.videoUrls || [],
                    texts: detail.texts || [],
                    error: detail.error || detail.errorMessage || null,
                    trace: {
                      traceId: detail.traceId ?? null,
                      requestId: detail.requestId ?? null,
                      tenantId: detail.tenantId ?? null,
                      clientId: detail.clientId ?? null,
                    },
                    cost: {
                      durationMs: detail.durationMs ?? null,
                      costAmount: detail.costAmount ?? null,
                      currency: detail.currency ?? null,
                      quotaUnits: detail.quotaUnits ?? null,
                      costBreakdown: detail.costBreakdown ?? null,
                    },
                  })}
                  readonly
                  autosize={{ minRows: 5, maxRows: 10 }}
                  className="font-mono text-xs"
                />
              </Col>
            </Row>
          </details>
        </Space>
      ) : null}
    </Dialog>
  </>
);

export const BusinessCapabilityEditorDialog = ({
  visible,
  form,
  error,
  abilityOptions,
  vlAbilityOptions,
  onChange,
  onClose,
  onConfirm,
}: {
  visible: boolean;
  form: BusinessCapabilityFormState;
  error?: string | null;
  abilityOptions: BusinessSelectOption[];
  vlAbilityOptions: BusinessSelectOption[];
  onChange: (next: BusinessCapabilityFormState) => void;
  onClose: () => void;
  onConfirm: () => void;
}) => (
  <Dialog
    header={form.id ? '编辑业务版本' : '新增业务版本'}
    visible={visible}
    width={760}
    onClose={onClose}
    onConfirm={onConfirm}
  >
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      {error ? <Alert theme="error" message={error} /> : null}
      <Row gutter={[12, 12]}>
        <Col span={6}>
          <Typography.Text theme="secondary">业务类型</Typography.Text>
          <Input
            value={form.businessKey}
            placeholder="例如 fission（图裂变）"
            onChange={(value) => onChange({ ...form, businessKey: String(value) })}
          />
        </Col>
        <Col span={6}>
          <Typography.Text theme="secondary">版本</Typography.Text>
          <Input
            value={form.version}
            placeholder="例如 v2"
            onChange={(value) => onChange({ ...form, version: String(value) })}
          />
        </Col>
        <Col span={6}>
          <Typography.Text theme="secondary">状态</Typography.Text>
          <Select
            value={form.status}
            onChange={(value) => onChange({ ...form, status: String(value) })}
            options={statusOptions}
          />
        </Col>
        <Col span={6}>
          <Typography.Text theme="secondary">是否默认</Typography.Text>
          <div style={{ paddingTop: 8 }}>
            <Switch value={form.isDefault} onChange={(value) => onChange({ ...form, isDefault: Boolean(value) })} />
          </div>
        </Col>
      </Row>
      <Row gutter={[12, 12]}>
        <Col span={12}>
          <Typography.Text theme="secondary">业务名称</Typography.Text>
          <Input
            value={form.displayName}
            placeholder="例如 图裂变 · GPT Image 2 测试版"
            onChange={(value) => onChange({ ...form, displayName: String(value) })}
          />
        </Col>
        <Col span={12}>
          <Typography.Text theme="secondary">主执行能力</Typography.Text>
          <Select
            value={form.primaryAbilityId}
            filterable
            options={abilityOptions}
            placeholder="选择这个业务版本主要调用的能力"
            onChange={(value) => onChange({ ...form, primaryAbilityId: String(value) })}
          />
        </Col>
      </Row>
      <Typography.Text theme="secondary">说明</Typography.Text>
      <Textarea
        autosize={{ minRows: 2, maxRows: 4 }}
        value={form.description || ''}
        onChange={(value) => onChange({ ...form, description: String(value) })}
      />
      <Card bordered title="图像理解辅助">
        <Space direction="vertical" size="small" style={{ width: '100%' }}>
          <Space align="center" size="small">
            <Switch
              value={form.vlAssistEnabled}
              onChange={(value) => onChange({ ...form, vlAssistEnabled: Boolean(value) })}
            />
            <Typography.Text theme="secondary">
              启用后会先分析原图，后续可用于自动生成提示词和风险提示。
            </Typography.Text>
          </Space>
          <Row gutter={[12, 12]}>
            <Col span={12}>
              <Typography.Text theme="secondary">图像理解能力</Typography.Text>
              <Select
                value={form.vlAssistAbilityId}
                filterable
                disabled={!form.vlAssistEnabled}
                options={vlAbilityOptions.length > 0 ? vlAbilityOptions : abilityOptions}
                placeholder="选择图像理解能力"
                onChange={(value) => onChange({ ...form, vlAssistAbilityId: String(value) })}
              />
            </Col>
          </Row>
        </Space>
      </Card>
      <Row gutter={[12, 12]}>
        <Col span={12}>
          <Typography.Text theme="secondary">发布时间</Typography.Text>
          <Input
            value={form.releaseTime || ''}
            placeholder="例如 2026-04-25T10:00:00，可留空"
            onChange={(value) => onChange({ ...form, releaseTime: String(value) })}
          />
        </Col>
      </Row>
      <Card bordered title="灰度发布">
        <Space direction="vertical" size="small" style={{ width: '100%' }}>
          <Space align="center" size="large">
            <Space align="center" size="small">
              <Switch
                value={form.rolloutEnabled}
                onChange={(value) => onChange({ ...form, rolloutEnabled: Boolean(value) })}
              />
              <Typography.Text theme="secondary">启用灰度</Typography.Text>
            </Space>
            <Space align="center" size="small">
              <Typography.Text theme="secondary">灰度比例</Typography.Text>
              <InputNumber
                min={0}
                max={100}
                value={form.rolloutPercent}
                onChange={(value) => onChange({ ...form, rolloutPercent: Number(value || 0) })}
              />
              <Typography.Text theme="secondary">%</Typography.Text>
            </Space>
          </Space>
          <Typography.Text theme="secondary">白名单每行一个客户标识。不确定时先留空，默认按比例灰度。</Typography.Text>
          <Textarea
            autosize={{ minRows: 2, maxRows: 5 }}
            value={form.rolloutAllowlistText}
            placeholder="例如：tenant-a"
            onChange={(value) => onChange({ ...form, rolloutAllowlistText: String(value) })}
          />
        </Space>
      </Card>
      <details
        style={{
          border: '1px solid var(--td-border-level-1-color)',
          borderRadius: 12,
          padding: 12,
        }}
      >
        <summary style={{ cursor: 'pointer', fontWeight: 600 }}>高级配置：多步骤配方和接口字段</summary>
        <Space direction="vertical" size="small" style={{ width: '100%', marginTop: 12 }}>
          <Alert
            theme="warning"
            message="一般不用改。只有这个业务版本需要多步骤编排、特殊入参或特殊发布策略时，才编辑下面内容。"
          />
          <Typography.Text theme="secondary">业务配方</Typography.Text>
          <Textarea
            autosize={{ minRows: 4, maxRows: 8 }}
            value={form.recipeText}
            onChange={(value) => onChange({ ...form, recipeText: String(value) })}
          />
          <Typography.Text theme="secondary">输入字段</Typography.Text>
          <Textarea
            autosize={{ minRows: 3, maxRows: 6 }}
            value={form.inputSchemaText}
            onChange={(value) => onChange({ ...form, inputSchemaText: String(value) })}
          />
          <Typography.Text theme="secondary">元信息</Typography.Text>
          <Textarea
            autosize={{ minRows: 3, maxRows: 6 }}
            value={form.metadataText}
            onChange={(value) => onChange({ ...form, metadataText: String(value) })}
          />
        </Space>
      </details>
    </Space>
  </Dialog>
);

export const BusinessGovernancePanel = ({
  capabilityOptions,
  targetOptions,
  compareLeftId,
  compareRightId,
  selectedTarget,
  compareResult,
  pendingApprovals,
  actionLoadingId,
  onCompareLeftChange,
  onCompareRightChange,
  onCompare,
  onRollback,
  onApprovalDecision,
  formatDateTime,
}: {
  capabilityOptions: BusinessOption[];
  targetOptions: BusinessOption[];
  compareLeftId: string;
  compareRightId: string;
  selectedTarget?: BusinessCapability | null;
  compareResult?: BusinessCapabilityCompareResponse | null;
  pendingApprovals: BusinessDefaultApproval[];
  actionLoadingId?: string | null;
  onCompareLeftChange: (value: string) => void;
  onCompareRightChange: (value: string) => void;
  onCompare: () => void;
  onRollback: () => void;
  onApprovalDecision: (item: BusinessDefaultApproval, decision: 'approve' | 'reject') => void;
  formatDateTime: (value?: string | null) => string;
}) => (
  <Space direction="vertical" size="large" style={{ width: '100%' }}>
    <Card bordered>
      <Space direction="vertical" size="small" style={{ width: '100%' }}>
        <Space align="center" style={{ justifyContent: 'space-between', width: '100%', flexWrap: 'wrap' }}>
          <div>
            <Typography.Text strong>版本对比与回滚</Typography.Text>
            <div>
              <Typography.Text theme="secondary">
                切默认版本前先看差异；回滚只切默认版本，不自动停用当前版本。
              </Typography.Text>
            </div>
          </div>
          <Space breakLine>
            <Select
              value={compareLeftId}
              options={capabilityOptions}
              style={{ minWidth: 280 }}
              placeholder="当前版本"
              onChange={(value) => onCompareLeftChange(String(value || ''))}
            />
            <Select
              value={compareRightId}
              options={targetOptions}
              style={{ minWidth: 260 }}
              placeholder="目标版本"
              onChange={(value) => onCompareRightChange(String(value || ''))}
            />
            <Button
              variant="outline"
              loading={actionLoadingId === 'compare:business'}
              disabled={!compareLeftId || !compareRightId}
              onClick={onCompare}
            >
              查看差异
            </Button>
            <Button
              theme="warning"
              variant="outline"
              loading={actionLoadingId === 'rollback:business'}
              disabled={!compareLeftId || !compareRightId || selectedTarget?.status !== 'active'}
              onClick={onRollback}
            >
              回滚为默认
            </Button>
          </Space>
        </Space>
        {selectedTarget && selectedTarget.status !== 'active' ? (
          <Alert theme="warning" message="目标版本未启用，不能回滚为默认版本。请先启用后再操作。" />
        ) : null}
        {selectedTarget ? (
          <Alert
            theme={businessCapabilityHasRollbackEvidence(selectedTarget) ? 'success' : 'warning'}
            message={`目标版本证据：${businessCapabilityRollbackEvidenceLabel(selectedTarget)}`}
          />
        ) : null}
        {compareResult ? (
          <Space direction="vertical" size="small" style={{ width: '100%' }}>
            <Space align="center" size={8} style={{ flexWrap: 'wrap' }}>
              <Tag theme={compareResult.sameBusinessKey ? 'success' : 'danger'} variant="light">
                {compareResult.sameBusinessKey ? '同一业务' : '业务不一致'}
              </Tag>
              <Tag theme={compareResult.summary.changedCount > 0 ? 'warning' : 'success'} variant="light">
                {compareResult.summary.changedCount} 处差异
              </Tag>
              <Typography.Text theme="secondary">
                {compareResult.left.version} → {compareResult.right.version}
              </Typography.Text>
            </Space>
            <Table
              size="small"
              rowKey="field"
              data={compareResult.changedFields || []}
              empty={<Typography.Text theme="secondary">两个版本主要字段一致。</Typography.Text>}
              columns={[
                {
                  colKey: 'section',
                  title: '范围',
                  width: 120,
                  cell: ({ row }) => <Tag variant="light">{row.section}</Tag>,
                },
                {
                  colKey: 'field',
                  title: '字段',
                  width: 150,
                  cell: ({ row }) => (
                    <Space direction="vertical" size={2}>
                      <Typography.Text>{businessCompareFieldLabel(row.field)}</Typography.Text>
                      <Typography.Text code theme="secondary">
                        {row.field}
                      </Typography.Text>
                    </Space>
                  ),
                },
                {
                  colKey: 'left',
                  title: '当前版本',
                  minWidth: 260,
                  cell: ({ row }) => <BusinessCompareValueBlock value={row.left} />,
                },
                {
                  colKey: 'right',
                  title: '目标版本',
                  minWidth: 260,
                  cell: ({ row }) => <BusinessCompareValueBlock value={row.right} />,
                },
              ]}
            />
          </Space>
        ) : null}
      </Space>
    </Card>
    <Card
      bordered
      title={
        <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
          <div>
            <Typography.Text strong>默认版本审批</Typography.Text>
            <div>
              <Typography.Text theme="secondary">
                待审批申请通过后才会真正切换默认版本，适合发版前二次确认。
              </Typography.Text>
            </div>
          </div>
          <Tag theme={pendingApprovals.length > 0 ? 'warning' : 'success'} variant="light">
            待处理 {pendingApprovals.length}
          </Tag>
        </Space>
      }
    >
      <Table
        size="small"
        rowKey="id"
        data={pendingApprovals}
        empty={<Typography.Text theme="secondary">暂无待审批的默认版本切换。</Typography.Text>}
        columns={[
          {
            colKey: 'createdAt',
            title: '申请时间',
            width: 170,
            cell: ({ row }) => <Typography.Text>{formatDateTime(row.createdAt)}</Typography.Text>,
          },
          {
            colKey: 'target',
            title: '目标版本',
            minWidth: 260,
            cell: ({ row }) => (
              <Space direction="vertical" size={2}>
                <Typography.Text strong>
                  {businessKeyLabel(row.businessKey)} · {row.targetCapability?.version || row.targetCapabilityId}
                </Typography.Text>
                <Typography.Text theme="secondary">
                  {row.sourceCapability?.version || '当前默认'} → {row.targetCapability?.displayName || row.targetCapabilityId}
                </Typography.Text>
              </Space>
            ),
          },
          {
            colKey: 'requester',
            title: '申请人',
            width: 140,
            cell: ({ row }) => <Typography.Text>{row.requesterUsername || row.requesterUserId || '系统'}</Typography.Text>,
          },
          {
            colKey: 'note',
            title: '说明',
            minWidth: 220,
            cell: ({ row }) => <Typography.Text>{row.requestNote || '未填写'}</Typography.Text>,
          },
          {
            colKey: 'actions',
            title: '处理',
            width: 180,
            cell: ({ row }) => (
              <Space size={6}>
                <Button
                  size="small"
                  theme="primary"
                  loading={actionLoadingId === `approve:approval:${row.id}`}
                  disabled={Boolean(actionLoadingId) && actionLoadingId !== `approve:approval:${row.id}`}
                  onClick={() => onApprovalDecision(row, 'approve')}
                >
                  通过并切换
                </Button>
                <Button
                  size="small"
                  variant="outline"
                  theme="warning"
                  loading={actionLoadingId === `reject:approval:${row.id}`}
                  disabled={Boolean(actionLoadingId) && actionLoadingId !== `reject:approval:${row.id}`}
                  onClick={() => onApprovalDecision(row, 'reject')}
                >
                  驳回
                </Button>
              </Space>
            ),
          },
        ]}
      />
    </Card>
  </Space>
);

const businessOperationTheme = (action?: string | null) => {
  if (action === 'business_capability_set_default') return 'primary';
  if (action === 'business_capability_rollback') return 'danger';
  if (action === 'business_capability_default_approval_apply') return 'success';
  if (action === 'business_capability_default_approval_reject') return 'warning';
  if (action === 'business_capability_status_change') return 'warning';
  return 'default';
};

export const BusinessOperationLogPanel = ({
  logs,
  onRefresh,
  formatDateTime,
}: {
  logs: BusinessOperationLog[];
  onRefresh: () => void;
  formatDateTime: (value?: string | null) => string;
}) => (
  <Card
    bordered
    title={
      <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
        <div>
          <Typography.Text strong>版本操作记录</Typography.Text>
          <div>
            <Typography.Text theme="secondary">记录新增、修改、设默认、启停，便于回溯版本变化。</Typography.Text>
          </div>
        </div>
        <Button variant="outline" onClick={onRefresh}>
          刷新记录
        </Button>
      </Space>
    }
  >
    <Table
      size="small"
      rowKey="id"
      data={logs}
      empty={<Typography.Text theme="secondary">暂无版本操作记录。</Typography.Text>}
      columns={[
        {
          colKey: 'createdAt',
          title: '时间',
          width: 180,
          cell: ({ row }) => <Typography.Text>{formatDateTime(row.createdAt)}</Typography.Text>,
        },
        {
          colKey: 'action',
          title: '动作',
          width: 120,
          cell: ({ row }) => (
            <Tag variant="light" theme={businessOperationTheme(row.action) as any}>
              {businessOperationActionLabel(row.action)}
            </Tag>
          ),
        },
        {
          colKey: 'target',
          title: '业务版本',
          minWidth: 260,
          cell: ({ row }) => (
            <Space direction="vertical" size={2}>
              <Typography.Text strong>{businessOperationTargetLabel(row)}</Typography.Text>
              <Typography.Text theme="secondary">版本编号：{formatShortBusinessId(row.targetId)}</Typography.Text>
            </Space>
          ),
        },
        {
          colKey: 'actor',
          title: '操作人',
          width: 180,
          cell: ({ row }) => (
            <Space direction="vertical" size={2}>
              <Typography.Text>{row.actorUsername || '系统'}</Typography.Text>
              <Typography.Text theme="secondary">{row.actorRole || '未记录角色'}</Typography.Text>
            </Space>
          ),
        },
        {
          colKey: 'note',
          title: '说明',
          ellipsis: true,
          cell: ({ row }) => <Typography.Text>{row.note || '—'}</Typography.Text>,
        },
      ]}
    />
  </Card>
);

export type BusinessWalletSettlement = {
  status?: string;
  method?: string;
  traceId?: string;
  refundTraceId?: string;
  points?: number;
  balance?: number;
  units?: number;
  remainingUnits?: number;
  packageKey?: string;
  packageName?: string;
  transactionId?: string;
  ledgerId?: string;
  refundTransactionId?: string;
  refundLedgerId?: string;
  idempotent?: boolean;
  refundIdempotent?: boolean;
  error?: string;
};

export const getBusinessWalletSettlement = (row?: BusinessRun | null): BusinessWalletSettlement | null => {
  const costBreakdown = row?.costBreakdown;
  if (!costBreakdown || typeof costBreakdown !== 'object') return null;
  const record = costBreakdown as Record<string, unknown>;
  const raw = record.billingSettlement || record.packageSettlement || record.walletSettlement;
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return null;
  return raw as BusinessWalletSettlement;
};

export const businessWalletStatusLabel = (settlement?: BusinessWalletSettlement | null) => {
  if (!settlement) return '未扣费';
  const methodLabel = settlement.method === 'package' ? '套餐' : '钱包';
  if (settlement.status === 'settled') return `${methodLabel}已扣`;
  if (settlement.status === 'failed') return `${methodLabel}扣减失败`;
  if (settlement.status === 'refunded') return '已退回';
  return settlement.status || '未扣费';
};

export const businessWalletStatusTheme = (settlement?: BusinessWalletSettlement | null) => {
  if (settlement?.status === 'settled') return 'success';
  if (settlement?.status === 'failed') return 'danger';
  if (settlement?.status === 'refunded') return 'warning';
  return 'default';
};

export const businessWalletSummary = (settlement?: BusinessWalletSettlement | null) => {
  if (!settlement) return '未产生套餐或钱包流水';
  const parts = [
    settlement.method === 'package' ? '套餐扣减' : '',
    settlement.method === 'wallet' ? '钱包扣费' : '',
    settlement.packageName || settlement.packageKey || '',
    settlement.units !== undefined ? `${settlement.units} 次` : '',
    settlement.remainingUnits !== undefined ? `剩余 ${settlement.remainingUnits}` : '',
    settlement.points !== undefined ? `${settlement.points} 点` : '',
    settlement.balance !== undefined ? `余额 ${settlement.balance}` : '',
    settlement.idempotent ? '重复查询已去重' : '',
    settlement.refundIdempotent ? '重复退回已去重' : '',
  ].filter(Boolean);
  return parts.join(' · ') || businessWalletStatusLabel(settlement);
};

export const businessCallbackStatusLabel = (status?: string | null) => {
  if (status === 'success') return '回调成功';
  if (status === 'failed') return '回调失败';
  if (status === 'running') return '回调中';
  if (status) return status;
  return '未配置回调';
};

export const businessCallbackStatusTheme = (status?: string | null) => {
  if (status === 'success') return 'success';
  if (status === 'failed') return 'danger';
  if (status === 'running') return 'warning';
  return 'default';
};

export const businessRunStepSummaryLabel = (summary?: JsonRecord | null) => {
  if (!summary || typeof summary !== 'object') return '';
  const text = summary.summary || summary.imageDesc || summary.textPreview;
  if (typeof text === 'string' && text.trim()) {
    const value = text.trim();
    return value.length > 24 ? `${value.slice(0, 24)}...` : value;
  }
  const imageCount = Number(summary.imageCount || 0);
  const videoCount = Number(summary.videoCount || 0);
  const structuredCount = Number(summary.structuredCount || 0);
  const resourceCount = Number(summary.resourceCount || 0);
  if (imageCount > 0) return `${imageCount} 张图`;
  if (videoCount > 0) return `${videoCount} 个视频`;
  if (structuredCount > 0) return `${structuredCount} 个结构化结果`;
  if (resourceCount > 0) return `${resourceCount} 个资源`;
  return '';
};

export const businessRunOutputLabel = (row?: BusinessRun | null) => {
  if (!row) return '—';
  const output = asJsonRecord(row.flowSummary?.output);
  const structuredCount = recordNumber(output, 'structuredCount', 0);
  const resourceCount = recordNumber(output, 'resourceCount', 0);
  const parts = [
    (row.imageUrls || []).length > 0 ? `${(row.imageUrls || []).length} 张图` : '',
    (row.videoUrls || []).length > 0 ? `${(row.videoUrls || []).length} 个视频` : '',
    (row.texts || []).length > 0 ? `${(row.texts || []).length} 段文字` : '',
    structuredCount > 0 ? `${structuredCount} 个结构化结果` : '',
    resourceCount > 0 ? `${resourceCount} 个资源` : '',
  ].filter(Boolean);
  return parts.join(' · ') || '无输出';
};

export const businessRunFlowSummaryLabel = (row?: BusinessRun | null) => {
  const summary = row?.flowSummary;
  if (!summary) return '未记录业务链路';
  const total = Number(summary.total || 0);
  if (total <= 0) return summary.message || '未记录业务链路';
  if (businessRunIsFinished(row?.status)) {
    return [summary.message || '业务链路执行完成', `输出：${businessRunOutputLabel(row)}`]
      .filter(Boolean)
      .join(' · ');
  }
  const progress = typeof summary.progressPercent === 'number' ? `${summary.progressPercent}%` : '—';
  const current = summary.currentStepLabel ? `当前：${summary.currentStepLabel}` : '';
  return [summary.message || `${total} 个步骤`, `进度 ${progress}`, current].filter(Boolean).join(' · ');
};

export const businessRecipeStepLabel = (type?: string | null, role?: string | null) => {
  if (role === 'primary') return '主执行';
  if (role === 'preprocess') return '前置分析';
  if (role === 'input') return '输入';
  if (role === 'output') return '输出';
  if (type === 'input') return '输入';
  if (type === 'input_mapping') return '参数整理';
  if (type === 'prompt_template') return '提示词组装';
  if (type === 'vl_analyze' || type === 'vl_analyze_image') return '图像理解';
  if (type === 'comfyui_workflow') return '生图工作流';
  if (type === 'vendor_api') return '商业模型/API';
  if (type === 'ability_task') return '原子能力';
  if (type === 'condition') return '条件判断';
  if (type === 'fanout') return '批量分发';
  if (type === 'merge') return '结果合并';
  if (type === 'output_mapping') return '结果整理';
  if (type === 'callback') return '回调通知';
  return type || '步骤';
};

const businessRecipeComponentKindLabel = (kind?: string | null) => {
  if (kind === 'execution') return '执行';
  if (kind === 'control') return '控制';
  if (kind === 'passive') return '说明';
  return '组件';
};

const businessRecipeComponentTheme = (kind?: string | null) => {
  if (kind === 'execution') return 'primary';
  if (kind === 'control') return 'warning';
  if (kind === 'passive') return 'default';
  return 'default';
};

const formatBusinessStepList = (value?: string[] | null) => {
  if (!Array.isArray(value) || value.length === 0) return '';
  return value.slice(0, 4).join('、') + (value.length > 4 ? ` 等 ${value.length} 项` : '');
};

const formatDurationMs = (value?: number | null) => {
  if (value === undefined || value === null) return '—';
  if (value < 1000) return `${value}ms`;
  return `${(value / 1000).toFixed(2)}s`;
};

type BusinessRecipeFlowStep = Partial<Omit<BusinessRecipeStep, 'id'>> &
  Partial<Omit<BusinessRunStep, 'id'>> & {
    id?: string | null;
  };

export const BusinessRecipeFlow = ({
  steps,
  compact = false,
  showRuntime = false,
}: {
  steps?: BusinessRecipeFlowStep[] | null;
  compact?: boolean;
  showRuntime?: boolean;
}) => {
  const visibleSteps = (steps || []).filter((step) => step && step.enabled !== false);
  if (visibleSteps.length === 0) {
    return <Typography.Text theme="secondary">暂无业务流程步骤。</Typography.Text>;
  }
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: compact ? '1fr' : 'repeat(auto-fit, minmax(190px, 1fr))',
        gap: 10,
        width: '100%',
      }}
    >
      {visibleSteps.map((step, index) => {
        const stepType = step.type || step.stepType || 'ability_task';
        const role = step.role || undefined;
        const label = step.componentLabel || businessRecipeStepLabel(stepType, role);
        const kind = step.componentKind || (step.abilityId ? 'execution' : 'passive');
        const title = step.displayName || step.abilityName || label;
        const order = step.order || index + 1;
        const dependsOn = formatBusinessStepList(step.dependsOn);
        const outputs = formatBusinessStepList(step.outputs);
        const inputs = formatBusinessStepList(step.inputs);
        return (
          <Card key={`${order}-${step.id || step.stepId || step.abilityId || stepType}`} bordered size="small">
            <Space direction="vertical" size={4} style={{ width: '100%' }}>
              <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
                <Tag theme={businessRecipeComponentTheme(kind) as any} variant="light">
                  {order}. {label}
                </Tag>
                <Tag variant="light">{businessRecipeComponentKindLabel(kind)}</Tag>
              </Space>
              <Typography.Text strong>{title}</Typography.Text>
              <Typography.Text theme="secondary">
                {step.componentDescription || step.abilityName || step.abilityId || '用于业务流程审阅。'}
              </Typography.Text>
              {showRuntime && step.status ? (
                <Space align="center" size={6}>
                  <Typography.Text theme="secondary">状态</Typography.Text>
                  <StatusBadge status={step.status} />
                  {step.durationMs ? <Typography.Text theme="secondary">{formatDurationMs(step.durationMs)}</Typography.Text> : null}
                </Space>
              ) : null}
              {step.abilityName || step.abilityId ? (
                <Typography.Text theme="secondary">
                  执行能力：{step.abilityName || step.abilityId}
                </Typography.Text>
              ) : null}
              {dependsOn ? <Typography.Text theme="secondary">依赖：{dependsOn}</Typography.Text> : null}
              {inputs ? <Typography.Text theme="secondary">输入：{inputs}</Typography.Text> : null}
              {outputs ? <Typography.Text theme="secondary">输出：{outputs}</Typography.Text> : null}
              {step.onError ? <Typography.Text theme="secondary">失败策略：{step.onError}</Typography.Text> : null}
              {step.error ? <Typography.Text theme="error">错误：{step.error}</Typography.Text> : null}
            </Space>
          </Card>
        );
      })}
    </div>
  );
};

const readCapabilityRollout = (metadata?: JsonRecord | null) => {
  const rollout = metadata && typeof metadata.rollout === 'object' && !Array.isArray(metadata.rollout)
    ? (metadata.rollout as JsonRecord)
    : {};
  const allowlist = Array.isArray(rollout.allowlist) ? rollout.allowlist : [];
  const percent = Number(rollout.percent || 0);
  return {
    enabled: Boolean(rollout.enabled),
    percent: Number.isFinite(percent) ? percent : 0,
    allowlistText: allowlist.map((item) => String(item)).join('\n'),
  };
};

const businessCapabilityGroupHint = (businessKey?: string | null) => {
  if (businessKey === 'pattern_extract') return '从原图中提取可复用花纹资产，是后续裂变和扩图的上游入口。';
  if (businessKey === 'fission') return '围绕原图生成多张变化图，是当前最核心的业务入口。';
  if (businessKey === 'outpaint') return '在原图基础上向外扩展画面，主要服务构图补全和素材延展。';
  return '承载一个对业务方稳定暴露的功能入口，底层能力可以独立换版本。';
};

const businessCapabilityMediaLabel = (item: BusinessCapability) => {
  const key = item.businessKey;
  if (key === 'pattern_extract') return '输入图片 · 输出花纹图';
  if (key === 'fission') return '输入图片 · 输出多张图';
  if (key === 'outpaint') return '输入图片 · 输出扩展图';
  const output = item.outputSchema || {};
  const text = JSON.stringify(output).toLowerCase();
  if (text.includes('video')) return '输出视频';
  if (text.includes('text')) return '输出文字';
  if (text.includes('image')) return '输出图片';
  return '按接口配置输出';
};

const businessCapabilityRiskTag = (item: BusinessCapability) => {
  if (item.status !== 'active') {
    return { theme: 'default', text: '未对外启用', detail: '不会承接新的业务请求。' };
  }
  if (!item.primaryAbilityId && !item.primaryAbilityName) {
    return { theme: 'danger', text: '缺底层能力', detail: '需要先绑定实际执行能力。' };
  }
  if (item.releaseGate?.status === 'blocked') {
    return {
      theme: 'danger',
      text: '未满足上线',
      detail: item.releaseGate.suggestions?.[0] || '需要先完成真实链路验收。',
    };
  }
  if (item.latestRun?.error || Number(item.runMetrics?.failed || 0) > 0) {
    return { theme: 'warning', text: '最近有失败', detail: businessCapabilityLatestRunLabel(item) };
  }
  if (item.releaseGate?.status === 'warning') {
    return { theme: 'warning', text: '上线需复核', detail: item.releaseGate.suggestions?.[0] || '上线前仍有风险项需要确认。' };
  }
  if (item.isDefault) {
    return { theme: 'success', text: '生产默认', detail: '当前业务入口默认使用这个版本。' };
  }
  return { theme: 'primary', text: '备用版本', detail: '可用于灰度、对照或回滚。' };
};

const businessCoreEntrySuggestion = ({
  defaultItem,
  activeCount,
  hasPendingApproval,
}: {
  defaultItem?: BusinessCapability;
  activeCount: number;
  hasPendingApproval: boolean;
}) => {
  if (!defaultItem) return '先补一个启用版本并设为默认，否则业务方没有稳定入口。';
  if (defaultItem.status !== 'active') return '默认版本未启用，先启用或切换到可用版本。';
  if (!defaultItem.primaryAbilityId && !defaultItem.primaryAbilityName) return '默认版本缺少底层能力，先绑定真实执行能力。';
  if (defaultItem.governanceStatus === 'blocker') {
    return defaultItem.governanceSuggestions?.[0] || '默认版本底层治理未通过，先补能力、模型、密钥或执行线路。';
  }
  if (defaultItem.releaseGate?.status === 'blocked') {
    return defaultItem.releaseGate.suggestions?.[0] || '默认版本未满足上线门禁，先跑真实链路并记录验收通过。';
  }
  if (defaultItem.releaseGate?.acceptancePassed === false || defaultItem.latestAcceptance?.status !== 'passed') {
    return '默认版本还没有验收通过记录，先跑真实链路测试并记录验收证据。';
  }
  if (defaultItem.latestRun?.error || Number(defaultItem.runMetrics?.failed || 0) > 0) return '最近有失败样本，先打开运行记录确认卡点。';
  if (hasPendingApproval) return '存在默认版本切换审批，先处理审批再对外说明。';
  if (defaultItem.releaseGate?.status === 'warning') return defaultItem.releaseGate.suggestions?.[0] || '上线前仍有风险项，先完成复核再小流量验证。';
  if (activeCount < 2) return '建议保留一个可用备选版本，便于灰度和快速回滚。';
  return '入口稳定，可进入测评端或小流量业务验证。';
};

export const BusinessCoreClosurePanel = ({
  capabilities,
  pendingApprovals,
  summary,
  formatDateTime,
}: {
  capabilities: BusinessCapability[];
  pendingApprovals: BusinessDefaultApproval[];
  summary?: BusinessUsageSummaryResponse | null;
  formatDateTime: (value?: string | null) => string;
}) => {
  const rows = buildCoreBusinessReleaseEvidenceRows({ capabilities, pendingApprovals, summary });

  return (
    <Card
      bordered
      className="podi-business-closure-card"
      title={
        <Space align="center" style={{ justifyContent: 'space-between', width: '100%', flexWrap: 'wrap' }}>
          <div>
            <Typography.Text strong>三主业务闭环总表</Typography.Text>
            <div>
              <Typography.Text theme="secondary">
                一张表核对默认版本、验收、真实样本、回调、计费和回滚；先看这里，再进入版本卡片或运行记录。
              </Typography.Text>
            </div>
          </div>
          <Tag theme={rows.every((row) => row.theme === 'success') ? 'success' : rows.some((row) => row.theme === 'danger') ? 'danger' : 'warning'} variant="light">
            {rows.filter((row) => row.theme === 'success').length}/{rows.length} 闭环正常
          </Tag>
        </Space>
      }
    >
      <div className="podi-business-closure-grid">
        {rows.map((row) => (
          <section key={row.businessKey} className={`podi-business-closure-item podi-business-closure-item--${row.theme}`}>
            <div className="podi-business-closure-item__header">
              <div>
                <Typography.Text strong>{businessKeyLabel(row.businessKey)}</Typography.Text>
                <div>
                  <Typography.Text theme="secondary">{businessCapabilityGroupHint(row.businessKey)}</Typography.Text>
                </div>
              </div>
              <Tag theme={row.theme} variant="light">
                {row.status}
              </Tag>
            </div>
            <div className="podi-business-closure-item__version">
              <Typography.Text theme="secondary">当前默认</Typography.Text>
              <Typography.Text>
                {row.defaultItem ? `${row.defaultItem.version} · ${row.defaultItem.displayName}` : '未设置默认版本'}
              </Typography.Text>
              <Typography.Text theme="secondary">
                发布时间：{row.defaultItem ? formatDateTime(row.defaultItem.releaseTime || row.defaultItem.createdAt) : '—'}
              </Typography.Text>
            </div>
            <div className="podi-business-closure-checks">
              {row.checks.map((check) => (
                <Tag key={check.key} theme={check.theme} variant="light" size="small">
                  {check.label}
                </Tag>
              ))}
            </div>
            <div className="podi-business-closure-metrics">
              <span>近 {summary?.windowHours || 24} 小时</span>
              <strong>{row.bucket?.total || 0}</strong>
              <span>成功 {row.bucket?.succeeded || 0} / 失败 {row.bucket?.failed || 0} / 运行 {Number(row.bucket?.running || 0) + Number(row.bucket?.queued || 0)}</span>
              <span>成功率 {formatRatePercent(row.bucket?.successRate)}</span>
            </div>
            <div className="podi-business-closure-item__footer">
              <Typography.Text theme={row.theme === 'danger' ? 'error' : row.theme === 'warning' ? 'warning' : 'secondary'}>
                {row.suggestion}
              </Typography.Text>
            </div>
          </section>
        ))}
      </div>
    </Card>
  );
};

export const BusinessCoreEntryPanel = ({
  capabilities,
  pendingApprovals,
  formatDateTime,
}: {
  capabilities: BusinessCapability[];
  pendingApprovals: BusinessDefaultApproval[];
  formatDateTime: (value?: string | null) => string;
}) => {
  const rows = coreBusinessKeys.map((businessKey) => {
    const items = capabilities.filter((item) => item.businessKey === businessKey);
    const defaultItem = items.find((item) => item.isDefault);
    const activeCount = items.filter((item) => item.status === 'active').length;
    const hasPendingApproval = pendingApprovals.some((item) => item.businessKey === businessKey && item.status === 'pending');
    const risk = defaultItem ? businessCapabilityRiskTag(defaultItem) : { theme: 'danger', text: '缺默认入口', detail: '业务方无法稳定调用。' };
    return {
      businessKey,
      items,
      defaultItem,
      activeCount,
      hasPendingApproval,
      risk,
      suggestion: businessCoreEntrySuggestion({ defaultItem, activeCount, hasPendingApproval }),
    };
  });

  return (
    <Card bordered title="核心业务入口总览">
      <Row gutter={[12, 12]}>
        {rows.map((row) => (
          <Col key={row.businessKey} xs={12} lg={4}>
            <Card bordered size="small" style={{ height: '100%' }}>
              <Space direction="vertical" size="small" style={{ width: '100%' }}>
                <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
                  <Typography.Text strong>{businessKeyLabel(row.businessKey)}</Typography.Text>
                  <Tag theme={row.risk.theme as any} variant="light">
                    {row.risk.text}
                  </Tag>
                </Space>
                <Typography.Text theme="secondary">{businessCapabilityGroupHint(row.businessKey)}</Typography.Text>
                <div>
                  <Typography.Text theme="secondary">默认版本</Typography.Text>
                  <div>
                    <Typography.Text>
                      {row.defaultItem ? `${row.defaultItem.version} · ${row.defaultItem.displayName}` : '未设置'}
                    </Typography.Text>
                  </div>
                </div>
                <Space size={6} style={{ flexWrap: 'wrap' }}>
                  <Tag theme={row.defaultItem?.status === 'active' ? 'success' : 'warning'} variant="light">
                    启用 {row.activeCount}/{row.items.length}
                  </Tag>
                  <Tag variant="light">{row.defaultItem ? businessCapabilityMediaLabel(row.defaultItem) : '缺输出定义'}</Tag>
                  {row.hasPendingApproval ? (
                    <Tag theme="warning" variant="light">
                      有切换审批
                    </Tag>
                  ) : null}
                </Space>
                <div>
                  <Typography.Text theme="secondary">最近结果</Typography.Text>
                  <div>
                    <Space size={6}>
                      {row.defaultItem?.latestRun ? <StatusBadge status={row.defaultItem.latestRun.status} /> : null}
                      <Typography.Text theme={row.defaultItem?.latestRun?.error ? 'error' : 'secondary'}>
                        {row.defaultItem ? businessCapabilityLatestRunLabel(row.defaultItem) : '无运行记录'}
                      </Typography.Text>
                    </Space>
                  </div>
                </div>
                <Typography.Text theme="secondary">
                  发布时间：{row.defaultItem ? formatDateTime(row.defaultItem.releaseTime || row.defaultItem.createdAt) : '—'}
                </Typography.Text>
                <Typography.Text theme={row.risk.theme === 'danger' ? 'error' : row.risk.theme === 'warning' ? 'warning' : 'secondary'}>
                  {row.suggestion}
                </Typography.Text>
              </Space>
            </Card>
          </Col>
        ))}
      </Row>
    </Card>
  );
};

export const BusinessOrchestrationMapPanel = ({
  capabilities,
  pendingApprovals,
  formatDateTime,
}: {
  capabilities: BusinessCapability[];
  pendingApprovals: BusinessDefaultApproval[];
  formatDateTime: (value?: string | null) => string;
}) => {
  const rows = coreBusinessKeys.map((businessKey) => {
    const items = capabilities.filter((item) => item.businessKey === businessKey);
    const defaultItem = items.find((item) => item.isDefault);
    const activeAlternatives = items.filter((item) => item.status === 'active' && !item.isDefault);
    const rollbackReadyAlternatives = activeAlternatives.filter(businessCapabilityHasRollbackEvidence);
    const hasPendingApproval = pendingApprovals.some((item) => item.businessKey === businessKey && item.status === 'pending');
    const rollout = readCapabilityRollout(defaultItem?.metadata);
    const risk = defaultItem ? businessCapabilityRiskTag(defaultItem) : { theme: 'danger', text: '缺默认入口', detail: '业务方无法稳定调用。' };
    return {
      businessKey,
      defaultItem,
      activeAlternatives,
      rollbackReadyAlternatives,
      hasPendingApproval,
      rollout,
      risk,
      suggestion: businessCoreEntrySuggestion({
        defaultItem,
        activeCount: items.filter((item) => item.status === 'active').length,
        hasPendingApproval,
      }),
    };
  });

  return (
    <Card
      bordered
      title={
        <Space align="center" style={{ justifyContent: 'space-between', width: '100%', flexWrap: 'wrap' }}>
          <div>
            <Typography.Text strong>主业务编排地图</Typography.Text>
            <div>
              <Typography.Text theme="secondary">
                按业务方看到的入口来审阅：生产版本、灰度/回滚、底层步骤和当前建议放在同一张图里。
              </Typography.Text>
            </div>
          </div>
          <Tag theme="primary" variant="light">
            类似 Coze 工作流视角
          </Tag>
        </Space>
      }
    >
      <Row gutter={[12, 12]}>
        {rows.map((row) => (
          <Col key={row.businessKey} xs={12} xl={4}>
            <Card bordered size="small" style={{ height: '100%' }}>
              <Space direction="vertical" size="small" style={{ width: '100%' }}>
                <Space align="center" style={{ justifyContent: 'space-between', width: '100%', gap: 8 }}>
                  <div>
                    <Typography.Text strong>{businessKeyLabel(row.businessKey)}</Typography.Text>
                    <div>
                      <Typography.Text theme="secondary">{businessCapabilityGroupHint(row.businessKey)}</Typography.Text>
                    </div>
                  </div>
                  <Tag theme={row.risk.theme as any} variant="light">
                    {row.risk.text}
                  </Tag>
                </Space>
                <Card bordered size="small" className="podi-business-orchestration-entry">
                  <Space direction="vertical" size={4} style={{ width: '100%' }}>
                    <Typography.Text theme="secondary">生产入口</Typography.Text>
                    <Typography.Text strong>
                      {row.defaultItem ? `${row.defaultItem.version} · ${row.defaultItem.displayName}` : '未设置默认版本'}
                    </Typography.Text>
                    <Typography.Text theme="secondary">
                      发布时间：{row.defaultItem ? formatDateTime(row.defaultItem.releaseTime || row.defaultItem.createdAt) : '—'}
                    </Typography.Text>
                    <Space size={6} breakLine>
                      <Tag theme={row.defaultItem?.status === 'active' ? 'success' : 'warning'} variant="light">
                        {row.defaultItem?.status === 'active' ? '已启用' : '未启用'}
                      </Tag>
                      <Tag theme={row.rollout.enabled ? 'warning' : 'default'} variant="light">
                        灰度 {row.rollout.enabled ? `${row.rollout.percent}%` : '关闭'}
                      </Tag>
                      <Tag theme={row.rollbackReadyAlternatives.length > 0 ? 'success' : 'warning'} variant="light">
                        {row.rollbackReadyAlternatives.length > 0
                          ? `可回滚 ${row.rollbackReadyAlternatives.length}`
                          : `备选 ${row.activeAlternatives.length}`}
                      </Tag>
                      {row.hasPendingApproval ? <Tag theme="warning" variant="light">切换审批中</Tag> : null}
                    </Space>
                  </Space>
                </Card>
                <Space direction="vertical" size={6} style={{ width: '100%' }}>
                  <Typography.Text theme="secondary">底层编排</Typography.Text>
                  <BusinessRecipeFlow steps={row.defaultItem?.recipeSteps || []} compact />
                </Space>
                <Alert
                  theme={row.risk.theme === 'danger' ? 'error' : row.risk.theme === 'warning' ? 'warning' : 'info'}
                  message={`当前建议：${row.suggestion}`}
                />
              </Space>
            </Card>
          </Col>
        ))}
      </Row>
    </Card>
  );
};

const businessCapabilityGroupSortValue = (businessKey?: string | null) => {
  const index = coreBusinessKeys.indexOf((businessKey || '') as (typeof coreBusinessKeys)[number]);
  return index >= 0 ? index : coreBusinessKeys.length;
};

const businessReleaseGateIssueLabel = (value?: string | null) => {
  const labels: Record<string, string> = {
    BUSINESS_RELEASE_VERSION_INACTIVE: '业务版本未启用',
    BUSINESS_RELEASE_PRIMARY_ABILITY_REQUIRED: '未绑定真实主能力',
    BUSINESS_RELEASE_GOVERNANCE_BLOCKED: '底层能力或模型治理未通过',
    BUSINESS_RELEASE_GOVERNANCE_WARNING: '底层治理信息需要补齐',
    BUSINESS_RELEASE_ACCEPTANCE_REQUIRED: '缺少真实链路验收记录',
    BUSINESS_RELEASE_LATEST_RUN_FAILED: '最近一次运行失败',
    BUSINESS_RELEASE_RECENT_FAILURES: '近期存在失败样本',
  };
  return labels[value || ''] || value || '';
};

function BusinessCapabilityReleaseEvidence({
  item,
  formatDateTime,
}: {
  item: BusinessCapability;
  formatDateTime: (value?: string | null) => string;
}) {
  const latestAcceptance = item.latestAcceptance;
  const releaseGate = item.releaseGate || null;
  const blockers = (releaseGate?.blockers || []).map((item) => businessReleaseGateIssueLabel(item)).filter(Boolean);
  const warnings = (releaseGate?.warnings || []).map((item) => businessReleaseGateIssueLabel(item)).filter(Boolean);
  const suggestions = releaseGate?.suggestions || [];
  const latestRun = item.latestRun;
  const outputCount = Number(latestRun?.imageCount || latestRun?.image_count || 0) + Number(latestRun?.videoCount || latestRun?.video_count || 0);
  const governanceTags = [
    {
      key: 'governance',
      label: businessGovernanceStatusLabel(item.governanceStatus),
      theme: businessGovernanceStatusTheme(item.governanceStatus),
    },
    {
      key: 'key',
      label: item.runtimeKeyConfigured === false ? '密钥缺失' : item.runtimeKeyConfigured === true ? '密钥可用' : '密钥未确认',
      theme: item.runtimeKeyConfigured === false ? 'danger' : item.runtimeKeyConfigured === true ? 'success' : 'default',
    },
    {
      key: 'cost',
      label: item.modelCostConfigured === false ? '成本缺失' : item.modelCostConfigured === true ? '成本已配' : '成本未确认',
      theme: item.modelCostConfigured === false ? 'warning' : item.modelCostConfigured === true ? 'success' : 'default',
    },
    item.egressVerified !== null && item.egressVerified !== undefined
      ? {
          key: 'egress',
          label: item.egressVerified ? '出网已验' : '出网未验',
          theme: item.egressVerified ? 'success' : 'warning',
        }
      : null,
  ].filter(Boolean) as Array<{ key: string; label: string; theme: 'success' | 'warning' | 'danger' | 'default' }>;

  return (
    <Card bordered size="small">
      <Space direction="vertical" size={6} style={{ width: '100%' }}>
        <Space align="center" style={{ justifyContent: 'space-between', width: '100%', flexWrap: 'wrap' }}>
          <Typography.Text strong>上线证据</Typography.Text>
          <Tag theme={businessReleaseGateStatusTheme(releaseGate?.status)} variant="light">
            {releaseGate?.label || businessReleaseGateLabel(releaseGate?.status)}
          </Tag>
        </Space>
        <Space size={6} breakLine>
          <Tag theme={businessAcceptanceStatusTheme(latestAcceptance?.status)} variant="light">
            {businessAcceptanceStatusLabel(latestAcceptance?.status)}
          </Tag>
          {latestAcceptance?.createdAt ? (
            <Typography.Text theme="secondary">{formatDateTime(latestAcceptance.createdAt)}</Typography.Text>
          ) : null}
          {latestAcceptance?.evidenceRunId ? (
            <Typography.Text theme="secondary">证据：{formatShortBusinessId(latestAcceptance.evidenceRunId)}</Typography.Text>
          ) : null}
          {latestAcceptance?.evidenceUrl ? (
            <Button size="small" variant="text" onClick={() => window.open(latestAcceptance.evidenceUrl || '', '_blank', 'noreferrer')}>
              打开证据
            </Button>
          ) : null}
        </Space>
        {latestAcceptance?.note ? <Typography.Text theme="secondary">{latestAcceptance.note}</Typography.Text> : null}
        <Space size={6} breakLine>
          {latestRun ? <StatusBadge status={latestRun.status} /> : <Tag variant="light">暂无真实样本</Tag>}
          <Typography.Text theme={latestRun?.error ? 'error' : 'secondary'}>
            {latestRun ? `最近样本：${businessCapabilityLatestRunLabel(item)}${outputCount > 0 ? ` · 输出 ${outputCount} 个` : ''}` : '还没有运行记录'}
          </Typography.Text>
        </Space>
        <Space size={6} breakLine>
          {governanceTags.map((tag) => (
            <Tag key={tag.key} theme={tag.theme} variant="light" size="small">
              {tag.label}
            </Tag>
          ))}
        </Space>
        {(blockers.length > 0 || warnings.length > 0 || suggestions.length > 0) ? (
          <Typography.Text theme={blockers.length > 0 ? 'error' : warnings.length > 0 ? 'warning' : 'secondary'}>
            {[...blockers, ...warnings, ...suggestions].slice(0, 2).join('；')}
          </Typography.Text>
        ) : (
          <Typography.Text theme="secondary">暂无门禁阻塞；上线前仍需保留一次真实链路验收记录。</Typography.Text>
        )}
      </Space>
    </Card>
  );
}

function BusinessCapabilityTechnicalDetails({ item }: { item: BusinessCapability }) {
  const primaryAbility = item.primaryAbilityName || item.primaryAbilityId || String(item.recipe?.primaryAbilityId || '未配置');
  const vendorModel = item.vendorModelName || item.vendorModelProvider || '未绑定';
  const governanceIssues = item.governanceIssues || [];
  const governanceSuggestions = item.governanceSuggestions || [];

  return (
    <details className="podi-business-technical-details">
      <summary>底层信息：能力、模型、配方</summary>
      <div className="podi-business-technical-details__body">
        <div>
          <Typography.Text theme="secondary">主执行能力</Typography.Text>
          <Typography.Text>{primaryAbility}</Typography.Text>
        </div>
        <div>
          <Typography.Text theme="secondary">模型来源</Typography.Text>
          <Typography.Text>{vendorModel}</Typography.Text>
        </div>
        <div>
          <Typography.Text theme="secondary">底层治理</Typography.Text>
          <Space size={6} breakLine>
            <Tag theme={businessGovernanceStatusTheme(item.governanceStatus)} variant="light" size="small">
              {businessGovernanceStatusLabel(item.governanceStatus)}
            </Tag>
            {item.primaryAbilityProvider ? (
              <Tag variant="light" size="small">
                {item.primaryAbilityProvider}
              </Tag>
            ) : null}
            {item.vendorModelProvider ? (
              <Tag variant="light" size="small">
                {item.vendorModelProvider}
              </Tag>
            ) : null}
          </Space>
        </div>
        {governanceIssues.length > 0 || governanceSuggestions.length > 0 ? (
          <Typography.Text theme={item.governanceStatus === 'blocker' ? 'error' : 'warning'}>
            {[...governanceIssues.map((value) => businessGovernanceIssueLabel(value)), ...governanceSuggestions].slice(0, 3).join('；')}
          </Typography.Text>
        ) : null}
        {item.recipeSteps && item.recipeSteps.length > 0 ? (
          <div>
            <Typography.Text theme="secondary">业务流程</Typography.Text>
            <div style={{ marginTop: 8 }}>
              <BusinessRecipeFlow steps={item.recipeSteps} compact />
            </div>
          </div>
        ) : null}
      </div>
    </details>
  );
}

export const BusinessCapabilityGrid = ({
  capabilities,
  pendingApprovals,
  isReadOnly,
  actionLoadingId,
  onEdit,
  onSetDefault,
  onToggleActive,
  onRecordAcceptance,
  formatDateTime,
}: {
  capabilities: BusinessCapability[];
  pendingApprovals: BusinessDefaultApproval[];
  isReadOnly: boolean;
  actionLoadingId?: string | null;
  onEdit: (item: BusinessCapability) => void;
  onSetDefault: (item: BusinessCapability) => void;
  onToggleActive: (item: BusinessCapability) => void;
  onRecordAcceptance: (item: BusinessCapability) => void;
  formatDateTime: (value?: string | null) => string;
}) => {
  const grouped = capabilities.reduce<Record<string, BusinessCapability[]>>((map, item) => {
    const key = item.businessKey || 'other';
    map[key] = map[key] || [];
    map[key].push(item);
    return map;
  }, {});
  const groupKeys = Object.keys(grouped).sort((left, right) => {
    const diff = businessCapabilityGroupSortValue(left) - businessCapabilityGroupSortValue(right);
    return diff !== 0 ? diff : left.localeCompare(right);
  });

  if (capabilities.length === 0) {
    return (
      <Card bordered>
        <Typography.Text theme="secondary">暂无业务版本。请先新增花纹提取、图裂变或扩图的业务入口。</Typography.Text>
      </Card>
    );
  }

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      {groupKeys.map((businessKey) => {
        const items = grouped[businessKey].slice().sort((left, right) => {
          if (left.isDefault !== right.isDefault) return left.isDefault ? -1 : 1;
          if (left.status !== right.status) return left.status === 'active' ? -1 : 1;
          return String(right.releaseTime || right.createdAt || '').localeCompare(String(left.releaseTime || left.createdAt || ''));
        });
        const defaultItem = items.find((item) => item.isDefault);
        const activeCount = items.filter((item) => item.status === 'active').length;
        return (
          <Card
            key={businessKey}
            bordered
            title={
              <Space align="center" style={{ justifyContent: 'space-between', width: '100%', flexWrap: 'wrap' }}>
                <div>
                  <Typography.Text strong>{businessKeyLabel(businessKey)}</Typography.Text>
                  <div>
                    <Typography.Text theme="secondary">{businessCapabilityGroupHint(businessKey)}</Typography.Text>
                  </div>
                </div>
                <Space breakLine>
                  <Tag theme={defaultItem ? 'success' : 'danger'} variant="light">
                    默认：{defaultItem ? `${defaultItem.version} · ${defaultItem.displayName}` : '未设置'}
                  </Tag>
                  <Tag variant="light">启用 {activeCount}/{items.length}</Tag>
                </Space>
              </Space>
            }
          >
            <Row gutter={[16, 16]}>
              {items.map((item) => {
                const rollout = readCapabilityRollout(item.metadata);
                const risk = businessCapabilityRiskTag(item);
                const defaultActionId = `default:${item.id}`;
                const statusActionId = `status:${item.id}`;
                const acceptanceActionId = `acceptance:${item.id}`;
                const isActive = item.status === 'active';
                const lockDefaultStop = isActive && item.isDefault;
                const actionBusy = Boolean(actionLoadingId);
                const defaultSwitchBlocked = item.releaseGate?.canRequestDefault === false;
                const pendingApproval = pendingApprovals.find(
                  (approval) => approval.targetCapabilityId === item.id && approval.status === 'pending',
                );

                return (
                  <Col key={item.id} xs={12} md={6} xl={4}>
                    <Card bordered size="small" style={{ height: '100%' }}>
                      <Space direction="vertical" size="small" style={{ width: '100%' }}>
                        <Space align="start" style={{ justifyContent: 'space-between', width: '100%', gap: 10 }}>
                          <div style={{ minWidth: 0 }}>
                            <Typography.Text strong>{item.displayName}</Typography.Text>
                            <div>
                              <Typography.Text theme="secondary">
                                {item.version} · {businessCapabilityMediaLabel(item)}
                              </Typography.Text>
                            </div>
                          </div>
                          <Tag theme={risk.theme as any} variant="light">
                            {risk.text}
                          </Tag>
                        </Space>
                        <Typography.Text theme="secondary">{item.description || risk.detail}</Typography.Text>
                        <Row gutter={[8, 8]}>
                          <Col span={6}>
                            <Typography.Text theme="secondary">发布时间</Typography.Text>
                            <div>
                              <Typography.Text>{formatDateTime(item.releaseTime || item.createdAt)}</Typography.Text>
                            </div>
                          </Col>
                          <Col span={6}>
                            <Typography.Text theme="secondary">最近结果</Typography.Text>
                            <div>
                              <Space size={4}>
                                {item.latestRun ? <StatusBadge status={item.latestRun.status} /> : null}
                                <Typography.Text theme={item.latestRun?.error ? 'error' : 'secondary'}>
                                  {businessCapabilityLatestRunLabel(item)}
                                </Typography.Text>
                              </Space>
                            </div>
                          </Col>
                          <Col span={6}>
                            <Typography.Text theme="secondary">上线门禁</Typography.Text>
                            <div>
                              <Tag theme={businessReleaseGateStatusTheme(item.releaseGate?.status)} variant="light" size="small">
                                {item.releaseGate?.label || businessReleaseGateLabel(item.releaseGate?.status)}
                              </Tag>
                            </div>
                          </Col>
                          <Col span={6}>
                            <Typography.Text theme="secondary">验收状态</Typography.Text>
                            <div>
                              <Tag theme={businessAcceptanceStatusTheme(item.latestAcceptance?.status)} variant="light" size="small">
                                {businessAcceptanceStatusLabel(item.latestAcceptance?.status)}
                              </Tag>
                            </div>
                          </Col>
                        </Row>
                        <Typography.Text theme={Number(item.runMetrics?.failed || 0) > 0 ? 'warning' : 'secondary'}>
                          {businessCapabilityRunMetricsLabel(item)}
                        </Typography.Text>
                        <BusinessCapabilityReleaseEvidence item={item} formatDateTime={formatDateTime} />
                        {rollout.enabled || rollout.percent > 0 || rollout.allowlistText ? (
                          <Typography.Text theme="secondary">
                            灰度：{rollout.enabled ? `${rollout.percent}%` : '未启用'}
                            {rollout.allowlistText ? ' · 含白名单' : ''}
                          </Typography.Text>
                        ) : null}
                        <BusinessCapabilityTechnicalDetails item={item} />
                        {isReadOnly ? (
                          <Tag theme="default" variant="light">
                            只读查看
                          </Tag>
                        ) : (
                          <Space breakLine size={6}>
                            <Button size="small" variant="outline" onClick={() => onEdit(item)}>
                              编辑
                            </Button>
                            <Button
                              size="small"
                              theme="success"
                              variant="outline"
                              loading={actionLoadingId === acceptanceActionId}
                              disabled={actionBusy && actionLoadingId !== acceptanceActionId}
                              onClick={() => onRecordAcceptance(item)}
                            >
                              记录验收通过
                            </Button>
                            {!item.isDefault ? (
                              <Button
                                size="small"
                                theme="primary"
                                variant="outline"
                                loading={actionLoadingId === defaultActionId}
                                disabled={
                                  defaultSwitchBlocked ||
                                  Boolean(pendingApproval) ||
                                  (actionBusy && actionLoadingId !== defaultActionId)
                                }
                                onClick={() => onSetDefault(item)}
                              >
                                {defaultSwitchBlocked ? '先验收' : pendingApproval ? '默认审批中' : '申请设为默认'}
                              </Button>
                            ) : null}
                            <Button
                              size="small"
                              theme={isActive ? 'warning' : 'primary'}
                              variant="outline"
                              loading={actionLoadingId === statusActionId}
                              disabled={lockDefaultStop || (actionBusy && actionLoadingId !== statusActionId)}
                              onClick={() => onToggleActive(item)}
                            >
                              {lockDefaultStop ? '默认版不能停用' : isActive ? '停用' : '启用'}
                            </Button>
                          </Space>
                        )}
                      </Space>
                    </Card>
                  </Col>
                );
              })}
            </Row>
          </Card>
        );
      })}
    </Space>
  );
};
