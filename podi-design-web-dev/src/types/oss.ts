/**
 * OSS 临时安全凭证（STS）
 */
export interface OssCredentials {
  accessKeyId: string;
  accessKeySecret: string;
  securityToken: string;
  endpoint: string;
  publicDomain: string;
  bucket: string;
  region: string;
  expiration: number;       // 时间戳（毫秒）
  isTemporary: boolean;     // 是否为临时凭证
  rootPrefix: string;
  // 注：'temporary' 字段冗余，可移除（与 isTemporary 重复）
}

/**
 * 获取 OSS 凭证的 API 响应结构
 */
export interface OssCredentialResponse {
  ossCredentials: OssCredentials;
  objectKey: string;
  host: string;
}

export interface UploadKeyResponse {
  uploadKey: string;
  expiresAt: string;
  expiresIn: number;
}

/**
 * 文件上传到 OSS 后的结果
 */
export interface UploadResult {
  url: string;    // 完整可访问的 OSS URL
  name: string;   // 原始文件名
  size: number;   // 文件大小（字节）
}
