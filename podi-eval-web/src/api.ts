import type { EvalRun, EvalRunListResponse, EvalWorkflowVersion } from './types';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '';
const DEFAULT_TIMEOUT_MS = 15000;
const AUTH_INVALID_MESSAGE = '认证已失效，请重新登录';
const GATEWAY_ERROR_MESSAGE = '服务不可达或网关异常，请稍后再试';

function extractErrorMessage(statusText: string, bodyText: string): string {
  const text = (bodyText || '').trim();
  if (!text) return statusText || 'Request failed';
  const lower = text.toLowerCase();
  if (lower.startsWith('<!doctype') || lower.startsWith('<html')) {
    return '服务异常（网关或代理返回了 HTML 页面）';
  }
  // Prefer FastAPI-style {"detail": "..."}.
  try {
    const parsed = JSON.parse(text);
    const detail = (parsed as any)?.detail;
    if (typeof detail === 'string' && detail.trim()) return detail.trim();
    if (detail && typeof detail === 'object') return JSON.stringify(detail);
    // Generic error/message fields.
    for (const key of ['message', 'msg', 'error_message', 'error']) {
      const v = (parsed as any)?.[key];
      if (typeof v === 'string' && v.trim()) return v.trim();
    }
  } catch {
    // non-JSON
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

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const { options: timedOptions, cancel } = withTimeout(options, DEFAULT_TIMEOUT_MS);
  let resp: Response;
  try {
    resp = await fetch(`${API_BASE}${path}`, {
      ...timedOptions,
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        ...(options.headers || {}),
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
    throw new Error(resolveHttpError(resp.status, resp.statusText, text));
  }
  const contentType = resp.headers.get('content-type') || '';
  const text = await resp.text();
  if (!contentType.includes('application/json')) {
    // When dev proxy isn't configured, Vite may return index.html (text/html).
    throw new Error(extractErrorMessage('', text) || '服务异常：响应不是 JSON');
  }
  return JSON.parse(text) as T;
}

export const evalApi = {
  me: () => request<{ raterId: string }>('/api/evals/me'),
  listWorkflowVersions: () => request<EvalWorkflowVersion[]>('/api/evals/workflow-versions?status=active'),
  getWorkflowDocs: () => request<{ markdown: string; generatedAt?: string }>('/api/evals/docs/workflows'),
  createRun: (payload: {
    workflow_version_id: string;
    dataset_item_id?: string | null;
    input_oss_urls_json?: string[];
    parameters_json?: Record<string, unknown>;
  }) => request<EvalRun>('/api/evals/runs', { method: 'POST', body: JSON.stringify(payload) }),
  listRuns: (params: { workflow_version_id?: string; limit?: number; offset?: number; status?: string; unrated?: boolean }) => {
    const qs = new URLSearchParams();
    if (params.workflow_version_id) qs.set('workflow_version_id', params.workflow_version_id);
    qs.set('limit', String(params.limit ?? 50));
    qs.set('offset', String(params.offset ?? 0));
    if (params.status) qs.set('status', params.status);
    if (params.unrated) qs.set('unrated', 'true');
    return request<EvalRunListResponse>(`/api/evals/runs?${qs.toString()}`);
  },
  getRun: (runId: string) => request<EvalRun>(`/api/evals/runs/${runId}`),
  createAnnotation: (runId: string, payload: { rating: number; comment?: string }) =>
    request(`/api/evals/runs/${runId}/annotations`, { method: 'POST', body: JSON.stringify(payload) }),
  listAnnotations: (runId: string) => request(`/api/evals/runs/${runId}/annotations`),
  workflowMetrics: () => request<{ metrics: Record<string, { ratingCount: number; avgRating: number | null }> }>(`/api/evals/metrics/workflows`),
  listRunsWithLatestAnnotation: (params: { workflow_version_id?: string; status?: string; unrated?: boolean; limit?: number; offset?: number }) => {
    const qs = new URLSearchParams();
    if (params.workflow_version_id) qs.set('workflow_version_id', params.workflow_version_id);
    if (params.status) qs.set('status', params.status);
    if (params.unrated) qs.set('unrated', 'true');
    qs.set('limit', String(params.limit ?? 50));
    qs.set('offset', String(params.offset ?? 0));
    return request<{ total: number; items: any[] }>(`/api/evals/runs/with-latest-annotation?${qs.toString()}`);
  },
  uploadImage: async (file: File) => {
    const form = new FormData();
    form.append('file', file);
    const { options: timedOptions, cancel } = withTimeout(
      { method: 'POST', body: form, credentials: 'include' },
      30000,
    );
    let resp: Response;
    try {
      resp = await fetch(`${API_BASE}/api/evals/uploads`, timedOptions);
    } catch (err) {
      cancel();
      if (err instanceof DOMException && err.name === 'AbortError') {
        throw new Error('上传超时，请检查网络或服务是否可用');
      }
      throw new Error(String((err as any)?.message || err || '网络请求失败'));
    }
    cancel();
    if (!resp.ok) {
      const text = await resp.text();
      const msg = resolveHttpError(resp.status, resp.statusText, text);
      // When reverse proxies return an empty body, `new Error('')` becomes just "Error".
      // Include status so the UI can show something actionable (413/502/etc).
      throw new Error(`上传失败 (status=${resp.status}): ${msg}`);
    }
    return resp.json() as Promise<{ url: string; objectKey: string }>;
  },
  adminListWorkflowVersions: async (adminToken: string) =>
    request<EvalWorkflowVersion[]>(`/api/evals/admin/workflow-versions`, { headers: { 'X-Eval-Admin-Token': adminToken } }),
  adminUpdateWorkflowVersion: async (adminToken: string, id: string, payload: Partial<EvalWorkflowVersion>) =>
    request<EvalWorkflowVersion>(`/api/evals/admin/workflow-versions/${id}`, {
      method: 'PUT',
      headers: { 'X-Eval-Admin-Token': adminToken },
      body: JSON.stringify(payload),
    }),
};
