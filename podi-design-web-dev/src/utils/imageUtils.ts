/**
 * 图片工具集合
 *
 * 组织信息：
 * 图片元信息获取
 * 图片上传校验
 * - 现统一在出错时返回 { width: 0, height: 0 }。
 * - 类型安全：`image` 参数目前使用 `any` 以兼容现有数据结构，建议长期为上传图片定义 `UploadedImage` 类型。
 * - 性能：`getDimensionsFromFile` 会创建 ObjectURL，已用 try/finally 确保 `URL.revokeObjectURL` 始终被调用。
 */

import {
  IMAGE_MIME_TYPE_MAP,
  IMAGE_FILE_EXTENSIONS,
  IMAGE_UPLOAD_MAX_FILE_SIZE,
  IMAGE_UPLOAD_MAX_RESOLUTION,
} from '@/constants/upload';
import type { ImageItem } from '@/types/upload';

type ImageDimensions = { width: number; height: number };

// ======================
// 图片元信息获取
// ======================

/**
 * 内部：通过 img 元素加载图片并获取尺寸
 */
async function loadImage(src: string): Promise<ImageDimensions> {
  return new Promise((resolve) => {
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.onload = () => resolve({ width: img.naturalWidth || img.width, height: img.naturalHeight || img.height });
    img.onerror = () => resolve({ width: 0, height: 0 });
    img.src = src;
  });
}

/**
 * 从 File 对象获取图片尺寸
 * 注意：函数会创建 ObjectURL，内部使用 try/finally 确保 revoke
 */
export async function getDimensionsFromFile(file: File): Promise<ImageDimensions> {
  if (!file) return { width: 0, height: 0 };

  const objectUrl = URL.createObjectURL(file);
  try {
    const dims = await loadImage(objectUrl);
    return dims;
  } finally {
    URL.revokeObjectURL(objectUrl);
  }
}

/**
 * 从图片 URL 获取尺寸
 */
export async function getDimensionsFromUrl(url: string): Promise<ImageDimensions> {
  if (!url) return { width: 0, height: 0 };
  return loadImage(url);
}

/**
 * 从 base64 字符串获取图片尺寸
 */
export async function getDimensionsFromBase64(base64String: string): Promise<ImageDimensions> {
  const dataUrl = base64String.startsWith('data:') ? base64String : `data:image/png;base64,${base64String}`;
  return loadImage(dataUrl);
}

/**
 * 从 UploadedImage-like 对象获取尺寸（兼容旧结构）
 */
export async function getDimensionsFromUploadedImage(image: any): Promise<ImageDimensions> {
  if (!image) return { width: 0, height: 0 };
  if (typeof image.width === 'number' && typeof image.height === 'number') return { width: image.width, height: image.height };
  if (image.file) return getDimensionsFromFile(image.file);
  if (image.preview) return getDimensionsFromUrl(image.preview);
  return { width: 0, height: 0 };
}

/**
 * 将 File 对象转为 base64 字符串（不包含 data:* 前缀）
 */
export async function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      const base64 = result.includes(',') ? result.split(',')[1] : result;
      resolve(base64);
    };
    reader.onerror = (error) => reject(error);
    reader.readAsDataURL(file);
  });
}

/**
 * 从 OSS 获取图片信息（宽高 / 文件大小）
 */
export async function fetchOssImageInfo(imageUrl: string): Promise<{ width: number; height: number; fileSize: number } | null> {
  if (!imageUrl?.startsWith('http')) return null;
  try {
    const res = await fetch(`${imageUrl}?x-oss-process=image/info`);
    if (!res.ok) return null;
    const data = await res.json();

    const parse = (v: any) => (typeof v === 'number' ? v : typeof v === 'string' ? parseInt(v, 10) : v?.value ? parseInt(v.value, 10) : 0);

    const width = parse(data.ImageWidth);
    const height = parse(data.ImageHeight);
    const fileSize = parse(data.FileSize);
    return width > 0 && height > 0 && fileSize > 0 ? { width, height, fileSize } : null;
  } catch (err) {
    console.error('fetchOssImageInfo failed', err);
    return null;
  }
}

