import type { EvalRun, EvalRunListResponse, EvalWorkflowVersion, WorkflowDoc } from './types';

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
  getWorkflowDocs: () =>
    request<{ markdown: string; generatedAt?: string; workflows?: WorkflowDoc[] }>('/api/evals/docs/workflows'),
  createRun: (payload: {
    workflow_version_id: string;
    dataset_item_id?: string | null;
    input_oss_urls_json?: string[];
    parameters_json?: Record<string, unknown>;
  }) => request<EvalRun>('/api/evals/runs', { method: 'POST', body: JSON.stringify(payload) }),
  listRuns: (params: {
    workflow_version_id?: string;
    batch_session_id?: string;
    batch_mode?: boolean;
    mine_only?: boolean;
    limit?: number;
    offset?: number;
    status?: string;
    unrated?: boolean;
  }) => {
    const qs = new URLSearchParams();
    if (params.workflow_version_id) qs.set('workflow_version_id', params.workflow_version_id);
    if (params.batch_session_id) qs.set('batch_session_id', params.batch_session_id);
    if (params.batch_mode) qs.set('batch_mode', 'true');
    if (params.mine_only) qs.set('mine_only', 'true');
    qs.set('limit', String(params.limit ?? 50));
    qs.set('offset', String(params.offset ?? 0));
    if (params.status) qs.set('status', params.status);
    if (params.unrated) qs.set('unrated', 'true');
    return request<EvalRunListResponse>(`/api/evals/runs?${qs.toString()}`);
  },
  listRunBatches: (params: { workflow_version_id?: string; mine_only?: boolean; limit?: number; offset?: number }) => {
    const qs = new URLSearchParams();
    if (params.workflow_version_id) qs.set('workflow_version_id', params.workflow_version_id);
    if (params.mine_only !== false) qs.set('mine_only', 'true');
    qs.set('limit', String(params.limit ?? 50));
    qs.set('offset', String(params.offset ?? 0));
    return request<{
      total: number;
      items: Array<{
        batchId: string;
        workflowVersionId?: string | null;
        workflowName?: string | null;
        total: number;
        completed: number;
        queued: number;
        running: number;
        succeeded: number;
        failed: number;
        expectedTotal?: number;
        expectedImages?: number;
        expectedRepeat?: number;
        latestCreatedAt?: string | null;
        latestUpdatedAt?: string | null;
      }>;
    }>(`/api/evals/runs/batches?${qs.toString()}`);
  },
  stopRunBatch: (batchId: string) => request<{ batchId: string; stoppedRuns: number; stoppedTasks: number }>(`/api/evals/runs/batches/${encodeURIComponent(batchId)}/stop`, { method: 'POST' }),
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
  uploadImage: (file: File, opts?: { onProgress?: (loaded: number, total: number) => void; timeoutMs?: number }) =>
    new Promise<{ url: string; objectKey: string }>((resolve, reject) => {
      const form = new FormData();
      form.append('file', file);
      const xhr = new XMLHttpRequest();
      xhr.open('POST', `${API_BASE}/api/evals/uploads`, true);
      xhr.withCredentials = true;
      xhr.timeout = Number(opts?.timeoutMs || 30000);

      xhr.upload.onprogress = (evt) => {
        if (!opts?.onProgress) return;
        if (evt.lengthComputable) {
          opts.onProgress(Math.max(0, evt.loaded || 0), Math.max(1, evt.total || file.size || 1));
          return;
        }
        opts.onProgress(0, Math.max(1, file.size || 1));
      };

      xhr.onerror = () => {
        reject(new Error('上传失败：网络异常或服务不可达'));
      };
      xhr.ontimeout = () => {
        reject(new Error('上传超时，请检查网络或服务是否可用'));
      };
      xhr.onabort = () => {
        reject(new Error('上传已中断，请重试'));
      };
      xhr.onload = () => {
        const status = xhr.status || 0;
        const bodyText = xhr.responseText || '';
        if (status < 200 || status >= 300) {
          const msg = resolveHttpError(status, xhr.statusText || '', bodyText);
          reject(new Error(`上传失败 (status=${status}): ${msg}`));
          return;
        }
        try {
          const parsed = JSON.parse(bodyText || '{}') as { url?: string; objectKey?: string };
          if (!parsed?.url) {
            reject(new Error('上传失败：服务未返回可用 URL'));
            return;
          }
          resolve({
            url: String(parsed.url),
            objectKey: String(parsed.objectKey || ''),
          });
        } catch {
          reject(new Error('上传失败：响应格式异常'));
        }
      };
      xhr.send(form);
    }),
  adminListWorkflowVersions: async (adminToken: string) =>
    request<EvalWorkflowVersion[]>(`/api/evals/admin/workflow-versions`, { headers: { 'X-Eval-Admin-Token': adminToken } }),
  adminUpdateWorkflowVersion: async (adminToken: string, id: string, payload: Partial<EvalWorkflowVersion>) =>
    request<EvalWorkflowVersion>(`/api/evals/admin/workflow-versions/${id}`, {
      method: 'PUT',
      headers: { 'X-Eval-Admin-Token': adminToken },
      body: JSON.stringify(payload),
    }),
};
