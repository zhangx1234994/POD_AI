const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '';
const DEFAULT_TIMEOUT_MS = 15000;
const GATEWAY_ERROR_MESSAGE = '服务不可达或网关异常，请稍后再试';

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

function resolveAuthError(status: number, statusText: string, bodyText: string): string {
  const message = extractErrorMessage(statusText, bodyText);
  switch (status) {
    case 400:
      return message || '登录参数错误';
    case 401:
    case 403:
      return message || '账号或密码错误';
    case 404:
      return message || '登录接口不存在或已下线';
    case 408:
      return message || '登录超时，请稍后再试';
    case 409:
      return message || '账号状态异常，请联系管理员';
    case 413:
      return message || '请求体过大';
    case 422:
      return message || '登录参数校验失败';
    case 429:
      return message || '登录过于频繁，请稍后再试';
    case 502:
    case 503:
    case 504:
      return GATEWAY_ERROR_MESSAGE;
    default:
      if (status >= 500) return message || '服务异常，请稍后再试';
      return message || statusText || `登录失败 (status=${status})`;
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

export const adminAuthAPI = {
  login: async (username: string, password: string) => {
    const { options, cancel } = withTimeout(
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      },
      DEFAULT_TIMEOUT_MS,
    );
    let resp: Response;
    try {
      resp = await fetch(`${API_BASE}/api/auth/login`, options);
    } catch (err) {
      cancel();
      throw new Error(resolveNetworkError(err, '登录超时，请检查网络或服务是否可用'));
    }
    cancel();
    if (!resp.ok) {
      const text = await resp.text();
      throw new Error(resolveAuthError(resp.status, resp.statusText, text));
    }
    return resp.json();
  },
};
