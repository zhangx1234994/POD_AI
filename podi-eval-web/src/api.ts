import type {
  EvalBusinessQualitySampleListResponse,
  ComfyuiQueueSummary,
  EvalResourceOptionsResponse,
  EvalOperationsHealth,
  EvalRun,
  EvalRunListResponse,
  EvalWorkflowVersion,
  WorkflowDoc,
} from './types';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '';
const DEFAULT_TIMEOUT_MS = 15000;
const BATCH_DETAIL_TIMEOUT_MS = 45000;
const AUTH_INVALID_MESSAGE = '认证已失效，请重新登录';
const GATEWAY_ERROR_MESSAGE = '服务不可达或网关异常，请稍后再试';

export class ApiRequestError extends Error {
  status?: number;
  statusText?: string;
  rawBody?: string;
  kind: 'http' | 'network' | 'timeout';

  constructor(params: {
    message: string;
    kind: 'http' | 'network' | 'timeout';
    status?: number;
    statusText?: string;
    rawBody?: string;
  }) {
    super(params.message);
    this.name = 'ApiRequestError';
    this.kind = params.kind;
    this.status = params.status;
    this.statusText = params.statusText;
    this.rawBody = params.rawBody;
  }
}

let cachedRaterId: string | null = null;

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
  if (status === 502 || status === 503 || status === 504) {
    const message = extractErrorMessage(statusText, bodyText);
    return message && message !== statusText ? message : GATEWAY_ERROR_MESSAGE;
  }
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
      throw new ApiRequestError({
        message: '请求超时，请检查网络或服务是否可用',
        kind: 'timeout',
      });
    }
    throw new ApiRequestError({
      message: String((err as any)?.message || err || '网络请求失败'),
      kind: 'network',
    });
  }
  cancel();
  if (!resp.ok) {
    const text = await resp.text();
    throw new ApiRequestError({
      message: resolveHttpError(resp.status, resp.statusText, text),
      kind: 'http',
      status: resp.status,
      statusText: resp.statusText,
      rawBody: text,
    });
  }
  const contentType = resp.headers.get('content-type') || '';
  const text = await resp.text();
  if (!contentType.includes('application/json')) {
    // When dev proxy isn't configured, Vite may return index.html (text/html).
    throw new ApiRequestError({
      message: extractErrorMessage('', text) || '服务异常：响应不是 JSON',
      kind: 'http',
      status: resp.status,
      statusText: resp.statusText,
      rawBody: text,
    });
  }
  return JSON.parse(text) as T;
}

async function ensureEvalRaterId(): Promise<string> {
  if (cachedRaterId) return cachedRaterId;
  const me = await request<{ raterId: string }>('/api/evals/me');
  const rid = String(me.raterId || '').trim() || 'eval-user';
  cachedRaterId = rid;
  return rid;
}

function uploadImageViaBackend(
  file: File,
  opts?: { onProgress?: (loaded: number, total: number) => void; timeoutMs?: number },
): Promise<{ url: string; objectKey: string }> {
  const totalBytes = Math.max(1, Number(file.size || 0));
  return new Promise((resolve, reject) => {
    const form = new FormData();
    form.append('file', file);
    const xhr = new XMLHttpRequest();
    xhr.open('POST', `${API_BASE}/api/evals/uploads`, true);
    xhr.withCredentials = true;
    xhr.timeout = Number(opts?.timeoutMs || 30000);
    xhr.upload.onprogress = (event) => {
      if (!opts?.onProgress) return;
      const loaded = event.lengthComputable ? event.loaded : 0;
      const total = event.lengthComputable ? event.total : totalBytes;
      opts.onProgress(Math.max(0, loaded), Math.max(1, total));
    };
    xhr.onload = () => {
      const bodyText = String(xhr.responseText || '');
      if (xhr.status < 200 || xhr.status >= 300) {
        reject(new Error(resolveHttpError(xhr.status, xhr.statusText, bodyText)));
        return;
      }
      try {
        const payload = JSON.parse(bodyText) as { url?: string | null; objectKey?: string | null };
        const url = String(payload.url || '').trim();
        if (!url) {
          reject(new Error('上传成功但未返回图片 URL'));
          return;
        }
        opts?.onProgress?.(totalBytes, totalBytes);
        resolve({ url, objectKey: String(payload.objectKey || '') });
      } catch {
        reject(new Error('上传成功但响应不是 JSON'));
      }
    };
    xhr.onerror = () => reject(new Error('上传失败：网络异常或服务不可达'));
    xhr.ontimeout = () => reject(new Error('上传超时，请稍后重试'));
    xhr.onabort = () => reject(new Error('上传已取消'));
    xhr.send(form);
  });
}

