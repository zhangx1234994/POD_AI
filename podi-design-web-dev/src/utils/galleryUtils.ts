import { generateImageFilename, extractPreviewImageUrl } from '@/utils/imageUtils';
import { formatDateTime } from '@/utils/timeUtils';
import {
  GALLERY_DEFAULT_GAP,
  GALLERY_TAG_KEY_TO_LABEL,
  GALLERY_IMAGE_MIN_WIDTH,
} from '@/constants/gallery';

/** 根据容器宽度计算适合的列数 */
export function getGridColumns(width: number): number {
  if (width >= 1440) return 6; // 2xl
  if (width >= 1280) return 5; // xl
  if (width >= 1024) return 4; // lg
  if (width >= 768) return 3;  // md
  if (width >= 640) return 2;  // sm
  return 1;
};

/** 将后端图像任务数据映射为前端画廊图像数据结构 */
export async function mapToGalleryImage(t: any) {
  const src = extractPreviewImageUrl(t) || t.ossUrl || t.oss_url || '';
  if (!src) return null;
  const url = src;

  const uploadDateRaw = t.createTime || t.create_time || t.uploadTime || t.upload_time || Date.now();
  const uploadDate = formatDateTime(uploadDateRaw) ? formatDateTime(uploadDateRaw) : String(uploadDateRaw);

  const name = (t.img_name || t.imgName || t.ossKey || t.oss_key || generateImageFilename('图片.png', undefined, true)) as string;

  const tt = String(t.type || '').toUpperCase();
  const tSourceType = String(t.sourceType || t.source_type || '').toUpperCase();

  let sourceType: 'UPLOAD' | 'GENERATE';
  let mappedType: 'uploaded' | 'generated';
  if (tSourceType === 'GENERATE') {
    sourceType = 'GENERATE';
    mappedType = 'generated';
  } else if (tSourceType === 'UPLOAD') {
    sourceType = 'UPLOAD';
    mappedType = 'uploaded';
  } else {
    const isGenerateType = [
      'GENERATE',
      'GENERATED',
      'AI_GENERATE',
      'TOOL_GENERATE',
      'generate',
      'generated',
      'ai_generate',
      'tool_generate',
    ].includes(tt);
    if (isGenerateType) {
      sourceType = 'GENERATE';
      mappedType = 'generated';
    } else {
      sourceType = 'UPLOAD';
      mappedType = 'uploaded';
    }
  }

  const id = String(t.id ?? t.imgId ?? t.img_id ?? t.key ?? `${Date.now()}`);
  const imgId = String(t.imgId ?? t.img_id ?? t.ossKey ?? '');
  const sizeStr = String(t.size || t.fileSize || t.file_size || '');
  const dimensions = String(t.dimensions || t.size_desc || '');

  let tags: string[] = [];
  try {
    const tagField = t.tags || t.tag || t.img_tags || t.image_tags;
    if (tagField) {
      if (typeof tagField === 'string') {
        const parsed = JSON.parse(tagField || '{}');
        if (Array.isArray(parsed)) {
          tags = parsed;
        } else if (typeof parsed === 'object' && parsed !== null) {
          for (const [key, value] of Object.entries(parsed)) {
            if (value === null || value === undefined) continue;
            let displayValue = '';
            if (Array.isArray(value)) displayValue = value.join(', ');
            else if (typeof value === 'object') displayValue = Object.values(value).flat().join(', ');
            else displayValue = String(value);
            if (displayValue.trim() === '') continue;
            const tagName = GALLERY_TAG_KEY_TO_LABEL[key] || key;
            tags.push(`${tagName}：${displayValue}`);
          }
        }
      } else if (Array.isArray(tagField)) {
        tags = tagField;
      } else if (typeof tagField === 'object' && tagField !== null) {
        for (const [key, value] of Object.entries(tagField)) {
          if (value === null || value === undefined) continue;
          let displayValue = '';
          if (Array.isArray(value)) displayValue = value.join(', ');
          else if (typeof value === 'object') displayValue = Object.values(value).flat().join(', ');
          else displayValue = String(value);
          if (displayValue.trim() === '') continue;
          const tagName = GALLERY_TAG_KEY_TO_LABEL[key] || key;
          tags.push(`${tagName}：${displayValue}`);
        }
      }
    }
  } catch (e) {
    console.error('解析标签失败:', e);
    tags = [];
  }

  const aiTool = t.aiTool || t.ai_tool || t.toolName || '';
  const originalType = t.type || t.originalType || t.original_type || '';

  return {
    id,
    imgId,
    name,
    url,
    type: mappedType,
    sourceType,
    size: sizeStr,
    dimensions,
    uploadDate,
    tags,
    aiTool,
    originalType,
  };
};

/** 计算画廊的列数和每列宽度 */
export function computeColumnsAndWidth(containerWidth: number | undefined | null, gapPx: number = Number(String(GALLERY_DEFAULT_GAP).replace(/[^0-9]/g, '')) || 12, minItemWidth = GALLERY_IMAGE_MIN_WIDTH) {
  const w = typeof containerWidth === 'number' ? Math.max(0, containerWidth) : (typeof window !== 'undefined' ? window.innerWidth : 1200);
  const cols = getGridColumns(w);
  const totalGap = gapPx * Math.max(0, cols - 1);
  const columnWidth = Math.max(minItemWidth, Math.floor((w - totalGap) / Math.max(1, cols)));
  return { cols, columnWidth };
};

export default {
  getGridColumns,
  mapToGalleryImage,
  computeColumnsAndWidth,
};
