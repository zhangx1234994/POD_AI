import type { EvalRun, EvalRunListResponse, EvalWorkflowVersion, WorkflowDoc } from './types';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '';
const DEFAULT_TIMEOUT_MS = 15000;
const BATCH_DETAIL_TIMEOUT_MS = 45000;
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
  if (status === 401) return AUTH_INVALID_MESSAGE;
  if (status === 403) {
    const message = extractErrorMessage(statusText, bodyText);
    if (message === 'BATCH_FORBIDDEN') return '无权访问该批次';
    return message || '无权访问';
  }
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

async function request<T>(path: string, options: RequestInit = {}, timeoutMs: number = DEFAULT_TIMEOUT_MS): Promise<T> {
  const { options: timedOptions, cancel } = withTimeout(options, timeoutMs);
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
    qs.set('mine_only', params.mine_only === false ? 'false' : 'true');
    qs.set('limit', String(params.limit ?? 50));
    qs.set('offset', String(params.offset ?? 0));
    return request<{
      total: number;
      items: Array<{
        id: string;
        workflow_version_id?: string | null;
        status?: string;
        planned_image_count?: number;
        repeat_count?: number;
        planned_run_count?: number;
        submitted_count?: number;
        running_count?: number;
        succeeded_count?: number;
        failed_count?: number;
        canceled_count?: number;
        created_at?: string | null;
        updated_at?: string | null;
      }>;
    }>(`/api/evals/batches?${qs.toString()}`).then((res) => ({
      total: Number(res.total || 0),
      items: (Array.isArray(res.items) ? res.items : []).map((item) => {
        const planned = Number(item.planned_run_count || 0);
        const succeeded = Number(item.succeeded_count || 0);
        const failed = Number(item.failed_count || 0);
        const canceled = Number(item.canceled_count || 0);
        const running = Number(item.running_count || 0);
        const submitted = Number(item.submitted_count || 0);
        const completed = succeeded + failed + canceled;
        const queued = Math.max(0, planned - completed - running);
        return {
          batchId: String(item.id || ''),
          workflowVersionId: item.workflow_version_id ? String(item.workflow_version_id) : null,
          workflowName: null,
          total: planned,
          completed,
          queued,
          running,
          succeeded,
          failed: failed + canceled,
          expectedTotal: planned,
          expectedImages: Number(item.planned_image_count || 0),
          expectedRepeat: Number(item.repeat_count || 0),
          latestCreatedAt: item.created_at || null,
          latestUpdatedAt: item.updated_at || null,
          submittedCount: submitted,
          status: String(item.status || ''),
        };
      }),
    }));
  },
  stopRunBatch: (batchId: string) =>
    request<{ batch_id: string; stopped_run_items: number; stopped_eval_runs: number; stopped_ability_tasks: number }>(
      `/api/evals/batches/${encodeURIComponent(batchId)}/stop`,
      { method: 'POST' },
    ).then((res) => ({
      batchId: String(res.batch_id || batchId),
      stoppedRuns: Number(res.stopped_eval_runs || 0),
      stoppedTasks: Number(res.stopped_ability_tasks || 0),
      stoppedRunItems: Number(res.stopped_run_items || 0),
    })),
  createBatch: (payload: {
    workflow_version_id: string;
    repeat_count: number;
    parameters_json?: Record<string, unknown>;
    metadata?: Record<string, unknown>;
  }) =>
    request<{
      id: string;
      status: string;
      planned_image_count: number;
      repeat_count: number;
      planned_run_count: number;
      created_at: string;
      updated_at: string;
    }>(`/api/evals/batches`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  upsertBatchAssets: (
    batchId: string,
    payload: {
      items: Array<{
        source_key: string;
        file_name: string;
        oss_url?: string;
        object_key?: string;
        size_bytes?: number;
        width?: number;
        height?: number;
        upload_status: string;
        upload_error_code?: string;
        upload_error_message?: string;
      }>;
    },
  ) =>
    request<{ total: number; items: Array<{ id: string; source_key: string; upload_status: string }> }>(
      `/api/evals/batches/${encodeURIComponent(batchId)}/assets`,
      { method: 'POST', body: JSON.stringify(payload) },
    ),
  listBatchAssets: (batchId: string, params?: { status?: string; limit?: number; offset?: number }) => {
    const qs = new URLSearchParams();
    if (params?.status) qs.set('status', params.status);
    qs.set('limit', String(params?.limit ?? 200));
    qs.set('offset', String(params?.offset ?? 0));
    return request<{
      total: number;
      items: Array<{
        id: string;
        source_key: string;
        file_name: string;
        oss_url?: string | null;
        upload_status: string;
        upload_error_code?: string | null;
        upload_error_message?: string | null;
      }>;
    }>(`/api/evals/batches/${encodeURIComponent(batchId)}/assets?${qs.toString()}`, {}, BATCH_DETAIL_TIMEOUT_MS);
  },
  submitBatch: (batchId: string, payload?: { parameters_json?: Record<string, unknown>; only_pending?: boolean }) =>
    request<{ batch_id: string; created_items: number; submitted_items: number; failed_items: number }>(
      `/api/evals/batches/${encodeURIComponent(batchId)}/submit`,
      { method: 'POST', body: JSON.stringify(payload || { only_pending: true }) },
    ),
  listBatchItems: (batchId: string, params?: { status?: string; limit?: number; offset?: number }) => {
    const qs = new URLSearchParams();
    if (params?.status) qs.set('status', params.status);
    qs.set('limit', String(params?.limit ?? 200));
    qs.set('offset', String(params?.offset ?? 0));
    return request<{
      total: number;
      items: Array<{
        id: string;
        batch_session_id: string;
        asset_id: string;
        asset_source_key?: string | null;
        asset_file_name?: string | null;
        asset_oss_url?: string | null;
        repeat_index: number;
        eval_run_id?: string | null;
        status: string;
        run_status?: string | null;
        run_prompt?: string | null;
        run_output_urls_json?: string[] | null;
        run_error_message?: string | null;
        error_code?: string | null;
        error_message?: string | null;
      }>;
    }>(`/api/evals/batches/${encodeURIComponent(batchId)}/items?${qs.toString()}`, {}, BATCH_DETAIL_TIMEOUT_MS);
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
