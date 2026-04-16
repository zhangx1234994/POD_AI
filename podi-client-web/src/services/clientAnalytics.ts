import packageJson from '../../package.json';

const STORAGE_KEY = 'podi-client-analytics-events';
const EVENT_NAME = 'podi-client-analytics';
const FLUSH_CURSOR_KEY = 'podi-client-analytics-flush-cursor';
const SESSION_ID_KEY = 'podi-client-analytics-session-id';
const ANALYTICS_PROTOCOL_VERSION = 'phase1.v1';

export type ClientAnalyticsContext = {
  app: 'podi-client-web';
  env: string;
  appVersion: string;
  sessionId: string;
  authenticated: boolean;
  userId: string | null;
  userRole: string | null;
  page: string | null;
  route: string | null;
};

export type ClientAnalyticsEvent = {
  id: string;
  name: string;
  at: string;
  payload?: Record<string, unknown>;
  context: ClientAnalyticsContext;
};

function createSessionId() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `session-${Date.now()}-${Math.round(Math.random() * 1_000_000)}`;
}

function readOrCreateSessionId() {
  try {
    const current = sessionStorage.getItem(SESSION_ID_KEY);
    if (current) return current;
    const created = createSessionId();
    sessionStorage.setItem(SESSION_ID_KEY, created);
    return created;
  } catch {
    return createSessionId();
  }
}

let analyticsContext: ClientAnalyticsContext = {
  app: 'podi-client-web',
  env: import.meta.env.VITE_APP_ENV || import.meta.env.MODE || 'development',
  appVersion: import.meta.env.VITE_APP_VERSION || packageJson.version,
  sessionId: readOrCreateSessionId(),
  authenticated: false,
  userId: null,
  userRole: null,
  page: null,
  route: typeof window !== 'undefined' ? `${window.location.pathname}${window.location.search}` : null,
};

