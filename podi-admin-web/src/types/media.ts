export interface UploadKeyResponse {
  uploadKey: string;
  expiresAt: string;
  expiresIn: number;
}

export interface UploadKeyRequest {
  userId: string;
}

export interface OssCredentialRequest {
  uploadKey: string;
  taskId: string;
  action: string;
  fileName: string;
  mimeType: string;
  fileSize: number;
  channel?: string | null;
}

export interface OssCredentials {
  accessKeyId: string;
  accessKeySecret: string;
  securityToken?: string | null;
  endpoint: string;
  publicDomain: string;
  bucket: string;
  region: string;
  expiration: number;
  isTemporary: boolean;
  rootPrefix: string;
}

export interface OssCredentialResponse {
  ossCredentials: OssCredentials;
  objectKey: string;
  host: string;
}

export interface UploadResult {
  url: string;
  objectKey: string;
  name: string;
  size: number;
}
