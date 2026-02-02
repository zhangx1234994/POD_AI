import type { OssCredentialRequest, OssCredentialResponse, UploadKeyResponse } from '../types/media';
import { ADMIN_TOKEN_INVALID_EVENT, getAdminToken } from './adminApi';

const MEDIA_BASE = import.meta.env.VITE_MEDIA_BASE_URL ?? '/api/media';
const ACCESS_TOKEN_KEY = 'podi_admin_access_token';
const REFRESH_TOKEN_KEY = 'podi_admin_refresh_token';
const TOKEN_INVALID_FLAG = 'podi_admin_token_invalid';
const TOKEN_INVALID_AT_KEY = 'podi_admin_token_invalid_at';
const DEFAULT_TIMEOUT_MS = 15000;
const AUTH_INVALID_MESSAGE = '登录已失效，请重新登录';
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

function resolveHttpError(status: number, statusText: string, bodyText: string): string {
  const message = extractErrorMessage(statusText, bodyText);
  switch (status) {
    case 400:
      return message || '请求参数错误';
    case 401:
    case 403:
      return AUTH_INVALID_MESSAGE;
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

async function mediaRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getAdminToken();
  const { options: timedOptions, cancel } = withTimeout(options, DEFAULT_TIMEOUT_MS);
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  let resp: Response;
  try {
    resp = await fetch(`${MEDIA_BASE}${path}`, {
      ...timedOptions,
      headers,
    });
  } catch (err) {
    cancel();
    throw new Error(resolveNetworkError(err, '请求超时，请检查网络或服务是否可用'));
  }
  cancel();
  if (!resp.ok) {
    const text = await resp.text();
    const message = resolveHttpError(resp.status, resp.statusText, text);
    if (resp.status === 401 || resp.status === 403) {
      forceReLogin(message);
    }
    throw new Error(message);
  }
  return resp.json();
}

export const mediaApi = {
  requestUploadKey: (payload: { userId: string }) =>
    mediaRequest<UploadKeyResponse>('/v1/upload-key', { method: 'POST', body: JSON.stringify(payload) }),
  requestOssCredential: (payload: OssCredentialRequest) =>
    mediaRequest<OssCredentialResponse>('/v1/sts', { method: 'POST', body: JSON.stringify(payload) }),
};
