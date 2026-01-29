import type { OssCredentialRequest, OssCredentialResponse, UploadKeyResponse } from '../types/media';
import { ADMIN_TOKEN_INVALID_EVENT, getAdminToken } from './adminApi';

const MEDIA_BASE = import.meta.env.VITE_MEDIA_BASE_URL ?? '/api/media';
const ACCESS_TOKEN_KEY = 'podi_admin_access_token';
const REFRESH_TOKEN_KEY = 'podi_admin_refresh_token';
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
  return resp.json();
}

export const mediaApi = {
  requestUploadKey: (payload: { userId: string }) =>
    mediaRequest<UploadKeyResponse>('/v1/upload-key', { method: 'POST', body: JSON.stringify(payload) }),
  requestOssCredential: (payload: OssCredentialRequest) =>
    mediaRequest<OssCredentialResponse>('/v1/sts', { method: 'POST', body: JSON.stringify(payload) }),
};
