import { useEffect, useMemo, useRef, useState } from 'react';
import { Alert, Button, Input, Select, Space, Tag, Textarea, Typography, MessagePlugin } from 'tdesign-react';
import { evalApi } from '../../api';
import type { BusinessRunPollResult, ProductCommercializationRequest, ProductCommercializationResponse } from '../../api';

type ProductCommercializationMode = 'copy' | 'video';
type WorkStatus = 'idle' | 'previewing' | 'keyframes' | 'video' | 'uploading' | 'visual';
type VideoProvider = 'kie_veo3_fast' | 'vidu_viduq3_turbo';
type ProductCommercializationStage = 'asset' | 'facts' | 'strategy' | 'review' | 'deliver';
type ProductImageInput = NonNullable<ProductCommercializationRequest['productImages']>[number];
type VideoPlanningFieldSource = 'auto' | 'manual' | 'default';
type VideoPlanningField = {
  id: string;
  label: string;
  description: string;
  value: string;
  removable?: boolean;
  source?: VideoPlanningFieldSource;
  sourceLabel?: string;
};
type VideoPlanningSuggestion = {
  value: string;
  sourceLabel: string;
};

const MODE_COPY: ProductCommercializationMode = 'copy';
const MODE_VIDEO: ProductCommercializationMode = 'video';
const KIE_EXECUTOR_ID = 'executor_kie_market_default';
const VIDU_EXECUTOR_ID = 'executor_vidu_default';
const SEGMENT_SECONDS = 8;

const VIDEO_MODEL_PROFILES: Record<
  VideoProvider,
  {
    label: string;
    executorId: string;
    segmentDurationOptions: number[];
    defaultSegmentSeconds: number;
    modes: Array<{ label: string; status: 'executable' | 'planned'; desc: string }>;
  }
> = {
  vidu_viduq3_turbo: {
    label: 'Vidu · viduq3-turbo',
    executorId: VIDU_EXECUTOR_ID,
    segmentDurationOptions: [3, 5, 8],
    defaultSegmentSeconds: 5,
    modes: [
      { label: '单参考图生视频', status: 'executable', desc: '直接用产品图生成单段或多段片段。' },
      { label: '关键帧控制', status: 'executable', desc: '先生成并确认关键帧/首尾帧，再调用对应视频接口。' },
    ],
  },
  kie_veo3_fast: {
    label: 'KIE · Veo3.1 Fast',
    executorId: KIE_EXECUTOR_ID,
    segmentDurationOptions: [8],
    defaultSegmentSeconds: 8,
    modes: [
      { label: '单参考图生视频', status: 'executable', desc: '当前稳定执行入口。' },
      { label: '关键帧控制', status: 'executable', desc: '先生成并确认关键帧/首尾帧，再调用对应视频接口。' },
    ],
  },
};

const DEFAULT_VIDEO_PLANNING_FIELDS: VideoPlanningField[] = [
  {
    id: 'core_message',
    label: '核心信息',
    description: '这个视频最需要让用户记住什么',
    value: '',
  },
  {
    id: 'target_audience',
    label: '目标人群',
    description: '给谁看，例如礼品买家、通勤人群、家居用户',
    value: '',
  },
  {
    id: 'usage_scene',
    label: '使用场景',
    description: '希望出现的生活、货架、详情页或广告场景',
    value: '',
  },
  {
    id: 'shot_preference',
    label: '镜头偏好',
    description: '希望强调的镜头，例如转圈、推进、材质特写',
    value: '',
  },
  {
    id: 'avoid',
    label: '禁止内容',
    description: '不要出现的元素，例如文字、水印、夸张承诺、变形',
    value: '不要出现文字、水印、Logo、价格标签，不要改变商品形状和图案。',
    source: 'default',
    sourceLabel: '系统默认商品保护约束',
  },
];

const DEFAULT_PRODUCT_FIELDS = {
  模板名称: '女款长袜（3D打印）',
  模板编号: 'F101P102C8M1535I1535',
  模板号: '1535',
  主体编码: '1535',
  产品型号: 'GZ-1535',
  英文名称: "Women's knitted woolen socks",
  产品重量: '110g',
  一级分类: '饰品/配件',
  二级分类: '穿搭配件',
  所属工厂: '101',
  生产工艺: '3D印花',
  产品材质: '包纱、涤纶、尼龙、橡筋',
  具体成分: '65%涤纶，15%氨纶，20%尼龙',
  建议售价: '10',
  包装尺寸: '20*13.6*3.8cm',
  包装尺寸In: '7.87*5.35*1.5in',
  包装体积: '1033.6cm³',
  含包装重量: '100g',
  是否外采: '不支持',
  是否独品: '否',
  是否48小时发货: '否',
  特殊码: '是',
  特殊发货: '是',
  关键词: ['custom socks', 'POD socks', '3D print socks', 'gift socks'],
  其他描述: '产品设计完成后用于海外电商上架、广告短文案和视频素材规划。',
};

const COPY_SCENARIOS = [
  { key: 'listing_title', label: '上架标题', desc: 'Marketplace title' },
  { key: 'bullet_points', label: '五点描述', desc: 'Selling bullets' },
  { key: 'detail_description', label: '详情页文案', desc: 'Detail page' },
  { key: 'ad_short_copy', label: '广告短文案', desc: 'Ad copy' },
  { key: 'keyword_pack', label: '关键词包', desc: 'SEO keywords' },
];

const COMMERCE_PLATFORM_OPTIONS = [
  { label: 'Amazon / marketplace', value: 'amazon_marketplace' },
  { label: 'Shopify 独立站', value: 'shopify_independent_site' },
  { label: 'Etsy 手作礼品', value: 'etsy_gift' },
  { label: 'TikTok Shop / 社媒', value: 'tiktok_shop_social' },
  { label: '通用海外电商', value: 'global_marketplace' },
];

const COPY_TONE_OPTIONS = [
  { label: '自然专业', value: 'natural_professional' },
  { label: '温暖礼品', value: 'warm_gift' },
  { label: '高级质感', value: 'premium' },
  { label: '活泼社媒', value: 'playful_social' },
  { label: '简洁转化', value: 'concise_conversion' },
];

const SELLING_ANGLE_OPTIONS = [
  { label: '日常实用', value: 'everyday_utility' },
  { label: '礼品场景', value: 'giftable_moment' },
  { label: '材质舒适', value: 'material_comfort' },
  { label: '图案设计', value: 'pattern_design' },
  { label: '季节上新', value: 'seasonal_collection' },
];

const VIDEO_SCENARIOS = [
  { key: 'product_showcase_short', label: '商品展示短视频', desc: '展示主体、材质和轮廓' },
  { key: 'social_ad_short', label: '社媒广告短视频', desc: '开头更吸睛，节奏更快' },
  { key: 'detail_explainer', label: '详情讲解短视频', desc: '偏详情页和卖点解释' },
];

const PENDING_VIDEO_ROUTES = [
  'Vidu 一键营销成片 Agent',
  'Vidu 视频复刻 Agent',
  'Vidu Ad · viduq3-ad / reference2video',
];

const VISUAL_SCENES = [
  {
    id: 'listing-main',
    label: '商品主视觉',
    desc: '适合详情页头图或平台主图候选',
    scene: 'ecommerce',
  },
  {
    id: 'social-ad-cover',
    label: '社媒广告封面',
    desc: '适合搭配广告短文案',
    scene: 'lifestyle',
  },
  {
    id: 'detail-closeup',
    label: '材质细节图',
    desc: '突出材质、印花和商品结构',
    scene: 'print_mockup',
  },
] as const;

type VisualScene = (typeof VISUAL_SCENES)[number];

const COMMERCIALIZATION_STAGES: Array<{
  key: ProductCommercializationStage;
  label: string;
  copyLabel: string;
  videoLabel: string;
  desc: string;
}> = [
  {
    key: 'asset',
    label: '素材',
    copyLabel: '上传产品图',
    videoLabel: '上传产品图',
    desc: '锁定唯一视觉事实源',
  },
  {
    key: 'facts',
    label: '核对',
    copyLabel: '确认商品事实',
    videoLabel: '确认商品事实',
    desc: 'JSON 可选，产品图优先',
  },
  {
    key: 'strategy',
    label: '方案',
    copyLabel: '设置文案策略',
    videoLabel: '设置视频策略',
    desc: '选择场景、供应商、时长和要求',
  },
  {
    key: 'review',
    label: '确认',
    copyLabel: '审核内容包',
    videoLabel: '确认脚本分镜',
    desc: '人工确认后再触发成本动作',
  },
  {
    key: 'deliver',
    label: '交付',
    copyLabel: '配图与下载',
    videoLabel: '素材包结果',
    desc: '查看 runId、OSS 与交付资产',
  },
];

const COPY_OUTPUT_LABELS: Record<string, string> = {
  listingTitle: '上架标题',
  bulletPoints: '五点描述',
  detailDescription: '详情页文案',
  adShortCopy: '广告短文案',
  keywordPack: '关键词包',
};

type GeneratedVisual = {
  id: string;
  label: string;
  runId: string;
  status: string;
  elapsedSeconds: number;
  urls: string[];
  error?: string;
};

const MODE_META: Record<
  ProductCommercializationMode,
  {
    title: string;
    subtitle: string;
    inputHint: string;
    outputHint: string;
    emptyText: string;
    previewButton: string;
    usageSteps: string[];
    interfaceNotes: Array<{ label: string; value: string }>;
    tags: Array<{ label: string; theme: 'primary' | 'success' | 'warning' }>;
  }
> = {
  copy: {
    title: '产品文案内容包',
    subtitle: '产品设计完成后，用大模型/VL 生成海外上架、详情页、广告和关键词内容。',
    inputHint: '产品图是事实锚点；字段只是可选补充，平台、语气、人群和卖点决定文案风格。',
    outputHint: '必须看到模型生成证据；模板兜底只能排障，不能作为验收通过。',
    emptyText: '先生成一次大模型文案包，再按需要显式生成配图。',
    previewButton: '生成文案内容包',
    usageSteps: ['上传产品图或填写图片 URL', '可选补充产品字段并选择平台/语气', '生成文案包，确认后再按需生成配图'],
    interfaceNotes: [
      { label: '预览接口', value: 'POST /api/business/product-commercialization/preview' },
      { label: '配图执行', value: 'POST /api/business/product-commercialization/runs · action=visual_generate · 默认 GPT Image 2' },
      { label: '查询结果', value: 'POST /api/business/runs/get · runId' },
    ],
    tags: [
      { label: 'LLM / VL', theme: 'primary' },
      { label: '电商文案', theme: 'success' },
      { label: 'GPT Image 2 配图', theme: 'warning' },
    ],
  },
  video: {
    title: '产品视频素材包',
    subtitle: '产品设计完成后，先用产品图和可选字段规划脚本分镜，再确认关键帧/首尾帧，最后生成分段视频素材。',
    inputHint: '产品图是必填素材；字段只是可选补充，用于约束脚本和镜头。',
    outputHint: '预览只生成脚本和分镜；关键帧/首尾帧和视频素材都必须显式触发成本动作，用户目标时长由规划器按模型能力拆段。',
    emptyText: '先生成视频规划，确认脚本分镜和关键帧/首尾帧，再生成视频素材包。',
    previewButton: '生成素材包规划',
    usageSteps: ['上传产品图或填写图片 URL', '可选补充产品字段，选择供应商/场景/时长', '生成脚本分镜，再生成并确认关键帧/首尾帧', '确认后提交分段视频素材任务'],
    interfaceNotes: [
      { label: '规划接口', value: 'POST /api/business/promo-video/plan' },
      { label: '关键帧执行', value: 'POST /api/business/promo-video/keyframes/runs' },
      { label: '视频素材执行', value: 'POST /api/business/promo-video/runs' },
      { label: '可选合成', value: 'POST /api/business/promo-video/compose/runs' },
      { label: '查询结果', value: 'POST /api/business/runs/get · runId' },
    ],
    tags: [
      { label: '视频素材包', theme: 'primary' },
      { label: 'KIE / Vidu', theme: 'success' },
      { label: 'OSS 回填', theme: 'warning' },
    ],
  },
};

