import type {
  Ability,
  AbilityListResponse,
  AbilityLogListResponse,
  AbilityLogMetricsResponse,
  ApiKey,
  Binding,
  DashboardMetrics,
  DispatchLogResponse,
  Executor,
  ComfyuiQueueStatus,
  ComfyuiQueueSummary,
  JsonRecord,
  PublicAbility,
  StoredAsset,
  SystemConfig,
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
  if (status === 401 || status === 403) return AUTH_INVALID_MESSAGE;
  if (status === 502 || status === 503 || status === 504) return GATEWAY_ERROR_MESSAGE;
  const message = extractErrorMessage(statusText, bodyText);
  if (status >= 500 && (!message || message === statusText)) {
    return '服务异常，请稍后再试';
  }
  return message || statusText || 'Request failed';
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
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new Error('请求超时，请检查网络或服务是否可用');
    }
    throw new Error(String((err as any)?.message || err || '网络请求失败'));
  }
  cancel();
  if (!resp.ok) {
    const text = await resp.text();
    const message = resolveHttpError(resp.status, resp.statusText, text);
    if (resp.status === 401 || resp.status === 403) {
      clearAdminTokens();
      broadcastInvalidToken(message);
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
    if (resp.status === 401 || resp.status === 403) {
      clearAdminTokens();
      broadcastInvalidToken(message);
    }
    throw new Error(message);
  }
  return resp.blob();
}

export const adminApi = {
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

  getComfyuiModels: (executorId: string) =>
    request<{ executorId: string; baseUrl: string; models: Record<string, string[]> }>(
      `/api/admin/comfyui/models?executorId=${encodeURIComponent(executorId)}`,
    ),
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

  // Dashboard
  getDashboardMetrics: () => request<DashboardMetrics>('/api/admin/dashboard/metrics'),
  getDispatchLogs: () => request<DispatchLogResponse>('/api/admin/dashboard/logs'),
  getSystemConfig: () => request<SystemConfig>('/api/admin/dashboard/system-config'),
  // Abilities
  listAbilities: () => request<Ability[]>('/api/admin/abilities'),
  createAbility: (payload: Partial<Ability>) =>
    request<Ability>('/api/admin/abilities', { method: 'POST', body: JSON.stringify(payload) }),
  updateAbility: (id: string, payload: Partial<Ability>) =>
    request<Ability>('/api/admin/abilities/' + id, { method: 'PUT', body: JSON.stringify(payload) }),
  deleteAbility: (id: string) => request<void>('/api/admin/abilities/' + id, { method: 'DELETE' }),
  listAbilityLogs: (abilityId: string, limit = 20) =>
    request<AbilityLogListResponse>(`/api/admin/abilities/${encodeURIComponent(abilityId)}/logs?limit=${limit}`),
  listAllAbilityLogs: (options?: { limit?: number; abilityId?: string; provider?: string; capabilityKey?: string }) => {
    const params = new URLSearchParams();
    const limit = options?.limit ?? 20;
    params.set('limit', String(limit));
    if (options?.abilityId) params.set('abilityId', options.abilityId);
    if (options?.provider) params.set('provider', options.provider);
    if (options?.capabilityKey) params.set('capabilityKey', options.capabilityKey);
    return request<AbilityLogListResponse>(`/api/admin/abilities/logs?${params.toString()}`);
  },
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