// ======================
// 图片元信息 & 文件大小
// ======================
/**
 * 格式化文件大小（字节 → 可读字符串）
 */
export function formatFileSize(bytes: number, decimals: number = 2): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(k)), sizes.length - 1);
  return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

// ======================
// 图片上传校验
// ======================

/**
 * 验证图片文件大小
 */
export function validateImageSize(file: File): { isValid: boolean; error?: string; size?: number; sizeText?: string } {
  if (!file) return { isValid: false, error: '文件不能为空' };
  const sizeText = (file.size / 1024 / 1024).toFixed(2) + ' MB';
  if (file.size > IMAGE_UPLOAD_MAX_FILE_SIZE) {
    return {
      isValid: false,
      error: `文件大小超过限制。最大允许 ${IMAGE_UPLOAD_MAX_FILE_SIZE / (1024 * 1024)}MB，请删除超出限制文件！`,
      size: file.size,
      sizeText,
    };
  }
  return { isValid: true, size: file.size, sizeText };
}

/**
 * 验证图片分辨率（会创建 ObjectURL 并 revoke）
 */
export function validateImageResolution(file: File): Promise<{ isValid: boolean; width?: number; height?: number; error?: string }> {
  return new Promise((resolve) => {
    if (!file) return resolve({ isValid: false, error: '文件不能为空' });
    const img = new Image();
    const objectUrl = URL.createObjectURL(file);
    img.onload = function () {
      const width = img.width || img.naturalWidth || 0;
      const height = img.height || img.naturalHeight || 0;
      URL.revokeObjectURL(objectUrl);
      if (width > IMAGE_UPLOAD_MAX_RESOLUTION.width || height > IMAGE_UPLOAD_MAX_RESOLUTION.height) {
        resolve({ isValid: false, width, height, error: `图片分辨率超过限制。最大允许 ${IMAGE_UPLOAD_MAX_RESOLUTION.width}x${IMAGE_UPLOAD_MAX_RESOLUTION.height}，当前图片分辨率 ${width}x${height}` });
      } else {
        resolve({ isValid: true, width, height });
      }
    };
    img.onerror = function () {
      URL.revokeObjectURL(objectUrl);
      resolve({ isValid: false, error: '无法读取图片分辨率，可能文件已损坏' });
    };
    img.src = objectUrl;
  });
}

/**
 * 根据文件名或MIME类型验证图片格式
 */
export function validateImageFormat(file: File): { isValid: boolean; format?: string; error?: string } {
  if (!file) return { isValid: false, error: '文件不能为空' };
  const fileType = file.type?.toLowerCase() || '';
  const fileName = file.name?.toLowerCase() || '';
  const isMimeTypeValid = Object.values(IMAGE_MIME_TYPE_MAP).includes(fileType as any);
  const hasValidExtension = IMAGE_FILE_EXTENSIONS.some((ext) => fileName.endsWith(ext));
  if (!isMimeTypeValid && !hasValidExtension) {
    return { isValid: false, error: `不支持的图片格式。支持的格式: ${IMAGE_FILE_EXTENSIONS.join(', ')}` };
  }
  let format = '';
  if (fileName.endsWith('.png') || fileType === 'image/png') format = 'PNG';
  else if (fileName.endsWith('.jpg') || fileName.endsWith('.jpeg') || fileType === 'image/jpeg') format = 'JPEG';
  else if (fileName.endsWith('.gif') || fileType === 'image/gif') format = 'GIF';
  else if (fileName.endsWith('.webp') || fileType === 'image/webp') format = 'WEBP';
  else if (fileName.endsWith('.bmp') || fileType === 'image/bmp') format = 'BMP';
  return { isValid: true, format };
}

/**
 * 综合验证图片（格式 / 大小 / 分辨率）
 */