export type BusinessAgentMessage = {
  id: string;
  sessionId: string;
  role: 'user' | 'assistant' | 'tool' | string;
  content?: string | null;
  attachments?: Array<Record<string, unknown>>;
  planId?: string | null;
  runId?: string | null;
  requestId?: string | null;
  createdAt?: string;
};

export type BusinessAgentRouteEvidence = {
  intent?: string;
  targetAbility?: string;
  targetBusinessKey?: string;
  confidence?: number;
  threshold?: number;
  baseImageRole?: 'source_image' | 'previous_result' | 'selected_history_result' | string;
  parentRunId?: string | null;
  methodologyId?: string | null;
  methodologyVersion?: string | null;
  missingFields?: string[];
  routeReason?: string;
  rejectedAbilities?: Array<{ ability?: string; reason?: string }>;
  requiresClarification?: boolean;
  clarificationReasons?: string[];
};

export type BusinessAgentPlan = {
  id: string;
  sessionId: string;
  agentKey: string;
  status: string;
  intent: string;
  title?: string | null;
  summary?: string | null;
  editPlan?: Array<{ step?: string; reason?: string }>;
  toolName: string;
  toolPayload: Record<string, unknown>;
  estimatedCostLevel?: string | null;
  riskLevel?: string | null;
  confirmationRequired?: boolean;
  plannerModel?: string | null;
  plannerMode?: string | null;
  warnings?: string[];
  routeEvidence?: BusinessAgentRouteEvidence;
  workingMemory?: Record<string, unknown>;
  assetState?: Record<string, unknown>;
  methodology?: Record<string, unknown>;
  baseImageRole?: string | null;
  parentRunId?: string | null;
  errorCode?: string | null;
  errorMessage?: string | null;
};

export type BusinessAgentToolCall = {
  id: string;
  sessionId: string;
  planId: string;
  toolName: string;
  businessKey?: string | null;
  runId?: string | null;
  status: string;
  requestPayload?: Record<string, unknown> | null;
  responsePayload?: Record<string, unknown> | null;
  errorCode?: string | null;
  errorMessage?: string | null;
};

export type BusinessAgentSession = {
  id: string;
  agentKey: string;
  status: string;
  title?: string | null;
  imageUrl?: string | null;
  latestPlanId?: string | null;
  latestRunId?: string | null;
  traceId?: string | null;
  requestId?: string | null;
  context?: Record<string, unknown> | null;
  metadata?: Record<string, unknown> | null;
  messages?: BusinessAgentMessage[];
  plans?: BusinessAgentPlan[];
  toolCalls?: BusinessAgentToolCall[];
  latestPlan?: BusinessAgentPlan | null;
  latestToolCall?: BusinessAgentToolCall | null;
};

export type BusinessRunPollResult = {
  runId?: string;
  id?: string;
  businessKey?: string;
  status?: string;
  version?: string | null;
  imageUrls?: string[];
  image_urls?: string[];
  videoUrls?: string[];
  texts?: string[];
  error?: string | null;
  errorMessage?: string | null;
  error_message?: string | null;
  retryAfterSeconds?: number;
  result?: Record<string, unknown> | null;
};

export type ProductCommercializationRequest = {
  productImageUrl?: string;
  designImageUrl?: string;
  productFields?: Record<string, unknown>;
  extraPrompt?: string;
  outputLanguage?: 'en-US' | 'zh-CN' | 'bilingual';
  marketRegion?: 'US' | 'UK' | 'EU' | 'global';
  copyScenarios?: string[];
  visualSupportMode?: 'none' | 'recommendation' | 'generate';
  videoScenario?: 'product_showcase_short' | 'social_ad_short' | 'detail_explainer';
  durationSeconds?: number;
  targetDurationSeconds?: number;
  aspectRatio?: string;
  strategyProfile?: string;
  executorId?: string;
  pollTimeout?: number;
  requestId?: string;
  traceId?: string;
  source?: string;
};

