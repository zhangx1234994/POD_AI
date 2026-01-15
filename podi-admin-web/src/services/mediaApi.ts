import type { OssCredentialRequest, OssCredentialResponse, UploadKeyResponse } from '../types/media';
import { getAdminToken } from './adminApi';

const MEDIA_BASE = import.meta.env.VITE_MEDIA_BASE_URL ?? '/api/media';

async function mediaRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getAdminToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  const resp = await fetch(`${MEDIA_BASE}${path}`, {
    ...options,
    headers,
  });
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(text || resp.statusText);
  }
  return resp.json();
}

export const mediaApi = {
  requestUploadKey: (payload: { userId: string }) =>
    mediaRequest<UploadKeyResponse>('/v1/upload-key', { method: 'POST', body: JSON.stringify(payload) }),
  requestOssCredential: (payload: OssCredentialRequest) =>
    mediaRequest<OssCredentialResponse>('/v1/sts', { method: 'POST', body: JSON.stringify(payload) }),
};