function prettyJson(value: unknown): string {
  return JSON.stringify(value ?? {}, null, 2);
}

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function delay(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function firstText(data: Record<string, unknown>, keys: string[]): string {
  for (const key of keys) {
    const value = data[key];
    if (Array.isArray(value)) {
      const text = value.map((item) => String(item || '').trim()).filter(Boolean).join(', ');
      if (text) return text;
      continue;
    }
    if (value && typeof value === 'object') {
      const text = JSON.stringify(value);
      if (text && text !== '{}') return text;
      continue;
    }
    const text = String(value || '').trim();
    if (text) return text;
  }
  return '';
}

function getProductFieldSummary(data: Record<string, unknown> | null) {
  const fields = data || {};
  return {
    name:
      firstText(fields, ['英文名称', 'productNameEn', 'product_name_en', '品类名称', '模板名称', 'templateName', 'name']) ||
      '未识别商品名',
    category: firstText(fields, ['二级分类', 'categoryLevel2', 'category_level_2', '一级分类', 'categoryLevel1']) || '未识别分类',
    material: firstText(fields, ['产品材质', 'material', '材质', '具体成分', 'composition']) || '未识别材质',
    model: firstText(fields, ['产品型号', 'productModel', '模板号', '模板编号', 'subjectCode', '主体编码']) || '未识别型号',
    keywords: firstText(fields, ['关键词', 'keywords', 'keyword']) || '未提供关键词',
  };
}

function getPendingImageSummary() {
  return {
    name: '产品图已锁定，待规划识别',
    category: '待规划识别',
    material: '待规划识别',
    model: '待规划识别',
    keywords: '待规划识别',
  };
}

function productFactSourceLabel(source: unknown, exportedFieldCount: number): string {
  const value = String(source || '').trim();
  const normalized = value.toLowerCase();
  if (!value) return exportedFieldCount > 0 ? '导出字段补充' : '产品图 / VL 识别';
  if (normalized.includes('image') || normalized.includes('vision') || normalized.includes('vl')) return '产品图 / VL 识别';
  if (normalized.includes('field') || normalized.includes('json') || normalized.includes('export')) {
    return exportedFieldCount > 0 ? '导出字段补充' : '产品图 / VL 识别';
  }
  return value;
}

function escapeHtml(value: unknown): string {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function formatCopyValue(value: unknown): string {
  if (Array.isArray(value)) return value.map((item, index) => `${index + 1}. ${String(item)}`).join('\n');
  if (value && typeof value === 'object') {
    const entries = Object.entries(value as Record<string, unknown>);
    return entries.map(([key, item]) => `${key}:\n${formatCopyValue(item)}`).join('\n\n');
  }
  return String(value ?? '');
}

function getReviewIssueTheme(level: unknown): 'success' | 'warning' | 'danger' | 'primary' {
  const text = String(level || '').toLowerCase();
  if (text === 'error' || text === 'critical') return 'danger';
  if (text === 'warning') return 'warning';
  if (text === 'info') return 'primary';
  return 'success';
}

function getReviewIssueLabel(level: unknown): string {
  const text = String(level || '').toLowerCase();
  if (text === 'error' || text === 'critical') return '阻断';
  if (text === 'warning') return '需确认';
  if (text === 'info') return '提示';
  return '通过';
}

function renderReviewHtml(value: unknown): string {
  const review = asRecord(value);
  const score = review.score;
  const issues = asArray(review.issues).map((item) => asRecord(item));
  const nextActions = asArray(review.nextActions).map((item) => String(item || '').trim()).filter(Boolean);
  const videoReady = Boolean(review.videoReady);
  const issueHtml =
    issues
      .map((item) => {
        const label = getReviewIssueLabel(item.level);
        const code = String(item.code || '').trim();
        const message = String(item.message || '').trim();
        return `<li><strong>${escapeHtml(label)}</strong>${code ? ` · ${escapeHtml(code)}` : ''}<br>${escapeHtml(message)}</li>`;
      })
      .join('') || '<li>暂无阻断项。</li>';
  const actionHtml = nextActions.map((item) => `<li>${escapeHtml(item)}</li>`).join('') || '<li>核对事实后即可进入发布或后续联动。</li>';
  return `<p>审核分：${escapeHtml(score ?? '-')}</p><h3>审核提示</h3><ul>${issueHtml}</ul><h3>下一步</h3><ol>${actionHtml}</ol><p>后续联动：${videoReady ? '可进入产品视频能力' : '需要先补齐产品图或分镜素材'}</p>`;
}

function splitLines(value: string): string[] {
  return value
    .split(/[\n,，;；|]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function parseProductImageSet(value: string, primaryUrl: string): ProductImageInput[] {
  const images: ProductImageInput[] = [];
  const seen = new Set<string>();
  const add = (item: ProductImageInput) => {
    const url = String(item.url || '').trim();
    if (!url || seen.has(url)) return;
    seen.add(url);
    images.push({
      ...item,
      url,
      role: String(item.role || (images.length === 0 ? 'primary' : 'reference')).trim(),
      label: String(item.label || item.role || (images.length === 0 ? '主图' : `参考图 ${images.length}`)).trim(),
      isPrimary: Boolean(item.isPrimary || images.length === 0),
    });
  };
  if (primaryUrl.trim()) {
    add({ url: primaryUrl.trim(), role: 'primary', label: '主图', isPrimary: true, source: 'productImageUrl' });
  }
  const text = value.trim();
  if (!text) return images;
  if (text.startsWith('[')) {
    try {
      const parsed = JSON.parse(text);
      if (Array.isArray(parsed)) {
        parsed.forEach((item) => {
          if (typeof item === 'string') add({ url: item });
          else if (item && typeof item === 'object') add(item as ProductImageInput);
        });
        return images;
      }
    } catch {
      // Fall back to line parser below.
    }
  }
  text
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .forEach((line) => {
      const parts = line.split(/[,，|]+/).map((item) => item.trim()).filter(Boolean);
      if (parts.length === 1) {
        add({ url: parts[0], role: 'reference', label: `参考图 ${images.length}` });
        return;
      }
      const [role, url, label] = parts;
      add({ url, role: role || 'reference', label: label || role || `参考图 ${images.length}` });
    });
  return images;
}

function copyGenerationLabel(method: unknown): string {
  const value = String(method || '').trim();
  if (value === 'openai_responses') return 'OpenAI Responses';
  if (value === 'volcengine_chat') return '火山 VL Chat';
  if (value === 'template_fallback') return '模板兜底';
  return value || '未知';
}

function themeForGeneration(method: unknown): 'success' | 'warning' | 'danger' {
  return String(method || '') === 'template_fallback' ? 'danger' : 'success';
}

function getVideoUrls(result: ProductCommercializationResponse | null): string[] {
  const urls: string[] = [];
  const add = (item: unknown) => {
    if (typeof item === 'string') {
      const text = item.trim();
      if (text.startsWith('http://') || text.startsWith('https://')) urls.push(text);
      return;
    }
    if (Array.isArray(item)) {
      item.forEach(add);
      return;
    }
    if (item && typeof item === 'object') {
      const record = item as Record<string, unknown>;
      ['videoUrl', 'videoUrls', 'url', 'ossUrl', 'storedUrl'].forEach((key) => add(record[key]));
    }
  };
  add(result?.videoResult);
  add(result?.videoAssetPackage);
  return uniqueStrings(urls);
}

function videoKeyframeRoleLabel(role: unknown): string {
  const value = String(role || '').trim();
  if (value === 'normalized_first_frame') return 'Vidu 归一化首帧';
  if (value === 'first_frame' || value === 'opening_frame') return '首帧';
  if (value === 'last_frame' || value === 'ending_frame' || value === 'closing_frame') return '尾帧';
  if (value === 'key_frame' || value === 'confirmed_keyframe') return '关键帧';
  return value || '关键帧';
}

function videoKeyframeRoleHint(role: unknown): string {
  const value = String(role || '').trim();
  if (value === 'normalized_first_frame') return '用于固定目标画幅，确认后作为 Vidu 视频参考首帧';
  if (value === 'first_frame' || value === 'opening_frame') return '作为本镜头开始画面的事实锚点';
  if (value === 'last_frame' || value === 'ending_frame' || value === 'closing_frame') return '作为本镜头结束画面的收束参考';
  return '用于约束本镜头视频生成效果';
}

function videoKeyframeRolesCompatible(needRole: unknown, frameRole: unknown): boolean {
  const need = String(needRole || 'key_frame').trim();
  const frame = String(frameRole || 'confirmed_keyframe').trim();
  if (need === frame) return true;
  const firstRoles = new Set(['first_frame', 'normalized_first_frame', 'opening_frame']);
  const lastRoles = new Set(['last_frame', 'ending_frame', 'closing_frame']);
  const genericRoles = new Set(['key_frame', 'confirmed_keyframe']);
  if (firstRoles.has(need) && firstRoles.has(frame)) return true;
  if (lastRoles.has(need) && lastRoles.has(frame)) return true;
  return genericRoles.has(need) && genericRoles.has(frame);
}

function findGeneratedKeyframeForNeed(need: Record<string, unknown>, frames: Record<string, unknown>[]) {
  return frames.find((frame) => getFrameImageUrl(frame) && videoKeyframeRolesCompatible(need.role, frame.role));
}

function keyframeGroupGenerationState(group: ReturnType<typeof buildVideoStoryboardGroups>[number]) {
  const needs = group.keyframeNeeds;
  const generatedFrames = group.generatedKeyframes.filter((item) => getFrameImageUrl(item));
  if (needs.length === 0) {
    return { generatedCount: generatedFrames.length, requiredCount: 0, missingNeeds: [] as Record<string, unknown>[], complete: true };
  }
  const missingNeeds = needs.filter((need) => !findGeneratedKeyframeForNeed(need, generatedFrames));
  return {
    generatedCount: generatedFrames.length,
    requiredCount: needs.length,
    missingNeeds,
    complete: missingNeeds.length === 0,
  };
}

function uniqueStrings(values: string[]): string[] {
  const seen = new Set<string>();
  return values.filter((item) => {
    const key = item.trim();
    if (!key || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function collectImageUrls(value: unknown): string[] {
  const urls: string[] = [];
  const add = (item: unknown) => {
    if (typeof item === 'string') {
      const text = item.trim();
      if (text.startsWith('http://') || text.startsWith('https://')) urls.push(text);
      return;
    }
    if (Array.isArray(item)) {
      item.forEach(add);
      return;
    }
    if (item && typeof item === 'object') {
      const record = item as Record<string, unknown>;
      ['imageUrl', 'imageUrls', 'image_url', 'image_urls', 'storedUrl', 'storedUrls', 'ossUrl', 'url', 'resultUrls'].forEach((key) =>
        add(record[key]),
      );
    }
  };
  add(value);
  return uniqueStrings(urls);
}

function getRunImageUrls(result: BusinessRunPollResult | null): string[] {
  if (!result) return [];
  const resultPayload = asRecord(result.resultPayload);
  const resultBody = asRecord(result.result);
  const imageResult = asRecord(resultPayload.imageResult || resultBody.imageResult);
  const candidates = [
    result.imageUrls,
    result.image_urls,
    resultPayload.imageUrls,
    resultPayload.image_urls,
    imageResult.imageUrls,
    imageResult.image_urls,
    imageResult.imageResults,
    imageResult.storedAssets,
    imageResult.storedUrl,
    resultBody.imageUrls,
    resultBody.image_urls,
  ];
  return uniqueStrings(candidates.flatMap(collectImageUrls));
}

function getRunVisualResults(result: BusinessRunPollResult | null): Array<{ sceneId: string; label?: string; urls: string[] }> {
  if (!result) return [];
  const resultPayload = asRecord(result.resultPayload);
  const resultBody = asRecord(result.result);
  const imageResult = asRecord(resultPayload.imageResult || resultBody.imageResult);
  const records = asArray(imageResult.imageResults).map((item) => asRecord(item));
  if (records.length === 0) {
    const urls = getRunImageUrls(result);
    return urls.length > 0 ? [{ sceneId: '', urls }] : [];
  }
  return records
    .map((item) => {
      const urls = collectImageUrls(item);
      return {
        sceneId: String(item.sceneId || item.scene_id || '').trim(),
        label: String(item.label || '').trim() || undefined,
        urls,
      };
    })
    .filter((item) => item.urls.length > 0);
}

function getFrameImageUrl(frame: Record<string, unknown>): string {
  return String(frame.imageUrl || frame.ossUrl || frame.storedUrl || frame.url || '').trim();
}

function normalizeShotScope(value: unknown): string {
  if (value === null || value === undefined || value === false) return '';
  const text = String(value).trim();
  if (!text) return '';
  const match = text.match(/\d+/);
  return match ? String(Number(match[0])) : text;
}

function frameMatchesShotScope(frame: Record<string, unknown>, shotScope: string, fallbackIndex = 0): boolean {
  const normalizedScope = normalizeShotScope(shotScope);
  if (!normalizedScope) return true;
  const frameShot = normalizeShotScope(frame.shot || frame.segmentIndex || frame.segment_index || frame.segment || fallbackIndex || '');
  return frameShot === normalizedScope;
}

function mergeKeyframesForShotScope(
  existingFrames: Record<string, unknown>[],
  incomingFrames: Record<string, unknown>[],
  shotScope: string,
): Record<string, unknown>[] {
  const normalizedScope = normalizeShotScope(shotScope);
  if (!normalizedScope) return incomingFrames.length > 0 ? incomingFrames : existingFrames;
  const keptFrames = existingFrames.filter((frame, index) => !frameMatchesShotScope(frame, normalizedScope, index + 1));
  return [...keptFrames, ...incomingFrames];
}

function mergeScopedVideoKeyframeResult(
  previous: ProductCommercializationResponse | null,
  incoming: ProductCommercializationResponse,
  shotScope: string,
): ProductCommercializationResponse {
  const normalizedScope = normalizeShotScope(shotScope);
  if (!previous || !normalizedScope) return incoming;

  const previousPackage = asRecord(previous.videoAssetPackage);
  const incomingPackage = asRecord(incoming.videoAssetPackage);
  const previousVideoPlan = asRecord(previous.videoPlan);
  const incomingVideoPlan = asRecord(incoming.videoPlan);
  const previousVideoResult = asRecord(previous.videoResult);
  const incomingVideoResult = asRecord(incoming.videoResult);
  const mergedKeyframes = mergeKeyframesForShotScope(
    asArray(previousPackage.keyframes).map((item) => asRecord(item)),
    asArray(incomingPackage.keyframes).map((item) => asRecord(item)),
    normalizedScope,
  );

  return {
    ...previous,
    ...incoming,
    videoPlan: {
      ...previousVideoPlan,
      ...incomingVideoPlan,
      generatedKeyframes: mergedKeyframes,
    },
    videoAssetPackage: {
      ...previousPackage,
      ...incomingPackage,
      keyframes: mergedKeyframes,
    },
    videoResult: {
      ...previousVideoResult,
      ...incomingVideoResult,
      keyframes: mergedKeyframes,
    },
  };
}

function mergeVisualRunState(
  previous: GeneratedVisual[],
  scenes: readonly VisualScene[],
  runId: string,
  status: string,
  elapsedSeconds: number,
  poll: BusinessRunPollResult | null,
): GeneratedVisual[] {
  const visualResults = getRunVisualResults(poll);
  const fallbackUrls = getRunImageUrls(poll);
  const byScene = new Map<string, Array<{ sceneId: string; label?: string; urls: string[] }>>();
  visualResults.forEach((item) => {
    const key = item.sceneId;
    byScene.set(key, [...(byScene.get(key) || []), item]);
  });
  const sceneIds = new Set<string>(scenes.map((scene) => scene.id));
  const updated = previous.filter((item) => !(item.runId === runId || sceneIds.has(item.id)));
  const next = scenes.map((scene, index) => {
    const matched = byScene.get(scene.id)?.[0];
    const existing = previous.find((item) => item.runId === runId && item.id === scene.id);
    const urls = matched?.urls?.length ? matched.urls : scenes.length === 1 ? fallbackUrls : fallbackUrls[index] ? [fallbackUrls[index]] : [];
    return {
      id: scene.id,
      label: matched?.label || scene.label,
      runId,
      status,
      elapsedSeconds: elapsedSeconds || existing?.elapsedSeconds || 0,
      urls,
    };
  });
  return [...next, ...updated];
}

function markVisualRunFailed(
  previous: GeneratedVisual[],
  scenes: readonly VisualScene[],
  message: string,
): GeneratedVisual[] {
  const sceneIds = new Set<string>(scenes.map((scene) => scene.id));
  return previous.map((item) =>
    sceneIds.has(item.id)
      ? {
          ...item,
          status: 'failed',
          error: message,
        }
      : item,
  );
}

function hasAnyGeneratedVisualForScenes(visuals: GeneratedVisual[], scenes: readonly VisualScene[]): boolean {
  const sceneIds = new Set<string>(scenes.map((scene) => scene.id));
  return visuals.some((item) => sceneIds.has(item.id) && item.urls.length > 0);
}

function asProductCommercializationResponse(value: unknown): ProductCommercializationResponse | null {
  if (!value || typeof value !== 'object') return null;
  const payload = value as ProductCommercializationResponse;
  return payload.businessKey === 'product_commercialization' ||
    payload.businessKey === 'promo_video' ||
    payload.underlyingBusinessKey === 'product_commercialization'
    ? payload
    : null;
}

function businessRunStatusLabel(status: string) {
  if (status === 'succeeded') return '已完成';
  if (status === 'failed') return '失败';
  if (status === 'cancelled') return '已取消';
  if (status === 'queued') return '排队中';
  return '生成中';
}

function videoProviderLabel(value: VideoProvider): string {
  return VIDEO_MODEL_PROFILES[value]?.label || value;
}

function normalizeTargetDuration(value: unknown): number {
  const parsed = Math.round(Number(value));
  if (!Number.isFinite(parsed)) return 8;
  return Math.max(1, Math.min(60, parsed));
}

function buildVideoSegmentPlan(profile: (typeof VIDEO_MODEL_PROFILES)[VideoProvider], targetDurationSeconds: number): number[] {
  const options = [...profile.segmentDurationOptions].filter((item) => item > 0).sort((a, b) => b - a);
  if (options.length === 0) return [profile.defaultSegmentSeconds || SEGMENT_SECONDS];
  const durations: number[] = [];
  let remaining = normalizeTargetDuration(targetDurationSeconds);
  while (remaining > 0 && durations.length < 12) {
    const next = options.find((item) => item <= remaining) || options[options.length - 1];
    durations.push(next);
    remaining -= next;
  }
  return durations.length > 0 ? durations : [profile.defaultSegmentSeconds || options[0]];
}

function buildVideoPlanningText(fields: VideoPlanningField[], targetDurationSeconds: number, profile: (typeof VIDEO_MODEL_PROFILES)[VideoProvider]) {
  const filled = fields
    .map((field) => ({
      label: field.label.trim(),
      description: field.description.trim(),
      value: field.value.trim(),
    }))
    .filter((field) => field.value);
  const lines = [
    `用户目标成片时长：${targetDurationSeconds} 秒。必须先围绕这个目标规划脚本和分镜，不要把供应商单段时长当成用户需求。`,
    `当前视频模型单段画像：${profile.label}，可执行片段 ${profile.segmentDurationOptions.join('/')} 秒；执行策略应根据模型能力拆段或合成。`,
  ];
  if (filled.length > 0) {
    lines.push('用户补充的视频规划要素：');
    filled.forEach((field) => {
      lines.push(`- ${field.label}${field.description ? `（${field.description}）` : ''}：${field.value}`);
    });
  }
  return lines.join('\n');
}

function buildVideoPlanningContext(fields: VideoPlanningField[]): Record<string, unknown> {
  const standardKeyMap: Record<string, string> = {
    core_message: 'coreMessage',
    target_audience: 'targetAudience',
    usage_scene: 'usageScene',
    shot_preference: 'shotPreference',
    avoid: 'avoid',
  };
  const filled = fields
    .map((field) => ({
      id: field.id,
      label: field.label.trim(),
      description: field.description.trim(),
      value: field.value.trim(),
      source: field.source || (field.value.trim() ? 'manual' : undefined),
      sourceLabel: field.sourceLabel,
    }))
    .filter((field) => field.value);
  const context: Record<string, unknown> = {
    source: 'eval-editable-video-planning-fields',
    fields: filled,
  };
  filled.forEach((field) => {
    const key = standardKeyMap[field.id];
    if (key) context[key] = field.value;
  });
  return context;
}

function joinUniqueText(values: unknown[], limit = 4): string {
  return uniqueStrings(
    values
      .map((item) => String(item || '').trim())
      .filter(Boolean),
  )
    .slice(0, limit)
    .join('；');
}

function deriveVideoPlanningSuggestions(response: ProductCommercializationResponse | null): Record<string, VideoPlanningSuggestion> {
  const videoPlan = asRecord(response?.videoPlan);
  const contractedFields = asArray(videoPlan.editablePlanningFields).map((item) => asRecord(item));
  if (contractedFields.length > 0) {
    const suggestions: Record<string, VideoPlanningSuggestion> = {};
    contractedFields.forEach((field) => {
      const id = String(field.id || '').trim();
      const value = String(field.value || '').trim();
      if (!id || !value) return;
      suggestions[id] = {
        value,
        sourceLabel: String(field.sourceLabel || field.evidence || '后端规划字段合同').trim(),
      };
    });
    return suggestions;
  }
  const brief = asRecord(videoPlan.directorBrief);
  const facts = asRecord(response?.resolvedProductFacts);
  const storyboard = asArray(videoPlan.storyboard).map((item) => asRecord(item));
  const productText = joinUniqueText([facts.summary, brief.productUnderstanding]);
  const sceneText = joinUniqueText(storyboard.flatMap((shot) => [shot.scene, shot.goal]));
  const cameraText = joinUniqueText(storyboard.flatMap((shot) => [shot.cameraMovement, shot.camera]));
  const subjectText = joinUniqueText(storyboard.map((shot) => shot.subject));
  return {
    core_message: {
      value: joinUniqueText([brief.commercialGoal, productText, subjectText], 3),
      sourceLabel: '产品图 / VL 商品理解 / 分镜规划',
    },
    target_audience: {
      value: joinUniqueText([brief.targetAudience, videoPlan.targetAudience, videoPlan.audience, brief.commercialGoal], 3),
      sourceLabel: '导演 brief / 目标市场推断',
    },
    usage_scene: {
      value: sceneText,
      sourceLabel: '分镜场景规划',
    },
    shot_preference: {
      value: cameraText,
      sourceLabel: '镜头运动规划',
    },
    avoid: {
      value: joinUniqueText([videoPlan.negativePrompt, brief.continuityRule, '不要出现文字、水印、Logo、价格标签，不要改变商品形状和图案。'], 3),
      sourceLabel: '模型风险约束 / 系统默认保护',
    },
  };
}

function getVideoPlanningSourceTag(field: VideoPlanningField) {
  if (field.source === 'auto') return { label: '模型回填', theme: 'success' as const };
  if (field.source === 'manual') return { label: '人工调整', theme: 'warning' as const };
  if (field.source === 'default') return { label: '默认约束', theme: 'primary' as const };
  return { label: field.value.trim() ? '已填写' : '待识别' };
}

function buildVideoStoryboardGroups(
  videoPlan: Record<string, unknown>,
  videoAssetPackagePlan: Record<string, unknown>,
  videoAssetPackage: Record<string, unknown>,
) {
  const storyboard = asArray(videoPlan.storyboard).map((item) => asRecord(item));
  const keyframeNeeds = asArray(videoAssetPackagePlan.keyframeNeeds).map((item) => asRecord(item));
  const shotPackages = asArray(videoAssetPackagePlan.shotPackages).map((item) => asRecord(item));
  const generatedKeyframes = asArray(videoAssetPackage.keyframes).map((item) => asRecord(item));
  const buildShotMatcher = (shotNo: string, fallbackIndex: number) => (item: Record<string, unknown>) => {
    const raw = String(item.shot || item.segmentIndex || item.segment_index || item.segment || '').trim();
    return raw === shotNo || Number(raw) === fallbackIndex + 1 || (!raw && fallbackIndex === 0);
  };

  if (shotPackages.length > 0) {
    return shotPackages.map((item, index) => {
      const shotNo = String(item.shotNo || item.segmentIndex || item.shot || index + 1);
      const matchesShot = buildShotMatcher(shotNo, index);
      const packageNeeds = asArray(item.keyframeNeeds).map((need) => asRecord(need));
      const fallbackShot = storyboard.find(matchesShot) || ({} as Record<string, unknown>);
      const shot: Record<string, unknown> = {
        ...fallbackShot,
        shot: item.shotNo || item.segmentIndex || item.shot || fallbackShot.shot || index + 1,
        label: item.label || fallbackShot.label,
        keepSeconds: item.keepSeconds || fallbackShot.keepSeconds,
        durationSeconds: item.durationSeconds || fallbackShot.durationSeconds,
        subject: item.subject || fallbackShot.subject,
        goal: item.goal || fallbackShot.goal,
        scene: item.scene || fallbackShot.scene,
        cameraMovement: item.cameraMovement || fallbackShot.cameraMovement || fallbackShot.camera,
        camera: item.camera || fallbackShot.camera,
        composition: item.composition || fallbackShot.composition,
        referenceImage: item.referenceImage || fallbackShot.referenceImage,
        prompt: item.prompt || item.videoPrompt || fallbackShot.prompt,
        vendorPrompt: item.videoPrompt || fallbackShot.vendorPrompt,
        firstFramePrompt: item.firstFramePrompt || fallbackShot.firstFramePrompt,
        lastFramePrompt: item.lastFramePrompt || fallbackShot.lastFramePrompt,
        negativePrompt: item.negativePrompt || fallbackShot.negativePrompt,
      };
      return {
        shot,
        shotNo,
        keyframeNeeds: packageNeeds.length > 0 ? packageNeeds : keyframeNeeds.filter(matchesShot),
        generatedKeyframes: generatedKeyframes.filter(matchesShot),
        prompt: String(item.videoPrompt || item.prompt || fallbackShot.vendorPrompt || fallbackShot.prompt || videoPlan.videoPrompt || '').trim(),
      };
    });
  }

  const sourceShots = storyboard.length > 0 ? storyboard : [{ shot: 1, label: '视频脚本', prompt: videoPlan.videoPrompt }];

  return sourceShots.map((shot, index) => {
    const shotNo = String(shot.shot || shot.segmentIndex || index + 1);
    const matchesShot = buildShotMatcher(shotNo, index);
    const plannedNeeds = keyframeNeeds.filter(matchesShot);
    const derivedNeeds =
      plannedNeeds.length > 0
        ? plannedNeeds
        : [
            shot.firstFramePrompt
              ? { role: 'first_frame', shot: shotNo, prompt: shot.firstFramePrompt, source: 'storyboard' }
              : null,
            shot.lastFramePrompt
              ? { role: 'last_frame', shot: shotNo, prompt: shot.lastFramePrompt, source: 'storyboard' }
              : null,
          ].filter(Boolean).map((item) => item as Record<string, unknown>);

    return {
      shot,
      shotNo,
      keyframeNeeds: derivedNeeds,
      generatedKeyframes: generatedKeyframes.filter(matchesShot),
      prompt: String(shot.vendorPrompt || shot.prompt || videoPlan.videoPrompt || '').trim(),
    };
  });
}

function buildConfirmedVideoKeyframesPayload(
  groups: ReturnType<typeof buildVideoStoryboardGroups>,
  confirmedShotScopes: string[],
): Array<Record<string, unknown>> {
  const confirmedScopes = new Set(confirmedShotScopes.map((item) => normalizeShotScope(item)).filter(Boolean));
  if (confirmedScopes.size === 0) return [];
  return groups.flatMap((group) => {
    if (!confirmedScopes.has(normalizeShotScope(group.shotNo))) return [];
    return group.generatedKeyframes
      .map((frame) => {
        const imageUrl = getFrameImageUrl(frame);
        if (!imageUrl) return null;
        return {
          ...frame,
          imageUrl,
          ossUrl: String(frame.ossUrl || imageUrl),
          shot: group.shotNo,
          segmentIndex: Number(normalizeShotScope(group.shotNo)) || group.shotNo,
          confirmed: true,
          source: String(frame.source || 'user_confirmed_video_keyframe'),
        };
      })
      .filter(Boolean) as Array<Record<string, unknown>>;
  });
}

function hasReviewIssue(result: ProductCommercializationResponse | null, code: string): boolean {
  const issues = asArray(asRecord(result?.review).issues).map((item) => asRecord(item));
  return issues.some((item) => String(item.code || '') === code);
}

export function ProductCommercializationWorkbench({ mode = MODE_VIDEO }: { mode?: ProductCommercializationMode }) {
  const meta = MODE_META[mode] || MODE_META.video;
  const isVideoMode = mode === MODE_VIDEO;
  const [productImageUrl, setProductImageUrl] = useState('');
  const [productImageSetText, setProductImageSetText] = useState('');
  const [productFieldsText, setProductFieldsText] = useState('{}');
  const [extraPrompt, setExtraPrompt] = useState('');
  const [outputLanguage, setOutputLanguage] = useState<'en-US' | 'zh-CN' | 'bilingual'>('en-US');
  const [marketRegion, setMarketRegion] = useState<'US' | 'UK' | 'EU' | 'global'>('US');
  const [commercePlatform, setCommercePlatform] = useState('amazon_marketplace');
  const [copyTone, setCopyTone] = useState('natural_professional');
  const [targetAudience, setTargetAudience] = useState('海外电商买家，偏礼品和日常穿搭场景');
  const [sellingAngle, setSellingAngle] = useState('giftable_moment');
  const [forbiddenClaims, setForbiddenClaims] = useState('环保认证, 医疗功效, 品牌词, 物流时效承诺');
  const [visualSupportMode, setVisualSupportMode] = useState<'none' | 'recommendation' | 'generate'>('generate');
  const [videoScenario, setVideoScenario] = useState<'product_showcase_short' | 'social_ad_short' | 'detail_explainer'>('product_showcase_short');
  const [videoProvider, setVideoProvider] = useState<VideoProvider>('vidu_viduq3_turbo');
  const [aspectRatio, setAspectRatio] = useState('16:9');
  const [targetDurationSeconds, setTargetDurationSeconds] = useState(8);
  const [videoPlanningFields, setVideoPlanningFields] = useState<VideoPlanningField[]>(() => DEFAULT_VIDEO_PLANNING_FIELDS);
  const [copyScenarios, setCopyScenarios] = useState<string[]>(COPY_SCENARIOS.map((item) => item.key));
  const [result, setResult] = useState<ProductCommercializationResponse | null>(null);
  const [status, setStatus] = useState<WorkStatus>('idle');
  const [error, setError] = useState('');
  const [fieldsConfirmed, setFieldsConfirmed] = useState(false);
  const [conflictAccepted, setConflictAccepted] = useState(false);
  const [generatedVisuals, setGeneratedVisuals] = useState<GeneratedVisual[]>([]);
  const uploadRef = useRef<HTMLInputElement | null>(null);
  const stageStudioRef = useRef<HTMLDivElement | null>(null);
  const stageMainRef = useRef<HTMLElement | null>(null);
  const stageScrollRequestedRef = useRef(false);
  const activeVideoRunIdRef = useRef<string | null>(null);
  const [videoRun, setVideoRun] = useState<{ runId: string; status: string; elapsedSeconds: number } | null>(null);
  const [resultInputSignature, setResultInputSignature] = useState('');
  const [videoPromptDraft, setVideoPromptDraft] = useState('');
  const [videoPlanConfirmed, setVideoPlanConfirmed] = useState(false);
  const [confirmedKeyframeShotScopes, setConfirmedKeyframeShotScopes] = useState<string[]>([]);
  const [activeKeyframeShotScope, setActiveKeyframeShotScope] = useState<string | null>(null);
  const [activeStage, setActiveStage] = useState<ProductCommercializationStage>('asset');
  const selectedVideoProfile = VIDEO_MODEL_PROFILES[videoProvider];
  const videoSegmentPlan = useMemo(
    () => buildVideoSegmentPlan(selectedVideoProfile, targetDurationSeconds),
    [selectedVideoProfile, targetDurationSeconds],
  );

  const parsedFields = useMemo(() => {
    try {
      const parsed = JSON.parse(productFieldsText || '{}');
      return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? (parsed as Record<string, unknown>) : {};
    } catch {
      return null;
    }
  }, [productFieldsText]);

  const productSummary = useMemo(() => getProductFieldSummary(parsedFields), [parsedFields]);
  const productImagesForPayload = useMemo(
    () => parseProductImageSet(productImageSetText, productImageUrl.trim()),
    [productImageSetText, productImageUrl],
  );
  const buildInputSignature = (planningFields: VideoPlanningField[] = videoPlanningFields) =>
    JSON.stringify({
      mode,
      productImageUrl: productImageUrl.trim(),
      productImageSetText: isVideoMode ? productImageSetText.trim() : undefined,
      productFieldsText,
      extraPrompt: extraPrompt.trim(),
      outputLanguage,
      marketRegion,
      commercePlatform: isVideoMode ? undefined : commercePlatform,
      copyTone: isVideoMode ? undefined : copyTone,
      targetAudience: isVideoMode ? undefined : targetAudience.trim(),
      sellingAngle: isVideoMode ? undefined : sellingAngle,
      forbiddenClaims: isVideoMode ? undefined : forbiddenClaims,
      visualSupportMode: isVideoMode ? undefined : visualSupportMode,
      copyScenarios: isVideoMode ? undefined : [...copyScenarios].sort(),
      videoScenario: isVideoMode ? videoScenario : undefined,
      videoProvider: isVideoMode ? videoProvider : undefined,
      aspectRatio: isVideoMode ? aspectRatio.trim() : undefined,
      targetDurationSeconds: isVideoMode ? targetDurationSeconds : undefined,
      videoPlanningFields: isVideoMode ? planningFields.map(({ id, label, description, value }) => ({ id, label, description, value })) : undefined,
    });
  const currentInputSignature = buildInputSignature();
  const shouldConfirmMatch = Boolean(productImageUrl.trim() && parsedFields && Object.keys(parsedFields).length > 0);
  const canRunPaidAction = Boolean(productImageUrl.trim());
  const hasFreshResult = Boolean(result && resultInputSignature === currentInputSignature && parsedFields !== null);
  const resultIsStale = Boolean(result && !hasFreshResult);
  const hasImageFieldConflict = hasFreshResult && hasReviewIssue(result, 'PRODUCT_IMAGE_FIELD_CONFLICT');
  const canRunCostAction = canRunPaidAction && hasFreshResult && (!hasImageFieldConflict || conflictAccepted);
  const currentVideoAssetPackagePlan = asRecord(result?.videoAssetPackagePlan);
  const currentVideoAssetPackage = asRecord(result?.videoAssetPackage);
  const currentVideoKeyframes = asArray(currentVideoAssetPackage.keyframes).map((item) => asRecord(item));
  const videoPlanForReview = asRecord(result?.videoPlan);
  const videoAssetPackagePlanForReview = asRecord(result?.videoAssetPackagePlan);
  const videoAssetPackageForReview = asRecord(result?.videoAssetPackage);
  const videoStoryboardGroupsForReview = buildVideoStoryboardGroups(
    videoPlanForReview,
    videoAssetPackagePlanForReview,
    videoAssetPackageForReview,
  );
  const keyframeReviewGroups = videoStoryboardGroupsForReview.filter((group) => group.keyframeNeeds.length > 0);
  const requiresVideoKeyframeConfirmation = isVideoMode && keyframeReviewGroups.length > 0;
  const isKeyframeGroupGenerated = (group: (typeof videoStoryboardGroupsForReview)[number]) =>
    keyframeGroupGenerationState(group).complete;
  const keyframeGeneratedShotScopes = keyframeReviewGroups
    .filter(isKeyframeGroupGenerated)
    .map((group) => group.shotNo);
  const allRequiredKeyframesGenerated =
    keyframeReviewGroups.length > 0 &&
    keyframeReviewGroups.every(isKeyframeGroupGenerated);
  const allRequiredKeyframesConfirmed =
    !requiresVideoKeyframeConfirmation ||
    (allRequiredKeyframesGenerated &&
      keyframeReviewGroups.every((group) => confirmedKeyframeShotScopes.includes(group.shotNo)));
  const hasGeneratedVideoKeyframes = requiresVideoKeyframeConfirmation
    ? allRequiredKeyframesGenerated
    : currentVideoKeyframes.some((item) => getFrameImageUrl(item));
  const confirmedKeyframeShotCount = keyframeReviewGroups.filter((group) =>
    confirmedKeyframeShotScopes.includes(group.shotNo),
  ).length;
  const canRunVideoCostAction = canRunCostAction && videoPlanConfirmed && allRequiredKeyframesConfirmed;
  const videoUrls = getVideoUrls(result);
  const hasGeneratedVisuals = hasAnyGeneratedVisualForScenes(generatedVisuals, VISUAL_SCENES);

  useEffect(() => {
    setFieldsConfirmed(false);
    setConflictAccepted(false);
    setVideoPromptDraft('');
    setVideoPlanConfirmed(false);
    setConfirmedKeyframeShotScopes([]);
  }, [productImageUrl, productImageSetText, productFieldsText]);

  useEffect(() => {
    setConflictAccepted(false);
  }, [resultInputSignature]);

  useEffect(() => {
    setVideoPlanConfirmed(false);
    setConfirmedKeyframeShotScopes([]);
  }, [currentInputSignature]);

  useEffect(() => {
    if (!stageScrollRequestedRef.current) {
      return;
    }
    stageScrollRequestedRef.current = false;
    window.requestAnimationFrame(() => {
      stageStudioRef.current?.scrollIntoView({ block: 'start', behavior: 'smooth' });
    });
  }, [activeStage]);

  const goToStage = (stage: ProductCommercializationStage) => {
    stageScrollRequestedRef.current = true;
    setActiveStage(stage);
  };

  const buildPayload = (): ProductCommercializationRequest => {
    if (parsedFields === null) {
      throw new Error('产品字段 JSON 格式不正确');
    }
    const executorId = selectedVideoProfile.executorId;
    const requestedSegmentSeconds = videoSegmentPlan[0] || selectedVideoProfile.defaultSegmentSeconds;
    const videoPlanningText = isVideoMode
      ? buildVideoPlanningText(videoPlanningFields, targetDurationSeconds, selectedVideoProfile)
      : '';
    const mergedExtraPrompt = [extraPrompt.trim(), videoPlanningText].filter(Boolean).join('\n\n');

    const basePayload: ProductCommercializationRequest = {
      productImageUrl: productImageUrl.trim() || undefined,
      productFields: parsedFields,
      extraPrompt: mergedExtraPrompt || undefined,
      outputLanguage,
      marketRegion,
      source: 'eval-product-commercialization',
      requestId: `eval-pc-${Date.now()}`,
    };

    if (isVideoMode) {
      return {
        ...basePayload,
        action: 'video_preview',
        productImages: productImagesForPayload,
        videoScenario,
        aspectRatio,
        durationSeconds: requestedSegmentSeconds,
        targetDurationSeconds,
        executorId,
        videoPlanningContext: buildVideoPlanningContext(videoPlanningFields),
      };
    }

    return {
      ...basePayload,
      action: 'copy_preview',
      commercePlatform,
      copyTone,
      targetAudience: targetAudience.trim() || undefined,
      sellingAngle,
      forbiddenClaims: splitLines(forbiddenClaims),
      copyScenarios,
      visualSupportMode,
    };
  };

  const buildPlanningFieldsWithSuggestions = (source: ProductCommercializationResponse | null, overwrite = false) => {
    const suggestions = deriveVideoPlanningSuggestions(source);
    const nextFields = videoPlanningFields.map((field) => {
      const suggestion = suggestions[field.id];
      const suggestionValue = String(suggestion?.value || '').trim();
      const sourceLabel = String(suggestion?.sourceLabel || '模型识别回填').trim();
      if (!suggestionValue) return field;
      if (!suggestion) return field;
      if (!overwrite && field.value.trim()) return field;
      if (field.value.trim() === suggestionValue && field.source === 'auto' && field.sourceLabel === sourceLabel) return field;
      return { ...field, value: suggestionValue, source: 'auto' as const, sourceLabel };
    });
    const changed = nextFields.some((field, index) => {
      const previous = videoPlanningFields[index];
      return field.value !== previous?.value || field.source !== previous?.source || field.sourceLabel !== previous?.sourceLabel;
    });
    return { nextFields, changed };
  };

  const applyVideoPlanningSuggestions = (source: ProductCommercializationResponse | null, overwrite = false, showMessage = true) => {
    const { nextFields, changed } = buildPlanningFieldsWithSuggestions(source, overwrite);
    if (!changed) {
      if (showMessage) MessagePlugin.warning('当前没有可回填的新要素；可以继续手动调整。');
      return;
    }
    setVideoPlanningFields(nextFields);
    setVideoPlanConfirmed(false);
    if (showMessage) MessagePlugin.success(overwrite ? '已用模型识别结果重填视频要素' : '已用模型识别结果补全空白视频要素');
  };

  const runPreview = async (
    options: {
      nextStage?: ProductCommercializationStage;
      successMessage?: string;
    } = {},
  ) => {
    setError('');
    setStatus('previewing');
    const signature = currentInputSignature;
    try {
      const payload = buildPayload();
      const response = isVideoMode ? await evalApi.planPromoVideo(payload) : await evalApi.previewProductCommercialization(payload);
      let signatureForResult = signature;
      setResult(response);
      setVideoPlanConfirmed(false);
      if (isVideoMode) {
        setVideoPromptDraft(String((response.videoPlan as Record<string, unknown> | undefined)?.videoPrompt || ''));
        const { nextFields, changed } = buildPlanningFieldsWithSuggestions(response, false);
        if (changed) {
          setVideoPlanningFields(nextFields);
          signatureForResult = buildInputSignature(nextFields);
        }
      }
      setResultInputSignature(signatureForResult);
      setGeneratedVisuals([]);
      setVideoRun(null);
      goToStage(options.nextStage || 'review');
      if (options.successMessage) MessagePlugin.success(options.successMessage);
    } catch (err) {
      setError(String((err as any)?.message || err || '生成失败'));
    } finally {
      setStatus('idle');
    }
  };

  const fillVideoPlanningFieldsWithModel = async () => {
    if (hasFreshResult) {
      applyVideoPlanningSuggestions(result, true);
      return;
    }
    if (!strategyStepReady) {
      setError('请先上传产品图，并确认产品字段 JSON 格式正确。');
      return;
    }
    await runPreview({
      nextStage: 'strategy',
      successMessage: '已用模型识别并填写视频规划要素，可继续人工调整。',
    });
  };

  const pollBusinessRun = async (
    runId: string,
    onTick: (poll: BusinessRunPollResult, elapsedSeconds: number) => void,
  ): Promise<BusinessRunPollResult> => {
    const startedAt = Date.now();
    let retryAfterSeconds = 3;
    for (let attempt = 0; attempt < 180; attempt += 1) {
      if (attempt > 0) {
        await delay(Math.max(2, Math.min(15, retryAfterSeconds)) * 1000);
      }
      const poll = await evalApi.getBusinessRun(runId, 'full');
      retryAfterSeconds = Number(poll.retryAfterSeconds || 5);
      const elapsedSeconds = Math.max(0, Math.round((Date.now() - startedAt) / 1000));
      onTick(poll, elapsedSeconds);
      const runStatus = String(poll.status || poll.taskStatus || 'running');
      if (runStatus === 'succeeded') return poll;
      if (runStatus === 'failed' || runStatus === 'cancelled') {
        throw new Error(String(poll.errorMessage || poll.error || poll.debugResponse || `任务${businessRunStatusLabel(runStatus)}`));
      }
    }
    throw new Error('任务轮询超时，请复制 runId 到任务追踪继续排查');
  };

  const runVideoKeyframes = async (shotScope?: string) => {
    setError('');
    const normalizedShotScope = normalizeShotScope(shotScope);
    if (!productImageUrl.trim()) {
      setError('生成关键帧/首尾帧必须先提供产品图 URL');
      return;
    }
    if (!hasFreshResult) {
      setError('请先生成当前视频规划，再生成关键帧/首尾帧。');
      return;
    }
    if (!videoPromptDraft.trim()) {
      setError('视频执行脚本不能为空；请先生成视频规划，或在脚本框里补充生成要求。');
      return;
    }
    if (!videoPlanConfirmed) {
      setError('请先确认当前视频脚本和分镜，再生成关键帧/首尾帧。');
      return;
    }
    if (hasImageFieldConflict && !conflictAccepted) {
      setError('检测到图片与 JSON 冲突。请先确认按产品图识别结果继续，再生成关键帧/首尾帧。');
      return;
    }
    setActiveKeyframeShotScope(normalizedShotScope || null);
    setConfirmedKeyframeShotScopes((prev) =>
      normalizedShotScope ? prev.filter((scope) => scope !== normalizedShotScope) : [],
    );
    setStatus('keyframes');
    const signature = currentInputSignature;
    try {
      const payload = buildPayload();
      payload.action = 'video_keyframes';
      payload.videoPromptOverride = videoPromptDraft.trim();
      if (normalizedShotScope) payload.keyframeShotScope = normalizedShotScope;
      const submitted = await evalApi.submitPromoVideoKeyframesRun(payload);
      const runId = String(submitted.runId || submitted.id || '').trim();
      if (!runId) {
        throw new Error('关键帧任务提交成功但未返回 runId');
      }
      activeVideoRunIdRef.current = runId;
      setVideoRun({ runId, status: String(submitted.status || 'queued'), elapsedSeconds: 0 });
      MessagePlugin.success(`${normalizedShotScope ? `镜头 ${normalizedShotScope} ` : ''}关键帧任务已提交：${runId}`);
      await pollBusinessRun(runId, (poll, elapsedSeconds) => {
        if (activeVideoRunIdRef.current !== runId) return;
        const runStatus = String(poll.status || poll.taskStatus || 'running');
        setVideoRun({ runId, status: runStatus, elapsedSeconds });
        const fullResult = asProductCommercializationResponse(poll.resultPayload || poll.result);
        if (fullResult) {
          setResult((previous) =>
            normalizedShotScope ? mergeScopedVideoKeyframeResult(previous, fullResult, normalizedShotScope) : fullResult,
          );
          setResultInputSignature(signature);
          setVideoPromptDraft(String((fullResult.videoPlan as Record<string, unknown> | undefined)?.videoPrompt || videoPromptDraft));
          setConfirmedKeyframeShotScopes((prev) =>
            normalizedShotScope ? prev.filter((scope) => scope !== normalizedShotScope) : [],
          );
        }
      });
      MessagePlugin.success(`${normalizedShotScope ? `镜头 ${normalizedShotScope} ` : ''}关键帧已生成，请确认后再生成视频。`);
    } catch (err) {
      setError(String((err as any)?.message || err || '关键帧生成失败'));
    } finally {
      setStatus('idle');
      setActiveKeyframeShotScope(null);
    }
  };

  const runVideo = async () => {
    setError('');
    if (!productImageUrl.trim()) {
      setError('生成视频必须先提供产品图 URL');
      return;
    }
    if (!hasFreshResult) {
      setError('请先生成当前视频规划，确认商品事实、供应商、场景和时长后再提交视频任务');
      return;
    }
    if (!videoPromptDraft.trim()) {
      setError('视频执行脚本不能为空；请先生成视频规划，或在脚本框里补充生成要求。');
      return;
    }
    if (!videoPlanConfirmed) {
      setError('请先确认当前视频脚本和分镜；脚本、产品图或参数变更后需要重新确认，再提交视频成本任务。');
      return;
    }
    if (requiresVideoKeyframeConfirmation && !hasGeneratedVideoKeyframes) {
      setError('当前规划要求关键帧/首尾帧。请先生成并确认，再提交视频成本任务。');
      return;
    }
    if (requiresVideoKeyframeConfirmation && !allRequiredKeyframesConfirmed) {
      setError('请逐个镜头确认生成的关键帧/首尾帧可用，再提交视频成本任务。');
      return;
    }
    if (hasImageFieldConflict && !conflictAccepted) {
      setError('检测到图片与 JSON 冲突。请先在结果区确认“按产品图识别结果继续”，再触发视频成本动作。');
      return;
    }
    setStatus('video');
    const signature = currentInputSignature;
    try {
      const payload = buildPayload();
      payload.action = 'video_generate';
      payload.videoPromptOverride = videoPromptDraft.trim();
      const confirmedVideoKeyframes = buildConfirmedVideoKeyframesPayload(
        videoStoryboardGroupsForReview,
        confirmedKeyframeShotScopes,
      );
      if (confirmedVideoKeyframes.length > 0) {
        payload.confirmedVideoKeyframes = confirmedVideoKeyframes;
      }
      const submitted = await evalApi.submitPromoVideoRun(payload);
      const runId = String(submitted.runId || submitted.id || '').trim();
      if (!runId) {
        throw new Error('视频任务提交成功但未返回 runId');
      }
      activeVideoRunIdRef.current = runId;
      setVideoRun({ runId, status: String(submitted.status || 'queued'), elapsedSeconds: 0 });
        goToStage('deliver');
      MessagePlugin.success(`视频任务已提交：${runId}`);
      await pollBusinessRun(runId, (poll, elapsedSeconds) => {
        if (activeVideoRunIdRef.current !== runId) return;
        const runStatus = String(poll.status || poll.taskStatus || 'running');
        setVideoRun({ runId, status: runStatus, elapsedSeconds });
        const fullResult = asProductCommercializationResponse(poll.resultPayload || poll.result);
        if (fullResult) {
          setResult(fullResult);
          setResultInputSignature(signature);
          setVideoPromptDraft(String((fullResult.videoPlan as Record<string, unknown> | undefined)?.videoPrompt || videoPromptDraft));
        } else if (Array.isArray(poll.videoUrls) && poll.videoUrls.length > 0) {
          setResult((prev) =>
            prev
              ? {
                  ...prev,
                  status: runStatus,
                  videoResult: {
                    ...((prev.videoResult || {}) as Record<string, unknown>),
                    status: runStatus,
                    videoUrls: poll.videoUrls,
                  },
                }
              : prev,
          );
        }
      });
    } catch (err) {
      setError(String((err as any)?.message || err || '视频生成失败'));
    } finally {
      setStatus('idle');
    }
  };

  const uploadProductImage = async (file: File | null | undefined) => {
    if (!file) return;
    setError('');
    setStatus('uploading');
    try {
      const uploaded = await evalApi.uploadImage(file);
      setProductImageUrl(uploaded.url);
      goToStage(isVideoMode ? 'strategy' : 'facts');
      MessagePlugin.success('产品图已上传');
    } catch (err) {
      setError(String((err as any)?.message || err || '上传失败'));
    } finally {
      setStatus('idle');
      if (uploadRef.current) uploadRef.current.value = '';
    }
  };

  const toggleScenario = (key: string) => {
    setCopyScenarios((prev) => {
      if (prev.includes(key)) return prev.filter((item) => item !== key);
      return [...prev, key];
    });
  };

  const updateVideoPlanningField = (id: string, patch: Partial<VideoPlanningField>) => {
    const isManualPatch = ['label', 'description', 'value'].some((key) => Object.prototype.hasOwnProperty.call(patch, key));
    setVideoPlanningFields((prev) =>
      prev.map((item) =>
        item.id === id
          ? {
              ...item,
              ...patch,
              ...(isManualPatch ? { source: 'manual' as const, sourceLabel: '人工调整' } : null),
            }
          : item,
      ),
    );
  };

  const addVideoPlanningField = () => {
    setVideoPlanningFields((prev) => [
      ...prev,
      {
        id: `custom_${Date.now()}`,
        label: `自定义要素 ${prev.filter((item) => item.removable).length + 1}`,
        description: '可选补充信息',
        value: '',
        removable: true,
        source: 'manual',
        sourceLabel: '人工新增',
      },
    ]);
  };

  const removeVideoPlanningField = (id: string) => {
    setVideoPlanningFields((prev) => prev.filter((item) => item.id !== id || !item.removable));
  };

  const findModelImageBrief = (sceneId: string): Record<string, unknown> | null => {
    const briefs = asArray(asRecord(result?.contentPackage).imageBriefs).map((item) => asRecord(item));
    return briefs.find((item) => String(item.id || '').trim() === sceneId) || null;
  };

  const generateVisualScenes = async (scenes: readonly VisualScene[]) => {
    setError('');
    if (scenes.length === 0) {
      setError('请至少选择一个配图场景');
      return;
    }
    if (!productImageUrl.trim()) {
      setError('生成配图必须先提供产品图 URL');
      return;
    }
    if (visualSupportMode !== 'generate') {
      setError('请先把配图模式切换为“生成配图”，再触发图片成本动作');
      return;
    }
    if (!hasFreshResult) {
      setError('当前输入已经变化，请先基于当前图片和字段重新生成文案内容包，再触发配图生成');
      return;
    }
    if (hasImageFieldConflict && !conflictAccepted) {
      setError('检测到图片与 JSON 冲突。请先在结果区确认“按产品图识别结果继续”，再触发配图成本动作。');
      return;
    }
    setStatus('visual');
    try {
      const payload: ProductCommercializationRequest = {
        ...buildPayload(),
        action: 'visual_generate',
        visualScenes: scenes.map((scene) => scene.id),
      };
      payload.requestId = `eval-pc-visual-${scenes.map((scene) => scene.id).join('-')}-${Date.now()}`;
      const submitted = await evalApi.submitProductCommercializationVideoRun(payload);
      const runId = String(submitted.runId || submitted.id || '').trim();
      if (!runId) {
        throw new Error('配图任务提交成功但未返回 runId');
      }
      setGeneratedVisuals((prev) =>
        mergeVisualRunState(prev, scenes, runId, String(submitted.status || 'queued'), 0, submitted),
      );
      goToStage('deliver');
      MessagePlugin.success(`${scenes.length > 1 ? '组图' : '配图'}任务已提交：${runId}`);
      const finalPoll = await pollBusinessRun(runId, (poll, elapsedSeconds) => {
        const runStatus = String(poll.status || poll.taskStatus || 'running');
        setGeneratedVisuals((prev) =>
          mergeVisualRunState(prev, scenes, runId, runStatus, elapsedSeconds, poll),
        );
      });
      if (getRunImageUrls(finalPoll).length === 0) {
        throw new Error('配图任务已完成但未返回图片 URL');
      }
      setGeneratedVisuals((prev) =>
        mergeVisualRunState(prev, scenes, runId, 'succeeded', 0, finalPoll),
      );
    } catch (err) {
      const message = String((err as any)?.message || err || '配图生成失败');
      setError(message);
      setGeneratedVisuals((prev) => markVisualRunFailed(prev, scenes, message));
    } finally {
      setStatus('idle');
    }
  };

  const generateVisualScene = async (scene: VisualScene) => generateVisualScenes([scene]);

  const generateAllVisualScenes = async () => generateVisualScenes(VISUAL_SCENES);

  const downloadContentPackage = () => {
    if (!result) return;
    if (!hasFreshResult) {
      setError('当前输入已经变化，请先重新生成内容包，再下载交付文件');
      return;
    }
    const copyPackage = asRecord(result.copyPackage);
    const generatedImages = generatedVisuals.flatMap((item) =>
      item.urls.map((url) => ({ label: item.label, runId: item.runId, url })),
    );
    const html = `<!doctype html>
<html lang="zh-CN">
<head><meta charset="utf-8"><title>PODI 产品商业化内容包</title>
<style>body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;line-height:1.6;padding:32px;color:#111827}section{border-top:1px solid #e5e7eb;padding:20px 0}img,video{max-width:720px;width:100%;display:block;margin:12px 0;border:1px solid #e5e7eb}pre{white-space:pre-wrap;background:#f8fafc;padding:12px;border-radius:8px}</style></head>
<body>
<h1>PODI 产品商业化内容包</h1>
<section><h2>产品图</h2>${productImageUrl ? `<img src="${escapeHtml(productImageUrl)}" alt="产品图">` : '<p>未提供产品图</p>'}</section>
<section><h2>产品字段</h2><pre>${escapeHtml(prettyJson(parsedFields || {}))}</pre></section>
<section><h2>模型生成证据</h2><pre>${escapeHtml(prettyJson(result.copyGeneration || {}))}</pre></section>
<section><h2>商家内容策略</h2><pre>${escapeHtml(prettyJson(result.contentPackage || {}))}</pre></section>
<section><h2>文案包</h2>${Object.entries(copyPackage)
      .map(([key, value]) => `<h3>${escapeHtml(COPY_OUTPUT_LABELS[key] || key)}</h3><pre>${escapeHtml(formatCopyValue(value))}</pre>`)
      .join('\n')}</section>
<section><h2>生成配图</h2>${generatedImages
      .map((item) => `<h3>${escapeHtml(item.label)} · runId=${escapeHtml(item.runId)}</h3><img src="${escapeHtml(item.url)}" alt="${escapeHtml(item.label)}"><p>${escapeHtml(item.url)}</p>`)
      .join('\n') || '<p>暂无生成配图</p>'}</section>
<section><h2>视频</h2>${videoUrls.map((url) => `<video src="${escapeHtml(url)}" controls></video><p>${escapeHtml(url)}</p>`).join('\n') || '<p>暂无视频</p>'}</section>
<section><h2>审核与下一步</h2>${renderReviewHtml(result.review)}</section>
</body></html>`;
    const blob = new Blob([html], { type: 'text/html;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `podi-product-content-${Date.now()}.html`;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  };

  const copyPackage = asRecord(result?.copyPackage);
  const contentPackage = asRecord(result?.contentPackage);
  const copyGeneration = asRecord(result?.copyGeneration);
  const resolvedProductFacts = asRecord(result?.resolvedProductFacts);
  const commercePositioning = asRecord(contentPackage.commercePositioning);
  const imageFactAssessment = asRecord(contentPackage.imageFactAssessment);
  const modelImageBriefs = asArray(contentPackage.imageBriefs).map((item) => asRecord(item));
  const channelUsageGuide = asArray(contentPackage.channelUsageGuide).map((item) => asRecord(item));
  const productCard = asRecord(result?.productCard);
  const visualAssetPlan = asRecord(result?.visualAssetPlan);
  const videoPlan = asRecord(result?.videoPlan);
  const videoAssetPackagePlan = asRecord(result?.videoAssetPackagePlan);
  const videoAssetPackage = asRecord(result?.videoAssetPackage);
  const videoStoryboardGroups = buildVideoStoryboardGroups(videoPlan, videoAssetPackagePlan, videoAssetPackage);
  const videoPackageKeyframes = asArray(videoAssetPackage.keyframes).map((item) => asRecord(item));
  const videoPackageSegments = asArray(videoAssetPackage.segmentVideos).map((item) => asRecord(item));
  const videoPackageComposition = asRecord(videoAssetPackage.composition);
  const videoAspectPolicy = asRecord(videoPlan.aspectPolicy);
  const videoReferenceImageSet = asRecord(videoPlan.referenceImageSet);
  const isViduVideoProvider = videoProvider === 'vidu_viduq3_turbo';
  const videoAspectExecutionLabel =
    String(videoAspectPolicy.mode || '') === 'normalized_first_frame'
      ? `已归一首帧 ${String(videoAspectPolicy.executionAspectRatio || videoPlan.aspectRatio || aspectRatio)}`
      : videoAspectPolicy.requiresFirstFrameNormalization
        ? `执行前归一到 ${String(videoAspectPolicy.requestedAspectRatio || videoPlan.aspectRatio || aspectRatio)}`
        : String(videoAspectPolicy.mode || '') === 'input_image_ratio'
          ? '实际比例随首帧'
          : String(videoAspectPolicy.executionAspectRatio || videoPlan.aspectRatio || aspectRatio);
  const videoPlanningReviewFields = videoPlanningFields.filter((field) => field.value.trim());
  const review = asRecord(result?.review);
  const requiresComposition = videoSegmentPlan.length > 1 || !selectedVideoProfile.segmentDurationOptions.includes(targetDurationSeconds);
  const selectedScenario = VIDEO_SCENARIOS.find((item) => item.key === videoScenario);
  const hasProductImage = Boolean(productImageUrl.trim());
  const hasParsedFields = parsedFields !== null;
  const exportedFieldCount = parsedFields ? Object.keys(parsedFields).length : 0;
  const visibleProductSummary = useMemo(
    () => (isVideoMode && hasProductImage && !hasFreshResult ? getPendingImageSummary() : productSummary),
    [hasFreshResult, hasProductImage, isVideoMode, productSummary],
  );
  const factsStepReady = hasProductImage && hasParsedFields && (!shouldConfirmMatch || fieldsConfirmed);
  const strategyStepReady = isVideoMode ? hasProductImage && hasParsedFields : hasProductImage && hasParsedFields && copyScenarios.length > 0;
  const deliverReady =
    generatedVisuals.some((item) => item.urls.length > 0) ||
    videoUrls.length > 0 ||
    Boolean(videoRun) ||
    Object.keys(videoAssetPackage).length > 0;
  const visibleStages = useMemo(
    () =>
      (isVideoMode
        ? COMMERCIALIZATION_STAGES.filter((stage) => stage.key !== 'facts').map((stage) =>
            stage.key === 'strategy'
              ? {
                  ...stage,
                  videoLabel: '核对商品与视频策略',
                  desc: '商品核对 + 场景/时长/镜头',
                }
              : stage,
          )
        : COMMERCIALIZATION_STAGES),
    [isVideoMode],
  );
  const activeStageIndex = visibleStages.findIndex((stage) => stage.key === activeStage);
  const canOpenStage = (stage: ProductCommercializationStage) => {
    if (stage === 'asset') return true;
    if (isVideoMode && stage === 'facts') return false;
    if (stage === 'facts') return hasProductImage;
    if (stage === 'strategy') return isVideoMode ? hasProductImage && hasParsedFields : factsStepReady;
    if (stage === 'review') return hasFreshResult || strategyStepReady;
    if (stage === 'deliver') return hasFreshResult || deliverReady;
    return true;
  };
  const stageState = (stage: ProductCommercializationStage): 'done' | 'active' | 'locked' | 'todo' => {
    if (activeStage === stage) return 'active';
    if (!canOpenStage(stage)) return 'locked';
    if (stage === 'asset' && hasProductImage) return 'done';
    if (stage === 'facts' && factsStepReady) return 'done';
    if (stage === 'strategy' && hasFreshResult) return 'done';
    if (
      stage === 'review' &&
      hasFreshResult &&
      (isVideoMode ? videoPlanConfirmed && allRequiredKeyframesConfirmed : true)
    ) return 'done';
    if (stage === 'deliver' && deliverReady) return 'done';
    return 'todo';
  };
  const handleStageClick = (stage: ProductCommercializationStage) => {
    if (!canOpenStage(stage)) return;
    goToStage(stage);
  };

  useEffect(() => {
    if (!isVideoMode || activeStage !== 'facts') return;
    setActiveStage(hasProductImage ? 'strategy' : 'asset');
  }, [activeStage, hasProductImage, isVideoMode]);

  return (
    <section className="podi-product-commercialization">
      <div className="podi-product-commercialization__head">
        <div>
          <Typography.Text theme="primary">{isVideoMode ? '产品视频能力' : '产品商业化能力'}</Typography.Text>
          <Typography.Title level="h3" style={{ margin: '4px 0' }}>
            {meta.title}
          </Typography.Title>
          <Typography.Text theme="secondary">{meta.subtitle}</Typography.Text>
        </div>
        <Space align="center">
          {meta.tags.map((tag) => (
            <Tag key={tag.label} theme={tag.theme} variant="light">
              {tag.label}
            </Tag>
          ))}
        </Space>
      </div>

      <Alert
        theme="info"
        message={
          isVideoMode
            ? '预览只生成视频脚本、分镜和执行参数；提交素材包任务需单独点击，并按所选模型的时长画像拆段。'
            : '预览生成大模型文案包和配图方案；商业化配图需单独点击，默认走 GPT Image 2 并按 runId 回填。'
        }
      />
      <div className="podi-product-commercialization__interface-note">
        <Typography.Text strong>能力接口</Typography.Text>
        <div className="podi-product-commercialization__interface-list">
          {meta.interfaceNotes.map((item) => (
            <span key={`${item.label}-${item.value}`}>
              <b>{item.label}</b>
              {item.value}
            </span>
          ))}
        </div>
      </div>
      {error ? <Alert theme="error" message={error} /> : null}
      {videoRun ? (
        <Alert
          theme={videoRun.status === 'failed' ? 'error' : videoRun.status === 'succeeded' ? 'success' : 'info'}
          message={`素材任务 ${businessRunStatusLabel(videoRun.status)} · runId=${videoRun.runId} · 已等待 ${videoRun.elapsedSeconds}s`}
        />
      ) : null}
      {status === 'previewing' ? (
        <Alert
          theme="info"
          message={isVideoMode ? '正在生成视频规划，通常需要 20-90 秒；完成后会进入脚本与分镜确认。' : '正在生成内容包，通常需要 20-90 秒；完成后结果会出现在右侧输出区。'}
        />
      ) : null}
      {status === 'visual' ? (
        <Alert theme="info" message="正在生成配图，页面会按 runId 轮询任务状态；完成后图片会自动回填到结果区。" />
      ) : null}
      {status === 'keyframes' ? (
        <Alert theme="info" message="正在生成视频关键帧/首尾帧，页面会按 runId 轮询任务状态；完成后需要人工确认再生成视频。" />
      ) : null}

      <div ref={stageStudioRef} className="podi-product-commercialization__studio">
        <aside className="podi-product-commercialization__stage-rail" aria-label="产品商业化流程">
          {visibleStages.map((stage, index) => {
            const state = stageState(stage.key);
            const isActive = activeStage === stage.key;
            return (
              <button
                key={stage.key}
                type="button"
                className={`podi-product-commercialization__stage-step is-${state}${isActive ? ' is-current' : ''}`}
                disabled={!canOpenStage(stage.key)}
                onClick={() => handleStageClick(stage.key)}
              >
                <span>{index + 1}</span>
                <strong>{isVideoMode ? stage.videoLabel : stage.copyLabel}</strong>
                <small>{stage.desc}</small>
              </button>
            );
          })}
        </aside>

        <main ref={stageMainRef} className="podi-product-commercialization__stage-main">
          {activeStage === 'asset' ? (
            <section className="podi-product-commercialization__stage-panel">
              <div className="podi-product-commercialization__stage-title">
                <span>STEP 1</span>
                <Typography.Title level="h4">{isVideoMode ? '上传产品图组' : '上传并锁定产品图'}</Typography.Title>
                <Typography.Text theme="secondary">
                  {isVideoMode
                    ? '主图决定商品身份；正面、背面、侧面和细节图用于辅助脚本、分镜和参考图选择。'
                    : '产品图是最高优先级事实源，后续文案和配图都围绕这张图展开。'}
                </Typography.Text>
              </div>
              <div className="podi-product-commercialization__asset-layout">
                <div
                  className="podi-product-commercialization__asset-drop"
                  role="button"
                  tabIndex={0}
                  onClick={() => uploadRef.current?.click()}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault();
                      uploadRef.current?.click();
                    }
                  }}
                  onDragOver={(event) => {
                    event.preventDefault();
                  }}
                  onDrop={(event) => {
                    event.preventDefault();
                    void uploadProductImage(event.dataTransfer.files?.[0]);
                  }}
                >
                  {productImageUrl ? (
                    <img src={productImageUrl} alt="产品图预览" />
                  ) : (
                    <div>
                      <strong>上传产品图</strong>
                      <span>拖拽图片到这里，或点击选择本地文件。</span>
                    </div>
                  )}
                </div>
                <div className="podi-product-commercialization__stage-controls">
                  <div className="podi-field-stack">
                    <Typography.Text>{isVideoMode ? '产品图来源' : '产品图 URL'}</Typography.Text>
                    <Space align="center">
                      <Input value={productImageUrl} onChange={(v) => setProductImageUrl(String(v))} placeholder="https://..." clearable />
                      <input
                        ref={uploadRef}
                        type="file"
                        accept="image/*"
                        style={{ display: 'none' }}
                        onChange={(event) => void uploadProductImage(event.currentTarget.files?.[0])}
                      />
                      <Button theme="primary" loading={status === 'uploading'} onClick={() => uploadRef.current?.click()}>
                        选择本地产品图
                      </Button>
                    </Space>
                    <Typography.Text theme="secondary">本地上传是主路径；公网 URL 仅用于复现或调试。</Typography.Text>
                  </div>
                  {isVideoMode ? (
                    <div className="podi-field-stack">
                      <Typography.Text>辅助视角图（可选）</Typography.Text>
                      <Textarea
                        value={productImageSetText}
                        onChange={(v) => setProductImageSetText(String(v))}
                        placeholder={'每行一张：role,url,label\nfront,https://example.com/front.png,正面\nback,https://example.com/back.png,背面\ndetail,https://example.com/detail.png,材质细节'}
                        autosize={{ minRows: 4, maxRows: 8 }}
                      />
                      {productImagesForPayload.length > 0 ? (
                        <div className="podi-product-commercialization__image-set">
                          {productImagesForPayload.map((item, index) => (
                            <div key={`${item.url}-${index}`}>
                              <img src={item.url} alt={item.label || item.role || `参考图 ${index + 1}`} />
                              <span>{item.isPrimary ? '主图' : item.label || item.role || '参考图'}</span>
                            </div>
                          ))}
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                  <Alert theme="info" message="导出 JSON 不是必填项；如果 JSON 与图片不一致，后续默认以产品图为准并要求人工复核。" />
                  <Space>
                    <Button theme="primary" disabled={!hasProductImage} onClick={() => goToStage(isVideoMode ? 'strategy' : 'facts')}>
                      {isVideoMode ? '下一步：核对并设置视频策略' : '下一步：核对商品事实'}
                    </Button>
                  </Space>
                </div>
              </div>
            </section>
          ) : null}

          {activeStage === 'facts' && !isVideoMode ? (
            <section className="podi-product-commercialization__stage-panel">
              <div className="podi-product-commercialization__stage-title">
                <span>STEP 2</span>
                <Typography.Title level="h4">核对图片与字段</Typography.Title>
                <Typography.Text theme="secondary">字段只是说明材料，不再强迫用户为了测试去填完整 JSON。</Typography.Text>
              </div>
              <div className="podi-product-commercialization__fact-layout">
                <div className="podi-field-stack">
                  <div className="podi-product-commercialization__panel-head">
                    <Typography.Text>产品导出字段 JSON（可选）</Typography.Text>
                    <Typography.Text theme={parsedFields === null ? 'error' : 'secondary'}>
                      {parsedFields === null
                        ? 'JSON 格式错误'
                        : exportedFieldCount > 0
                          ? `${exportedFieldCount} 个补充字段`
                          : '未填写，按产品图推断'}
                    </Typography.Text>
                  </div>
                  <Space size="small" breakLine>
                    <Button size="small" variant="outline" onClick={() => setProductFieldsText(prettyJson(DEFAULT_PRODUCT_FIELDS))}>
                      填入示例字段
                    </Button>
                    <Button size="small" variant="outline" onClick={() => setProductFieldsText('{}')}>
                      清空字段，仅用产品图
                    </Button>
                  </Space>
                  <Textarea
                    value={productFieldsText}
                    onChange={(v) => setProductFieldsText(String(v))}
                    autosize={{ minRows: 8, maxRows: 14 }}
                    status={parsedFields === null ? 'error' : 'default'}
                  />
                </div>
                <div className="podi-product-commercialization__fact-card">
                  <Typography.Text strong>当前商品摘要</Typography.Text>
                  <div className="podi-product-commercialization__facts">
                    <span>商品：{productSummary.name}</span>
                    <span>分类：{productSummary.category}</span>
                    <span>材质：{productSummary.material}</span>
                    <span>型号：{productSummary.model}</span>
                  </div>
                  {shouldConfirmMatch ? (
                    <label className="podi-product-commercialization__confirm podi-product-commercialization__confirm--strong">
                      <input
                        type="checkbox"
                        checked={fieldsConfirmed}
                        onChange={(event) => setFieldsConfirmed(event.currentTarget.checked)}
                      />
                      <span>我已核对：这批字段与当前产品图属于同一商品。若只是乱填测试，请清空字段或接受后续冲突复核。</span>
                    </label>
                  ) : (
                    <Alert theme="success" message="当前按产品图主流程继续；缺失字段会由模型推断并降低置信度。" />
                  )}
                  <Space>
                    <Button variant="outline" onClick={() => goToStage('asset')}>
                      返回素材
                    </Button>
                    <Button theme="primary" disabled={!factsStepReady} onClick={() => goToStage('strategy')}>
                      下一步：设置生成方案
                    </Button>
                  </Space>
                </div>
              </div>
            </section>
          ) : null}

          {activeStage === 'strategy' ? (
            <section className="podi-product-commercialization__stage-panel">
              <div className="podi-product-commercialization__stage-title">
                <span>{isVideoMode ? 'STEP 2' : 'STEP 3'}</span>
                <Typography.Title level="h4">{isVideoMode ? '核对商品并规划视频素材包' : '规划文案与配图'}</Typography.Title>
                <Typography.Text theme="secondary">
                  {isVideoMode
                    ? '先让模型读产品图和可选字段补齐关键要素；你确认或修改后，再生成脚本和分镜。'
                    : '先生成结构化内容包；配图仍需后续显式点击。'}
                </Typography.Text>
              </div>
              {isVideoMode ? (
                <div className="podi-product-commercialization__merged-facts">
                  <div className="podi-field-stack">
                    <div className="podi-product-commercialization__panel-head">
                      <Typography.Text>产品导出字段 JSON（可选）</Typography.Text>
                      <Typography.Text theme={parsedFields === null ? 'error' : 'secondary'}>
                        {parsedFields === null
                          ? 'JSON 格式错误'
                          : exportedFieldCount > 0
                            ? `${exportedFieldCount} 个补充字段`
                            : '未填写，按产品图推断'}
                      </Typography.Text>
                    </div>
                    <Space size="small" breakLine>
                      <Button size="small" variant="outline" onClick={() => setProductFieldsText(prettyJson(DEFAULT_PRODUCT_FIELDS))}>
                        填入示例字段
                      </Button>
                      <Button size="small" variant="outline" onClick={() => setProductFieldsText('{}')}>
                        清空字段，仅用产品图
                      </Button>
                    </Space>
                    <Textarea
                      value={productFieldsText}
                      onChange={(v) => setProductFieldsText(String(v))}
                      autosize={{ minRows: 5, maxRows: 10 }}
                      status={parsedFields === null ? 'error' : 'default'}
                    />
                  </div>
                  <div className="podi-product-commercialization__fact-card">
                    <Typography.Text strong>当前商品摘要</Typography.Text>
                    <div className="podi-product-commercialization__facts">
                      <span>商品：{visibleProductSummary.name}</span>
                      <span>分类：{visibleProductSummary.category}</span>
                      <span>材质：{visibleProductSummary.material}</span>
                      <span>型号：{visibleProductSummary.model}</span>
                    </div>
                    {shouldConfirmMatch ? (
                      <Alert theme="warning" message="视频规划不会要求你预先确认 JSON 一定正确；产品图优先，字段只作为说明材料。若图片与字段冲突，结果区会标记并要求人工复核。" />
                    ) : (
                      <Alert theme="success" message="当前按产品图主流程继续；缺失字段会由模型推断并降低置信度。" />
                    )}
                  </div>
                </div>
              ) : null}
              <div className="podi-product-commercialization__strategy-workbench">
                <div className="podi-product-commercialization__controls">
                  <Select
                    label="语言"
                    value={outputLanguage}
                    onChange={(v) => setOutputLanguage(String(v) as any)}
                    options={[
                      { label: '英文 en-US', value: 'en-US' },
                      { label: '中文 zh-CN', value: 'zh-CN' },
                      { label: '中英双语', value: 'bilingual' },
                    ]}
                  />
                  <Select
                    label="市场"
                    value={marketRegion}
                    onChange={(v) => setMarketRegion(String(v) as any)}
                    options={[
                      { label: '美国 US', value: 'US' },
                      { label: '英国 UK', value: 'UK' },
                      { label: '欧盟 EU', value: 'EU' },
                      { label: '全球 global', value: 'global' },
                    ]}
                  />
                  {!isVideoMode ? (
                    <>
                      <Select label="平台" value={commercePlatform} onChange={(v) => setCommercePlatform(String(v))} options={COMMERCE_PLATFORM_OPTIONS} />
                      <Select label="语气" value={copyTone} onChange={(v) => setCopyTone(String(v))} options={COPY_TONE_OPTIONS} />
                      <Select label="主打角度" value={sellingAngle} onChange={(v) => setSellingAngle(String(v))} options={SELLING_ANGLE_OPTIONS} />
                      <Select
                        label="配图"
                        value={visualSupportMode}
                        onChange={(v) => setVisualSupportMode(String(v) as any)}
                        options={[
                          { label: '生成配图', value: 'generate' },
                          { label: '只给建议', value: 'recommendation' },
                          { label: '不配图', value: 'none' },
                        ]}
                      />
                    </>
                  ) : (
                    <>
                      <Select
                        label="视频供应商"
                        value={videoProvider}
                        onChange={(v) => setVideoProvider(String(v) as VideoProvider)}
                        options={[
                          { label: 'Vidu · viduq3-turbo', value: 'vidu_viduq3_turbo' },
                          { label: 'KIE · Veo3.1 Fast', value: 'kie_veo3_fast' },
                        ]}
                      />
                      <Input
                        label="客户目标时长（秒）"
                        value={String(targetDurationSeconds)}
                        onChange={(v) => setTargetDurationSeconds(normalizeTargetDuration(v))}
                        placeholder="例如 15"
                      />
                      <Input
                        label={isViduVideoProvider ? '目标比例（执行前归一首帧）' : '目标比例'}
                        value={aspectRatio}
                        onChange={(v) => setAspectRatio(String(v))}
                      />
                    </>
                  )}
                </div>

                {!isVideoMode ? (
                  <>
                    <Input
                      label="目标人群"
                      value={targetAudience}
                      onChange={(v) => setTargetAudience(String(v))}
                      placeholder="例如：美国礼品买家、日常穿搭人群、季节上新受众"
                    />
                    <div className="podi-field-stack">
                      <Typography.Text>文案应用场景</Typography.Text>
                      <div className="podi-product-commercialization__chips" aria-label="文案场景">
                        {COPY_SCENARIOS.map((item) => (
                          <button key={item.key} type="button" className={copyScenarios.includes(item.key) ? 'is-active' : ''} onClick={() => toggleScenario(item.key)}>
                            <strong>{item.label}</strong>
                            <small>{item.desc}</small>
                          </button>
                        ))}
                      </div>
                    </div>
                    <div className="podi-field-stack">
                      <Typography.Text>禁用声明</Typography.Text>
                      <Textarea
                        value={forbiddenClaims}
                        onChange={(v) => setForbiddenClaims(String(v))}
                        placeholder="用逗号或换行分隔，例如：医疗功效、环保认证、品牌词、物流时效承诺"
                        autosize={{ minRows: 2, maxRows: 4 }}
                      />
                    </div>
                  </>
                ) : (
                  <div className="podi-field-stack">
                    <Typography.Text>视频应用场景</Typography.Text>
                    <div className="podi-product-commercialization__chips" aria-label="视频场景">
                      {VIDEO_SCENARIOS.map((item) => (
                        <button key={item.key} type="button" className={videoScenario === item.key ? 'is-active' : ''} onClick={() => setVideoScenario(item.key as any)}>
                          <strong>{item.label}</strong>
                          <small>{item.desc}</small>
                        </button>
                      ))}
                    </div>
                    <div className="podi-product-commercialization__pending">
                      <Typography.Text theme="secondary">执行策略预估</Typography.Text>
                      <div className="podi-product-commercialization__execution-plan">
                        <div>
                          <strong>{targetDurationSeconds}s</strong>
                          <span>客户目标时长</span>
                        </div>
                        <div>
                          <strong>{videoSegmentPlan.join(' + ')}s</strong>
                          <span>{requiresComposition ? '规划为分段素材包' : '可走单段素材'}</span>
                        </div>
                      </div>
                      <Typography.Text theme="secondary">当前模型</Typography.Text>
                      <Space size="small" breakLine>
                        <Tag theme="success" variant="light">{selectedVideoProfile.label}</Tag>
                        {selectedVideoProfile.segmentDurationOptions.map((seconds) => (
                          <Tag key={seconds} theme="primary" variant="light">{seconds} 秒片段</Tag>
                        ))}
                      </Space>
                      {isViduVideoProvider ? (
                        <Alert theme="info" message="Vidu 图生视频会跟随输入首帧比例；请先生成并确认目标画幅首帧，再提交视频素材任务。" />
                      ) : null}
                    </div>
                    <div className="podi-product-commercialization__planning-fields">
                      <div className="podi-product-commercialization__panel-head">
                        <Typography.Text strong>视频规划要素</Typography.Text>
                        <Space size="small">
                          <Button
                            size="small"
                            variant="outline"
                            loading={status === 'previewing'}
                            disabled={!strategyStepReady || status !== 'idle'}
                            onClick={() => void fillVideoPlanningFieldsWithModel()}
                          >
                            {hasFreshResult ? '用模型结果重填' : '用模型填写'}
                          </Button>
                          <Button size="small" variant="outline" onClick={addVideoPlanningField}>
                            添加更多
                          </Button>
                        </Space>
                      </div>
                      <Alert
                        theme="info"
                        message="可以只填你确定的信息；留空要素会在生成规划后由产品图、VL 识别和可选 JSON 回填。回填后仍可人工修改，修改后需要重新生成素材包规划。"
                      />
                      {resultIsStale ? (
                        <Alert
                          theme="warning"
                          message="当前视频规划要素已经变更，旧脚本和分镜已过期。请重新生成素材包规划后，再确认关键帧/首尾帧或提交视频任务。"
                        />
                      ) : null}
                      {videoPlanningFields.map((field) => {
                        const isCustomField = Boolean(field.removable);
                        const sourceTag = getVideoPlanningSourceTag(field);
                        const sourceLabel = field.sourceLabel || (field.value.trim() ? '当前内容将作为规划输入' : '等待生成规划后识别');
                        return (
                          <div key={field.id} className="podi-product-commercialization__planning-field">
                            {isCustomField ? (
                              <>
                                <div className="podi-product-commercialization__planning-field-meta">
                                  <Input
                                    label="要素名称"
                                    value={field.label}
                                    onChange={(v) => updateVideoPlanningField(field.id, { label: String(v) })}
                                  />
                                  <Input
                                    label="说明"
                                    value={field.description}
                                    onChange={(v) => updateVideoPlanningField(field.id, { description: String(v) })}
                                  />
                                </div>
                                <div className="podi-product-commercialization__planning-source">
                                  <Tag {...(sourceTag.theme ? { theme: sourceTag.theme } : {})} variant="light">{sourceTag.label}</Tag>
                                  <Typography.Text theme="secondary">{sourceLabel}</Typography.Text>
                                </div>
                              </>
                            ) : (
                              <div className="podi-product-commercialization__planning-field-title">
                                <div>
                                  <Typography.Text strong>{field.label}</Typography.Text>
                                  <Typography.Text theme="secondary">{field.description}</Typography.Text>
                                  <Typography.Text theme="secondary" className="podi-product-commercialization__planning-source-copy">
                                    {sourceLabel}
                                  </Typography.Text>
                                </div>
                                <Tag {...(sourceTag.theme ? { theme: sourceTag.theme } : {})} variant="light">{sourceTag.label}</Tag>
                              </div>
                            )}
                            <Textarea
                              value={field.value}
                              onChange={(v) => updateVideoPlanningField(field.id, { value: String(v) })}
                              placeholder={`${field.label}可由产品图/JSON 识别后回填，也可以在这里手动调整；留空不会阻塞规划。`}
                              autosize={{ minRows: 2, maxRows: 5 }}
                            />
                            {field.removable ? (
                              <Button size="small" variant="text" theme="danger" onClick={() => removeVideoPlanningField(field.id)}>
                                删除这个要素
                              </Button>
                            ) : null}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                <div className="podi-field-stack">
                  <Typography.Text>补充要求</Typography.Text>
                  <Textarea
                    value={extraPrompt}
                    onChange={(v) => setExtraPrompt(String(v))}
                    placeholder={isVideoMode ? '例如：突出材质纹理和商品轮廓，不要出现文字和水印。' : '例如：偏节日礼品场景，避免夸张承诺。'}
                    autosize={{ minRows: 3, maxRows: 6 }}
                  />
                </div>

                <Space breakLine>
                  <Button variant="outline" onClick={() => goToStage(isVideoMode ? 'asset' : 'facts')}>
                    {isVideoMode ? '返回素材' : '返回核对'}
                  </Button>
                  <Button theme="primary" loading={status === 'previewing'} disabled={!strategyStepReady || (!isVideoMode && copyScenarios.length === 0)} onClick={() => void runPreview()}>
                    {isVideoMode && resultIsStale ? '重新生成素材包规划' : meta.previewButton}
                  </Button>
                </Space>
              </div>
            </section>
          ) : null}

          {activeStage === 'review' ? (
            <section className="podi-product-commercialization__stage-panel">
              <div className="podi-product-commercialization__stage-title">
                <span>{isVideoMode ? 'STEP 3' : 'STEP 4'}</span>
                <Typography.Title level="h4">{isVideoMode ? '确认脚本与分镜' : '审核内容包'}</Typography.Title>
                <Typography.Text theme="secondary">
                  {isVideoMode
                    ? '每个镜头都是一组脚本、视频提示词、关键帧/首尾帧需求和生成结果；确认无误后再触发视频成本任务。'
                    : '这一屏只做人工确认和成本动作入口，不再混入前置表单。'}
                </Typography.Text>
              </div>
              {!result ? (
                <div className="podi-product-commercialization__empty">
                  <Typography.Text theme="secondary">
                    {isVideoMode ? '还没有生成视频规划。请回到上一步生成脚本和分镜。' : '还没有生成方案。请回到上一步生成内容包。'}
                  </Typography.Text>
                  <Button theme="primary" onClick={() => goToStage('strategy')}>去生成方案</Button>
                </div>
              ) : resultIsStale ? (
                <Alert theme="warning" title="结果已过期" message="当前产品图、JSON 或策略参数已经变化，请回到方案步骤重新生成。" />
              ) : (
                <Space direction="vertical" size="medium" style={{ width: '100%' }}>
                  <section className="podi-result-section">
                    <Typography.Text strong>产品理解</Typography.Text>
                    <div className="podi-product-commercialization__strategy-summary">
                      <div>
                        <Typography.Text theme="secondary">商品判断</Typography.Text>
                        <Typography.Text>{String(resolvedProductFacts.summary || productSummary.name || '-')}</Typography.Text>
                      </div>
                      <div>
                        <Typography.Text theme="secondary">事实来源</Typography.Text>
                        <Typography.Text>{productFactSourceLabel(resolvedProductFacts.source, exportedFieldCount)}</Typography.Text>
                      </div>
                      <div>
                        <Typography.Text theme="secondary">置信度</Typography.Text>
                        <Typography.Text>{String(resolvedProductFacts.confidence || imageFactAssessment.confidence || productCard.confidence || '-')}</Typography.Text>
                      </div>
                    </div>
                    {hasImageFieldConflict ? (
                      <>
                        <Alert theme="warning" message={`疑似冲突：${asArray(resolvedProductFacts.fieldConflicts || imageFactAssessment.fieldConflicts).map((item) => String(item)).join('；')}`} />
                        <label className="podi-product-commercialization__confirm podi-product-commercialization__confirm--strong">
                          <input checked={conflictAccepted} type="checkbox" onChange={(event) => setConflictAccepted(event.currentTarget.checked)} />
                          <span>我确认按产品图识别结果继续，忽略与图片冲突的导出字段。</span>
                        </label>
                      </>
                    ) : null}
                  </section>

                  {!isVideoMode ? (
                    <>
                      <section className="podi-result-section">
                        <div className="podi-product-commercialization__panel-head">
                          <Typography.Text strong>模型生成证据</Typography.Text>
                          <Tag theme={themeForGeneration(copyGeneration.method)} variant="light">{copyGenerationLabel(copyGeneration.method)}</Tag>
                        </div>
                        <div className="podi-product-commercialization__facts">
                          <span>provider {String(copyGeneration.provider || '-')}</span>
                          <span>model {String(copyGeneration.model || '-')}</span>
                          <span>fallback {String(copyGeneration.fallback ?? '-')}</span>
                        </div>
                      </section>
                      <section className="podi-result-section">
                        <Typography.Text strong>文案结果</Typography.Text>
                        <div className="podi-product-commercialization__copy-list">
                          {Object.entries(copyPackage)
                            .filter(([key]) => COPY_OUTPUT_LABELS[key])
                            .map(([key, value]) => (
                              <div key={key}>
                                <Typography.Text strong>{COPY_OUTPUT_LABELS[key]}</Typography.Text>
                                <pre>{formatCopyValue(value)}</pre>
                              </div>
                            ))}
                        </div>
                      </section>
	                      <Space breakLine>
	                        <Button variant="outline" onClick={() => goToStage('strategy')}>调整方案</Button>
                        <Button
                          variant="outline"
                          loading={status === 'visual'}
                          disabled={status === 'visual' || visualSupportMode !== 'generate' || !canRunCostAction || !hasFreshResult}
                          onClick={() => void generateVisualScene(VISUAL_SCENES[1])}
                        >
                          生成社媒封面
                        </Button>
                        <Button
                          theme="success"
                          loading={status === 'visual'}
                          disabled={status === 'visual' || visualSupportMode !== 'generate' || !canRunCostAction || !hasFreshResult}
                          onClick={() => void generateAllVisualScenes()}
                        >
                          {hasGeneratedVisuals ? '重新生成全部组图' : '生成全部组图'}
                        </Button>
                        <Button theme="primary" disabled={!deliverReady} onClick={() => goToStage('deliver')}>
                          {deliverReady ? '查看交付' : '等待素材包结果'}
                        </Button>
                      </Space>
                    </>
                  ) : (
                    <>
                      <section className="podi-result-section">
                        <Typography.Text strong>视频规划</Typography.Text>
                        <div className="podi-product-commercialization__facts">
                          <span>{videoProviderLabel(videoProvider)}</span>
                          <span>{selectedScenario?.label || videoScenario}</span>
                          <span>{String(videoPlan.targetDurationSeconds || targetDurationSeconds)}s</span>
                          <span>{videoAspectExecutionLabel}</span>
                          <span>参考图 {String(videoReferenceImageSet.count || productImagesForPayload.length || 0)}</span>
                          <span>{asArray(videoPlan.storyboard).length || 1} 个镜头</span>
                        </div>
                        {(() => {
                          const planner = asRecord(videoPlan.planner);
                          const fallback = planner.fallback === true;
                          return (
                            <div className="podi-product-commercialization__planner-evidence">
                              <div>
                                <Typography.Text strong>规划器证据</Typography.Text>
                                <Typography.Text theme="secondary">
                                  {String(planner.provider || 'internal')} · {String(planner.model || '-')} · {String(planner.method || '-')}
                                </Typography.Text>
                              </div>
                              <Tag theme={fallback ? 'warning' : 'success'} variant="light">
                                {fallback ? '模板兜底' : '模型规划'}
                              </Tag>
                              {fallback ? (
                                <Alert theme="warning" message="当前没有成功调用 LLM/VL 规划器；该结果只能用于排障和交互验证，不能作为最终视频方法论验收。" />
                              ) : null}
                            </div>
                          );
                        })()}
                        {(() => {
                          const brief = asRecord(videoPlan.directorBrief);
                          return Object.keys(brief).length > 0 ? (
                            <div className="podi-product-commercialization__director-brief">
                              {[
                                { label: '商品理解', value: brief.productUnderstanding },
                                { label: '商业目标', value: brief.commercialGoal },
                                { label: '视觉风格', value: brief.visualStyle },
                                { label: '连续性规则', value: brief.continuityRule },
                              ].map((item) => (
                                <div key={item.label}>
                                  <Typography.Text theme="secondary">{item.label}</Typography.Text>
                                  <Typography.Text>{String(item.value || '-')}</Typography.Text>
                                </div>
                              ))}
                            </div>
                          ) : null;
                        })()}
                        {videoPlanningReviewFields.length > 0 ? (
                          <div className="podi-product-commercialization__planning-review" aria-label="模型回填要素">
                            <div className="podi-product-commercialization__panel-head">
                              <Typography.Text strong>模型回填要素</Typography.Text>
                              <Typography.Text theme="secondary">这些内容会随脚本和分镜一起提交；不合理先返回调整方案。</Typography.Text>
                            </div>
                            <div className="podi-product-commercialization__planning-review-grid">
                              {videoPlanningReviewFields.map((field) => {
                                const sourceTag = getVideoPlanningSourceTag(field);
                                return (
                                  <div key={field.id}>
                                    <div>
                                      <Typography.Text strong>{field.label}</Typography.Text>
                                      <Tag {...(sourceTag.theme ? { theme: sourceTag.theme } : {})} variant="light">{sourceTag.label}</Tag>
                                    </div>
                                    <Typography.Text>{field.value}</Typography.Text>
                                    <small>{field.sourceLabel || field.description}</small>
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        ) : null}
                        {Object.keys(videoAssetPackagePlan).length > 0 ? (
                          <div className="podi-product-commercialization__package-flow" aria-label="视频素材包阶段">
                            {[
                              { label: '脚本', value: videoPlanConfirmed ? '已确认' : String(asRecord(videoAssetPackagePlan.script).status || '待确认') },
                              { label: '分镜', value: `${videoStoryboardGroups.length || 1} 个镜头` },
                              {
                                label: '关键帧',
                                value: `${videoStoryboardGroups.reduce((total, group) => total + group.keyframeNeeds.length, 0)} 项需求`,
                              },
                              { label: '分段视频', value: requiresComposition ? '多段生成' : '单段生成' },
                              { label: '合成片', value: asRecord(videoAssetPackagePlan.compositionPlan).availableAsOptionalAction ? '可选后续动作' : '非必需' },
                            ].map((item) => (
                              <div key={item.label}>
                                <strong>{item.label}</strong>
                                <span>{item.value}</span>
                              </div>
                            ))}
                          </div>
                        ) : null}
                        <div className="podi-product-commercialization__script-review" aria-label="脚本确认与执行稿">
                          <div className="podi-product-commercialization__panel-head">
                            <Typography.Text strong>脚本确认与执行稿</Typography.Text>
                            <Typography.Text theme="secondary">先核对或改写这份总执行稿，再按镜头生成关键帧/首尾帧。</Typography.Text>
                          </div>
                          <Textarea
                            value={videoPromptDraft || String(videoPlan.videoPrompt || '')}
                            onChange={(value) => {
                              setVideoPromptDraft(String(value));
                              setVideoPlanConfirmed(false);
                              setConfirmedKeyframeShotScopes([]);
                            }}
                            autosize={{ minRows: 5, maxRows: 10 }}
                            placeholder="先生成视频规划，或在这里写入最终视频脚本。"
                          />
                          <label className="podi-product-commercialization__confirm podi-product-commercialization__confirm--strong">
                            <input
                              type="checkbox"
                              checked={videoPlanConfirmed}
                              disabled={!hasFreshResult || !videoPromptDraft.trim()}
                              onChange={(event) => setVideoPlanConfirmed(event.currentTarget.checked)}
                            />
                            <span>我已核对当前脚本和分镜；按当前稿提交视频素材包任务。</span>
                          </label>
                        </div>
                        <div className="podi-product-commercialization__storyboard-groups">
                          {videoStoryboardGroups.map((group, index) => {
                            const shot = group.shot;
                            const referenceImage = asRecord(shot.referenceImage);
                            const generationState = keyframeGroupGenerationState(group);
                            const generatedFrameCount = generationState.generatedCount;
                            const isShotGenerated = generationState.complete;
                            const missingNeedLabels = generationState.missingNeeds.map((need) => videoKeyframeRoleLabel(need.role)).join('、');
                            const isShotConfirmed =
                              group.keyframeNeeds.length > 0 && confirmedKeyframeShotScopes.includes(group.shotNo);
                            const shotNextAction =
                              group.keyframeNeeds.length === 0
                                ? '下一步：随视频任务直接执行'
                                : isShotConfirmed
                                  ? '下一步：可提交视频任务'
                                  : isShotGenerated
                                    ? '下一步：核对图片并勾选确认'
                                    : videoPlanConfirmed
                                      ? '下一步：生成本镜头关键帧'
                                      : '下一步：先勾选脚本确认';
                            return (
                              <article key={`${String(shot.label || 'shot')}-${index}`} className="podi-product-commercialization__storyboard-group">
                                <header>
                                  <div>
                                    <Typography.Text strong>
                                      镜头 {group.shotNo} · {String(shot.label || '商品镜头')}
                                    </Typography.Text>
                                    <Typography.Text theme="secondary">
                                      {String(shot.keepSeconds || shot.durationSeconds || SEGMENT_SECONDS)}s · {String(shot.subject || '产品主体')}
                                      {referenceImage.role ? ` · 参考 ${String(referenceImage.role)}` : ''}
                                    </Typography.Text>
                                  </div>
                                  <Tag
                                    theme={
                                      group.keyframeNeeds.length === 0
                                        ? 'default'
                                        : isShotConfirmed
                                          ? 'success'
                                          : isShotGenerated
                                            ? 'primary'
                                            : 'warning'
                                    }
                                    variant="light"
                                  >
                                    {group.keyframeNeeds.length === 0
                                      ? '无需关键帧'
                                      : isShotConfirmed
                                        ? '本镜头已确认'
                                        : isShotGenerated
                                          ? '待人工确认'
                                          : '待生成关键帧'}
                                  </Tag>
                                </header>
                                <div className="podi-product-commercialization__storyboard-body">
                                  <div>
                                    <Typography.Text theme="secondary">脚本意图</Typography.Text>
                                    <p>{String(shot.goal || shot.scene || '按当前产品图生成商品展示镜头。')}</p>
                                    <small>场景：{String(shot.scene || '-')} · 镜头：{String(shot.cameraMovement || shot.camera || '-')}</small>
                                  </div>
                                  <div>
                                    <Typography.Text theme="secondary">视频提示词</Typography.Text>
                                    <pre>{group.prompt || String(videoPlan.videoPrompt || '-')}</pre>
                                  </div>
                                  <div>
                                    <Typography.Text theme="secondary">关键帧提示词与结果</Typography.Text>
                                    <div className="podi-product-commercialization__frame-status">
                                      <span>计划 {group.keyframeNeeds.length} 项</span>
                                      <span>已生成 {generatedFrameCount} 张</span>
                                      {missingNeedLabels ? <span>缺少 {missingNeedLabels}</span> : null}
                                      <span>
                                        {group.keyframeNeeds.length === 0
                                          ? '无需独立关键帧'
                                          : isShotConfirmed
                                            ? '本镜头已确认'
                                            : isShotGenerated
                                              ? '生成后待确认'
                                            : '先生成关键帧再提交视频'}
                                      </span>
                                      <span>{shotNextAction}</span>
                                    </div>
                                    {group.keyframeNeeds.length > 0 ? (
                                      <div className="podi-product-commercialization__frame-needs">
                                        {group.keyframeNeeds.map((frame, frameIndex) => (
                                          <div key={`${String(frame.role || 'frame')}-${frameIndex}`}>
                                            <strong>{videoKeyframeRoleLabel(frame.role)}</strong>
                                            <span>{String(frame.prompt || frame.reason || videoKeyframeRoleHint(frame.role))}</span>
                                            <small>{videoKeyframeRoleHint(frame.role)}</small>
                                            <small>
                                              {findGeneratedKeyframeForNeed(frame, group.generatedKeyframes)
                                                ? '已生成对应图片'
                                                : '待生成对应图片'}
                                            </small>
                                          </div>
                                        ))}
                                      </div>
                                    ) : (
                                      <p>当前镜头暂不要求独立关键帧；执行时直接使用产品参考图。</p>
                                    )}
                                    {group.generatedKeyframes.length > 0 ? (
                                      <div className="podi-product-commercialization__frame-assets">
                                        {group.generatedKeyframes.map((frame, frameIndex) => {
                                          const frameUrl = getFrameImageUrl(frame);
                                          return (
                                            <div key={`${frameUrl || String(frame.role || 'frame')}-${frameIndex}`}>
                                              {frameUrl ? <img src={frameUrl} alt={`镜头 ${group.shotNo} ${videoKeyframeRoleLabel(frame.role)} ${frameIndex + 1}`} /> : null}
                                              <span>{videoKeyframeRoleLabel(frame.role)}</span>
                                            </div>
                                          );
                                        })}
                                      </div>
                                    ) : null}
                                    {group.keyframeNeeds.length > 0 ? (
                                      <>
                                        <label className="podi-product-commercialization__confirm podi-product-commercialization__confirm--inline">
                                          <input
                                            type="checkbox"
                                            checked={isShotConfirmed}
                                            disabled={!isShotGenerated}
                                            onChange={(event) => {
                                              const checked = event.currentTarget.checked;
                                              setConfirmedKeyframeShotScopes((prev) => {
                                                const withoutCurrent = prev.filter((scope) => scope !== group.shotNo);
                                                return checked ? [...withoutCurrent, group.shotNo] : withoutCurrent;
                                              });
                                            }}
                                          />
                                          <span>
                                            我确认镜头 {group.shotNo} 关键帧/首尾帧可用；如果不满意，只重生成本镜头。
                                          </span>
                                        </label>
                                        <div className="podi-product-commercialization__frame-actions">
                                          <Button
                                            size="small"
                                            variant="outline"
                                            loading={status === 'keyframes' && activeKeyframeShotScope === group.shotNo}
                                            disabled={
                                              status === 'keyframes' ||
                                              !canRunCostAction ||
                                              !videoPlanConfirmed ||
                                              !videoPromptDraft.trim()
                                            }
                                            onClick={() => void runVideoKeyframes(group.shotNo)}
                                          >
                                            {generatedFrameCount > 0 ? '重生成本镜头关键帧' : '生成本镜头关键帧'}
                                          </Button>
                                        </div>
                                      </>
                                    ) : null}
                                  </div>
                                </div>
                              </article>
                            );
                          })}
                        </div>
                        {requiresVideoKeyframeConfirmation ? (
                          <div className="podi-product-commercialization__confirm-gate" aria-label="关键帧确认门禁">
                            <div className="podi-product-commercialization__frame-status">
                              <span>关键帧确认进度 {confirmedKeyframeShotCount}/{keyframeReviewGroups.length} 个镜头。</span>
                              <span>{allRequiredKeyframesGenerated ? '关键帧已生成' : '仍有镜头待生成'}</span>
                              <span>{allRequiredKeyframesConfirmed ? '可提交视频素材任务' : '逐镜头确认后解锁视频生成'}</span>
                            </div>
                            <Typography.Text theme="secondary">
                              这里不再设置额外总确认；每个镜头确认一次就是最终门禁，不满意直接重生成对应镜头。
                            </Typography.Text>
                          </div>
                        ) : (
                          <Alert theme="info" message="当前规划没有独立关键帧需求，可以直接在确认脚本后生成视频素材。" />
                        )}
                      </section>
                      <Space breakLine>
                        <Button variant="outline" onClick={() => goToStage('strategy')}>调整方案</Button>
                        <Button
                          variant="outline"
                          loading={status === 'keyframes' && !activeKeyframeShotScope}
                          disabled={
                            status === 'keyframes' ||
                            !canRunCostAction ||
                            !videoPlanConfirmed ||
                            !videoPromptDraft.trim() ||
                            !requiresVideoKeyframeConfirmation
                          }
                          onClick={() => void runVideoKeyframes()}
                        >
                          {hasGeneratedVideoKeyframes ? '重新生成全部关键帧' : '生成全部关键帧'}
                        </Button>
                        <Button
                          theme="success"
                          loading={status === 'video'}
                          disabled={status === 'video' || !canRunVideoCostAction || !videoPromptDraft.trim()}
                          onClick={() => void runVideo()}
                        >
                          {requiresComposition ? `生成 ${targetDurationSeconds}s 分段视频素材包` : `生成 ${targetDurationSeconds}s 单段视频素材`}
                        </Button>
                        <Button theme="primary" disabled={!deliverReady} onClick={() => goToStage('deliver')}>
                          {deliverReady ? '查看交付' : '等待素材包结果'}
                        </Button>
                      </Space>
                      <div className="podi-product-commercialization__cost-note" role="note">
                        <strong>成本动作提示</strong>
                        <span>“生成关键帧”和“生成视频素材”都会提交异步任务并返回 runId；当前页会轮询结果，也可以复制 runId 到任务追踪继续查看。</span>
                      </div>
                    </>
                  )}
                </Space>
              )}
            </section>
          ) : null}

          {activeStage === 'deliver' ? (
            <section className="podi-product-commercialization__stage-panel">
              <div className="podi-product-commercialization__stage-title">
                <span>{isVideoMode ? 'STEP 4' : 'STEP 5'}</span>
                <Typography.Title level="h4">交付与追踪</Typography.Title>
                <Typography.Text theme="secondary">集中查看 runId、OSS 链接、视频素材包和审核提示。</Typography.Text>
              </div>
              {!result ? (
                <div className="podi-product-commercialization__empty">
                  <Typography.Text theme="secondary">还没有可交付结果。</Typography.Text>
                  <Button theme="primary" onClick={() => goToStage('strategy')}>返回生成方案</Button>
                </div>
              ) : (
                <Space direction="vertical" size="medium" style={{ width: '100%' }}>
                  {!isVideoMode ? (
                    <section className="podi-result-section">
                      <div className="podi-product-commercialization__panel-head">
                        <Typography.Text strong>配图与图文包</Typography.Text>
                        <Button size="small" variant="outline" disabled={!hasFreshResult} onClick={downloadContentPackage}>下载图文包</Button>
                      </div>
                      <div className="podi-product-commercialization__visual-grid">
                        {VISUAL_SCENES.map((scene) => {
                          const visual = generatedVisuals.find((item) => item.id === scene.id);
                          const modelBrief = modelImageBriefs.find((item) => String(item.id || '').trim() === scene.id);
                          const label = String(modelBrief?.label || scene.label);
                          const desc = String(modelBrief?.usage || scene.desc);
                          return (
                            <div key={scene.id} className="podi-product-commercialization__visual-card">
                              <div>
                                <Typography.Text strong>{label}</Typography.Text>
                                <Typography.Text theme="secondary">{desc}</Typography.Text>
                              </div>
                              {visual?.urls?.[0] ? <img src={visual.urls[0]} alt={label} /> : null}
                              {visual ? (
                                <Typography.Text theme={visual.status === 'failed' ? 'error' : 'secondary'}>{businessRunStatusLabel(visual.status)} · runId={visual.runId}</Typography.Text>
                              ) : (
                                <Typography.Text theme="secondary">尚未生成</Typography.Text>
                              )}
                              <Button
                                size="small"
                                variant="outline"
                                loading={status === 'visual'}
                                disabled={status === 'visual' || visualSupportMode !== 'generate' || !canRunCostAction || !hasFreshResult}
                                onClick={() => void generateVisualScene(scene)}
                              >
                                生成{label}
                              </Button>
                            </div>
                          );
                        })}
                      </div>
                    </section>
                  ) : (
                    <section className="podi-result-section">
                      <Typography.Text strong>视频素材包</Typography.Text>
                      {videoRun ? <Alert theme="info" message={`视频任务 ${businessRunStatusLabel(videoRun.status)} · runId=${videoRun.runId} · 已等待 ${videoRun.elapsedSeconds}s`} /> : null}
                      <div className="podi-product-commercialization__facts">
                        <span>交付阶段 {String(videoAssetPackage.deliveryStatus || '-')}</span>
                        <span>分段 {videoPackageSegments.length}</span>
                        <span>合成 {String(videoPackageComposition.status || '未执行')}</span>
                      </div>
                      {videoPackageKeyframes.length > 0 ? (
                        <div className="podi-product-commercialization__keyframes">
                          {videoPackageKeyframes.map((frame, index) => {
                            const frameUrl = getFrameImageUrl(frame);
                            return (
                              <div key={`${String(frame.role || 'frame')}-${String(frame.segmentIndex || index)}`}>
                                {frameUrl ? <img src={frameUrl} alt={`视频${videoKeyframeRoleLabel(frame.role)} ${index + 1}`} /> : null}
                                <Typography.Text strong>
                                  {videoKeyframeRoleLabel(frame.role)} · 分段 {String(frame.segmentIndex || frame.shot || index + 1)}
                                </Typography.Text>
                                <Typography.Text theme="secondary">
                                  {String(frame.aspectRatio || '-')} · {String(frame.width || '-')}×{String(frame.height || '-')}
                                </Typography.Text>
                              </div>
                            );
                          })}
                        </div>
                      ) : null}
                      {videoUrls.map((url, index) => (
                        <div key={`${url}-${index}`} className="podi-product-commercialization__video">
                          <video src={url} controls />
                          <Button variant="outline" onClick={() => window.open(url, '_blank', 'noreferrer')}>打开视频</Button>
                        </div>
                      ))}
                      {videoPackageSegments.length > 0 ? (
                        <div className="podi-product-commercialization__shot-list">
                          {videoPackageSegments.map((segment, index) => (
                            <div key={`${String(segment.segmentIndex || index)}-${String(segment.status || '')}`}>
                              <strong>分段 {String(segment.segmentIndex || index + 1)} · {String(segment.status || '-')}</strong>
                              <span>{String(segment.durationSeconds || '-')}s · {String(segment.provider || '-')} · {String(segment.model || '-')}</span>
                              {segment.referenceImageUrl ? <small>执行参考图：{String(segment.referenceImageUrl)}</small> : null}
                            </div>
                          ))}
                        </div>
                      ) : null}
                    </section>
                  )}
                  <section className="podi-result-section">
                    <Typography.Text strong>审核与下一步</Typography.Text>
                    <div className="podi-product-commercialization__review">
                      <div className="podi-product-commercialization__facts">
                        <span>审核分 {String(review.score ?? '-')}</span>
                        <span>提示 {asArray(review.issues).length}</span>
                        <span>{review.videoReady ? '可联动产品视频' : '需补齐视频素材'}</span>
                      </div>
                      <div className="podi-product-commercialization__review-grid">
                        <div className="podi-product-commercialization__review-list">
                          {(asArray(review.issues).length > 0 ? asArray(review.issues) : [{ level: 'success', code: 'NO_BLOCKER', message: '暂无阻断项，仍需人工核对商品事实和平台规则。' }]).map((item, index) => {
                            const issue = asRecord(item);
                            return (
                              <div key={`${String(issue.code || 'issue')}-${index}`}>
                                <Tag theme={getReviewIssueTheme(issue.level)} variant="light">{getReviewIssueLabel(issue.level)}</Tag>
                                <div>
                                  <strong>{String(issue.code || '审核提示')}</strong>
                                  <p>{String(issue.message || '请核对商品事实后再发布。')}</p>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                        <ol className="podi-product-commercialization__next-list">
                          {(asArray(review.nextActions).map((item) => String(item || '').trim()).filter(Boolean).length > 0
                            ? asArray(review.nextActions).map((item) => String(item || '').trim()).filter(Boolean)
                            : ['核对事实后使用当前资产；如需调整，返回方案步骤重新生成。']
                          ).map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}
                        </ol>
                      </div>
                    </div>
                  </section>
                </Space>
              )}
            </section>
          ) : null}
        </main>

        <aside className="podi-product-commercialization__studio-side">
          <div className="podi-product-commercialization__side-card">
            <Typography.Text strong>当前产品图</Typography.Text>
            <div className="podi-product-commercialization__side-image">
              {productImageUrl ? <img src={productImageUrl} alt="当前产品图" /> : <span>等待上传</span>}
            </div>
            {isVideoMode && productImagesForPayload.length > 1 ? (
              <div className="podi-product-commercialization__mini-image-set">
                {productImagesForPayload.slice(0, 4).map((item, index) => (
                  <img key={`${item.url}-${index}`} src={item.url} alt={item.label || item.role || `参考图 ${index + 1}`} />
                ))}
              </div>
            ) : null}
            <div className="podi-product-commercialization__facts">
              <span>字段 {exportedFieldCount}</span>
              {isVideoMode ? <span>图组 {productImagesForPayload.length}</span> : null}
              <span>{hasFreshResult ? '方案已生成' : '待生成方案'}</span>
              <span>{isVideoMode ? videoProviderLabel(videoProvider) : visualSupportMode === 'generate' ? 'GPT Image 2' : '仅建议'}</span>
            </div>
          </div>
          <div className="podi-product-commercialization__side-card">
            <Typography.Text strong>当前阶段</Typography.Text>
            <p>{visibleStages[activeStageIndex]?.desc || '-'}</p>
            <Space size="small" breakLine>
              {meta.tags.map((tag) => (
                <Tag key={tag.label} theme={tag.theme} variant="light">{tag.label}</Tag>
              ))}
            </Space>
          </div>
        </aside>
      </div>

    </section>
  );
}