export type ProductCommercializationResponse = {
  requestId: string;
  businessKey: string;
  version: string;
  status: string;
  generatedAt?: string;
  strategyProfile: string;
  outputLanguage: string;
  marketRegion: string;
  copyScenarios: string[];
  productCard: Record<string, unknown>;
  copyPackage: Record<string, unknown>;
  visualAssetPlan: Record<string, unknown>;
  videoPlan: Record<string, unknown>;
  review: Record<string, unknown>;
  execution: Record<string, unknown>;
  audit?: Record<string, unknown> | null;
  videoResult?: Record<string, unknown> | null;
};

export const evalApi = {
  me: () => request<{ raterId: string }>('/api/evals/me'),
  listWorkflowVersions: () => request<EvalWorkflowVersion[]>('/api/evals/workflow-versions?status=active&includeAuxiliary=true'),
  listResourceOptions: (params: { type: string; status?: string; q?: string }) => {
    const qs = new URLSearchParams();
    qs.set('type', params.type);
    if (params.status) qs.set('status', params.status);
    if (params.q) qs.set('q', params.q);
    return request<EvalResourceOptionsResponse>(`/api/evals/resources/options?${qs.toString()}`);
  },
  getWorkflowDocs: () =>
    request<{ markdown: string; generatedAt?: string; workflows?: WorkflowDoc[] }>('/api/evals/docs/workflows'),
  listBusinessQualitySamples: (params?: { businessKey?: string; status?: string; limit?: number }) => {
    const qs = new URLSearchParams();
    if (params?.businessKey) qs.set('business_key', params.businessKey);
    qs.set('status', params?.status || 'active');
    qs.set('limit', String(params?.limit ?? 200));
    return request<EvalBusinessQualitySampleListResponse>(`/api/evals/business/quality-samples?${qs.toString()}`);
  },
  createRun: (payload: {
    workflow_version_id: string;
    dataset_item_id?: string | null;
    input_oss_urls_json?: string[];
    parameters_json?: Record<string, unknown>;
  }) => request<EvalRun>('/api/evals/runs', { method: 'POST', body: JSON.stringify(payload) }),
  prepareTextFissionPrompt: (payload: {
    imageUrl: string;
    provider?: string;
    prompt?: string;
    source?: string;
    channel?: string;
    requestId?: string;
    traceId?: string;
    metadata?: Record<string, unknown>;
  }) =>
    request<{
      promptDraftId: string;
      status: string;
      imageUrl: string;
      editablePrompt: string;
      editablePromptCn?: string | null;
      editable_prompt?: string | null;
      editableNegativePrompt?: string | null;
      editableNegativePromptCn?: string | null;
      editable_negative_prompt?: string | null;
      textContent?: string | null;
      textItems?: Array<{ index?: number; text: string; role?: string; keep?: boolean; confidence?: number }>;
      routeDecision?: string | null;
      routeReason?: string | null;
      canUseText2Img?: boolean | null;
      textCount?: number | null;
      text_content?: string | null;
      promptProfile?: string | null;
      prompt_profile?: string | null;
      layoutCard?: unknown;
      layout_card?: unknown;
      paletteCard?: unknown;
      palette_card?: unknown;
      riskNotes?: unknown;
      risk_notes?: unknown;
      vlResult?: Record<string, unknown>;
      traceId?: string | null;
    }>('/api/evals/text-fission/prompts', {
      method: 'POST',
      body: JSON.stringify(payload),
    }, 90000),
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
        uploaded_count?: number;
        upload_failed_count?: number;
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
          uploadedCount: Number(item.uploaded_count || 0),
          uploadFailedCount: Number(item.upload_failed_count || 0),
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
        run_output_reviews_json?: Array<{
          id: string;
          run_item_id: string;
          output_index: number;
          verdict: string;
          reason?: string | null;
          note?: string | null;
          updated_by?: string | null;
          updated_at?: string | null;
        }> | null;
        run_error_message?: string | null;
        error_code?: string | null;
        error_message?: string | null;
      }>;
    }>(`/api/evals/batches/${encodeURIComponent(batchId)}/items?${qs.toString()}`, {}, BATCH_DETAIL_TIMEOUT_MS);
  },
  listBatchReviewGroups: (batchId: string, params?: { page?: number; page_size?: number }) => {
    const qs = new URLSearchParams();
    qs.set('page', String(Math.max(1, Number(params?.page || 1))));
    qs.set('page_size', String(Math.max(1, Number(params?.page_size || 20))));
    return request<{
      batch_id: string;
      page: number;
      page_size: number;
      total_groups: number;
      total_pages: number;
      review_progress: {
        page_size: number;
        current_page: number;
        completed_page: number;
        updated_at?: string | null;
      };
      items: Array<{
        asset_id: string;
        source_key: string;
        file_name: string;
        input_url?: string | null;
        group_status: 'has_output' | 'no_output' | 'failed' | string;
        run_total: number;
        completed: number;
        failed: number;
        waiting: number;
        outputs: Array<{
          run_item_id: string;
          run_id?: string | null;
          output_index: number;
          url: string;
          run_status?: string | null;
          review?: {
            id: string;
            run_item_id: string;
            output_index: number;
            verdict: string;
            reason?: string | null;
            note?: string | null;
            updated_by?: string | null;
            updated_at?: string | null;
          } | null;
        }>;
        last_error?: string | null;
      }>;
    }>(`/api/evals/batches/${encodeURIComponent(batchId)}/review-groups?${qs.toString()}`, {}, BATCH_DETAIL_TIMEOUT_MS);
  },
  saveBatchReviewProgress: (
    batchId: string,
    payload: { current_page: number; completed_page: number; page_size?: number },
  ) =>
    request<{
      batch_id: string;
      review_progress: {
        page_size: number;
        current_page: number;
        completed_page: number;
        updated_at?: string | null;
      };
    }>(`/api/evals/batches/${encodeURIComponent(batchId)}/review-progress`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  upsertBatchOutputReviews: (
    batchId: string,
    payload: {
      items: Array<{
        run_item_id: string;
        output_index: number;
        verdict: 'pending' | 'satisfied' | 'unsatisfied';
        reason?: string;
        note?: string;
      }>;
    },
  ) =>
    request<{ total: number; items: Array<{ id: string; run_item_id: string; output_index: number; verdict: string }> }>(
      `/api/evals/batches/${encodeURIComponent(batchId)}/reviews`,
      { method: 'POST', body: JSON.stringify(payload) },
    ),
  getRun: (runId: string) => request<EvalRun>(`/api/evals/runs/${runId}`),
  createAnnotation: (runId: string, payload: { rating: number; comment?: string }) =>
    request(`/api/evals/runs/${runId}/annotations`, { method: 'POST', body: JSON.stringify(payload) }),
  listAnnotations: (runId: string) => request(`/api/evals/runs/${runId}/annotations`),
  workflowMetrics: () =>
    request<{
      metrics: Record<
        string,
        {
          ratingCount: number;
          avgRating: number | null;
          runCount?: number;
          recentRunCount?: number;
          recentSuccessCount?: number;
          recentFailureCount?: number;
          recentRunningCount?: number;
          recentNoOutputCount?: number;
          recentOutputKindCounts?: Record<string, number>;
          recentHours?: number;
          lastRunStatus?: string | null;
          lastRunAt?: string | null;
          lastRunHasOutput?: boolean | null;
          lastRunOutputKind?: string | null;
          lastErrorCode?: string | null;
          lastErrorMessage?: string | null;
        }
      >;
      recentHours?: number;
    }>(`/api/evals/metrics/workflows`),
  listRunsWithLatestAnnotation: (params: { workflow_version_id?: string; status?: string; unrated?: boolean; limit?: number; offset?: number }) => {
    const qs = new URLSearchParams();
    if (params.workflow_version_id) qs.set('workflow_version_id', params.workflow_version_id);
    if (params.status) qs.set('status', params.status);
    if (params.unrated) qs.set('unrated', 'true');
    qs.set('limit', String(params.limit ?? 50));
    qs.set('offset', String(params.offset ?? 0));
    return request<{ total: number; items: any[] }>(`/api/evals/runs/with-latest-annotation?${qs.toString()}`);
  },
  uploadImage: async (file: File, opts?: { onProgress?: (loaded: number, total: number) => void; timeoutMs?: number }) => {
    try {
      // Keep a lightweight identity preflight so uploads remain attached to the same rater cookie.
      await ensureEvalRaterId();
    } catch (err) {
      throw new Error(`上传准备失败（身份）: ${String((err as any)?.message || err || '未知错误')}`);
    }
    try {
      return await uploadImageViaBackend(file, opts);
    } catch (err) {
      throw new Error(`上传失败: ${String((err as any)?.message || err || '未知错误')}`);
    }
  },
  createImageEditAgentSession: (payload: {
    imageUrl?: string;
    message?: string;
    title?: string;
    context?: Record<string, unknown>;
    metadata?: Record<string, unknown>;
    source?: string;
    channel?: string;
    requestId?: string;
    editSkill?: string;
    quality?: string;
    size?: string;
    outputFormat?: string;
    maskUrl?: string;
    referenceImages?: Array<Record<string, unknown>> | string[];
    selectionHints?: Array<Record<string, unknown>>;
  }) =>
    request<{ session: BusinessAgentSession; plan?: BusinessAgentPlan }>(
      '/api/business/image-edit-chat/sessions',
      { method: 'POST', body: JSON.stringify(payload) },
      90000,
    ),
  getImageEditAgentSession: (sessionId: string) =>
    request<{ session: BusinessAgentSession }>(
      `/api/business/image-edit-chat/sessions/${encodeURIComponent(sessionId)}`,
      {},
      30000,
    ),
  sendImageEditAgentMessage: (
    sessionId: string,
    payload: {
      message: string;
      imageUrl?: string;
      editSkill?: string;
      quality?: string;
      size?: string;
      outputFormat?: string;
      maskUrl?: string;
      referenceImages?: Array<Record<string, unknown>> | string[];
      selectionHints?: Array<Record<string, unknown>>;
      context?: Record<string, unknown>;
      metadata?: Record<string, unknown>;
      requestId?: string;
    },
  ) =>
    request<{ session: BusinessAgentSession; plan: BusinessAgentPlan }>(
      `/api/business/image-edit-chat/sessions/${encodeURIComponent(sessionId)}/messages`,
      { method: 'POST', body: JSON.stringify(payload) },
      90000,
    ),
  confirmImageEditAgentPlan: (sessionId: string, planId: string, payload?: { overrides?: Record<string, unknown>; requestId?: string }) =>
    request<{ session: BusinessAgentSession; plan: BusinessAgentPlan; toolCall: BusinessAgentToolCall; run: Record<string, unknown> }>(
      `/api/business/image-edit-chat/sessions/${encodeURIComponent(sessionId)}/confirm`,
      { method: 'POST', body: JSON.stringify({ ...(payload || {}), planId }) },
      30000,
    ),
  getBusinessRun: (runId: string) =>
    request<BusinessRunPollResult>(
      '/api/business/runs/get',
      { method: 'POST', body: JSON.stringify({ runId }) },
      30000,
    ),
  previewProductCommercialization: (payload: ProductCommercializationRequest) =>
    request<ProductCommercializationResponse>(
      '/api/business/product-commercialization/preview',
      { method: 'POST', body: JSON.stringify(payload) },
      90000,
    ),
  generateProductCommercializationVideo: (payload: ProductCommercializationRequest) =>
    request<ProductCommercializationResponse>(
      '/api/business/product-commercialization/video',
      { method: 'POST', body: JSON.stringify(payload) },
      240000,
    ),
  generateProductCommercializationComposedVideo: (payload: ProductCommercializationRequest) =>
    request<ProductCommercializationResponse>(
      '/api/business/product-commercialization/video-compose',
      { method: 'POST', body: JSON.stringify(payload) },
      900000,
    ),
  adminListWorkflowVersions: async (adminToken: string) =>
    request<EvalWorkflowVersion[]>(`/api/evals/admin/workflow-versions`, { headers: { 'X-Eval-Admin-Token': adminToken } }),
  adminGetOperationsHealth: async (adminToken: string) =>
    request<EvalOperationsHealth>(`/api/evals/admin/operations-health`, { headers: { 'X-Eval-Admin-Token': adminToken } }),
  adminGetComfyuiQueueSummary: async (adminToken: string) =>
    request<ComfyuiQueueSummary>(`/api/evals/admin/comfyui-queue-summary`, { headers: { 'X-Eval-Admin-Token': adminToken } }),
  adminUpdateWorkflowVersion: async (adminToken: string, id: string, payload: Partial<EvalWorkflowVersion>) =>
    request<EvalWorkflowVersion>(`/api/evals/admin/workflow-versions/${id}`, {
      method: 'PUT',
      headers: { 'X-Eval-Admin-Token': adminToken },
      body: JSON.stringify(payload),
    }),
};
