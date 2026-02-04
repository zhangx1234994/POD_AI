import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { ChangeEvent, ReactNode } from 'react';
import {
  Alert,
  Button,
  Card,
  Col,
  Dialog,
  Input,
  InputNumber,
  Layout,
  Menu,
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
import { uploadAbilityTestFile } from '../utils/ossUploader';
import type {
  Ability,
  AbilityInvocationLog,
  AbilityFormState,
  AbilityLogMetricsResponse,
  AbilityLogMetricBucket,
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
  ComfyuiQueueSummary,
  SystemConfig,
  StoredAsset,
  Workflow,
  WorkflowFormState,
} from '../types/admin';
import type { UploadResult } from '../types/media';
import { AbilityEvaluationPage } from './AbilityEvaluation/AbilityEvaluationPage';

const navItems = [
  { id: 'overview', label: '总体概览', description: '指标、刷新、运行状态' },
  { id: 'abilities', label: '能力目录', description: '原子能力列表与成本' },
  { id: 'ability-tests', label: '能力详情/测试', description: '链路自检与演示' },
  { id: 'ability-evals', label: '能力评测', description: 'Coze 工作流试运行 + 评分' },
  { id: 'executors', label: '执行节点', description: '节点配置与健康' },
  { id: 'ability-logs', label: '能力调用', description: '全局历史记录' },
  { id: 'comfyui-templates', label: 'ComfyUI 模板', description: 'Workflow JSON 管理', advanced: true },
  { id: 'workflow-builder', label: '工作流编排', description: 'Coze Studio 工作流 + Loop 观测', advanced: true },
  { id: 'bindings', label: '分配策略', description: 'action 绑定链路', advanced: true },
  { id: 'apikeys', label: 'API Keys', description: '凭证配额管理' },
  { id: 'monitor', label: '调度监控', description: '队列/任务/节点健康' },
  { id: 'system', label: '系统配置', description: '环境、OSS、待办' },
  { id: 'logs', label: '调度事件', description: '任务追踪', advanced: true },
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

const WORKFLOW_VALUE_TYPES = new Set(['string', 'int', 'float', 'bool', 'json']);

type ComfyInputMapItem = {
  field: string;
  nodeId: string;
  inputKey: string;
  valueType?: string;
};
const statusOptions = [
  { value: 'inactive', label: '未启用' },
  { value: 'active', label: '启用' },
  { value: 'deprecated', label: '下线' },
];
const apiKeyStatusOptions = [
  { value: 'active', label: '启用 (active)' },
  { value: 'inactive', label: '停用 (inactive)' },
  { value: 'deprecated', label: '下线 (deprecated)' },
] as const;

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
  comfyuiSubmitOnly: boolean;
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
  comfyuiSubmitOnly: false,
};

const formatJsonValue = (value?: JsonRecord | null) => (value ? JSON.stringify(value, null, 2) : '');
const toImagePreview = (value?: string | null) => {
  if (!value) return '';
  return value.startsWith('data:') ? value : `data:image/png;base64,${value}`;
};
const abilityLogPageSize = 20;
const globalAbilityLogPageSize = 30;
const parseDateValue = (value?: string | null): Date | null => {
  if (!value) return null;
  const raw = String(value).trim();
  if (!raw) return null;

  // If timezone is missing, treat server timestamps as UTC and convert to Asia/Shanghai for display.
  const hasTimezone = /[zZ]|[+-]\d{2}:?\d{2}$/.test(raw);
  if (hasTimezone) {
    const d = new Date(raw);
    return Number.isNaN(d.getTime()) ? null : d;
  }

  // Handle "YYYY-MM-DD HH:mm:ss" and "YYYY-MM-DDTHH:mm:ss" without timezone.
  const normalized = raw.includes(' ') && !raw.includes('T') ? raw.replace(' ', 'T') : raw;
  const isoUtc = `${normalized}Z`;
  const d = new Date(isoUtc);
  return Number.isNaN(d.getTime()) ? null : d;
};
const formatDateTime = (value?: string | null) => {
  const date = parseDateValue(value);
  if (!date) return value || '';
  return date.toLocaleString('zh-CN', { hour12: false, timeZone: 'Asia/Shanghai' });
};
const formatDurationMs = (value?: number | null) => {
  if (value === undefined || value === null) return '—';
  if (value < 1000) return `${value}ms`;
  return `${(value / 1000).toFixed(2)}s`;
};
const renderStatusTag = (status?: string | null) => {
  const normalized = (status || '').toLowerCase();
  const theme =
    normalized === 'succeeded' ||
    normalized === 'success' ||
    normalized === 'completed' ||
    normalized === 'active' ||
    normalized === 'on'
      ? ('success' as const)
      : normalized === 'failed' || normalized === 'error' || normalized === 'off'
        ? ('danger' as const)
        : normalized === 'running' || normalized === 'queued' || normalized === 'pending'
          ? ('warning' as const)
          : ('default' as const);
  return (
    <Tag theme={theme} variant="light">
      {status || 'unknown'}
    </Tag>
  );
};
const getAbilityLogStatusTag = (status?: string | null) => {
  const normalized = (status || '').toLowerCase();
  if (normalized === 'success') return { theme: 'success' as const, text: 'success' };
  if (normalized === 'failed') return { theme: 'danger' as const, text: 'failed' };
  return { theme: 'default' as const, text: status || 'unknown' };
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
const getAbilitySourceTagTheme = (value?: string | null) => {
  const v = value || '';
  if (v === 'admin-test') return 'primary' as const;
  if (v === 'ability-api' || v === 'ability_api') return 'warning' as const;
  if (v === 'ability-task' || v === 'ability_task') return 'default' as const;
  if (v === 'workflow') return 'success' as const;
  if (v === 'task') return 'warning' as const;
  return 'default' as const;
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

const hasJsonContent = (value: unknown): boolean => {
  if (!value || typeof value !== 'object') return false;
  return Object.keys(value as Record<string, unknown>).length > 0;
};

const getAbilitySchemaIssues = (ability: Ability | null): string[] => {
  if (!ability) return [];
  const issues: string[] = [];
  if (parseAbilitySchemaFields(ability.input_schema).length === 0) {
    issues.push('缺少输入 Schema');
  }
  if (!hasJsonContent(ability.metadata)) {
    issues.push('缺少 Metadata');
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

const extractComfyuiNodes = (definition?: string | JsonRecord): ComfyNode[] => {
  const parsed = safeParseJSON(definition);
  if (!parsed.ok) return [];
  const record = parsed.value as Record<string, unknown>;
  const graphCandidate = record?.graph;
  const graph =
    graphCandidate && typeof graphCandidate === 'object' ? (graphCandidate as Record<string, unknown>) : record;
  if (!graph || typeof graph !== 'object') return [];
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
    const pickSystem = (key: string) => (typeof (system as Record<string, unknown>)[key] === 'string' ? String((system as Record<string, unknown>)[key]).trim() : '');
    return {
      version: pickSystem('comfyui_version'),
      customNodes: pickSystem('installed_templates_version'),
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

const isEmptyRecord = (value?: Record<string, unknown> | null) => {
  if (!value) return true;
  return Object.keys(value).length === 0;
};

export function IntegrationDashboard({
  theme,
  onToggleTheme,
}: {
  theme: 'light' | 'dark';
  onToggleTheme: () => void;
}) {
  const [executors, setExecutors] = useState<Executor[]>([]);
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [bindings, setBindings] = useState<Binding[]>([]);
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([]);
  const [abilities, setAbilities] = useState<Ability[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadErrors, setLoadErrors] = useState<string[]>([]);
  const [activeNav, setActiveNav] = useState<NavId>(navItems[0].id);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const contentRef = useRef<HTMLDivElement | null>(null);
  const [dashboardMetrics, setDashboardMetrics] = useState<DashboardMetrics | null>(null);
  const [dispatchLogs, setDispatchLogs] = useState<DispatchLogEntry[]>([]);
  const [dispatchLogDetail, setDispatchLogDetail] = useState<DispatchLogEntry | null>(null);
  const [dispatchLogDetailOpen, setDispatchLogDetailOpen] = useState(false);
  const [systemConfig, setSystemConfig] = useState<SystemConfig | null>(null);
  const [abilityForm, setAbilityForm] = useState<AbilityFormState>(defaultAbilityForm);
  const [abilityDialogOpen, setAbilityDialogOpen] = useState(false);
  const [selectedAbilityId, setSelectedAbilityId] = useState<string | null>(null);
  const [abilityRoutingPolicy, setAbilityRoutingPolicy] = useState<string>('auto');
  const [abilityAllowedExecutors, setAbilityAllowedExecutors] = useState<string[]>([]);
  const [abilityRequiredTags, setAbilityRequiredTags] = useState<string>('');
  const [abilityFallbackToDefault, setAbilityFallbackToDefault] = useState<boolean>(true);
  const [abilitySearch, setAbilitySearch] = useState('');
  const [abilityProviderFilter, setAbilityProviderFilter] = useState<string>('all');
  const [abilityStatusFilter, setAbilityStatusFilter] = useState<string>('all');
  const [activeAbilityDetailTab, setActiveAbilityDetailTab] = useState<AbilityDetailTab>('overview');
  const [abilityLogDetail, setAbilityLogDetail] = useState<AbilityInvocationLog | null>(null);
  const [abilityLogDetailOpen, setAbilityLogDetailOpen] = useState(false);
  const [abilityLogResolveLoading, setAbilityLogResolveLoading] = useState(false);
  const [abilityLogResolveError, setAbilityLogResolveError] = useState<string | null>(null);
  const [globalAbilityLogProvider, setGlobalAbilityLogProvider] = useState<string>('all');
  const [globalAbilityLogSource, setGlobalAbilityLogSource] = useState<string>('all');
  const [globalAbilityLogStatus, setGlobalAbilityLogStatus] = useState<string>('all');
  const [globalAbilityLogSearch, setGlobalAbilityLogSearch] = useState<string>('');
  const [executorForm, setExecutorForm] = useState<ExecutorFormState>(defaultExecutorForm);
  const [workflowForm, setWorkflowForm] = useState<WorkflowFormState>(defaultWorkflowForm);
  const [workflowFormAllowedExecutors, setWorkflowFormAllowedExecutors] = useState<string[]>([]);
  const [workflowInputMap, setWorkflowInputMap] = useState<ComfyInputMapItem[]>([]);
  const [workflowOutputNodeIds, setWorkflowOutputNodeIds] = useState<string[]>([]);
  const [workflowInputPickerNodeId, setWorkflowInputPickerNodeId] = useState<string>('');
  const [workflowInputPickerKeys, setWorkflowInputPickerKeys] = useState<string[]>([]);
  const [workflowOutputPickerNodeId, setWorkflowOutputPickerNodeId] = useState<string>('');
  const [workflowOutputShowAll, setWorkflowOutputShowAll] = useState(false);
  const [workflowFormErrors, setWorkflowFormErrors] = useState<string[]>([]);
  const [bindingForm, setBindingForm] = useState<BindingFormState>(defaultBindingForm);
  const [apiKeyForm, setApiKeyForm] = useState<ApiKeyFormState>(defaultApiKeyForm);
  const [testForm, setTestForm] = useState<AbilityTestForm>(defaultTestForm);
  const [testResult, setTestResult] = useState<AbilityTestResultPayload | null>(null);
  const [testLoading, setTestLoading] = useState(false);
  const [schemaValues, setSchemaValues] = useState<SchemaFormValues>({});
  const [comfyModelCache, setComfyModelCache] = useState<Record<string, Record<string, string[]>>>({});
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
  const [uploadingImage, setUploadingImage] = useState(false);
  const [uploadedImage, setUploadedImage] = useState<UploadResult | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [abilityLogs, setAbilityLogs] = useState<AbilityInvocationLog[]>([]);
  const [abilityLogsLoading, setAbilityLogsLoading] = useState(false);
  const [abilityLogsError, setAbilityLogsError] = useState<string | null>(null);
  const [abilityLogTotal, setAbilityLogTotal] = useState<number | null>(null);
  const [abilityLogsAutoRefresh, setAbilityLogsAutoRefresh] = useState(true);
  const [abilityLogsUpdatedAt, setAbilityLogsUpdatedAt] = useState<string | null>(null);
  const [globalAbilityLogs, setGlobalAbilityLogs] = useState<AbilityInvocationLog[]>([]);
  const [globalAbilityLogsLoading, setGlobalAbilityLogsLoading] = useState(false);
  const [globalAbilityLogsError, setGlobalAbilityLogsError] = useState<string | null>(null);
  const [globalAbilityLogTotal, setGlobalAbilityLogTotal] = useState<number | null>(null);
  const [globalAbilityLogsAutoRefresh, setGlobalAbilityLogsAutoRefresh] = useState(true);
  const [globalAbilityLogsUpdatedAt, setGlobalAbilityLogsUpdatedAt] = useState<string | null>(null);
  const abilityLogsCountRef = useRef(0);
  const globalAbilityLogsCountRef = useRef(0);
  const [abilityLogMetrics, setAbilityLogMetrics] = useState<AbilityLogMetricsResponse | null>(null);
  const [abilityLogMetricsLoading, setAbilityLogMetricsLoading] = useState(false);
  const [abilityLogMetricsError, setAbilityLogMetricsError] = useState<string | null>(null);
  const [exportingAbilityLogs, setExportingAbilityLogs] = useState(false);
  const [publicAbilities, setPublicAbilities] = useState<PublicAbility[]>([]);
  const [publicAbilitiesLoading, setPublicAbilitiesLoading] = useState(false);
  const [executorTraffic, setExecutorTraffic] = useState<Record<string, ExecutorTraffic>>({});
  const [executorTrafficLoading, setExecutorTrafficLoading] = useState(false);
  const [executorTrafficError, setExecutorTrafficError] = useState<string | null>(null);
  const [executorsView, setExecutorsView] = useState<'list' | 'channels'>('channels');
  const [executorInlineConcurrency, setExecutorInlineConcurrency] = useState<Record<string, number>>({});
  const [executorInlineSaving, setExecutorInlineSaving] = useState<Record<string, boolean>>({});
  const [executorInlineError, setExecutorInlineError] = useState<Record<string, string>>({});
  const [executorFormError, setExecutorFormError] = useState<string | null>(null);

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
  const comfyWorkflowNodes = useMemo(
    () => extractComfyuiNodes(workflowForm.definition),
    [workflowForm.definition],
  );
  const comfyWorkflowNodeMap = useMemo(() => {
    const map = new Map<string, ComfyNode>();
    comfyWorkflowNodes.forEach((node) => map.set(node.id, node));
    return map;
  }, [comfyWorkflowNodes]);
  const workflowDefinitionParse = useMemo(
    () => safeParseJSON(workflowForm.definition),
    [workflowForm.definition],
  );
  const workflowMetadataParse = useMemo(
    () => safeParseJSON(workflowForm.metadata),
    [workflowForm.metadata],
  );
  const workflowDefinitionError =
    workflowForm.definition && !workflowDefinitionParse.ok ? 'Workflow JSON 解析失败，请检查格式。' : '';
  const workflowMetadataError =
    workflowForm.metadata && !workflowMetadataParse.ok ? 'metadata JSON 解析失败，请检查格式。' : '';
  const workflowMappingErrors = useMemo(() => {
    const errors: string[] = [];
    if (workflowInputMap.length === 0 && workflowOutputNodeIds.length === 0) {
      return errors;
    }
    if (!comfyWorkflowNodes.length) {
      errors.push('未解析到节点，无法校验输入/输出映射，请先导入有效的 Workflow JSON。');
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
        errors.push(`${prefix}未选择输入 Key`);
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
        errors.push(`输出节点 #${nodeId} 不在当前 Workflow 中`);
      }
    });
    return errors;
  }, [workflowInputMap, workflowOutputNodeIds, comfyWorkflowNodes, comfyWorkflowNodeMap]);
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
      { key: 'provider', label: 'provider', hint: '可选，建议填写 comfyui', placeholder: 'comfyui' },
      { key: 'baseUrl', label: 'baseUrl', hint: '可选：与 Base URL 保持一致', placeholder: 'http://<ip>:8079' },
      { key: 'channel_key', label: 'channel_key', hint: '可选：用于多机/多中转站区分', placeholder: 'comfyui-158' },
      { key: 'tags', label: 'tags', hint: '可选：路由标签，逗号分隔', placeholder: 'gpu:4090, region:hz' },
      { key: 'comfyui_version', label: 'comfyui_version', hint: '可选：ComfyUI 版本号', placeholder: 'v0.2.x / commit' },
      { key: 'custom_nodes_version', label: 'custom_nodes_version', hint: '可选：自定义节点版本', placeholder: 'nodes-2026.02' },
      { key: 'models_hash', label: 'models_hash', hint: '可选：模型清单 hash', placeholder: 'sha1:...' },
      { key: 'lora_hash', label: 'lora_hash', hint: '可选：LoRA 清单 hash', placeholder: 'sha1:...' },
      { key: 'sync_role', label: 'sync_role', hint: '可选：母/子服务器标记', placeholder: 'master / worker' },
      { key: 'last_sync_at', label: 'last_sync_at', hint: '可选：最近同步时间', placeholder: '2026-02-02 12:00' },
    ];
    const kie = [
      { key: 'apiKey', label: 'apiKey', hint: '必填：KIE API Key', placeholder: 'sk-***' },
      { key: 'baseUrl', label: 'baseUrl', hint: '默认 https://api.kie.ai', placeholder: 'https://api.kie.ai' },
      { key: 'channel_key', label: 'channel_key', hint: '可选：多中转站区分', placeholder: 'kie-default' },
    ];
    const volcengine = [
      { key: 'apiKey', label: 'apiKey', hint: '必填：火山 API Key', placeholder: '***' },
      { key: 'baseUrl', label: 'baseUrl', hint: '默认 https://ark.cn-beijing.volces.com', placeholder: 'https://ark.cn-beijing.volces.com' },
    ];
    const baidu = [
      { key: 'apiKey', label: 'apiKey', hint: '必填：百度 API Key', placeholder: '***' },
      { key: 'secretKey', label: 'secretKey', hint: '必填：百度 Secret Key', placeholder: '***' },
      { key: 'accessKey', label: 'accessKey', hint: '可选：如接入点需要', placeholder: '***' },
    ];
    if (executorTypeNormalized.includes('kie')) return kie;
    if (executorTypeNormalized.includes('volc') || executorTypeNormalized.includes('ark')) return volcengine;
    if (executorTypeNormalized.includes('baidu')) return baidu;
    if (executorTypeNormalized.includes('comfyui')) return comfyui;
    return [
      { key: 'channel_key', label: 'channel_key', hint: '可选：用于区分多渠道/多节点', placeholder: 'default' },
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
    () => Array.from(new Set(globalAbilityLogs.map((log) => log.ability_provider))).sort(),
    [globalAbilityLogs],
  );
  const globalAbilityLogSources = useMemo(
    () => Array.from(new Set(globalAbilityLogs.map((log) => log.source))).sort(),
    [globalAbilityLogs],
  );
  const globalAbilityLogStatuses = useMemo(
    () => Array.from(new Set(globalAbilityLogs.map((log) => log.status).filter(Boolean) as string[])).sort(),
    [globalAbilityLogs],
  );
  const filteredGlobalAbilityLogs = useMemo(() => {
    const keyword = globalAbilityLogSearch.trim().toLowerCase();
    return globalAbilityLogs.filter((log) => {
      if (globalAbilityLogProvider !== 'all' && log.ability_provider !== globalAbilityLogProvider) return false;
      if (globalAbilityLogSource !== 'all' && log.source !== globalAbilityLogSource) return false;
      if (globalAbilityLogStatus !== 'all' && (log.status || '') !== globalAbilityLogStatus) return false;
      if (!keyword) return true;
      const haystack = `${log.ability_name || ''} ${log.capability_key} ${log.ability_provider} ${log.executor_name || ''} ${
        log.executor_id || ''
      } ${log.task_id || ''} ${log.trace_id || ''}`.toLowerCase();
      return haystack.includes(keyword);
    });
  }, [
    globalAbilityLogs,
    globalAbilityLogProvider,
    globalAbilityLogSource,
    globalAbilityLogStatus,
    globalAbilityLogSearch,
  ]);
  const abilityLogsHasMore = useMemo(() => {
    if (abilityLogTotal !== null) {
      return abilityLogs.length < abilityLogTotal;
    }
    return abilityLogs.length >= abilityLogPageSize;
  }, [abilityLogTotal, abilityLogs.length]);
  const globalAbilityLogsHasMore = useMemo(() => {
    if (globalAbilityLogTotal !== null) {
      return globalAbilityLogs.length < globalAbilityLogTotal;
    }
    return globalAbilityLogs.length >= globalAbilityLogPageSize;
  }, [globalAbilityLogTotal, globalAbilityLogs.length]);
  const abilitySchemaFields = useMemo(
    () => parseAbilitySchemaFields(selectedAbility?.input_schema),
    [selectedAbility],
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
    : 'created/pending/queued';
  const runningQueueSub = queueOverview
    ? `任务 ${queueOverview.task_running} · 能力 ${queueOverview.ability_running} · 评测 ${queueOverview.eval_running}`
    : 'running';
  const pendingBatchValue = queueOverview?.pending_batches ?? dashboardMetrics?.totals.pending_batches ?? 0;
  const pendingBatchSub = queueOverview ? `剩余 ${queueOverview.pending_batch_tasks} 条任务` : '未完成的 TaskBatch';
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

  const load = async () => {
    setLoading(true);
    setLoadErrors([]);
    try {
      const settled = await Promise.allSettled([
        adminApi.listExecutors(),
        adminApi.listWorkflows(),
        adminApi.listBindings(),
        adminApi.listApiKeys(),
        adminApi.getDashboardMetrics(),
        adminApi.getDispatchLogs(),
        adminApi.getSystemConfig(),
        adminApi.listAbilities(),
        adminApi.getAbilityLogMetrics({ windowHours: 24 }).catch(() => null),
      ]);

      const errors: string[] = [];
      const unwrap = <T,>(idx: number, label: string): T | null => {
        const res = settled[idx];
        if (res.status === 'fulfilled') return res.value as T;
        const msg = (res.reason as any)?.message || String(res.reason || '');
        errors.push(`${label}：${msg || '请求失败'}`);
        return null;
      };

      const execRes = unwrap<Executor[]>(0, '执行节点');
      const wfRes = unwrap<Workflow[]>(1, '工作流');
      const bindingRes = unwrap<Binding[]>(2, '绑定策略');
      const apiKeyRes = unwrap<ApiKey[]>(3, 'API Keys');
      const metricsRes = unwrap<DashboardMetrics>(4, '监控指标');
      const logsRes = unwrap<{ entries: DispatchLogEntry[] }>(5, '调度事件');
      const configRes = unwrap<SystemConfig>(6, '系统配置');
      const abilityRes = unwrap<Ability[]>(7, '能力目录');
      const abilityLogMetricsRes = settled[8].status === 'fulfilled' ? (settled[8].value as any) : null;

      if (execRes) setExecutors(execRes);
      if (wfRes) setWorkflows(wfRes);
      if (bindingRes) setBindings(bindingRes);
      if (apiKeyRes) setApiKeys(apiKeyRes);
      if (metricsRes) setDashboardMetrics(metricsRes);
      if (logsRes) setDispatchLogs(logsRes.entries);
      if (configRes) setSystemConfig(configRes);
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

  const refreshAbilityLogMetrics = async () => {
    setAbilityLogMetricsLoading(true);
    setAbilityLogMetricsError(null);
    try {
      const res = await adminApi.getAbilityLogMetrics({ windowHours: 24 });
      setAbilityLogMetrics(res);
    } catch (err: any) {
      console.error('Failed to load ability log metrics:', err);
      setAbilityLogMetricsError(err?.message || '获取能力调用指标失败');
    } finally {
      setAbilityLogMetricsLoading(false);
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

  const refreshComfyuiModelCatalog = useCallback(
    async (executorId: string, options?: { silent?: boolean }) => {
      if (!executorId) return;
      const silent = Boolean(options?.silent);
      if (!silent) {
        setComfyModelLoadingByExecutor((prev) => ({ ...prev, [executorId]: true }));
      }
      setComfyModelErrorByExecutor((prev) => ({ ...prev, [executorId]: '' }));
      try {
        const resp = await adminApi.getComfyuiModels(executorId);
        setComfyModelCache((prev) => ({
          ...prev,
          [resp.executorId]: resp.models || {},
        }));
      } catch (error: any) {
        console.error('Failed to load ComfyUI models:', error);
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
    [],
  );

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

  const refreshComfyQueueSummary = useCallback(
    async (options?: { silent?: boolean }) => {
      const silent = Boolean(options?.silent);
      const executorIds = comfyExecutors.map((ex) => ex.id).filter(Boolean);
      if (!executorIds.length) {
        setComfyQueueSummary(null);
        setComfyQueueSummaryError(null);
        setComfyQueueSummaryUpdatedAt(null);
        if (!silent) setComfyQueueSummaryLoading(false);
        return;
      }
      if (!silent) {
        setComfyQueueSummaryLoading(true);
      }
      try {
        const response = await adminApi.getComfyuiQueueSummary(executorIds);
        setComfyQueueSummary(response);
        setComfyQueueSummaryError(null);
        setComfyQueueSummaryUpdatedAt(response.timestamp || new Date().toISOString());
      } catch (error) {
        console.error('load ComfyUI queue summary failed', error);
        setComfyQueueSummaryError(error instanceof Error ? error.message : '获取 ComfyUI 队列汇总失败');
      } finally {
        if (!silent) {
          setComfyQueueSummaryLoading(false);
        }
      }
    },
    [comfyExecutors],
  );

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
    async (options?: { silent?: boolean; keepSize?: boolean }) => {
    if (!selectedAbility?.id) {
      setAbilityLogs([]);
      setAbilityLogsError(null);
      setAbilityLogTotal(null);
      return;
    }
    const silent = options?.silent;
    if (!silent) {
      setAbilityLogsLoading(true);
    }
    try {
      const keepSize = Boolean(options?.keepSize);
      const currentSize = abilityLogsCountRef.current;
      const limit = keepSize ? Math.max(abilityLogPageSize, currentSize) : abilityLogPageSize;
      const response = await adminApi.listAbilityLogs(selectedAbility.id, { limit, offset: 0 });
      const items = response.items || [];
      setAbilityLogs(items);
      setAbilityLogTotal(typeof response.total === 'number' ? response.total : items.length);
      setAbilityLogsUpdatedAt(new Date().toISOString());
      setAbilityLogsError(null);
    } catch (error) {
      console.error('load ability logs failed', error);
      setAbilityLogsError(error instanceof Error ? error.message : '加载能力调用记录失败');
    } finally {
      if (!silent) {
        setAbilityLogsLoading(false);
      }
    }
    },
    [selectedAbility?.id],
  );

  const loadMoreAbilityLogs = useCallback(async () => {
    if (!selectedAbility?.id) return;
    setAbilityLogsLoading(true);
    try {
      const offset = abilityLogs.length;
      const response = await adminApi.listAbilityLogs(selectedAbility.id, { limit: abilityLogPageSize, offset });
      const items = response.items || [];
      setAbilityLogs((prev) => prev.concat(items));
      setAbilityLogTotal(
        typeof response.total === 'number' ? response.total : offset + items.length,
      );
      setAbilityLogsUpdatedAt(new Date().toISOString());
      setAbilityLogsError(null);
    } catch (error) {
      console.error('load more ability logs failed', error);
      setAbilityLogsError(error instanceof Error ? error.message : '加载更多调用记录失败');
    } finally {
      setAbilityLogsLoading(false);
    }
  }, [selectedAbility?.id, abilityLogs.length]);

  useEffect(() => {
    void refreshAbilityLogs();
  }, [refreshAbilityLogs]);

  const refreshGlobalAbilityLogs = useCallback(
    async (options?: { silent?: boolean; keepSize?: boolean }) => {
    const silent = options?.silent;
    if (!silent) {
      setGlobalAbilityLogsLoading(true);
    }
    try {
      const keepSize = Boolean(options?.keepSize);
      const currentSize = globalAbilityLogsCountRef.current;
      const limit = keepSize ? Math.max(globalAbilityLogPageSize, currentSize) : globalAbilityLogPageSize;
      const response = await adminApi.listAllAbilityLogs({ limit, offset: 0 });
      const items = response.items || [];
      setGlobalAbilityLogs(items);
      setGlobalAbilityLogTotal(typeof response.total === 'number' ? response.total : items.length);
      setGlobalAbilityLogsUpdatedAt(new Date().toISOString());
      setGlobalAbilityLogsError(null);
    } catch (error) {
      console.error('load global ability logs failed', error);
      setGlobalAbilityLogsError(error instanceof Error ? error.message : '加载能力调用清单失败');
    } finally {
      if (!silent) {
        setGlobalAbilityLogsLoading(false);
      }
    }
    },
    [],
  );

  const loadMoreGlobalAbilityLogs = useCallback(async () => {
    setGlobalAbilityLogsLoading(true);
    try {
      const offset = globalAbilityLogs.length;
      const response = await adminApi.listAllAbilityLogs({ limit: globalAbilityLogPageSize, offset });
      const items = response.items || [];
      setGlobalAbilityLogs((prev) => prev.concat(items));
      setGlobalAbilityLogTotal(
        typeof response.total === 'number' ? response.total : offset + items.length,
      );
      setGlobalAbilityLogsUpdatedAt(new Date().toISOString());
      setGlobalAbilityLogsError(null);
    } catch (error) {
      console.error('load more global ability logs failed', error);
      setGlobalAbilityLogsError(error instanceof Error ? error.message : '加载更多调用清单失败');
    } finally {
      setGlobalAbilityLogsLoading(false);
    }
  }, [globalAbilityLogs.length]);

  const resolveAbilityLog = useCallback(async () => {
    if (!abilityLogDetail) return;
    setAbilityLogResolveLoading(true);
    setAbilityLogResolveError(null);
    try {
      const updated = await adminApi.resolveAbilityLog(abilityLogDetail.id);
      setAbilityLogDetail(updated);
      await refreshAbilityLogs({ silent: true, keepSize: true });
      await refreshGlobalAbilityLogs({ silent: true, keepSize: true });
    } catch (error: any) {
      console.error('resolve ability log failed', error);
      setAbilityLogResolveError(error?.message || '回调解析失败');
    } finally {
      setAbilityLogResolveLoading(false);
    }
  }, [abilityLogDetail, refreshAbilityLogs, refreshGlobalAbilityLogs]);

  useEffect(() => {
    void refreshGlobalAbilityLogs();
  }, [refreshGlobalAbilityLogs]);

  useEffect(() => {
    abilityLogsCountRef.current = abilityLogs.length;
  }, [abilityLogs.length]);

  useEffect(() => {
    globalAbilityLogsCountRef.current = globalAbilityLogs.length;
  }, [globalAbilityLogs.length]);

  useEffect(() => {
    if (!selectedAbility?.id || !abilityLogsAutoRefresh) return;
    const interval = window.setInterval(() => {
      void refreshAbilityLogs({ silent: true, keepSize: true });
    }, 10000);
    return () => window.clearInterval(interval);
  }, [selectedAbility?.id, abilityLogsAutoRefresh, refreshAbilityLogs]);

  useEffect(() => {
    if (activeNav !== 'ability-logs' || !globalAbilityLogsAutoRefresh) return;
    const interval = window.setInterval(() => {
      void refreshGlobalAbilityLogs({ silent: true, keepSize: true });
    }, 12000);
    return () => window.clearInterval(interval);
  }, [activeNav, globalAbilityLogsAutoRefresh, refreshGlobalAbilityLogs]);

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

  const syncWorkflowMetadata = useCallback(
    (options?: {
      inputMap?: ComfyInputMapItem[];
      outputNodeIds?: string[];
      allowedExecutorIds?: string[];
    }) => {
      setWorkflowForm((prev) => {
        const base = prev.metadata ? parseJSON(prev.metadata) : {};
        const metadata: Record<string, unknown> = { ...(base || {}) };
        const allowed = options?.allowedExecutorIds ?? workflowFormAllowedExecutors;
        if (allowed && allowed.length > 0) {
          metadata.allowed_executor_ids = allowed;
        } else {
          delete metadata.allowed_executor_ids;
        }
        const inputMap = options?.inputMap ?? workflowInputMap;
        if (inputMap && inputMap.length > 0) {
          metadata.input_node_map = serializeInputNodeMap(inputMap);
        } else {
          delete metadata.input_node_map;
        }
        const outputIds = options?.outputNodeIds ?? workflowOutputNodeIds;
        if (outputIds && outputIds.length > 0) {
          metadata.output_node_ids = outputIds;
        } else {
          delete metadata.output_node_ids;
        }
        return { ...prev, metadata: stringifyJSON(metadata as JsonRecord) };
      });
    },
    [workflowFormAllowedExecutors, workflowInputMap, workflowOutputNodeIds],
  );

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
    setAbilityDialogOpen(false);
    load();
  };

  const handleAbilityEdit = (ability: Ability) => {
    const routing = parseRoutingMetadata(ability.metadata as JsonRecord | null);
    setAbilityForm({
      ...ability,
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
    setAbilityDialogOpen(true);
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
      setExecutorFormError(`配置 JSON 无法解析：${executorConfigJsonInvalid}`);
      return;
    }
    if (baseUrl && !(baseUrl.startsWith('http://') || baseUrl.startsWith('https://'))) {
      setExecutorFormError('Base URL 需以 http:// 或 https:// 开头');
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

  const updateWorkflowInputMap = (index: number, patch: Partial<ComfyInputMapItem>) => {
    const next = workflowInputMap.map((item, idx) => (idx === index ? { ...item, ...patch } : item));
    setWorkflowInputMap(next);
    syncWorkflowMetadata({ inputMap: next });
  };

  const addWorkflowInputMap = () => {
    const next = [...workflowInputMap, { field: '', nodeId: '', inputKey: '', valueType: '' }];
    setWorkflowInputMap(next);
    syncWorkflowMetadata({ inputMap: next });
  };

  const removeWorkflowInputMap = (index: number) => {
    const next = workflowInputMap.filter((_, idx) => idx !== index);
    setWorkflowInputMap(next);
    syncWorkflowMetadata({ inputMap: next });
  };

  const updateWorkflowOutputNodes = (next: string[]) => {
    setWorkflowOutputNodeIds(next);
    syncWorkflowMetadata({ outputNodeIds: next });
  };

  const pickWorkflowOutputNodes = (mode: 'save' | 'preview' | 'all' | 'clear') => {
    if (mode === 'clear') {
      updateWorkflowOutputNodes([]);
      return;
    }
    if (mode === 'all') {
      updateWorkflowOutputNodes(comfyWorkflowNodes.map((node) => node.id));
      return;
    }
    const keyword = mode === 'save' ? 'saveimage' : 'preview';
    const picked = comfyWorkflowNodes
      .filter((node) => node.classType.toLowerCase().includes(keyword))
      .map((node) => node.id);
    updateWorkflowOutputNodes(picked);
  };

  const addWorkflowOutputNode = () => {
    if (!workflowOutputPickerNodeId) return;
    if (workflowOutputNodeIds.includes(workflowOutputPickerNodeId)) return;
    updateWorkflowOutputNodes([...workflowOutputNodeIds, workflowOutputPickerNodeId]);
  };

  const removeWorkflowOutputNode = (nodeId: string) => {
    updateWorkflowOutputNodes(workflowOutputNodeIds.filter((id) => id !== nodeId));
  };

  const addWorkflowInputMappingsForNode = () => {
    const nodeId = workflowInputPickerNodeId;
    if (!nodeId || workflowInputPickerKeys.length === 0) return;
    const next = [...workflowInputMap];
    const existing = new Set(next.map((item) => `${item.nodeId}::${item.inputKey}`));
    workflowInputPickerKeys.forEach((key) => {
      const signature = `${nodeId}::${key}`;
      if (existing.has(signature)) return;
      next.push({ field: key, nodeId, inputKey: key, valueType: '' });
      existing.add(signature);
    });
    setWorkflowInputMap(next);
    syncWorkflowMetadata({ inputMap: next });
  };

  const handleWorkflowSubmit = async () => {
    const errors: string[] = [];
    if (!workflowForm.action || !workflowForm.action.trim()) {
      errors.push('请填写 Action');
    }
    if (!workflowForm.name || !workflowForm.name.trim()) {
      errors.push('请填写名称');
    }
    if (!workflowForm.definition || !workflowForm.definition.trim()) {
      errors.push('请先导入或粘贴 Workflow JSON');
    }
    if (workflowDefinitionError) {
      errors.push(workflowDefinitionError);
    }
    if (workflowMetadataError) {
      errors.push(workflowMetadataError);
    }
    if (workflowMappingErrors.length > 0) {
      errors.push(...workflowMappingErrors);
    }
    if (errors.length > 0) {
      setWorkflowFormErrors(errors);
      return;
    }
    setWorkflowFormErrors([]);
    const { definition, metadata, ...rest } = workflowForm;
    const definitionPayload = definition && workflowDefinitionParse.ok ? workflowDefinitionParse.value : undefined;
    const metadataPayload = metadata && workflowMetadataParse.ok ? workflowMetadataParse.value : {};
    if (workflowFormAllowedExecutors.length > 0) {
      metadataPayload.allowed_executor_ids = workflowFormAllowedExecutors;
    } else {
      delete metadataPayload.allowed_executor_ids;
    }
    const inputMapPayload = serializeInputNodeMap(workflowInputMap);
    if (inputMapPayload.length > 0) {
      metadataPayload.input_node_map = inputMapPayload;
    } else {
      delete metadataPayload.input_node_map;
    }
    if (workflowOutputNodeIds.length > 0) {
      metadataPayload.output_node_ids = workflowOutputNodeIds;
    } else {
      delete metadataPayload.output_node_ids;
    }
    const payload: Partial<Workflow> = {
      ...rest,
      ...(definitionPayload ? { definition: definitionPayload } : {}),
      ...(Object.keys(metadataPayload).length > 0 ? { metadata: metadataPayload } : {}),
    };
    try {
      if (workflowForm.id) {
        await adminApi.updateWorkflow(workflowForm.id, payload);
      } else {
        await adminApi.createWorkflow(payload);
      }
      setWorkflowForm(defaultWorkflowForm);
    setWorkflowFormAllowedExecutors([]);
    setWorkflowInputMap([]);
    setWorkflowOutputNodeIds([]);
    setWorkflowOutputPickerNodeId('');
    setWorkflowOutputShowAll(false);
    setWorkflowFormErrors([]);
    load();
    } catch (error) {
      console.error('save workflow failed', error);
      setWorkflowFormErrors([extractErrorMessage(error) || '保存失败，请检查网络或参数']);
    }
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

  const renderAbilityOverview = () => {
    if (!selectedAbility) {
      return (
        <Alert
          theme="info"
          message="请先在左侧“能力目录”中选中一条能力，系统会在此处展示能力描述、默认节点、成本与标签。"
        />
      );
    }
    const baseItems = [
      { label: '能力 Key', value: selectedAbility.capability_key || '—' },
      { label: '能力类型', value: getAbilityTypeLabel(selectedAbility.ability_type) || '—' },
      {
        label: '默认节点',
        value: pinnedAbilityExecutor ? `${pinnedAbilityExecutor.name} · ${pinnedAbilityExecutor.type}` : '按厂商类型自动匹配',
      },
      { label: '关联工作流', value: selectedAbilityWorkflowLabel || '未绑定' },
    ];
    return (
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        {selectedAbilitySchemaIssues.length > 0 ? (
          <Alert
            theme="warning"
            title="能力配置不完整"
            message={`请补齐：${selectedAbilitySchemaIssues.join(' / ')}`}
          />
        ) : null}
        <Card bordered>
          <Space align="start" style={{ justifyContent: 'space-between', width: '100%' }}>
            <Space direction="vertical" size={2}>
              <Typography.Text theme="secondary">
                {getProviderLabel(selectedAbility.provider)} · {getCategoryLabel(selectedAbility.category)}
              </Typography.Text>
              <Typography.Title level="h4" style={{ margin: 0 }}>
                {selectedAbility.display_name}
              </Typography.Title>
              <Typography.Text theme="secondary">
                {selectedAbility.description || '暂无描述，建议在能力管理中补充。'}
              </Typography.Text>
              {selectedAbilityTags.length > 0 ? (
                <Space breakLine>
                  {selectedAbilityTags.map((tag, index) => (
                    <Tag key={`selected-ability-tag-${index}`} theme="primary" variant="light">
                      {tag}
                    </Tag>
                  ))}
                </Space>
              ) : null}
            </Space>
            <StatusPill status={selectedAbility.status} />
          </Space>
        </Card>

        <Row gutter={[12, 12]}>
          <Col xs={24} md={12}>
            <InfoCard title="基础信息" items={baseItems} />
          </Col>
          <Col xs={24} md={12}>
            <Card bordered title="计价信息">
              <Space direction="vertical" size="small">
                <Typography.Text>{selectedAbilityPricingText}</Typography.Text>
                {selectedAbilityPricingText === '—' ? (
                  <Typography.Text theme="secondary">
                    可在 Metadata.pricing 中设置 `currency/unit/list_price/discount_price`，ComfyUI 默认按 ¥0.30 / 每张计算。
                  </Typography.Text>
                ) : null}
              </Space>
            </Card>
          </Col>
        </Row>

        <Row gutter={[12, 12]}>
          <Col xs={24} md={12}>
            <InfoCard
              title="健康巡检"
              items={[
                { label: '状态', value: selectedAbilityHealth.status },
                { label: '最近巡检', value: selectedAbilityHealth.checkedAt },
              ]}
            />
          </Col>
          <Col xs={24} md={12}>
            <InfoCard
              title="成功率（近 24h）"
              items={[
                { label: '成功率', value: selectedAbilityHealth.successRateText },
                { label: '来源', value: 'ability_invocation_logs（详见“能力调用记录”）' },
              ]}
            />
          </Col>
        </Row>
      </Space>
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
    const showParamIssues = selectedAbilitySchemaIssues.filter((issue) =>
      ['缺少输入 Schema', '缺少默认参数'].includes(issue),
    );
    return (
      <div className="space-y-4 text-xs text-slate-400">
        {showParamIssues.length > 0 ? (
          <Alert theme="warning" title="参数配置提醒" message={`尚未补齐：${showParamIssues.join(' / ')}`} />
        ) : null}
        <div>
          <div className="text-slate-500">默认参数</div>
          {selectedAbility.default_params ? (
            <CodeBlock value={formatJsonValue(selectedAbility.default_params)} maxHeight={260} />
          ) : (
            <p className="mt-1">未配置，测试时可以在实时测试 Tab 的 JSON 输入框补充。</p>
          )}
        </div>
        <div>
          <div className="text-slate-500">输入 Schema</div>
          {selectedAbility.input_schema ? (
            <CodeBlock value={formatJsonValue(selectedAbility.input_schema)} maxHeight={260} />
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
    const showMetadataIssues = selectedAbilitySchemaIssues.filter((issue) =>
      ['缺少 Metadata', '缺少计价'].includes(issue),
    );
    return (
      <div className="space-y-4 text-xs text-slate-400">
        {showMetadataIssues.length > 0 ? (
          <Alert
            theme="warning"
            title="元信息缺失"
            message={`尚未补齐：${showMetadataIssues.join(' / ')}。建议补充 api_type、pricing、requirements 等字段。`}
          />
        ) : null}
        <div>
          <div className="text-slate-500">能力 Metadata</div>
          {selectedAbility.metadata ? (
            <CodeBlock value={formatJsonValue(selectedAbility.metadata)} maxHeight={320} />
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
                {comfyQueueLoading ? '正在获取队列状态…' : '暂无实时数据，请点击刷新。'}
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
        {selectedAbility?.provider === 'comfyui' && (
          <div className="flex items-center gap-2 text-xs text-slate-400">
            <Switch
              value={testForm.comfyuiSubmitOnly}
              onChange={(value) => setTestForm((prev) => ({ ...prev, comfyuiSubmitOnly: Boolean(value) }))}
            />
            提交后不等待（直接入队）
          </div>
        )}
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
                  <CodeBlock value={formatRawResponse(testResult.raw)} maxHeight={240} />
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

  const renderAbilityLogsTab = () => {
    if (!selectedAbility) {
      return (
        <Alert theme="info" message="请选择能力后查看最近的调用记录。" />
      );
    }
    return (
      <Card
        bordered
        title={
          <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
            <div>
              <Typography.Text strong>最近调用记录</Typography.Text>
              <div>
                <Typography.Text theme="secondary">
                  已加载 {abilityLogs.length}
                  {typeof abilityLogTotal === 'number' ? ` / ${abilityLogTotal}` : ''} 条 · 自动刷新仅更新最近一页
                </Typography.Text>
              </div>
            </div>
            <Space>
              <Space align="center" size="small">
                <Typography.Text theme="secondary">自动刷新</Typography.Text>
                <Switch value={abilityLogsAutoRefresh} onChange={(v) => setAbilityLogsAutoRefresh(Boolean(v))} />
              </Space>
              {abilityLogsUpdatedAt ? (
                <Typography.Text theme="secondary">更新：{formatDateTime(abilityLogsUpdatedAt)}</Typography.Text>
              ) : null}
              <Button variant="outline" loading={abilityLogsLoading} onClick={() => refreshAbilityLogs()}>
                刷新
              </Button>
            </Space>
          </Space>
        }
      >
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          {abilityLogsError ? <Alert theme="error" message={abilityLogsError} /> : null}
          <Table
            size="small"
            rowKey="id"
            loading={abilityLogsLoading}
            data={abilityLogs}
            empty={<Typography.Text theme="secondary">暂无历史记录，运行一次测试即可自动写入。</Typography.Text>}
            columns={[
              {
                colKey: 'created_at',
                title: '时间',
                width: 180,
                cell: ({ row }) => <Typography.Text>{formatDateTime(row.created_at)}</Typography.Text>,
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
                colKey: 'executor',
                title: '节点',
                width: 220,
                cell: ({ row }) => <Typography.Text theme="secondary">{row.executor_name || row.executor_id || '—'}</Typography.Text>,
              },
              {
                colKey: 'status',
                title: '状态',
                width: 160,
                cell: ({ row }) => (
                  <Space direction="vertical" size={2}>
                    <Tag theme={getAbilityLogStatusTag(row.status).theme} variant="light">
                      {getAbilityLogStatusTag(row.status).text}
                    </Tag>
                    {typeof row.duration_ms === 'number' ? (
                      <Typography.Text theme="secondary" style={{ fontSize: 12 }}>
                        {row.duration_ms}ms
                      </Typography.Text>
                    ) : null}
                  </Space>
                ),
              },
              {
                colKey: 'callback',
                title: '回调',
                width: 160,
                cell: ({ row }) => {
                  if (!row.callback_status && !row.callback_http_status && !row.callback_finished_at) {
                    return <Typography.Text theme="secondary">—</Typography.Text>;
                  }
                  return (
                    <Space direction="vertical" size={2}>
                      {row.callback_status ? (
                        <Tag theme={getAbilityLogStatusTag(row.callback_status).theme} variant="light">
                          {getAbilityLogStatusTag(row.callback_status).text}
                        </Tag>
                      ) : null}
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
                colKey: 'result',
                title: '结果',
                minWidth: 240,
                cell: ({ row }) => {
                  const previewUrl =
                    row.stored_url ||
                    (row.result_assets && row.result_assets.length > 0 ? resolveAssetUrl(row.result_assets[0]) : '') ||
                    '';
                  const canPreviewImage = Boolean(previewUrl) && /\.(png|jpg|jpeg|webp|gif)(\?|#|$)/i.test(previewUrl);
                  return (
                    <Space size="small">
                      {previewUrl ? (
                        canPreviewImage ? (
                          <Popup
                            trigger="hover"
                            placement="left"
                            content={<img src={previewUrl} alt="preview" style={{ maxWidth: 360, maxHeight: 360, display: 'block' }} />}
                          >
                            <Button size="small" variant="text">
                              预览
                            </Button>
                          </Popup>
                        ) : (
                          <Button size="small" variant="text" onClick={() => window.open(previewUrl, '_blank', 'noreferrer')}>
                            打开
                          </Button>
                        )
                      ) : null}
                      <Button
                        size="small"
                        variant="text"
                        onClick={() => {
                          setAbilityLogDetail(row);
                          setAbilityLogResolveError(null);
                          setAbilityLogDetailOpen(true);
                        }}
                      >
                        详情
                      </Button>
                      {row.error_message ? <Typography.Text theme="error">{row.error_message}</Typography.Text> : null}
                      {!previewUrl && !row.error_message ? <Typography.Text theme="secondary">—</Typography.Text> : null}
                    </Space>
                  );
                },
              },
            ]}
          />
          <div className="flex items-center justify-between">
            <Typography.Text theme="secondary">
              {abilityLogsUpdatedAt ? `最近刷新：${formatDateTime(abilityLogsUpdatedAt)}` : '尚未刷新'}
            </Typography.Text>
            {abilityLogsHasMore ? (
              <Button variant="outline" loading={abilityLogsLoading} onClick={() => loadMoreAbilityLogs()}>
                加载更多
              </Button>
            ) : (
              <Typography.Text theme="secondary">已加载全部</Typography.Text>
            )}
          </div>
        </Space>
      </Card>
    );
  };

  const selectSection = (id: NavId) => {
    setActiveNav(id);
    // Only the right content pane scrolls. Switching sections resets scroll.
    contentRef.current?.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const visibleNavItems = useMemo(
    () => navItems.filter((item) => !(item as any).advanced || showAdvanced),
    [showAdvanced],
  );

  return (
    <Layout style={{ height: '100vh' }}>
      <Layout.Aside
        style={{
          width: 260,
          borderRight: '1px solid var(--td-component-border)',
          background: 'var(--td-bg-color-container)',
          padding: 16,
          overflow: 'auto',
        }}
      >
        <Space direction="vertical" size="small" style={{ width: '100%' }}>
          <div>
            <Typography.Text theme="secondary">控制台</Typography.Text>
            <Typography.Title level="h4" style={{ margin: '6px 0 0' }}>
              AI 管理端
            </Typography.Title>
            <Typography.Text theme="secondary">集中管理执行节点、工作流、密钥与调度测试。</Typography.Text>
          </div>
          <Menu
            value={activeNav}
            theme={theme === 'dark' ? 'dark' : 'light'}
            onChange={(value) => selectSection(value as NavId)}
          >
            {visibleNavItems.map((item) => (
              <Menu.MenuItem key={item.id} value={item.id}>
                <Tooltip content={item.description}>
                  <span>{item.label}</span>
                </Tooltip>
              </Menu.MenuItem>
            ))}
          </Menu>
        </Space>
      </Layout.Aside>

      <Layout>
        <Layout.Header
          style={{
            borderBottom: '1px solid var(--td-component-border)',
            background: 'var(--td-bg-color-container)',
            padding: '0 16px',
          }}
        >
          <Space align="center" style={{ justifyContent: 'space-between', width: '100%', height: '100%' }}>
            <Typography.Text strong>{navItems.find((x) => x.id === activeNav)?.label || '控制台'}</Typography.Text>
            <Space>
              <Space align="center" size="small">
                <Typography.Text theme="secondary">高级</Typography.Text>
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
              </Space>
              <Button variant="outline" loading={loading} onClick={load}>
                刷新
              </Button>
              <Button variant="outline" onClick={onToggleTheme}>
                {theme === 'dark' ? '深色' : '浅色'}
              </Button>
            </Space>
          </Space>
        </Layout.Header>
        <Layout.Content style={{ padding: 16, overflow: 'hidden' }}>
          <div ref={contentRef} style={{ height: '100%', overflow: 'auto' }}>
            {loadErrors.length > 0 ? (
              <div style={{ marginBottom: 16 }}>
                <Alert
                  theme="warning"
                  title="部分数据加载失败"
                  message={
                    <div>
                      <div style={{ marginBottom: 6 }}>
                        不影响已加载模块，可点击右上角“刷新”重试；失败明细：
                      </div>
                      <ul style={{ margin: 0, paddingLeft: 18 }}>
                        {loadErrors.slice(0, 6).map((msg) => (
                          <li key={msg}>{msg}</li>
                        ))}
                      </ul>
                    </div>
                  }
                  operation={
                    <Button size="small" variant="outline" onClick={load}>
                      立即重试
                    </Button>
                  }
                />
              </div>
            ) : null}
          {activeNav === 'overview' && (
            <Section id="overview" title="总体概览" description="观察运行快照、调度指标与刷新入口。">
            <Card bordered>
              <Space direction="vertical" size="small" style={{ width: '100%' }}>
                <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
                  <div>
                    <Typography.Text theme="secondary">控制台</Typography.Text>
                    <Typography.Title level="h3" style={{ margin: '6px 0 0' }}>
                      AI 集成管理控制台
                    </Typography.Title>
                    <Typography.Text theme="secondary">
                      独立系统，聚合 OpenAI/ComfyUI/百度/火山等执行能力，支持链路自检。
                    </Typography.Text>
                  </div>
                  <Space>
                    <Button variant="outline" loading={loading} onClick={load}>
                      刷新数据
                    </Button>
                  </Space>
                </Space>
              </Space>
            </Card>
            <div className="grid gap-4 pt-4 sm:grid-cols-2 lg:grid-cols-4">
              <MetricCard label="执行节点" value={summary.executors} sub={`活跃 ${summary.activeExecutors}`} />
              <MetricCard label="工作流" value={summary.workflows} sub="版本 & 类型" />
              <MetricCard label="绑定策略" value={summary.bindings} sub="action → workflow → executor" />
              <MetricCard label="API Keys" value={summary.apiKeys} sub="即将到期请注意" />
              <MetricCard label="能力目录" value={summary.abilities || 0} sub="厂商 × 功能" />
            </div>
            </Section>
          )}

          {activeNav === 'monitor' && dashboardMetrics && (
            <Section id="monitor" title="运行监控" description="实时关注任务队列、当日执行概况以及节点健康状态。">
              <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                <MetricCard label="累计任务" value={dashboardMetrics.totals.total_tasks} sub="历史累计" />
                <MetricCard label="排队中" value={pendingQueueTotal} sub={pendingQueueSub} />
                <MetricCard label="执行中（含回调）" value={runningQueueTotal} sub={runningQueueSub} />
                <MetricCard label="批次待处理" value={pendingBatchValue} sub={pendingBatchSub} />
                <MetricCard label="失败任务" value={dashboardMetrics.totals.failed_tasks} sub="含错误待复盘" />
                <MetricCard
                  label="ComfyUI 排队"
                  value={comfyQueueSummary ? comfyQueueSummary.totalPending : '—'}
                  sub={
                    comfyExecutors.length === 0
                      ? '未配置 ComfyUI 节点'
                      : comfyQueueSummaryLoading
                        ? '加载中'
                        : comfyQueueSummary
                          ? `running ${comfyQueueSummary.totalRunning}`
                          : '等待刷新'
                  }
                />
              </div>
              <Row gutter={[16, 16]}>
                <Col span={12}>
                  <Card title="状态分布" bordered>
                    <Typography.Text theme="secondary">统计所有任务的最新状态，便于评估调度堵塞点。</Typography.Text>
                    <div style={{ marginTop: 12 }}>
                      <Table
                        rowKey="status"
                        size="small"
                        data={dashboardMetrics.status_buckets}
                        columns={[
                          { colKey: 'status', title: '状态', width: 220 },
                          { colKey: 'count', title: '数量' },
                        ]}
                      />
                    </div>
                  </Card>
                </Col>
                <Col span={12}>
                  <Card title="今日任务" bordered>
                    <Typography.Text theme="secondary">按东八区自然日统计。</Typography.Text>
                    <div style={{ marginTop: 12 }} className="grid gap-4 sm:grid-cols-3">
                      <MetricCard label="新建" value={dashboardMetrics.today.created} />
                      <MetricCard label="完成" value={dashboardMetrics.today.completed} />
                      <MetricCard label="失败" value={dashboardMetrics.today.failed} />
                    </div>
                  </Card>
                </Col>
              </Row>
              <Row gutter={[16, 16]}>
                <Col span={24}>
                  <Card title="队列总览" bordered>
                    <Typography.Text theme="secondary">
                      排队=created/pending/queued；执行=running（含回调中）。批次任务显示“待处理批次 / 剩余任务数”。
                    </Typography.Text>
                    <div style={{ marginTop: 12 }}>
                      <Table
                        rowKey="key"
                        size="small"
                        data={queueOverviewRows}
                        columns={[
                          { colKey: 'label', title: '类型', width: 180 },
                          { colKey: 'pending', title: '排队中', width: 140 },
                          { colKey: 'running', title: '执行中', width: 140 },
                          {
                            colKey: 'total',
                            title: '合计',
                            width: 140,
                            cell: ({ row }) => (row.pending || 0) + (row.running || 0),
                          },
                          {
                            colKey: 'note',
                            title: '备注',
                            cell: ({ row }) => row.note || '—',
                          },
                        ]}
                      />
                    </div>
                  </Card>
                </Col>
              </Row>
              <Row gutter={[16, 16]}>
                <Col span={24}>
                  <Card
                    title={
                      <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
                        <Space align="center">
                          <span>ComfyUI 队列</span>
                          <Typography.Text theme="secondary">跨节点汇总</Typography.Text>
                        </Space>
                        <Button
                          size="small"
                          variant="outline"
                          onClick={() => refreshComfyQueueSummary()}
                          loading={comfyQueueSummaryLoading}
                          disabled={comfyExecutors.length === 0}
                        >
                          刷新
                        </Button>
                      </Space>
                    }
                    bordered
                  >
                    <Typography.Text theme="secondary">
                      该队列来自 ComfyUI 节点自身的 /queue 状态，与内部任务队列分开统计。
                    </Typography.Text>
                    <div style={{ marginTop: 12 }} className="grid gap-4 sm:grid-cols-3">
                      <MetricCard label="Running" value={comfyQueueSummary?.totalRunning ?? '—'} />
                      <MetricCard label="Pending" value={comfyQueueSummary?.totalPending ?? '—'} />
                      <MetricCard label="Total" value={comfyQueueSummary?.totalCount ?? '—'} />
                    </div>
                    <div style={{ marginTop: 12 }}>
                      <Table
                        rowKey="executorId"
                        size="small"
                        data={comfyQueueSummary?.servers || []}
                        columns={[
                          {
                            colKey: 'executorId',
                            title: '节点',
                            cell: ({ row }) => {
                              const ex = executors.find((item) => item.id === row.executorId);
                              return (
                                <Space direction="vertical" size={2}>
                                  <Typography.Text>{ex?.name || row.executorId}</Typography.Text>
                                  <Typography.Text theme="secondary">{row.executorId}</Typography.Text>
                                </Space>
                              );
                            },
                          },
                          {
                            colKey: 'baseUrl',
                            title: 'Base URL',
                            ellipsis: true,
                          },
                          { colKey: 'runningCount', title: 'Running', width: 120 },
                          { colKey: 'pendingCount', title: 'Pending', width: 120 },
                          {
                            colKey: 'queueMaxSize',
                            title: 'Max',
                            width: 100,
                            cell: ({ row }) => (typeof row.queueMaxSize === 'number' ? row.queueMaxSize : '—'),
                          },
                          {
                            colKey: 'supported',
                            title: '支持',
                            width: 100,
                            cell: ({ row }) => (row.supported === false ? '否' : '是'),
                          },
                          {
                            colKey: 'message',
                            title: '备注',
                            ellipsis: true,
                            cell: ({ row }) =>
                              row.message ? <Typography.Text theme="warning">{row.message}</Typography.Text> : '—',
                          },
                        ]}
                        empty={
                          comfyQueueSummaryLoading ? (
                            <Typography.Text theme="secondary">加载中…</Typography.Text>
                          ) : (
                            <Typography.Text theme="secondary">暂无队列数据。</Typography.Text>
                          )
                        }
                      />
                    </div>
                  </Card>
                </Col>
              </Row>
              <Row gutter={[16, 16]}>
                <Col span={12}>
                  <Card
                    title={
                      <Space align="center">
                        <span>最近任务</span>
                        <Typography.Text theme="secondary">最新 8 条</Typography.Text>
                      </Space>
                    }
                    bordered
                  >
                    <Table
                      rowKey="id"
                      size="small"
                      data={dashboardMetrics.recent_tasks}
                      columns={[
                        {
                          colKey: 'tool_action',
                          title: '任务',
                          ellipsis: true,
                          cell: ({ row }) => (
                            <Space direction="vertical" size={2}>
                              <Typography.Text>{row.tool_action}</Typography.Text>
                              <Typography.Text theme="secondary">{row.id}</Typography.Text>
                            </Space>
                          ),
                        },
                        { colKey: 'channel', title: '渠道', width: 160, ellipsis: true },
                        { colKey: 'status', title: '状态', width: 140, cell: ({ row }) => renderStatusTag(row.status) },
                        {
                          colKey: 'created_at',
                          title: '时间',
                          width: 220,
                          cell: ({ row }) => <Typography.Text theme="secondary">{formatDateTime(row.created_at)}</Typography.Text>,
                        },
                      ]}
                    />
                  </Card>
                </Col>
                <Col span={12}>
                  <Card title="节点健康" bordered>
                    <Table
                      rowKey="id"
                      size="small"
                      data={dashboardMetrics.executor_health}
                      columns={[
                        {
                          colKey: 'name',
                          title: '节点',
                          ellipsis: true,
                          cell: ({ row }) => (
                            <Space direction="vertical" size={2}>
                              <Typography.Text>{row.name}</Typography.Text>
                              <Typography.Text theme="secondary">{row.id}</Typography.Text>
                            </Space>
                          ),
                        },
                        { colKey: 'status', title: '状态', width: 120, cell: ({ row }) => renderStatusTag(row.status) },
                        { colKey: 'health_status', title: '健康', width: 120, ellipsis: true },
                        { colKey: 'max_concurrency', title: '并发', width: 80 },
                        { colKey: 'weight', title: '权重', width: 80 },
                        {
                          colKey: 'last_heartbeat_at',
                          title: '心跳',
                          width: 220,
                          cell: ({ row }) =>
                            row.last_heartbeat_at ? (
                              <Typography.Text theme="secondary">{formatDateTime(row.last_heartbeat_at)}</Typography.Text>
                            ) : (
                              <Typography.Text theme="secondary">—</Typography.Text>
                            ),
                        },
                      ]}
                      empty={<Typography.Text theme="secondary">暂无节点数据。</Typography.Text>}
                    />
                  </Card>
                </Col>
              </Row>
            </Section>
          )}

          {activeNav === 'executors' && (
      <Section id="executors" title="执行节点" description="维护执行器的接入信息、并发能力与心跳状态。">
        <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
          <Typography.Text theme="secondary">
            同一能力可配置多条线路（多中转站 / 多 ComfyUI 服务器），后续调度会基于优先级与健康度自动切换。
          </Typography.Text>
          <Space>
            <Button
              size="small"
              variant={executorsView === 'channels' ? 'base' : 'outline'}
              onClick={() => setExecutorsView('channels')}
            >
              渠道视图
            </Button>
            <Button size="small" variant={executorsView === 'list' ? 'base' : 'outline'} onClick={() => setExecutorsView('list')}>
              列表/编辑
            </Button>
            <Button
              size="small"
              variant="outline"
              onClick={() => refreshExecutorTraffic()}
              loading={executorTrafficLoading}
              title="刷新近 24h 调用指标（成功率/失败/耗时）"
            >
              刷新指标
            </Button>
            <Button
              size="small"
              variant="outline"
              onClick={() => refreshComfyQueueSummary()}
              loading={comfyQueueSummaryLoading}
              disabled={comfyExecutors.length === 0}
              title="刷新 ComfyUI 队列汇总"
            >
              刷新队列
            </Button>
          </Space>
        </Space>

        {executorsView === 'channels' ? (
          <div className="space-y-4">
            {executorTrafficError && (
              <Alert theme="error" message={executorTrafficError} />
            )}
            {comfyQueueSummaryError && (
              <Alert theme="error" message={`ComfyUI 队列：${comfyQueueSummaryError}`} />
            )}
            {(() => {
              const groups = new Map<string, Executor[]>();
              executors.forEach((ex) => {
                const key = ex.type || 'unknown';
                const list = groups.get(key) || [];
                list.push(ex);
                groups.set(key, list);
              });
              const entries = Array.from(groups.entries()).sort(([a], [b]) => a.localeCompare(b));
              if (entries.length === 0) {
                return <div className="text-sm text-slate-500">暂无执行节点，请先新增。</div>;
              }
              return (
                <div className="grid gap-4 lg:grid-cols-2">
                  {entries.map(([type, items]) => {
                    const activeCount = items.filter((x) => x.status === 'active').length;
                    const typeLower = (type || '').toLowerCase();
                    const isComfyGroup = typeLower.includes('comfyui');
                    const queueSummary = isComfyGroup ? comfyQueueSummary : null;
                    const queueSummaryTimestamp = queueSummary?.timestamp || comfyQueueSummaryUpdatedAt;
                    return (
                      <div
                        key={`channel-group-${type}`}
                        className="rounded-2xl border border-slate-200/70 bg-white/80 p-5 dark:border-slate-800 dark:bg-slate-900/40"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <div className="text-xs uppercase tracking-[0.35em] text-slate-500">Provider / Type</div>
                            <div className="mt-2 text-lg font-semibold text-slate-900 dark:text-white">{type}</div>
                            <div className="mt-1 text-xs text-slate-600 dark:text-slate-400">
                              {activeCount}/{items.length} active · 建议至少 2 条线路做容灾（主/备）
                            </div>
                            {isComfyGroup && (
                              <div className="mt-2 text-xs text-slate-600 dark:text-slate-400">
                                {comfyQueueSummaryLoading
                                  ? 'ComfyUI 队列：加载中…'
                                  : queueSummary
                                    ? `ComfyUI 队列：running ${queueSummary.totalRunning} · pending ${queueSummary.totalPending}`
                                    : 'ComfyUI 队列：—'}
                                {queueSummaryTimestamp ? (
                                  <span className="ml-2 text-[11px] text-slate-500">
                                    更新：{formatDateTime(queueSummaryTimestamp)}
                                  </span>
                                ) : null}
                              </div>
                            )}
                          </div>
                        </div>

                        <div className="mt-4 space-y-3">
                          {items
                            .slice()
                            .sort((a, b) => (b.weight || 0) - (a.weight || 0))
                            .map((ex) => {
                              const metric = executorTraffic[ex.id];
                              const isComfyExecutor = (ex.type || '').toLowerCase().includes('comfyui');
                              const queueStatus = isComfyExecutor ? comfyQueueByExecutor[ex.id] : null;
                              const modelCatalog = isComfyExecutor ? comfyModelCache[ex.id] : undefined;
                              const modelCounts = isComfyExecutor ? extractComfyuiModelCounts(modelCatalog) : null;
                              const systemInfo = isComfyExecutor ? comfySystemCache[ex.id] : undefined;
                              const versionInfo = isComfyExecutor ? extractComfyuiVersionInfo(ex, systemInfo) : null;
                              const modelLoading = Boolean(comfyModelLoadingByExecutor[ex.id]);
                              const modelError = comfyModelErrorByExecutor[ex.id];
                              const systemLoading = Boolean(comfySystemLoadingByExecutor[ex.id]);
                              const systemError = comfySystemErrorByExecutor[ex.id];
                              return (
                                <div
                                  key={`channel-${ex.id}`}
                                  className="rounded-2xl border border-slate-200 bg-slate-50/50 p-4 dark:border-slate-800 dark:bg-slate-950/20"
                                >
                                  <div className="flex items-start justify-between gap-3">
                                    <div className="min-w-0">
                                      <div className="flex items-center gap-2">
                                        <div className="truncate font-semibold text-slate-900 dark:text-white">
                                          {getExecutorChannelLabel(ex)}
                                        </div>
                                        <StatusPill status={ex.status} />
                                      </div>
                                      <div className="mt-1 truncate text-xs text-slate-600 dark:text-slate-400">
                                        {ex.base_url || '—'}
                                      </div>
                                    </div>
                                    <div className="shrink-0 text-right text-xs text-slate-600 dark:text-slate-400">
                                      <div>
                                        并发/权重：{ex.max_concurrency}/{ex.weight}
                                      </div>
                                      <div>心跳：{ex.last_heartbeat_at ? formatDate(ex.last_heartbeat_at) : '—'}</div>
                                    </div>
                                  </div>

                                  <div className="mt-3 grid gap-2 sm:grid-cols-3">
                                    <div className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700 dark:border-slate-800 dark:bg-slate-950/40 dark:text-slate-300">
                                      <div className="text-[10px] uppercase tracking-widest text-slate-500">24h Calls</div>
                                      <div className="mt-1 text-sm font-semibold text-slate-900 dark:text-white">
                                        {metric ? metric.count : '—'}
                                      </div>
                                    </div>
                                    <div className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700 dark:border-slate-800 dark:bg-slate-950/40 dark:text-slate-300">
                                      <div className="text-[10px] uppercase tracking-widest text-slate-500">Success</div>
                                      <div className="mt-1 text-sm font-semibold text-slate-900 dark:text-white">
                                        {metric && metric.successRate !== null ? `${Math.round(metric.successRate * 100)}%` : '—'}
                                      </div>
                                      {metric?.lastFailedAt && (
                                        <div className="mt-1 text-[11px] text-rose-700 dark:text-rose-300">
                                          最近失败：{formatDateTime(metric.lastFailedAt)}
                                        </div>
                                      )}
                                    </div>
                                    <div className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700 dark:border-slate-800 dark:bg-slate-950/40 dark:text-slate-300">
                                      <div className="text-[10px] uppercase tracking-widest text-slate-500">P95</div>
                                      <div className="mt-1 text-sm font-semibold text-slate-900 dark:text-white">
                                        {metric?.p95Ms ? `${Math.round(metric.p95Ms)}ms` : '—'}
                                      </div>
                                      <div className="mt-1 text-[11px] text-slate-500">
                                        路由：按“分配策略”优先级（后续支持失败/超时自动回退）
                                      </div>
                                    </div>
                                    {isComfyExecutor && (
                                      <div className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700 dark:border-slate-800 dark:bg-slate-950/40 dark:text-slate-300">
                                        <div className="text-[10px] uppercase tracking-widest text-slate-500">Queue</div>
                                        <div className="mt-1 text-sm font-semibold text-slate-900 dark:text-white">
                                          {queueStatus
                                            ? `${queueStatus.runningCount}/${queueStatus.pendingCount}`
                                            : comfyQueueSummaryLoading
                                              ? '加载中…'
                                              : '—'}
                                        </div>
                                        <div className="mt-1 text-[11px] text-slate-500">running/pending</div>
                                        {queueStatus?.message ? (
                                          <div className="mt-1 text-[11px] text-amber-600">{queueStatus.message}</div>
                                        ) : null}
                                      </div>
                                    )}
                                  </div>
                                  {isComfyExecutor && (
                                    <div className="mt-3 grid gap-2 sm:grid-cols-3">
                                      <div className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700 dark:border-slate-800 dark:bg-slate-950/40 dark:text-slate-300">
                                        <div className="text-[10px] uppercase tracking-widest text-slate-500">ComfyUI 版本</div>
                                        <div className="mt-1 text-sm font-semibold text-slate-900 dark:text-white">
                                          {versionInfo?.version || '—'}
                                        </div>
                                        <div className="mt-1 text-[11px] text-slate-500">
                                          节点：{versionInfo?.customNodes || '—'}
                                        </div>
                                        {systemError ? (
                                          <div className="mt-1 text-[11px] text-rose-500">{systemError}</div>
                                        ) : null}
                                      </div>
                                      <div className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700 dark:border-slate-800 dark:bg-slate-950/40 dark:text-slate-300">
                                        <div className="text-[10px] uppercase tracking-widest text-slate-500">模型/LoRA</div>
                                        <div className="mt-1 text-sm font-semibold text-slate-900 dark:text-white">
                                          {modelCatalog ? `${modelCounts?.unet || 0}/${modelCounts?.lora || 0}` : '—'}
                                        </div>
                                        <div className="mt-1 text-[11px] text-slate-500">unet/lora</div>
                                        {modelError ? (
                                          <div className="mt-1 text-[11px] text-rose-500">{modelError}</div>
                                        ) : null}
                                      </div>
                                      <div className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700 dark:border-slate-800 dark:bg-slate-950/40 dark:text-slate-300">
                                        <div className="text-[10px] uppercase tracking-widest text-slate-500">同步标记</div>
                                        <div className="mt-1 text-sm font-semibold text-slate-900 dark:text-white">
                                          {versionInfo?.syncRole || '—'}
                                        </div>
                                        <div className="mt-1 text-[11px] text-slate-500">
                                          {versionInfo?.lastSyncAt ? `更新：${versionInfo.lastSyncAt}` : '未标记时间'}
                                        </div>
                                        <div className="mt-2 grid grid-cols-2 gap-2">
                                          <button
                                            className="rounded border border-slate-300 bg-white px-2 py-1 text-[11px] text-slate-700 hover:bg-slate-50 disabled:opacity-60 dark:border-slate-700 dark:bg-slate-950/60 dark:text-slate-200 dark:hover:bg-slate-900/60"
                                            onClick={() => refreshComfyuiSystemStats(ex.id)}
                                            disabled={systemLoading}
                                          >
                                            {systemLoading ? '同步中…' : '拉取版本'}
                                          </button>
                                          <button
                                            className="rounded border border-slate-300 bg-white px-2 py-1 text-[11px] text-slate-700 hover:bg-slate-50 disabled:opacity-60 dark:border-slate-700 dark:bg-slate-950/60 dark:text-slate-200 dark:hover:bg-slate-900/60"
                                            onClick={() => refreshComfyuiModelCatalog(ex.id)}
                                            disabled={modelLoading}
                                          >
                                            {modelLoading ? '同步中…' : '拉取模型'}
                                          </button>
                                        </div>
                                      </div>
                                    </div>
                                  )}
                                </div>
                              );
                            })}
                        </div>
                      </div>
                    );
                  })}
                </div>
              );
            })()}
          </div>
        ) : (
          <Space direction="vertical" size="large" style={{ width: '100%' }}>
            <Row gutter={[16, 16]}>
              <Col xs={12} lg={7}>
                <Card bordered title="节点列表" style={{ width: '100%' }}>
                  <Space direction="vertical" size="small" style={{ width: '100%' }}>
                    <Typography.Text theme="secondary">
                      小贴士：并发（max_concurrency）保存后会立即生效；建议从 1~4 起逐步放量。
                    </Typography.Text>
                    <div style={{ overflowX: 'auto' }}>
                      <table style={{ width: '100%' }}>
                        <thead>
                          <tr style={{ textAlign: 'left' }}>
                            <th style={{ padding: '8px 6px' }}>名称</th>
                            <th style={{ padding: '8px 6px' }}>类型</th>
                            <th style={{ padding: '8px 6px' }}>状态</th>
                            <th style={{ padding: '8px 6px', width: 220 }}>并发</th>
                            <th style={{ padding: '8px 6px', width: 140 }}>权重</th>
                            <th style={{ padding: '8px 6px', width: 160 }}>心跳</th>
                            <th style={{ padding: '8px 6px', width: 120 }} />
                          </tr>
                        </thead>
                        <tbody>
                          {executors.map((ex) => {
                            const draft = Number(executorInlineConcurrency[ex.id] ?? ex.max_concurrency ?? 1) || 1;
                            const changed = draft !== ex.max_concurrency;
                            const saving = Boolean(executorInlineSaving[ex.id]);
                            const err = executorInlineError[ex.id];
                            const isComfyExecutor = (ex.type || '').toLowerCase().includes('comfyui');
                            const systemInfo = isComfyExecutor ? comfySystemCache[ex.id] : undefined;
                            const versionInfo = isComfyExecutor ? extractComfyuiVersionInfo(ex, systemInfo) : null;
                            const modelCatalog = isComfyExecutor ? comfyModelCache[ex.id] : undefined;
                            const modelCounts = isComfyExecutor ? extractComfyuiModelCounts(modelCatalog) : null;
                            const modelLoading = Boolean(comfyModelLoadingByExecutor[ex.id]);
                            const systemLoading = Boolean(comfySystemLoadingByExecutor[ex.id]);
                            return (
                              <tr key={ex.id}>
                                <td style={{ padding: '10px 6px' }}>
                                  <div style={{ fontWeight: 600 }}>{ex.name}</div>
                                  <Typography.Text theme="secondary">{ex.base_url || '—'}</Typography.Text>
                                  {isComfyExecutor && (
                                    <div className="mt-1 text-[11px] text-slate-500">
                                      版本：{versionInfo?.version || '—'} · 模型/LoRA：{modelCatalog ? `${modelCounts?.unet || 0}/${modelCounts?.lora || 0}` : '—'}
                                    </div>
                                  )}
                                </td>
                                <td style={{ padding: '10px 6px' }}>
                                  <Typography.Text theme="secondary">{ex.type}</Typography.Text>
                                </td>
                                <td style={{ padding: '10px 6px' }}>
                                  <StatusPill status={ex.status} />
                                </td>
                                <td style={{ padding: '10px 6px' }}>
                                  <Space direction="vertical" size={2}>
                                    <Space align="center" size="small">
                                      <InputNumber
                                        size="small"
                                        min={1}
                                        max={50}
                                        value={draft}
                                        onChange={(v) =>
                                          setExecutorInlineConcurrency((prev) => ({ ...prev, [ex.id]: Number(v) || 1 }))
                                        }
                                      />
                                      <Button
                                        size="small"
                                        theme="primary"
                                        disabled={!changed || saving}
                                        loading={saving}
                                        onClick={() => saveExecutorConcurrency(ex.id)}
                                      >
                                        保存
                                      </Button>
                                    </Space>
                                    {err ? (
                                      <Typography.Text theme="error" style={{ fontSize: 12 }}>
                                        {err}
                                      </Typography.Text>
                                    ) : null}
                                  </Space>
                                </td>
                                <td style={{ padding: '10px 6px' }}>
                                  <Typography.Text theme="secondary">{ex.weight}</Typography.Text>
                                </td>
                                <td style={{ padding: '10px 6px' }}>
                                  <Typography.Text theme="secondary">{ex.last_heartbeat_at || '—'}</Typography.Text>
                                </td>
                                <td style={{ padding: '10px 6px' }}>
                                  <Space size="small">
                                    <Button
                                      size="small"
                                      variant="text"
                                      onClick={() => {
                                        const { config, ...rest } = ex;
                                        setExecutorForm({ ...rest, config: stringifyJSON(config) });
                                        setExecutorFormError(null);
                                      }}
                                    >
                                      编辑
                                    </Button>
                                    {isComfyExecutor && (
                                      <>
                                        <Button
                                          size="small"
                                          variant="text"
                                          disabled={systemLoading}
                                          onClick={() => refreshComfyuiSystemStats(ex.id)}
                                        >
                                          {systemLoading ? '同步中…' : '拉取版本'}
                                        </Button>
                                        <Button
                                          size="small"
                                          variant="text"
                                          disabled={modelLoading}
                                          onClick={() => refreshComfyuiModelCatalog(ex.id)}
                                        >
                                          {modelLoading ? '同步中…' : '拉取模型'}
                                        </Button>
                                      </>
                                    )}
                                    <Button size="small" theme="danger" variant="text" onClick={() => handleDelete('executor', ex.id)}>
                                      删除
                                    </Button>
                                  </Space>
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </Space>
                </Card>
              </Col>

              <Col xs={12} lg={5}>
                <Card bordered title={executorForm.id ? '编辑节点' : '新增节点'} style={{ width: '100%' }}>
                  <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                    {executorFormError ? <Alert theme="error" message={executorFormError} /> : null}
                    <div>
                      <Typography.Text strong>名称</Typography.Text>
                      <div style={{ marginTop: 8 }}>
                        <Input value={String(executorForm.name || '')} onChange={(v) => setExecutorForm({ ...executorForm, name: String(v) })} placeholder="例如：KIE Market · Default Node" />
                      </div>
                    </div>

                    <div>
                      <Space align="center" size="small">
                        <Typography.Text strong>类型</Typography.Text>
                        <Tooltip content="常用：comfyui / kie / volcengine / baidu。用于路由与测试分支。">
                          <Typography.Text theme="secondary">?</Typography.Text>
                        </Tooltip>
                      </Space>
                      <div style={{ marginTop: 8 }}>
                        <Input
                          value={String(executorForm.type || '')}
                          onChange={(v) => {
                            const nextType = String(v);
                            setExecutorForm((prev) => {
                              const base = { ...prev, type: nextType };
                              const norm = nextType.trim().toLowerCase();
                              if (!base.base_url) {
                                if (norm.includes('kie')) base.base_url = 'https://api.kie.ai';
                                else if (norm.includes('volc') || norm.includes('ark')) base.base_url = 'https://ark.cn-beijing.volces.com';
                                else if (norm.includes('baidu')) base.base_url = 'https://aip.baidubce.com';
                              }
                              return base;
                            });
                          }}
                          placeholder="comfyui / kie / volcengine / baidu"
                        />
                      </div>
                      <div style={{ marginTop: 8 }}>
                        <Space size="small">
                          {['comfyui', 'kie', 'volcengine', 'baidu'].map((t) => (
                            <Button key={`ex-type-${t}`} size="small" variant="outline" onClick={() => setExecutorForm((prev) => ({ ...prev, type: t }))}>
                              {t}
                            </Button>
                          ))}
                        </Space>
                      </div>
                    </div>

                    <div>
                      <Typography.Text strong>Base URL</Typography.Text>
                      <Typography.Text theme="secondary" style={{ marginLeft: 8 }}>
                        （可选：部分 provider 也可在 config.baseUrl 填）
                      </Typography.Text>
                      <div style={{ marginTop: 8 }}>
                        <Input
                          value={String(executorForm.base_url || '')}
                          onChange={(v) => setExecutorForm({ ...executorForm, base_url: String(v) })}
                          placeholder="http://<ip>:<port> 或 https://..."
                        />
                      </div>
                    </div>

                    <Row gutter={[12, 12]}>
                      <Col xs={6}>
                        <Typography.Text strong>状态</Typography.Text>
                        <div style={{ marginTop: 8 }}>
                          <Select
                            value={String(executorForm.status || 'inactive')}
                            options={[
                              { label: 'active', value: 'active' },
                              { label: 'inactive', value: 'inactive' },
                            ]}
                            onChange={(v) => setExecutorForm({ ...executorForm, status: String(v) })}
                          />
                        </div>
                      </Col>
                      <Col xs={6}>
                        <Typography.Text strong>权重</Typography.Text>
                        <div style={{ marginTop: 8 }}>
                          <InputNumber
                            min={1}
                            max={999}
                            value={Number(executorForm.weight ?? 1)}
                            onChange={(v) => setExecutorForm({ ...executorForm, weight: Number(v) || 1 })}
                          />
                        </div>
                      </Col>
                    </Row>

                    <div>
                      <Space align="center" size="small">
                        <Typography.Text strong>最大并发</Typography.Text>
                        <Tooltip content="1~50。并发越大越容易触发第三方限流/502，建议逐步放量。">
                          <Typography.Text theme="secondary">?</Typography.Text>
                        </Tooltip>
                      </Space>
                      <div style={{ marginTop: 8 }}>
                        <InputNumber
                          min={1}
                          max={50}
                          value={Number(executorForm.max_concurrency ?? 1)}
                          onChange={(v) => setExecutorForm({ ...executorForm, max_concurrency: Number(v) || 1 })}
                        />
                      </div>
                    </div>

                    <Card
                      bordered
                      title="接入配置（推荐用下方表单，不需要懂 JSON）"
                      style={{ background: 'var(--td-bg-color-secondarycontainer)' }}
                    >
                      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                        {executorConfigTemplates.map((item) => (
                          <div key={`ex-cfg-${item.key}`}>
                            <Space align="center" size="small">
                              <Typography.Text strong>{item.label}</Typography.Text>
                              <Typography.Text theme="secondary">{item.hint}</Typography.Text>
                            </Space>
                            <div style={{ marginTop: 8 }}>
                              <Input
                                value={String((executorConfigRecord as any)?.[item.key] ?? '')}
                                placeholder={item.placeholder}
                                onChange={(v) => setExecutorConfigField(item.key, String(v))}
                              />
                            </div>
                          </div>
                        ))}
                        <div>
                          <Typography.Text theme="secondary">
                            高级：如需更多字段，可展开 JSON 编辑器（保存时会校验 JSON）。
                          </Typography.Text>
                        </div>
                      </Space>
                    </Card>

                    <div>
                      <Space align="center" size="small">
                        <Typography.Text strong>配置 JSON（高级）</Typography.Text>
                        {executorConfigJsonInvalid ? (
                          <Typography.Text theme="error" style={{ fontSize: 12 }}>
                            JSON 无效
                          </Typography.Text>
                        ) : (
                          <Typography.Text theme="secondary" style={{ fontSize: 12 }}>
                            JSON 有效
                          </Typography.Text>
                        )}
                      </Space>
                      <div style={{ marginTop: 8 }}>
                        <Textarea
                          value={String(executorForm.config || '')}
                          onChange={(v) => setExecutorForm({ ...executorForm, config: String(v) })}
                          autosize={{ minRows: 5, maxRows: 10 }}
                          placeholder='例如：{"apiKey":"***","baseUrl":"https://api.kie.ai"}'
                        />
                      </div>
                    </div>

                    <Space style={{ width: '100%' }}>
                      <Button theme="primary" style={{ flex: 1 }} onClick={handleExecutorSubmit}>
                        保存
                      </Button>
                      {executorForm.id ? (
                        <Button variant="outline" onClick={() => { setExecutorForm(defaultExecutorForm); setExecutorFormError(null); }}>
                          取消
                        </Button>
                      ) : null}
                    </Space>
                  </Space>
                </Card>
              </Col>
            </Row>
          </Space>
        )}
      </Section>
          )}

          {activeNav === 'abilities' && (
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
          )}

          {activeNav === 'abilities' && (
      <Section
        id="ability-api"
        title="统一能力接口"
        description="面向客户端/业务方公开的 `/api/abilities` 清单与调用示例，便于快速查找能力 ID、输入要求、是否支持多图等。"
      >
        <Card bordered>
          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
            <Space align="start" style={{ justifyContent: 'space-between', width: '100%' }}>
              <Typography.Text theme="secondary">
                所有终端都应通过{' '}
                <Tag theme="primary" variant="outline" size="small">
                  GET /api/abilities
                </Tag>{' '}
                查询能力，并使用{' '}
                <Tag theme="primary" variant="outline" size="small">
                  POST /api/abilities/&lt;abilityId&gt;/invoke
                </Tag>{' '}
                触发；调度层会根据能力配置、绑定规则与执行节点健康度自行分配资源。
              </Typography.Text>
              <Button variant="outline" size="small" loading={publicAbilitiesLoading} onClick={refreshPublicAbilities}>
                刷新列表
              </Button>
            </Space>

            <div>
              <Typography.Text theme="secondary">调用示例（可复制到 Postman / cURL）</Typography.Text>
              <CodeBlock value={abilityApiExample} maxHeight={260} />
            </div>

            <div>
              <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
                <Typography.Text theme="secondary">能力 ID 清单</Typography.Text>
                <Typography.Text theme="secondary">更多细节见 docs/api/abilities.md</Typography.Text>
              </Space>
              <div style={{ marginTop: 12 }}>
                <Table
                  rowKey="id"
                  size="small"
                  data={publicAbilities}
                  loading={publicAbilitiesLoading}
                  maxHeight={360}
                  columns={[
                    {
                      colKey: 'displayName',
                      title: '能力',
                      ellipsis: true,
                      cell: ({ row }) => (
                        <Space direction="vertical" size={2}>
                          <Typography.Text>{row.displayName}</Typography.Text>
                          <Typography.Text theme="secondary">
                            {getProviderLabel(row.provider)} · {getCategoryLabel(row.category)}
                          </Typography.Text>
                          {row.description ? <Typography.Text theme="secondary">{row.description}</Typography.Text> : null}
                        </Space>
                      ),
                    },
                    {
                      colKey: 'id',
                      title: 'Ability ID',
                      width: 360,
                      cell: ({ row }) => (
                        <Space>
                          <Tag theme="default" variant="outline">
                            {row.id}
                          </Tag>
                          <Button size="small" variant="text" onClick={() => copyTextToClipboard(row.id)}>
                            复制
                          </Button>
                        </Space>
                      ),
                    },
                    {
                      colKey: 'features',
                      title: '特性',
                      width: 240,
                      cell: ({ row }) => (
                        <Space direction="vertical" size={2}>
                          {row.requiresImage ? <Typography.Text theme="secondary">需图片输入</Typography.Text> : null}
                          {row.supportsMultipleImages ? <Typography.Text theme="secondary">多图输出</Typography.Text> : null}
                          {row.maxOutputImages ? (
                            <Typography.Text theme="secondary">最高 {row.maxOutputImages} 张结果</Typography.Text>
                          ) : null}
                          {!row.requiresImage && !row.supportsMultipleImages && !row.maxOutputImages ? (
                            <Typography.Text theme="secondary">标准调用</Typography.Text>
                          ) : null}
                        </Space>
                      ),
                    },
                  ]}
                  empty={
                    <Typography.Text theme="secondary">
                      暂无可用能力，请先在“能力管理”新增并设为 active。
                    </Typography.Text>
                  }
                />
              </div>
            </div>
          </Space>
        </Card>
      </Section>
          )}

          {activeNav === 'ability-logs' && (
      <Section
        id="ability-logs"
        title="能力调用记录"
        description="展示最近能力调用日志（不限能力 ID），支持按厂商/来源/状态/关键词筛选与导出，便于回溯来源、节点与成本。"
      >
        <Card bordered>
          <Space direction="vertical" size="large" style={{ width: '100%' }}>
            <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
              <div>
                <Typography.Text strong>能力调用清单</Typography.Text>
                <div>
                  <Typography.Text theme="secondary">
                    已加载 {globalAbilityLogs.length}
                    {typeof globalAbilityLogTotal === 'number' ? ` / ${globalAbilityLogTotal}` : ''} 条 · 支持导出最近 24h
                  </Typography.Text>
                </div>
              </div>
              <Space>
                <Space align="center" size="small">
                  <Typography.Text theme="secondary">自动刷新</Typography.Text>
                  <Switch value={globalAbilityLogsAutoRefresh} onChange={(v) => setGlobalAbilityLogsAutoRefresh(Boolean(v))} />
                </Space>
                {globalAbilityLogsUpdatedAt ? (
                  <Typography.Text theme="secondary">更新：{formatDateTime(globalAbilityLogsUpdatedAt)}</Typography.Text>
                ) : null}
                <Button variant="outline" loading={globalAbilityLogsLoading} onClick={() => refreshGlobalAbilityLogs()}>
                  刷新
                </Button>
                <Button variant="outline" loading={abilityLogMetricsLoading} onClick={() => refreshAbilityLogMetrics()}>
                  刷新指标
                </Button>
                <Button
                  variant="outline"
                  loading={exportingAbilityLogs}
                  onClick={async () => {
                    setExportingAbilityLogs(true);
                    try {
                      const blob = await adminApi.exportAbilityLogs({ format: 'csv', sinceHours: 24 });
                      const filename = `ability_logs_24h_${new Date().toISOString().slice(0, 10)}.csv`;
                      downloadBlob(blob, filename);
                    } catch (err: any) {
                      console.error('Export ability logs failed:', err);
                      setGlobalAbilityLogsError(err?.message || '导出失败');
                    } finally {
                      setExportingAbilityLogs(false);
                    }
                  }}
                >
                  导出 CSV
                </Button>
                <Button
                  variant="outline"
                  loading={exportingAbilityLogs}
                  onClick={async () => {
                    setExportingAbilityLogs(true);
                    try {
                      const blob = await adminApi.exportAbilityLogs({ format: 'json', sinceHours: 24 });
                      const filename = `ability_logs_24h_${new Date().toISOString().slice(0, 10)}.json`;
                      downloadBlob(blob, filename);
                    } catch (err: any) {
                      console.error('Export ability logs failed:', err);
                      setGlobalAbilityLogsError(err?.message || '导出失败');
                    } finally {
                      setExportingAbilityLogs(false);
                    }
                  }}
                >
                  导出 JSON
                </Button>
              </Space>
            </Space>

            {globalAbilityLogsError ? <Alert theme="error" message={globalAbilityLogsError} /> : null}
            {abilityLogMetricsError ? <Alert theme="error" message={abilityLogMetricsError} /> : null}

            <Row gutter={[12, 12]}>
              <Col flex="auto">
                <Input
                  value={globalAbilityLogSearch}
                  placeholder="搜索：能力名/Key/节点/Trace/Task…"
                  onChange={(v) => setGlobalAbilityLogSearch(String(v))}
                  clearable
                />
              </Col>
              <Col flex="180px">
                <Select
                  value={globalAbilityLogProvider}
                  onChange={(v) => setGlobalAbilityLogProvider(String(v))}
                  options={[
                    { label: '全部厂商', value: 'all' },
                    ...globalAbilityLogProviders.map((p) => ({ label: p, value: p })),
                  ]}
                />
              </Col>
              <Col flex="180px">
                <Select
                  value={globalAbilityLogSource}
                  onChange={(v) => setGlobalAbilityLogSource(String(v))}
                  options={[
                    { label: '全部来源', value: 'all' },
                    ...globalAbilityLogSources.map((s) => ({ label: formatAbilitySource(s), value: s })),
                  ]}
                />
              </Col>
              <Col flex="180px">
                <Select
                  value={globalAbilityLogStatus}
                  onChange={(v) => setGlobalAbilityLogStatus(String(v))}
                  options={[
                    { label: '全部状态', value: 'all' },
                    ...globalAbilityLogStatuses.map((s) => ({ label: getAbilityLogStatusTag(s).text, value: s })),
                  ]}
                />
              </Col>
            </Row>

            {abilityLogMetrics?.buckets && abilityLogMetrics.buckets.length > 0 ? (
              <Card bordered title={`近 ${abilityLogMetrics.window_hours}h 指标（Top 8）`}>
                <Table
                  size="small"
                  rowKey="__key"
                  data={(abilityLogMetrics.buckets as AbilityLogMetricBucket[])
                    .slice(0, 8)
                    .map((b) => ({ ...b, __key: `${b.ability_provider}:${b.capability_key}` }))}
                  columns={[
                    {
                      colKey: 'ability',
                      title: '能力',
                      cell: ({ row }) => (
                        <Space direction="vertical" size={2}>
                          <Typography.Text strong>{row.capability_key}</Typography.Text>
                          <Typography.Text theme="secondary">{row.ability_provider}</Typography.Text>
                        </Space>
                      ),
                    },
                    {
                      colKey: 'count',
                      title: '次数',
                      width: 120,
                      cell: ({ row }) => (
                        <Typography.Text theme="secondary">
                          {row.count}（{row.success_count}/{row.failed_count}）
                        </Typography.Text>
                      ),
                    },
                    {
                      colKey: 'success_rate',
                      title: '成功率',
                      width: 120,
                      cell: ({ row }) => (
                        <Typography.Text>
                          {row.success_rate !== null && row.success_rate !== undefined ? `${(row.success_rate * 100).toFixed(1)}%` : '—'}
                        </Typography.Text>
                      ),
                    },
                    {
                      colKey: 'p50',
                      title: 'p50 / p95',
                      width: 160,
                      cell: ({ row }) => (
                        <Typography.Text theme="secondary">
                          {row.p50_duration_ms ?? '—'}ms / {row.p95_duration_ms ?? '—'}ms
                        </Typography.Text>
                      ),
                    },
                  ]}
                />
              </Card>
            ) : null}

            <Table
              size="small"
              rowKey="id"
              loading={globalAbilityLogsLoading}
              data={filteredGlobalAbilityLogs}
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
                              Trace: <span style={{ fontFamily: 'monospace' }}>{formatTaskMarker(row.trace_id)}</span>
                            </span>
                          ) : null}
                          {row.workflow_run_id ? (
                            <span>
                              Flow: <span style={{ fontFamily: 'monospace' }}>{formatTaskMarker(row.workflow_run_id)}</span>
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
                  colKey: 'executor',
                  title: '节点',
                  width: 220,
                  cell: ({ row }) => <Typography.Text theme="secondary">{row.executor_name || row.executor_id || '—'}</Typography.Text>,
                },
                {
                  colKey: 'status',
                  title: '状态',
                  width: 160,
                  cell: ({ row }) => (
                    <Space direction="vertical" size={2}>
                      <Tag theme={getAbilityLogStatusTag(row.status).theme} variant="light">
                        {getAbilityLogStatusTag(row.status).text}
                      </Tag>
                      {typeof row.duration_ms === 'number' ? (
                        <Typography.Text theme="secondary" style={{ fontSize: 12 }}>
                          {row.duration_ms}ms
                        </Typography.Text>
                      ) : null}
                    </Space>
                  ),
                },
                {
                  colKey: 'callback',
                  title: '回调',
                  width: 160,
                  cell: ({ row }) => {
                    if (!row.callback_status && !row.callback_http_status && !row.callback_finished_at) {
                      return <Typography.Text theme="secondary">—</Typography.Text>;
                    }
                    return (
                      <Space direction="vertical" size={2}>
                        {row.callback_status ? (
                          <Tag theme={getAbilityLogStatusTag(row.callback_status).theme} variant="light">
                            {getAbilityLogStatusTag(row.callback_status).text}
                          </Tag>
                        ) : null}
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
                    const previewUrl =
                      row.stored_url ||
                      (row.result_assets && row.result_assets.length > 0 ? resolveAssetUrl(row.result_assets[0]) : '') ||
                      '';
                    const canPreviewImage = Boolean(previewUrl) && /\.(png|jpg|jpeg|webp|gif)(\?|#|$)/i.test(previewUrl);
                    return (
                      <Space size="small">
                        {previewUrl ? (
                          canPreviewImage ? (
                            <Popup
                              trigger="hover"
                              placement="left"
                              content={<img src={previewUrl} alt="preview" style={{ maxWidth: 360, maxHeight: 360, display: 'block' }} />}
                            >
                              <Button size="small" variant="text">
                                预览
                              </Button>
                            </Popup>
                          ) : (
                            <Button size="small" variant="text" onClick={() => window.open(previewUrl, '_blank', 'noreferrer')}>
                              打开
                            </Button>
                          )
                        ) : null}
                        <Button
                          size="small"
                          variant="text"
                          onClick={() => {
                            setAbilityLogDetail(row);
                            setAbilityLogResolveError(null);
                            setAbilityLogDetailOpen(true);
                          }}
                        >
                          详情
                        </Button>
                        {row.error_message ? <Typography.Text theme="error">{row.error_message}</Typography.Text> : null}
                        {!previewUrl && !row.error_message ? <Typography.Text theme="secondary">—</Typography.Text> : null}
                      </Space>
                    );
                  },
                },
              ]}
            />
            <div className="flex items-center justify-between">
              <Typography.Text theme="secondary">
                {globalAbilityLogsUpdatedAt ? `最近刷新：${formatDateTime(globalAbilityLogsUpdatedAt)}` : '尚未刷新'}
              </Typography.Text>
              {globalAbilityLogsHasMore ? (
                <Button variant="outline" loading={globalAbilityLogsLoading} onClick={() => loadMoreGlobalAbilityLogs()}>
                  加载更多
                </Button>
              ) : (
                <Typography.Text theme="secondary">已加载全部</Typography.Text>
              )}
            </div>
          </Space>
        </Card>
      </Section>
          )}

          {activeNav === 'abilities' && (
      <Section
        id="abilities"
        title="能力管理"
        description="集中维护各厂商能力、默认参数和绑定节点，后续工作流和测试面板将直接引用这些配置。"
      >
        <Card
          bordered
          title={
            <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
              <div>
                <Typography.Text strong>能力列表</Typography.Text>
                <div>
                  <Typography.Text theme="secondary">新增/编辑改为弹窗，列表占满宽度，操作不再被挤压。</Typography.Text>
                </div>
              </div>
              <Button
                theme="primary"
                onClick={() => {
                  setAbilityForm(defaultAbilityForm);
                  setAbilityRoutingPolicy('auto');
                  setAbilityAllowedExecutors([]);
                  setAbilityRequiredTags('');
                  setAbilityFallbackToDefault(true);
                  setAbilityDialogOpen(true);
                }}
              >
                新增能力
              </Button>
            </Space>
          }
        >
          <Row gutter={[12, 12]}>
            <Col span={4}>
              <Input value={abilitySearch} onChange={(v) => setAbilitySearch(String(v))} placeholder="搜索名称/能力 Key" />
            </Col>
            <Col span={4}>
              <Select
                value={abilityProviderFilter}
                onChange={(v) => setAbilityProviderFilter(String(v))}
                options={[
                  { label: '全部厂商', value: 'all' },
                  ...abilityProviders.map((provider) => ({ label: getProviderLabel(provider), value: provider })),
                ]}
                placeholder="全部厂商"
              />
            </Col>
            <Col span={4}>
              <Select
                value={abilityStatusFilter}
                onChange={(v) => setAbilityStatusFilter(String(v))}
                options={[{ label: '全部状态', value: 'all' }, ...statusOptions]}
                placeholder="全部状态"
              />
            </Col>
          </Row>
          <div style={{ marginTop: 12 }}>
            <Table
              rowKey="id"
              size="small"
              data={filteredAbilities}
              columns={[
                {
                  colKey: 'display_name',
                  title: '名称',
                  ellipsis: {
                    props: { theme: 'light', placement: 'top' },
                    content: ({ row }) => {
                      const issues = getAbilitySchemaIssues(row as Ability);
                      return (
                        <div className="max-w-[360px] text-xs text-slate-900 dark:text-slate-100">
                          <div className="font-semibold">{row.display_name}</div>
                          <div className="mt-1 text-slate-600 dark:text-slate-400">{row.description || '—'}</div>
                          {issues.length > 0 ? (
                            <div className="mt-2 flex flex-wrap gap-1">
                              {issues.map((issue) => (
                                <Tag key={`${row.id}-tooltip-${issue}`} theme="warning" variant="light" size="small">
                                  {issue}
                                </Tag>
                              ))}
                            </div>
                          ) : null}
                        </div>
                      );
                    },
                  },
                  cell: ({ row }) => {
                    const issues = getAbilitySchemaIssues(row);
                    return (
                      <Space direction="vertical" size={2}>
                        <Typography.Text strong>{row.display_name}</Typography.Text>
                        <Typography.Text theme="secondary">{row.description || '—'}</Typography.Text>
                        {issues.length > 0 ? (
                          <Space size="small" breakLine>
                            {issues.map((issue) => (
                              <Tag key={`${row.id}-${issue}`} theme="warning" variant="light" size="small">
                                {issue}
                              </Tag>
                            ))}
                          </Space>
                        ) : null}
                      </Space>
                    );
                  },
                },
                {
                  colKey: 'provider',
                  title: '厂商/能力',
                  width: 260,
                  cell: ({ row }) => (
                    <Space direction="vertical" size={2}>
                      <Typography.Text>{getProviderLabel(row.provider)}</Typography.Text>
                      <Typography.Text theme="secondary">
                        {row.capability_key} · {getCategoryLabel(row.category)}
                      </Typography.Text>
                      <Typography.Text theme="secondary">
                        {getAbilityTypeLabel(row.ability_type)}
                        {row.workflow_id ? ` · ${workflowLookup[row.workflow_id]?.name || row.workflow_id}` : ''}
                      </Typography.Text>
                    </Space>
                  ),
                },
                { colKey: 'status', title: '状态', width: 120, cell: ({ row }) => renderStatusTag(row.status) },
                {
                  colKey: 'pricing',
                  title: '成本',
                  width: 180,
                  cell: ({ row }) => {
                    const pricing =
                      abilityPricingMap[row.id] || abilityPricingMap[`${row.provider}:${row.capability_key}`] || null;
                    const text = describePricing(pricing);
                    return <Typography.Text theme="secondary">{text !== '—' ? text : '未设置'}</Typography.Text>;
                  },
                },
                {
                  colKey: 'executor',
                  title: '绑定节点',
                  width: 220,
                  cell: ({ row }) => {
                    const bound = row.executor_id ? executors.find((ex) => ex.id === row.executor_id) : null;
                    return (
                      <Typography.Text theme="secondary">
                        {bound ? `${bound.name} · ${bound.type}` : '自动匹配（按厂商/标签）'}
                      </Typography.Text>
                    );
                  },
                },
                {
                  colKey: 'latest',
                  title: '最近调用',
                  width: 220,
                  cell: ({ row }) => {
                    const latestLog = latestAbilityLogMap[row.id];
                    if (!latestLog) return <Typography.Text theme="secondary">—</Typography.Text>;
                    return (
                      <Space direction="vertical" size={2}>
                        <Typography.Text theme="secondary">{formatDateTime(latestLog.created_at)}</Typography.Text>
                        <Space size="small">
                          <Tag theme={getAbilityLogStatusTag(latestLog.status).theme} variant="light" size="small">
                            {getAbilityLogStatusTag(latestLog.status).text}
                          </Tag>
                          {typeof latestLog.duration_ms === 'number' ? (
                            <Typography.Text theme="secondary">{latestLog.duration_ms}ms</Typography.Text>
                          ) : null}
                        </Space>
                      </Space>
                    );
                  },
                },
                {
                  colKey: 'actions',
                  title: '操作',
                  width: 180,
                  cell: ({ row }) => (
                    <Space size="small">
                      <Button
                        size="small"
                        variant="text"
                        onClick={(event) => {
                          event?.stopPropagation?.();
                          handleAbilityEdit(row);
                        }}
                      >
                        编辑
                      </Button>
                      <Button
                        size="small"
                        variant="text"
                        theme="danger"
                        onClick={(event) => {
                          event?.stopPropagation?.();
                          handleAbilityDelete(row.id);
                        }}
                      >
                        删除
                      </Button>
                    </Space>
                  ),
                },
              ]}
              onRowClick={({ row }) => setSelectedAbilityId((row as any).id)}
              rowClassName={({ row }) => ((row as any).id === selectedAbilityId ? 'podi-row-selected' : '')}
              empty={<Typography.Text theme="secondary">暂无满足筛选条件的能力。</Typography.Text>}
            />
          </div>
        </Card>

        <Dialog
          header={abilityForm.id ? '编辑能力' : '新增能力'}
          visible={abilityDialogOpen}
          width={760}
          onClose={() => setAbilityDialogOpen(false)}
          onConfirm={async () => {
            await handleAbilitySubmit();
          }}
        >
          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
            <Row gutter={[12, 12]}>
              <Col span={6}>
                <Typography.Text theme="secondary">厂商</Typography.Text>
                <Select
                  value={abilityForm.provider || providerOptions[0].value}
                  onChange={(v) => setAbilityForm({ ...abilityForm, provider: String(v) })}
                  options={providerOptions}
                />
              </Col>
              <Col span={6}>
                <Typography.Text theme="secondary">能力类型</Typography.Text>
                <Select
                  value={abilityForm.ability_type || abilityTypeOptions[0].value}
                  onChange={(v) => setAbilityForm({ ...abilityForm, ability_type: String(v) })}
                  options={abilityTypeOptions}
                />
              </Col>
              <Col span={6}>
                <Typography.Text theme="secondary">能力分类</Typography.Text>
                <Select
                  value={abilityForm.category || categoryOptions[0].value}
                  onChange={(v) => setAbilityForm({ ...abilityForm, category: String(v) })}
                  options={categoryOptions}
                />
              </Col>
              <Col span={6}>
                <Typography.Text theme="secondary">状态</Typography.Text>
                <Select
                  value={abilityForm.status || statusOptions[0].value}
                  onChange={(v) => setAbilityForm({ ...abilityForm, status: String(v) })}
                  options={statusOptions}
                />
              </Col>
            </Row>

            <Row gutter={[12, 12]}>
              <Col span={12}>
                <Typography.Text theme="secondary">能力 Key</Typography.Text>
                <Input
                  value={abilityForm.capability_key || ''}
                  onChange={(v) => setAbilityForm({ ...abilityForm, capability_key: String(v) })}
                  placeholder="例如 quality_upgrade"
                />
              </Col>
              <Col span={12}>
                <Typography.Text theme="secondary">展示名称</Typography.Text>
                <Input
                  value={abilityForm.display_name || ''}
                  onChange={(v) => setAbilityForm({ ...abilityForm, display_name: String(v) })}
                  placeholder="例如 百度无损放大"
                />
              </Col>
            </Row>

            <div>
              <Typography.Text theme="secondary">描述（选填）</Typography.Text>
              <Input
                value={abilityForm.description || ''}
                onChange={(v) => setAbilityForm({ ...abilityForm, description: String(v) })}
                placeholder="一句话说明用途"
              />
            </div>

            <Row gutter={[12, 12]}>
              <Col span={12}>
                <Typography.Text theme="secondary">默认节点（可选）</Typography.Text>
                <Select
                  value={abilityForm.executor_id || ''}
                  onChange={(v) => setAbilityForm({ ...abilityForm, executor_id: String(v) || undefined })}
                  options={[
                    { label: '自动匹配', value: '' },
                    ...executors.map((executor) => ({
                      label: `${executor.name} · ${executor.type}`,
                      value: executor.id,
                    })),
                  ]}
                  placeholder="自动匹配"
                />
              </Col>
              <Col span={12}>
                <Typography.Text theme="secondary">关联工作流（可选）</Typography.Text>
                <Select
                  value={abilityForm.workflow_id || ''}
                  onChange={(v) => setAbilityForm({ ...abilityForm, workflow_id: String(v) || undefined })}
                  options={[
                    { label: '未绑定', value: '' },
                    ...workflows.map((workflow) => ({
                      label: `${workflow.name} · ${workflow.version || workflow.type}`,
                      value: workflow.id,
                    })),
                  ]}
                  placeholder="未绑定"
                />
              </Col>
            </Row>

            {abilityForm.provider === 'comfyui' ? (
              <div className="rounded-2xl border border-slate-200/70 bg-slate-50/40 p-4 dark:border-slate-800 dark:bg-slate-950/40">
                <Space direction="vertical" size="small" style={{ width: '100%' }}>
                  <Typography.Text strong>ComfyUI 路由策略（面向非技术同学的配置）</Typography.Text>
                  <Typography.Text theme="secondary">
                    这些字段会写入 ability.metadata，用于控制“哪些节点可用、如何分配、是否允许回退默认节点”。
                  </Typography.Text>

                  <Row gutter={[12, 12]}>
                    <Col span={12}>
                      <Typography.Text theme="secondary">路由策略 routing_policy</Typography.Text>
                      <Select
                        value={abilityRoutingPolicy}
                        onChange={(v) => setAbilityRoutingPolicy(String(v) || 'auto')}
                        options={[
                          { label: '自动（默认：跟随系统设置）', value: 'auto' },
                          { label: '按队列最短（queue）', value: 'queue' },
                          { label: '按权重随机（weight）', value: 'weight' },
                          { label: '轮询（round_robin）', value: 'round_robin' },
                          { label: '固定第一个（fixed）', value: 'fixed' },
                        ]}
                      />
                      <Typography.Text theme="secondary" style={{ fontSize: 12, display: 'block', marginTop: 6 }}>
                        建议：对性能敏感可用 weight/round_robin，想避开排队可用 queue。
                      </Typography.Text>
                    </Col>
                    <Col span={12}>
                      <Space align="center" size="small">
                        <Typography.Text theme="secondary">回退到默认节点</Typography.Text>
                        <Tooltip content="当没有符合条件的节点时，是否允许系统回退到默认/绑定节点。">
                          <Typography.Text theme="secondary">?</Typography.Text>
                        </Tooltip>
                      </Space>
                      <div style={{ marginTop: 8 }}>
                        <Switch value={abilityFallbackToDefault} onChange={(v) => setAbilityFallbackToDefault(Boolean(v))} />
                      </div>
                      <Typography.Text theme="secondary" style={{ fontSize: 12, display: 'block', marginTop: 6 }}>
                        关闭后：不匹配即报错，适合严格分机的生产能力。
                      </Typography.Text>
                    </Col>
                  </Row>

                  <div>
                    <Typography.Text theme="secondary">允许运行节点（多选）</Typography.Text>
                    {comfyExecutors.length > 0 ? (
                      <select
                        multiple
                        value={abilityAllowedExecutors}
                        onChange={(e) =>
                          setAbilityAllowedExecutors(Array.from(e.target.selectedOptions).map((option) => option.value))
                        }
                        className="mt-2 h-32 w-full rounded-2xl border border-slate-300 bg-white px-4 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-950/70 dark:text-white"
                      >
                        {comfyExecutors.map((executor) => (
                          <option key={`ability-executor-${executor.id}`} value={executor.id}>
                            {executor.name} · {executor.base_url || executor.type}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <div className="mt-2 rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-4 py-3 text-slate-700 dark:border-slate-700 dark:bg-slate-950/40 dark:text-slate-500">
                        还没有 ComfyUI 执行节点，请先在“执行节点”里新增。
                      </div>
                    )}
                    <Typography.Text theme="secondary" style={{ fontSize: 12, display: 'block', marginTop: 6 }}>
                      不选表示“允许系统自动匹配所有 ComfyUI 节点”。
                    </Typography.Text>
                  </div>

                  <div>
                    <Typography.Text theme="secondary">要求标签（required_tags，可多选）</Typography.Text>
                    <Input
                      value={abilityRequiredTags}
                      onChange={(v) => setAbilityRequiredTags(String(v))}
                      placeholder="例如：gpu:4090, region:hz, comfyui-158"
                    />
                    <Typography.Text theme="secondary" style={{ fontSize: 12, display: 'block', marginTop: 6 }}>
                      逗号分隔。要求执行节点 config.tags 中包含全部标签。
                    </Typography.Text>
                  </div>
                </Space>
              </div>
            ) : null}

            {abilityForm.provider === 'coze' ? (
              <div>
                <Typography.Text theme="secondary">Coze Workflow ID</Typography.Text>
                <Input
                  value={abilityForm.coze_workflow_id || ''}
                  onChange={(v) =>
                    setAbilityForm({
                      ...abilityForm,
                      coze_workflow_id: String(v).trim() ? String(v).trim() : undefined,
                    })
                  }
                  placeholder="例如 1234567890"
                />
              </div>
            ) : null}

            <div>
              <Typography.Text theme="secondary">默认参数 JSON</Typography.Text>
              <Textarea
                value={abilityForm.default_params || ''}
                onChange={(v) => setAbilityForm({ ...abilityForm, default_params: String(v) })}
                autosize={{ minRows: 3, maxRows: 8 }}
              />
            </div>

            <div>
              <Typography.Text theme="secondary">输入表单 Schema（选填）</Typography.Text>
              <Textarea
                value={abilityForm.input_schema || ''}
                onChange={(v) => setAbilityForm({ ...abilityForm, input_schema: String(v) })}
                autosize={{ minRows: 3, maxRows: 8 }}
              />
            </div>

            <div>
              <Typography.Text theme="secondary">其他元信息（选填）</Typography.Text>
              <Textarea
                value={abilityForm.metadata || ''}
                onChange={(v) => setAbilityForm({ ...abilityForm, metadata: String(v) })}
                autosize={{ minRows: 3, maxRows: 8 }}
              />
            </div>
          </Space>
        </Dialog>
      </Section>
          )}

          {activeNav === 'ability-tests' && (
      <Section
        id="ability-tests"
        title="能力详情/测试"
        description="选择在能力目录中配置好的接口，查看能力上下文、Schema、元信息，并在“实时测试”中一键巡检。"
      >
        {abilities.length === 0 ? (
          <Alert
            theme="warning"
            title="暂无可用能力"
            message="请先到“能力管理”新增能力并设为 active（例如：百度 · 无损放大），再回到这里进行测试。"
          />
        ) : (
          <Card bordered title="能力详情 & 链路自检">
            <Space direction="vertical" size="middle" style={{ width: '100%' }}>
              <Space align="start" style={{ justifyContent: 'space-between', width: '100%' }}>
                <Typography.Text theme="secondary">
                  选择能力后，可查看概览、参数、元数据，并直接运行测试/查看日志。
                </Typography.Text>
                {selectedAbility ? (
                  <Space direction="vertical" size={2} style={{ textAlign: 'right' }}>
                    <Typography.Text theme="secondary">Ability ID：{selectedAbility.id}</Typography.Text>
                    <Typography.Text theme="secondary">{selectedAbility.capability_key}</Typography.Text>
                  </Space>
                ) : null}
              </Space>

              <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
                <div style={{ width: 420 }}>
                  <Select
                    value={selectedAbilityId ?? ''}
                    onChange={(v) => setSelectedAbilityId(String(v) || null)}
                    options={[
                      { label: '请选择（或在能力管理中新建）', value: '' },
                      ...abilities.map((ability) => ({
                        label: `${ability.display_name} · ${getProviderLabel(ability.provider)}`,
                        value: ability.id,
                      })),
                    ]}
                    placeholder="快速选择能力"
                  />
                </div>
                <Button variant="outline" onClick={() => selectSection('abilities')}>
                  前往能力管理
                </Button>
              </Space>

              {!selectedAbility ? (
                <Alert theme="info" message="暂未选择能力，请先在下拉框选择，或回到“能力管理”点击一行。" />
              ) : (
                <Tabs
                  theme="card"
                  value={activeAbilityDetailTab}
                  onChange={(v) => setActiveAbilityDetailTab(v as AbilityDetailTab)}
                  list={abilityDetailTabs.map((tab) => ({
                    value: tab.id,
                    label: tab.label,
                    panel: <div style={{ paddingTop: 12 }}>{renderAbilityDetailContent(tab.id)}</div>,
                  }))}
                />
              )}
            </Space>
          </Card>
        )}
      </Section>
          )}
          {activeNav === 'ability-evals' && (
      <Section
        id="ability-evals"
        title="能力评测"
        description="内部迭代工具：统一用 Coze 工作流试运行，并对输出做 1-5 评分与备注。"
      >
        <AbilityEvaluationPage />
      </Section>
          )}
          {activeNav === 'comfyui-templates' && (
      <Section
        id="comfyui-templates"
        title="ComfyUI 模板"
        description="管理本地/云端多台 ComfyUI 服务器的 Workflow JSON，指定允许运行的节点，作为一类原子能力。后续 Workflow Builder 会基于这些模板拼装业务流程。"
      >
        <div className="grid gap-6 lg:grid-cols-[320px_1fr] lg:items-start">
          <div className="rounded-2xl border border-slate-200/70 bg-white/80 p-4 dark:border-slate-800 dark:bg-slate-900/40 lg:sticky lg:top-4">
            <h3 className="mb-4 text-lg font-semibold text-slate-900 dark:text-white">工作流列表</h3>
            <div className="max-h-[460px] overflow-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-left text-[11px] text-slate-700 dark:text-slate-400">
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
                      <td className="text-slate-800 dark:text-slate-300">{wf.action}</td>
                      <td className="font-medium text-slate-900 dark:text-white">{wf.name}</td>
                      <td className="text-slate-800 dark:text-slate-300">{wf.version}</td>
                      <td className="text-xs text-slate-700 dark:text-slate-400">
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
                      <td className="text-xs text-slate-700 dark:text-slate-500">{wf.updated_at || '—'}</td>
                      <td className="text-right text-xs space-x-2">
                        <button
                          className="text-sky-400"
                          onClick={() => {
                            const { definition, metadata, ...rest } = wf;
                            const parsedMeta = (metadata ? parseJSON(metadata) : {}) as JsonRecord;
                            setWorkflowForm({
                              ...rest,
                              definition: stringifyJSON(definition),
                              metadata: stringifyJSON(metadata),
                            });
                            setWorkflowFormAllowedExecutors(extractAllowedExecutorIds(parsedMeta));
                            setWorkflowInputMap(normalizeInputNodeMap(parsedMeta));
                            setWorkflowOutputNodeIds(normalizeOutputNodeIds(parsedMeta));
                            setWorkflowOutputPickerNodeId('');
                            setWorkflowOutputShowAll(false);
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
          <div className="rounded-2xl border border-slate-200/70 bg-white/80 p-4 space-y-3 dark:border-slate-800 dark:bg-slate-900/40">
            <h3 className="text-lg font-semibold text-slate-900 dark:text-white">
              {workflowForm.id ? '编辑工作流' : '导入/新增工作流'}
            </h3>
            <div className="text-sm space-y-2">
              <input
                placeholder="Action"
                value={workflowForm.action || ''}
                onChange={(e) => setWorkflowForm({ ...workflowForm, action: e.target.value })}
                className={formControlClass}
              />
              <input
                placeholder="名称"
                value={workflowForm.name || ''}
                onChange={(e) => setWorkflowForm({ ...workflowForm, name: e.target.value })}
                className={formControlClass}
              />
              <div className="flex gap-3">
                <input
                  placeholder="版本"
                  value={workflowForm.version || ''}
                  onChange={(e) => setWorkflowForm({ ...workflowForm, version: e.target.value })}
                  className={formControlFlexClass}
                />
                <input
                  placeholder="类型"
                  value={workflowForm.type || ''}
                  onChange={(e) => setWorkflowForm({ ...workflowForm, type: e.target.value })}
                  className={formControlFlexClass}
                />
              </div>
              <select
                value={workflowForm.status || 'inactive'}
                onChange={(e) => setWorkflowForm({ ...workflowForm, status: e.target.value })}
                className={formControlClass}
              >
                {statusOptions.map((option) => (
                  <option key={`workflow-status-${option.value}`} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
              <label className="block text-xs text-slate-700 dark:text-slate-400">
                导入 JSON 文件
                <input
                  type="file"
                  accept=".json"
                  onChange={(e) => handleWorkflowFile(e.target.files)}
                  className="mt-1 block w-full text-xs text-slate-700 file:mr-3 file:rounded-lg file:border file:border-slate-300 file:bg-white file:px-3 file:py-1 file:text-xs file:text-slate-700 hover:file:bg-slate-50 dark:text-slate-300 dark:file:border-slate-700 dark:file:bg-slate-950/50 dark:file:text-slate-200 dark:hover:file:bg-slate-900/60"
                />
              </label>
              <textarea
                rows={6}
                placeholder="workflow definition JSON"
                value={workflowForm.definition ?? ''}
                onChange={(e) => setWorkflowForm({ ...workflowForm, definition: e.target.value })}
                className={`${formControlClass} font-mono text-xs`}
              />
              {workflowDefinitionError ? (
                <div className="text-xs text-rose-500">{workflowDefinitionError}</div>
              ) : null}
              <textarea
                rows={4}
                placeholder="metadata JSON（参数映射、依赖等）"
                value={workflowForm.metadata ?? ''}
                onChange={(e) => setWorkflowForm({ ...workflowForm, metadata: e.target.value })}
                className={`${formControlClass} font-mono text-xs`}
              />
              {workflowMetadataError ? (
                <div className="text-xs text-rose-500">{workflowMetadataError}</div>
              ) : null}
              <div className="rounded-2xl border border-slate-200/70 bg-slate-50/80 p-3 space-y-3 dark:border-slate-800 dark:bg-slate-950/40">
                <div className="flex items-center justify-between">
                  <div className="text-sm font-semibold text-slate-900 dark:text-white">节点映射（ComfyUI）</div>
                  <div className="text-[11px] text-slate-500">
                    {comfyWorkflowNodes.length > 0 ? `已解析 ${comfyWorkflowNodes.length} 个节点` : '未解析节点'}
                  </div>
                </div>
                <p className="text-xs text-slate-600 dark:text-slate-400">
                  选择需要对外暴露的输入/输出节点。未选择输出节点时默认返回全部输出；输入未填写时将使用 Workflow JSON
                  默认值。
                </p>
                {comfyWorkflowNodes.length === 0 ? (
                  <div className="rounded-2xl border border-dashed border-slate-300 bg-white px-4 py-3 text-xs text-slate-600 dark:border-slate-700 dark:bg-slate-950/50 dark:text-slate-500">
                    请先导入或粘贴 ComfyUI Workflow JSON，保存后即可解析节点。
                  </div>
                ) : (
                  <>
                    <div className="rounded-2xl border border-slate-200/70 bg-white/70 p-3 space-y-2 dark:border-slate-800 dark:bg-slate-950/50">
                      <div className="text-xs text-slate-700 dark:text-slate-300">快速按节点添加输入映射</div>
                      <div className="space-y-2">
                        <label className="block text-[11px] text-slate-600 dark:text-slate-400">输入节点（含 ID）</label>
                        <select
                          value={workflowInputPickerNodeId}
                          onChange={(e) => {
                            setWorkflowInputPickerNodeId(e.target.value);
                            setWorkflowInputPickerKeys([]);
                          }}
                          className="w-full rounded-2xl border border-slate-300 bg-white px-3 py-2 text-xs text-slate-900 dark:border-slate-700 dark:bg-slate-950/70 dark:text-white"
                        >
                          <option value="">选择输入节点（含 ID）</option>
                          {comfyWorkflowNodes.map((node) => (
                            <option key={`workflow-picker-node-${node.id}`} value={node.id}>
                              #{node.id} · {node.title} · {node.classType}
                            </option>
                          ))}
                        </select>
                        <div className="flex items-center justify-between text-[11px] text-slate-600 dark:text-slate-400">
                          <span>输入 Key（勾选）</span>
                          <div className="space-x-2">
                            <button
                              className="text-slate-500 hover:text-slate-700 dark:hover:text-slate-300"
                              onClick={() =>
                                setWorkflowInputPickerKeys(
                                  comfyWorkflowNodeMap.get(workflowInputPickerNodeId)?.inputs || [],
                                )
                              }
                              disabled={!workflowInputPickerNodeId}
                            >
                              全选
                            </button>
                            <button
                              className="text-slate-500 hover:text-slate-700 dark:hover:text-slate-300"
                              onClick={() => setWorkflowInputPickerKeys([])}
                              disabled={!workflowInputPickerNodeId}
                            >
                              清空
                            </button>
                          </div>
                        </div>
                        <div className="h-28 w-full overflow-auto rounded-2xl border border-slate-300 bg-white px-3 py-2 text-xs text-slate-900 dark:border-slate-700 dark:bg-slate-950/70 dark:text-white">
                          {!workflowInputPickerNodeId ? (
                            <div className="text-slate-500 dark:text-slate-500">请先选择节点</div>
                          ) : (
                            (comfyWorkflowNodeMap.get(workflowInputPickerNodeId)?.inputs || []).map((key) => (
                              <label key={`workflow-picker-input-${workflowInputPickerNodeId}-${key}`} className="flex items-center gap-2 py-0.5">
                                <input
                                  type="checkbox"
                                  checked={workflowInputPickerKeys.includes(key)}
                                  onChange={(e) =>
                                    setWorkflowInputPickerKeys((prev) =>
                                      e.target.checked ? [...prev, key] : prev.filter((item) => item !== key),
                                    )
                                  }
                                />
                                <span>{key}</span>
                              </label>
                            ))
                          )}
                        </div>
                        <button
                          className="w-full rounded border border-slate-300 bg-white px-3 py-2 text-xs text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-700 dark:bg-slate-950/60 dark:text-slate-200 dark:hover:bg-slate-900/60"
                          onClick={addWorkflowInputMappingsForNode}
                          disabled={!workflowInputPickerNodeId || workflowInputPickerKeys.length === 0}
                        >
                          添加到映射
                        </button>
                      </div>
                      <p className="text-[11px] text-slate-600 dark:text-slate-500">
                        以节点 ID 为主进行配置；每个输入会自动生成一条映射，参数名默认等于输入 Key，可在下方表格继续调整。
                      </p>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-slate-700 dark:text-slate-400">输入参数映射</span>
                      <button
                        className="rounded border border-slate-300 bg-white px-2 py-1 text-xs text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-950/60 dark:text-slate-200 dark:hover:bg-slate-900/60"
                        onClick={addWorkflowInputMap}
                      >
                        添加映射
                      </button>
                    </div>
                    {workflowInputMap.length === 0 ? (
                      <div className="rounded-2xl border border-dashed border-slate-300 bg-white px-4 py-3 text-xs text-slate-600 dark:border-slate-700 dark:bg-slate-950/50 dark:text-slate-500">
                        尚未配置输入映射。可选择需要暴露给 Coze 的字段。
                      </div>
                    ) : (
                      <div className="space-y-2">
                        <div className="grid grid-cols-[1.2fr_1fr_1fr_0.6fr_auto] gap-2 text-[11px] text-slate-500">
                          <div>参数名</div>
                          <div>节点</div>
                          <div>输入 Key</div>
                          <div>类型</div>
                          <div></div>
                        </div>
                        {workflowInputMap.map((item, idx) => {
                          const node = comfyWorkflowNodeMap.get(item.nodeId);
                          const inputOptions = node?.inputs || [];
                          return (
                            <div key={`workflow-input-${idx}`} className="grid grid-cols-[1.2fr_1fr_1fr_0.6fr_auto] gap-2">
                              <input
                                value={item.field}
                                onChange={(e) => updateWorkflowInputMap(idx, { field: e.target.value })}
                                placeholder="参数名，如 prompt / width"
                                className="rounded-2xl border border-slate-300 bg-white px-3 py-2 text-xs text-slate-900 dark:border-slate-700 dark:bg-slate-950/70 dark:text-white"
                              />
                              <select
                                value={item.nodeId}
                                onChange={(e) => updateWorkflowInputMap(idx, { nodeId: e.target.value, inputKey: '' })}
                                className="rounded-2xl border border-slate-300 bg-white px-3 py-2 text-xs text-slate-900 dark:border-slate-700 dark:bg-slate-950/70 dark:text-white"
                              >
                                <option value="">选择节点</option>
                                {comfyWorkflowNodes.map((nodeOption) => (
                                  <option key={`workflow-node-${nodeOption.id}`} value={nodeOption.id}>
                                    #{nodeOption.id} · {nodeOption.title}
                                  </option>
                                ))}
                              </select>
                              <select
                                value={item.inputKey}
                                onChange={(e) => updateWorkflowInputMap(idx, { inputKey: e.target.value })}
                                disabled={!item.nodeId}
                                className="rounded-2xl border border-slate-300 bg-white px-3 py-2 text-xs text-slate-900 disabled:bg-slate-100 dark:border-slate-700 dark:bg-slate-950/70 dark:text-white dark:disabled:bg-slate-900/40"
                              >
                                <option value="">选择输入</option>
                                {inputOptions.map((key) => (
                                  <option key={`workflow-input-${item.nodeId}-${key}`} value={key}>
                                    {key}
                                  </option>
                                ))}
                              </select>
                              <select
                                value={item.valueType || ''}
                                onChange={(e) => updateWorkflowInputMap(idx, { valueType: e.target.value })}
                                className="rounded-2xl border border-slate-300 bg-white px-3 py-2 text-xs text-slate-900 dark:border-slate-700 dark:bg-slate-950/70 dark:text-white"
                              >
                                <option value="">原样</option>
                                <option value="string">string</option>
                                <option value="int">int</option>
                                <option value="float">float</option>
                                <option value="bool">bool</option>
                                <option value="json">json</option>
                              </select>
                              <button
                                className="rounded border border-slate-200 bg-white px-2 py-1 text-xs text-slate-600 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-950/60 dark:text-slate-200 dark:hover:bg-slate-900/60"
                                onClick={() => removeWorkflowInputMap(idx)}
                              >
                                删除
                              </button>
                            </div>
                          );
                        })}
                      </div>
                    )}
                    <div className="mt-4 space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-slate-700 dark:text-slate-400">输出节点映射（保存图片为主）</span>
                        <div className="space-x-2 text-[11px]">
                          <button
                            className="text-slate-500 hover:text-slate-700 dark:hover:text-slate-300"
                            onClick={() => setWorkflowOutputShowAll((prev) => !prev)}
                          >
                            {workflowOutputShowAll ? '仅显示 SaveImage' : '显示全部节点'}
                          </button>
                          <button
                            className="text-slate-500 hover:text-slate-700 dark:hover:text-slate-300"
                            onClick={() => updateWorkflowOutputNodes([])}
                          >
                            清空输出
                          </button>
                        </div>
                      </div>
                      <div className="grid grid-cols-[1fr_auto] gap-2">
                        <select
                          value={workflowOutputPickerNodeId}
                          onChange={(e) => setWorkflowOutputPickerNodeId(e.target.value)}
                          className="rounded-2xl border border-slate-300 bg-white px-3 py-2 text-xs text-slate-900 dark:border-slate-700 dark:bg-slate-950/70 dark:text-white"
                        >
                          <option value="">选择输出节点（含 ID）</option>
                          {(workflowOutputShowAll
                            ? comfyWorkflowNodes
                            : comfyWorkflowNodes.filter((node) => node.classType.toLowerCase().includes('saveimage'))
                          ).map((node) => (
                            <option key={`workflow-output-picker-${node.id}`} value={node.id}>
                              #{node.id} · {node.title} · {node.classType}
                            </option>
                          ))}
                        </select>
                        <button
                          className="rounded border border-slate-300 bg-white px-3 py-2 text-xs text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-700 dark:bg-slate-950/60 dark:text-slate-200 dark:hover:bg-slate-900/60"
                          onClick={addWorkflowOutputNode}
                          disabled={!workflowOutputPickerNodeId}
                        >
                          添加映射
                        </button>
                      </div>
                      {workflowOutputNodeIds.length === 0 ? (
                        <div className="rounded-2xl border border-dashed border-slate-300 bg-white px-4 py-3 text-xs text-slate-600 dark:border-slate-700 dark:bg-slate-950/50 dark:text-slate-500">
                          未选择输出节点时，默认返回全部输出（建议选择 SaveImage 节点）。
                        </div>
                      ) : (
                        <div className="space-y-2">
                          <div className="grid grid-cols-[1fr_auto] gap-2 text-[11px] text-slate-500">
                            <div>已选输出节点</div>
                            <div></div>
                          </div>
                          {workflowOutputNodeIds.map((nodeId) => {
                            const node = comfyWorkflowNodeMap.get(nodeId);
                            const label = node ? `#${node.id} · ${node.title} · ${node.classType}` : `#${nodeId}`;
                            return (
                              <div key={`workflow-output-picked-${nodeId}`} className="grid grid-cols-[1fr_auto] gap-2">
                                <div className="rounded-2xl border border-slate-300 bg-white px-3 py-2 text-xs text-slate-900 dark:border-slate-700 dark:bg-slate-950/70 dark:text-white">
                                  {label}
                                </div>
                                <button
                                  className="rounded border border-slate-200 bg-white px-2 py-1 text-xs text-slate-600 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-950/60 dark:text-slate-200 dark:hover:bg-slate-900/60"
                                  onClick={() => removeWorkflowOutputNode(nodeId)}
                                >
                                  删除
                                </button>
                              </div>
                            );
                          })}
                        </div>
                      )}
                      <p className="text-[11px] text-slate-600 dark:text-slate-500">
                        输出建议只选 SaveImage 节点，避免返回无用的中间数据。
                      </p>
                    </div>
                    {workflowMappingErrors.length > 0 ? (
                      <div className="rounded-2xl border border-rose-200/80 bg-rose-50/80 p-3 text-xs text-rose-600 dark:border-rose-900/50 dark:bg-rose-950/30">
                        <div className="font-semibold">映射校验未通过：</div>
                        <ul className="mt-2 list-disc space-y-1 pl-5">
                          {workflowMappingErrors.slice(0, 8).map((msg, idx) => (
                            <li key={`workflow-map-error-${idx}`}>{msg}</li>
                          ))}
                        </ul>
                        {workflowMappingErrors.length > 8 ? (
                          <div className="mt-2">…共 {workflowMappingErrors.length} 条</div>
                        ) : null}
                      </div>
                    ) : null}
                  </>
                )}
              </div>
              <label className="block text-xs text-slate-700 dark:text-slate-400">
                允许运行节点（多选）
                {comfyExecutors.length > 0 ? (
                  <select
                    multiple
                    value={workflowFormAllowedExecutors}
                    onChange={(e) =>
                      (() => {
                        const next = Array.from(e.target.selectedOptions).map((option) => option.value);
                        setWorkflowFormAllowedExecutors(next);
                        syncWorkflowMetadata({ allowedExecutorIds: next });
                      })()
                    }
                    className="mt-1 h-32 w-full rounded-2xl border border-slate-300 bg-white px-4 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-950/70 dark:text-white"
                  >
                    {comfyExecutors.map((executor) => (
                      <option key={`workflow-executor-${executor.id}`} value={executor.id}>
                        {executor.name} · {executor.base_url || executor.type}
                      </option>
                    ))}
                  </select>
                ) : (
                  <div className="mt-1 rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-4 py-3 text-slate-700 dark:border-slate-700 dark:bg-slate-950/40 dark:text-slate-500">
                    还没有 ComfyUI 类型的执行节点，请先在“执行节点”中新建，再回到此处绑定允许运行的机器列表。
                  </div>
                )}
                <p className="mt-1 text-[11px] text-slate-700 dark:text-slate-500">
                  用于限制某个 ComfyUI 工作流可以在哪些机器上执行；保存后会写入 metadata.allowed_executor_ids，调度器会据此路由。
                </p>
              </label>
              {workflowFormErrors.length > 0 ? (
                <div className="rounded-2xl border border-rose-200/80 bg-rose-50/80 p-3 text-xs text-rose-600 dark:border-rose-900/50 dark:bg-rose-950/30">
                  <div className="font-semibold">请先处理以下问题：</div>
                  <ul className="mt-2 list-disc space-y-1 pl-5">
                    {workflowFormErrors.slice(0, 8).map((msg, idx) => (
                      <li key={`workflow-form-error-${idx}`}>{msg}</li>
                    ))}
                  </ul>
                  {workflowFormErrors.length > 8 ? <div className="mt-2">…共 {workflowFormErrors.length} 条</div> : null}
                </div>
              ) : null}
              <div className="flex gap-3">
                <button
                  className={`flex-1 rounded py-2 text-white ${
                    workflowSubmitDisabled
                      ? 'bg-slate-400/60 text-slate-200 cursor-not-allowed'
                      : 'bg-sky-500/80 hover:bg-sky-500'
                  }`}
                  onClick={handleWorkflowSubmit}
                  disabled={workflowSubmitDisabled}
                >
                  保存
                </button>
                {workflowForm.id && (
                <button
                  className="rounded border border-slate-300 bg-white px-4 py-2 text-slate-700 hover:bg-slate-50 dark:border-slate-500 dark:bg-transparent dark:text-slate-200"
                  onClick={() => {
                    setWorkflowForm(defaultWorkflowForm);
                    setWorkflowFormAllowedExecutors([]);
                    setWorkflowInputMap([]);
                    setWorkflowOutputNodeIds([]);
                    setWorkflowOutputPickerNodeId('');
                    setWorkflowOutputShowAll(false);
                    setWorkflowFormErrors([]);
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
          )}
          {activeNav === 'workflow-builder' && (
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
                <Space breakLine>
                  <Button variant="outline" disabled={!cozeBaseUrl} onClick={handleOpenCozeStudio}>
                    打开 Coze Studio
                  </Button>
                  <Button variant="outline" disabled={!cozeLoopUrl} onClick={handleOpenCozeLoop}>
                    打开 Coze Loop
                  </Button>
                </Space>
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
          )}

          {activeNav === 'bindings' && (
      <Section
        id="bindings"
        title="分配策略"
        description="为业务入口（Action）配置工作流与执行节点的回退链路，优先级越大越先尝试，用于多节点容灾/流量分摊。"
      >
        <div style={{ margin: '0 0 12px' }}>
          <Typography.Text theme="secondary">
          例如：`action=pattern.extract` 可以先指向云端 ComfyUI 节点，若排队或失败再回落到本地节点；也可以为百度/火山能力配置不同 API Key 的执行器，实现配额切换。
          </Typography.Text>
        </div>

        <Row gutter={[16, 16]}>
          <Col xs={12} lg={8}>
            <Card title="绑定列表" bordered>
              <Table
                rowKey="id"
                data={bindings as any}
                columns={
                  [
                    { colKey: 'action', title: 'Action', width: 220 },
                    { colKey: 'workflow_id', title: 'Workflow ID', width: 220 },
                    { colKey: 'executor_id', title: 'Executor ID', width: 220 },
                    { colKey: 'priority', title: '优先级', width: 100 },
                    {
                      colKey: 'enabled',
                      title: '启用',
                      width: 90,
                      cell: ({ row }: any) => <StatusPill status={row.enabled ? 'ON' : 'OFF'} />,
                    },
                    {
                      colKey: 'op',
                      title: '操作',
                      width: 140,
                      fixed: 'right',
                      cell: ({ row }: any) => (
                        <Space>
                          <Button size="small" variant="text" onClick={() => setBindingForm(row)}>
                            编辑
                          </Button>
                          <Button size="small" variant="text" theme="danger" onClick={() => handleDelete('binding', row.id)}>
                            删除
                          </Button>
                        </Space>
                      ),
                    },
                  ] as any
                }
              />
            </Card>
          </Col>

          <Col xs={12} lg={4}>
            <Card title={bindingForm.id ? '编辑绑定' : '新增绑定'} bordered>
              <Space direction="vertical" size="medium" style={{ width: '100%' }}>
                <Input
                  placeholder="Action"
                  value={bindingForm.action || ''}
                  onChange={(value) => setBindingForm({ ...bindingForm, action: String(value) })}
                />
                <Input
                  placeholder="Workflow ID"
                  value={bindingForm.workflow_id || ''}
                  onChange={(value) => setBindingForm({ ...bindingForm, workflow_id: String(value) })}
                />
                <Input
                  placeholder="Executor ID"
                  value={bindingForm.executor_id || ''}
                  onChange={(value) => setBindingForm({ ...bindingForm, executor_id: String(value) })}
                />
                <InputNumber
                  placeholder="优先级"
                  value={bindingForm.priority ?? 0}
                  onChange={(value) => setBindingForm({ ...bindingForm, priority: Number(value || 0) })}
                />
                <div>
                  <Space align="center">
                    <Switch
                      value={Boolean(bindingForm.enabled ?? true)}
                      onChange={(value) => setBindingForm({ ...bindingForm, enabled: Boolean(value) })}
                    />
                    <Typography.Text>启用</Typography.Text>
                  </Space>
                </div>
                <Space>
                  <Button theme="primary" onClick={handleBindingSubmit} style={{ width: 120 }}>
                    保存
                  </Button>
                  {bindingForm.id ? (
                    <Button variant="outline" onClick={() => setBindingForm(defaultBindingForm)}>
                      取消
                    </Button>
                  ) : null}
                </Space>
              </Space>
            </Card>
          </Col>
        </Row>
      </Section>
          )}

          {activeNav === 'apikeys' && (
      <Section
        id="apikeys"
        title="API Key 仓库"
        description="统一管理百度、火山、OpenAI 等凭证，并为每个能力分配可用 Key 池，方便限流/欠费时快速切换。"
      >
        <p className="mb-4 text-xs text-slate-700 dark:text-slate-500">
          建议同一 Provider 维护多条 Key，搭配“分配策略”中的不同执行器，实现“主 Key + 备用 Key”或“高优先级/低优先级”模式。
        </p>
        <div className="grid gap-6 lg:grid-cols-2">
          <div className="rounded-2xl border border-slate-200/70 bg-white/80 p-4 dark:border-slate-800 dark:bg-slate-900/40">
            <h3 className="mb-4 text-lg font-semibold text-slate-900 dark:text-white">Key 列表</h3>
            <div className="overflow-x-auto">
              <table>
                <thead>
                  <tr className="text-left text-sm text-slate-700 dark:text-slate-400">
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
                      <td className="text-sm text-slate-800 dark:text-slate-300">{key.provider}</td>
                      <td className="text-sm text-slate-800 dark:text-slate-300">{key.name}</td>
                      <td>
                        <StatusPill status={key.status} />
                      </td>
                      <td className="text-sm text-slate-800 dark:text-slate-300">{key.daily_quota ?? '—'}</td>
                      <td className="text-sm text-slate-800 dark:text-slate-300">{key.usage_count ?? 0}</td>
                      <td className="text-xs text-slate-700 dark:text-slate-400">{key.expire_at || '—'}</td>
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
          <div className="rounded-2xl border border-slate-200/70 bg-white/80 p-4 space-y-2 text-sm dark:border-slate-800 dark:bg-slate-900/40">
            <h3 className="text-lg font-semibold text-slate-900 dark:text-white">{apiKeyForm.id ? '编辑 Key' : '新增 Key'}</h3>
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs text-slate-700 dark:border-slate-800 dark:bg-slate-950/40 dark:text-slate-300">
              <div className="font-semibold text-slate-900 dark:text-slate-100">怎么填？</div>
              <div>Provider 选厂商；名称随便起；Key 值粘贴厂商给的 API Key；状态选 active 即可。</div>
              <div className="mt-1 text-slate-600 dark:text-slate-400">日配额/当前用量/过期时间可先不填，后续需要做限流/轮换再补。</div>
            </div>
            <label className="text-xs text-slate-700 dark:text-slate-400">Provider</label>
            <select
              value={apiKeyForm.provider || ''}
              onChange={(e) => setApiKeyForm({ ...apiKeyForm, provider: e.target.value })}
              className={formControlClass}
            >
              <option value="">请选择厂商…</option>
              {providerOptions
                .filter((opt) => ['baidu', 'volcengine', 'kie', 'openai', 'aliyun', 'coze'].includes(opt.value))
                .map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label} ({opt.value})
                  </option>
                ))}
            </select>
            <label className="text-xs text-slate-700 dark:text-slate-400">名称</label>
            <input
              placeholder="名称"
              value={apiKeyForm.name || ''}
              onChange={(e) => setApiKeyForm({ ...apiKeyForm, name: e.target.value })}
              className={formControlClass}
            />
            {!apiKeyForm.id && (
              <>
                <label className="text-xs text-slate-700 dark:text-slate-400">Key 值</label>
              <input
                placeholder="粘贴 API Key（不会显示明文在列表里）"
                value={apiKeyForm.key || ''}
                onChange={(e) => setApiKeyForm({ ...apiKeyForm, key: e.target.value })}
                className={formControlClass}
              />
              </>
            )}
            <label className="text-xs text-slate-700 dark:text-slate-400">状态</label>
            <select
              value={apiKeyForm.status || 'active'}
              onChange={(e) => setApiKeyForm({ ...apiKeyForm, status: e.target.value })}
              className={formControlClass}
            >
              {apiKeyStatusOptions.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
            <div className="flex gap-3">
              <input
                type="number"
                placeholder="日配额"
                value={apiKeyForm.daily_quota ?? ''}
                onChange={(e) =>
                  setApiKeyForm({ ...apiKeyForm, daily_quota: e.target.value ? Number(e.target.value) : undefined })
                }
                className={formControlFlexClass}
              />
              <input
                type="number"
                placeholder="当前用量"
                value={apiKeyForm.usage_count ?? ''}
                onChange={(e) =>
                  setApiKeyForm({ ...apiKeyForm, usage_count: e.target.value ? Number(e.target.value) : undefined })
                }
                className={formControlFlexClass}
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
              className={formControlClass}
            />
            <div className="flex gap-3">
              <button className="flex-1 rounded bg-sky-500/80 py-2 text-white" onClick={handleApiKeySubmit}>
                保存
              </button>
              {apiKeyForm.id && (
                <button
                  className="rounded border border-slate-300 bg-white px-4 py-2 text-slate-700 hover:bg-slate-50 dark:border-slate-500 dark:bg-transparent dark:text-slate-200"
                  onClick={() => setApiKeyForm(defaultApiKeyForm)}
                >
                  取消
                </button>
              )}
            </div>
          </div>
        </div>
      </Section>
          )}

      {activeNav === 'system' && systemConfig && (
        <Section id="system" title="系统配置" description="汇总环境信息、OSS 配置及安全参数，便于排障和入职交接。">
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

      {activeNav === 'logs' && (
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
          <div className="mt-2 text-xs text-slate-500">回执=调度事件 payload，点击“查看”可查看完整内容。</div>
          <div className="mt-3 overflow-x-auto">
            <table>
              <thead>
                <tr className="text-left text-xs uppercase tracking-widest text-slate-500">
                  <th>ID</th>
                  <th>任务</th>
                  <th>类型</th>
                  <th>回执摘要</th>
                  <th>时间</th>
                  <th>详情</th>
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
                    <td>
                      <Button
                        size="small"
                        variant="text"
                        onClick={() => {
                          setDispatchLogDetail(log);
                          setDispatchLogDetailOpen(true);
                        }}
                      >
                        查看
                      </Button>
                    </td>
                  </tr>
                ))}
                {dispatchLogs.length === 0 && (
                  <tr>
                    <td colSpan={6} className="text-center text-sm text-slate-500 py-4">
                      暂无日志。
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </Section>
      )}

      <Dialog
        header={abilityLogDetail ? `能力调用详情 #${abilityLogDetail.id}` : '能力调用详情'}
        visible={abilityLogDetailOpen}
        width={860}
        confirmBtn={null}
        cancelBtn="关闭"
        onClose={() => {
          setAbilityLogDetailOpen(false);
          setAbilityLogResolveError(null);
          setAbilityLogResolveLoading(false);
        }}
        onCancel={() => {
          setAbilityLogDetailOpen(false);
          setAbilityLogResolveError(null);
          setAbilityLogResolveLoading(false);
        }}
      >
        {abilityLogDetail ? (
          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
            <Row gutter={[12, 12]}>
              <Col span={12}>
                <Typography.Text theme="secondary">能力</Typography.Text>
                <div>
                  <Typography.Text strong>
                    {abilityLogDetail.ability_name || abilityLogDetail.capability_key}
                  </Typography.Text>
                </div>
                <Typography.Text theme="secondary">{abilityLogDetail.ability_provider}</Typography.Text>
              </Col>
              <Col span={12}>
                <Typography.Text theme="secondary">状态</Typography.Text>
                <div>
                  <Tag theme={getAbilityLogStatusTag(abilityLogDetail.status).theme} variant="light">
                    {getAbilityLogStatusTag(abilityLogDetail.status).text}
                  </Tag>
                </div>
                <Typography.Text theme="secondary">
                  {formatDateTime(abilityLogDetail.created_at)} · {formatDurationMs(abilityLogDetail.duration_ms)}
                </Typography.Text>
              </Col>
              <Col span={12}>
                <Typography.Text theme="secondary">来源</Typography.Text>
                <div>
                  <Tag theme={getAbilitySourceTagTheme(abilityLogDetail.source)} variant="light">
                    {formatAbilitySource(abilityLogDetail.source)}
                  </Tag>
                </div>
              </Col>
              <Col span={12}>
                <Typography.Text theme="secondary">节点</Typography.Text>
                <div>
                  <Typography.Text>
                    {abilityLogDetail.executor_name || abilityLogDetail.executor_type || abilityLogDetail.executor_id || '—'}
                  </Typography.Text>
                </div>
              </Col>
            </Row>

            {(() => {
              const resolveMeta = (abilityLogDetail.response_payload || {}) as Record<string, any>;
              const resolvePromptId = resolveMeta.promptId || resolveMeta.taskId;
              const previewUrl =
                abilityLogDetail.stored_url ||
                (abilityLogDetail.result_assets && abilityLogDetail.result_assets.length > 0
                  ? resolveAssetUrl(abilityLogDetail.result_assets[0])
                  : '') ||
                '';
              const canPreviewImage = Boolean(previewUrl) && /\.(png|jpg|jpeg|webp|gif)(\?|#|$)/i.test(previewUrl);
              if (!previewUrl) {
                if ((abilityLogDetail.ability_provider || '').toLowerCase() === 'comfyui' && resolvePromptId) {
                  return (
                    <div>
                      <Typography.Text theme="secondary">结果预览</Typography.Text>
                      <div style={{ marginTop: 8 }}>
                        <Space direction="vertical" size="small">
                          <Typography.Text theme="secondary">当前为提交态结果，尚未解析图片。</Typography.Text>
                          {abilityLogResolveError ? <Alert theme="error" message={abilityLogResolveError} /> : null}
                          <Button variant="outline" loading={abilityLogResolveLoading} onClick={resolveAbilityLog}>
                            拉取回调结果
                          </Button>
                        </Space>
                      </div>
                    </div>
                  );
                }
                return null;
              }
              return (
                <div>
                  <Typography.Text theme="secondary">结果预览</Typography.Text>
                  <div style={{ marginTop: 8 }}>
                    {canPreviewImage ? (
                      <img src={previewUrl} alt="preview" style={{ maxWidth: '100%', maxHeight: 420, display: 'block' }} />
                    ) : (
                      <Button variant="outline" onClick={() => window.open(previewUrl, '_blank', 'noreferrer')}>
                        打开结果链接
                      </Button>
                    )}
                    {abilityLogResolveError ? <Alert theme="error" message={abilityLogResolveError} /> : null}
                  </div>
                </div>
              );
            })()}

            {abilityLogDetail.request_payload ? (
              <div>
                <Typography.Text theme="secondary">Request</Typography.Text>
                <CodeBlock value={formatRawResponse(abilityLogDetail.request_payload)} maxHeight={260} />
              </div>
            ) : null}

            {abilityLogDetail.response_payload ? (
              <div>
                <Typography.Text theme="secondary">Response</Typography.Text>
                <CodeBlock value={formatRawResponse(abilityLogDetail.response_payload)} maxHeight={260} />
              </div>
            ) : null}

            {(() => {
              const hasCallback =
                abilityLogDetail.callback_status ||
                abilityLogDetail.callback_http_status ||
                abilityLogDetail.callback_started_at ||
                abilityLogDetail.callback_finished_at ||
                abilityLogDetail.callback_payload ||
                abilityLogDetail.callback_response ||
                abilityLogDetail.callback_error;
              if (!hasCallback) return null;
              return (
                <div>
                  <Typography.Text theme="secondary">回调记录</Typography.Text>
                  <Space direction="vertical" size="small" style={{ marginTop: 8, width: '100%' }}>
                    <Space align="center" size="small">
                      {abilityLogDetail.callback_status ? (
                        <Tag theme={getAbilityLogStatusTag(abilityLogDetail.callback_status).theme} variant="light">
                          {getAbilityLogStatusTag(abilityLogDetail.callback_status).text}
                        </Tag>
                      ) : null}
                      {typeof abilityLogDetail.callback_http_status === 'number' ? (
                        <Typography.Text theme="secondary">HTTP {abilityLogDetail.callback_http_status}</Typography.Text>
                      ) : null}
                      {abilityLogDetail.callback_started_at ? (
                        <Typography.Text theme="secondary">
                          开始：{formatDateTime(abilityLogDetail.callback_started_at)}
                        </Typography.Text>
                      ) : null}
                      {abilityLogDetail.callback_finished_at ? (
                        <Typography.Text theme="secondary">
                          完成：{formatDateTime(abilityLogDetail.callback_finished_at)}
                        </Typography.Text>
                      ) : null}
                    </Space>
                    {abilityLogDetail.callback_payload ? (
                      <div>
                        <Typography.Text theme="secondary">Callback Request</Typography.Text>
                        <CodeBlock value={formatRawResponse(abilityLogDetail.callback_payload)} maxHeight={240} />
                      </div>
                    ) : null}
                    {abilityLogDetail.callback_response ? (
                      <div>
                        <Typography.Text theme="secondary">Callback Response</Typography.Text>
                        <CodeBlock value={formatRawResponse(abilityLogDetail.callback_response)} maxHeight={240} />
                      </div>
                    ) : null}
                    {abilityLogDetail.callback_error ? (
                      <Alert theme="error" message={abilityLogDetail.callback_error} />
                    ) : null}
                  </Space>
                </div>
              );
            })()}

            {abilityLogDetail.error_message ? <Alert theme="error" message={abilityLogDetail.error_message} /> : null}
          </Space>
        ) : null}
      </Dialog>

      <Dialog
        header={dispatchLogDetail ? `调度回执详情 #${dispatchLogDetail.id}` : '调度回执详情'}
        visible={dispatchLogDetailOpen}
        width={820}
        confirmBtn={null}
        cancelBtn="关闭"
        onClose={() => setDispatchLogDetailOpen(false)}
        onCancel={() => setDispatchLogDetailOpen(false)}
      >
        {dispatchLogDetail ? (
          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
            <Row gutter={[12, 12]}>
              <Col span={12}>
                <Typography.Text theme="secondary">任务</Typography.Text>
                <div>
                  <Typography.Text strong>{dispatchLogDetail.tool_action || '—'}</Typography.Text>
                </div>
                <Typography.Text theme="secondary">{dispatchLogDetail.task_id || '—'}</Typography.Text>
              </Col>
              <Col span={12}>
                <Typography.Text theme="secondary">事件类型</Typography.Text>
                <div>
                  <StatusPill status={dispatchLogDetail.event_type} />
                </div>
                <Typography.Text theme="secondary">{formatDate(dispatchLogDetail.created_at)}</Typography.Text>
              </Col>
              <Col span={12}>
                <Typography.Text theme="secondary">任务状态</Typography.Text>
                <div>{renderStatusTag(dispatchLogDetail.task_status)}</div>
              </Col>
            </Row>
            {dispatchLogDetail.payload ? (
              <div>
                <Typography.Text theme="secondary">回执内容</Typography.Text>
                <CodeBlock value={formatRawResponse(dispatchLogDetail.payload)} maxHeight={320} />
              </div>
            ) : (
              <Typography.Text theme="secondary">无回执内容</Typography.Text>
            )}
          </Space>
        ) : null}
      </Dialog>
          </div>
        </Layout.Content>
      </Layout>
    </Layout>
  );
}

function MetricCard({ label, value, sub }: { label: string; value: number | string; sub?: string }) {
  return (
    <Card bordered>
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
    <section id={id} style={{ padding: '4px 0' }}>
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        <div>
          <Typography.Title level="h4" style={{ margin: 0 }}>
            {title}
          </Typography.Title>
          {description ? <Typography.Text theme="secondary">{description}</Typography.Text> : null}
        </div>
        <div>{children}</div>
      </Space>
    </section>
  );
}

function StatusPill({ status }: { status: string }) {
  return renderStatusTag(status);
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

function CodeBlock({ value, maxHeight = 320 }: { value: string; maxHeight?: number }) {
  const [copied, setCopied] = useState(false);
  return (
    <div style={{ position: 'relative' }}>
      <Button
        size="small"
        variant="text"
        style={{ position: 'absolute', top: 6, right: 6, zIndex: 1 }}
        onClick={async () => {
          try {
            await navigator.clipboard.writeText(value);
            setCopied(true);
            window.setTimeout(() => setCopied(false), 1200);
          } catch {
            // ignore clipboard errors
          }
        }}
      >
        {copied ? '已复制' : '复制'}
      </Button>
      <pre
        style={{
          marginTop: 8,
          padding: 12,
          paddingRight: 56,
          borderRadius: 8,
          border: '1px solid var(--td-border-level-1-color)',
          background: 'var(--td-bg-color-secondarycontainer)',
          color: 'var(--td-text-color-primary)',
          fontSize: 12,
          lineHeight: 1.5,
          maxHeight,
          overflow: 'auto',
        }}
      >
        {value}
      </pre>
    </div>
  );
}

function formatDate(value: string) {
  const date = parseDateValue(value);
  if (!date) return value;
  return date.toLocaleString('zh-CN', { hour12: false, timeZone: 'Asia/Shanghai' });
}

function previewPayload(payload?: Record<string, unknown> | null) {
  if (!payload) return '—';
  const json = JSON.stringify(payload);
  return json.length > 80 ? `${json.slice(0, 77)}…` : json;
}

function StepTitle({ index, label, hint }: { index: number; label: string; hint?: string }) {
  return (
    <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
      <Space align="center" size="small">
        <Tag theme="primary" variant="light">
          {index}
        </Tag>
        <Typography.Text strong>{label}</Typography.Text>
      </Space>
      {hint ? <Typography.Text theme="secondary">{hint}</Typography.Text> : null}
    </Space>
  );
}
