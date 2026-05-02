import type {
  Ability,
  AbilityHealthSummaryResponse,
  AbilityListResponse,
  AbilityLogListResponse,
  AbilityLogMetricsResponse,
  AbilityTemplateStateResponse,
  AbilityTemplateValidateResponse,
  AbilityInvocationLog,
  ApiKey,
  AuthSession,
  AuthSessionListResponse,
  AuthScopeSummaryResponse,
  AuthUser,
  AuthUserListResponse,
  AuthUserUpdatePayload,
  BillingMonthlySettlementIssuePayload,
  BillingMonthlySettlementIssueResponse,
  BillingMonthlySettlementListResponse,
  BillingMonthlySettlementResponse,
  BillingMonthlySettlementUpdatePayload,
  BillingMonthlySettlementRecord,
  BillingNotificationConfigPayload,
  BillingNotificationConfigResponse,
  BillingInvoiceRequestCreatePayload,
  BillingInvoiceRequestListResponse,
  BillingInvoiceRequestUpdatePayload,
  BillingInvoiceRequest,
  BillingOverviewResponse,
  BillingUserDetailResponse,
  Binding,
  BusinessCapability,
  BusinessCapabilityCompareResponse,
  BusinessCapabilityListResponse,
  BusinessDefaultApprovalListResponse,
  BusinessOperationLogListResponse,
  BusinessRunListResponse,
  BusinessUsageSummaryResponse,
  DashboardMetrics,
  DispatchLogResponse,
  Executor,
  ComfyuiModelCatalogResponse,
  ComfyuiModelCatalogItem,
  ComfyuiLora,
  ComfyuiLoraCatalogResponse,
  ComfyuiPluginCatalogItem,
  ComfyuiPluginCatalogResponse,
  ComfyuiVersionCatalogItem,
  ComfyuiVersionCatalogResponse,
  ComfyuiVersionCatalogSyncResponse,
  ComfyuiQueueStatus,
  ComfyuiQueueSummary,
  ComfyuiServerDiffLog,
  ComfyuiAgent,
  ComfyuiAgentAlert,
  ComfyuiAgentManifest,
  ComfyuiAgentTokenResponse,
  ComfyuiAgentTask,
  ComfyuiAgentTaskEvent,
  ComfyuiDesktopRelease,
  ComfyuiEnrollCode,
  ComfyuiManifestDriftResponse,
  ComfyuiMonitoringSummary,
  ComfyuiMonitoringQueuesResponse,
  ComfyuiMonitoringErrorsResponse,
  ComfyuiRepairJob,
  ComfyuiRepairPlan,
  ComfyuiResourceOptionsResponse,
  ComfyuiRuntimePolicy,
  ComfyuiRolePrimary,
  JsonRecord,
  InviteCode,
  InviteCodeCreatePayload,
  InviteCodeListResponse,
  PackageAlertNotificationListResponse,
  PackageAlertNotificationPayload,
  PackageAlertNotificationResponse,
  PackagePurchaseOrderCreatePayload,
  PackagePurchaseOrderListResponse,
  PackagePurchaseOrderUpdatePayload,
  PackagePurchaseOrderUpdateResponse,
  MonthlySettlementCollectionNotificationListResponse,
  MonthlySettlementCollectionNotificationPayload,
  MonthlySettlementCollectionNotificationResponse,
  PackageGrantPayload,
  PackageGrantResponse,
  PublicAbility,
  ReleaseDecisionRecordListResponse,
  ReleaseDecisionRecordResponse,
  ReleasePreflightResponse,
  ReleasePreflightSnapshotListResponse,
  ReleasePatrolRecordListResponse,
  ReleasePatrolRecordResponse,
  StrategySnapshotListResponse,
  StrategySnapshotResponse,
  StoredAsset,
  SystemConfig,
  VendorEgressCheckResponse,
  VendorGovernanceSummaryResponse,
  VendorKey,
  VendorKeyListResponse,
  WeeklyReportListResponse,
  WeeklyReportResponse,
  VendorModel,
  VendorModelListResponse,
  VendorModelSyncResponse,
  VendorProviderListResponse,
  VendorUsageSummaryResponse,
  Workflow,
} from '../types/admin';
import type {
  EvalAnnotation,
  EvalDatasetItem,
  EvalRun,
  EvalRunListResponse,
  EvalRunPurgeResponse,
  EvalWorkflowVersion,
} from '../types/eval';

type AbilityContextPayload = {
  abilityId?: string | null;
  abilityName?: string | null;
  abilityProvider?: string | null;
  capabilityKey?: string | null;
};

type AbilityHealthQueryOptions = {
  staleHours?: number;
  limit?: number;
  provider?: string;
  status?: string;
  healthStatus?: string;
  needsTest?: boolean;
  staleOnly?: boolean;
};

type BusinessRunQueryOptions = {
  businessKey?: string;
  status?: string;
  billingStatus?: string;
  callbackStatus?: string;
  version?: string;
  source?: string;
  tenantId?: string;
  clientId?: string;
  traceId?: string;
  windowHours?: number;
  limit?: number;
};

type BusinessOperationLogQueryOptions = {
  action?: string;
  targetType?: string;
  businessKey?: string;
  tenantId?: string;
  clientId?: string;
  actorUserId?: string;
  limit?: number;
};

type BusinessDefaultApprovalQueryOptions = {
  status?: string;
  businessKey?: string;
  limit?: number;
};

type BillingQueryOptions = {
  month?: string;
  windowDays?: number;
  limit?: number;
  page?: number;
  pageSize?: number;
  tenantId?: string;
  clientId?: string;
  businessKey?: string;
  issueLimit?: number;
  packageAlertLimit?: number;
};

type BaiduImageTestResponse = {
  provider?: string;
  logId?: string | number;
  resultImage: string;
  raw?: JsonRecord | null;
};

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '';
const ACCESS_TOKEN_KEY = 'podi_admin_access_token';
const REFRESH_TOKEN_KEY = 'podi_admin_refresh_token';
export const ADMIN_TOKEN_INVALID_EVENT = 'podi-admin-token-invalid';
const TOKEN_INVALID_FLAG = 'podi_admin_token_invalid';
const TOKEN_INVALID_AT_KEY = 'podi_admin_token_invalid_at';
const DEFAULT_TIMEOUT_MS = 15000;
const TEST_TIMEOUT_MS = 60000;
const KIE_TIMEOUT_MS = 180000;
const COMFYUI_TIMEOUT_MS = 600000;
const AUTH_INVALID_MESSAGE = '登录已失效，请重新登录';
const GATEWAY_ERROR_MESSAGE = '服务不可达或网关异常，请稍后再试';

export function getAdminToken() {
  return localStorage.getItem('podi_admin_access_token');
}

function extractErrorMessage(statusText: string, bodyText: string): string {
  const text = (bodyText || '').trim();
  if (!text) return statusText || 'Request failed';
  const lower = text.toLowerCase();
  if (lower.startsWith('<!doctype') || lower.startsWith('<html')) {
    return '服务异常（网关或代理返回了 HTML 页面）';
  }
  try {
    const parsed = JSON.parse(text);
    const detail = (parsed as any)?.detail;
    if (typeof detail === 'string' && detail.trim()) return detail.trim();
    if (detail && typeof detail === 'object') return JSON.stringify(detail);
    for (const key of ['message', 'msg', 'error_message', 'error']) {
      const v = (parsed as any)?.[key];
      if (typeof v === 'string' && v.trim()) return v.trim();
    }
  } catch {
    // ignore JSON parse errors
  }
  return text;
}

function resolveHttpError(status: number, statusText: string, bodyText: string): string {
  const message = extractErrorMessage(statusText, bodyText);
  switch (status) {
    case 400:
      return message || '请求参数错误';
    case 401:
      return AUTH_INVALID_MESSAGE;
    case 403:
      return message && message !== 'ADMIN_ONLY' ? message : '当前账号没有权限访问这个功能';
    case 404:
      return message || '接口不存在或已下线';
    case 408:
      return message || '请求超时，请稍后再试';
    case 409:
      return message || '资源冲突或状态不允许';
    case 413:
      return message || '上传内容过大';
    case 422:
      return message || '参数校验失败';
    case 429:
      return message || '请求过于频繁，请稍后再试';
    case 502:
    case 503:
    case 504:
      return GATEWAY_ERROR_MESSAGE;
    default:
      if (status >= 500) {
        return message || '服务异常，请稍后再试';
      }
      return message || statusText || 'Request failed';
  }
}

