import { useEffect, useMemo, useState } from 'react';
import { Alert, Button, Card, Col, Dialog, Input, InputNumber, Row, Select, Space, Switch, Table, Tag, Textarea, Typography } from 'tdesign-react';
import {
  Background,
  Controls,
  Handle,
  MarkerType,
  Position,
  ReactFlow,
  type Edge,
  type Node,
  type NodeProps,
  type NodeTypes,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import type {
  BusinessCapability,
  BusinessCapabilityCompareResponse,
  BusinessCapabilityFormState,
  BusinessDefaultApproval,
  BusinessFlowEvidenceBucket,
  BusinessOperationLog,
  BusinessOutputReview,
  BusinessOutputReviewBatchSummary,
  BusinessOutputReviewBucket,
  BusinessOutputReviewSummaryResponse,
  BusinessOutputReviewVersionSummary,
  BusinessQualityActionRule,
  BusinessQualitySample,
  BusinessQualitySampleImportItem,
  BusinessQualitySampleImportResponse,
  BusinessQualitySampleVersion,
  BusinessReleaseGate,
  BusinessOrchestrationEdge,
  BusinessOrchestrationGraph,
  BusinessOrchestrationNode,
  BusinessOrchestrationNodeRunSample,
  BusinessRecipeStep,
  BusinessRun,
  BusinessRunStep,
  BusinessUsageSummaryResponse,
  JsonRecord,
} from '../../../types/admin';
import { adminApi } from '../../../services/adminApi';
import { GuidanceQueueCard, OperationFlowCard, StatusBadge, type GuidanceQueueItem } from '../shared/ui';
import {
  businessRunBillingStatusOptions,
  businessRunCallbackStatusOptions,
  businessRunIssueCategoryOptions,
  businessRunStatusOptions,
  businessUsageWindowOptions,
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
  canonicalBusinessKey,
  coreBusinessKeys,
} from './businessLabels';
import {
  buildCoreBusinessReleaseEvidenceRows,
  businessCapabilityHasRollbackEvidence,
  businessCapabilityLifecycleStatus,
  businessCapabilityRollbackEvidenceLabel,
} from './businessReleaseEvidence';
import { createBusinessCapabilityFormState } from './businessDashboardState';
export {
  businessBillingStatusLabel,
  businessBillingStatusTheme,
  businessCapabilityLatestRunLabel,
  businessCapabilityRunMetricsLabel,
  businessKeyLabel,
  businessRunStepStatusLabel,
  canonicalBusinessKey,
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

const businessRunIsInternalOrEvalSource = (row?: Pick<BusinessRun, 'source' | 'channel' | 'noChargeReason'> | null) => {
  const source = String(row?.source || '').trim().toLowerCase();
  const channel = String(row?.channel || '').trim().toLowerCase();
  const noChargeReason = String(row?.noChargeReason || '').trim().toLowerCase();
  return (
    source === 'eval' ||
    source === 'eval-web' ||
    source === 'admin' ||
    source === 'admin-test' ||
    channel.includes('patrol') ||
    channel.includes('smoke') ||
    channel.includes('internal') ||
    noChargeReason.includes('internal') ||
    noChargeReason.includes('patrol')
  );
};

const businessRunUsesVendorModelChannel = (
  row?: Pick<BusinessRun, 'abilityProvider' | 'vendorModelProvider' | 'vendorModelName'> | null,
) => {
  const provider = String(row?.vendorModelProvider || row?.abilityProvider || '').trim().toLowerCase();
  return Boolean(row?.vendorModelName || ['openai', 'openai_compatible', 'kie', 'volcengine', 'baidu'].includes(provider));
};

const businessGovernanceIssueLabel = (value?: string | null) => {
  const labels: Record<string, string> = {
    BUSINESS_GOVERNANCE_PRIMARY_ABILITY_MISSING: '未绑定主能力',
    BUSINESS_GOVERNANCE_PRIMARY_ABILITY_NOT_FOUND: '主能力不存在',
    BUSINESS_GOVERNANCE_PRIMARY_ABILITY_INACTIVE: '主能力未启用',
    BUSINESS_GOVERNANCE_EXECUTABLE_STEP_MISSING: '配方没有可执行步骤',
    BUSINESS_GOVERNANCE_STEP_ABILITY_MISSING: '步骤缺少能力',
    BUSINESS_GOVERNANCE_STEP_ABILITY_NOT_FOUND: '步骤能力不存在',
    BUSINESS_GOVERNANCE_STEP_ABILITY_INACTIVE: '步骤能力未启用',
    BUSINESS_GOVERNANCE_RECIPE_STEP_ID_DUPLICATED: '步骤编号重复',
    BUSINESS_GOVERNANCE_RECIPE_PRIMARY_STEP_MISMATCH: '主步骤不一致',
    BUSINESS_GOVERNANCE_VENDOR_MODEL_NOT_FOUND: '模型目录不存在',
    BUSINESS_GOVERNANCE_VENDOR_MODEL_INACTIVE: '模型未启用',
    BUSINESS_GOVERNANCE_VENDOR_MODEL_ACCEPTANCE_REQUIRED: '模型待补验收证据',
    BUSINESS_GOVERNANCE_VENDOR_MODEL_COST_MISSING: '模型成本未配置',
    BUSINESS_GOVERNANCE_VENDOR_KEY_MISSING: '第三方密钥不可用',
    BUSINESS_GOVERNANCE_VENDOR_EGRESS_NOT_VERIFIED: '出网未验证',
  };
  return labels[value || ''] || value || '暂无风险';
};

const businessCapabilityStatusOptions = [
  { value: 'draft', label: '草稿' },
  { value: 'inactive', label: '未启用' },
  { value: 'active', label: '启用' },
  { value: 'deprecated', label: '下线' },
];

const businessVersionDecisionOptions = [
  { value: 'version_upgrade', label: '同一业务版本升级' },
  { value: 'new_feature', label: '新的业务功能' },
  { value: 'rollback', label: '回滚保底版本' },
  { value: 'unknown', label: '归属待补' },
];

const buildBusinessDraftRecipeText = (form: BusinessCapabilityFormState) => {
  const steps: JsonRecord[] = [];
  if (form.vlAssistEnabled) {
    steps.push({
      id: 'vl_analyze',
      type: 'vl_analyze',
      role: 'preprocess',
      displayName: 'VL 图像理解',
      abilityId: form.vlAssistAbilityId || 'vl_analyze_image',
      enabled: true,
    });
  }
  if (form.primaryAbilityId) {
    steps.push({
      id: 'primary',
      type: 'ability_task',
      role: 'primary',
      displayName: '主执行能力',
      abilityId: form.primaryAbilityId,
      enabled: true,
    });
  }
  return JSON.stringify(
    {
      mode: form.vlAssistEnabled ? 'vl_then_primary' : 'single_ability_task',
      primaryAbilityId: form.primaryAbilityId || '',
      visualDraft: {
        version: 1,
        source: 'admin_business_orchestration_canvas',
        note: '草稿编排只保存到业务版本，不直接影响线上默认版本。',
      },
      steps,
      vlAssist: form.vlAssistEnabled
        ? {
            enabled: true,
            abilityId: form.vlAssistAbilityId || 'vl_analyze_image',
          }
        : undefined,
    },
    null,
    2,
  );
};

interface BusinessRecipeDraftStep {
  id: string;
  type: string;
  role: string;
  displayName: string;
  abilityId: string;
  enabled: boolean;
  config?: JsonRecord;
}

const parseBusinessDraftRecipe = (value?: string): { ok: true; recipe: JsonRecord } | { ok: false; recipe: JsonRecord; error: string } => {
  if (!value || !value.trim()) return { ok: true, recipe: {} };
  try {
    const parsed = JSON.parse(value);
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      return { ok: false, recipe: {}, error: '业务配方必须是 JSON 对象。' };
    }
    return { ok: true, recipe: parsed as JsonRecord };
  } catch {
    return { ok: false, recipe: {}, error: '业务配方 JSON 格式不正确，先修正后再用可视化编辑。' };
  }
};

const readBusinessDraftSteps = (form: BusinessCapabilityFormState): {
  recipe: JsonRecord;
  steps: BusinessRecipeDraftStep[];
  error?: string;
} => {
  const parsed = parseBusinessDraftRecipe(form.recipeText);
  const recipe = parsed.recipe;
  const rawSteps = Array.isArray(recipe.steps) ? recipe.steps : [];
  const steps = rawSteps
    .map((rawStep, index): BusinessRecipeDraftStep | null => {
      if (!rawStep || typeof rawStep !== 'object' || Array.isArray(rawStep)) return null;
      const step = rawStep as JsonRecord;
      const stepType = String(step.type || 'ability_task');
      const role = String(step.role || (stepType === 'vl_analyze' ? 'preprocess' : 'primary'));
      const abilityId = String(step.abilityId || step.ability_id || '');
      return {
        id: String(step.id || `step_${index + 1}`),
        type: stepType,
        role,
        displayName: String(step.displayName || step.name || step.title || (stepType === 'vl_analyze' ? 'VL 图像理解' : '主执行能力')),
        abilityId,
        enabled: step.enabled !== false,
        config: step.config && typeof step.config === 'object' && !Array.isArray(step.config) ? (step.config as JsonRecord) : undefined,
      };
    })
    .filter(Boolean) as BusinessRecipeDraftStep[];

  if (steps.length === 0) {
    if (form.vlAssistEnabled) {
      steps.push({
        id: 'vl_analyze',
        type: 'vl_analyze',
        role: 'preprocess',
        displayName: 'VL 图像理解',
        abilityId: form.vlAssistAbilityId || 'vl_analyze_image',
        enabled: true,
      });
    }
    if (form.primaryAbilityId) {
      steps.push({
        id: 'primary',
        type: 'ability_task',
        role: 'primary',
        displayName: '主执行能力',
        abilityId: form.primaryAbilityId,
        enabled: true,
      });
    }
  }

  return {
    recipe,
    steps,
    error: parsed.ok ? undefined : parsed.error,
  };
};

const normalizeBusinessDraftStepForRecipe = (step: BusinessRecipeDraftStep, index: number): JsonRecord => {
  const next: JsonRecord = {
    id: step.id || `step_${index + 1}`,
    type: step.type || 'ability_task',
    role: step.role || (step.type === 'vl_analyze' ? 'preprocess' : 'primary'),
    displayName: step.displayName || (step.type === 'vl_analyze' ? 'VL 图像理解' : '业务处理步骤'),
    enabled: step.enabled,
  };
  if (step.abilityId) next.abilityId = step.abilityId;
  if (step.config && Object.keys(step.config).length > 0) next.config = step.config;
  return next;
};

const writeBusinessDraftStepsToForm = (
  form: BusinessCapabilityFormState,
  steps: BusinessRecipeDraftStep[],
): BusinessCapabilityFormState => {
  const parsed = parseBusinessDraftRecipe(form.recipeText);
  const recipe: JsonRecord = parsed.ok ? { ...parsed.recipe } : {};
  const normalizedSteps = steps.map(normalizeBusinessDraftStepForRecipe);
  const primaryStep =
    steps.find((step) => step.enabled && step.role === 'primary' && step.abilityId) ||
    steps.find((step) => step.enabled && step.type !== 'vl_analyze' && step.abilityId);
  const vlStep =
    steps.find((step) => step.enabled && (step.type === 'vl_analyze' || step.role === 'preprocess') && step.abilityId);
  const primaryAbilityId = primaryStep?.abilityId || form.primaryAbilityId;
  recipe.steps = normalizedSteps;
  recipe.primaryAbilityId = primaryAbilityId;
  recipe.mode = vlStep ? 'vl_then_primary' : 'single_ability_task';
  recipe.visualDraft = {
    ...((recipe.visualDraft && typeof recipe.visualDraft === 'object' && !Array.isArray(recipe.visualDraft)
      ? recipe.visualDraft
      : {}) as JsonRecord),
    version: 1,
    source: 'admin_business_orchestration_canvas',
  };
  if (vlStep) {
    const existingVlAssist =
      recipe.vlAssist && typeof recipe.vlAssist === 'object' && !Array.isArray(recipe.vlAssist)
        ? (recipe.vlAssist as JsonRecord)
        : {};
    recipe.vlAssist = {
      ...existingVlAssist,
      enabled: true,
      abilityId: vlStep.abilityId,
    };
  } else {
    delete recipe.vlAssist;
  }

  return {
    ...form,
    primaryAbilityId,
    vlAssistEnabled: Boolean(vlStep),
    vlAssistAbilityId: vlStep?.abilityId || form.vlAssistAbilityId,
    recipeText: JSON.stringify(recipe, null, 2),
  };
};

const createBusinessDraftStep = (type: 'vl_analyze' | 'ability_task', index: number): BusinessRecipeDraftStep => ({
  id: type === 'vl_analyze' ? `vl_${index + 1}` : `ability_${index + 1}`,
  type,
  role: type === 'vl_analyze' ? 'preprocess' : 'primary',
  displayName: type === 'vl_analyze' ? 'VL 图像理解' : '业务处理步骤',
  abilityId: type === 'vl_analyze' ? 'vl_analyze_image' : '',
  enabled: true,
});

const businessDraftStepTypeOptions = [
  { label: 'VL 图像理解', value: 'vl_analyze' },
  { label: '能力执行', value: 'ability_task' },
];

const businessDraftStepRoleOptions = [
  { label: '前置分析', value: 'preprocess' },
  { label: '主执行', value: 'primary' },
  { label: '质检评分', value: 'evaluate' },
  { label: '后处理', value: 'postprocess' },
];

const BusinessRecipeDraftEditor = ({
  form,
  abilityOptions,
  vlAbilityOptions,
  disabled,
  onChange,
}: {
  form: BusinessCapabilityFormState;
  abilityOptions: BusinessSelectOption[];
  vlAbilityOptions: BusinessSelectOption[];
  disabled?: boolean;
  onChange: (next: BusinessCapabilityFormState) => void;
}) => {
  const { steps, error } = readBusinessDraftSteps(form);
  const setSteps = (nextSteps: BusinessRecipeDraftStep[]) => onChange(writeBusinessDraftStepsToForm(form, nextSteps));
  const updateStep = (index: number, patch: Partial<BusinessRecipeDraftStep>) => {
    const nextSteps = steps.map((step, stepIndex) => (stepIndex === index ? { ...step, ...patch } : step));
    setSteps(nextSteps);
  };
  const moveStep = (index: number, direction: -1 | 1) => {
    const nextIndex = index + direction;
    if (nextIndex < 0 || nextIndex >= steps.length) return;
    const nextSteps = [...steps];
    const [current] = nextSteps.splice(index, 1);
    nextSteps.splice(nextIndex, 0, current);
    setSteps(nextSteps);
  };
  const removeStep = (index: number) => setSteps(steps.filter((_, stepIndex) => stepIndex !== index));
  const flowSteps: BusinessRecipeFlowStep[] = steps.map((step, index) => ({
    id: step.id,
    type: step.type,
    role: step.role,
    displayName: step.displayName,
    abilityId: step.abilityId,
    enabled: step.enabled,
    order: index + 1,
    params: step.config,
  }));

  return (
    <Card bordered title="草稿编排">
      <Space direction="vertical" size="small" style={{ width: '100%' }}>
        <Alert
          theme="info"
          message="这里编辑的步骤会直接写回业务配方 recipe，不会另存第二套流程。线上默认版本请先复制为草稿再调整。"
        />
        {error ? <Alert theme="warning" message={error} /> : null}
        <div className="podi-business-draft-editor">
          {steps.map((step, index) => {
            const stepAbilityOptions = step.type === 'vl_analyze' && vlAbilityOptions.length > 0 ? vlAbilityOptions : abilityOptions;
            return (
              <section className="podi-business-draft-step" key={`${step.id}-${index}`}>
                <div className="podi-business-draft-step__head">
                  <Tag theme={step.enabled ? 'primary' : 'default'} variant="light">
                    第 {index + 1} 步
                  </Tag>
                  <Space size={4}>
                    <Button size="small" variant="text" disabled={disabled || index === 0} onClick={() => moveStep(index, -1)}>
                      上移
                    </Button>
                    <Button
                      size="small"
                      variant="text"
                      disabled={disabled || index === steps.length - 1}
                      onClick={() => moveStep(index, 1)}
                    >
                      下移
                    </Button>
                    <Button size="small" variant="text" theme="danger" disabled={disabled} onClick={() => removeStep(index)}>
                      删除
                    </Button>
                  </Space>
                </div>
                <Row gutter={[10, 10]}>
                  <Col span={6}>
                    <Typography.Text theme="secondary">步骤类型</Typography.Text>
                    <Select
                      value={step.type}
                      disabled={disabled}
                      options={businessDraftStepTypeOptions}
                      onChange={(value) =>
                        updateStep(index, {
                          type: String(value),
                          role: String(value) === 'vl_analyze' ? 'preprocess' : step.role || 'primary',
                          displayName:
                            step.displayName || (String(value) === 'vl_analyze' ? 'VL 图像理解' : '业务处理步骤'),
                        })
                      }
                    />
                  </Col>
                  <Col span={6}>
                    <Typography.Text theme="secondary">步骤角色</Typography.Text>
                    <Select
                      value={step.role}
                      disabled={disabled}
                      options={businessDraftStepRoleOptions}
                      onChange={(value) => updateStep(index, { role: String(value) })}
                    />
                  </Col>
                  <Col span={12}>
                    <Typography.Text theme="secondary">显示名称</Typography.Text>
                    <Input
                      value={step.displayName}
                      disabled={disabled}
                      onChange={(value) => updateStep(index, { displayName: String(value) })}
                    />
                  </Col>
                  <Col span={18}>
                    <Typography.Text theme="secondary">调用能力</Typography.Text>
                    <Select
                      value={step.abilityId}
                      filterable
                      clearable
                      disabled={disabled}
                      options={stepAbilityOptions}
                      placeholder="选择这个步骤实际调用的能力"
                      onChange={(value) => updateStep(index, { abilityId: String(value || '') })}
                    />
                  </Col>
                  <Col span={6}>
                    <Typography.Text theme="secondary">是否启用</Typography.Text>
                    <div style={{ paddingTop: 8 }}>
                      <Switch
                        value={step.enabled}
                        disabled={disabled}
                        onChange={(value) => updateStep(index, { enabled: Boolean(value) })}
                      />
                    </div>
                  </Col>
                </Row>
              </section>
            );
          })}
        </div>
        <Space breakLine>
          <Button
            variant="outline"
            disabled={disabled}
            onClick={() => setSteps([...steps, createBusinessDraftStep('vl_analyze', steps.length)])}
          >
            添加 VL 步骤
          </Button>
          <Button
            variant="outline"
            disabled={disabled}
            onClick={() => setSteps([...steps, createBusinessDraftStep('ability_task', steps.length)])}
          >
            添加能力步骤
          </Button>
          <Typography.Text theme="secondary">保存业务版本时，这些步骤会随配方一起提交。</Typography.Text>
        </Space>
        <div className="podi-business-draft-preview">
          <Typography.Text strong>流程预览</Typography.Text>
          <BusinessRecipeFlow steps={flowSteps} compact />
        </div>
      </Space>
    </Card>
  );
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
  return '待补验收';
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
  if (value === 'ready') return '门禁通过';
  if (value === 'warning') return '需复核';
  if (value === 'blocked') return '门禁阻塞';
  return '未判断';
};

const normalizeBusinessReleaseGateLabel = (label?: string | null, status?: string | null) => {
  const text = String(label || '').trim();
  if (text === '可上线') return '门禁通过';
  if (text === '暂不能上线') return '门禁阻塞';
  if (text === '待上线') return '待补验收';
  return text || businessReleaseGateLabel(status);
};

const businessReleaseGateDisplay = (releaseGate?: BusinessReleaseGate | null): { label: string; theme: 'success' | 'warning' | 'danger' | 'default' } => {
  if (businessReleaseGateHasOnlyEvidenceBlockers(releaseGate)) {
    return {
      label: businessReleaseGateHasQualityBlocker(releaseGate) ? '待补质量' : '待补验收',
      theme: 'warning',
    };
  }
  return {
    label: normalizeBusinessReleaseGateLabel(releaseGate?.label, releaseGate?.status),
    theme: businessReleaseGateStatusTheme(releaseGate?.status),
  };
};

type BusinessActionTheme = 'success' | 'warning' | 'danger' | 'default';
type BusinessActionPriority = '必须先处理' | '上线前处理' | '建议处理' | '继续观察';

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
  const isCoreCapability = (item: BusinessCapability) =>
    coreBusinessKeys.includes(canonicalBusinessKey(item.businessKey) as (typeof coreBusinessKeys)[number]);
  const coreCapabilities = capabilities.filter(isCoreCapability);
  const windowHours = Number(summary?.windowHours || 24);
  const defaultActiveByKey = new Set(
    coreCapabilities
      .filter((item) => item.isDefault && item.status === 'active')
      .map((item) => canonicalBusinessKey(item.businessKey)),
  );
  const missingDefaults = coreBusinessKeys.filter((key) => !defaultActiveByKey.has(key));
  const inactiveDefaults = coreCapabilities.filter((item) => item.isDefault && item.status !== 'active');
  const failedDefaults = coreCapabilities.filter((item) => item.isDefault && Number(item.runMetrics?.failed || 0) > 0);
  const missingPrimary = coreCapabilities.filter((item) => item.isDefault && !item.primaryAbilityId && !item.primaryAbilityName);
  const governanceBlockedDefaults = coreCapabilities.filter((item) => item.isDefault && item.governanceStatus === 'blocker');
  const governanceWarningDefaults = coreCapabilities.filter((item) => item.isDefault && item.governanceStatus === 'warning');
  const acceptanceMissingDefaults = coreCapabilities.filter(
    (item) => item.isDefault && item.status === 'active' && item.releaseGate?.acceptancePassed === false,
  );
  const rollbackWeakKeys = coreBusinessKeys.filter((businessKey) => {
    const versions = capabilities.filter((item) => canonicalBusinessKey(item.businessKey) === businessKey);
    return versions.some((item) => item.isDefault && item.status === 'active') &&
      versions.filter((item) => item.status === 'active' && !item.isDefault).length === 0;
  });
  const totalRuns = Number(summary?.total || 0);
  const items: BusinessActionItem[] = [];

  if (missingDefaults.length > 0) {
    items.push({
      theme: 'danger',
      priority: '必须先处理',
      title: '核心能力缺默认版本',
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
      title: '默认版本待补验收',
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
  if (items.length === 0 && !summary) {
    items.push({
      theme: 'default',
      priority: '继续观察',
      title: '正在读取业务统计',
      detail: '业务版本和编排信息已显示，近 24 小时调用统计仍在加载；不要把加载中误判为没有调用。',
      action: '统计返回后再判断是否需要跑真实链路巡检。',
    });
  }
  if (items.length === 0 && totalRuns <= 0) {
    items.push({
      theme: 'warning',
      priority: '上线前处理',
      title: '统计窗口内暂无样本',
      detail: `近 ${windowHours} 小时业务统计窗口内暂无调用；如果下方任务清单有历史记录，请继续按 runId 排查历史样本。`,
      action: '需要做上线判断时，先跑一次真实链路巡检。',
    });
  }
  if (items.length === 0) {
    items.push({
      theme: 'success',
      priority: '继续观察',
      title: '当前没有明显阻塞',
      detail: '默认入口、最近失败和回调没有明显阻塞；继续保留真实样本和回滚目标。',
      action: '进入测评端或小流量业务验证，补齐生产推荐证据。',
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

export function BusinessMainlineContractPanel() {
  const steps = [
    {
      key: 'caller',
      title: '先看业务入口',
      done: '入口',
      theme: 'primary' as const,
      detail: '先确认这次调用到底要做什么，是花纹提取、图裂变、扩图还是评分。',
      checks: ['业务类型明确', '业务方优先走业务 API', 'Coze 只是其中一种入口'],
      action: '先确认这是花纹提取、图裂变、扩图还是其他业务。',
    },
    {
      key: 'run',
      title: '保存这次调用的 runId',
      done: '任务编号',
      theme: 'success' as const,
      detail: 'runId 就是这次任务的查询编号。查结果、看错误、找成本，都先用它。',
      checks: ['提交会返回 runId', '查询结果继续用同一个 runId', '多张图建议拆成多次提交'],
      action: '排查业务是否成功时，先找业务调用清单里的 runId。',
    },
    {
      key: 'version',
      title: '确认用的是哪个版本',
      done: '版本',
      theme: 'primary' as const,
      detail: '同一个业务可能有多个版本。这里要看清当前用了哪个版本，能不能回到旧版本。',
      checks: ['默认版本可见', '新旧版本关系可见', '每一步处理过程可查看'],
      action: '在能力版本地图确认版本、灰度、回滚和步骤。',
    },
    {
      key: 'children',
      title: '查看后台处理步骤',
      done: '处理步骤',
      theme: 'warning' as const,
      detail: '图片分析、生图、评分、上传结果、通知业务方，都属于这次 runId 下面的处理步骤。',
      checks: ['步骤有顺序和状态', '失败能定位到具体阶段', '能力调用列表只做排障下钻'],
      action: '业务失败时，从 runId 详情下钻到处理步骤。',
    },
    {
      key: 'result',
      title: '看结果和后续处理',
      done: '结果',
      theme: 'success' as const,
      detail: '结果图能打开是第一位；回调、成本、复测和回滚记录用于后续排查。',
      checks: ['结果可访问', '通知失败单独显示', '成本和验收不挡住结果查询'],
      action: '上线或切默认版本时，只看业务调用和版本证据。',
    },
  ];

  return (
    <OperationFlowCard
      title="业务处理顺序"
      description="以后排查和测试都按这个顺序：先看这次业务调用，再看下面每一步处理。"
      summary="记住一个点：一次调用对应一个 runId；图片分析、生图、评分、回填、回调、计费都属于这次调用里的处理步骤。"
      summaryTheme="primary"
      steps={steps}
    />
  );
}

export function BusinessWorkPathPanel() {
  const paths = [
    {
      key: 'release-new-version',
      title: '上一个新版本',
      tag: '发布路径',
      theme: 'primary' as const,
      steps: ['新增业务版本', '确认底层能力和模型已就绪', '跑真实链路并记录验收通过', '小流量灰度或申请切默认'],
      result: '业务方仍调用同一个业务 API，中台内部切版本。',
      action: '新增版本后先跑真实链路，验收通过再申请切默认。',
    },
    {
      key: 'diagnose-failure',
      title: '处理一次失败',
      tag: '排障路径',
      theme: 'warning' as const,
      steps: ['先看业务复测闭环', '打开失败运行详情', '确认卡在版本、能力、执行节点、回填、回调还是计费', '复测或重试回调后再标记结论'],
      result: '不要只看“任务失败”，要定位到闭环里的具体步骤。',
      action: '先打开失败运行详情，把卡点定位到具体阶段。',
    },
    {
      key: 'connect-business',
      title: '给业务方接入',
      tag: '接入口径',
      theme: 'success' as const,
      steps: ['优先给业务 API', '让对方保存 runId', '统一轮询结果或接收回调', '不要让业务方理解 Coze 工作流或 ComfyUI 节点'],
      result: '业务方只关心传参、runId、结果和错误提示。',
      action: '给业务方业务 API、查询接口和错误码处理口径。',
    },
    {
      key: 'gray-or-rollback',
      title: '做灰度或回滚',
      tag: '风险控制',
      theme: 'default' as const,
      steps: ['先看目标版本证据', '确认验收通过和最近成功样本', '确认有可回滚备选', '再执行灰度、切默认或回滚'],
      result: '切换前必须有证据，不再靠口头确认。',
      action: '先确认验收、样本和回滚版本，再执行切换动作。',
    },
  ];

  return (
    <OperationFlowCard
      title="业务能力怎么用"
      description="这页不是底层配置表。先按实际工作选择路径，再进入版本、运行记录或验收操作。"
      summary="核心能力要固定成线上可用、可灰度、可回滚、可排障的闭环，不再靠口头确认。"
      summaryTheme="primary"
      steps={paths.map((path) => ({
        key: path.key,
        title: path.title,
        detail: path.result,
        action: path.action,
        done: path.tag,
        theme: path.theme,
        checks: path.steps,
      }))}
    />
  );
}

export const BusinessCoreDecisionPanel = ({
  capabilities,
  pendingApprovals,
  summary,
  formatDateTime,
  capabilitiesLoading = false,
}: {
  capabilities: BusinessCapability[];
  pendingApprovals: BusinessDefaultApproval[];
  summary?: BusinessUsageSummaryResponse | null;
  formatDateTime: (value?: string | null) => string;
  capabilitiesLoading?: boolean;
}) => {
  if (capabilitiesLoading && capabilities.length === 0) {
    return (
      <Card bordered className="podi-business-decision-card" title="核心能力当前结论">
        <Alert theme="info" message="业务版本数据还在加载中，加载完成后再判断默认入口、验收、回滚和发布风险。" />
      </Card>
    );
  }

  const rows = buildCoreBusinessReleaseEvidenceRows({ capabilities, pendingApprovals, summary });
  const dangerCount = rows.filter((row) => row.theme === 'danger').length;
  const warningCount = rows.filter((row) => row.theme === 'warning').length;
  const successCount = rows.filter((row) => row.theme === 'success').length;
  const summaryTheme = dangerCount > 0 ? 'danger' : warningCount > 0 ? 'warning' : 'success';
  const summaryText =
    dangerCount > 0
      ? `先处理 ${dangerCount} 条阻塞，再谈上线或放量。`
      : warningCount > 0
        ? `${warningCount} 条核心能力还需要补证据或复核。`
        : `${rows.length} 条核心能力当前都具备基础闭环，可继续小流量验证。`;

  return (
    <Card
      bordered
      className="podi-business-decision-card"
      title={
        <Space align="center" style={{ justifyContent: 'space-between', width: '100%', flexWrap: 'wrap' }}>
          <div>
            <Typography.Text strong>核心能力当前结论</Typography.Text>
            <div>
              <Typography.Text theme="secondary">
                先看这里：每条核心能力只保留状态、卡点、下一步和关键证据，详细配置再往下看。
              </Typography.Text>
            </div>
          </div>
          <Tag theme={summaryTheme} variant="light">
            {successCount}/{rows.length} 生产推荐
          </Tag>
        </Space>
      }
    >
      <Alert theme={summaryTheme === 'danger' ? 'error' : summaryTheme === 'warning' ? 'warning' : 'success'} message={summaryText} />
      <div className="podi-business-decision-grid">
        {rows.map((row) => {
          const defaultItem = row.defaultItem;
          const nextAction =
            row.theme === 'danger'
              ? row.suggestion
              : row.theme === 'warning'
                ? row.suggestion
                : '保持日常巡检；上新版本前先跑真实链路并保留回滚版本。';
          return (
            <section key={row.businessKey} className={`podi-business-decision-item podi-business-decision-item--${row.theme}`}>
              <div className="podi-business-decision-item__header">
                <div>
                  <Typography.Text strong>{businessKeyLabel(row.businessKey)}</Typography.Text>
                  <div>
                    <Typography.Text theme="secondary">{businessCapabilityGroupHint(row.businessKey)}</Typography.Text>
                  </div>
                </div>
                <Space size={4}>
                  <Tag theme={row.onlineStatus.theme} variant="light">
                    {row.onlineStatus.label}
                  </Tag>
                  <Tag theme={row.recommendationStatus.theme} variant="light">
                    {row.recommendationStatus.label}
                  </Tag>
                </Space>
              </div>
              <div className="podi-business-decision-main">
                <Typography.Text theme="secondary">当前默认</Typography.Text>
                <Typography.Text>{businessCapabilityVersionRoleLabel(defaultItem)}</Typography.Text>
                {defaultItem ? (
                  <Typography.Text theme="secondary">内部版本：{defaultItem.version}</Typography.Text>
                ) : null}
                <Typography.Text theme="secondary">
                  发布时间：{defaultItem ? formatDateTime(defaultItem.releaseTime || defaultItem.createdAt) : '—'}
                </Typography.Text>
              </div>
              <div className="podi-business-decision-problem">
                <Typography.Text theme="secondary">当前卡点</Typography.Text>
                <Typography.Text theme={row.theme === 'danger' ? 'error' : row.theme === 'warning' ? 'warning' : 'success'}>
                  {row.reason}
                </Typography.Text>
              </div>
              <div className="podi-business-decision-evidence">
                <Tag theme={row.acceptancePassed ? 'success' : 'warning'} variant="light" size="small">
                  {row.acceptancePassed ? '验收通过' : '待补验收'}
                </Tag>
                <Tag theme={row.outputCount > 0 ? 'success' : 'warning'} variant="light" size="small">
                  {row.outputCount > 0 ? `样本 ${row.outputCount}` : '缺样本'}
                </Tag>
                <Tag theme={row.rollbackReadyAlternatives.length > 0 ? 'success' : 'warning'} variant="light" size="small">
                  {row.rollbackReadyAlternatives.length > 0 ? `可回滚 ${row.rollbackReadyAlternatives.length}` : '回滚待补'}
                </Tag>
                <Tag theme={Number(row.bucket?.failed || 0) > 0 ? 'warning' : 'success'} variant="light" size="small">
                  近 {summary?.windowHours || 24}h 失败 {row.bucket?.failed || 0}
                </Tag>
              </div>
              <Alert theme={row.theme === 'danger' ? 'error' : row.theme === 'warning' ? 'warning' : 'info'} message={`下一步：${nextAction}`} />
            </section>
          );
        })}
      </div>
    </Card>
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
    const versions = capabilities.filter((item) => canonicalBusinessKey(item.businessKey) === businessKey);
    const defaultVersion = versions.find((item) => item.isDefault);
    const rollbackVersions = versions.filter((item) => item.status === 'active' && !item.isDefault);
    const rollbackReadyVersions = rollbackVersions.filter(businessCapabilityHasRollbackEvidence);
    const hasPendingApproval = pendingApprovals.some(
      (item) => canonicalBusinessKey(item.businessKey) === businessKey && item.status === 'pending',
    );
    const failedCount = versions
      .filter((item) => item.isDefault)
      .reduce((total, item) => total + Number(item.runMetrics?.failed || 0), 0);
    const latestDefaultError = defaultVersion?.latestRun?.error || '';
    const governanceStatus = defaultVersion?.governanceStatus || 'unknown';
    const firstGovernanceIssue = defaultVersion?.governanceIssues?.[0] || '';
    const governanceBlocked = governanceStatus === 'blocker';
    const releaseGate = defaultVersion?.releaseGate || null;
    const acceptancePassed = defaultVersion ? releaseGate?.acceptancePassed === true : false;
    const outputCount = Number(defaultVersion?.latestRun?.imageCount || defaultVersion?.latestRun?.image_count || 0) +
      Number(defaultVersion?.latestRun?.videoCount || defaultVersion?.latestRun?.video_count || 0) +
      Number(defaultVersion?.latestRun?.textCount || defaultVersion?.latestRun?.text_count || 0);
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
                ? '默认版本待补验收'
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
      lifecycle: businessCapabilityLifecycleStatus(defaultVersion, {
        outputCount,
        acceptancePassed,
        releaseGateBlocked: releaseGate?.status === 'blocked',
        governanceBlocked,
        runFailed: Boolean(latestDefaultError || failedCount > 0),
        hasPendingApproval,
        rollbackReadyCount: rollbackReadyVersions.length,
        activeAlternativeCount: rollbackVersions.length,
      }),
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
              title: '核心能力',
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
                    <Tag theme={row.lifecycle.online.theme} variant="light">
                      {row.lifecycle.online.label}
                    </Tag>
                    <Tag theme={row.lifecycle.recommendation.theme} variant="light">
                      {row.lifecycle.recommendation.label}
                    </Tag>
                    <Typography.Text>{businessCapabilityVersionRoleLabel(row.defaultVersion)}</Typography.Text>
                  </Space>
                  {row.defaultVersion ? (
                    <Typography.Text theme="secondary">内部版本：{row.defaultVersion.version}</Typography.Text>
                  ) : null}
                  <Typography.Text theme="secondary">
                    {row.defaultVersion?.primaryAbilityName || row.defaultVersion?.primaryAbilityId || '未绑定主能力'}
                  </Typography.Text>
                  {row.defaultVersion ? (
                    <Space size={6} breakLine>
                      {(() => {
                        const releaseGateDisplay = businessReleaseGateDisplay(row.releaseGate);
                        return (
                          <Tag theme={releaseGateDisplay.theme} variant="light">
                            {releaseGateDisplay.label}
                          </Tag>
                        );
                      })()}
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
                        ? `${row.rollbackVersions.length} 个备选待补证据`
                        : '缺回滚安全垫'}
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
          <Typography.Text strong>业务窗口统计</Typography.Text>
          <div>
            <Typography.Text theme="secondary">
              只统计当前筛选的近 {summary?.windowHours || windowHours} 小时；逐条排查仍以“业务调用清单”的 runId 为准。
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
        <BusinessMetricCard label="窗口内调用" value={summary?.total ?? 0} sub="业务入口调用数" />
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
        message={`仍有 ${Number((summary?.unresolvedIssues || []).reduce((total, bucket) => total + Number(bucket.total || 0), 0))} 条问题未确认恢复。先回到上方业务调用清单筛选问题类型，再打开 runId 详情定位卡点。`}
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

type BusinessFlowMonitorStage = {
  key: string;
  title: string;
  status: string;
  detail: string;
  evidence?: string;
  action: string;
  theme: BusinessRunFlowStageTheme;
};

type BusinessFlowHitGroup = {
  key: string;
  title: string;
  detail: string;
  buckets: BusinessFlowEvidenceBucket[];
};

const businessIssueBucketTotal = (summary: BusinessUsageSummaryResponse | null | undefined, keys: string[]) =>
  (summary?.byIssue || [])
    .filter((bucket) => keys.includes(String(bucket.key || '').toLowerCase()))
    .reduce((total, bucket) => total + Number(bucket.total || 0), 0);

const businessIssueBucketFailed = (summary: BusinessUsageSummaryResponse | null | undefined, keys: string[]) =>
  (summary?.byIssue || [])
    .filter((bucket) => keys.includes(String(bucket.key || '').toLowerCase()))
    .reduce((total, bucket) => total + Number(bucket.failed || 0), 0);

const businessFlowStageEvidence = (summary: BusinessUsageSummaryResponse | null | undefined, key: string) =>
  (summary?.flowEvidence?.stageEvidence || []).find((item) => item.key === key);

const businessFlowEvidenceDurationLabel = (bucket?: BusinessFlowEvidenceBucket | null) => {
  if (!bucket) return '';
  const parts = [
    typeof bucket.avgDurationMs === 'number' ? `均 ${formatPanelDurationMs(bucket.avgDurationMs)}` : '',
    typeof bucket.p95DurationMs === 'number' ? `P95 ${formatPanelDurationMs(bucket.p95DurationMs)}` : '',
  ].filter(Boolean);
  return parts.join(' · ');
};

const businessFlowEvidenceCountLabel = (bucket?: BusinessFlowEvidenceBucket | null) => {
  if (!bucket) return '';
  const durationLabel = businessFlowEvidenceDurationLabel(bucket);
  const samples = Number((bucket.evidence as JsonRecord | undefined)?.durationSamples || 0);
  return [durationLabel, samples > 0 ? `耗时样本 ${samples}` : ''].filter(Boolean).join(' · ');
};

const businessFlowHitDigest = (buckets?: BusinessFlowEvidenceBucket[]) => {
  const items = (buckets || []).slice(0, 3);
  if (items.length === 0) return '暂无命中';
  return items.map((bucket) => `${formatShortBusinessId(bucket.label || bucket.key)} ${bucket.total}`).join(' · ');
};

const businessFlowHitGroups = (summary: BusinessUsageSummaryResponse | null | undefined): BusinessFlowHitGroup[] => {
  const flow = summary?.flowEvidence;
  if (!flow) return [];
  return [
    {
      key: 'route',
      title: '路由命中',
      detail: businessFlowHitDigest(flow.routeHits),
      buckets: flow.routeHits || [],
    },
    {
      key: 'candidate',
      title: '候选命中',
      detail: businessFlowHitDigest(flow.candidateHits),
      buckets: flow.candidateHits || [],
    },
    {
      key: 'lora',
      title: 'LoRA',
      detail: businessFlowHitDigest(flow.loraHits),
      buckets: flow.loraHits || [],
    },
    {
      key: 'workflow',
      title: 'Workflow',
      detail: businessFlowHitDigest(flow.workflowHits),
      buckets: flow.workflowHits || [],
    },
  ].filter((group) => group.buckets.length > 0);
};

const businessFlowStageTheme = ({
  danger,
  warning,
  empty,
}: {
  danger?: boolean;
  warning?: boolean;
  empty?: boolean;
}): BusinessRunFlowStageTheme => {
  if (danger) return 'danger';
  if (warning) return 'warning';
  if (empty) return 'default';
  return 'success';
};

const buildBusinessFlowMonitorStages = (
  summary: BusinessUsageSummaryResponse | null | undefined,
): BusinessFlowMonitorStage[] => {
  const total = Number(summary?.total || 0);
  const active = Number(summary?.running || 0) + Number(summary?.queued || 0);
  const versionIssues = businessIssueBucketTotal(summary, ['version']);
  const parameterIssues = businessIssueBucketTotal(summary, ['parameter']);
  const executorIssues = businessIssueBucketTotal(summary, ['executor']);
  const executorFailed = businessIssueBucketFailed(summary, ['executor']);
  const outputIssues = businessIssueBucketTotal(summary, ['output']);
  const outputFailed = businessIssueBucketFailed(summary, ['output']);
  const callbackIssues = businessIssueBucketTotal(summary, ['callback']);
  const billingIssues = businessIssueBucketTotal(summary, ['billing']);
  const callbackFailed = Number(summary?.callbackFailed || 0);
  const callbackRunning = Number(summary?.callbackRunning || 0);
  const billingPending = Number(summary?.billingPending || 0);
  const unpriced = Number(summary?.unpriced || 0);
  const windowHours = Number(summary?.windowHours || 24);
  const versionCount = Number(summary?.byVersion?.length || 0);
  const businessCount = Number(summary?.byBusiness?.length || 0);
  const sourceCount = Number(summary?.bySource?.length || 0);
  const entryEvidence = businessFlowStageEvidence(summary, 'entry');
  const versionEvidence = businessFlowStageEvidence(summary, 'version');
  const preprocessEvidence = businessFlowStageEvidence(summary, 'preprocess');
  const routingEvidence = businessFlowStageEvidence(summary, 'routing');
  const primaryEvidence = businessFlowStageEvidence(summary, 'primary');
  const outputEvidence = businessFlowStageEvidence(summary, 'output');
  const callbackBillingEvidence = businessFlowStageEvidence(summary, 'callback-billing');
  const routeHits = summary?.flowEvidence?.routeHits || [];
  const candidateHits = summary?.flowEvidence?.candidateHits || [];
  const loraHits = summary?.flowEvidence?.loraHits || [];
  const workflowHits = summary?.flowEvidence?.workflowHits || [];
  const candidateHitTotal = candidateHits.reduce((sum, bucket) => sum + Number(bucket.total || 0), 0);

  return [
    {
      key: 'entry',
      title: '提交入口',
      status: total > 0 ? '有入口样本' : '暂无样本',
      detail: `近 ${windowHours} 小时 ${total} 次调用 · 来源 ${sourceCount} 类`,
      evidence: businessFlowEvidenceCountLabel(entryEvidence),
      action: total > 0 ? '继续按 runId 追踪入口到结果。' : '需要封版或验收时，先跑真实业务样本。',
      theme: businessFlowStageTheme({ empty: total <= 0 }),
    },
    {
      key: 'version',
      title: '版本命中',
      status: versionIssues > 0 ? '版本/路由需复核' : '版本命中正常',
      detail: `涉及 ${versionCount} 个版本 · 版本/路由问题 ${versionIssues} 条`,
      evidence: businessFlowEvidenceCountLabel(versionEvidence),
      action: versionIssues > 0 ? '先跑 route-preview，确认默认、灰度和候选版本命中。' : '版本命中稳定，可继续观察候选和历史版本。',
      theme: businessFlowStageTheme({ warning: versionIssues > 0, empty: total <= 0 }),
    },
    {
      key: 'preprocess',
      title: '输入预处理',
      status: parameterIssues > 0 ? '参数或输入需处理' : '输入未见集中问题',
      detail: `参数问题 ${parameterIssues} 条`,
      evidence: businessFlowEvidenceCountLabel(preprocessEvidence),
      action: parameterIssues > 0 ? '核对图片 URL、尺寸、必填字段和业务方请求样例。' : '保留输入摘要即可，专家参数继续折叠。',
      theme: businessFlowStageTheme({ warning: parameterIssues > 0, empty: total <= 0 }),
    },
    {
      key: 'routing',
      title: '路由/分流',
      status: candidateHitTotal > 0 ? '已有候选分流' : businessCount > 0 ? '已有业务分布' : '暂无分布',
      detail: `业务入口 ${businessCount} 类 · 路由 ${routeHits.length} 类 · 候选 ${candidateHitTotal} 次 · 排队/运行 ${active}`,
      evidence: businessFlowEvidenceCountLabel(routingEvidence),
      action:
        candidateHitTotal > 0 || loraHits.length > 0 || workflowHits.length > 0
          ? '下方查看候选、LoRA 和 workflow 命中，效果复盘时按命中项分组抽检。'
          : active > 0
            ? '关注是否长期停留 queued/running，必要时下钻 runId。'
            : '默认路由稳定；候选策略上线后这里会自动显示命中。',
      theme: businessFlowStageTheme({ warning: active > 0, empty: total <= 0 }),
    },
    {
      key: 'primary',
      title: '主执行',
      status: executorIssues > 0 || active > 0 ? '执行链路需观察' : '执行链路正常',
      detail: `执行节点问题 ${executorIssues} 条 · 执行失败 ${executorFailed} · 排队/运行 ${active}`,
      evidence: businessFlowEvidenceCountLabel(primaryEvidence),
      action: executorIssues > 0 || active > 0 ? '检查执行节点、队列、模型/LoRA 依赖和能力日志。' : '执行面暂无集中问题。',
      theme: businessFlowStageTheme({ danger: executorFailed > 0, warning: executorIssues > 0 || active > 0, empty: total <= 0 }),
    },
    {
      key: 'output',
      title: '结果入库',
      status: outputIssues > 0 ? '结果入库需处理' : '结果入库正常',
      detail: `结果/OSS 问题 ${outputIssues} 条 · 失败 ${outputFailed}`,
      evidence: businessFlowEvidenceCountLabel(outputEvidence),
      action: outputIssues > 0 ? '检查输出解析、storedUrl、OSS 落盘和结果字段映射。' : '继续保证对外只暴露自有 URL。',
      theme: businessFlowStageTheme({ danger: outputFailed > 0, warning: outputIssues > 0, empty: total <= 0 }),
    },
    {
      key: 'callback-billing',
      title: '回调/计费',
      status: callbackFailed > 0 || callbackIssues > 0 || billingIssues > 0 || unpriced > 0 ? '交付后置需处理' : '后置链路正常',
      detail: `回调问题 ${callbackIssues} · 回调失败 ${callbackFailed} · 回调中 ${callbackRunning} · 待计费 ${billingPending} · 未定价 ${unpriced}`,
      evidence: businessFlowEvidenceCountLabel(callbackBillingEvidence),
      action:
        callbackFailed > 0
          ? '先重试回调，再确认业务方地址和签名。'
          : callbackIssues > 0
            ? '检查回调配置、签名和业务方接收状态。'
          : billingIssues > 0 || unpriced > 0
            ? '补价格规则、套餐/钱包扣减和结算流水。'
            : '回调和计费暂无集中阻塞。',
      theme: businessFlowStageTheme({
        warning: callbackFailed > 0 || callbackIssues > 0 || callbackRunning > 0 || billingPending > 0 || billingIssues > 0 || unpriced > 0,
        empty: total <= 0,
      }),
    },
  ];
};

const businessFlowMonitorBusinessRows = (summary: BusinessUsageSummaryResponse | null | undefined) =>
  businessOrchestrationKeys.map((businessKey) => {
    const bucket = businessUsageBucketForKey(summary, businessKey);
    const unresolved = businessUnresolvedBucketForKey(summary, businessKey);
    const active = Number(bucket?.running || 0) + Number(bucket?.queued || 0);
    const unresolvedCount = Number(unresolved?.total || 0);
    const failed = Number(bucket?.failed || 0);
    const theme = unresolvedCount > 0 ? 'danger' : active > 0 || failed > 0 ? 'warning' : bucket?.total ? 'success' : 'default';
    const bottleneck =
      unresolvedCount > 0
        ? `未恢复 ${unresolvedCount}`
        : active > 0
          ? `排队/运行 ${active}`
          : failed > 0
            ? `历史失败 ${failed}`
            : bucket?.total
              ? '暂无卡点'
              : '暂无样本';
    return {
      businessKey,
      bucket,
      unresolved,
      theme: theme as BusinessRunFlowStageTheme,
      bottleneck,
    };
  });

const businessFlowStageRoleActions = (stage?: BusinessFlowMonitorStage | null) => {
  if (!stage) {
    return {
      operator: '先跑固定样例，补一个可追踪 runId。',
      ops: '确认业务接口、队列和执行节点是否有可用样本。',
    };
  }
  if (stage.key === 'entry') {
    return {
      operator: stage.theme === 'default' ? '补真实样例，形成入口样本。' : '业务反馈统一收 runId。',
      ops: '检查认证、4xx、限流和入口日志。',
    };
  }
  if (stage.key === 'version' || stage.key === 'routing') {
    return {
      operator: '对比默认版、候选版和固定样例结果。',
      ops: '跑 route-preview，核对版本、灰度和路由命中。',
    };
  }
  if (stage.key === 'preprocess') {
    return {
      operator: '收集输入图和请求参数样例。',
      ops: '核对 schema、上传、图片 URL 和尺寸规则。',
    };
  }
  if (stage.key === 'primary') {
    return {
      operator: '暂停扩大复跑，先等执行链路恢复。',
      ops: '检查执行节点、ComfyUI 队列、模型和 LoRA 依赖。',
    };
  }
  if (stage.key === 'output') {
    return {
      operator: '确认业务方拿到的结果图是否完整。',
      ops: '检查输出解析、storedUrl、OSS 落盘和回填字段。',
    };
  }
  return {
    operator: '同步业务方回调或计费状态。',
    ops: '重试回调，核对签名、价格规则和扣减流水。',
  };
};

export const BusinessFlowMonitoringPanel = ({
  summary,
}: {
  summary?: BusinessUsageSummaryResponse | null;
}) => {
  const stages = buildBusinessFlowMonitorStages(summary);
  const rows = businessFlowMonitorBusinessRows(summary);
  const hitGroups = businessFlowHitGroups(summary);
  const focusedStage = stages.find((stage) => stage.theme === 'danger') || stages.find((stage) => stage.theme === 'warning') || stages[0];
  const focusedActions = businessFlowStageRoleActions(focusedStage);
  return (
    <Card
      bordered
      title={
        <Space align="center" style={{ justifyContent: 'space-between', width: '100%', flexWrap: 'wrap' }}>
          <div>
            <Typography.Text strong>流程监控摘要</Typography.Text>
            <div>
              <Typography.Text theme="secondary">
                按七阶段看近 {summary?.windowHours || 24} 小时业务是否卡在入口、版本、输入、路由、执行、入库或回调计费。
              </Typography.Text>
            </div>
          </div>
          {focusedStage ? (
            <Tag theme={focusedStage.theme as any} variant="light">
              当前关注：{focusedStage.title}
            </Tag>
          ) : null}
          {summary?.flowEvidence ? (
            <Tag theme="primary" variant="light">
              流程证据已接入
            </Tag>
          ) : null}
        </Space>
      }
    >
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        <section className={`podi-business-flow-focus podi-business-flow-focus--${focusedStage?.theme || 'default'}`}>
          <div className="podi-business-flow-focus__main">
            <span>当前卡点</span>
            <strong>{focusedStage ? `${focusedStage.title} · ${focusedStage.status}` : '暂无流程样本'}</strong>
            <small>{focusedStage?.action || '先跑真实业务样本，形成可追踪 runId。'}</small>
          </div>
          <div className="podi-business-flow-focus__meta">
            <span>{focusedStage?.detail || `近 ${summary?.windowHours || 24} 小时暂无样本`}</span>
            {focusedStage?.evidence ? <span>{focusedStage.evidence}</span> : null}
          </div>
          <div className="podi-business-flow-focus__actions">
            <div>
              <span>运营</span>
              <strong>{focusedActions.operator}</strong>
            </div>
            <div>
              <span>运维</span>
              <strong>{focusedActions.ops}</strong>
            </div>
          </div>
        </section>
        <div className="podi-business-flow-rail" aria-label="业务七阶段流程轨道">
          {stages.map((stage, index) => (
            <div
              key={stage.key}
              className={`podi-business-flow-rail__step podi-business-flow-rail__step--${stage.theme}${
                focusedStage?.key === stage.key ? ' is-current' : ''
              }`}
            >
              <span>{index + 1}</span>
              <strong>{stage.title}</strong>
              <small>{stage.status}</small>
            </div>
          ))}
        </div>
        {hitGroups.length > 0 ? (
          <div className="podi-business-flow-hit-grid">
            {hitGroups.map((group) => (
              <section key={group.key} className="podi-business-flow-hit">
                <Space direction="vertical" size={4} style={{ width: '100%' }}>
                  <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
                    <Typography.Text strong>{group.title}</Typography.Text>
                    <Tag size="small" variant="light">
                      {group.buckets.reduce((sum, bucket) => sum + Number(bucket.total || 0), 0)}
                    </Tag>
                  </Space>
                  <Typography.Text theme="secondary">{group.detail}</Typography.Text>
                </Space>
              </section>
            ))}
          </div>
        ) : null}
        <details className="podi-business-disclosure">
          <summary>
            <span>阶段明细</span>
            <small>展开查看七阶段耗时、证据和处理动作</small>
          </summary>
          <div className="podi-business-flow-stage-grid">
            {stages.map((stage, index) => (
              <section key={stage.key} className={`podi-business-flow-stage-card podi-business-flow-stage-card--${stage.theme}`}>
                <Space direction="vertical" size={6} style={{ width: '100%' }}>
                  <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
                    <Typography.Text strong>{stage.title}</Typography.Text>
                    <Tag theme={stage.theme as any} variant="light" size="small">
                      {index + 1}
                    </Tag>
                  </Space>
                  <Typography.Text>{stage.status}</Typography.Text>
                  <Typography.Text theme="secondary">{stage.detail}</Typography.Text>
                  {stage.evidence ? <Typography.Text theme="secondary">{stage.evidence}</Typography.Text> : null}
                  <Typography.Text theme={stage.theme === 'danger' ? 'error' : stage.theme === 'warning' ? 'warning' : 'secondary'}>
                    {stage.action}
                  </Typography.Text>
                </Space>
              </section>
            ))}
          </div>
        </details>
        <div className="podi-business-command-table">
          <div className="podi-business-command-head">
            <span>业务能力</span>
            <span>流程健康</span>
            <span>近 {summary?.windowHours || 24} 小时</span>
            <span>当前卡点</span>
            <span>下一步</span>
          </div>
          {rows.map((row) => {
            const active = Number(row.bucket?.running || 0) + Number(row.bucket?.queued || 0);
            const nextAction =
              row.theme === 'danger'
                ? '打开 runId 详情，按七阶段定位并复测。'
                : row.theme === 'warning'
                  ? active > 0
                    ? '观察队列和执行时长，超时后转排障。'
                    : '保留历史失败，等待同版本成功样本覆盖。'
                  : row.bucket?.total
                    ? '作为稳定样本进入效果复盘。'
                    : '需要验收时先跑固定样例。';
            return (
              <section key={row.businessKey} className={`podi-business-command-row podi-business-command-row--${row.theme}`}>
                <div className="podi-business-command-cell podi-business-command-cell--entry">
                  <Typography.Text strong>{businessKeyLabel(row.businessKey)}</Typography.Text>
                  <Typography.Text theme="secondary">{businessCapabilityGroupHint(row.businessKey)}</Typography.Text>
                </div>
                <div className="podi-business-command-cell">
                  <Tag theme={row.theme as any} variant="light">
                    {row.theme === 'danger' ? '有未恢复问题' : row.theme === 'warning' ? '观察中' : row.theme === 'success' ? '稳定' : '缺样本'}
                  </Tag>
                  <Typography.Text theme="secondary">成功率 {formatRatePercent(row.bucket?.successRate)}</Typography.Text>
                </div>
                <div className="podi-business-command-cell">
                  <Typography.Text>
                    {row.bucket?.total || 0} 次 · 成功 {row.bucket?.succeeded || 0} · 失败 {row.bucket?.failed || 0}
                  </Typography.Text>
                  <Typography.Text theme="secondary">排队/运行 {active}</Typography.Text>
                </div>
                <div className="podi-business-command-cell">
                  <Typography.Text theme={row.theme === 'danger' ? 'error' : row.theme === 'warning' ? 'warning' : 'secondary'}>
                    {row.bottleneck}
                  </Typography.Text>
                  {row.unresolved?.label ? (
                    <Typography.Text theme="secondary">{businessIssueLabel(row.unresolved.key, row.unresolved.label)}</Typography.Text>
                  ) : null}
                </div>
                <div className="podi-business-command-cell">
                  <Typography.Text theme="secondary">{nextAction}</Typography.Text>
                </div>
              </section>
            );
          })}
        </div>
      </Space>
    </Card>
  );
};

type BusinessQualityReviewRow = {
  businessKey: string;
  bucket: ReturnType<typeof businessUsageBucketForKey>;
  unresolved: ReturnType<typeof businessUnresolvedBucketForKey>;
  loadedOutputCount: number;
  reviewableCount: number;
  reviewTarget: number;
  theme: BusinessRunFlowStageTheme;
  status: string;
  evidence: string;
  action: string;
  samplePlan: string;
  inputTags: string[];
  issueTags: string[];
  recordedTotal: number;
  recordedReviewed: number;
  recordedBad: number;
  recordedBorderline: number;
  recordedTopIssueTags: string[];
  recordedTopInputTags: string[];
  recordedTopIssueBuckets: BusinessOutputReviewBucket[];
  recordedTopInputBuckets: BusinessOutputReviewBucket[];
};

const businessQualityInputTags = (businessKey?: string | null) => {
  const key = canonicalBusinessKey(businessKey);
  if (key === 'pattern_extract') return ['平铺花纹', '复杂背景', '布料纹理'];
  if (key === 'fission') return ['主体清晰', '满版图案', '颜色敏感'];
  if (key === 'product_design') return ['服装面料', '家纺软装', '电商主图'];
  if (key === 'image_edit') return ['局部修改', '参考图约束', '画布扩展'];
  if (key === 'outpaint') return ['四边扩展', '单边扩展', '比例变化'];
  if (key === 'text_fission') return ['中文文字', '英文数字', '版式复刻'];
  return ['标准样例', '边界样例', '业务样例'];
};

const businessQualityIssueTags = (businessKey?: string | null) => {
  const key = canonicalBusinessKey(businessKey);
  if (key === 'pattern_extract') return ['主体残留', '边缘脏污', '纹理断裂', '颜色偏移'];
  if (key === 'fission') return ['结构偏移', '主体变形', '图案密度变化', '色差过大'];
  if (key === 'product_design') return ['图案贴合差', '产品结构错误', '材质不真实', '商业感不足'];
  if (key === 'image_edit') return ['指令未执行', '参考图丢失', '局部边缘不自然', '原图被误改'];
  if (key === 'outpaint') return ['接缝明显', '背景穿帮', '主体拉伸', '比例失真'];
  if (key === 'text_fission') return ['文字错字', '版式漂移', '笔画糊化', '语义丢失'];
  return ['效果不稳定', '输出不可用', '需要人工复核'];
};

const businessQualitySamplePlan = (businessKey?: string | null) => {
  const key = canonicalBusinessKey(businessKey);
  if (key === 'pattern_extract') return '每轮至少 3 张：干净花纹、复杂背景、布料纹理。';
  if (key === 'fission') return '每轮至少 5 张：单主体、满版图案、颜色敏感、复杂纹理、业务真实图。';
  if (key === 'product_design') return '每轮至少 5 张：服装、家纺、箱包、包装、电商主图。';
  if (key === 'image_edit') return '每轮至少 5 张：删除、替换、补色、参考图、扩展画布。';
  if (key === 'outpaint') return '每轮至少 4 张：四边、单边、横向、纵向扩展。';
  if (key === 'text_fission') return '每轮至少 3 张：中文密集、英文数字、低对比文字。';
  return '每轮固定覆盖标准、边界和真实业务图。';
};

const businessRunVisualOutputCount = (row: BusinessRun) => {
  const flowOutput = asJsonRecord(row.flowSummary?.output);
  const imageCount = recordNumber(flowOutput, 'imageCount', row.imageUrls?.length || 0);
  const videoCount = recordNumber(flowOutput, 'videoCount', row.videoUrls?.length || 0);
  const resourceCount = recordNumber(flowOutput, 'resourceCount', 0);
  return imageCount + videoCount + resourceCount;
};

const businessQualityReviewRunId = (review?: BusinessOutputReview | null) =>
  String(review?.runId || (review as any)?.run_id || '').trim();

const businessQualityReviewOutputIndex = (review?: BusinessOutputReview | null) =>
  Number(review?.outputIndex ?? (review as any)?.output_index ?? 0);

const businessQualityReviewSamples = (bucket?: BusinessOutputReviewBucket | null) =>
  (bucket?.sampleReviews || (bucket as any)?.sample_reviews || []).filter(Boolean) as BusinessOutputReview[];

const businessQualityReviewGradeText = (value?: string | null) => {
  if (value === 'excellent') return '优秀';
  if (value === 'usable') return '可用';
  if (value === 'borderline') return '临界';
  if (value === 'bad') return '差图';
  if (value === 'blocked') return '阻断';
  return '待评';
};

const businessQualityReviewGradeTheme = (value?: string | null) => {
  if (value === 'excellent' || value === 'usable') return 'success';
  if (value === 'borderline' || value === 'pending') return 'warning';
  if (value === 'bad' || value === 'blocked') return 'danger';
  return 'default';
};

const businessQualityReviewIsImage = (url?: string | null) => /\.(png|jpg|jpeg|webp|gif|bmp|svg)(\?|#|$)/i.test(String(url || ''));

const buildBusinessQualityReviewRows = (
  summary: BusinessUsageSummaryResponse | null | undefined,
  runs: BusinessRun[] = [],
  qualitySummary?: BusinessOutputReviewSummaryResponse | null,
): BusinessQualityReviewRow[] =>
  businessOrchestrationKeys.map((businessKey) => {
    const bucket = businessUsageBucketForKey(summary, businessKey);
    const unresolved = businessUnresolvedBucketForKey(summary, businessKey);
    const reviewStats = (qualitySummary?.byBusiness || []).find((item) => canonicalBusinessKey(item.businessKey) === businessKey);
    const loadedOutputCount = runs.filter((row) => canonicalBusinessKey(row.businessKey) === businessKey && businessRunVisualOutputCount(row) > 0).length;
    const recordedTotal = Number(reviewStats?.total || 0);
    const recordedReviewed = Number(reviewStats?.reviewed || 0);
    const recordedBad = Number(reviewStats?.bad || 0);
    const recordedBorderline = Number(reviewStats?.borderline || 0);
    const reviewableCount = Math.max(Number(bucket?.succeeded || 0), loadedOutputCount, recordedTotal);
    const reviewTarget = reviewableCount > 0 ? Math.min(5, reviewableCount) : 0;
    const failed = Number(bucket?.failed || 0);
    const unresolvedCount = Number(unresolved?.total || 0);
    const successRate = typeof bucket?.successRate === 'number' ? bucket.successRate : null;
    const lowSuccessRate = successRate !== null && successRate < 0.9;
    const theme: BusinessRunFlowStageTheme =
      unresolvedCount > 0
        ? 'danger'
        : recordedBad > 0 || recordedBorderline > 0 || failed > 0 || lowSuccessRate
          ? 'warning'
          : recordedReviewed > 0 || reviewableCount >= 3
            ? 'success'
            : reviewableCount > 0
              ? 'warning'
              : 'default';
    const status =
      unresolvedCount > 0
        ? '先排障再评审'
        : recordedBad > 0 || recordedBorderline > 0
          ? '已有质量问题'
        : failed > 0 || lowSuccessRate
          ? '稳定性需复盘'
          : recordedReviewed > 0 || reviewableCount >= 3
            ? '可进入抽检'
            : reviewableCount > 0
              ? '样本不足'
              : '待补固定样例';
    const action =
      unresolvedCount > 0
        ? '先打开未恢复 runId，确认不是链路故障。'
        : recordedBad > 0 || recordedBorderline > 0
          ? '查看 Top 问题标签，决定调参、分流或换候选。'
        : failed > 0 || lowSuccessRate
          ? '先标失败类型，再决定分流或换 LoRA。'
          : recordedReviewed > 0 || reviewableCount >= 3
            ? '抽检输出图，打质量档位和问题标签。'
            : '按固定样例池补跑标准样例。';
    const evidence =
      recordedReviewed > 0
        ? `已标注 ${recordedReviewed}/${recordedTotal} · 不可用 ${recordedBad} · 临界 ${recordedBorderline}`
        : reviewableCount > 0
        ? `可抽检 ${reviewableCount} 张 · 本轮建议 ${reviewTarget} 张 · 成功率 ${formatRatePercent(bucket?.successRate)}`
        : `近 ${summary?.windowHours || 24} 小时暂无可抽检输出`;
    return {
      businessKey,
      bucket,
      unresolved,
      loadedOutputCount,
      reviewableCount,
      reviewTarget,
      theme,
      status,
      evidence,
      action,
      samplePlan: businessQualitySamplePlan(businessKey),
      inputTags: businessQualityInputTags(businessKey),
      issueTags: businessQualityIssueTags(businessKey),
      recordedTotal,
      recordedReviewed,
	      recordedBad,
	      recordedBorderline,
	      recordedTopIssueTags: (reviewStats?.topIssueTags || []).map((item) => item.label || item.key).filter(Boolean),
	      recordedTopInputTags: (reviewStats?.topInputTags || []).map((item) => item.label || item.key).filter(Boolean),
	      recordedTopIssueBuckets: reviewStats?.topIssueTags || [],
	      recordedTopInputBuckets: reviewStats?.topInputTags || [],
	    };
	  });

const businessQualityReviewSummary = (rows: BusinessQualityReviewRow[]) => {
  const reviewableBusinesses = rows.filter((row) => row.reviewableCount > 0).length;
  const reviewTargets = rows.reduce((total, row) => total + row.reviewTarget, 0);
  const blocked = rows.filter((row) => row.theme === 'danger').length;
  const warning = rows.filter((row) => row.theme === 'warning').length;
  const topIssueTags = Array.from(new Set(rows.flatMap((row) => row.issueTags))).slice(0, 8);
  return { reviewableBusinesses, reviewTargets, blocked, warning, topIssueTags };
};

const businessQualityReviewFocusRow = (rows: BusinessQualityReviewRow[]) => {
  const candidates = [...rows].sort((a, b) => {
    const priority = (row: BusinessQualityReviewRow) =>
      row.theme === 'danger' ? 400 : row.theme === 'warning' ? 300 : row.reviewTarget > 0 ? 200 : 100;
    return (
      priority(b) - priority(a) ||
      b.recordedBad - a.recordedBad ||
      b.recordedBorderline - a.recordedBorderline ||
      b.reviewTarget - a.reviewTarget ||
      b.reviewableCount - a.reviewableCount
    );
  });
  return candidates[0] || null;
};

const businessQualityReviewRoleActions = (row?: BusinessQualityReviewRow | null) => {
  if (!row) {
    return {
      operator: '先补固定样例，跑出可标注输出。',
      engineer: '确认业务版本、样例池和质量标签口径。',
    };
  }
  if (row.theme === 'danger') {
    return {
      operator: '暂停效果判断，先跟进未恢复 runId。',
      engineer: '排除链路故障后，再评估模型、LoRA 或 workflow。',
    };
  }
  if (row.recordedBad > 0 || row.recordedBorderline > 0) {
    return {
      operator: '补同类样例标注，确认问题是否集中。',
      engineer: '按问题标签准备分流、调参或候选 LoRA/workflow。',
    };
  }
  if (row.reviewTarget > 0) {
    return {
      operator: '按本轮建议数量抽检并打质量标签。',
      engineer: '观察输入标签和候选命中，积累默认切换证据。',
    };
  }
  return {
    operator: '先维护固定样例池，再发起同批复跑。',
    engineer: '补齐样例覆盖范围，避免只凭单张图判断效果。',
  };
};

export const BusinessQualityReviewPanel = ({
  summary,
  runs = [],
  qualitySummary,
  onOpenReview,
}: {
  summary?: BusinessUsageSummaryResponse | null;
  runs?: BusinessRun[];
  qualitySummary?: BusinessOutputReviewSummaryResponse | null;
  onOpenReview?: (review: BusinessOutputReview) => void;
}) => {
  const rows = buildBusinessQualityReviewRows(summary, runs, qualitySummary);
  const reviewSummary = businessQualityReviewSummary(rows);
  const recordedReviewTotal = Number(qualitySummary?.total || 0);
  const recentReviewSamples = (qualitySummary?.recentReviews || []).filter((review) => businessQualityReviewRunId(review)).slice(0, 6);
  const focusRow = businessQualityReviewFocusRow(rows);
  const focusActions = businessQualityReviewRoleActions(focusRow);
  const focusIssueTags =
    focusRow?.recordedTopIssueTags.length ? focusRow.recordedTopIssueTags.slice(0, 3).join('、') : focusRow?.issueTags.slice(0, 3).join('、') || '待标注';
  const overallTheme: BusinessRunFlowStageTheme =
    reviewSummary.blocked > 0 ? 'danger' : reviewSummary.warning > 0 ? 'warning' : reviewSummary.reviewableBusinesses > 0 ? 'success' : 'default';
  const renderBucketButtons = (
    buckets: BusinessOutputReviewBucket[],
    fallbackTags: string[],
    options?: { theme?: string; prefix: string },
  ) => {
    const visibleBuckets = buckets.length > 0 ? buckets.slice(0, 4) : [];
    if (visibleBuckets.length > 0) {
      return visibleBuckets.map((bucket) => {
        const sample = businessQualityReviewSamples(bucket)[0];
        const disabled = !sample || !onOpenReview;
        return (
          <Button
            key={`${options?.prefix || 'bucket'}:${bucket.key}`}
            size="small"
            variant="outline"
            theme={(options?.theme || 'default') as any}
            disabled={disabled}
            onClick={() => sample && onOpenReview?.(sample)}
          >
            {bucket.label || bucket.key} {bucket.total}
          </Button>
        );
      });
    }
    return fallbackTags.slice(0, options?.prefix === 'issue' ? 4 : 3).map((tag) => (
      <Tag key={`${options?.prefix || 'tag'}:${tag}`} theme={(options?.theme || 'default') as any} variant="light" size="small">
        {tag}
      </Tag>
    ));
  };
  return (
    <Card
      bordered
      title={
        <Space align="center" style={{ justifyContent: 'space-between', width: '100%', flexWrap: 'wrap' }}>
          <div>
            <Typography.Text strong>出图效果复盘</Typography.Text>
	            <div>
	              <Typography.Text theme="secondary">
	                先用固定样例、输入标签和问题标签做轻量抽检；Top 标签可直接打开对应 runId 和输出图。
	              </Typography.Text>
	            </div>
          </div>
          <Tag theme={overallTheme as any} variant="light">
            本轮建议抽检 {reviewSummary.reviewTargets} 张
          </Tag>
        </Space>
      }
    >
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        <section className={`podi-business-quality-focus podi-business-quality-focus--${overallTheme}`}>
          <div className="podi-business-quality-focus__main">
            <span>本轮关注</span>
            <strong>{focusRow ? `${businessKeyLabel(focusRow.businessKey)} · ${focusRow.status}` : '暂无可复盘输出'}</strong>
            <small>{focusRow?.action || '先跑固定样例，形成可标注输出。'}</small>
          </div>
          <div className="podi-business-quality-focus__metrics">
            <div>
              <span>建议抽检</span>
              <strong>{reviewSummary.reviewTargets} 张</strong>
              <small>已标注 {recordedReviewTotal}</small>
            </div>
            <div>
              <span>业务覆盖</span>
              <strong>{reviewSummary.reviewableBusinesses}/{rows.length}</strong>
              <small>先排障 {reviewSummary.blocked} · 观察 {reviewSummary.warning}</small>
            </div>
            <div>
              <span>问题标签</span>
              <strong>{focusIssueTags}</strong>
              <small>{focusRow?.samplePlan || '维护固定样例后再抽检'}</small>
            </div>
          </div>
          <div className="podi-business-quality-focus__actions">
            <div>
              <span>运营</span>
              <strong>{focusActions.operator}</strong>
            </div>
            <div>
              <span>能力工程师</span>
              <strong>{focusActions.engineer}</strong>
            </div>
          </div>
        </section>
        <div className="podi-business-command-table">
          <div className="podi-business-command-head">
            <span>业务能力</span>
            <span>质量状态</span>
            <span>样例与标注</span>
            <span>下一步</span>
            <span>下钻</span>
          </div>
          {rows.map((row) => (
            <section key={row.businessKey} className={`podi-business-command-row podi-business-command-row--${row.theme}`}>
              <div className="podi-business-command-cell podi-business-command-cell--entry">
                <Typography.Text strong>{businessKeyLabel(row.businessKey)}</Typography.Text>
                <Typography.Text theme="secondary">{businessCapabilityGroupHint(row.businessKey)}</Typography.Text>
              </div>
              <div className="podi-business-command-cell">
                <Tag theme={row.theme as any} variant="light">
                  {row.status}
                </Tag>
                <Typography.Text theme="secondary">{row.evidence}</Typography.Text>
                {row.unresolved?.label ? (
                  <Typography.Text theme="warning">{businessIssueLabel(row.unresolved.key, row.unresolved.label)}</Typography.Text>
                ) : null}
              </div>
              <div className="podi-business-command-cell">
                <Typography.Text>
                  可抽检 {row.reviewableCount} · 本轮 {row.reviewTarget}
                  {row.loadedOutputCount > 0 ? ` · 当前页输出 ${row.loadedOutputCount}` : ''}
                </Typography.Text>
                <Typography.Text theme="secondary">{row.samplePlan}</Typography.Text>
              </div>
              <div className="podi-business-command-cell">
                <Typography.Text theme={row.theme === 'danger' ? 'error' : row.theme === 'warning' ? 'warning' : 'secondary'}>
                  {row.action}
                </Typography.Text>
              </div>
              <div className="podi-business-command-cell">
                <Typography.Text theme="secondary">
                  输入标签 {row.recordedTopInputBuckets.length || row.inputTags.length} · 问题标签{' '}
                  {row.recordedTopIssueBuckets.length || row.issueTags.length}
                </Typography.Text>
                <Typography.Text theme="secondary">展开下方查看样例和 Top 标签。</Typography.Text>
              </div>
            </section>
	          ))}
	        </div>
        <details className="podi-business-disclosure">
          <summary>
            <span>标签体系与样例下钻</span>
            <small>展开查看输入标签、问题标签和最近质量样例</small>
          </summary>
          <div className="podi-business-disclosure-body">
            <div className="podi-business-quality-tag-grid">
              {rows.map((row) => (
                <section key={`${row.businessKey}:quality-tags`} className="podi-business-quality-tag-row">
                  <div>
                    <Typography.Text strong>{businessKeyLabel(row.businessKey)}</Typography.Text>
                    <Typography.Text theme="secondary">{row.samplePlan}</Typography.Text>
                  </div>
                  <div>
                    <Typography.Text theme="secondary">输入标签</Typography.Text>
                    <Space size={4} breakLine>
                      {renderBucketButtons(row.recordedTopInputBuckets, row.inputTags, { prefix: `input:${row.businessKey}` })}
                    </Space>
                  </div>
                  <div>
                    <Typography.Text theme="secondary">问题标签</Typography.Text>
                    <Space size={4} breakLine>
                      {renderBucketButtons(row.recordedTopIssueBuckets, row.issueTags, { prefix: `issue:${row.businessKey}`, theme: 'warning' })}
                    </Space>
                  </div>
                </section>
              ))}
            </div>
            {recentReviewSamples.length > 0 ? (
              <div className="podi-business-quality-samples">
                <Space align="center" style={{ justifyContent: 'space-between', width: '100%', flexWrap: 'wrap' }}>
                  <Typography.Text strong>最近质量样例</Typography.Text>
                  <Typography.Text theme="secondary">用于从统计结论回到具体输出图</Typography.Text>
                </Space>
                <div className="podi-business-quality-sample-grid">
                  {recentReviewSamples.map((review) => {
                    const runId = businessQualityReviewRunId(review);
                    const outputIndex = businessQualityReviewOutputIndex(review);
                    const issueLabel = (review.issueTags || []).slice(0, 2).join('、') || '无问题标签';
                    return (
                      <div key={`${review.id}:${runId}:${outputIndex}`} className="podi-business-quality-sample-item">
                        <div className="podi-business-quality-sample-item__preview">
                          {businessQualityReviewIsImage(review.outputUrl) ? (
                            <img src={review.outputUrl || ''} alt={`quality-review-${runId}-${outputIndex}`} loading="lazy" />
                          ) : (
                            <span>{review.outputUrl ? '资源' : '无预览'}</span>
                          )}
                        </div>
                        <Space direction="vertical" size={4} style={{ minWidth: 0 }}>
                          <Space size={4} breakLine>
                            <Tag theme={businessQualityReviewGradeTheme(review.qualityGrade) as any} variant="light" size="small">
                              {businessQualityReviewGradeText(review.qualityGrade)}
                            </Tag>
                            <Typography.Text theme="secondary">结果 {outputIndex + 1}</Typography.Text>
                          </Space>
                          <Typography.Text>{businessKeyLabel(review.businessKey)}</Typography.Text>
                          <Typography.Text theme="secondary">{issueLabel}</Typography.Text>
                          <Button size="small" variant="outline" disabled={!onOpenReview} onClick={() => onOpenReview?.(review)}>
                            打开 runId
                          </Button>
                        </Space>
                      </div>
                    );
                  })}
                </div>
              </div>
            ) : null}
            <Alert
              theme="info"
              message={
                recordedReviewTotal > 0
                  ? `已接入人工标注汇总：近 ${qualitySummary?.windowHours || 168} 小时 ${recordedReviewTotal} 条；按业务、输入标签、问题标签统计 TopN 后，再决定分流、调参或切换 LoRA/workflow。`
                  : `质量标签候选：${reviewSummary.topIssueTags.join('、')}。后续标注后，按业务、输入标签、问题标签统计 TopN，再决定分流、调参或切换 LoRA/workflow。`
              }
            />
          </div>
        </details>
      </Space>
    </Card>
  );
};

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
    return '待核对套餐或钱包扣减';
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

const businessRunStepTheme = (status?: string | null): BusinessRunFlowStageTheme => {
  const value = String(status || '').toLowerCase();
  if (value === 'succeeded' || value === 'success' || value === 'completed') return 'success';
  if (value === 'failed' || value === 'error' || value === 'timeout' || value === 'cancelled') return 'danger';
  if (value === 'running' || value === 'queued' || value === 'pending' || value === 'planned') return 'warning';
  if (value === 'skipped') return 'default';
  return 'default';
};

const businessRunStepDurationLabel = (step?: Pick<BusinessRunStep, 'durationMs'> | null) =>
  typeof step?.durationMs === 'number' ? `耗时 ${formatPanelDurationMs(step.durationMs)}` : '';

const businessRunStepDisplayName = (step?: BusinessRunStep | null) =>
  step?.displayName || step?.componentLabel || step?.abilityName || step?.stepId || step?.stepType || '';

const findBusinessRunStep = (detail: BusinessRun, matcher: (step: BusinessRunStep) => boolean) =>
  (detail.steps || []).find((step) => step.enabled !== false && matcher(step));

const countRequestPayloadFields = (detail: BusinessRun) => Object.keys(asJsonRecord(detail.requestPayload)).length;

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
  const routeMode = businessRunRouteLabel(detail.routeInfo);

  const abilityName = recordText(ability, 'name', detail.abilityName || detail.abilityId || '');
  const abilityTaskId = recordText(ability, 'taskId', detail.abilityTaskId || detail.taskId || '');
  const abilityOk = hasBusinessEvidenceValue(abilityName) || hasBusinessEvidenceValue(abilityTaskId);

  const executorName = recordText(executor, 'name', '');
  const executorId = recordText(executor, 'id', '');
  const executorType = recordText(executor, 'type', '');
  const executorOk = hasBusinessEvidenceValue(executorName) || hasBusinessEvidenceValue(executorId);
  const vendorModelChannel = !executorOk && businessRunUsesVendorModelChannel(detail);
  const vendorModelLabel = [detail.vendorModelProvider || detail.abilityProvider, detail.vendorModelName].filter(Boolean).join(' · ');
  const apiSummary = detail.apiUsage?.summary || {};
  const apiTotal = Number(apiSummary.total || 0);
  const submitCount = Number(apiSummary.submitCount || 0);
  const pollCount = Number(apiSummary.pollCount || 0);
  const apiMissingForExternal = apiTotal <= 0 && !businessRunIsInternalOrEvalSource(detail);
  const requestFieldCount = countRequestPayloadFields(detail);
  const preprocessStep = findBusinessRunStep(detail, (step) => {
    const role = String(step.role || '').toLowerCase();
    const type = String(step.stepType || '').toLowerCase();
    return (
      role === 'preprocess' ||
      role === 'input' ||
      type === 'input' ||
      type === 'input_mapping' ||
      type === 'prompt_template' ||
      type === 'vl_analyze' ||
      type === 'vl_analyze_image'
    );
  });
  const primaryStep = findBusinessRunStep(detail, (step) => {
    const role = String(step.role || '').toLowerCase();
    const type = String(step.stepType || '').toLowerCase();
    return (
      role === 'primary' ||
      Boolean(step.abilityTaskId) ||
      type === 'ability_task' ||
      type === 'comfyui_workflow' ||
      type === 'vendor_api'
    );
  });
  const outputStep = findBusinessRunStep(detail, (step) => {
    const role = String(step.role || '').toLowerCase();
    const type = String(step.stepType || '').toLowerCase();
    return role === 'output' || type === 'output_mapping' || type === 'result_mapping';
  });

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
  const callbackStageResult = callbackConfigured ? businessCallbackStatusLabel(callbackStatus) : '未配置回调';
  const billingStageResult = billingSettled
    ? businessWalletStatusLabel(settlement)
    : billingFailed
      ? '扣减失败'
      : billingUnpriced
        ? '成功但未定价'
        : billingNoCharge
          ? '本次不计费'
          : billingPending
            ? '等待计费确认'
            : businessBillingStatusLabel(detail.billingStatus);
  const primaryTheme = primaryStep
    ? businessRunStepTheme(primaryStep.status)
    : executorOk || vendorModelChannel || abilityOk
      ? active
        ? 'primary'
        : 'success'
      : failed
        ? 'danger'
        : 'warning';
  const callbackBillingTheme: BusinessRunFlowStageTheme = callbackFailed || billingFailed
    ? 'danger'
    : callbackStatus === 'running' || billingUnpriced || billingPending
      ? 'warning'
      : finished
        ? 'success'
        : 'default';

  return [
    {
      title: '提交入口',
      result: apiTotal > 0 ? '入口已记录' : businessRunIsInternalOrEvalSource(detail) ? '内部/测评提交' : '未记录入口',
      detail: `${businessSourceLabel(detail.source)} · ${detail.channel || '未标记渠道'}`,
      hint:
        apiTotal > 0
          ? `提交 ${submitCount} · 轮询 ${pollCount} · 最近入口 ${apiSummary.lastSeenAt || detail.createdAt}`
          : detail.requestId || detail.traceId
            ? `追踪：${formatShortBusinessId(detail.requestId || detail.traceId)}`
            : '外部业务反馈时优先让对方提供 runId 和提交时间。',
      theme: apiMissingForExternal ? 'warning' : 'success',
    },
    {
      title: '版本命中',
      result: routeOk ? '已确定业务版本' : '未确认版本',
      detail: `${routeVersion} · ${routeMode}`,
      hint: routeCapabilityId ? `对应能力：${formatShortBusinessId(routeCapabilityId)}` : '需要确认默认版本是否生效。',
      theme: routeOk ? 'success' : failed ? 'danger' : 'warning',
    },
    {
      title: '输入预处理',
      result: preprocessStep
        ? businessRunStepStatusLabel(preprocessStep.status)
        : requestFieldCount > 0
          ? '已记录输入摘要'
          : '无前置处理',
      detail: preprocessStep ? businessRunStepDisplayName(preprocessStep) : `请求字段 ${requestFieldCount}`,
      hint:
        preprocessStep?.error ||
        businessRunStepDurationLabel(preprocessStep) ||
        (requestFieldCount > 0 ? '输入已进入业务运行记录，详情里可查看请求摘要。' : '该业务可能不需要 VL 或参数整理步骤。'),
      theme: preprocessStep ? businessRunStepTheme(preprocessStep.status) : requestFieldCount > 0 ? 'success' : 'default',
    },
    {
      title: '路由/分流',
      result: routeOk ? routeMode : active ? '等待路由' : '未见路由证据',
      detail: routeCapabilityId ? `能力 ${formatShortBusinessId(routeCapabilityId)}` : abilityName || '未记录分流目标',
      hint:
        recordText(route, 'reason', '') ||
        recordText(route, 'selectedBy', '') ||
        '后续分流规则会在这里说明命中图类、灰度或候选版本。',
      theme: routeOk ? 'success' : failed ? 'danger' : active ? 'warning' : 'default',
    },
    {
      title: '主执行',
      result: primaryStep
        ? businessRunStepStatusLabel(primaryStep.status)
        : executorOk
          ? '已命中执行节点'
          : vendorModelChannel
            ? '第三方模型通道'
            : abilityOk
              ? '已下发到能力'
              : active
                ? '等待执行'
                : '未见执行证据',
      detail: businessRunStepDisplayName(primaryStep) || executorName || executorId || vendorModelLabel || abilityName || '未记录执行目标',
      hint:
        primaryStep?.error ||
        businessRunStepDurationLabel(primaryStep) ||
        (abilityTaskId ? `排障编号：${formatShortBusinessId(abilityTaskId)}` : '') ||
        (executorOk
          ? [formatShortBusinessId(executorId), executorType].filter(Boolean).join(' · ')
          : vendorModelChannel
            ? '该任务走模型服务通道，不一定绑定固定执行节点。'
            : '需检查节点健康、标签、并发和路由规则。'),
      theme: primaryTheme,
    },
    {
      title: '结果入库',
      result: outputStep
        ? businessRunStepStatusLabel(outputStep.status)
        : hasOutput
          ? hasOssOutput
            ? '结果已入库'
            : '有结果，未确认自有链接'
          : finished
            ? '完成但无结果'
            : '等待结果',
      detail: `图 ${imageCount} · 视频 ${videoCount} · 文字 ${textCount} · 结构化 ${structuredCount} · 资源 ${resourceCount}`,
      hint: outputStep?.error || businessRunStepDurationLabel(outputStep) || (hasOutput
        ? hasOssOutput
          ? '业务侧可直接取结果。'
          : '有输出但未确认 OSS 入库，需防止外链过期。'
        : finished
          ? '完成状态没有结果，优先查输出解析和 OSS 入库。'
          : '未完成任务先看执行节点和队列状态。'),
      theme: outputStep
        ? businessRunStepTheme(outputStep.status)
        : hasOutput
          ? hasOssOutput
            ? 'success'
            : 'warning'
          : finished
            ? 'danger'
            : active
              ? 'warning'
              : 'default',
    },
    {
      title: '回调/计费',
      result: `${callbackStageResult} · ${billingStageResult}`,
      detail: callbackHttpStatus ? `HTTP ${callbackHttpStatus} · ${businessWalletSummary(settlement)}` : businessWalletSummary(settlement),
      hint: billingFailed
        ? settlement?.error || '先修复套餐或钱包扣减，再重试计费。'
        : callbackFailed
          ? '先重试回调；若仍失败，检查业务方地址和签名。'
          : billingUnpriced
            ? '先补模型成本或业务价格规则，否则无法进入收费闭环。'
            : billingPending
              ? '任务完成后会继续确认计费；如长期停留，检查业务结算日志。'
            : billingNoCharge
              ? businessBillingReasonLabel(detail) || '该业务按规则不收费。'
              : settlement?.traceId
                ? `流水：${formatShortBusinessId(settlement.traceId)}`
                : '未产生套餐或钱包流水。',
      theme: callbackBillingTheme,
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
  const priorityStage = businessRunPriorityStage(detail);
  return (
    <Card
      bordered
      title={
        <Space align="center" style={{ justifyContent: 'space-between', width: '100%', flexWrap: 'wrap' }}>
          <Typography.Text strong>runId 七阶段流程</Typography.Text>
          {priorityStage ? (
            <Tag variant="light" theme={priorityStage.theme as any}>
              当前关注：{priorityStage.title}
            </Tag>
          ) : null}
        </Space>
      }
    >
      <Space direction="vertical" size="small" style={{ width: '100%' }}>
        <Typography.Text theme="secondary">
          提交入口、版本命中、输入预处理、路由/分流、主执行、结果入库、回调/计费。
        </Typography.Text>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
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
                minHeight: 150,
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

function BusinessRunTraceTreeCard({ detail }: { detail: BusinessRun }) {
  const trace = detail.traceSummary;
  const nodes = trace?.nodes || [];
  if (nodes.length === 0) return null;
  return (
    <Card
      bordered
      title={
        <Space align="center" style={{ justifyContent: 'space-between', width: '100%', flexWrap: 'wrap' }}>
          <div>
            <Typography.Text strong>业务父子链路</Typography.Text>
            <div>
              <Typography.Text theme="secondary">
                一次业务调用只看一个 runId；VL、生图、结果回填、回调和计费都挂在这条主线下。
              </Typography.Text>
            </div>
          </div>
          <Space size={6} breakLine>
            {trace?.failedNodeId ? <Tag theme="danger" variant="light">卡点 {formatShortBusinessId(trace.failedNodeId)}</Tag> : null}
            {trace?.activeNodeId ? <Tag theme="warning" variant="light">当前 {formatShortBusinessId(trace.activeNodeId)}</Tag> : null}
          </Space>
        </Space>
      }
    >
      <Space direction="vertical" size="small" style={{ width: '100%' }}>
        {trace?.summary || trace?.nextAction ? (
          <Alert
            theme={trace.failedNodeId ? 'error' : trace.activeNodeId ? 'warning' : 'success'}
            message={[trace.summary, trace.nextAction].filter(Boolean).join('。')}
          />
        ) : null}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))', gap: 10 }}>
          {nodes.map((node, index) => {
            const theme = businessRunStepTheme(node.status);
            const evidence = asJsonRecord(node.evidence);
            return (
              <div
                key={node.id}
                style={{
                  border: '1px solid var(--td-border-level-1-color)',
                  borderTop: `3px solid ${businessFlowStageColor(theme)}`,
                  borderRadius: 12,
                  padding: 12,
                  background: 'var(--td-bg-color-container)',
                  minHeight: 132,
                }}
              >
                <Space direction="vertical" size={6} style={{ width: '100%' }}>
                  <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
                    <Typography.Text strong>{node.label || `节点 ${index + 1}`}</Typography.Text>
                    <Tag theme={theme as any} variant="light">{node.statusLabel || node.status || '未知'}</Tag>
                  </Space>
                  <Typography.Text theme="secondary">{node.type}</Typography.Text>
                  {node.parentId ? (
                    <Typography.Text theme="secondary">上级：{formatShortBusinessId(node.parentId)}</Typography.Text>
                  ) : (
                    <Typography.Text theme="secondary">主线入口</Typography.Text>
                  )}
                  {recordText(evidence, 'abilityId') ? (
                    <Typography.Text code>{formatShortBusinessId(recordText(evidence, 'abilityId'))}</Typography.Text>
                  ) : null}
                  {recordText(evidence, 'executorName') ? (
                    <Typography.Text theme="secondary">{recordText(evidence, 'executorName')}</Typography.Text>
                  ) : null}
                  {recordText(evidence, 'error') ? (
                    <Typography.Text theme="error">{recordText(evidence, 'error')}</Typography.Text>
                  ) : null}
                </Space>
              </div>
            );
          })}
        </div>
      </Space>
    </Card>
  );
}

const countBusinessRunSteps = (steps?: BusinessRunStep[] | null) => {
  const stats = {
    total: 0,
    succeeded: 0,
    running: 0,
    failed: 0,
    planned: 0,
    skipped: 0,
  };
  for (const step of steps || []) {
    stats.total += 1;
    const status = String(step.status || '').toLowerCase();
    if (status === 'succeeded' || status === 'success' || status === 'completed') {
      stats.succeeded += 1;
    } else if (status === 'failed' || status === 'error' || status === 'timeout' || status === 'cancelled') {
      stats.failed += 1;
    } else if (status === 'running' || status === 'queued' || status === 'pending') {
      stats.running += 1;
    } else if (status === 'planned') {
      stats.planned += 1;
    } else if (status === 'skipped') {
      stats.skipped += 1;
    }
  }
  return stats;
};

const businessRunStepCountLabel = (steps?: BusinessRunStep[] | null) => {
  const stats = countBusinessRunSteps(steps);
  if (stats.total === 0) return '暂无处理步骤';
  return `共 ${stats.total} 步 · 成功 ${stats.succeeded} · 进行中 ${stats.running} · 失败 ${stats.failed}`;
};

const businessApiEndpointKindLabel = (value?: string | null) => {
  const normalized = String(value || '').trim();
  if (normalized === 'submit') return '提交任务';
  if (normalized === 'poll') return '查询结果';
  if (normalized === 'callback') return '回调';
  if (normalized === 'route_preview') return '路由预览';
  return normalized || '其他';
};

const businessApiUsageIssueTheme = (code?: string | null, needsAttention?: boolean | null): 'success' | 'warning' | 'danger' | 'default' => {
  if (code === 'OK') return 'success';
  if (code === 'HAS_ERROR') return 'danger';
  if (needsAttention) return 'warning';
  return 'default';
};

const businessApiStatusTheme = (statusCode?: number | null): 'success' | 'warning' | 'danger' | 'default' => {
  if (typeof statusCode !== 'number') return 'default';
  if (statusCode >= 500) return 'danger';
  if (statusCode >= 400) return 'warning';
  if (statusCode >= 200 && statusCode < 400) return 'success';
  return 'default';
};

const businessApiUsageSummary = (row?: BusinessRun | null) => row?.apiUsage?.summary || {};

const businessRunApiUsageTotal = (row?: BusinessRun | null) => Number(businessApiUsageSummary(row).total || 0);

const businessRunApiUsageTheme = (row?: BusinessRun | null): 'success' | 'warning' | 'danger' | 'default' => {
  const summary = businessApiUsageSummary(row);
  if (Number(summary.errorCount || 0) > 0 || summary.issueCode === 'HAS_ERROR') return 'danger';
  if (businessRunApiUsageTotal(row) <= 0 && businessRunIsInternalOrEvalSource(row)) return 'default';
  if (summary.needsAttention || businessRunApiUsageTotal(row) <= 0) return 'warning';
  return 'success';
};

const businessRunApiUsageLabel = (row?: BusinessRun | null) => {
  const summary = businessApiUsageSummary(row);
  const total = Number(summary.total || 0);
  if (total <= 0) return businessRunIsInternalOrEvalSource(row) ? '内部/测评提交' : '未记录入口调用';
  return [
    `入口 ${total}`,
    Number(summary.submitCount || 0) > 0 ? `提交 ${Number(summary.submitCount || 0)}` : '',
    Number(summary.pollCount || 0) > 0 ? `查询 ${Number(summary.pollCount || 0)}` : '',
    Number(summary.callbackCount || 0) > 0 ? `回调 ${Number(summary.callbackCount || 0)}` : '',
    Number(summary.errorCount || 0) > 0 ? `失败 ${Number(summary.errorCount || 0)}` : '',
  ]
    .filter(Boolean)
    .join(' · ');
};

const businessRunApiUsageHint = (row?: BusinessRun | null) => {
  const summary = businessApiUsageSummary(row);
  if (summary.issueHint) return summary.issueHint;
  if (businessRunApiUsageTotal(row) <= 0 && businessRunIsInternalOrEvalSource(row)) return '内部巡检或测评端创建，通常没有外部入口调用日志。';
  if (businessRunApiUsageTotal(row) <= 0) return '未匹配到业务入口日志，可能是旧数据、后台补录或入口未打点。';
  if (Number(summary.errorCount || 0) > 0) return '入口或查询接口存在失败，打开详情确认具体接口和状态码。';
  return '业务入口和查询记录已关联到本次 runId。';
};

const businessInvocationCenterStats = (runs: BusinessRun[], total: number) => {
  const loaded = runs.length;
  const active = runs.filter((row) => businessRunIsActive(row.status)).length;
  const failed = runs.filter((row) => businessRunIsFailed(row.status) || row.error || row.errorMessage).length;
  const callbackFailed = runs.filter((row) => row.callbackStatus === 'failed').length;
  const apiLogged = runs.filter((row) => businessRunApiUsageTotal(row) > 0).length;
  const apiMissing = runs.filter((row) => businessRunApiUsageTotal(row) <= 0).length;
  const apiNeedsAttention = runs.filter((row) => {
    const summary = businessApiUsageSummary(row);
    return Boolean(summary.needsAttention) || Number(summary.errorCount || 0) > 0;
  }).length;
  const issueTheme: 'success' | 'warning' | 'danger' =
    failed > 0 || apiNeedsAttention > 0 ? 'danger' : callbackFailed > 0 || apiMissing > 0 ? 'warning' : 'success';
  const issueText =
    failed > 0
      ? `有 ${failed} 条失败，先按 runId 下钻`
      : apiNeedsAttention > 0
        ? `有 ${apiNeedsAttention} 条接口证据需处理`
        : callbackFailed > 0
          ? `有 ${callbackFailed} 条回调失败`
          : apiMissing > 0
            ? `有 ${apiMissing} 条未匹配入口日志`
            : '当前筛选内未发现明显阻塞';
  return { loaded, total, active, failed, callbackFailed, apiLogged, apiMissing, apiNeedsAttention, issueTheme, issueText };
};

function BusinessInvocationCenterSummary({ runs, total }: { runs: BusinessRun[]; total: number }) {
  const stats = businessInvocationCenterStats(runs, total);
  return (
    <div className="podi-business-invocation-center">
      <div className="podi-business-invocation-center__head">
        <div>
          <Typography.Text strong>接口调用中心</Typography.Text>
          <div>
            <Typography.Text theme="secondary">
              业务方反馈问题时，先用 runId 在这里确认入口、版本、状态、接口证据和当前卡点。
            </Typography.Text>
          </div>
        </div>
        <Tag variant="light" theme={stats.issueTheme}>
          {stats.issueText}
        </Tag>
      </div>
      <div className="podi-business-invocation-center__grid">
        <div>
          <span>当前筛选</span>
          <strong>
            {stats.loaded}/{stats.total}
          </strong>
          <small>已加载 / 总数</small>
        </div>
        <div>
          <span>排队或执行</span>
          <strong>{stats.active}</strong>
          <small>需要继续观察</small>
        </div>
        <div>
          <span>失败或异常</span>
          <strong>{stats.failed}</strong>
          <small>先打开详情定位步骤</small>
        </div>
        <div>
          <span>入口证据</span>
          <strong>
            {stats.apiLogged}/{stats.loaded || 0}
          </strong>
          <small>能证明业务接口已打入</small>
        </div>
        <div>
          <span>回调异常</span>
          <strong>{stats.callbackFailed}</strong>
          <small>失败时优先重试或查业务方地址</small>
        </div>
      </div>
      <div className="podi-business-invocation-center__contract">
        <Tag variant="light">状态口径</Tag>
        <Typography.Text theme="secondary">
          queued=排队，running=处理中，succeeded=成功，failed/timeout/cancelled=失败或终止；一次业务调用只认一个 runId。
        </Typography.Text>
      </div>
    </div>
  );
}

function BusinessRunParentTaskCard({
  detail,
  formatDateTime,
}: {
  detail: BusinessRun;
  formatDateTime: (value?: string | null) => string;
}) {
  const stepStats = countBusinessRunSteps(detail.steps);
  const outputLabel = businessRunOutputLabel(detail);
  const walletSettlement = getBusinessWalletSettlement(detail);
  const routeLabel = businessRunRouteLabel(detail.routeInfo);
  const issueTheme = detail.issueSeverity === 'danger' ? 'danger' : detail.issueSeverity === 'warning' ? 'warning' : 'success';
  return (
    <Card
      bordered
      title={
        <Space align="center" style={{ justifyContent: 'space-between', width: '100%', flexWrap: 'wrap' }}>
          <div>
            <Typography.Text strong>这次业务调用</Typography.Text>
            <div>
              <Typography.Text theme="secondary">
                先看入口、版本、状态和结果；图片分析、生图、评分和回填在下方作为处理步骤展示。
              </Typography.Text>
            </div>
          </div>
          <Tag variant="light" theme={issueTheme as any}>
            {businessIssueLabel(detail.issueCategory, detail.issueLabel)}
          </Tag>
        </Space>
      }
    >
      <Row gutter={[12, 12]}>
        <Col span={6}>
          <Typography.Text theme="secondary">runId</Typography.Text>
          <Typography.Text code>{detail.runId || detail.id}</Typography.Text>
        </Col>
        <Col span={6}>
          <Typography.Text theme="secondary">入口</Typography.Text>
          <Typography.Text>
            {businessSourceLabel(detail.source)} · {detail.channel || '未标记渠道'}
          </Typography.Text>
        </Col>
        <Col span={6}>
          <Typography.Text theme="secondary">业务版本</Typography.Text>
          <Typography.Text>
            {businessKeyLabel(detail.businessKey)} · {detail.version || '未记录版本'} · {routeLabel}
          </Typography.Text>
        </Col>
        <Col span={6}>
          <Typography.Text theme="secondary">当前状态</Typography.Text>
          <StatusBadge status={detail.status} />
        </Col>
        <Col span={6}>
          <Typography.Text theme="secondary">处理步骤</Typography.Text>
          <Space size={4} breakLine>
            <Tag variant="light">总计 {stepStats.total}</Tag>
            <Tag variant="light" theme="success">成功 {stepStats.succeeded}</Tag>
            <Tag variant="light" theme={stepStats.running > 0 ? 'warning' : 'default'}>
              进行中 {stepStats.running}
            </Tag>
            <Tag variant="light" theme={stepStats.failed > 0 ? 'danger' : 'default'}>
              失败 {stepStats.failed}
            </Tag>
          </Space>
        </Col>
        <Col span={6}>
          <Typography.Text theme="secondary">结果</Typography.Text>
          <Typography.Text>{outputLabel}</Typography.Text>
        </Col>
        <Col span={6}>
          <Typography.Text theme="secondary">回调</Typography.Text>
          <Typography.Text>
            {businessCallbackStatusLabel(detail.callbackStatus)}
            {detail.callbackHttpStatus ? ` · HTTP ${detail.callbackHttpStatus}` : ''}
          </Typography.Text>
        </Col>
        <Col span={6}>
          <Typography.Text theme="secondary">计费</Typography.Text>
          <Typography.Text>
            {businessBillingStatusLabel(detail.billingStatus)} · {businessWalletStatusLabel(walletSettlement)}
          </Typography.Text>
        </Col>
        <Col span={6}>
          <Typography.Text theme="secondary">创建 / 完成</Typography.Text>
          <Typography.Text>
            {formatDateTime(detail.createdAt)} / {formatDateTime(detail.finishedAt)}
          </Typography.Text>
        </Col>
        <Col span={6}>
          <Typography.Text theme="secondary">业务方 / 客户端</Typography.Text>
          <Typography.Text>
            {detail.tenantId || '—'} · {detail.clientId || '—'}
          </Typography.Text>
        </Col>
        <Col span={6}>
          <Typography.Text theme="secondary">请求追踪</Typography.Text>
          <Typography.Text>{formatShortBusinessId(detail.traceId || detail.requestId)}</Typography.Text>
        </Col>
        <Col span={6}>
          <Typography.Text theme="secondary">底层排障编号</Typography.Text>
          <Typography.Text>{formatShortBusinessId(detail.taskId || detail.abilityTaskId)}</Typography.Text>
        </Col>
      </Row>
    </Card>
  );
}

function BusinessRunApiUsageEvidenceCard({
  detail,
  formatDateTime,
}: {
  detail: BusinessRun;
  formatDateTime: (value?: string | null) => string;
}) {
  const apiUsage = detail.apiUsage;
  const summary = apiUsage?.summary || {};
  const items = Array.isArray(apiUsage?.items) ? apiUsage.items : [];
  const total = Number(summary.total || 0);
  const issueCode = summary.issueCode || (total > 0 ? 'OK' : 'NO_ENTRY_LOG');
  const issueTheme = total <= 0 && businessRunIsInternalOrEvalSource(detail) ? 'default' : businessApiUsageIssueTheme(issueCode, summary.needsAttention);
  return (
    <Card bordered title="入口调用证据">
      <Space direction="vertical" size="small" style={{ width: '100%' }}>
        <Alert
          theme={issueTheme === 'danger' ? 'error' : issueTheme === 'warning' ? 'warning' : 'info'}
          message={
            summary.issueHint ||
            (total <= 0 && businessRunIsInternalOrEvalSource(detail)
              ? '这是内部巡检或测评端创建的任务，通常没有外部入口调用日志；排障时继续看版本、能力和结果链路。'
              : '没有找到入口调用记录；如果这是旧数据或后台补录任务，可继续看下方处理步骤。')
          }
        />
        <Row gutter={[12, 12]}>
          <Col span={4}>
            <Typography.Text theme="secondary">调用记录</Typography.Text>
            <Typography.Text>{total}</Typography.Text>
          </Col>
          <Col span={4}>
            <Typography.Text theme="secondary">提交</Typography.Text>
            <Typography.Text>{Number(summary.submitCount || 0)}</Typography.Text>
          </Col>
          <Col span={4}>
            <Typography.Text theme="secondary">查询</Typography.Text>
            <Typography.Text>{Number(summary.pollCount || 0)}</Typography.Text>
          </Col>
          <Col span={4}>
            <Typography.Text theme="secondary">失败</Typography.Text>
            <Tag variant="light" theme={Number(summary.errorCount || 0) > 0 ? 'danger' : 'success'}>
              {Number(summary.errorCount || 0)}
            </Tag>
          </Col>
          <Col span={4}>
            <Typography.Text theme="secondary">最近调用</Typography.Text>
            <Typography.Text>{formatDateTime(summary.lastSeenAt)}</Typography.Text>
          </Col>
          <Col span={4}>
            <Typography.Text theme="secondary">匹配方式</Typography.Text>
            <Typography.Text>{(apiUsage?.matchBy || []).join(' / ') || 'runId'}</Typography.Text>
          </Col>
        </Row>
        {items.length > 0 ? (
          <Table
            size="small"
            rowKey="id"
            data={items.slice(0, 8)}
            columns={[
              {
                colKey: 'createdAt',
                title: '时间',
                width: 170,
                cell: ({ row }) => <Typography.Text>{formatDateTime(row.createdAt)}</Typography.Text>,
              },
              {
                colKey: 'endpointKind',
                title: '动作',
                width: 110,
                cell: ({ row }) => <Tag variant="light">{businessApiEndpointKindLabel(row.endpointKind)}</Tag>,
              },
              {
                colKey: 'path',
                title: '接口',
                ellipsis: true,
                cell: ({ row }) => (
                  <Space direction="vertical" size={2}>
                    <Typography.Text code>
                      {row.method || 'GET'} {row.path || '—'}
                    </Typography.Text>
                    <Typography.Text theme="secondary">
                      {row.apiKeyName || '未记录 Key'}{row.apiKeyPreview ? ` · ${row.apiKeyPreview}` : ''}
                    </Typography.Text>
                  </Space>
                ),
              },
              {
                colKey: 'statusCode',
                title: '结果',
                width: 150,
                cell: ({ row }) => (
                  <Space direction="vertical" size={2}>
                    <Tag variant="light" theme={businessApiStatusTheme(row.statusCode)}>
                      HTTP {row.statusCode || '—'}
                    </Tag>
                    {row.errorCode ? <Typography.Text theme="error">{row.errorCode}</Typography.Text> : null}
                  </Space>
                ),
              },
              {
                colKey: 'durationMs',
                title: '耗时',
                width: 100,
                cell: ({ row }) => <Typography.Text>{formatDurationMs(row.durationMs)}</Typography.Text>,
              },
            ]}
          />
        ) : (
          <Typography.Text theme="secondary">
            暂无入口调用明细。若本任务由后台补录、复测或旧版本迁移产生，可以继续按下方处理步骤排查。
          </Typography.Text>
        )}
      </Space>
    </Card>
  );
}

const businessAgentStatusLabel = (value?: string | null) => {
  if (value === 'collecting_context') return '收集上下文';
  if (value === 'awaiting_confirmation') return '等待用户补充';
  if (value === 'confirming') return '确认中';
  if (value === 'running') return '已提交执行';
  if (value === 'executed') return '已执行';
  if (value === 'failed') return '失败';
  if (value === 'submitted') return '已提交';
  if (value === 'queued') return '已排队';
  return value || '未记录';
};

const businessAgentStatusTheme = (value?: string | null): 'success' | 'warning' | 'danger' | 'default' => {
  if (value === 'running' || value === 'executed' || value === 'submitted') return 'success';
  if (value === 'awaiting_confirmation' || value === 'confirming' || value === 'queued') return 'warning';
  if (value === 'failed') return 'danger';
  return 'default';
};

function BusinessRunAgentTraceCard({
  detail,
  formatDateTime,
}: {
  detail: BusinessRun;
  formatDateTime: (value?: string | null) => string;
}) {
  const trace = detail.agentTrace;
  if (!trace?.sessionId && !trace?.planId && !trace?.toolCallId) return null;
  const warnings = Array.isArray(trace.warnings) ? trace.warnings.filter(Boolean) : [];
  return (
    <Card bordered title="Agent 来源证据">
      <Space direction="vertical" size="small" style={{ width: '100%' }}>
        <Alert
          theme={trace.toolCallStatus === 'failed' || trace.planStatus === 'failed' ? 'warning' : 'info'}
          message={
            trace.planSummary ||
            '这条业务 run 由对话式 Agent 确认后创建；排障时先看方案和工具调用，再看下方业务执行步骤。'
          }
        />
        <Row gutter={[12, 12]}>
          <Col span={6}>
            <Typography.Text theme="secondary">Agent 会话</Typography.Text>
            <Space direction="vertical" size={2}>
              <Typography.Text code>{formatShortBusinessId(trace.sessionId)}</Typography.Text>
              <Tag variant="light" theme={businessAgentStatusTheme(trace.sessionStatus)}>
                {businessAgentStatusLabel(trace.sessionStatus)}
              </Tag>
            </Space>
          </Col>
          <Col span={6}>
            <Typography.Text theme="secondary">方案</Typography.Text>
            <Space direction="vertical" size={2}>
              <Typography.Text>{trace.planTitle || '未记录方案标题'}</Typography.Text>
              <Space size={4} breakLine>
                <Tag variant="light" theme={businessAgentStatusTheme(trace.planStatus)}>
                  {businessAgentStatusLabel(trace.planStatus)}
                </Tag>
                {trace.riskLevel ? <Tag variant="light">风险 {trace.riskLevel}</Tag> : null}
                {trace.estimatedCostLevel ? <Tag variant="light">成本 {trace.estimatedCostLevel}</Tag> : null}
              </Space>
            </Space>
          </Col>
          <Col span={6}>
            <Typography.Text theme="secondary">工具调用</Typography.Text>
            <Space direction="vertical" size={2}>
              <Typography.Text>{trace.toolName || 'business.image_edit'}</Typography.Text>
              <Tag variant="light" theme={businessAgentStatusTheme(trace.toolCallStatus)}>
                {businessAgentStatusLabel(trace.toolCallStatus)}
              </Tag>
            </Space>
          </Col>
          <Col span={6}>
            <Typography.Text theme="secondary">Planner</Typography.Text>
            <Typography.Text>
              {trace.plannerMode || '未记录'} · {trace.plannerModel || '—'}
            </Typography.Text>
          </Col>
          <Col span={6}>
            <Typography.Text theme="secondary">参数</Typography.Text>
            <Typography.Text>
              {trace.editSkill || '图编辑'} · {trace.quality || 'auto'} · {trace.size || 'auto'} · {trace.outputFormat || 'png'}
            </Typography.Text>
          </Col>
          <Col span={6}>
            <Typography.Text theme="secondary">入口</Typography.Text>
            <Typography.Text>
              {businessSourceLabel(trace.entrySource || detail.source)} · {trace.channel || detail.channel || '未标记渠道'}
            </Typography.Text>
          </Col>
          <Col span={6}>
            <Typography.Text theme="secondary">确认 / 执行</Typography.Text>
            <Typography.Text>
              {formatDateTime(trace.confirmedAt)} / {formatDateTime(trace.executedAt)}
            </Typography.Text>
          </Col>
          <Col span={6}>
            <Typography.Text theme="secondary">请求追踪</Typography.Text>
            <Typography.Text>{formatShortBusinessId(trace.traceId || trace.requestId)}</Typography.Text>
          </Col>
          {trace.instruction ? (
            <Col span={24}>
              <Typography.Text theme="secondary">执行指令</Typography.Text>
              <Typography.Paragraph ellipsis={{ row: 2, expandable: true, collapsible: true }}>
                {trace.instruction}
              </Typography.Paragraph>
            </Col>
          ) : null}
          {warnings.length > 0 ? (
            <Col span={24}>
              <Typography.Text theme="secondary">方案提醒</Typography.Text>
              <Space breakLine size={4}>
                {warnings.map((item, index) => (
                  <Tag key={`${item}-${index}`} variant="light" theme="warning">
                    {item}
                  </Tag>
                ))}
              </Space>
            </Col>
          ) : null}
        </Row>
      </Space>
    </Card>
  );
}

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
        const executorLabel =
          executor ||
          (businessRunUsesVendorModelChannel({ abilityProvider: step.abilityProvider })
            ? '第三方模型通道'
            : '未记录执行节点');
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
                <Typography.Text theme="secondary">{executorLabel}</Typography.Text>
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
    <details className="podi-business-run-ops">
      <summary>
        <span>排障与批量操作</span>
        <Tag theme={retestableRuns.length > 0 ? 'warning' : 'success'} variant="light" size="small">
          {retestableRuns.length > 0 ? `待复测 ${retestableRuns.length}` : '当前页暂无待复测'}
        </Tag>
        <Typography.Text theme="secondary">
          仅作用于当前已加载记录，需要时展开。
        </Typography.Text>
      </summary>
      <Row gutter={[12, 12]} style={{ marginTop: 10 }}>
        <Col xs={12} lg={4}>
          <Card bordered size="small">
            <Space direction="vertical" size="small">
              <Typography.Text strong>当前已加载问题</Typography.Text>
              <Typography.Text>
                问题 {issueRuns.length} · 失败 {failedRuns.length} · 回调失败 {callbackFailedRuns.length} · 已恢复 {recoveredRuns.length}
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
        <Col xs={12} lg={5}>
          <Card bordered size="small">
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
        <Col xs={12} lg={3}>
          <Alert
            theme={retestableRuns.length > 0 ? 'warning' : 'info'}
            message={
              retestableRuns.length > 0
                ? '建议先生成排障清单留证，再批量复测。'
                : '发版前仍需按核心能力分别跑真实链路。'
            }
          />
        </Col>
      </Row>
    </details>
  );
}

type BusinessOutputReviewUpsertItem = {
  outputIndex: number;
  outputUrl?: string | null;
  qualityGrade: string;
  inputTags?: string[];
  issueTags?: string[];
  nextAction?: string | null;
  note?: string | null;
};

type BusinessRunVisualOutput = {
  outputIndex: number;
  outputUrl: string;
  kind: 'image' | 'video' | 'resource';
};

export type BusinessOutputReviewFocus = {
  runId: string;
  outputIndex: number;
};

type BusinessOutputReviewDraft = {
  qualityGrade: string;
  inputTagsText: string;
  issueTagsText: string;
  nextAction: string;
  note: string;
};

const businessOutputReviewGradeOptions = [
  { label: '待评', value: 'pending' },
  { label: '优秀', value: 'excellent' },
  { label: '可用', value: 'usable' },
  { label: '勉强', value: 'borderline' },
  { label: '差图', value: 'bad' },
  { label: '阻断', value: 'blocked' },
];

const businessOutputReviewActionOptions = [
  { label: '采纳', value: 'accept' },
  { label: '调参', value: 'tune_params' },
  { label: '分流', value: 'route_split' },
  { label: '换 LoRA', value: 'switch_lora' },
  { label: '人工复核', value: 'manual_review' },
  { label: '暂停推荐', value: 'pause_recommendation' },
];

const businessOutputReviewGradeLabel = (value?: string | null) =>
  businessOutputReviewGradeOptions.find((option) => option.value === value)?.label || '待评';

const businessOutputReviewGradeTheme = (value?: string | null) => {
  if (value === 'excellent' || value === 'usable') return 'success';
  if (value === 'borderline' || value === 'pending') return 'warning';
  if (value === 'bad' || value === 'blocked') return 'danger';
  return 'default';
};

const businessOutputReviewActionLabel = (value?: string | null) =>
  businessOutputReviewActionOptions.find((option) => option.value === value)?.label || '人工复核';

type BusinessRunQualitySignal = {
  theme: 'success' | 'warning' | 'danger' | 'default';
  title: string;
  detail: string;
  nextAction?: string;
  reviewCount: number;
  goodCount: number;
  riskCount: number;
  pendingCount: number;
  tags: string[];
};

const buildBusinessRunQualitySignal = (
  detail: BusinessRun,
  reviews?: BusinessOutputReview[] | null,
  loading?: boolean,
): BusinessRunQualitySignal => {
  const outputs = buildBusinessRunVisualOutputs(detail);
  const items = reviews || [];
  const reviewCount = items.length;
  const goodCount = items.filter((item) => ['excellent', 'usable'].includes(String(item.qualityGrade || ''))).length;
  const riskCount = items.filter((item) => ['borderline', 'bad', 'blocked'].includes(String(item.qualityGrade || ''))).length;
  const pendingCount = items.filter((item) => !item.qualityGrade || item.qualityGrade === 'pending').length;
  const tags = Array.from(
    new Set(items.flatMap((item) => [...(item.inputTags || []), ...(item.issueTags || [])].map((tag) => String(tag || '').trim()).filter(Boolean))),
  ).slice(0, 5);
  const action = items.find((item) => item.nextAction && item.nextAction !== 'accept')?.nextAction || items.find((item) => item.nextAction)?.nextAction;
  if (loading) {
    return {
      theme: 'default',
      title: '质量证据加载中',
      detail: '正在读取本次输出的质量标注。',
      reviewCount,
      goodCount,
      riskCount,
      pendingCount,
      tags,
    };
  }
  if (outputs.length === 0) {
    return {
      theme: businessRunIsFinished(detail.status) ? 'danger' : 'warning',
      title: businessRunIsFinished(detail.status) ? '完成但无输出' : '等待输出',
      detail: businessRunIsFinished(detail.status) ? '先查主执行、结果解析和 OSS 入库。' : '任务未完成前先看执行阶段和队列。',
      reviewCount,
      goodCount,
      riskCount,
      pendingCount,
      tags,
    };
  }
  if (reviewCount === 0) {
    return {
      theme: 'warning',
      title: '待质量标注',
      detail: `已回收 ${outputs.length} 个输出，但还没有质量结论。`,
      nextAction: 'manual_review',
      reviewCount,
      goodCount,
      riskCount,
      pendingCount,
      tags,
    };
  }
  if (riskCount > 0) {
    return {
      theme: 'danger',
      title: `质量风险 ${riskCount}`,
      detail: `已标注 ${reviewCount}，可用 ${goodCount}，待评 ${pendingCount}。`,
      nextAction: action || 'manual_review',
      reviewCount,
      goodCount,
      riskCount,
      pendingCount,
      tags,
    };
  }
  if (goodCount > 0 && pendingCount === 0) {
    return {
      theme: 'success',
      title: '质量可用',
      detail: `已标注 ${reviewCount}，可用 ${goodCount}。`,
      nextAction: action || 'accept',
      reviewCount,
      goodCount,
      riskCount,
      pendingCount,
      tags,
    };
  }
  return {
    theme: 'warning',
    title: '质量未定',
    detail: `已标注 ${reviewCount}，仍有 ${pendingCount} 个输出待评。`,
    nextAction: action || 'manual_review',
    reviewCount,
    goodCount,
    riskCount,
    pendingCount,
    tags,
  };
};

const buildBusinessRunGovernanceSignal = (detail: BusinessRun, quality: BusinessRunQualitySignal, stage?: BusinessRunFlowStage) => {
  if (detail.issueAction) {
    return {
      theme: detail.issueSeverity === 'danger' ? 'danger' : 'warning',
      title: '按链路问题处理',
      detail: detail.issueAction,
    };
  }
  if (quality.riskCount > 0) {
    return {
      theme: 'warning',
      title: quality.nextAction ? businessOutputReviewActionLabel(quality.nextAction) : '沉淀治理项',
      detail: '把问题标签、输入标签和样例 batchId 记录到治理台账，再复跑候选版本验证。',
    };
  }
  if (quality.reviewCount === 0 && buildBusinessRunVisualOutputs(detail).length > 0) {
    return {
      theme: 'warning',
      title: '补质量标注',
      detail: '先标出质量档位、输入标签和问题标签，再决定是否分流或切默认。',
    };
  }
  if (stage?.theme === 'danger') {
    return {
      theme: 'danger',
      title: `处理 ${stage.title}`,
      detail: stage.hint || stage.detail || '按当前卡点排查链路证据。',
    };
  }
  if (businessRunIsActive(detail.status)) {
    return {
      theme: 'warning',
      title: '继续观察',
      detail: '任务仍在排队或执行中，超过正常耗时后再进入排障。',
    };
  }
  if (quality.goodCount > 0 && quality.riskCount === 0) {
    return {
      theme: 'success',
      title: '可进入样例复盘',
      detail: '本次输出可作为候选版本或固定样例批次的正向证据。',
    };
  }
  return {
    theme: stage?.theme || 'default',
    title: '保持记录',
    detail: stage?.hint || '当前没有明确治理动作，保留 runId 作为后续对照样本。',
  };
};

function BusinessRunFlowMonitorBrief({
  detail,
  reviews,
  reviewsLoading,
  formatDateTime,
}: {
  detail: BusinessRun;
  reviews?: BusinessOutputReview[];
  reviewsLoading?: boolean;
  formatDateTime: (value?: string | null) => string;
}) {
  const stages = buildBusinessRunFlowStages(detail);
  const priorityStage = businessRunPriorityStage(detail);
  const quality = buildBusinessRunQualitySignal(detail, reviews, reviewsLoading);
  const governance = buildBusinessRunGovernanceSignal(detail, quality, priorityStage);
  const dangerCount = stages.filter((stage) => stage.theme === 'danger').length;
  const warningCount = stages.filter((stage) => stage.theme === 'warning' || stage.theme === 'primary').length;
  const successCount = stages.filter((stage) => stage.theme === 'success').length;
  const verdictTheme =
    dangerCount > 0 || quality.theme === 'danger'
      ? 'danger'
      : warningCount > 0 || quality.theme === 'warning'
        ? 'warning'
        : 'success';
  const verdictText =
    verdictTheme === 'danger'
      ? '需要处理'
      : verdictTheme === 'warning'
        ? '需要确认'
        : businessRunIsActive(detail.status)
          ? '观察中'
          : '链路可用';
  const actionMessage = [
    priorityStage ? `${priorityStage.title}：${priorityStage.result}` : '',
    quality.title,
    governance.detail,
  ].filter(Boolean).join('。');

  return (
    <Card
      bordered
      className="podi-business-run-monitor"
      title={
        <Space align="center" style={{ justifyContent: 'space-between', width: '100%', flexWrap: 'wrap' }}>
          <div>
            <Typography.Text strong>流程监控结论</Typography.Text>
            <div>
              <Typography.Text theme="secondary">
                runId {formatShortBusinessId(detail.runId || detail.id)} · {formatDateTime(detail.createdAt)}
              </Typography.Text>
            </div>
          </div>
          <Tag variant="light" theme={verdictTheme as any}>
            {verdictText}
          </Tag>
        </Space>
      }
    >
      <Space direction="vertical" size="small" style={{ width: '100%' }}>
        <div className="podi-business-run-monitor__grid">
          <div className="podi-business-run-monitor__item" data-theme={priorityStage?.theme || 'default'}>
            <span>当前卡点</span>
            <strong>{priorityStage?.title || '暂无卡点'}</strong>
            <small>{[priorityStage?.result, priorityStage?.detail].filter(Boolean).join(' · ') || '等待更多链路证据'}</small>
          </div>
          <div className="podi-business-run-monitor__item" data-theme={quality.theme}>
            <span>质量证据</span>
            <strong>{quality.title}</strong>
            <small>{quality.detail}</small>
          </div>
          <div className="podi-business-run-monitor__item" data-theme={governance.theme}>
            <span>治理动作</span>
            <strong>{governance.title}</strong>
            <small>{governance.detail}</small>
          </div>
          <div className="podi-business-run-monitor__item" data-theme={verdictTheme}>
            <span>阶段完整度</span>
            <strong>
              {successCount}/{stages.length}
            </strong>
            <small>风险 {dangerCount} · 需复核 {warningCount}</small>
          </div>
        </div>
        <Space size={6} breakLine>
          {quality.tags.length > 0 ? (
            quality.tags.map((tag) => (
              <Tag key={tag} variant="light" size="small">
                {tag}
              </Tag>
            ))
          ) : (
            <Tag variant="light" size="small">
              暂无质量标签
            </Tag>
          )}
          {quality.nextAction ? (
            <Tag variant="light" theme={quality.theme as any} size="small">
              建议动作：{businessOutputReviewActionLabel(quality.nextAction)}
            </Tag>
          ) : null}
        </Space>
        <Alert
          theme={verdictTheme === 'danger' ? 'error' : verdictTheme === 'warning' ? 'warning' : 'success'}
          message={actionMessage || '当前没有明确阻塞，继续保留 runId 作为复盘证据。'}
        />
      </Space>
    </Card>
  );
}

const splitBusinessOutputReviewTags = (value?: string | null) =>
  String(value || '')
    .split(/[,，;；\n]/)
    .map((item) => item.trim())
    .filter(Boolean)
    .slice(0, 12);

const businessOutputReviewElementId = (runId: string, outputIndex: number) =>
  `podi-output-review-${String(runId || '').replace(/[^a-zA-Z0-9_-]/g, '_')}-${outputIndex}`;

const classifyBusinessOutputUrl = (url?: string | null): BusinessRunVisualOutput['kind'] => {
  const value = String(url || '').toLowerCase();
  if (/\.(png|jpg|jpeg|webp|gif|bmp|svg)(\?|#|$)/i.test(value)) return 'image';
  if (/\.(mp4|mov|webm|m4v|avi|mkv)(\?|#|$)/i.test(value)) return 'video';
  return 'resource';
};

const collectBusinessOutputUrls = (value: unknown, depth = 0): string[] => {
  if (depth > 3 || value === undefined || value === null) return [];
  if (typeof value === 'string') {
    const text = value.trim();
    return /^https?:\/\//i.test(text) ? [text] : [];
  }
  if (Array.isArray(value)) {
    return value.flatMap((item) => collectBusinessOutputUrls(item, depth + 1));
  }
  if (typeof value !== 'object') return [];

  const record = value as Record<string, unknown>;
  const directKeys = [
    'storedUrl',
    'stored_url',
    'ossUrl',
    'oss_url',
    'imageUrl',
    'image_url',
    'videoUrl',
    'video_url',
    'url',
    'sourceUrl',
    'source_url',
  ];
  const nestedKeys = [
    'assets',
    'images',
    'videos',
    'imageUrls',
    'image_urls',
    'videoUrls',
    'video_urls',
    'resultUrls',
    'result_urls',
    'outputs',
    'results',
    'data',
    'result',
  ];
  return [
    ...directKeys.flatMap((key) => collectBusinessOutputUrls(record[key], depth + 1)),
    ...nestedKeys.flatMap((key) => collectBusinessOutputUrls(record[key], depth + 1)),
  ];
};

const buildBusinessRunVisualOutputs = (detail: BusinessRun): BusinessRunVisualOutput[] => {
  const candidates: Array<Omit<BusinessRunVisualOutput, 'outputIndex'>> = [
    ...(detail.imageUrls || []).map((url) => ({ outputUrl: String(url || '').trim(), kind: 'image' as const })),
    ...(detail.videoUrls || []).map((url) => ({ outputUrl: String(url || '').trim(), kind: 'video' as const })),
    ...collectBusinessOutputUrls(detail.resultPayload).map((url) => ({
      outputUrl: url,
      kind: classifyBusinessOutputUrl(url),
    })),
  ];
  const seen = new Set<string>();
  return candidates
    .filter((item) => {
      if (!item.outputUrl || seen.has(item.outputUrl)) return false;
      seen.add(item.outputUrl);
      return true;
    })
    .map((item, index) => ({
      ...item,
      outputIndex: index,
    }));
};

const businessOutputReviewDraftFromReview = (review?: BusinessOutputReview | null): BusinessOutputReviewDraft => ({
  qualityGrade: review?.qualityGrade || 'pending',
  inputTagsText: (review?.inputTags || []).join(', '),
  issueTagsText: (review?.issueTags || []).join(', '),
  nextAction: review?.nextAction || 'manual_review',
  note: review?.note || '',
});

function BusinessRunOutputReviewCard({
  detail,
  reviews,
  loading,
  error,
  isReadOnly,
  actionLoadingId,
  outputReviewFocus,
  onRefreshOutputReviews,
  onSaveOutputReview,
}: {
  detail: BusinessRun;
  reviews?: BusinessOutputReview[];
  loading?: boolean;
  error?: string | null;
  isReadOnly: boolean;
  actionLoadingId?: string | null;
  outputReviewFocus?: BusinessOutputReviewFocus | null;
  onRefreshOutputReviews?: (runId: string) => void;
  onSaveOutputReview?: (runId: string, item: BusinessOutputReviewUpsertItem) => Promise<void> | void;
}) {
  const runKey = detail.runId || detail.id;
  const outputs = useMemo(() => buildBusinessRunVisualOutputs(detail), [detail]);
  const focusedOutputIndex =
    outputReviewFocus && outputReviewFocus.runId === runKey ? Number(outputReviewFocus.outputIndex || 0) : null;
  const reviewByIndex = useMemo(() => {
    const map = new Map<number, BusinessOutputReview>();
    (reviews || []).forEach((review) => map.set(Number(review.outputIndex || 0), review));
    return map;
  }, [reviews]);
  const [drafts, setDrafts] = useState<Record<number, BusinessOutputReviewDraft>>({});

  useEffect(() => {
    const next: Record<number, BusinessOutputReviewDraft> = {};
    outputs.forEach((output) => {
      next[output.outputIndex] = businessOutputReviewDraftFromReview(reviewByIndex.get(output.outputIndex));
    });
    setDrafts(next);
  }, [outputs, reviewByIndex, runKey]);

  useEffect(() => {
    if (focusedOutputIndex === null || focusedOutputIndex === undefined) return;
    window.setTimeout(() => {
      document.getElementById(businessOutputReviewElementId(runKey, focusedOutputIndex))?.scrollIntoView({
        behavior: 'smooth',
        block: 'center',
      });
    }, 80);
  }, [focusedOutputIndex, runKey]);

  const updateDraft = (outputIndex: number, patch: Partial<BusinessOutputReviewDraft>) => {
    setDrafts((prev) => ({
      ...prev,
      [outputIndex]: {
        ...(prev[outputIndex] || businessOutputReviewDraftFromReview(reviewByIndex.get(outputIndex))),
        ...patch,
      },
    }));
  };

  const saveDraft = (output: BusinessRunVisualOutput) => {
    if (!onSaveOutputReview) return;
    const draft = drafts[output.outputIndex] || businessOutputReviewDraftFromReview(reviewByIndex.get(output.outputIndex));
    void onSaveOutputReview(runKey, {
      outputIndex: output.outputIndex,
      outputUrl: output.outputUrl,
      qualityGrade: draft.qualityGrade || 'pending',
      inputTags: splitBusinessOutputReviewTags(draft.inputTagsText),
      issueTags: splitBusinessOutputReviewTags(draft.issueTagsText),
      nextAction: draft.nextAction || 'manual_review',
      note: draft.note.trim() || null,
    });
  };

  const reviewedCount = (reviews || []).filter((item) => item.qualityGrade && item.qualityGrade !== 'pending').length;

  return (
    <Card
      bordered
      title={
        <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
          <Space direction="vertical" size={2}>
            <Typography.Text strong>出图质量标注</Typography.Text>
            <Typography.Text theme="secondary">
              按单张结果记录质量、输入特征和问题标签，后续用于分流、调参和 LoRA/workflow 切换。
            </Typography.Text>
          </Space>
          <Space size="small">
            <Tag variant="light" theme={reviewedCount > 0 ? 'success' : 'warning'}>
              已评 {reviewedCount}/{outputs.length}
            </Tag>
            <Button
              size="small"
              variant="outline"
              loading={loading}
              onClick={() => onRefreshOutputReviews?.(runKey)}
            >
              刷新标注
            </Button>
          </Space>
        </Space>
      }
    >
      <Space direction="vertical" size="small" style={{ width: '100%' }}>
        {error ? <Alert theme="error" message={error} /> : null}
        {outputs.length === 0 ? (
          <Alert theme="warning" message="这条 run 还没有可标注的图片或视频结果；先确认结果回填和 OSS 落盘是否正常。" />
        ) : (
          <div className="podi-business-output-review-grid">
            {outputs.map((output) => {
              const review = reviewByIndex.get(output.outputIndex);
              const draft = drafts[output.outputIndex] || businessOutputReviewDraftFromReview(review);
              const savingKey = `output-review:${runKey}:${output.outputIndex}`;
              return (
                <div
                  id={businessOutputReviewElementId(runKey, output.outputIndex)}
                  key={`${output.outputIndex}-${output.outputUrl}`}
                  className={`podi-business-output-review-item${
                    focusedOutputIndex === output.outputIndex ? ' podi-business-output-review-item--focused' : ''
                  }`}
                >
                  <div className="podi-business-output-review-item__preview">
                    {output.kind === 'image' ? (
                      <img src={output.outputUrl} alt={`business-output-${output.outputIndex + 1}`} loading="lazy" />
                    ) : output.kind === 'video' ? (
                      <video src={output.outputUrl} controls preload="metadata" />
                    ) : (
                      <a href={output.outputUrl} target="_blank" rel="noreferrer">
                        打开资源
                      </a>
                    )}
                  </div>
                  <Space direction="vertical" size="small" style={{ width: '100%' }}>
                    <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
                      <Space size={6}>
                        <Typography.Text strong>结果 {output.outputIndex + 1}</Typography.Text>
                        <Tag variant="light">{output.kind === 'image' ? '图片' : output.kind === 'video' ? '视频' : '资源'}</Tag>
                        <Tag variant="light" theme={businessOutputReviewGradeTheme(review?.qualityGrade) as any}>
                          {businessOutputReviewGradeLabel(review?.qualityGrade)}
                        </Tag>
                      </Space>
                      {review?.updatedAt ? (
                        <Typography.Text theme="secondary">{review.reviewerUsername || '已标注'}</Typography.Text>
                      ) : null}
                    </Space>
                    <Row gutter={[8, 8]}>
                      <Col xs={12} lg={6}>
                        <Typography.Text theme="secondary">质量</Typography.Text>
                        <Select
                          value={draft.qualityGrade}
                          options={businessOutputReviewGradeOptions}
                          disabled={isReadOnly}
                          onChange={(value) => updateDraft(output.outputIndex, { qualityGrade: String(value || 'pending') })}
                        />
                      </Col>
                      <Col xs={12} lg={6}>
                        <Typography.Text theme="secondary">下一步</Typography.Text>
                        <Select
                          value={draft.nextAction}
                          options={businessOutputReviewActionOptions}
                          disabled={isReadOnly}
                          onChange={(value) => updateDraft(output.outputIndex, { nextAction: String(value || 'manual_review') })}
                        />
                      </Col>
                      <Col xs={12} lg={6}>
                        <Typography.Text theme="secondary">输入标签</Typography.Text>
                        <Input
                          value={draft.inputTagsText}
                          disabled={isReadOnly}
                          placeholder="如 商品图, 复杂花型, 横图"
                          onChange={(value) => updateDraft(output.outputIndex, { inputTagsText: String(value || '') })}
                        />
                      </Col>
                      <Col xs={12} lg={6}>
                        <Typography.Text theme="secondary">问题标签</Typography.Text>
                        <Input
                          value={draft.issueTagsText}
                          disabled={isReadOnly}
                          placeholder="如 主体变形, 边缘接缝, 色偏"
                          onChange={(value) => updateDraft(output.outputIndex, { issueTagsText: String(value || '') })}
                        />
                      </Col>
                      <Col span={12}>
                        <Typography.Text theme="secondary">备注</Typography.Text>
                        <Textarea
                          value={draft.note}
                          disabled={isReadOnly}
                          placeholder="只记录影响判断的事实，例如哪类图不稳定、是否需要换参数或 LoRA。"
                          autosize={{ minRows: 2, maxRows: 4 }}
                          onChange={(value) => updateDraft(output.outputIndex, { note: String(value || '') })}
                        />
                      </Col>
                    </Row>
                    <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
                      <Typography.Text theme="secondary">
                        {draft.nextAction ? `动作：${businessOutputReviewActionLabel(draft.nextAction)}` : '等待复核'}
                      </Typography.Text>
                      <Button
                        size="small"
                        theme="primary"
                        disabled={isReadOnly || !onSaveOutputReview}
                        loading={actionLoadingId === savingKey}
                        onClick={() => saveDraft(output)}
                      >
                        保存标注
                      </Button>
                    </Space>
                  </Space>
                </div>
              );
            })}
          </div>
        )}
      </Space>
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
  outputReviews,
  outputReviewsLoading,
  outputReviewsError,
  outputReviewFocus,
  autoRefresh,
  onFiltersChange,
  onAutoRefreshChange,
  onRefresh,
  onExport,
  onBulkCallbackRetry,
  onBulkRetest,
  onBulkIgnoreIssues,
  onGenerateIssueChecklist,
  onOpenDetail,
  onCloseDetail,
  onCallbackRetry,
  onRefreshOutputReviews,
  onSaveOutputReview,
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
  outputReviews?: BusinessOutputReview[];
  outputReviewsLoading?: boolean;
  outputReviewsError?: string | null;
  outputReviewFocus?: BusinessOutputReviewFocus | null;
  autoRefresh: boolean;
  onFiltersChange: (updater: (prev: BusinessRunFilters) => BusinessRunFilters) => void;
  onAutoRefreshChange: (value: boolean) => void;
  onRefresh: () => void;
  onExport: () => void;
  onBulkCallbackRetry: () => void;
  onBulkRetest: () => void;
  onBulkIgnoreIssues: () => void;
  onGenerateIssueChecklist: () => void;
  onOpenDetail: (row: BusinessRun) => void;
  onCloseDetail: () => void;
  onCallbackRetry: (row: BusinessRun) => void;
  onRefreshOutputReviews?: (runId: string) => void;
  onSaveOutputReview?: (runId: string, item: BusinessOutputReviewUpsertItem) => Promise<void> | void;
  formatDateTime: (value?: string | null) => string;
}) => (
  <>
    <Card
      bordered
      title={
        <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
          <div>
            <Typography.Text strong>业务调用清单</Typography.Text>
            <div>
              <Typography.Text theme="secondary">
                已加载 {runs.length} / {total} 条；一行就是一次业务调用，点详情查看图片分析、生图、评分、回填和回调。
              </Typography.Text>
            </div>
          </div>
          <Space size="small">
            <Button
              variant="outline"
              theme={autoRefresh ? 'primary' : 'default'}
              onClick={() => onAutoRefreshChange(!autoRefresh)}
            >
              {autoRefresh ? '自动刷新中' : '开启自动刷新'}
            </Button>
            <Button variant="outline" onClick={onRefresh}>
              刷新
            </Button>
          </Space>
        </Space>
      }
    >
      <BusinessInvocationCenterSummary runs={runs} total={total} />
      <Alert
        theme="info"
        message="排查顺序：先确认 runId 和入口证据，再看版本与状态；原子能力调用只作为下钻证据，不再单独当成一次业务。"
        style={{ marginBottom: 12 }}
      />
      <BusinessRunRetestControlPanel
        runs={runs}
        isReadOnly={isReadOnly}
        actionLoadingId={actionLoadingId}
        onBulkRetest={onBulkRetest}
        onBulkCallbackRetry={onBulkCallbackRetry}
        onBulkIgnoreIssues={onBulkIgnoreIssues}
        onGenerateIssueChecklist={onGenerateIssueChecklist}
      />

      <div className="podi-business-run-filters">
        <div className="podi-business-run-filters__primary">
          <Select
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
            value={filters.issueCategory}
            options={businessRunIssueCategoryOptions}
            onChange={(value) =>
              onFiltersChange((prev) => ({
                ...prev,
                issueCategory: String(value),
              }))
            }
          />
          <Select
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
          <div className="podi-business-run-filters__actions">
            <Button theme="primary" variant="outline" onClick={onRefresh}>
              应用筛选
            </Button>
            <Button variant="outline" loading={actionLoadingId === 'export:runs'} onClick={onExport}>
              导出调用记录
            </Button>
          </div>
        </div>
        <details className="podi-business-run-filters__advanced">
          <summary>展开低频筛选：来源、业务方、计费、回调、排障编号</summary>
          <div className="podi-business-run-filters__secondary">
            <Select
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
              value={filters.callbackStatus}
              options={businessRunCallbackStatusOptions}
              onChange={(value) =>
                onFiltersChange((prev) => ({
                  ...prev,
                  callbackStatus: String(value),
                }))
              }
            />
            <Input
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
          </div>
        </details>
      </div>
      <div className="podi-business-run-table-wrap">
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
            colKey: 'runId',
            title: 'runId',
            width: 230,
            ellipsis: true,
            cell: ({ row }) => (
              <Space direction="vertical" size={2}>
                <Typography.Text code>{formatShortBusinessId(row.runId || row.id)}</Typography.Text>
                {row.requestId ? (
                  <Typography.Text theme="secondary">请求：{formatShortBusinessId(row.requestId)}</Typography.Text>
                ) : null}
              </Space>
            ),
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
            colKey: 'apiUsage',
            title: '接口证据',
            width: 230,
            cell: ({ row }) => (
              <Space direction="vertical" size={2}>
                <Tag variant="light" theme={businessRunApiUsageTheme(row)}>
                  {businessRunApiUsageLabel(row)}
                </Tag>
                <Typography.Text theme="secondary">{businessRunApiUsageHint(row)}</Typography.Text>
              </Space>
            ),
          },
          {
            colKey: 'route',
            title: '生效方式',
            width: 160,
            cell: ({ row }) => <Typography.Text theme="secondary">{businessRunRouteLabel(row.routeInfo)}</Typography.Text>,
          },
          {
            colKey: 'steps',
            title: '处理进度',
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
                    <Tag variant="light">{businessRunStepCountLabel(steps)}</Tag>
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
            title: '主执行能力',
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
      </div>
    </Card>
    <Dialog
      header="业务调用详情"
      visible={detailOpen}
      width={1120}
      confirmBtn={null}
      cancelBtn="关闭"
      onClose={onCloseDetail}
      onCancel={onCloseDetail}
    >
      {detail ? (
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <BusinessRunFlowMonitorBrief
            detail={detail}
            reviews={outputReviews}
            reviewsLoading={outputReviewsLoading}
            formatDateTime={formatDateTime}
          />
          <BusinessRunParentTaskCard detail={detail} formatDateTime={formatDateTime} />
          <BusinessRunApiUsageEvidenceCard detail={detail} formatDateTime={formatDateTime} />
          <BusinessRunAgentTraceCard detail={detail} formatDateTime={formatDateTime} />
          <Row gutter={[12, 12]}>
            <Col span={6}>
              <Typography.Text theme="secondary">业务调用</Typography.Text>
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
          <BusinessRunTraceTreeCard detail={detail} />
          <BusinessRunFlowEvidenceBar detail={detail} />
          <BusinessRunOutputReviewCard
            detail={detail}
            reviews={outputReviews}
            loading={outputReviewsLoading}
            error={outputReviewsError}
            isReadOnly={isReadOnly}
            actionLoadingId={actionLoadingId}
            outputReviewFocus={outputReviewFocus}
            onRefreshOutputReviews={onRefreshOutputReviews}
            onSaveOutputReview={onSaveOutputReview}
          />
          <Card bordered title="本次业务编排">
            <Space direction="vertical" size="small" style={{ width: '100%' }}>
              <Typography.Text theme="secondary">
                一次业务调用只看一个 runId；下面按真实执行顺序展示入口、图像理解、生图/编辑、结果回填和当前卡点。
              </Typography.Text>
              <BusinessOrchestrationGraphView
                graph={detail.orchestrationGraph}
                fallbackSteps={detail.steps || []}
                showRuntime
              />
            </Space>
          </Card>
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
}) => {
  const controlLocked = Boolean(form.id && form.isDefault);
  return (
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
            onChange={(value) => {
              const nextStatus = String(value);
              onChange({ ...form, status: nextStatus, isDefault: nextStatus === 'active' ? form.isDefault : false });
            }}
            options={businessCapabilityStatusOptions}
          />
        </Col>
        <Col span={6}>
          <Typography.Text theme="secondary">是否默认</Typography.Text>
          <div style={{ paddingTop: 8 }}>
            <Switch
              value={form.isDefault}
              disabled={controlLocked || form.status !== 'active'}
              onChange={(value) => onChange({ ...form, isDefault: Boolean(value) })}
            />
          </div>
        </Col>
      </Row>
      {controlLocked ? (
        <Alert theme="warning" message="这是线上默认版本。名称和说明可微调；主能力、配方、字段、版本号等控制项请通过新草稿版本修改。" />
      ) : null}
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
      <Card bordered title="版本关系">
        <Space direction="vertical" size="small" style={{ width: '100%' }}>
          <Alert
            theme="info"
            message="默认按同一业务的版本升级处理；只有入口含义真的变化时，才标成新的业务功能。"
          />
          <Row gutter={[12, 12]}>
            <Col span={12}>
              <Typography.Text theme="secondary">归属判断</Typography.Text>
              <Select
                value={form.versionDecision}
                options={businessVersionDecisionOptions}
                onChange={(value) => onChange({ ...form, versionDecision: String(value) })}
              />
            </Col>
            <Col span={12}>
              <Typography.Text theme="secondary">是否破坏兼容</Typography.Text>
              <div style={{ paddingTop: 8 }}>
                <Switch
                  value={form.versionBreakingChange}
                  onChange={(value) => onChange({ ...form, versionBreakingChange: Boolean(value) })}
                />
              </div>
            </Col>
            <Col span={12}>
              <Typography.Text theme="secondary">来源版本 ID</Typography.Text>
              <Input
                value={form.parentVersionId}
                placeholder="从哪个版本继续迭代，可留空"
                onChange={(value) => onChange({ ...form, parentVersionId: String(value) })}
              />
            </Col>
            <Col span={12}>
              <Typography.Text theme="secondary">替代版本 ID</Typography.Text>
              <Input
                value={form.supersedesVersionId}
                placeholder="上线后主要替代哪个版本，可留空"
                onChange={(value) => onChange({ ...form, supersedesVersionId: String(value) })}
              />
            </Col>
          </Row>
          <Typography.Text theme="secondary">本次更新说明</Typography.Text>
          <Textarea
            autosize={{ minRows: 2, maxRows: 4 }}
            value={form.versionChangeSummary}
            placeholder="写清楚这次改了什么，例如：修补锁色参数、保持接口不变。"
            onChange={(value) => onChange({ ...form, versionChangeSummary: String(value) })}
          />
          <Typography.Text theme="secondary">判断备注</Typography.Text>
          <Textarea
            autosize={{ minRows: 2, maxRows: 3 }}
            value={form.versionDecisionNote}
            placeholder="如果不确定是新功能还是版本升级，在这里记录原因。"
            onChange={(value) => onChange({ ...form, versionDecisionNote: String(value) })}
          />
        </Space>
      </Card>
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
            theme={controlLocked ? 'error' : 'warning'}
            message={
              controlLocked
                ? '当前是线上默认版本。不能直接改主能力、配方或接口字段；请复制为草稿版本，验收通过后再申请切默认。'
                : '一般不用改。只有这个业务版本需要多步骤编排、特殊入参或特殊发布策略时，才编辑下面内容。'
            }
          />
          <Space breakLine>
            <Button
              variant="outline"
              disabled={!form.primaryAbilityId}
              onClick={() =>
                onChange({
                  ...form,
                  id: controlLocked ? undefined : form.id,
                  version: controlLocked && !form.version.endsWith('-draft') ? `${form.version}-draft` : form.version,
                  displayName:
                    controlLocked && !form.displayName.includes('草稿') ? `${form.displayName} 草稿` : form.displayName,
                  status: 'draft',
                  isDefault: false,
                  recipeText: buildBusinessDraftRecipeText(form),
                })
              }
            >
              {controlLocked ? '复制为草稿配方' : '按当前选择生成草稿配方'}
            </Button>
          <Typography.Text theme="secondary">
            只生成草稿，不会覆盖线上默认版本；试运行和验收通过后再切默认。
          </Typography.Text>
          </Space>
          <BusinessRecipeDraftEditor
            form={form}
            abilityOptions={abilityOptions}
            vlAbilityOptions={vlAbilityOptions}
            disabled={controlLocked}
            onChange={onChange}
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
};

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
                  {businessKeyLabel(row.businessKey)} · {businessCapabilityVersionRoleLabel(row.targetCapability)}
                </Typography.Text>
                <Typography.Text theme="secondary">
                  {row.sourceCapability ? businessCapabilityVersionOptionLabel(row.sourceCapability) : '当前默认'} →{' '}
                  {row.targetCapability ? businessCapabilityVersionOptionLabel(row.targetCapability) : row.targetCapabilityId}
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

const businessGraphNodeStatusTheme = (
  node: BusinessOrchestrationNode,
  graph?: BusinessOrchestrationGraph | null,
): BusinessRunFlowStageTheme => {
  const status = String(node.status || '').toLowerCase();
  if (graph?.summary?.currentNodeId === node.id && businessRunIsActive(status)) return 'primary';
  if (status === 'succeeded' || status === 'success' || status === 'completed') return 'success';
  if (status === 'failed' || status === 'error' || status === 'timeout' || status === 'cancelled') return 'danger';
  if (status === 'queued' || status === 'running' || status === 'pending') return 'warning';
  return 'default';
};

const businessGraphStatusLabel = (node: BusinessOrchestrationNode) => {
  const status = String(node.status || '').toLowerCase();
  if (status === 'planned') return '待执行';
  if (status === 'skipped') return '已跳过';
  if (!status) return '未记录';
  return businessRunStepStatusLabel(status);
};

const businessGraphModeLabel = (mode?: string | null) => {
  if (mode === 'run') return '本次运行';
  if (mode === 'recipe') return '版本配方';
  return '业务编排';
};

const businessGraphNodeTitle = (node: BusinessOrchestrationNode) =>
  node.label || node.abilityName || businessRecipeStepLabel(node.type, node.role);

const businessGraphNodeKindLabel = (node: BusinessOrchestrationNode) => {
  if (node.type === 'entry') return '入口';
  if (node.type === 'result') return '结果';
  return businessRecipeStepLabel(node.type, node.role);
};

const businessGraphNodeDetail = (node: BusinessOrchestrationNode, graph?: BusinessOrchestrationGraph | null) => {
  if (node.type === 'entry') {
    const business = businessKeyLabel(node.businessKey || graph?.businessKey);
    const version = node.version || graph?.businessVersion || '未定版本';
    return `${business} · ${version}`;
  }
  if (node.type === 'result') {
    const output = [
      node.imageCount ? `${node.imageCount} 张图` : '',
      node.videoCount ? `${node.videoCount} 个视频` : '',
      node.textCount ? `${node.textCount} 段文字` : '',
    ].filter(Boolean);
    const callback = node.callbackStatus ? `回调：${businessCallbackStatusLabel(node.callbackStatus)}` : '';
    return [...output, callback].filter(Boolean).join(' · ') || '等待结果回填';
  }
  return node.abilityName || node.abilityId || '说明步骤，不直接调用底层能力';
};

const businessGraphNodeOutputLabel = (node: BusinessOrchestrationNode) => {
  const output = asJsonRecord(node.output);
  const parts = [
    recordNumber(output, 'imageCount', 0) > 0 ? `${recordNumber(output, 'imageCount')} 张图` : '',
    recordNumber(output, 'videoCount', 0) > 0 ? `${recordNumber(output, 'videoCount')} 个视频` : '',
    recordNumber(output, 'textCount', 0) > 0 ? `${recordNumber(output, 'textCount')} 段文字` : '',
    recordNumber(output, 'structuredCount', 0) > 0 ? `${recordNumber(output, 'structuredCount')} 个结构化结果` : '',
    recordNumber(output, 'resourceCount', 0) > 0 ? `${recordNumber(output, 'resourceCount')} 个资源` : '',
  ].filter(Boolean);
  return parts.join(' · ');
};

const businessGraphHasValue = (value?: unknown) => {
  if (value === undefined || value === null || value === '') return false;
  if (Array.isArray(value)) return value.length > 0;
  if (typeof value === 'object') return Object.keys(value as JsonRecord).length > 0;
  return true;
};

const businessGraphSchemaSummary = (schema?: JsonRecord | null) => {
  const source = asJsonRecord(schema);
  const fields = Array.isArray(source.fields) ? source.fields : [];
  const fieldLabels = fields
    .slice(0, 6)
    .map((field) => {
      if (!field || typeof field !== 'object') return '';
      const item = field as JsonRecord;
      return businessGraphFieldLabel(item);
    })
    .filter(Boolean);
  const count = recordNumber(source, 'fieldCount', fields.length);
  if (!count && fieldLabels.length === 0) return '';
  return `${count || fieldLabels.length} 个字段${fieldLabels.length > 0 ? `：${fieldLabels.join('、')}` : ''}`;
};

const businessGraphFieldLabel = (field: JsonRecord) => {
  const name = String(field.name || field.key || '').trim().toLowerCase();
  const label = String(field.label || field.name || '').trim();
  if (name === 'bili' || name === 'similarity' || /相似度|similarity/i.test(label)) {
    return '重绘幅度 Repaint Strength';
  }
  return label;
};

const businessGraphRoutingSummary = (routing?: JsonRecord | null) => {
  const source = asJsonRecord(routing);
  const policy = recordText(source, 'selectionPolicy', '');
  const tags = Array.isArray(source.requiredExecutorTags) ? source.requiredExecutorTags.join('、') : '';
  const executors = Array.isArray(source.allowedExecutorIds) ? source.allowedExecutorIds.join('、') : '';
  const fallback = source.fallbackToDefault === false ? '禁止兜底' : source.fallbackToDefault === true ? '允许兜底' : '';
  return [policy ? `策略 ${policy}` : '', tags ? `标签 ${tags}` : '', executors ? `节点 ${executors}` : '', fallback].filter(Boolean).join(' · ');
};

const businessGraphNodeFlowLabel = (
  node: BusinessOrchestrationNode,
  graph?: BusinessOrchestrationGraph | null,
) => {
  const nodes = graph?.nodes || [];
  const nodeMap = new Map(nodes.map((item) => [item.id, item]));
  const incoming = (graph?.edges || [])
    .filter((edge) => edge.target === node.id)
    .map((edge) => nodeMap.get(edge.source))
    .filter(Boolean)
    .map((item) => businessGraphNodeTitle(item as BusinessOrchestrationNode));
  const outgoing = (graph?.edges || [])
    .filter((edge) => edge.source === node.id)
    .map((edge) => nodeMap.get(edge.target))
    .filter(Boolean)
    .map((item) => businessGraphNodeTitle(item as BusinessOrchestrationNode));
  return {
    incoming: incoming.length > 0 ? incoming.join('、') : '业务入口',
    outgoing: outgoing.length > 0 ? outgoing.join('、') : '业务结果',
  };
};

const businessGraphNodeActionAdvice = (
  node: BusinessOrchestrationNode,
  graph?: BusinessOrchestrationGraph | null,
) => {
  const status = String(node.status || '').toLowerCase();
  if (node.error) return '先从本节点的错误和本次 runId 处理步骤定位；如果是底层能力失败，再下钻到能力调用记录。';
  if (node.type === 'entry') return '先确认业务入口、版本和入参是否正确；业务方排障时优先保存 runId。';
  if (node.type === 'result') return '重点确认结果数量、OSS 链接、回填和回调状态；结果缺失时回到上一个执行节点。';
  if (!node.abilityId && !node.abilityName) return '这是说明或聚合节点，不直接调用底层能力；主要用于理解业务流程。';
  if (businessRunIsActive(status)) return '任务还在排队或执行中，先观察队列和执行节点；超时后再进入失败排查。';
  if (status === 'succeeded' || status === 'success' || status === 'completed') {
    return '本节点已完成；继续核对输出是否进入下一步、是否落 OSS、是否计入本次业务 runId。';
  }
  if (graph?.mode === 'recipe') return '这是版本配方视角；发版前需要用真实样本跑一次，确认字段、路由和输出都符合预期。';
  return '按字段、路由、执行节点和输出四项核对；缺哪一项就先补哪一项。';
};

const BusinessGraphNodeDiagnostics = ({ node }: { node: BusinessOrchestrationNode }) => {
  const schemaSummary = businessGraphSchemaSummary(node.inputSchema);
  const routingSummary = businessGraphRoutingSummary(node.routing);
  const hasDiagnostics =
    schemaSummary ||
    routingSummary ||
    businessGraphHasValue(node.defaultParams) ||
    businessGraphHasValue(node.recipeInputs) ||
    businessGraphHasValue(node.recipeOutputs);

  if (!hasDiagnostics) return null;

  return (
    <details className="podi-business-graph-node__diagnostics">
      <summary>参数 / 路由</summary>
      <div className="podi-business-graph-node__diagnostics-body">
        {schemaSummary ? (
          <div>
            <Typography.Text strong>字段</Typography.Text>
            <Typography.Text theme="secondary">{schemaSummary}</Typography.Text>
          </div>
        ) : null}
        {routingSummary ? (
          <div>
            <Typography.Text strong>路由</Typography.Text>
            <Typography.Text theme="secondary">{routingSummary}</Typography.Text>
          </div>
        ) : null}
        {businessGraphHasValue(node.recipeInputs) ? (
          <div>
            <Typography.Text strong>本步骤输入</Typography.Text>
            <pre>{formatJsonValue(node.recipeInputs)}</pre>
          </div>
        ) : null}
        {businessGraphHasValue(node.recipeOutputs) ? (
          <div>
            <Typography.Text strong>本步骤输出</Typography.Text>
            <pre>{formatJsonValue(node.recipeOutputs)}</pre>
          </div>
        ) : null}
        {businessGraphHasValue(node.defaultParams) ? (
          <div>
            <Typography.Text strong>能力默认值</Typography.Text>
            <pre>{formatJsonValue(node.defaultParams)}</pre>
          </div>
        ) : null}
      </div>
    </details>
  );
};

interface BusinessFlowNodeData extends Record<string, unknown> {
  node: BusinessOrchestrationNode;
  graph?: BusinessOrchestrationGraph | null;
  theme: BusinessRunFlowStageTheme;
  hasRuntime: boolean;
  outputText: string;
  isCurrent: boolean;
}

type BusinessFlowNode = Node<BusinessFlowNodeData, 'businessGraphNode'>;

const BusinessFlowNodeCard = ({ data, selected }: NodeProps<BusinessFlowNode>) => {
  const node = data.node;
  return (
    <section
      className={`podi-business-flow-node podi-business-flow-node--${data.theme} ${
        data.isCurrent ? 'podi-business-flow-node--current' : ''
      } ${selected ? 'podi-business-flow-node--selected' : ''}`}
    >
      <Handle type="target" position={Position.Left} className="podi-business-flow-node__handle" />
      <div className="podi-business-flow-node__top">
        <Tag theme={data.theme as any} variant="light" size="small">
          {businessGraphNodeKindLabel(node)}
        </Tag>
        <span>{node.order ?? '—'}</span>
      </div>
      <Typography.Text strong>{businessGraphNodeTitle(node)}</Typography.Text>
      <Typography.Text theme="secondary">{businessGraphNodeDetail(node, data.graph)}</Typography.Text>
      <Space size={6} breakLine>
        {data.hasRuntime ? (
          <Tag theme={data.theme as any} variant="light" size="small">
            {businessGraphStatusLabel(node)}
          </Tag>
        ) : null}
        {node.abilityProvider ? <Tag variant="light" size="small">{node.abilityProvider}</Tag> : null}
        {node.executorName || node.executorId ? (
          <Tag variant="light" size="small">{node.executorName || node.executorId}</Tag>
        ) : null}
        {node.durationMs ? <Tag variant="light" size="small">{formatDurationMs(node.durationMs)}</Tag> : null}
        {node.hasOssOutput ? <Tag theme="success" variant="light" size="small">已落盘</Tag> : null}
      </Space>
      {data.outputText ? <Typography.Text theme="secondary">输出：{data.outputText}</Typography.Text> : null}
      {node.abilityTaskId ? (
        <Typography.Text theme="secondary">排障：{formatShortBusinessId(node.abilityTaskId)}</Typography.Text>
      ) : null}
      {node.error ? <Typography.Text theme="error">{node.error}</Typography.Text> : null}
      <Handle type="source" position={Position.Right} className="podi-business-flow-node__handle" />
    </section>
  );
};

const businessGraphNodeTypes: NodeTypes = {
  businessGraphNode: BusinessFlowNodeCard,
};

const BusinessGraphJsonBlock = ({ title, value }: { title: string; value?: unknown }) => {
  if (!businessGraphHasValue(value)) return null;
  return (
    <div className="podi-business-flow-detail__block">
      <Typography.Text strong>{title}</Typography.Text>
      <pre>{formatJsonValue(value)}</pre>
    </div>
  );
};

const formatBusinessGraphTime = (
  value?: string | null,
  formatDateTime?: (value?: string | null) => string,
) => {
  if (!value) return '—';
  if (formatDateTime) return formatDateTime(value);
  return value;
};

const BusinessGraphRunSample = ({
  title,
  sample,
  formatDateTime,
  onOpenBusinessRun,
}: {
  title: string;
  sample?: BusinessOrchestrationNodeRunSample | null;
  formatDateTime?: (value?: string | null) => string;
  onOpenBusinessRun?: (runId: string) => void;
}) => {
  if (!sample?.runId) {
    return (
      <div className="podi-business-flow-detail__sample is-empty">
        <Typography.Text strong>{title}</Typography.Text>
        <Typography.Text theme="secondary">暂无样本</Typography.Text>
      </div>
    );
  }
  const status = String(sample.status || sample.runStatus || '').trim();
  const failed = ['failed', 'error', 'timeout', 'cancelled'].includes(status.toLowerCase());
  return (
    <div className={`podi-business-flow-detail__sample ${failed ? 'is-failed' : ''}`}>
      <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
        <Typography.Text strong>{title}</Typography.Text>
        <Tag theme={failed ? 'danger' : 'success'} variant="light" size="small">
          {status ? businessRunStepStatusLabel(status) : '已记录'}
        </Tag>
      </Space>
      <Typography.Text code>{formatShortBusinessId(sample.runId)}</Typography.Text>
      <Typography.Text theme="secondary">
        时间：{formatBusinessGraphTime(sample.finishedAt || sample.createdAt, formatDateTime)}
      </Typography.Text>
      <Typography.Text theme="secondary">
        耗时：{sample.durationMs ? formatDurationMs(sample.durationMs) : '—'}
        {sample.abilityLogId ? ` · 日志 ${sample.abilityLogId}` : ''}
      </Typography.Text>
      {sample.error ? <Typography.Text theme="error">{sample.error}</Typography.Text> : null}
      {onOpenBusinessRun ? (
        <Button size="small" variant="outline" onClick={() => onOpenBusinessRun(sample.runId as string)}>
          打开 runId
        </Button>
      ) : null}
    </div>
  );
};

const BusinessGraphSelectedNodePanel = ({
  node,
  graph,
  formatDateTime,
  onOpenBusinessRun,
}: {
  node?: BusinessOrchestrationNode | null;
  graph?: BusinessOrchestrationGraph | null;
  formatDateTime?: (value?: string | null) => string;
  onOpenBusinessRun?: (runId: string) => void;
}) => {
  if (!node) {
    return (
      <aside className="podi-business-flow-detail">
        <Typography.Text strong>节点详情</Typography.Text>
        <Typography.Text theme="secondary">点击画布里的节点查看参数、路由和排障信息。</Typography.Text>
      </aside>
    );
  }
  const schemaSummary = businessGraphSchemaSummary(node.inputSchema);
  const routingSummary = businessGraphRoutingSummary(node.routing);
  const flowLabel = businessGraphNodeFlowLabel(node, graph);
  const actionAdvice = businessGraphNodeActionAdvice(node, graph);
  const runtimeEvidence = node.runtimeEvidence;
  return (
    <aside className="podi-business-flow-detail">
      <div className="podi-business-flow-detail__head">
        <Typography.Text strong>{businessGraphNodeTitle(node)}</Typography.Text>
        <Tag theme={businessGraphNodeStatusTheme(node, graph) as any} variant="light">
          {businessGraphStatusLabel(node)}
        </Tag>
      </div>
      <Typography.Text theme="secondary">{businessGraphNodeDetail(node, graph)}</Typography.Text>
      <div className="podi-business-flow-detail__facts">
        <span>类型：{businessGraphNodeKindLabel(node)}</span>
        <span>顺序：{node.order ?? '—'}</span>
        <span>能力：{node.abilityName || node.abilityId || '无底层能力'}</span>
        <span>节点：{node.executorName || node.executorId || '未指定'}</span>
        <span>耗时：{node.durationMs ? formatDurationMs(node.durationMs) : '—'}</span>
        <span>排障：{node.abilityTaskId ? formatShortBusinessId(node.abilityTaskId) : '—'}</span>
      </div>
      <div className="podi-business-flow-detail__block">
        <Typography.Text strong>上下游</Typography.Text>
        <Typography.Text theme="secondary">上一步：{flowLabel.incoming}</Typography.Text>
        <Typography.Text theme="secondary">下一步：{flowLabel.outgoing}</Typography.Text>
      </div>
      {runtimeEvidence ? (
        <div className="podi-business-flow-detail__block">
          <Typography.Text strong>最近运行</Typography.Text>
          <Typography.Text theme="secondary">
            近 {runtimeEvidence.windowHours || 24} 小时：总计 {runtimeEvidence.total || 0}，成功{' '}
            {runtimeEvidence.succeeded || 0}，失败 {runtimeEvidence.failed || 0}，排队/运行{' '}
            {Number(runtimeEvidence.queued || 0) + Number(runtimeEvidence.running || 0)}。
          </Typography.Text>
          <div className="podi-business-flow-detail__samples">
            <BusinessGraphRunSample
              title="最近一次"
              sample={runtimeEvidence.latest}
              formatDateTime={formatDateTime}
              onOpenBusinessRun={onOpenBusinessRun}
            />
            <BusinessGraphRunSample
              title="成功样本"
              sample={runtimeEvidence.latestSuccess}
              formatDateTime={formatDateTime}
              onOpenBusinessRun={onOpenBusinessRun}
            />
            <BusinessGraphRunSample
              title="失败样本"
              sample={runtimeEvidence.latestFailure}
              formatDateTime={formatDateTime}
              onOpenBusinessRun={onOpenBusinessRun}
            />
          </div>
        </div>
      ) : null}
      <Alert theme={node.error ? 'error' : 'info'} message={`建议：${actionAdvice}`} />
      {schemaSummary ? (
        <div className="podi-business-flow-detail__block">
          <Typography.Text strong>字段摘要</Typography.Text>
          <Typography.Text theme="secondary">{schemaSummary}</Typography.Text>
        </div>
      ) : null}
      {routingSummary ? (
        <div className="podi-business-flow-detail__block">
          <Typography.Text strong>路由摘要</Typography.Text>
          <Typography.Text theme="secondary">{routingSummary}</Typography.Text>
        </div>
      ) : null}
      <BusinessGraphJsonBlock title="本步骤输入" value={node.recipeInputs} />
      <BusinessGraphJsonBlock title="本步骤输出" value={node.recipeOutputs} />
      <BusinessGraphJsonBlock title="能力默认值" value={node.defaultParams} />
      <BusinessGraphJsonBlock title="路由详情" value={node.routing} />
      {node.error ? <Alert theme="error" message={node.error} /> : null}
    </aside>
  );
};

const buildBusinessFallbackGraph = (
  steps?: BusinessRecipeFlowStep[] | null,
  baseGraph?: BusinessOrchestrationGraph | null,
): BusinessOrchestrationGraph | null => {
  const visibleSteps = (steps || []).filter((step) => step && step.enabled !== false);
  if (visibleSteps.length === 0) return null;

  const entryNode: BusinessOrchestrationNode = {
    id: 'entry',
    type: 'entry',
    label: '业务入口',
    order: 0,
    businessKey: baseGraph?.businessKey,
    version: baseGraph?.businessVersion,
    status: baseGraph?.mode === 'run' ? 'succeeded' : 'planned',
  };
  const stepNodes: BusinessOrchestrationNode[] = visibleSteps.map((step, index) => {
    const nodeId = String(step.id || step.stepId || step.abilityId || `step-${index + 1}`);
    const params =
      step.params && typeof step.params === 'object' && !Array.isArray(step.params)
        ? (step.params as JsonRecord)
        : undefined;
    return {
      id: nodeId,
      type: step.type || step.stepType || 'ability_task',
      role: step.role,
      label: step.componentLabel || step.displayName || step.abilityName || businessRecipeStepLabel(step.type || step.stepType, step.role),
      order: step.order || index + 1,
      status: step.status || (baseGraph?.mode === 'run' ? 'planned' : 'planned'),
      abilityId: step.abilityId,
      abilityName: step.abilityName || step.displayName,
      abilityProvider: step.abilityProvider,
      abilityTaskId: step.abilityTaskId,
      defaultParams: params,
      recipeInputs: step.inputs && step.inputs.length > 0 ? { fields: step.inputs } : undefined,
      recipeOutputs: step.outputs && step.outputs.length > 0 ? { fields: step.outputs } : undefined,
      durationMs: step.durationMs,
      error: step.error,
    };
  });
  const resultNode: BusinessOrchestrationNode = {
    id: 'result',
    type: 'result',
    label: '结果回填',
    order: visibleSteps.length + 1,
    status: baseGraph?.mode === 'run' ? baseGraph?.summary?.status || 'planned' : 'planned',
  };
  const nodes = [entryNode, ...stepNodes, resultNode];
  const edges: BusinessOrchestrationEdge[] = nodes.slice(0, -1).map((node, index) => ({
    id: `${node.id}-${nodes[index + 1].id}`,
    source: node.id,
    target: nodes[index + 1].id,
  }));

  return {
    ...baseGraph,
    mode: baseGraph?.mode || 'recipe',
    nodes,
    edges,
    summary: {
      ...(baseGraph?.summary || {}),
      stepCount: visibleSteps.length,
      executableStepCount: visibleSteps.filter((step) => step.abilityId || step.abilityName).length,
      hasVlStep: visibleSteps.some((step) => String(step.role || step.type || step.stepType || '').toLowerCase().includes('vl')),
    },
  };
};

export const BusinessOrchestrationGraphView = ({
  graph,
  fallbackSteps,
  compact = false,
  showRuntime = false,
  formatDateTime,
  onOpenBusinessRun,
}: {
  graph?: BusinessOrchestrationGraph | null;
  fallbackSteps?: BusinessRecipeFlowStep[] | null;
  compact?: boolean;
  showRuntime?: boolean;
  formatDateTime?: (value?: string | null) => string;
  onOpenBusinessRun?: (runId: string) => void;
}) => {
  const effectiveGraph =
    graph && (graph.nodes || []).some((node) => node && node.enabled !== false)
      ? graph
      : buildBusinessFallbackGraph(fallbackSteps, graph);
  const nodes = (effectiveGraph?.nodes || []).filter((node) => node && node.enabled !== false);
  const edges = effectiveGraph?.edges || [];
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  if (nodes.length === 0) {
    return <BusinessRecipeFlow steps={fallbackSteps} compact={compact} showRuntime={showRuntime} />;
  }
  const summary = effectiveGraph?.summary || {};
  const hasRuntime = effectiveGraph?.mode === 'run' || showRuntime;
  const output = asJsonRecord(summary.output);
  const outputLabel = [
    recordNumber(output, 'imageCount', 0) > 0 ? `${recordNumber(output, 'imageCount')} 张图` : '',
    recordNumber(output, 'videoCount', 0) > 0 ? `${recordNumber(output, 'videoCount')} 个视频` : '',
    recordNumber(output, 'textCount', 0) > 0 ? `${recordNumber(output, 'textCount')} 段文字` : '',
    recordNumber(output, 'structuredCount', 0) > 0 ? `${recordNumber(output, 'structuredCount')} 个结构化结果` : '',
    recordNumber(output, 'resourceCount', 0) > 0 ? `${recordNumber(output, 'resourceCount')} 个资源` : '',
  ].filter(Boolean).join(' · ');
  const defaultSelectedNode =
    nodes.find((node) => {
      const type = String(node.type || '').toLowerCase();
      return type !== 'entry' && type !== 'result' && (node.abilityId || node.abilityName || node.executorId || node.executorName);
    }) ||
    nodes.find((node) => String(node.type || '').toLowerCase() !== 'entry') ||
    nodes[0] ||
    null;
  const selectedNode = nodes.find((node) => node.id === selectedNodeId) || defaultSelectedNode;
  const nodeIdSet = new Set(nodes.map((node) => node.id));
  const flowNodes: BusinessFlowNode[] = nodes.map((node, index) => {
    const theme = businessGraphNodeStatusTheme(node, effectiveGraph);
    return {
      id: node.id,
      type: 'businessGraphNode',
      position: { x: index * 330, y: index % 2 === 0 ? 0 : 34 },
      data: {
        node,
        graph: effectiveGraph,
        theme,
        hasRuntime,
        outputText: businessGraphNodeOutputLabel(node),
        isCurrent: summary.currentNodeId === node.id,
      },
    };
  });
  const flowEdges: Edge[] = edges
    .filter((edge) => nodeIdSet.has(edge.source) && nodeIdSet.has(edge.target))
    .map((edge) => ({
      id: edge.id || `${edge.source}-${edge.target}`,
      source: edge.source,
      target: edge.target,
      label: edge.label || undefined,
      type: 'smoothstep',
      markerEnd: { type: MarkerType.ArrowClosed },
      animated: summary.currentNodeId === edge.target,
    }));

  return (
    <div className={`podi-business-graph ${compact ? 'podi-business-graph--compact' : ''}`}>
      <div className="podi-business-graph__head">
        <Space size={6} breakLine>
          <Tag theme={effectiveGraph?.mode === 'run' ? 'primary' : 'default'} variant="light">
            {businessGraphModeLabel(effectiveGraph?.mode)}
          </Tag>
          <Tag variant="light">步骤 {summary.stepCount ?? Math.max(nodes.length - 2, 0)}</Tag>
          {summary.executableStepCount !== undefined && summary.executableStepCount !== null ? (
            <Tag variant="light">执行 {summary.executableStepCount}</Tag>
          ) : null}
          {summary.hasVlStep ? <Tag theme="primary" variant="light">含图像理解</Tag> : null}
          {typeof summary.progressPercent === 'number' ? <Tag variant="light">进度 {summary.progressPercent}%</Tag> : null}
          {outputLabel ? <Tag theme="success" variant="light">输出 {outputLabel}</Tag> : null}
        </Space>
        {summary.issueLabel ? (
          <Typography.Text theme={summary.issueCategory === 'none' ? 'secondary' : 'warning'}>
            {summary.issueLabel}
          </Typography.Text>
        ) : null}
      </div>
      {compact ? (
        <div className="podi-business-graph__track">
          {nodes.map((node, index) => {
            const theme = businessGraphNodeStatusTheme(node, effectiveGraph);
            const isCurrent = summary.currentNodeId === node.id;
            const outputText = businessGraphNodeOutputLabel(node);
            const nextEdge = edges.find((edge) => edge.source === node.id && nodes.some((item) => item.id === edge.target));
            return (
              <div className="podi-business-graph__segment" key={`${node.id}-${index}`}>
                <section className={`podi-business-graph-node podi-business-graph-node--${theme} ${isCurrent ? 'podi-business-graph-node--current' : ''}`}>
                  <div className="podi-business-graph-node__top">
                    <Tag theme={theme as any} variant="light" size="small">
                      {businessGraphNodeKindLabel(node)}
                    </Tag>
                    <span>{node.order ?? index}</span>
                  </div>
                  <Typography.Text strong>{businessGraphNodeTitle(node)}</Typography.Text>
                  <Typography.Text theme="secondary">{businessGraphNodeDetail(node, effectiveGraph)}</Typography.Text>
                  <Space size={6} breakLine>
                    {hasRuntime ? (
                      <Tag theme={theme as any} variant="light" size="small">
                        {businessGraphStatusLabel(node)}
                      </Tag>
                    ) : null}
                    {node.abilityProvider ? <Tag variant="light" size="small">{node.abilityProvider}</Tag> : null}
                    {node.executorName || node.executorId ? (
                      <Tag variant="light" size="small">{node.executorName || node.executorId}</Tag>
                    ) : null}
                    {node.durationMs ? <Tag variant="light" size="small">{formatDurationMs(node.durationMs)}</Tag> : null}
                    {node.hasOssOutput ? <Tag theme="success" variant="light" size="small">已落盘</Tag> : null}
                  </Space>
                  <BusinessGraphNodeDiagnostics node={node} />
                  {outputText ? <Typography.Text theme="secondary">输出：{outputText}</Typography.Text> : null}
                  {node.abilityTaskId ? (
                    <Typography.Text theme="secondary">排障：{formatShortBusinessId(node.abilityTaskId)}</Typography.Text>
                  ) : null}
                  {node.error ? <Typography.Text theme="error">{node.error}</Typography.Text> : null}
                </section>
                {index < nodes.length - 1 ? (
                  <div className="podi-business-graph__edge" title={nextEdge?.label || ''}>
                    →
                  </div>
                ) : null}
              </div>
            );
          })}
        </div>
      ) : (
        <div className="podi-business-flow-shell">
          <div className="podi-business-flow-canvas">
            <ReactFlow
              nodes={flowNodes}
              edges={flowEdges}
              nodeTypes={businessGraphNodeTypes}
              fitView
              fitViewOptions={{ padding: 0.18 }}
              minZoom={0.45}
              maxZoom={1.35}
              nodesDraggable={false}
              nodesConnectable={false}
              elementsSelectable
              proOptions={{ hideAttribution: true }}
              onNodeClick={(_, node) => setSelectedNodeId(node.id)}
            >
              <Background gap={18} size={1} />
              <Controls showInteractive={false} />
            </ReactFlow>
          </div>
          <BusinessGraphSelectedNodePanel
            node={selectedNode}
            graph={effectiveGraph}
            formatDateTime={formatDateTime}
            onOpenBusinessRun={onOpenBusinessRun}
          />
        </div>
      )}
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
  const key = canonicalBusinessKey(businessKey);
  if (key === 'pattern_extract') return '从原图中提取可复用花纹资产，是后续裂变和扩图的上游入口。';
  if (key === 'fission') return '围绕原图生成多张变化图，是当前最核心的业务入口。';
  if (key === 'product_design') return '把花纹或素材上到具体产品载体，输出可评估的产品设计图。';
  if (key === 'image_edit') return '通用改图组件入口，承接主图、标注、参考图、蒙版和编辑指令。';
  if (key === 'fission_evaluate') return '评估裂变结果质量和逻辑合理性，作为图裂变的质检接口。';
  if (key === 'outpaint') return '在原图基础上向外扩展画面，主要服务构图补全和素材延展。';
  if (key === 'text_fission') return '文字强化裂变两步式入口，先生成可编辑提示词，再提交文生图。';
  return '承载一个对业务方稳定暴露的功能入口，底层能力可以独立换版本。';
};

const businessOrchestrationKeys = ['pattern_extract', 'fission', 'product_design', 'image_edit', 'outpaint', 'text_fission'] as const;

const businessApiEntryPath = (businessKey?: string | null) => {
  const key = canonicalBusinessKey(businessKey);
  if (key === 'pattern_extract') return '/api/business/pattern-extract/runs';
  if (key === 'fission') return '/api/business/fission/runs';
  if (key === 'product_design') return '/api/business/product-design/runs';
  if (key === 'image_edit') return '/api/business/image-edit/runs';
  if (key === 'fission_evaluate') return '/api/business/fission-evaluate/runs';
  if (key === 'outpaint') return '/api/business/outpaint/runs';
  if (key === 'text_fission') return '/api/business/text-fission/runs';
  return '/api/business/{business}/runs';
};

const businessDraftRunRequiresGeneratedImage = (businessKey?: string | null) =>
  canonicalBusinessKey(businessKey) === 'fission_evaluate';

const businessEntryUsageHint = (businessKey?: string | null) => {
  const key = canonicalBusinessKey(businessKey);
  if (key === 'fission') return '业务方、测评端和新的 Coze 工具箱都应收敛到这里，再由中台切版本。';
  if (key === 'product_design') return '客户端可把它编排到端到端链路；中台只管理能力、版本、路由和质量。';
  if (key === 'image_edit') return '业务方可嵌入托管组件或源码组件；两者都调用同一个中台业务 API。';
  if (key === 'fission_evaluate') return '通常在裂变完成后调用，用于判断结果是否可用或是否需要重跑。';
  if (key === 'pattern_extract') return '作为素材生产上游入口，可被裂变、扩图或人工流程复用。';
  if (key === 'outpaint') return '对业务方保持固定入口，底层可以在 ComfyUI 或商业模型间切换。';
  if (key === 'text_fission') return '业务方先调用 prompts 生成可编辑提示词，再确认后提交 runs。';
  return '业务方只需要调用固定入口，内部版本和处理步骤由中台管理。';
};

const businessCapabilityEngineLabel = (item?: BusinessCapability | null) => {
  if (!item) return '未绑定';
  if (item.primaryAbilityName) {
    return [item.primaryAbilityProvider, item.primaryAbilityName].filter(Boolean).join(' · ');
  }
  if (item.vendorModelName) {
    return [item.vendorModelProvider, item.vendorModelName].filter(Boolean).join(' · ');
  }
  return item.primaryAbilityId || item.vendorModelId || '未绑定真实能力';
};

const businessCapabilityVersionLine = (item?: BusinessCapability | null) => {
  const family = item?.versionFamily;
  if (family?.lineKey || family?.lineLabel) {
    const key = String(family.lineKey || 'standard');
    const theme =
      key === 'rollback'
        ? ('warning' as const)
        : key === 'quality-gate'
          ? ('primary' as const)
        : key === 'commercial-model'
          ? ('primary' as const)
          : key === 'comfyui'
            ? ('success' as const)
            : key === 'coze'
              ? ('default' as const)
              : item?.isDefault
                ? ('success' as const)
                : ('default' as const);
    return {
      key,
      label: String(family.lineLabel || '标准版本'),
      theme,
      detail: String(family.lineDetail || '同一业务入口下的稳定版本。'),
      priority: Number(family.linePriority ?? (item?.isDefault ? 10 : 50)),
    };
  }
  const serverLine = item?.versionLine;
  if (serverLine?.key || serverLine?.label) {
    const key = String(serverLine.key || 'standard');
    const theme =
      key === 'rollback'
        ? ('warning' as const)
        : key === 'quality-gate'
          ? ('primary' as const)
        : key === 'commercial-model'
          ? ('primary' as const)
          : key === 'comfyui'
            ? ('success' as const)
            : key === 'coze'
              ? ('default' as const)
              : item?.isDefault
                ? ('success' as const)
                : ('default' as const);
    return {
      key,
      label: String(serverLine.label || '标准版本'),
      theme,
      detail: String(serverLine.detail || '同一业务入口下的稳定版本。'),
      priority: Number(serverLine.priority ?? (item?.isDefault ? 10 : 50)),
    };
  }
  const metadata = (item?.metadata || {}) as JsonRecord;
  const role = String(metadata.role || '').toLowerCase();
  const provider = String(metadata.provider || item?.primaryAbilityProvider || item?.vendorModelProvider || '').toLowerCase();
  const version = String(item?.version || '').toLowerCase();
  const displayName = String(item?.displayName || '').toLowerCase();
  const hasVendorModel = Boolean(item?.vendorModelId || item?.vendorModelName || item?.vendorModelProvider);
  if (!item) {
    return { key: 'unknown', label: '未归类路线', theme: 'default' as const, detail: '还没有业务版本。', priority: 99 };
  }
  if (role.includes('rollback') || metadata.rollbackSafety || version.includes('rollback') || displayName.includes('保底')) {
    return {
      key: 'rollback',
      label: '保底回滚',
      theme: 'warning' as const,
      detail: '只在主线异常时切回，不作为新功能入口。',
      priority: 80,
    };
  }
  if (provider.includes('comfyui') || version.includes('comfyui') || displayName.includes('comfyui')) {
    return {
      key: 'comfyui',
      label: 'ComfyUI 自研线',
      theme: 'success' as const,
      detail: '业务仍是同一个入口，底层由 ComfyUI 工作流执行。',
      priority: 20,
    };
  }
  if (String(metadata.entry || '').toLowerCase().includes('coze') || displayName.includes('coze')) {
    return {
      key: 'coze',
      label: 'Coze 旧链路',
      theme: 'default' as const,
      detail: '兼容旧业务接入，不作为新功能命名。',
      priority: 70,
    };
  }
  const commercialProviderTokens = ['openai', 'gpt-image', 'kie', 'volcengine', 'doubao', 'qwen', 'seedream', 'vendor-api'];
  if (
    hasVendorModel ||
    commercialProviderTokens.some((token) => provider.includes(token)) ||
    version.includes('gpt-image') ||
    displayName.includes('gpt image')
  ) {
    return {
      key: 'commercial-model',
      label: '商业模型线',
      theme: 'primary' as const,
      detail: '业务仍是同一个入口，底层改用商业模型执行。',
      priority: 30,
    };
  }
  return {
    key: 'standard',
    label: item.isDefault ? '生产主线' : '标准版本',
    theme: item.isDefault ? ('success' as const) : ('default' as const),
    detail: '同一业务入口下的稳定版本。',
    priority: item.isDefault ? 10 : 50,
  };
};

const businessCapabilityVersionLineage = (item?: BusinessCapability | null) => {
  const family = item?.versionFamily;
  const metadata = (item?.metadata || {}) as JsonRecord;
  const raw = item?.versionLineage || (
    metadata.versionLineage && typeof metadata.versionLineage === 'object' && !Array.isArray(metadata.versionLineage)
      ? (metadata.versionLineage as JsonRecord)
      : null
  );
  const parentVersionId =
    typeof family?.parentVersionId === 'string' ? family.parentVersionId : typeof raw?.parentVersionId === 'string' ? raw.parentVersionId : '';
  const supersedesVersionId =
    typeof family?.supersedesVersionId === 'string'
      ? family.supersedesVersionId
      : typeof raw?.supersedesVersionId === 'string'
        ? raw.supersedesVersionId
        : '';
  const changeSummary =
    typeof family?.changeSummary === 'string' ? family.changeSummary : typeof raw?.changeSummary === 'string' ? raw.changeSummary : '';
  const decision = typeof family?.decision === 'string' ? family.decision : typeof raw?.decision === 'string' ? raw.decision : 'unknown';
  const decisionNote =
    typeof family?.decisionNote === 'string' ? family.decisionNote : typeof raw?.decisionNote === 'string' ? raw.decisionNote : '';
  return {
    parentVersionId,
    supersedesVersionId,
    parentLabel: family?.parent?.label || '',
    supersedesLabel: family?.supersedes?.label || '',
    changeSummary,
    breakingChange: Boolean(family?.breakingChange ?? raw?.breakingChange),
    decision,
    decisionLabel: family?.decisionLabel || '',
    decisionNote,
  };
};

const businessCapabilityVersionRoleLabel = (item?: BusinessCapability | null) => {
  if (!item) return '未设置版本';
  const line = businessCapabilityVersionLine(item);
  const lifecycle = item.versionFamily?.lifecycleLabel;
  if (lifecycle) return `${lifecycle} · ${line.label}`;
  if (item.isDefault) return `线上默认 · ${line.label}`;
  if (line.key === 'rollback') return `保底回滚 · ${line.label}`;
  if (line.key === 'quality-gate') return `质检入口 · ${line.label}`;
  if (item.status === 'draft') return `草稿验证 · ${line.label}`;
  return `备选验证 · ${line.label}`;
};

const businessCapabilityVersionOptionLabel = (item: BusinessCapability) => {
  const versionLabel = item.versionFamily?.versionLabel || (item.version ? `版本 ${item.version}` : '未填版本号');
  return `${businessCapabilityVersionRoleLabel(item)} · ${versionLabel}`;
};

const businessCapabilityVersionBrief = (item?: BusinessCapability | null) =>
  item ? businessCapabilityVersionOptionLabel(item) : '';

const businessCapabilityVersionRelationLabel = (item: BusinessCapability, items: BusinessCapability[]) => {
  const lineage = businessCapabilityVersionLineage(item);
  const parent = lineage.parentVersionId ? items.find((candidate) => candidate.id === lineage.parentVersionId) : null;
  const supersedes = lineage.supersedesVersionId ? items.find((candidate) => candidate.id === lineage.supersedesVersionId) : null;
  if (lineage.decision === 'new_feature') {
    return `新功能判断：${lineage.decisionNote || '入口含义发生变化，需要作为独立业务管理。'}`;
  }
  if (parent || supersedes || lineage.parentVersionId || lineage.supersedesVersionId || lineage.parentLabel || lineage.supersedesLabel) {
    const parts = [
      parent
        ? `来源 ${businessCapabilityVersionBrief(parent)}`
        : lineage.parentLabel
          ? `来源 ${lineage.parentLabel}`
          : lineage.parentVersionId
            ? `来源 ${formatShortBusinessId(lineage.parentVersionId)}`
            : '',
      supersedes
        ? `替代 ${businessCapabilityVersionBrief(supersedes)}`
        : lineage.supersedesLabel
          ? `替代 ${lineage.supersedesLabel}`
          : lineage.supersedesVersionId
            ? `替代 ${formatShortBusinessId(lineage.supersedesVersionId)}`
            : '',
    ].filter(Boolean);
    return parts.join('；');
  }
  const line = businessCapabilityVersionLine(item);
  if (line.key === 'rollback') return '保底版本：只作为异常回滚，不新开功能。';
  const sameLine = items
    .filter((candidate) => businessCapabilityVersionLine(candidate).key === line.key)
    .slice()
    .sort((left, right) => {
      const leftTime = String(left.releaseTime || left.createdAt || '');
      const rightTime = String(right.releaseTime || right.createdAt || '');
      return leftTime.localeCompare(rightTime);
    });
  const index = sameLine.findIndex((candidate) => candidate.id === item.id);
  const previous = index > 0 ? sameLine[index - 1] : null;
  if (previous) return `同路线参考：${previous.version} -> ${item.version}`;
  return '同路线起点：后续修补继续作为版本升级。';
};

const businessUsageBucketForKey = (summary: BusinessUsageSummaryResponse | null | undefined, businessKey: string) =>
  summary?.byBusiness?.find((item) => canonicalBusinessKey(item.key) === canonicalBusinessKey(businessKey));

const businessUnresolvedBucketForKey = (summary: BusinessUsageSummaryResponse | null | undefined, businessKey: string) =>
  summary?.unresolvedByBusiness?.find((item) => canonicalBusinessKey(item.key) === canonicalBusinessKey(businessKey));

const businessUsageDigest = (summary: BusinessUsageSummaryResponse | null | undefined, businessKey: string) => {
  const bucket = businessUsageBucketForKey(summary, businessKey);
  const windowHours = Number(summary?.windowHours || 24);
  if (!bucket || !bucket.total) return `近 ${windowHours} 小时暂无业务调用`;
  return `近 ${windowHours} 小时 ${bucket.total} 次 · 成功 ${bucket.succeeded} · 失败 ${bucket.failed} · 排队/运行 ${
    Number(bucket.queued || 0) + Number(bucket.running || 0)
  } · 成功率 ${formatRatePercent(bucket.successRate)}`;
};

const businessCapabilityMediaLabel = (item: BusinessCapability) => {
  const key = canonicalBusinessKey(item.businessKey);
  if (key === 'pattern_extract') return '输入图片 · 输出花纹图';
  if (key === 'fission') return '输入图片 · 输出多张图';
  if (key === 'product_design') return '输入素材/花纹 · 输出产品设计图';
  if (key === 'image_edit') return '输入主图/参考图 · 输出改图结果';
  if (key === 'fission_evaluate') return '输入原图和结果图 · 输出评分';
  if (key === 'outpaint') return '输入图片 · 输出扩展图';
  if (key === 'text_fission') return '输入图片/确认提示词 · 输出文字强化图';
  const output = item.outputSchema || {};
  const text = JSON.stringify(output).toLowerCase();
  if (text.includes('video')) return '输出视频';
  if (text.includes('text')) return '输出文字';
  if (text.includes('image')) return '输出图片';
  return '按接口配置输出';
};

const businessCapabilityRiskTag = (item: BusinessCapability) => {
  if (item.status === 'draft') {
    return { theme: 'primary', text: '草稿中', detail: '只用于编排和试运行，不会承接线上业务请求。' };
  }
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

const businessCapabilityIsHistoricalVersion = (item: BusinessCapability, supersededIds?: Set<string>) => {
  if (item.isDefault || item.status === 'draft') return false;
  const status = String(item.status || '').toLowerCase();
  const lifecycle = String(item.versionFamily?.lifecycleKey || '').toLowerCase();
  const line = businessCapabilityVersionLine(item);
  if (['deprecated', 'disabled', 'inactive'].includes(status)) return true;
  if (['deprecated', 'disabled', 'inactive'].includes(lifecycle)) return true;
  if (line.key === 'legacy') return true;
  return Boolean(item.id && supersededIds?.has(item.id));
};

const businessCoreEntrySuggestion = ({
  defaultItem,
  activeCount,
  hasPendingApproval,
  unresolvedCount = 0,
}: {
  defaultItem?: BusinessCapability;
  activeCount: number;
  hasPendingApproval: boolean;
  unresolvedCount?: number;
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
  if (defaultItem.latestRun?.error || unresolvedCount > 0) return '最近有失败样本，先打开业务调用清单确认卡点。';
  if (Number(defaultItem.runMetrics?.failed || 0) > 0) return '历史失败已被后续成功样本覆盖，保留追溯即可。';
  if (hasPendingApproval) return '存在默认版本切换审批，先处理审批再对外说明。';
  if (defaultItem.releaseGate?.status === 'warning') return defaultItem.releaseGate.suggestions?.[0] || '上线前仍有风险项，先完成复核再小流量验证。';
  if (activeCount < 2) return '建议保留一个可用备选版本，便于灰度和快速回滚。';
  return '入口稳定，可进入测评端或小流量业务验证。';
};

const businessEntryCommandStatus = ({
  defaultItem,
  bucket,
  unresolvedBucket,
  activeCount,
  hasPendingApproval,
}: {
  defaultItem?: BusinessCapability;
  bucket?: ReturnType<typeof businessUsageBucketForKey>;
  unresolvedBucket?: ReturnType<typeof businessUnresolvedBucketForKey>;
  activeCount: number;
  hasPendingApproval: boolean;
}) => {
  const unresolvedCount = Number(unresolvedBucket?.total || 0);
  if (!defaultItem) {
    return {
      theme: 'danger',
      label: '缺入口',
      detail: '业务方还没有稳定可调的默认版本。',
    };
  }
  if (defaultItem.status !== 'active') {
    return {
      theme: 'danger',
      label: '未启用',
      detail: '默认版本未启用，业务方调用前必须先切到可用版本。',
    };
  }
  if (!defaultItem.primaryAbilityId && !defaultItem.primaryAbilityName) {
    return {
      theme: 'danger',
      label: '缺执行能力',
      detail: '默认版本没有绑定真实执行能力。',
    };
  }
  const latestRunSucceeded = String(defaultItem.latestRun?.status || '').toLowerCase() === 'succeeded' && !defaultItem.latestRun?.error;
  if (defaultItem.releaseGate?.status === 'blocked' && latestRunSucceeded && unresolvedCount === 0) {
    return {
      theme: 'warning',
      label: '线上可用',
      detail: '接口已有成功样本，但还缺验收通过记录；补证据后再作为封版依据。',
    };
  }
  if (defaultItem.governanceStatus === 'blocker' || defaultItem.releaseGate?.status === 'blocked') {
    return {
      theme: 'danger',
      label: '有阻塞',
      detail: defaultItem.governanceSuggestions?.[0] || defaultItem.releaseGate?.suggestions?.[0] || '上线门禁或底层能力未通过。',
    };
  }
  if (defaultItem.latestRun?.error || unresolvedCount > 0) {
    return {
      theme: 'warning',
      label: '需复核',
      detail: unresolvedCount > 0 ? `${unresolvedCount} 条失败还没被同版本成功样本覆盖，先看业务调用清单定位。` : '最近一次真实调用失败，先看业务调用清单定位。',
    };
  }
  if (Number(bucket?.callbackFailed || 0) > 0) {
    return {
      theme: 'warning',
      label: '回填风险',
      detail: '有结果回填失败，先确认业务方是否能拿到最终图。',
    };
  }
  if (hasPendingApproval) {
    return {
      theme: 'warning',
      label: '切换中',
      detail: '默认版本切换还在审批，先不要对外宣称已切换。',
    };
  }
  if (activeCount < 2) {
    return {
      theme: 'warning',
      label: '线上可用',
      detail: '入口可用，但建议保留一个可回滚版本。',
    };
  }
  if (Number(bucket?.failed || 0) > 0) {
    return {
      theme: 'success',
      label: '线上可用',
      detail: '有历史失败，但后续同版本成功样本已覆盖；历史记录只保留追溯。',
    };
  }
  return {
    theme: 'success',
    label: '线上可用',
    detail: '业务入口、默认版本和最近调用都可继续验证。',
  };
};

export const BusinessEntryCommandPanel = ({
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
  const windowHours = Number(summary?.windowHours || 24);
  const rows = businessOrchestrationKeys.map((businessKey) => {
    const items = capabilities.filter((item) => canonicalBusinessKey(item.businessKey) === businessKey);
    const defaultItem = items.find((item) => item.isDefault);
    const activeCount = items.filter((item) => item.status === 'active').length;
    const bucket = businessUsageBucketForKey(summary, businessKey);
    const unresolvedBucket = businessUnresolvedBucketForKey(summary, businessKey);
    const hasPendingApproval = pendingApprovals.some(
      (item) => canonicalBusinessKey(item.businessKey) === businessKey && item.status === 'pending',
    );
    const status = businessEntryCommandStatus({ defaultItem, bucket, unresolvedBucket, activeCount, hasPendingApproval });
    return {
      businessKey,
      items,
      defaultItem,
      activeCount,
      bucket,
      unresolvedBucket,
      hasPendingApproval,
      status,
      suggestion: businessCoreEntrySuggestion({
        defaultItem,
        activeCount,
        hasPendingApproval,
        unresolvedCount: Number(unresolvedBucket?.total || 0),
      }),
    };
  });
  const onlineCount = rows.filter((row) => row.status.theme !== 'danger').length;

  return (
    <Card
      bordered
      className="podi-business-command-card"
      title={
        <Space align="center" style={{ justifyContent: 'space-between', width: '100%', flexWrap: 'wrap' }}>
          <div>
            <Typography.Text strong>业务入口概览</Typography.Text>
            <div>
              <Typography.Text theme="secondary">
                看业务方应该调哪个入口、线上默认跑哪个版本、最近有没有真实调用。
              </Typography.Text>
            </div>
          </div>
          <Tag theme={onlineCount === rows.length ? 'success' : rows.some((row) => row.status.theme === 'danger') ? 'danger' : 'warning'} variant="light">
            {onlineCount}/{rows.length} 有线上入口
          </Tag>
        </Space>
      }
    >
      <div className="podi-business-command-table">
        <div className="podi-business-command-head">
          <span>业务入口</span>
          <span>当前线上版本</span>
          <span>近 {windowHours} 小时调用</span>
          <span>最近结果</span>
          <span>现在怎么做</span>
        </div>
        {rows.map((row) => {
          const runningCount = Number(row.bucket?.running || 0) + Number(row.bucket?.queued || 0);
          return (
            <section
              key={row.businessKey}
              className={`podi-business-command-row podi-business-command-row--${row.status.theme}`}
            >
              <div className="podi-business-command-cell podi-business-command-cell--entry">
                <Space align="center" size={8} style={{ flexWrap: 'wrap' }}>
                  <Typography.Text strong>{businessKeyLabel(row.businessKey)}</Typography.Text>
                  <Tag theme={row.status.theme as any} variant="light">
                    {row.status.label}
                  </Tag>
                </Space>
                <Typography.Text theme="secondary">{businessCapabilityGroupHint(row.businessKey)}</Typography.Text>
                <Typography.Text code>{businessApiEntryPath(row.businessKey)}</Typography.Text>
              </div>
              <div className="podi-business-command-cell">
                <Typography.Text strong>{businessCapabilityVersionRoleLabel(row.defaultItem)}</Typography.Text>
                <Typography.Text theme="secondary">
                  发布：{row.defaultItem ? formatDateTime(row.defaultItem.releaseTime || row.defaultItem.createdAt) : '—'}
                </Typography.Text>
                {row.defaultItem ? (
                  <Typography.Text theme="secondary">内部版本：{row.defaultItem.version}</Typography.Text>
                ) : null}
                <Space size={6} breakLine>
                  <Tag theme={row.defaultItem?.status === 'active' ? 'success' : 'default'} variant="light" size="small">
                    启用 {row.activeCount}/{row.items.length}
                  </Tag>
                  <Tag variant="light" size="small">
                    {row.defaultItem ? businessCapabilityMediaLabel(row.defaultItem) : '缺输出定义'}
                  </Tag>
                </Space>
              </div>
              <div className="podi-business-command-cell">
                <div className="podi-business-command-metrics">
                  <strong>{row.bucket?.total || 0}</strong>
                  <span>成功 {row.bucket?.succeeded || 0}</span>
                  <span>{Number(row.unresolvedBucket?.total || 0) > 0 ? `未恢复 ${row.unresolvedBucket?.total || 0}` : `历史失败 ${row.bucket?.failed || 0}`}</span>
                  <span>排队/运行 {runningCount}</span>
                </div>
                <Typography.Text theme="secondary">成功率 {formatRatePercent(row.bucket?.successRate)}</Typography.Text>
              </div>
              <div className="podi-business-command-cell">
                <Space align="center" size={6} style={{ flexWrap: 'wrap' }}>
                  {row.defaultItem?.latestRun ? <StatusBadge status={row.defaultItem.latestRun.status} /> : null}
                  <Typography.Text theme={row.defaultItem?.latestRun?.error ? 'error' : 'secondary'}>
                    {row.defaultItem ? businessCapabilityLatestRunLabel(row.defaultItem) : '暂无真实样本'}
                  </Typography.Text>
                </Space>
                <Typography.Text theme="secondary">
                  {row.defaultItem?.latestRun
                    ? formatDateTime(row.defaultItem.latestRun.finishedAt || row.defaultItem.latestRun.createdAt)
                    : '还没有真实运行记录'}
                </Typography.Text>
              </div>
              <div className="podi-business-command-cell">
                <Typography.Text theme={row.status.theme === 'danger' ? 'error' : row.status.theme === 'warning' ? 'warning' : 'secondary'}>
                  {row.status.detail}
                </Typography.Text>
                <Typography.Text theme="secondary">{row.suggestion}</Typography.Text>
              </div>
            </section>
          );
        })}
      </div>
    </Card>
  );
};

export const BusinessCoreClosurePanel = ({
  capabilities,
  pendingApprovals,
  summary,
  formatDateTime,
  capabilitiesLoading = false,
}: {
  capabilities: BusinessCapability[];
  pendingApprovals: BusinessDefaultApproval[];
  summary?: BusinessUsageSummaryResponse | null;
  formatDateTime: (value?: string | null) => string;
  capabilitiesLoading?: boolean;
}) => {
  if (capabilitiesLoading && capabilities.length === 0) {
    return (
      <Card bordered className="podi-business-closure-card" title="核心能力决策总表">
        <Alert theme="info" message="业务版本数据还在加载中，请等待接口返回后再查看线上可用、生产推荐和回滚安全垫。" />
      </Card>
    );
  }

  const rows = buildCoreBusinessReleaseEvidenceRows({ capabilities, pendingApprovals, summary });

  return (
    <Card
      bordered
      className="podi-business-closure-card"
      title={
        <Space align="center" style={{ justifyContent: 'space-between', width: '100%', flexWrap: 'wrap' }}>
          <div>
            <Typography.Text strong>核心能力决策总表</Typography.Text>
            <div>
              <Typography.Text theme="secondary">
                一张表分清线上可用、生产推荐、待补证据和回滚安全垫；先看这里，再进入版本卡片或运行记录。
              </Typography.Text>
            </div>
          </div>
          <Tag theme={rows.every((row) => row.theme === 'success') ? 'success' : rows.some((row) => row.theme === 'danger') ? 'danger' : 'warning'} variant="light">
            {rows.filter((row) => row.theme === 'success').length}/{rows.length} 生产推荐
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
              <Typography.Text>{businessCapabilityVersionRoleLabel(row.defaultItem)}</Typography.Text>
              {row.defaultItem ? (
                <Typography.Text theme="secondary">内部版本：{row.defaultItem.version}</Typography.Text>
              ) : null}
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

export const BusinessOrchestrationMapPanel = ({
  capabilities,
  pendingApprovals,
  summary,
  formatDateTime,
  capabilitiesLoading = false,
  isReadOnly = false,
  actionLoadingId,
  abilityOptions,
  vlAbilityOptions,
  onCreateDraft,
  onSaveDraftRecipe,
  onOpenBusinessRun,
}: {
  capabilities: BusinessCapability[];
  pendingApprovals: BusinessDefaultApproval[];
  summary?: BusinessUsageSummaryResponse | null;
  formatDateTime: (value?: string | null) => string;
  capabilitiesLoading?: boolean;
  isReadOnly?: boolean;
  actionLoadingId?: string | null;
  abilityOptions: BusinessSelectOption[];
  vlAbilityOptions: BusinessSelectOption[];
  onCreateDraft?: (item: BusinessCapability) => Promise<BusinessCapability | null>;
  onSaveDraftRecipe?: (
    item: BusinessCapability,
    payload: { recipe: Record<string, unknown>; primaryAbilityId?: string | null; note?: string | null },
  ) => Promise<BusinessCapability | null>;
  onOpenBusinessRun?: (runId: string) => void;
}) => {
  const [selectedBusinessKey, setSelectedBusinessKey] = useState<(typeof businessOrchestrationKeys)[number]>('fission');
  const [selectedCapabilityIds, setSelectedCapabilityIds] = useState<Record<string, string>>({});
  const [draftEditorTarget, setDraftEditorTarget] = useState<BusinessCapability | null>(null);
  const [draftEditorForm, setDraftEditorForm] = useState<BusinessCapabilityFormState | null>(null);
  const [draftEditorError, setDraftEditorError] = useState<string | null>(null);
  if (capabilitiesLoading && capabilities.length === 0) {
    return (
      <Card
        bordered
        className="podi-business-workflow-map-card"
        title={
          <Space align="center" style={{ justifyContent: 'space-between', width: '100%', flexWrap: 'wrap' }}>
            <div>
              <Typography.Text strong>业务链路图</Typography.Text>
              <div>
                <Typography.Text theme="secondary">正在读取业务版本和编排链路，避免把加载中误判成“缺默认入口”。</Typography.Text>
              </div>
            </div>
            <Tag theme="primary" variant="light">
              加载中
            </Tag>
          </Space>
        }
      >
        <Alert theme="info" message="业务版本数据还在加载中，请稍等几秒；加载完成后再显示默认版本、版本族和处理链路。" />
      </Card>
    );
  }
  const rows = businessOrchestrationKeys.map((businessKey) => {
    const items = capabilities
      .filter((item) => canonicalBusinessKey(item.businessKey) === businessKey)
      .slice()
      .sort((left, right) => {
        if (left.isDefault !== right.isDefault) return left.isDefault ? -1 : 1;
        if (left.status !== right.status) return left.status === 'active' ? -1 : 1;
        const lineDiff = businessCapabilityVersionLine(left).priority - businessCapabilityVersionLine(right).priority;
        if (lineDiff !== 0) return lineDiff;
        return String(right.releaseTime || right.updatedAt || right.createdAt || '').localeCompare(
          String(left.releaseTime || left.updatedAt || left.createdAt || ''),
        );
      });
    const defaultItem = items.find((item) => item.isDefault);
    const activeAlternatives = items.filter((item) => item.status === 'active' && !item.isDefault);
    const rollbackReadyAlternatives = activeAlternatives.filter(businessCapabilityHasRollbackEvidence);
    const hasPendingApproval = pendingApprovals.some(
      (item) => canonicalBusinessKey(item.businessKey) === businessKey && item.status === 'pending',
    );
    const rollout = readCapabilityRollout(defaultItem?.metadata);
    const risk = defaultItem ? businessCapabilityRiskTag(defaultItem) : { theme: 'danger', text: '缺默认入口', detail: '业务方无法稳定调用。' };
    return {
      businessKey,
      items,
      defaultItem,
      activeAlternatives,
      rollbackReadyAlternatives,
      hasPendingApproval,
      rollout,
      risk,
      usage: businessUsageBucketForKey(summary, businessKey),
      suggestion: businessCoreEntrySuggestion({
        defaultItem,
        activeCount: items.filter((item) => item.status === 'active').length,
        hasPendingApproval,
      }),
    };
  });
  const selectedRow = rows.find((row) => row.businessKey === selectedBusinessKey) || rows[0];
  const selectedVersionItems = selectedRow?.items || [];
  const selectedCapabilityId =
    selectedCapabilityIds[selectedBusinessKey] || selectedRow?.defaultItem?.id || selectedVersionItems[0]?.id || '';
  const selectedCapability =
    selectedVersionItems.find((item) => item.id === selectedCapabilityId) ||
    selectedRow?.defaultItem ||
    selectedVersionItems[0] ||
    null;
  const selectedCapabilityLine = businessCapabilityVersionLine(selectedCapability);
  const selectedCapabilityLineage = businessCapabilityVersionLineage(selectedCapability);
  const selectedCapabilityRisk = selectedCapability
    ? businessCapabilityRiskTag(selectedCapability)
    : selectedRow?.risk || { theme: 'danger', text: '缺默认入口', detail: '业务方无法稳定调用。' };
  const selectedCapabilityRollout = readCapabilityRollout(selectedCapability?.metadata);
  const selectedCapabilityRelation = selectedCapability
    ? businessCapabilityVersionRelationLabel(selectedCapability, selectedVersionItems)
    : '还没有可查看的业务版本。';
  const openDraftEditor = (item: BusinessCapability) => {
    setDraftEditorTarget(item);
    setDraftEditorForm(createBusinessCapabilityFormState(item));
    setDraftEditorError(null);
  };
  const createDraftAndEdit = async (item: BusinessCapability) => {
    if (!onCreateDraft) return;
    const draft = await onCreateDraft(item);
    if (!draft) return;
    setSelectedCapabilityIds((prev) => ({ ...prev, [canonicalBusinessKey(draft.businessKey)]: draft.id }));
    openDraftEditor(draft);
  };
  const saveDraftRecipe = async () => {
    if (!draftEditorTarget || !draftEditorForm || !onSaveDraftRecipe) return;
    const parsed = parseBusinessDraftRecipe(draftEditorForm.recipeText);
    if (!parsed.ok) {
      setDraftEditorError(parsed.error);
      return;
    }
    const steps = Array.isArray(parsed.recipe.steps) ? parsed.recipe.steps : [];
    if (steps.length === 0) {
      setDraftEditorError('草稿配方至少需要一个可执行步骤。');
      return;
    }
    const saved = await onSaveDraftRecipe(draftEditorTarget, {
      recipe: parsed.recipe,
      primaryAbilityId: draftEditorForm.primaryAbilityId || null,
      note: '在业务链路图中调整草稿配方。',
    });
    if (!saved) return;
    setSelectedCapabilityIds((prev) => ({ ...prev, [canonicalBusinessKey(saved.businessKey)]: saved.id }));
    setDraftEditorTarget(null);
    setDraftEditorForm(null);
    setDraftEditorError(null);
  };
  const draftEditorBusy = Boolean(draftEditorTarget && actionLoadingId === `save-draft-recipe:${draftEditorTarget.id}`);

  return (
    <>
      <Card
        bordered
        className="podi-business-workflow-map-card"
        title={
          <Space align="center" style={{ justifyContent: 'space-between', width: '100%', flexWrap: 'wrap' }}>
            <div>
              <Typography.Text strong>业务链路图</Typography.Text>
              <div>
                <Typography.Text theme="secondary">
                  只看当前选中业务的编排链路。入口状态、调用次数和接口问题回到“业务调用”查看。
                </Typography.Text>
              </div>
            </div>
            <Tag theme="primary" variant="light">
              组件化编排视角
            </Tag>
          </Space>
        }
      >
      <Space direction="vertical" size="small" style={{ width: '100%' }}>
        <div className="podi-business-workflow-map-hint">
          一条业务调用只对应一个 runId；图片理解、生图、评分、回填都挂在这条业务链下面。
        </div>
        <div className="podi-business-workflow-switcher">
          {rows.map((row) => (
            <button
              key={row.businessKey}
              className={`podi-business-workflow-switcher__item ${row.businessKey === selectedRow.businessKey ? 'is-active' : ''}`}
              type="button"
              onClick={() => setSelectedBusinessKey(row.businessKey)}
            >
              <Space size={6} breakLine>
                <Typography.Text strong>{businessKeyLabel(row.businessKey)}</Typography.Text>
                <Tag theme={row.risk.theme as any} variant="light" size="small">
                  {row.risk.text}
                </Tag>
              </Space>
              <Typography.Text theme="secondary">{businessUsageDigest(summary, row.businessKey)}</Typography.Text>
              <Typography.Text theme="secondary">
                {row.defaultItem
                  ? `默认走：${businessCapabilityVersionLine(row.defaultItem).label} · 版本 ${row.defaultItem.version}`
                  : '未设置默认版本'}
              </Typography.Text>
            </button>
          ))}
        </div>
        {selectedRow ? (
          <section className="podi-business-workflow-focus">
            <aside className="podi-business-workflow-focus__summary">
              <Space direction="vertical" size={8} style={{ width: '100%' }}>
                <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
                  <Typography.Text strong>{businessKeyLabel(selectedRow.businessKey)}</Typography.Text>
                  <Tag theme={selectedRow.risk.theme as any} variant="light">
                    {selectedRow.risk.text}
                  </Tag>
                </Space>
                <Typography.Text theme="secondary">{businessCapabilityGroupHint(selectedRow.businessKey)}</Typography.Text>
                <div className="podi-business-workflow-focus__block">
                  <Typography.Text theme="secondary">业务入口</Typography.Text>
                  <Typography.Text code>{businessApiEntryPath(selectedRow.businessKey)}</Typography.Text>
                  <Typography.Text theme="secondary">{businessEntryUsageHint(selectedRow.businessKey)}</Typography.Text>
                </div>
                <div className="podi-business-workflow-focus__block">
                  <Tag theme={selectedCapability?.status === 'active' ? 'success' : 'warning'} variant="light">
                    查看版本
                  </Tag>
                  <Typography.Text theme="secondary">选择一个版本查看它的处理链路。</Typography.Text>
                  <Select
                    value={selectedCapability?.id || ''}
                    options={selectedVersionItems.map((item) => ({
                      label: businessCapabilityVersionOptionLabel(item),
                      value: item.id,
                    }))}
                    onChange={(value) =>
                      setSelectedCapabilityIds((prev) => ({ ...prev, [selectedBusinessKey]: String(value) }))
                    }
                  />
                  <Typography.Text theme="secondary">
                    版本族：{selectedCapability ? selectedCapabilityLine.label : '未设置'}
                  </Typography.Text>
                  <Typography.Text strong>{businessCapabilityVersionRoleLabel(selectedCapability)}</Typography.Text>
                  {selectedCapability ? (
                    <Typography.Text theme="secondary">
                      内部版本：{selectedCapability.version}
                    </Typography.Text>
                  ) : null}
                  {selectedCapability?.displayName ? (
                    <Typography.Text theme="secondary">技术说明：{selectedCapability.displayName}</Typography.Text>
                  ) : null}
                  <Typography.Text theme="secondary">
                    发布：{selectedCapability ? formatDateTime(selectedCapability.releaseTime || selectedCapability.createdAt) : '—'}
                  </Typography.Text>
                  <Typography.Text theme="secondary">
                    更新：{selectedCapability ? formatDateTime(selectedCapability.updatedAt || selectedCapability.releaseTime || selectedCapability.createdAt) : '—'}
                  </Typography.Text>
                  <Typography.Text theme="secondary">{selectedCapabilityRelation}</Typography.Text>
                  {selectedCapabilityLineage.changeSummary ? (
                    <Typography.Text theme="secondary">更新说明：{selectedCapabilityLineage.changeSummary}</Typography.Text>
                  ) : null}
                </div>
                <Space size={6} breakLine>
                  <Tag theme={selectedRow.usage?.failed ? 'warning' : 'default'} variant="light">
                    {businessUsageDigest(summary, selectedRow.businessKey)}
                  </Tag>
                  <Tag theme={selectedCapabilityRollout.enabled ? 'warning' : 'default'} variant="light">
                    灰度 {selectedCapabilityRollout.enabled ? `${selectedCapabilityRollout.percent}%` : '关闭'}
                  </Tag>
                  <Tag theme={selectedRow.rollbackReadyAlternatives.length > 0 ? 'success' : 'warning'} variant="light">
                    {selectedRow.rollbackReadyAlternatives.length > 0
                      ? `可回滚 ${selectedRow.rollbackReadyAlternatives.length}`
                      : `备选 ${selectedRow.activeAlternatives.length}`}
                  </Tag>
                  {selectedRow.hasPendingApproval ? <Tag theme="warning" variant="light">切换审批中</Tag> : null}
                </Space>
                <Typography.Text
                  theme={selectedCapabilityRisk.theme === 'danger' ? 'error' : selectedCapabilityRisk.theme === 'warning' ? 'warning' : 'secondary'}
                >
                  {selectedCapabilityRisk.detail || selectedRow.suggestion}
                </Typography.Text>
                {selectedCapability ? (
                  <div className="podi-business-workflow-focus__block">
                    <Typography.Text theme="secondary">编排修改</Typography.Text>
                    {selectedCapability.status === 'draft' ? (
                      <>
                        <Alert theme="success" message="当前是草稿版本，可以在这里调整步骤和能力绑定；保存后不会影响线上默认版本。" />
                        <Button
                          theme="primary"
                          variant="outline"
                          disabled={isReadOnly}
                          onClick={() => openDraftEditor(selectedCapability)}
                        >
                          编辑草稿步骤
                        </Button>
                      </>
                    ) : (
                      <>
                        <Alert theme="info" message="当前版本只读。要改编排，先复制为草稿，试运行和验收通过后再申请切默认。" />
                        <Button
                          theme="primary"
                          variant="outline"
                          loading={actionLoadingId === `create-draft:${selectedCapability.id}`}
                          disabled={isReadOnly || !onCreateDraft || Boolean(actionLoadingId)}
                          onClick={() => {
                            void createDraftAndEdit(selectedCapability);
                          }}
                        >
                          复制为草稿并编辑
                        </Button>
                      </>
                    )}
                  </div>
                ) : null}
              </Space>
            </aside>
            <div className="podi-business-workflow-focus__canvas">
              <div className="podi-business-workflow-focus__canvas-head">
                <Space size={6} breakLine>
                  <Tag theme="primary" variant="light">
                    处理链路
                  </Tag>
                  <Tag variant="light">
                    版本族：{selectedCapability ? selectedCapabilityLine.label : '未设置'}
                  </Tag>
                  <Tag variant="light">主执行：{businessCapabilityEngineLabel(selectedCapability)}</Tag>
                  <Tag theme={selectedCapabilityRisk.theme as any} variant="light">
                    最近：{selectedCapability ? businessCapabilityLatestRunLabel(selectedCapability) : '无运行记录'}
                  </Tag>
                </Space>
                <Space size={6} breakLine>
                  {selectedCapability?.isDefault ? (
                    <Tag theme="success" variant="light" size="small">
                      当前默认
                    </Tag>
                  ) : null}
                  {selectedVersionItems.slice(0, 5).map((item) => (
                    <Tag
                      key={item.id}
                      theme={item.id === selectedCapability?.id ? 'primary' : (businessCapabilityVersionLine(item).theme as any)}
                      variant="light"
                      size="small"
                      title={businessCapabilityVersionOptionLabel(item)}
                    >
                      {item.isDefault ? '线上默认' : businessCapabilityVersionLine(item).label}
                    </Tag>
                  ))}
                  {selectedVersionItems.length > 5 ? <Tag variant="light" size="small">+{selectedVersionItems.length - 5}</Tag> : null}
                </Space>
              </div>
              <BusinessOrchestrationGraphView
                graph={selectedCapability?.orchestrationGraph}
                fallbackSteps={selectedCapability?.recipeSteps || []}
                formatDateTime={formatDateTime}
                onOpenBusinessRun={onOpenBusinessRun}
              />
            </div>
          </section>
        ) : null}
      </Space>
      </Card>
      <Dialog
        visible={Boolean(draftEditorTarget && draftEditorForm)}
        header={draftEditorTarget ? `编辑草稿编排：${draftEditorTarget.displayName}` : '编辑草稿编排'}
        width={980}
        onClose={() => {
          setDraftEditorTarget(null);
          setDraftEditorForm(null);
          setDraftEditorError(null);
        }}
        onConfirm={() => {
          void saveDraftRecipe();
        }}
        confirmBtn={draftEditorBusy ? '保存中...' : '保存草稿配方'}
        cancelBtn="取消"
      >
        <Space direction="vertical" size="small" style={{ width: '100%' }}>
          {draftEditorError ? <Alert theme="error" message={draftEditorError} /> : null}
          <Alert
            theme="info"
            message="这里只改草稿版本的步骤和能力绑定。保存后先试运行，再记录验收；不会直接影响业务方正在调用的默认版本。"
          />
          {draftEditorForm ? (
            <BusinessRecipeDraftEditor
              form={draftEditorForm}
              abilityOptions={abilityOptions}
              vlAbilityOptions={vlAbilityOptions}
              disabled={draftEditorBusy}
              onChange={(next) => {
                setDraftEditorForm(next);
                setDraftEditorError(null);
              }}
            />
          ) : null}
        </Space>
      </Dialog>
    </>
  );
};

const businessCapabilityGroupSortValue = (businessKey?: string | null) => {
  const index = coreBusinessKeys.indexOf(canonicalBusinessKey(businessKey) as (typeof coreBusinessKeys)[number]);
  return index >= 0 ? index : coreBusinessKeys.length;
};

const businessReleaseGateIssueLabel = (value?: string | null) => {
  const labels: Record<string, string> = {
    BUSINESS_RELEASE_VERSION_INACTIVE: '业务版本未启用',
    BUSINESS_RELEASE_PRIMARY_ABILITY_REQUIRED: '未绑定真实主能力',
    BUSINESS_RELEASE_GOVERNANCE_BLOCKED: '底层能力或模型治理未通过',
    BUSINESS_RELEASE_GOVERNANCE_WARNING: '底层治理信息需要补齐',
    BUSINESS_RELEASE_ACCEPTANCE_REQUIRED: '缺少真实链路验收记录',
    BUSINESS_RELEASE_QUALITY_REVIEW_REQUIRED: '缺少出图质量标注',
    BUSINESS_RELEASE_QUALITY_REVIEW_POSITIVE_REQUIRED: '缺少可用/优秀样本',
    BUSINESS_RELEASE_QUALITY_REVIEW_RISKY: '质量样本有风险',
    BUSINESS_RELEASE_LATEST_RUN_FAILED: '最近一次运行失败',
    BUSINESS_RELEASE_RECENT_FAILURES: '近期存在失败样本',
  };
  return labels[value || ''] || value || '';
};

const businessEvidenceOnlyReleaseBlockers = new Set([
  'BUSINESS_RELEASE_ACCEPTANCE_REQUIRED',
  'BUSINESS_RELEASE_QUALITY_REVIEW_REQUIRED',
  'BUSINESS_RELEASE_QUALITY_REVIEW_POSITIVE_REQUIRED',
  'BUSINESS_RELEASE_QUALITY_REVIEW_RISKY',
]);

const businessReleaseGateBlockerCodes = (releaseGate?: BusinessReleaseGate | null) =>
  (releaseGate?.blockers || []).map((code) => String(code || '')).filter(Boolean);

const businessReleaseGateHasOnlyEvidenceBlockers = (releaseGate?: BusinessReleaseGate | null) => {
  if (releaseGate?.status !== 'blocked') return false;
  const blockers = businessReleaseGateBlockerCodes(releaseGate);
  return blockers.length > 0 && blockers.every((code) => businessEvidenceOnlyReleaseBlockers.has(code));
};

const businessReleaseGateHasQualityBlocker = (releaseGate?: BusinessReleaseGate | null) =>
  (releaseGate?.blockers || []).some((code) => String(code || '').includes('QUALITY_REVIEW'));

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
  const qualityEvidence = (releaseGate?.qualityEvidence || {}) as JsonRecord;
  const qualityRequired = Boolean(qualityEvidence.required);
  const qualityReviewed = Number(qualityEvidence.reviewed || 0);
  const qualityAccepted = Number(qualityEvidence.accepted || 0);
  const qualityRisky = Number(qualityEvidence.risky || 0);
  const qualityStatus = String(qualityEvidence.status || '');
  const qualityTheme =
    qualityStatus === 'ready' ? 'success' : qualityStatus === 'warning' ? 'warning' : qualityRequired ? 'danger' : 'default';
  const latestRun = item.latestRun;
  const outputCount = Number(latestRun?.imageCount || latestRun?.image_count || 0) + Number(latestRun?.videoCount || latestRun?.video_count || 0);
  const lifecycle = businessCapabilityLifecycleStatus(item, {
    outputCount,
    acceptancePassed: releaseGate?.acceptancePassed === true || latestAcceptance?.status === 'passed',
    releaseGateBlocked: releaseGate?.status === 'blocked',
    governanceBlocked: item.governanceStatus === 'blocker',
    runFailed: Boolean(latestRun?.error),
  });
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
          <Space size={4}>
            <Tag theme={lifecycle.online.theme} variant="light">
              {lifecycle.online.label}
            </Tag>
            <Tag theme={lifecycle.recommendation.theme} variant="light">
              {lifecycle.recommendation.label}
            </Tag>
          </Space>
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
          <Tag theme={qualityTheme as any} variant="light" size="small">
            {qualityEvidence.label ? String(qualityEvidence.label) : qualityRequired ? '缺少质量复盘' : '质量非强制'}
          </Tag>
          <Typography.Text theme="secondary">
            标注 {qualityReviewed} · 可用 {qualityAccepted} · 风险 {qualityRisky}
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
          <Typography.Text theme="secondary">暂无门禁阻塞；发版前仍需保留一次真实链路验收记录。</Typography.Text>
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
        {(item.orchestrationGraph || (item.recipeSteps && item.recipeSteps.length > 0)) ? (
          <div>
            <Typography.Text theme="secondary">业务编排</Typography.Text>
            <div style={{ marginTop: 8 }}>
              <BusinessOrchestrationGraphView
                graph={item.orchestrationGraph}
                fallbackSteps={item.recipeSteps}
                compact
              />
            </div>
          </div>
        ) : null}
      </div>
    </details>
  );
}

type BusinessAbilityGovernanceRow = {
  businessKey: string;
  items: BusinessCapability[];
  defaultItem?: BusinessCapability;
  activeCount: number;
  candidateCount: number;
  rollbackReadyCount: number;
  hasPendingApproval: boolean;
  bucket?: ReturnType<typeof businessUsageBucketForKey>;
  unresolvedBucket?: ReturnType<typeof businessUnresolvedBucketForKey>;
  quality?: BusinessOutputReviewSummaryResponse['byBusiness'][number];
  status: {
    theme: 'success' | 'warning' | 'danger' | 'default';
    label: string;
    detail: string;
    action: string;
  };
};

const businessQualitySummaryForKey = (
  qualitySummary: BusinessOutputReviewSummaryResponse | null | undefined,
  businessKey: string,
) => qualitySummary?.byBusiness?.find((item) => canonicalBusinessKey(item.businessKey) === canonicalBusinessKey(businessKey));

const businessAbilityGovernanceStatus = ({
  defaultItem,
  activeCount,
  candidateCount,
  rollbackReadyCount,
  hasPendingApproval,
  bucket,
  unresolvedBucket,
  quality,
}: {
  defaultItem?: BusinessCapability;
  activeCount: number;
  candidateCount: number;
  rollbackReadyCount: number;
  hasPendingApproval: boolean;
  bucket?: ReturnType<typeof businessUsageBucketForKey>;
  unresolvedBucket?: ReturnType<typeof businessUnresolvedBucketForKey>;
  quality?: BusinessOutputReviewSummaryResponse['byBusiness'][number];
}): BusinessAbilityGovernanceRow['status'] => {
  const unresolvedCount = Number(unresolvedBucket?.total || 0);
  const qualityRiskCount = Number(quality?.borderline || 0) + Number(quality?.bad || 0) + Number(quality?.blocked || 0);
  const latestRunSucceeded = String(defaultItem?.latestRun?.status || '').toLowerCase() === 'succeeded' && !defaultItem?.latestRun?.error;
  const hasOutput =
    Number(defaultItem?.latestRun?.imageCount || defaultItem?.latestRun?.image_count || 0) +
      Number(defaultItem?.latestRun?.videoCount || defaultItem?.latestRun?.video_count || 0) +
      Number(defaultItem?.latestRun?.textCount || defaultItem?.latestRun?.text_count || 0) >
    0;
  const evidenceOnlyBlocked = Boolean(latestRunSucceeded && hasOutput && businessReleaseGateHasOnlyEvidenceBlockers(defaultItem?.releaseGate));
  if (!defaultItem) {
    return {
      theme: 'danger',
      label: '缺默认能力',
      detail: '客户端和业务方没有稳定入口。',
      action: '先创建或指定一个 active 默认版本。',
    };
  }
  if (defaultItem.status !== 'active') {
    return {
      theme: 'danger',
      label: '默认未启用',
      detail: '默认版本不会承接新的业务请求。',
      action: '启用默认版本，或切换到可用版本。',
    };
  }
  if (!defaultItem.primaryAbilityId && !defaultItem.primaryAbilityName) {
    return {
      theme: 'danger',
      label: '缺执行能力',
      detail: '业务能力没有绑定底层原子能力。',
      action: '先补主执行能力和配方，再跑验收。',
    };
  }
  if (defaultItem.releaseGate?.status === 'blocked' && evidenceOnlyBlocked) {
    const blockers = businessReleaseGateBlockerCodes(defaultItem.releaseGate);
    const qualityOnly = blockers.length > 0 && blockers.every((code) => code.includes('QUALITY_REVIEW'));
    return {
      theme: 'warning',
      label: qualityOnly ? '待补质量' : '待补验收',
      detail: qualityOnly ? '线上已跑通，但缺少质量标注证据。' : '线上已跑通，但还缺验收通过记录。',
      action: qualityOnly ? '补一张可用质量标注，再作为生产推荐。' : '记录真实链路验收通过，再作为封版证据。',
    };
  }
  if (defaultItem.governanceStatus === 'blocker' || defaultItem.releaseGate?.status === 'blocked') {
    return {
      theme: 'danger',
      label: '门禁阻塞',
      detail: defaultItem.releaseGate?.suggestions?.[0] || defaultItem.governanceSuggestions?.[0] || '底层能力或上线门禁未通过。',
      action: '先补验收、密钥、模型或质量证据。',
    };
  }
  if (unresolvedCount > 0 || defaultItem.latestRun?.error) {
    return {
      theme: 'warning',
      label: '调用需复核',
      detail: unresolvedCount > 0 ? `${unresolvedCount} 条问题未被后续成功覆盖。` : '最近一次真实调用失败。',
      action: '下钻到业务调用，按 runId 看失败步骤。',
    };
  }
  if (qualityRiskCount > 0) {
    return {
      theme: 'warning',
      label: '质量需优化',
      detail: `质量复盘中有 ${qualityRiskCount} 条边界/差样本。`,
      action: '进入质量样例，决定分流、换模型、换 LoRA 或调参数。',
    };
  }
  if (Number(bucket?.callbackFailed || 0) > 0) {
    return {
      theme: 'warning',
      label: '回填风险',
      detail: '生成可能成功，但结果回填给业务方有失败样本。',
      action: '先处理回填失败，再对外承诺稳定。',
    };
  }
  if (defaultItem.modelCostConfigured === false || Number(bucket?.unpriced || 0) > 0) {
    return {
      theme: 'warning',
      label: '成本未齐',
      detail: '能力可跑，但成本口径不完整。',
      action: '补模型计价和业务成本映射。',
    };
  }
  if (hasPendingApproval) {
    return {
      theme: 'warning',
      label: '默认切换中',
      detail: '存在默认版本审批，线上口径还不能按新版本说明。',
      action: '先完成审批或撤回切换。',
    };
  }
  if (candidateCount === 0 || rollbackReadyCount === 0 || activeCount < 2) {
    return {
      theme: 'warning',
      label: '安全垫不足',
      detail: '默认版本可用，但缺少通过验收的灰度或回滚备选。',
      action: '不阻塞当前调用；放量或封版前补一个可回滚版本。',
    };
  }
  return {
    theme: 'success',
    label: '生产推荐',
    detail: '线上默认、调用、质量和回滚安全垫均有基本证据。',
    action: '继续按样例和真实调用小步优化。',
  };
};

const buildBusinessAbilityGovernanceRows = ({
  capabilities,
  pendingApprovals,
  summary,
  qualitySummary,
}: {
  capabilities: BusinessCapability[];
  pendingApprovals: BusinessDefaultApproval[];
  summary?: BusinessUsageSummaryResponse | null;
  qualitySummary?: BusinessOutputReviewSummaryResponse | null;
}): BusinessAbilityGovernanceRow[] => {
  const keySet = new Set<string>();
  businessOrchestrationKeys.forEach((key) => keySet.add(key));
  capabilities.forEach((item) => {
    const key = canonicalBusinessKey(item.businessKey);
    if (key) keySet.add(key);
  });
  (summary?.byBusiness || []).forEach((item) => {
    const key = canonicalBusinessKey(item.key);
    if (key) keySet.add(key);
  });
  (qualitySummary?.byBusiness || []).forEach((item) => {
    const key = canonicalBusinessKey(item.businessKey);
    if (key) keySet.add(key);
  });

  return Array.from(keySet)
    .sort((left, right) => {
      const diff = businessCapabilityGroupSortValue(left) - businessCapabilityGroupSortValue(right);
      return diff !== 0 ? diff : businessKeyLabel(left).localeCompare(businessKeyLabel(right));
    })
    .map((businessKey) => {
      const items = capabilities
        .filter((item) => canonicalBusinessKey(item.businessKey) === businessKey)
        .slice()
        .sort((left, right) => {
          if (left.isDefault !== right.isDefault) return left.isDefault ? -1 : 1;
          if (left.status !== right.status) return left.status === 'active' ? -1 : 1;
          const lineDiff = businessCapabilityVersionLine(left).priority - businessCapabilityVersionLine(right).priority;
          if (lineDiff !== 0) return lineDiff;
          return String(right.releaseTime || right.updatedAt || right.createdAt || '').localeCompare(
            String(left.releaseTime || left.updatedAt || left.createdAt || ''),
          );
        });
      const defaultItem = items.find((item) => item.isDefault);
      const activeItems = items.filter((item) => item.status === 'active');
      const candidateCount = activeItems.filter((item) => !item.isDefault).length;
      const rollbackReadyCount = activeItems.filter((item) => !item.isDefault && businessCapabilityHasRollbackEvidence(item)).length;
      const bucket = businessUsageBucketForKey(summary, businessKey);
      const unresolvedBucket = businessUnresolvedBucketForKey(summary, businessKey);
      const quality = businessQualitySummaryForKey(qualitySummary, businessKey);
      const hasPendingApproval = pendingApprovals.some(
        (item) => canonicalBusinessKey(item.businessKey) === businessKey && item.status === 'pending',
      );
      return {
        businessKey,
        items,
        defaultItem,
        activeCount: activeItems.length,
        candidateCount,
        rollbackReadyCount,
        hasPendingApproval,
        bucket,
        unresolvedBucket,
        quality,
        status: businessAbilityGovernanceStatus({
          defaultItem,
          activeCount: activeItems.length,
          candidateCount,
          rollbackReadyCount,
          hasPendingApproval,
          bucket,
          unresolvedBucket,
          quality,
        }),
      };
    });
};

export const BusinessAbilityGovernancePanel = ({
  capabilities,
  pendingApprovals,
  summary,
  qualitySummary,
  formatDateTime,
  capabilitiesLoading = false,
}: {
  capabilities: BusinessCapability[];
  pendingApprovals: BusinessDefaultApproval[];
  summary?: BusinessUsageSummaryResponse | null;
  qualitySummary?: BusinessOutputReviewSummaryResponse | null;
  formatDateTime: (value?: string | null) => string;
  capabilitiesLoading?: boolean;
}) => {
  const rows = useMemo(
    () => buildBusinessAbilityGovernanceRows({ capabilities, pendingApprovals, summary, qualitySummary }),
    [capabilities, pendingApprovals, summary, qualitySummary],
  );
  if (capabilitiesLoading && capabilities.length === 0) {
    return (
      <Card bordered title="能力治理总览">
        <Alert theme="info" message="业务能力数据还在加载中，暂不展示默认版本结论，避免把加载中误判成缺默认入口。" />
      </Card>
    );
  }

  const blockedCount = rows.filter((row) => row.status.theme === 'danger').length;
  const warningCount = rows.filter((row) => row.status.theme === 'warning').length;
  const readyCount = rows.filter((row) => row.status.theme === 'success').length;
  const totalCalls = rows.reduce((total, row) => total + Number(row.bucket?.total || 0), 0);
  const totalFailures = rows.reduce((total, row) => total + Number(row.bucket?.failed || 0), 0);
  const totalQualityRisk = rows.reduce(
    (total, row) => total + Number(row.quality?.borderline || 0) + Number(row.quality?.bad || 0) + Number(row.quality?.blocked || 0),
    0,
  );
  const windowHours = Number(summary?.windowHours || 24);

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Card
        bordered
        title={
          <Space align="center" style={{ justifyContent: 'space-between', width: '100%', flexWrap: 'wrap' }}>
            <div>
              <Typography.Text strong>能力治理总览</Typography.Text>
              <div>
                <Typography.Text theme="secondary">
                  先按能力判断版本、路由、质量、成本、回滚和下一步动作；运行证据只作为下钻。
                </Typography.Text>
              </div>
            </div>
            <Tag theme={blockedCount > 0 ? 'danger' : warningCount > 0 ? 'warning' : 'success'} variant="light">
              {readyCount}/{rows.length} 生产推荐
            </Tag>
          </Space>
        }
      >
        <Row gutter={[12, 12]}>
          <Col xs={12} sm={6} lg={3}>
            <BusinessMetricCard label="纳管能力" value={rows.length} sub={`默认缺失 ${rows.filter((row) => !row.defaultItem).length}`} />
          </Col>
          <Col xs={12} sm={6} lg={3}>
            <BusinessMetricCard label="阻塞 / 需复核" value={`${blockedCount} / ${warningCount}`} sub="按能力聚合" />
          </Col>
          <Col xs={12} sm={6} lg={3}>
            <BusinessMetricCard label={`近 ${windowHours}h 调用`} value={totalCalls} sub={`失败 ${totalFailures}`} />
          </Col>
          <Col xs={12} sm={6} lg={3}>
            <BusinessMetricCard label="质量风险" value={totalQualityRisk} sub={`已标注 ${qualitySummary?.total || 0}`} />
          </Col>
        </Row>
        {rows.length === 0 ? (
          <Alert theme="warning" style={{ marginTop: 12 }} message="当前没有业务能力版本数据，请先进入版本管理新增业务能力。" />
        ) : null}
      </Card>

      <Card bordered>
        <Table
          size="small"
          rowKey="businessKey"
          data={rows}
          columns={[
            {
              colKey: 'ability',
              title: '能力',
              minWidth: 260,
              cell: ({ row }) => (
                <Space direction="vertical" size={2}>
                  <Space size={6} breakLine>
                    <Typography.Text strong>{businessKeyLabel(row.businessKey)}</Typography.Text>
                    <Tag theme={row.status.theme as any} variant="light">
                      {row.status.label}
                    </Tag>
                  </Space>
                  <Typography.Text theme="secondary">{businessCapabilityGroupHint(row.businessKey)}</Typography.Text>
                  <Typography.Text code>{businessApiEntryPath(row.businessKey)}</Typography.Text>
                </Space>
              ),
            },
            {
              colKey: 'version',
              title: '默认与备选',
              minWidth: 260,
              cell: ({ row }) => (
                <Space direction="vertical" size={2}>
                  <Typography.Text strong>{businessCapabilityVersionRoleLabel(row.defaultItem)}</Typography.Text>
                  <Typography.Text theme="secondary">
                    {row.defaultItem ? `版本 ${row.defaultItem.version} · ${businessCapabilityMediaLabel(row.defaultItem)}` : '还没有默认版本'}
                  </Typography.Text>
                  <Space size={6} breakLine>
                    <Tag theme={row.defaultItem?.status === 'active' ? 'success' : 'default'} variant="light" size="small">
                      启用 {row.activeCount}/{row.items.length}
                    </Tag>
                    <Tag theme={row.candidateCount > 0 ? 'primary' : 'warning'} variant="light" size="small">
                      候选 {row.candidateCount}
                    </Tag>
                    <Tag theme={row.rollbackReadyCount > 0 ? 'success' : 'warning'} variant="light" size="small">
                      可回滚 {row.rollbackReadyCount}
                    </Tag>
                    {row.hasPendingApproval ? (
                      <Tag theme="warning" variant="light" size="small">
                        默认审批中
                      </Tag>
                    ) : null}
                  </Space>
                </Space>
              ),
            },
            {
              colKey: 'runtime',
              title: `近 ${windowHours}h 调用`,
              minWidth: 190,
              cell: ({ row }) => (
                <Space direction="vertical" size={2}>
                  <Typography.Text>
                    {row.bucket?.total || 0} 次 · 成功率 {formatRatePercent(row.bucket?.successRate)}
                  </Typography.Text>
                  <Typography.Text theme={Number(row.unresolvedBucket?.total || 0) > 0 ? 'warning' : 'secondary'}>
                    成功 {row.bucket?.succeeded || 0} · 失败 {row.bucket?.failed || 0} · 未恢复 {row.unresolvedBucket?.total || 0}
                  </Typography.Text>
                  <Typography.Text theme="secondary">
                    排队/运行 {Number(row.bucket?.queued || 0) + Number(row.bucket?.running || 0)}
                  </Typography.Text>
                </Space>
              ),
            },
            {
              colKey: 'qualityCost',
              title: '质量与成本',
              minWidth: 220,
              cell: ({ row }) => {
                const qualityRisk = Number(row.quality?.borderline || 0) + Number(row.quality?.bad || 0) + Number(row.quality?.blocked || 0);
                return (
                  <Space direction="vertical" size={2}>
                    <Typography.Text theme={qualityRisk > 0 ? 'warning' : 'secondary'}>
                      质量：标注 {row.quality?.reviewed || 0} · 可用 {Number(row.quality?.excellent || 0) + Number(row.quality?.usable || 0)} · 风险 {qualityRisk}
                    </Typography.Text>
                    <Typography.Text theme="secondary">成本：{formatCurrencyTotals(row.bucket?.costByCurrency)}</Typography.Text>
                    <Typography.Text theme={Number(row.bucket?.unpriced || 0) > 0 ? 'warning' : 'secondary'}>
                      未计价 {row.bucket?.unpriced || 0}
                    </Typography.Text>
                  </Space>
                );
              },
            },
            {
              colKey: 'evidence',
              title: '门禁证据',
              minWidth: 230,
              cell: ({ row }) => {
                const releaseGateDisplay = businessReleaseGateDisplay(row.defaultItem?.releaseGate);
                return (
                  <Space direction="vertical" size={2}>
                    <Space size={6} breakLine>
                      <Tag theme={releaseGateDisplay.theme} variant="light" size="small">
                        {releaseGateDisplay.label}
                      </Tag>
                    <Tag theme={businessAcceptanceStatusTheme(row.defaultItem?.latestAcceptance?.status)} variant="light" size="small">
                      {businessAcceptanceStatusLabel(row.defaultItem?.latestAcceptance?.status)}
                    </Tag>
                    </Space>
                    <Typography.Text theme={row.defaultItem?.latestRun?.error ? 'error' : 'secondary'}>
                      {row.defaultItem ? businessCapabilityLatestRunLabel(row.defaultItem) : '暂无真实样本'}
                    </Typography.Text>
                    <Typography.Text theme="secondary">
                      {row.defaultItem?.latestRun
                        ? formatDateTime(row.defaultItem.latestRun.finishedAt || row.defaultItem.latestRun.createdAt)
                        : '还没有运行证据'}
                    </Typography.Text>
                  </Space>
                );
              },
            },
            {
              colKey: 'next',
              title: '当前要做',
              minWidth: 280,
              cell: ({ row }) => (
                <Space direction="vertical" size={2}>
                  <Typography.Text theme={row.status.theme === 'danger' ? 'error' : row.status.theme === 'warning' ? 'warning' : 'secondary'}>
                    {row.status.detail}
                  </Typography.Text>
                  <Typography.Text theme="secondary">{row.status.action}</Typography.Text>
                </Space>
              ),
            },
          ]}
          empty={<Typography.Text theme="secondary">暂无业务能力治理数据。</Typography.Text>}
        />
      </Card>
    </Space>
  );
};

type BusinessFixedSamplePreset = {
  key: string;
  label: string;
  hint: string;
  prompt?: string;
  imageUrl?: string;
  generatedImageUrl?: string;
  sampleId?: string;
  source?: 'preset' | 'library';
  inputs?: Record<string, unknown>;
};

type BusinessFixedSampleBatchRow = {
  enabled: boolean;
  imageUrl: string;
  prompt: string;
  generatedImageUrl: string;
};

type BusinessDraftRunBatchRequest = {
  capability: BusinessCapability;
  payload: Record<string, unknown>;
};

type BusinessDraftRunBatchResult = {
  submitted: number;
  total: number;
  runIds: string[];
  errors: string[];
};

type BusinessFixedSampleBatchReport = BusinessDraftRunBatchResult & {
  batchId: string;
  businessKey: string;
  sampleCount: number;
  targetCount: number;
  createdAt: string;
};

const businessFixedSamplePresets = (businessKey?: string | null): BusinessFixedSamplePreset[] => {
  const key = canonicalBusinessKey(businessKey);
  if (key === 'pattern_extract') {
    return [
      { key: 'clean-pattern', label: '干净花纹', hint: '边缘干净、主体完整，检查是否有残留。' },
      { key: 'complex-background', label: '复杂背景', hint: '背景干扰明显，检查抠取和边缘脏污。' },
      { key: 'fabric-texture', label: '布料纹理', hint: '布料纹理或褶皱图，检查纹理断裂和色偏。' },
    ];
  }
  if (key === 'fission') {
    return [
      { key: 'single-subject', label: '单主体', hint: '主体清晰，检查结构是否稳定。' },
      { key: 'dense-pattern', label: '满版图案', hint: '高密度图案，检查密度变化和重复瑕疵。' },
      { key: 'color-sensitive', label: '颜色敏感', hint: '品牌色或强色块，检查色差。' },
      { key: 'complex-texture', label: '复杂纹理', hint: '复杂纹理，检查主体变形。' },
      { key: 'business-real', label: '业务真实图', hint: '线上真实样例，检查最终业务可用性。' },
    ];
  }
  if (key === 'product_design') {
    return [
      { key: 'apparel-pattern', label: '服装面料', hint: '检查图案上身比例、褶皱贴合和商业展示感。', inputs: { productType: 'apparel', scene: 'studio_product' } },
      { key: 'home-textile', label: '家纺软装', hint: '检查抱枕/床品/窗帘材质和花纹贴合。', inputs: { productType: 'home_textile', scene: 'print_mockup' } },
      { key: 'bag-mockup', label: '箱包 mockup', hint: '检查包型结构、图案裁切和边缘透视。', inputs: { productType: 'bag', scene: 'studio_product' } },
      { key: 'packaging', label: '包装设计', hint: '检查包装结构、版面清晰度和图案应用。', inputs: { productType: 'packaging', scene: 'ecommerce' } },
      { key: 'lifestyle', label: '生活方式', hint: '检查场景合理性，避免主体被弱化或过度装饰。', inputs: { productType: 'generic', scene: 'lifestyle' } },
    ];
  }
  if (key === 'image_edit') {
    return [
      { key: 'remove-object', label: '删除修补', hint: '检查局部删除后边缘和背景连贯性。', inputs: { editSkill: 'remove_object' } },
      { key: 'replace-reference', label: '参考替换', hint: '检查参考图约束和原图保留。', inputs: { editSkill: 'replace_with_reference' } },
      { key: 'color-repair', label: '补色校正', hint: '检查局部颜色是否自然。', inputs: { editSkill: 'color_repair' } },
      { key: 'canvas-outpaint', label: '扩展画布', hint: '检查扩展边缘、接缝和原图区域。', inputs: { editSkill: 'canvas_outpaint' } },
    ];
  }
  if (key === 'outpaint') {
    return [
      { key: 'all-sides', label: '四边扩展', hint: '检查四边接缝和主体比例。', inputs: { expand_left: 256, expand_right: 256, expand_top: 256, expand_bottom: 256 } },
      { key: 'single-side', label: '单边扩展', hint: '检查单侧背景延展是否穿帮。', inputs: { expand_right: 512 } },
      { key: 'wide-ratio', label: '横向扩展', hint: '检查横幅比例和主体拉伸。', inputs: { expand_left: 512, expand_right: 512 } },
      { key: 'tall-ratio', label: '纵向扩展', hint: '检查竖图比例和上下背景。', inputs: { expand_top: 512, expand_bottom: 512 } },
    ];
  }
  if (key === 'text_fission') {
    return [
      { key: 'dense-chinese', label: '中文密集', hint: '检查错字、笔画和版式漂移。' },
      { key: 'english-number', label: '英文数字', hint: '检查字母数字是否保真。' },
      { key: 'low-contrast-text', label: '低对比文字', hint: '检查低对比文字可读性。' },
    ];
  }
  return [
    { key: 'standard', label: '标准样例', hint: '覆盖常规输入。' },
    { key: 'edge', label: '边界样例', hint: '覆盖风险输入。' },
    { key: 'real', label: '业务样例', hint: '覆盖真实业务图。' },
  ];
};

const businessQualitySampleToPreset = (sample: BusinessQualitySample): BusinessFixedSamplePreset => ({
  key: sample.sampleKey || sample.id,
  label: sample.label,
  hint: sample.description || (sample.inputTags || []).join('、') || '固定样例库保存样例',
  prompt: sample.prompt || '',
  imageUrl: sample.imageUrl,
  generatedImageUrl: sample.generatedImageUrl || '',
  sampleId: sample.id,
  source: 'library',
  inputs: sample.defaultParams || {},
});

const parseBusinessQualitySampleDefaultParams = (value: unknown): JsonRecord => {
  if (!value) return {};
  if (typeof value === 'object' && !Array.isArray(value)) return value as JsonRecord;
  const text = String(value || '').trim();
  if (!text) return {};
  try {
    const parsed = JSON.parse(text);
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) return parsed as JsonRecord;
  } catch {
    throw new Error('defaultParams 必须是 JSON 对象。');
  }
  throw new Error('defaultParams 必须是 JSON 对象。');
};

const normalizeBusinessQualitySampleImportItem = (
  raw: Record<string, unknown>,
  fallbackBusinessKey?: string,
): BusinessQualitySampleImportItem => {
  const inputTags = raw.inputTags ?? raw.input_tags;
  return {
    businessKey: String(raw.businessKey ?? raw.business_key ?? fallbackBusinessKey ?? '').trim() || undefined,
    sampleKey: String(raw.sampleKey ?? raw.sample_key ?? '').trim() || undefined,
    label: String(raw.label ?? raw.name ?? '').trim() || undefined,
    description: String(raw.description ?? raw.desc ?? '').trim() || undefined,
    imageUrl: String(raw.imageUrl ?? raw.image_url ?? raw.url ?? '').trim() || undefined,
    prompt: String(raw.prompt ?? '').trim() || undefined,
    generatedImageUrl: String(raw.generatedImageUrl ?? raw.generated_image_url ?? '').trim() || undefined,
    inputTags: Array.isArray(inputTags) ? inputTags.map((item) => String(item || '').trim()).filter(Boolean) : splitBusinessOutputReviewTags(String(inputTags || '')),
    defaultParams: parseBusinessQualitySampleDefaultParams(raw.defaultParams ?? raw.default_params),
    status: String(raw.status || 'active').trim() || 'active',
    sortOrder: Number(raw.sortOrder ?? raw.sort_order ?? 0) || 0,
    changeNote: String(raw.changeNote ?? raw.change_note ?? '').trim() || undefined,
  };
};

const parseBusinessQualitySampleImportText = (
  value: string,
  fallbackBusinessKey?: string,
): BusinessQualitySampleImportItem[] => {
  const text = value.trim();
  if (!text) throw new Error('请粘贴 JSON 或 CSV 样例数据。');
  if (text.startsWith('[') || text.startsWith('{')) {
    const parsed = JSON.parse(text);
    const rawItems = Array.isArray(parsed) ? parsed : Array.isArray(parsed?.items) ? parsed.items : [];
    if (rawItems.length === 0) throw new Error('JSON 中没有 items。');
    return rawItems.map((item: unknown) => normalizeBusinessQualitySampleImportItem(item as Record<string, unknown>, fallbackBusinessKey));
  }
  const lines = text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  if (lines.length === 0) throw new Error('CSV 内容为空。');
  const firstCells = lines[0].split(/\t|,/).map((cell) => cell.trim());
  const hasHeader = firstCells.some((cell) => ['businessKey', 'business_key', 'sampleKey', 'sample_key', 'imageUrl', 'image_url'].includes(cell));
  const headers = hasHeader
    ? firstCells
    : ['businessKey', 'sampleKey', 'label', 'imageUrl', 'prompt', 'inputTags', 'defaultParams', 'status', 'sortOrder'];
  const dataLines = hasHeader ? lines.slice(1) : lines;
  return dataLines.map((line) => {
    const cells = line.split(/\t|,/);
    const row = headers.reduce<Record<string, unknown>>((map, key, index) => {
      map[key] = cells[index] || '';
      return map;
    }, {});
    return normalizeBusinessQualitySampleImportItem(row, fallbackBusinessKey);
  });
};

const businessFixedSampleOptions = (
  businessKey: string | null | undefined,
  qualitySamples: BusinessQualitySample[],
): BusinessFixedSamplePreset[] => {
  const key = canonicalBusinessKey(businessKey);
  const saved = qualitySamples
    .filter((sample) => canonicalBusinessKey(sample.businessKey) === key && sample.status !== 'archived' && sample.status !== 'inactive')
    .sort((left, right) => {
      const sortDiff = Number(left.sortOrder || 0) - Number(right.sortOrder || 0);
      if (sortDiff !== 0) return sortDiff;
      return String(right.createdAt || '').localeCompare(String(left.createdAt || ''));
    })
    .map(businessQualitySampleToPreset);
  return saved.length > 0 ? saved : businessFixedSamplePresets(key);
};

const findBusinessCapabilityField = (value: unknown, names: string[], depth = 0): string => {
  if (!value || depth > 4) return '';
  if (typeof value !== 'object') return '';
  if (Array.isArray(value)) {
    for (const item of value) {
      const found = findBusinessCapabilityField(item, names, depth + 1);
      if (found) return found;
    }
    return '';
  }
  const record = value as Record<string, unknown>;
  for (const [key, item] of Object.entries(record)) {
    if (names.includes(key) && item !== undefined && item !== null && item !== '') {
      return String(item);
    }
  }
  for (const item of Object.values(record)) {
    const found = findBusinessCapabilityField(item, names, depth + 1);
    if (found) return found;
  }
  return '';
};

const businessCapabilityCandidateRoute = (item: BusinessCapability) => {
  const sources = [item.recipe, item.metadata, item.inputSchema, item.outputSchema];
  const workflow =
    item.metadata && typeof item.metadata.workflow_key === 'string'
      ? item.metadata.workflow_key
      : sources.map((source) => findBusinessCapabilityField(source, ['workflowKey', 'workflow_key', 'workflowId', 'workflow_id'])).find(Boolean) || '';
  const lora = sources.map((source) => findBusinessCapabilityField(source, ['lora', 'loraName', 'lora_name', 'loraFile', 'lora_file'])).find(Boolean) || '';
  const model =
    item.vendorModelName ||
    sources.map((source) => findBusinessCapabilityField(source, ['modelId', 'model_id', 'model', 'modelName', 'model_name'])).find(Boolean) ||
    item.primaryAbilityProvider ||
    '';
  return {
    workflow,
    lora,
    model,
    label: [workflow ? `workflow ${workflow}` : '', lora ? `LoRA ${lora}` : '', model ? `模型 ${model}` : ''].filter(Boolean).join(' · ') || '沿用业务默认路线',
  };
};

const businessQualityVersionSummaryForCapability = (
  qualitySummary: BusinessOutputReviewSummaryResponse | null | undefined,
  item: BusinessCapability,
): BusinessOutputReviewVersionSummary | null =>
  (qualitySummary?.byVersion || []).find(
    (row) =>
      (row.businessVersionId && row.businessVersionId === item.id) ||
      (canonicalBusinessKey(row.businessKey) === canonicalBusinessKey(item.businessKey) && String(row.version || '') === String(item.version || '')),
  ) || null;

const businessCandidateQualityLabel = (item: BusinessCapability, summary?: BusinessOutputReviewVersionSummary | null) => {
  const qualityEvidence = (item.releaseGate?.qualityEvidence || {}) as JsonRecord;
  const reviewed = Number(summary?.reviewed ?? qualityEvidence.reviewed ?? 0);
  const accepted = Number((summary?.excellent || 0) + (summary?.usable || 0) || qualityEvidence.accepted || 0);
  const risky = Number((summary?.borderline || 0) + (summary?.bad || 0) + (summary?.blocked || 0) || qualityEvidence.risky || 0);
  if (reviewed <= 0) return { theme: 'warning', text: '待质量标注', detail: '还没有可用于切默认的输出样例。', reviewed, accepted, risky };
  if (accepted <= 0) return { theme: 'danger', text: '缺可用样本', detail: `已标注 ${reviewed}，但没有优秀/可用样本。`, reviewed, accepted, risky };
  if (risky > 0) return { theme: 'warning', text: '需复核', detail: `可用 ${accepted}，风险 ${risky}。`, reviewed, accepted, risky };
  return { theme: 'success', text: '质量可用', detail: `可用 ${accepted}/${reviewed}。`, reviewed, accepted, risky };
};

type BusinessCandidateQualityView = ReturnType<typeof businessCandidateQualityLabel>;

type BusinessCandidateVersionView = {
  item: BusinessCapability;
  route: ReturnType<typeof businessCapabilityCandidateRoute>;
  summary?: BusinessOutputReviewVersionSummary | null;
  quality: BusinessCandidateQualityView;
};

const businessCandidateLatestRunTime = (item?: BusinessCapability | null) =>
  Date.parse(String(item?.latestRun?.createdAt || item?.latestRun?.created_at || item?.latestRun?.finishedAt || item?.latestRun?.finished_at || '')) || 0;

const businessCandidateFocus = ({
  presetsCount,
  libraryCount,
  actionRulesCount,
  versionRows,
  candidateCount,
}: {
  presetsCount: number;
  libraryCount: number;
  actionRulesCount: number;
  versionRows: BusinessCandidateVersionView[];
  candidateCount: number;
}) => {
  const noQualityCount = versionRows.filter((row) => row.quality.reviewed <= 0).length;
  const dangerQualityCount = versionRows.filter((row) => row.quality.theme === 'danger').length;
  const riskyCount = versionRows.filter((row) => row.quality.risky > 0).length;
  if (libraryCount <= 0) {
    return {
      theme: 'warning',
      title: '先建固定样例库',
      detail: presetsCount > 0 ? '当前只有系统建议覆盖类型，建议沉淀真实可复用的固定样例。' : '还没有固定样例，无法做标准批量对照。',
      action: '导入样例',
    };
  }
  if (dangerQualityCount > 0) {
    return {
      theme: 'danger',
      title: '质量阻断',
      detail: `${dangerQualityCount} 个版本缺少可用样本，先补标注或换候选策略。`,
      action: '记录治理项',
    };
  }
  if (riskyCount > 0) {
    return {
      theme: 'warning',
      title: '处理风险样本',
      detail: `${riskyCount} 个版本存在风险标注，优先沉淀分流、LoRA 或 workflow 策略。`,
      action: actionRulesCount > 0 ? '复跑治理项' : '记录治理项',
    };
  }
  if (noQualityCount > 0) {
    return {
      theme: 'warning',
      title: '补质量标注',
      detail: `${noQualityCount} 个版本没有质量证据，先用固定样例跑同批对照。`,
      action: '批量复跑',
    };
  }
  if (candidateCount > 0) {
    return {
      theme: 'success',
      title: '可做候选验收',
      detail: `已有 ${candidateCount} 条候选路线，可继续用固定样例做版本对照。`,
      action: '批量复跑',
    };
  }
  return {
    theme: 'default',
    title: '保持观察',
    detail: '当前只有默认路线，继续积累样例和质量标注。',
    action: '观察',
  };
};

const createBusinessFixedSamplePayload = ({
  imageUrl,
  generatedImageUrl,
  prompt,
  preset,
  capability,
  batchId,
  batchMode = false,
  extraParams = {},
}: {
  imageUrl: string;
  generatedImageUrl?: string;
  prompt?: string;
  preset?: BusinessFixedSamplePreset;
  capability: BusinessCapability;
  batchId?: string;
  batchMode?: boolean;
  extraParams?: Record<string, unknown>;
}): Record<string, unknown> => {
  const payload: Record<string, unknown> = {
    ...(preset?.inputs || {}),
    ...extraParams,
    imageUrl,
    variation_preset: preset?.key || 'fixed-sample',
    metadata: {
      qualitySample: {
        batchId,
        batchMode,
        businessKey: canonicalBusinessKey(capability.businessKey),
        businessVersionId: capability.id,
        version: capability.version,
        sampleId: preset?.sampleId,
        sampleKey: preset?.key || 'fixed-sample',
        sampleLabel: preset?.label || '固定样例',
        sampleHint: preset?.hint || '',
        sampleSource: preset?.source || 'preset',
        source: 'admin-quality-candidate-panel',
      },
    },
  };
  if (prompt?.trim()) payload.prompt = prompt.trim();
  if (generatedImageUrl?.trim()) {
    payload.originalImageUrl = imageUrl;
    payload.generatedImageUrl = generatedImageUrl.trim();
  }
  return payload;
};

const businessBatchSummaryLabel = (batch: BusinessOutputReviewBatchSummary) => {
  if (batch.reviewed <= 0) return { theme: 'warning', text: '待标注', detail: `已回收 ${batch.total} 张输出，尚未形成质量结论。` };
  if (batch.good <= 0) return { theme: 'danger', text: '无可用样本', detail: `已标注 ${batch.reviewed}，暂无优秀/可用。` };
  if (batch.risk > 0) return { theme: 'warning', text: '需复核', detail: `可用 ${batch.good}，风险 ${batch.risk}。` };
  return { theme: 'success', text: '同批可用', detail: `可用 ${batch.good}/${batch.reviewed}。` };
};

const businessQualityActionTypeOptions = [
  { label: '观察记录', value: 'watch_only' },
  { label: '调参', value: 'tune_params' },
  { label: '分流', value: 'route_split' },
  { label: '换 LoRA', value: 'switch_lora' },
  { label: '换 workflow', value: 'switch_workflow' },
  { label: '暂停推荐', value: 'pause_recommendation' },
];

const businessQualityActionStatusOptions = [
  { label: '草稿', value: 'draft' },
  { label: '候选', value: 'candidate' },
  { label: '已验证', value: 'validated' },
  { label: '默认策略', value: 'default' },
  { label: '暂停', value: 'paused' },
  { label: '拒绝', value: 'rejected' },
  { label: '已归档', value: 'archived' },
];

const businessQualityActionTypeLabel = (value?: string | null) =>
  businessQualityActionTypeOptions.find((option) => option.value === value)?.label || '观察记录';

const businessQualityActionStatusLabel = (value?: string | null) =>
  businessQualityActionStatusOptions.find((option) => option.value === value)?.label || '候选';

const businessQualityActionStatusTheme = (value?: string | null) => {
  if (value === 'validated' || value === 'default') return 'success';
  if (value === 'paused' || value === 'rejected') return 'danger';
  if (value === 'draft' || value === 'candidate') return 'warning';
  return 'default';
};

type BusinessQualityActionRuleForm = {
  title: string;
  actionType: string;
  status: string;
  targetBusinessVersionId: string;
  targetRef: string;
  issueTagsText: string;
  inputTagsText: string;
  description: string;
};

const defaultBusinessQualityActionRuleForm = (): BusinessQualityActionRuleForm => ({
  title: '',
  actionType: 'watch_only',
  status: 'candidate',
  targetBusinessVersionId: '',
  targetRef: '',
  issueTagsText: '',
  inputTagsText: '',
  description: '',
});

const downloadBusinessQualityCsv = (blob: Blob, filename: string) => {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
};

const businessQualityFileToken = (value?: string | null) =>
  String(value || 'all')
    .trim()
    .replace(/[^A-Za-z0-9._-]+/g, '-')
    .slice(0, 80) || 'all';

export const BusinessQualityCandidatePanel = ({
  capabilities,
  qualitySummary,
  isReadOnly,
  actionLoadingId,
  onDraftRun,
  onDraftRunBatch,
  onOpenReview,
  formatDateTime,
}: {
  capabilities: BusinessCapability[];
  qualitySummary?: BusinessOutputReviewSummaryResponse | null;
  isReadOnly: boolean;
  actionLoadingId?: string | null;
  onDraftRun: (item: BusinessCapability, payload?: Record<string, unknown>) => void | Promise<void>;
  onDraftRunBatch: (items: BusinessDraftRunBatchRequest[]) => Promise<BusinessDraftRunBatchResult>;
  onOpenReview?: (review: BusinessOutputReview) => void;
  formatDateTime: (value?: string | null) => string;
}) => {
  const [sampleTarget, setSampleTarget] = useState<BusinessCapability | null>(null);
  const [batchTarget, setBatchTarget] = useState<{ businessKey: string; items: BusinessCapability[] } | null>(null);
  const [sampleForm, setSampleForm] = useState({
    sampleKey: '',
    imageUrl: '',
    prompt: '',
    generatedImageUrl: '',
    extraParamsText: '',
  });
  const [batchRows, setBatchRows] = useState<Record<string, BusinessFixedSampleBatchRow>>({});
  const [batchTargetIds, setBatchTargetIds] = useState<string[]>([]);
  const [batchExtraParamsText, setBatchExtraParamsText] = useState('');
  const [sampleError, setSampleError] = useState<string | null>(null);
  const [sampleNotice, setSampleNotice] = useState<string | null>(null);
  const [sampleSaving, setSampleSaving] = useState(false);
  const [batchError, setBatchError] = useState<string | null>(null);
  const [batchReport, setBatchReport] = useState<BusinessFixedSampleBatchReport | null>(null);
  const [qualitySamples, setQualitySamples] = useState<BusinessQualitySample[]>([]);
  const [qualitySamplesLoading, setQualitySamplesLoading] = useState(false);
  const [qualitySamplesError, setQualitySamplesError] = useState<string | null>(null);
  const [sampleUploadLoading, setSampleUploadLoading] = useState(false);
  const [sampleImportVisible, setSampleImportVisible] = useState(false);
  const [sampleImportBusinessKey, setSampleImportBusinessKey] = useState('all');
  const [sampleImportText, setSampleImportText] = useState('');
  const [sampleImportDryRun, setSampleImportDryRun] = useState(false);
  const [sampleImportLoading, setSampleImportLoading] = useState(false);
  const [sampleImportError, setSampleImportError] = useState<string | null>(null);
  const [sampleImportReport, setSampleImportReport] = useState<BusinessQualitySampleImportResponse | null>(null);
  const [sampleHistoryTargetId, setSampleHistoryTargetId] = useState('');
  const [sampleHistoryItems, setSampleHistoryItems] = useState<BusinessQualitySampleVersion[]>([]);
  const [sampleHistoryLoading, setSampleHistoryLoading] = useState(false);
  const [sampleHistoryError, setSampleHistoryError] = useState<string | null>(null);
  const [qualityActionRules, setQualityActionRules] = useState<BusinessQualityActionRule[]>([]);
  const [qualityActionRulesLoading, setQualityActionRulesLoading] = useState(false);
  const [qualityActionRulesError, setQualityActionRulesError] = useState<string | null>(null);
  const [ruleDialogBusinessKey, setRuleDialogBusinessKey] = useState<string | null>(null);
  const [ruleEditTarget, setRuleEditTarget] = useState<BusinessQualityActionRule | null>(null);
  const [ruleForm, setRuleForm] = useState<BusinessQualityActionRuleForm>(() => defaultBusinessQualityActionRuleForm());
  const [ruleError, setRuleError] = useState<string | null>(null);
  const [ruleSaving, setRuleSaving] = useState(false);
  const [ruleArchivingId, setRuleArchivingId] = useState<string | null>(null);
  const [reviewExportingKey, setReviewExportingKey] = useState<string | null>(null);
  const [reviewExportError, setReviewExportError] = useState<string | null>(null);
  const refreshQualitySamples = async () => {
    setQualitySamplesLoading(true);
    setQualitySamplesError(null);
    try {
      const response = await adminApi.listBusinessQualitySamples({ limit: 500 });
      setQualitySamples(response.items || []);
    } catch (error: any) {
      setQualitySamples([]);
      setQualitySamplesError(error?.message || '固定样例库暂不可用。');
    } finally {
      setQualitySamplesLoading(false);
    }
  };
  const uploadSampleImageToOss = async (file?: File | null) => {
    if (!file) return;
    setSampleUploadLoading(true);
    setSampleError(null);
    setSampleNotice(null);
    try {
      const { uploadAbilityTestFile } = await import('../../../utils/ossUploader');
      const uploaded = await uploadAbilityTestFile(file, {
        action: 'business-quality-sample',
        channel: 'admin-quality-sample-library',
      });
      setSampleForm((prev) => ({ ...prev, imageUrl: uploaded.url }));
      setSampleNotice(`已上传到 OSS：${uploaded.name}`);
    } catch (error: any) {
      setSampleError(error?.message || 'OSS 上传失败，请稍后重试。');
    } finally {
      setSampleUploadLoading(false);
    }
  };
  const openSampleImportDialog = (businessKey?: string) => {
    setSampleImportVisible(true);
    setSampleImportBusinessKey(businessKey ? canonicalBusinessKey(businessKey) : 'all');
    setSampleImportError(null);
    setSampleImportReport(null);
    setSampleHistoryError(null);
    setSampleHistoryItems([]);
    setSampleHistoryTargetId((prev) => prev || qualitySamples[0]?.id || '');
  };
  const submitSampleImport = async () => {
    const businessKey = sampleImportBusinessKey !== 'all' ? sampleImportBusinessKey : undefined;
    let items: BusinessQualitySampleImportItem[] = [];
    try {
      items = parseBusinessQualitySampleImportText(sampleImportText, businessKey);
    } catch (error: any) {
      setSampleImportError(error?.message || '导入内容解析失败。');
      return;
    }
    setSampleImportLoading(true);
    setSampleImportError(null);
    try {
      const response = await adminApi.importBusinessQualitySamples({
        businessKey,
        items,
        dryRun: sampleImportDryRun,
        changeNote: sampleImportDryRun ? '管理端批量导入预检查' : '管理端批量导入',
      });
      setSampleImportReport(response);
      if (!sampleImportDryRun && (response.created > 0 || response.updated > 0)) {
        await refreshQualitySamples();
      }
    } catch (error: any) {
      setSampleImportError(error?.message || '批量导入失败。');
    } finally {
      setSampleImportLoading(false);
    }
  };
  const loadSampleHistory = async (sampleId?: string) => {
    const targetId = sampleId || sampleHistoryTargetId;
    if (!targetId) {
      setSampleHistoryError('请选择样例。');
      return;
    }
    setSampleHistoryLoading(true);
    setSampleHistoryError(null);
    try {
      const response = await adminApi.listBusinessQualitySampleVersions(targetId, 50);
      setSampleHistoryItems(response.items || []);
      setSampleHistoryTargetId(targetId);
    } catch (error: any) {
      setSampleHistoryItems([]);
      setSampleHistoryError(error?.message || '样例历史加载失败。');
    } finally {
      setSampleHistoryLoading(false);
    }
  };
  const refreshQualityActionRules = async () => {
    setQualityActionRulesLoading(true);
    setQualityActionRulesError(null);
    try {
      const response = await adminApi.listBusinessQualityActionRules({ limit: 500 });
      setQualityActionRules(response.items || []);
    } catch (error: any) {
      setQualityActionRules([]);
      setQualityActionRulesError(error?.message || '质量治理台账暂不可用。');
    } finally {
      setQualityActionRulesLoading(false);
    }
  };
  const exportBusinessQualityReviews = async (options?: { batch?: BusinessOutputReviewBatchSummary; businessKey?: string }) => {
    const batch = options?.batch;
    const exportKey = batch?.batchId || options?.businessKey || 'all';
    setReviewExportingKey(exportKey);
    setReviewExportError(null);
    try {
      const blob = await adminApi.exportBusinessOutputReviews({
        windowHours: qualitySummary?.windowHours || 168,
        businessKey: batch?.businessKey || options?.businessKey,
        batchId: batch?.batchId,
        limit: 5000,
      });
      const filename = batch
        ? `business-quality-${businessQualityFileToken(batch.businessKey)}-${businessQualityFileToken(batch.batchId)}.csv`
        : `business-quality-${businessQualityFileToken(options?.businessKey)}-${Date.now()}.csv`;
      downloadBusinessQualityCsv(blob, filename);
    } catch (error: any) {
      setReviewExportError(error?.message || '质量结果导出失败，请稍后重试。');
    } finally {
      setReviewExportingKey(null);
    }
  };
  useEffect(() => {
    void refreshQualitySamples();
    void refreshQualityActionRules();
  }, []);
  const grouped = capabilities.reduce<Record<string, BusinessCapability[]>>((map, item) => {
    const key = canonicalBusinessKey(item.businessKey);
    if (!businessOrchestrationKeys.includes(key as any)) return map;
    map[key] = map[key] || [];
    map[key].push(item);
    return map;
  }, {});
  const groupKeys = businessOrchestrationKeys.filter((key) => grouped[key]?.length);
  const openSampleRun = (item: BusinessCapability, preset?: BusinessFixedSamplePreset) => {
    const firstPreset = preset || businessFixedSampleOptions(item.businessKey, qualitySamples)[0];
    setSampleTarget(item);
    setSampleError(null);
    setSampleNotice(null);
    setSampleForm({
      sampleKey: firstPreset?.key || '',
      imageUrl: firstPreset?.imageUrl || '',
      prompt: firstPreset?.prompt || '',
      generatedImageUrl: firstPreset?.generatedImageUrl || '',
      extraParamsText: '',
    });
  };
  const openBatchRun = (businessKey: string, items: BusinessCapability[]) => {
    const presets = businessFixedSampleOptions(businessKey, qualitySamples);
    const nextRows = presets.reduce<Record<string, BusinessFixedSampleBatchRow>>((map, preset) => {
      map[preset.key] = {
        enabled: true,
        imageUrl: preset.imageUrl || '',
        prompt: preset.prompt || '',
        generatedImageUrl: preset.generatedImageUrl || '',
      };
      return map;
    }, {});
    const runnable = items.filter((item) => item.status !== 'deprecated' && item.status !== 'disabled');
    const defaultTarget = runnable.find((item) => item.isDefault);
    const candidateTarget = runnable.find((item) => !item.isDefault);
    const defaultIds = [defaultTarget?.id, candidateTarget?.id].filter(Boolean) as string[];
    setBatchTarget({ businessKey, items: runnable });
    setBatchTargetIds(defaultIds.length > 0 ? defaultIds : runnable.slice(0, 2).map((item) => item.id));
    setBatchRows(nextRows);
    setBatchExtraParamsText('');
    setBatchError(null);
  };
  const openQualityActionRuleDialog = (businessKey: string, items: BusinessCapability[]) => {
    const key = canonicalBusinessKey(businessKey);
    const businessSummary = (qualitySummary?.byBusiness || []).find((item) => canonicalBusinessKey(item.businessKey) === key);
    const topIssue = businessSummary?.topIssueTags?.[0]?.key || '';
    const topInput = businessSummary?.topInputTags?.[0]?.key || '';
    const candidate = items.find((item) => !item.isDefault && item.status !== 'deprecated' && item.status !== 'disabled');
    setRuleDialogBusinessKey(key);
    setRuleEditTarget(null);
    setRuleError(null);
    setRuleForm({
      title: topIssue ? `${businessKeyLabel(key)} · ${topIssue}` : `${businessKeyLabel(key)}质量治理`,
      actionType: topIssue ? 'route_split' : 'watch_only',
      status: 'candidate',
      targetBusinessVersionId: candidate?.id || '',
      targetRef: '',
      issueTagsText: topIssue,
      inputTagsText: topInput,
      description: '',
    });
  };
  const openQualityActionRuleEditDialog = (rule: BusinessQualityActionRule) => {
    setRuleDialogBusinessKey(canonicalBusinessKey(rule.businessKey));
    setRuleEditTarget(rule);
    setRuleError(null);
    setRuleForm({
      title: rule.title || '',
      actionType: rule.actionType || 'watch_only',
      status: rule.status || 'candidate',
      targetBusinessVersionId: rule.targetBusinessVersionId || '',
      targetRef: rule.targetRef || '',
      issueTagsText: (rule.issueTags || []).join('、'),
      inputTagsText: (rule.inputTags || []).join('、'),
      description: rule.description || '',
    });
  };
  const submitQualityActionRule = async () => {
    const businessKey = ruleDialogBusinessKey;
    if (!businessKey) return;
    const title = ruleForm.title.trim();
    if (!title) {
      setRuleError('请填写治理项标题。');
      return;
    }
    setRuleSaving(true);
    setRuleError(null);
    try {
      const payload: Partial<BusinessQualityActionRule> = {
        businessKey,
        title,
        actionType: ruleForm.actionType,
        status: ruleForm.status,
        targetBusinessVersionId: ruleForm.targetBusinessVersionId || null,
        targetRef: ruleForm.targetRef.trim() || null,
        issueTags: splitBusinessOutputReviewTags(ruleForm.issueTagsText),
        inputTags: splitBusinessOutputReviewTags(ruleForm.inputTagsText),
        description: ruleForm.description.trim() || null,
      };
      if (ruleEditTarget) {
        await adminApi.updateBusinessQualityActionRule(ruleEditTarget.id, payload);
      } else {
        await adminApi.createBusinessQualityActionRule(payload);
      }
      await refreshQualityActionRules();
      setRuleDialogBusinessKey(null);
      setRuleEditTarget(null);
    } catch (error: any) {
      setRuleError(error?.message || '质量治理项保存失败。');
    } finally {
      setRuleSaving(false);
    }
  };
  const archiveQualityActionRule = async (rule: BusinessQualityActionRule) => {
    setRuleArchivingId(rule.id);
    setQualityActionRulesError(null);
    try {
      await adminApi.archiveBusinessQualityActionRule(rule.id);
      await refreshQualityActionRules();
    } catch (error: any) {
      setQualityActionRulesError(error?.message || '质量治理项归档失败。');
    } finally {
      setRuleArchivingId(null);
    }
  };
  const submitSampleRun = async () => {
    if (!sampleTarget) return;
    const imageUrl = sampleForm.imageUrl.trim();
    if (!imageUrl) {
      setSampleError('请填写固定样例图片 URL。');
      return;
    }
    const preset = samplePresets.find((item) => item.key === sampleForm.sampleKey);
    let extraParams: Record<string, unknown> = {};
    if (sampleForm.extraParamsText.trim()) {
      try {
        const parsed = JSON.parse(sampleForm.extraParamsText);
        if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
          setSampleError('附加参数必须是 JSON 对象。');
          return;
        }
        extraParams = parsed as Record<string, unknown>;
      } catch {
        setSampleError('附加参数 JSON 格式不正确。');
        return;
      }
    }
    const payload = createBusinessFixedSamplePayload({
      imageUrl,
      generatedImageUrl: sampleForm.generatedImageUrl,
      prompt: sampleForm.prompt,
      preset,
      capability: sampleTarget,
      batchMode: false,
      extraParams,
    });
    await onDraftRun(sampleTarget, payload);
    setSampleTarget(null);
  };
  const saveCurrentSampleToLibrary = async () => {
    if (!sampleTarget) return;
    const imageUrl = sampleForm.imageUrl.trim();
    if (!imageUrl) {
      setSampleError('请先填写样例图片 URL。');
      return;
    }
    let extraParams: Record<string, unknown> = {};
    if (sampleForm.extraParamsText.trim()) {
      try {
        const parsed = JSON.parse(sampleForm.extraParamsText);
        if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
          setSampleError('附加参数必须是 JSON 对象。');
          return;
        }
        extraParams = parsed as Record<string, unknown>;
      } catch {
        setSampleError('附加参数 JSON 格式不正确。');
        return;
      }
    }
    const preset = samplePresets.find((item) => item.key === sampleForm.sampleKey);
    setSampleSaving(true);
    setSampleError(null);
    setSampleNotice(null);
    try {
      const created = await adminApi.createBusinessQualitySample({
        businessKey: canonicalBusinessKey(sampleTarget.businessKey),
        label: preset?.label || '固定样例',
        description: preset?.hint || '',
        imageUrl,
        prompt: sampleForm.prompt.trim() || undefined,
        generatedImageUrl: sampleForm.generatedImageUrl.trim() || undefined,
        inputTags: preset?.label ? [preset.label] : [],
        defaultParams: {
          ...(preset?.inputs || {}),
          ...extraParams,
        } as JsonRecord,
        status: 'active',
        changeNote: '管理端保存固定样例',
      });
      await refreshQualitySamples();
      setSampleNotice(`已保存到样例库：${created.label}`);
    } catch (error: any) {
      setSampleError(error?.message || '保存固定样例失败，请检查 URL 和样例名称。');
    } finally {
      setSampleSaving(false);
    }
  };
  const submitBatchRun = async () => {
    if (!batchTarget) return;
    if (batchTargetIds.length === 0) {
      setBatchError('至少选择一个要复跑的版本。');
      return;
    }
    let extraParams: Record<string, unknown> = {};
    if (batchExtraParamsText.trim()) {
      try {
        const parsed = JSON.parse(batchExtraParamsText);
        if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
          setBatchError('批量附加参数必须是 JSON 对象。');
          return;
        }
        extraParams = parsed as Record<string, unknown>;
      } catch {
        setBatchError('批量附加参数 JSON 格式不正确。');
        return;
      }
    }
    const presets = batchPresets;
    const selectedTargets = batchTarget.items.filter((item) => batchTargetIds.includes(item.id));
    const enabledSamples = presets
      .map((preset) => ({ preset, row: batchRows[preset.key] }))
      .filter(({ row }) => row?.enabled && row.imageUrl.trim());
    if (enabledSamples.length === 0) {
      setBatchError('至少填写一个启用样例的图片 URL。');
      return;
    }
    const batchId = `qsample-${canonicalBusinessKey(batchTarget.businessKey)}-${Date.now()}`;
    const requests: BusinessDraftRunBatchRequest[] = [];
    for (const target of selectedTargets) {
      for (const { preset, row } of enabledSamples) {
        requests.push({
          capability: target,
          payload: createBusinessFixedSamplePayload({
            imageUrl: row.imageUrl.trim(),
            generatedImageUrl: row.generatedImageUrl,
            prompt: row.prompt,
            preset,
            capability: target,
            batchId,
            batchMode: true,
            extraParams,
          }),
        });
      }
    }
    const result = await onDraftRunBatch(requests);
    setBatchReport({
      ...result,
      batchId,
      businessKey: batchTarget.businessKey,
      sampleCount: enabledSamples.length,
      targetCount: selectedTargets.length,
      createdAt: new Date().toISOString(),
    });
    if (result.submitted > 0) {
      setBatchTarget(null);
    } else if (result.errors.length > 0) {
      setBatchError(result.errors.slice(0, 3).join('；'));
    }
  };
  const samplePresets = businessFixedSampleOptions(sampleTarget?.businessKey, qualitySamples);
  const sampleBusy = Boolean(sampleTarget && actionLoadingId === `draft-run:${sampleTarget.id}`);
  const batchPresets = businessFixedSampleOptions(batchTarget?.businessKey, qualitySamples);
  const batchBusy = actionLoadingId === 'draft-run-batch';
  const ruleTargetItems = ruleDialogBusinessKey ? grouped[ruleDialogBusinessKey] || [] : [];
  const ruleTargetOptions = [
    { label: '不绑定候选版本', value: '' },
    ...ruleTargetItems.map((item) => ({
      label: `${item.isDefault ? '默认 · ' : ''}${item.version} · ${item.displayName}`,
      value: item.id,
    })),
  ];

  if (groupKeys.length === 0) return null;

  return (
    <>
      <Card
        bordered
        title={
          <Space align="center" style={{ justifyContent: 'space-between', width: '100%', flexWrap: 'wrap' }}>
            <div>
              <Typography.Text strong>候选对照与质量样例复跑</Typography.Text>
              <div>
                <Typography.Text theme="secondary">
                  默认版本和候选版本放在同一张表里看；固定样例库用于标准复跑，内置建议只提示该覆盖哪些图。
                </Typography.Text>
              </div>
            </div>
            <Tag variant="light">质量窗口 {qualitySummary?.windowHours || 168} 小时</Tag>
            <Tag theme={qualitySamplesError ? 'warning' : 'default'} variant="light">
              固定样例库 {qualitySamplesLoading ? '加载中' : `${qualitySamples.length} 个`}
            </Tag>
            <Tag theme={qualityActionRulesError ? 'warning' : 'default'} variant="light">
              治理台账 {qualityActionRulesLoading ? '加载中' : `${qualityActionRules.length} 条`}
            </Tag>
            <Button size="small" variant="outline" disabled={isReadOnly} onClick={() => openSampleImportDialog()}>
              导入样例
            </Button>
            <Button size="small" variant="outline" loading={qualitySamplesLoading} onClick={() => void refreshQualitySamples()}>
              刷新样例库
            </Button>
          </Space>
        }
      >
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          {qualitySamplesError ? <Alert theme="warning" message={`固定样例库暂不可用，已退回内置样例类型：${qualitySamplesError}`} /> : null}
          {qualityActionRulesError ? <Alert theme="warning" message={`质量治理台账暂不可用：${qualityActionRulesError}`} /> : null}
          {reviewExportError ? <Alert theme="warning" message={`质量结果导出失败：${reviewExportError}`} /> : null}
          {batchReport ? (
            <Alert
              theme={batchReport.errors.length > 0 ? 'warning' : 'success'}
              message={`最近批量复跑 ${batchReport.submitted}/${batchReport.total} 已提交 · batchId ${batchReport.batchId}。覆盖 ${batchReport.sampleCount} 个样例、${batchReport.targetCount} 个版本；完成后到 runId 详情标注质量，会自动归入同批对照。`}
            />
          ) : null}
          {(qualitySummary?.byBatch || []).length > 0 ? (
            <details className="podi-business-disclosure">
              <summary>
                <span>近期同批质量对照</span>
                <small>{(qualitySummary?.byBatch || []).length} 批 · 按 batchId 聚合同一批样例的版本质量标注</small>
              </summary>
              <div className="podi-business-disclosure-body">
                <Space align="center" style={{ justifyContent: 'space-between', width: '100%', flexWrap: 'wrap' }}>
                  <Typography.Text theme="secondary">展开后查看批次明细；默认收起，避免占用首屏。</Typography.Text>
                  <Button
                    size="small"
                    variant="outline"
                    loading={reviewExportingKey === 'all'}
                    onClick={() => void exportBusinessQualityReviews()}
                  >
                    导出窗口
                  </Button>
                </Space>
                <div className="podi-business-batch-report-grid">
                  {(qualitySummary?.byBatch || []).slice(0, 4).map((batch) => {
                    const status = businessBatchSummaryLabel(batch);
                    return (
                      <div key={`${batch.batchId}:${batch.sampleKey || ''}`} className="podi-business-batch-report-card">
                        <Space align="center" style={{ justifyContent: 'space-between', width: '100%', flexWrap: 'wrap' }}>
                          <Typography.Text strong>{batch.sampleLabel || batch.sampleKey || batch.label}</Typography.Text>
                          <Tag theme={status.theme as any} variant="light" size="small">
                            {status.text}
                          </Tag>
                        </Space>
                        <Typography.Text theme="secondary">{batch.batchId}</Typography.Text>
                        <Typography.Text>{status.detail}</Typography.Text>
                        <div className="podi-business-batch-version-list">
                          {(batch.versions || []).slice(0, 4).map((version) => (
                            <span key={`${batch.batchId}:${version.businessVersionId || version.version || version.label}`}>
                              {version.version || version.label}: 可用 {version.good} / 风险 {version.risk} / 标注 {version.reviewed}
                            </span>
                          ))}
                        </div>
                        <Space size={6} breakLine>
                          <Button
                            size="small"
                            variant="outline"
                            loading={reviewExportingKey === batch.batchId}
                            onClick={() => void exportBusinessQualityReviews({ batch })}
                          >
                            导出 CSV
                          </Button>
                          <Typography.Text theme="secondary">{batch.reviewed}/{batch.total} 已标注</Typography.Text>
                        </Space>
                      </div>
                    );
                  })}
                </div>
              </div>
            </details>
          ) : null}
          {groupKeys.map((businessKey) => {
            const items = grouped[businessKey]
              .slice()
              .sort((left, right) => {
                if (left.isDefault !== right.isDefault) return left.isDefault ? -1 : 1;
                if (left.status !== right.status) return left.status === 'active' ? -1 : 1;
                return String(right.releaseTime || right.createdAt || '').localeCompare(String(left.releaseTime || left.createdAt || ''));
              });
            const presets = businessFixedSampleOptions(businessKey, qualitySamples);
            const libraryCount = presets.filter((preset) => preset.source === 'library').length;
            const actionRules = qualityActionRules
              .filter((rule) => canonicalBusinessKey(rule.businessKey) === canonicalBusinessKey(businessKey) && rule.status !== 'archived')
              .sort((left, right) => {
                const priorityDiff = Number(left.priority || 0) - Number(right.priority || 0);
                if (priorityDiff !== 0) return priorityDiff;
                return String(right.updatedAt || '').localeCompare(String(left.updatedAt || ''));
              });
            const versionRows: BusinessCandidateVersionView[] = items.map((item) => {
              const summary = businessQualityVersionSummaryForCapability(qualitySummary, item);
              return {
                item,
                route: businessCapabilityCandidateRoute(item),
                summary,
                quality: businessCandidateQualityLabel(item, summary),
              };
            });
            const defaultItem = items.find((item) => item.isDefault);
            const candidateCount = items.filter((item) => !item.isDefault && item.status !== 'deprecated' && item.status !== 'disabled').length;
            const latestRunItem = items
              .filter((item) => businessCandidateLatestRunTime(item) > 0)
              .sort((left, right) => businessCandidateLatestRunTime(right) - businessCandidateLatestRunTime(left))[0];
            const latestReviewAt = versionRows
              .map((row) => row.summary?.latestAt)
              .filter(Boolean)
              .sort((left, right) => String(right).localeCompare(String(left)))[0];
            const reviewedTotal = versionRows.reduce((sum, row) => sum + row.quality.reviewed, 0);
            const acceptedTotal = versionRows.reduce((sum, row) => sum + row.quality.accepted, 0);
            const riskTotal = versionRows.reduce((sum, row) => sum + row.quality.risky, 0);
            const focus = businessCandidateFocus({
              presetsCount: presets.length,
              libraryCount,
              actionRulesCount: actionRules.length,
              versionRows,
              candidateCount,
            });
            return (
              <section key={businessKey} className="podi-business-candidate-panel">
                <Space align="center" style={{ justifyContent: 'space-between', width: '100%', flexWrap: 'wrap' }}>
                  <Space direction="vertical" size={2}>
                    <Space size={6} breakLine>
                      <Typography.Text strong>{businessKeyLabel(businessKey)}</Typography.Text>
                      <Tag theme={focus.theme as any} variant="light" size="small">
                        {focus.title}
                      </Tag>
                    </Space>
                    <Typography.Text theme="secondary">{focus.detail}</Typography.Text>
                  </Space>
                  <Space size={6} breakLine>
                    <Tag variant="light" size="small">
                      版本 {items.length}
                    </Tag>
                    <Tag theme={libraryCount > 0 ? 'success' : 'warning'} variant="light" size="small">
                      {libraryCount > 0 ? `固定样例 ${libraryCount}` : `未建固定样例 · 内置建议 ${presets.length}`}
                    </Tag>
                    <Tag theme={actionRules.length > 0 ? 'primary' : 'default'} variant="light" size="small">
                      治理 {actionRules.length}
                    </Tag>
                    <Button
                      size="small"
                      theme="primary"
                      variant="outline"
                      disabled={isReadOnly}
                      loading={batchBusy && batchTarget?.businessKey === businessKey}
                      onClick={() => openBatchRun(businessKey, items)}
                    >
                      批量复跑
                    </Button>
                    <Button
                      size="small"
                      variant="outline"
                      disabled={isReadOnly}
                      loading={qualityActionRulesLoading}
                      onClick={() => openQualityActionRuleDialog(businessKey, items)}
                    >
                      记录治理项
                    </Button>
                  </Space>
                </Space>
                <div className="podi-business-candidate-brief-grid">
                  <div className="podi-business-candidate-brief-item" data-theme={focus.theme}>
                    <span>下一步</span>
                    <strong>{focus.action}</strong>
                    <small>{businessQualitySamplePlan(businessKey)}</small>
                  </div>
                  <div className="podi-business-candidate-brief-item">
                    <span>默认版本</span>
                    <strong>{defaultItem?.version || '未配置'}</strong>
                    <small>{defaultItem?.displayName || '需要确认默认业务版本'}</small>
                  </div>
                  <div className="podi-business-candidate-brief-item">
                    <span>候选路线</span>
                    <strong>{candidateCount}</strong>
                    <small>{candidateCount > 0 ? '可做同批对照' : '暂无候选版本'}</small>
                  </div>
                  <div className="podi-business-candidate-brief-item" data-theme={riskTotal > 0 ? 'warning' : reviewedTotal > 0 ? 'success' : 'default'}>
                    <span>质量证据</span>
                    <strong>标注 {reviewedTotal}</strong>
                    <small>可用 {acceptedTotal} · 风险 {riskTotal}</small>
                  </div>
                  <div className="podi-business-candidate-brief-item" data-theme={latestRunItem?.latestRun?.error ? 'danger' : 'default'}>
                    <span>最近运行</span>
                    <strong>{latestRunItem ? businessCapabilityLatestRunLabel(latestRunItem) : '暂无运行'}</strong>
                    <small>{latestReviewAt ? `最近标注 ${formatDateTime(latestReviewAt)}` : '未形成版本级质量样本'}</small>
                  </div>
                </div>
                <details className="podi-business-disclosure">
                  <summary>
                    <span>{libraryCount > 0 ? '固定样例库' : '内置建议样例'}</span>
                    <small>
                      {libraryCount > 0
                        ? `${libraryCount} 个固定样例 · 用于同批复跑和质量对照`
                        : `${presets.length} 个建议覆盖类型 · 需要导入真实图片后才算固定样例`}
                    </small>
                  </summary>
                  <div className="podi-business-disclosure-body">
                    <Space size={6} breakLine>
                      {presets.length > 0 ? (
                        presets.map((preset) => (
                          <Tag key={preset.key} theme={preset.source === 'library' ? 'success' : 'default'} variant="light" size="small">
                            {preset.label}
                          </Tag>
                        ))
                      ) : (
                        <Typography.Text theme="secondary">暂无固定样例。</Typography.Text>
                      )}
                      <Button size="small" variant="outline" disabled={isReadOnly} onClick={() => openSampleImportDialog(businessKey)}>
                        导入本业务样例
                      </Button>
                    </Space>
                  </div>
                </details>
                <details className="podi-business-disclosure">
                  <summary>
                    <span>质量治理台账</span>
                    <small>{actionRules.length} 条 · 分流、调参、换 LoRA/workflow 的候选策略</small>
                  </summary>
                  <div className="podi-business-disclosure-body">
                    {actionRules.length > 0 ? (
                      <div className="podi-business-quality-action-rules">
                        {actionRules.slice(0, 4).map((rule) => (
                          <div key={rule.id} className="podi-business-quality-action-rule">
                            <Space size={4} breakLine>
                              <Tag theme={businessQualityActionStatusTheme(rule.status) as any} variant="light" size="small">
                                {businessQualityActionStatusLabel(rule.status)}
                              </Tag>
                              <Tag variant="light" size="small">
                                {businessQualityActionTypeLabel(rule.actionType)}
                              </Tag>
                              <Typography.Text strong>{rule.title}</Typography.Text>
                            </Space>
                            <Typography.Text theme="secondary">
                              {[rule.issueTags?.join('、'), rule.inputTags?.length ? `输入：${rule.inputTags.join('、')}` : '', rule.targetLabel || rule.targetVersion || rule.targetRef]
                                .filter(Boolean)
                                .join(' · ') || '待补充证据'}
                            </Typography.Text>
                            <Space size={6} breakLine>
                              <Button size="small" variant="outline" disabled={isReadOnly} onClick={() => openQualityActionRuleEditDialog(rule)}>
                                编辑
                              </Button>
                              <Button
                                size="small"
                                variant="text"
                                theme="danger"
                                disabled={isReadOnly}
                                loading={ruleArchivingId === rule.id}
                                onClick={() => void archiveQualityActionRule(rule)}
                              >
                                归档
                              </Button>
                            </Space>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <Typography.Text theme="secondary">暂无治理项；发现质量风险后再记录分流、调参或切换策略。</Typography.Text>
                    )}
                  </div>
                </details>
                <details className="podi-business-disclosure">
                  <summary>
                    <span>版本明细</span>
                    <small>{items.length} 个版本 · 查看路线、质量样例和单版本复跑动作</small>
                  </summary>
                  <div className="podi-business-disclosure-body">
                    <div className="podi-business-candidate-table">
                      <div className="podi-business-candidate-head">
                        <span>版本</span>
                        <span>候选路线</span>
                        <span>质量证据</span>
                        <span>最近运行</span>
                        <span>动作</span>
                      </div>
                      {versionRows.map(({ item, route, summary, quality }) => {
                        const issueBucket = summary?.topIssueTags?.[0];
                        const issueSample = businessQualityReviewSamples(issueBucket)[0];
                        const actionId = `draft-run:${item.id}`;
                        return (
                          <div key={item.id} className="podi-business-candidate-row">
                            <div className="podi-business-candidate-cell">
                              <Space size={4} breakLine>
                                <Tag theme={item.isDefault ? 'success' : item.status === 'draft' ? 'warning' : 'default'} variant="light" size="small">
                                  {item.isDefault ? '默认' : item.status === 'draft' ? '草稿' : '候选'}
                                </Tag>
                                <Typography.Text strong>{item.version}</Typography.Text>
                              </Space>
                              <Typography.Text theme="secondary">{item.displayName}</Typography.Text>
                            </div>
                            <div className="podi-business-candidate-cell">
                              <Typography.Text>{route.label}</Typography.Text>
                              <Typography.Text theme="secondary">{businessCapabilityVersionLine(item).label}</Typography.Text>
                            </div>
                            <div className="podi-business-candidate-cell">
                              <Space size={4} breakLine>
                                <Tag theme={quality.theme as any} variant="light" size="small">
                                  {quality.text}
                                </Tag>
                                <Typography.Text theme="secondary">
                                  标注 {quality.reviewed} · 可用 {quality.accepted} · 风险 {quality.risky}
                                </Typography.Text>
                              </Space>
                              <Typography.Text theme={quality.theme === 'danger' ? 'error' : quality.theme === 'warning' ? 'warning' : 'secondary'}>
                                {issueBucket ? `Top 问题：${issueBucket.label || issueBucket.key} ${issueBucket.total}` : quality.detail}
                              </Typography.Text>
                            </div>
                            <div className="podi-business-candidate-cell">
                              <Typography.Text theme={item.latestRun?.error ? 'error' : 'secondary'}>
                                {businessCapabilityLatestRunLabel(item)}
                              </Typography.Text>
                              <Typography.Text theme="secondary">{summary?.latestAt ? `最近标注 ${formatDateTime(summary.latestAt)}` : '未形成版本级质量样本'}</Typography.Text>
                            </div>
                            <div className="podi-business-candidate-cell">
                              <Space size={6} breakLine>
                                <Button
                                  size="small"
                                  theme="primary"
                                  variant="outline"
                                  disabled={isReadOnly || item.status === 'deprecated' || item.status === 'disabled'}
                                  loading={actionLoadingId === actionId}
                                  onClick={() => openSampleRun(item)}
                                >
                                  跑固定样例
                                </Button>
                                <Button size="small" variant="outline" disabled={!issueSample || !onOpenReview} onClick={() => issueSample && onOpenReview?.(issueSample)}>
                                  看质量样例
                                </Button>
                              </Space>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </details>
              </section>
	                  );
	                })}
	              </Space>
	            </Card>
      <Dialog
        visible={Boolean(ruleDialogBusinessKey)}
        header={
          ruleDialogBusinessKey
            ? `${ruleEditTarget ? '编辑' : '记录'}质量治理项 · ${businessKeyLabel(ruleDialogBusinessKey)}`
            : '记录质量治理项'
        }
        width={720}
        confirmBtn={ruleSaving ? '保存中...' : ruleEditTarget ? '保存修改' : '保存治理项'}
        cancelBtn="取消"
        onClose={() => {
          setRuleDialogBusinessKey(null);
          setRuleEditTarget(null);
        }}
        onConfirm={submitQualityActionRule}
      >
        <Space direction="vertical" size="small" style={{ width: '100%' }}>
          {ruleError ? <Alert theme="error" message={ruleError} /> : null}
          <Typography.Text theme="secondary">把“哪类图要分流、调参、换 LoRA/workflow”先记成候选策略，验证后再切默认。</Typography.Text>
          <Row gutter={[12, 12]}>
            <Col xs={12} lg={6}>
              <Typography.Text theme="secondary">标题</Typography.Text>
              <Input
                value={ruleForm.title}
                placeholder="例如：满版图案切候选 LoRA"
                onChange={(value) => setRuleForm((prev) => ({ ...prev, title: String(value || '') }))}
              />
            </Col>
            <Col xs={12} lg={3}>
              <Typography.Text theme="secondary">动作</Typography.Text>
              <Select
                value={ruleForm.actionType}
                options={businessQualityActionTypeOptions}
                onChange={(value) => setRuleForm((prev) => ({ ...prev, actionType: String(value || 'watch_only') }))}
              />
            </Col>
            <Col xs={12} lg={3}>
              <Typography.Text theme="secondary">状态</Typography.Text>
              <Select
                value={ruleForm.status}
                options={businessQualityActionStatusOptions}
                onChange={(value) => setRuleForm((prev) => ({ ...prev, status: String(value || 'candidate') }))}
              />
            </Col>
            <Col xs={12} lg={6}>
              <Typography.Text theme="secondary">目标候选版本</Typography.Text>
              <Select
                value={ruleForm.targetBusinessVersionId}
                options={ruleTargetOptions}
                onChange={(value) => setRuleForm((prev) => ({ ...prev, targetBusinessVersionId: String(value || '') }))}
              />
            </Col>
            <Col xs={12} lg={6}>
              <Typography.Text theme="secondary">目标 LoRA / workflow / 参数引用</Typography.Text>
              <Input
                value={ruleForm.targetRef}
                placeholder="例如：YinHuaTiQu-v2.safetensors"
                onChange={(value) => setRuleForm((prev) => ({ ...prev, targetRef: String(value || '') }))}
              />
            </Col>
            <Col xs={12} lg={6}>
              <Typography.Text theme="secondary">问题标签</Typography.Text>
              <Input
                value={ruleForm.issueTagsText}
                placeholder="例如：结构偏移, 边缘脏污"
                onChange={(value) => setRuleForm((prev) => ({ ...prev, issueTagsText: String(value || '') }))}
              />
            </Col>
            <Col xs={12} lg={6}>
              <Typography.Text theme="secondary">输入标签</Typography.Text>
              <Input
                value={ruleForm.inputTagsText}
                placeholder="例如：满版图案, 颜色敏感"
                onChange={(value) => setRuleForm((prev) => ({ ...prev, inputTagsText: String(value || '') }))}
              />
            </Col>
            <Col xs={12}>
              <Typography.Text theme="secondary">说明</Typography.Text>
              <Textarea
                value={ruleForm.description}
                autosize={{ minRows: 3, maxRows: 5 }}
                placeholder="记录验证依据、适用边界和下一次复跑样例。"
                onChange={(value) => setRuleForm((prev) => ({ ...prev, description: String(value || '') }))}
              />
            </Col>
          </Row>
          <Space size={8} breakLine>
            <Button size="small" variant="outline" loading={qualityActionRulesLoading} onClick={() => void refreshQualityActionRules()}>
              刷新台账
            </Button>
          </Space>
        </Space>
      </Dialog>
      <Dialog
        visible={Boolean(sampleTarget)}
        header={sampleTarget ? `固定样例复跑 · ${businessCapabilityVersionOptionLabel(sampleTarget)}` : '固定样例复跑'}
        width={680}
        confirmBtn={sampleBusy ? '提交中...' : '提交复跑'}
        cancelBtn="取消"
        onClose={() => setSampleTarget(null)}
        onConfirm={submitSampleRun}
      >
        <Space direction="vertical" size="small" style={{ width: '100%' }}>
          {sampleError ? <Alert theme="error" message={sampleError} /> : null}
          {sampleNotice ? <Alert theme="success" message={sampleNotice} /> : null}
          <Typography.Text theme="secondary">同一个样例 URL 应在默认版和候选版各跑一次，跑完后到 runId 详情标注质量。</Typography.Text>
          <Row gutter={[12, 12]}>
            <Col xs={12} lg={6}>
              <Typography.Text theme="secondary">样例类型</Typography.Text>
              <Select
                value={sampleForm.sampleKey}
                options={samplePresets.map((preset) => ({
                  label: `${preset.source === 'library' ? '样例库 · ' : ''}${preset.label} · ${preset.hint}`,
                  value: preset.key,
                }))}
                onChange={(value) => {
                  const nextKey = String(value || '');
                  const preset = samplePresets.find((item) => item.key === nextKey);
                  setSampleForm((prev) => ({
                    ...prev,
                    sampleKey: nextKey,
                    imageUrl: preset?.imageUrl || prev.imageUrl,
                    prompt: preset?.prompt || '',
                    generatedImageUrl: preset?.generatedImageUrl || '',
                    extraParamsText: preset?.source === 'library' && preset.inputs && Object.keys(preset.inputs).length > 0
                      ? JSON.stringify(preset.inputs, null, 2)
                      : prev.extraParamsText,
                  }));
                }}
              />
            </Col>
            <Col xs={12} lg={6}>
              <Typography.Text theme="secondary">样例图片 URL</Typography.Text>
              <Input
                value={sampleForm.imageUrl}
                placeholder="https://..."
                onChange={(value) => setSampleForm((prev) => ({ ...prev, imageUrl: String(value || '') }))}
              />
              <div className="podi-business-sample-upload-row">
                <input
                  type="file"
                  accept="image/*"
                  disabled={isReadOnly || sampleUploadLoading}
                  onChange={(event) => {
                    const file = event.currentTarget.files?.[0] || null;
                    event.currentTarget.value = '';
                    void uploadSampleImageToOss(file);
                  }}
                />
                <Typography.Text theme="secondary">
                  {sampleUploadLoading ? '上传中...' : '上传后自动填入 OSS URL'}
                </Typography.Text>
              </div>
            </Col>
            <Col xs={12} lg={6}>
              <Typography.Text theme="secondary">提示词 / 指令</Typography.Text>
              <Input
                value={sampleForm.prompt}
                placeholder="可选，按业务需要填写"
                onChange={(value) => setSampleForm((prev) => ({ ...prev, prompt: String(value || '') }))}
              />
            </Col>
            <Col xs={12} lg={6}>
              <Typography.Text theme="secondary">生成图 URL</Typography.Text>
              <Input
                value={sampleForm.generatedImageUrl}
                placeholder="仅裂变评分或对照样例需要"
                onChange={(value) => setSampleForm((prev) => ({ ...prev, generatedImageUrl: String(value || '') }))}
              />
            </Col>
            <Col span={12}>
              <Typography.Text theme="secondary">附加参数 JSON</Typography.Text>
              <Textarea
                value={sampleForm.extraParamsText}
                autosize={{ minRows: 3, maxRows: 6 }}
                placeholder='例如 {"width": 1536, "height": 1536}'
                onChange={(value) => setSampleForm((prev) => ({ ...prev, extraParamsText: String(value || '') }))}
              />
            </Col>
          </Row>
          <Space size={8} breakLine>
            <Button
              size="small"
              variant="outline"
              loading={sampleSaving}
              disabled={isReadOnly || sampleBusy || sampleSaving}
              onClick={saveCurrentSampleToLibrary}
            >
              保存到样例库
            </Button>
            <Button size="small" variant="outline" loading={qualitySamplesLoading} onClick={() => void refreshQualitySamples()}>
              刷新样例库
            </Button>
          </Space>
        </Space>
      </Dialog>
      <Dialog
        visible={sampleImportVisible}
        header="固定样例库维护"
        width={860}
        confirmBtn={sampleImportLoading ? '处理中...' : sampleImportDryRun ? '预检查' : '导入 / 更新'}
        cancelBtn="关闭"
        onClose={() => setSampleImportVisible(false)}
        onConfirm={submitSampleImport}
      >
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          {sampleImportError ? <Alert theme="error" message={sampleImportError} /> : null}
          {sampleImportReport ? (
            <Alert
              theme={sampleImportReport.failed > 0 ? 'warning' : 'success'}
              message={`导入结果：新增 ${sampleImportReport.created}，更新 ${sampleImportReport.updated}，预检查 ${sampleImportReport.skipped}，失败 ${sampleImportReport.failed}。`}
            />
          ) : null}
          <Row gutter={[12, 12]}>
            <Col xs={12} lg={4}>
              <Typography.Text theme="secondary">默认业务</Typography.Text>
              <Select
                value={sampleImportBusinessKey}
                options={[
                  { label: '按数据中的 businessKey', value: 'all' },
                  ...businessOrchestrationKeys.map((key) => ({ label: businessKeyLabel(key), value: key })),
                ]}
                onChange={(value) => setSampleImportBusinessKey(String(value || 'all'))}
              />
            </Col>
            <Col xs={12} lg={8}>
              <Typography.Text theme="secondary">模式</Typography.Text>
              <div className="podi-business-sample-maintenance-switch">
                <Switch value={sampleImportDryRun} onChange={(value) => setSampleImportDryRun(Boolean(value))} />
                <Typography.Text theme="secondary">先预检查，不写入数据库</Typography.Text>
              </div>
            </Col>
            <Col xs={12}>
              <Typography.Text theme="secondary">批量数据</Typography.Text>
              <Textarea
                value={sampleImportText}
                autosize={{ minRows: 7, maxRows: 12 }}
                placeholder={`支持 JSON 数组或 CSV。字段：businessKey,sampleKey,label,imageUrl,prompt,inputTags,defaultParams,status,sortOrder\n例如：fission,dense-pattern,满版图案,https://...,保持纹理,满版图案,"{""quality"":""preview""}",active,10`}
                onChange={(value) => setSampleImportText(String(value || ''))}
              />
            </Col>
          </Row>
          {sampleImportReport?.items?.length ? (
            <div className="podi-business-sample-import-report">
              {sampleImportReport.items.slice(0, 8).map((item) => (
                <div key={`${item.index}:${item.sampleKey || item.errorCode || item.action}`}>
                  <Tag theme={item.action === 'error' ? 'danger' : item.action.includes('dry_run') ? 'warning' : 'success'} variant="light" size="small">
                    {item.action}
                  </Tag>
                  <Typography.Text>{[item.businessKey, item.sampleKey, item.label].filter(Boolean).join(' · ') || `第 ${item.index + 1} 行`}</Typography.Text>
                  {item.errorCode ? <Typography.Text theme="error">{item.errorCode}</Typography.Text> : null}
                </div>
              ))}
            </div>
          ) : null}
          <div className="podi-business-sample-history-panel">
            <Space align="center" style={{ justifyContent: 'space-between', width: '100%', flexWrap: 'wrap' }}>
              <Typography.Text strong>样例版本历史</Typography.Text>
              <Space size={8} breakLine>
                <Select
                  value={sampleHistoryTargetId}
                  style={{ minWidth: 260 }}
                  options={qualitySamples.map((sample) => ({
                    label: `${businessKeyLabel(sample.businessKey)} · ${sample.label}`,
                    value: sample.id,
                  }))}
                  onChange={(value) => {
                    setSampleHistoryTargetId(String(value || ''));
                    setSampleHistoryItems([]);
                  }}
                />
                <Button size="small" variant="outline" loading={sampleHistoryLoading} onClick={() => void loadSampleHistory()}>
                  查看历史
                </Button>
              </Space>
            </Space>
            {sampleHistoryError ? <Alert theme="error" message={sampleHistoryError} /> : null}
            {sampleHistoryItems.length > 0 ? (
              <div className="podi-business-sample-history-list">
                {sampleHistoryItems.map((item) => (
                  <div key={item.id} className="podi-business-sample-history-item">
                    <Space size={6} breakLine>
                      <Tag variant="light" size="small">
                        v{item.versionNo}
                      </Tag>
                      <Tag theme={item.changeType.includes('import') ? 'primary' : item.changeType === 'archive' ? 'danger' : 'default'} variant="light" size="small">
                        {item.changeType}
                      </Tag>
                      <Typography.Text strong>{item.label}</Typography.Text>
                      <Typography.Text theme="secondary">{formatDateTime(item.createdAt)}</Typography.Text>
                    </Space>
                    <Typography.Text theme="secondary">
                      {[item.actorUsername, item.changeNote, item.status, item.imageUrl].filter(Boolean).join(' · ')}
                    </Typography.Text>
                  </div>
                ))}
              </div>
            ) : (
              <Typography.Text theme="secondary">选择样例后可查看每次新增、更新、导入或归档快照。</Typography.Text>
            )}
          </div>
        </Space>
      </Dialog>
      <Dialog
        visible={Boolean(batchTarget)}
        header={batchTarget ? `批量复跑样例集 · ${businessKeyLabel(batchTarget.businessKey)}` : '批量复跑样例集'}
        width={860}
        confirmBtn={batchBusy ? '提交中...' : '提交批量复跑'}
        cancelBtn="取消"
        onClose={() => setBatchTarget(null)}
        onConfirm={submitBatchRun}
      >
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          {batchError ? <Alert theme="error" message={batchError} /> : null}
          <Typography.Text theme="secondary">
            建议选择“当前默认 + 一个候选版”，同一批样例会写入同一个 batchId。结果完成后，运营在 runId 详情标注质量，面板会形成同批对照。
          </Typography.Text>
          <div className="podi-business-batch-targets">
            <Typography.Text theme="secondary">复跑版本</Typography.Text>
            <Space size={6} breakLine>
              {(batchTarget?.items || []).map((item) => {
                const selected = batchTargetIds.includes(item.id);
                return (
                  <Button
                    key={item.id}
                    size="small"
                    variant={selected ? 'base' : 'outline'}
                    theme={item.isDefault ? 'success' : selected ? 'primary' : 'default'}
                    onClick={() =>
                      setBatchTargetIds((prev) =>
                        prev.includes(item.id) ? prev.filter((id) => id !== item.id) : [...prev, item.id],
                      )
                    }
                  >
                    {item.isDefault ? '默认 · ' : ''}
                    {item.version}
                  </Button>
                );
              })}
            </Space>
          </div>
          <div className="podi-business-batch-sample-list">
            {batchPresets.map((preset) => {
              const row = batchRows[preset.key] || { enabled: true, imageUrl: '', prompt: '', generatedImageUrl: '' };
              const updateRow = (patch: Partial<BusinessFixedSampleBatchRow>) =>
                setBatchRows((prev) => {
                  const current = prev[preset.key] || {
                    enabled: true,
                    imageUrl: '',
                    prompt: preset.prompt || '',
                    generatedImageUrl: '',
                  };
                  return {
                    ...prev,
                    [preset.key]: {
                      ...current,
                      ...patch,
                    },
                  };
                });
              return (
                <section key={preset.key} className="podi-business-batch-sample-row">
                  <div className="podi-business-batch-sample-title">
                    <Switch value={row.enabled} onChange={(value) => updateRow({ enabled: Boolean(value) })} />
	                    <div>
	                      <Typography.Text strong>{preset.label}</Typography.Text>
	                      <div>
	                        <Typography.Text theme="secondary">
	                          {preset.source === 'library' ? '样例库 · ' : ''}
	                          {preset.hint}
	                        </Typography.Text>
	                      </div>
	                    </div>
                  </div>
                  <Row gutter={[10, 10]}>
                    <Col xs={12} lg={6}>
                      <Typography.Text theme="secondary">样例图片 URL</Typography.Text>
                      <Input
                        value={row.imageUrl}
                        disabled={!row.enabled}
                        placeholder="https://..."
                        onChange={(value) => updateRow({ imageUrl: String(value || '') })}
                      />
                    </Col>
                    <Col xs={12} lg={3}>
                      <Typography.Text theme="secondary">提示词 / 指令</Typography.Text>
                      <Input
                        value={row.prompt}
                        disabled={!row.enabled}
                        placeholder="可选"
                        onChange={(value) => updateRow({ prompt: String(value || '') })}
                      />
                    </Col>
                    <Col xs={12} lg={3}>
                      <Typography.Text theme="secondary">生成图 URL</Typography.Text>
                      <Input
                        value={row.generatedImageUrl}
                        disabled={!row.enabled}
                        placeholder="评分场景可填"
                        onChange={(value) => updateRow({ generatedImageUrl: String(value || '') })}
                      />
                    </Col>
                  </Row>
                </section>
              );
            })}
          </div>
          <div>
            <Typography.Text theme="secondary">批量附加参数 JSON</Typography.Text>
            <Textarea
              value={batchExtraParamsText}
              autosize={{ minRows: 3, maxRows: 6 }}
              placeholder='可选，例如 {"quality":"preview"}，会附加到本批所有样例'
              onChange={(value) => setBatchExtraParamsText(String(value || ''))}
            />
          </div>
        </Space>
      </Dialog>
    </>
  );
};

export const BusinessCapabilityGrid = ({
  capabilities,
  pendingApprovals,
  isReadOnly,
  actionLoadingId,
  onEdit,
  onSetDefault,
  onToggleActive,
  onRecordAcceptance,
  onDraftRun,
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
  onDraftRun: (item: BusinessCapability, payload?: Record<string, unknown>) => void | Promise<void>;
  formatDateTime: (value?: string | null) => string;
}) => {
  const [draftRunTarget, setDraftRunTarget] = useState<BusinessCapability | null>(null);
  const [draftRunForm, setDraftRunForm] = useState({
    imageUrl: '',
    generatedImageUrl: '',
    prompt: '',
    extraParamsText: '',
  });
  const [draftRunError, setDraftRunError] = useState<string | null>(null);
  const grouped = capabilities.reduce<Record<string, BusinessCapability[]>>((map, item) => {
    const key = canonicalBusinessKey(item.businessKey);
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

  const openDraftRunDialog = (item: BusinessCapability) => {
    setDraftRunTarget(item);
    setDraftRunError(null);
    setDraftRunForm({
      imageUrl: '',
      generatedImageUrl: '',
      prompt: '',
      extraParamsText: '',
    });
  };
  const submitDraftRunDialog = async () => {
    if (!draftRunTarget) return;
    const imageUrl = draftRunForm.imageUrl.trim();
    const generatedImageUrl = draftRunForm.generatedImageUrl.trim();
    const requiresGenerated = businessDraftRunRequiresGeneratedImage(draftRunTarget.businessKey);
    if (!imageUrl) {
      setDraftRunError('请填写原图 URL。');
      return;
    }
    if (requiresGenerated && !generatedImageUrl) {
      setDraftRunError('裂变评分需要填写生成图 URL。');
      return;
    }
    let extraParams: Record<string, unknown> = {};
    if (draftRunForm.extraParamsText.trim()) {
      try {
        const parsed = JSON.parse(draftRunForm.extraParamsText);
        if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
          setDraftRunError('附加参数必须是 JSON 对象。');
          return;
        }
        extraParams = parsed as Record<string, unknown>;
      } catch {
        setDraftRunError('附加参数 JSON 格式不正确。');
        return;
      }
    }
    const payload: Record<string, unknown> = {
      ...extraParams,
      imageUrl,
    };
    if (draftRunForm.prompt.trim()) {
      payload.prompt = draftRunForm.prompt.trim();
    }
    if (requiresGenerated) {
      payload.originalImageUrl = imageUrl;
      payload.generatedImageUrl = generatedImageUrl;
    }
    await onDraftRun(draftRunTarget, payload);
    setDraftRunTarget(null);
  };
  const draftRunBusy = Boolean(draftRunTarget && actionLoadingId === `draft-run:${draftRunTarget.id}`);
  const draftRunRequiresGenerated = businessDraftRunRequiresGeneratedImage(draftRunTarget?.businessKey);

  return (
    <>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <Alert
          theme="info"
          message="默认只看线上默认、草稿和候选版本；已停用或被替代的历史版本收起到下方，排障或回滚追溯时再展开。"
        />
        {groupKeys.map((businessKey) => {
          const items = grouped[businessKey].slice().sort((left, right) => {
            if (left.isDefault !== right.isDefault) return left.isDefault ? -1 : 1;
            if (left.status !== right.status) return left.status === 'active' ? -1 : 1;
            const lineDiff = businessCapabilityVersionLine(left).priority - businessCapabilityVersionLine(right).priority;
            if (lineDiff !== 0) return lineDiff;
            return String(right.releaseTime || right.createdAt || '').localeCompare(String(left.releaseTime || left.createdAt || ''));
          });
          const defaultItem = items.find((item) => item.isDefault);
          const activeCount = items.filter((item) => item.status === 'active').length;
          const supersededIds = new Set(
            items.map((item) => businessCapabilityVersionLineage(item).supersedesVersionId).filter(Boolean) as string[],
          );
          const currentItems = items.filter((item) => !businessCapabilityIsHistoricalVersion(item, supersededIds));
          const visibleItems = currentItems.length > 0 ? currentItems : items.slice(0, 1);
          const visibleItemIds = new Set(visibleItems.map((item) => item.id));
          const historicalItems = items.filter((item) => !visibleItemIds.has(item.id));
          const lineGroups = visibleItems.reduce<Record<string, BusinessCapability[]>>((map, item) => {
            const line = businessCapabilityVersionLine(item);
            if (!map[line.key]) map[line.key] = [];
            map[line.key].push(item);
            return map;
          }, {});
          const lineGroupEntries = Object.values(lineGroups).sort((left, right) => {
            const leftLine = businessCapabilityVersionLine(left[0]);
            const rightLine = businessCapabilityVersionLine(right[0]);
            return leftLine.priority - rightLine.priority;
          });
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
	                      默认：{defaultItem ? businessCapabilityVersionRoleLabel(defaultItem) : '未设置'}
	                    </Tag>
	                    <Tag variant="light">启用 {activeCount}/{items.length}</Tag>
	                    {historicalItems.length > 0 ? <Tag variant="light">历史 {historicalItems.length}</Tag> : null}
	                  </Space>
	                </Space>
	              }
            >
              <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                {lineGroupEntries.map((lineItems) => {
                  const groupLine = businessCapabilityVersionLine(lineItems[0]);
                  return (
                    <section key={groupLine.key} className="podi-business-version-line-group">
                      <Space align="center" style={{ justifyContent: 'space-between', width: '100%', marginBottom: 10 }}>
                        <Space size={8}>
                          <Tag theme={groupLine.theme as any} variant="light">
                            {groupLine.label}
                          </Tag>
                          <Typography.Text theme="secondary">{groupLine.detail}</Typography.Text>
                        </Space>
                        <Tag variant="light" size="small">
                          {lineItems.length} 个版本
                        </Tag>
                      </Space>
                      <Row gutter={[16, 16]}>
                        {lineItems.map((item) => {
                  const rollout = readCapabilityRollout(item.metadata);
                  const risk = businessCapabilityRiskTag(item);
                  const lifecycle = businessCapabilityLifecycleStatus(item);
                  const versionLine = businessCapabilityVersionLine(item);
                  const lineage = businessCapabilityVersionLineage(item);
                  const relationLabel = businessCapabilityVersionRelationLabel(item, items);
                  const defaultActionId = `default:${item.id}`;
                  const statusActionId = `status:${item.id}`;
                  const acceptanceActionId = `acceptance:${item.id}`;
                  const draftRunActionId = `draft-run:${item.id}`;
                  const isActive = item.status === 'active';
                  const lockDefaultStop = isActive && item.isDefault;
                  const actionBusy = Boolean(actionLoadingId);
                  const defaultSwitchBlocked = item.releaseGate?.canRequestDefault === false;
                  const qualitySwitchBlocked = businessReleaseGateHasQualityBlocker(item.releaseGate);
                  const pendingApproval = pendingApprovals.find(
                    (approval) => approval.targetCapabilityId === item.id && approval.status === 'pending',
                  );

                  return (
                    <Col key={item.id} xs={12} md={6} xl={4}>
                      <Card bordered size="small" style={{ height: '100%' }}>
                      <Space direction="vertical" size="small" style={{ width: '100%' }}>
                        <Space align="start" style={{ justifyContent: 'space-between', width: '100%', gap: 10 }}>
                          <div style={{ minWidth: 0 }}>
                            <Typography.Text strong>{businessCapabilityVersionRoleLabel(item)}</Typography.Text>
                            <div>
                              <Typography.Text theme="secondary">{item.displayName}</Typography.Text>
                            </div>
                            <div>
                              <Typography.Text theme="secondary">{businessCapabilityMediaLabel(item)}</Typography.Text>
                            </div>
                          </div>
                          <Tag theme={risk.theme as any} variant="light">
                            {risk.text}
                          </Tag>
                        </Space>
                        <Space size={6} breakLine>
                          <Tag theme={versionLine.theme as any} variant="light" size="small">
                            {versionLine.label}
                          </Tag>
                          <Tag variant="light" size="small">
                            版本 {item.version}
                          </Tag>
                          {item.isDefault ? (
                            <Tag theme="success" variant="light" size="small">
                              当前默认
                            </Tag>
                          ) : null}
                        </Space>
                        <Typography.Text theme="secondary">{relationLabel}</Typography.Text>
                        {lineage.changeSummary ? (
                          <Typography.Text theme="secondary">更新：{lineage.changeSummary}</Typography.Text>
                        ) : null}
                        <div className="podi-business-version-lineage">
                          <Typography.Text strong>版本关系</Typography.Text>
                          <div className="podi-business-version-lineage__grid">
                            <span>来源版本</span>
                            <strong>
                              {lineage.parentLabel || (lineage.parentVersionId ? formatShortBusinessId(lineage.parentVersionId) : '同路线起点')}
                            </strong>
                            <span>替代版本</span>
                            <strong>
                              {lineage.supersedesLabel || (lineage.supersedesVersionId ? formatShortBusinessId(lineage.supersedesVersionId) : '未指定')}
                            </strong>
                            <span>归属判断</span>
                            <strong>
                              {lineage.decisionLabel || businessVersionDecisionOptions.find((option) => option.value === lineage.decision)?.label || '归属待补'}
                            </strong>
                            <span>更新说明</span>
                            <strong>{lineage.changeSummary || relationLabel}</strong>
                          </div>
                          {lineage.decisionNote ? (
                            <Typography.Text theme="secondary">判断备注：{lineage.decisionNote}</Typography.Text>
                          ) : null}
                        </div>
                        {lineage.breakingChange ? (
                          <Tag theme="warning" variant="light" size="small">
                            破坏兼容，需单独验收
                          </Tag>
                        ) : null}
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
                            <Typography.Text theme="secondary">可用状态</Typography.Text>
                            <div>
                              <Space size={4}>
                                <Tag theme={lifecycle.online.theme} variant="light" size="small">
                                  {lifecycle.online.label}
                                </Tag>
                                <Tag theme={lifecycle.recommendation.theme} variant="light" size="small">
                                  {lifecycle.recommendation.label}
                                </Tag>
                              </Space>
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
                              theme={item.status === 'draft' ? 'primary' : 'default'}
                              variant="outline"
                              loading={actionLoadingId === draftRunActionId}
                              disabled={
                                item.status === 'deprecated' ||
                                item.status === 'disabled' ||
                                (actionBusy && actionLoadingId !== draftRunActionId)
                              }
                              onClick={() => openDraftRunDialog(item)}
                            >
                              {item.status === 'draft' ? '试运行草稿' : '跑一次验证'}
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
                                {defaultSwitchBlocked ? (qualitySwitchBlocked ? '补质量标注' : '先验收') : pendingApproval ? '默认审批中' : '申请设为默认'}
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
                    </section>
                  );
                })}
                {historicalItems.length > 0 ? (
                  <details className="podi-business-disclosure">
                    <summary>
                      <span>历史版本</span>
                      <small>{historicalItems.length} 个已停用或被替代版本，默认不参与日常判断</small>
                    </summary>
                    <div className="podi-business-disclosure-body">
                      <div className="podi-business-history-version-list">
                        {historicalItems.map((item) => {
                          const line = businessCapabilityVersionLine(item);
                          const lineage = businessCapabilityVersionLineage(item);
                          const risk = businessCapabilityRiskTag(item);
                          const statusActionId = `status:${item.id}`;
                          const draftRunActionId = `draft-run:${item.id}`;
                          const actionBusy = Boolean(actionLoadingId);
                          return (
                            <div key={item.id} className="podi-business-history-version-row">
                              <div>
                                <Space size={6} breakLine>
                                  <Typography.Text strong>{businessCapabilityVersionRoleLabel(item)}</Typography.Text>
                                  <Tag theme={risk.theme as any} variant="light" size="small">
                                    {risk.text}
                                  </Tag>
                                  <Tag theme={line.theme as any} variant="light" size="small">
                                    {line.label}
                                  </Tag>
                                  <Tag variant="light" size="small">
                                    版本 {item.version}
                                  </Tag>
                                </Space>
                                <Typography.Text theme="secondary">
                                  {[item.displayName, lineage.changeSummary, businessCapabilityVersionRelationLabel(item, items)]
                                    .filter(Boolean)
                                    .join(' · ')}
                                </Typography.Text>
                              </div>
                              <div className="podi-business-history-version-row__meta">
                                <span>{formatDateTime(item.releaseTime || item.createdAt)}</span>
                                <span>{businessCapabilityLatestRunLabel(item)}</span>
                              </div>
                              {isReadOnly ? (
                                <Tag theme="default" variant="light" size="small">
                                  只读查看
                                </Tag>
                              ) : (
                                <Space size={6} breakLine>
                                  <Button size="small" variant="outline" onClick={() => onEdit(item)}>
                                    编辑
                                  </Button>
                                  <Button
                                    size="small"
                                    variant="outline"
                                    loading={actionLoadingId === draftRunActionId}
                                    disabled={
                                      item.status === 'deprecated' ||
                                      item.status === 'disabled' ||
                                      (actionBusy && actionLoadingId !== draftRunActionId)
                                    }
                                    onClick={() => openDraftRunDialog(item)}
                                  >
                                    跑一次验证
                                  </Button>
                                  <Button
                                    size="small"
                                    theme={item.status === 'active' ? 'warning' : 'primary'}
                                    variant="outline"
                                    loading={actionLoadingId === statusActionId}
                                    disabled={(item.status === 'active' && item.isDefault) || (actionBusy && actionLoadingId !== statusActionId)}
                                    onClick={() => onToggleActive(item)}
                                  >
                                    {item.status === 'active' ? '停用' : '重新启用'}
                                  </Button>
                                </Space>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  </details>
                ) : null}
              </Space>
            </Card>
          );
        })}
      </Space>
      <Dialog
        visible={Boolean(draftRunTarget)}
        header={draftRunTarget ? `试运行：${draftRunTarget.displayName}` : '试运行业务版本'}
        width={680}
        onClose={() => setDraftRunTarget(null)}
        onConfirm={() => {
          void submitDraftRunDialog();
        }}
        confirmBtn={draftRunBusy ? '提交中...' : '提交试运行'}
        cancelBtn="取消"
      >
        <Space direction="vertical" size="small" style={{ width: '100%' }}>
          {draftRunError ? <Alert theme="error" message={draftRunError} /> : null}
          <Alert
            theme="info"
            message="试运行会生成真实 runId 和处理步骤，但来源标记为管理端草稿验证；业务方不会命中草稿版本。"
          />
          <Row gutter={[12, 12]}>
            <Col span={12}>
              <Typography.Text theme="secondary">原图 URL</Typography.Text>
              <Input
                value={draftRunForm.imageUrl}
                placeholder="填写一张可公网访问的样图 URL"
                onChange={(value) => setDraftRunForm((prev) => ({ ...prev, imageUrl: String(value) }))}
              />
            </Col>
            {draftRunRequiresGenerated ? (
              <Col span={12}>
                <Typography.Text theme="secondary">生成图 URL</Typography.Text>
                <Input
                  value={draftRunForm.generatedImageUrl}
                  placeholder="评分接口需要同时提供生成图"
                  onChange={(value) => setDraftRunForm((prev) => ({ ...prev, generatedImageUrl: String(value) }))}
                />
              </Col>
            ) : null}
            <Col span={12}>
              <Typography.Text theme="secondary">提示词 / 额外要求</Typography.Text>
              <Textarea
                autosize={{ minRows: 2, maxRows: 4 }}
                value={draftRunForm.prompt}
                placeholder="可选；不填则使用业务版本默认逻辑"
                onChange={(value) => setDraftRunForm((prev) => ({ ...prev, prompt: String(value) }))}
              />
            </Col>
            <Col span={12}>
              <Typography.Text theme="secondary">附加参数 JSON</Typography.Text>
              <Textarea
                autosize={{ minRows: 2, maxRows: 4 }}
                value={draftRunForm.extraParamsText}
                placeholder='可选，例如 {"bili":"80%","profile":"pattern_risk_routed_v4"}'
                onChange={(value) => setDraftRunForm((prev) => ({ ...prev, extraParamsText: String(value) }))}
              />
            </Col>
          </Row>
          <Typography.Text theme="secondary">
            当前版本：{draftRunTarget ? `${businessKeyLabel(draftRunTarget.businessKey)} · ${draftRunTarget.version}` : '—'}
          </Typography.Text>
        </Space>
      </Dialog>
    </>
  );
};
