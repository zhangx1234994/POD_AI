import type {
  BusinessCapability,
  BusinessDefaultApproval,
  BusinessUsageBucket,
  BusinessUsageSummaryResponse,
} from '../../../types/admin';
import { businessKeyLabel, canonicalBusinessKey, coreBusinessKeys } from './businessLabels';

export type BusinessEvidenceTheme = 'success' | 'warning' | 'danger' | 'default';

export type BusinessLifecycleBadge = {
  label: string;
  theme: BusinessEvidenceTheme;
  detail: string;
};

export type BusinessLifecycleStatus = {
  online: BusinessLifecycleBadge;
  recommendation: BusinessLifecycleBadge;
};

const releaseEvidenceOnlyBlockers = new Set([
  'BUSINESS_RELEASE_ACCEPTANCE_REQUIRED',
  'BUSINESS_RELEASE_QUALITY_REVIEW_REQUIRED',
  'BUSINESS_RELEASE_QUALITY_REVIEW_POSITIVE_REQUIRED',
  'BUSINESS_RELEASE_QUALITY_REVIEW_RISKY',
]);

const businessReleaseGateBlockerCodes = (item?: BusinessCapability) =>
  (item?.releaseGate?.blockers || []).map((code) => String(code || '')).filter(Boolean);

const businessReleaseGateHasHardBlocker = (item?: BusinessCapability) => {
  if (item?.releaseGate?.status !== 'blocked') return false;
  const blockers = businessReleaseGateBlockerCodes(item);
  if (blockers.length === 0) return true;
  return blockers.some((code) => !releaseEvidenceOnlyBlockers.has(code));
};

const businessReleaseGateHasEvidenceBlocker = (item?: BusinessCapability) => {
  if (item?.releaseGate?.status !== 'blocked') return false;
  const blockers = businessReleaseGateBlockerCodes(item);
  return blockers.length > 0 && blockers.every((code) => releaseEvidenceOnlyBlockers.has(code));
};

type BusinessLifecycleEvidence = {
  outputCount?: number;
  acceptancePassed?: boolean;
  releaseGateBlocked?: boolean;
  governanceBlocked?: boolean;
  runFailed?: boolean;
  hasPendingApproval?: boolean;
  callbackRisk?: number;
  billingRisk?: number;
  rollbackReadyCount?: number;
  activeAlternativeCount?: number;
};

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
  onlineStatus: BusinessLifecycleBadge;
  recommendationStatus: BusinessLifecycleBadge;
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
    BUSINESS_RELEASE_QUALITY_REVIEW_REQUIRED: '缺少出图质量标注',
    BUSINESS_RELEASE_QUALITY_REVIEW_POSITIVE_REQUIRED: '缺少可用质量标注',
    BUSINESS_RELEASE_QUALITY_REVIEW_RISKY: '质量样本存在风险',
    BUSINESS_RELEASE_LATEST_RUN_FAILED: '最近一次运行失败',
    BUSINESS_RELEASE_RECENT_FAILURES: '近期存在失败样本',
  };
  return labels[value || ''] || value || '';
};

export const getBusinessRunOutputCount = (item?: BusinessCapability) => {
  const latestRun = item?.latestRun;
  return (
    Number(latestRun?.imageCount ?? latestRun?.image_count ?? 0) +
    Number(latestRun?.videoCount ?? latestRun?.video_count ?? 0) +
    Number(latestRun?.textCount ?? latestRun?.text_count ?? 0)
  );
};

const businessLatestRunSucceeded = (item?: BusinessCapability) =>
  ['succeeded', 'success', 'completed'].includes(String(item?.latestRun?.status || '').toLowerCase()) && !item?.latestRun?.error;

