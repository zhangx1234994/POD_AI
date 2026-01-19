import { useCallback, useEffect, useMemo, useState } from 'react';
import type { ChangeEvent, ReactNode } from 'react';
import { adminApi } from '../services/adminApi';
import { uploadAbilityTestFile } from '../utils/ossUploader';
import type {
  Ability,
  AbilityInvocationLog,
  AbilityFormState,
  ApiKey,
  ApiKeyFormState,
  Binding,
  BindingFormState,
  DashboardMetrics,
  DispatchLogEntry,
  Executor,
  ExecutorFormState,
  JsonRecord,
  JsonValue,
  PublicAbility,
  ComfyuiQueueStatus,
  SystemConfig,
  StoredAsset,
  Workflow,
  WorkflowFormState,
} from '../types/admin';
import type { UploadResult } from '../types/media';

const navItems = [
  { id: 'overview', label: '总体概览', description: '指标、刷新、运行状态' },
  { id: 'abilities', label: '能力目录', description: '原子能力列表与成本' },
  { id: 'ability-tests', label: '能力详情/测试', description: '链路自检与演示' },
  { id: 'executors', label: '执行节点', description: '节点配置与健康' },
  { id: 'ability-logs', label: '能力调用', description: '全局历史记录' },
  { id: 'comfyui-templates', label: 'ComfyUI 模板', description: 'Workflow JSON 管理' },
  { id: 'workflow-builder', label: '工作流编排', description: 'Coze Studio 工作流 + Loop 观测' },
  { id: 'bindings', label: '分配策略', description: 'action 绑定链路' },
  { id: 'apikeys', label: 'API Keys', description: '凭证配额管理' },
  { id: 'monitor', label: '调度监控', description: '队列/任务/节点健康' },
  { id: 'system', label: '系统配置', description: '环境、OSS、待办' },
  { id: 'logs', label: '调度事件', description: '任务追踪' },
] as const;
type NavId = (typeof navItems)[number]['id'];
const abilityDetailTabs = [
  { id: 'overview', label: '概览' },
  { id: 'params', label: '参数' },
  { id: 'metadata', label: '元信息' },
  { id: 'testing', label: '实时测试' },
  { id: 'logs', label: '调用记录' },
] as const;
type AbilityDetailTab = (typeof abilityDetailTabs)[number]['id'];

