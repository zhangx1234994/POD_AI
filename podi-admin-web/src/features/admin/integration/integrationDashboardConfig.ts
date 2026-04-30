import type {
  AbilityFormState,
  ApiKeyFormState,
  AuthUserFormState,
  BindingFormState,
  BusinessCapabilityFormState,
  ExecutorFormState,
  InviteCodeCreatePayload,
  JsonRecord,
  StoredAsset,
  VendorKeyFormState,
  VendorModelFormState,
  WorkflowFormState,
} from '../../../types/admin';
import {
  abilityTypeOptions,
  categoryOptions,
  providerOptions,
} from './formOptions';
import {
  isIntegrationNavId,
  type IntegrationNavId,
} from './navigation';

export const readHashParams = (): URLSearchParams | null => {
  if (typeof window === 'undefined') return null;
  const hash = window.location.hash.replace(/^#/, '');
  if (!hash) return null;
  return new URLSearchParams(hash.includes('=') ? hash : `nav=${hash}`);
};

export const readNavFromHash = (): IntegrationNavId | null => {
  const params = readHashParams();
  if (!params) return null;
  const value = params.get('nav') || '';
  if (value === 'ability-tests') return 'abilities';
  return isIntegrationNavId(value) ? value : null;
};

export const readEvalRunIdFromHash = (): string => {
  const params = readHashParams();
  return String(params?.get('runId') || params?.get('evalRunId') || '').trim();
};

export const abilityDetailTabs = [
  { id: 'overview', label: '概览' },
  { id: 'params', label: '参数' },
  { id: 'metadata', label: '元信息' },
  { id: 'testing', label: '实时测试' },
  { id: 'logs', label: '调用记录' },
] as const;
export type AbilityDetailTab = (typeof abilityDetailTabs)[number]['id'];

export const abilityLogTabs = [
  { id: 'metrics', label: '指标' },
  { id: 'logs', label: '调用清单' },
] as const;
export type AbilityLogTab = (typeof abilityLogTabs)[number]['id'];

export const readOnlyNavIds = new Set<IntegrationNavId>(['business']);

export const currentMonthValue = () => {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  return `${now.getFullYear()}-${month}`;
};

export const defaultExecutorForm: ExecutorFormState = { status: 'inactive', weight: 1, max_concurrency: 1 };
export const defaultWorkflowForm: WorkflowFormState = { action: '', name: '', version: 'v1', status: 'inactive', type: 'generic' };
export const defaultBindingForm: BindingFormState = { enabled: true, priority: 0 };
export const defaultApiKeyForm: ApiKeyFormState = { status: 'active' };
export const defaultInviteCodeForm: InviteCodeCreatePayload = { role: 'user', maxUses: 1 };
export const defaultAuthUserForm: AuthUserFormState = { role: 'user', status: 'active' };
export const defaultVendorKeyForm: VendorKeyFormState = { status: 'active', maxConcurrency: 1 };
export const defaultVendorModelForm: VendorModelFormState = {
  status: 'active',
  source: 'backend-admin',
  supportsMask: false,
  supportsMultipleImages: false,
  supportsVideo: false,
  supportsText: true,
  requiresGlobalEgress: false,
  apiTypesText: 'image_generation',
  executionModesText: 'sync',
  metadataText: '{}',
  routePolicyText: '{}',
  defaultTaskPolicyText: '{}',
  inputSchemaText: '{}',
  costPolicyText: '{}',
};
export const defaultBusinessCapabilityForm: BusinessCapabilityFormState = {
  businessKey: 'pattern_extract',
  version: 'v1',
  displayName: '',
  description: '',
  status: 'inactive',
  isDefault: false,
  releaseTime: '',
  primaryAbilityId: '',
  vlAssistEnabled: false,
  vlAssistAbilityId: 'vl_analyze_image',
  rolloutEnabled: false,
  rolloutPercent: 0,
  rolloutAllowlistText: '',
  recipeText: '{}',
  inputSchemaText: '{"fields":[]}',
  outputSchemaText: '{"fields":[]}',
  metadataText: '{}',
};
export const defaultAbilityForm: AbilityFormState = {
  provider: providerOptions[0].value,
  category: categoryOptions[0].value,
  capability_key: '',
  version: 'v1',
  display_name: '',
  status: 'inactive',
  ability_type: abilityTypeOptions[0].value,
};

export type AbilityTestForm = {
  abilityId: string | null;
  provider: string | null;
  capabilityKey: string | null;
  executorId: string | null;
  params: string;
  imageBase64: string;
  imageUrl: string;
  comfyuiSubmitOnly: boolean;
};

export type AbilityTestResultPayload = {
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

export const defaultTestForm: AbilityTestForm = {
  abilityId: null,
  provider: null,
  capabilityKey: null,
  executorId: null,
  params: '',
  imageBase64: '',
  imageUrl: '',
  comfyuiSubmitOnly: false,
};

export const abilityLogPageSize = 20;
export const globalAbilityLogPageSize = 30;

export type AbilityPricing = {
  currency?: string;
  unit?: string;
  listPrice?: number;
  discountPrice?: number;
};

export const defaultComfyPricing: AbilityPricing = {
  currency: 'CNY',
  unit: 'per_image',
  listPrice: 0.5,
  discountPrice: 0.3,
};