export const businessCapabilityLifecycleStatus = (
  item?: BusinessCapability,
  evidence: BusinessLifecycleEvidence = {},
): BusinessLifecycleStatus => {
  const outputCount = evidence.outputCount ?? getBusinessRunOutputCount(item);
  const acceptancePassed = Boolean(
    evidence.acceptancePassed ?? (item?.releaseGate?.acceptancePassed === true || item?.latestAcceptance?.status === 'passed'),
  );
  const latestRunSucceeded = businessLatestRunSucceeded(item);
  const hasSuccessfulOutput = latestRunSucceeded && outputCount > 0;
  const hasPrimaryAbility = Boolean(item?.primaryAbilityId || item?.primaryAbilityName);
  const rawReleaseGateBlocked = Boolean(evidence.releaseGateBlocked ?? item?.releaseGate?.status === 'blocked');
  const hardReleaseGateBlocked =
    evidence.releaseGateBlocked !== undefined ? rawReleaseGateBlocked && businessReleaseGateHasHardBlocker(item) : businessReleaseGateHasHardBlocker(item);
  const evidenceReleaseGateBlocked =
    evidence.releaseGateBlocked !== undefined ? rawReleaseGateBlocked && !hardReleaseGateBlocked : businessReleaseGateHasEvidenceBlocker(item);
  const governanceBlocked = Boolean(evidence.governanceBlocked ?? item?.governanceStatus === 'blocker');
  const runFailed = Boolean(evidence.runFailed ?? item?.latestRun?.error);
  const callbackRisk = Number(evidence.callbackRisk || 0);
  const billingRisk = Number(evidence.billingRisk || 0);
  const rollbackReadyCount = Number(evidence.rollbackReadyCount || 0);
  const activeAlternativeCount = Number(evidence.activeAlternativeCount || 0);
  const hasPendingApproval = Boolean(evidence.hasPendingApproval);
  const status = String(item?.status || '').toLowerCase();
  const isInactive = ['inactive', 'disabled', 'deprecated', 'archived'].includes(status);
  const isDraft = status === 'draft';
  const hasRisk = rawReleaseGateBlocked || governanceBlocked || runFailed || callbackRisk > 0 || billingRisk > 0;

  let online: BusinessLifecycleBadge;
  if (!item) {
    online = { label: '缺入口', theme: 'danger', detail: '没有默认版本，业务方没有稳定可调入口。' };
  } else if (isInactive) {
    online = { label: '已下线', theme: 'default', detail: '该版本不再承接线上业务，只保留追溯或回滚记录。' };
  } else if (isDraft) {
    online = { label: '候选验证', theme: 'default', detail: '草稿或候选版本只能试运行，不能作为线上默认入口。' };
  } else if (!hasPrimaryAbility) {
    online = { label: '配置缺失', theme: 'danger', detail: '缺少主执行能力，不能稳定调用。' };
  } else if ((hardReleaseGateBlocked || governanceBlocked) && !hasSuccessfulOutput) {
    online = { label: '不可用', theme: 'danger', detail: '存在阻塞项且没有可用成功样本。' };
  } else if (hasRisk && hasSuccessfulOutput) {
    online = { label: '受限可用', theme: 'warning', detail: '已有成功输出，但仍有验收、治理、回填、计费或失败风险需要复核。' };
  } else if (hasSuccessfulOutput) {
    online = { label: '线上可用', theme: 'success', detail: '启用版本已有真实成功输出，可作为当前可用入口。' };
  } else if (item.isDefault) {
    online = { label: '线上待验证', theme: 'warning', detail: '默认版本已启用，但还缺最近成功输出证据。' };
  } else {
    online = { label: '候选验证', theme: 'default', detail: '非默认版本还需要试运行和验收后再切入线上。' };
  }

  let recommendation: BusinessLifecycleBadge;
  if (!item) {
    recommendation = { label: '缺默认', theme: 'danger', detail: '先补默认版本。' };
  } else if (isInactive) {
    recommendation = { label: '历史版本', theme: 'default', detail: '仅用于追溯、对照或回滚说明。' };
  } else if (isDraft) {
    recommendation = { label: '候选验证', theme: 'default', detail: '先完成真实链路试运行和验收。' };
  } else if (!hasPrimaryAbility || hardReleaseGateBlocked || governanceBlocked || runFailed) {
    recommendation = { label: '需复核', theme: hardReleaseGateBlocked || governanceBlocked || !hasPrimaryAbility ? 'danger' : 'warning', detail: '存在影响推荐默认入口的风险。' };
  } else if (hasPendingApproval) {
    recommendation = { label: '切换中', theme: 'warning', detail: '默认版本切换仍在审批，不能按新默认版本对外说明。' };
  } else if (hasSuccessfulOutput && acceptancePassed && callbackRisk === 0 && billingRisk === 0 && item.isDefault && rollbackReadyCount > 0) {
    recommendation = { label: '生产推荐', theme: 'success', detail: '默认入口、验收、真实输出、回填计费和回滚证据齐全。' };
  } else if (hasSuccessfulOutput && evidenceReleaseGateBlocked) {
    recommendation = { label: acceptancePassed ? '待补质量' : '待补验收', theme: 'warning', detail: '真实链路已跑通，但缺少验收或质量证据，不能作为生产推荐。' };
  } else if (hasSuccessfulOutput && acceptancePassed) {
    recommendation = {
      label: item.isDefault ? '灰度可用' : '备选可用',
      theme: 'warning',
      detail: activeAlternativeCount > 0 || rollbackReadyCount > 0 ? '已有验收和成功样本，可小流量使用或作为备选。' : '已有验收和成功样本，但生产推荐前还要补回滚或风险证据。',
    };
  } else if (hasSuccessfulOutput) {
    recommendation = { label: '待补验收', theme: 'warning', detail: '已有真实成功样本，但还缺验收通过记录。' };
  } else {
    recommendation = { label: '候选验证', theme: 'default', detail: '还缺真实成功输出，先跑固定样例。' };
  }

  return { online, recommendation };
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
  const acceptance = item.latestAcceptance?.status === 'passed' ? '验收通过' : '待补验收';
  const outputCount = getBusinessRunOutputCount(item);
  const latestRunStatus = String(item.latestRun?.status || '').toLowerCase();
  const latestRun = !item.latestRun
    ? '无真实样本'
    : latestRunStatus === 'succeeded' && outputCount > 0 && !item.latestRun.error
      ? `最近成功 · ${outputCount} 个输出`
      : item.latestRun.error
        ? '最近失败'
        : '样本未通过';
  const gate =
    item.governanceStatus === 'blocker' || businessReleaseGateHasHardBlocker(item)
      ? '门禁阻塞'
      : businessReleaseGateHasEvidenceBlocker(item)
        ? '待补发布证据'
        : '门禁可用';
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
  unresolvedCount,
}: {
  defaultItem?: BusinessCapability;
  activeCount: number;
  rollbackReadyCount: number;
  hasPendingApproval: boolean;
  reason: string;
  unresolvedCount: number;
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
  if (defaultItem.latestRun?.error || unresolvedCount > 0) return '最近有失败样本，先打开运行记录确认卡点。';
  if (Number(defaultItem.runMetrics?.failed || 0) > 0) return '历史失败已被后续成功样本覆盖，保留追溯即可。';
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
    const items = capabilities.filter((item) => canonicalBusinessKey(item.businessKey) === businessKey);
    const defaultItem = items.find((item) => item.isDefault);
    const activeAlternatives = items.filter((item) => item.status === 'active' && !item.isDefault);
    const rollbackReadyAlternatives = activeAlternatives.filter(businessCapabilityHasRollbackEvidence);
    const activeCount = items.filter((item) => item.status === 'active').length;
    const bucket = summary?.byBusiness?.find((item) => canonicalBusinessKey(item.key) === businessKey);
    const unresolvedBucket = summary?.unresolvedByBusiness?.find((item) => canonicalBusinessKey(item.key) === businessKey);
    const unresolvedCount = Number(unresolvedBucket?.total || 0);
    const hasPendingApproval = pendingApprovals.some(
      (item) => canonicalBusinessKey(item.businessKey) === businessKey && item.status === 'pending',
    );
    const outputCount = getBusinessRunOutputCount(defaultItem);
    const hasDefault = Boolean(defaultItem);
    const acceptancePassed = Boolean(defaultItem?.releaseGate?.acceptancePassed === true || defaultItem?.latestAcceptance?.status === 'passed');
    const releaseGateBlockers = businessReleaseGateBlockerCodes(defaultItem);
    const latestRunSucceeded = String(defaultItem?.latestRun?.status || '').toLowerCase() === 'succeeded' && !defaultItem?.latestRun?.error;
    const acceptanceOnlyBlocked = Boolean(
      defaultItem?.releaseGate?.status === 'blocked' &&
      latestRunSucceeded &&
      releaseGateBlockers.length > 0 &&
      releaseGateBlockers.every((item) => releaseEvidenceOnlyBlockers.has(item)),
    );
    const gateBlocked =
      defaultItem?.governanceStatus === 'blocker' ||
      (defaultItem?.releaseGate?.status === 'blocked' && !acceptanceOnlyBlocked);
    const runFailed = Boolean(defaultItem?.latestRun?.error) || unresolvedCount > 0;
    const callbackRisk = Number(bucket?.callbackFailed || 0) + Number(bucket?.callbackMissing || 0);
    const billingRisk = Number(bucket?.unpriced || 0) + Number(bucket?.billingPending || 0);
    const missingRollback = hasDefault && rollbackReadyAlternatives.length === 0;
    const lifecycle = businessCapabilityLifecycleStatus(defaultItem, {
      outputCount,
      acceptancePassed,
      releaseGateBlocked: gateBlocked,
      governanceBlocked: defaultItem?.governanceStatus === 'blocker',
      runFailed,
      hasPendingApproval,
      callbackRisk,
      billingRisk,
      rollbackReadyCount: rollbackReadyAlternatives.length,
      activeAlternativeCount: activeAlternatives.length,
    });
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
            ? outputCount > 0 ? '待补验收' : '候选验证'
            : outputCount === 0
              ? '待样本'
              : callbackRisk > 0 || billingRisk > 0
                ? '需复核'
                : missingRollback
                  ? activeAlternatives.length > 0 ? '备选待补证据' : '安全垫不足'
                : '生产推荐';
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
        label: acceptancePassed ? '验收通过' : '待补验收',
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
            ? `备选待补证据 ${activeAlternatives.length}`
            : '缺回滚安全垫',
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
      onlineStatus: lifecycle.online,
      recommendationStatus: lifecycle.recommendation,
      checks,
      suggestion: firstBusinessReleaseSuggestion({
        defaultItem,
        activeCount,
        rollbackReadyCount: rollbackReadyAlternatives.length,
        hasPendingApproval,
        reason,
        unresolvedCount,
      }),
    };
  });
