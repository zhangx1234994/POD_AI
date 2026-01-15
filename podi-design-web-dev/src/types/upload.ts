// 上传图片类型
export interface ImageItem {
  id: string;
  url?: string;          // 最终可访问的图片 URL
  file?: File;           // 原始 File 对象（仅本地上传时存在）
  preview?: string;      // 本地预览 URL（如 object URL）
  name?: string;         // 文件名
  size?: string;         // 文件大小（如 "2.3 MB"）
  source?: 'upload' | 'personal' | 'zebra' | 'hummingbird';
  width?: number;        // 图片宽度（px）
  height?: number;       // 图片高度（px）
  ossUrl?: string;       // OSS 存储地址
  isOversized?: boolean; // 是否超出尺寸限制
}