function readEvents(): ClientAnalyticsEvent[] {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as ClientAnalyticsEvent[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function writeEvents(events: ClientAnalyticsEvent[]) {
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(events.slice(-100)));
}

function countByName(events: ClientAnalyticsEvent[], name: string, predicate?: (event: ClientAnalyticsEvent) => boolean) {
  return events.filter((event) => event.name === name && (!predicate || predicate(event))).length;
}

function hasSource(source: string) {
  return (event: ClientAnalyticsEvent) => event.payload?.source === source;
}

function humanizeEvent(event: ClientAnalyticsEvent) {
  const labelMap: Record<string, string> = {
    client_page_view: '页面进入',
    home_workflow_click: '首页工作流点击',
    home_scenario_click: '首页案例点击',
    home_final_cta_click: '首页主 CTA 点击',
    template_start_click: '模板带入',
    studio_workflow_click: 'Studio 工作流点击',
    studio_route_click: 'Studio 路径点击',
    workspace_submit_started: '任务发起',
    workspace_submit_succeeded: '同步任务成功',
    workspace_task_created: '异步任务创建',
    task_preview_opened: '结果预览打开',
    task_result_reopen: '回到工作台',
    task_retry_click: '任务重做',
    client_asset_saved: '素材沉淀',
    asset_continue_click: '从资产继续创作',
    wallet_low_balance_intercept: '低余额拦截',
    wallet_order_created: '创建充值单',
    wallet_order_paid: '充值完成',
  };
  return labelMap[event.name] || event.name;
}

export type ClientOperatingSummary = {
  metrics: Array<{
    id: string;
    label: string;
    value: string;
    note: string;
    status: 'idle' | 'active' | 'healthy';
  }>;
  recentEvents: Array<{
    id: string;
    label: string;
    note: string;
    at: string;
  }>;
};

export type ClientAnalyticsFlushResult = {
  status: 'disabled' | 'success' | 'failed';
  endpoint: string | null;
  sent: number;
  pending: number;
  message: string;
  statusCode?: number;
  failureCode?: string | null;
  retryable?: boolean;
};

export type ClientAnalyticsTransportConfig = {
  endpoint: string | null;
  project: string | null;
  protocolVersion: typeof ANALYTICS_PROTOCOL_VERSION;
  authHeader: string | null;
  hasAuthToken: boolean;
};

export type ClientAnalyticsPayload = {
  source: 'podi-client-web';
  protocolVersion: typeof ANALYTICS_PROTOCOL_VERSION;
  batchId: string;
  generatedAt: string;
  project: string | null;
  range: {
    fromEventId: string | null;
    toEventId: string | null;
    fromAt: string | null;
    toAt: string | null;
    eventCount: number;
  };
  context: ClientAnalyticsContext;
  summary: ClientOperatingSummary;
  events: ClientAnalyticsEvent[];
};

function readFlushCursor() {
  try {
    return sessionStorage.getItem(FLUSH_CURSOR_KEY);
  } catch {
    return null;
  }
}

function writeFlushCursor(cursor: string | null) {
  try {
    if (!cursor) {
      sessionStorage.removeItem(FLUSH_CURSOR_KEY);
      return;
    }
    sessionStorage.setItem(FLUSH_CURSOR_KEY, cursor);
  } catch {
    // ignore storage failure
  }
}

function getPendingEvents(events = readEvents()) {
  const cursor = readFlushCursor();
  if (!cursor) return events;
  return events.filter((event) => event.at > cursor);
}

function getCurrentRoute() {
  if (typeof window === 'undefined') return null;
  return `${window.location.pathname}${window.location.search}`;
}

function normalizePage(payload?: Record<string, unknown>) {
  return typeof payload?.page === 'string' ? payload.page : analyticsContext.page;
}

function buildEventContext(payload?: Record<string, unknown>) {
  const route = getCurrentRoute();
  const context = {
    ...analyticsContext,
    page: normalizePage(payload) || null,
    route,
  } satisfies ClientAnalyticsContext;
  analyticsContext = context;
  return context;
}

export function setClientAnalyticsAuthContext(user: { id: string; role: string } | null) {
  analyticsContext = {
    ...analyticsContext,
    authenticated: Boolean(user?.id),
    userId: user?.id || null,
    userRole: user?.role || null,
  };
}

export function trackClientEvent(name: string, payload?: Record<string, unknown>) {
  const context = buildEventContext(payload);
  const event: ClientAnalyticsEvent = {
    id: `${Date.now()}-${Math.round(Math.random() * 1_000_000)}`,
    name,
    at: new Date().toISOString(),
    payload,
    context,
  };
  const next = [...readEvents(), event];
  writeEvents(next);
  window.dispatchEvent(new CustomEvent(EVENT_NAME, { detail: event }));
}

export function listClientEvents() {
  return readEvents();
}

export function getClientAnalyticsEndpoint() {
  return getClientAnalyticsTransportConfig().endpoint;
}

export function getClientAnalyticsTransportConfig(): ClientAnalyticsTransportConfig {
  const endpoint = import.meta.env.VITE_CLIENT_ANALYTICS_ENDPOINT;
  const project = import.meta.env.VITE_CLIENT_ANALYTICS_PROJECT;
  const authHeader = import.meta.env.VITE_CLIENT_ANALYTICS_AUTH_HEADER;
  const authToken = import.meta.env.VITE_CLIENT_ANALYTICS_AUTH_TOKEN;
  return {
    endpoint: typeof endpoint === 'string' && endpoint.trim() ? endpoint.trim() : null,
    project: typeof project === 'string' && project.trim() ? project.trim() : null,
    protocolVersion: ANALYTICS_PROTOCOL_VERSION,
    authHeader: typeof authHeader === 'string' && authHeader.trim() ? authHeader.trim() : 'Authorization',
    hasAuthToken: typeof authToken === 'string' && Boolean(authToken.trim()),
  };
}

export function subscribeClientEvents(listener: () => void) {
  window.addEventListener(EVENT_NAME, listener);
  return () => window.removeEventListener(EVENT_NAME, listener);
}

export function exportClientEventsJson(events = readEvents()) {
  return JSON.stringify(
    {
      source: 'podi-client-web',
      protocolVersion: ANALYTICS_PROTOCOL_VERSION,
      generatedAt: new Date().toISOString(),
      project: getClientAnalyticsTransportConfig().project,
      context: analyticsContext,
      range: buildEventRange(events),
      summary: summarizeClientOperations(events),
      events,
    },
    null,
    2,
  );
}

export function buildClientAnalyticsPayload(events = getPendingEvents()): ClientAnalyticsPayload {
  const transport = getClientAnalyticsTransportConfig();
  return {
    source: 'podi-client-web',
    protocolVersion: ANALYTICS_PROTOCOL_VERSION,
    batchId: buildBatchId(events),
    generatedAt: new Date().toISOString(),
    project: transport.project,
    range: buildEventRange(events),
    context: analyticsContext,
    summary: summarizeClientOperations(readEvents()),
    events,
  };
}

export async function flushClientEvents() {
  const transport = getClientAnalyticsTransportConfig();
  const endpoint = transport.endpoint;
  const pendingEvents = getPendingEvents();
  if (!endpoint) {
    return {
      status: 'disabled',
      endpoint: null,
      sent: 0,
      pending: pendingEvents.length,
      message: '未配置统计出口，当前只保留本地事件。',
      retryable: false,
    } satisfies ClientAnalyticsFlushResult;
  }

  if (!pendingEvents.length) {
    return {
      status: 'success',
      endpoint,
      sent: 0,
      pending: 0,
      message: '没有待上报的新事件。',
      retryable: false,
    } satisfies ClientAnalyticsFlushResult;
  }

  const payload = buildClientAnalyticsPayload(pendingEvents);
  try {
    const headers = buildAnalyticsHeaders(transport);
    const response = await window.fetch(endpoint, {
      method: 'POST',
      headers,
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      const errorDetail = await parseAnalyticsErrorResponse(response);
      return {
        status: 'failed',
        endpoint,
        sent: 0,
        pending: pendingEvents.length,
        message: errorDetail.message,
        statusCode: response.status,
        failureCode: errorDetail.code,
        retryable: errorDetail.retryable,
      } satisfies ClientAnalyticsFlushResult;
    }
    writeFlushCursor(pendingEvents[pendingEvents.length - 1]?.at || null);
    return {
      status: 'success',
      endpoint,
      sent: pendingEvents.length,
      pending: 0,
      message: `已上报 ${pendingEvents.length} 条事件。`,
      retryable: false,
    } satisfies ClientAnalyticsFlushResult;
  } catch (error) {
    return {
      status: 'failed',
      endpoint,
      sent: 0,
      pending: pendingEvents.length,
      message: error instanceof Error ? error.message : '统计出口上报失败',
      retryable: true,
    } satisfies ClientAnalyticsFlushResult;
  }
}

export function summarizeClientOperations(events = readEvents()): ClientOperatingSummary {
  const taskStarts = countByName(events, 'workspace_submit_started');
  const resultViews = countByName(events, 'task_preview_opened') + countByName(events, 'task_result_reopen');
  const repeatStarts = Math.max(0, taskStarts - 1);
  const resultAssets = countByName(events, 'client_asset_saved', (event) => event.payload?.origin === 'result');
  const lowBalanceIntercepts = countByName(events, 'wallet_low_balance_intercept');
  const lowBalanceOrders = countByName(events, 'wallet_order_created', (event) => Boolean(event.payload?.returnTo));
  const homeActivationClicks =
    countByName(events, 'home_workflow_click') +
    countByName(events, 'home_scenario_click') +
    countByName(events, 'home_final_cta_click') +
    countByName(events, 'template_start_click', hasSource('home'));

  const metrics: ClientOperatingSummary['metrics'] = [
    {
      id: 'activation',
      label: '首任务发起',
      value: taskStarts ? `${taskStarts} 次` : '待触发',
      note: homeActivationClicks ? `首页已产生 ${homeActivationClicks} 次激活入口点击。` : '先从首页或 Studio 触发第一条工作流。',
      status: taskStarts ? 'healthy' : homeActivationClicks ? 'active' : 'idle',
    },
    {
      id: 'review',
      label: '结果回看',
      value: resultViews ? `${resultViews} 次` : '待回看',
      note: taskStarts ? '目标是让首个成功结果能立即回到任务中心或工作台。' : '先触发首任务，再验证结果回看链路。',
      status: resultViews ? 'healthy' : taskStarts ? 'active' : 'idle',
    },
    {
      id: 'repeat',
      label: '二次任务发起',
      value: repeatStarts ? `${repeatStarts} 次` : '待二次使用',
      note: '判断用户有没有从一次试用进入持续使用。',
      status: repeatStarts ? 'healthy' : taskStarts ? 'active' : 'idle',
    },
    {
      id: 'assets',
      label: '结果沉淀',
      value: resultAssets ? `${resultAssets} 条` : '待沉淀',
      note: '结果进入资产中心后，后续复跑和继续创作才有基础。',
      status: resultAssets ? 'healthy' : taskStarts ? 'active' : 'idle',
    },
    {
      id: 'wallet',
      label: '低余额转化',
      value: lowBalanceIntercepts ? `${lowBalanceOrders}/${lowBalanceIntercepts}` : '未触发',
      note: lowBalanceIntercepts ? '看低余额拦截后，是否真实创建了充值单。' : '当前还没有出现低余额拦截场景。',
      status: lowBalanceOrders ? 'healthy' : lowBalanceIntercepts ? 'active' : 'idle',
    },
  ];

  const recentEvents = events
    .slice(-6)
    .reverse()
    .map((event, index) => ({
      id: `${event.at}-${index}`,
      label: humanizeEvent(event),
      note:
        typeof event.payload?.path === 'string'
          ? event.payload.path
          : typeof event.payload?.templateId === 'string'
            ? `模板 ${event.payload.templateId}`
            : typeof event.payload?.taskId === 'string'
              ? `任务 ${event.payload.taskId}`
              : typeof event.payload?.title === 'string'
                ? String(event.payload.title)
                : '客户端埋点事件',
      at: new Date(event.at).toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' }),
    }));

  return { metrics, recentEvents };
}

function buildBatchId(events: ClientAnalyticsEvent[]) {
  const first = events[0];
  const last = events[events.length - 1];
  return [
    'batch',
    analyticsContext.sessionId,
    first?.id || 'empty',
    last?.id || 'empty',
    Date.now(),
  ].join('-');
}

function buildEventRange(events: ClientAnalyticsEvent[]) {
  const first = events[0];
  const last = events[events.length - 1];
  return {
    fromEventId: first?.id || null,
    toEventId: last?.id || null,
    fromAt: first?.at || null,
    toAt: last?.at || null,
    eventCount: events.length,
  };
}

function buildAnalyticsHeaders(transport: ClientAnalyticsTransportConfig) {
  const headers = new Headers({
    'Content-Type': 'application/json',
    'X-Podi-Client-Source': 'podi-client-web',
    'X-Podi-Protocol-Version': transport.protocolVersion,
  });

  if (transport.project) {
    headers.set('X-Podi-Analytics-Project', transport.project);
  }

  const rawToken = import.meta.env.VITE_CLIENT_ANALYTICS_AUTH_TOKEN;
  if (typeof rawToken === 'string' && rawToken.trim()) {
    const normalized = transport.authHeader === 'Authorization' && !/^Bearer\s+/i.test(rawToken.trim())
      ? `Bearer ${rawToken.trim()}`
      : rawToken.trim();
    headers.set(transport.authHeader || 'Authorization', normalized);
  }

  return headers;
}

async function parseAnalyticsErrorResponse(response: Response) {
  const contentType = response.headers.get('content-type') || '';
  const isJson = contentType.includes('application/json');
  const payload = isJson
    ? await response.json().catch(() => null)
    : await response.text().catch(() => null);

  let message = `统计出口返回 ${response.status}`;
  let code: string | null = null;
  let retryable = response.status >= 500;

  if (typeof payload === 'string' && payload.trim()) {
    message = `${message}：${payload.trim()}`;
  } else if (payload && typeof payload === 'object') {
    const record = payload as Record<string, unknown>;
    const detail = typeof record.detail === 'string'
      ? record.detail
      : typeof record.message === 'string'
        ? record.message
        : null;
    if (detail) {
      message = `${message}：${detail}`;
    }
    code = typeof record.code === 'string' ? record.code : null;
    if (typeof record.retryable === 'boolean') {
      retryable = record.retryable;
    }
  }

  return {
    message,
    code,
    retryable,
  };
}
