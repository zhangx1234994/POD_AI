import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { ChangeEvent, ReactNode } from 'react';
import {
  Alert,
  Button,
  Card,
  Col,
  Input,
  InputNumber,
  Popup,
  Row,
  Select,
  Space,
  Switch,
  Table,
  Tabs,
  Tag,
  Textarea,
  Tooltip,
  Typography,
} from 'tdesign-react';
import { adminApi } from '../services/adminApi';
import type {
  Ability,
  AbilityHealthSummaryResponse,
  AbilityInvocationLog,
  AbilityTemplateStateResponse,
  AbilityTemplateValidateResponse,
  AbilityFormState,
  AbilityLogMetricsResponse,
  AbilityLogMetricBucket,
  ApiKey,
  ApiKeyFormState,
  AuthScopeSummaryResponse,
  AuthSession,
  AuthUser,
  AuthUserFormState,
  BillingCommercialReportResponse,
  BillingMonthlySettlementListResponse,
  BillingMonthlySettlementResponse,
  BillingNotificationConfigResponse,
  BillingInvoiceRequestListResponse,
  BillingOverviewResponse,
  BillingUserDetailResponse,
  Binding,
  BindingFormState,
  BusinessCapability,
  BusinessCapabilityCompareResponse,
  BusinessDefaultApproval,
  BusinessCapabilityFormState,
  BusinessOperationLog,
  BusinessOutputReview,
  BusinessOutputReviewSummaryResponse,
  BusinessRun,
  BusinessUsageSummaryResponse,
  DashboardMetrics,
  DispatchLogEntry,
  Executor,
  ExecutorFormState,
  HealthWatchStatusResponse,
  JsonRecord,
  JsonValue,
  InviteCode,
  InviteCodeCreatePayload,
  MonthlySettlementCollectionNotificationListResponse,
  PackageAlertNotificationListResponse,
  PackageCatalogListResponse,
  PackagePurchaseOrderListResponse,
  PublicAbility,
  ReleaseDecisionRecordResponse,
  ReleasePatrolRecordResponse,
  ReleasePreflightResponse,
  StrategySnapshotResponse,
  WeeklyReportResponse,
  ComfyuiModelCatalogItem,
  ComfyuiPluginCatalogItem,
  ComfyuiVersionCatalogItem,
  ComfyuiServerDiffLog,
  ComfyuiAgent,
  ComfyuiAgentAlert,
  ComfyuiAgentManifest,
  ComfyuiAgentTask,
  ComfyuiAgentTaskEvent,
  ComfyuiDesktopRelease,
  ComfyuiEnrollCode,
  ComfyuiManifestDriftResponse,
  ComfyuiMonitoringSummary,
  ComfyuiRepairJob,
  ComfyuiRepairPlan,
  ComfyuiLora,
  ComfyuiLoraCatalogResponse,
  ComfyuiQueueStatus,
  ComfyuiQueueSummary,
  ComfyuiWorkflowCompatibility,
  SystemConfig,
  StoredAsset,
  VendorEgressCheckResponse,
  VendorGovernanceSummaryResponse,
  VendorKey,
  VendorKeyFormState,
  VendorModel,
  VendorModelFormState,
  VendorProvider,
  VendorUsageSummaryItem,
  Workflow,
  WorkflowFormState,
} from '../types/admin';
import type { UploadResult } from '../types/media';
import { AdminShell } from '../layouts/AdminShell';
import type { AbilityHealthFilter } from '../features/admin/integration/abilityHealth';
import { useAuthActions } from '../features/admin/integration/authActions';
import { useBillingActions } from '../features/admin/integration/billingActions';
import {
  getAbilityHealthTag,
  getAbilityLogCallbackStageTag,
  getAbilityLogSubmitTag,
  isAbilityLogSuccessful,
  resolveLogDurationMs,
} from '../features/admin/integration/abilityLogs';
import {
  integrationNavItems as navItems,
  isAdvancedIntegrationNav as isAdvancedNav,
  type IntegrationNavId as NavId,
} from '../features/admin/integration/navigation';
import { integrationNavIconMap as navIconMap } from '../features/admin/integration/navigationIcons';
import { moduleGuides } from '../features/admin/integration/moduleGuides';
import { AbilityLogDetailDialog, DispatchLogDetailDialog } from '../features/admin/integration/logDetailDialogs';
import { OverviewPanel } from '../features/admin/integration/overview';
import {
  abilityTypeOptions,
  categoryOptions,
  comfyDesktopReleaseStatusOptions,
  comfyDesktopUpdateStatusMeta,
  comfyModelTypeOptions,
  providerOptions,
  statusOptions,
} from '../features/admin/integration/formOptions';
import {
  canonicalBusinessKey,
  coreBusinessKeys,
} from '../features/admin/integration/businessLabels';
import { useBusinessDashboardDerivedState } from '../features/admin/integration/businessDashboardState';
import {
  useBusinessDashboardActions,
  type BusinessRunFilters,
} from '../features/admin/integration/businessDashboardActions';
import {
  comfySyncStepStatusMeta,
  comfyuiGroupBadge,
  comfyuiGroupMeta,
  comfyuiTabGroupOrder,
  comfyuiTabHelpText,
  comfyuiTabMeta,
  createComfyuiGroupMap,
  formatComfyAgentActions,
  readComfyuiTabFromParams,
  type ComfyuiManageTab,
} from '../features/admin/integration/comfyuiDashboardConfig';
import { useComfyuiDashboardDerivedState } from '../features/admin/integration/comfyuiDashboardState';
import { useComfyuiAgentActions } from '../features/admin/integration/comfyuiAgentActions';
import { useComfyuiDesktopActions } from '../features/admin/integration/comfyuiDesktopActions';
import { useComfyuiLoraActions } from '../features/admin/integration/comfyuiLoraActions';
import { useComfyuiManifestActions } from '../features/admin/integration/comfyuiManifestActions';
import { useComfyuiResourceCatalogActions } from '../features/admin/integration/comfyuiResourceCatalogActions';
import {
  useComfyuiServerActions,
  type ComfyServerFormState,
} from '../features/admin/integration/comfyuiServerActions';
import {
  useComfyuiTaskActions,
  type ComfyuiAgentTaskFormState,
} from '../features/admin/integration/comfyuiTaskActions';
import { useWorkflowTemplateActions } from '../features/admin/integration/workflowTemplateActions';
import { useVendorModelActions } from '../features/admin/integration/vendorModelActions';
import { ComfyuiManagementHeader } from '../features/admin/integration/comfyuiManagement';
import {
  formatDate,
  formatDateTime,
  formatDurationSeconds,
  formatPriceValue,
  formatUnitLabel,
} from '../features/admin/integration/formatters';
import {
  abilityDetailTabs,
  abilityLogPageSize,
  abilityLogTabs,
  currentMonthValue,
  defaultAbilityForm,
  defaultApiKeyForm,
  defaultAuthUserForm,
  defaultBindingForm,
  defaultBusinessCapabilityForm,
  defaultComfyPricing,
  defaultExecutorForm,
  defaultInviteCodeForm,
  defaultTestForm,
  defaultVendorKeyForm,
  defaultVendorModelForm,
  defaultWorkflowForm,
  globalAbilityLogPageSize,
  readBusinessRunIdFromHash,
  readEvalRunIdFromHash,
  readHashParams,
  readNavFromHash,
  readOnlyNavIds,
  type AbilityDetailTab,
  type AbilityLogTab,
  type AbilityPricing,
  type AbilityTestForm,
  type AbilityTestResultPayload,
} from '../features/admin/integration/integrationDashboardConfig';
import {
  AbilityApiPanel,
  AbilityCatalogPanel,
  AbilityEditorDialog,
  AbilityEvaluationPage,
  AbilityLogListPanel,
  AbilityLogMetricsPanel,
  AbilityMetadataTab,
  AbilityOverviewSummaryPanel,
  AbilityOverviewTab,
  AbilityParamsTab,
  AbilityRecentLogsPanel,
  AbilityRoadmapPanel,
  AbilityTestingTab,
  AbilityWorkbenchPanel,
  AuthPanel,
  BillingPanel,
  BindingRoutesPanel,
  BusinessAbilityGovernancePanel,
  BusinessActionPanel,
  BusinessCapabilityEditorDialog,
  BusinessCapabilityGrid,
  BusinessCoreClosurePanel,
  BusinessCoreDecisionPanel,
  BusinessEntryCommandPanel,
  BusinessFlowMonitoringPanel,
  BusinessGovernancePanel,
  BusinessOrchestrationMapPanel,
  BusinessOperationLogPanel,
  BusinessQualityCandidatePanel,
  BusinessQualityReviewPanel,
  BusinessReleaseGuardPanel,
  BusinessRunHistoryPanel,
  BusinessUsageSummaryPanel,
  ApiExposurePanel,
  ComfyuiAgentsPanel,
  ComfyuiAlertsPanel,
  ComfyuiAssetsPanel,
  ComfyuiDesktopPanel,
  ComfyuiLorasPanel,
  ComfyuiManifestsPanel,
  ComfyuiServersPanel,
  ComfyuiTasksPanel,
  ComfyuiTemplatesPanel,
  DispatchLogsPanel,
  ExecutorsPanel,
  LegacyApiKeysPanel,
  MonitorPanel,
  SystemConfigPanel,
  VendorModelsPanel,
  WorkflowBuilderPanel,
  panelFallback,
} from '../features/admin/integration/lazyPanels';
import { ActionBar, ErrorState, PageHeader } from '../features/admin/shared/ui';

type BusinessWorkspaceTab = 'governance' | 'runs' | 'map' | 'versions' | 'operations';

const businessWorkspaceTabs: Array<{ label: string; value: BusinessWorkspaceTab }> = [
  { label: '能力治理', value: 'governance' },
  { label: '业务调用', value: 'runs' },
  { label: '业务链路', value: 'map' },
  { label: '版本管理', value: 'versions' },
  { label: '变更治理', value: 'operations' },
];

const businessWorkspaceTabValues = new Set(businessWorkspaceTabs.map((item) => item.value));
const readBusinessWorkspaceTabFromParams = (params: URLSearchParams | null): BusinessWorkspaceTab | null => {
  const value = params?.get('businessTab') as BusinessWorkspaceTab | null;
  return value && businessWorkspaceTabValues.has(value) ? value : null;
};
const readBusinessWorkspaceTabFromHash = (): BusinessWorkspaceTab | null =>
  readBusinessWorkspaceTabFromParams(readHashParams());

type ExecutorTraffic = {
  count: number;
  success: number;
  failed: number;
  successRate: number | null;
  lastSuccessAt?: string | null;
  lastFailedAt?: string | null;
  p95Ms?: number | null;
};

type ComfyNode = {
  id: string;
  title: string;
  classType: string;
  inputs: string[];
};

type ComfyNodeInputDetail = {
  key: string;
  value: unknown;
  linked: boolean;
  linkRef?: string;
};

type ComfyNodeDetail = {
  id: string;
  title: string;
  classType: string;
  inputs: ComfyNodeInputDetail[];
};

type ComfyGraphSource = 'prompt' | 'ui' | 'unknown';

type ComfyDefinitionInfo = {
  ok: boolean;
  source: ComfyGraphSource;
  graph: JsonRecord;
  payload: JsonRecord;
  hasGraphContainer: boolean;
};

const WORKFLOW_VALUE_TYPES = new Set(['string', 'int', 'float', 'bool', 'json']);

type ComfyInputMapItem = {
  field: string;
  nodeId: string;
  inputKey: string;
  valueType?: string;
};

type ComfyWorkflowDependencies = {
  ok: boolean;
  nodes: string[];
  models: {
    unet: string[];
    clip: string[];
    vae: string[];
    lora: string[];
  };
  dynamic: {
    unet: number;
    clip: number;
    vae: number;
    lora: number;
  };
};
const formControlClass =
  'w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100 dark:placeholder:text-slate-500';
const formControlFlexClass =
  'flex-1 rounded-md border border-slate-300 bg-white px-3 py-2 text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100 dark:placeholder:text-slate-500';
const providerLabelMap = providerOptions.reduce<Record<string, string>>((map, option) => {
  map[option.value] = option.label;
  return map;
}, {});
const abilityTypeLabelMap = abilityTypeOptions.reduce<Record<string, string>>((map, option) => {
  map[option.value] = option.label;
  return map;
}, {});
const categoryLabelMap = categoryOptions.reduce<Record<string, string>>((map, option) => {
  map[option.value] = option.label;
  return map;
}, {});
const getProviderLabel = (value: string) => providerLabelMap[value] ?? value;
const getAbilityTypeLabel = (value?: string | null) => {
  if (!value) {
    return abilityTypeLabelMap.api ?? 'api';
  }
  return abilityTypeLabelMap[value] ?? value;
};

const normalizeDesktopOsType = (value?: string | null): string => {
  const raw = String(value || '').trim().toLowerCase();
  if (!raw) return '';
  if (raw === 'windows' || raw === 'win' || raw === 'win32' || raw === 'win64') return 'windows';
  if (raw === 'linux') return 'linux';
  if (raw === 'darwin' || raw === 'mac' || raw === 'macos') return 'macos';
  return raw;
};

const normalizeDesktopArch = (value?: string | null): string => {
  const raw = String(value || '').trim().toLowerCase();
  if (!raw) return '';
  if (raw === 'x64' || raw === 'amd64' || raw === 'x86_64') return 'x64';
  if (raw === 'arm64' || raw === 'aarch64') return 'arm64';
  return raw;
};

const readComfyuiTabFromHash = (): ComfyuiManageTab | null => {
  return readComfyuiTabFromParams(readHashParams());
};
const getCategoryLabel = (value: string) => categoryLabelMap[value] ?? value;
const normalizeKey = (value?: string | null) => (value ? value.trim().toLowerCase().replace(/[\s_]+/g, '-') : '');
const matchesExecutorHint = (executorType: string, hint: string) => {
  if (!executorType || !hint) return false;
  if (executorType === hint) return true;
  return (
    executorType.startsWith(`${hint}-`) ||
    executorType.endsWith(`-${hint}`) ||
    executorType.includes(`${hint}-`) ||
    executorType.includes(`-${hint}`)
  );
};
const collectAbilityExecutorHints = (ability: Ability | null): string[] => {
  if (!ability) return [];
  const hints = new Set<string>();
  const push = (value?: string | null) => {
    const normalized = normalizeKey(value);
    if (normalized) hints.add(normalized);
  };
  push(ability.provider);
  const metadata = ability.metadata;
  const executorType = metadata?.executor_type;
  if (typeof executorType === 'string') push(executorType);
  const executorTag = metadata?.executor_tag;
  if (typeof executorTag === 'string') push(executorTag);
  const appendMany = (value: unknown) => {
    if (Array.isArray(value)) {
      value.forEach((entry) => {
        if (typeof entry === 'string') {
          push(entry);
        } else if (entry !== null && entry !== undefined) {
          push(String(entry));
        }
      });
    } else if (typeof value === 'string') {
      push(value);
    }
  };
  appendMany(metadata?.executor_types);
  appendMany(metadata?.executor_tags);
  return Array.from(hints);
};
const extractExecutorTags = (executor: Executor): string[] => {
  if (Array.isArray(executor.tags) && executor.tags.length > 0) {
    return executor.tags.map((item) => item.trim().toLowerCase()).filter(Boolean);
  }
  const cfg = (executor.config || {}) as Record<string, unknown>;
  const raw = cfg.tags ?? cfg.tag;
  return normalizeTagList(raw).map((item) => item.trim().toLowerCase()).filter(Boolean);
};
const resolveAbilityExecutors = (ability: Ability | null, availableExecutors: Executor[]): Executor[] => {
  if (!ability) return [];
  const hints = collectAbilityExecutorHints(ability);
  const normalizedHints = hints.length > 0 ? hints : [normalizeKey(ability.provider)];
  const matched = availableExecutors.filter((executor) => {
    const executorType = normalizeKey(executor.type);
    if (!executorType) return false;
    return normalizedHints.some((hint) => matchesExecutorHint(executorType, hint));
  });
  const metadata = (ability.metadata || {}) as Record<string, unknown>;
  const requiredTags = normalizeTagList(metadata.required_tags).map((item) => item.trim().toLowerCase()).filter(Boolean);
  const filterByTags = (list: Executor[]) => {
    if (requiredTags.length === 0) return list;
    return list.filter((executor) => {
      const tags = new Set(extractExecutorTags(executor));
      return requiredTags.every((tag) => tags.has(tag));
    });
  };
  const allowedExecutorIds = Array.isArray(metadata.allowed_executor_ids)
    ? metadata.allowed_executor_ids.filter((id): id is string => typeof id === 'string' && id.trim().length > 0)
    : [];
  if (ability.executor_id) {
    const pinned = availableExecutors.find((executor) => executor.id === ability.executor_id);
    if (pinned) {
      const base = filterByTags([pinned, ...matched.filter((executor) => executor.id !== pinned.id)]);
      if (allowedExecutorIds.length > 0) {
        return base.filter((executor) => allowedExecutorIds.includes(executor.id));
      }
      return base;
    }
  }
  if (allowedExecutorIds.length > 0) {
    return filterByTags(matched).filter((executor) => allowedExecutorIds.includes(executor.id));
  }
  return filterByTags(matched);
};

const extractCozeWorkflowId = (ability: Ability | null): string => {
  if (!ability) return '';
  if (ability.coze_workflow_id) {
    return ability.coze_workflow_id;
  }
  const metadata = ability.metadata as JsonRecord | null;
  const metaValue =
    metadata && typeof metadata.coze_workflow_id === 'string' ? metadata.coze_workflow_id.trim() : undefined;
  return metaValue || '';
};

const formatJsonValue = (value?: JsonRecord | null) => (value ? JSON.stringify(value, null, 2) : '');
const toImagePreview = (value?: string | null) => {
  if (!value) return '';
  return value.startsWith('data:') ? value : `data:image/png;base64,${value}`;
};
const getAbilityHealthFilterQuery = (filter: AbilityHealthFilter) => {
  if (filter === 'needs_test') return { needsTest: true };
  if (filter === 'stale') return { staleOnly: true };
  if (filter === 'all') return {};
  return { healthStatus: filter };
};
type AbilityTemplateSummary = {
  currentId: string | null;
  historyCount: number;
  latestAt: string | null;
  latestAction: string | null;
  latestLabel: string | null;
};

const resolveAbilityTemplateSummary = (ability: Ability): AbilityTemplateSummary => {
  const metadata = (ability.metadata || {}) as JsonRecord;
  const registry = metadata.__template_registry;
  if (!registry || typeof registry !== 'object' || Array.isArray(registry)) {
    return {
      currentId: null,
      historyCount: 0,
      latestAt: null,
      latestAction: null,
      latestLabel: null,
    };
  }
  const currentRaw = (registry as JsonRecord).current_template_id;
  const currentId = typeof currentRaw === 'string' && currentRaw.trim() ? currentRaw.trim() : null;
  const historyRaw = (registry as JsonRecord).history;
  const historyList = Array.isArray(historyRaw)
    ? historyRaw.filter((item): item is JsonRecord => Boolean(item && typeof item === 'object' && !Array.isArray(item)))
    : [];
  const latest = historyList[0] || null;
  const latestAtRaw = latest?.created_at;
  const latestAt = typeof latestAtRaw === 'string' && latestAtRaw.trim() ? latestAtRaw.trim() : null;
  const latestActionRaw = latest?.action;
  const latestAction = typeof latestActionRaw === 'string' && latestActionRaw.trim() ? latestActionRaw.trim() : null;
  const latestLabelRaw = latest?.version_label;
  const latestLabel = typeof latestLabelRaw === 'string' && latestLabelRaw.trim() ? latestLabelRaw.trim() : null;
  return {
    currentId,
    historyCount: historyList.length,
    latestAt,
    latestAction,
    latestLabel,
  };
};

const asJsonRecord = (value: unknown): JsonRecord | null => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  return value as JsonRecord;
};
const pickRecord = (source: JsonRecord | null, key: string): JsonRecord | null => {
  if (!source) return null;
  return asJsonRecord(source[key]);
};
const pickString = (source: JsonRecord | null, keys: string[]): string | null => {
  if (!source) return null;
  for (const key of keys) {
    const value = source[key];
    if (typeof value === 'string' && value.trim()) {
      return value.trim();
    }
  }
  return null;
};
const getComfyDesktopUpdateSnapshot = (agent: ComfyuiAgent) => {
  const config = asJsonRecord(agent.config || {});
  const heartbeat = pickRecord(config, 'heartbeat');
  const updateState = pickRecord(heartbeat, 'updateState') || pickRecord(config, 'updateState');
  const payload = pickRecord(updateState, 'payload');
  const runtime = pickRecord(heartbeat, 'runtime');
  const status = pickString(updateState, ['status']) || '';
  const rawCurrentVersion =
    pickString(updateState, ['currentVersion', 'current_version']) ||
    pickString(runtime, ['desktopVersion']) ||
    pickString(config, ['agent_version', 'agentVersion']) ||
    '—';
  const currentVersion = rawCurrentVersion.replace(/^desktop-/, '');
  const targetVersion = pickString(updateState, ['targetVersion', 'target_version']) || '—';
  const updatedAt = pickString(updateState, ['updatedAt', 'updated_at']) || agent.last_heartbeat_at || agent.last_seen_at || null;
  const failureReason =
    pickString(updateState, ['error', 'message']) ||
    pickString(payload, ['error', 'message', 'reason', 'detail']) ||
    null;
  return {
    status,
    currentVersion,
    targetVersion,
    updatedAt,
    failureReason,
  };
};
const getComfyDesktopUpdateTag = (status?: string | null) => {
  const normalized = String(status || '').trim().toLowerCase();
  if (!normalized) return { theme: 'default' as const, text: '未上报' };
  return comfyDesktopUpdateStatusMeta[normalized] || { theme: 'default' as const, text: normalized };
};
const isRolePrimaryAgent = (agent: ComfyuiAgent) => {
  const config = (agent.config || {}) as JsonRecord;
  return Boolean(config?.rolePrimary);
};
const resolveAssetUrl = (asset: StoredAsset) => asset.ossUrl || asset.url || asset.sourceUrl || '';
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

type SchemaFieldType = 'text' | 'textarea' | 'select' | 'number' | 'switch' | 'image';
type SchemaFieldComponent = 'select';

type AbilitySchemaFieldOption = {
  label: string;
  value: string;
};

type AbilitySchemaField = {
  name: string;
  label: string;
  type: SchemaFieldType;
  required?: boolean;
  description?: string;
  placeholder?: string;
  options?: AbilitySchemaFieldOption[];
  defaultValue?: string | number | boolean;
  component?: SchemaFieldComponent;
  allowCustomValue?: boolean;
};

type SchemaFormValues = Record<string, string | boolean>;

const allowedSchemaTypes: SchemaFieldType[] = ['text', 'textarea', 'select', 'number', 'switch', 'image'];
const allowedSchemaComponents: SchemaFieldComponent[] = ['select'];

const getString = (value: unknown): string | undefined => {
  if (typeof value === 'string') {
    const trimmed = value.trim();
    return trimmed ? trimmed : undefined;
  }
  return undefined;
};

const coerceNumber = (value: unknown): number | undefined => {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === 'string') {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : undefined;
  }
  return undefined;
};

const pickLocalized = (record: Record<string, unknown>, candidates: string[]): string | undefined => {
  for (const key of candidates) {
    const result = getString(record[key]);
    if (result) return result;
  }
  return undefined;
};

const composeBilingual = (primary?: string, secondary?: string): string | undefined => {
  const a = primary?.trim();
  const b = secondary?.trim();
  if (a && b && a.toLowerCase() !== b.toLowerCase()) {
    return `${a} (${b})`;
  }
  return a || b || undefined;
};

const normalizeSchemaOptions = (options: unknown): AbilitySchemaFieldOption[] => {
  if (!Array.isArray(options)) return [];
  return options
    .map((entry) => {
      if (typeof entry === 'string') {
        return { label: entry, value: entry };
      }
      if (entry && typeof entry === 'object') {
        const value = 'value' in entry && typeof entry.value === 'string' ? entry.value : null;
        const label = 'label' in entry && typeof entry.label === 'string' ? entry.label : null;
        if (value && label) return { value, label };
        if (value) return { value, label: value };
      }
      return null;
    })
    .filter((item): item is AbilitySchemaFieldOption => Boolean(item));
};

const parseAbilitySchemaFields = (schema?: JsonRecord | null): AbilitySchemaField[] => {
  if (!schema || typeof schema !== 'object') return [];
  const fields = (schema as { fields?: unknown }).fields;
  if (!Array.isArray(fields)) return [];
  const parsed: AbilitySchemaField[] = [];
  fields.forEach((entry) => {
    if (!entry || typeof entry !== 'object') return;
    const record = entry as Record<string, unknown>;
    const name = 'name' in record && typeof record.name === 'string' ? record.name : '';
    if (!name) return;
    const rawType = 'type' in record && typeof record.type === 'string' ? record.type : 'text';
    const type = allowedSchemaTypes.includes(rawType as SchemaFieldType) ? (rawType as SchemaFieldType) : 'text';
    const zhLabel = pickLocalized(record, ['label_zh', 'labelZh', 'label_cn', 'labelCn']);
    const enLabel = pickLocalized(record, ['label_en', 'labelEn', 'labelEN']);
    const baseLabel = getString(record['label']);
    const label = composeBilingual(zhLabel || baseLabel || name, enLabel) || name;
    const zhDescription = pickLocalized(record, ['description_zh', 'descriptionZh']);
    const enDescription = pickLocalized(record, ['description_en', 'descriptionEn']);
    const baseDescription = getString(record['description']);
    const description = composeBilingual(zhDescription || baseDescription, enDescription) || baseDescription;
    const zhPlaceholder = pickLocalized(record, ['placeholder_zh', 'placeholderZh']);
    const enPlaceholder = pickLocalized(record, ['placeholder_en', 'placeholderEn']);
    const basePlaceholder = getString(record['placeholder']);
    const placeholder = composeBilingual(zhPlaceholder || basePlaceholder, enPlaceholder) || basePlaceholder;
    const required = 'required' in record ? Boolean(record.required) : undefined;
    const rawDefault =
      'default' in record
        ? record.default
        : 'defaultValue' in record
          ? record.defaultValue
          : undefined;
    const defaultValue =
      typeof rawDefault === 'string' || typeof rawDefault === 'number' || typeof rawDefault === 'boolean'
        ? rawDefault
        : undefined;
    const options = normalizeSchemaOptions(record.options);
    const componentCandidate = getString(record['component']);
    const componentNormalized = componentCandidate?.toLowerCase() as SchemaFieldComponent | undefined;
    const component = componentNormalized && allowedSchemaComponents.includes(componentNormalized)
      ? componentNormalized
      : undefined;
    const allowCustomValue =
      typeof record['allow_custom_value'] === 'boolean'
        ? record['allow_custom_value']
        : typeof record['allowCustomValue'] === 'boolean'
          ? record['allowCustomValue']
          : undefined;
    parsed.push({
      name,
      type,
      label,
      description: description || undefined,
      placeholder: placeholder || undefined,
      required,
      options: options.length > 0 ? options : undefined,
      defaultValue,
      component,
      allowCustomValue,
    });
  });
  return parsed;
};

const hasJsonContent = (value: unknown): boolean => {
  if (!value || typeof value !== 'object') return false;
  return Object.keys(value as Record<string, unknown>).length > 0;
};

const getAbilitySchemaIssues = (ability: Ability | null): string[] => {
  if (!ability) return [];
  const issues: string[] = [];
  if (parseAbilitySchemaFields(ability.input_schema).length === 0) {
    issues.push('缺少输入表单配置');
  }
  if (!hasJsonContent(ability.metadata)) {
    issues.push('缺少高级配置');
  }
  if (!hasJsonContent(ability.default_params)) {
    issues.push('缺少默认参数');
  }
  const pricing = parsePricingFromMetadata(ability.metadata as JsonRecord | null, ability.provider);
  if (!pricing) {
    issues.push('缺少计价');
  }
  return issues;
};

const formatSchemaValueForInput = (field: AbilitySchemaField, value: unknown): string | boolean => {
  if (field.type === 'switch') {
    if (typeof value === 'boolean') return value;
    if (typeof value === 'string') return value.toLowerCase() === 'true';
    return Boolean(value);
  }
  if (value === undefined || value === null) return '';
  return String(value);
};

const convertSchemaValue = (field: AbilitySchemaField, raw: string | boolean | undefined) => {
  if (raw === undefined || raw === '' || raw === null) return undefined;
  if (field.type === 'number') {
    const num = typeof raw === 'number' ? raw : Number(raw);
    return Number.isNaN(num) ? undefined : num;
  }
  if (field.type === 'switch') {
    return Boolean(raw);
  }
  return raw;
};

const splitByKeys = (source: Record<string, unknown>, keys: string[]) => {
  const rest: Record<string, unknown> = { ...source };
  const picked: Record<string, unknown> = {};
  keys.forEach((key) => {
    if (key in rest) {
      picked[key] = rest[key];
      delete rest[key];
    }
  });
  return { picked, rest };
};

const cleanParams = (params: Record<string, unknown>): JsonRecord => {
  const cleaned: JsonRecord = {};
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '') return;
    cleaned[key] = value as JsonValue;
  });
  return cleaned;
};

const parseMultilineList = (value: unknown): string[] => {
  if (!value && value !== 0) return [];
  if (Array.isArray(value)) {
    return value
      .map((item) => (typeof item === 'string' ? item.trim() : String(item)))
      .map((item) => item.trim())
      .filter((item) => Boolean(item));
  }
  if (typeof value === 'string') {
    const trimmed = value.trim();
    if (!trimmed) return [];
    if ((trimmed.startsWith('[') && trimmed.endsWith(']')) || trimmed.startsWith('{')) {
      try {
        const parsed = JSON.parse(trimmed);
        if (Array.isArray(parsed)) {
          return parsed.map((item) => (typeof item === 'string' ? item.trim() : String(item))).filter(Boolean);
        }
      } catch {
        // fallback to line split
      }
    }
    return trimmed
      .split(/[\n,]/)
      .map((item) => item.trim())
      .filter((item) => Boolean(item));
  }
  const coerced = String(value);
  return coerced ? [coerced] : [];
};

const appendValueToListField = (prev: unknown, entry: string): string => {
  const existing = typeof prev === 'string' ? prev.trim() : '';
  if (!existing) return entry;
  if (existing.includes(entry)) return existing;
  return `${existing}\n${entry}`;
};

const parsePricingFromMetadata = (metadata?: JsonRecord | null, provider?: string): AbilityPricing | null => {
  if (!metadata || typeof metadata !== 'object') {
    return provider === 'comfyui' ? defaultComfyPricing : null;
  }
  const rawPricing = (metadata as Record<string, unknown>).pricing;
  const pricing =
    rawPricing && typeof rawPricing === 'object'
      ? {
          currency: getString((rawPricing as Record<string, unknown>).currency) || undefined,
          unit: getString((rawPricing as Record<string, unknown>).unit) || undefined,
          listPrice: coerceNumber((rawPricing as Record<string, unknown>).list_price ?? (rawPricing as Record<string, unknown>).listPrice),
          discountPrice: coerceNumber(
            (rawPricing as Record<string, unknown>).discount_price ?? (rawPricing as Record<string, unknown>).discountPrice,
          ),
        }
      : null;
  if (pricing && (pricing.listPrice !== undefined || pricing.discountPrice !== undefined)) {
    if (!pricing.currency && provider === 'comfyui') pricing.currency = defaultComfyPricing.currency;
    if (!pricing.unit && provider === 'comfyui') pricing.unit = defaultComfyPricing.unit;
    return pricing;
  }
  if (provider === 'comfyui') {
    return defaultComfyPricing;
  }
  return null;
};

const extractAbilityTags = (ability: Ability): string[] => {
  const tags: string[] = [];
  if (ability.ability_type) {
    tags.push(getAbilityTypeLabel(ability.ability_type));
  }
  const metadata = ability.metadata || {};
  if (metadata && typeof metadata === 'object') {
    const apiType = (metadata as Record<string, unknown>).api_type;
    if (typeof apiType === 'string') tags.push(apiType);
    const supportsVision = (metadata as Record<string, unknown>).supports_vision;
    if (supportsVision) tags.push('视觉');
    const modelId = (metadata as Record<string, unknown>).model_id;
    if (typeof modelId === 'string') tags.push(modelId);
  }
  return tags;
};

const resolveAbilityApiType = (ability: Ability | null): string => {
  if (!ability) return '';
  const metadata = ability.metadata;
  const rawApiType =
    metadata && typeof metadata === 'object' && typeof (metadata as Record<string, unknown>).api_type === 'string'
      ? String((metadata as Record<string, unknown>).api_type)
      : '';
  const normalized = rawApiType.trim().toLowerCase();
  if (normalized) return normalized;
  if (ability.provider === 'kie') {
    if (ability.category === 'image_generation') return 'market_image_to_image';
    if (ability.category === 'video_generation') return 'market_text_to_video';
  }
  if (ability.category === 'image_generation') return 'image_generation';
  if (ability.category === 'text_generation') return 'chat_completions';
  return '';
};

const parseJSON = (value?: string | JsonRecord): JsonRecord => {
  if (!value) return {};
  if (typeof value === 'object') return value;
  try {
    return JSON.parse(value);
  } catch {
    return {};
  }
};

const safeParseJSON = (value?: string | JsonRecord): { ok: boolean; value: JsonRecord } => {
  if (!value) return { ok: true, value: {} };
  if (typeof value === 'object') return { ok: true, value };
  try {
    return { ok: true, value: JSON.parse(value) };
  } catch {
    return { ok: false, value: {} };
  }
};

const isComfyUiDefinition = (record: Record<string, unknown>): boolean => {
  const nodes = record.nodes;
  if (!Array.isArray(nodes)) return false;
  return nodes.some((node) => node && typeof node === 'object' && 'id' in (node as Record<string, unknown>));
};

const isComfyPromptGraph = (record: Record<string, unknown>): boolean => {
  return Object.values(record).some((value) => {
    if (!value || typeof value !== 'object' || Array.isArray(value)) return false;
    return 'class_type' in (value as Record<string, unknown>);
  });
};

const getComfyUiNodeTitle = (raw: Record<string, unknown>, classType: string, nodeId: string) => {
  if (typeof raw.title === 'string' && raw.title.trim()) return raw.title.trim();
  const props = raw.properties;
  if (props && typeof props === 'object') {
    const propTitle = (props as Record<string, unknown>)['Node name for S&R'];
    if (typeof propTitle === 'string' && propTitle.trim()) return propTitle.trim();
  }
  return classType || nodeId;
};

const convertComfyUiToPromptGraph = (record: Record<string, unknown>): JsonRecord => {
  const nodes = Array.isArray(record.nodes) ? (record.nodes as Array<Record<string, unknown>>) : [];
  const links = Array.isArray(record.links) ? (record.links as Array<unknown>) : [];
  const linkMap = new Map<string, { nodeId: string; slot: number }>();
  links.forEach((item) => {
    if (!Array.isArray(item) || item.length < 3) return;
    const [linkId, fromNode, fromSlot] = item;
    if (linkId === null || linkId === undefined) return;
    linkMap.set(String(linkId), {
      nodeId: String(fromNode),
      slot: typeof fromSlot === 'number' ? fromSlot : Number(fromSlot) || 0,
    });
  });
  const graph: JsonRecord = {};
  nodes.forEach((rawNode) => {
    if (!rawNode || typeof rawNode !== 'object') return;
    const nodeIdRaw = rawNode.id;
    if (nodeIdRaw === null || nodeIdRaw === undefined) return;
    const nodeId = String(nodeIdRaw);
    const classType = typeof rawNode.type === 'string' ? rawNode.type : '';
    const inputs: JsonRecord = {};
    const inputList = Array.isArray(rawNode.inputs) ? (rawNode.inputs as Array<Record<string, unknown>>) : null;
    const widgetValues = Array.isArray(rawNode.widgets_values) ? rawNode.widgets_values : [];
    let widgetIndex = 0;
    if (inputList) {
      inputList.forEach((input) => {
        if (!input || typeof input !== 'object') return;
        const key = typeof input.name === 'string' ? input.name : '';
        const linkId = input.link;
        const hasWidget = Boolean(input.widget);
        const linkRef = linkId !== null && linkId !== undefined ? linkMap.get(String(linkId)) : undefined;
        if (linkRef && key) {
          inputs[key] = [linkRef.nodeId, linkRef.slot];
        }
        if (hasWidget) {
          const widgetValue = widgetIndex < widgetValues.length ? widgetValues[widgetIndex] : undefined;
          widgetIndex += 1;
          if (!linkRef && key) {
            inputs[key] = widgetValue;
          }
        }
      });
    } else if (rawNode.inputs && typeof rawNode.inputs === 'object') {
      Object.assign(inputs, rawNode.inputs as Record<string, unknown>);
    }
    const nodePayload: JsonRecord = {
      class_type: classType,
      inputs,
    };
    const title = getComfyUiNodeTitle(rawNode, classType, nodeId);
    if (title) {
      nodePayload._meta = { title };
    }
    graph[nodeId] = nodePayload;
  });
  return graph;
};

const resolveComfyuiDefinition = (definition?: string | JsonRecord): ComfyDefinitionInfo => {
  const parsed = safeParseJSON(definition);
  if (!parsed.ok) {
    return { ok: false, source: 'unknown', graph: {}, payload: {}, hasGraphContainer: false };
  }
  const record = parsed.value as Record<string, unknown>;
  const graphCandidate = record?.graph;
  if (graphCandidate && typeof graphCandidate === 'object' && !Array.isArray(graphCandidate)) {
    return {
      ok: true,
      source: 'prompt',
      graph: graphCandidate as JsonRecord,
      payload: parsed.value,
      hasGraphContainer: true,
    };
  }
  if (isComfyUiDefinition(record)) {
    return {
      ok: true,
      source: 'ui',
      graph: convertComfyUiToPromptGraph(record),
      payload: parsed.value,
      hasGraphContainer: false,
    };
  }
  if (isComfyPromptGraph(record)) {
    return { ok: true, source: 'prompt', graph: parsed.value, payload: parsed.value, hasGraphContainer: false };
  }
  return { ok: true, source: 'unknown', graph: {}, payload: parsed.value, hasGraphContainer: false };
};

const extractComfyuiNodes = (definition?: string | JsonRecord): ComfyNode[] => {
  const info = resolveComfyuiDefinition(definition);
  if (!info.ok) return [];
  const graph = info.graph as Record<string, unknown>;
  if (!graph || typeof graph !== 'object' || Array.isArray(graph)) return [];
  const nodes: ComfyNode[] = [];
  Object.entries(graph).forEach(([id, node]) => {
    if (!node || typeof node !== 'object') return;
    const raw = node as Record<string, unknown>;
    const classType = typeof raw.class_type === 'string' ? raw.class_type : '';
    const meta = raw._meta as Record<string, unknown> | undefined;
    const title = typeof meta?.title === 'string' ? meta.title : classType || id;
    const inputs = raw.inputs && typeof raw.inputs === 'object' ? Object.keys(raw.inputs as Record<string, unknown>) : [];
    nodes.push({ id: String(id), title, classType, inputs });
  });
  nodes.sort((a, b) => {
    const na = Number(a.id);
    const nb = Number(b.id);
    if (!Number.isNaN(na) && !Number.isNaN(nb)) return na - nb;
    return a.id.localeCompare(b.id);
  });
  return nodes;
};

const extractComfyuiNodeDetails = (definition?: string | JsonRecord): ComfyNodeDetail[] => {
  const info = resolveComfyuiDefinition(definition);
  if (!info.ok) return [];
  const graph = info.graph as Record<string, unknown>;
  if (!graph || typeof graph !== 'object' || Array.isArray(graph)) return [];
  const nodes: ComfyNodeDetail[] = [];
  Object.entries(graph).forEach(([id, node]) => {
    if (!node || typeof node !== 'object') return;
    const raw = node as Record<string, unknown>;
    const classType = typeof raw.class_type === 'string' ? raw.class_type : '';
    const meta = raw._meta as Record<string, unknown> | undefined;
    const title = typeof meta?.title === 'string' ? meta.title : classType || id;
    const inputsObj = raw.inputs && typeof raw.inputs === 'object' ? (raw.inputs as Record<string, unknown>) : {};
    const inputs = Object.entries(inputsObj).map(([key, value]) => {
      let linked = false;
      let linkRef: string | undefined;
      if (Array.isArray(value) && value.length >= 2) {
        const refNode = value[0];
        const refIndex = value[1];
        if (typeof refNode === 'string' || typeof refNode === 'number') {
          linked = true;
          linkRef = `#${refNode}${typeof refIndex === 'number' ? `:${refIndex}` : ''}`;
        }
      }
      return { key, value, linked, linkRef };
    });
    inputs.sort((a, b) => a.key.localeCompare(b.key));
    nodes.push({ id: String(id), title, classType, inputs });
  });
  nodes.sort((a, b) => {
    const na = Number(a.id);
    const nb = Number(b.id);
    if (!Number.isNaN(na) && !Number.isNaN(nb)) return na - nb;
    return a.id.localeCompare(b.id);
  });
  return nodes;
};

const COMFY_MODEL_INPUTS: Record<string, Array<{ key: string; category: keyof ComfyWorkflowDependencies['models'] }>> = {
  UNETLoader: [{ key: 'unet_name', category: 'unet' }],
  CheckpointLoaderSimple: [{ key: 'ckpt_name', category: 'unet' }],
  CLIPLoader: [{ key: 'clip_name', category: 'clip' }],
  DualCLIPLoader: [
    { key: 'clip_name1', category: 'clip' },
    { key: 'clip_name2', category: 'clip' },
  ],
  VAELoader: [{ key: 'vae_name', category: 'vae' }],
  LoraLoaderModelOnly: [{ key: 'lora_name', category: 'lora' }],
  LoraLoader: [{ key: 'lora_name', category: 'lora' }],
};

const extractComfyuiWorkflowDependencies = (definition?: string | JsonRecord): ComfyWorkflowDependencies => {
  const empty: ComfyWorkflowDependencies = {
    ok: false,
    nodes: [],
    models: { unet: [], clip: [], vae: [], lora: [] },
    dynamic: { unet: 0, clip: 0, vae: 0, lora: 0 },
  };
  const info = resolveComfyuiDefinition(definition);
  if (!info.ok) return empty;
  const graph = info.graph as Record<string, unknown>;
  if (!graph || typeof graph !== 'object' || Array.isArray(graph)) return empty;
  const nodes = new Set<string>();
  const models = {
    unet: new Set<string>(),
    clip: new Set<string>(),
    vae: new Set<string>(),
    lora: new Set<string>(),
  };
  const dynamic = { unet: 0, clip: 0, vae: 0, lora: 0 };
  Object.values(graph).forEach((rawNode) => {
    if (!rawNode || typeof rawNode !== 'object') return;
    const node = rawNode as Record<string, unknown>;
    const classType = typeof node.class_type === 'string' ? node.class_type : '';
    if (!classType) return;
    nodes.add(classType);
    const inputs = node.inputs && typeof node.inputs === 'object' ? (node.inputs as Record<string, unknown>) : null;
    if (!inputs) return;
    const mapping = COMFY_MODEL_INPUTS[classType] || [];
    mapping.forEach((item) => {
      const value = inputs[item.key];
      if (typeof value === 'string' && value.trim()) {
        models[item.category].add(value.trim());
      } else if (value !== undefined && value !== null) {
        dynamic[item.category] += 1;
      }
    });
  });
  return {
    ok: true,
    nodes: Array.from(nodes).sort(),
    models: {
      unet: Array.from(models.unet).sort(),
      clip: Array.from(models.clip).sort(),
      vae: Array.from(models.vae).sort(),
      lora: Array.from(models.lora).sort(),
    },
    dynamic,
  };
};

const normalizeInputNodeMap = (metadata?: JsonRecord | null): ComfyInputMapItem[] => {
  if (!metadata || typeof metadata !== 'object') return [];
  const raw = (metadata as Record<string, unknown>).input_node_map ?? (metadata as Record<string, unknown>).inputNodeMap;
  if (!Array.isArray(raw)) return [];
  return raw
    .map((item) => {
      if (!item || typeof item !== 'object') return null;
      const record = item as Record<string, unknown>;
      const field = typeof record.field === 'string' ? record.field : typeof record.name === 'string' ? record.name : '';
      const nodeId = typeof record.node_id === 'string' ? record.node_id : typeof record.nodeId === 'string' ? record.nodeId : '';
      const inputKey =
        typeof record.input_key === 'string'
          ? record.input_key
          : typeof record.inputKey === 'string'
            ? record.inputKey
            : typeof record.input === 'string'
              ? record.input
              : '';
      const valueType =
        typeof record.value_type === 'string'
          ? record.value_type
          : typeof record.valueType === 'string'
            ? record.valueType
            : undefined;
      if (!field || !nodeId || !inputKey) return null;
      return {
        field: field.trim(),
        nodeId: String(nodeId).trim(),
        inputKey: String(inputKey).trim(),
        valueType: valueType ? valueType.trim() : undefined,
      } as ComfyInputMapItem;
    })
    .filter((item): item is ComfyInputMapItem => Boolean(item && item.field && item.nodeId && item.inputKey));
};

const serializeInputNodeMap = (items: ComfyInputMapItem[]): JsonRecord[] => {
  return items
    .map((item) => {
      const field = item.field.trim();
      const nodeId = item.nodeId.trim();
      const inputKey = item.inputKey.trim();
      if (!field || !nodeId || !inputKey) return null;
      const record: JsonRecord = {
        field,
        node_id: nodeId,
        input_key: inputKey,
      };
      if (item.valueType && item.valueType.trim()) {
        record.value_type = item.valueType.trim();
      }
      return record;
    })
    .filter((item): item is JsonRecord => Boolean(item));
};

const normalizeOutputNodeIds = (metadata?: JsonRecord | null): string[] => {
  if (!metadata || typeof metadata !== 'object') return [];
  const raw = (metadata as Record<string, unknown>).output_node_ids ?? (metadata as Record<string, unknown>).outputNodeIds;
  if (!Array.isArray(raw)) return [];
  return raw.map((item) => String(item).trim()).filter(Boolean);
};

const extractComfyuiVersionInfo = (executor?: Executor | null, system?: Record<string, unknown> | null) => {
  if (system && typeof system === 'object') {
    const pickSystem = (key: string) =>
      typeof (system as Record<string, unknown>)[key] === 'string'
        ? String((system as Record<string, unknown>)[key]).trim()
        : '';
    const pickSystemAny = (keys: string[]) => {
      for (const key of keys) {
        const value = pickSystem(key);
        if (value) return value;
      }
      return '';
    };
    return {
      version: pickSystemAny(['comfyui_version', 'version', 'comfyuiVersion']),
      commit: pickSystemAny(['comfyui_commit', 'commit', 'git_commit', 'commit_sha']),
      customNodes: pickSystemAny(['installed_templates_version', 'custom_nodes_version']),
      modelsHash: '',
      loraHash: '',
      syncRole: '',
      lastSyncAt: '',
    };
  }
  const config = (executor?.config || {}) as Record<string, unknown>;
  const pick = (keys: string[]) => {
    for (const key of keys) {
      const value = config[key];
      if (typeof value === 'string' && value.trim()) return value.trim();
    }
    return '';
  };
  return {
    version: pick(['comfyui_version', 'comfyuiVersion', 'version']),
    commit: pick(['comfyui_commit', 'commit', 'git_commit', 'commit_sha']),
    customNodes: pick(['custom_nodes_version', 'customNodesVersion', 'custom_nodes']),
    modelsHash: pick(['models_hash', 'modelsHash']),
    loraHash: pick(['lora_hash', 'loraHash']),
    syncRole: pick(['sync_role', 'syncRole', 'role']),
    lastSyncAt: pick(['last_sync_at', 'lastSyncAt']),
  };
};

const extractComfyuiModelCounts = (catalog?: Record<string, string[]>) => {
  const count = (key: string) => (Array.isArray(catalog?.[key]) ? catalog?.[key]?.length || 0 : 0);
  return {
    unet: count('unet'),
    clip: count('clip'),
    vae: count('vae'),
    lora: count('lora'),
  };
};

const diffMissingItems = (baseline: Set<string>, target?: string[] | null) => {
  if (!baseline || baseline.size === 0) return [];
  const targetSet = new Set((target || []).map((item) => String(item).trim()).filter(Boolean));
  const missing: string[] = [];
  baseline.forEach((item) => {
    if (!targetSet.has(item)) {
      missing.push(item);
    }
  });
  return missing;
};

const normalizeTagList = (value: unknown): string[] => {
  const out: string[] = [];
  if (!value) return out;
  if (Array.isArray(value)) {
    value.forEach((item) => {
      if (typeof item === 'string') {
        const trimmed = item.trim();
        if (trimmed) out.push(trimmed);
      } else if (item !== null && item !== undefined) {
        const trimmed = String(item).trim();
        if (trimmed) out.push(trimmed);
      }
    });
    return out;
  }
  if (typeof value === 'string') {
    value
      .replace(/;/g, ',')
      .split(',')
      .map((item) => item.trim())
      .filter(Boolean)
      .forEach((item) => out.push(item));
    return out;
  }
  const trimmed = String(value).trim();
  if (trimmed) out.push(trimmed);
  return out;
};

const normalizeTextList = (value: unknown): string[] => {
  if (typeof value === 'string') {
    return normalizeTagList(value.replace(/[\n，]/g, ','));
  }
  return normalizeTagList(value);
};

const formatTextList = (value?: string[] | null) => {
  if (!value || value.length === 0) return '';
  return value.join(', ');
};

const parseRoutingMetadata = (metadata?: JsonRecord | null) => {
  const record = (metadata || {}) as Record<string, unknown>;
  const policy =
    typeof record.routing_policy === 'string' && record.routing_policy.trim()
      ? record.routing_policy.trim().toLowerCase()
      : 'auto';
  const allowed =
    Array.isArray(record.allowed_executor_ids) ?
      record.allowed_executor_ids.filter((id): id is string => typeof id === 'string' && id.trim().length > 0) :
      [];
  const required = normalizeTagList(record.required_tags);
  const fallback =
    typeof record.fallback_to_default === 'boolean' ? record.fallback_to_default : true;
  return { policy, allowed, required, fallback };
};

const parseLoraMetadata = (metadata?: JsonRecord | null) => {
  const record = (metadata || {}) as Record<string, unknown>;
  const allowedFiles = normalizeTextList(
    record.allowed_lora_files || record.allowed_loras || record.lora_allow_files,
  );
  const allowedTags = normalizeTextList(
    record.allowed_lora_tags || record.lora_allow_tags,
  );
  const allowedBaseModels = normalizeTextList(
    record.allowed_lora_base_models || record.allowed_base_models || record.lora_allow_base_models,
  );
  const defaultLora =
    typeof record.default_lora === 'string' && record.default_lora.trim()
      ? record.default_lora.trim()
      : typeof record.lora_default === 'string' && record.lora_default.trim()
        ? record.lora_default.trim()
        : '';
  const policy =
    typeof record.lora_policy === 'string' && record.lora_policy.trim()
      ? record.lora_policy.trim().toLowerCase()
      : 'fallback';
  return { allowedFiles, allowedTags, allowedBaseModels, defaultLora, policy };
};

const resolveLoraBaseModels = (record?: { base_models?: string[] | null; base_model?: string | null }) => {
  const normalized = normalizeTextList(record?.base_models ?? record?.base_model);
  return Array.from(new Set(normalized));
};

const resolveAgentBaseUrl = (agent?: ComfyuiAgent | null) => {
  if (!agent) return '';
  return (
    agent.baseUrl ||
    agent.base_url ||
    (agent.config && (agent.config as Record<string, unknown>).baseUrl as string) ||
    (agent.config && (agent.config as Record<string, unknown>).base_url as string) ||
    ''
  );
};

const COMFYUI_BASE_MODEL_STORAGE_KEY = 'comfyui.base_models.v1';
const COMFYUI_BASELINE_STORAGE_KEY = 'comfyui.baseline_executor_id';

const isEmptyRecord = (value?: Record<string, unknown> | null) => {
  if (!value) return true;
  return Object.keys(value).length === 0;
};

export function IntegrationDashboard({
  theme,
  currentUser,
  onToggleTheme,
}: {
  theme: 'light' | 'dark';
  currentUser?: AuthUser | null;
  onToggleTheme: () => void;
}) {
  const [pageVisible, setPageVisible] = useState<boolean>(() =>
    typeof document === 'undefined' ? true : document.visibilityState === 'visible',
  );
  const [executors, setExecutors] = useState<Executor[]>([]);
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [bindings, setBindings] = useState<Binding[]>([]);
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([]);
  const [abilities, setAbilities] = useState<Ability[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadErrors, setLoadErrors] = useState<string[]>([]);
  const [activeNav, setActiveNav] = useState<NavId>(() => readNavFromHash() ?? navItems[0].id);
  const [focusedEvalRunId, setFocusedEvalRunId] = useState<string>(() => readEvalRunIdFromHash());
  const [showAdvanced, setShowAdvanced] = useState(() => {
    const navFromHash = readNavFromHash();
    return navFromHash ? isAdvancedNav(navFromHash) : false;
  });
  const contentRef = useRef<HTMLDivElement | null>(null);
  const [dashboardMetrics, setDashboardMetrics] = useState<DashboardMetrics | null>(null);
  const [dispatchLogs, setDispatchLogs] = useState<DispatchLogEntry[]>([]);
  const [dispatchLogDetail, setDispatchLogDetail] = useState<DispatchLogEntry | null>(null);
  const [dispatchLogDetailOpen, setDispatchLogDetailOpen] = useState(false);
  const [systemConfig, setSystemConfig] = useState<SystemConfig | null>(null);
  const [releasePreflightLatest, setReleasePreflightLatest] = useState<ReleasePreflightResponse | null>(null);
  const [releasePreflightSnapshots, setReleasePreflightSnapshots] = useState<ReleasePreflightResponse[]>([]);
  const [releasePreflightLoading, setReleasePreflightLoading] = useState(false);
  const [releasePreflightError, setReleasePreflightError] = useState<string | null>(null);
  const [releasePatrolRecords, setReleasePatrolRecords] = useState<ReleasePatrolRecordResponse[]>([]);
  const [releasePatrolLoading, setReleasePatrolLoading] = useState(false);
  const [releasePatrolError, setReleasePatrolError] = useState<string | null>(null);
  const [releaseDecisionRecords, setReleaseDecisionRecords] = useState<ReleaseDecisionRecordResponse[]>([]);
  const [releaseDecisionLoading, setReleaseDecisionLoading] = useState(false);
  const [releaseDecisionError, setReleaseDecisionError] = useState<string | null>(null);
  const [healthWatchStatus, setHealthWatchStatus] = useState<HealthWatchStatusResponse | null>(null);
  const [healthWatchLoading, setHealthWatchLoading] = useState(false);
  const [healthWatchError, setHealthWatchError] = useState<string | null>(null);
  const [strategySnapshots, setStrategySnapshots] = useState<StrategySnapshotResponse[]>([]);
  const [strategySnapshotLoading, setStrategySnapshotLoading] = useState(false);
  const [strategySnapshotError, setStrategySnapshotError] = useState<string | null>(null);
  const [weeklyReports, setWeeklyReports] = useState<WeeklyReportResponse[]>([]);
  const [weeklyReportLoading, setWeeklyReportLoading] = useState(false);
  const [weeklyReportError, setWeeklyReportError] = useState<string | null>(null);
  const [businessCapabilities, setBusinessCapabilities] = useState<BusinessCapability[]>([]);
  const [businessRuns, setBusinessRuns] = useState<BusinessRun[]>([]);
  const [businessRunTotal, setBusinessRunTotal] = useState(0);
  const [businessUsageSummary, setBusinessUsageSummary] = useState<BusinessUsageSummaryResponse | null>(null);
  const [businessOutputReviewSummary, setBusinessOutputReviewSummary] = useState<BusinessOutputReviewSummaryResponse | null>(null);
  const [businessOutputReviews, setBusinessOutputReviews] = useState<BusinessOutputReview[]>([]);
  const [businessOutputReviewsLoading, setBusinessOutputReviewsLoading] = useState(false);
  const [businessOutputReviewsError, setBusinessOutputReviewsError] = useState<string | null>(null);
  const [businessOperationLogs, setBusinessOperationLogs] = useState<BusinessOperationLog[]>([]);
  const [businessDefaultApprovals, setBusinessDefaultApprovals] = useState<BusinessDefaultApproval[]>([]);
  const [businessRunFilters, setBusinessRunFilters] = useState<BusinessRunFilters>({
    businessKey: 'all',
    status: 'all',
    billingStatus: 'all',
    callbackStatus: 'all',
    issueCategory: 'all',
    version: 'all',
    source: '',
    tenantId: '',
    clientId: '',
    traceId: '',
    windowHours: 24,
    limit: 20,
  });
  const [businessRunDetail, setBusinessRunDetail] = useState<BusinessRun | null>(null);
  const [businessRunDetailOpen, setBusinessRunDetailOpen] = useState(false);
  const [businessOutputReviewFocus, setBusinessOutputReviewFocus] = useState<{ runId: string; outputIndex: number } | null>(null);
  const [focusedBusinessRunId, setFocusedBusinessRunId] = useState<string>(() => readBusinessRunIdFromHash());
  const [businessRunAutoRefresh, setBusinessRunAutoRefresh] = useState(true);
  const [businessWorkspaceTab, setBusinessWorkspaceTab] = useState<BusinessWorkspaceTab>(() => readBusinessWorkspaceTabFromHash() ?? 'governance');
  const [businessDialogOpen, setBusinessDialogOpen] = useState(false);
  const [businessForm, setBusinessForm] = useState<BusinessCapabilityFormState>(defaultBusinessCapabilityForm);
  const [businessFormError, setBusinessFormError] = useState<string | null>(null);
  const [businessActionError, setBusinessActionError] = useState<string | null>(null);
  const [businessActionLoadingId, setBusinessActionLoadingId] = useState<string | null>(null);
  const [businessCompareLeftId, setBusinessCompareLeftId] = useState('');
  const [businessCompareRightId, setBusinessCompareRightId] = useState('');
  const [businessCompareResult, setBusinessCompareResult] = useState<BusinessCapabilityCompareResponse | null>(null);
  const isBusinessReadOnly = Boolean(currentUser && currentUser.role !== 'admin');
  const [authUsers, setAuthUsers] = useState<AuthUser[]>([]);
  const [authSessions, setAuthSessions] = useState<AuthSession[]>([]);
  const [inviteCodes, setInviteCodes] = useState<InviteCode[]>([]);
  const [authScopeSummary, setAuthScopeSummary] = useState<AuthScopeSummaryResponse | null>(null);
  const [authLoading, setAuthLoading] = useState(false);
  const [authError, setAuthError] = useState<string | null>(null);
  const [authUserForm, setAuthUserForm] = useState<AuthUserFormState>(defaultAuthUserForm);
  const [authInviteForm, setAuthInviteForm] = useState<InviteCodeCreatePayload>(defaultInviteCodeForm);
  const [billingMonth, setBillingMonth] = useState(currentMonthValue);
  const [billingWindowDays, setBillingWindowDays] = useState(30);
  const [billingTenantId, setBillingTenantId] = useState('');
  const [billingClientId, setBillingClientId] = useState('');
  const [billingBusinessKey, setBillingBusinessKey] = useState('all');
  const [billingOverview, setBillingOverview] = useState<BillingOverviewResponse | null>(null);
  const [billingMonthlySettlement, setBillingMonthlySettlement] = useState<BillingMonthlySettlementResponse | null>(null);
  const [billingMonthlySettlementRecords, setBillingMonthlySettlementRecords] = useState<BillingMonthlySettlementListResponse | null>(null);
  const [billingPackageAlertNotifications, setBillingPackageAlertNotifications] =
    useState<PackageAlertNotificationListResponse | null>(null);
  const [billingMonthlyCollectionNotifications, setBillingMonthlyCollectionNotifications] =
    useState<MonthlySettlementCollectionNotificationListResponse | null>(null);
  const [billingNotificationConfig, setBillingNotificationConfig] = useState<BillingNotificationConfigResponse | null>(null);
  const [billingCommercialReport, setBillingCommercialReport] = useState<BillingCommercialReportResponse | null>(null);
  const [billingPackageCatalog, setBillingPackageCatalog] = useState<PackageCatalogListResponse | null>(null);
  const [billingPackagePurchaseOrders, setBillingPackagePurchaseOrders] = useState<PackagePurchaseOrderListResponse | null>(null);
  const [billingInvoiceRequests, setBillingInvoiceRequests] = useState<BillingInvoiceRequestListResponse | null>(null);
  const [billingDetail, setBillingDetail] = useState<BillingUserDetailResponse | null>(null);
  const [billingSelectedUserId, setBillingSelectedUserId] = useState('');
  const [billingLoading, setBillingLoading] = useState(false);
  const [billingExporting, setBillingExporting] = useState(false);
  const [billingError, setBillingError] = useState<string | null>(null);
  const [vendorProviders, setVendorProviders] = useState<VendorProvider[]>([]);
  const [vendorModels, setVendorModels] = useState<VendorModel[]>([]);
  const [vendorKeys, setVendorKeys] = useState<VendorKey[]>([]);
  const [vendorUsageItems, setVendorUsageItems] = useState<VendorUsageSummaryItem[]>([]);
  const [vendorGovernanceSummary, setVendorGovernanceSummary] = useState<VendorGovernanceSummaryResponse | null>(null);
  const [vendorUsageWindowHours, setVendorUsageWindowHours] = useState(24);
  const [vendorBaseUrl, setVendorBaseUrl] = useState('');
  const [vendorLoading, setVendorLoading] = useState(false);
  const [vendorError, setVendorError] = useState('');
  const [vendorNotice, setVendorNotice] = useState('');
  const [vendorEgressChecks, setVendorEgressChecks] = useState<Record<string, VendorEgressCheckResponse>>({});
  const [vendorKeyForm, setVendorKeyForm] = useState<VendorKeyFormState>(defaultVendorKeyForm);
  const [vendorModelForm, setVendorModelForm] = useState<VendorModelFormState>(defaultVendorModelForm);
  const [vendorModelFormError, setVendorModelFormError] = useState<string | null>(null);
  const [abilityForm, setAbilityForm] = useState<AbilityFormState>(defaultAbilityForm);
  const [abilityDialogOpen, setAbilityDialogOpen] = useState(false);
  const [selectedAbilityId, setSelectedAbilityId] = useState<string | null>(null);
  const [abilityRoutingPolicy, setAbilityRoutingPolicy] = useState<string>('auto');
  const [abilityAllowedExecutors, setAbilityAllowedExecutors] = useState<string[]>([]);
  const [abilityRequiredTags, setAbilityRequiredTags] = useState<string>('');
  const [abilityFallbackToDefault, setAbilityFallbackToDefault] = useState<boolean>(true);
  const [abilityLoraDefault, setAbilityLoraDefault] = useState<string>('');
  const [abilityLoraAllowedFiles, setAbilityLoraAllowedFiles] = useState<string[]>([]);
  const [abilityLoraAllowedTags, setAbilityLoraAllowedTags] = useState<string>('');
  const [abilityLoraAllowedBaseModels, setAbilityLoraAllowedBaseModels] = useState<string[]>([]);
  const [abilityLoraPolicy, setAbilityLoraPolicy] = useState<string>('fallback');
  const [abilitySearch, setAbilitySearch] = useState('');
  const [abilityProviderFilter, setAbilityProviderFilter] = useState<string>('all');
  const [abilityStatusFilter, setAbilityStatusFilter] = useState<string>('all');
  const [activeAbilityDetailTab, setActiveAbilityDetailTab] = useState<AbilityDetailTab>('overview');
  const [abilityLogDetail, setAbilityLogDetail] = useState<AbilityInvocationLog | null>(null);
  const [abilityLogDetailOpen, setAbilityLogDetailOpen] = useState(false);
  const [abilityLogResolveLoading, setAbilityLogResolveLoading] = useState(false);
  const [abilityLogResolveError, setAbilityLogResolveError] = useState<string | null>(null);
  const [abilityLogTab, setAbilityLogTab] = useState<AbilityLogTab>('logs');
  const [globalAbilityLogProvider, setGlobalAbilityLogProvider] = useState<string>('all');
  const [globalAbilityLogSource, setGlobalAbilityLogSource] = useState<string>('all');
  const [globalAbilityLogStatus, setGlobalAbilityLogStatus] = useState<string>('all');
  const [globalAbilityLogCapabilityKey, setGlobalAbilityLogCapabilityKey] = useState<string>('all');
  const [globalAbilityLogTemplatePublished, setGlobalAbilityLogTemplatePublished] = useState<string>('all');
  const [globalAbilityLogOnlyCallbackFailed, setGlobalAbilityLogOnlyCallbackFailed] = useState<boolean>(false);
  const [globalAbilityLogSearch, setGlobalAbilityLogSearch] = useState<string>('');
  const [globalAbilityLogWindowHours, setGlobalAbilityLogWindowHours] = useState<number>(6);
  const [executorForm, setExecutorForm] = useState<ExecutorFormState>(defaultExecutorForm);
  const [workflowForm, setWorkflowForm] = useState<WorkflowFormState>(defaultWorkflowForm);
  const [workflowFormAllowedExecutors, setWorkflowFormAllowedExecutors] = useState<string[]>([]);
  const [workflowInputMap, setWorkflowInputMap] = useState<ComfyInputMapItem[]>([]);
  const [workflowOutputNodeIds, setWorkflowOutputNodeIds] = useState<string[]>([]);
  const [workflowInputPickerNodeId, setWorkflowInputPickerNodeId] = useState<string>('');
  const [workflowInputPickerKeys, setWorkflowInputPickerKeys] = useState<string[]>([]);
  const [workflowOutputPickerNodeId, setWorkflowOutputPickerNodeId] = useState<string>('');
  const [workflowOutputShowAll, setWorkflowOutputShowAll] = useState(false);
  const [workflowNodeSearch, setWorkflowNodeSearch] = useState<string>('');
  const [workflowParamScope, setWorkflowParamScope] = useState<'internal' | 'all'>('internal');
  const [workflowEditTab, setWorkflowEditTab] = useState<'base' | 'io' | 'params' | 'executors' | 'advanced'>('base');
  const [workflowFormErrors, setWorkflowFormErrors] = useState<string[]>([]);
  const [bindingForm, setBindingForm] = useState<BindingFormState>(defaultBindingForm);
  const [apiKeyForm, setApiKeyForm] = useState<ApiKeyFormState>(defaultApiKeyForm);
  const [testForm, setTestForm] = useState<AbilityTestForm>(defaultTestForm);
  const [testResult, setTestResult] = useState<AbilityTestResultPayload | null>(null);
  const [testLoading, setTestLoading] = useState(false);
  const [schemaValues, setSchemaValues] = useState<SchemaFormValues>({});
  const [comfyModelCache, setComfyModelCache] = useState<Record<string, Record<string, string[]>>>({});
  const [comfyBaseModelCache, setComfyBaseModelCache] = useState<Record<string, string[]>>({});
  const [comfyNodeCache, setComfyNodeCache] = useState<Record<string, string[]>>({});
  const [comfyModelLoading, setComfyModelLoading] = useState(false);
  const [comfyModelError, setComfyModelError] = useState<string | null>(null);
  const [comfyModelLoadingByExecutor, setComfyModelLoadingByExecutor] = useState<Record<string, boolean>>({});
  const [comfyModelErrorByExecutor, setComfyModelErrorByExecutor] = useState<Record<string, string>>({});
  const [comfySystemCache, setComfySystemCache] = useState<Record<string, Record<string, unknown>>>({});
  const [comfySystemLoadingByExecutor, setComfySystemLoadingByExecutor] = useState<Record<string, boolean>>({});
  const [comfySystemErrorByExecutor, setComfySystemErrorByExecutor] = useState<Record<string, string>>({});
  const [comfyQueueStatus, setComfyQueueStatus] = useState<ComfyuiQueueStatus | null>(null);
  const [comfyQueueLoading, setComfyQueueLoading] = useState(false);
  const [comfyQueueError, setComfyQueueError] = useState<string | null>(null);
  const [comfyQueueUpdatedAt, setComfyQueueUpdatedAt] = useState<string | null>(null);
  const [comfyQueueSummary, setComfyQueueSummary] = useState<ComfyuiQueueSummary | null>(null);
  const [comfyQueueSummaryLoading, setComfyQueueSummaryLoading] = useState(false);
  const [comfyQueueSummaryError, setComfyQueueSummaryError] = useState<string | null>(null);
  const [comfyQueueSummaryUpdatedAt, setComfyQueueSummaryUpdatedAt] = useState<string | null>(null);
  const [comfyWorkflowCompatibility, setComfyWorkflowCompatibility] = useState<ComfyuiWorkflowCompatibility | null>(null);
  const [comfyWorkflowCompatibilityLoading, setComfyWorkflowCompatibilityLoading] = useState(false);
  const [comfyWorkflowCompatibilityError, setComfyWorkflowCompatibilityError] = useState<string | null>(null);
  const [comfyWorkflowCompatibilityUpdatedAt, setComfyWorkflowCompatibilityUpdatedAt] = useState<string | null>(null);
  const [comfyLoraSelectCache, setComfyLoraSelectCache] = useState<Record<string, ComfyuiLora[]>>({});
  const [comfyShowTestNodes, setComfyShowTestNodes] = useState(false);
  const [comfyuiManageTab, setComfyuiManageTab] = useState<ComfyuiManageTab>(() => readComfyuiTabFromHash() ?? 'lora');
  const [comfyAgentList, setComfyAgentList] = useState<ComfyuiAgent[]>([]);
  const [comfyAgentLoading, setComfyAgentLoading] = useState(false);
  const [comfyAgentError, setComfyAgentError] = useState<string | null>(null);
  const [comfyAgentDialogOpen, setComfyAgentDialogOpen] = useState(false);
  const [comfyAgentSaving, setComfyAgentSaving] = useState(false);
  const [comfyAgentForm, setComfyAgentForm] = useState<Partial<ComfyuiAgent>>({
    status: 'active',
    allowed: true,
  });
  const [comfyAgentConfigInput, setComfyAgentConfigInput] = useState('');
  const [comfyAgentFormError, setComfyAgentFormError] = useState<string | null>(null);
  const [comfyAgentStatusFilter, setComfyAgentStatusFilter] = useState('all');
  const [comfyManifestList, setComfyManifestList] = useState<ComfyuiAgentManifest[]>([]);
  const [comfyManifestLoading, setComfyManifestLoading] = useState(false);
  const [comfyManifestError, setComfyManifestError] = useState<string | null>(null);
  const [comfyManifestDialogOpen, setComfyManifestDialogOpen] = useState(false);
  const [comfyManifestSaving, setComfyManifestSaving] = useState(false);
  const [comfyManifestActionLoading, setComfyManifestActionLoading] = useState<Record<number, boolean>>({});
  const [comfyManifestEditorMode, setComfyManifestEditorMode] = useState<'wizard' | 'json'>('wizard');
  const [comfyManifestIncludeInactive, setComfyManifestIncludeInactive] = useState(false);
  const [comfyManifestForm, setComfyManifestForm] = useState<Partial<ComfyuiAgentManifest>>({
    status: 'draft',
  });
  const [comfyManifestContentInput, setComfyManifestContentInput] = useState('');
  const [comfyManifestFormError, setComfyManifestFormError] = useState<string | null>(null);
  const [comfyManifestRoleFilter, setComfyManifestRoleFilter] = useState('');
  const [comfyManifestStatusFilter, setComfyManifestStatusFilter] = useState('all');
  const [comfyManifestDriftDialogOpen, setComfyManifestDriftDialogOpen] = useState(false);
  const [comfyManifestDriftLoading, setComfyManifestDriftLoading] = useState(false);
  const [comfyManifestDriftError, setComfyManifestDriftError] = useState<string | null>(null);
  const [comfyManifestDriftData, setComfyManifestDriftData] = useState<ComfyuiManifestDriftResponse | null>(null);
  const [comfyManifestDriftTitle, setComfyManifestDriftTitle] = useState('');
  const [comfyManifestDriftContext, setComfyManifestDriftContext] = useState<{ manifestId: number; agentId: string } | null>(null);
  const [comfyRepairPlanLoading, setComfyRepairPlanLoading] = useState(false);
  const [comfyRepairPlan, setComfyRepairPlan] = useState<ComfyuiRepairPlan | null>(null);
  const [comfyRepairJobLoading, setComfyRepairJobLoading] = useState(false);
  const [comfyRepairJobs, setComfyRepairJobs] = useState<ComfyuiRepairJob[]>([]);
  const [comfyAgentTasks, setComfyAgentTasks] = useState<ComfyuiAgentTask[]>([]);
  const [comfyAgentTasksLoading, setComfyAgentTasksLoading] = useState(false);
  const [comfyAgentTasksError, setComfyAgentTasksError] = useState<string | null>(null);
  const [comfyAgentTaskAgentFilter, setComfyAgentTaskAgentFilter] = useState('all');
  const [comfyAgentTaskStatusFilter, setComfyAgentTaskStatusFilter] = useState('all');
  const [comfyAgentTaskForm, setComfyAgentTaskForm] = useState<ComfyuiAgentTaskFormState>({
    taskId: '',
    agentId: '',
    manifestId: '',
    manifestUrl: '',
    actions: '',
    expiresAt: '',
  });
  const [comfyServersAssistOpen, setComfyServersAssistOpen] = useState(false);
  const [comfyManifestsAssistOpen, setComfyManifestsAssistOpen] = useState(false);
  const [comfyAgentTaskPushAfterCreate, setComfyAgentTaskPushAfterCreate] = useState(true);
  const [comfyTaskAdvancedOpen, setComfyTaskAdvancedOpen] = useState(false);
  const [comfyAgentTaskSaving, setComfyAgentTaskSaving] = useState(false);
  const [comfyAgentTaskFormError, setComfyAgentTaskFormError] = useState<string | null>(null);
  const [comfyAgentTaskPushLoading, setComfyAgentTaskPushLoading] = useState<Record<string, boolean>>({});
  const [comfyAgentTaskEvents, setComfyAgentTaskEvents] = useState<ComfyuiAgentTaskEvent[]>([]);
  const [comfyAgentTaskEventsLoading, setComfyAgentTaskEventsLoading] = useState(false);
  const [comfyAgentTaskEventsError, setComfyAgentTaskEventsError] = useState<string | null>(null);
  const [comfyAgentTaskEventsDialogOpen, setComfyAgentTaskEventsDialogOpen] = useState(false);
  const [comfyAgentTaskEventsTaskId, setComfyAgentTaskEventsTaskId] = useState('');
  const [comfyAgentAlerts, setComfyAgentAlerts] = useState<ComfyuiAgentAlert[]>([]);
  const [comfyAgentAlertsLoading, setComfyAgentAlertsLoading] = useState(false);
  const [comfyAgentAlertsError, setComfyAgentAlertsError] = useState<string | null>(null);
  const [comfyAgentAlertsAgentFilter, setComfyAgentAlertsAgentFilter] = useState('all');
  const [comfyAgentAlertsTypeFilter, setComfyAgentAlertsTypeFilter] = useState('');
  const [comfyAgentAlertsLimit, setComfyAgentAlertsLimit] = useState(50);
  const [comfyAgentTokenDialogOpen, setComfyAgentTokenDialogOpen] = useState(false);
  const [comfyAgentTokenAgentId, setComfyAgentTokenAgentId] = useState('');
  const [comfyAgentTokenValue, setComfyAgentTokenValue] = useState('');
  const [comfyAgentTokenExpiresAt, setComfyAgentTokenExpiresAt] = useState('');
  const [comfyAgentTokenError, setComfyAgentTokenError] = useState<string | null>(null);
  const [comfyAgentTokenLoading, setComfyAgentTokenLoading] = useState(false);
  const [comfyAgentPrimarySaving, setComfyAgentPrimarySaving] = useState<Record<string, boolean>>({});
  const [comfyEnrollCodes, setComfyEnrollCodes] = useState<ComfyuiEnrollCode[]>([]);
  const [comfyEnrollCodesLoading, setComfyEnrollCodesLoading] = useState(false);
  const [comfyEnrollCodesError, setComfyEnrollCodesError] = useState<string | null>(null);
  const [comfyEnrollCodeRole, setComfyEnrollCodeRole] = useState('full');
  const [comfyEnrollCodeTtlSeconds, setComfyEnrollCodeTtlSeconds] = useState(600);
  const [comfyEnrollCodeMaxUses, setComfyEnrollCodeMaxUses] = useState(1);
  const [comfyEnrollCodeNote, setComfyEnrollCodeNote] = useState('');
  const [comfyEnrollCodeCreating, setComfyEnrollCodeCreating] = useState(false);
  const [comfyDesktopReleases, setComfyDesktopReleases] = useState<ComfyuiDesktopRelease[]>([]);
  const [comfyDesktopReleasesLoading, setComfyDesktopReleasesLoading] = useState(false);
  const [comfyDesktopReleasesError, setComfyDesktopReleasesError] = useState<string | null>(null);
  const [comfyDesktopReleaseStatusFilter, setComfyDesktopReleaseStatusFilter] = useState('all');
  const [comfyDesktopInstallReleaseId, setComfyDesktopInstallReleaseId] = useState('');
  const [comfyDesktopReleaseDialogOpen, setComfyDesktopReleaseDialogOpen] = useState(false);
  const [comfyDesktopReleaseSaving, setComfyDesktopReleaseSaving] = useState(false);
  const [comfyDesktopReleaseFormError, setComfyDesktopReleaseFormError] = useState<string | null>(null);
  const [comfyDesktopReleaseForm, setComfyDesktopReleaseForm] = useState<Partial<ComfyuiDesktopRelease>>({
    channel: 'stable',
    osType: 'windows',
    arch: 'x64',
    status: 'active',
  });
  const [comfyDesktopReleasePayloadInput, setComfyDesktopReleasePayloadInput] = useState('');
  const [comfyMonitoringSummary, setComfyMonitoringSummary] = useState<ComfyuiMonitoringSummary | null>(null);
  const [comfyMonitoringLoading, setComfyMonitoringLoading] = useState(false);
  const [comfyMonitoringError, setComfyMonitoringError] = useState<string | null>(null);
  const [comfyMonitoringWindowHours, setComfyMonitoringWindowHours] = useState<number>(24);
  const [comfyBaselineExecutorId, setComfyBaselineExecutorId] = useState<string>('');
  const [comfyLoraCatalog, setComfyLoraCatalog] = useState<ComfyuiLoraCatalogResponse | null>(null);
  const [comfyLoraLoading, setComfyLoraLoading] = useState(false);
  const [comfyLoraError, setComfyLoraError] = useState<string | null>(null);
  const [comfyLoraUntrackedLoaded, setComfyLoraUntrackedLoaded] = useState(false);
  const [comfyLoraSaving, setComfyLoraSaving] = useState(false);
  const [comfyLoraExecutorId, setComfyLoraExecutorId] = useState<string>('');
  const [comfyLoraSearch, setComfyLoraSearch] = useState('');
  const [comfyLoraStatusFilter, setComfyLoraStatusFilter] = useState<string>('all');
  const [comfyLoraDialogOpen, setComfyLoraDialogOpen] = useState(false);
  const [comfyLoraForm, setComfyLoraForm] = useState<Partial<ComfyuiLora>>({ status: 'active' });
  const [comfyLoraTagsInput, setComfyLoraTagsInput] = useState('');
  const [comfyLoraTriggersInput, setComfyLoraTriggersInput] = useState('');
  const [comfyLoraFormError, setComfyLoraFormError] = useState<string | null>(null);
  const [comfyServerForm, setComfyServerForm] = useState<ComfyServerFormState>({
    name: '',
    base_url: '',
    max_concurrency: 1,
    weight: 1,
    status: 'active',
  });
  const [comfyServerFormError, setComfyServerFormError] = useState<string | null>(null);
  const [comfyServerSaving, setComfyServerSaving] = useState(false);
  const [comfyServerRefreshing, setComfyServerRefreshing] = useState(false);
  const [comfyDiffDialogOpen, setComfyDiffDialogOpen] = useState(false);
  const [comfyDiffDialogTitle, setComfyDiffDialogTitle] = useState('');
  const [comfyDiffDialogPayload, setComfyDiffDialogPayload] = useState<unknown>(null);
  const [comfyDiffSaving, setComfyDiffSaving] = useState(false);
  const [comfyDiffLogs, setComfyDiffLogs] = useState<ComfyuiServerDiffLog[]>([]);
  const [comfyDiffLogsLoading, setComfyDiffLogsLoading] = useState(false);
  const [comfyDiffLogsError, setComfyDiffLogsError] = useState<string | null>(null);
  const [comfyModelCatalogItems, setComfyModelCatalogItems] = useState<ComfyuiModelCatalogItem[]>([]);
  const [comfyModelCatalogLoading, setComfyModelCatalogLoading] = useState(false);
  const [comfyModelCatalogError, setComfyModelCatalogError] = useState<string | null>(null);
  const [comfyModelCatalogSearch, setComfyModelCatalogSearch] = useState('');
  const [comfyModelCatalogStatus, setComfyModelCatalogStatus] = useState('all');
  const [comfyModelCatalogType, setComfyModelCatalogType] = useState('all');
  const [comfyModelDialogOpen, setComfyModelDialogOpen] = useState(false);
  const [comfyModelSaving, setComfyModelSaving] = useState(false);
  const [comfyModelFormError, setComfyModelFormError] = useState<string | null>(null);
  const [comfyModelForm, setComfyModelForm] = useState<Partial<ComfyuiModelCatalogItem>>({
    status: 'active',
    model_type: 'unet',
  });
  const [comfyModelFormTags, setComfyModelFormTags] = useState('');
  const [comfyVersionCatalogItems, setComfyVersionCatalogItems] = useState<ComfyuiVersionCatalogItem[]>([]);
  const [comfyVersionCatalogLoading, setComfyVersionCatalogLoading] = useState(false);
  const [comfyVersionCatalogError, setComfyVersionCatalogError] = useState<string | null>(null);
  const [comfyVersionCatalogSearch, setComfyVersionCatalogSearch] = useState('');
  const [comfyVersionCatalogStatus, setComfyVersionCatalogStatus] = useState('all');
  const [comfyVersionServerLoading, setComfyVersionServerLoading] = useState(false);
  const [comfyVersionDialogOpen, setComfyVersionDialogOpen] = useState(false);
  const [comfyVersionSaving, setComfyVersionSaving] = useState(false);
  const [comfyVersionSyncing, setComfyVersionSyncing] = useState(false);
  const [comfyVersionFormError, setComfyVersionFormError] = useState<string | null>(null);
  const [comfyVersionForm, setComfyVersionForm] = useState<Partial<ComfyuiVersionCatalogItem>>({
    status: 'active',
  });
  const [comfyPluginCatalogItems, setComfyPluginCatalogItems] = useState<ComfyuiPluginCatalogItem[]>([]);
  const [comfyPluginCatalogLoading, setComfyPluginCatalogLoading] = useState(false);
  const [comfyPluginCatalogError, setComfyPluginCatalogError] = useState<string | null>(null);
  const [comfyPluginCatalogSearch, setComfyPluginCatalogSearch] = useState('');
  const [comfyPluginCatalogStatus, setComfyPluginCatalogStatus] = useState('all');
  const [comfyPluginDialogOpen, setComfyPluginDialogOpen] = useState(false);
  const [comfyPluginSaving, setComfyPluginSaving] = useState(false);
  const [comfyPluginFormError, setComfyPluginFormError] = useState<string | null>(null);
  const [comfyPluginForm, setComfyPluginForm] = useState<Partial<ComfyuiPluginCatalogItem>>({
    status: 'active',
  });
  const [comfyPluginFormTags, setComfyPluginFormTags] = useState('');
  const [uploadingImage, setUploadingImage] = useState(false);
  const [uploadedImage, setUploadedImage] = useState<UploadResult | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [abilityLogs, setAbilityLogs] = useState<AbilityInvocationLog[]>([]);
  const [abilityLogsLoading, setAbilityLogsLoading] = useState(false);
  const [abilityLogsError, setAbilityLogsError] = useState<string | null>(null);
  const [abilityLogTotal, setAbilityLogTotal] = useState<number | null>(null);
  const [abilityLogPage, setAbilityLogPage] = useState(1);
  const [abilityLogsAutoRefresh, setAbilityLogsAutoRefresh] = useState(true);
  const [abilityLogsUpdatedAt, setAbilityLogsUpdatedAt] = useState<string | null>(null);
  const [globalAbilityLogs, setGlobalAbilityLogs] = useState<AbilityInvocationLog[]>([]);
  const [globalAbilityLogsLoading, setGlobalAbilityLogsLoading] = useState(false);
  const [globalAbilityLogsError, setGlobalAbilityLogsError] = useState<string | null>(null);
  const [globalAbilityLogTotal, setGlobalAbilityLogTotal] = useState<number | null>(null);
  const [globalAbilityLogPage, setGlobalAbilityLogPage] = useState(1);
  const [globalAbilityLogsAutoRefresh, setGlobalAbilityLogsAutoRefresh] = useState(true);
  const [globalAbilityLogsUpdatedAt, setGlobalAbilityLogsUpdatedAt] = useState<string | null>(null);
  const globalAbilityLogsRequestInFlightRef = useRef(false);
  const [abilityLogMetrics, setAbilityLogMetrics] = useState<AbilityLogMetricsResponse | null>(null);
  const [abilityLogMetricsLoading, setAbilityLogMetricsLoading] = useState(false);
  const [abilityLogMetricsError, setAbilityLogMetricsError] = useState<string | null>(null);
  const [abilityHealthSummary, setAbilityHealthSummary] = useState<AbilityHealthSummaryResponse | null>(null);
  const [abilityHealthLoading, setAbilityHealthLoading] = useState(false);
  const [abilityHealthError, setAbilityHealthError] = useState<string | null>(null);
  const [abilityHealthFilter, setAbilityHealthFilter] = useState<AbilityHealthFilter>('needs_test');
  const [abilityHealthExporting, setAbilityHealthExporting] = useState(false);
  const [abilityTemplateState, setAbilityTemplateState] = useState<AbilityTemplateStateResponse | null>(null);
  const [abilityTemplateLoading, setAbilityTemplateLoading] = useState(false);
  const [abilityTemplateError, setAbilityTemplateError] = useState<string | null>(null);
  const [abilityTemplateActionLoading, setAbilityTemplateActionLoading] = useState(false);
  const [abilityTemplateVersionLabel, setAbilityTemplateVersionLabel] = useState('');
  const [abilityTemplateNotes, setAbilityTemplateNotes] = useState('');
  const [abilityTemplateRollbackId, setAbilityTemplateRollbackId] = useState('');
  const [abilityTemplateValidateResult, setAbilityTemplateValidateResult] = useState<AbilityTemplateValidateResponse | null>(null);
  const [abilityMetricsWindowHours, setAbilityMetricsWindowHours] = useState<number>(24);
  const [abilityMetricsProvider, setAbilityMetricsProvider] = useState<string>('all');
  const [abilityMetricsCapabilityKey, setAbilityMetricsCapabilityKey] = useState<string>('all');
  const [exportingAbilityLogs, setExportingAbilityLogs] = useState(false);
  const [publicAbilities, setPublicAbilities] = useState<PublicAbility[]>([]);

  useEffect(() => {
    if (typeof document === 'undefined') return undefined;
    const syncVisibility = () => setPageVisible(document.visibilityState === 'visible');
    syncVisibility();
    document.addEventListener('visibilitychange', syncVisibility);
    window.addEventListener('focus', syncVisibility);
    return () => {
      document.removeEventListener('visibilitychange', syncVisibility);
      window.removeEventListener('focus', syncVisibility);
    };
  }, []);
  const [publicAbilitiesLoading, setPublicAbilitiesLoading] = useState(false);
  const [executorTraffic, setExecutorTraffic] = useState<Record<string, ExecutorTraffic>>({});
  const [executorTrafficLoading, setExecutorTrafficLoading] = useState(false);
  const [executorTrafficError, setExecutorTrafficError] = useState<string | null>(null);
  const [executorsView, setExecutorsView] = useState<'list' | 'channels'>('channels');
  const [executorInlineConcurrency, setExecutorInlineConcurrency] = useState<Record<string, number>>({});
  const [executorInlineSaving, setExecutorInlineSaving] = useState<Record<string, boolean>>({});
  const [executorInlineError, setExecutorInlineError] = useState<Record<string, string>>({});
  const [executorFormError, setExecutorFormError] = useState<string | null>(null);
  const baseModelCacheLoadedRef = useRef(false);
  const baselineLoadedRef = useRef(false);

  const storedPreviewUrl = testResult?.storedUrl || (testResult?.assets && testResult.assets[0]?.ossUrl) || '';
  const fallbackResultUrl =
    storedPreviewUrl || (testResult?.resultUrls && testResult.resultUrls.length > 0 ? testResult.resultUrls[0] : '');
  const testResultPreviewSrc = testResult?.imageBase64
    ? toImagePreview(testResult.imageBase64)
    : testResult?.imageUrl || fallbackResultUrl || '';

  // Derived lists to simplify rendering; declared before effects to avoid TDZ issues.
  const abilityProviders = useMemo(
    () => Array.from(new Set(abilities.map((ability) => ability.provider))).sort(),
    [abilities],
  );
  const globalAbilityLogCapabilityOptions = useMemo(() => {
    if (globalAbilityLogProvider === 'all') return [];
    const seen = new Set<string>();
    return abilities.reduce<{ label: string; value: string }[]>((acc, ability) => {
      if (ability.provider !== globalAbilityLogProvider) return acc;
      const key = ability.capability_key;
      if (!key || seen.has(key)) return acc;
      seen.add(key);
      const label = ability.display_name ? `${ability.display_name}（${ability.capability_key}）` : ability.capability_key;
      acc.push({ label, value: key });
      return acc;
    }, []);
  }, [abilities, globalAbilityLogProvider]);
  const abilityMetricsCapabilityOptions = useMemo(() => {
    if (abilityMetricsProvider === 'all') return [];
    const seen = new Set<string>();
    return abilities.reduce<{ label: string; value: string }[]>((acc, ability) => {
      if (ability.provider !== abilityMetricsProvider) return acc;
      const key = ability.capability_key;
      if (!key || seen.has(key)) return acc;
      seen.add(key);
      const label = ability.display_name ? `${ability.display_name}（${ability.capability_key}）` : ability.capability_key;
      acc.push({ label, value: key });
      return acc;
    }, []);
  }, [abilities, abilityMetricsProvider]);
  const filteredAbilities = useMemo(() => {
    const keyword = abilitySearch.trim().toLowerCase();
    return abilities.filter((ability) => {
      if (abilityProviderFilter !== 'all' && ability.provider !== abilityProviderFilter) return false;
      if (abilityStatusFilter !== 'all' && ability.status !== abilityStatusFilter) return false;
      if (!keyword) return true;
      const haystack = `${ability.display_name} ${ability.capability_key} ${ability.version || ''} ${ability.description || ''}`.toLowerCase();
      return haystack.includes(keyword);
    });
  }, [abilities, abilityProviderFilter, abilityStatusFilter, abilitySearch]);
  const selectedAbility = useMemo(() => {
    if (!selectedAbilityId) return null;
    return abilities.find((ability) => ability.id === selectedAbilityId) ?? null;
  }, [abilities, selectedAbilityId]);
  const abilityTemplateSummaryMap = useMemo(() => {
    const map: Record<string, AbilityTemplateSummary> = {};
    abilities.forEach((ability) => {
      map[ability.id] = resolveAbilityTemplateSummary(ability);
    });
    return map;
  }, [abilities]);
  const selectedAbilityMetadata = (selectedAbility?.metadata || {}) as Record<string, unknown>;
  const abilityExecutors = useMemo(
    () => resolveAbilityExecutors(selectedAbility, executors),
    [selectedAbility, executors],
  );
  const {
    comfyAgentMap,
    comfyAgentOptions,
    comfyExecutors,
    comfyHiddenAgentCount,
    comfyHiddenExecutorCount,
    comfyManifestOptions,
    comfyPublishedManifestCount,
    comfyRepairFailedCount,
    comfyRepairRunningCount,
    comfyRunningTaskCount,
    comfySyncCurrentGuide,
    comfySyncCurrentStep,
    comfySyncSteps,
    visibleComfyAgentAlerts,
    visibleComfyAgentList,
    visibleComfyAgentTasks,
  } = useComfyuiDashboardDerivedState({
    activeTab: comfyuiManageTab,
    agentAlerts: comfyAgentAlerts,
    agentList: comfyAgentList,
    agentTasks: comfyAgentTasks,
    baselineExecutorId: comfyBaselineExecutorId,
    diffLogCount: comfyDiffLogs.length,
    executors,
    manifestList: comfyManifestList,
    repairJobs: comfyRepairJobs,
    showTestNodes: comfyShowTestNodes,
  });
  const comfyDesktopActiveRelease = useMemo(
    () =>
      comfyDesktopReleases.find(
        (item) =>
          item.status === 'active' &&
          normalizeDesktopOsType(item.osType) === 'windows' &&
          normalizeDesktopArch(item.arch) === 'x64',
      ) || null,
    [comfyDesktopReleases],
  );
  const comfyDesktopReleaseOptions = useMemo(() => {
    const windows = comfyDesktopReleases
      .filter((item) => normalizeDesktopOsType(item.osType) === 'windows' && normalizeDesktopArch(item.arch) === 'x64')
      .map((item) => ({
        label: `${item.version} · ${item.channel} · ${item.status === 'active' ? '启用' : '未启用'}`,
        value: String(item.id),
      }));
    if (windows.length > 0) return windows;
    return comfyDesktopReleases.map((item) => ({
      label: `${item.version} · ${item.channel} · ${item.osType || 'unknown'}/${item.arch || 'unknown'}`,
      value: String(item.id),
    }));
  }, [comfyDesktopReleases]);
  const comfyDesktopHasWindowsX64Release = useMemo(
    () =>
      comfyDesktopReleases.some(
        (item) => normalizeDesktopOsType(item.osType) === 'windows' && normalizeDesktopArch(item.arch) === 'x64',
      ),
    [comfyDesktopReleases],
  );
  const comfyDesktopSelectedRelease = useMemo(() => {
    if (comfyDesktopInstallReleaseId) {
      return comfyDesktopReleases.find((item) => String(item.id) === comfyDesktopInstallReleaseId) || null;
    }
    return comfyDesktopActiveRelease;
  }, [comfyDesktopActiveRelease, comfyDesktopInstallReleaseId, comfyDesktopReleases]);
  const comfyDesktopAgentRows = useMemo(
    () =>
      visibleComfyAgentList
        .map((agent) => {
          const update = getComfyDesktopUpdateSnapshot(agent);
          return {
            agent,
            update,
          };
        })
        .sort((a, b) => {
          const left = new Date(a.update.updatedAt || a.agent.last_heartbeat_at || a.agent.last_seen_at || '').getTime();
          const right = new Date(b.update.updatedAt || b.agent.last_heartbeat_at || b.agent.last_seen_at || '').getTime();
          return (Number.isFinite(right) ? right : 0) - (Number.isFinite(left) ? left : 0);
        }),
    [visibleComfyAgentList],
  );
  const comfyDesktopCenterUrl = useMemo(() => {
    if (typeof window === 'undefined') return 'http://117.50.80.158:8099';
    try {
      const current = new URL(window.location.origin);
      current.port = '8099';
      return current.toString().replace(/\/$/, '');
    } catch (error) {
      return 'http://117.50.80.158:8099';
    }
  }, []);
  const comfyDesktopInstallCommand = useMemo(() => {
    const releaseUrl = (comfyDesktopSelectedRelease?.downloadUrl || '').trim();
    const sha256 = (comfyDesktopSelectedRelease?.sha256 || '').trim().toLowerCase();
    if (!releaseUrl) {
      return '请先在下方发布 Windows x64 安装包，并在上方选择目标版本。';
    }
    return [
      '# 1) 下载安装包到本地',
      '$installer = "$env:TEMP\\PODI-ComfyUI-Agent-Setup.exe"',
      `Invoke-WebRequest -Uri "${releaseUrl}" -OutFile $installer`,
      '',
      '# 2) 校验 SHA256（不一致会中断）',
      '$actual = (Get-FileHash $installer -Algorithm SHA256).Hash.ToLower()',
      `$expected = "${sha256}"`,
      'if ($actual -ne $expected) { throw "安装包校验失败，请重新下载" }',
      '',
      '# 3) 管理员静默安装',
      'Start-Process $installer -ArgumentList "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART" -Verb RunAs -Wait',
      '',
      '# 安装后代理服务会自动向中台发起握手：',
      `# ${comfyDesktopCenterUrl}/api/agent/bootstrap/auto-exchange`,
    ].join('\n');
  }, [comfyDesktopCenterUrl, comfyDesktopSelectedRelease?.downloadUrl, comfyDesktopSelectedRelease?.sha256]);
  const comfyAgentEditing = useMemo(
    () => Boolean(comfyAgentForm.id && comfyAgentList.some((agent) => agent.id === comfyAgentForm.id)),
    [comfyAgentForm.id, comfyAgentList],
  );
  const comfyBaselineExecutor = useMemo(() => {
    if (comfyBaselineExecutorId) {
      return comfyExecutors.find((executor) => executor.id === comfyBaselineExecutorId) || null;
    }
    return comfyExecutors[0] || null;
  }, [comfyBaselineExecutorId, comfyExecutors]);
  const comfyLoraExecutor = useMemo(
    () => comfyExecutors.find((executor) => executor.id === comfyLoraExecutorId) || null,
    [comfyExecutors, comfyLoraExecutorId],
  );
  const comfyCachedBaseModels = useMemo(
    () => (comfyLoraExecutorId ? comfyBaseModelCache[comfyLoraExecutorId] || [] : []),
    [comfyBaseModelCache, comfyLoraExecutorId],
  );
  const comfyLoraBaseModels = useMemo(() => {
    if (!comfyLoraExecutorId) return [];
    const models = comfyModelCache[comfyLoraExecutorId] || {};
    const cached = comfyCachedBaseModels;
    const list = Array.isArray(models.unet) ? models.unet : [];
    if (cached.length === 0) return list;
    const merged = new Set(list);
    cached.forEach((item) => merged.add(item));
    return Array.from(merged);
  }, [comfyCachedBaseModels, comfyModelCache, comfyLoraExecutorId]);
  const comfyLoraFormBaseModels = useMemo(
    () => resolveLoraBaseModels(comfyLoraForm),
    [comfyLoraForm.base_models, comfyLoraForm.base_model],
  );
  const comfyServerVersionUsage = useMemo(() => {
    const usage = new Map<string, string[]>();
    comfyExecutors
      .filter((executor) => (executor.type || '').toLowerCase() === 'comfyui')
      .forEach((executor) => {
        const system = comfySystemCache[executor.id];
        const info = extractComfyuiVersionInfo(executor, system);
        const label = executor.name || executor.id;
        const register = (key?: string | null) => {
          if (!key) return;
          const trimmed = String(key).trim();
          if (!trimmed) return;
          const list = usage.get(trimmed) || [];
          if (!list.includes(label)) list.push(label);
          usage.set(trimmed, list);
        };
        register(info.version);
        register(info.commit);
      });
    return usage;
  }, [comfyExecutors, comfySystemCache]);
  const comfyLoraBaseModelOptions = useMemo(() => {
    const merged = new Set(comfyLoraBaseModels);
    comfyLoraFormBaseModels.forEach((model) => merged.add(model));
    return Array.from(merged);
  }, [comfyLoraBaseModels, comfyLoraFormBaseModels]);
  const comfyWorkflowNodes = useMemo(
    () => extractComfyuiNodes(workflowForm.definition),
    [workflowForm.definition],
  );
  const workflowCanMap = comfyWorkflowNodes.length > 0;
  const comfyWorkflowNodeDetails = useMemo(
    () => extractComfyuiNodeDetails(workflowForm.definition),
    [workflowForm.definition],
  );
  const comfyWorkflowNodeMap = useMemo(() => {
    const map = new Map<string, ComfyNode>();
    comfyWorkflowNodes.forEach((node) => map.set(node.id, node));
    return map;
  }, [comfyWorkflowNodes]);
  const workflowInterfaceNodeIds = useMemo(() => {
    const set = new Set<string>();
    workflowInputMap.forEach((item) => {
      if (item.nodeId) set.add(item.nodeId);
    });
    workflowOutputNodeIds.forEach((nodeId) => {
      if (nodeId) set.add(nodeId);
    });
    return set;
  }, [workflowInputMap, workflowOutputNodeIds]);
  const filteredWorkflowNodeDetails = useMemo(() => {
    const keyword = workflowNodeSearch.trim().toLowerCase();
    const base = workflowParamScope === 'internal'
      ? comfyWorkflowNodeDetails.filter((node) => !workflowInterfaceNodeIds.has(node.id))
      : comfyWorkflowNodeDetails;
    if (!keyword) return base;
    return base.filter((node) => {
      const haystack = `${node.id} ${node.title} ${node.classType}`.toLowerCase();
      return haystack.includes(keyword);
    });
  }, [comfyWorkflowNodeDetails, workflowInterfaceNodeIds, workflowNodeSearch, workflowParamScope]);
  const comfyLoraItems = comfyLoraCatalog?.items || [];
  const comfyLoraUntracked = comfyLoraCatalog?.untrackedFiles || [];
  const comfyLoraInstalledFiles = comfyLoraCatalog?.installedFiles || [];
  const comfyLoraInstalledCount =
    comfyLoraInstalledFiles.length > 0
      ? comfyLoraInstalledFiles.length
      : comfyLoraItems.filter((item) => item.installed).length;
  const comfyLoraServerScanned = comfyLoraUntrackedLoaded;
  const abilityFormComfyExecutorId = useMemo(() => {
    if ((abilityForm.provider || '').toLowerCase() !== 'comfyui') return '';
    const pinned = abilityForm.executor_id
      ? comfyExecutors.find((executor) => executor.id === abilityForm.executor_id)
      : null;
    return pinned?.id || comfyExecutors[0]?.id || '';
  }, [abilityForm.provider, abilityForm.executor_id, comfyExecutors]);
  const abilityFormLoraOptions = useMemo(() => {
    if (!abilityFormComfyExecutorId) return [];
    return comfyLoraSelectCache[abilityFormComfyExecutorId] || [];
  }, [abilityFormComfyExecutorId, comfyLoraSelectCache]);
  const abilityFormBaseModelOptions = useMemo(() => {
    if (!abilityFormComfyExecutorId) return [];
    const catalog = comfyModelCache[abilityFormComfyExecutorId];
    const cached = comfyBaseModelCache[abilityFormComfyExecutorId] || [];
    const list = Array.isArray(catalog?.unet) ? catalog.unet : [];
    if (cached.length === 0) return list;
    const merged = new Set(list);
    cached.forEach((item) => merged.add(item));
    return Array.from(merged);
  }, [abilityFormComfyExecutorId, comfyBaseModelCache, comfyModelCache]);
  const abilityFormLoraSelectOptions = useMemo(() => {
    const baseSet = new Set(abilityLoraAllowedBaseModels);
    const filtered = baseSet.size > 0
      ? abilityFormLoraOptions.filter((item) => {
          const baseModels = resolveLoraBaseModels(item);
          return baseModels.some((model) => baseSet.has(model));
        })
      : abilityFormLoraOptions;
    return filtered.map((item) => {
      const display = item.display_name || item.file_name;
      const label = display !== item.file_name ? `${display} (${item.file_name})` : display;
      return { value: item.file_name, label };
    });
  }, [abilityFormLoraOptions, abilityLoraAllowedBaseModels]);
  const abilityVendorModelOptions = useMemo(() => {
    const provider = String(abilityForm.provider || '').trim().toLowerCase();
    return vendorModels
      .filter((item) => !provider || item.provider.toLowerCase() === provider)
      .map((item) => ({
        label: `${item.displayName} · ${item.provider}/${item.model}`,
        value: item.id ?? 0,
        provider: item.provider,
      }))
      .filter((item) => item.value > 0);
  }, [abilityForm.provider, vendorModels]);
  const {
    businessAbilityOptions,
    businessVlAbilityOptions,
    businessRunBusinessOptions,
    businessRunVersionOptions,
    businessCapabilityVersionOptions,
    effectiveBusinessCompareLeftId,
    selectedBusinessCompareLeft,
    businessCompareTargetOptions,
    effectiveBusinessCompareRightId,
    selectedBusinessCompareRight,
  } = useBusinessDashboardDerivedState({
    abilities,
    businessCapabilities,
    businessRunFilters,
    businessCompareLeftId,
    businessCompareRightId,
  });
  const resolveComfyModelList = useCallback(
    (executorId: string, key: string) => {
      if (!executorId) return [];
      const catalog = comfyModelCache[executorId] || {};
      const list = Array.isArray(catalog[key]) ? catalog[key] : [];
      if (key === 'unet') {
        const cached = comfyBaseModelCache[executorId] || [];
        if (cached.length === 0) return list;
        const merged = new Set(list);
        cached.forEach((item) => merged.add(item));
        return Array.from(merged);
      }
      return list;
    },
    [comfyBaseModelCache, comfyModelCache],
  );
  const comfyBaselineSets = useMemo(() => {
    const baselineId = comfyBaselineExecutor?.id || '';
    const buildSet = (list: string[]) => new Set(list.map((item) => item.trim()).filter(Boolean));
    return {
      id: baselineId,
      unet: buildSet(resolveComfyModelList(baselineId, 'unet')),
      clip: buildSet(resolveComfyModelList(baselineId, 'clip')),
      vae: buildSet(resolveComfyModelList(baselineId, 'vae')),
      lora: buildSet(resolveComfyModelList(baselineId, 'lora')),
      nodes: buildSet(comfyNodeCache[baselineId] || []),
    };
  }, [comfyBaselineExecutor, comfyNodeCache, resolveComfyModelList]);
  const comfyWorkflowDepsMap = useMemo(() => {
    const map: Record<string, ComfyWorkflowDependencies> = {};
    workflows.forEach((wf) => {
      if ((wf.type || '').toLowerCase().includes('comfyui')) {
        map[wf.id] = extractComfyuiWorkflowDependencies(wf.definition);
      }
    });
    return map;
  }, [workflows]);
  const comfyModelCatalogMap = useMemo(() => {
    const map: Record<string, Record<string, ComfyuiModelCatalogItem>> = {};
    comfyModelCatalogItems.forEach((item) => {
      const type = (item.model_type || 'other').toLowerCase();
      if (!map[type]) map[type] = {};
      map[type][item.file_name] = item;
    });
    return map;
  }, [comfyModelCatalogItems]);
  const comfyPluginCatalogMap = useMemo(() => {
    const map: Record<string, ComfyuiPluginCatalogItem> = {};
    comfyPluginCatalogItems.forEach((item) => {
      map[item.node_key] = item;
    });
    return map;
  }, [comfyPluginCatalogItems]);
  const comfyManifestWizardPreview = useMemo(() => {
    const pickActive = <T extends { status?: string | null }>(items: T[]) =>
      comfyManifestIncludeInactive ? items : items.filter((item) => (item.status || 'active') === 'active');
    const models = pickActive(comfyModelCatalogItems).map((item) => item.file_name).filter(Boolean);
    const loras = pickActive(comfyLoraItems).map((item) => item.file_name).filter(Boolean);
    const plugins = pickActive(comfyPluginCatalogItems).map((item) => item.node_key).filter(Boolean);
    const workflowKeys = workflows
      .filter((workflow) => {
        const isComfyWorkflow = (workflow.type || '').toLowerCase().includes('comfyui');
        if (!isComfyWorkflow) return false;
        if (comfyManifestIncludeInactive) return true;
        return (workflow.status || 'active') === 'active';
      })
      .map((workflow) => workflow.action || workflow.id)
      .filter(Boolean);
    const activeVersion = pickActive(comfyVersionCatalogItems)[0];
    const content: JsonRecord = {
      source: 'catalog-wizard',
      generatedAt: new Date().toISOString(),
      comfyui: {
        version: activeVersion?.version || '',
        commit: activeVersion?.commit_sha || '',
      },
      models: Array.from(new Set([...models, ...loras])),
      plugins: Array.from(new Set(plugins)),
      workflows: Array.from(new Set(workflowKeys)),
    };
    return content;
  }, [
    comfyManifestIncludeInactive,
    comfyModelCatalogItems,
    comfyLoraItems,
    comfyPluginCatalogItems,
    comfyVersionCatalogItems,
    workflows,
  ]);
  const groupComfyMissingRepos = useCallback(
    (nodes: string[]) => {
      const repoMap: Record<
        string,
        { repo: string; source_url: string | null; download_url: string | null; nodes: string[] }
      > = {};
      const missingRepoNodes: string[] = [];
      nodes.forEach((node) => {
        const record = comfyPluginCatalogMap[node];
        const repo = (record?.source_url || record?.download_url || '').trim();
        if (!repo) {
          missingRepoNodes.push(node);
          return;
        }
        if (!repoMap[repo]) {
          repoMap[repo] = {
            repo,
            source_url: record?.source_url || null,
            download_url: record?.download_url || null,
            nodes: [],
          };
        }
        repoMap[repo].nodes.push(node);
      });
      const repos = Object.values(repoMap).sort((a, b) => a.repo.localeCompare(b.repo));
      missingRepoNodes.sort();
      return { repos, missingRepoNodes };
    },
    [comfyPluginCatalogMap],
  );
  const comfyServersLoadedCount = useMemo(
    () =>
      comfyExecutors.filter((executor) => Boolean(comfyModelCache[executor.id]) && Boolean(comfyNodeCache[executor.id]))
        .length,
    [comfyExecutors, comfyModelCache, comfyNodeCache],
  );
  const resolveWorkflowExecutors = useCallback(
    (workflow: Workflow) => {
      if (!(workflow.type || '').toLowerCase().includes('comfyui')) return [];
      const allowedIds = extractAllowedExecutorIds(workflow.metadata);
      if (allowedIds.length === 0) return comfyExecutors;
      return comfyExecutors.filter((executor) => allowedIds.includes(executor.id));
    },
    [comfyExecutors],
  );
  const buildComfyServerDiff = useCallback(
    (executor: Executor) => {
      const baselineId = comfyBaselineExecutor?.id || '';
      const unetList = resolveComfyModelList(executor.id, 'unet');
      const clipList = resolveComfyModelList(executor.id, 'clip');
      const vaeList = resolveComfyModelList(executor.id, 'vae');
      const loraList = resolveComfyModelList(executor.id, 'lora');
      const nodeKeys = comfyNodeCache[executor.id] || [];
      const missing = {
        unet: diffMissingItems(comfyBaselineSets.unet, unetList),
        clip: diffMissingItems(comfyBaselineSets.clip, clipList),
        vae: diffMissingItems(comfyBaselineSets.vae, vaeList),
        lora: diffMissingItems(comfyBaselineSets.lora, loraList),
        nodes: diffMissingItems(comfyBaselineSets.nodes, nodeKeys),
      };
      const missingRepoGroups = groupComfyMissingRepos(missing.nodes);
      const attachModel = (items: string[], type: string) =>
        items.map((name) => {
          const record = comfyModelCatalogMap[type]?.[name];
          return {
            name,
            display_name: record?.display_name || null,
            source_url: record?.source_url || null,
            download_url: record?.download_url || null,
          };
        });
      const attachPlugin = (items: string[]) =>
        items.map((name) => {
          const record = comfyPluginCatalogMap[name];
          return {
            name,
            display_name: record?.display_name || null,
            source_url: record?.source_url || null,
            download_url: record?.download_url || null,
          };
        });
      return {
        baseline: {
          id: baselineId,
          name: comfyBaselineExecutor?.name || '',
          baseUrl: comfyBaselineExecutor?.base_url || '',
        },
        server: {
          id: executor.id,
          name: executor.name,
          baseUrl: executor.base_url || '',
        },
        missing,
        missing_details: {
          unet: attachModel(missing.unet, 'unet'),
          clip: attachModel(missing.clip, 'clip'),
          vae: attachModel(missing.vae, 'vae'),
          lora: attachModel(missing.lora, 'lora'),
          nodes: attachPlugin(missing.nodes),
        },
        missing_repo_groups: missingRepoGroups,
        totals: {
          unet: unetList.length,
          clip: clipList.length,
          vae: vaeList.length,
          lora: loraList.length,
          nodes: nodeKeys.length,
        },
      };
    },
    [
      comfyBaselineExecutor?.base_url,
      comfyBaselineExecutor?.id,
      comfyBaselineExecutor?.name,
      comfyBaselineSets,
      comfyModelCatalogMap,
      comfyPluginCatalogMap,
      comfyNodeCache,
      resolveComfyModelList,
    ],
  );
  const buildComfyDiffSnapshot = useCallback(() => {
    if (!comfyBaselineExecutor?.id) return null;
    return {
      generatedAt: new Date().toISOString(),
      baseline: {
        id: comfyBaselineExecutor.id,
        name: comfyBaselineExecutor.name,
        baseUrl: comfyBaselineExecutor.base_url || '',
      },
      servers: comfyExecutors.map((executor) => ({
        ...buildComfyServerDiff(executor),
        isBaseline: executor.id === comfyBaselineExecutor.id,
      })),
    };
  }, [buildComfyServerDiff, comfyBaselineExecutor, comfyExecutors]);
  const evaluateWorkflowOnExecutor = useCallback(
    (deps: ComfyWorkflowDependencies, executor: Executor) => {
      const nodeKeys = comfyNodeCache[executor.id] || [];
      const nodesReady = nodeKeys.length > 0;
      const unetList = resolveComfyModelList(executor.id, 'unet');
      const clipList = resolveComfyModelList(executor.id, 'clip');
      const vaeList = resolveComfyModelList(executor.id, 'vae');
      const loraList = resolveComfyModelList(executor.id, 'lora');
      const modelsReady = Boolean(comfyModelCache[executor.id]);
      const missing = {
        nodes: diffMissingItems(new Set(deps.nodes), nodeKeys),
        unet: diffMissingItems(new Set(deps.models.unet), unetList),
        clip: diffMissingItems(new Set(deps.models.clip), clipList),
        vae: diffMissingItems(new Set(deps.models.vae), vaeList),
        lora: diffMissingItems(new Set(deps.models.lora), loraList),
      };
      const hasDeps =
        deps.nodes.length > 0 ||
        deps.models.unet.length > 0 ||
        deps.models.clip.length > 0 ||
        deps.models.vae.length > 0 ||
        deps.models.lora.length > 0;
      const ok =
        !hasDeps ||
        (missing.nodes.length === 0 &&
          missing.unet.length === 0 &&
          missing.clip.length === 0 &&
          missing.vae.length === 0 &&
          missing.lora.length === 0);
      return {
        ready: nodesReady && modelsReady,
        ok,
        missing,
      };
    },
    [comfyModelCache, comfyNodeCache, resolveComfyModelList],
  );
  const workflowDefinitionParse = useMemo(
    () => safeParseJSON(workflowForm.definition),
    [workflowForm.definition],
  );
  const workflowDefinitionInfo = useMemo(
    () => resolveComfyuiDefinition(workflowForm.definition),
    [workflowForm.definition],
  );
  const workflowMetadataParse = useMemo(
    () => safeParseJSON(workflowForm.metadata),
    [workflowForm.metadata],
  );
  const workflowDefinitionError =
    workflowForm.definition && !workflowDefinitionParse.ok ? '工作流 JSON 解析失败，请检查格式。' : '';
  const workflowMetadataError =
    workflowForm.metadata && !workflowMetadataParse.ok ? '高级配置解析失败，请检查格式。' : '';
  const workflowDefinitionNotice = useMemo(() => {
    if (!workflowForm.definition || !workflowDefinitionParse.ok) return '';
    if (workflowDefinitionInfo.source === 'ui') {
      return '检测到 ComfyUI UI JSON，保存时会自动转换为 Prompt Graph。';
    }
    if (workflowDefinitionInfo.source === 'unknown') {
      return 'JSON 已解析，但未识别为 ComfyUI 工作流；节点解析可能为空。';
    }
    return '';
  }, [workflowForm.definition, workflowDefinitionParse.ok, workflowDefinitionInfo.source]);
  const workflowMappingErrors = useMemo(() => {
    const errors: string[] = [];
    if (workflowInputMap.length === 0 && workflowOutputNodeIds.length === 0) {
      return errors;
    }
    if (!comfyWorkflowNodes.length) {
      errors.push('未解析到节点，无法校验输入/输出映射，请先导入有效的工作流 JSON。');
      return errors;
    }
    const used = new Set<string>();
    workflowInputMap.forEach((item, idx) => {
      const prefix = `第 ${idx + 1} 条输入映射`;
      if (!item.field || !item.field.trim()) {
        errors.push(`${prefix}缺少参数名`);
      }
      if (!item.nodeId) {
        errors.push(`${prefix}未选择节点`);
        return;
      }
      const node = comfyWorkflowNodeMap.get(item.nodeId);
      if (!node) {
        errors.push(`${prefix}节点 #${item.nodeId} 不存在`);
        return;
      }
      if (!item.inputKey) {
        errors.push(`${prefix}未选择输入字段`);
      } else if (!node.inputs.includes(item.inputKey)) {
        errors.push(`${prefix}输入 ${item.inputKey} 不在节点 #${item.nodeId} 的输入列表`);
      }
      const signature = `${item.nodeId}::${item.inputKey}`;
      if (item.inputKey) {
        if (used.has(signature)) {
          errors.push(`${prefix}重复映射了节点 #${item.nodeId} 的输入 ${item.inputKey}`);
        } else {
          used.add(signature);
        }
      }
      if (item.valueType && !WORKFLOW_VALUE_TYPES.has(item.valueType)) {
        errors.push(`${prefix}类型 ${item.valueType} 不合法`);
      }
    });
    workflowOutputNodeIds.forEach((nodeId) => {
      if (!comfyWorkflowNodeMap.has(nodeId)) {
        errors.push(`输出节点 #${nodeId} 不在当前工作流中`);
      }
    });
    return errors;
  }, [workflowInputMap, workflowOutputNodeIds, comfyWorkflowNodes, comfyWorkflowNodeMap]);

  const comfyDiffDialogText = useMemo(() => {
    if (!comfyDiffDialogPayload) return '';
    try {
      return JSON.stringify(comfyDiffDialogPayload, null, 2);
    } catch {
      return '';
    }
  }, [comfyDiffDialogPayload]);
  const comfyManifestDriftText = useMemo(() => {
    if (!comfyManifestDriftData) return '';
    try {
      return JSON.stringify(comfyManifestDriftData, null, 2);
    } catch {
      return '';
    }
  }, [comfyManifestDriftData]);
  const workflowSubmitDisabled =
    !workflowForm.action?.trim() ||
    !workflowForm.name?.trim() ||
    !workflowForm.definition?.trim() ||
    Boolean(workflowDefinitionError) ||
    Boolean(workflowMetadataError) ||
    workflowMappingErrors.length > 0;
  const comfyQueueByExecutor = useMemo(() => {
    const next: Record<string, ComfyuiQueueStatus> = {};
    for (const item of comfyQueueSummary?.servers || []) {
      if (item?.executorId) {
        next[item.executorId] = item;
      }
    }
    return next;
  }, [comfyQueueSummary]);

  const executorConfigRecord = useMemo(() => parseJSON(executorForm.config), [executorForm.config]);
  const executorTypeNormalized = String(executorForm.type || '').trim().toLowerCase();
  const executorConfigJsonInvalid = useMemo(() => {
    const raw = (executorForm.config || '').trim();
    if (!raw) return null;
    try {
      JSON.parse(raw);
      return null;
    } catch (e: any) {
      return String(e?.message || e || 'JSON 解析失败');
    }
  }, [executorForm.config]);

  const setExecutorConfigField = useCallback(
    (key: string, value: unknown) => {
      const record = parseJSON(executorForm.config);
      const next: Record<string, unknown> = { ...(record || {}) };
      if (value === null || value === undefined || (typeof value === 'string' && !value.trim())) {
        delete next[key];
      } else {
        next[key] = value;
      }
      setExecutorForm((prev) => ({ ...prev, config: stringifyJSON(next as JsonRecord) }));
    },
    [executorForm.config],
  );

  const executorConfigTemplates = useMemo(() => {
    // Human-friendly templates (non-dev friendly) for common providers.
    const comfyui = [
      { key: 'provider', label: '来源类型', hint: '可选，建议填写 comfyui', placeholder: 'comfyui' },
      { key: 'baseUrl', label: '服务地址', hint: '可选：与上方服务地址保持一致', placeholder: 'http://<ip>:8079' },
      { key: 'channel_key', label: '通道标识', hint: '可选：用于多机或多中转站区分', placeholder: 'comfyui-158' },
      { key: 'tags', label: '路由标签', hint: '可选：多个标签用逗号分隔', placeholder: 'gpu:4090, region:hz' },
      { key: 'comfyui_version', label: 'ComfyUI 版本', hint: '可选：版本号或提交号', placeholder: 'v0.2.x / commit' },
      { key: 'custom_nodes_version', label: '自定义节点版本', hint: '可选：自定义节点包版本', placeholder: 'nodes-2026.02' },
      { key: 'models_hash', label: '模型清单指纹', hint: '可选：用于判断模型是否漂移', placeholder: 'sha1:...' },
      { key: 'lora_hash', label: 'LoRA 清单指纹', hint: '可选：用于判断 LoRA 是否漂移', placeholder: 'sha1:...' },
      { key: 'sync_role', label: '同步角色', hint: '可选：母服务器或子服务器标记', placeholder: 'master / worker' },
      { key: 'last_sync_at', label: '最近同步时间', hint: '可选：最近同步时间', placeholder: '2026-02-02 12:00' },
    ];
    const kie = [
      { key: 'apiKey', label: '接口密钥', hint: '必填：KIE 调用密钥', placeholder: 'sk-***' },
      { key: 'baseUrl', label: '服务地址', hint: '默认 https://api.kie.ai', placeholder: 'https://api.kie.ai' },
      { key: 'channel_key', label: '通道标识', hint: '可选：多中转站区分', placeholder: 'kie-default' },
    ];
    const volcengine = [
      { key: 'apiKey', label: '接口密钥', hint: '必填：火山调用密钥', placeholder: '***' },
      { key: 'baseUrl', label: '服务地址', hint: '默认 https://ark.cn-beijing.volces.com', placeholder: 'https://ark.cn-beijing.volces.com' },
    ];
    const baidu = [
      { key: 'apiKey', label: '接口密钥', hint: '必填：百度调用密钥', placeholder: '***' },
      { key: 'secretKey', label: '密钥二段', hint: '必填：百度配套密钥', placeholder: '***' },
      { key: 'accessKey', label: '访问密钥', hint: '可选：如接入点需要', placeholder: '***' },
    ];
    if (executorTypeNormalized.includes('kie')) return kie;
    if (executorTypeNormalized.includes('volc') || executorTypeNormalized.includes('ark')) return volcengine;
    if (executorTypeNormalized.includes('baidu')) return baidu;
    if (executorTypeNormalized.includes('comfyui')) return comfyui;
    return [
      { key: 'channel_key', label: '通道标识', hint: '可选：用于区分多渠道或多节点', placeholder: 'default' },
    ];
  }, [executorTypeNormalized]);

  // Keep inline concurrency inputs in sync with list results.
  useEffect(() => {
    setExecutorInlineConcurrency((prev) => {
      const next = { ...prev };
      for (const ex of executors) {
        if (typeof next[ex.id] !== 'number') next[ex.id] = ex.max_concurrency ?? 1;
      }
      return next;
    });
  }, [executors]);
  const workflowLookup = useMemo(() => {
    const map: Record<string, Workflow> = {};
    workflows.forEach((workflow) => {
      map[workflow.id] = workflow;
    });
    return map;
  }, [workflows]);
  const selectedAbilityWorkflow = useMemo(() => {
    if (!selectedAbility?.workflow_id) return null;
    return workflowLookup[selectedAbility.workflow_id] || null;
  }, [selectedAbility?.workflow_id, workflowLookup]);
  const selectedAbilityWorkflowLabel = useMemo(() => {
    if (!selectedAbility) return '未绑定';
    if (selectedAbilityWorkflow) {
      return `${selectedAbilityWorkflow.name}${
        selectedAbilityWorkflow.version ? ` · ${selectedAbilityWorkflow.version}` : ''
      }`;
    }
    return selectedAbility.workflow_id || '未绑定';
  }, [selectedAbility, selectedAbilityWorkflow]);
  const selectedAbilityHealth = useMemo(() => {
    if (!selectedAbility) {
      return {
        status: 'unknown',
        checkedAt: '从未巡检',
        successRateText: '暂未统计',
      };
    }
    const status = selectedAbility.last_health_status || 'unknown';
    const checkedAt = selectedAbility.last_health_check_at
      ? formatDateTime(selectedAbility.last_health_check_at)
      : '从未巡检';
    const successRateText =
      typeof selectedAbility.success_rate === 'number'
        ? `${Math.round(selectedAbility.success_rate * 1000) / 10}%`
        : '暂未统计';
    return { status, checkedAt, successRateText };
  }, [
    selectedAbility,
    selectedAbility?.last_health_check_at,
    selectedAbility?.last_health_status,
    selectedAbility?.success_rate,
  ]);
  const filteredAbilityHealthItems = useMemo(() => {
    const items = abilityHealthSummary?.items || [];
    if (abilityHealthFilter === 'all') return items;
    if (abilityHealthFilter === 'needs_test') return items.filter((item) => item.needsTest);
    if (abilityHealthFilter === 'stale') return items.filter((item) => item.stale);
    return items.filter((item) => item.healthStatus === abilityHealthFilter);
  }, [abilityHealthFilter, abilityHealthSummary?.items]);
  const abilityPricingMap = useMemo(() => {
    const map: Record<string, AbilityPricing> = {};
    abilities.forEach((ability) => {
      const pricing = parsePricingFromMetadata(ability.metadata as JsonRecord | null, ability.provider);
      if (!pricing) return;
      map[ability.id] = pricing;
      map[`${ability.provider}:${ability.capability_key}`] = pricing;
    });
    return map;
  }, [abilities]);
  const latestAbilityLogMap = useMemo(() => {
    const map: Record<string, AbilityInvocationLog> = {};
    globalAbilityLogs.forEach((log) => {
      if (!log.ability_id) return;
      const existing = map[log.ability_id];
      if (!existing) {
        map[log.ability_id] = log;
        return;
      }
      if (new Date(log.created_at).getTime() > new Date(existing.created_at).getTime()) {
        map[log.ability_id] = log;
      }
    });
    return map;
  }, [globalAbilityLogs]);
  const globalAbilityLogProviders = useMemo(
    () =>
      Array.from(
        new Set([
          ...abilities.map((ability) => ability.provider).filter(Boolean),
          ...globalAbilityLogs.map((log) => log.ability_provider).filter(Boolean),
        ]),
      ).sort(),
    [abilities, globalAbilityLogs],
  );
  const globalAbilityLogSources = useMemo(
    () =>
      Array.from(
        new Set([
          'admin-test',
          'workflow',
          'task',
          'ability-api',
          'ability-task',
          'ability_api',
          'ability_task',
          'business-api',
          ...globalAbilityLogs.map((log) => log.source).filter(Boolean),
        ]),
      ).sort(),
    [globalAbilityLogs],
  );
  const globalAbilityLogStatuses = useMemo(
    () =>
      Array.from(
        new Set([
          'pending',
          'success',
          'failed',
          ...globalAbilityLogs.map((log) => log.status).filter(Boolean) as string[],
        ]),
      ).sort(),
    [globalAbilityLogs],
  );
  const filteredGlobalAbilityLogs = globalAbilityLogs;
  const abilityLogDetailDurationMs = useMemo(
    () => (abilityLogDetail ? resolveLogDurationMs(abilityLogDetail) : null),
    [abilityLogDetail],
  );
  const abilitySchemaFields = useMemo(
    () => parseAbilitySchemaFields(selectedAbility?.input_schema),
    [selectedAbility],
  );
  const abilitySchemaHasLora = useMemo(
    () => abilitySchemaFields.some((field) => field.name === 'lora' || field.name === 'lora_name'),
    [abilitySchemaFields],
  );
  const selectedAbilitySchemaIssues = useMemo(
    () => getAbilitySchemaIssues(selectedAbility),
    [selectedAbility],
  );
  const activeComfyExecutorId = useMemo(() => {
    if (selectedAbility?.provider !== 'comfyui') return null;
    if (testForm.executorId && abilityExecutors.some((executor) => executor.id === testForm.executorId)) {
      return testForm.executorId;
    }
    return abilityExecutors[0]?.id || null;
  }, [selectedAbility?.provider, testForm.executorId, abilityExecutors]);
  const comfyModelOptionsByField = useMemo(() => {
    if (selectedAbility?.provider !== 'comfyui' || !activeComfyExecutorId) return {};
    const catalog = comfyModelCache[activeComfyExecutorId];
    if (!catalog) return {};
    const toOptions = (list?: string[]) =>
      Array.isArray(list) && list.length > 0 ? list.map((value) => ({ value, label: value })) : undefined;
    return {
      unet_name: toOptions(catalog.unet),
      clip_name: toOptions(catalog.clip),
      vae_name: toOptions(catalog.vae),
      lora_name: toOptions(catalog.lora),
    } as Record<string, AbilitySchemaFieldOption[] | undefined>;
  }, [selectedAbility?.provider, activeComfyExecutorId, comfyModelCache]);
  const comfyLoraOptionsByField = useMemo(() => {
    if (selectedAbility?.provider !== 'comfyui' || !activeComfyExecutorId) return {};
    const items = comfyLoraSelectCache[activeComfyExecutorId];
    if (!items || items.length === 0) return {};
    const loraMeta = parseLoraMetadata(selectedAbility.metadata as JsonRecord | null);
    const allowedFiles = new Set(loraMeta.allowedFiles);
    const allowedTags = new Set(loraMeta.allowedTags);
    const allowedBaseModels = new Set(loraMeta.allowedBaseModels);
    const filteredItems = items.filter((item) => {
      if (allowedFiles.size > 0 && !allowedFiles.has(item.file_name)) return false;
      if (allowedTags.size > 0) {
        const tags = (item.tags || []).map((tag) => tag.trim());
        if (!tags.some((tag) => allowedTags.has(tag))) return false;
      }
      if (allowedBaseModels.size > 0) {
        const baseModels = resolveLoraBaseModels(item);
        if (!baseModels.some((model) => allowedBaseModels.has(model))) return false;
      }
      return true;
    });
    const options = filteredItems.map((item) => {
      const display = item.display_name || item.file_name;
      const label = display !== item.file_name ? `${display} (${item.file_name})` : display;
      return { value: item.file_name, label };
    });
    return {
      lora: options,
      lora_name: options,
    } as Record<string, AbilitySchemaFieldOption[] | undefined>;
  }, [selectedAbility?.provider, selectedAbility?.metadata, activeComfyExecutorId, comfyLoraSelectCache]);
  const renderedSchemaFields = useMemo(() => {
    if (!abilitySchemaFields.length) return abilitySchemaFields;
    return abilitySchemaFields.map((field) => {
      const dynamicOptions = comfyLoraOptionsByField[field.name] || comfyModelOptionsByField[field.name];
      if (dynamicOptions && dynamicOptions.length > 0) {
        const preferSelect = field.type === 'select' || field.component === 'select';
        return {
          ...field,
          type: preferSelect ? 'select' : field.type,
          options: dynamicOptions,
        };
      }
      return field;
    });
  }, [abilitySchemaFields, comfyModelOptionsByField, comfyLoraOptionsByField]);
  const selectedAbilityTags = useMemo(
    () => (selectedAbility ? extractAbilityTags(selectedAbility) : []),
    [selectedAbility],
  );
  const describePricing = useCallback((pricing: AbilityPricing | null) => {
    if (!pricing) return '—';
    const unitLabel = formatUnitLabel(pricing.unit);
    const discount = pricing.discountPrice ?? pricing.listPrice;
    const list = pricing.listPrice;
    const discountText =
      typeof discount === 'number' ? `${formatPriceValue(discount, pricing.currency)} / ${unitLabel}` : null;
    const listText =
      typeof list === 'number' && (discount === undefined || list !== discount)
        ? `${formatPriceValue(list, pricing.currency)} / ${unitLabel}`
        : null;
    if (discountText && listText) {
      return `折扣 ${discountText} · 对外 ${listText}`;
    }
    if (discountText) return discountText;
    if (listText) return listText;
    return '—';
  }, []);
  const selectedAbilityPricing = useMemo(() => {
    if (!selectedAbility) return null;
    return (
      abilityPricingMap[selectedAbility.id] ||
      abilityPricingMap[`${selectedAbility.provider}:${selectedAbility.capability_key}`] ||
      parsePricingFromMetadata(selectedAbility.metadata as JsonRecord | null, selectedAbility.provider)
    );
  }, [selectedAbility, abilityPricingMap]);
  const selectedAbilityPricingText = useMemo(
    () => describePricing(selectedAbilityPricing),
    [selectedAbilityPricing, describePricing],
  );
  const cozeAbilities = useMemo(
    () => abilities.filter((ability) => ability.provider === 'coze'),
    [abilities],
  );
  const cozeAbilityStats = useMemo(() => {
    const mapped = cozeAbilities.filter((ability) => extractCozeWorkflowId(ability)).length;
    return { total: cozeAbilities.length, mapped };
  }, [cozeAbilities]);
  const cozeAbilityMappings = useMemo(
    () =>
      cozeAbilities.map((ability) => ({
        ability,
        workflowId: extractCozeWorkflowId(ability),
        latestLog: latestAbilityLogMap[ability.id],
      })),
    [cozeAbilities, latestAbilityLogMap],
  );
  const cozeRecentLogs = useMemo(
    () => globalAbilityLogs.filter((log) => log.ability_provider === 'coze').slice(0, 6),
    [globalAbilityLogs],
  );
  const cozeConfig = systemConfig?.coze;
  const cozeBaseUrl = useMemo(() => {
    const raw = cozeConfig?.base_url?.trim();
    if (!raw) return '';
    return raw.endsWith('/') ? raw.slice(0, -1) : raw;
  }, [cozeConfig?.base_url]);
  const cozeLoopUrl = useMemo(() => {
    const raw = cozeConfig?.loop_base_url?.trim();
    if (!raw) return '';
    return raw.endsWith('/') ? raw.slice(0, -1) : raw;
  }, [cozeConfig?.loop_base_url]);
  const cozeTokenHint = cozeConfig?.token_present ? (cozeConfig?.token_hint || '已配置') : '未配置';
  const resolveLogPricing = useCallback(
    (log: AbilityInvocationLog): AbilityPricing | null => {
      const logDiscount = coerceNumber(log.cost_amount);
      const logList = coerceNumber(log.unit_price);
      if (logDiscount !== undefined || logList !== undefined) {
        return {
          currency: log.currency || (log.ability_provider === 'comfyui' ? defaultComfyPricing.currency : undefined),
          unit: log.billing_unit || (log.ability_provider === 'comfyui' ? defaultComfyPricing.unit : undefined),
          discountPrice: logDiscount ?? logList,
          listPrice: logList,
        };
      }
      if (log.ability_id && abilityPricingMap[log.ability_id]) {
        return abilityPricingMap[log.ability_id];
      }
      const key = `${log.ability_provider}:${log.capability_key}`;
      if (abilityPricingMap[key]) {
        return abilityPricingMap[key];
      }
      if (log.ability_provider === 'comfyui') {
        return defaultComfyPricing;
      }
      return null;
    },
    [abilityPricingMap],
  );

  useEffect(() => {
    if (!selectedAbility) return;
    if (testForm.executorId && abilityExecutors.some((executor) => executor.id === testForm.executorId)) {
      return;
    }
    const fallbackExecutorId = abilityExecutors[0]?.id || null;
    if (fallbackExecutorId !== testForm.executorId) {
      setTestForm((prev) => ({
        ...prev,
        executorId: fallbackExecutorId,
      }));
    }
  }, [selectedAbility?.id, abilityExecutors, testForm.executorId]);

  const summary = useMemo(
    () => ({
      executors: executors.length,
      workflows: workflows.length,
      bindings: bindings.length,
      apiKeys: apiKeys.length,
      abilities: abilities.length,
      activeExecutors: executors.filter((i) => i.status === 'active').length,
    }),
    [executors, workflows, bindings, apiKeys, abilities],
  );
  const executorTrafficTotals = useMemo(() => {
    const items = Object.values(executorTraffic);
    const totalCalls = items.reduce((sum, item) => sum + Number(item.count || 0), 0);
    const failedCalls = items.reduce((sum, item) => sum + Number(item.failed || 0), 0);
    const successCalls = items.reduce((sum, item) => sum + Number(item.success || 0), 0);
    return {
      totalCalls,
      failedCalls,
      successRate: totalCalls > 0 ? Math.round((successCalls / totalCalls) * 100) : null,
    };
  }, [executorTraffic]);
  const statusCountMap = useMemo(() => {
    const map: Record<string, number> = {};
    for (const bucket of dashboardMetrics?.status_buckets || []) {
      map[bucket.status] = bucket.count;
    }
    return map;
  }, [dashboardMetrics]);
  const runningQueueCount = statusCountMap.running ?? 0;
  const queueOverview = dashboardMetrics?.queue_overview;
  const pendingQueueTotal = queueOverview?.total_pending ?? dashboardMetrics?.totals.queue_depth ?? 0;
  const runningQueueTotal = queueOverview?.total_running ?? runningQueueCount;
  const pendingQueueSub = queueOverview
    ? `任务 ${queueOverview.task_pending} · 能力 ${queueOverview.ability_pending} · 评测 ${queueOverview.eval_pending}`
    : '待创建 / 排队中';
  const runningQueueSub = queueOverview
    ? `任务 ${queueOverview.task_running} · 能力 ${queueOverview.ability_running} · 评测 ${queueOverview.eval_running}`
    : '执行中';
  const pendingBatchValue = queueOverview?.pending_batches ?? dashboardMetrics?.totals.pending_batches ?? 0;
  const pendingBatchSub = queueOverview ? `剩余 ${queueOverview.pending_batch_tasks} 条任务` : '未完成批次';
  const queueOverviewRows = useMemo(
    () => [
      {
        key: 'tasks',
        label: '任务调度',
        pending: queueOverview?.task_pending ?? 0,
        running: queueOverview?.task_running ?? 0,
      },
      {
        key: 'abilities',
        label: '统一能力',
        pending: queueOverview?.ability_pending ?? 0,
        running: queueOverview?.ability_running ?? 0,
      },
      {
        key: 'evals',
        label: '能力评测',
        pending: queueOverview?.eval_pending ?? 0,
        running: queueOverview?.eval_running ?? 0,
      },
      {
        key: 'batches',
        label: '批次任务',
        pending: queueOverview?.pending_batches ?? 0,
        running: queueOverview?.pending_batch_tasks ?? 0,
        note: '待处理批次 / 剩余任务数',
      },
    ],
    [queueOverview],
  );

  const vendorUsageTotal = useMemo(
    () => vendorUsageItems.reduce((sum, item) => sum + Number(item.count || 0), 0),
    [vendorUsageItems],
  );
  const vendorUsageFailed = useMemo(
    () =>
      vendorUsageItems
        .filter((item) => item.status === 'failed' || item.errorCode)
        .reduce((sum, item) => sum + Number(item.count || 0), 0),
    [vendorUsageItems],
  );
  const vendorUsageSuccessRate = vendorUsageTotal > 0
    ? Math.round(((vendorUsageTotal - vendorUsageFailed) / vendorUsageTotal) * 100)
    : null;
  const vendorGovernanceIssueCount = useMemo(
    () =>
      (vendorGovernanceSummary?.issues?.length || 0) +
      (vendorGovernanceSummary?.providers || []).reduce((sum, item) => sum + (item.issues?.length || 0), 0),
    [vendorGovernanceSummary],
  );
  const healthWatchIssueCount = useMemo(
    () =>
      healthWatchStatus?.supported === false
        ? 0
        : (healthWatchStatus?.items || []).filter((item) =>
            ['failed', 'disabled', 'unavailable'].includes(item.status),
          ).length,
    [healthWatchStatus],
  );
  const healthWatchHeaderText = healthWatchStatus
    ? healthWatchStatus.supported === false
      ? '巡检守护本地不可读'
      : healthWatchIssueCount > 0
        ? `巡检守护异常 ${healthWatchIssueCount}`
        : '巡检守护正常'
    : '巡检守护待检查';

  const {
    handleAuthInviteDisable,
    handleAuthInviteSubmit,
    handleAuthSessionRevoke,
    handleAuthUserEditSelect,
    handleAuthUserSubmit,
    refreshAuthPanel,
  } = useAuthActions({
    authInviteForm,
    authUserForm,
    extractErrorMessage: (error) => extractErrorMessage(error),
    setAuthError,
    setAuthInviteForm,
    setAuthLoading,
    setAuthScopeSummary,
    setAuthSessions,
    setAuthUserForm,
    setAuthUsers,
    setInviteCodes,
  });

  const {
    createBillingInvoiceRequest,
    createPackagePurchaseOrder,
    exportBillingCommercialReport,
    exportBillingUserLedger,
    grantBillingPackage,
    issueBillingMonthlySettlement,
    markBillingInvoiceRequestIssued,
    markBillingMonthlySettlementPaid,
    markPackagePurchaseOrderPaid,
    refreshBillingOverview,
    refreshBillingUserDetail,
    refundBillingIssue,
    retryBillingIssue,
    runBillingMonthlyCollectionNotification,
    runBillingPackageAlertNotification,
    saveBillingNotificationConfig,
    savePackageCatalog,
  } = useBillingActions({
    billingBusinessKey,
    billingClientId,
    billingDetail,
    billingMonth,
    billingSelectedUserId,
    billingTenantId,
    billingWindowDays,
    downloadBlob: (blob, filename) => downloadBlob(blob, filename),
    extractErrorMessage: (error) => extractErrorMessage(error),
    setBillingDetail,
    setBillingCommercialReport,
    setBillingError,
    setBillingExporting,
    setBillingInvoiceRequests,
    setBillingLoading,
    setBillingMonthlyCollectionNotifications,
    setBillingMonthlySettlement,
    setBillingMonthlySettlementRecords,
    setBillingNotificationConfig,
    setBillingOverview,
    setBillingPackageAlertNotifications,
    setBillingPackageCatalog,
    setBillingPackagePurchaseOrders,
    setBillingSelectedUserId,
  });

  const load = async () => {
    setLoading(true);
    setLoadErrors([]);
    try {
      if (isBusinessReadOnly) {
        const settled = await Promise.allSettled([
          adminApi.listBusinessCapabilities(),
          adminApi.listBusinessRuns(businessRunFilters),
          adminApi.getBusinessUsageSummary(businessRunFilters),
          adminApi.getBusinessOutputReviewSummary({ windowHours: 168 }),
        ]);
        const errors: string[] = [];
        if (settled[0].status === 'fulfilled') {
          setBusinessCapabilities(settled[0].value.items || []);
        } else {
          errors.push(`业务能力：${settled[0].reason?.message || '请求失败'}`);
        }
        if (settled[1].status === 'fulfilled') {
          setBusinessRuns(settled[1].value.items || []);
          setBusinessRunTotal(Number(settled[1].value.total || 0));
        } else {
          errors.push(`业务运行记录：${settled[1].reason?.message || '请求失败'}`);
        }
        if (settled[2].status === 'fulfilled') {
          setBusinessUsageSummary(settled[2].value);
        } else {
          errors.push(`业务统计：${settled[2].reason?.message || '请求失败'}`);
        }
        if (settled[3].status === 'fulfilled') {
          setBusinessOutputReviewSummary(settled[3].value);
        } else {
          errors.push(`质量复盘：${settled[3].reason?.message || '请求失败'}`);
        }
        setBusinessOperationLogs([]);
        setBusinessDefaultApprovals([]);
        setLoadErrors(errors);
        return;
      }
      const businessCapabilityPromise = adminApi.listBusinessCapabilities();
      const businessRunPromise = adminApi.listBusinessRuns(businessRunFilters);
      const businessUsagePromise = adminApi.getBusinessUsageSummary(businessRunFilters).catch((error) => ({ __error: error }));
      const businessOutputReviewSummaryPromise = adminApi
        .getBusinessOutputReviewSummary({ windowHours: 168 })
        .catch((error) => ({ __error: error }));
      const businessOperationLogPromise = isBusinessReadOnly
        ? Promise.resolve({ items: [] })
        : adminApi
            .listBusinessOperationLogs({ businessKey: businessRunFilters.businessKey, limit: 20 })
            .catch((error) => ({ __error: error }));
      const businessDefaultApprovalPromise = isBusinessReadOnly
        ? Promise.resolve({ items: [] })
        : adminApi
            .listBusinessDefaultApprovals({ businessKey: businessRunFilters.businessKey, status: 'pending', limit: 20 })
            .catch((error) => ({ __error: error }));

      void businessCapabilityPromise.then((res) => setBusinessCapabilities(res.items || [])).catch(() => {});
      void businessRunPromise
        .then((res) => {
          setBusinessRuns(res.items || []);
          setBusinessRunTotal(Number(res.total || 0));
        })
        .catch(() => {});
      void businessUsagePromise.then((res: any) => {
        if (res && !res.__error) setBusinessUsageSummary(res as BusinessUsageSummaryResponse);
      });
      void businessOutputReviewSummaryPromise.then((res: any) => {
        if (res && !res.__error) setBusinessOutputReviewSummary(res as BusinessOutputReviewSummaryResponse);
      });

      const settled = await Promise.allSettled([
        adminApi.listExecutors(),
        adminApi.listWorkflows(),
        adminApi.listBindings(),
        adminApi.listApiKeys(),
        adminApi.getDashboardMetrics(),
        adminApi.getDispatchLogs(),
        adminApi.getSystemConfig(),
        businessCapabilityPromise,
        businessRunPromise,
        businessUsagePromise,
        businessOperationLogPromise,
        businessDefaultApprovalPromise,
        adminApi.listAbilities(),
        adminApi.getAbilityHealthSummary({ staleHours: 24, limit: 100 }).catch((error) => ({ __error: error })),
        adminApi.getAbilityLogMetrics({ windowHours: 24 }).catch(() => null),
        adminApi.listVendorProviders().catch((error) => ({ __error: error })),
        adminApi.listVendorKeys().catch((error) => ({ __error: error })),
        adminApi.listVendorModels().catch((error) => ({ __error: error })),
        adminApi.getVendorUsageSummary(24).catch((error) => ({ __error: error })),
        adminApi.getVendorGovernanceSummary(24).catch((error) => ({ __error: error })),
        adminApi.listReleasePreflightSnapshots(5).catch((error) => ({ __error: error })),
        adminApi.listStrategySnapshots(8).catch((error) => ({ __error: error })),
        adminApi.listReleasePatrolRecords(5).catch((error) => ({ __error: error })),
        adminApi.listWeeklyReports(5).catch((error) => ({ __error: error })),
        adminApi.listReleaseDecisionRecords(5).catch((error) => ({ __error: error })),
        adminApi.getHealthWatchStatus().catch((error) => ({ __error: error })),
      ]);

      const errors: string[] = [];
      const unwrap = <T,>(idx: number, label: string): T | null => {
        const res = settled[idx];
        if (res.status === 'fulfilled') return res.value as T;
        const msg = (res.reason as any)?.message || String(res.reason || '');
        errors.push(`${label}：${msg || '请求失败'}`);
        return null;
      };

      const execRes = unwrap<Executor[]>(0, '运行线路');
      const wfRes = unwrap<Workflow[]>(1, '工作流');
      const bindingRes = unwrap<Binding[]>(2, '路由策略');
      const apiKeyRes = unwrap<ApiKey[]>(3, '历史密钥');
      const metricsRes = unwrap<DashboardMetrics>(4, '监控指标');
      const logsRes = unwrap<{ entries: DispatchLogEntry[] }>(5, '调度事件');
      const configRes = unwrap<SystemConfig>(6, '系统配置');
      const businessCapabilityRes = unwrap<{ items: BusinessCapability[] }>(7, '业务能力');
      const businessRunRes = unwrap<{ total: number; items: BusinessRun[] }>(8, '业务运行记录');
      const businessUsageRes = settled[9].status === 'fulfilled' ? (settled[9].value as any) : null;
      const businessOperationLogRes = settled[10].status === 'fulfilled' ? (settled[10].value as any) : null;
      const businessDefaultApprovalRes = settled[11].status === 'fulfilled' ? (settled[11].value as any) : null;
      const abilityRes = unwrap<Ability[]>(12, '能力目录');
      const abilityHealthRes = settled[13].status === 'fulfilled' ? (settled[13].value as any) : null;
      const abilityLogMetricsRes = settled[14].status === 'fulfilled' ? (settled[14].value as any) : null;
      const vendorProviderRes = settled[15].status === 'fulfilled' ? (settled[15].value as any) : null;
      const vendorKeyRes = settled[16].status === 'fulfilled' ? (settled[16].value as any) : null;
      const vendorModelRes = settled[17].status === 'fulfilled' ? (settled[17].value as any) : null;
      const vendorUsageRes = settled[18].status === 'fulfilled' ? (settled[18].value as any) : null;
      const vendorGovernanceRes = settled[19].status === 'fulfilled' ? (settled[19].value as any) : null;
      const releasePreflightRes = settled[20].status === 'fulfilled' ? (settled[20].value as any) : null;
      const strategySnapshotRes = settled[21].status === 'fulfilled' ? (settled[21].value as any) : null;
      const releasePatrolRes = settled[22].status === 'fulfilled' ? (settled[22].value as any) : null;
      const weeklyReportRes = settled[23].status === 'fulfilled' ? (settled[23].value as any) : null;
      const releaseDecisionRes = settled[24].status === 'fulfilled' ? (settled[24].value as any) : null;
      const healthWatchRes = settled[25].status === 'fulfilled' ? (settled[25].value as any) : null;

      if (execRes) setExecutors(execRes);
      if (wfRes) setWorkflows(wfRes);
      if (bindingRes) setBindings(bindingRes);
      if (apiKeyRes) setApiKeys(apiKeyRes);
      if (metricsRes) setDashboardMetrics(metricsRes);
      if (logsRes) setDispatchLogs(logsRes.entries);
      if (configRes) setSystemConfig(configRes);
      if (businessCapabilityRes) setBusinessCapabilities(businessCapabilityRes.items || []);
      if (businessRunRes) {
        setBusinessRuns(businessRunRes.items || []);
        setBusinessRunTotal(Number(businessRunRes.total || 0));
      }
      if (businessUsageRes && !businessUsageRes.__error) {
        setBusinessUsageSummary(businessUsageRes as BusinessUsageSummaryResponse);
      }
      if (businessOperationLogRes && !businessOperationLogRes.__error) {
        setBusinessOperationLogs(businessOperationLogRes.items || []);
      }
      if (businessDefaultApprovalRes && !businessDefaultApprovalRes.__error) {
        setBusinessDefaultApprovals(businessDefaultApprovalRes.items || []);
      }
      if (abilityRes) {
        const normalized = abilityRes.map((ability) => {
          const extra = (ability as Ability & { extra_metadata?: JsonRecord | null }).extra_metadata;
          return {
            ...ability,
            metadata: ability.metadata ?? extra ?? null,
          };
        });
        setAbilities(normalized);
      }
      if (abilityLogMetricsRes) setAbilityLogMetrics(abilityLogMetricsRes);
      if (abilityHealthRes && !abilityHealthRes.__error) {
        setAbilityHealthSummary(abilityHealthRes);
        setAbilityHealthError(null);
      } else if (abilityHealthRes?.__error) {
        setAbilityHealthError(abilityHealthRes.__error?.message || '能力健康统计加载失败');
      }
      const vendorErrors = [vendorProviderRes, vendorKeyRes, vendorModelRes, vendorUsageRes, vendorGovernanceRes]
        .map((item) => item?.__error?.message)
        .filter(Boolean);
      if (vendorErrors.length > 0) setVendorError(vendorErrors.join('；'));
      if (vendorProviderRes && !vendorProviderRes.__error) {
        setVendorProviders(vendorProviderRes.providers || []);
        setVendorBaseUrl(vendorProviderRes.baseUrl || vendorProviderRes.base_url || '');
      }
      if (vendorKeyRes && !vendorKeyRes.__error) {
        setVendorKeys(vendorKeyRes.items || []);
        setVendorBaseUrl((prev) => prev || vendorKeyRes.baseUrl || vendorKeyRes.base_url || '');
      }
      if (vendorModelRes && !vendorModelRes.__error) {
        setVendorModels(vendorModelRes.items || []);
        setVendorBaseUrl((prev) => prev || vendorModelRes.baseUrl || vendorModelRes.base_url || '');
      }
      if (vendorUsageRes && !vendorUsageRes.__error) {
        setVendorUsageItems(vendorUsageRes.items || []);
        setVendorUsageWindowHours(Number(vendorUsageRes.windowHours || 24));
        setVendorBaseUrl((prev) => prev || vendorUsageRes.baseUrl || vendorUsageRes.base_url || '');
      }
      if (vendorGovernanceRes && !vendorGovernanceRes.__error) {
        setVendorGovernanceSummary(vendorGovernanceRes);
        setVendorBaseUrl((prev) => prev || vendorGovernanceRes.baseUrl || vendorGovernanceRes.base_url || '');
      }
      if (releasePreflightRes && !releasePreflightRes.__error) {
        const items = releasePreflightRes.items || [];
        setReleasePreflightSnapshots(items);
        setReleasePreflightLatest(items[0] || null);
        setReleasePreflightError(null);
      } else if (releasePreflightRes?.__error) {
        setReleasePreflightError(releasePreflightRes.__error?.message || '发布前门禁记录加载失败');
      }
      if (strategySnapshotRes && !strategySnapshotRes.__error) {
        setStrategySnapshots(strategySnapshotRes.items || []);
        setStrategySnapshotError(null);
      } else if (strategySnapshotRes?.__error) {
        setStrategySnapshotError(strategySnapshotRes.__error?.message || '战略指标快照加载失败');
      }
      if (releasePatrolRes && !releasePatrolRes.__error) {
        setReleasePatrolRecords(releasePatrolRes.items || []);
        setReleasePatrolError(null);
      } else if (releasePatrolRes?.__error) {
        setReleasePatrolError(releasePatrolRes.__error?.message || '完整巡检记录加载失败');
      }
      if (weeklyReportRes && !weeklyReportRes.__error) {
        setWeeklyReports(weeklyReportRes.items || []);
        setWeeklyReportError(null);
      } else if (weeklyReportRes?.__error) {
        setWeeklyReportError(weeklyReportRes.__error?.message || '周报记录加载失败');
      }
      if (releaseDecisionRes && !releaseDecisionRes.__error) {
        setReleaseDecisionRecords(releaseDecisionRes.items || []);
        setReleaseDecisionError(null);
      } else if (releaseDecisionRes?.__error) {
        setReleaseDecisionError(releaseDecisionRes.__error?.message || '发版结论登记加载失败');
      }
      if (healthWatchRes && !healthWatchRes.__error) {
        setHealthWatchStatus(healthWatchRes as HealthWatchStatusResponse);
        setHealthWatchError(null);
      } else if (healthWatchRes?.__error) {
        setHealthWatchError(healthWatchRes.__error?.message || '线上自检守护状态加载失败');
      }

      if (abilityRes) {
        if (abilityRes.length > 0) {
          if (!selectedAbilityId || !abilityRes.some((item) => item.id === selectedAbilityId)) {
            setSelectedAbilityId(abilityRes[0].id);
          }
        } else {
          setSelectedAbilityId(null);
        }
      }

      if (errors.length > 0) setLoadErrors(errors);
    } finally {
      setLoading(false);
    }
  };

  const refreshReleasePreflightSnapshots = async () => {
    setReleasePreflightLoading(true);
    try {
      const response = await adminApi.listReleasePreflightSnapshots(5);
      const items = response.items || [];
      setReleasePreflightSnapshots(items);
      setReleasePreflightLatest(items[0] || null);
      setReleasePreflightError(null);
    } catch (error) {
      setReleasePreflightError(error instanceof Error ? error.message : '发布前门禁记录加载失败');
    } finally {
      setReleasePreflightLoading(false);
    }
  };

  const refreshStrategySnapshots = async () => {
    setStrategySnapshotLoading(true);
    try {
      const response = await adminApi.listStrategySnapshots(8);
      setStrategySnapshots(response.items || []);
      setStrategySnapshotError(null);
    } catch (error) {
      setStrategySnapshotError(error instanceof Error ? error.message : '战略指标快照加载失败');
    } finally {
      setStrategySnapshotLoading(false);
    }
  };

  const createStrategySnapshot = async () => {
    setStrategySnapshotLoading(true);
    try {
      const response = await adminApi.createStrategySnapshot({ windowHours: 168, note: 'weekly' });
      setStrategySnapshots((prev) => [response, ...prev.filter((item) => item.id !== response.id)].slice(0, 8));
      setStrategySnapshotError(null);
    } catch (error) {
      setStrategySnapshotError(error instanceof Error ? error.message : '战略指标快照保存失败');
    } finally {
      setStrategySnapshotLoading(false);
    }
  };

  const refreshWeeklyReports = async () => {
    setWeeklyReportLoading(true);
    try {
      const response = await adminApi.listWeeklyReports(5);
      setWeeklyReports(response.items || []);
      setWeeklyReportError(null);
    } catch (error) {
      setWeeklyReportError(error instanceof Error ? error.message : '周报记录加载失败');
    } finally {
      setWeeklyReportLoading(false);
    }
  };

  const runWeeklyReport = async (send: boolean) => {
    setWeeklyReportLoading(true);
    try {
      const response = await adminApi.runWeeklyReport({ windowHours: 168, note: 'weekly-report', send, webhookFormat: 'generic' });
      setWeeklyReports((prev) => [response, ...prev.filter((item) => item.id !== response.id)].slice(0, 5));
      setWeeklyReportError(null);
    } catch (error) {
      setWeeklyReportError(error instanceof Error ? error.message : '周报生成失败');
    } finally {
      setWeeklyReportLoading(false);
    }
  };

  const runReleasePreflight = async () => {
    setReleasePreflightLoading(true);
    try {
      const response = await adminApi.runReleasePreflight({ mode: 'light' });
      setReleasePreflightLatest(response);
      setReleasePreflightSnapshots((prev) => [response, ...prev.filter((item) => item.id !== response.id)].slice(0, 5));
      setReleasePreflightError(null);
    } catch (error) {
      setReleasePreflightError(error instanceof Error ? error.message : '发布前门禁运行失败');
    } finally {
      setReleasePreflightLoading(false);
    }
  };

  const refreshReleasePatrolRecords = async () => {
    setReleasePatrolLoading(true);
    try {
      const response = await adminApi.listReleasePatrolRecords(5);
      setReleasePatrolRecords(response.items || []);
      setReleasePatrolError(null);
    } catch (error) {
      setReleasePatrolError(error instanceof Error ? error.message : '完整巡检记录加载失败');
    } finally {
      setReleasePatrolLoading(false);
    }
  };

  const refreshHealthWatchStatus = async () => {
    setHealthWatchLoading(true);
    try {
      const response = await adminApi.getHealthWatchStatus();
      setHealthWatchStatus(response);
      setHealthWatchError(null);
    } catch (error) {
      setHealthWatchError(error instanceof Error ? error.message : '线上自检守护状态加载失败');
    } finally {
      setHealthWatchLoading(false);
    }
  };

  const createReleasePatrolRecord = async (status: 'passed' | 'failed') => {
    const command =
      'python3 backend/scripts/patrol_eval_workflows.py --base-url http://127.0.0.1:8099 --timeout 1800 --report reports/eval_patrol_$(date +%Y%m%d_%H%M%S).json';
    setReleasePatrolLoading(true);
    try {
      const response = await adminApi.createReleasePatrolRecord({
        status,
        command,
        reportPath: 'reports/eval_patrol_*.json',
        note: status === 'passed' ? '人工确认完整巡检通过' : '人工确认完整巡检失败，需查看报告处理',
      });
      setReleasePatrolRecords((prev) => [response, ...prev.filter((item) => item.id !== response.id)].slice(0, 5));
      setReleasePatrolError(null);
    } catch (error) {
      setReleasePatrolError(error instanceof Error ? error.message : '完整巡检记录保存失败');
    } finally {
      setReleasePatrolLoading(false);
    }
  };

  const importReleasePatrolReport = async (reportPath: string) => {
    const normalizedPath = String(reportPath || '').trim();
    if (!normalizedPath) {
      setReleasePatrolError('请先填写巡检报告路径。');
      return;
    }
    const command =
      'python3 backend/scripts/patrol_eval_workflows.py --base-url http://127.0.0.1:8099 --timeout 1800 --report reports/eval_patrol_$(date +%Y%m%d_%H%M%S).json';
    setReleasePatrolLoading(true);
    try {
      const response = await adminApi.importReleasePatrolReport({ reportPath: normalizedPath, command });
      setReleasePatrolRecords((prev) => [response, ...prev.filter((item) => item.id !== response.id)].slice(0, 5));
      setReleasePatrolError(null);
    } catch (error) {
      setReleasePatrolError(error instanceof Error ? error.message : '巡检报告导入失败，请确认路径在后端工作目录内且 JSON 格式正确');
    } finally {
      setReleasePatrolLoading(false);
    }
  };

  const refreshReleaseDecisionRecords = async () => {
    setReleaseDecisionLoading(true);
    try {
      const response = await adminApi.listReleaseDecisionRecords(5);
      setReleaseDecisionRecords(response.items || []);
      setReleaseDecisionError(null);
    } catch (error) {
      setReleaseDecisionError(error instanceof Error ? error.message : '发版结论登记加载失败');
    } finally {
      setReleaseDecisionLoading(false);
    }
  };

  const createReleaseDecisionRecord = async (payload: {
    status: 'approved' | 'deferred' | 'blocked';
    title: string;
    note?: string;
    summary?: Record<string, unknown>;
  }) => {
    setReleaseDecisionLoading(true);
    try {
      const response = await adminApi.createReleaseDecisionRecord({
        status: payload.status,
        title: payload.title,
        note: payload.note,
        preflightId: releasePreflightLatest?.id || releasePreflightSnapshots[0]?.id || null,
        patrolId: releasePatrolRecords[0]?.id || null,
        summary: (payload.summary || {}) as JsonRecord,
      });
      setReleaseDecisionRecords((prev) => [response, ...prev.filter((item) => item.id !== response.id)].slice(0, 5));
      setReleaseDecisionError(null);
    } catch (error) {
      setReleaseDecisionError(error instanceof Error ? error.message : '发版结论登记失败');
    } finally {
      setReleaseDecisionLoading(false);
    }
  };

  const downloadBlob = (blob: Blob, filename: string) => {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  };

  const downloadJson = (data: unknown, filename: string) => {
    const payload = JSON.stringify(data, null, 2);
    downloadBlob(new Blob([payload], { type: 'application/json' }), filename);
  };

  const exportGlobalAbilityLogs = async (format: 'csv' | 'json') => {
    setExportingAbilityLogs(true);
    try {
      const exportSinceHours = globalAbilityLogWindowHours > 0 ? globalAbilityLogWindowHours : 24 * 30;
      const blob = await adminApi.exportAbilityLogs({
        format,
        sinceHours: exportSinceHours,
        provider: globalAbilityLogProvider !== 'all' ? globalAbilityLogProvider : undefined,
        capabilityKey: globalAbilityLogCapabilityKey !== 'all' ? globalAbilityLogCapabilityKey : undefined,
        status: globalAbilityLogStatus !== 'all' ? globalAbilityLogStatus : undefined,
        source: globalAbilityLogSource !== 'all' ? globalAbilityLogSource : undefined,
        templatePublished:
          globalAbilityLogTemplatePublished === 'all'
            ? undefined
            : globalAbilityLogTemplatePublished === 'published',
        search: globalAbilityLogSearch.trim() || undefined,
        callbackFailed: globalAbilityLogOnlyCallbackFailed || undefined,
      });
      const windowLabel = `${exportSinceHours}h`;
      const filename = `ability_logs_${windowLabel}_${new Date().toISOString().slice(0, 10)}.${format}`;
      downloadBlob(blob, filename);
    } catch (err: any) {
      console.error('Export ability logs failed:', err);
      setGlobalAbilityLogsError(err?.message || '导出失败');
    } finally {
      setExportingAbilityLogs(false);
    }
  };

  useEffect(() => {
    if (activeNav !== 'auth') return;
    if (isBusinessReadOnly) return;
    void refreshAuthPanel();
  }, [activeNav, isBusinessReadOnly]);

  useEffect(() => {
    if (activeNav !== 'billing') return;
    if (isBusinessReadOnly) return;
    if (billingOverview || billingLoading) return;
    void refreshBillingOverview();
  }, [activeNav, billingOverview, billingLoading, isBusinessReadOnly]);

  const refreshAbilityLogMetrics = async () => {
    setAbilityLogMetricsLoading(true);
    setAbilityLogMetricsError(null);
    try {
      const res = await adminApi.getAbilityLogMetrics({
        windowHours: abilityMetricsWindowHours,
        provider: abilityMetricsProvider !== 'all' ? abilityMetricsProvider : undefined,
        capabilityKey: abilityMetricsCapabilityKey !== 'all' ? abilityMetricsCapabilityKey : undefined,
      });
      setAbilityLogMetrics(res);
    } catch (err: any) {
      console.error('Failed to load ability log metrics:', err);
      setAbilityLogMetricsError(err?.message || '获取能力调用指标失败');
    } finally {
      setAbilityLogMetricsLoading(false);
    }
  };

  const refreshAbilityHealthSummary = async () => {
    setAbilityHealthLoading(true);
    setAbilityHealthError(null);
    try {
      const res = await adminApi.refreshAbilityHealthSummary({ staleHours: 24, limit: 100 });
      setAbilityHealthSummary(res);
    } catch (err: any) {
      console.error('Failed to refresh ability health summary:', err);
      setAbilityHealthError(err?.message || '刷新能力健康统计失败');
    } finally {
      setAbilityHealthLoading(false);
    }
  };

  const exportAbilityHealthSummary = async () => {
    setAbilityHealthExporting(true);
    setAbilityHealthError(null);
    try {
      const blob = await adminApi.exportAbilityHealthSummary({
        staleHours: 24,
        limit: 500,
        ...getAbilityHealthFilterQuery(abilityHealthFilter),
      });
      downloadBlob(blob, `ability-health-${abilityHealthFilter}-${Date.now()}.csv`);
    } catch (err: any) {
      console.error('Failed to export ability health summary:', err);
      setAbilityHealthError(err?.message || '导出能力复测清单失败');
    } finally {
      setAbilityHealthExporting(false);
    }
  };

  const refreshExecutorTraffic = useCallback(
    async (options?: { silent?: boolean }) => {
      const silent = Boolean(options?.silent);
      if (!silent) setExecutorTrafficLoading(true);
      setExecutorTrafficError(null);
      try {
        const res = await adminApi.getAbilityLogMetrics({ windowHours: 24, groupByExecutor: true });
        const next: Record<string, ExecutorTraffic> = {};
        for (const bucket of res.buckets || []) {
          const execId = bucket.executor_id;
          if (!execId) continue;
          const entry = next[execId] || {
            count: 0,
            success: 0,
            failed: 0,
            successRate: null,
            lastSuccessAt: null,
            lastFailedAt: null,
            p95Ms: null,
          };
          entry.count += bucket.count || 0;
          entry.success += bucket.success_count || 0;
          entry.failed += bucket.failed_count || 0;
          if (bucket.last_success_at && (!entry.lastSuccessAt || bucket.last_success_at > entry.lastSuccessAt)) {
            entry.lastSuccessAt = bucket.last_success_at;
          }
          if (bucket.last_failed_at && (!entry.lastFailedAt || bucket.last_failed_at > entry.lastFailedAt)) {
            entry.lastFailedAt = bucket.last_failed_at;
          }
          if (bucket.p95_duration_ms !== null && bucket.p95_duration_ms !== undefined) {
            entry.p95Ms = Math.max(entry.p95Ms || 0, bucket.p95_duration_ms);
          }
          next[execId] = entry;
        }
        for (const [execId, entry] of Object.entries(next)) {
          entry.successRate = entry.count > 0 ? entry.success / entry.count : null;
          next[execId] = entry;
        }
        setExecutorTraffic(next);
      } catch (err: any) {
        console.error('Failed to load executor traffic metrics:', err);
        setExecutorTrafficError(err?.message || '获取节点调用指标失败');
      } finally {
        if (!silent) setExecutorTrafficLoading(false);
      }
    },
    [setExecutorTraffic],
  );

  useEffect(() => {
    if (activeNav !== 'executors') return;
    // Warm cache for "channels" view, but avoid blocking initial render.
    refreshExecutorTraffic({ silent: true });
  }, [activeNav, refreshExecutorTraffic]);

  useEffect(() => {
    if (activeNav !== 'executors' && activeNav !== 'monitor') return;
    // Keep queue summary manual-refresh only.
    setComfyQueueSummary(null);
    setComfyQueueSummaryUpdatedAt(null);
    setComfyQueueSummaryError(null);
    setComfyQueueSummaryLoading(false);
  }, [activeNav]);

  useEffect(() => {
    load();
  }, []);

  useEffect(() => {
    if (activeNav !== 'monitor') return;
    if (!pageVisible) return;
    void load();
    const hasActiveWork = Boolean(
      (dashboardMetrics?.queue_overview?.total_pending ?? 0) > 0 ||
      (dashboardMetrics?.queue_overview?.total_running ?? 0) > 0,
    );
    const intervalMs = hasActiveWork ? 2000 : 10000;
    const timer = window.setInterval(() => {
      void load();
    }, intervalMs);
    return () => window.clearInterval(timer);
  }, [activeNav, pageVisible, dashboardMetrics?.queue_overview?.total_pending, dashboardMetrics?.queue_overview?.total_running]);

  useEffect(() => {
    if (selectedAbility?.provider !== 'comfyui' || !activeComfyExecutorId) {
      setComfyModelLoading(false);
      setComfyModelError(null);
      return;
    }
    if (comfyModelCache[activeComfyExecutorId]) {
      setComfyModelError(null);
      return;
    }
    let cancelled = false;
    setComfyModelLoading(true);
    setComfyModelError(null);
    adminApi
      .getComfyuiModels(activeComfyExecutorId)
      .then((resp) => {
        if (cancelled) return;
        setComfyModelCache((prev) => ({
          ...prev,
          [resp.executorId]: resp.models || {},
        }));
      })
      .catch((error) => {
        if (cancelled) return;
        setComfyModelError(error.message || '获取模型列表失败');
      })
      .finally(() => {
        if (!cancelled) setComfyModelLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedAbility?.provider, activeComfyExecutorId, comfyModelCache]);

  useEffect(() => {
    if (selectedAbility?.provider !== 'comfyui' || !activeComfyExecutorId || !abilitySchemaHasLora) {
      return;
    }
    if (comfyLoraSelectCache[activeComfyExecutorId]) return;
    let cancelled = false;
    adminApi
      .listComfyuiLoras({
        executorId: activeComfyExecutorId,
        status: 'active',
        includeUntracked: false,
      })
      .then((resp) => {
        if (cancelled) return;
        setComfyLoraSelectCache((prev) => ({ ...prev, [activeComfyExecutorId]: resp.items || [] }));
      })
      .catch((error) => {
        if (cancelled) return;
        console.error('Failed to load ComfyUI LoRA catalog for schema:', error);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedAbility?.provider, activeComfyExecutorId, abilitySchemaHasLora, comfyLoraSelectCache]);

  useEffect(() => {
    if (!abilityDialogOpen) return;
    if ((abilityForm.provider || '').toLowerCase() !== 'comfyui') return;
    if (!abilityFormComfyExecutorId) return;
    if (comfyLoraSelectCache[abilityFormComfyExecutorId]) return;
    let cancelled = false;
    adminApi
      .listComfyuiLoras({
        executorId: abilityFormComfyExecutorId,
        status: 'active',
        includeUntracked: false,
      })
      .then((resp) => {
        if (cancelled) return;
        setComfyLoraSelectCache((prev) => ({ ...prev, [abilityFormComfyExecutorId]: resp.items || [] }));
      })
      .catch((error) => {
        if (cancelled) return;
        console.error('Failed to load ComfyUI LoRA catalog for ability form:', error);
      });
    return () => {
      cancelled = true;
    };
  }, [abilityDialogOpen, abilityForm.provider, abilityFormComfyExecutorId, comfyLoraSelectCache]);

  const mergeComfyBaseModels = useCallback((executorId: string, incoming: string[]) => {
    if (!executorId) return;
    const cleaned = incoming.map((item) => item.trim()).filter(Boolean);
    if (cleaned.length === 0) return;
    setComfyBaseModelCache((prev) => {
      const existing = prev[executorId] || [];
      const merged = Array.from(new Set([...existing, ...cleaned]));
      return { ...prev, [executorId]: merged };
    });
    setComfyModelCache((prev) => {
      const existing = prev[executorId] || {};
      const existingList = Array.isArray(existing.unet) ? existing.unet : [];
      const merged = Array.from(new Set([...existingList, ...cleaned]));
      return { ...prev, [executorId]: { ...existing, unet: merged } };
    });
  }, []);

  const removeComfyBaseModel = useCallback(
    (executorId: string, model: string) => {
      if (!executorId) return;
      setComfyBaseModelCache((prev) => {
        const existing = prev[executorId] || [];
        const next = existing.filter((item) => item !== model);
        return { ...prev, [executorId]: next };
      });
      setComfyModelCache((prev) => {
        const existing = prev[executorId] || {};
        const existingList = Array.isArray(existing.unet) ? existing.unet : [];
        const next = existingList.filter((item) => item !== model);
        return { ...prev, [executorId]: { ...existing, unet: next } };
      });
    },
    [],
  );

  const clearComfyBaseModels = useCallback((executorId: string) => {
    if (!executorId) return;
    setComfyBaseModelCache((prev) => ({ ...prev, [executorId]: [] }));
    setComfyModelCache((prev) => {
      const existing = prev[executorId] || {};
      const next = { ...existing };
      if (next.unet) next.unet = [];
      return { ...prev, [executorId]: next };
    });
  }, []);

  const refreshComfyuiModelCatalog = useCallback(
    async (executorId: string, options?: { silent?: boolean; includeNodes?: boolean }) => {
      if (!executorId) return;
      const silent = Boolean(options?.silent);
      if (!silent) {
        setComfyModelLoadingByExecutor((prev) => ({ ...prev, [executorId]: true }));
      }
      setComfyModelErrorByExecutor((prev) => ({ ...prev, [executorId]: '' }));
      try {
        const resp = await adminApi.getComfyuiModels(executorId, { includeNodes: options?.includeNodes });
        const nextModels = resp.models || {};
        const nextUnet = Array.isArray(nextModels.unet) ? nextModels.unet : [];
        if (nextUnet.length > 0) {
          mergeComfyBaseModels(resp.executorId, nextUnet);
        }
        if (resp.nodeKeys && Array.isArray(resp.nodeKeys)) {
          setComfyNodeCache((prev) => ({
            ...prev,
            [resp.executorId]: resp.nodeKeys || [],
          }));
        }
        setComfyModelCache((prev) => ({
          ...prev,
          [resp.executorId]: { ...(prev[resp.executorId] || {}), ...nextModels, unet: nextUnet.length ? Array.from(new Set([...(prev[resp.executorId]?.unet || []), ...nextUnet])) : prev[resp.executorId]?.unet || [] },
        }));
      } catch (error: any) {
        setComfyModelErrorByExecutor((prev) => ({
          ...prev,
          [executorId]: error?.message || '获取模型列表失败',
        }));
      } finally {
        if (!silent) {
          setComfyModelLoadingByExecutor((prev) => ({ ...prev, [executorId]: false }));
        }
      }
    },
    [mergeComfyBaseModels],
  );

  useEffect(() => {
    if (!abilityDialogOpen) return;
    if ((abilityForm.provider || '').toLowerCase() !== 'comfyui') return;
    if (!abilityFormComfyExecutorId) return;
    if (comfyModelCache[abilityFormComfyExecutorId]) return;
    refreshComfyuiModelCatalog(abilityFormComfyExecutorId, { silent: true });
  }, [abilityDialogOpen, abilityForm.provider, abilityFormComfyExecutorId, comfyModelCache, refreshComfyuiModelCatalog]);

  const {
    handleComfyLoraDelete,
    handleComfyLoraSave,
    refreshComfyuiLoraCatalog,
    resetComfyLoraForm,
  } = useComfyuiLoraActions({
    comfyLoraExecutorId,
    comfyLoraForm,
    comfyLoraSearch,
    comfyLoraStatusFilter,
    comfyLoraTagsInput,
    comfyLoraTriggersInput,
    comfyLoraUntrackedLoaded,
    setComfyLoraCatalog,
    setComfyLoraDialogOpen,
    setComfyLoraError,
    setComfyLoraForm,
    setComfyLoraFormError,
    setComfyLoraLoading,
    setComfyLoraSaving,
    setComfyLoraTagsInput,
    setComfyLoraTriggersInput,
    setComfyLoraUntrackedLoaded,
  });

  const {
    handleComfyModelDelete,
    handleComfyModelSave,
    handleComfyPluginDelete,
    handleComfyPluginSave,
    handleComfyVersionDelete,
    handleComfyVersionSave,
    handleComfyVersionSync,
    refreshComfyModelCatalog,
    refreshComfyPluginCatalog,
    refreshComfyVersionCatalog,
    resetComfyModelForm,
    resetComfyPluginForm,
    resetComfyVersionForm,
  } = useComfyuiResourceCatalogActions({
    comfyModelCatalogSearch,
    comfyModelCatalogStatus,
    comfyModelCatalogType,
    comfyModelForm,
    comfyModelFormTags,
    comfyPluginCatalogSearch,
    comfyPluginCatalogStatus,
    comfyPluginForm,
    comfyPluginFormTags,
    comfyVersionCatalogSearch,
    comfyVersionCatalogStatus,
    comfyVersionForm,
    setComfyModelCatalogError,
    setComfyModelCatalogItems,
    setComfyModelCatalogLoading,
    setComfyModelDialogOpen,
    setComfyModelForm,
    setComfyModelFormError,
    setComfyModelFormTags,
    setComfyModelSaving,
    setComfyPluginCatalogError,
    setComfyPluginCatalogItems,
    setComfyPluginCatalogLoading,
    setComfyPluginDialogOpen,
    setComfyPluginForm,
    setComfyPluginFormError,
    setComfyPluginFormTags,
    setComfyPluginSaving,
    setComfyVersionCatalogError,
    setComfyVersionCatalogItems,
    setComfyVersionCatalogLoading,
    setComfyVersionDialogOpen,
    setComfyVersionForm,
    setComfyVersionFormError,
    setComfyVersionSaving,
    setComfyVersionSyncing,
  });

  const {
    handleComfyAgentDelete,
    handleComfyAgentSave,
    handleComfyAgentSetPrimary,
    handleComfyAgentTokenIssue,
    refreshComfyAgents,
    resetComfyAgentForm,
  } = useComfyuiAgentActions({
    comfyAgentConfigInput,
    comfyAgentForm,
    comfyAgentList,
    comfyAgentStatusFilter,
    setComfyAgentConfigInput,
    setComfyAgentDialogOpen,
    setComfyAgentError,
    setComfyAgentForm,
    setComfyAgentFormError,
    setComfyAgentList,
    setComfyAgentLoading,
    setComfyAgentPrimarySaving,
    setComfyAgentSaving,
    setComfyAgentTokenAgentId,
    setComfyAgentTokenDialogOpen,
    setComfyAgentTokenError,
    setComfyAgentTokenExpiresAt,
    setComfyAgentTokenLoading,
    setComfyAgentTokenValue,
  });

  const {
    handleComfyCreateRepairJob,
    handleComfyGenerateRepairPlan,
    handleComfyManifestGenerateFromWizard,
    handleComfyManifestPublish,
    handleComfyManifestRollback,
    handleComfyManifestSave,
    handleOpenComfyManifestDrift,
    refreshComfyManifests,
    refreshComfyRepairJobs,
    resetComfyManifestForm,
  } = useComfyuiManifestActions({
    comfyManifestContentInput,
    comfyManifestDriftContext,
    comfyManifestEditorMode,
    comfyManifestForm,
    comfyManifestRoleFilter,
    comfyManifestStatusFilter,
    comfyManifestWizardPreview,
    comfyRepairPlan,
    visibleComfyAgentList,
    setComfyManifestActionLoading,
    setComfyManifestContentInput,
    setComfyManifestDialogOpen,
    setComfyManifestDriftContext,
    setComfyManifestDriftData,
    setComfyManifestDriftDialogOpen,
    setComfyManifestDriftError,
    setComfyManifestDriftLoading,
    setComfyManifestDriftTitle,
    setComfyManifestEditorMode,
    setComfyManifestError,
    setComfyManifestForm,
    setComfyManifestFormError,
    setComfyManifestIncludeInactive,
    setComfyManifestList,
    setComfyManifestLoading,
    setComfyManifestSaving,
    setComfyRepairJobLoading,
    setComfyRepairJobs,
    setComfyRepairPlan,
    setComfyRepairPlanLoading,
  });

  const {
    handleComfyAgentTaskCreate,
    handleComfyAgentTaskPush,
    openComfyAgentTaskEvents,
    refreshComfyAgentTasks,
    refreshComfyMonitoringSummary,
    refreshComfyQueueSummary,
    refreshComfyWorkflowCompatibility,
  } = useComfyuiTaskActions({
    comfyAgentTaskAgentFilter,
    comfyAgentTaskForm,
    comfyAgentTaskPushAfterCreate,
    comfyAgentTaskStatusFilter,
    comfyExecutors,
    comfyMonitoringWindowHours,
    setComfyAgentTaskEvents,
    setComfyAgentTaskEventsDialogOpen,
    setComfyAgentTaskEventsError,
    setComfyAgentTaskEventsLoading,
    setComfyAgentTaskEventsTaskId,
    setComfyAgentTaskForm,
    setComfyAgentTaskFormError,
    setComfyAgentTaskPushLoading,
    setComfyAgentTaskSaving,
    setComfyAgentTasks,
    setComfyAgentTasksError,
    setComfyAgentTasksLoading,
    setComfyMonitoringError,
    setComfyMonitoringLoading,
    setComfyMonitoringSummary,
    setComfyQueueSummary,
    setComfyQueueSummaryError,
    setComfyQueueSummaryLoading,
    setComfyQueueSummaryUpdatedAt,
    setComfyWorkflowCompatibility,
    setComfyWorkflowCompatibilityError,
    setComfyWorkflowCompatibilityLoading,
    setComfyWorkflowCompatibilityUpdatedAt,
  });

  const {
    handleComfyDesktopReleaseSave,
    handleComfyEnrollCodeCreate,
    handleToggleComfyDesktopReleaseStatus,
    refreshComfyDesktopReleases,
    refreshComfyEnrollCodes,
    resetComfyDesktopReleaseForm,
  } = useComfyuiDesktopActions({
    comfyDesktopReleaseForm,
    comfyDesktopReleasePayloadInput,
    comfyDesktopReleaseStatusFilter,
    comfyEnrollCodeMaxUses,
    comfyEnrollCodeNote,
    comfyEnrollCodeRole,
    comfyEnrollCodeTtlSeconds,
    setComfyDesktopReleaseDialogOpen,
    setComfyDesktopReleaseForm,
    setComfyDesktopReleaseFormError,
    setComfyDesktopReleasePayloadInput,
    setComfyDesktopReleases,
    setComfyDesktopReleasesError,
    setComfyDesktopReleasesLoading,
    setComfyDesktopReleaseSaving,
    setComfyEnrollCodeCreating,
    setComfyEnrollCodeNote,
    setComfyEnrollCodes,
    setComfyEnrollCodesError,
    setComfyEnrollCodesLoading,
  });

  const refreshComfyuiSystemStats = useCallback(
    async (executorId: string, options?: { silent?: boolean }) => {
      if (!executorId) return;
      const silent = Boolean(options?.silent);
      if (!silent) {
        setComfySystemLoadingByExecutor((prev) => ({ ...prev, [executorId]: true }));
      }
      setComfySystemErrorByExecutor((prev) => ({ ...prev, [executorId]: '' }));
      try {
        const resp = await adminApi.getComfyuiSystemStats(executorId);
        const system = (resp?.system && typeof resp.system === 'object' ? (resp.system as Record<string, unknown>) : {}) || {};
        setComfySystemCache((prev) => ({ ...prev, [executorId]: system }));
      } catch (error: any) {
        console.error('Failed to load ComfyUI system stats:', error);
        setComfySystemErrorByExecutor((prev) => ({
          ...prev,
          [executorId]: error?.message || '获取版本失败',
        }));
      } finally {
        if (!silent) {
          setComfySystemLoadingByExecutor((prev) => ({ ...prev, [executorId]: false }));
        }
      }
    },
    [],
  );

  const refreshComfyVersionUsage = useCallback(async () => {
    if (comfyExecutors.length === 0) return;
    setComfyVersionServerLoading(true);
    try {
      await Promise.all(
        comfyExecutors
          .filter((executor) => (executor.type || '').toLowerCase() === 'comfyui')
          .map((executor) => refreshComfyuiSystemStats(executor.id, { silent: true })),
      );
    } finally {
      setComfyVersionServerLoading(false);
    }
  }, [comfyExecutors, refreshComfyuiSystemStats]);

  const {
    handleComfyuiServerCreate,
    handleSaveComfyDiffSnapshot,
    refreshComfyAgentAlerts,
    refreshComfyDiffLogs,
    refreshComfyuiServers,
  } = useComfyuiServerActions({
    buildComfyDiffSnapshot,
    comfyAgentAlertsAgentFilter,
    comfyAgentAlertsLimit,
    comfyAgentAlertsTypeFilter,
    comfyExecutors,
    comfyServerForm,
    load,
    refreshComfyuiModelCatalog,
    refreshComfyuiSystemStats,
    setComfyAgentAlerts,
    setComfyAgentAlertsError,
    setComfyAgentAlertsLoading,
    setComfyDiffLogs,
    setComfyDiffLogsError,
    setComfyDiffLogsLoading,
    setComfyDiffSaving,
    setComfyServerForm,
    setComfyServerFormError,
    setComfyServerRefreshing,
    setComfyServerSaving,
  });

  useEffect(() => {
    if (activeNav !== 'comfyui-management') return;
    if (!comfyLoraExecutorId && comfyExecutors.length > 0) {
      setComfyLoraExecutorId(comfyExecutors[0].id);
    }
  }, [activeNav, comfyExecutors, comfyLoraExecutorId]);

  useEffect(() => {
    if (activeNav !== 'comfyui-management') return;
    if (!comfyLoraExecutorId) return;
    if (!comfyModelCache[comfyLoraExecutorId]) {
      refreshComfyuiModelCatalog(comfyLoraExecutorId, { silent: true });
    }
  }, [activeNav, comfyLoraExecutorId, comfyModelCache, refreshComfyuiModelCatalog]);

  useEffect(() => {
    if (activeNav !== 'comfyui-management') return;
    refreshComfyuiLoraCatalog({ includeUntracked: false });
  }, [activeNav, comfyLoraExecutorId, comfyLoraSearch, comfyLoraStatusFilter, refreshComfyuiLoraCatalog]);

  useEffect(() => {
    if (activeNav !== 'comfyui-management' || comfyuiManageTab !== 'assets') return;
    refreshComfyVersionCatalog();
    refreshComfyModelCatalog();
    refreshComfyPluginCatalog();
  }, [
    activeNav,
    comfyuiManageTab,
    comfyVersionCatalogSearch,
    comfyVersionCatalogStatus,
    comfyModelCatalogSearch,
    comfyModelCatalogStatus,
    comfyModelCatalogType,
    comfyPluginCatalogSearch,
    comfyPluginCatalogStatus,
    refreshComfyVersionCatalog,
    refreshComfyModelCatalog,
    refreshComfyPluginCatalog,
  ]);

  useEffect(() => {
    if (activeNav !== 'comfyui-management' || comfyuiManageTab !== 'servers') return;
    const baselineId = comfyBaselineExecutor?.id;
    if (!baselineId) return;
    if (!comfyModelCache[baselineId]) {
      refreshComfyuiModelCatalog(baselineId, { silent: true, includeNodes: true });
    }
    if (!comfySystemCache[baselineId]) {
      refreshComfyuiSystemStats(baselineId, { silent: true });
    }
    if (comfyModelCatalogItems.length === 0) {
      refreshComfyModelCatalog({ silent: true });
    }
    if (comfyPluginCatalogItems.length === 0) {
      refreshComfyPluginCatalog({ silent: true });
    }
    refreshComfyDiffLogs({ silent: true });
  }, [
    activeNav,
    comfyuiManageTab,
    comfyBaselineExecutor?.id,
    comfyModelCache,
    comfySystemCache,
    comfyModelCatalogItems.length,
    comfyPluginCatalogItems.length,
    refreshComfyuiModelCatalog,
    refreshComfyuiSystemStats,
    refreshComfyModelCatalog,
    refreshComfyPluginCatalog,
    refreshComfyDiffLogs,
  ]);

  useEffect(() => {
    if (activeNav !== 'comfyui-management' || comfyuiManageTab !== 'templates') return;
    if (comfyExecutors.length === 0) return;
    comfyExecutors.forEach((executor) => {
      if (!comfyModelCache[executor.id] || !comfyNodeCache[executor.id]) {
        refreshComfyuiModelCatalog(executor.id, { silent: true, includeNodes: true });
      }
    });
  }, [
    activeNav,
    comfyuiManageTab,
    comfyExecutors,
    comfyModelCache,
    comfyNodeCache,
    refreshComfyuiModelCatalog,
  ]);

  useEffect(() => {
    if (activeNav !== 'comfyui-management' || comfyuiManageTab !== 'agents') return;
    refreshComfyAgents();
  }, [activeNav, comfyuiManageTab, refreshComfyAgents]);

  useEffect(() => {
    if (activeNav !== 'comfyui-management' || comfyuiManageTab !== 'desktop') return;
    refreshComfyEnrollCodes();
    refreshComfyDesktopReleases();
    refreshComfyAgents({ silent: true, status: 'all' });
  }, [
    activeNav,
    comfyuiManageTab,
    refreshComfyAgents,
    refreshComfyDesktopReleases,
    refreshComfyEnrollCodes,
  ]);

  useEffect(() => {
    if (comfyDesktopReleaseOptions.length === 0) {
      if (comfyDesktopInstallReleaseId) setComfyDesktopInstallReleaseId('');
      return;
    }
    if (comfyDesktopInstallReleaseId && comfyDesktopReleaseOptions.some((item) => item.value === comfyDesktopInstallReleaseId)) {
      return;
    }
    if (comfyDesktopActiveRelease?.id) {
      setComfyDesktopInstallReleaseId(String(comfyDesktopActiveRelease.id));
      return;
    }
    setComfyDesktopInstallReleaseId(comfyDesktopReleaseOptions[0].value);
  }, [comfyDesktopActiveRelease?.id, comfyDesktopInstallReleaseId, comfyDesktopReleaseOptions]);

  useEffect(() => {
    if (activeNav !== 'comfyui-management' || comfyuiManageTab !== 'manifests') return;
    refreshComfyManifests();
    refreshComfyRepairJobs();
  }, [activeNav, comfyuiManageTab, refreshComfyManifests, refreshComfyRepairJobs]);

  useEffect(() => {
    if (activeNav !== 'comfyui-management' || comfyuiManageTab !== 'tasks') return;
    if (visibleComfyAgentList.length === 0) {
      refreshComfyAgents({ silent: true });
    }
    if (comfyManifestList.length === 0) {
      refreshComfyManifests({ silent: true });
    }
    refreshComfyAgentTasks();
    refreshComfyMonitoringSummary();
  }, [
    activeNav,
    comfyuiManageTab,
    visibleComfyAgentList.length,
    comfyManifestList.length,
    refreshComfyAgents,
    refreshComfyManifests,
    refreshComfyAgentTasks,
    refreshComfyMonitoringSummary,
  ]);

  useEffect(() => {
    if (activeNav !== 'comfyui-management' || comfyuiManageTab !== 'alerts') return;
    if (visibleComfyAgentList.length === 0) {
      refreshComfyAgents({ silent: true });
    }
    refreshComfyAgentAlerts();
  }, [activeNav, comfyuiManageTab, visibleComfyAgentList.length, refreshComfyAgents, refreshComfyAgentAlerts]);

  useEffect(() => {
    setAbilityTemplateState(null);
    setAbilityTemplateError(null);
    setAbilityTemplateValidateResult(null);
    setAbilityTemplateVersionLabel('');
    setAbilityTemplateNotes('');
    setAbilityTemplateRollbackId('');
  }, [selectedAbilityId]);

  useEffect(() => {
    if (visibleComfyAgentList.length === 0) return;
    const selected = comfyAgentTaskForm.agentId;
    const matched = selected ? visibleComfyAgentList.some((agent) => agent.id === selected) : false;
    if (!selected || !matched) {
      setComfyAgentTaskForm((prev) => ({ ...prev, agentId: visibleComfyAgentList[0].id }));
    }
  }, [visibleComfyAgentList, comfyAgentTaskForm.agentId]);

  const refreshComfyQueueStatus = useCallback(
    async (options?: { silent?: boolean }) => {
      const silent = Boolean(options?.silent);
      if (selectedAbility?.provider !== 'comfyui' || !activeComfyExecutorId) {
        setComfyQueueStatus(null);
        setComfyQueueError(null);
        setComfyQueueUpdatedAt(null);
        if (!silent) setComfyQueueLoading(false);
        return;
      }
      if (!silent) {
        setComfyQueueLoading(true);
      }
      try {
        const response = await adminApi.getComfyuiQueueStatus(activeComfyExecutorId);
        setComfyQueueStatus(response);
        setComfyQueueError(null);
        setComfyQueueUpdatedAt(new Date().toISOString());
      } catch (error) {
        console.error('load ComfyUI queue status failed', error);
        setComfyQueueError(error instanceof Error ? error.message : '获取队列状态失败');
      } finally {
        if (!silent) {
          setComfyQueueLoading(false);
        }
      }
    },
    [selectedAbility?.provider, activeComfyExecutorId],
  );

  useEffect(() => {
    if (activeNav !== 'comfyui-management' || comfyuiManageTab !== 'tasks') return;
    refreshComfyQueueSummary({ silent: true });
    refreshComfyWorkflowCompatibility({ silent: true });
  }, [activeNav, comfyuiManageTab, refreshComfyQueueSummary, refreshComfyWorkflowCompatibility]);

  useEffect(() => {
    if (selectedAbility?.provider !== 'comfyui' || !activeComfyExecutorId) {
      setComfyQueueStatus(null);
      setComfyQueueError(null);
      setComfyQueueUpdatedAt(null);
      setComfyQueueLoading(false);
      return;
    }
    // Manual refresh only; reset stale state when switching executor.
    setComfyQueueStatus(null);
    setComfyQueueError(null);
    setComfyQueueUpdatedAt(null);
    setComfyQueueLoading(false);
  }, [selectedAbility?.provider, activeComfyExecutorId]);

  const copyTextToClipboard = async (value: string) => {
    try {
      await navigator.clipboard.writeText(value);
    } catch (error) {
      console.error('copy text failed', error);
    }
  };
  const refreshAbilityLogs = useCallback(
    async (options?: { silent?: boolean; page?: number }) => {
    if (!selectedAbility?.id) {
      setAbilityLogs([]);
      setAbilityLogsError(null);
      setAbilityLogTotal(null);
      return;
    }
    const silent = options?.silent;
    const targetPage = Math.max(1, options?.page ?? abilityLogPage);
    if (!silent) {
      setAbilityLogsLoading(true);
    }
    try {
      const response = await adminApi.listAbilityLogs(selectedAbility.id, {
        limit: abilityLogPageSize,
        offset: (targetPage - 1) * abilityLogPageSize,
      });
      const items = response.items || [];
      setAbilityLogs(items);
      setAbilityLogTotal(typeof response.total === 'number' ? response.total : items.length);
      setAbilityLogPage(targetPage);
      setAbilityLogsUpdatedAt(new Date().toISOString());
      setAbilityLogsError(null);
    } catch (error) {
      console.debug('load ability logs failed', error);
      setAbilityLogsError(error instanceof Error ? error.message : '加载能力调用记录失败');
    } finally {
      if (!silent) {
        setAbilityLogsLoading(false);
      }
    }
    },
    [selectedAbility?.id, abilityLogPage],
  );

  useEffect(() => {
    void refreshAbilityLogs();
  }, [refreshAbilityLogs]);

  const refreshGlobalAbilityLogs = useCallback(
    async (options?: { silent?: boolean; page?: number }) => {
    const silent = options?.silent;
    const targetPage = Math.max(1, options?.page ?? globalAbilityLogPage);
    if (globalAbilityLogsRequestInFlightRef.current) {
      return;
    }
    globalAbilityLogsRequestInFlightRef.current = true;
    if (!silent) {
      setGlobalAbilityLogsLoading(true);
    }
    try {
      const response = await adminApi.listAllAbilityLogs({
        limit: globalAbilityLogPageSize,
        offset: (targetPage - 1) * globalAbilityLogPageSize,
        provider: globalAbilityLogProvider !== 'all' ? globalAbilityLogProvider : undefined,
        capabilityKey: globalAbilityLogCapabilityKey !== 'all' ? globalAbilityLogCapabilityKey : undefined,
        status: globalAbilityLogStatus !== 'all' ? globalAbilityLogStatus : undefined,
        source: globalAbilityLogSource !== 'all' ? globalAbilityLogSource : undefined,
        templatePublished:
          globalAbilityLogTemplatePublished === 'all'
            ? undefined
            : globalAbilityLogTemplatePublished === 'published',
        sinceHours: globalAbilityLogWindowHours,
        search: globalAbilityLogSearch.trim() || undefined,
        callbackFailed: globalAbilityLogOnlyCallbackFailed || undefined,
      });
      const items = response.items || [];
      setGlobalAbilityLogs(items);
      setGlobalAbilityLogTotal(typeof response.total === 'number' ? response.total : items.length);
      setGlobalAbilityLogPage(targetPage);
      setGlobalAbilityLogsUpdatedAt(new Date().toISOString());
      setGlobalAbilityLogsError(null);
    } catch (error) {
      console.debug('load global ability logs failed', error);
      setGlobalAbilityLogsError(error instanceof Error ? error.message : '加载能力调用清单失败');
    } finally {
      globalAbilityLogsRequestInFlightRef.current = false;
      if (!silent) {
        setGlobalAbilityLogsLoading(false);
      }
    }
    },
    [
      globalAbilityLogCapabilityKey,
      globalAbilityLogPage,
      globalAbilityLogProvider,
      globalAbilityLogWindowHours,
      globalAbilityLogOnlyCallbackFailed,
      globalAbilityLogSearch,
      globalAbilityLogSource,
      globalAbilityLogStatus,
      globalAbilityLogTemplatePublished,
    ],
  );

  const openAbilityLogDetail = useCallback(async (row: AbilityInvocationLog) => {
    setAbilityLogDetail(row);
    setAbilityLogResolveError(null);
    setAbilityLogResolveLoading(false);
    setAbilityLogDetailOpen(true);
    try {
      const detail = await adminApi.getAbilityLog(row.id);
      setAbilityLogDetail(detail);
    } catch (error: any) {
      console.error('load ability log detail failed', error);
      setAbilityLogResolveError(error?.message || '加载调用详情失败，请刷新后重试。');
    }
  }, []);

  const resolveAbilityLog = useCallback(async () => {
    if (!abilityLogDetail) return;
    setAbilityLogResolveLoading(true);
    setAbilityLogResolveError(null);
    try {
      const updated = await adminApi.resolveAbilityLog(abilityLogDetail.id);
      setAbilityLogDetail(updated);
      await refreshAbilityLogs({ silent: true });
      await refreshGlobalAbilityLogs({ silent: true });
    } catch (error: any) {
      console.error('resolve ability log failed', error);
      setAbilityLogResolveError(error?.message || '回调解析失败');
    } finally {
      setAbilityLogResolveLoading(false);
    }
  }, [abilityLogDetail, refreshAbilityLogs, refreshGlobalAbilityLogs]);

  useEffect(() => {
    if (abilityMetricsProvider === 'all') {
      if (abilityMetricsCapabilityKey !== 'all') {
        setAbilityMetricsCapabilityKey('all');
      }
      return;
    }
    if (
      abilityMetricsCapabilityKey !== 'all' &&
      !abilities.some(
        (ability) => ability.provider === abilityMetricsProvider && ability.capability_key === abilityMetricsCapabilityKey,
      )
    ) {
      setAbilityMetricsCapabilityKey('all');
    }
  }, [abilities, abilityMetricsProvider, abilityMetricsCapabilityKey]);

  useEffect(() => {
    if (globalAbilityLogProvider === 'all') {
      if (globalAbilityLogCapabilityKey !== 'all') {
        setGlobalAbilityLogCapabilityKey('all');
      }
      return;
    }
    if (
      globalAbilityLogCapabilityKey !== 'all' &&
      !abilities.some(
        (ability) => ability.provider === globalAbilityLogProvider && ability.capability_key === globalAbilityLogCapabilityKey,
      )
    ) {
      setGlobalAbilityLogCapabilityKey('all');
    }
  }, [abilities, globalAbilityLogProvider, globalAbilityLogCapabilityKey]);

  useEffect(() => {
    if (activeNav !== 'ability-logs' || abilityLogTab !== 'logs') return;
    void refreshGlobalAbilityLogs();
  }, [activeNav, abilityLogTab, refreshGlobalAbilityLogs]);

  useEffect(() => {
    setAbilityLogPage(1);
  }, [selectedAbility?.id]);

  useEffect(() => {
    setGlobalAbilityLogPage(1);
  }, [
    globalAbilityLogCapabilityKey,
    globalAbilityLogOnlyCallbackFailed,
    globalAbilityLogProvider,
    globalAbilityLogSearch,
    globalAbilityLogSource,
    globalAbilityLogStatus,
    globalAbilityLogTemplatePublished,
    globalAbilityLogWindowHours,
  ]);

  useEffect(() => {
    if (activeNav !== 'ability-logs' || abilityLogTab !== 'metrics') return;
    void refreshAbilityLogMetrics();
  }, [activeNav, abilityLogTab, abilityMetricsWindowHours, abilityMetricsProvider, abilityMetricsCapabilityKey]);

  useEffect(() => {
    if (!selectedAbility?.id || !abilityLogsAutoRefresh || !pageVisible) return;
    const interval = window.setInterval(() => {
      void refreshAbilityLogs({ silent: true });
    }, 10000);
    return () => window.clearInterval(interval);
  }, [selectedAbility?.id, abilityLogsAutoRefresh, refreshAbilityLogs, pageVisible]);

  useEffect(() => {
    if (activeNav !== 'ability-logs' || abilityLogTab !== 'logs' || !globalAbilityLogsAutoRefresh || !pageVisible) return;
    const interval = window.setInterval(() => {
      void refreshGlobalAbilityLogs({ silent: true });
    }, 12000);
    return () => window.clearInterval(interval);
  }, [activeNav, abilityLogTab, globalAbilityLogsAutoRefresh, refreshGlobalAbilityLogs, pageVisible]);

  const refreshPublicAbilities = useCallback(async () => {
    setPublicAbilitiesLoading(true);
    try {
      const list = await adminApi.listPublicAbilities();
      setPublicAbilities(list);
    } catch (error) {
      console.error('load public abilities failed', error);
    } finally {
      setPublicAbilitiesLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshPublicAbilities();
  }, [refreshPublicAbilities]);

  const handleOpenCozeStudio = useCallback(() => {
    if (cozeBaseUrl) {
      window.open(cozeBaseUrl, '_blank', 'noopener,noreferrer');
    }
  }, [cozeBaseUrl]);

  const handleOpenCozeLoop = useCallback(() => {
    if (cozeLoopUrl) {
      window.open(cozeLoopUrl, '_blank', 'noopener,noreferrer');
    }
  }, [cozeLoopUrl]);

  const abilityApiExample = useMemo(() => {
    const abilityId = selectedAbility?.id ?? '{abilityId}';
    const body = {
      imageUrl: 'https://example.com/sample.png',
      inputs: selectedAbility?.default_params || { prompt: '示例提示词' },
    };
    const payload = JSON.stringify(body, null, 2).replace(/'/g, "\\'");
    return `curl -X POST https://<host>/api/abilities/${abilityId}/invoke \\\n  -H \"Authorization: Bearer <token>\" \\\n  -H \"Content-Type: application/json\" \\\n  -d '${payload}'`;
  }, [selectedAbility?.id, selectedAbility?.default_params]);
  const schemaHasImageField = useMemo(
    () =>
      abilitySchemaFields.some(
        (field) =>
          field.name === 'image_url' ||
          field.name === 'image_urls' ||
          field.name === 'input_urls' ||
          field.type === 'image',
      ),
    [abilitySchemaFields],
  );
  const abilityRequiresImageInput =
    selectedAbilityMetadata?.requires_image_input !== undefined
      ? Boolean(selectedAbilityMetadata?.requires_image_input)
      : selectedAbility?.provider === 'baidu';
  const abilityAllowsImageInput = abilityRequiresImageInput || schemaHasImageField;
  const pinnedAbilityExecutor = useMemo(() => {
    if (!selectedAbility?.executor_id) return null;
    return executors.find((executor) => executor.id === selectedAbility.executor_id) || null;
  }, [executors, selectedAbility]);

  useEffect(() => {
    if (abilities.length === 0) {
      setSelectedAbilityId(null);
      return;
    }
    if (!selectedAbilityId || !abilities.some((ability) => ability.id === selectedAbilityId)) {
      setSelectedAbilityId(abilities[0].id);
    }
  }, [abilities, selectedAbilityId]);

  useEffect(() => {
    setActiveAbilityDetailTab('overview');
  }, [selectedAbilityId]);

  useEffect(() => {
    if (!selectedAbility) {
      setTestForm((prev) => ({
        ...prev,
        abilityId: null,
        provider: null,
        capabilityKey: null,
        executorId: null,
        params: '',
        imageUrl: '',
        imageBase64: '',
        comfyuiSubmitOnly: false,
      }));
      setSchemaValues({});
      return;
    }
    const fallbackExecutorId = selectedAbility.executor_id || abilityExecutors[0]?.id || null;
    setTestForm((prev) => ({
      ...prev,
      abilityId: selectedAbility.id,
      provider: selectedAbility.provider,
      capabilityKey: selectedAbility.capability_key,
      executorId: fallbackExecutorId,
      params: '',
      imageUrl: '',
      imageBase64: '',
      comfyuiSubmitOnly: false,
    }));
    setTestResult(null);
    setUploadedImage(null);
    setUploadError(null);
  }, [selectedAbility, abilityExecutors]);

  useEffect(() => {
    if (!selectedAbility) {
      setSchemaValues({});
      return;
    }
    if (abilitySchemaFields.length === 0) {
      setSchemaValues({});
      return;
    }
    const defaults = (selectedAbility.default_params || {}) as Record<string, unknown>;
    const nextValues: SchemaFormValues = {};
    abilitySchemaFields.forEach((field) => {
      const fallback = defaults[field.name] ?? field.defaultValue;
      nextValues[field.name] = formatSchemaValueForInput(field, fallback);
    });
    setSchemaValues(nextValues);
  }, [selectedAbility?.id, abilitySchemaFields]);

  const getExecutorChannelLabel = (executor: Executor): string => {
    const config = executor.config || {};
    const channelKey =
      (typeof config.channel_key === 'string' && config.channel_key.trim()) ||
      (typeof config.channelKey === 'string' && config.channelKey.trim()) ||
      '';
    if (channelKey) return channelKey;
    if (executor.base_url) {
      try {
        const url = new URL(executor.base_url);
        return url.host;
      } catch {
        // ignore
      }
    }
    return executor.name;
  };

  const extractAllowedExecutorIds = (metadata?: string | JsonRecord | null): string[] => {
    if (!metadata) return [];
    const record = parseJSON(metadata);
    const value = record.allowed_executor_ids;
    if (Array.isArray(value)) {
      return value.filter((entry): entry is string => typeof entry === 'string' && entry.trim().length > 0);
    }
    return [];
  };

  const {
    addWorkflowInputMap,
    addWorkflowInputMapEntry,
    addWorkflowInputMappingsForNode,
    addWorkflowOutputNode,
    addWorkflowOutputNodeById,
    handleWorkflowClone,
    handleWorkflowFile,
    handleWorkflowSubmit,
    removeWorkflowInputMap,
    removeWorkflowOutputNode,
    syncWorkflowMetadata,
    updateWorkflowInputMap,
    updateWorkflowNodeInputValue,
    updateWorkflowOutputNodes,
  } = useWorkflowTemplateActions({
    comfyWorkflowNodes,
    defaultWorkflowForm,
    extractAllowedExecutorIds,
    extractErrorMessage: (error) => extractErrorMessage(error),
    load,
    normalizeInputNodeMap,
    normalizeOutputNodeIds,
    parseJSON,
    resolveComfyuiDefinition,
    serializeInputNodeMap,
    setWorkflowForm,
    setWorkflowFormAllowedExecutors,
    setWorkflowFormErrors,
    setWorkflowInputMap,
    setWorkflowOutputNodeIds,
    setWorkflowOutputPickerNodeId,
    setWorkflowOutputShowAll,
    stringifyJSON: (value) => stringifyJSON(value),
    workflowDefinitionError,
    workflowDefinitionInfo,
    workflowDefinitionParse,
    workflowForm,
    workflowFormAllowedExecutors,
    workflowInputMap,
    workflowInputPickerKeys,
    workflowInputPickerNodeId,
    workflowMappingErrors,
    workflowMetadataError,
    workflowMetadataParse,
    workflowOutputNodeIds,
    workflowOutputPickerNodeId,
  });

  useEffect(() => {
    const parsed = safeParseJSON(workflowForm.metadata);
    if (!parsed.ok) return;
    setWorkflowFormAllowedExecutors(extractAllowedExecutorIds(parsed.value));
    setWorkflowInputMap(normalizeInputNodeMap(parsed.value));
    setWorkflowOutputNodeIds(normalizeOutputNodeIds(parsed.value));
  }, [workflowForm.metadata]);

  useEffect(() => {
    if (workflowFormErrors.length === 0) return;
    setWorkflowFormErrors([]);
  }, [
    workflowForm.action,
    workflowForm.name,
    workflowForm.definition,
    workflowForm.metadata,
    workflowInputMap,
    workflowOutputNodeIds,
  ]);

  useEffect(() => {
    if (baseModelCacheLoadedRef.current) return;
    baseModelCacheLoadedRef.current = true;
    try {
      const raw = localStorage.getItem(COMFYUI_BASE_MODEL_STORAGE_KEY);
      if (!raw) return;
      const parsed = safeParseJSON(raw);
      if (!parsed.ok || !parsed.value || typeof parsed.value !== 'object') return;
      const record = parsed.value as Record<string, unknown>;
      const normalized: Record<string, string[]> = {};
      Object.entries(record).forEach(([executorId, value]) => {
        const items = normalizeTextList(value);
        if (items.length > 0) {
          normalized[executorId] = Array.from(new Set(items));
        }
      });
      if (Object.keys(normalized).length === 0) return;
      setComfyBaseModelCache(normalized);
      setComfyModelCache((prev) => {
        const next = { ...prev };
        Object.entries(normalized).forEach(([executorId, list]) => {
          const existing = next[executorId] || {};
          const merged = Array.from(new Set([...(existing.unet || []), ...list]));
          next[executorId] = { ...existing, unet: merged };
        });
        return next;
      });
    } catch (error) {
      console.warn('Failed to load comfy base model cache', error);
    }
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(COMFYUI_BASE_MODEL_STORAGE_KEY, JSON.stringify(comfyBaseModelCache));
    } catch (error) {
      console.warn('Failed to persist comfy base model cache', error);
    }
  }, [comfyBaseModelCache]);

  useEffect(() => {
    if (baselineLoadedRef.current) return;
    if (comfyExecutors.length === 0) return;
    baselineLoadedRef.current = true;
    try {
      const stored = localStorage.getItem(COMFYUI_BASELINE_STORAGE_KEY);
      if (stored && comfyExecutors.some((executor) => executor.id === stored)) {
        setComfyBaselineExecutorId(stored);
        return;
      }
    } catch (error) {
      console.warn('Failed to read comfy baseline id', error);
    }
    setComfyBaselineExecutorId(comfyExecutors[0]?.id || '');
  }, [comfyExecutors]);

  useEffect(() => {
    if (!comfyBaselineExecutorId) return;
    try {
      localStorage.setItem(COMFYUI_BASELINE_STORAGE_KEY, comfyBaselineExecutorId);
    } catch (error) {
      console.warn('Failed to persist comfy baseline id', error);
    }
  }, [comfyBaselineExecutorId]);

  const handleAbilitySubmit = async () => {
    if (
      !abilityForm.provider ||
      !abilityForm.category ||
      !abilityForm.capability_key ||
      !abilityForm.display_name ||
      !abilityForm.status
    ) {
      return;
    }
    const baseMetadata = abilityForm.metadata ? parseJSON(abilityForm.metadata) : {};
    const nextMetadata: Record<string, unknown> = { ...(baseMetadata || {}) };
    if (abilityForm.provider === 'comfyui') {
      const cleanedAllowed = abilityAllowedExecutors.filter((id) => id && id.trim());
      const cleanedTags = normalizeTagList(abilityRequiredTags)
        .map((item) => item.trim())
        .filter(Boolean);
      if (cleanedAllowed.length > 0) {
        nextMetadata.allowed_executor_ids = cleanedAllowed;
      } else {
        delete nextMetadata.allowed_executor_ids;
      }
      if (cleanedTags.length > 0) {
        nextMetadata.required_tags = cleanedTags;
      } else {
        delete nextMetadata.required_tags;
      }
      if (abilityRoutingPolicy && abilityRoutingPolicy !== 'auto') {
        nextMetadata.routing_policy = abilityRoutingPolicy;
      } else {
        delete nextMetadata.routing_policy;
      }
      nextMetadata.fallback_to_default = Boolean(abilityFallbackToDefault);

      const cleanedLoraFiles = abilityLoraAllowedFiles.filter((name) => name && name.trim());
      const cleanedLoraTags = normalizeTagList(abilityLoraAllowedTags)
        .map((item) => item.trim())
        .filter(Boolean);
      if (cleanedLoraFiles.length > 0) {
        nextMetadata.allowed_lora_files = cleanedLoraFiles;
      } else {
        delete nextMetadata.allowed_lora_files;
      }
      if (cleanedLoraTags.length > 0) {
        nextMetadata.allowed_lora_tags = cleanedLoraTags;
      } else {
        delete nextMetadata.allowed_lora_tags;
      }
      const cleanedBaseModels = abilityLoraAllowedBaseModels.filter((name) => name && name.trim());
      if (cleanedBaseModels.length > 0) {
        nextMetadata.allowed_lora_base_models = cleanedBaseModels;
      } else {
        delete nextMetadata.allowed_lora_base_models;
      }
      if (abilityLoraDefault && abilityLoraDefault.trim()) {
        nextMetadata.default_lora = abilityLoraDefault.trim();
      } else {
        delete nextMetadata.default_lora;
      }
      if (abilityLoraPolicy && abilityLoraPolicy !== 'fallback') {
        nextMetadata.lora_policy = abilityLoraPolicy;
      } else {
        delete nextMetadata.lora_policy;
      }
    }

    const payload: Partial<Ability> = {
      provider: abilityForm.provider,
      category: abilityForm.category,
      capability_key: abilityForm.capability_key,
      version: abilityForm.version || 'v1',
      display_name: abilityForm.display_name,
      description: abilityForm.description,
      status: abilityForm.status,
      ability_type: abilityForm.ability_type || abilityTypeOptions[0].value,
      executor_id: abilityForm.executor_id,
      workflow_id: abilityForm.workflow_id || undefined,
      vendor_model_id: abilityForm.vendor_model_id ? Number(abilityForm.vendor_model_id) : null,
      coze_workflow_id: abilityForm.coze_workflow_id || undefined,
      default_params: abilityForm.default_params ? parseJSON(abilityForm.default_params) : undefined,
      input_schema: abilityForm.input_schema ? parseJSON(abilityForm.input_schema) : undefined,
      metadata: isEmptyRecord(nextMetadata) ? undefined : (nextMetadata as JsonRecord),
    };
    if (abilityForm.id) {
      await adminApi.updateAbility(abilityForm.id, payload);
    } else {
      await adminApi.createAbility({ ...payload, id: abilityForm.id || undefined });
    }
    setAbilityForm(defaultAbilityForm);
    setAbilityRoutingPolicy('auto');
    setAbilityAllowedExecutors([]);
    setAbilityRequiredTags('');
    setAbilityFallbackToDefault(true);
    setAbilityLoraDefault('');
    setAbilityLoraAllowedFiles([]);
    setAbilityLoraAllowedTags('');
    setAbilityLoraAllowedBaseModels([]);
    setAbilityLoraPolicy('fallback');
    setAbilityDialogOpen(false);
    load();
  };

  const handleAbilityEdit = (ability: Ability) => {
    const routing = parseRoutingMetadata(ability.metadata as JsonRecord | null);
    const loraMeta = parseLoraMetadata(ability.metadata as JsonRecord | null);
    setAbilityForm({
      ...ability,
      version: ability.version || 'v1',
      ability_type: ability.ability_type || abilityTypeOptions[0].value,
      workflow_id: ability.workflow_id || undefined,
      default_params: formatJsonValue(ability.default_params),
      input_schema: formatJsonValue(ability.input_schema),
      metadata: formatJsonValue(ability.metadata),
    });
    setAbilityRoutingPolicy(routing.policy || 'auto');
    setAbilityAllowedExecutors(routing.allowed);
    setAbilityRequiredTags(routing.required.join(', '));
    setAbilityFallbackToDefault(routing.fallback);
    setAbilityLoraDefault(loraMeta.defaultLora || '');
    setAbilityLoraAllowedFiles(loraMeta.allowedFiles || []);
    setAbilityLoraAllowedTags((loraMeta.allowedTags || []).join(', '));
    setAbilityLoraAllowedBaseModels(loraMeta.allowedBaseModels || []);
    setAbilityLoraPolicy(loraMeta.policy || 'fallback');
    setAbilityDialogOpen(true);
  };

  const handleAbilityDelete = async (id: string) => {
    await adminApi.deleteAbility(id);
    load();
  };

  const {
    resetBusinessForm,
    handleBusinessEdit,
    handleBusinessCreateDraft,
    handleBusinessDraftRecipeUpdate,
    handleBusinessSetDefault,
    handleBusinessDefaultApprovalDecision,
    handleBusinessToggleActive,
    handleBusinessRecordAcceptance,
    handleBusinessDraftRun,
    handleBusinessDraftRunBatch,
    handleBusinessCompare,
    handleBusinessRollback,
    refreshBusinessRuns,
    exportBusinessRuns,
    handleBusinessCallbackRetry,
    handleBusinessBulkCallbackRetry,
    handleBusinessBulkRetest,
    handleBusinessBulkIgnoreIssues,
    handleBusinessGenerateIssueChecklist,
    handleBusinessSubmit,
  } = useBusinessDashboardActions({
    businessForm,
    businessRuns,
    businessRunFilters,
    defaultBusinessCapabilityForm,
    effectiveBusinessCompareLeftId,
    effectiveBusinessCompareRightId,
    isBusinessReadOnly,
    selectedBusinessCompareLeft,
    selectedBusinessCompareRight,
    downloadBlob,
    load,
    setBusinessActionError,
    setBusinessActionLoadingId,
    setBusinessCompareResult,
    setBusinessDefaultApprovals,
    setBusinessDialogOpen,
    setBusinessForm,
    setBusinessFormError,
    setBusinessOperationLogs,
    setBusinessRunDetail,
    setBusinessRuns,
    setBusinessRunTotal,
    setBusinessUsageSummary,
  });

  const loadBusinessOutputReviews = useCallback(async (runId: string) => {
    const normalizedRunId = runId.trim();
    if (!normalizedRunId) {
      setBusinessOutputReviews([]);
      setBusinessOutputReviewsError(null);
      return;
    }
    setBusinessOutputReviewsLoading(true);
    setBusinessOutputReviewsError(null);
    try {
      const response = await adminApi.listBusinessOutputReviews(normalizedRunId);
      setBusinessOutputReviews(response.items || []);
    } catch (error: any) {
      setBusinessOutputReviews([]);
      setBusinessOutputReviewsError(error?.message || '加载出图质量标注失败，请刷新后重试。');
    } finally {
      setBusinessOutputReviewsLoading(false);
    }
  }, []);

  const handleBusinessOutputReviewSave = useCallback(
    async (
      runId: string,
      item: {
        outputIndex: number;
        outputUrl?: string | null;
        qualityGrade: string;
        inputTags?: string[];
        issueTags?: string[];
        nextAction?: string | null;
        note?: string | null;
      },
    ) => {
      if (isBusinessReadOnly) return;
      const normalizedRunId = runId.trim();
      if (!normalizedRunId) return;
      const actionId = `output-review:${normalizedRunId}:${item.outputIndex}`;
      setBusinessActionLoadingId(actionId);
      setBusinessOutputReviewsError(null);
      try {
        const response = await adminApi.upsertBusinessOutputReviews(normalizedRunId, { items: [item] });
        setBusinessOutputReviews(response.items || []);
        void adminApi
          .getBusinessOutputReviewSummary({ windowHours: 168 })
          .then(setBusinessOutputReviewSummary)
          .catch(() => undefined);
      } catch (error: any) {
        setBusinessOutputReviewsError(error?.message || '保存出图质量标注失败，请检查填写内容后重试。');
      } finally {
        setBusinessActionLoadingId((prev) => (prev === actionId ? null : prev));
      }
    },
    [isBusinessReadOnly],
  );

  const activeBusinessRunReviewRunId = businessRunDetailOpen ? businessRunDetail?.runId || businessRunDetail?.id || '' : '';

  useEffect(() => {
    if (!activeBusinessRunReviewRunId) {
      setBusinessOutputReviews([]);
      setBusinessOutputReviewsError(null);
      return;
    }
    void loadBusinessOutputReviews(activeBusinessRunReviewRunId);
  }, [activeBusinessRunReviewRunId, loadBusinessOutputReviews]);

  const handleOpenBusinessRunDetail = useCallback((row: BusinessRun) => {
    const runId = row.runId || row.id;
    setBusinessWorkspaceTab('runs');
    setBusinessRunDetail(row);
    setBusinessRunDetailOpen(true);
    setBusinessOutputReviewFocus(null);
    setFocusedBusinessRunId(runId);
    setBusinessActionError(null);
    void adminApi
      .getBusinessRun(runId)
      .then((detail) => setBusinessRunDetail(detail))
      .catch((error) => {
        setBusinessActionError(error?.message || '加载业务运行详情失败，请刷新后重试。');
      });
  }, []);

  const handleOpenBusinessRunDetailById = useCallback((runId: string) => {
    const normalizedRunId = runId.trim();
    if (!normalizedRunId) return;
    setActiveNav('business');
    setBusinessWorkspaceTab('runs');
    setFocusedBusinessRunId(normalizedRunId);
    setBusinessOutputReviewFocus(null);
    setBusinessRunDetail(null);
    setBusinessRunDetailOpen(true);
    setBusinessActionError(null);
    contentRef.current?.scrollTo({ top: 0, behavior: 'smooth' });
  }, []);

  const handleOpenBusinessOutputReview = useCallback((review: BusinessOutputReview) => {
    const runId = String(review.runId || (review as any)?.run_id || '').trim();
    if (!runId) return;
    const outputIndex = Number(review.outputIndex ?? (review as any)?.output_index ?? 0);
    setActiveNav('business');
    setBusinessWorkspaceTab('runs');
    setFocusedBusinessRunId(runId);
    setBusinessOutputReviewFocus({ runId, outputIndex });
    setBusinessRunDetail(null);
    setBusinessRunDetailOpen(true);
    setBusinessActionError(null);
    contentRef.current?.scrollTo({ top: 0, behavior: 'smooth' });
  }, []);

  const handleCloseBusinessRunDetail = useCallback(() => {
    setBusinessRunDetailOpen(false);
    setBusinessOutputReviewFocus(null);
    setFocusedBusinessRunId('');
  }, []);

  useEffect(() => {
    const normalizedRunId = focusedBusinessRunId.trim();
    if (activeNav !== 'business' || !normalizedRunId) return;
    if (
      businessRunDetailOpen &&
      businessRunDetail &&
      (businessRunDetail.runId === normalizedRunId || businessRunDetail.id === normalizedRunId)
    ) {
      return;
    }
    setBusinessWorkspaceTab('runs');
    setBusinessRunDetail(null);
    setBusinessRunDetailOpen(true);
    setBusinessActionError(null);
    void adminApi
      .getBusinessRun(normalizedRunId)
      .then((detail) => {
        setBusinessRunDetail(detail);
        setBusinessRunFilters((prev) => ({
          ...prev,
          businessKey: canonicalBusinessKey(detail.businessKey || prev.businessKey),
          traceId: detail.traceId || prev.traceId,
        }));
      })
      .catch((error) => {
        setBusinessRunDetailOpen(false);
        setBusinessActionError(error?.message || '加载业务调用详情失败，请刷新后重试。');
      });
  }, [activeNav, businessRunDetail, businessRunDetailOpen, focusedBusinessRunId]);

  useEffect(() => {
    if (activeNav !== 'business' || !businessRunAutoRefresh || !pageVisible) return;
    const timer = window.setInterval(() => {
      void refreshBusinessRuns();
    }, 10000);
    return () => window.clearInterval(timer);
  }, [activeNav, businessRunAutoRefresh, pageVisible, refreshBusinessRuns]);

  const refreshAbilityTemplateState = useCallback(
    async (abilityId?: string | null, options?: { silent?: boolean }) => {
      const targetId = String(abilityId || '').trim();
      if (!targetId) {
        setAbilityTemplateState(null);
        setAbilityTemplateError(null);
        return;
      }
      const silent = Boolean(options?.silent);
      if (!silent) setAbilityTemplateLoading(true);
      setAbilityTemplateError(null);
      try {
        const state = await adminApi.getAbilityTemplateState(targetId);
        setAbilityTemplateState(state);
        setAbilityTemplateRollbackId((prev) => {
          if (prev && state.history.some((item) => item.id === prev)) return prev;
          return state.current_template_id || state.history[0]?.id || '';
        });
      } catch (error: any) {
        console.error('load ability template state failed', error);
        setAbilityTemplateError(error?.message || '获取能力模板状态失败');
      } finally {
        if (!silent) setAbilityTemplateLoading(false);
      }
    },
    [],
  );

  const handleAbilityTemplateValidate = useCallback(async () => {
    if (!selectedAbility?.id) return;
    setAbilityTemplateActionLoading(true);
    setAbilityTemplateError(null);
    try {
      const result = await adminApi.validateAbilityTemplate(selectedAbility.id);
      setAbilityTemplateValidateResult(result);
    } catch (error: any) {
      console.error('validate ability template failed', error);
      setAbilityTemplateError(error?.message || '模板校验失败');
    } finally {
      setAbilityTemplateActionLoading(false);
    }
  }, [selectedAbility]);

  const handleAbilityTemplatePublish = useCallback(async () => {
    if (!selectedAbility?.id) return;
    setAbilityTemplateActionLoading(true);
    setAbilityTemplateError(null);
    try {
      const state = await adminApi.publishAbilityTemplate(selectedAbility.id, {
        version_label: abilityTemplateVersionLabel.trim() || undefined,
        notes: abilityTemplateNotes.trim() || undefined,
      });
      setAbilityTemplateState(state);
      setAbilityTemplateValidateResult(null);
      setAbilityTemplateRollbackId(state.current_template_id || state.history[0]?.id || '');
    } catch (error: any) {
      console.error('publish ability template failed', error);
      setAbilityTemplateError(error?.message || '发布模板失败');
    } finally {
      setAbilityTemplateActionLoading(false);
    }
  }, [abilityTemplateNotes, abilityTemplateVersionLabel, selectedAbility]);

  const handleAbilityTemplateRollback = useCallback(async () => {
    if (!selectedAbility?.id) return;
    if (!abilityTemplateRollbackId.trim()) {
      setAbilityTemplateError('请选择要回滚的模板版本。');
      return;
    }
    setAbilityTemplateActionLoading(true);
    setAbilityTemplateError(null);
    try {
      const state = await adminApi.rollbackAbilityTemplate(selectedAbility.id, {
        templateId: abilityTemplateRollbackId.trim(),
        notes: abilityTemplateNotes.trim() || undefined,
      });
      setAbilityTemplateState(state);
      setAbilityTemplateValidateResult(null);
      setAbilityTemplateRollbackId(state.current_template_id || state.history[0]?.id || '');
    } catch (error: any) {
      console.error('rollback ability template failed', error);
      setAbilityTemplateError(error?.message || '模板回滚失败');
    } finally {
      setAbilityTemplateActionLoading(false);
    }
  }, [abilityTemplateNotes, abilityTemplateRollbackId, selectedAbility]);

  useEffect(() => {
    if (activeNav !== 'abilities' || activeAbilityDetailTab !== 'metadata') return;
    if (!selectedAbility?.id) return;
    refreshAbilityTemplateState(selectedAbility.id);
  }, [activeAbilityDetailTab, activeNav, refreshAbilityTemplateState, selectedAbility?.id]);

  const handleTestFile = async (files: FileList | null) => {
    if (!files || !files[0]) return;
    const file = files[0];
    setUploadingImage(true);
    setUploadError(null);
    try {
      const { uploadAbilityTestFile } = await import('../utils/ossUploader');
      const uploadResult = await uploadAbilityTestFile(file, {
        action: selectedAbility?.capability_key || 'ability-test',
        channel: 'admin-console',
        userId: 'admin',
      });
      setUploadedImage(uploadResult);
      setTestForm((prev) => ({
        ...prev,
        imageUrl: uploadResult.url,
      }));
      if (schemaHasImageField) {
        setSchemaValues((prev) => {
          const next = { ...prev };
          abilitySchemaFields.forEach((field) => {
            if (field.name === 'image_url') {
              next[field.name] = uploadResult.url;
            }
            if (field.name === 'image_urls' || field.name === 'input_urls') {
              next[field.name] = appendValueToListField(prev[field.name], uploadResult.url);
            }
          });
          return next;
        });
      }
      const reader = new FileReader();
      reader.onload = (event) => {
        const result = event.target?.result?.toString() || '';
        const [, base64Payload] = result.split(',');
        setTestForm((prev) => ({ ...prev, imageBase64: base64Payload || result }));
      };
      reader.readAsDataURL(file);
      setTestResult(null);
    } catch (error) {
      console.error('oss upload failed', error);
      setUploadError(error instanceof Error ? error.message : '上传 OSS 失败，请重试');
    } finally {
      setUploadingImage(false);
    }
  };

  const handleImageUrlInput = (value: string) => {
    setUploadedImage(null);
    setUploadError(null);
    setTestResult(null);
    setTestForm((prev) => ({
      ...prev,
    imageUrl: value,
    imageBase64: '',
  }));
  if (schemaHasImageField) {
    setSchemaValues((prev) => {
      const next = { ...prev };
      abilitySchemaFields.forEach((field) => {
        if (field.name === 'image_url') {
          next[field.name] = value;
        }
        if (field.name === 'image_urls' || field.name === 'input_urls') {
          next[field.name] = value;
        }
      });
      return next;
    });
  }
};

  const handleRunAbilityTest = async () => {
    if (!selectedAbility) return;
    if (!testForm.executorId) {
      alert('请先选择执行节点');
      return;
    }
    let paramsPayload: Record<string, unknown> = {};
    if (testForm.params) {
      try {
        paramsPayload = JSON.parse(testForm.params);
      } catch (error) {
        alert('参数 JSON 解析失败，请检查格式');
        return;
      }
    }
    const defaultParams = (selectedAbility.default_params || {}) as Record<string, unknown>;
    const mergedBaseParams: Record<string, unknown> = { ...defaultParams, ...paramsPayload };
    const schemaPayload: Record<string, unknown> = {};
    abilitySchemaFields.forEach((field) => {
      const rawValue = schemaValues[field.name];
      const value = convertSchemaValue(field, rawValue);
      if (value !== undefined) {
        schemaPayload[field.name] = value;
      }
    });
    const resolvedImageUrl =
      testForm.imageUrl ||
      (typeof schemaPayload.image_url === 'string' ? (schemaPayload.image_url as string) : undefined) ||
      (typeof mergedBaseParams.image_url === 'string' ? (mergedBaseParams.image_url as string) : undefined);
    if (abilityRequiresImageInput && !testForm.imageBase64 && !resolvedImageUrl) {
      alert('该能力需要图片输入，请先上传或填写 URL');
      return;
    }
    const abilityContextPayload = {
      abilityId: selectedAbility.id,
      abilityName: selectedAbility.display_name,
      abilityProvider: selectedAbility.provider,
      capabilityKey: selectedAbility.capability_key,
    };
    setTestLoading(true);
    setTestResult(null);
    try {
      if (selectedAbility.provider === 'baidu') {
        const schemaSplit = splitByKeys(schemaPayload, ['image_url']);
        const baseSplit = splitByKeys(mergedBaseParams, ['image_url']);
        const params = cleanParams({ ...baseSplit.rest, ...schemaSplit.rest });
        const response = await adminApi.testBaiduImageProcess({
          ...abilityContextPayload,
          executorId: testForm.executorId,
          imageBase64: testForm.imageBase64 || undefined,
          imageUrl: resolvedImageUrl,
          operation: selectedAbility.capability_key,
          params,
        });
        setTestResult({
          provider: response.provider || selectedAbility.provider,
          logId: response.logId ?? undefined,
          imageBase64: response.resultImage,
          raw: response.raw ?? null,
        });
        return;
      }
      if (selectedAbility.provider === 'volcengine') {
        const metadata = (selectedAbility.metadata || {}) as Record<string, unknown>;
        const apiType = resolveAbilityApiType(selectedAbility);
        if (apiType === 'chat_completions') {
          const knownKeys = ['prompt', 'image_url', 'model'];
          const schemaSplit = splitByKeys(schemaPayload, knownKeys);
          const baseSplit = splitByKeys(mergedBaseParams, knownKeys);
          const promptValue = (schemaSplit.picked.prompt || baseSplit.picked.prompt) as string | undefined;
          if (!promptValue) {
            alert('请填写提示词');
            return;
          }
          const modelValue = (schemaSplit.picked.model ||
            baseSplit.picked.model ||
            (typeof metadata.model_id === 'string' ? metadata.model_id : undefined)) as string | undefined;
          if (!modelValue) {
            alert('请在能力配置中设置默认模型或在表单中填写 model');
            return;
          }
          const extraParams = cleanParams({ ...baseSplit.rest, ...schemaSplit.rest });
          const response = await adminApi.testVolcengineChat({
            ...abilityContextPayload,
            executorId: testForm.executorId,
            model: modelValue,
            prompt: promptValue,
            imageUrl: resolvedImageUrl,
            params: Object.keys(extraParams).length > 0 ? extraParams : undefined,
          });
          setTestResult({
            provider: response.provider,
            model: response.model,
            text: response.text,
            logId: response.logId ?? undefined,
            raw: response.raw ?? null,
          });
          return;
        }
        if (apiType === 'image_generation') {
          const knownKeys = ['prompt', 'negative_prompt', 'model', 'size', 'response_format'];
          const schemaSplit = splitByKeys(schemaPayload, knownKeys);
          const baseSplit = splitByKeys(mergedBaseParams, knownKeys);
          const promptValue = (schemaSplit.picked.prompt || baseSplit.picked.prompt) as string | undefined;
          if (!promptValue) {
            alert('请填写提示词');
            return;
          }
          const modelValue = (schemaSplit.picked.model ||
            baseSplit.picked.model ||
            (typeof metadata.model_id === 'string' ? metadata.model_id : undefined)) as string | undefined;
          if (!modelValue) {
            alert('请在能力配置中设置默认模型或在表单中填写 model');
            return;
          }
          const extraParams = cleanParams({ ...baseSplit.rest, ...schemaSplit.rest });
          const response = await adminApi.testVolcengineImage({
            ...abilityContextPayload,
            executorId: testForm.executorId,
            model: modelValue,
            prompt: promptValue,
            negativePrompt: (schemaSplit.picked.negative_prompt || baseSplit.picked.negative_prompt) as string | undefined,
            size: (schemaSplit.picked.size || baseSplit.picked.size) as string | undefined,
            responseFormat: (schemaSplit.picked.response_format ||
              baseSplit.picked.response_format) as string | undefined,
            params: Object.keys(extraParams).length > 0 ? extraParams : undefined,
          });
        setTestResult({
          provider: response.provider,
          model: response.model,
          logId: response.logId ?? undefined,
          imageUrl: response.imageUrl,
          imageBase64: response.imageBase64,
          storedUrl: response.storedUrl || (response.assets && response.assets[0]?.ossUrl) || undefined,
          assets: response.assets || undefined,
          raw: response.raw ?? null,
        });
        return;
        }
        if (apiType === 'video_generation') {
          const knownKeys = [
            'prompt',
            'model',
            'image_url',
            'duration',
            'ratio',
            'resolution',
            'watermark',
            'generate_audio',
            'camera_fixed',
          ];
          const schemaSplit = splitByKeys(schemaPayload, knownKeys);
          const baseSplit = splitByKeys(mergedBaseParams, knownKeys);
          const promptValue = (schemaSplit.picked.prompt || baseSplit.picked.prompt) as string | undefined;
          if (!promptValue) {
            alert('请填写提示词');
            return;
          }
          const modelValue = (schemaSplit.picked.model ||
            baseSplit.picked.model ||
            (typeof metadata.model_id === 'string' ? metadata.model_id : undefined)) as string | undefined;
          if (!modelValue) {
            alert('请在能力配置中设置默认模型或在表单中填写 model');
            return;
          }
          const imageUrlValue = ((schemaSplit.picked.image_url || baseSplit.picked.image_url) as string | undefined) || resolvedImageUrl;
          const extraParams = cleanParams({
            ...baseSplit.rest,
            ...schemaSplit.rest,
            duration: schemaSplit.picked.duration || baseSplit.picked.duration,
            ratio: schemaSplit.picked.ratio || baseSplit.picked.ratio,
            resolution: schemaSplit.picked.resolution || baseSplit.picked.resolution,
            watermark: schemaSplit.picked.watermark ?? baseSplit.picked.watermark,
            generate_audio: schemaSplit.picked.generate_audio ?? baseSplit.picked.generate_audio,
            camera_fixed: schemaSplit.picked.camera_fixed ?? baseSplit.picked.camera_fixed,
          });
          const response = await adminApi.testVolcengineVideo({
            ...abilityContextPayload,
            executorId: testForm.executorId,
            model: modelValue,
            prompt: promptValue,
            imageUrl: imageUrlValue,
            params: Object.keys(extraParams).length > 0 ? extraParams : undefined,
          });
          setTestResult({
            provider: response.provider,
            model: response.model,
            logId: response.logId ?? undefined,
            taskId: response.taskId,
            state: response.state,
            resultUrls: response.resultUrls || [],
            assets: response.assets || undefined,
            raw: response.raw ?? null,
          });
          return;
        }
      }
      if (selectedAbility.provider === 'comfyui') {
        const metadata = (selectedAbility.metadata || {}) as Record<string, unknown>;
        const workflowKey =
          (typeof metadata.workflow_key === 'string' && metadata.workflow_key) || selectedAbility.capability_key;
        if (!workflowKey) {
          alert('该能力缺少 workflow_key，无法定位 ComfyUI 工作流');
          return;
        }
        const knownKeys = [
          'prompt',
          'patternType',
          'pattern_type',
          'width',
          'height',
          'resolution',
          'output_width',
          'output_height',
          'lora_name',
        ];
        const schemaSplit = splitByKeys(schemaPayload, knownKeys);
        const baseSplit = splitByKeys(mergedBaseParams, knownKeys);
        const workflowParams: JsonRecord = {
          ...(baseSplit.rest as JsonRecord),
          ...(schemaSplit.rest as JsonRecord),
        };
        const mergedPicked: Record<string, unknown> = { ...baseSplit.picked, ...schemaSplit.picked };
        const pickString = (key: string) => {
          const value = mergedPicked[key];
          if (value === undefined || value === null) return undefined;
          if (typeof value === 'string') {
            const trimmed = value.trim();
            return trimmed || undefined;
          }
          if (typeof value === 'number' || typeof value === 'boolean') return String(value);
          return undefined;
        };
        const pickNumber = (key: string) => {
          const value = mergedPicked[key];
          if (typeof value === 'number') return value;
          if (typeof value === 'string' && value.trim()) {
            const parsed = Number(value.trim());
            return Number.isFinite(parsed) ? parsed : undefined;
          }
          return undefined;
        };
        const promptValue = pickString('prompt');
        if (promptValue) workflowParams.prompt = promptValue;
        const patternValue = pickString('patternType') || pickString('pattern_type');
        if (patternValue) workflowParams.patternType = patternValue;
        const resolutionValue = pickString('resolution');
        if (resolutionValue) workflowParams.resolution = resolutionValue;
        const outputWidthValue = pickNumber('output_width') ?? pickNumber('width');
        if (outputWidthValue) {
          workflowParams.output_width = outputWidthValue;
          delete workflowParams.width;
        }
        const outputHeightValue = pickNumber('output_height') ?? pickNumber('height');
        if (outputHeightValue) {
          workflowParams.output_height = outputHeightValue;
          delete workflowParams.height;
        }
        const loraNameValue = pickString('lora_name');
        if (loraNameValue) workflowParams.lora_name = loraNameValue;
        if (resolvedImageUrl) workflowParams.imageUrl = resolvedImageUrl;
        if (testForm.imageBase64) workflowParams.imageBase64 = testForm.imageBase64;
        const imageListPayload: JsonRecord[] = [];
        if (resolvedImageUrl) {
          imageListPayload.push({ filename: 'ability-test.png', ossUrl: resolvedImageUrl });
        }
        if (testForm.imageBase64) {
          imageListPayload.push({ filename: 'ability-test.png', base64: testForm.imageBase64 });
        }
        if (imageListPayload.length > 0) {
          workflowParams.imageList = imageListPayload;
        }
        if (abilityRequiresImageInput && imageListPayload.length === 0) {
          alert('该能力需要图片输入，请先上传或填写 URL');
          return;
        }
        const response = await adminApi.testComfyuiWorkflow({
          ...abilityContextPayload,
          executorId: testForm.executorId,
          workflowKey,
          workflowParams,
          submitOnly: testForm.comfyuiSubmitOnly,
        });
        setTestResult({
          provider: response.provider,
          model: response.workflowKey,
          taskId: response.promptId,
          state: response.state || (testForm.comfyuiSubmitOnly ? 'submitted' : undefined),
          logId: response.logId ?? undefined,
          storedUrl: response.storedUrl ?? (response.assets && response.assets[0]?.ossUrl) ?? undefined,
          assets: response.assets ?? undefined,
          text: testForm.comfyuiSubmitOnly
            ? '已提交到 ComfyUI 队列（submit-only）。请到队列/日志查看进度或等待业务侧轮询回写。'
            : undefined,
          raw: response.raw ?? null,
        });
        return;
      }
      if (selectedAbility.provider === 'kie') {
        const metadata = (selectedAbility.metadata || {}) as Record<string, unknown>;
        const apiType = resolveAbilityApiType(selectedAbility);
        if (!apiType) {
          alert('该能力缺少 api_type，暂无法测试');
          return;
        }
        const knownKeys = [
          'prompt',
          'model',
          'image_urls',
          'imageUrls',
          'input_urls',
          'aspect_ratio',
          'aspectRatio',
          'resolution',
          'output_format',
          'callBackUrl',
          'generationType',
          'enableFallback',
          'enableTranslation',
          'watermark',
          'n_frames',
          'size',
          'remove_watermark',
          'character_ids',
        ];
        const schemaSplit = splitByKeys(schemaPayload, knownKeys);
        const baseSplit = splitByKeys(mergedBaseParams, knownKeys);
        const mergedPicked: Record<string, unknown> = { ...baseSplit.picked, ...schemaSplit.picked };
        const getPickedString = (key: string) => {
          const value = mergedPicked[key];
          if (value === undefined || value === null) return undefined;
          if (typeof value === 'string') {
            const trimmed = value.trim();
            return trimmed || undefined;
          }
          if (typeof value === 'number' || typeof value === 'boolean') return String(value);
          return undefined;
        };
        const getPickedBoolean = (key: string) => {
          const value = mergedPicked[key];
          if (typeof value === 'boolean') return value;
          if (typeof value === 'string') {
            const lowered = value.toLowerCase();
            if (['true', '1', 'yes'].includes(lowered)) return true;
            if (['false', '0', 'no'].includes(lowered)) return false;
          }
          return undefined;
        };
        const modelValue =
          getPickedString('model') || (typeof metadata.model_id === 'string' ? (metadata.model_id as string) : undefined);
        if (!modelValue) {
          alert('请在能力配置或表单中填写模型 ID');
          return;
        }
        const promptValue = getPickedString('prompt');
        if (!promptValue) {
          alert('请填写提示词');
          return;
        }
        const callBackUrlValue = getPickedString('callBackUrl');
        const inputPayload: JsonRecord = { prompt: promptValue };
        if (apiType === 'market_image_to_image') {
          const requiresImage = Boolean(metadata.requires_image_input);
          const mergedImageValue = mergedPicked.image_urls ?? mergedPicked.input_urls;
          let imageList = parseMultilineList(mergedImageValue);
          if (imageList.length === 0 && resolvedImageUrl) {
            imageList = [resolvedImageUrl];
          }
          if (requiresImage && imageList.length === 0) {
            alert('请提供至少一张参考图 URL');
            return;
          }
          if (imageList.length > 0) {
            const arrayTarget =
              typeof metadata.input_array_target === 'string'
                ? (metadata.input_array_target as string)
                : 'image_input';
            inputPayload[arrayTarget] = imageList;
          }
          const aspectRatio = getPickedString('aspect_ratio');
          if (aspectRatio) inputPayload.aspect_ratio = aspectRatio;
          const resolution = getPickedString('resolution');
          if (resolution) inputPayload.resolution = resolution;
          const outputFormat = getPickedString('output_format');
          if (outputFormat) inputPayload.output_format = outputFormat;
        } else if (apiType === 'market_text_to_video') {
          const mergedImageValue = mergedPicked.image_urls ?? mergedPicked.imageUrls ?? mergedPicked.input_urls;
          let imageList = parseMultilineList(mergedImageValue);
          if (imageList.length === 0 && resolvedImageUrl) {
            imageList = [resolvedImageUrl];
          }
          if (imageList.length > 0) {
            const arrayTarget =
              typeof metadata.input_array_target === 'string'
                ? (metadata.input_array_target as string)
                : 'image_input';
            inputPayload[arrayTarget] = imageList;
          }
          const isVeoKie =
            typeof metadata.status_endpoint === 'string' && (metadata.status_endpoint as string).includes('/veo/');
          const aspectRatio = getPickedString('aspectRatio') || getPickedString('aspect_ratio');
          if (aspectRatio) {
            if (isVeoKie) inputPayload.aspectRatio = aspectRatio;
            else inputPayload.aspect_ratio = aspectRatio;
          }
          const generationType = getPickedString('generationType');
          if (generationType) inputPayload.generationType = generationType;
          const enableFallback = getPickedBoolean('enableFallback');
          if (enableFallback !== undefined) inputPayload.enableFallback = enableFallback;
          const enableTranslation = getPickedBoolean('enableTranslation');
          if (enableTranslation !== undefined) inputPayload.enableTranslation = enableTranslation;
          const watermark = getPickedString('watermark');
          if (watermark) inputPayload.watermark = watermark;
          const nFrames = getPickedString('n_frames');
          if (nFrames) inputPayload.n_frames = nFrames;
          const sizeValue = getPickedString('size');
          if (sizeValue) inputPayload.size = sizeValue;
          const removeWatermark = getPickedBoolean('remove_watermark');
          if (removeWatermark !== undefined) inputPayload.remove_watermark = removeWatermark;
          const characterIds = parseMultilineList(mergedPicked.character_ids);
          if (characterIds.length > 0) inputPayload.character_id_list = characterIds;
        } else {
          alert('暂不支持该类型的 KIE 能力测试');
          return;
        }
        const extraParams = cleanParams({ ...baseSplit.rest, ...schemaSplit.rest });
        const response = await adminApi.testKieMarket({
          ...abilityContextPayload,
          executorId: testForm.executorId,
          model: modelValue,
          endpoint: typeof metadata.request_endpoint === 'string' ? (metadata.request_endpoint as string) : undefined,
          statusEndpoint:
            typeof metadata.status_endpoint === 'string' ? (metadata.status_endpoint as string) : undefined,
          inputArrayTarget:
            typeof metadata.input_array_target === 'string' ? (metadata.input_array_target as string) : undefined,
          resultFormat: typeof metadata.result_format === 'string' ? (metadata.result_format as string) : undefined,
          callBackUrl: callBackUrlValue,
          input: inputPayload,
          extra: Object.keys(extraParams).length > 0 ? extraParams : undefined,
        });
        setTestResult({
          provider: response.provider,
          model: response.model,
          logId: response.logId ?? undefined,
          taskId: response.taskId,
          state: response.state ?? undefined,
          storedUrl:
            response.storedAssets && response.storedAssets[0]?.ossUrl ? response.storedAssets[0]?.ossUrl : undefined,
          imageUrl: response.resultUrls && response.resultUrls.length > 0 ? response.resultUrls[0] : undefined,
          resultUrls: response.resultUrls || [],
          videoUrls: response.videoUrls || [],
          assets: response.storedAssets || undefined,
          raw: response.raw ?? null,
        });
        return;
      }
      alert('该厂商的能力测试尚未接入，请稍后再试。');
    } catch (error) {
      console.error('ability test failed', error);
      alert('测试失败，请检查日志或参数');
    } finally {
      setTestLoading(false);
      await refreshAbilityLogs();
    }
  };

const stringifyJSON = (value?: string | JsonRecord) => {
  if (!value) return '';
  if (typeof value === 'string') return value;
  return JSON.stringify(value, null, 2);
};
const extractErrorMessage = (error: unknown): string => {
  if (!error) return '';
  if (error instanceof Error && error.message) return error.message;
  if (typeof error === 'string') return error;
  try {
    return JSON.stringify(error);
  } catch {
    return String(error);
  }
};
  const handleExecutorSubmit = async () => {
    setExecutorFormError(null);
    const name = String(executorForm.name || '').trim();
    const type = String(executorForm.type || '').trim();
    const baseUrl = String(executorForm.base_url || '').trim();
    const status = String(executorForm.status || '').trim() || 'inactive';
    const weight = Number(executorForm.weight ?? 1) || 1;
    const maxConcurrency = Number(executorForm.max_concurrency ?? 1) || 1;

    if (!name) {
      setExecutorFormError('请填写节点名称');
      return;
    }
    if (!type) {
      setExecutorFormError('请填写节点类型（如：comfyui/kie/volcengine/baidu）');
      return;
    }
    if (executorConfigJsonInvalid) {
      setExecutorFormError(`配置内容无法解析：${executorConfigJsonInvalid}`);
      return;
    }
    if (baseUrl && !(baseUrl.startsWith('http://') || baseUrl.startsWith('https://'))) {
      setExecutorFormError('服务地址需以 http:// 或 https:// 开头');
      return;
    }

    const { config } = executorForm;
    const payload: Partial<Executor> = {
      id: executorForm.id,
      name,
      type,
      base_url: baseUrl || undefined,
      status,
      weight: Math.max(1, Math.min(999, weight)),
      max_concurrency: Math.max(1, Math.min(50, maxConcurrency)),
      ...(config ? { config: parseJSON(config) } : {}),
    };
    try {
      if (executorForm.id) {
        await adminApi.updateExecutor(executorForm.id, payload);
      } else {
        await adminApi.createExecutor(payload);
      }
      setExecutorForm(defaultExecutorForm);
      await load();
    } catch (err: any) {
      console.error(err);
      setExecutorFormError(err?.message || '保存失败');
    }
  };

  const saveExecutorConcurrency = useCallback(
    async (executorId: string) => {
      const executor = executors.find((ex) => ex.id === executorId);
      if (!executor) return;
      const draft = Number(executorInlineConcurrency[executorId] ?? executor.max_concurrency ?? 1) || 1;
      if (draft === executor.max_concurrency) return;
      setExecutorInlineSaving((prev) => ({ ...prev, [executorId]: true }));
      setExecutorInlineError((prev) => ({ ...prev, [executorId]: '' }));
      try {
        await adminApi.updateExecutor(executorId, { max_concurrency: Math.max(1, Math.min(50, draft)) });
        // Update local list to reflect immediately (avoid waiting for full reload).
        setExecutors((prev) => prev.map((ex) => (ex.id === executorId ? { ...ex, max_concurrency: draft } : ex)));
      } catch (err: any) {
        console.error(err);
        setExecutorInlineError((prev) => ({ ...prev, [executorId]: err?.message || '更新失败' }));
      } finally {
        setExecutorInlineSaving((prev) => ({ ...prev, [executorId]: false }));
      }
    },
    [executors, executorInlineConcurrency],
  );

  const handleBindingSubmit = async () => {
    if (!bindingForm.action || !bindingForm.workflow_id || !bindingForm.executor_id) return;
    const payload: Partial<Binding> = { ...bindingForm };
    if (bindingForm.id) {
      await adminApi.updateBinding(bindingForm.id, payload);
    } else {
      await adminApi.createBinding(payload);
    }
    setBindingForm(defaultBindingForm);
    load();
  };

  const handleApiKeySubmit = async () => {
    if (!apiKeyForm.provider || !apiKeyForm.name || !apiKeyForm.status) return;
    const { key: _plainKey, key_preview: _preview, ...safePayload } = apiKeyForm;
    if (apiKeyForm.id) {
      await adminApi.updateApiKey(apiKeyForm.id, {
        ...safePayload,
        ...(apiKeyForm.key ? { key: apiKeyForm.key } : {}),
      });
    } else if (apiKeyForm.key) {
      await adminApi.createApiKey(apiKeyForm);
    } else {
      return;
    }
    setApiKeyForm(defaultApiKeyForm);
    load();
  };

  const {
    handleSyncVolcengineModels,
    handleVendorEgressCheck,
    handleVendorKeyCheck,
    handleVendorKeySubmit,
    handleVendorModelBulkAction,
    handleVendorModelAcceptance,
    handleVendorModelSubmit,
    loadVendorCatalog,
    resetVendorModelForm,
  } = useVendorModelActions({
    extractErrorMessage,
    setVendorBaseUrl,
    setVendorEgressChecks,
    setVendorError,
    setVendorGovernanceSummary,
    setVendorKeyForm,
    setVendorKeys,
    setVendorLoading,
    setVendorModelForm,
    setVendorModelFormError,
    setVendorModels,
    setVendorNotice,
    setVendorProviders,
    setVendorUsageItems,
    setVendorUsageWindowHours,
    vendorKeyForm,
    vendorModelForm,
  });

  const handleDelete = async (type: 'executor' | 'workflow' | 'binding' | 'apikey', id: string) => {
    const map = {
      executor: adminApi.deleteExecutor,
      workflow: adminApi.deleteWorkflow,
      binding: adminApi.deleteBinding,
      apikey: adminApi.deleteApiKey,
    };
    await map[type](id);
    load();
  };

  const CUSTOM_SELECT_VALUE = '__custom__';

  const renderSchemaField = (field: AbilitySchemaField) => {
    const rawValue = schemaValues[field.name];
    const label = `${field.label}${field.required ? ' *' : ''}`;
    const description = field.description;
    const placeholder = field.placeholder;

    const heading = (
      <Space direction="vertical" size={2}>
        <Typography.Text>{label}</Typography.Text>
        {description ? <Typography.Text theme="secondary">{description}</Typography.Text> : null}
      </Space>
    );

    if (field.type === 'switch') {
      return (
        <Card key={field.name} bordered>
          <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
            {heading}
            <Switch
              value={Boolean(rawValue)}
              onChange={(v) => setSchemaValues((prev) => ({ ...prev, [field.name]: Boolean(v) }))}
            />
          </Space>
        </Card>
      );
    }

    if (field.type === 'textarea') {
      const value = typeof rawValue === 'string' ? rawValue : rawValue ? String(rawValue) : '';
      return (
        <div key={field.name}>
          {heading}
          <div style={{ marginTop: 8 }}>
            <Textarea
              value={value}
              onChange={(v) => setSchemaValues((prev) => ({ ...prev, [field.name]: String(v) }))}
              autosize={{ minRows: 3, maxRows: 8 }}
              placeholder={placeholder}
            />
          </div>
        </div>
      );
    }

    if (field.type === 'select' && field.options && field.options.length > 0) {
      const value = typeof rawValue === 'string' ? rawValue : rawValue ? String(rawValue) : '';
      const optionValues = field.options.map((option) => option.value);
      const allowCustom = Boolean(field.allowCustomValue);
      const isCustomValue = allowCustom && Boolean(value) && !optionValues.includes(value);
      const selectValue = isCustomValue ? CUSTOM_SELECT_VALUE : value;
      return (
        <div key={field.name}>
          {heading}
          <div style={{ marginTop: 8 }}>
            <Select
              value={selectValue}
              onChange={(v) => {
                const selected = String(v);
                if (allowCustom && selected === CUSTOM_SELECT_VALUE) {
                  setSchemaValues((prev) => ({ ...prev, [field.name]: isCustomValue ? value : '' }));
                  return;
                }
                setSchemaValues((prev) => ({ ...prev, [field.name]: selected }));
              }}
              options={[
                { label: '请选择', value: '' },
                ...field.options.map((opt) => ({ label: opt.label, value: opt.value })),
                ...(allowCustom
                  ? [{ label: `自定义 ${field.label.replace(/[*\\s]/g, '') || '选项'}`, value: CUSTOM_SELECT_VALUE }]
                  : []),
              ]}
              placeholder="请选择"
            />
            {allowCustom && (isCustomValue || selectValue === CUSTOM_SELECT_VALUE) ? (
              <div style={{ marginTop: 8 }}>
                <Input
                  value={value}
                  placeholder="输入自定义值，例如其他 LoRA 文件"
                  onChange={(v) => setSchemaValues((prev) => ({ ...prev, [field.name]: String(v) }))}
                />
              </div>
            ) : null}
          </div>
        </div>
      );
    }

    const value = typeof rawValue === 'string' ? rawValue : rawValue ? String(rawValue) : '';
    if (field.type === 'number') {
      const numberValue = value === '' ? undefined : Number(value);
      return (
        <div key={field.name}>
          {heading}
          <div style={{ marginTop: 8 }}>
            <InputNumber
              value={Number.isNaN(numberValue as any) ? undefined : (numberValue as any)}
              onChange={(v) => setSchemaValues((prev) => ({ ...prev, [field.name]: v as any }))}
              placeholder={placeholder}
            />
          </div>
        </div>
      );
    }

    return (
      <div key={field.name}>
        {heading}
        <div style={{ marginTop: 8 }}>
          <Input
            value={value}
            placeholder={placeholder}
            onChange={(v) => setSchemaValues((prev) => ({ ...prev, [field.name]: String(v) }))}
          />
        </div>
      </div>
    );
  };

  const renderAbilityOverview = () => (
    <AbilityOverviewTab
      selectedAbility={selectedAbility}
      schemaIssues={selectedAbilitySchemaIssues}
      tags={selectedAbilityTags}
      defaultExecutorLabel={
        pinnedAbilityExecutor ? `${pinnedAbilityExecutor.name} · ${pinnedAbilityExecutor.type}` : '按厂商类型自动匹配'
      }
      workflowLabel={selectedAbilityWorkflowLabel || '未绑定'}
      pricingText={selectedAbilityPricingText}
      health={selectedAbilityHealth}
      getProviderLabel={getProviderLabel}
      getCategoryLabel={getCategoryLabel}
      getAbilityTypeLabel={getAbilityTypeLabel}
    />
  );

  const renderAbilityParamsTab = () => (
    <AbilityParamsTab selectedAbility={selectedAbility} schemaIssues={selectedAbilitySchemaIssues} />
  );

  const renderAbilityMetadataTab = () => (
    <AbilityMetadataTab
      selectedAbility={selectedAbility}
      schemaIssues={selectedAbilitySchemaIssues}
      workflowLabel={selectedAbilityWorkflowLabel || '未绑定'}
      pricingText={selectedAbilityPricingText}
      health={selectedAbilityHealth}
      templateState={abilityTemplateState}
      templateLoading={abilityTemplateLoading}
      templateActionLoading={abilityTemplateActionLoading}
      templateVersionLabel={abilityTemplateVersionLabel}
      templateRollbackId={abilityTemplateRollbackId}
      templateNotes={abilityTemplateNotes}
      templateError={abilityTemplateError}
      templateValidateResult={abilityTemplateValidateResult}
      onRefreshTemplate={refreshAbilityTemplateState}
      onValidateTemplate={handleAbilityTemplateValidate}
      onPublishTemplate={handleAbilityTemplatePublish}
      onRollbackTemplate={handleAbilityTemplateRollback}
      onTemplateVersionLabelChange={setAbilityTemplateVersionLabel}
      onTemplateRollbackIdChange={setAbilityTemplateRollbackId}
      onTemplateNotesChange={setAbilityTemplateNotes}
      getAbilityTypeLabel={getAbilityTypeLabel}
    />
  );

  const renderAbilityTestingTab = () => (
    <AbilityTestingTab
      selectedAbility={selectedAbility}
      abilityExecutors={abilityExecutors}
      testForm={testForm}
      testResult={testResult}
      testLoading={testLoading}
      abilityAllowsImageInput={abilityAllowsImageInput}
      abilityRequiresImageInput={abilityRequiresImageInput}
      uploadingImage={uploadingImage}
      uploadedImage={uploadedImage}
      uploadError={uploadError}
      renderedSchemaFieldCount={renderedSchemaFields.length}
      schemaFieldNodes={renderedSchemaFields.map((field) => renderSchemaField(field))}
      activeComfyExecutorId={activeComfyExecutorId}
      comfyQueueStatus={comfyQueueStatus}
      comfyQueueLoading={comfyQueueLoading}
      comfyQueueError={comfyQueueError}
      comfyQueueUpdatedAt={comfyQueueUpdatedAt}
      comfyModelLoading={comfyModelLoading}
      comfyModelError={comfyModelError}
      hasComfyModelCache={Boolean(activeComfyExecutorId && comfyModelCache[activeComfyExecutorId])}
      testResultPreviewSrc={testResultPreviewSrc}
      onExecutorChange={(executorId) => setTestForm((prev) => ({ ...prev, executorId }))}
      onImageUrlChange={handleImageUrlInput}
      onFileChange={handleTestFile}
      onParamsChange={(params) => setTestForm((prev) => ({ ...prev, params }))}
      onComfySubmitOnlyChange={(comfyuiSubmitOnly) => setTestForm((prev) => ({ ...prev, comfyuiSubmitOnly }))}
      onRefreshComfyQueue={refreshComfyQueueStatus}
      onRun={handleRunAbilityTest}
      getProviderLabel={getProviderLabel}
    />
  );

  const renderAbilityDetailContent = (tab: AbilityDetailTab) => {
    switch (tab) {
      case 'overview':
        return renderAbilityOverview();
      case 'params':
        return renderAbilityParamsTab();
      case 'metadata':
        return renderAbilityMetadataTab();
      case 'testing':
        return renderAbilityTestingTab();
      case 'logs':
        return renderAbilityLogsTab();
      default:
        return null;
    }
  };

  const renderAbilityLogsTab = () => (
    <AbilityRecentLogsPanel
      selectedAbility={selectedAbility}
      logs={abilityLogs}
      total={abilityLogTotal}
      loading={abilityLogsLoading}
      error={abilityLogsError}
      autoRefresh={abilityLogsAutoRefresh}
      updatedAt={abilityLogsUpdatedAt}
      page={abilityLogPage}
      pageSize={abilityLogPageSize}
      onAutoRefreshChange={setAbilityLogsAutoRefresh}
      onRefresh={refreshAbilityLogs}
      onPageChange={setAbilityLogPage}
      onOpenDetail={openAbilityLogDetail}
    />
  );

  const renderAbilityWorkbenchCard = () => (
    <AbilityWorkbenchPanel
      abilities={abilities}
      selectedAbility={selectedAbility}
      selectedAbilityId={selectedAbilityId}
      activeTab={activeAbilityDetailTab}
      tabs={abilityDetailTabs}
      onSelectAbility={setSelectedAbilityId}
      onSelectAbilitiesSection={() => selectSection('abilities')}
      onTabChange={(tab) => setActiveAbilityDetailTab(tab as AbilityDetailTab)}
      renderContent={(tab) => renderAbilityDetailContent(tab as AbilityDetailTab)}
      getProviderLabel={getProviderLabel}
    />
  );

  const selectSection = (id: NavId) => {
    if (isAdvancedNav(id)) {
      setShowAdvanced(true);
    }
    setActiveNav(id);
    if (id !== 'ability-evals') {
      setFocusedEvalRunId('');
    }
    if (id !== 'business') {
      setFocusedBusinessRunId('');
    }
    // Only the right content pane scrolls. Switching sections resets scroll.
    contentRef.current?.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const visibleNavItems = useMemo(() => {
    const baseItems = navItems.filter((item) => !(item as any).advanced || showAdvanced);
    if (!isBusinessReadOnly) return baseItems;
    return baseItems.filter((item) => readOnlyNavIds.has(item.id as NavId));
  }, [isBusinessReadOnly, showAdvanced]);
  const activeNavMeta = useMemo(
    () => visibleNavItems.find((item) => item.id === activeNav) || navItems.find((item) => item.id === activeNav),
    [activeNav, visibleNavItems],
  );
  const activeModuleGuide = moduleGuides[activeNav];
  const coreBusinessOverviewItems = useMemo(
    () =>
      coreBusinessKeys
        .map(
          (key) =>
            businessCapabilities.find((item) => item.businessKey === key && item.isDefault) ||
            businessCapabilities.find((item) => item.businessKey === key),
        )
        .filter((item): item is BusinessCapability => Boolean(item)),
    [businessCapabilities],
  );
  const activeComfyTabMeta = comfyuiTabMeta[comfyuiManageTab];
  const comfyuiGroupMap = useMemo(() => createComfyuiGroupMap(), []);
  const activeComfyGroupTabs = comfyuiGroupMap[activeComfyTabMeta.group];
  const navSelectOptions = useMemo(
    () =>
      visibleNavItems.map((item) => ({
        label: `${item.groupLabel || '模块'} / ${item.label}${Boolean((item as any).advanced) ? '（高级）' : ''}`,
        value: item.id,
      })),
    [visibleNavItems],
  );
  const activeNavIndex = visibleNavItems.findIndex((item) => item.id === activeNav);
  const hasCompactNavSelect = activeNavIndex >= 0;

  useEffect(() => {
    const syncFromHash = () => {
      const params = readHashParams();
      const rawNav = params?.get('nav') || '';
      if (rawNav === 'ability-tests') {
        setActiveNav('abilities');
        setFocusedEvalRunId('');
        setFocusedBusinessRunId('');
        setActiveAbilityDetailTab('testing');
        return;
      }

      const navFromHash = readNavFromHash();
      if (!navFromHash) return;
      if (isBusinessReadOnly && !readOnlyNavIds.has(navFromHash)) {
        setActiveNav('business');
        setFocusedEvalRunId('');
        setFocusedBusinessRunId(readBusinessRunIdFromHash());
        return;
      }
      if (!showAdvanced && isAdvancedNav(navFromHash)) {
        setShowAdvanced(true);
      }
      setActiveNav(navFromHash);
      setFocusedEvalRunId(navFromHash === 'ability-evals' ? readEvalRunIdFromHash() : '');
      setFocusedBusinessRunId(navFromHash === 'business' ? readBusinessRunIdFromHash() : '');
      if (navFromHash === 'business') {
        setBusinessWorkspaceTab(readBusinessWorkspaceTabFromParams(params) ?? 'runs');
      }
      if (navFromHash === 'comfyui-management') {
        const comfyTabFromHash = readComfyuiTabFromHash();
        if (comfyTabFromHash) setComfyuiManageTab(comfyTabFromHash);
      }
    };

    syncFromHash();
    window.addEventListener('hashchange', syncFromHash);
    return () => window.removeEventListener('hashchange', syncFromHash);
  }, [isBusinessReadOnly, showAdvanced]);

  useEffect(() => {
    if (!isBusinessReadOnly) return;
    if (readOnlyNavIds.has(activeNav)) return;
    selectSection('business');
  }, [activeNav, isBusinessReadOnly]);

  useEffect(() => {
    const params = new URLSearchParams();
    params.set('nav', activeNav);
    if (activeNav === 'comfyui-management') {
      params.set('comfyTab', comfyuiManageTab);
    }
    if (activeNav === 'ability-evals' && focusedEvalRunId) {
      params.set('runId', focusedEvalRunId);
    }
    if (activeNav === 'business' && focusedBusinessRunId) {
      params.set('businessRunId', focusedBusinessRunId);
    }
    if (activeNav === 'business') {
      params.set('businessTab', businessWorkspaceTab);
    }
    const nextHash = params.toString();
    const currentHash = window.location.hash.replace(/^#/, '');
    if (currentHash === nextHash) return;
    window.history.replaceState(null, '', `${window.location.pathname}${window.location.search}#${nextHash}`);
  }, [activeNav, businessWorkspaceTab, comfyuiManageTab, focusedBusinessRunId, focusedEvalRunId]);

  return (
    <AdminShell
      title="AI 管理端"
      subtitle="集中管理业务能力、模型、运行线路、密钥与调度测试。"
      theme={theme}
      navItems={visibleNavItems.map((item) => ({ ...item, icon: navIconMap[item.id as NavId] }))}
      activeNav={activeNav}
      onSelectNav={(value) => selectSection(value as NavId)}
      headerTitle={activeNavMeta?.label || '控制台'}
      headerSubtitle={activeNavMeta?.description || '按模块管理能力、任务、运行线路与稳定性。'}
      contentRef={contentRef}
      headerActions={
        <Space align="center" size="small" style={{ flexWrap: 'wrap', justifyContent: 'flex-end', width: '100%' }}>
          <Button variant="outline" loading={loading} onClick={load}>
            刷新
          </Button>
          <Button variant="outline" onClick={onToggleTheme}>
            {theme === 'dark' ? '深色模式' : '浅色模式'}
          </Button>
        </Space>
      }
    >
      <div className="podi-admin-dashboard">
      {loadErrors.length > 0 ? (
        <div style={{ marginBottom: 12 }}>
          <Alert
            theme="warning"
            message={
              <Space direction="vertical" size={6} style={{ width: '100%' }}>
                <div>
                  部分后台数据暂时没加载完整，当前页面已加载内容可以继续使用；连续重试失败时再进入对应模块排查。
                </div>
                <details>
                  <summary style={{ cursor: 'pointer' }}>查看未加载模块</summary>
                  <ul style={{ margin: '8px 0 0', paddingLeft: 18 }}>
                    {loadErrors.slice(0, 6).map((msg) => (
                      <li key={msg}>{msg}</li>
                    ))}
                  </ul>
                </details>
              </Space>
            }
            operation={
              <Button size="small" variant="outline" onClick={load}>
                重试
              </Button>
            }
          />
        </div>
      ) : null}
      {isBusinessReadOnly ? (
        <Alert
          theme="warning"
          message={`当前账号是业务方只读视图，只能查看 ${
            currentUser?.tenantId || '当前业务方'
          }${currentUser?.clientId ? ` / ${currentUser.clientId}` : ''} 范围内的业务任务和统计；配置、发布、密钥、执行资源、账号权限等后台能力已隐藏。`}
          style={{ marginBottom: 16 }}
        />
      ) : null}
      <div style={{ marginBottom: 16 }}>
        <ActionBar>
          <Space direction="vertical" size={8} style={{ minWidth: 0 }}>
            <Space align="center" size="small" style={{ flexWrap: 'wrap' }}>
              <Typography.Text strong>{activeNavMeta?.label || '当前模块'}</Typography.Text>
              {activeModuleGuide ? <Tag variant="light">{activeModuleGuide.audience}</Tag> : null}
              {activeModuleGuide?.riskHint ? (
                <Tag theme="warning" variant="light">
                  {activeModuleGuide.riskHint}
                </Tag>
              ) : null}
            </Space>
            <Space direction="vertical" size={2}>
              <Typography.Text theme="secondary">
                {activeModuleGuide?.firstLook || activeNavMeta?.description || '先确认当前模块状态，再执行操作。'}
              </Typography.Text>
              {activeModuleGuide?.nextAction ? (
                <Typography.Text theme="secondary">下一步：{activeModuleGuide.nextAction}</Typography.Text>
              ) : null}
            </Space>
            <Space size="small" style={{ flexWrap: 'wrap' }}>
              <Select
                style={{ width: 220 }}
                size="small"
                value={activeNav}
                options={navSelectOptions}
                onChange={(value) => selectSection(String(value) as NavId)}
              />
              <Space align="center" size="small">
                <Typography.Text theme="secondary">高级模块</Typography.Text>
                <Switch
                  value={showAdvanced}
                  onChange={(v) => {
                    const next = Boolean(v);
                    setShowAdvanced(next);
                    if (!next) {
                      const isAdvanced = Boolean((navItems.find((item) => item.id === activeNav) as any)?.advanced);
                      if (isAdvanced) selectSection('overview');
                    }
                  }}
                />
                <Tag theme={showAdvanced ? 'primary' : 'default'} variant="light">
                  {showAdvanced ? '全部视图' : '核心视图'}
                </Tag>
              </Space>
            </Space>
            {hasCompactNavSelect ? null : <Typography.Text theme="secondary">当前模块未在核心导航中展示，请检查高级模块开关。</Typography.Text>}
          </Space>
          <Space align="center" size="small" style={{ flexWrap: 'wrap' }}>
            <Tag variant="light" theme={coreBusinessOverviewItems.length >= coreBusinessKeys.length ? 'success' : 'warning'}>
              核心能力 {coreBusinessOverviewItems.length}/{coreBusinessKeys.length}
            </Tag>
            <Tag variant="light" theme={Number(abilityHealthSummary?.failed || 0) > 0 ? 'danger' : 'success'}>
              能力异常 {abilityHealthSummary?.failed || 0}
            </Tag>
            <Tag variant="light" theme={vendorGovernanceIssueCount > 0 ? 'warning' : 'success'}>
              模型风险 {vendorGovernanceIssueCount}
            </Tag>
            <Tag variant="light" theme={healthWatchIssueCount > 0 ? 'danger' : healthWatchStatus ? 'success' : 'warning'}>
              {healthWatchHeaderText}
            </Tag>
            <Tag variant="light">运行线路 {summary.activeExecutors}/{summary.executors}</Tag>
            <Tag variant="light" theme={loadErrors.length > 0 ? 'danger' : 'success'}>
              {loadErrors.length > 0 ? `异常 ${loadErrors.length}` : '状态正常'}
            </Tag>
            <Tag variant="light" theme={isBusinessReadOnly ? 'warning' : 'success'}>
              {isBusinessReadOnly ? '业务方只读' : '管理员'}
            </Tag>
          </Space>
        </ActionBar>
      </div>
          {activeNav === 'overview' && (
            <Section id="overview" title="总体概览" description="观察运行快照、调度指标与刷新入口。">
              <OverviewPanel
                dashboardMetrics={dashboardMetrics}
                pendingQueueTotal={pendingQueueTotal}
                businessUsageSummary={businessUsageSummary}
                coreBusinessOverviewItems={coreBusinessOverviewItems}
                abilityHealthSummary={abilityHealthSummary}
                vendorModelCount={vendorModels.length}
                vendorKeyCount={vendorKeys.length}
                vendorUsageFailed={vendorUsageFailed}
                vendorGovernanceIssueCount={vendorGovernanceIssueCount}
                strategySnapshots={strategySnapshots}
                strategySnapshotLoading={strategySnapshotLoading}
                strategySnapshotError={strategySnapshotError}
                weeklyReports={weeklyReports}
                weeklyReportLoading={weeklyReportLoading}
                weeklyReportError={weeklyReportError}
                releasePreflightLatest={releasePreflightLatest}
                releasePreflightSnapshots={releasePreflightSnapshots}
                releasePreflightLoading={releasePreflightLoading}
                releasePreflightError={releasePreflightError}
                healthWatchStatus={healthWatchStatus}
                healthWatchLoading={healthWatchLoading}
                healthWatchError={healthWatchError}
                releasePatrolRecords={releasePatrolRecords}
                releasePatrolLoading={releasePatrolLoading}
                releasePatrolError={releasePatrolError}
                releaseDecisionRecords={releaseDecisionRecords}
                releaseDecisionLoading={releaseDecisionLoading}
                releaseDecisionError={releaseDecisionError}
                summary={summary}
                loading={loading}
                onRefresh={load}
                onCreateStrategySnapshot={createStrategySnapshot}
                onRefreshStrategySnapshots={refreshStrategySnapshots}
                onRunWeeklyReport={runWeeklyReport}
                onRefreshWeeklyReports={refreshWeeklyReports}
                onRunReleasePreflight={runReleasePreflight}
                onRefreshReleasePreflight={refreshReleasePreflightSnapshots}
                onRefreshHealthWatchStatus={refreshHealthWatchStatus}
                onCreateReleasePatrolRecord={createReleasePatrolRecord}
                onImportReleasePatrolReport={importReleasePatrolReport}
                onRefreshReleasePatrolRecords={refreshReleasePatrolRecords}
                onCreateReleaseDecisionRecord={createReleaseDecisionRecord}
                onRefreshReleaseDecisionRecords={refreshReleaseDecisionRecords}
                onCopyText={copyTextToClipboard}
                onOpenEvalRun={(runId) => {
                  setFocusedEvalRunId(runId);
                  selectSection('ability-evals');
                  copyTextToClipboard(runId);
                }}
                onNavigate={(target) => selectSection(target)}
              />
            </Section>
          )}

          {activeNav === 'business' && (
            <Section id="business" title="业务能力" description="按业务入口管理版本、真实调用和每一步处理结果。">
              <Suspense
                fallback={
                  <div className="rounded-3xl border border-slate-200 bg-white px-6 py-5 text-sm text-slate-600 shadow-sm">
                    业务能力加载中，请稍候...
                  </div>
                }
              >
                <Space direction="vertical" size="large" style={{ width: '100%' }}>
                {isBusinessReadOnly ? (
                  <Alert
                    theme="warning"
                    message={`当前为业务方只读视图，只展示 ${
                      currentUser?.tenantId || '当前业务方'
                    }${currentUser?.clientId ? ` / ${currentUser.clientId}` : ''} 范围内的任务和统计；版本发布、默认切换和停用请联系管理员处理。`}
                  />
                ) : null}
                {businessActionError ? <Alert theme="error" message={businessActionError} /> : null}
                <Card bordered>
                  <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                    <Space align="center" style={{ justifyContent: 'space-between', width: '100%', flexWrap: 'wrap' }}>
                      <div>
                          <Typography.Text strong>业务工作台</Typography.Text>
                          <div>
                            <Typography.Text theme="secondary">
                            默认先看能力治理；调用、链路、版本和变更记录按需下钻。
                          </Typography.Text>
                        </div>
                      </div>
                      {!isBusinessReadOnly ? (
                        <Button
                          theme="primary"
                          onClick={() => {
                            resetBusinessForm();
                            setBusinessDialogOpen(true);
                          }}
                        >
                          新增业务版本
                        </Button>
                      ) : null}
                    </Space>
                    <Tabs
                      value={businessWorkspaceTab}
                      onChange={(value) => setBusinessWorkspaceTab(value as BusinessWorkspaceTab)}
                      list={businessWorkspaceTabs}
                    />
                    <Typography.Text theme="secondary">
                      {businessWorkspaceTab === 'governance'
                        ? '这里先按能力判断默认版本、质量、调用、成本、回滚和下一步动作。'
                        : businessWorkspaceTab === 'runs'
                          ? '排查业务是否跑通时，只看这里的一条 runId。VL、生成、评分、回填、回调都是这条调用下面的处理步骤。'
                          : businessWorkspaceTab === 'map'
                            ? '这里看每个业务入口当前用哪个版本、由哪些组件组成、最近是否跑通过。'
                            : businessWorkspaceTab === 'versions'
                              ? '这里管理业务版本、默认入口、草稿试运行和验收记录。'
                              : '这里处理发布门禁、默认切换、回滚、复测和操作记录。'}
                    </Typography.Text>
                  </Space>
                </Card>
                {businessWorkspaceTab === 'governance' ? (
                  <BusinessAbilityGovernancePanel
                    capabilities={businessCapabilities}
                    pendingApprovals={businessDefaultApprovals}
                    summary={businessUsageSummary}
                    qualitySummary={businessOutputReviewSummary}
                    formatDateTime={formatDateTime}
                    capabilitiesLoading={loading && businessCapabilities.length === 0}
                  />
                ) : null}
                {businessWorkspaceTab === 'runs' ? (
                  <>
                    <BusinessEntryCommandPanel
                      capabilities={businessCapabilities}
                      pendingApprovals={businessDefaultApprovals}
                      summary={businessUsageSummary}
                      formatDateTime={formatDateTime}
                    />
                    <BusinessFlowMonitoringPanel summary={businessUsageSummary} />
                    <BusinessQualityReviewPanel
                      summary={businessUsageSummary}
                      runs={businessRuns}
                      qualitySummary={businessOutputReviewSummary}
                      onOpenReview={handleOpenBusinessOutputReview}
                    />
                    <BusinessRunHistoryPanel
                      runs={businessRuns}
                      total={businessRunTotal}
                      filters={businessRunFilters}
                      businessOptions={businessRunBusinessOptions}
                      versionOptions={businessRunVersionOptions}
                      isReadOnly={isBusinessReadOnly}
                      tenantId={currentUser?.tenantId}
                      clientId={currentUser?.clientId}
                      actionLoadingId={businessActionLoadingId}
                      detail={businessRunDetail}
                      detailOpen={businessRunDetailOpen}
                      outputReviews={businessOutputReviews}
                      outputReviewsLoading={businessOutputReviewsLoading}
                      outputReviewsError={businessOutputReviewsError}
                      outputReviewFocus={businessOutputReviewFocus}
                      autoRefresh={businessRunAutoRefresh}
                      onFiltersChange={setBusinessRunFilters}
                      onAutoRefreshChange={setBusinessRunAutoRefresh}
                      onRefresh={refreshBusinessRuns}
                      onExport={exportBusinessRuns}
                      onBulkCallbackRetry={handleBusinessBulkCallbackRetry}
                      onBulkRetest={handleBusinessBulkRetest}
                      onBulkIgnoreIssues={handleBusinessBulkIgnoreIssues}
                      onGenerateIssueChecklist={handleBusinessGenerateIssueChecklist}
                      onOpenDetail={handleOpenBusinessRunDetail}
                      onCloseDetail={handleCloseBusinessRunDetail}
                      onCallbackRetry={handleBusinessCallbackRetry}
                      onRefreshOutputReviews={loadBusinessOutputReviews}
                      onSaveOutputReview={handleBusinessOutputReviewSave}
                      formatDateTime={formatDateTime}
                    />
                    <BusinessUsageSummaryPanel
                      summary={businessUsageSummary}
                      windowHours={businessRunFilters.windowHours}
                      formatDateTime={formatDateTime}
                    />
                  </>
                ) : null}
                {businessWorkspaceTab === 'map' ? (
                  <>
                    <BusinessOrchestrationMapPanel
                      capabilities={businessCapabilities}
                      pendingApprovals={businessDefaultApprovals}
                      summary={businessUsageSummary}
                      formatDateTime={formatDateTime}
                      capabilitiesLoading={loading && businessCapabilities.length === 0}
                      isReadOnly={isBusinessReadOnly}
                      actionLoadingId={businessActionLoadingId}
                      abilityOptions={businessAbilityOptions}
                      vlAbilityOptions={businessVlAbilityOptions}
                      onCreateDraft={handleBusinessCreateDraft}
                      onSaveDraftRecipe={handleBusinessDraftRecipeUpdate}
                      onOpenBusinessRun={handleOpenBusinessRunDetailById}
                    />
                  </>
                ) : null}
                {businessWorkspaceTab === 'versions' ? (
                  <>
                    <BusinessQualityCandidatePanel
                      capabilities={businessCapabilities}
                      qualitySummary={businessOutputReviewSummary}
                      isReadOnly={isBusinessReadOnly}
                      actionLoadingId={businessActionLoadingId}
                      onDraftRun={handleBusinessDraftRun}
                      onDraftRunBatch={handleBusinessDraftRunBatch}
                      onOpenReview={handleOpenBusinessOutputReview}
                      formatDateTime={formatDateTime}
                    />
                    <BusinessCapabilityGrid
                      capabilities={businessCapabilities}
                      pendingApprovals={businessDefaultApprovals}
                      isReadOnly={isBusinessReadOnly}
                      actionLoadingId={businessActionLoadingId}
                      onEdit={handleBusinessEdit}
                      onSetDefault={handleBusinessSetDefault}
                      onToggleActive={handleBusinessToggleActive}
                      onRecordAcceptance={handleBusinessRecordAcceptance}
                      onDraftRun={handleBusinessDraftRun}
                      formatDateTime={formatDateTime}
                    />
                  </>
                ) : null}
                {businessWorkspaceTab === 'operations' ? (
                  <>
                    <BusinessActionPanel
                      capabilities={businessCapabilities}
                      pendingApprovals={businessDefaultApprovals}
                      summary={businessUsageSummary}
                    />
                    <BusinessCoreDecisionPanel
                      capabilities={businessCapabilities}
                      pendingApprovals={businessDefaultApprovals}
                      summary={businessUsageSummary}
                      formatDateTime={formatDateTime}
                      capabilitiesLoading={loading && businessCapabilities.length === 0}
                    />
                    <BusinessCoreClosurePanel
                      capabilities={businessCapabilities}
                      pendingApprovals={businessDefaultApprovals}
                      summary={businessUsageSummary}
                      formatDateTime={formatDateTime}
                      capabilitiesLoading={loading && businessCapabilities.length === 0}
                    />
                    {!isBusinessReadOnly ? (
                      <BusinessReleaseGuardPanel
                        capabilities={businessCapabilities}
                        pendingApprovals={businessDefaultApprovals}
                        summary={businessUsageSummary}
                      />
                    ) : null}
                    {!isBusinessReadOnly ? (
                      <BusinessGovernancePanel
                        capabilityOptions={businessCapabilityVersionOptions}
                        targetOptions={businessCompareTargetOptions}
                        compareLeftId={effectiveBusinessCompareLeftId}
                        compareRightId={effectiveBusinessCompareRightId}
                        selectedTarget={selectedBusinessCompareRight}
                        compareResult={businessCompareResult}
                        pendingApprovals={businessDefaultApprovals}
                        actionLoadingId={businessActionLoadingId}
                        onCompareLeftChange={(value) => {
                          setBusinessCompareLeftId(value);
                          setBusinessCompareRightId('');
                          setBusinessCompareResult(null);
                        }}
                        onCompareRightChange={(value) => {
                          setBusinessCompareRightId(value);
                          setBusinessCompareResult(null);
                        }}
                        onCompare={handleBusinessCompare}
                        onRollback={handleBusinessRollback}
                        onApprovalDecision={handleBusinessDefaultApprovalDecision}
                        formatDateTime={formatDateTime}
                      />
                    ) : null}
                    {!isBusinessReadOnly ? (
                      <BusinessOperationLogPanel
                        logs={businessOperationLogs}
                        onRefresh={refreshBusinessRuns}
                        formatDateTime={formatDateTime}
                      />
                    ) : null}
                  </>
                ) : null}
                <BusinessCapabilityEditorDialog
                  visible={businessDialogOpen}
                  form={businessForm}
                  error={businessFormError}
                  abilityOptions={businessAbilityOptions}
                  vlAbilityOptions={businessVlAbilityOptions}
                  onChange={setBusinessForm}
                  onClose={() => setBusinessDialogOpen(false)}
                  onConfirm={handleBusinessSubmit}
                />
                </Space>
              </Suspense>
            </Section>
          )}

          {activeNav === 'api-exposure' && (
            <Section
              id="api-exposure"
              title="接口调用"
              description="业务 API 文档、API Key、调用清单和 Coze 工具箱入口统一在这里查看。"
            >
              <Suspense fallback={panelFallback('接口调用')}>
                <ApiExposurePanel
                  publicAbilities={publicAbilities}
                  publicAbilitiesLoading={publicAbilitiesLoading}
                  cozeAbilityStats={cozeAbilityStats}
                  onRefreshPublicAbilities={refreshPublicAbilities}
                  onCopy={copyTextToClipboard}
                  onOpenBusinessRun={handleOpenBusinessRunDetailById}
                  getProviderLabel={getProviderLabel}
                  getCategoryLabel={getCategoryLabel}
                />
              </Suspense>
            </Section>
          )}

          {activeNav === 'billing' && (
            <Section id="billing" title="账单与套餐" description="先看业务是否正常收费、套餐是否够用、收入和成本是否能对上；支付和正式开票后续再接。">
              <Suspense fallback={panelFallback('账单与套餐')}>
                <BillingPanel
                  month={billingMonth}
                  windowDays={billingWindowDays}
                  tenantId={billingTenantId}
                  clientId={billingClientId}
                  businessKey={billingBusinessKey}
                  overview={billingOverview}
                  monthlySettlement={billingMonthlySettlement}
                  monthlySettlementRecords={billingMonthlySettlementRecords}
                  packageAlertNotifications={billingPackageAlertNotifications}
                  monthlyCollectionNotifications={billingMonthlyCollectionNotifications}
                  notificationConfig={billingNotificationConfig}
                  commercialReport={billingCommercialReport}
                  packageCatalog={billingPackageCatalog}
                  packagePurchaseOrders={billingPackagePurchaseOrders}
                  invoiceRequests={billingInvoiceRequests}
                  detail={billingDetail}
                  selectedUserId={billingSelectedUserId}
                  loading={billingLoading}
                  exporting={billingExporting}
                  error={billingError}
                  onMonthChange={setBillingMonth}
                  onWindowDaysChange={setBillingWindowDays}
                  onTenantIdChange={setBillingTenantId}
                  onClientIdChange={setBillingClientId}
                  onBusinessKeyChange={setBillingBusinessKey}
                  onRefresh={refreshBillingOverview}
                  onExportCommercialReport={exportBillingCommercialReport}
                  onExport={exportBillingUserLedger}
                  onSelectUser={refreshBillingUserDetail}
                  onRetryIssue={retryBillingIssue}
                  onRefundIssue={refundBillingIssue}
                  onGrantPackage={grantBillingPackage}
                  onIssueMonthlySettlement={issueBillingMonthlySettlement}
                  onMarkMonthlySettlementPaid={markBillingMonthlySettlementPaid}
                  onRunPackageAlertNotification={runBillingPackageAlertNotification}
                  onRunMonthlyCollectionNotification={runBillingMonthlyCollectionNotification}
                  onSaveNotificationConfig={saveBillingNotificationConfig}
                  onSavePackageCatalog={savePackageCatalog}
                  onCreatePackagePurchaseOrder={createPackagePurchaseOrder}
                  onMarkPackagePurchaseOrderPaid={markPackagePurchaseOrderPaid}
                  onCreateInvoiceRequest={createBillingInvoiceRequest}
                  onMarkInvoiceRequestIssued={markBillingInvoiceRequestIssued}
                  formatDateTime={formatDateTime}
                />
              </Suspense>
            </Section>
          )}

          {activeNav === 'auth' && (
            <Section id="auth" title="账号权限" description="管理用户、登录会话和邀请码；复杂权限后续再拆。">
              <Suspense fallback={panelFallback('账号权限')}>
                <AuthPanel
                  users={authUsers}
                  sessions={authSessions}
                  inviteCodes={inviteCodes}
                  scopeSummary={authScopeSummary}
                  userForm={authUserForm}
                  inviteForm={authInviteForm}
                  loading={authLoading}
                  error={authError}
                  onRefresh={refreshAuthPanel}
                  onUserFormChange={setAuthUserForm}
                  onUserEditSelect={handleAuthUserEditSelect}
                  onUserSubmit={handleAuthUserSubmit}
                  onInviteFormChange={setAuthInviteForm}
                  onInviteSubmit={handleAuthInviteSubmit}
                  onInviteDisable={handleAuthInviteDisable}
                  onSessionRevoke={handleAuthSessionRevoke}
                  formatDateTime={formatDateTime}
                />
              </Suspense>
            </Section>
          )}

          {activeNav === 'monitor' && dashboardMetrics && (
            <Section id="monitor" title="运行监控" description="实时关注任务队列、当日执行概况以及节点健康状态。">
              <Suspense fallback={panelFallback('运行监控')}>
                <MonitorPanel
                  dashboardMetrics={dashboardMetrics}
                  pendingQueueTotal={pendingQueueTotal}
                  pendingQueueSub={pendingQueueSub}
                  runningQueueTotal={runningQueueTotal}
                  runningQueueSub={runningQueueSub}
                  pendingBatchValue={pendingBatchValue}
                  pendingBatchSub={pendingBatchSub}
                  queueOverviewRows={queueOverviewRows}
                  comfyExecutors={comfyExecutors}
                  comfyQueueSummary={comfyQueueSummary}
                  comfyQueueSummaryLoading={comfyQueueSummaryLoading}
                  executors={executors}
                  onRefreshComfyQueue={refreshComfyQueueSummary}
                />
              </Suspense>
            </Section>
          )}

          {activeNav === 'executors' && (
            <Section id="executors" title="运行线路" description="维护能力运行线路、并发能力与健康状态。">
              <Suspense fallback={panelFallback('运行线路')}>
                <ExecutorsPanel
                  comfyExecutors={comfyExecutors}
                  comfyModelCache={comfyModelCache}
                  comfyModelErrorByExecutor={comfyModelErrorByExecutor}
                  comfyModelLoadingByExecutor={comfyModelLoadingByExecutor}
                  comfyQueueByExecutor={comfyQueueByExecutor}
                  comfyQueueSummary={comfyQueueSummary}
                  comfyQueueSummaryError={comfyQueueSummaryError}
                  comfyQueueSummaryLoading={comfyQueueSummaryLoading}
                  comfyQueueSummaryUpdatedAt={comfyQueueSummaryUpdatedAt}
                  comfySystemCache={comfySystemCache}
                  comfySystemErrorByExecutor={comfySystemErrorByExecutor}
                  comfySystemLoadingByExecutor={comfySystemLoadingByExecutor}
                  executorConfigJsonInvalid={executorConfigJsonInvalid}
                  executorConfigRecord={executorConfigRecord}
                  executorConfigTemplates={executorConfigTemplates}
                  executorForm={executorForm}
                  executorFormError={executorFormError}
                  executorInlineConcurrency={executorInlineConcurrency}
                  executorInlineError={executorInlineError}
                  executorInlineSaving={executorInlineSaving}
                  executorTraffic={executorTraffic}
                  executorTrafficError={executorTrafficError}
                  executorTrafficLoading={executorTrafficLoading}
                  executorTrafficTotals={executorTrafficTotals}
                  executors={executors}
                  executorsView={executorsView}
                  extractComfyuiModelCounts={extractComfyuiModelCounts}
                  extractComfyuiVersionInfo={extractComfyuiVersionInfo}
                  extractExecutorTags={extractExecutorTags}
                  formatDate={formatDate}
                  formatDateTime={formatDateTime}
                  getExecutorChannelLabel={getExecutorChannelLabel}
                  handleDelete={handleDelete}
                  handleExecutorSubmit={handleExecutorSubmit}
                  refreshComfyQueueSummary={refreshComfyQueueSummary}
                  refreshComfyuiModelCatalog={refreshComfyuiModelCatalog}
                  refreshComfyuiSystemStats={refreshComfyuiSystemStats}
                  refreshExecutorTraffic={refreshExecutorTraffic}
                  saveExecutorConcurrency={saveExecutorConcurrency}
                  setExecutorConfigField={setExecutorConfigField}
                  setExecutorForm={setExecutorForm}
                  setExecutorFormError={setExecutorFormError}
                  setExecutorInlineConcurrency={setExecutorInlineConcurrency}
                  setExecutorsView={setExecutorsView}
                  stringifyJSON={stringifyJSON}
                  summary={summary}
                />
              </Suspense>
            </Section>
          )}

          {activeNav === 'abilities' && (
            <Section
              id="ability-overview"
              title="原子能力总览"
              description="先判断能力是否可用，再进入参数、节点和测试细节。"
            >
              <Suspense fallback={panelFallback('原子能力总览')}>
                <AbilityOverviewSummaryPanel
                  abilityHealthSummary={abilityHealthSummary}
                  abilityTotalFallback={summary.abilities || 0}
                  filteredCount={filteredAbilities.length}
                />
              </Suspense>
            </Section>
          )}

          {activeNav === 'abilities' && (
            <Section
              id="future-abilities"
              title="原子能力类型路线"
              description="把用户能理解的能力范围固定下来，避免所有能力都混在一张技术表里。"
            >
              <Suspense fallback={panelFallback('原子能力类型路线')}>
                <AbilityRoadmapPanel />
              </Suspense>
            </Section>
          )}

          {activeNav === 'abilities' && (
            <Section
              id="ability-api"
              title="统一能力接口"
              description="面向客户端/业务方公开的 `/api/abilities` 清单与调用示例，便于快速查找能力 ID、输入要求、是否支持多图等。"
            >
              <Suspense fallback={panelFallback('统一能力接口')}>
                <AbilityApiPanel
                  publicAbilities={publicAbilities}
                  publicAbilitiesLoading={publicAbilitiesLoading}
                  abilityApiExample={abilityApiExample}
                  onRefresh={refreshPublicAbilities}
                  onCopy={copyTextToClipboard}
                  getProviderLabel={getProviderLabel}
                  getCategoryLabel={getCategoryLabel}
                />
              </Suspense>
            </Section>
          )}

          {activeNav === 'ability-logs' && (
      <Section
        id="ability-logs"
        title="处理步骤"
        description="这里展示图片分析、模型、生图、评分等后台步骤；业务是否成功先看业务调用清单。"
      >
        <Suspense fallback={panelFallback('处理步骤')}>
        <Card bordered>
          <Space direction="vertical" size="large" style={{ width: '100%' }}>
            <Tabs
              value={abilityLogTab}
              onChange={(v) => setAbilityLogTab(v as AbilityLogTab)}
              list={abilityLogTabs.map((tab) => ({
                label: tab.label,
                value: tab.id,
              }))}
            />

            {abilityLogTab === 'metrics' && (
              <AbilityLogMetricsPanel
                windowHours={abilityMetricsWindowHours}
                provider={abilityMetricsProvider}
                capabilityKey={abilityMetricsCapabilityKey}
                providerOptions={abilityProviders}
                capabilityOptions={abilityMetricsCapabilityOptions}
                metrics={abilityLogMetrics}
                loading={abilityLogMetricsLoading}
                error={abilityLogMetricsError}
                onWindowHoursChange={setAbilityMetricsWindowHours}
                onProviderChange={setAbilityMetricsProvider}
                onCapabilityKeyChange={setAbilityMetricsCapabilityKey}
                onRefresh={refreshAbilityLogMetrics}
                getProviderLabel={getProviderLabel}
              />
            )}

            {abilityLogTab === 'logs' && (
              <AbilityLogListPanel
                logs={globalAbilityLogs}
                filteredLogs={filteredGlobalAbilityLogs}
                total={globalAbilityLogTotal}
                loading={globalAbilityLogsLoading}
                exporting={exportingAbilityLogs}
                error={globalAbilityLogsError}
                updatedAt={globalAbilityLogsUpdatedAt}
                page={globalAbilityLogPage}
                pageSize={globalAbilityLogPageSize}
                windowHours={globalAbilityLogWindowHours}
                autoRefresh={globalAbilityLogsAutoRefresh}
                onlyCallbackFailed={globalAbilityLogOnlyCallbackFailed}
                search={globalAbilityLogSearch}
                provider={globalAbilityLogProvider}
                source={globalAbilityLogSource}
                status={globalAbilityLogStatus}
                templatePublished={globalAbilityLogTemplatePublished}
                capabilityKey={globalAbilityLogCapabilityKey}
                providers={globalAbilityLogProviders}
                sources={globalAbilityLogSources}
                statuses={globalAbilityLogStatuses}
                capabilityOptions={globalAbilityLogCapabilityOptions}
                onAutoRefreshChange={setGlobalAbilityLogsAutoRefresh}
                onWindowHoursChange={(value) => {
                  setGlobalAbilityLogPage(1);
                  setGlobalAbilityLogWindowHours(value);
                }}
                onRefresh={refreshGlobalAbilityLogs}
                onPageChange={setGlobalAbilityLogPage}
                onExport={exportGlobalAbilityLogs}
                onOnlyCallbackFailedChange={(value) => {
                  setGlobalAbilityLogPage(1);
                  setGlobalAbilityLogOnlyCallbackFailed(value);
                }}
                onSearchChange={(value) => {
                  setGlobalAbilityLogPage(1);
                  setGlobalAbilityLogSearch(value);
                }}
                onProviderChange={(value) => {
                  setGlobalAbilityLogPage(1);
                  setGlobalAbilityLogProvider(value);
                }}
                onSourceChange={(value) => {
                  setGlobalAbilityLogPage(1);
                  setGlobalAbilityLogSource(value);
                }}
                onStatusChange={(value) => {
                  setGlobalAbilityLogPage(1);
                  setGlobalAbilityLogStatus(value);
                }}
                onTemplatePublishedChange={(value) => {
                  setGlobalAbilityLogPage(1);
                  setGlobalAbilityLogTemplatePublished(value);
                }}
                onCapabilityKeyChange={(value) => {
                  setGlobalAbilityLogPage(1);
                  setGlobalAbilityLogCapabilityKey(value);
                }}
                onCopy={copyTextToClipboard}
                onOpenDetail={openAbilityLogDetail}
                resolveLogPricing={resolveLogPricing}
              />
            )}
          </Space>
        </Card>
        </Suspense>
      </Section>
          )}

          {activeNav === 'abilities' && (
      <Section
        id="abilities"
        title="能力管理"
        description="集中维护各厂商能力、默认参数和绑定节点，后续工作流和测试面板将直接引用这些配置。"
      >
        <Suspense fallback={panelFallback('能力管理')}>
        <AbilityCatalogPanel
          healthError={abilityHealthError}
          healthLoading={abilityHealthLoading}
          healthSummary={abilityHealthSummary}
          healthFilter={abilityHealthFilter}
          healthItems={filteredAbilityHealthItems}
          healthExporting={abilityHealthExporting}
          search={abilitySearch}
          providerFilter={abilityProviderFilter}
          statusFilter={abilityStatusFilter}
          providerOptions={abilityProviders}
          abilities={filteredAbilities}
          selectedAbilityId={selectedAbilityId}
          workflowsById={workflowLookup}
          vendorModels={vendorModels}
          vendorGovernanceSummary={vendorGovernanceSummary}
          executors={executors}
          pricingByAbility={abilityPricingMap}
          latestLogByAbility={latestAbilityLogMap}
          templateSummaryByAbility={abilityTemplateSummaryMap}
          onRefreshHealth={refreshAbilityHealthSummary}
          onHealthFilterChange={setAbilityHealthFilter}
          onExportHealth={exportAbilityHealthSummary}
          onCreate={() => {
            setAbilityForm(defaultAbilityForm);
            setAbilityRoutingPolicy('auto');
            setAbilityAllowedExecutors([]);
            setAbilityRequiredTags('');
            setAbilityFallbackToDefault(true);
            setAbilityDialogOpen(true);
          }}
          onSearchChange={setAbilitySearch}
          onProviderFilterChange={setAbilityProviderFilter}
          onStatusFilterChange={setAbilityStatusFilter}
          onSelectAbility={setSelectedAbilityId}
          onOpenTemplate={(ability) => {
            setSelectedAbilityId(ability.id);
            setActiveAbilityDetailTab('metadata');
            selectSection('abilities');
          }}
          onEdit={handleAbilityEdit}
          onDelete={handleAbilityDelete}
          getProviderLabel={getProviderLabel}
          getCategoryLabel={getCategoryLabel}
          getAbilityTypeLabel={getAbilityTypeLabel}
          getAbilitySchemaIssues={getAbilitySchemaIssues}
          describePricing={describePricing}
        />

        <div style={{ marginTop: 16 }}>{renderAbilityWorkbenchCard()}</div>

        <AbilityEditorDialog
          visible={abilityDialogOpen}
          form={abilityForm}
          executors={executors}
          workflows={workflows}
          vendorModels={vendorModels}
          vendorModelOptions={abilityVendorModelOptions}
          comfyExecutors={comfyExecutors}
          routingPolicy={abilityRoutingPolicy}
          fallbackToDefault={abilityFallbackToDefault}
          allowedExecutors={abilityAllowedExecutors}
          requiredTags={abilityRequiredTags}
          loraDefault={abilityLoraDefault}
          loraOptions={abilityFormLoraSelectOptions}
          loraAllowedFiles={abilityLoraAllowedFiles}
          loraAllowedTags={abilityLoraAllowedTags}
          loraAllowedBaseModels={abilityLoraAllowedBaseModels}
          baseModelOptions={abilityFormBaseModelOptions}
          loraPolicy={abilityLoraPolicy}
          onClose={() => setAbilityDialogOpen(false)}
          onSubmit={handleAbilitySubmit}
          onFormChange={setAbilityForm}
          onRoutingPolicyChange={setAbilityRoutingPolicy}
          onFallbackToDefaultChange={setAbilityFallbackToDefault}
          onAllowedExecutorsChange={setAbilityAllowedExecutors}
          onRequiredTagsChange={setAbilityRequiredTags}
          onLoraDefaultChange={setAbilityLoraDefault}
          onLoraAllowedFilesChange={setAbilityLoraAllowedFiles}
          onLoraAllowedTagsChange={setAbilityLoraAllowedTags}
          onLoraAllowedBaseModelsChange={setAbilityLoraAllowedBaseModels}
          onLoraPolicyChange={setAbilityLoraPolicy}
        />
        </Suspense>
      </Section>
          )}

          {activeNav === 'ability-evals' && (
      <Section
        id="ability-evals"
        title="能力评测"
        description="内部迭代工具：统一用 Coze 工作流试运行，并对输出做 1-5 评分与备注。"
      >
        <Suspense
          fallback={
            <div className="rounded-3xl border border-slate-200 bg-white px-6 py-5 text-sm text-slate-600 shadow-sm">
              能力评测加载中，请稍候...
            </div>
          }
        >
          <AbilityEvaluationPage focusRunId={focusedEvalRunId} />
        </Suspense>
      </Section>
          )}
          {activeNav === 'comfyui-management' && (
      <Section
        id="comfyui-management"
        title="ComfyUI 管理"
        description="纳管 ComfyUI 执行节点，关注机器可用性、能力部署一致性、队列衔接与结果回填；不替代 ComfyUI 工作流编辑后台。"
      >
        <ComfyuiManagementHeader
          activeTab={comfyuiManageTab}
          activeTabMeta={activeComfyTabMeta}
          groupOrder={comfyuiTabGroupOrder}
          groupMap={comfyuiGroupMap}
          groupMeta={comfyuiGroupMeta}
          groupBadge={comfyuiGroupBadge}
          tabMeta={comfyuiTabMeta}
          activeGroupTabs={activeComfyGroupTabs}
          tabHelpText={comfyuiTabHelpText}
          syncSteps={comfySyncSteps}
          syncStepStatusMeta={comfySyncStepStatusMeta}
          syncCurrentStep={comfySyncCurrentStep}
          syncCurrentGuide={comfySyncCurrentGuide}
          showTestNodes={comfyShowTestNodes}
          hiddenExecutorCount={comfyHiddenExecutorCount}
          hiddenAgentCount={comfyHiddenAgentCount}
          serversAssistOpen={comfyServersAssistOpen}
          manifestsAssistOpen={comfyManifestsAssistOpen}
          taskAdvancedOpen={comfyTaskAdvancedOpen}
          onTabChange={(tab) => setComfyuiManageTab(tab as ComfyuiManageTab)}
          onRefreshCurrentStep={() => {
            if (comfyuiManageTab === 'servers') {
              refreshComfyuiServers();
              return;
            }
            if (comfyuiManageTab === 'manifests') {
              refreshComfyManifests();
              return;
            }
            refreshComfyAgentTasks();
          }}
          onToggleServersAssist={() => setComfyServersAssistOpen((prev) => !prev)}
          onToggleManifestsAssist={() => setComfyManifestsAssistOpen((prev) => !prev)}
          onCreateManifest={() => {
            resetComfyManifestForm();
            setComfyManifestDialogOpen(true);
          }}
          onToggleTaskAdvanced={() => setComfyTaskAdvancedOpen((prev) => !prev)}
          onScrollToTaskCreate={() => {
            const el = document.getElementById('comfy-task-create-card');
            if (el) {
              el.scrollIntoView({ behavior: 'smooth', block: 'start' });
              return;
            }
            contentRef.current?.scrollTo({ top: 0, behavior: 'smooth' });
          }}
          onShowTestNodesChange={setComfyShowTestNodes}
        />
        <Suspense fallback={panelFallback('ComfyUI 管理')}>
        {comfyuiManageTab === 'lora' && (
          <ComfyuiLorasPanel
            executors={comfyExecutors}
            executorId={comfyLoraExecutorId}
            executor={comfyLoraExecutor}
            catalog={comfyLoraCatalog}
            loading={comfyLoraLoading}
            error={comfyLoraError}
            cachedBaseModels={comfyCachedBaseModels}
            baseModelOptions={comfyLoraBaseModelOptions}
            formBaseModels={comfyLoraFormBaseModels}
            items={comfyLoraItems}
            untracked={comfyLoraUntracked}
            installedCount={comfyLoraInstalledCount}
            serverScanned={comfyLoraServerScanned}
            search={comfyLoraSearch}
            statusFilter={comfyLoraStatusFilter}
            statusOptions={statusOptions}
            dialogOpen={comfyLoraDialogOpen}
            saving={comfyLoraSaving}
            form={comfyLoraForm}
            tagsInput={comfyLoraTagsInput}
            triggersInput={comfyLoraTriggersInput}
            formError={comfyLoraFormError}
            onExecutorChange={setComfyLoraExecutorId}
            onRefreshLibrary={() => refreshComfyuiLoraCatalog({ includeUntracked: false })}
            onRefreshBaseModels={() => refreshComfyuiModelCatalog(comfyLoraExecutorId)}
            onRefreshUntracked={() => refreshComfyuiLoraCatalog({ includeUntracked: true })}
            onCreateLora={() => {
              resetComfyLoraForm();
              setComfyLoraDialogOpen(true);
            }}
            onClearBaseModels={clearComfyBaseModels}
            onRemoveBaseModel={removeComfyBaseModel}
            onSearchChange={setComfyLoraSearch}
            onStatusFilterChange={setComfyLoraStatusFilter}
            onCreateFromUntracked={(name) => {
              resetComfyLoraForm({
                file_name: name,
                display_name: name.replace(/\.safetensors$/i, ''),
              });
              setComfyLoraDialogOpen(true);
            }}
            onEditLora={(item) => {
              resetComfyLoraForm(item);
              setComfyLoraDialogOpen(true);
            }}
            onDeleteLora={handleComfyLoraDelete}
            onCloseDialog={() => setComfyLoraDialogOpen(false)}
            onSaveLora={handleComfyLoraSave}
            onFormPatch={(patch) => setComfyLoraForm((prev) => ({ ...prev, ...patch }))}
            onBaseModelsChange={(baseModels) =>
              setComfyLoraForm((prev) => ({
                ...prev,
                base_models: baseModels,
                base_model: baseModels.length === 1 ? baseModels[0] : undefined,
              }))
            }
            onTagsInputChange={setComfyLoraTagsInput}
            onTriggersInputChange={setComfyLoraTriggersInput}
          />
        )}
        {comfyuiManageTab === 'assets' && (
          <ComfyuiAssetsPanel
            executors={comfyExecutors}
            versionItems={comfyVersionCatalogItems}
            versionLoading={comfyVersionCatalogLoading}
            versionError={comfyVersionCatalogError}
            versionSearch={comfyVersionCatalogSearch}
            versionStatus={comfyVersionCatalogStatus}
            versionServerLoading={comfyVersionServerLoading}
            versionSyncing={comfyVersionSyncing}
            versionUsage={comfyServerVersionUsage}
            versionDialogOpen={comfyVersionDialogOpen}
            versionSaving={comfyVersionSaving}
            versionForm={comfyVersionForm}
            versionFormError={comfyVersionFormError}
            modelItems={comfyModelCatalogItems}
            modelLoading={comfyModelCatalogLoading}
            modelError={comfyModelCatalogError}
            modelSearch={comfyModelCatalogSearch}
            modelType={comfyModelCatalogType}
            modelStatus={comfyModelCatalogStatus}
            modelDialogOpen={comfyModelDialogOpen}
            modelSaving={comfyModelSaving}
            modelForm={comfyModelForm}
            modelFormTags={comfyModelFormTags}
            modelFormError={comfyModelFormError}
            pluginItems={comfyPluginCatalogItems}
            pluginLoading={comfyPluginCatalogLoading}
            pluginError={comfyPluginCatalogError}
            pluginSearch={comfyPluginCatalogSearch}
            pluginStatus={comfyPluginCatalogStatus}
            pluginDialogOpen={comfyPluginDialogOpen}
            pluginSaving={comfyPluginSaving}
            pluginForm={comfyPluginForm}
            pluginFormTags={comfyPluginFormTags}
            pluginFormError={comfyPluginFormError}
            statusOptions={statusOptions}
            modelTypeOptions={comfyModelTypeOptions}
            onVersionSearchChange={setComfyVersionCatalogSearch}
            onVersionStatusChange={setComfyVersionCatalogStatus}
            onRefreshVersionUsage={refreshComfyVersionUsage}
            onSyncVersions={handleComfyVersionSync}
            onCreateVersion={() => {
              resetComfyVersionForm();
              setComfyVersionDialogOpen(true);
            }}
            onEditVersion={(item) => {
              resetComfyVersionForm(item);
              setComfyVersionDialogOpen(true);
            }}
            onDeleteVersion={handleComfyVersionDelete}
            onCloseVersionDialog={() => setComfyVersionDialogOpen(false)}
            onSaveVersion={handleComfyVersionSave}
            onVersionFormPatch={(patch) => setComfyVersionForm((prev) => ({ ...prev, ...patch }))}
            onModelSearchChange={setComfyModelCatalogSearch}
            onModelTypeChange={setComfyModelCatalogType}
            onModelStatusChange={setComfyModelCatalogStatus}
            onCreateModel={() => {
              resetComfyModelForm();
              setComfyModelDialogOpen(true);
            }}
            onEditModel={(item) => {
              resetComfyModelForm(item);
              setComfyModelDialogOpen(true);
            }}
            onDeleteModel={handleComfyModelDelete}
            onCloseModelDialog={() => setComfyModelDialogOpen(false)}
            onSaveModel={handleComfyModelSave}
            onModelFormPatch={(patch) => setComfyModelForm((prev) => ({ ...prev, ...patch }))}
            onModelTagsChange={setComfyModelFormTags}
            onPluginSearchChange={setComfyPluginCatalogSearch}
            onPluginStatusChange={setComfyPluginCatalogStatus}
            onCreatePlugin={() => {
              resetComfyPluginForm();
              setComfyPluginDialogOpen(true);
            }}
            onEditPlugin={(item) => {
              resetComfyPluginForm(item);
              setComfyPluginDialogOpen(true);
            }}
            onDeletePlugin={handleComfyPluginDelete}
            onClosePluginDialog={() => setComfyPluginDialogOpen(false)}
            onSavePlugin={handleComfyPluginSave}
            onPluginFormPatch={(patch) => setComfyPluginForm((prev) => ({ ...prev, ...patch }))}
            onPluginTagsChange={setComfyPluginFormTags}
          />
        )}
        {comfyuiManageTab === 'servers' && (
          <ComfyuiServersPanel
            executors={comfyExecutors}
            baselineExecutor={comfyBaselineExecutor}
            modelCache={comfyModelCache}
            baseModelCache={comfyBaseModelCache}
            nodeCache={comfyNodeCache}
            systemCache={comfySystemCache}
            systemLoadingByExecutor={comfySystemLoadingByExecutor}
            modelLoadingByExecutor={comfyModelLoadingByExecutor}
            systemErrorByExecutor={comfySystemErrorByExecutor}
            modelErrorByExecutor={comfyModelErrorByExecutor}
            serverRefreshing={comfyServerRefreshing}
            diffSaving={comfyDiffSaving}
            assistOpen={comfyServersAssistOpen}
            serverForm={comfyServerForm}
            serverFormError={comfyServerFormError}
            serverSaving={comfyServerSaving}
            statusOptions={statusOptions}
            diffLogs={comfyDiffLogs}
            diffLogsLoading={comfyDiffLogsLoading}
            diffLogsError={comfyDiffLogsError}
            diffDialogOpen={comfyDiffDialogOpen}
            diffDialogTitle={comfyDiffDialogTitle}
            diffDialogText={comfyDiffDialogText}
            diffDialogPayload={comfyDiffDialogPayload}
            buildServerDiff={buildComfyServerDiff}
            buildDiffSnapshot={buildComfyDiffSnapshot}
            onBaselineExecutorChange={setComfyBaselineExecutorId}
            onRefreshAllServers={refreshComfyuiServers}
            onRefreshExecutor={(executorId) => {
              refreshComfyuiSystemStats(executorId);
              refreshComfyuiModelCatalog(executorId, { includeNodes: true });
            }}
            onSaveDiffSnapshot={handleSaveComfyDiffSnapshot}
            onCreateServer={handleComfyuiServerCreate}
            onServerFormChange={(patch) => setComfyServerForm((prev) => ({ ...prev, ...patch }))}
            onRefreshDiffLogs={refreshComfyDiffLogs}
            onOpenDiffDialog={(title, payload) => {
              setComfyDiffDialogTitle(title);
              setComfyDiffDialogPayload(payload);
              setComfyDiffDialogOpen(true);
            }}
            onDownloadJson={downloadJson}
            onCopyText={copyTextToClipboard}
            onCloseDiffDialog={() => setComfyDiffDialogOpen(false)}
          />
        )}
        {comfyuiManageTab === 'agents' && (
          <ComfyuiAgentsPanel
            agents={visibleComfyAgentList}
            loading={comfyAgentLoading}
            error={comfyAgentError}
            statusFilter={comfyAgentStatusFilter}
            statusOptions={statusOptions}
            tokenError={comfyAgentTokenError}
            tokenDialogOpen={comfyAgentTokenDialogOpen}
            tokenLoading={comfyAgentTokenLoading}
            primarySaving={comfyAgentPrimarySaving}
            formDialogOpen={comfyAgentDialogOpen}
            formEditing={comfyAgentEditing}
            formSaving={comfyAgentSaving}
            form={comfyAgentForm}
            configInput={comfyAgentConfigInput}
            formError={comfyAgentFormError}
            tokenAgentId={comfyAgentTokenAgentId}
            tokenValue={comfyAgentTokenValue}
            tokenExpiresAt={comfyAgentTokenExpiresAt}
            resolveBaseUrl={resolveAgentBaseUrl}
            isPrimaryAgent={isRolePrimaryAgent}
            onStatusFilterChange={setComfyAgentStatusFilter}
            onRefresh={() => refreshComfyAgents()}
            onCreate={() => {
              resetComfyAgentForm();
              setComfyAgentDialogOpen(true);
            }}
            onEdit={(agent, baseUrl) => {
              resetComfyAgentForm({
                ...agent,
                baseUrl: baseUrl || undefined,
              });
              setComfyAgentDialogOpen(true);
            }}
            onIssueToken={handleComfyAgentTokenIssue}
            onSetPrimary={handleComfyAgentSetPrimary}
            onDelete={handleComfyAgentDelete}
            onCloseForm={() => setComfyAgentDialogOpen(false)}
            onSaveForm={handleComfyAgentSave}
            onFormPatch={(patch) => setComfyAgentForm((prev) => ({ ...prev, ...patch }))}
            onConfigInputChange={setComfyAgentConfigInput}
            onCloseToken={() => setComfyAgentTokenDialogOpen(false)}
            onCopyText={copyTextToClipboard}
          />
        )}
        {comfyuiManageTab === 'desktop' && (
          <ComfyuiDesktopPanel
            centerUrl={comfyDesktopCenterUrl}
            installReleaseId={comfyDesktopInstallReleaseId}
            releaseOptions={comfyDesktopReleaseOptions}
            hasWindowsX64Release={comfyDesktopHasWindowsX64Release}
            releases={comfyDesktopReleases}
            selectedRelease={comfyDesktopSelectedRelease}
            activeRelease={comfyDesktopActiveRelease}
            installCommand={comfyDesktopInstallCommand}
            agentRows={comfyDesktopAgentRows}
            agentLoading={comfyAgentLoading}
            agentError={comfyAgentError}
            enrollCodes={comfyEnrollCodes}
            enrollCodesLoading={comfyEnrollCodesLoading}
            enrollCodesError={comfyEnrollCodesError}
            enrollCodeRole={comfyEnrollCodeRole}
            enrollCodeTtlSeconds={comfyEnrollCodeTtlSeconds}
            enrollCodeMaxUses={comfyEnrollCodeMaxUses}
            enrollCodeNote={comfyEnrollCodeNote}
            enrollCodeCreating={comfyEnrollCodeCreating}
            releaseStatusFilter={comfyDesktopReleaseStatusFilter}
            releaseStatusOptions={comfyDesktopReleaseStatusOptions}
            releasesLoading={comfyDesktopReleasesLoading}
            releasesError={comfyDesktopReleasesError}
            releaseDialogOpen={comfyDesktopReleaseDialogOpen}
            releaseSaving={comfyDesktopReleaseSaving}
            releaseForm={comfyDesktopReleaseForm}
            releasePayloadInput={comfyDesktopReleasePayloadInput}
            releaseFormError={comfyDesktopReleaseFormError}
            getUpdateTag={getComfyDesktopUpdateTag}
            onInstallReleaseChange={setComfyDesktopInstallReleaseId}
            onCopyText={copyTextToClipboard}
            onRefreshAgents={() => refreshComfyAgents({ status: 'all' })}
            onEnrollRoleChange={setComfyEnrollCodeRole}
            onEnrollTtlChange={setComfyEnrollCodeTtlSeconds}
            onEnrollMaxUsesChange={setComfyEnrollCodeMaxUses}
            onEnrollNoteChange={setComfyEnrollCodeNote}
            onCreateEnrollCode={handleComfyEnrollCodeCreate}
            onRefreshEnrollCodes={refreshComfyEnrollCodes}
            onReleaseStatusFilterChange={setComfyDesktopReleaseStatusFilter}
            onRefreshReleases={refreshComfyDesktopReleases}
            onCreateRelease={() => {
              resetComfyDesktopReleaseForm();
              setComfyDesktopReleaseDialogOpen(true);
            }}
            onEditRelease={(release) => {
              resetComfyDesktopReleaseForm(release);
              setComfyDesktopReleaseDialogOpen(true);
            }}
            onToggleReleaseStatus={handleToggleComfyDesktopReleaseStatus}
            onCloseReleaseDialog={() => setComfyDesktopReleaseDialogOpen(false)}
            onSaveRelease={handleComfyDesktopReleaseSave}
            onReleaseFormPatch={(patch) => setComfyDesktopReleaseForm((prev) => ({ ...prev, ...patch }))}
            onReleasePayloadInputChange={setComfyDesktopReleasePayloadInput}
          />
        )}
        {comfyuiManageTab === 'manifests' && (
          <ComfyuiManifestsPanel
            manifests={comfyManifestList}
            loading={comfyManifestLoading}
            error={comfyManifestError}
            roleFilter={comfyManifestRoleFilter}
            statusFilter={comfyManifestStatusFilter}
            actionLoading={comfyManifestActionLoading}
            assistOpen={comfyManifestsAssistOpen}
            repairJobs={comfyRepairJobs}
            repairRunningCount={comfyRepairRunningCount}
            repairFailedCount={comfyRepairFailedCount}
            dialogOpen={comfyManifestDialogOpen}
            saving={comfyManifestSaving}
            form={comfyManifestForm}
            editorMode={comfyManifestEditorMode}
            includeInactive={comfyManifestIncludeInactive}
            wizardPreview={comfyManifestWizardPreview}
            contentInput={comfyManifestContentInput}
            formError={comfyManifestFormError}
            driftDialogOpen={comfyManifestDriftDialogOpen}
            driftTitle={comfyManifestDriftTitle}
            driftError={comfyManifestDriftError}
            driftLoading={comfyManifestDriftLoading}
            driftText={comfyManifestDriftText}
            driftData={comfyManifestDriftData}
            repairPlan={comfyRepairPlan}
            repairPlanLoading={comfyRepairPlanLoading}
            repairJobLoading={comfyRepairJobLoading}
            onRoleFilterChange={setComfyManifestRoleFilter}
            onStatusFilterChange={setComfyManifestStatusFilter}
            onRefreshManifests={() => refreshComfyManifests()}
            onCreateManifest={() => {
              resetComfyManifestForm();
              setComfyManifestDialogOpen(true);
            }}
            onEditManifest={(manifest) => {
              resetComfyManifestForm({
                ...manifest,
                downloadUrl: manifest.downloadUrl || manifest.download_url || undefined,
              });
              setComfyManifestDialogOpen(true);
            }}
            onPublishManifest={handleComfyManifestPublish}
            onRollbackManifest={handleComfyManifestRollback}
            onOpenDrift={handleOpenComfyManifestDrift}
            onRefreshRepairJobs={() => refreshComfyRepairJobs()}
            onCloseDialog={() => setComfyManifestDialogOpen(false)}
            onSaveManifest={handleComfyManifestSave}
            onFormPatch={(patch) => setComfyManifestForm((prev) => ({ ...prev, ...patch }))}
            onEditorModeChange={setComfyManifestEditorMode}
            onIncludeInactiveChange={setComfyManifestIncludeInactive}
            onGenerateFromWizard={handleComfyManifestGenerateFromWizard}
            onContentInputChange={setComfyManifestContentInput}
            onCloseDriftDialog={() => setComfyManifestDriftDialogOpen(false)}
            onCopyText={copyTextToClipboard}
            onDownloadJson={downloadJson}
            onGenerateRepairPlan={handleComfyGenerateRepairPlan}
            onCreateRepairJob={handleComfyCreateRepairJob}
          />
        )}
        {comfyuiManageTab === 'tasks' && (
          <ComfyuiTasksPanel
            taskForm={comfyAgentTaskForm}
            agentOptions={comfyAgentOptions}
            manifestOptions={comfyManifestOptions}
            pushAfterCreate={comfyAgentTaskPushAfterCreate}
            formError={comfyAgentTaskFormError}
            saving={comfyAgentTaskSaving}
            advancedOpen={comfyTaskAdvancedOpen}
            monitoringWindowHours={comfyMonitoringWindowHours}
            monitoringSummary={comfyMonitoringSummary}
            monitoringLoading={comfyMonitoringLoading}
            monitoringError={comfyMonitoringError}
            queueSummary={comfyQueueSummary}
            queueSummaryLoading={comfyQueueSummaryLoading}
            queueSummaryError={comfyQueueSummaryError}
            queueSummaryUpdatedAt={comfyQueueSummaryUpdatedAt}
            workflowCompatibility={comfyWorkflowCompatibility}
            workflowCompatibilityLoading={comfyWorkflowCompatibilityLoading}
            workflowCompatibilityError={comfyWorkflowCompatibilityError}
            workflowCompatibilityUpdatedAt={comfyWorkflowCompatibilityUpdatedAt}
            taskAgentFilter={comfyAgentTaskAgentFilter}
            taskStatusFilter={comfyAgentTaskStatusFilter}
            tasks={visibleComfyAgentTasks}
            tasksLoading={comfyAgentTasksLoading}
            tasksError={comfyAgentTasksError}
            manifests={comfyManifestList}
            taskPushLoading={comfyAgentTaskPushLoading}
            runningTaskCount={comfyRunningTaskCount}
            taskEventsDialogOpen={comfyAgentTaskEventsDialogOpen}
            taskEventsTaskId={comfyAgentTaskEventsTaskId}
            taskEvents={comfyAgentTaskEvents}
            taskEventsLoading={comfyAgentTaskEventsLoading}
            taskEventsError={comfyAgentTaskEventsError}
            formatActions={formatComfyAgentActions}
            onTaskFormPatch={(patch) => setComfyAgentTaskForm((prev) => ({ ...prev, ...patch }))}
            onPushAfterCreateChange={setComfyAgentTaskPushAfterCreate}
            onCreateTask={handleComfyAgentTaskCreate}
            onMonitoringWindowChange={setComfyMonitoringWindowHours}
            onRefreshMonitoring={() => refreshComfyMonitoringSummary()}
            onRefreshQueueSummary={() => refreshComfyQueueSummary()}
            onRefreshWorkflowCompatibility={() => refreshComfyWorkflowCompatibility()}
            onTaskAgentFilterChange={setComfyAgentTaskAgentFilter}
            onTaskStatusFilterChange={setComfyAgentTaskStatusFilter}
            onRefreshTasks={() => refreshComfyAgentTasks()}
            onPushTask={handleComfyAgentTaskPush}
            onOpenTaskEvents={openComfyAgentTaskEvents}
            onCloseTaskEvents={() => setComfyAgentTaskEventsDialogOpen(false)}
          />
        )}
        {comfyuiManageTab === 'alerts' && (
          <ComfyuiAlertsPanel
            alerts={visibleComfyAgentAlerts}
            loading={comfyAgentAlertsLoading}
            error={comfyAgentAlertsError}
            agentFilter={comfyAgentAlertsAgentFilter}
            agentOptions={comfyAgentOptions}
            typeFilter={comfyAgentAlertsTypeFilter}
            limit={comfyAgentAlertsLimit}
            onAgentFilterChange={setComfyAgentAlertsAgentFilter}
            onTypeFilterChange={setComfyAgentAlertsTypeFilter}
            onLimitChange={setComfyAgentAlertsLimit}
            onRefresh={refreshComfyAgentAlerts}
          />
        )}
        {comfyuiManageTab === 'templates' && (
          <ComfyuiTemplatesPanel
            comfyServerRefreshing={comfyServerRefreshing}
            comfyExecutors={comfyExecutors}
            refreshComfyuiServers={refreshComfyuiServers}
            comfyServersLoadedCount={comfyServersLoadedCount}
            workflows={workflows}
            extractAllowedExecutorIds={extractAllowedExecutorIds}
            executors={executors}
            comfyWorkflowDepsMap={comfyWorkflowDepsMap}
            resolveWorkflowExecutors={resolveWorkflowExecutors}
            evaluateWorkflowOnExecutor={evaluateWorkflowOnExecutor}
            parseJSON={parseJSON}
            setWorkflowForm={setWorkflowForm}
            stringifyJSON={stringifyJSON}
            setWorkflowFormAllowedExecutors={setWorkflowFormAllowedExecutors}
            normalizeInputNodeMap={normalizeInputNodeMap}
            setWorkflowInputMap={setWorkflowInputMap}
            normalizeOutputNodeIds={normalizeOutputNodeIds}
            setWorkflowOutputNodeIds={setWorkflowOutputNodeIds}
            setWorkflowOutputShowAll={setWorkflowOutputShowAll}
            handleWorkflowClone={handleWorkflowClone}
            handleDelete={handleDelete}
            workflowForm={workflowForm}
            extractComfyuiWorkflowDependencies={extractComfyuiWorkflowDependencies}
            downloadJson={downloadJson}
            workflowEditTab={workflowEditTab}
            setWorkflowEditTab={setWorkflowEditTab}
            statusOptions={statusOptions}
            handleWorkflowFile={handleWorkflowFile}
            workflowDefinitionError={workflowDefinitionError}
            workflowDefinitionNotice={workflowDefinitionNotice}
            workflowMetadataError={workflowMetadataError}
            workflowCanMap={workflowCanMap}
            comfyWorkflowNodes={comfyWorkflowNodes}
            workflowInputMap={workflowInputMap}
            workflowOutputNodeIds={workflowOutputNodeIds}
            workflowInputPickerNodeId={workflowInputPickerNodeId}
            setWorkflowInputPickerNodeId={setWorkflowInputPickerNodeId}
            setWorkflowInputPickerKeys={setWorkflowInputPickerKeys}
            comfyWorkflowNodeMap={comfyWorkflowNodeMap}
            workflowInputPickerKeys={workflowInputPickerKeys}
            addWorkflowInputMappingsForNode={addWorkflowInputMappingsForNode}
            addWorkflowInputMap={addWorkflowInputMap}
            updateWorkflowInputMap={updateWorkflowInputMap}
            removeWorkflowInputMap={removeWorkflowInputMap}
            workflowOutputShowAll={workflowOutputShowAll}
            updateWorkflowOutputNodes={updateWorkflowOutputNodes}
            workflowOutputPickerNodeId={workflowOutputPickerNodeId}
            setWorkflowOutputPickerNodeId={setWorkflowOutputPickerNodeId}
            addWorkflowOutputNode={addWorkflowOutputNode}
            removeWorkflowOutputNode={removeWorkflowOutputNode}
            workflowMappingErrors={workflowMappingErrors}
            workflowNodeSearch={workflowNodeSearch}
            setWorkflowNodeSearch={setWorkflowNodeSearch}
            workflowParamScope={workflowParamScope}
            setWorkflowParamScope={setWorkflowParamScope}
            filteredWorkflowNodeDetails={filteredWorkflowNodeDetails}
            workflowInterfaceNodeIds={workflowInterfaceNodeIds}
            addWorkflowOutputNodeById={addWorkflowOutputNodeById}
            addWorkflowInputMapEntry={addWorkflowInputMapEntry}
            updateWorkflowNodeInputValue={updateWorkflowNodeInputValue}
            workflowFormAllowedExecutors={workflowFormAllowedExecutors}
            syncWorkflowMetadata={syncWorkflowMetadata}
            workflowFormErrors={workflowFormErrors}
            workflowSubmitDisabled={workflowSubmitDisabled}
            handleWorkflowSubmit={handleWorkflowSubmit}
            defaultWorkflowForm={defaultWorkflowForm}
            setWorkflowFormErrors={setWorkflowFormErrors}
          />
        )}
        </Suspense>
      </Section>
          )}
          {activeNav === 'workflow-builder' && (
            <Section
              id="workflow-builder"
              title="高级编排"
              description="管理外部编排画布、流程绑定和运行观察入口；普通业务优先走“业务能力”，这里主要给高级配置和排查使用。"
            >
              <Suspense fallback={panelFallback('高级编排')}>
                <WorkflowBuilderPanel
                  loading={!systemConfig}
                  cozeBaseUrl={cozeBaseUrl}
                  cozeLoopUrl={cozeLoopUrl}
                  cozeTokenHint={cozeTokenHint}
                  defaultTimeout={cozeConfig?.default_timeout}
                  cozeAbilityStats={cozeAbilityStats}
                  cozeAbilityMappings={cozeAbilityMappings}
                  cozeRecentLogs={cozeRecentLogs}
                  onOpenCozeStudio={handleOpenCozeStudio}
                  onOpenCozeLoop={handleOpenCozeLoop}
                  resolveAssetUrl={resolveAssetUrl}
                />
              </Suspense>
            </Section>
          )}

          {activeNav === 'bindings' && (
            <Section
              id="bindings"
              title="路由策略"
              description="配置业务入口使用哪套工作流、走哪条运行线路，以及失败时如何按优先级切换。"
            >
              <Suspense fallback={panelFallback('路由策略')}>
                <BindingRoutesPanel
                  bindings={bindings}
                  bindingForm={bindingForm}
                  onFormChange={setBindingForm}
                  onSubmit={handleBindingSubmit}
                  onDelete={(id) => handleDelete('binding', id)}
                  onReset={() => setBindingForm(defaultBindingForm)}
                />
              </Suspense>
            </Section>
          )}

          {activeNav === 'vendor-models' && (
            <Section
              id="vendor-models"
              title="模型弹药库"
              description="集中查看第三方模型、密钥池、出网状态与能力范围；业务能力只引用这里沉淀后的模型资源。"
            >
              <Suspense
                fallback={
                  <div className="rounded-3xl border border-slate-200 bg-white px-6 py-5 text-sm text-slate-600 shadow-sm">
                    模型弹药库加载中，请稍候...
                  </div>
                }
              >
                <VendorModelsPanel
                  baseUrl={vendorBaseUrl}
                  providers={vendorProviders}
                  models={vendorModels}
                  keys={vendorKeys}
                  usageItems={vendorUsageItems}
                  governanceSummary={vendorGovernanceSummary}
                  usageTotal={vendorUsageTotal}
                  usageFailed={vendorUsageFailed}
                  usageSuccessRate={vendorUsageSuccessRate}
                  usageWindowHours={vendorUsageWindowHours}
                  governanceIssueCount={vendorGovernanceIssueCount}
                  loading={vendorLoading}
                  error={vendorError}
                  notice={vendorNotice}
                  egressChecks={vendorEgressChecks}
                  modelForm={vendorModelForm}
                  modelFormError={vendorModelFormError}
                  keyForm={vendorKeyForm}
                  onRefresh={loadVendorCatalog}
                  onSyncVolcengine={handleSyncVolcengineModels}
                  onEgressCheck={handleVendorEgressCheck}
                  onModelFormChange={setVendorModelForm}
                  onModelEdit={resetVendorModelForm}
                  onModelBulkAction={handleVendorModelBulkAction}
                  onModelAccept={handleVendorModelAcceptance}
                  onModelReset={() => resetVendorModelForm()}
                  onModelSubmit={handleVendorModelSubmit}
                  onKeyFormChange={setVendorKeyForm}
                  onKeyCheck={handleVendorKeyCheck}
                  onKeySubmit={handleVendorKeySubmit}
                  onKeyReset={() => setVendorKeyForm(defaultVendorKeyForm)}
                />
              </Suspense>
            </Section>
          )}

          {activeNav === 'apikeys' && (
            <Section
              id="apikeys"
              title="历史密钥仓库"
              description="兼容旧版密钥表；第三方模型密钥请优先使用“模型弹药库”，这里后续会逐步降级为历史兼容入口。"
            >
              <Suspense fallback={panelFallback('历史密钥仓库')}>
                <LegacyApiKeysPanel
                  apiKeys={apiKeys}
                  apiKeyForm={apiKeyForm}
                  onFormChange={setApiKeyForm}
                  onSubmit={handleApiKeySubmit}
                  onDelete={(id) => handleDelete('apikey', String(id))}
                  onReset={() => setApiKeyForm(defaultApiKeyForm)}
                  getProviderLabel={getProviderLabel}
                />
              </Suspense>
            </Section>
          )}

          {activeNav === 'system' && systemConfig && (
            <Section id="system" title="系统配置" description="汇总环境信息、OSS 配置及安全参数，便于排障和入职交接。">
              <Suspense fallback={panelFallback('系统配置')}>
                <SystemConfigPanel systemConfig={systemConfig} />
              </Suspense>
            </Section>
          )}

          {activeNav === 'logs' && (
            <Section id="logs" title="调度事件" description="追踪任务事件、调度动作与回调结果，便于排障和多用户并发分析。">
              <Suspense fallback={panelFallback('调度事件')}>
                <DispatchLogsPanel
                  dispatchLogs={dispatchLogs}
                  onOpenDetail={(entry) => {
                    setDispatchLogDetail(entry);
                    setDispatchLogDetailOpen(true);
                  }}
                />
              </Suspense>
            </Section>
          )}

      <AbilityLogDetailDialog
        detail={abilityLogDetail}
        visible={abilityLogDetailOpen}
        durationMs={abilityLogDetailDurationMs}
        resolveError={abilityLogResolveError}
        resolveLoading={abilityLogResolveLoading}
        onResolve={resolveAbilityLog}
        onClose={() => {
          setAbilityLogDetailOpen(false);
          setAbilityLogResolveError(null);
          setAbilityLogResolveLoading(false);
        }}
      />

      <DispatchLogDetailDialog
        detail={dispatchLogDetail}
        visible={dispatchLogDetailOpen}
        onClose={() => setDispatchLogDetailOpen(false)}
      />
      </div>
    </AdminShell>
  );
}

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

function Section({
  id,
  title,
  description,
  children,
}: {
  id?: string;
  title: string;
  description?: string;
  children: ReactNode;
}) {
  return (
    <section id={id} style={{ padding: '4px 0' }} className="podi-section">
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        <PageHeader title={title} description={description} />
        <div className="podi-section__body">{children}</div>
      </Space>
    </section>
  );
}

function InfoCard({ title, items }: { title: string; items: { label: string; value: string }[] }) {
  return (
    <Card title={title} bordered>
      <Space direction="vertical" size="small" style={{ width: '100%' }}>
        {items.map((item) => (
          <Row key={item.label} gutter={12} align="middle">
            <Col span={10}>
              <Typography.Text theme="secondary">{item.label}</Typography.Text>
            </Col>
            <Col span={14}>
              <Typography.Text>{item.value || '—'}</Typography.Text>
            </Col>
          </Row>
        ))}
      </Space>
    </Card>
  );
}
