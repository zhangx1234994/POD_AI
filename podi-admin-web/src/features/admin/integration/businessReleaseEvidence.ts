import type {
  BusinessCapability,
  BusinessDefaultApproval,
  BusinessUsageBucket,
  BusinessUsageSummaryResponse,
} from '../../../types/admin';
import { businessKeyLabel, coreBusinessKeys } from './businessLabels';

export type BusinessEvidenceTheme = 'success' | 'warning' | 'danger' | 'default';

export type BusinessReleaseEvidenceCheck = {
  key: string;
  label: string;
  theme: BusinessEvidenceTheme;
};

export type CoreBusinessReleaseEvidenceRow = {
  businessKey: string;
  defaultItem?: BusinessCapability;
  activeCount: number;
  totalVersions: number;
  bucket?: BusinessUsageBucket;
  hasPendingApproval: boolean;
  activeAlternatives: BusinessCapability[];
  rollbackReadyAlternatives: BusinessCapability[];
  theme: BusinessEvidenceTheme;
  status: string;
  reason: string;
  outputCount: number;
  callbackRisk: number;
  billingRisk: number;
  acceptancePassed: boolean;
  checks: BusinessReleaseEvidenceCheck[];
  suggestion: string;
};

export const businessReleaseIssueLabel = (value?: string | null) => {
  const labels: Record<string, string> = {
    BUSINESS_RELEASE_VERSION_INACTIVE: '版本未启用',
    BUSINESS_RELEASE_PRIMARY_ABILITY_REQUIRED: '未绑定主能力',
    BUSINESS_RELEASE_GOVERNANCE_BLOCKED: '底层治理未通过',
    BUSINESS_RELEASE_GOVERNANCE_WARNING: '底层治理需补齐',
    BUSINESS_RELEASE_ACCEPTANCE_REQUIRED: '缺少真实链路验收',
    BUSINESS_RELEASE_LATEST_RUN_FAILED: '最近一次运行失败',
    BUSINESS_RELEASE_RECENT_FAILURES: '近期存在失败样本',
  };
  return labels[value || ''] || value || '';
};

export const getBusinessRunOutputCount = (item?: BusinessCapability) => {
  const latestRun = item?.latestRun;
  return (
    Number(latestRun?.imageCount ?? latestRun?.image_count ?? 0) +
    Number(latestRun?.videoCount ?? latestRun?.video_count ?? 0)
  );
};

export const businessCapabilityHasRollbackEvidence = (item?: BusinessCapability) => {
  if (!item || item.status !== 'active' || item.isDefault) return false;
  const latestRunStatus = String(item.latestRun?.status || '').toLowerCase();
  return Boolean(
    item.latestAcceptance?.status === 'passed' &&
    latestRunStatus === 'succeeded' &&
    getBusinessRunOutputCount(item) > 0 &&
    !item.latestRun?.error &&
    item.governanceStatus !== 'blocker' &&
    item.releaseGate?.status !== 'blocked',
  );
};

export const businessCapabilityRollbackEvidenceLabel = (item: BusinessCapability) => {
  const acceptance = item.latestAcceptance?.status === 'passed' ? '验收通过' : '未验收';
  const outputCount = getBusinessRunOutputCount(item);
  const latestRunStatus = String(item.latestRun?.status || '').toLowerCase();
  const latestRun = !item.latestRun
    ? '无真实样本'
    : latestRunStatus === 'succeeded' && outputCount > 0 && !item.latestRun.error
      ? `最近成功 · ${outputCount} 个输出`
      : item.latestRun.error
        ? '最近失败'
        : '样本未通过';
  const gate = item.releaseGate?.status === 'blocked' || item.governanceStatus === 'blocker' ? '门禁阻塞' : '门禁可用';
  return `${item.version}：${acceptance} · ${latestRun} · ${gate}`;
};

const firstBusinessReleaseReason = ({
  defaultItem,
  hasPendingApproval,
  activeAlternatives,
  rollbackReadyAlternatives,
  outputCount,
  callbackRisk,
  billingRisk,
  acceptancePassed,
  runFailed,
}: {
  defaultItem?: BusinessCapability;
  hasPendingApproval: boolean;
  activeAlternatives: BusinessCapability[];
  rollbackReadyAlternatives: BusinessCapability[];
  outputCount: number;
  callbackRisk: number;
  billingRisk: number;
  acceptancePassed: boolean;
  runFailed: boolean;
}) => {
  if (!defaultItem) return '缺少默认版本';
  if (defaultItem.status !== 'active') return '默认版本未启用';
  if (!defaultItem.primaryAbilityId && !defaultItem.primaryAbilityName) return '默认版本未绑定主能力';
  if (defaultItem.governanceStatus === 'blocker') return defaultItem.governanceSuggestions?.[0] || '底层能力或模型治理未通过';
  const releaseGate = defaultItem.releaseGate || null;
  const blockers = (releaseGate?.blockers || []).map((item) => businessReleaseIssueLabel(item)).filter(Boolean);
  const warnings = (releaseGate?.warnings || []).map((item) => businessReleaseIssueLabel(item)).filter(Boolean);
  if (blockers[0]) return blockers[0];
  if (!acceptancePassed) return '缺少真实链路验收记录';
  if (runFailed) return '近期存在失败样本';
  if (outputCount <= 0) return '缺少最近真实输出样本';
  if (warnings[0]) return warnings[0];
  if (callbackRisk > 0) return `存在 ${callbackRisk} 个回调风险`;
  if (billingRisk > 0) return `存在 ${billingRisk} 个计费风险`;
  if (rollbackReadyAlternatives.length === 0) {
    return activeAlternatives.length > 0 ? '备选版本缺少通过证据' : '缺少可回滚备选版本';
  }
  if (hasPendingApproval) return '存在默认版本切换审批';
  return releaseGate?.suggestions?.[0] || '默认版本具备上线证据';
};

