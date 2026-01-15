// ========== 画廊（Gallery）相关常量 ==========

/** 画廊网格项之间的默认间距（单位：px） */
export const GALLERY_DEFAULT_GAP = 12;

// 画廊默认分页大小
export const GALLERY_DEFAULT_PAGE_SIZE = 20;

/** IntersectionObserver 的 rootMargin（用于提前触发预取） */
export const GALLERY_DEFAULT_ROOT_MARGIN = '1000px';

/** 是否默认启用预取功能 */
export const GALLERY_DEFAULT_PREFETCH_ENABLED = false;

/** 默认预取深度（例如预取下 N 页） */
export const GALLERY_DEFAULT_PREFETCH_DEPTH = 0;

/** 标签键（key）到中文显示名称的映射 */
export const GALLERY_TAG_KEY_TO_LABEL: Record<string, string> = {
  main_color: '主色',
  core_elements: '核心元素',
  style_keywords: '风格关键词',
  person_info: '人物信息',
  person_source: '人物出处',
};

/** 标签显示名称到键的反向映射（由 GALLERY_TAG_KEY_TO_LABEL 自动生成） */
export const GALLERY_TAG_LABEL_TO_KEY: Record<string, string> = Object.entries(GALLERY_TAG_KEY_TO_LABEL).reduce((acc, [key, value]) => {
  acc[value] = key;
  return acc;
}, {} as Record<string, string>);

/** 画廊标签的显示优先级顺序（从高到低） */
export const GALLERY_TAG_DISPLAY_PRIORITY = [
  'main_color',
  'core_elements',
  'style_keywords',
  'person_info',
  'person_source',
];

/** 画廊中每张图片的最小宽度（用于响应式计算列数，单位：px） */
export const GALLERY_IMAGE_MIN_WIDTH = 200;

/** 加载更多提示的持续时长（毫秒） */
export const LOAD_MORE_TOAST_DURATION_MS = 6000;

/** 第三方平台基础地址（用于推送图片等操作） */
export const PLATFORM_BASE_URL = 'http://73ui8di80odaitest3434.168196.xyz:65412';

export default {
  GALLERY_DEFAULT_GAP,
  GALLERY_DEFAULT_PAGE_SIZE,
  GALLERY_DEFAULT_ROOT_MARGIN,
  GALLERY_DEFAULT_PREFETCH_ENABLED,
  GALLERY_DEFAULT_PREFETCH_DEPTH,
  GALLERY_TAG_KEY_TO_LABEL,
  GALLERY_TAG_LABEL_TO_KEY,
  GALLERY_TAG_DISPLAY_PRIORITY,
  GALLERY_IMAGE_MIN_WIDTH,
  LOAD_MORE_TOAST_DURATION_MS,
  PLATFORM_BASE_URL,
};
