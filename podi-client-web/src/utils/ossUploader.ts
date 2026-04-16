import { mediaApi } from '../services/mediaApi';
import type { OssCredentialResponse, OssCredentials, UploadResult } from '../types/media';

const buildRandomId = () => {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return `client-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`;
};

let cachedUploadKey: { token: string; expiresAt: number } | null = null;
let pendingUploadKeyPromise: Promise<string> | null = null;

async function ensureUploadKey(userId: string): Promise<string> {
  const now = Date.now();
  if (cachedUploadKey && cachedUploadKey.expiresAt - now > 60_000) {
    return cachedUploadKey.token;
  }
  if (!pendingUploadKeyPromise) {
    pendingUploadKeyPromise = mediaApi
      .requestUploadKey({ userId })
      .then((response) => {
        cachedUploadKey = {
          token: response.uploadKey,
          expiresAt: Date.parse(response.expiresAt),
        };
        return response.uploadKey;
      })
      .finally(() => {
        pendingUploadKeyPromise = null;
      });
  }
  return pendingUploadKeyPromise;
}

async function createClient(credentials: OssCredentials) {
  const { default: OSS } = await import('ali-oss');
  const config: Record<string, string> = {
    region: credentials.region,
    accessKeyId: credentials.accessKeyId,
    accessKeySecret: credentials.accessKeySecret,
    bucket: credentials.bucket,
  };
  const endpoint = credentials.endpoint?.trim();
  if (endpoint) {
    const normalized = endpoint.startsWith('http') ? endpoint : `https://${endpoint}`;
    config.endpoint = normalized;
    if (normalized.startsWith('https://')) {
      (config as { secure?: boolean }).secure = true;
    }
  } else {
    (config as { secure?: boolean }).secure = true;
  }
  if (credentials.securityToken) {
    (config as { stsToken?: string }).stsToken = credentials.securityToken;
  }
  return new OSS(config);
}

function encodeObjectKey(key: string) {
  return key
    .split('/')
    .map((segment) => encodeURIComponent(segment))
    .join('/');
}

function buildPublicUrl(payload: OssCredentialResponse): string {
  const domain = payload.ossCredentials.publicDomain?.trim() || payload.host;
  return `${domain.replace(/\/$/, '')}/${encodeObjectKey(payload.objectKey)}`;
}

export async function uploadClientFile(file: File, userId: string, action: string): Promise<UploadResult> {
  const uploadKey = await ensureUploadKey(userId);
  const credentialPayload = await mediaApi.requestOssCredential({
    uploadKey,
    taskId: buildRandomId(),
    action,
    fileName: file.name,
    mimeType: file.type || 'application/octet-stream',
    fileSize: file.size,
    channel: 'client-web',
  });
  const client = await createClient(credentialPayload.ossCredentials);
  await client.put(credentialPayload.objectKey, file);
  return {
    url: buildPublicUrl(credentialPayload),
    objectKey: credentialPayload.objectKey,
    name: file.name,
    size: file.size,
  };
}