function resolveNetworkError(err: unknown, timeoutMessage: string) {
  if (err instanceof DOMException && err.name === 'AbortError') {
    return timeoutMessage;
  }
  const message = String((err as any)?.message || err || '').trim();
  const lower = message.toLowerCase();
  if (!message) return '网络请求失败';
  if (lower.includes('failed to fetch') || lower.includes('networkerror') || lower.includes('load failed') || lower.includes('fetch failed')) {
    return '网络异常或服务不可达，请检查网络/网关配置';
  }
  if (lower.includes('cors')) {
    return '跨域限制导致请求失败，请检查网关/域名配置';
  }
  if (lower.includes('ssl') || lower.includes('tls') || lower.includes('certificate')) {
    return '证书或 TLS 配置异常，请检查服务端配置';
  }
  return message || '网络请求失败';
}

function withTimeout(options: RequestInit, timeoutMs: number) {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);
  return {
    options: { ...options, signal: controller.signal },
    cancel: () => window.clearTimeout(timer),
  };
}

function clearAdminTokens() {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
}

function broadcastInvalidToken(message?: string) {
  window.dispatchEvent(
    new CustomEvent(ADMIN_TOKEN_INVALID_EVENT, {
      detail: {
        message,
      },
    }),
  );
}

function forceReLogin(message?: string) {
  const now = Date.now();
  const last = Number(localStorage.getItem(TOKEN_INVALID_AT_KEY) || '0');
  clearAdminTokens();
  localStorage.setItem(TOKEN_INVALID_FLAG, message || AUTH_INVALID_MESSAGE);
  broadcastInvalidToken(message);
  if (!Number.isNaN(last) && now - last < 3000) return;
  localStorage.setItem(TOKEN_INVALID_AT_KEY, String(now));
  window.setTimeout(() => {
    window.location.reload();
  }, 50);
}

function buildAbilityHealthQuery(options?: AbilityHealthQueryOptions) {
  const params = new URLSearchParams();
  params.set('staleHours', String(options?.staleHours ?? 24));
  params.set('limit', String(options?.limit ?? 20));
  if (options?.provider && options.provider !== 'all') params.set('provider', options.provider);
  if (options?.status && options.status !== 'all') params.set('status', options.status);
  if (options?.healthStatus && options.healthStatus !== 'all') params.set('healthStatus', options.healthStatus);
  if (typeof options?.needsTest === 'boolean') params.set('needsTest', options.needsTest ? 'true' : 'false');
  if (options?.staleOnly) params.set('staleOnly', 'true');
  return params;
}

function buildBusinessRunQuery(options?: BusinessRunQueryOptions) {
  const params = new URLSearchParams();
  if (options?.businessKey && options.businessKey !== 'all') params.set('business_key', options.businessKey);
  if (options?.status && options.status !== 'all') params.set('status', options.status);
  if (options?.billingStatus && options.billingStatus !== 'all') {
    params.set('billing_status', options.billingStatus);
  }
  if (options?.callbackStatus && options.callbackStatus !== 'all') {
    params.set('callback_status', options.callbackStatus);
  }
  if (options?.version && options.version !== 'all') params.set('version', options.version);
  if (options?.source?.trim()) params.set('source', options.source.trim());
  if (options?.tenantId?.trim()) params.set('tenant_id', options.tenantId.trim());
  if (options?.clientId?.trim()) params.set('client_id', options.clientId.trim());
  if (options?.traceId?.trim()) params.set('trace_id', options.traceId.trim());
  if (options?.windowHours) params.set('window_hours', String(options.windowHours));
  if (options?.limit) params.set('limit', String(options.limit));
  return params;
}

function buildBusinessOperationLogQuery(options?: BusinessOperationLogQueryOptions) {
  const params = new URLSearchParams();
  if (options?.action && options.action !== 'all') params.set('action', options.action);
  if (options?.targetType && options.targetType !== 'all') params.set('target_type', options.targetType);
  if (options?.businessKey && options.businessKey !== 'all') params.set('business_key', options.businessKey);
  if (options?.tenantId?.trim()) params.set('tenant_id', options.tenantId.trim());
  if (options?.clientId?.trim()) params.set('client_id', options.clientId.trim());
  if (options?.actorUserId?.trim()) params.set('actor_user_id', options.actorUserId.trim());
  if (options?.limit) params.set('limit', String(options.limit));
  return params;
}

function buildBusinessDefaultApprovalQuery(options?: BusinessDefaultApprovalQueryOptions) {
  const params = new URLSearchParams();
  if (options?.status && options.status !== 'all') params.set('approval_status', options.status);
  if (options?.businessKey && options.businessKey !== 'all') params.set('business_key', options.businessKey);
  if (options?.limit) params.set('limit', String(options.limit));
  return params;
}

function buildBillingQuery(options?: BillingQueryOptions) {
  const params = new URLSearchParams();
  if (options?.month?.trim()) params.set('month', options.month.trim());
  if (options?.windowDays) params.set('window_days', String(options.windowDays));
  if (options?.limit) params.set('limit', String(options.limit));
  if (options?.page) params.set('page', String(options.page));
  if (options?.pageSize) params.set('page_size', String(options.pageSize));
  if (options?.tenantId?.trim()) params.set('tenant_id', options.tenantId.trim());
  if (options?.clientId?.trim()) params.set('client_id', options.clientId.trim());
  if (options?.businessKey?.trim() && options.businessKey !== 'all') {
    params.set('business_key', options.businessKey.trim());
  }
  if (options?.issueLimit) params.set('issue_limit', String(options.issueLimit));
  if (options?.packageAlertLimit) params.set('package_alert_limit', String(options.packageAlertLimit));
  return params;
}

