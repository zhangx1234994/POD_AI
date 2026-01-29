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
  if (status === 502 || status === 503 || status === 504) return GATEWAY_ERROR_MESSAGE;
  const message = extractErrorMessage(statusText, bodyText);
  if (status >= 500 && (!message || message === statusText)) return '服务异常，请稍后再试';
  if (message) return message;
  return statusText || `登录失败 (status=${status})`;
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
      if (err instanceof DOMException && err.name === 'AbortError') {
        throw new Error('登录超时，请检查网络或服务是否可用');
      }
      throw new Error(String((err as any)?.message || err || '网络请求失败'));
    }
    cancel();
    if (!resp.ok) {
      const text = await resp.text();
      throw new Error(resolveAuthError(resp.status, resp.statusText, text));
    }
    return resp.json();
  },
};
