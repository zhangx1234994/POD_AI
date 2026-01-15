// =====================
// OSS 内部工具函数
// =====================
import OSS from 'ali-oss';
import axios from 'axios';
import { OssCredentials, OssCredentialResponse, UploadKeyResponse, UploadResult } from '@/types/oss';
import { getToken, getUserId } from './http';

const mediaHttp = axios.create({
  baseURL: '/api/media',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

mediaHttp.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  const userId = getUserId();
  if (userId) {
    config.headers['X-User-Id'] = userId;
  }
  return config;
});

const buildRandomId = () => {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return `task-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
};

let cachedUploadKey: { token: string; expiresAt: number } | null = null;

const ensureUploadKey = async (userId?: string): Promise<string> => {
  const now = Date.now();
  if (cachedUploadKey && cachedUploadKey.expiresAt - now > 60 * 1000) {
    return cachedUploadKey.token;
  }
  const targetUser = userId && userId.trim() !== '' ? userId : getUserId() || 'anonymous';
  const response = await mediaHttp.post<UploadKeyResponse>('/v1/upload-key', { userId: targetUser });
  const data = response.data;
  cachedUploadKey = {
    token: data.uploadKey,
    expiresAt: Date.parse(data.expiresAt),
  };
  return data.uploadKey;
};

/**
 * 获取OSS临时凭证
 */
const fetchOssCredential = async (file: File, userId?: string): Promise<OssCredentialResponse> => {
  try {
    const uploadKey = await ensureUploadKey(userId);
    const response = await mediaHttp.post<OssCredentialResponse>('/v1/sts', {
      uploadKey,
      taskId: buildRandomId(),
      action: 'media-upload',
      fileName: file.name,
      mimeType: file.type,
      fileSize: file.size,
      channel: 'design-web',
    });
    const payload = response.data;
    if (!payload || !payload.ossCredentials) {
      throw new Error('OSS 凭证响应格式无效：响应数据为空');
    }
    return payload;
  } catch (error) {
    console.error('获取 OSS 临时凭证失败:', error);
    throw new Error('获取 OSS 凭证失败，请稍后重试');
  }
};

/**
 * 创建OSS客户端
 */
const createOssClient = (credentials: OssCredentials): any => {
  const config: any = {
    region: credentials.region,
    accessKeyId: credentials.accessKeyId,
    accessKeySecret: credentials.accessKeySecret,
    bucket: credentials.bucket,
    // 不设置endpoint，使用region自动构建
    // 设置签名版本为V4，提高安全性
    signatureVersion: 'v4',
  };
  if (credentials.securityToken) {
    config.stsToken = credentials.securityToken;
  }
  if (credentials.endpoint) {
    config.endpoint = credentials.endpoint;
  }
  return new OSS(config);
};

/**
 * 生成唯一 OSS 对象路径（非仅文件名）
 */
export const uploadFileToOss = async (file: File, userId?: string): Promise<UploadResult> => {
  try {
    const { ossCredentials: credentials, objectKey } = await fetchOssCredential(file, userId);
    const client = createOssClient(credentials);

    // 4. 上传文件并获取 SDK 返回结果（以便在没有 publicDomain 时回退）
    const result = await client.put(objectKey, file);

    // 5. 返回上传结果
    // 优先使用 credential.publicDomain；若不存在则回退到 credential.endpoint 或 SDK 返回的 result.url
    let ossUrl = '';
    try {
      if (credentials && typeof credentials.publicDomain === 'string' && credentials.publicDomain.trim() !== '') {
        const endpoint = credentials.publicDomain.replace(/\/$/, ''); // 移除末尾斜杠
        ossUrl = `${endpoint}/${objectKey}`;
      } else if (credentials && typeof credentials.endpoint === 'string' && credentials.endpoint.trim() !== '') {
        // endpoint 有时为 host（不含协议），若缺少协议则默认使用 https
        let ep = credentials.endpoint.trim();
        if (!/^https?:\/\//i.test(ep)) ep = `https://${ep}`;
        ep = ep.replace(/\/$/, '');
        ossUrl = `${ep}/${objectKey}`;
      } else if (result && (result as any).url) {
        ossUrl = (result as any).url;
      } else {
        // 最后回退为 objectName（相对路径，调用方应知悉）
        ossUrl = objectKey;
      }
    } catch (e) {
      // 避免因 undefined 字段导致的运行时错误，回退到 result.url 或 objectName
      if (result && (result as any).url) ossUrl = (result as any).url;
      else ossUrl = objectKey;
    }

    // 使用我们构建的URL，而不是ali-oss返回的result.url，因为result.url可能包含bucket名称
    return {
      url: ossUrl,
      name: file.name,
      size: file.size,
    };
  } catch (error) {
    console.error('上传文件到OSS失败:', error);
    throw new Error(`上传文件失败: ${error instanceof Error ? error.message : '未知错误'}`);
  }
};

/**
 * 批量上传文件到 OSS（串行，支持进度回调）
 */
export const uploadFilesToOss = async (
  files: File[],
  userId?: string,
  onProgress?: (completed: number, total: number, currentFile?: string) => void
): Promise<UploadResult[]> => {
  const results: UploadResult[] = [];

  for (let i = 0; i < files.length; i++) {
    const file = files[i];
    try {
      // 通知进度
      if (onProgress) {
        onProgress(i, files.length, file.name);
      }

      // 上传单个文件
      const result = await uploadFileToOss(file, userId);
      results.push(result);

      // 通知进度
      if (onProgress) {
        onProgress(i + 1, files.length, file.name);
      }
    } catch (error) {
      console.error(`上传文件 ${file.name} 失败:`, error);
      // 继续上传其他文件，但记录错误
      throw new Error(
        `上传文件 ${file.name} 失败: ${error instanceof Error ? error.message : '未知错误'}`
      );
    }
  }

  return results;
};

export default {
  uploadFileToOss,
  uploadFilesToOss,
};