const firstBusinessReleaseSuggestion = ({
  defaultItem,
  activeCount,
  rollbackReadyCount,
  hasPendingApproval,
  reason,
}: {
  defaultItem?: BusinessCapability;
  activeCount: number;
  rollbackReadyCount: number;
  hasPendingApproval: boolean;
  reason: string;
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
  if (rollbackReadyCount < 1) {
    return activeCount >= 2
      ? '已有备选版本，但还缺验收通过和成功输出证据；先补证据再切默认。'
      : '建议保留一个可用备选版本，便于灰度和快速回滚。';
  }
  if (reason !== '默认版本具备上线证据') return reason;
  return '入口稳定，可进入测评端或小流量业务验证。';
};

export const buildCoreBusinessReleaseEvidenceRows = ({
  capabilities,
  pendingApprovals = [],
  summary,
}: {
  capabilities: BusinessCapability[];
  pendingApprovals?: BusinessDefaultApproval[];
  summary?: BusinessUsageSummaryResponse | null;
}): CoreBusinessReleaseEvidenceRow[] =>
  coreBusinessKeys.map((businessKey) => {
    const items = capabilities.filter((item) => item.businessKey === businessKey);
    const defaultItem = items.find((item) => item.isDefault);
    const activeAlternatives = items.filter((item) => item.status === 'active' && !item.isDefault);
    const rollbackReadyAlternatives = activeAlternatives.filter(businessCapabilityHasRollbackEvidence);
    const activeCount = items.filter((item) => item.status === 'active').length;
    const bucket = summary?.byBusiness?.find((item) => item.key === businessKey);
    const hasPendingApproval = pendingApprovals.some((item) => item.businessKey === businessKey && item.status === 'pending');
    const outputCount = getBusinessRunOutputCount(defaultItem);
    const hasDefault = Boolean(defaultItem);
    const acceptancePassed = Boolean(defaultItem?.releaseGate?.acceptancePassed === true || defaultItem?.latestAcceptance?.status === 'passed');
    const gateBlocked = defaultItem?.releaseGate?.status === 'blocked' || defaultItem?.governanceStatus === 'blocker';
    const runFailed = Boolean(defaultItem?.latestRun?.error) || Number(bucket?.failed || defaultItem?.runMetrics?.failed || 0) > 0;
    const callbackRisk = Number(bucket?.callbackFailed || 0) + Number(bucket?.callbackMissing || 0);
    const billingRisk = Number(bucket?.unpriced || 0) + Number(bucket?.billingPending || 0);
    const missingRollback = hasDefault && rollbackReadyAlternatives.length === 0;
    const theme: BusinessEvidenceTheme = !hasDefault || gateBlocked || runFailed
      ? 'danger'
      : !acceptancePassed || outputCount === 0 || callbackRisk > 0 || billingRisk > 0 || missingRollback || hasPendingApproval
        ? 'warning'
        : 'success';
    const status = !hasDefault
      ? '缺默认'
      : gateBlocked
        ? '阻塞'
        : runFailed
          ? '有失败'
          : !acceptancePassed
            ? '待验收'
            : outputCount === 0
              ? '待样本'
              : callbackRisk > 0 || billingRisk > 0
                ? '需复核'
                : '闭环正常';
    const reason = firstBusinessReleaseReason({
      defaultItem,
      hasPendingApproval,
      activeAlternatives,
      rollbackReadyAlternatives,
      outputCount,
      callbackRisk,
      billingRisk,
      acceptancePassed,
      runFailed,
    });
    const checks = [
      {
        key: 'default',
        label: hasDefault ? `默认 ${defaultItem?.version || '—'}` : '缺默认版本',
        theme: hasDefault && defaultItem?.status === 'active' ? 'success' : 'danger',
      },
      {
        key: 'acceptance',
        label: acceptancePassed ? '验收通过' : '未验收',
        theme: acceptancePassed ? 'success' : 'warning',
      },
      {
        key: 'sample',
        label: outputCount > 0 ? `样本 ${outputCount} 个输出` : '缺真实样本',
        theme: outputCount > 0 ? 'success' : 'warning',
      },
      {
        key: 'callback',
        label: callbackRisk > 0 ? `回调风险 ${callbackRisk}` : '回调正常',
        theme: callbackRisk > 0 ? 'warning' : 'success',
      },
      {
        key: 'billing',
        label: billingRisk > 0 ? `计费风险 ${billingRisk}` : '计费正常',
        theme: billingRisk > 0 ? 'warning' : 'success',
      },
      {
        key: 'rollback',
        label: rollbackReadyAlternatives.length > 0
          ? `可回滚 ${rollbackReadyAlternatives.length}`
          : activeAlternatives.length > 0
            ? `备选待验收 ${activeAlternatives.length}`
            : '缺回滚备选',
        theme: rollbackReadyAlternatives.length > 0 ? 'success' : 'warning',
      },
    ] as BusinessReleaseEvidenceCheck[];
    return {
      businessKey,
      defaultItem,
      activeCount,
      totalVersions: items.length,
      bucket,
      hasPendingApproval,
      activeAlternatives,
      rollbackReadyAlternatives,
      theme,
      status,
      reason: reason === '缺少默认版本' ? `${businessKeyLabel(businessKey)}缺少默认版本` : reason,
      outputCount,
      callbackRisk,
      billingRisk,
      acceptancePassed,
      checks,
      suggestion: firstBusinessReleaseSuggestion({
        defaultItem,
        activeCount,
        rollbackReadyCount: rollbackReadyAlternatives.length,
        hasPendingApproval,
        reason,
      }),
    };
  });
