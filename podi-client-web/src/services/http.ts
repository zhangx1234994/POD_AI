const JSON_HEADERS = {
  'Content-Type': 'application/json',
};

export class HttpError extends Error {
  status: number;
  detail: unknown;

  constructor(message: string, status: number, detail: unknown) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

function getBaseUrl() {
  return import.meta.env.VITE_API_BASE_URL || '';
}

export async function requestJson<T>(path: string, options: RequestInit = {}, accessToken?: string): Promise<T> {
  const headers = new Headers(options.headers || {});
  if (!headers.has('Content-Type') && options.body) {
    Object.entries(JSON_HEADERS).forEach(([key, value]) => headers.set(key, value));
  }
  if (accessToken) {
    headers.set('Authorization', `Bearer ${accessToken}`);
  }

  const response = await fetch(`${getBaseUrl()}${path}`, {
    ...options,
    headers,
  });

  const contentType = response.headers.get('content-type') || '';
  const isJson = contentType.includes('application/json');
  const payload = isJson ? await response.json().catch(() => null) : await response.text().catch(() => null);

  if (!response.ok) {
    const detail =
      typeof payload === 'object' && payload !== null && 'detail' in payload
        ? (payload as { detail?: unknown }).detail
        : payload;
    throw new HttpError(typeof detail === 'string' ? detail : response.statusText, response.status, detail);
  }

  return payload as T;
}

