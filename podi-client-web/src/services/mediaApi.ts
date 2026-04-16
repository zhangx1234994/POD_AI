import type { OssCredentialRequest, OssCredentialResponse, UploadKeyResponse } from '../types/media';
import { requestJson } from './http';

const MEDIA_BASE = import.meta.env.VITE_MEDIA_BASE_URL ?? '/api/media';

export const mediaApi = {
  requestUploadKey(payload: { userId: string }) {
    return requestJson<UploadKeyResponse>(`${MEDIA_BASE}/v1/upload-key`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },
  requestOssCredential(payload: OssCredentialRequest) {
    return requestJson<OssCredentialResponse>(`${MEDIA_BASE}/v1/sts`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },
};