const defaultExecutorForm: ExecutorFormState = { status: 'inactive', weight: 1, max_concurrency: 1 };
const defaultWorkflowForm: WorkflowFormState = { action: '', name: '', version: 'v1', status: 'inactive', type: 'generic' };
const defaultBindingForm: BindingFormState = { enabled: true, priority: 0 };
const defaultApiKeyForm: ApiKeyFormState = { status: 'active' };
const providerOptions = [
  { value: 'baidu', label: '百度智能云' },
  { value: 'openai', label: 'OpenAI' },
  { value: 'aliyun', label: '阿里云' },
  { value: 'volcengine', label: '火山引擎' },
  { value: 'kie', label: 'KIE 中转' },
  { value: 'comfyui', label: 'ComfyUI 流程' },
  { value: 'coze', label: 'Coze Studio' },
];
const abilityTypeOptions = [
  { value: 'api', label: 'API 能力（HTTP 接口）' },
  { value: 'comfyui', label: 'ComfyUI 工作流' },
  { value: 'workflow', label: '内部工作流调度' },
  { value: 'tool', label: '工具/服务（PDI、校验等）' },
];
const categoryOptions = [
  { value: 'image_process', label: '图像处理' },
  { value: 'text_generation', label: '文本生成' },
  { value: 'speech', label: '语音/音频' },
  { value: 'video', label: '视频处理' },
  { value: 'other', label: '其他' },
];
const statusOptions = [
  { value: 'inactive', label: '未启用' },
  { value: 'active', label: '启用' },
  { value: 'deprecated', label: '下线' },
];
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
const resolveAbilityExecutors = (ability: Ability | null, availableExecutors: Executor[]): Executor[] => {
  if (!ability) return [];
  const hints = collectAbilityExecutorHints(ability);
  const normalizedHints = hints.length > 0 ? hints : [normalizeKey(ability.provider)];
  const matched = availableExecutors.filter((executor) => {
    const executorType = normalizeKey(executor.type);
    if (!executorType) return false;
    return normalizedHints.some((hint) => matchesExecutorHint(executorType, hint));
  });
  if (ability.executor_id) {
    const pinned = availableExecutors.find((executor) => executor.id === ability.executor_id);
    if (pinned) {
      return [pinned, ...matched.filter((executor) => executor.id !== pinned.id)];
    }
  }
  return matched;
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

const defaultAbilityForm: AbilityFormState = {
  provider: providerOptions[0].value,
  category: categoryOptions[0].value,
  capability_key: '',
  display_name: '',
  status: 'inactive',
  ability_type: abilityTypeOptions[0].value,
};

type AbilityTestForm = {
  abilityId: string | null;
  provider: string | null;
  capabilityKey: string | null;
  executorId: string | null;
  params: string;
  imageBase64: string;
  imageUrl: string;
};

type AbilityTestResultPayload = {
  provider?: string;
  model?: string;
  logId?: string | number;
  durationMs?: number;
  taskId?: string;
  state?: string;
  imageBase64?: string;
  imageUrl?: string;
  storedUrl?: string;
  resultUrls?: string[];
  assets?: StoredAsset[];
  text?: string;
  raw?: JsonRecord | null;
};

const defaultTestForm: AbilityTestForm = {
  abilityId: null,
  provider: null,
  capabilityKey: null,
  executorId: null,
  params: '',
  imageBase64: '',
  imageUrl: '',
};

const formatJsonValue = (value?: JsonRecord | null) => (value ? JSON.stringify(value, null, 2) : '');
const toImagePreview = (value?: string | null) => {
  if (!value) return '';
  return value.startsWith('data:') ? value : `data:image/png;base64,${value}`;
};
const abilityLogLimit = 12;
const formatDateTime = (value?: string | null) => {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('zh-CN', { hour12: false, timeZone: 'Asia/Shanghai' });
};
const formatDurationMs = (value?: number | null) => {
  if (value === undefined || value === null) return '—';
  if (value < 1000) return `${value}ms`;
  return `${(value / 1000).toFixed(2)}s`;
};
const getAbilityLogStatusClass = (status?: string | null) => {
  const normalized = (status || '').toLowerCase();
  if (normalized === 'success') return 'bg-emerald-500/15 text-emerald-300';
  if (normalized === 'failed') return 'bg-rose-500/15 text-rose-300';
  return 'bg-slate-600/30 text-slate-200';
};
const abilitySourceLabels: Record<string, string> = {
  'admin-test': '控制台测试',
  workflow: '工作流',
  task: '任务调度',
  'ability-api': '能力接口',
  'ability-task': '异步任务',
  'ability_api': '能力接口',
  'ability_task': '异步任务',
};
const formatAbilitySource = (value?: string | null) => {
  if (!value) return '未知来源';
  return abilitySourceLabels[value] ?? value;
};
const abilitySourceBadgeClasses: Record<string, string> = {
  'admin-test': 'bg-sky-500/20 text-sky-200',
  'ability-api': 'bg-indigo-500/20 text-indigo-200',
  'ability-task': 'bg-violet-500/20 text-violet-200',
  workflow: 'bg-emerald-500/20 text-emerald-200',
  task: 'bg-amber-500/20 text-amber-200',
};
const getAbilitySourceBadgeClass = (value?: string | null) => {
  if (!value) return 'bg-slate-700/60 text-slate-300';
  return abilitySourceBadgeClasses[value] ?? 'bg-slate-700/60 text-slate-300';
};
const resolveAssetUrl = (asset: StoredAsset) => asset.ossUrl || asset.url || asset.sourceUrl || '';
const formatTaskMarker = (value?: string | null) => {
  if (!value) return '';
  const trimmed = value.trim();
  if (trimmed.length <= 16) return trimmed;
  return `${trimmed.slice(0, 8)}…${trimmed.slice(-4)}`;
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
type AbilityPricing = {
  currency?: string;
  unit?: string;
  listPrice?: number;
  discountPrice?: number;
};

const allowedSchemaTypes: SchemaFieldType[] = ['text', 'textarea', 'select', 'number', 'switch', 'image'];
const allowedSchemaComponents: SchemaFieldComponent[] = ['select'];
const currencySymbolMap: Record<string, string> = { CNY: '¥', USD: '$', EUR: '€' };
const defaultComfyPricing: AbilityPricing = { currency: 'CNY', unit: 'per_image', listPrice: 0.5, discountPrice: 0.3 };

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

const formatUnitLabel = (unit?: string) => {
  if (!unit) return '每次';
  const map: Record<string, string> = {
    per_image: '每张',
    per_call: '每次',
    per_minute: '每分钟',
    per_hour: '每小时',
    per_token: '每千 Token',
  };
  return map[unit] ?? unit;
};

const formatPriceValue = (value?: number, currency?: string) => {
  if (typeof value !== 'number' || Number.isNaN(value)) return '—';
  const symbol = currency ? currencySymbolMap[currency] || currency : '';
  return `${symbol}${value.toFixed(2)}`;
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

export function IntegrationDashboard() {
  const [executors, setExecutors] = useState<Executor[]>([]);
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [bindings, setBindings] = useState<Binding[]>([]);
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([]);
  const [abilities, setAbilities] = useState<Ability[]>([]);
  const [loading, setLoading] = useState(false);
  const [activeNav, setActiveNav] = useState<NavId>(navItems[0].id);
  const [dashboardMetrics, setDashboardMetrics] = useState<DashboardMetrics | null>(null);
  const [dispatchLogs, setDispatchLogs] = useState<DispatchLogEntry[]>([]);
  const [systemConfig, setSystemConfig] = useState<SystemConfig | null>(null);
  const [abilityForm, setAbilityForm] = useState<AbilityFormState>(defaultAbilityForm);
  const [selectedAbilityId, setSelectedAbilityId] = useState<string | null>(null);
  const [abilitySearch, setAbilitySearch] = useState('');
  const [abilityProviderFilter, setAbilityProviderFilter] = useState<string>('all');
  const [abilityStatusFilter, setAbilityStatusFilter] = useState<string>('all');
  const [activeAbilityDetailTab, setActiveAbilityDetailTab] = useState<AbilityDetailTab>('overview');
  const [executorForm, setExecutorForm] = useState<ExecutorFormState>(defaultExecutorForm);
  const [workflowForm, setWorkflowForm] = useState<WorkflowFormState>(defaultWorkflowForm);
  const [workflowFormAllowedExecutors, setWorkflowFormAllowedExecutors] = useState<string[]>([]);
  const [bindingForm, setBindingForm] = useState<BindingFormState>(defaultBindingForm);
  const [apiKeyForm, setApiKeyForm] = useState<ApiKeyFormState>(defaultApiKeyForm);
  const [testForm, setTestForm] = useState<AbilityTestForm>(defaultTestForm);
  const [testResult, setTestResult] = useState<AbilityTestResultPayload | null>(null);
  const [testLoading, setTestLoading] = useState(false);
  const [schemaValues, setSchemaValues] = useState<SchemaFormValues>({});
  const [comfyModelCache, setComfyModelCache] = useState<Record<string, Record<string, string[]>>>({});
  const [comfyModelLoading, setComfyModelLoading] = useState(false);
  const [comfyModelError, setComfyModelError] = useState<string | null>(null);
  const [comfyQueueStatus, setComfyQueueStatus] = useState<ComfyuiQueueStatus | null>(null);
  const [comfyQueueLoading, setComfyQueueLoading] = useState(false);
  const [comfyQueueError, setComfyQueueError] = useState<string | null>(null);
  const [comfyQueueUpdatedAt, setComfyQueueUpdatedAt] = useState<string | null>(null);
  const [uploadingImage, setUploadingImage] = useState(false);
  const [uploadedImage, setUploadedImage] = useState<UploadResult | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [abilityLogs, setAbilityLogs] = useState<AbilityInvocationLog[]>([]);
  const [abilityLogsLoading, setAbilityLogsLoading] = useState(false);
  const [abilityLogsError, setAbilityLogsError] = useState<string | null>(null);
  const [globalAbilityLogs, setGlobalAbilityLogs] = useState<AbilityInvocationLog[]>([]);
  const [globalAbilityLogsLoading, setGlobalAbilityLogsLoading] = useState(false);
  const [globalAbilityLogsError, setGlobalAbilityLogsError] = useState<string | null>(null);
  const [publicAbilities, setPublicAbilities] = useState<PublicAbility[]>([]);
  const [publicAbilitiesLoading, setPublicAbilitiesLoading] = useState(false);

  const storedPreviewUrl = testResult?.storedUrl || (testResult?.assets && testResult.assets[0]?.ossUrl) || '';
  const fallbackResultUrl =
    storedPreviewUrl || (testResult?.resultUrls && testResult.resultUrls.length > 0 ? testResult.resultUrls[0] : '');
  const testResultPreviewSrc = testResult?.imageBase64
    ? toImagePreview(testResult.imageBase64)
    : testResult?.imageUrl || fallbackResultUrl || '';
  const hasTestResultPreview = Boolean(testResultPreviewSrc);

  // Derived lists to simplify rendering; declared before effects to avoid TDZ issues.
  const abilityProviders = useMemo(
    () => Array.from(new Set(abilities.map((ability) => ability.provider))).sort(),
    [abilities],
  );
  const filteredAbilities = useMemo(() => {
    const keyword = abilitySearch.trim().toLowerCase();
    return abilities.filter((ability) => {
      if (abilityProviderFilter !== 'all' && ability.provider !== abilityProviderFilter) return false;
      if (abilityStatusFilter !== 'all' && ability.status !== abilityStatusFilter) return false;
      if (!keyword) return true;
      const haystack = `${ability.display_name} ${ability.capability_key} ${ability.description || ''}`.toLowerCase();
      return haystack.includes(keyword);
    });
  }, [abilities, abilityProviderFilter, abilityStatusFilter, abilitySearch]);
  const selectedAbility = useMemo(() => {
    if (!selectedAbilityId) return null;
    return abilities.find((ability) => ability.id === selectedAbilityId) ?? null;
  }, [abilities, selectedAbilityId]);
  const selectedAbilityMetadata = (selectedAbility?.metadata || {}) as Record<string, unknown>;
  const abilityExecutors = useMemo(
    () => resolveAbilityExecutors(selectedAbility, executors),
    [selectedAbility, executors],
  );
  const comfyExecutors = useMemo(
    () => executors.filter((executor) => (executor.type || '').toLowerCase().includes('comfyui')),
    [executors],
  );
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
  const abilitySchemaFields = useMemo(
    () => parseAbilitySchemaFields(selectedAbility?.input_schema),
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
  const renderedSchemaFields = useMemo(() => {
    if (!abilitySchemaFields.length) return abilitySchemaFields;
    return abilitySchemaFields.map((field) => {
      const dynamicOptions = comfyModelOptionsByField[field.name];
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
  }, [abilitySchemaFields, comfyModelOptionsByField]);
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

  const load = async () => {
    setLoading(true);
    try {
      const [execRes, wfRes, bindingRes, apiKeyRes, metricsRes, logsRes, configRes, abilityRes] = await Promise.all([
        adminApi.listExecutors(),
        adminApi.listWorkflows(),
        adminApi.listBindings(),
        adminApi.listApiKeys(),
        adminApi.getDashboardMetrics(),
        adminApi.getDispatchLogs(),
        adminApi.getSystemConfig(),
        adminApi.listAbilities(),
      ]);
      setExecutors(execRes);
      setWorkflows(wfRes);
      setBindings(bindingRes);
      setApiKeys(apiKeyRes);
      setAbilities(abilityRes);
      setDashboardMetrics(metricsRes);
      setDispatchLogs(logsRes.entries);
      setSystemConfig(configRes);
      if (abilityRes.length > 0) {
        if (!selectedAbilityId || !abilityRes.some((item) => item.id === selectedAbilityId)) {
          setSelectedAbilityId(abilityRes[0].id);
        }
      } else {
        setSelectedAbilityId(null);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

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
        console.error('Failed to load ComfyUI models:', error);
        setComfyModelError(error.message || '获取模型列表失败');
      })
      .finally(() => {
        if (!cancelled) setComfyModelLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedAbility?.provider, activeComfyExecutorId, comfyModelCache]);

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
    if (selectedAbility?.provider !== 'comfyui' || !activeComfyExecutorId) {
      setComfyQueueStatus(null);
      setComfyQueueError(null);
      setComfyQueueUpdatedAt(null);
      setComfyQueueLoading(false);
      return;
    }
    let cancelled = false;
    const run = async (silent?: boolean) => {
      if (cancelled) return;
      await refreshComfyQueueStatus({ silent });
    };
    void run(false);
    const interval = window.setInterval(() => {
      void run(true);
    }, 15000);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [refreshComfyQueueStatus, selectedAbility?.provider, activeComfyExecutorId]);

  const copyTextToClipboard = async (value: string) => {
    try {
      await navigator.clipboard.writeText(value);
    } catch (error) {
      console.error('copy text failed', error);
    }
  };
  const refreshAbilityLogs = useCallback(async () => {
    if (!selectedAbility?.id) {
      setAbilityLogs([]);
      setAbilityLogsError(null);
      return;
    }
    setAbilityLogsLoading(true);
    try {
      const response = await adminApi.listAbilityLogs(selectedAbility.id, abilityLogLimit);
      setAbilityLogs(response.items);
      setAbilityLogsError(null);
    } catch (error) {
      console.error('load ability logs failed', error);
      setAbilityLogsError(error instanceof Error ? error.message : '加载能力调用记录失败');
    } finally {
      setAbilityLogsLoading(false);
    }
  }, [selectedAbility?.id]);

  useEffect(() => {
    void refreshAbilityLogs();
  }, [refreshAbilityLogs]);

  const refreshGlobalAbilityLogs = useCallback(async () => {
    setGlobalAbilityLogsLoading(true);
    try {
      const response = await adminApi.listAllAbilityLogs({ limit: 30 });
      setGlobalAbilityLogs(response.items);
      setGlobalAbilityLogsError(null);
    } catch (error) {
      console.error('load global ability logs failed', error);
      setGlobalAbilityLogsError(error instanceof Error ? error.message : '加载能力调用清单失败');
    } finally {
      setGlobalAbilityLogsLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshGlobalAbilityLogs();
  }, [refreshGlobalAbilityLogs]);

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

  const parseJSON = (value?: string | JsonRecord): JsonRecord => {
    if (!value) return {};
    if (typeof value === 'object') return value;
    try {
      return JSON.parse(value);
    } catch {
      return {};
    }
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

  useEffect(() => {
    setWorkflowFormAllowedExecutors(extractAllowedExecutorIds(workflowForm.metadata));
  }, [workflowForm.metadata]);

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
    const payload: Partial<Ability> = {
      provider: abilityForm.provider,
      category: abilityForm.category,
      capability_key: abilityForm.capability_key,
      display_name: abilityForm.display_name,
      description: abilityForm.description,
      status: abilityForm.status,
      ability_type: abilityForm.ability_type || abilityTypeOptions[0].value,
      executor_id: abilityForm.executor_id,
      workflow_id: abilityForm.workflow_id || undefined,
      coze_workflow_id: abilityForm.coze_workflow_id || undefined,
      default_params: abilityForm.default_params ? parseJSON(abilityForm.default_params) : undefined,
      input_schema: abilityForm.input_schema ? parseJSON(abilityForm.input_schema) : undefined,
      metadata: abilityForm.metadata ? parseJSON(abilityForm.metadata) : undefined,
    };
    if (abilityForm.id) {
      await adminApi.updateAbility(abilityForm.id, payload);
    } else {
      await adminApi.createAbility({ ...payload, id: abilityForm.id || undefined });
    }
    setAbilityForm(defaultAbilityForm);
    load();
  };

  const handleAbilityEdit = (ability: Ability) => {
    setAbilityForm({
      ...ability,
      ability_type: ability.ability_type || abilityTypeOptions[0].value,
      workflow_id: ability.workflow_id || undefined,
      default_params: formatJsonValue(ability.default_params),
      input_schema: formatJsonValue(ability.input_schema),
      metadata: formatJsonValue(ability.metadata),
    });
  };

  const handleAbilityDelete = async (id: string) => {
    await adminApi.deleteAbility(id);
    load();
  };

  const handleTestFile = async (files: FileList | null) => {
    if (!files || !files[0]) return;
    const file = files[0];
    setUploadingImage(true);
    setUploadError(null);
    try {
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
        });
        setTestResult({
          provider: response.provider,
          model: response.workflowKey,
          taskId: response.promptId,
          logId: response.logId ?? undefined,
          storedUrl: response.storedUrl ?? (response.assets && response.assets[0]?.ossUrl) ?? undefined,
          assets: response.assets ?? undefined,
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
          'input_urls',
          'aspect_ratio',
          'resolution',
          'output_format',
          'callBackUrl',
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
          const mergedImageValue = mergedPicked.image_urls ?? mergedPicked.input_urls;
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
          const aspectRatio = getPickedString('aspect_ratio');
          if (aspectRatio) inputPayload.aspect_ratio = aspectRatio;
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
const formatRawResponse = (record?: JsonRecord | null, max = 2000) => {
  if (!record) return '';
  const raw = stringifyJSON(record);
  return raw.length > max ? `${raw.slice(0, max)}…` : raw;
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
const normalizeErrorMessage = (message: string): string => {
  if (!message) return '';
  const trimmed = message.trim();
  try {
    const parsed = JSON.parse(trimmed);
    if (parsed?.detail) {
      return typeof parsed.detail === 'string' ? parsed.detail : JSON.stringify(parsed.detail);
    }
  } catch {
    // ignore
  }
  return trimmed;
};

  const handleExecutorSubmit = async () => {
    if (!executorForm.name || !executorForm.type) return;
    const { config, ...rest } = executorForm;
    const payload: Partial<Executor> = {
      ...rest,
      ...(config ? { config: parseJSON(config) } : {}),
    };
    if (executorForm.id) {
      await adminApi.updateExecutor(executorForm.id, payload);
    } else {
      await adminApi.createExecutor(payload);
    }
    setExecutorForm(defaultExecutorForm);
    load();
  };

  const handleWorkflowSubmit = async () => {
    if (!workflowForm.name || !workflowForm.action) return;
    const { definition, metadata, ...rest } = workflowForm;
    const definitionPayload = definition ? parseJSON(definition) : undefined;
    const metadataPayload = metadata ? parseJSON(metadata) : {};
    if (workflowFormAllowedExecutors.length > 0) {
      metadataPayload.allowed_executor_ids = workflowFormAllowedExecutors;
    } else {
      delete metadataPayload.allowed_executor_ids;
    }
    const payload: Partial<Workflow> = {
      ...rest,
      ...(definitionPayload ? { definition: definitionPayload } : {}),
      ...(Object.keys(metadataPayload).length > 0 ? { metadata: metadataPayload } : {}),
    };
    if (workflowForm.id) {
      await adminApi.updateWorkflow(workflowForm.id, payload);
    } else {
      await adminApi.createWorkflow(payload);
    }
    setWorkflowForm(defaultWorkflowForm);
    setWorkflowFormAllowedExecutors([]);
    load();
  };

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
    if (apiKeyForm.id) {
      await adminApi.updateApiKey(apiKeyForm.id, apiKeyForm);
    } else if (apiKeyForm.key) {
      await adminApi.createApiKey(apiKeyForm);
    } else {
      return;
    }
    setApiKeyForm(defaultApiKeyForm);
    load();
  };

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

  const handleWorkflowFile = (files: FileList | null) => {
    if (!files || !files[0]) return;
    const file = files[0];
    const reader = new FileReader();
    reader.onload = (event) => {
      try {
        const json = JSON.parse(event.target?.result as string);
        setWorkflowForm((prev) => ({
          ...prev,
          definition: JSON.stringify(json, null, 2),
        }));
      } catch (error) {
        console.error(error);
      }
    };
    reader.readAsText(file);
  };

  const CUSTOM_SELECT_VALUE = '__custom__';

  const renderSchemaField = (field: AbilitySchemaField) => {
    const rawValue = schemaValues[field.name];
    const label = `${field.label}${field.required ? ' *' : ''}`;
    const description = field.description;
    const placeholder = field.placeholder;
    if (field.type === 'switch') {
      return (
        <label
          key={field.name}
          className="flex items-center justify-between rounded-2xl border border-slate-800 bg-slate-950/40 px-4 py-3 text-xs text-slate-300"
        >
          <div>
            <div className="font-semibold text-slate-100">{label}</div>
            {description && <div className="text-[11px] text-slate-500">{description}</div>}
          </div>
          <input
            type="checkbox"
            checked={Boolean(rawValue)}
            onChange={(e) => setSchemaValues((prev) => ({ ...prev, [field.name]: e.target.checked }))}
            className="h-5 w-5 rounded border border-slate-600 bg-slate-900"
          />
        </label>
      );
    }
    if (field.type === 'textarea') {
      const value = typeof rawValue === 'string' ? rawValue : rawValue ? String(rawValue) : '';
      return (
        <label key={field.name} className="block text-xs text-slate-400">
          {label}
          <textarea
            rows={4}
            value={value}
            placeholder={placeholder}
            onChange={(e) => setSchemaValues((prev) => ({ ...prev, [field.name]: e.target.value }))}
            className="mt-1 w-full rounded-2xl border border-slate-700 bg-slate-950/70 px-4 py-3 text-sm text-white"
          />
          {description && <p className="mt-1 text-[11px] text-slate-500">{description}</p>}
        </label>
      );
    }
    if (field.type === 'select' && field.options && field.options.length > 0) {
      const value = typeof rawValue === 'string' ? rawValue : rawValue ? String(rawValue) : '';
      const optionValues = field.options.map((option) => option.value);
      const allowCustom = Boolean(field.allowCustomValue);
      const isCustomValue = allowCustom && Boolean(value) && !optionValues.includes(value);
      const selectValue = isCustomValue ? CUSTOM_SELECT_VALUE : value;
      const handleSelectChange = (event: ChangeEvent<HTMLSelectElement>) => {
        const selected = event.target.value;
        if (allowCustom && selected === CUSTOM_SELECT_VALUE) {
          setSchemaValues((prev) => ({
            ...prev,
            [field.name]: isCustomValue ? value : '',
          }));
          return;
        }
        setSchemaValues((prev) => ({ ...prev, [field.name]: selected }));
      };
      return (
        <label key={field.name} className="block text-xs text-slate-400">
          {label}
          <select
            value={selectValue}
            onChange={handleSelectChange}
            className="mt-1 w-full rounded-2xl border border-slate-700 bg-slate-950/70 px-4 py-3 text-white"
          >
            <option value="">请选择</option>
            {field.options.map((option) => (
              <option key={`${field.name}-${option.value}`} value={option.value}>
                {option.label}
              </option>
            ))}
            {allowCustom && (
              <option value={CUSTOM_SELECT_VALUE}>
                自定义 {field.label.replace(/[*\\s]/g, '') || '选项'}
              </option>
            )}
          </select>
          {allowCustom && (isCustomValue || selectValue === CUSTOM_SELECT_VALUE) && (
            <input
              type="text"
              value={value}
              placeholder="输入自定义值，例如其他 LoRA 文件"
              onChange={(e) => setSchemaValues((prev) => ({ ...prev, [field.name]: e.target.value }))}
              className="mt-2 w-full rounded-2xl border border-slate-700 bg-slate-950/70 px-4 py-3 text-white"
            />
          )}
          {description && <p className="mt-1 text-[11px] text-slate-500">{description}</p>}
        </label>
      );
    }
    const value = typeof rawValue === 'string' ? rawValue : rawValue ? String(rawValue) : '';
    const inputType = field.type === 'number' ? 'number' : 'text';
    const hasOptions = field.options && field.options.length > 0;
    const datalistId = hasOptions ? `schema-${field.name}-options` : undefined;
    return (
      <label key={field.name} className="block text-xs text-slate-400">
        {label}
        <input
          type={inputType}
          value={value}
          placeholder={placeholder}
          list={inputType === 'text' && hasOptions ? datalistId : undefined}
          onChange={(e) => setSchemaValues((prev) => ({ ...prev, [field.name]: e.target.value }))}
          className="mt-1 w-full rounded-2xl border border-slate-700 bg-slate-950/70 px-4 py-3 text-white"
        />
        {hasOptions && inputType === 'text' && datalistId && (
          <datalist id={datalistId}>
            {field.options!.map((option) => (
              <option key={`${field.name}-${option.value}`} value={option.value}>
                {option.label}
              </option>
            ))}
          </datalist>
        )}
        {description && <p className="mt-1 text-[11px] text-slate-500">{description}</p>}
      </label>
    );
  };

  const renderAbilityOverview = () => {
    if (!selectedAbility) {
      return (
        <div className="rounded-2xl border border-dashed border-slate-700 bg-slate-950/30 p-4 text-sm text-slate-400">
          请先在左侧“能力目录”中选中一条能力，系统会在此处展示能力描述、默认节点、成本与标签。
        </div>
      );
    }
    return (
      <div className="space-y-4">
        <div className="rounded-2xl border border-slate-800 bg-slate-950/40 p-4 space-y-3">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-xs uppercase tracking-widest text-slate-500">
                {getProviderLabel(selectedAbility.provider)} · {getCategoryLabel(selectedAbility.category)}
              </p>
              <h4 className="mt-1 text-lg font-semibold text-white">{selectedAbility.display_name}</h4>
              <p className="mt-1 text-xs text-slate-400">
                每个 Ability 都是一个原子能力（API、ComfyUI 或第三方服务），下游工作流只需要引用 Ability ID 即可复用配置。
              </p>
            </div>
            <StatusPill status={selectedAbility.status} />
          </div>
          <p className="text-xs text-slate-400">
            {selectedAbility.description || '暂无描述，建议在能力管理中补充。'}
          </p>
          {selectedAbilityTags.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {selectedAbilityTags.map((tag, index) => (
                <span
                  key={`selected-ability-tag-${index}`}
                  className="rounded-full border border-sky-500/40 px-2 py-0.5 text-[10px] uppercase tracking-wide text-sky-200"
                >
                  {tag}
                </span>
              ))}
            </div>
          )}
          <dl className="grid gap-3 text-xs text-slate-400 sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <dt className="uppercase tracking-wide text-slate-500">能力 Key</dt>
              <dd className="mt-1 font-mono text-sm text-white">{selectedAbility.capability_key}</dd>
            </div>
            <div>
              <dt className="uppercase tracking-wide text-slate-500">能力类型</dt>
              <dd className="mt-1 text-white">{getAbilityTypeLabel(selectedAbility.ability_type)}</dd>
            </div>
            <div>
              <dt className="uppercase tracking-wide text-slate-500">默认节点</dt>
              <dd className="mt-1 text-white">
                {pinnedAbilityExecutor
                  ? `${pinnedAbilityExecutor.name} · ${pinnedAbilityExecutor.type}`
                  : '按厂商类型自动匹配'}
              </dd>
            </div>
            <div>
              <dt className="uppercase tracking-wide text-slate-500">关联工作流</dt>
              <dd className="mt-1 text-white">{selectedAbilityWorkflowLabel || '未绑定'}</dd>
            </div>
          </dl>
          <div className="rounded-2xl border border-slate-800 bg-slate-950/40 p-3 text-xs text-slate-400">
            <div className="text-slate-500">计价信息</div>
            <div className="mt-1 text-sm text-white">{selectedAbilityPricingText}</div>
            {selectedAbilityPricingText === '—' && (
              <p className="text-[11px] text-slate-500">
                可在 Metadata.pricing 中设置 `currency/unit/list_price/discount_price`，ComfyUI 默认按 ¥0.30 / 每张计算。
              </p>
            )}
          </div>
        </div>
        <div className="grid gap-3 md:grid-cols-2">
          <div className="rounded-2xl border border-slate-800 bg-slate-950/40 p-4 text-xs text-slate-400">
            <div className="text-[11px] uppercase tracking-widest text-slate-500">健康巡检</div>
            <p className="mt-2 text-sm text-white">{selectedAbilityHealth.status}</p>
            <p className="mt-1 text-[11px] text-slate-500">最近巡检：{selectedAbilityHealth.checkedAt}</p>
            <p className="mt-1 text-[11px] text-slate-500">可通过能力测试或自动巡检任务刷新该状态。</p>
          </div>
          <div className="rounded-2xl border border-slate-800 bg-slate-950/40 p-4 text-xs text-slate-400">
            <div className="text-[11px] uppercase tracking-widest text-slate-500">成功率 (近 24h)</div>
            <p className="mt-2 text-sm text-white">{selectedAbilityHealth.successRateText}</p>
            <p className="mt-1 text-[11px] text-slate-500">
              数据来源于 ability_invocation_logs，可在“能力调用记录”中查看明细。
            </p>
          </div>
        </div>
      </div>
    );
  };

  const renderAbilityParamsTab = () => {
    if (!selectedAbility) {
      return (
        <div className="rounded-2xl border border-dashed border-slate-700 bg-slate-950/30 p-4 text-sm text-slate-400">
          请在能力目录中选择一个能力后查看默认参数与动态 Schema。
        </div>
      );
    }
    return (
      <div className="space-y-4 text-xs text-slate-400">
        <div>
          <div className="text-slate-500">默认参数</div>
          {selectedAbility.default_params ? (
            <pre className="mt-1 max-h-64 overflow-auto rounded-2xl border border-slate-800 bg-slate-950/60 p-3 font-mono text-[11px] text-slate-200">
              {formatJsonValue(selectedAbility.default_params)}
            </pre>
          ) : (
            <p className="mt-1">未配置，测试时可以在实时测试 Tab 的 JSON 输入框补充。</p>
          )}
        </div>
        <div>
          <div className="text-slate-500">输入 Schema</div>
          {selectedAbility.input_schema ? (
            <pre className="mt-1 max-h-64 overflow-auto rounded-2xl border border-slate-800 bg-slate-950/60 p-3 font-mono text-[11px] text-slate-200">
              {formatJsonValue(selectedAbility.input_schema)}
            </pre>
          ) : (
            <p className="mt-1">尚未提供 Schema，表单将仅展示 JSON 编辑区。</p>
          )}
        </div>
      </div>
    );
  };

  const renderAbilityMetadataTab = () => {
    if (!selectedAbility) {
      return (
        <div className="rounded-2xl border border-dashed border-slate-700 bg-slate-950/30 p-4 text-sm text-slate-400">
          请选择能力以查看 metadata/workflow_key/pricing 等元信息。
        </div>
      );
    }
    return (
      <div className="space-y-4 text-xs text-slate-400">
        <div>
          <div className="text-slate-500">能力 Metadata</div>
          {selectedAbility.metadata ? (
            <pre className="mt-1 max-h-80 overflow-auto rounded-2xl border border-slate-800 bg-slate-950/60 p-3 font-mono text-[11px] text-slate-200">
              {formatJsonValue(selectedAbility.metadata)}
            </pre>
          ) : (
            <p className="mt-1">暂无 metadata，建议补充 workflow_key、api_type、pricing、requirements 等信息。</p>
          )}
        </div>
        <div className="rounded-2xl border border-slate-800 bg-slate-950/40 p-4 text-[11px] text-slate-400 space-y-1">
          <div className="text-[11px] uppercase tracking-widest text-slate-500">调度 / 成本要点</div>
          <p>能力类型：{getAbilityTypeLabel(selectedAbility.ability_type)}</p>
          <p>关联 Workflow：{selectedAbilityWorkflowLabel || '未绑定'}</p>
          <p>最近健康检查：{selectedAbilityHealth.checkedAt}</p>
          <p>成功率：{selectedAbilityHealth.successRateText}</p>
          <p>计价：{selectedAbilityPricingText}</p>
        </div>
      </div>
    );
  };

  const renderAbilityTestingTab = () => {
    if (!selectedAbility) {
      return (
        <div className="rounded-2xl border border-dashed border-slate-700 bg-slate-950/30 p-4 text-sm text-slate-400">
          请在左侧能力列表中选择一条能力后，再运行链路自检。
        </div>
      );
    }
    return (
      <div className="space-y-4 text-sm">
        <div className="rounded-2xl border border-slate-800 bg-slate-950/40 p-3 text-xs text-slate-400">
          当前能力：<span className="text-white">{selectedAbility.display_name}</span>（{getProviderLabel(selectedAbility.provider)}）；
          这里仅用于链路巡检 / 运营测试，实际业务仍应通过能力接口或工作流调度调用。
        </div>
        <StepTitle index={1} label="选择接入节点" hint="系统按厂商/标签优先匹配" />
        <div className="rounded-2xl border border-slate-800 bg-slate-950/50 p-4 space-y-2">
          <select
            value={abilityExecutors.length === 0 ? '' : testForm.executorId ?? abilityExecutors[0]?.id ?? ''}
            disabled={abilityExecutors.length === 0}
            onChange={(e) => setTestForm((prev) => ({ ...prev, executorId: e.target.value || null }))}
            className="w-full rounded-2xl border border-slate-700 bg-slate-950/70 px-4 py-3 text-white disabled:cursor-not-allowed disabled:border-slate-800 disabled:text-slate-500"
          >
            {abilityExecutors.length === 0 ? (
              <option value="">暂无匹配节点</option>
            ) : (
              abilityExecutors.map((executor) => (
                <option key={executor.id} value={executor.id}>
                  {executor.name} · {executor.type}
                </option>
              ))
            )}
          </select>
          {abilityExecutors.length === 0 && (
            <p className="text-xs text-amber-400">
              暂无 {getProviderLabel(selectedAbility.provider)} 类型/标签匹配的节点，请先前往“执行节点”创建并配置该厂商的 Key/Secret。
            </p>
          )}
        </div>
        {selectedAbility.provider === 'comfyui' && activeComfyExecutorId && (
          <div className="rounded-2xl border border-sky-900/40 bg-slate-950/40 p-4 text-xs text-slate-300 space-y-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <p className="text-sm font-semibold text-white">ComfyUI 队列状态</p>
                <p className="text-[11px] text-slate-500">
                  节点：<span className="font-mono">{activeComfyExecutorId}</span>
                </p>
              </div>
              <button
                type="button"
                onClick={() => refreshComfyQueueStatus()}
                className="rounded-full border border-slate-600 px-3 py-1 text-[11px] text-slate-100 hover:border-slate-400"
                disabled={comfyQueueLoading}
              >
                {comfyQueueLoading ? '刷新中…' : '刷新'}
              </button>
            </div>
            {comfyQueueError ? (
              <p className="text-rose-400 text-xs">{comfyQueueError}</p>
            ) : comfyQueueStatus ? (
              <>
                <div className="grid grid-cols-3 gap-3 text-center text-slate-200">
                  <div className="rounded-2xl border border-slate-800/70 bg-slate-950/60 p-3">
                    <div className="text-[11px] uppercase tracking-widest text-slate-500">运行中</div>
                    <div className="mt-1 text-2xl font-semibold">{comfyQueueStatus.runningCount}</div>
                  </div>
                  <div className="rounded-2xl border border-slate-800/70 bg-slate-950/60 p-3">
                    <div className="text-[11px] uppercase tracking-widest text-slate-500">排队中</div>
                    <div className="mt-1 text-2xl font-semibold">{comfyQueueStatus.pendingCount}</div>
                  </div>
                  <div className="rounded-2xl border border-slate-800/70 bg-slate-950/60 p-3">
                    <div className="text-[11px] uppercase tracking-widest text-slate-500">队列上限</div>
                    <div className="mt-1 text-2xl font-semibold">
                      {typeof comfyQueueStatus.queueMaxSize === 'number' ? comfyQueueStatus.queueMaxSize : '—'}
                    </div>
                  </div>
                </div>
                <div className="text-[11px] text-slate-500">基座：{comfyQueueStatus.baseUrl || '—'}</div>
                <div className="text-[11px] text-slate-500">
                  最近刷新：{comfyQueueUpdatedAt ? formatDateTime(comfyQueueUpdatedAt) : '刚刚'}
                </div>
                {comfyQueueStatus.supported === false ? (
                  <p className="text-[11px] text-amber-400">
                    {comfyQueueStatus.message || '该 ComfyUI 版本未暴露 /queue/status，暂无法获取排队情况。'}
                  </p>
                ) : (
                  <p className="text-[11px] text-slate-500">
                    ComfyUI 默认单 worker 顺序执行，排队数量 &gt; 0 时说明仍在处理前序任务，可错峰提交或切换其他节点。
                  </p>
                )}
              </>
            ) : (
              <p className="text-xs text-slate-500">
                {comfyQueueLoading ? '正在获取队列状态…' : '暂无实时数据，稍后自动刷新。'}
              </p>
            )}
          </div>
        )}
        <StepTitle index={2} label="准备输入" />
        {abilityAllowsImageInput ? (
          <>
            <label className="text-xs text-slate-400">
              图片 URL（可选）
              <input
                type="text"
                value={testForm.imageUrl}
                onChange={(e) => handleImageUrlInput(e.target.value)}
                className="mt-1 w-full rounded-2xl border border-slate-700 bg-slate-950/70 px-4 py-3 text-white placeholder:text-slate-600"
                placeholder="https://xxx.example.com/image.png"
              />
            </label>
            <label className="text-xs text-slate-400">
              上传图片（或拖拽）
              <input
                type="file"
                accept="image/*"
                onChange={(e) => handleTestFile(e.target.files)}
                className="mt-1 block w-full rounded-2xl border border-dashed border-slate-600 bg-slate-950/40 px-4 py-3 text-white"
              />
            </label>
            {uploadingImage && <p className="text-xs text-sky-400">上传中，请稍候…</p>}
            {uploadedImage && !uploadingImage && (
              <p className="text-xs text-emerald-400">
                已上传：{uploadedImage.name}（{(uploadedImage.size / 1024).toFixed(1)} KB）
              </p>
            )}
            {uploadError && <p className="text-xs text-rose-400">{uploadError}</p>}
            <p className="text-xs text-slate-500">
              上传的文件会暂存到 OSS（podi/test/…），我们会优先使用该 URL；若接口不支持 URL，将自动回退为 Base64。
              {abilityRequiresImageInput ? '本能力为必填输入。' : '若该厂商支持视觉输入，可选填。'}
            </p>
          </>
        ) : (
          <p className="text-xs text-slate-500">该能力不需要图片输入，请直接在下方填写参数或使用默认配置。</p>
        )}
        <StepTitle index={3} label="调节参数（可选）" hint="默认值来自能力配置" />
        {renderedSchemaFields.length > 0 && (
          <div className="rounded-2xl border border-slate-800 bg-slate-950/40 p-4 space-y-3">
            <p className="text-xs text-slate-400">表单由能力输入 Schema 自动生成，可快速调整提示词、尺寸等关键参数。</p>
            {selectedAbility.provider === 'comfyui' && activeComfyExecutorId && (
              <p className="text-[11px] text-slate-500">
                {comfyModelLoading
                  ? '正在同步该执行节点的模型/LoRA 列表…'
                  : comfyModelError
                    ? `模型列表读取失败：${comfyModelError}`
                    : comfyModelCache[activeComfyExecutorId]
                      ? '模型/LoRA 列表已载入，可直接从下拉选项选择或手动输入。'
                      : '正在准备模型/LoRA 列表…'}
              </p>
            )}
            <div className="space-y-3">{renderedSchemaFields.map((field) => renderSchemaField(field))}</div>
          </div>
        )}
        <label className="text-xs text-slate-400">
          附加参数 JSON（覆盖默认值）
          <textarea
            rows={renderedSchemaFields.length > 0 ? 4 : 6}
            className="mt-1 w-full rounded-2xl border border-slate-700 bg-slate-950/60 p-3 text-xs text-white font-mono"
            placeholder='例如 {"temperature":0.6,"top_p":0.8}'
            value={testForm.params}
            onChange={(e) => setTestForm((prev) => ({ ...prev, params: e.target.value }))}
          />
        </label>
        <button
          onClick={handleRunAbilityTest}
          disabled={
            testLoading ||
            !selectedAbility ||
            !testForm.executorId ||
            (abilityRequiresImageInput && !testForm.imageBase64 && !testForm.imageUrl)
          }
          className="w-full rounded-2xl bg-gradient-to-r from-sky-500 to-indigo-500 px-4 py-3 text-white font-semibold disabled:opacity-40"
        >
          {testLoading ? '测试中…' : selectedAbility ? `运行：${selectedAbility.display_name}` : '请选择能力'}
        </button>
        {!testForm.executorId && (
          <p className="text-xs text-amber-400">
            {abilityExecutors.length === 0
              ? '请先在“执行节点”中新建该厂商的节点，并填入 API Key/Secret。'
              : '请选择一个执行节点，才能带着正确的 Key/Secret 调用接口。'}
          </p>
        )}
        {abilityRequiresImageInput && !testForm.imageBase64 && !testForm.imageUrl && (
          <p className="text-xs text-amber-400">该能力需要图片，请上传或填写一个可访问的 URL。</p>
        )}
        <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-4">
          <h3 className="text-lg font-semibold text-white mb-3">测试结果</h3>
          {testResult ? (
            <>
              {hasTestResultPreview && (
                <img src={testResultPreviewSrc} alt="test-result" className="w-full max-h-[360px] rounded object-contain" />
              )}
              {testResult.text && (
                <div className="mt-3 rounded-2xl border border-slate-800 bg-slate-950/40 p-4 text-sm text-slate-100 whitespace-pre-line">
                  {testResult.text}
                </div>
              )}
              <div className="mt-3 space-y-1 text-xs text-slate-400">
                {testResult.provider && <div>厂商：{getProviderLabel(testResult.provider)}</div>}
                {testResult.model && <div>模型：{testResult.model}</div>}
                {testResult.state && <div>状态：{testResult.state}</div>}
                {testResult.taskId && (
                  <div className="break-all">
                    任务 ID：<span className="font-mono text-slate-200">{testResult.taskId}</span>
                  </div>
                )}
                {testResult.logId && <div>Log ID：{testResult.logId}</div>}
                {typeof testResult.durationMs === 'number' && <div>耗时：{testResult.durationMs} ms</div>}
                {testResult.storedUrl && (
                  <div>
                    OSS 预览：
                    <a href={testResult.storedUrl} target="_blank" rel="noreferrer" className="text-emerald-400 underline">
                      打开
                    </a>
                  </div>
                )}
                {testResult.imageUrl && !testResult.imageBase64 && (
                  <div>
                    厂商预览：
                    <a href={testResult.imageUrl} target="_blank" rel="noreferrer" className="text-sky-400 underline">
                      打开
                    </a>
                  </div>
                )}
              </div>
              {testResult.assets && testResult.assets.length > 0 && (
                <div className="mt-3 rounded-2xl border border-slate-800 bg-slate-950/40 p-3 text-xs text-slate-300">
                  <div className="text-slate-200">已同步至 OSS</div>
                  <ul className="mt-2 space-y-1">
                    {testResult.assets.map((asset, index) => (
                      <li key={asset.ossKey || index} className="break-all">
                        <span className="text-slate-500">[{asset.tag || `asset-${index + 1}`}] </span>
                        <a href={asset.ossUrl} target="_blank" rel="noreferrer" className="text-emerald-400 underline">
                          {asset.ossUrl}
                        </a>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {testResult.resultUrls && testResult.resultUrls.length > 0 && (
                <div className="mt-3 rounded-2xl border border-slate-800 bg-slate-950/40 p-3 text-xs text-slate-300">
                  <div className="text-slate-200">厂商原始链接</div>
                  <ul className="mt-2 space-y-1">
                    {testResult.resultUrls.map((url, index) => (
                      <li key={`result-url-${index}`} className="break-all">
                        <a href={url} target="_blank" rel="noreferrer" className="text-sky-400 underline">
                          {url}
                        </a>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {testResult.raw && (
                <details className="mt-3 rounded-2xl border border-slate-800 bg-slate-950/40 p-3 text-xs text-slate-300">
                  <summary className="cursor-pointer text-slate-200">查看原始响应</summary>
                  <pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap font-mono text-[11px] text-slate-300">
                    {formatRawResponse(testResult.raw)}
                  </pre>
                </details>
              )}
              {!hasTestResultPreview && !testResult.text && (
                <div className="mt-4 text-sm text-slate-500">调用完成但未返回可预览内容，可展开原始响应确认详情。</div>
              )}
            </>
          ) : (
            <div className="text-sm text-slate-500">
              步骤填写完成后点击“运行测试”，结果会在此处预览；如需保存到任务列表，请改用正式任务流程。
            </div>
          )}
        </div>
      </div>
    );
  };

  const renderAbilityDetailContent = () => {
    switch (activeAbilityDetailTab) {
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

  const renderAbilityLogsTab = () => {
    if (!selectedAbility) {
      return (
        <div className="rounded-2xl border border-dashed border-slate-700 bg-slate-950/30 p-4 text-sm text-slate-400">
          请选择能力后查看最近的调用记录。
        </div>
      );
    }
    return (
      <div className="rounded-2xl border border-slate-800 bg-slate-900/30 p-4">
        <div className="mb-3 flex items-center justify-between gap-4">
          <div>
            <h4 className="text-lg font-semibold text-white">最近调用记录</h4>
            <p className="text-xs text-slate-400">展示最近 {abilityLogLimit} 条测试/任务调用，便于排查链路</p>
          </div>
          <button
            type="button"
            onClick={() => refreshAbilityLogs()}
            disabled={abilityLogsLoading}
            className="rounded-full border border-slate-600 px-3 py-1 text-xs text-slate-200 disabled:opacity-40"
          >
            {abilityLogsLoading ? '刷新中…' : '刷新'}
          </button>
        </div>
        {abilityLogsError && <p className="text-xs text-rose-400">{abilityLogsError}</p>}
        {abilityLogsLoading && abilityLogs.length === 0 ? (
          <p className="text-sm text-slate-500">正在加载能力调用记录…</p>
        ) : abilityLogs.length === 0 ? (
          <p className="text-sm text-slate-500">暂无历史记录，运行一次测试即可自动写入。</p>
        ) : (
          <ul className="space-y-3">
            {abilityLogs.map((log) => {
              const logPricing = resolveLogPricing(log);
              const logPricingText = describePricing(logPricing);
              return (
                <li
                  key={log.id}
                  className="rounded-2xl border border-slate-800 bg-slate-950/40 p-4 text-xs text-slate-300 space-y-2"
                >
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <div className="text-sm font-semibold text-white">{log.ability_name || log.capability_key}</div>
                      <div className="mt-1 text-[11px] text-slate-500">
                        {formatDateTime(log.created_at)} · {log.executor_name || log.executor_type || log.executor_id || '未指定节点'}
                        {typeof log.duration_ms === 'number' ? ` · ${log.duration_ms}ms` : ''}
                      </div>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className={`rounded-full px-3 py-0.5 text-[11px] font-semibold ${getAbilitySourceBadgeClass(log.source)}`}>
                        {formatAbilitySource(log.source)}
                      </span>
                      <span className={`rounded-full px-3 py-0.5 text-[11px] font-semibold ${getAbilityLogStatusClass(log.status)}`}>
                        {log.status === 'success' ? '成功' : log.status === 'failed' ? '失败' : log.status}
                      </span>
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-3 text-[11px] text-slate-400">
                    {log.ability_id && (
                      <span className="flex items-center gap-1">
                        Ability：
                        <code className="bg-slate-900/70 px-1 py-0.5 font-mono">{log.ability_id}</code>
                        <button type="button" onClick={() => copyTextToClipboard(log.ability_id!)} className="text-sky-400">
                          复制
                        </button>
                      </span>
                    )}
                    <span className="flex items-center gap-1">
                      Log ID：
                      <code className="bg-slate-900/70 px-1 py-0.5 font-mono">{log.id}</code>
                    </span>
                    {log.task_id && (
                      <span className="flex items-center gap-1">
                        请求 ID：
                        <span className="font-mono text-slate-200">{formatTaskMarker(log.task_id)}</span>
                        <button type="button" onClick={() => copyTextToClipboard(log.task_id!)} className="text-sky-400">
                          复制
                        </button>
                      </span>
                    )}
                    {log.trace_id && (
                      <span className="flex items-center gap-1">
                        Trace：
                        <span className="font-mono text-slate-200">{formatTaskMarker(log.trace_id)}</span>
                        <button type="button" onClick={() => copyTextToClipboard(log.trace_id!)} className="text-sky-400">
                          复制
                        </button>
                      </span>
                    )}
                    {log.workflow_run_id && (
                      <span className="flex items-center gap-1">
                        Workflow：
                        <span className="font-mono text-slate-200">{formatTaskMarker(log.workflow_run_id)}</span>
                      </span>
                    )}
                    {log.executor_id && (
                      <span className="flex items-center gap-1">
                        节点：
                        <span className="font-mono">{log.executor_id}</span>
                      </span>
                    )}
                  </div>
                  {logPricingText && logPricingText !== '—' && <div className="text-[11px] text-slate-400">成本：{logPricingText}</div>}
                  {log.stored_url && (
                    <div className="text-[11px]">
                      OSS 预览：
                      <a href={log.stored_url} target="_blank" rel="noreferrer" className="text-emerald-400 underline">
                        {log.stored_url}
                      </a>
                    </div>
                  )}
                  {log.result_assets && log.result_assets.length > 0 && (
                    <div className="space-y-1 text-[11px]">
                      {log.result_assets.map((asset, index) => {
                        const assetUrl = resolveAssetUrl(asset);
                        if (!assetUrl) return null;
                        return (
                          <div key={`${log.id}-asset-${index}`} className="break-all">
                            输出 {index + 1}：
                            <a href={assetUrl} target="_blank" rel="noreferrer" className="text-sky-400 underline">
                              {assetUrl}
                            </a>
                          </div>
                        );
                      })}
                    </div>
                  )}
                  {log.error_message && <p className="text-sm text-rose-400">{log.error_message}</p>}
                  {(log.request_payload || log.response_payload) && (
                    <details className="text-[11px] text-slate-300">
                      <summary className="cursor-pointer text-slate-200">查看请求/响应详情</summary>
                      {log.request_payload && (
                        <div className="mt-1">
                          <div className="text-[10px] uppercase tracking-wide text-slate-500">Request</div>
                          <pre className="mt-1 max-h-32 overflow-auto rounded border border-slate-800 bg-slate-950/60 p-2 font-mono text-[10px]">
                            {formatRawResponse(log.request_payload)}
                          </pre>
                        </div>
                      )}
                      {log.response_payload && (
                        <div className="mt-2">
                          <div className="text-[10px] uppercase tracking-wide text-slate-500">Response</div>
                          <pre className="mt-1 max-h-32 overflow-auto rounded border border-slate-800 bg-slate-950/60 p-2 font-mono text-[10px]">
                            {formatRawResponse(log.response_payload)}
                          </pre>
                        </div>
                      )}
                    </details>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </div>
    );
  };

  const scrollToSection = (id: NavId) => {
    setActiveNav(id);
    const target = document.getElementById(id);
    if (target) {
      const offset = target.getBoundingClientRect().top + window.scrollY - 24;
      window.scrollTo({ top: offset, behavior: 'smooth' });
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 px-4 py-8">
      <div className="mx-auto flex max-w-[1500px] gap-8">
        <aside className="sticky top-6 h-fit w-64 rounded-3xl border border-white/5 bg-slate-950/70 p-6 shadow-[0_20px_60px_rgba(2,6,23,0.65)] backdrop-blur">
          <div className="mb-6">
            <p className="text-xs uppercase tracking-[0.4em] text-slate-500">控制台</p>
            <h1 className="mt-2 text-2xl font-semibold text-white">AI 管理端</h1>
            <p className="text-sm text-slate-400">集中管理执行节点、工作流、密钥与调度测试。</p>
          </div>
          <nav className="space-y-2">
            {navItems.map((item) => {
              const active = activeNav === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => scrollToSection(item.id)}
                  className={`w-full rounded-2xl border px-4 py-3 text-left transition ${
                    active
                      ? 'border-sky-500/70 bg-sky-500/10 text-white'
                      : 'border-white/5 bg-transparent text-slate-300 hover:border-slate-500/60'
                  }`}
                >
                  <div className="text-sm font-semibold">{item.label}</div>
                  <div className="text-xs text-slate-400">{item.description}</div>
                </button>
              );
            })}
          </nav>
        </aside>

        <div className="flex-1 space-y-8 rounded-[32px] border border-white/5 bg-slate-950/70 p-8 shadow-[0_40px_120px_rgba(15,23,42,0.55)] backdrop-blur">
          <Section id="overview" title="总体概览" description="观察运行快照、调度指标与刷新入口。">
            <div className="flex flex-col gap-4 rounded-2xl border border-slate-800 bg-slate-900/50 p-6 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <p className="text-sm uppercase tracking-[0.4em] text-slate-500">控制面</p>
                <h2 className="mt-2 text-2xl font-semibold text-white">AI 集成管理控制台</h2>
                <p className="text-sm text-slate-400">
                  独立系统，聚合 OpenAI/ComfyUI/百度/火山等执行能力，支持链路自检。所有管理操作会实时写入文档。
                </p>
              </div>
              <div className="flex gap-3">
                <button
                  onClick={load}
                  className="rounded-2xl border border-slate-700 bg-slate-900/70 px-4 py-2 text-sm text-slate-200 hover:bg-slate-800"
                >
                  {loading ? '刷新中…' : '刷新数据'}
                </button>
              </div>
            </div>
            <div className="grid gap-4 pt-4 sm:grid-cols-2 lg:grid-cols-4">
              <MetricCard label="执行节点" value={summary.executors} sub={`活跃 ${summary.activeExecutors}`} />
              <MetricCard label="工作流" value={summary.workflows} sub="版本 & 类型" />
              <MetricCard label="绑定策略" value={summary.bindings} sub="action → workflow → executor" />
              <MetricCard label="API Keys" value={summary.apiKeys} sub="即将到期请注意" />
              <MetricCard label="能力目录" value={summary.abilities || 0} sub="厂商 × 功能" />
            </div>
          </Section>

          {dashboardMetrics && (
            <Section
              id="monitor"
              title="运行监控"
              description="实时关注任务队列、当日执行概况以及节点健康状态。"
            >
              <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                <MetricCard label="累计任务" value={dashboardMetrics.totals.total_tasks} sub="历史累计" />
                <MetricCard label="排队中" value={dashboardMetrics.totals.queue_depth} sub="created/pending/queued" />
                <MetricCard label="批次待处理" value={dashboardMetrics.totals.pending_batches} sub="未完成的 TaskBatch" />
                <MetricCard label="失败任务" value={dashboardMetrics.totals.failed_tasks} sub="含错误待复盘" />
              </div>
              <div className="grid gap-6 lg:grid-cols-2">
                <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-5">
                  <h3 className="text-white text-lg font-semibold">状态分布</h3>
                  <p className="text-sm text-slate-400 mb-4">统计所有任务的最新状态，便于评估调度堵塞点。</p>
                  <div className="space-y-3">
                    {dashboardMetrics.status_buckets.map((bucket) => (
                      <div key={bucket.status}>
                        <div className="flex items-center justify-between text-sm text-slate-300">
                          <span>{bucket.status}</span>
                          <span>{bucket.count}</span>
                        </div>
                        <div className="mt-1 h-2 rounded-full bg-slate-800">
                          <div
                            className="h-2 rounded-full bg-gradient-to-r from-sky-500 to-blue-400"
                            style={{
                              width: `${Math.min(
                                100,
                                (bucket.count / (dashboardMetrics.totals.total_tasks || 1)) * 100,
                              )}%`,
                            }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
                <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-5">
                  <h3 className="text-white text-lg font-semibold">今日任务</h3>
                  <p className="text-sm text-slate-400 mb-4">UTC 当日维度数据，协助判断短期业务波动。</p>
                  <div className="grid gap-4 sm:grid-cols-3">
                    <MiniStat label="新建" value={dashboardMetrics.today.created} accent="from-sky-500 to-cyan-400" />
                    <MiniStat label="完成" value={dashboardMetrics.today.completed} accent="from-emerald-500 to-lime-400" />
                    <MiniStat label="失败" value={dashboardMetrics.today.failed} accent="from-rose-500 to-amber-500" />
                  </div>
                </div>
              </div>
              <div className="grid gap-6 lg:grid-cols-2">
                <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-5">
                  <div className="flex items-center justify-between">
                    <h3 className="text-white text-lg font-semibold">最近任务</h3>
                    <span className="text-xs text-slate-500">显示最新 8 条</span>
                  </div>
                  <div className="mt-3 overflow-x-auto">
                    <table>
                      <thead>
                        <tr className="text-left text-xs uppercase tracking-widest text-slate-500">
                          <th>任务</th>
                          <th>渠道</th>
                          <th>状态</th>
                          <th>时间</th>
                        </tr>
                      </thead>
                      <tbody>
                        {dashboardMetrics.recent_tasks.map((task) => (
                          <tr key={task.id}>
                            <td className="text-sm text-white">
                              <div className="font-semibold">{task.tool_action}</div>
                              <div className="text-xs text-slate-500">{task.id}</div>
                            </td>
                            <td className="text-sm text-slate-300">{task.channel}</td>
                            <td>
                              <StatusPill status={task.status} />
                            </td>
                            <td className="text-xs text-slate-400">{formatDate(task.created_at)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
                <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-5">
                  <h3 className="text-white text-lg font-semibold mb-3">节点健康</h3>
                  <div className="space-y-4">
                    {dashboardMetrics.executor_health.map((item) => (
                      <div
                        key={item.id}
                        className="rounded-2xl border border-slate-800/80 bg-slate-950/40 p-4 flex flex-col gap-1"
                      >
                        <div className="flex items-center justify-between">
                          <div>
                            <div className="text-white font-medium">{item.name}</div>
                            <div className="text-xs text-slate-500">{item.id}</div>
                          </div>
                          <StatusPill status={item.status} />
                        </div>
                        <div className="flex flex-wrap items-center gap-4 text-xs text-slate-400">
                          <span>健康：{item.health_status || 'unknown'}</span>
                          <span>最大并发：{item.max_concurrency}</span>
                          <span>权重：{item.weight}</span>
                        </div>
                        <div className="text-xs text-slate-500">
                          心跳：
                          {item.last_heartbeat_at ? formatDate(item.last_heartbeat_at) : '暂无'}
                        </div>
                      </div>
                    ))}
                    {dashboardMetrics.executor_health.length === 0 && (
                      <div className="text-sm text-slate-500">暂无节点数据。</div>
                    )}
                  </div>
                </div>
              </div>
            </Section>
          )}

      <Section id="executors" title="执行节点" description="维护执行器的接入信息、并发能力与心跳状态。">
        <div className="grid gap-6 lg:grid-cols-2">
          <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-4">
            <h3 className="text-lg font-semibold text-white mb-4">节点列表</h3>
            <div className="overflow-x-auto">
              <table>
                <thead>
                  <tr className="text-left text-slate-400 text-sm">
                    <th>名称</th>
                    <th>类型</th>
                    <th>状态</th>
                    <th>并发/权重</th>
                    <th>心跳</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {executors.map((ex) => (
                    <tr key={ex.id}>
                      <td>
                        <div className="text-white font-medium">{ex.name}</div>
                        <div className="text-xs text-slate-400">{ex.base_url || '—'}</div>
                      </td>
                      <td className="text-sm text-slate-300">{ex.type}</td>
                      <td className="text-sm">
                        <StatusPill status={ex.status} />
                      </td>
                      <td className="text-sm text-slate-300">
                        {ex.max_concurrency}/{ex.weight}
                      </td>
                      <td className="text-xs text-slate-400">{ex.last_heartbeat_at || '—'}</td>
                      <td className="text-right text-xs space-x-2">
                        <button
                          onClick={() => {
                            const { config, ...rest } = ex;
                            setExecutorForm({ ...rest, config: stringifyJSON(config) });
                          }}
                          className="text-sky-400"
                        >
                          编辑
                        </button>
                        <button onClick={() => handleDelete('executor', ex.id)} className="text-red-400">
                          删除
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-4">
            <h3 className="text-lg font-semibold text-white mb-4">
              {executorForm.id ? '编辑节点' : '新增节点'}
            </h3>
            <div className="space-y-3 text-sm">
              <input
                placeholder="名称"
                value={executorForm.name || ''}
                onChange={(e) => setExecutorForm({ ...executorForm, name: e.target.value })}
              />
              <input
                placeholder="类型（mock/openai/comfyui...）"
                value={executorForm.type || ''}
                onChange={(e) => setExecutorForm({ ...executorForm, type: e.target.value })}
              />
              <input
                placeholder="Base URL"
                value={executorForm.base_url || ''}
                onChange={(e) => setExecutorForm({ ...executorForm, base_url: e.target.value })}
              />
              <input
                placeholder="状态"
                value={executorForm.status || ''}
                onChange={(e) => setExecutorForm({ ...executorForm, status: e.target.value })}
              />
              <div className="flex gap-3">
                <input
                  type="number"
                  placeholder="权重"
                  value={executorForm.weight ?? 1}
                  onChange={(e) => setExecutorForm({ ...executorForm, weight: Number(e.target.value) })}
                />
                <input
                  type="number"
                  placeholder="最大并发"
                  value={executorForm.max_concurrency ?? 1}
                  onChange={(e) => setExecutorForm({ ...executorForm, max_concurrency: Number(e.target.value) })}
                />
              </div>
              <textarea
                placeholder='配置 JSON, 例如 {"provider":"openai"}'
                rows={5}
                value={executorForm.config ?? ''}
                onChange={(e) => setExecutorForm({ ...executorForm, config: e.target.value })}
              />
              <div className="flex gap-3">
                <button className="flex-1 rounded bg-sky-500/80 py-2 text-white" onClick={handleExecutorSubmit}>
                  保存
                </button>
                {executorForm.id && (
                  <button
                    className="rounded border border-slate-500 px-4 py-2 text-slate-200"
                    onClick={() => setExecutorForm(defaultExecutorForm)}
                  >
                    取消
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
        <p className="mt-4 text-xs text-slate-500">
          提示：允许的节点会写入 `metadata.allowed_executor_ids`，调度器只会在这些 ComfyUI 节点上运行该模板；如未选择则按标签自动匹配。
        </p>
      </Section>

      <Section
        id="future-abilities"
        title="其他原子能力类型（占位）"
        description="向量库、PDI 工具、调色/鉴黄等能力会以独立卡片呈现，当前阶段先留出位置，待接入时补充配置与巡检。"
      >
        <div className="rounded-2xl border border-dashed border-slate-700 bg-slate-950/30 p-5 text-sm text-slate-400">
          <p>
            TODO：支持“向量库能力”“图像后处理工具”等新的原子能力类型，采用与 ComfyUI 模板类似的配置体验（指定接入点、默认参数、自检计划）。
          </p>
          <p className="mt-2">
            在完成元数据设计与后端 API 之前，此处保持占位，便于大家理解整体 IA 结构并预留空间。
          </p>
        </div>
      </Section>

      <Section
        id="ability-api"
        title="统一能力接口"
        description="面向客户端/业务方公开的 `/api/abilities` 清单与调用示例，便于快速查找能力 ID、输入要求、是否支持多图等。"
      >
        <div className="rounded-2xl border border-slate-800 bg-slate-950/40 p-4 space-y-4">
          <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
            <div>
              <p className="text-xs text-slate-400">
                所有终端都应通过 <code className="bg-slate-900 rounded px-1 py-0.5 text-[10px]">GET /api/abilities</code>{' '}
                查询能力，并使用 <code className="bg-slate-900 rounded px-1 py-0.5 text-[10px]">POST /api/abilities/&lt;abilityId&gt;/invoke</code> 触发。
                调度层会根据能力配置、绑定规则与执行节点健康度自行分配资源。
              </p>
            </div>
            <button
              onClick={refreshPublicAbilities}
              disabled={publicAbilitiesLoading}
              className="self-start rounded-full border border-slate-700 px-3 py-1 text-xs text-slate-200 disabled:opacity-40"
            >
              {publicAbilitiesLoading ? '刷新中…' : '刷新列表'}
            </button>
          </div>
          <div>
            <div className="text-xs text-slate-400">调用示例（可复制到 Postman / cURL）</div>
            <pre className="mt-2 rounded-2xl border border-slate-800 bg-slate-900/70 p-4 text-[11px] text-slate-200 whitespace-pre-wrap">
              {abilityApiExample}
            </pre>
          </div>
          <div className="space-y-2">
            <div className="text-xs text-slate-400">能力 ID 清单</div>
            <div className="max-h-72 overflow-auto rounded-2xl border border-slate-800">
              <table className="min-w-full text-sm text-slate-200">
                <thead className="bg-slate-900/80 text-xs uppercase tracking-wide text-slate-400">
                  <tr>
                    <th className="px-4 py-2 text-left">能力</th>
                    <th className="px-4 py-2 text-left">Ability ID</th>
                    <th className="px-4 py-2 text-left">特性</th>
                  </tr>
                </thead>
                <tbody>
                  {publicAbilitiesLoading && publicAbilities.length === 0 ? (
                    <tr>
                      <td colSpan={3} className="px-4 py-4 text-center text-slate-500">
                        正在加载能力列表…
                      </td>
                    </tr>
                  ) : publicAbilities.length === 0 ? (
                    <tr>
                      <td colSpan={3} className="px-4 py-4 text-center text-slate-500">
                        暂无可用能力，请先在“能力管理”新增并设为 active。
                      </td>
                    </tr>
                  ) : (
                    publicAbilities.map((ability) => (
                      <tr key={ability.id} className="border-t border-slate-900/70">
                        <td className="px-4 py-3 align-top">
                          <div className="font-medium text-white">{ability.displayName}</div>
                          <div className="text-xs text-slate-400">
                            {getProviderLabel(ability.provider)} · {getCategoryLabel(ability.category)}
                          </div>
                          {ability.description && (
                            <div className="mt-1 text-xs text-slate-500 line-clamp-2">{ability.description}</div>
                          )}
                        </td>
                        <td className="px-4 py-3 align-top">
                          <div className="flex items-center gap-2">
                            <code className="rounded bg-slate-900/80 px-2 py-1 text-[11px]">{ability.id}</code>
                            <button
                              type="button"
                              onClick={() => copyTextToClipboard(ability.id)}
                              className="text-xs text-sky-400"
                            >
                              复制
                            </button>
                          </div>
                          <div className="mt-1 text-xs text-slate-500">{ability.capabilityKey}</div>
                        </td>
                        <td className="px-4 py-3 align-top text-xs text-slate-400 space-y-1">
                          {ability.requiresImage && <div>• 需图片输入</div>}
                          {ability.supportsMultipleImages && <div>• 多图输出</div>}
                          {ability.maxOutputImages && <div>• 最高 {ability.maxOutputImages} 张结果</div>}
                          {!ability.requiresImage && !ability.supportsMultipleImages && !ability.maxOutputImages && (
                            <div>• 标准调用</div>
                          )}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
          <p className="text-[11px] text-slate-500">
            更多细节见 <code className="bg-slate-900 rounded px-1">docs/api/abilities.md</code>。如需开放新的能力，请先在“能力管理”补齐配置信息，再在此复查 Ability ID 是否对外可见。
          </p>
        </div>
      </Section>

      <Section
        id="ability-logs"
        title="能力调用记录"
        description="展示最近 30 条能力调用日志（不限能力 ID），便于回溯来源、节点与成本。后续将支持按能力/时间筛选。"
      >
        <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-5">
          <div className="mb-3 flex items-center justify-between gap-2">
            <div>
              <h3 className="text-white text-lg font-semibold">能力调用清单</h3>
              <p className="text-xs text-slate-500">最新 30 条（不限能力 ID）</p>
            </div>
            <button
              type="button"
              onClick={() => refreshGlobalAbilityLogs()}
              className="rounded-full border border-slate-600 px-3 py-1 text-xs text-slate-200 disabled:opacity-40"
              disabled={globalAbilityLogsLoading}
            >
              {globalAbilityLogsLoading ? '刷新中…' : '刷新'}
            </button>
          </div>
          {globalAbilityLogsError && <p className="text-xs text-rose-400">{globalAbilityLogsError}</p>}
          <div className="mt-2 overflow-x-auto">
            <table className="min-w-full text-xs">
              <thead>
                <tr className="text-left uppercase tracking-widest text-slate-500">
                  <th>时间</th>
                  <th>能力</th>
                  <th>来源</th>
                  <th>节点</th>
                  <th>状态</th>
                  <th>成本</th>
                  <th>结果</th>
                </tr>
              </thead>
              <tbody>
                {globalAbilityLogs.map((log) => {
                  const logPricing = resolveLogPricing(log);
                  const primaryCost =
                    logPricing && (logPricing.discountPrice ?? logPricing.listPrice) !== undefined
                      ? `${formatPriceValue(logPricing.discountPrice ?? logPricing.listPrice, logPricing.currency)}`
                      : null;
                  return (
                    <tr key={`global-log-${log.id}`} className="text-slate-300">
                      <td className="whitespace-nowrap text-slate-400">{formatDateTime(log.created_at)}</td>
                      <td className="whitespace-nowrap text-slate-200">
                        <div className="font-semibold text-white">{log.ability_name || log.capability_key}</div>
                        <div className="text-[11px] text-slate-500">{log.ability_provider}</div>
                        {(log.trace_id || log.workflow_run_id) && (
                          <div className="text-[10px] text-slate-500">
                            {log.trace_id && (
                              <span>
                                Trace:{' '}
                                <span className="font-mono text-slate-300">{formatTaskMarker(log.trace_id)}</span>
                              </span>
                            )}
                            {log.workflow_run_id && (
                              <span className="ml-2">
                                Flow:{' '}
                                <span className="font-mono text-slate-300">{formatTaskMarker(log.workflow_run_id)}</span>
                              </span>
                            )}
                          </div>
                        )}
                      </td>
                      <td>
                        <span className={`inline-flex rounded-full px-2 py-0.5 text-[11px] ${getAbilitySourceBadgeClass(log.source)}`}>
                          {formatAbilitySource(log.source)}
                        </span>
                      </td>
                      <td className="text-[11px] text-slate-400">{log.executor_name || log.executor_id || '—'}</td>
                      <td>
                        <span className={`inline-flex rounded-full px-2 py-0.5 text-[11px] ${getAbilityLogStatusClass(log.status)}`}>
                          {log.status}
                        </span>
                        {typeof log.duration_ms === 'number' && (
                          <div className="text-[10px] text-slate-500">{log.duration_ms}ms</div>
                        )}
                      </td>
                      <td className="text-[11px] text-slate-400">
                        {primaryCost ? (
                          <>
                            {primaryCost}
                            <div className="text-[10px] text-slate-500">{formatUnitLabel(logPricing?.unit)}</div>
                          </>
                        ) : (
                          '—'
                        )}
                      </td>
                      <td className="text-[11px] text-slate-400">
                        {log.stored_url ? (
                          <a href={log.stored_url} className="text-emerald-400 underline" target="_blank" rel="noreferrer">
                            预览
                          </a>
                        ) : log.error_message ? (
                          <span className="text-rose-400">{log.error_message}</span>
                        ) : log.result_assets && log.result_assets.length > 0 ? (
                          <a
                            href={resolveAssetUrl(log.result_assets[0])}
                            className="text-sky-400 underline"
                            target="_blank"
                            rel="noreferrer"
                          >
                            {log.result_assets[0].tag || '结果'}
                          </a>
                        ) : (
                          '—'
                        )}
                      </td>
                    </tr>
                  );
                })}
                {globalAbilityLogs.length === 0 && (
                  <tr>
                    <td colSpan={7} className="py-4 text-center text-sm text-slate-500">
                      暂无数据。
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </Section>

      <Section
        id="abilities"
        title="能力管理"
        description="集中维护各厂商能力、默认参数和绑定节点，后续工作流和测试面板将直接引用这些配置。"
      >
        <div className="grid gap-6 lg:grid-cols-2">
          <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-4">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <div>
                <h3 className="text-lg font-semibold text-white">能力列表</h3>
                <p className="text-xs text-slate-500">
                  支持搜索/筛选，点击行即可在右侧查看详情与测试；顶部指标和全局日志同步引用本列表。
                </p>
              </div>
            </div>
            <div className="mb-4 grid gap-3 md:grid-cols-3">
              <input
                value={abilitySearch}
                onChange={(e) => setAbilitySearch(e.target.value)}
                placeholder="搜索名称/能力 Key"
                className="rounded-2xl border border-slate-700 bg-slate-950/60 px-4 py-2 text-sm text-white placeholder:text-slate-500"
              />
              <select
                value={abilityProviderFilter}
                onChange={(e) => setAbilityProviderFilter(e.target.value)}
                className="rounded-2xl border border-slate-700 bg-slate-950/60 px-4 py-2 text-sm text-white"
              >
                <option value="all">全部厂商</option>
                {abilityProviders.map((provider) => (
                  <option key={provider} value={provider}>
                    {getProviderLabel(provider)}
                  </option>
                ))}
              </select>
              <select
                value={abilityStatusFilter}
                onChange={(e) => setAbilityStatusFilter(e.target.value)}
                className="rounded-2xl border border-slate-700 bg-slate-950/60 px-4 py-2 text-sm text-white"
              >
                <option value="all">全部状态</option>
                {statusOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="overflow-x-auto">
              <table>
                <thead>
                  <tr className="text-left text-xs uppercase tracking-wider text-slate-500">
                    <th>名称</th>
                    <th>厂商/能力</th>
                    <th>状态</th>
                    <th>成本</th>
                    <th>绑定节点</th>
                    <th>最近调用</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {filteredAbilities.map((ability) => {
                    const boundExecutor = ability.executor_id
                      ? executors.find((executor) => executor.id === ability.executor_id)
                      : null;
                    const abilityRowPricing =
                      abilityPricingMap[ability.id] ||
                      abilityPricingMap[`${ability.provider}:${ability.capability_key}`] ||
                      null;
                    const abilityRowPricingText = describePricing(abilityRowPricing);
                    const latestLog = latestAbilityLogMap[ability.id];
                    const active = ability.id === selectedAbilityId;
                    return (
                      <tr
                        key={ability.id}
                        className={`cursor-pointer border-b border-slate-800/60 text-sm transition ${
                          active ? 'bg-sky-500/5' : 'hover:bg-slate-900/30'
                        }`}
                        onClick={() => setSelectedAbilityId(ability.id)}
                      >
                        <td className="text-sm text-white">
                          <div className="font-semibold">{ability.display_name}</div>
                          <div className="text-xs text-slate-500">{ability.description || '—'}</div>
                        </td>
                        <td className="text-sm text-slate-300">
                          <div>{getProviderLabel(ability.provider)}</div>
                          <div className="text-xs text-slate-500">
                            {ability.capability_key} · {getCategoryLabel(ability.category)}
                          </div>
                          <div className="text-[11px] text-slate-500">
                            {getAbilityTypeLabel(ability.ability_type)}
                            {ability.workflow_id
                              ? ` · ${workflowLookup[ability.workflow_id]?.name || ability.workflow_id}`
                              : ''}
                          </div>
                        </td>
                        <td>
                          <StatusPill status={ability.status} />
                        </td>
                        <td className="text-xs text-slate-400">
                          {abilityRowPricingText !== '—' ? abilityRowPricingText : '未设置'}
                        </td>
                        <td className="text-xs text-slate-400">
                          {boundExecutor
                            ? `${boundExecutor.name} · ${boundExecutor.type}`
                            : '自动匹配（按厂商/标签）'}
                        </td>
                        <td className="text-xs text-slate-400">
                          {latestLog ? (
                            <>
                              <div>{formatDateTime(latestLog.created_at)}</div>
                              <div className="mt-1 flex items-center gap-2">
                                <span className={`rounded-full px-2 py-0.5 text-[10px] ${getAbilityLogStatusClass(latestLog.status)}`}>
                                  {latestLog.status}
                                </span>
                                {typeof latestLog.duration_ms === 'number' && (
                                  <span className="text-[10px] text-slate-500">{latestLog.duration_ms}ms</span>
                                )}
                              </div>
                            </>
                          ) : (
                            <span className="text-slate-600">—</span>
                          )}
                        </td>
                        <td className="text-right text-xs space-x-2">
                          <button
                            className="text-sky-400"
                            onClick={(event) => {
                              event.stopPropagation();
                              handleAbilityEdit(ability);
                            }}
                          >
                            编辑
                          </button>
                          <button
                            className="text-red-400"
                            onClick={(event) => {
                              event.stopPropagation();
                              handleAbilityDelete(ability.id);
                            }}
                          >
                            删除
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                  {filteredAbilities.length === 0 && (
                    <tr>
                      <td colSpan={7} className="py-6 text-center text-sm text-slate-500">
                        暂无满足筛选条件的能力，可调整筛选或在右侧表单新增。
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-4 space-y-3 text-sm">
            <h3 className="text-lg font-semibold text-white">{abilityForm.id ? '编辑能力' : '新增能力'}</h3>
            <label className="text-xs text-slate-400">
              厂商
              <select
                value={abilityForm.provider || providerOptions[0].value}
                onChange={(e) => setAbilityForm({ ...abilityForm, provider: e.target.value })}
                className="mt-1 w-full rounded-2xl border border-slate-700 bg-slate-950/70 px-4 py-3 text-white"
              >
                {providerOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-xs text-slate-400">
              能力类型
              <select
                value={abilityForm.ability_type || abilityTypeOptions[0].value}
                onChange={(e) => setAbilityForm({ ...abilityForm, ability_type: e.target.value })}
                className="mt-1 w-full rounded-2xl border border-slate-700 bg-slate-950/70 px-4 py-3 text-white"
              >
                {abilityTypeOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-xs text-slate-400">
              能力分类
              <select
                value={abilityForm.category || categoryOptions[0].value}
                onChange={(e) => setAbilityForm({ ...abilityForm, category: e.target.value })}
                className="mt-1 w-full rounded-2xl border border-slate-700 bg-slate-950/70 px-4 py-3 text-white"
              >
                {categoryOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-xs text-slate-400">
              能力 Key
              <input
                value={abilityForm.capability_key || ''}
                onChange={(e) => setAbilityForm({ ...abilityForm, capability_key: e.target.value })}
                placeholder="例如 quality_upgrade"
                className="mt-1 w-full rounded-2xl border border-slate-700 bg-slate-950/70 px-4 py-3 text-white"
              />
            </label>
            <label className="text-xs text-slate-400">
              展示名称
              <input
                value={abilityForm.display_name || ''}
                onChange={(e) => setAbilityForm({ ...abilityForm, display_name: e.target.value })}
                placeholder="百度无损放大"
                className="mt-1 w-full rounded-2xl border border-slate-700 bg-slate-950/70 px-4 py-3 text-white"
              />
            </label>
            <label className="text-xs text-slate-400">
              描述
              <textarea
                rows={2}
                value={abilityForm.description || ''}
                onChange={(e) => setAbilityForm({ ...abilityForm, description: e.target.value })}
                className="mt-1 w-full rounded-2xl border border-slate-700 bg-slate-950/70 px-4 py-3 text-white"
              />
            </label>
            <label className="text-xs text-slate-400">
              状态
              <select
                value={abilityForm.status || 'inactive'}
                onChange={(e) => setAbilityForm({ ...abilityForm, status: e.target.value })}
                className="mt-1 w-full rounded-2xl border border-slate-700 bg-slate-950/70 px-4 py-3 text-white"
              >
                {statusOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-xs text-slate-400">
              默认节点（可选）
              <select
                value={abilityForm.executor_id || ''}
                onChange={(e) => setAbilityForm({ ...abilityForm, executor_id: e.target.value || undefined })}
                className="mt-1 w-full rounded-2xl border border-slate-700 bg-slate-950/70 px-4 py-3 text-white"
              >
                <option value="">自动匹配</option>
                {executors.map((executor) => (
                  <option key={executor.id} value={executor.id}>
                    {executor.name} · {executor.type}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-xs text-slate-400">
              关联工作流（可选）
              <select
                value={abilityForm.workflow_id || ''}
                onChange={(e) => setAbilityForm({ ...abilityForm, workflow_id: e.target.value || undefined })}
                className="mt-1 w-full rounded-2xl border border-slate-700 bg-slate-950/70 px-4 py-3 text-white"
              >
                <option value="">未绑定</option>
                {workflows.map((workflow) => (
                  <option key={workflow.id} value={workflow.id}>
                    {workflow.name} · {workflow.version || workflow.type}
                  </option>
                ))}
              </select>
            </label>
            {abilityForm.provider === 'coze' && (
              <label className="text-xs text-slate-400">
                Coze Workflow ID
                <input
                  value={abilityForm.coze_workflow_id || ''}
                  onChange={(e) =>
                    setAbilityForm({
                      ...abilityForm,
                      coze_workflow_id: e.target.value ? e.target.value.trim() : undefined,
                    })
                  }
                  placeholder="例如 1234567890"
                  className="mt-1 w-full rounded-2xl border border-slate-700 bg-slate-950/70 px-4 py-3 text-white"
                />
                <p className="mt-1 text-[11px] text-slate-500">对应 Coze Studio 发布后的 workflow_id。</p>
              </label>
            )}
            <label className="text-xs text-slate-400">
              默认参数 JSON
              <textarea
                rows={3}
                value={abilityForm.default_params || ''}
                onChange={(e) => setAbilityForm({ ...abilityForm, default_params: e.target.value })}
                className="mt-1 w-full rounded-2xl border border-slate-700 bg-slate-950/70 px-4 py-3 font-mono text-xs text-white"
              />
            </label>
            <label className="text-xs text-slate-400">
              输入表单 Schema（选填）
              <textarea
                rows={3}
                value={abilityForm.input_schema || ''}
                onChange={(e) => setAbilityForm({ ...abilityForm, input_schema: e.target.value })}
                className="mt-1 w-full rounded-2xl border border-slate-700 bg-slate-950/70 px-4 py-3 font-mono text-xs text-white"
              />
            </label>
            <label className="text-xs text-slate-400">
              其他元信息（选填）
              <textarea
                rows={3}
                value={abilityForm.metadata || ''}
                onChange={(e) => setAbilityForm({ ...abilityForm, metadata: e.target.value })}
                className="mt-1 w-full rounded-2xl border border-slate-700 bg-slate-950/70 px-4 py-3 font-mono text-xs text-white"
              />
              <p className="mt-1 text-[11px] text-slate-500">
                支持 <code className="bg-slate-900/60 px-1 rounded">pricing</code> 字段，例如
                <code className="text-slate-300">
                  {' {"pricing":{"currency":"CNY","unit":"per_image","discount_price":0.3,"list_price":0.5}}'}
                </code>
                。
              </p>
            </label>
            <div className="flex gap-3">
              <button className="flex-1 rounded bg-sky-500/80 py-2 text-white" onClick={handleAbilitySubmit}>
                保存
              </button>
              {abilityForm.id && (
                <button className="rounded border border-slate-500 px-4 py-2 text-slate-200" onClick={() => setAbilityForm(defaultAbilityForm)}>
                  取消
                </button>
              )}
            </div>
          </div>
        </div>
      </Section>

      <Section
        id="ability-tests"
        title="能力详情/测试"
        description="选择在能力目录中配置好的接口，查看能力上下文、Schema、元信息，并在“实时测试”中一键巡检。"
      >
        {abilities.length === 0 ? (
          <div className="rounded-2xl border border-amber-500/50 bg-amber-500/5 p-6 text-sm text-amber-100">
            还没有可用能力，请先到“能力目录”中新建，比如“百度 · 无损放大”。配置好默认参数和节点后，再回到这里进行测试。
          </div>
        ) : (
          <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h3 className="text-lg font-semibold text-white">能力详情 & 链路自检</h3>
                <p className="text-xs text-slate-500">
                  在左侧列表选择能力后，可在此查看概览、参数、元数据，并直接运行测试/查看日志。
                </p>
              </div>
              {selectedAbility && (
                <div className="text-right text-xs text-slate-400">
                  <div>Ability ID：{selectedAbility.id}</div>
                  <div className="text-[11px] text-slate-500 font-mono">{selectedAbility.capability_key}</div>
                </div>
              )}
            </div>
            <div className="mt-4 flex flex-wrap items-center gap-3 text-xs text-slate-400">
              <label className="flex-1">
                快速选择能力
                <select
                  value={selectedAbilityId ?? ''}
                  onChange={(e) => setSelectedAbilityId(e.target.value || null)}
                  className="mt-1 w-full rounded-2xl border border-slate-700 bg-slate-950/70 px-4 py-2 text-sm text-white"
                >
                  <option value="">请选择（或在能力管理中新建）</option>
                  {abilities.map((ability) => (
                    <option key={`ability-selector-${ability.id}`} value={ability.id}>
                      {ability.display_name} · {getProviderLabel(ability.provider)}
                    </option>
                  ))}
                </select>
              </label>
              <button
                type="button"
                onClick={() => scrollToSection('abilities')}
                className="rounded-full border border-slate-600 px-3 py-1 text-[11px] text-slate-200"
              >
                前往能力目录
              </button>
            </div>
            {!selectedAbility ? (
              <div className="mt-4 rounded-2xl border border-dashed border-slate-700 bg-slate-950/30 p-4 text-sm text-slate-400">
                暂未选择能力，请在“能力目录”中点击一行，或使用筛选快速定位目标能力。
              </div>
            ) : (
              <>
                <div className="mt-4 flex flex-wrap gap-2 border-b border-slate-800">
                  {abilityDetailTabs.map((tab) => {
                    const isActive = tab.id === activeAbilityDetailTab;
                    return (
                      <button
                        key={tab.id}
                        type="button"
                        onClick={() => setActiveAbilityDetailTab(tab.id)}
                        className={`rounded-t-2xl px-4 py-2 text-sm transition ${
                          isActive ? 'bg-slate-900 text-white' : 'text-slate-500 hover:text-slate-200'
                        }`}
                      >
                        {tab.label}
                      </button>
                    );
                  })}
                </div>
                <div className="mt-4">{renderAbilityDetailContent()}</div>
              </>
            )}
          </div>
        )}
      </Section>
      <Section
        id="comfyui-templates"
        title="ComfyUI 模板"
        description="管理本地/云端多台 ComfyUI 服务器的 Workflow JSON，指定允许运行的节点，作为一类原子能力。后续 Workflow Builder 会基于这些模板拼装业务流程。"
      >
        <div className="grid gap-6 lg:grid-cols-2">
          <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-4">
            <h3 className="text-lg font-semibold text-white mb-4">工作流列表</h3>
            <div className="overflow-x-auto">
              <table>
                <thead>
                  <tr className="text-left text-slate-400 text-sm">
                    <th>Action</th>
                    <th>名称</th>
                    <th>版本</th>
                    <th>允许运行节点</th>
                    <th>状态</th>
                    <th>更新时间</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {workflows.map((wf) => (
                    <tr key={wf.id}>
                      <td className="text-sm text-slate-300">{wf.action}</td>
                      <td className="text-white font-medium">{wf.name}</td>
                      <td className="text-sm text-slate-300">{wf.version}</td>
                      <td className="text-xs text-slate-400">
                        {(() => {
                          const allowedIds = extractAllowedExecutorIds(wf.metadata);
                          if (allowedIds.length === 0) return '未限制（匹配任意 ComfyUI 节点）';
                          return allowedIds
                            .map((id) => {
                              const exec = executors.find((executor) => executor.id === id);
                              return exec ? `${exec.name}` : id;
                            })
                            .join('、');
                        })()}
                      </td>
                      <td>
                        <StatusPill status={wf.status || 'inactive'} />
                      </td>
                      <td className="text-xs text-slate-500">{wf.updated_at || '—'}</td>
                      <td className="text-right text-xs space-x-2">
                        <button
                          className="text-sky-400"
                          onClick={() => {
                            const { definition, metadata, ...rest } = wf;
                            setWorkflowForm({
                              ...rest,
                              definition: stringifyJSON(definition),
                              metadata: stringifyJSON(metadata),
                            });
                            setWorkflowFormAllowedExecutors(extractAllowedExecutorIds(metadata));
                          }}
                        >
                          编辑
                        </button>
                        <button className="text-red-400" onClick={() => handleDelete('workflow', wf.id)}>
                          删除
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-4 space-y-3">
            <h3 className="text-lg font-semibold text-white">
              {workflowForm.id ? '编辑工作流' : '导入/新增工作流'}
            </h3>
            <div className="text-sm space-y-2">
              <input
                placeholder="Action"
                value={workflowForm.action || ''}
                onChange={(e) => setWorkflowForm({ ...workflowForm, action: e.target.value })}
              />
              <input
                placeholder="名称"
                value={workflowForm.name || ''}
                onChange={(e) => setWorkflowForm({ ...workflowForm, name: e.target.value })}
              />
              <div className="flex gap-3">
                <input
                  placeholder="版本"
                  value={workflowForm.version || ''}
                  onChange={(e) => setWorkflowForm({ ...workflowForm, version: e.target.value })}
                />
                <input
                  placeholder="类型"
                  value={workflowForm.type || ''}
                  onChange={(e) => setWorkflowForm({ ...workflowForm, type: e.target.value })}
                />
              </div>
              <input
                placeholder="状态，如 active/inactive"
                value={workflowForm.status || ''}
                onChange={(e) => setWorkflowForm({ ...workflowForm, status: e.target.value })}
              />
              <label className="block text-xs text-slate-400">
                导入 JSON 文件
                <input type="file" accept=".json" onChange={(e) => handleWorkflowFile(e.target.files)} />
              </label>
              <textarea
                rows={6}
                placeholder="workflow definition JSON"
                value={workflowForm.definition ?? ''}
                onChange={(e) => setWorkflowForm({ ...workflowForm, definition: e.target.value })}
              />
              <textarea
                rows={4}
                placeholder="metadata JSON（参数映射、依赖等）"
                value={workflowForm.metadata ?? ''}
                onChange={(e) => setWorkflowForm({ ...workflowForm, metadata: e.target.value })}
              />
              <label className="block text-xs text-slate-400">
                允许运行节点（多选）
                {comfyExecutors.length > 0 ? (
                  <select
                    multiple
                    value={workflowFormAllowedExecutors}
                    onChange={(e) =>
                      setWorkflowFormAllowedExecutors(Array.from(e.target.selectedOptions).map((option) => option.value))
                    }
                    className="mt-1 h-32 w-full rounded-2xl border border-slate-700 bg-slate-950/70 px-4 py-2 text-sm text-white"
                  >
                    {comfyExecutors.map((executor) => (
                      <option key={`workflow-executor-${executor.id}`} value={executor.id}>
                        {executor.name} · {executor.base_url || executor.type}
                      </option>
                    ))}
                  </select>
                ) : (
                  <div className="mt-1 rounded-2xl border border-dashed border-slate-700 bg-slate-950/40 px-4 py-3 text-slate-500">
                    还没有 ComfyUI 类型的执行节点，请先在“执行节点”中新建，再回到此处绑定允许运行的机器列表。
                  </div>
                )}
                <p className="mt-1 text-[11px] text-slate-500">
                  用于限制某个 ComfyUI 工作流可以在哪些机器上执行；保存后会写入 metadata.allowed_executor_ids，调度器会据此路由。
                </p>
              </label>
              <div className="flex gap-3">
                <button className="flex-1 rounded bg-sky-500/80 py-2 text-white" onClick={handleWorkflowSubmit}>
                  保存
                </button>
                {workflowForm.id && (
                <button
                  className="rounded border border-slate-500 px-4 py-2 text-slate-200"
                  onClick={() => {
                    setWorkflowForm(defaultWorkflowForm);
                    setWorkflowFormAllowedExecutors([]);
                  }}
                >
                  取消
                </button>
              )}
            </div>
            </div>
          </div>
        </div>
      </Section>
      <Section
        id="workflow-builder"
        title="工作流编排"
        description="Coze Studio + Coze Loop 承担原子能力的拖拽式编排与运行观测，统一账号、统一 Token，避免多套系统割裂。"
      >
        {!systemConfig ? (
          <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-6 text-sm text-slate-400">
            正在加载系统配置…
          </div>
        ) : (
          <div className="space-y-6">
            <div className="rounded-2xl border border-slate-800 bg-slate-950/40 p-6">
              <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                <div>
                  <div className="text-lg font-semibold text-white">Coze Studio · 工作流画布</div>
                  <p className="mt-2 text-sm text-slate-400">
                    Studio 负责节点拖拽/运行调试，Loop 负责运行诊断。所有能力均在“能力目录”中填写 Coze Workflow ID，
                    调度器即可根据 <code className="px-1">coze_workflow_id</code> 直接调用。
                  </p>
                  <div className="mt-3 grid gap-3 text-xs text-slate-400 md:grid-cols-3">
                    <div>
                      <div className="text-slate-500">Studio Base URL</div>
                      <div className="font-mono text-sm text-white">{cozeBaseUrl || '未配置'}</div>
                    </div>
                    <div>
                      <div className="text-slate-500">Loop Dashboard URL</div>
                      <div className="font-mono text-sm text-white">{cozeLoopUrl || '未配置'}</div>
                    </div>
                    <div>
                      <div className="text-slate-500">API Token</div>
                      <div className="text-white">{cozeTokenHint}</div>
                    </div>
                    <div>
                      <div className="text-slate-500">默认超时</div>
                      <div className="text-white">{cozeConfig?.default_timeout ?? 0}s</div>
                    </div>
                    <div>
                      <div className="text-slate-500">能力映射</div>
                      <div className="text-white">
                        {cozeAbilityStats.mapped}/{cozeAbilityStats.total} 已填写 Workflow ID
                      </div>
                    </div>
                  </div>
                </div>
                <div className="flex flex-col gap-3 text-sm text-white">
                  <button
                    className="rounded-full border border-slate-600 px-4 py-2 font-semibold transition hover:border-sky-500 hover:text-sky-200 disabled:cursor-not-allowed disabled:border-slate-800 disabled:text-slate-500"
                    disabled={!cozeBaseUrl}
                    onClick={handleOpenCozeStudio}
                  >
                    打开 Coze Studio
                  </button>
                  <button
                    className="rounded-full border border-slate-600 px-4 py-2 font-semibold transition hover:border-emerald-500 hover:text-emerald-200 disabled:cursor-not-allowed disabled:border-slate-800 disabled:text-slate-500"
                    disabled={!cozeLoopUrl}
                    onClick={handleOpenCozeLoop}
                  >
                    打开 Coze Loop
                  </button>
                </div>
              </div>
              <div className="mt-4 rounded-2xl border border-slate-800/70 bg-slate-950/40 p-4 text-xs text-slate-300">
                <div className="font-semibold text-white">接入步骤提醒</div>
                <ol className="mt-2 list-decimal space-y-1 pl-4">
                  <li>在 Coze Studio 内创建 Workflow，复制 Workflow ID。</li>
                  <li>在“能力目录”中选择 provider=Coze 的能力，填写 <code className="px-1">Coze Workflow ID</code> 字段。</li>
                  <li>保存后即可在本平台触发能力，日志会写入 <code className="px-1">ability_invocation_logs</code> 并可在 Loop 中回放。</li>
                </ol>
              </div>
            </div>
            <div className="grid gap-6 lg:grid-cols-2">
              <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-5">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-white text-lg font-semibold">Coze 能力映射</h3>
                    <p className="text-xs text-slate-400">列出 provider=Coze 的能力与 workflow 绑定情况。</p>
                  </div>
                </div>
                {cozeAbilityMappings.length === 0 ? (
                  <div className="mt-4 rounded-2xl border border-slate-800/70 bg-slate-950/40 p-4 text-sm text-slate-400">
                    还没有注册 Coze 能力，请在“能力目录”中新建 provider=Coze 的能力，并填写 Workflow ID。
                  </div>
                ) : (
                  <div className="mt-4 overflow-x-auto">
                    <table>
                      <thead>
                        <tr className="text-left text-xs uppercase tracking-widest text-slate-500">
                          <th>能力</th>
                          <th>Workflow ID</th>
                          <th>最近运行</th>
                        </tr>
                      </thead>
                      <tbody>
                        {cozeAbilityMappings.map(({ ability, workflowId, latestLog }) => (
                          <tr key={ability.id}>
                            <td className="text-sm text-white">
                              <div className="font-semibold">{ability.display_name}</div>
                              <div className="text-xs text-slate-500">{ability.capability_key}</div>
                              <div className="mt-1 text-xs text-slate-400">
                                状态：<StatusPill status={ability.status} />
                              </div>
                            </td>
                            <td className="text-sm text-slate-300">
                              {workflowId ? (
                                <span className="font-mono text-xs">{workflowId}</span>
                              ) : (
                                <span className="text-amber-300">未填写</span>
                              )}
                            </td>
                            <td className="text-xs text-slate-400">
                              {latestLog ? (
                                <>
                                  <StatusPill status={latestLog.status} />
                                  <div className="mt-1">{formatDateTime(latestLog.created_at)}</div>
                                </>
                              ) : (
                                '—'
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
              <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-5">
                <div className="flex items-center justify-between">
                  <h3 className="text-white text-lg font-semibold">Coze 最新运行</h3>
                  <span className="text-xs text-slate-500">按能力日志实时刷新</span>
                </div>
                {cozeRecentLogs.length === 0 ? (
                  <div className="mt-4 rounded-2xl border border-slate-800/60 bg-slate-950/40 p-4 text-sm text-slate-400">
                    暂无运行记录，可在上方能力详情中执行一次测试。
                  </div>
                ) : (
                  <div className="mt-4 space-y-3">
                    {cozeRecentLogs.map((log) => (
                      <div
                        key={log.id}
                        className="rounded-2xl border border-slate-800/60 bg-slate-950/40 p-4 text-xs text-slate-300"
                      >
                        <div className="flex items-center justify-between text-white">
                          <span>
                            #{log.id} · {log.capability_key}
                          </span>
                          <StatusPill status={log.status} />
                        </div>
                        <div className="mt-1 text-slate-400">{formatDateTime(log.created_at)}</div>
                        {log.result_assets && log.result_assets.length > 0 && (
                          <div className="mt-2">
                            <div className="text-slate-500">输出资源</div>
                            {log.result_assets.map((asset, index) => {
                              const url = resolveAssetUrl(asset);
                              if (!url) return null;
                              return (
                                <div key={`${log.id}-asset-${index}`} className="truncate text-sky-300">
                                  <a href={url} target="_blank" rel="noreferrer" className="underline">
                                    {url}
                                  </a>
                                </div>
                              );
                            })}
                          </div>
                        )}
                        {log.error_message && (
                          <div className="mt-2 text-rose-300">错误：{log.error_message}</div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </Section>

      <Section
        id="bindings"
        title="分配策略"
        description="为业务入口（Action）配置工作流与执行节点的回退链路，优先级越大越先尝试，用于多节点容灾/流量分摊。"
      >
        <p className="mb-4 text-xs text-slate-500">
          例如：`action=pattern.extract` 可以先指向云端 ComfyUI 节点，若排队或失败再回落到本地节点；也可以为百度/火山能力配置不同 API Key 的执行器，实现配额切换。
        </p>
        <div className="grid gap-6 lg:grid-cols-2">
          <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-4">
            <h3 className="text-lg font-semibold mb-4 text-white">绑定列表</h3>
            <div className="overflow-x-auto">
              <table>
                <thead>
                  <tr className="text-left text-slate-400 text-sm">
                    <th>Action</th>
                    <th>Workflow</th>
                    <th>Executor</th>
                    <th>优先级</th>
                    <th>启用</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {bindings.map((binding) => (
                    <tr key={binding.id}>
                      <td className="text-sm text-slate-300">{binding.action}</td>
                      <td className="text-sm text-slate-300">{binding.workflow_id}</td>
                      <td className="text-sm text-slate-300">{binding.executor_id}</td>
                      <td className="text-sm text-slate-300">{binding.priority}</td>
                      <td>
                        <StatusPill status={binding.enabled ? 'ON' : 'OFF'} />
                      </td>
                      <td className="text-right text-xs space-x-2">
                        <button className="text-sky-400" onClick={() => setBindingForm(binding)}>
                          编辑
                        </button>
                        <button className="text-red-400" onClick={() => handleDelete('binding', binding.id)}>
                          删除
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-4 space-y-2 text-sm">
            <h3 className="text-lg font-semibold text-white">{bindingForm.id ? '编辑绑定' : '新增绑定'}</h3>
            <input
              placeholder="Action"
              value={bindingForm.action || ''}
              onChange={(e) => setBindingForm({ ...bindingForm, action: e.target.value })}
            />
            <input
              placeholder="Workflow ID"
              value={bindingForm.workflow_id || ''}
              onChange={(e) => setBindingForm({ ...bindingForm, workflow_id: e.target.value })}
            />
            <input
              placeholder="Executor ID"
              value={bindingForm.executor_id || ''}
              onChange={(e) => setBindingForm({ ...bindingForm, executor_id: e.target.value })}
            />
            <input
              type="number"
              placeholder="优先级"
              value={bindingForm.priority ?? 0}
              onChange={(e) => setBindingForm({ ...bindingForm, priority: Number(e.target.value) })}
            />
            <label className="text-xs text-slate-400 flex items-center gap-2">
              <input
                type="checkbox"
                checked={bindingForm.enabled ?? true}
                onChange={(e) => setBindingForm({ ...bindingForm, enabled: e.target.checked })}
              />
              启用
            </label>
            <div className="flex gap-3">
              <button className="flex-1 rounded bg-sky-500/80 py-2 text-white" onClick={handleBindingSubmit}>
                保存
              </button>
              {bindingForm.id && (
                <button
                  className="rounded border border-slate-500 px-4 py-2 text-slate-200"
                  onClick={() => setBindingForm(defaultBindingForm)}
                >
                  取消
                </button>
              )}
            </div>
          </div>
        </div>
      </Section>

      <Section
        id="apikeys"
        title="API Key 仓库"
        description="统一管理百度、火山、OpenAI 等凭证，并为每个能力分配可用 Key 池，方便限流/欠费时快速切换。"
      >
        <p className="mb-4 text-xs text-slate-500">
          建议同一 Provider 维护多条 Key，搭配“分配策略”中的不同执行器，实现“主 Key + 备用 Key”或“高优先级/低优先级”模式。
        </p>
        <div className="grid gap-6 lg:grid-cols-2">
          <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-4">
            <h3 className="text-lg font-semibold text-white mb-4">Key 列表</h3>
            <div className="overflow-x-auto">
              <table>
                <thead>
                  <tr className="text-left text-slate-400 text-sm">
                    <th>Provider</th>
                    <th>名称</th>
                    <th>状态</th>
                    <th>日配额</th>
                    <th>使用</th>
                    <th>过期</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {apiKeys.map((key) => (
                    <tr key={key.id}>
                      <td className="text-sm text-slate-300">{key.provider}</td>
                      <td className="text-sm text-slate-300">{key.name}</td>
                      <td>
                        <StatusPill status={key.status} />
                      </td>
                      <td className="text-sm text-slate-300">{key.daily_quota ?? '—'}</td>
                      <td className="text-sm text-slate-300">{key.usage_count ?? 0}</td>
                      <td className="text-xs text-slate-400">{key.expire_at || '—'}</td>
                      <td className="text-right text-xs space-x-2">
                        <button className="text-sky-400" onClick={() => setApiKeyForm(key)}>
                          编辑
                        </button>
                        <button className="text-red-400" onClick={() => handleDelete('apikey', key.id)}>
                          删除
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-4 space-y-2 text-sm">
            <h3 className="text-lg font-semibold text-white">{apiKeyForm.id ? '编辑 Key' : '新增 Key'}</h3>
            <input
              placeholder="Provider"
              value={apiKeyForm.provider || ''}
              onChange={(e) => setApiKeyForm({ ...apiKeyForm, provider: e.target.value })}
            />
            <input
              placeholder="名称"
              value={apiKeyForm.name || ''}
              onChange={(e) => setApiKeyForm({ ...apiKeyForm, name: e.target.value })}
            />
            {!apiKeyForm.id && (
              <input
                placeholder="Key 值"
                value={apiKeyForm.key || ''}
                onChange={(e) => setApiKeyForm({ ...apiKeyForm, key: e.target.value })}
              />
            )}
            <input
              placeholder="状态"
              value={apiKeyForm.status || ''}
              onChange={(e) => setApiKeyForm({ ...apiKeyForm, status: e.target.value })}
            />
            <div className="flex gap-3">
              <input
                type="number"
                placeholder="日配额"
                value={apiKeyForm.daily_quota ?? ''}
                onChange={(e) =>
                  setApiKeyForm({ ...apiKeyForm, daily_quota: e.target.value ? Number(e.target.value) : undefined })
                }
              />
              <input
                type="number"
                placeholder="当前用量"
                value={apiKeyForm.usage_count ?? ''}
                onChange={(e) =>
                  setApiKeyForm({ ...apiKeyForm, usage_count: e.target.value ? Number(e.target.value) : undefined })
                }
              />
            </div>
            <input
              type="datetime-local"
              value={apiKeyForm.expire_at ? new Date(apiKeyForm.expire_at).toISOString().slice(0, 16) : ''}
              onChange={(e) =>
                setApiKeyForm({
                  ...apiKeyForm,
                  expire_at: e.target.value ? new Date(e.target.value).toISOString() : undefined,
                })
              }
            />
            <div className="flex gap-3">
              <button className="flex-1 rounded bg-sky-500/80 py-2 text-white" onClick={handleApiKeySubmit}>
                保存
              </button>
              {apiKeyForm.id && (
                <button
                  className="rounded border border-slate-500 px-4 py-2 text-slate-200"
                  onClick={() => setApiKeyForm(defaultApiKeyForm)}
                >
                  取消
                </button>
              )}
            </div>
          </div>
        </div>
      </Section>

      {systemConfig && (
        <Section
          id="system"
          title="系统配置"
          description="汇总环境信息、OSS 配置及安全参数，便于排障和入职交接。"
        >
          <div className={`grid gap-6 ${systemConfig.coze ? 'lg:grid-cols-4' : 'lg:grid-cols-3'}`}>
            <InfoCard
              title="数据库"
              items={[
                { label: '后端', value: systemConfig.database.backend },
                { label: '驱动', value: systemConfig.database.driver || 'default' },
                { label: '主机', value: systemConfig.database.host || 'local' },
                { label: 'DSN', value: systemConfig.database.dsn },
              ]}
            />
            <InfoCard
              title="OSS/上传"
              items={[
                { label: 'Bucket', value: systemConfig.oss.bucket },
                { label: 'Endpoint', value: systemConfig.oss.endpoint },
                { label: 'Public Domain', value: systemConfig.oss.public_domain || '未配置' },
                { label: 'Root Prefix', value: systemConfig.oss.root_prefix },
              ]}
            />
            <InfoCard
              title="安全参数"
              items={[
                { label: 'JWT Access TTL', value: `${systemConfig.security.jwt_access_ttl}s` },
                { label: 'JWT Refresh TTL', value: `${systemConfig.security.jwt_refresh_ttl}s` },
                { label: '上传 Token TTL', value: `${systemConfig.security.upload_token_ttl}s` },
              ]}
            />
            {systemConfig.coze && (
              <InfoCard
                title="Coze 集成"
                items={[
                  { label: 'Studio URL', value: systemConfig.coze.base_url || '未配置' },
                  { label: 'Loop URL', value: systemConfig.coze.loop_base_url || '未配置' },
                  { label: 'Token', value: systemConfig.coze.token_present ? systemConfig.coze.token_hint || '已配置' : '未配置' },
                ]}
              />
            )}
          </div>
          <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-5">
            <h3 className="text-white text-lg font-semibold">特性开关</h3>
            <div className="mt-3 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {Object.entries(systemConfig.feature_flags).map(([key, enabled]) => (
                <div key={key} className="rounded-2xl border border-slate-800/80 bg-slate-950/40 p-4">
                  <div className="text-sm font-semibold text-white">{key}</div>
                  <div className="text-xs text-slate-400 mt-1">{enabled ? '启用' : '关闭'}</div>
                </div>
              ))}
            </div>
          </div>
          <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-5">
            <h3 className="text-white text-lg font-semibold mb-4">待办事项</h3>
            <div className="space-y-3">
              {systemConfig.todo_items.map((todo) => (
                <div key={todo.title} className="rounded-2xl border border-slate-800/70 bg-slate-950/40 p-4">
                  <div className="flex items-center justify-between">
                    <div className="text-white font-medium">{todo.title}</div>
                    <span className="text-xs text-slate-400 uppercase">{todo.severity}</span>
                  </div>
                  <p className="text-sm text-slate-400 mt-2">{todo.description}</p>
                  <div className="text-xs text-slate-500 mt-1">状态：{todo.status}</div>
                </div>
              ))}
            </div>
          </div>
        </Section>
      )}

      <Section
        id="logs"
        title="调度事件"
        description="追踪任务事件、调度动作与回调结果，便于排障和多用户并发分析。"
      >
        <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-5">
          <div className="flex items-center justify-between">
            <h3 className="text-white text-lg font-semibold">调度事件</h3>
            <span className="text-xs text-slate-500">最新 25 条</span>
          </div>
          <div className="mt-3 overflow-x-auto">
            <table>
              <thead>
                <tr className="text-left text-xs uppercase tracking-widest text-slate-500">
                  <th>ID</th>
                  <th>任务</th>
                  <th>类型</th>
                  <th>负载摘要</th>
                  <th>时间</th>
                </tr>
              </thead>
              <tbody>
                {dispatchLogs.map((log) => (
                  <tr key={log.id}>
                    <td className="text-xs text-slate-500">{log.id}</td>
                    <td className="text-sm text-white">
                      <div className="font-semibold">{log.tool_action}</div>
                      <div className="text-xs text-slate-500">{log.task_id}</div>
                    </td>
                    <td>
                      <StatusPill status={log.event_type} />
                    </td>
                    <td className="text-xs text-slate-400">{previewPayload(log.payload)}</td>
                    <td className="text-xs text-slate-400">{formatDate(log.created_at)}</td>
                  </tr>
                ))}
                {dispatchLogs.length === 0 && (
                  <tr>
                    <td colSpan={5} className="text-center text-sm text-slate-500 py-4">
                      暂无日志。
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </Section>
        </div>
      </div>
    </div>
  );
}

function MetricCard({ label, value, sub }: { label: string; value: number; sub?: string }) {
  return (
    <div className="rounded-3xl border border-white/5 bg-slate-900/60 p-5 shadow-lg shadow-black/40">
      <div className="text-xs uppercase tracking-[0.3em] text-slate-500">{label}</div>
      <div className="text-3xl font-semibold text-white mt-1">{value}</div>
      {sub && <div className="text-xs text-slate-400 mt-1">{sub}</div>}
    </div>
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
    <section id={id} className="space-y-5 scroll-mt-24">
      <div>
        <h2 className="text-xl font-semibold text-white tracking-wide">{title}</h2>
        {description && <p className="text-sm text-slate-400 mt-1">{description}</p>}
      </div>
      {children}
    </section>
  );
}

function StatusPill({ status }: { status: string }) {
  const className =
    status === 'active' || status === 'ON'
      ? 'from-emerald-400 to-emerald-600 text-emerald-100'
      : status === 'completed'
        ? 'from-sky-400 to-indigo-500 text-sky-100'
        : status === 'failed' || status === 'OFF'
          ? 'from-rose-500 to-amber-500 text-rose-100'
          : 'from-slate-600 to-slate-700 text-slate-100';
  return (
    <span className={`inline-flex rounded-full bg-gradient-to-r ${className} px-3 py-1 text-xs font-semibold`}>
      {status}
    </span>
  );
}

function MiniStat({ label, value, accent }: { label: string; value: number; accent: string }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/40 p-4">
      <div className="text-xs uppercase tracking-[0.4em] text-slate-500">{label}</div>
      <div className={`mt-1 text-2xl font-semibold text-white bg-gradient-to-r bg-clip-text text-transparent ${accent}`}>
        {value}
      </div>
    </div>
  );
}

function InfoCard({ title, items }: { title: string; items: { label: string; value: string }[] }) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-5">
      <h3 className="text-white text-lg font-semibold mb-3">{title}</h3>
      <div className="space-y-2 text-sm">
        {items.map((item) => (
          <div key={item.label} className="flex justify-between text-slate-300">
            <span className="text-slate-400">{item.label}</span>
            <span className="text-right">{item.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function formatDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('zh-CN', { hour12: false, timeZone: 'Asia/Shanghai' });
}

function previewPayload(payload?: Record<string, unknown> | null) {
  if (!payload) return '—';
  const json = JSON.stringify(payload);
  return json.length > 80 ? `${json.slice(0, 77)}…` : json;
}

function StepTitle({ index, label, hint }: { index: number; label: string; hint?: string }) {
  return (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-2 text-white">
        <span className="flex h-6 w-6 items-center justify-center rounded-full bg-slate-800 text-xs font-semibold text-slate-100">
          {index}
        </span>
        <span className="text-sm font-semibold">{label}</span>
      </div>
      {hint && <span className="text-xs text-slate-500">{hint}</span>}
    </div>
  );
}
