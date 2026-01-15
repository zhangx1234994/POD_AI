import OSS from 'ali-oss';
import { mediaApi } from '../services/mediaApi';
import type { OssCredentialResponse, OssCredentials, UploadResult } from '../types/media';

type UploadContext = {
  userId?: string;
  action?: string;
  channel?: string;
};

const buildRandomId = () => {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return `ability-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`;
};

let cachedUploadKey: { token: string; expiresAt: number } | null = null;

const ensureUploadKey = async (userId?: string): Promise<string> => {
  const now = Date.now();
  if (cachedUploadKey && cachedUploadKey.expiresAt - now > 60 * 1000) {
    return cachedUploadKey.token;
  }
  const targetUser = userId && userId.trim() ? userId : 'admin';
  const response = await mediaApi.requestUploadKey({ userId: targetUser });
  cachedUploadKey = {
    token: response.uploadKey,
    expiresAt: Date.parse(response.expiresAt),
  };
  return response.uploadKey;
};

const createClient = (credentials: OssCredentials) => {
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
      (config as any).secure = true;
    }
  } else {
    (config as any).secure = true;
  }
  if (credentials.securityToken) {
    (config as any).stsToken = credentials.securityToken;
  }
  return new OSS(config);
};

const encodeObjectKey = (key: string) =>
  key
    .split('/')
    .map((segment) => encodeURIComponent(segment))
    .join('/');

const buildPublicUrl = (payload: OssCredentialResponse): string => {
  const domain = payload.ossCredentials.publicDomain?.trim() || payload.host;
  const encodedKey = encodeObjectKey(payload.objectKey);
  return `${domain.replace(/\/$/, '')}/${encodedKey}`;
};

export const uploadAbilityTestFile = async (file: File, context?: UploadContext): Promise<UploadResult> => {
  const uploadKey = await ensureUploadKey(context?.userId);
  const credentialPayload = await mediaApi.requestOssCredential({
    uploadKey,
    taskId: buildRandomId(),
    action: context?.action || 'ability-test',
    fileName: file.name,
    mimeType: file.type || 'application/octet-stream',
    fileSize: file.size,
    channel: context?.channel || 'admin-console',
  });
  const client = createClient(credentialPayload.ossCredentials);
  await client.put(credentialPayload.objectKey, file);
  const url = buildPublicUrl(credentialPayload);
  return {
    url,
    objectKey: credentialPayload.objectKey,
    name: file.name,
    size: file.size,
  };
};