export async function validateImage(file: File): Promise<{ isValid: boolean; format?: string; width?: number; height?: number; error?: string; size?: number; sizeText?: string; isOversized?: boolean }> {
  // 验证格式
  const formatValidation = validateImageFormat(file);
  if (!formatValidation.isValid) return formatValidation as any;

  // 验证大小
  const sizeValidation = validateImageSize(file);
  const isOversized = !sizeValidation.isValid && sizeValidation.error?.includes('文件大小超过限制');
  if (isOversized) {
    return {
      isValid: false,
      format: formatValidation.format,
      error: sizeValidation.error,
      size: sizeValidation.size,
      sizeText: sizeValidation.sizeText,
      isOversized: true,
    };
  }

  // 验证分辨率
  const resolutionValidation = await validateImageResolution(file);

  return {
    isValid: true,
    format: formatValidation.format,
    width: resolutionValidation.width,
    height: resolutionValidation.height,
    size: sizeValidation.size,
    sizeText: sizeValidation.sizeText,
    isOversized: false,
  };
}

/**
 * 检查文件是否为支持的图片格式
 */
export function isSupportedImage(file: File): boolean {
  return validateImageFormat(file).isValid;
}

/**
 * 填充图片数组中缺失的尺寸信息
 * - 在无法获取尺寸或发生错误时返回 { width: 0, height: 0 }
 */
export async function fillImageDimensions(imgs: ImageItem[]): Promise<ImageItem[]> {
  return Promise.all(
    imgs.map(async (img) => {
      if ((img as any).width && (img as any).height) return img;
      try {
        if ((img as any).file) {
          const d = await getDimensionsFromFile((img as any).file);
          return { ...img, width: d.width, height: d.height };
        }
        return { ...img, width: 0, height: 0 };
      } catch (e) {
        return { ...img, width: 0, height: 0 };
      }
    })
  );
}

/**
 * 根据尺寸键（如 '1:1', '1:2', '2:1', 'original', 'auto'）解析出具体的像素宽高
 * 会结合自定义值或首张图片的实际尺寸进行回退
 */
export function resolveImageSize(
  sizeKey: string,
  opts?: { customWidth?: number; customHeight?: number; firstImage?: ImageItem | null }
): { width?: number; height?: number } {
  const customWidth = opts?.customWidth;
  const customHeight = opts?.customHeight;
  const firstImage = opts?.firstImage;

  let width: number | undefined;
  let height: number | undefined;

  if (sizeKey === 'original' && firstImage && (firstImage as any).width && (firstImage as any).height) {
    width = (firstImage as any).width;
    height = (firstImage as any).height;
  } else if (sizeKey === 'auto') {
    width = customWidth ?? (firstImage ? (firstImage as any).width : undefined);
    height = customHeight ?? (firstImage ? (firstImage as any).height : undefined);
  } else if (sizeKey === '1:2') {
    width = 900;
    height = 1800;
  } else if (sizeKey === '1:1') {
    width = 2000;
    height = 2000;
  } else if (sizeKey === '2:1') {
    width = 1800;
    height = 900;
  }

  return { width, height };
}

// ======================
// 图片 URL 处理
// ======================
/**
 * 清洗图片 URL：移除控制字符、引号等非法字符
 */
