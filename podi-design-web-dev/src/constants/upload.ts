// ========== 文件上传相关常量 ==========

/** 最大允许上传的图片数量 */
export const MAX_UPLOAD_IMAGE_COUNT = 50;

/** 支持的图片 MIME 类型映射（用于校验文件类型） */
export const IMAGE_MIME_TYPE_MAP = {
  PNG: 'image/png',
  JPEG: 'image/jpeg',
  JPG: 'image/jpeg',
  GIF: 'image/gif',
  WEBP: 'image/webp',
  BMP: 'image/bmp',
} as const;

/** 支持的图片文件扩展名（用于文件名后缀校验） */
export const IMAGE_FILE_EXTENSIONS = ['.png', '.jpg', '.jpeg', '.bmp'];

/** 图片上传的最大文件大小（单位：字节），默认 5MB */
export const IMAGE_UPLOAD_MAX_FILE_SIZE = 5 * 1024 * 1024; // 5MB

/** 图片上传的最大分辨率限制（用于宽高校验） */
export const IMAGE_UPLOAD_MAX_RESOLUTION = {
  width: 2048,
  height: 2048,
};

export default {
  MAX_UPLOAD_IMAGE_COUNT,
  IMAGE_MIME_TYPE_MAP,
  IMAGE_FILE_EXTENSIONS,
  IMAGE_UPLOAD_MAX_FILE_SIZE,
  IMAGE_UPLOAD_MAX_RESOLUTION,
};