async function request<T>(path: string, options: RequestInit = {}, timeoutMs = DEFAULT_TIMEOUT_MS): Promise<T> {
  const token = getAdminToken();
  const { options: timedOptions, cancel } = withTimeout(options, timeoutMs);
  let resp: Response;
  try {
    resp = await fetch(`${API_BASE}${path}`, {
      ...timedOptions,
      headers: {
        'Content-Type': 'application/json',
        ...(options.headers || {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    });
  } catch (err) {
    cancel();
    throw new Error(resolveNetworkError(err, '请求超时，请检查网络或服务是否可用'));
  }
  cancel();
  if (!resp.ok) {
    const text = await resp.text();
    const message = resolveHttpError(resp.status, resp.statusText, text);
    if (resp.status === 401) {
      forceReLogin(message);
    }
    throw new Error(message);
  }
  const text = await resp.text();
  if (!text) return undefined as T;
  try {
    return JSON.parse(text) as T;
  } catch {
    const message = extractErrorMessage('', text) || '响应解析失败';
    throw new Error(message);
  }
}

async function requestBlob(path: string, options: RequestInit = {}, timeoutMs = DEFAULT_TIMEOUT_MS): Promise<Blob> {
  const token = getAdminToken();
  const { options: timedOptions, cancel } = withTimeout(options, timeoutMs);
  let resp: Response;
  try {
    resp = await fetch(`${API_BASE}${path}`, {
      ...timedOptions,
      headers: {
        ...(options.headers || {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    });
  } catch (err) {
    cancel();
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new Error('请求超时，请检查网络或服务是否可用');
    }
    throw new Error(String((err as any)?.message || err || '网络请求失败'));
  }
  cancel();
  if (!resp.ok) {
    const text = await resp.text();
    const message = resolveHttpError(resp.status, resp.statusText, text);
    if (resp.status === 401) {
      forceReLogin(message);
    }
    throw new Error(message);
  }
  return resp.blob();
}

export const adminApi = {
  listAuthUsers: () => request<AuthUserListResponse>('/api/auth/users'),
  updateAuthUser: (userId: string, payload: AuthUserUpdatePayload) =>
    request<AuthUser>(`/api/auth/users/${userId}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  getAuthScopeSummary: () => request<AuthScopeSummaryResponse>('/api/auth/scope-summary'),
  listAuthSessions: () => request<AuthSessionListResponse>('/api/auth/sessions/all'),
  revokeAuthSession: (sessionId: string) =>
    request<AuthSession>(`/api/auth/sessions/${sessionId}/revoke`, { method: 'POST' }),
  listInviteCodes: () => request<InviteCodeListResponse>('/api/auth/invite-codes'),
  createInviteCode: (payload: InviteCodeCreatePayload) =>
    request<InviteCode>('/api/auth/invite-codes', { method: 'POST', body: JSON.stringify(payload) }),
  disableInviteCode: (inviteId: string) =>
    request<InviteCode>(`/api/auth/invite-codes/${inviteId}/disable`, { method: 'POST' }),

  listExecutors: () => request<Executor[]>('/api/admin/executors'),
  createExecutor: (payload: Partial<Executor>) =>
    request<Executor>('/api/admin/executors', { method: 'POST', body: JSON.stringify(payload) }),
  updateExecutor: (id: string, payload: Partial<Executor>) =>
    request<Executor>(`/api/admin/executors/${id}`, { method: 'PUT', body: JSON.stringify(payload) }),
  deleteExecutor: (id: string) => request<void>(`/api/admin/executors/${id}`, { method: 'DELETE' }),

  listWorkflows: () => request<Workflow[]>('/api/admin/workflows'),
  createWorkflow: (payload: Partial<Workflow>) =>
    request<Workflow>('/api/admin/workflows', { method: 'POST', body: JSON.stringify(payload) }),
  updateWorkflow: (id: string, payload: Partial<Workflow>) =>
    request<Workflow>(`/api/admin/workflows/${id}`, { method: 'PUT', body: JSON.stringify(payload) }),
  deleteWorkflow: (id: string) => request<void>(`/api/admin/workflows/${id}`, { method: 'DELETE' }),

  listBindings: () => request<Binding[]>('/api/admin/workflow-bindings'),
  createBinding: (payload: Partial<Binding>) =>
    request<Binding>('/api/admin/workflow-bindings', { method: 'POST', body: JSON.stringify(payload) }),
  updateBinding: (id: string, payload: Partial<Binding>) =>
    request<Binding>(`/api/admin/workflow-bindings/${id}`, { method: 'PUT', body: JSON.stringify(payload) }),
  deleteBinding: (id: string) => request<void>(`/api/admin/workflow-bindings/${id}`, { method: 'DELETE' }),

  listApiKeys: () => request<ApiKey[]>('/api/admin/api-keys'),
  createApiKey: (payload: Partial<ApiKey>) =>
    request<ApiKey>('/api/admin/api-keys', { method: 'POST', body: JSON.stringify(payload) }),
  updateApiKey: (id: string, payload: Partial<ApiKey>) =>
    request<ApiKey>(`/api/admin/api-keys/${id}`, { method: 'PUT', body: JSON.stringify(payload) }),
  deleteApiKey: (id: string) => request<void>(`/api/admin/api-keys/${id}`, { method: 'DELETE' }),

  listVendorProviders: () => request<VendorProviderListResponse>('/api/admin/vendor-api/providers'),
  checkVendorProviderEgress: (provider: string, payload?: { check?: string; includeAuth?: boolean }) =>
    request<VendorEgressCheckResponse>(`/api/admin/vendor-api/providers/${encodeURIComponent(provider)}/egress-check`, {
      method: 'POST',
      body: JSON.stringify(payload || { check: 'models', includeAuth: false }),
    }),
  listVendorKeys: (provider?: string) => {
    const suffix = provider ? `?provider=${encodeURIComponent(provider)}` : '';
    return request<VendorKeyListResponse>(`/api/admin/vendor-api/keys${suffix}`);
  },
  getVendorUsageSummary: (windowHours = 24) =>
    request<VendorUsageSummaryResponse>(`/api/admin/vendor-api/usage/summary?windowHours=${encodeURIComponent(String(windowHours))}`),
  getVendorGovernanceSummary: (windowHours = 24) =>
    request<VendorGovernanceSummaryResponse>(
      `/api/admin/vendor-api/governance/summary?windowHours=${encodeURIComponent(String(windowHours))}`,
    ),
  createVendorKey: (payload: Partial<VendorKey> & { key: string; secret?: string | null; provider: string; alias: string }) =>
    request<VendorKey>('/api/admin/vendor-api/keys', { method: 'POST', body: JSON.stringify(payload) }),
  updateVendorKey: (id: string, payload: Partial<VendorKey> & { key?: string; secret?: string | null }) =>
    request<VendorKey>(`/api/admin/vendor-api/keys/${encodeURIComponent(id)}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),
  listVendorModels: () => request<VendorModelListResponse>('/api/admin/vendor-api/models'),
  syncVolcengineModels: () =>
    request<VendorModelSyncResponse>('/api/admin/vendor-api/models/sync/volcengine', { method: 'POST' }),
  createVendorModel: (payload: Partial<VendorModel>) =>
    request<VendorModel>('/api/admin/vendor-api/models', { method: 'POST', body: JSON.stringify(payload) }),
  updateVendorModel: (id: number, payload: Partial<VendorModel>) =>
    request<VendorModel>(`/api/admin/vendor-api/models/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),

  // Tests
  testBaiduQualityUpgrade: (payload: AbilityContextPayload & { executorId: string; imageBase64: string; resolution: string; upscaleType: string }) =>
    request<BaiduImageTestResponse>(
      '/api/admin/tests/baidu/quality-upgrade',
      {
        method: 'POST',
        body: JSON.stringify(payload),
      },
      TEST_TIMEOUT_MS,
    ),
  testBaiduImageProcess: (payload: AbilityContextPayload & {
    executorId: string;
    operation: string;
    imageBase64?: string;
    imageUrl?: string;
    params?: Record<string, unknown>;
  }): Promise<BaiduImageTestResponse> =>
    request<BaiduImageTestResponse>(
      '/api/admin/tests/baidu/image-process',
      {
        method: 'POST',
        body: JSON.stringify(payload),
      },
      TEST_TIMEOUT_MS,
    ),
  testVolcengineChat: (payload: AbilityContextPayload & {
    executorId: string;
    model: string;
    prompt: string;
    imageUrl?: string;
    params?: Record<string, unknown>;
  }) =>
    request<{ provider: string; model: string; text: string; logId?: number | string; raw?: JsonRecord | null }>(
      '/api/admin/tests/volcengine/chat',
      {
        method: 'POST',
        body: JSON.stringify(payload),
      },
      TEST_TIMEOUT_MS,
    ),
  testVolcengineImage: (payload: AbilityContextPayload & {
    executorId: string;
    model: string;
    prompt: string;
    negativePrompt?: string;
    size?: string;
    responseFormat?: string;
    params?: Record<string, unknown>;
  }) =>
    request<{
      provider: string;
      model: string;
      logId?: number | string;
      imageUrl?: string;
      imageBase64?: string;
      storedUrl?: string;
      assets?: StoredAsset[];
      raw?: JsonRecord | null;
    }>(
      '/api/admin/tests/volcengine/image',
      {
        method: 'POST',
        body: JSON.stringify(payload),
      },
      TEST_TIMEOUT_MS,
    ),
  testVolcengineVideo: (payload: AbilityContextPayload & {
    executorId: string;
    model: string;
    prompt: string;
    imageUrl?: string;
    params?: Record<string, unknown>;
  }) =>
    request<{
      provider: string;
      model: string;
      logId?: number | string;
      taskId?: string;
      state?: string;
      resultUrls?: string[];
      assets?: StoredAsset[];
      raw?: JsonRecord | null;
    }>(
      '/api/admin/tests/volcengine/video',
      {
        method: 'POST',
        body: JSON.stringify(payload),
      },
      TEST_TIMEOUT_MS,
    ),
  testKieMarket: (payload: AbilityContextPayload & {
    executorId: string;
    model: string;
    endpoint?: string;
    callBackUrl?: string;
    input: JsonRecord;
    extra?: JsonRecord;
  }) =>
    request<{
      provider: string;
      model: string;
      logId?: number | string;
      taskId: string;
      state?: string;
      resultUrls?: string[];
      storedAssets?: StoredAsset[];
      raw?: JsonRecord | null;
    }>(
      '/api/admin/tests/kie/market',
      {
        method: 'POST',
        body: JSON.stringify(payload),
      },
      KIE_TIMEOUT_MS,
    ),
  testComfyuiWorkflow: (payload: AbilityContextPayload & {
    executorId: string;
    workflowKey: string;
    workflowParams: JsonRecord;
    submitOnly?: boolean;
  }) =>
    request<{
      provider: string;
      workflowKey: string;
      promptId: string;
      state?: string;
      logId?: number | string;
      storedUrl?: string;
      assets?: StoredAsset[];
      raw?: JsonRecord | null;
    }>(
      '/api/admin/tests/comfyui/workflow',
      {
        method: 'POST',
        body: JSON.stringify(payload),
      },
      COMFYUI_TIMEOUT_MS,
    ),

  getComfyuiModels: (executorId: string, options?: { includeNodes?: boolean }) => {
    const params = new URLSearchParams();
    params.set('executorId', executorId);
    if (options?.includeNodes) params.set('includeNodes', 'true');
    return request<ComfyuiModelCatalogResponse>(`/api/admin/comfyui/models?${params.toString()}`);
  },
  listComfyuiModelCatalog: (options?: { q?: string; type?: string; status?: string }) => {
    const params = new URLSearchParams();
    if (options?.q) params.set('q', options.q);
    if (options?.type) params.set('type', options.type);
    if (options?.status) params.set('status', options.status);
    const suffix = params.toString() ? `?${params.toString()}` : '';
    return request<ComfyuiModelCatalogResponse>(`/api/admin/comfyui/model-catalog${suffix}`);
  },
  createComfyuiModelCatalog: (payload: Partial<ComfyuiModelCatalogItem>) =>
    request<ComfyuiModelCatalogItem>('/api/admin/comfyui/model-catalog', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  updateComfyuiModelCatalog: (id: number, payload: Partial<ComfyuiModelCatalogItem>) =>
    request<ComfyuiModelCatalogItem>(`/api/admin/comfyui/model-catalog/${id}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),
  deleteComfyuiModelCatalog: (id: number) =>
    request<void>(`/api/admin/comfyui/model-catalog/${id}`, { method: 'DELETE' }),
  listComfyuiPluginCatalog: (options?: { q?: string; status?: string }) => {
    const params = new URLSearchParams();
    if (options?.q) params.set('q', options.q);
    if (options?.status) params.set('status', options.status);
    const suffix = params.toString() ? `?${params.toString()}` : '';
    return request<ComfyuiPluginCatalogResponse>(`/api/admin/comfyui/plugin-catalog${suffix}`);
  },
  createComfyuiPluginCatalog: (payload: Partial<ComfyuiPluginCatalogItem>) =>
    request<ComfyuiPluginCatalogItem>('/api/admin/comfyui/plugin-catalog', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  updateComfyuiPluginCatalog: (id: number, payload: Partial<ComfyuiPluginCatalogItem>) =>
    request<ComfyuiPluginCatalogItem>(`/api/admin/comfyui/plugin-catalog/${id}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),
  deleteComfyuiPluginCatalog: (id: number) =>
    request<void>(`/api/admin/comfyui/plugin-catalog/${id}`, { method: 'DELETE' }),
  listComfyuiVersionCatalog: (options?: { q?: string; status?: string }) => {
    const params = new URLSearchParams();
    if (options?.q) params.set('q', options.q);
    if (options?.status) params.set('status', options.status);
    const suffix = params.toString() ? `?${params.toString()}` : '';
    return request<ComfyuiVersionCatalogResponse>(`/api/admin/comfyui/version-catalog${suffix}`);
  },
  createComfyuiVersionCatalog: (payload: Partial<ComfyuiVersionCatalogItem>) =>
    request<ComfyuiVersionCatalogItem>('/api/admin/comfyui/version-catalog', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  updateComfyuiVersionCatalog: (id: number, payload: Partial<ComfyuiVersionCatalogItem>) =>
    request<ComfyuiVersionCatalogItem>(`/api/admin/comfyui/version-catalog/${id}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),
  deleteComfyuiVersionCatalog: (id: number) =>
    request<void>(`/api/admin/comfyui/version-catalog/${id}`, { method: 'DELETE' }),
  syncComfyuiVersionCatalog: (limit?: number) => {
    const params = new URLSearchParams();
    if (typeof limit === 'number') params.set('limit', String(limit));
    const suffix = params.toString() ? `?${params.toString()}` : '';
    return request<ComfyuiVersionCatalogSyncResponse>(`/api/admin/comfyui/version-catalog/sync${suffix}`, {
      method: 'POST',
    });
  },
  listComfyuiLoras: (options?: { executorId?: string; q?: string; status?: string; includeUntracked?: boolean }) => {
    const params = new URLSearchParams();
    if (options?.executorId) params.set('executorId', options.executorId);
    if (options?.q) params.set('q', options.q);
    if (options?.status) params.set('status', options.status);
    if (typeof options?.includeUntracked === 'boolean') {
      params.set('includeUntracked', options.includeUntracked ? 'true' : 'false');
    }
    const suffix = params.toString() ? `?${params.toString()}` : '';
    return request<ComfyuiLoraCatalogResponse>(`/api/admin/comfyui/loras${suffix}`);
  },
  createComfyuiLora: (payload: Partial<ComfyuiLora>) =>
    request<ComfyuiLora>('/api/admin/comfyui/loras', { method: 'POST', body: JSON.stringify(payload) }),
  updateComfyuiLora: (id: number, payload: Partial<ComfyuiLora>) =>
    request<ComfyuiLora>(`/api/admin/comfyui/loras/${id}`, { method: 'PUT', body: JSON.stringify(payload) }),
  deleteComfyuiLora: (id: number) =>
    request<void>(`/api/admin/comfyui/loras/${id}`, { method: 'DELETE' }),
  getComfyuiQueueStatus: (executorId: string) =>
    request<ComfyuiQueueStatus>(`/api/admin/comfyui/queue-status?executorId=${encodeURIComponent(executorId)}`),
  getComfyuiQueueSummary: (executorIds?: string[]) => {
    const params = new URLSearchParams();
    (executorIds || []).forEach((id) => {
      if (id) params.append('executorIds', id);
    });
    const suffix = params.toString() ? `?${params.toString()}` : '';
    return request<ComfyuiQueueSummary>(`/api/admin/comfyui/queue-summary${suffix}`);
  },
  saveComfyuiServerDiff: (payload: { baseline_executor_id: string; payload: JsonRecord }) =>
    request<ComfyuiServerDiffLog>('/api/admin/comfyui/server-diff', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  listComfyuiServerDiff: (limit = 10) =>
    request<ComfyuiServerDiffLog[]>(`/api/admin/comfyui/server-diff?limit=${limit}`),
  getComfyuiSystemStats: (executorId: string) =>
    request<{ executorId: string; baseUrl: string; system?: Record<string, unknown> | null; devices?: Record<string, unknown>[] | null; raw?: JsonRecord | null }>(
      `/api/admin/comfyui/system-stats?executorId=${encodeURIComponent(executorId)}`,
    ),
  listComfyuiAgents: (options?: { status?: string; role?: string; limit?: number }) => {
    const params = new URLSearchParams();
    if (options?.status) params.set('status', options.status);
    if (options?.role) params.set('role', options.role);
    if (typeof options?.limit === 'number') params.set('limit', String(options.limit));
    const suffix = params.toString() ? `?${params.toString()}` : '';
    return request<ComfyuiAgent[]>(`/api/admin/comfyui/agents${suffix}`);
  },
  createComfyuiAgent: (payload: Partial<ComfyuiAgent> & { id: string }) =>
    request<ComfyuiAgent>('/api/admin/comfyui/agents', { method: 'POST', body: JSON.stringify(payload) }),
  updateComfyuiAgent: (id: string, payload: Partial<ComfyuiAgent>) =>
    request<ComfyuiAgent>(`/api/admin/comfyui/agents/${encodeURIComponent(id)}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),
  deleteComfyuiAgent: (id: string) =>
    request<void>(`/api/admin/comfyui/agents/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  issueComfyuiAgentToken: (agentId: string, payload?: { ttlSeconds?: number }) =>
    request<ComfyuiAgentTokenResponse>(`/api/admin/comfyui/agents/${encodeURIComponent(agentId)}/token`, {
      method: 'POST',
      body: JSON.stringify(payload || {}),
    }),
  createComfyuiEnrollCode: (payload?: { role?: string; ttlSeconds?: number; note?: string; maxUses?: number }) =>
    request<ComfyuiEnrollCode>('/api/admin/comfyui/agents/enroll-codes', {
      method: 'POST',
      body: JSON.stringify(payload || {}),
    }),
  listComfyuiEnrollCodes: (options?: { status?: string; role?: string; limit?: number }) => {
    const params = new URLSearchParams();
    if (options?.status) params.set('status', options.status);
    if (options?.role) params.set('role', options.role);
    if (typeof options?.limit === 'number') params.set('limit', String(options.limit));
    const suffix = params.toString() ? `?${params.toString()}` : '';
    return request<ComfyuiEnrollCode[]>(`/api/admin/comfyui/agents/enroll-codes${suffix}`);
  },
  listComfyuiAgentAlerts: (options?: { agentId?: string; alertType?: string; limit?: number }) => {
    const params = new URLSearchParams();
    if (options?.agentId) params.set('agent_id', options.agentId);
    if (options?.alertType) params.set('alert_type', options.alertType);
    if (typeof options?.limit === 'number') params.set('limit', String(options.limit));
    const suffix = params.toString() ? `?${params.toString()}` : '';
    return request<ComfyuiAgentAlert[]>(`/api/admin/comfyui/alerts${suffix}`);
  },
  listComfyuiManifests: (options?: { role?: string; status?: string; limit?: number }) => {
    const params = new URLSearchParams();
    if (options?.role) params.set('role', options.role);
    if (options?.status) params.set('status', options.status);
    if (typeof options?.limit === 'number') params.set('limit', String(options.limit));
    const suffix = params.toString() ? `?${params.toString()}` : '';
    return request<ComfyuiAgentManifest[]>(`/api/admin/comfyui/manifests${suffix}`);
  },
  getComfyuiManifest: (id: number) =>
    request<ComfyuiAgentManifest>(`/api/admin/comfyui/manifests/${id}`),
  createComfyuiManifest: (payload: Partial<ComfyuiAgentManifest>) =>
    request<ComfyuiAgentManifest>('/api/admin/comfyui/manifests', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  updateComfyuiManifest: (id: number, payload: Partial<ComfyuiAgentManifest>) =>
    request<ComfyuiAgentManifest>(`/api/admin/comfyui/manifests/${id}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),
  publishComfyuiManifest: (id: number, payload?: { notes?: string }) =>
    request<ComfyuiAgentManifest>(`/api/admin/comfyui/manifests/${id}/publish`, {
      method: 'POST',
      body: JSON.stringify(payload || {}),
    }),
  rollbackComfyuiManifest: (
    id: number,
    payload?: {
      targetManifestId?: number;
      notes?: string;
    },
  ) =>
    request<ComfyuiAgentManifest>(`/api/admin/comfyui/manifests/${id}/rollback`, {
      method: 'POST',
      body: JSON.stringify(payload || {}),
    }),
  getComfyuiManifestDrift: (manifestId: number, agentId: string) =>
    request<ComfyuiManifestDriftResponse>(
      `/api/admin/comfyui/manifests/${manifestId}/drift?agent_id=${encodeURIComponent(agentId)}`,
    ),
  createComfyuiRepairPlan: (
    manifestId: number,
    payload?: { agentIds?: string[]; mode?: string },
  ) =>
    request<ComfyuiRepairPlan>(`/api/admin/comfyui/manifests/${manifestId}/repair-plan`, {
      method: 'POST',
      body: JSON.stringify(payload || {}),
    }),
  createComfyuiRepairJob: (payload: {
    manifestId: number;
    mode?: string;
    push?: boolean;
    items: Array<{ agentId: string; actions: string[]; missingItems?: Record<string, string[]> }>;
  }) =>
    request<ComfyuiRepairJob>('/api/admin/comfyui/repair-jobs', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  listComfyuiRepairJobs: (options?: { manifestId?: number; limit?: number }) => {
    const params = new URLSearchParams();
    if (typeof options?.manifestId === 'number') params.set('manifest_id', String(options.manifestId));
    if (typeof options?.limit === 'number') params.set('limit', String(options.limit));
    const suffix = params.toString() ? `?${params.toString()}` : '';
    return request<ComfyuiRepairJob[]>(`/api/admin/comfyui/repair-jobs${suffix}`);
  },
  getComfyuiRepairJob: (jobId: string) =>
    request<ComfyuiRepairJob>(`/api/admin/comfyui/repair-jobs/${encodeURIComponent(jobId)}`),
  getComfyuiRolePrimary: (role: string) =>
    request<ComfyuiRolePrimary>(`/api/admin/comfyui/roles/${encodeURIComponent(role)}/primary-agent`),
  setComfyuiRolePrimary: (role: string, agentId: string) =>
    request<ComfyuiRolePrimary>(`/api/admin/comfyui/roles/${encodeURIComponent(role)}/primary-agent`, {
      method: 'POST',
      body: JSON.stringify({ agentId }),
    }),
  getComfyuiMonitoringSummary: (windowHours = 24) =>
    request<ComfyuiMonitoringSummary>(`/api/admin/comfyui/monitoring/summary?window_hours=${windowHours}`),
  getComfyuiMonitoringQueues: (windowHours = 24) =>
    request<ComfyuiMonitoringQueuesResponse>(`/api/admin/comfyui/monitoring/queues?window_hours=${windowHours}`),
  getComfyuiMonitoringErrors: (windowHours = 24, limit = 100) =>
    request<ComfyuiMonitoringErrorsResponse>(
      `/api/admin/comfyui/monitoring/errors?window_hours=${windowHours}&limit=${limit}`,
    ),
  getComfyuiConcurrencyPolicy: () =>
    request<ComfyuiRuntimePolicy>('/api/admin/comfyui/policies/concurrency'),
  updateComfyuiConcurrencyPolicy: (payload: {
    defaultPolicy?: JsonRecord;
    laneOverrides?: JsonRecord;
    nodeOverrides?: JsonRecord;
    notes?: string;
  }) =>
    request<ComfyuiRuntimePolicy>('/api/admin/comfyui/policies/concurrency', {
      method: 'PUT',
      body: JSON.stringify(payload || {}),
    }),
  getComfyuiRetryPolicy: () =>
    request<ComfyuiRuntimePolicy>('/api/admin/comfyui/policies/retry'),
  updateComfyuiRetryPolicy: (payload: {
    defaultPolicy?: JsonRecord;
    laneOverrides?: JsonRecord;
    nodeOverrides?: JsonRecord;
    notes?: string;
  }) =>
    request<ComfyuiRuntimePolicy>('/api/admin/comfyui/policies/retry', {
      method: 'PUT',
      body: JSON.stringify(payload || {}),
    }),
  listComfyuiResourceOptions: (resourceType: 'lora' | 'model' | 'plugin' | 'version', options?: { status?: string; q?: string; limit?: number }) => {
    const params = new URLSearchParams();
    params.set('type', resourceType);
    if (options?.status) params.set('status', options.status);
    if (options?.q) params.set('q', options.q);
    if (typeof options?.limit === 'number') params.set('limit', String(options.limit));
    const suffix = params.toString() ? `?${params.toString()}` : '';
    return request<ComfyuiResourceOptionsResponse>(`/api/admin/comfyui/resources/options${suffix}`);
  },
  getComfyuiDesktopReleaseDownloadUrl: (releaseId: number) =>
    `${API_BASE}/api/admin/comfyui/desktop/releases/${releaseId}/download`,
  getComfyuiDesktopLatestDownloadUrl: (params?: { os?: string; arch?: string; channel?: string }) => {
    const query = new URLSearchParams();
    if (params?.os) query.set('os', params.os);
    if (params?.arch) query.set('arch', params.arch);
    if (params?.channel) query.set('channel', params.channel);
    const suffix = query.toString() ? `?${query.toString()}` : '';
    return `${API_BASE}/api/admin/comfyui/desktop/releases/latest/download${suffix}`;
  },
  listComfyuiDesktopReleases: (options?: {
    channel?: string;
    osType?: string;
    arch?: string;
    status?: string;
    limit?: number;
  }) => {
    const params = new URLSearchParams();
    if (options?.channel) params.set('channel', options.channel);
    if (options?.osType) params.set('os_type', options.osType);
    if (options?.arch) params.set('arch', options.arch);
    if (options?.status) params.set('status', options.status);
    if (typeof options?.limit === 'number') params.set('limit', String(options.limit));
    const suffix = params.toString() ? `?${params.toString()}` : '';
    return request<ComfyuiDesktopRelease[]>(`/api/admin/comfyui/desktop/releases${suffix}`);
  },
  createComfyuiDesktopRelease: (payload: Partial<ComfyuiDesktopRelease>) =>
    request<ComfyuiDesktopRelease>('/api/admin/comfyui/desktop/releases', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  updateComfyuiDesktopRelease: (releaseId: number, payload: Partial<ComfyuiDesktopRelease>) =>
    request<ComfyuiDesktopRelease>(`/api/admin/comfyui/desktop/releases/${releaseId}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),
  listComfyuiAgentTasks: (options?: { agentId?: string; status?: string; limit?: number }) => {
    const params = new URLSearchParams();
    if (options?.agentId) params.set('agent_id', options.agentId);
    if (options?.status) params.set('status', options.status);
    if (typeof options?.limit === 'number') params.set('limit', String(options.limit));
    const suffix = params.toString() ? `?${params.toString()}` : '';
    return request<ComfyuiAgentTask[]>(`/api/admin/comfyui/tasks${suffix}`);
  },
  createComfyuiAgentTask: (
    payload: {
      agentId: string;
      actions: string[];
      manifestId?: number | null;
      manifestUrl?: string | null;
      expiresAt?: string | null;
      taskId?: string | null;
    },
    options?: { push?: boolean },
  ) => {
    const suffix = options?.push === false ? '?push=false' : '';
    return request<ComfyuiAgentTask>(`/api/admin/comfyui/tasks${suffix}`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },
  getComfyuiAgentTask: (taskId: string) =>
    request<ComfyuiAgentTask>(`/api/admin/comfyui/tasks/${encodeURIComponent(taskId)}`),
  pushComfyuiAgentTask: (taskId: string) =>
    request<{ taskId: string; agentId: string; status: string; pushStatus: number; tokenExpiresAt: string }>(
      `/api/admin/comfyui/tasks/${encodeURIComponent(taskId)}/push`,
      { method: 'POST' },
    ),
  listComfyuiAgentTaskEvents: (taskId: string, limit = 50) =>
    request<ComfyuiAgentTaskEvent[]>(
      `/api/admin/comfyui/tasks/${encodeURIComponent(taskId)}/events?limit=${limit}`,
    ),

  // Dashboard
  getDashboardMetrics: () => request<DashboardMetrics>('/api/admin/dashboard/metrics'),
  getDispatchLogs: () => request<DispatchLogResponse>('/api/admin/dashboard/logs'),
  getSystemConfig: () => request<SystemConfig>('/api/admin/dashboard/system-config'),
  createStrategySnapshot: (payload?: { windowHours?: number; note?: string }) =>
    request<StrategySnapshotResponse>('/api/admin/dashboard/strategy-summary/snapshots', {
      method: 'POST',
      body: JSON.stringify(payload || { windowHours: 168 }),
    }),
  listStrategySnapshots: (limit = 8) =>
    request<StrategySnapshotListResponse>(`/api/admin/dashboard/strategy-summary/snapshots?limit=${limit}`),
  runWeeklyReport: (payload?: { windowHours?: number; note?: string; send?: boolean; webhookFormat?: string }) =>
    request<WeeklyReportResponse>('/api/admin/dashboard/weekly-report/run', {
      method: 'POST',
      body: JSON.stringify(payload || { windowHours: 168, send: false }),
    }),
  listWeeklyReports: (limit = 5) =>
    request<WeeklyReportListResponse>(`/api/admin/dashboard/weekly-report/records?limit=${limit}`),
  runReleasePreflight: (payload?: { mode?: string; baseUrl?: string; expectServerUrl?: string }) =>
    request<ReleasePreflightResponse>('/api/admin/dashboard/release-preflight/run', {
      method: 'POST',
      body: JSON.stringify(payload || { mode: 'light' }),
    }),
  listReleasePreflightSnapshots: (limit = 5) =>
    request<ReleasePreflightSnapshotListResponse>(`/api/admin/dashboard/release-preflight/snapshots?limit=${limit}`),
  createReleasePatrolRecord: (payload: {
    status: string;
    command?: string;
    reportPath?: string;
    note?: string;
    summary?: JsonRecord;
  }) =>
    request<ReleasePatrolRecordResponse>('/api/admin/dashboard/release-patrol/records', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  importReleasePatrolReport: (payload: { reportPath: string; command?: string }) =>
    request<ReleasePatrolRecordResponse>('/api/admin/dashboard/release-patrol/import-report', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  listReleasePatrolRecords: (limit = 5) =>
    request<ReleasePatrolRecordListResponse>(`/api/admin/dashboard/release-patrol/records?limit=${limit}`),
  createReleaseDecisionRecord: (payload: {
    status: string;
    title?: string;
    preflightId?: string | null;
    patrolId?: string | null;
    note?: string;
    summary?: JsonRecord;
  }) =>
    request<ReleaseDecisionRecordResponse>('/api/admin/dashboard/release-decisions/records', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  listReleaseDecisionRecords: (limit = 5) =>
    request<ReleaseDecisionRecordListResponse>(`/api/admin/dashboard/release-decisions/records?limit=${limit}`),
  listBusinessCapabilities: () => request<BusinessCapabilityListResponse>('/api/admin/business/capabilities'),
  createBusinessCapability: (payload: Partial<BusinessCapability>) =>
    request<BusinessCapability>('/api/admin/business/capabilities', { method: 'POST', body: JSON.stringify(payload) }),
  updateBusinessCapability: (id: string, payload: Partial<BusinessCapability>) =>
    request<BusinessCapability>(`/api/admin/business/capabilities/${encodeURIComponent(id)}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),
  compareBusinessCapabilities: (id: string, targetId: string) =>
    request<BusinessCapabilityCompareResponse>(
      `/api/admin/business/capabilities/${encodeURIComponent(id)}/compare?target_id=${encodeURIComponent(targetId)}`,
    ),
  rollbackBusinessCapability: (id: string, payload: { targetCapabilityId: string; note?: string }) =>
    request<BusinessCapability>(`/api/admin/business/capabilities/${encodeURIComponent(id)}/rollback`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  createBusinessDefaultApproval: (id: string, payload: { note?: string }) =>
    request<BusinessDefaultApprovalListResponse['items'][number]>(
      `/api/admin/business/capabilities/${encodeURIComponent(id)}/default-approvals`,
      {
        method: 'POST',
        body: JSON.stringify(payload),
      },
    ),
  listBusinessDefaultApprovals: (options?: BusinessDefaultApprovalQueryOptions) => {
    const params = buildBusinessDefaultApprovalQuery(options);
    const suffix = params.toString() ? `?${params.toString()}` : '';
    return request<BusinessDefaultApprovalListResponse>(`/api/admin/business/default-approvals${suffix}`);
  },
  approveBusinessDefaultApproval: (id: string, payload: { note?: string }) =>
    request<BusinessDefaultApprovalListResponse['items'][number]>(
      `/api/admin/business/default-approvals/${encodeURIComponent(id)}/approve`,
      {
        method: 'POST',
        body: JSON.stringify(payload),
      },
    ),
  rejectBusinessDefaultApproval: (id: string, payload: { note?: string }) =>
    request<BusinessDefaultApprovalListResponse['items'][number]>(
      `/api/admin/business/default-approvals/${encodeURIComponent(id)}/reject`,
      {
        method: 'POST',
        body: JSON.stringify(payload),
      },
    ),
  listBusinessRuns: (options?: BusinessRunQueryOptions) => {
    const params = buildBusinessRunQuery(options);
    params.delete('window_hours');
    const suffix = params.toString() ? `?${params.toString()}` : '';
    return request<BusinessRunListResponse>(`/api/admin/business/runs${suffix}`);
  },
  exportBusinessRuns: (options?: BusinessRunQueryOptions) => {
    const params = buildBusinessRunQuery({ ...options, limit: options?.limit ?? 1000 });
    params.delete('window_hours');
    return requestBlob(`/api/admin/business/runs/export?${params.toString()}`, {
      method: 'GET',
      headers: { Accept: 'text/csv' },
    });
  },
  retryBusinessRunCallback: (runId: string) =>
    request<BusinessRunListResponse['items'][number]>(
      `/api/admin/business/runs/${encodeURIComponent(runId)}/callback/retry`,
      { method: 'POST' },
    ),
  retryBusinessRunBilling: (runId: string) =>
    request<BusinessRunListResponse['items'][number]>(
      `/api/admin/business/runs/${encodeURIComponent(runId)}/billing/retry`,
      { method: 'POST' },
    ),
  refundBusinessRunBilling: (runId: string) =>
    request<BusinessRunListResponse['items'][number]>(
      `/api/admin/business/runs/${encodeURIComponent(runId)}/billing/refund`,
      { method: 'POST' },
    ),
  getBusinessUsageSummary: (options?: BusinessRunQueryOptions) => {
    const params = buildBusinessRunQuery(options);
    params.delete('limit');
    if (!params.has('window_hours')) params.set('window_hours', '24');
    return request<BusinessUsageSummaryResponse>(`/api/admin/business/usage-summary?${params.toString()}`);
  },
  listBusinessOperationLogs: (options?: BusinessOperationLogQueryOptions) => {
    const params = buildBusinessOperationLogQuery(options);
    const suffix = params.toString() ? `?${params.toString()}` : '';
    return request<BusinessOperationLogListResponse>(`/api/admin/business/operation-logs${suffix}`);
  },
  getBillingOverview: (options?: BillingQueryOptions) => {
    const params = buildBillingQuery({ ...options, limit: options?.limit ?? 100 });
    return request<BillingOverviewResponse>(`/api/admin/billing/overview?${params.toString()}`);
  },
  getBillingMonthlySettlement: (options?: BillingQueryOptions) => {
    const params = buildBillingQuery({ ...options, limit: options?.limit ?? 200 });
    params.delete('issue_limit');
    params.delete('package_alert_limit');
    return request<BillingMonthlySettlementResponse>(`/api/admin/billing/monthly-settlement?${params.toString()}`);
  },
  listBillingMonthlySettlements: (options?: BillingQueryOptions & { status?: string }) => {
    const params = buildBillingQuery({ ...options, limit: options?.limit ?? 100 });
    params.delete('issue_limit');
    params.delete('package_alert_limit');
    if (options?.status?.trim() && options.status !== 'all') params.set('status', options.status.trim());
    return request<BillingMonthlySettlementListResponse>(`/api/admin/billing/monthly-settlements?${params.toString()}`);
  },
  issueBillingMonthlySettlement: (payload: BillingMonthlySettlementIssuePayload) =>
    request<BillingMonthlySettlementIssueResponse>('/api/admin/billing/monthly-settlements/issue', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  updateBillingMonthlySettlement: (settlementId: string, payload: BillingMonthlySettlementUpdatePayload) =>
    request<BillingMonthlySettlementRecord>(`/api/admin/billing/monthly-settlements/${encodeURIComponent(settlementId)}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),
  runBillingPackageAlertNotification: (payload: PackageAlertNotificationPayload) =>
    request<PackageAlertNotificationResponse>('/api/admin/billing/package-alerts/notify', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  listBillingPackageAlertNotifications: (limit = 20) =>
    request<PackageAlertNotificationListResponse>(
      `/api/admin/billing/package-alert-notifications?limit=${encodeURIComponent(String(limit))}`,
    ),
  getBillingNotificationConfig: () => request<BillingNotificationConfigResponse>('/api/admin/billing/notification-config'),
  updateBillingNotificationConfig: (payload: BillingNotificationConfigPayload) =>
    request<BillingNotificationConfigResponse>('/api/admin/billing/notification-config', {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),
  listPackagePurchaseOrders: (options?: Pick<BillingQueryOptions, 'businessKey'> & { userId?: string; status?: string; limit?: number }) => {
    const params = new URLSearchParams();
    if (options?.businessKey?.trim() && options.businessKey !== 'all') params.set('business_key', options.businessKey.trim());
    if (options?.userId?.trim()) params.set('user_id', options.userId.trim());
    if (options?.status?.trim() && options.status !== 'all') params.set('status', options.status.trim());
    params.set('limit', String(options?.limit ?? 50));
    return request<PackagePurchaseOrderListResponse>(`/api/admin/billing/package-purchase-orders?${params.toString()}`);
  },
  createPackagePurchaseOrder: (payload: PackagePurchaseOrderCreatePayload) =>
    request<PackagePurchaseOrderUpdateResponse['order']>('/api/admin/billing/package-purchase-orders', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  updatePackagePurchaseOrder: (orderId: string, payload: PackagePurchaseOrderUpdatePayload) =>
    request<PackagePurchaseOrderUpdateResponse>(`/api/admin/billing/package-purchase-orders/${encodeURIComponent(orderId)}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),
  listBillingInvoiceRequests: (options?: Pick<BillingQueryOptions, 'businessKey'> & { userId?: string; status?: string; relatedOrderType?: string; limit?: number }) => {
    const params = new URLSearchParams();
    if (options?.businessKey?.trim() && options.businessKey !== 'all') params.set('business_key', options.businessKey.trim());
    if (options?.userId?.trim()) params.set('user_id', options.userId.trim());
    if (options?.status?.trim() && options.status !== 'all') params.set('status', options.status.trim());
    if (options?.relatedOrderType?.trim()) params.set('related_order_type', options.relatedOrderType.trim());
    params.set('limit', String(options?.limit ?? 50));
    return request<BillingInvoiceRequestListResponse>(`/api/admin/billing/invoice-requests?${params.toString()}`);
  },
  createBillingInvoiceRequest: (payload: BillingInvoiceRequestCreatePayload) =>
    request<BillingInvoiceRequest>('/api/admin/billing/invoice-requests', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  updateBillingInvoiceRequest: (invoiceRequestId: string, payload: BillingInvoiceRequestUpdatePayload) =>
    request<BillingInvoiceRequest>(`/api/admin/billing/invoice-requests/${encodeURIComponent(invoiceRequestId)}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),
  runBillingMonthlyCollectionNotification: (payload: MonthlySettlementCollectionNotificationPayload) =>
    request<MonthlySettlementCollectionNotificationResponse>('/api/admin/billing/monthly-settlements/collections/notify', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  listBillingMonthlyCollectionNotifications: (limit = 20) =>
    request<MonthlySettlementCollectionNotificationListResponse>(
      `/api/admin/billing/monthly-settlement-collection-notifications?limit=${encodeURIComponent(String(limit))}`,
    ),
  getBillingUserDetail: (userId: string, options?: BillingQueryOptions) => {
    const params = buildBillingQuery({ ...options, pageSize: options?.pageSize ?? 20 });
    return request<BillingUserDetailResponse>(
      `/api/admin/billing/users/${encodeURIComponent(userId)}?${params.toString()}`,
    );
  },
  grantBillingPackage: (userId: string, payload: PackageGrantPayload) =>
    request<PackageGrantResponse>(`/api/admin/billing/users/${encodeURIComponent(userId)}/packages/grant`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  exportBillingUserLedger: (userId: string, month?: string, options?: Pick<BillingQueryOptions, 'businessKey'>) => {
    const params = new URLSearchParams();
    if (month?.trim()) params.set('month', month.trim());
    if (options?.businessKey?.trim() && options.businessKey !== 'all') {
      params.set('business_key', options.businessKey.trim());
    }
    return requestBlob(`/api/admin/billing/users/${encodeURIComponent(userId)}/ledger/export?${params.toString()}`, {
      method: 'GET',
      headers: { Accept: 'text/csv' },
    });
  },
  // Abilities
  listAbilities: () => request<Ability[]>('/api/admin/abilities'),
  getAbilityHealthSummary: (options?: AbilityHealthQueryOptions) => {
    const params = buildAbilityHealthQuery(options);
    return request<AbilityHealthSummaryResponse>(`/api/admin/abilities/health/summary?${params.toString()}`);
  },
  refreshAbilityHealthSummary: (options?: AbilityHealthQueryOptions) => {
    const params = buildAbilityHealthQuery(options);
    return request<AbilityHealthSummaryResponse>(`/api/admin/abilities/health/refresh?${params.toString()}`, {
      method: 'POST',
    });
  },
  exportAbilityHealthSummary: (options?: AbilityHealthQueryOptions) => {
    const params = buildAbilityHealthQuery({ ...options, limit: options?.limit ?? 500 });
    return requestBlob(`/api/admin/abilities/health/export?${params.toString()}`, {
      method: 'GET',
      headers: { Accept: 'text/csv' },
    });
  },
  createAbility: (payload: Partial<Ability>) =>
    request<Ability>('/api/admin/abilities', { method: 'POST', body: JSON.stringify(payload) }),
  updateAbility: (id: string, payload: Partial<Ability>) =>
    request<Ability>('/api/admin/abilities/' + id, { method: 'PUT', body: JSON.stringify(payload) }),
  deleteAbility: (id: string) => request<void>('/api/admin/abilities/' + id, { method: 'DELETE' }),
  getAbilityTemplateState: (abilityId: string) =>
    request<AbilityTemplateStateResponse>(`/api/admin/abilities/${encodeURIComponent(abilityId)}/template`),
  validateAbilityTemplate: (
    abilityId: string,
    payload?: { default_params?: JsonRecord; input_schema?: JsonRecord; metadata?: JsonRecord },
  ) =>
    request<AbilityTemplateValidateResponse>(`/api/admin/abilities/${encodeURIComponent(abilityId)}/template/validate`, {
      method: 'POST',
      body: JSON.stringify(payload || {}),
    }),
  publishAbilityTemplate: (abilityId: string, payload?: { version_label?: string; notes?: string }) =>
    request<AbilityTemplateStateResponse>(`/api/admin/abilities/${encodeURIComponent(abilityId)}/template/publish`, {
      method: 'POST',
      body: JSON.stringify(payload || {}),
    }),
  rollbackAbilityTemplate: (abilityId: string, payload: { templateId: string; notes?: string }) =>
    request<AbilityTemplateStateResponse>(`/api/admin/abilities/${encodeURIComponent(abilityId)}/template/rollback`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  listAbilityLogs: (abilityId: string, options?: { limit?: number; offset?: number }) => {
    const params = new URLSearchParams();
    params.set('limit', String(options?.limit ?? 20));
    if (typeof options?.offset === 'number') params.set('offset', String(options.offset));
    return request<AbilityLogListResponse>(
      `/api/admin/abilities/${encodeURIComponent(abilityId)}/logs?${params.toString()}`,
    );
  },
  listAllAbilityLogs: (options?: {
    limit?: number;
    offset?: number;
    abilityId?: string;
    provider?: string;
    capabilityKey?: string;
    status?: string;
    source?: string;
    templateId?: string;
    templatePublished?: boolean;
  }) => {
    const params = new URLSearchParams();
    const limit = options?.limit ?? 20;
    params.set('limit', String(limit));
    if (typeof options?.offset === 'number') params.set('offset', String(options.offset));
    if (options?.abilityId) params.set('abilityId', options.abilityId);
    if (options?.provider) params.set('provider', options.provider);
    if (options?.capabilityKey) params.set('capabilityKey', options.capabilityKey);
    if (options?.status) params.set('status', options.status);
    if (options?.source) params.set('source', options.source);
    if (options?.templateId) params.set('templateId', options.templateId);
    if (typeof options?.templatePublished === 'boolean') {
      params.set('templatePublished', options.templatePublished ? 'true' : 'false');
    }
    return request<AbilityLogListResponse>(`/api/admin/abilities/logs?${params.toString()}`);
  },
  resolveAbilityLog: (logId: number) =>
    request<AbilityInvocationLog>(`/api/admin/abilities/logs/${logId}/resolve`, { method: 'POST' }),
  getAbilityLogMetrics: (options?: { windowHours?: number; provider?: string; capabilityKey?: string; groupByExecutor?: boolean }) => {
    const params = new URLSearchParams();
    params.set('windowHours', String(options?.windowHours ?? 24));
    if (options?.provider) params.set('provider', options.provider);
    if (options?.capabilityKey) params.set('capabilityKey', options.capabilityKey);
    if (options?.groupByExecutor) params.set('groupByExecutor', 'true');
    return request<AbilityLogMetricsResponse>(`/api/admin/abilities/logs/metrics?${params.toString()}`);
  },
  exportAbilityLogs: async (options?: {
    format?: 'csv' | 'json';
    provider?: string;
    capabilityKey?: string;
    abilityId?: string;
    templateId?: string;
    templatePublished?: boolean;
    executorId?: string;
    status?: string;
    source?: string;
    sinceHours?: number;
  }) => {
    const params = new URLSearchParams();
    params.set('format', options?.format ?? 'csv');
    params.set('sinceHours', String(options?.sinceHours ?? 24));
    if (options?.provider) params.set('provider', options.provider);
    if (options?.capabilityKey) params.set('capabilityKey', options.capabilityKey);
    if (options?.abilityId) params.set('abilityId', options.abilityId);
    if (options?.templateId) params.set('templateId', options.templateId);
    if (typeof options?.templatePublished === 'boolean') {
      params.set('templatePublished', options.templatePublished ? 'true' : 'false');
    }
    if (options?.executorId) params.set('executorId', options.executorId);
    if (options?.status) params.set('status', options.status);
    if (options?.source) params.set('source', options.source);
    return requestBlob(`/api/admin/abilities/logs/export?${params.toString()}`, {
      method: 'GET',
      headers: { Accept: options?.format === 'json' ? 'application/json' : 'text/csv' },
    });
  },
  listPublicAbilities: () =>
    request<AbilityListResponse>('/api/abilities').then((res) => (res.items || []) as PublicAbility[]),

  // Ability evaluations (internal)
  listEvalWorkflowVersions: (params?: { category?: string; status?: string }) => {
    const qs = new URLSearchParams();
    if (params?.category) qs.set('category', params.category);
    if (params?.status) qs.set('status', params.status);
    const suffix = qs.toString() ? `?${qs.toString()}` : '';
    return request<EvalWorkflowVersion[]>(`/api/admin/evals/workflow-versions${suffix}`);
  },
  createEvalWorkflowVersion: (payload: Partial<EvalWorkflowVersion>) =>
    request<EvalWorkflowVersion>('/api/admin/evals/workflow-versions', { method: 'POST', body: JSON.stringify(payload) }),
  updateEvalWorkflowVersion: (id: string, payload: Partial<EvalWorkflowVersion>) =>
    request<EvalWorkflowVersion>(`/api/admin/evals/workflow-versions/${encodeURIComponent(id)}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),
  listEvalDatasetItems: (params?: { category?: string }) => {
    const qs = new URLSearchParams();
    if (params?.category) qs.set('category', params.category);
    const suffix = qs.toString() ? `?${qs.toString()}` : '';
    return request<EvalDatasetItem[]>(`/api/admin/evals/datasets${suffix}`);
  },
  createEvalDatasetItem: (payload: Partial<EvalDatasetItem>) =>
    request<EvalDatasetItem>('/api/admin/evals/datasets', { method: 'POST', body: JSON.stringify(payload) }),
  createEvalRun: (payload: {
    workflow_version_id: string;
    dataset_item_id?: string | null;
    input_oss_urls_json?: string[];
    parameters_json?: Record<string, unknown>;
  }) => request<EvalRun>('/api/admin/evals/runs', { method: 'POST', body: JSON.stringify(payload) }),
  listEvalRuns: (params?: { workflow_version_id?: string; status?: string; limit?: number; offset?: number }) => {
    const qs = new URLSearchParams();
    if (params?.workflow_version_id) qs.set('workflow_version_id', params.workflow_version_id);
    if (params?.status) qs.set('status', params.status);
    if (params?.limit !== undefined) qs.set('limit', String(params.limit));
    if (params?.offset !== undefined) qs.set('offset', String(params.offset));
    const suffix = qs.toString() ? `?${qs.toString()}` : '';
    return request<EvalRunListResponse>(`/api/admin/evals/runs${suffix}`);
  },
  getEvalRun: (runId: string) => request<EvalRun>(`/api/admin/evals/runs/${runId}`),
  createEvalAnnotation: (runId: string, payload: { rating: number; comment?: string; tags_json?: string[] }) =>
    request<EvalAnnotation>(`/api/admin/evals/runs/${runId}/annotations`, { method: 'POST', body: JSON.stringify(payload) }),
  purgeEvalRuns: (params?: { workflow_version_id?: string }) => {
    const qs = new URLSearchParams();
    if (params?.workflow_version_id) qs.set('workflow_version_id', params.workflow_version_id);
    qs.set('confirm', 'true');
    const suffix = qs.toString() ? `?${qs.toString()}` : '';
    return request<EvalRunPurgeResponse>(`/api/admin/evals/runs${suffix}`, { method: 'DELETE' });
  },
};
