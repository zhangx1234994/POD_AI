import type {
  Ability,
  AbilityListResponse,
  AbilityLogListResponse,
  ApiKey,
  Binding,
  DashboardMetrics,
  DispatchLogResponse,
  Executor,
  ComfyuiQueueStatus,
  JsonRecord,
  PublicAbility,
  StoredAsset,
  SystemConfig,
  Workflow,
} from '../types/admin';
import type { EvalAnnotation, EvalDatasetItem, EvalRun, EvalRunListResponse, EvalWorkflowVersion } from '../types/eval';

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

export function getAdminToken() {
  return localStorage.getItem('podi_admin_access_token');
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

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getAdminToken();
  const resp = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });
  if (!resp.ok) {
    const text = await resp.text();
    if (resp.status === 401) {
      clearAdminTokens();
      let message = text;
      try {
        const parsed = JSON.parse(text);
        if (parsed?.detail) {
          message = typeof parsed.detail === 'string' ? parsed.detail : JSON.stringify(parsed.detail);
        }
      } catch (err) {
        // ignore JSON parse errors
      }
      broadcastInvalidToken(message || '登录已失效，请重新登录');
    }
    throw new Error(text || resp.statusText);
  }
  return resp.json();
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
    request<BaiduImageTestResponse>('/api/admin/tests/baidu/quality-upgrade', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  testBaiduImageProcess: (payload: AbilityContextPayload & {
    executorId: string;
    operation: string;
    imageBase64?: string;
    imageUrl?: string;
    params?: Record<string, unknown>;
  }): Promise<BaiduImageTestResponse> =>
    request<BaiduImageTestResponse>('/api/admin/tests/baidu/image-process', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
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
    ),
  testComfyuiWorkflow: (payload: AbilityContextPayload & {
    executorId: string;
    workflowKey: string;
    workflowParams: JsonRecord;
  }) =>
    request<{
      provider: string;
      workflowKey: string;
      promptId: string;
      logId?: number | string;
      storedUrl?: string;
      assets?: StoredAsset[];
      raw?: JsonRecord | null;
    }>('/api/admin/tests/comfyui/workflow', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  getComfyuiModels: (executorId: string) =>
    request<{ executorId: string; baseUrl: string; models: Record<string, string[]> }>(
      `/api/admin/comfyui/models?executorId=${encodeURIComponent(executorId)}`,
    ),
  getComfyuiQueueStatus: (executorId: string) =>
    request<ComfyuiQueueStatus>(`/api/admin/comfyui/queue-status?executorId=${encodeURIComponent(executorId)}`),

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
};