export function cleanImageUrl(s: string): string {
  try {
    let u = String(s || '').trim();
    u = u.replace(/[`"'\u0000-\u001F]/g, '');
    u = u.trim();
    return u;
  } catch {
    return '';
  }
}

/**
 * 清洗并验证图片 URL，移除非法字符，确保可安全用于 img.src
 * 原始 URL 字符串，清洗后的 URL，当 URL 为空或无效时则抛出错误，以便调用方处理
 */
export async function sanitizeImageUrl(url: string): Promise<string> {
  const cleaned = cleanImageUrl(url);
  if (!cleaned) {
    throw new Error('无效的图片地址');
  }
  return cleaned;
}

/**
 * 从任意值（字符串/对象）中解析出图片 URL
 */
export function parseImageUrl(value: any): string {
  if (!value) return '';
  if (typeof value === 'string') {
    const s = value.trim();
    if (s.startsWith('{') && s.endsWith('}')) {
      try {
        const obj = JSON.parse(s);
        if (obj && typeof obj.ossUrl === 'string') {
          return cleanImageUrl(obj.ossUrl);
        }
      } catch {}
    }
    return cleanImageUrl(s);
  }
  if (typeof value === 'object') {
    if (typeof value.ossUrl === 'string') return cleanImageUrl(value.ossUrl);
    if (typeof value.url === 'string') return cleanImageUrl(value.url);
  }
  return '';
}

/**
 * 从 API 响应对象中提取预览图片 URL
 */
export function extractPreviewImageUrl(response: any): string {
  if (!response) return '';
  return (
    parseImageUrl(response.ossUrl) ||
    parseImageUrl(response.imgUrl) ||
    parseImageUrl(response.imageUrl) ||
    parseImageUrl(response.img_url) ||
    parseImageUrl(response.imgurl) ||
    ''
  );
}

/** 生成缩略图 URL（OSS 加速兼容） */
export const getThumbnailUrl = (url: string) => {
  if (!url) return '';
  if (url.includes('x-oss-process')) return url;
  const separator = url.includes('?') ? '&' : '?';
  return `${url}${separator}x-oss-process=image/resize,w_200,h_200,m_lfit`;
};

// ======================
// 图片文件名生成
// ======================
/**
 * 生成图片文件名（支持保留原名或使用时间戳）
 */
export function generateImageFilename(
  name?: string,
  index?: number,
  preserveOriginalName?: boolean
): string {
  const raw = String(name || 'image.png');
  const base = raw.split(/[\\/]/).pop() || 'image.png';

  if (preserveOriginalName) {
    const suffix = index !== undefined && index > 0 ? `-${index}` : '';
    const lastDot = base.lastIndexOf('.');
    if (lastDot > 0) {
      return `${base.substring(0, lastDot)}${suffix}${base.substring(lastDot)}`;
    }
    return `${base}${suffix}`;
  }

  const lastDot = base.lastIndexOf('.');
  const ext = lastDot > 0 ? base.substring(lastDot) : '.png';
  const suffix = index !== undefined && index > 0 ? `-${index}` : '';
  return `${Date.now()}${suffix}${ext}`;
}

// ======================
// 获取当前任务对应的（原图 + 结果图）
// ======================
/**
 * 在任务详情页面，点击任务卡片，需要展示当前任务对应的（原图 + 结果图），返回标准化的 OSS 地址和文件名列表
 */
export function getTaskPreviewImages(task: any): Array<{ ossUrl?: string; filename?: string }> {
  if (!task?.workflowParams) return [];
  const images: Array<{ ossUrl?: string; filename?: string }> = [];

  const pushFromCandidate = (img: any, defaultName?: string, index?: number) => {
    if (!img) return;
    if (typeof img === 'object') {
      const src = extractPreviewImageUrl(img);
      if (src) {
        images.push({ ossUrl: src, filename: img.filename || img.name || defaultName || '原图' });
      }
    } else if (typeof img === 'string') {
      const src = extractPreviewImageUrl({ img_url: img });
      if (src) {
        images.push({ ossUrl: src, filename: defaultName || `原图${index ?? ''}` });
      }
    }
  };

  if (Array.isArray(task.workflowParams.imageList)) {
    task.workflowParams.imageList.forEach((img: any) => pushFromCandidate(img, '原图'));
  }

  if (Array.isArray(task.workflowParams.aux_imageList)) {
    task.workflowParams.aux_imageList.forEach((img: any, idx: number) => pushFromCandidate(img, `辅助图${idx + 1}`, idx + 1));
  }

  return images;
}

export default {
  getDimensionsFromFile,
  getDimensionsFromUrl,
  getDimensionsFromBase64,
  getDimensionsFromUploadedImage,
  fetchOssImageInfo,
  formatFileSize,
  validateImageSize,
  validateImageResolution,
  validateImageFormat,
  validateImage,
  isSupportedImage,
  fillImageDimensions,
  resolveImageSize,
  cleanImageUrl,
  sanitizeImageUrl,
  parseImageUrl,
  extractPreviewImageUrl,
  getThumbnailUrl,
  generateImageFilename,
  getTaskPreviewImages,
};
