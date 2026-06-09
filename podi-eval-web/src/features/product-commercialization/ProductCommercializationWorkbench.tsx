import { useEffect, useMemo, useRef, useState } from 'react';
import { Alert, Button, Input, Select, Space, Tag, Textarea, Typography, MessagePlugin } from 'tdesign-react';
import { evalApi } from '../../api';
import type { BusinessRunPollResult, ProductCommercializationRequest, ProductCommercializationResponse, ProductDesignRunRequest } from '../../api';

type ProductCommercializationMode = 'copy' | 'video';
type WorkStatus = 'idle' | 'previewing' | 'video' | 'uploading' | 'visual';
type VideoProvider = 'kie_veo3_fast' | 'vidu_viduq3_turbo';

const MODE_COPY: ProductCommercializationMode = 'copy';
const MODE_VIDEO: ProductCommercializationMode = 'video';
const KIE_EXECUTOR_ID = 'executor_kie_market_default';
const VIDU_EXECUTOR_ID = 'executor_vidu_default';
const SEGMENT_SECONDS = 8;

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
    tags: Array<{ label: string; theme: 'primary' | 'success' | 'warning' }>;
  }
> = {
  copy: {
    title: '产品文案内容包',
    subtitle: '产品设计完成后，用大模型/VL 生成海外上架、详情页、广告和关键词内容。',
    inputHint: '产品图和字段是事实锚点；平台、语气、人群和卖点决定文案风格。',
    outputHint: '必须看到模型生成证据；模板兜底只能排障，不能作为验收通过。',
    emptyText: '先生成一次大模型文案包，再按需要显式生成配图。',
    previewButton: '生成文案内容包',
    tags: [
      { label: 'LLM / VL', theme: 'primary' },
      { label: '电商文案', theme: 'success' },
      { label: '多语言', theme: 'warning' },
    ],
  },
  video: {
    title: '产品视频生成',
    subtitle: '产品设计完成后，规划视频脚本，再选择 KIE 或 Vidu 生成视频。',
    inputHint: '产品图是必填素材；字段用于约束脚本和镜头。',
    outputHint: '预览只生成脚本；视频按钮才会触发成本动作。',
    emptyText: '先生成视频规划，确认商品、场景、供应商和时长，再生成视频。',
    previewButton: '生成视频规划',
    tags: [
      { label: '视频分镜', theme: 'primary' },
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

function inferProductType(data: Record<string, unknown> | null): ProductDesignRunRequest['productType'] {
  const summary = getProductFieldSummary(data);
  const text = `${summary.name} ${summary.category} ${summary.material}`.toLowerCase();
  if (/sock|socks|shirt|dress|apparel|服|袜|穿搭|面料/.test(text)) return 'apparel';
  if (/home|pillow|blanket|家纺|软装|抱枕|毯/.test(text)) return 'home_textile';
  if (/bag|tote|箱包|包/.test(text)) return 'bag';
  if (/shoe|鞋/.test(text)) return 'shoe';
  if (/stationery|文具/.test(text)) return 'stationery';
  if (/pack|包装/.test(text)) return 'packaging';
  return 'generic';
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
  const videoResult = result?.videoResult;
  if (!videoResult || typeof videoResult !== 'object') return [];
  const urls = (videoResult as Record<string, unknown>).videoUrls;
  return Array.isArray(urls) ? urls.filter((item): item is string => typeof item === 'string' && item.length > 0) : [];
}

function getRunImageUrls(result: BusinessRunPollResult | null): string[] {
  if (!result) return [];
  const candidates = [
    result.imageUrls,
    result.image_urls,
    asRecord(result.resultPayload).imageUrls,
    asRecord(result.resultPayload).image_urls,
    asRecord(result.result).imageUrls,
    asRecord(result.result).image_urls,
  ];
  for (const value of candidates) {
    if (Array.isArray(value)) {
      const urls = value.filter((item): item is string => typeof item === 'string' && item.length > 0);
      if (urls.length > 0) return urls;
    }
  }
  return [];
}

function asProductCommercializationResponse(value: unknown): ProductCommercializationResponse | null {
  if (!value || typeof value !== 'object') return null;
  const payload = value as ProductCommercializationResponse;
  return payload.businessKey === 'product_commercialization' ? payload : null;
}

function businessRunStatusLabel(status: string) {
  if (status === 'succeeded') return '已完成';
  if (status === 'failed') return '失败';
  if (status === 'cancelled') return '已取消';
  if (status === 'queued') return '排队中';
  return '生成中';
}

function videoProviderLabel(value: VideoProvider): string {
  return value === 'vidu_viduq3_turbo' ? 'Vidu · viduq3-turbo' : 'KIE · Veo3.1 Fast';
}

export function ProductCommercializationWorkbench({ mode = MODE_COPY }: { mode?: ProductCommercializationMode }) {
  const meta = MODE_META[mode] || MODE_META.copy;
  const isVideoMode = mode === MODE_VIDEO;
  const [productImageUrl, setProductImageUrl] = useState('');
  const [productFieldsText, setProductFieldsText] = useState(prettyJson(DEFAULT_PRODUCT_FIELDS));
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
  const [copyScenarios, setCopyScenarios] = useState<string[]>(COPY_SCENARIOS.map((item) => item.key));
  const [result, setResult] = useState<ProductCommercializationResponse | null>(null);
  const [status, setStatus] = useState<WorkStatus>('idle');
  const [error, setError] = useState('');
  const [fieldsConfirmed, setFieldsConfirmed] = useState(false);
  const [generatedVisuals, setGeneratedVisuals] = useState<GeneratedVisual[]>([]);
  const uploadRef = useRef<HTMLInputElement | null>(null);
  const activeVideoRunIdRef = useRef<string | null>(null);
  const [videoRun, setVideoRun] = useState<{ runId: string; status: string; elapsedSeconds: number } | null>(null);

  const parsedFields = useMemo(() => {
    try {
      const parsed = JSON.parse(productFieldsText || '{}');
      return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? (parsed as Record<string, unknown>) : {};
    } catch {
      return null;
    }
  }, [productFieldsText]);

  const productSummary = useMemo(() => getProductFieldSummary(parsedFields), [parsedFields]);
  const shouldConfirmMatch = Boolean(productImageUrl.trim() && parsedFields && Object.keys(parsedFields).length > 0);
  const canRunPaidAction = Boolean(productImageUrl.trim() && (!shouldConfirmMatch || fieldsConfirmed));
  const videoUrls = getVideoUrls(result);

  useEffect(() => {
    setFieldsConfirmed(false);
  }, [productImageUrl, productFieldsText]);

  const buildPayload = (): ProductCommercializationRequest => {
    if (parsedFields === null) {
      throw new Error('产品字段 JSON 格式不正确');
    }
    const executorId = videoProvider === 'vidu_viduq3_turbo' ? VIDU_EXECUTOR_ID : KIE_EXECUTOR_ID;
    return {
      productImageUrl: productImageUrl.trim() || undefined,
      productFields: parsedFields,
      extraPrompt: extraPrompt.trim() || undefined,
      outputLanguage,
      marketRegion,
      commercePlatform,
      copyTone,
      targetAudience: targetAudience.trim() || undefined,
      sellingAngle,
      forbiddenClaims: splitLines(forbiddenClaims),
      copyScenarios,
      visualSupportMode,
      videoScenario,
      aspectRatio,
      durationSeconds: SEGMENT_SECONDS,
      targetDurationSeconds,
      executorId,
      source: 'eval-product-commercialization',
      requestId: `eval-pc-${Date.now()}`,
    };
  };

  const runPreview = async () => {
    setError('');
    setStatus('previewing');
    try {
      const payload = buildPayload();
      const response = await evalApi.previewProductCommercialization(payload);
      setResult(response);
    } catch (err) {
      setError(String((err as any)?.message || err || '生成失败'));
    } finally {
      setStatus('idle');
    }
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

  const runVideo = async () => {
    setError('');
    if (!productImageUrl.trim()) {
      setError('生成视频必须先提供产品图 URL');
      return;
    }
    if (!canRunPaidAction) {
      setError('请先确认产品图与导出 JSON 属于同一商品，再触发视频成本动作');
      return;
    }
    setStatus('video');
    try {
      const payload = buildPayload();
      const submitted = await evalApi.submitProductCommercializationVideoRun(payload);
      const runId = String(submitted.runId || submitted.id || '').trim();
      if (!runId) {
        throw new Error('视频任务提交成功但未返回 runId');
      }
      activeVideoRunIdRef.current = runId;
      setVideoRun({ runId, status: String(submitted.status || 'queued'), elapsedSeconds: 0 });
      MessagePlugin.success(`视频任务已提交：${runId}`);
      await pollBusinessRun(runId, (poll, elapsedSeconds) => {
        if (activeVideoRunIdRef.current !== runId) return;
        const runStatus = String(poll.status || poll.taskStatus || 'running');
        setVideoRun({ runId, status: runStatus, elapsedSeconds });
        const fullResult = asProductCommercializationResponse(poll.resultPayload || poll.result);
        if (fullResult) {
          setResult(fullResult);
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

  const findModelImageBrief = (sceneId: string): Record<string, unknown> | null => {
    const briefs = asArray(asRecord(result?.contentPackage).imageBriefs).map((item) => asRecord(item));
    return briefs.find((item) => String(item.id || '').trim() === sceneId) || null;
  };

  const buildVisualDesignBrief = (scene: (typeof VISUAL_SCENES)[number]): string => {
    const copyPackage = asRecord(result?.copyPackage);
    const adCopy = formatCopyValue(copyPackage.adShortCopy).split('\n').slice(0, 2).join('；');
    const modelBrief = findModelImageBrief(scene.id);
    const modelPrompt = String(modelBrief?.prompt || '').trim();
    return [
      modelPrompt ? `大模型配图规划：${modelPrompt}` : '',
      `基于当前产品图生成一张${scene.label}。`,
      `商品：${productSummary.name}；分类：${productSummary.category}；材质：${productSummary.material}。`,
      `用途：${scene.desc}，目标市场：${marketRegion}。`,
      adCopy ? `可参考广告文案氛围：${adCopy}。` : '',
      '必须保持产品主体、花纹、颜色和结构一致；不要新增文字、水印、价格牌、Logo 或无关装饰元素。',
      extraPrompt.trim() ? `补充要求：${extraPrompt.trim()}` : '',
    ]
      .filter(Boolean)
      .join('\n');
  };

  const generateVisualScene = async (scene: (typeof VISUAL_SCENES)[number]) => {
    setError('');
    if (!productImageUrl.trim()) {
      setError('生成配图必须先提供产品图 URL');
      return;
    }
    if (visualSupportMode !== 'generate') {
      setError('请先把配图模式切换为“生成配图”，再触发图片成本动作');
      return;
    }
    if (!canRunPaidAction) {
      setError('请先确认产品图与导出 JSON 属于同一商品，再触发配图生成');
      return;
    }
    setStatus('visual');
    try {
      const payload: ProductDesignRunRequest = {
        imageUrl: productImageUrl.trim(),
        productType: inferProductType(parsedFields),
        designBrief: buildVisualDesignBrief(scene),
        scene: scene.scene,
        quality: 'preview',
        size: '1024x1024',
        output_format: 'png',
        source: 'eval-product-commercialization-visual',
        requestId: `eval-pc-visual-${scene.id}-${Date.now()}`,
        inputs: {
          productCommercializationScene: scene.id,
          productFields: parsedFields || {},
          marketRegion,
          outputLanguage,
        },
      };
      const submitted = await evalApi.submitProductDesignRun(payload);
      const runId = String(submitted.runId || submitted.id || '').trim();
      if (!runId) {
        throw new Error('配图任务提交成功但未返回 runId');
      }
      setGeneratedVisuals((prev) => [
        { id: scene.id, label: scene.label, runId, status: String(submitted.status || 'queued'), elapsedSeconds: 0, urls: [] },
        ...prev.filter((item) => item.id !== scene.id),
      ]);
      MessagePlugin.success(`配图任务已提交：${runId}`);
      const finalPoll = await pollBusinessRun(runId, (poll, elapsedSeconds) => {
        const runStatus = String(poll.status || poll.taskStatus || 'running');
        const urls = getRunImageUrls(poll);
        setGeneratedVisuals((prev) =>
          prev.map((item) => (item.runId === runId ? { ...item, status: runStatus, elapsedSeconds, urls } : item)),
        );
      });
      const urls = getRunImageUrls(finalPoll);
      if (urls.length === 0) {
        throw new Error('配图任务已完成但未返回图片 URL');
      }
      setGeneratedVisuals((prev) =>
        prev.map((item) => (item.runId === runId ? { ...item, status: 'succeeded', urls } : item)),
      );
    } catch (err) {
      const message = String((err as any)?.message || err || '配图生成失败');
      setError(message);
      setGeneratedVisuals((prev) =>
        prev.map((item) => (item.id === scene.id ? { ...item, status: 'failed', error: message } : item)),
      );
    } finally {
      setStatus('idle');
    }
  };

  const downloadContentPackage = () => {
    if (!result) return;
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
  const commercePositioning = asRecord(contentPackage.commercePositioning);
  const modelImageBriefs = asArray(contentPackage.imageBriefs).map((item) => asRecord(item));
  const channelUsageGuide = asArray(contentPackage.channelUsageGuide).map((item) => asRecord(item));
  const productCard = asRecord(result?.productCard);
  const visualAssetPlan = asRecord(result?.visualAssetPlan);
  const videoPlan = asRecord(result?.videoPlan);
  const review = asRecord(result?.review);
  const requiresComposition = targetDurationSeconds > SEGMENT_SECONDS;
  const selectedScenario = VIDEO_SCENARIOS.find((item) => item.key === videoScenario);

  return (
    <section className="podi-product-commercialization">
      <div className="podi-product-commercialization__head">
        <div>
          <Typography.Text theme="primary">v0.7 新能力试点 · 整改版</Typography.Text>
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
        theme="warning"
        message={
          isVideoMode
            ? '当前是测评入口：视频规划不扣成本；生成视频必须显式点击，并通过中台业务 runId 查询结果。'
            : '当前是测评入口：文案包应由大模型/VL 生成；模板兜底只用于排障，生成配图必须显式点击。'
        }
      />
      {error ? <Alert theme="error" message={error} /> : null}
      {videoRun ? (
        <Alert
          theme={videoRun.status === 'failed' ? 'error' : videoRun.status === 'succeeded' ? 'success' : 'info'}
          message={`视频任务 ${businessRunStatusLabel(videoRun.status)} · runId=${videoRun.runId} · 已等待 ${videoRun.elapsedSeconds}s`}
        />
      ) : null}

      <div className="podi-product-commercialization__grid">
        <div className="podi-product-commercialization__panel">
          <div className="podi-product-commercialization__panel-head">
            <Typography.Text strong>输入与核对</Typography.Text>
            <Typography.Text theme="secondary">{meta.inputHint}</Typography.Text>
          </div>

          <Space direction="vertical" size="medium" style={{ width: '100%' }}>
            <div className="podi-field-stack">
              <Typography.Text>产品图 URL</Typography.Text>
              <Space align="center">
                <Input value={productImageUrl} onChange={(v) => setProductImageUrl(String(v))} placeholder="https://..." clearable />
                <input
                  ref={uploadRef}
                  type="file"
                  accept="image/*"
                  style={{ display: 'none' }}
                  onChange={(event) => void uploadProductImage(event.currentTarget.files?.[0])}
                />
                <Button variant="outline" loading={status === 'uploading'} onClick={() => uploadRef.current?.click()}>
                  上传
                </Button>
              </Space>
            </div>

            {productImageUrl ? (
              <div className="podi-product-commercialization__image">
                <img src={productImageUrl} alt="产品图预览" />
              </div>
            ) : null}

            <div className="podi-field-stack">
              <div className="podi-product-commercialization__panel-head">
                <Typography.Text>产品导出字段 JSON</Typography.Text>
                <Typography.Text theme={parsedFields === null ? 'error' : 'secondary'}>
                  {parsedFields === null ? 'JSON 格式错误' : `${Object.keys(parsedFields).length} 个字段`}
                </Typography.Text>
              </div>
              <Textarea
                value={productFieldsText}
                onChange={(v) => setProductFieldsText(String(v))}
                autosize={{ minRows: 12, maxRows: 22 }}
                status={parsedFields === null ? 'error' : 'default'}
              />
            </div>

            <div className="podi-product-commercialization__field-check">
              <div>
                <Typography.Text strong>图片 / 字段核对</Typography.Text>
                <Typography.Text theme="secondary">
                  {shouldConfirmMatch ? '生成图片或视频前必须确认，避免错误商品字段触发成本动作。' : '提供产品图和字段后会显示确认项。'}
                </Typography.Text>
              </div>
              <div className="podi-product-commercialization__facts">
                <span>商品：{productSummary.name}</span>
                <span>分类：{productSummary.category}</span>
                <span>材质：{productSummary.material}</span>
                <span>型号：{productSummary.model}</span>
              </div>
              <label className="podi-product-commercialization__confirm">
                <input
                  type="checkbox"
                  checked={fieldsConfirmed}
                  disabled={!shouldConfirmMatch}
                  onChange={(event) => setFieldsConfirmed(event.currentTarget.checked)}
                />
                <span>我确认当前图片与导出 JSON 属于同一商品；如果是乱填测试，我知道生成结果可能不可靠。</span>
              </label>
            </div>

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
                  <Select
                    label="平台"
                    value={commercePlatform}
                    onChange={(v) => setCommercePlatform(String(v))}
                    options={COMMERCE_PLATFORM_OPTIONS}
                  />
                  <Select
                    label="语气"
                    value={copyTone}
                    onChange={(v) => setCopyTone(String(v))}
                    options={COPY_TONE_OPTIONS}
                  />
                  <Select
                    label="主打角度"
                    value={sellingAngle}
                    onChange={(v) => setSellingAngle(String(v))}
                    options={SELLING_ANGLE_OPTIONS}
                  />
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
                  <Select
                    label="目标时长"
                    value={String(targetDurationSeconds)}
                    onChange={(v) => setTargetDurationSeconds(Number(v) || SEGMENT_SECONDS)}
                    options={[8, 16, 24, 32, 48, 60].map((seconds) => ({
                      label: seconds === 8 ? '8 秒 · 单段' : `${seconds} 秒 · 多段合成`,
                      value: String(seconds),
                    }))}
                  />
                </>
              )}
              {isVideoMode ? <Input label="比例" value={aspectRatio} onChange={(v) => setAspectRatio(String(v))} /> : null}
            </div>

            {!isVideoMode ? (
              <>
                <div className="podi-product-commercialization__strategy">
                  <Input
                    label="目标人群"
                    value={targetAudience}
                    onChange={(v) => setTargetAudience(String(v))}
                    placeholder="例如：美国礼品买家、日常穿搭人群、季节上新受众"
                  />
                  <div className="podi-field-stack">
                    <Typography.Text>禁用声明</Typography.Text>
                    <Textarea
                      value={forbiddenClaims}
                      onChange={(v) => setForbiddenClaims(String(v))}
                      placeholder="用逗号或换行分隔，例如：医疗功效、环保认证、品牌词、物流时效承诺"
                      autosize={{ minRows: 2, maxRows: 4 }}
                    />
                  </div>
                </div>
                <div className="podi-field-stack">
                  <Typography.Text>文案应用场景</Typography.Text>
                  <div className="podi-product-commercialization__chips" aria-label="文案场景">
                    {COPY_SCENARIOS.map((item) => (
                      <button
                        key={item.key}
                        type="button"
                        className={copyScenarios.includes(item.key) ? 'is-active' : ''}
                        onClick={() => toggleScenario(item.key)}
                      >
                        <strong>{item.label}</strong>
                        <small>{item.desc}</small>
                      </button>
                    ))}
                  </div>
                </div>
              </>
            ) : (
              <div className="podi-field-stack">
                <Typography.Text>视频应用场景</Typography.Text>
                <div className="podi-product-commercialization__chips" aria-label="视频场景">
                  {VIDEO_SCENARIOS.map((item) => (
                    <button
                      key={item.key}
                      type="button"
                      className={videoScenario === item.key ? 'is-active' : ''}
                      onClick={() => setVideoScenario(item.key as any)}
                    >
                      <strong>{item.label}</strong>
                      <small>{item.desc}</small>
                    </button>
                  ))}
                </div>
                <div className="podi-product-commercialization__pending">
                  <Typography.Text theme="secondary">当前可执行视频模型</Typography.Text>
                  <Space size="small" breakLine>
                    <Tag theme="success" variant="light">
                      Vidu · viduq3-turbo
                    </Tag>
                    <Tag theme="success" variant="light">
                      KIE · Veo3.1 Fast
                    </Tag>
                  </Space>
                  <Typography.Text theme="secondary">当前可选时长</Typography.Text>
                  <Space size="small" breakLine>
                    {[8, 16, 24, 32, 48, 60].map((seconds) => (
                      <Tag key={seconds} theme={seconds === 8 ? 'primary' : 'success'} variant="light">
                        {seconds === 8 ? '8 秒单段' : `${seconds} 秒多段合成`}
                      </Tag>
                    ))}
                  </Space>
                  <Typography.Text theme="secondary">待接入 Vidu 场景</Typography.Text>
                  <Space size="small" breakLine>
                    {PENDING_VIDEO_ROUTES.map((item) => (
                      <Tag key={item} theme="warning" variant="light">
                        {item}
                      </Tag>
                    ))}
                  </Space>
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
              <Button theme="primary" loading={status === 'previewing'} disabled={copyScenarios.length === 0} onClick={() => void runPreview()}>
                {meta.previewButton}
              </Button>
              {!isVideoMode && result ? (
                <Button variant="outline" disabled={visualSupportMode !== 'generate' || !canRunPaidAction} onClick={() => void generateVisualScene(VISUAL_SCENES[1])}>
                  生成一张配图
                </Button>
              ) : null}
              {isVideoMode ? (
                <Button theme="success" loading={status === 'video'} disabled={!canRunPaidAction} onClick={() => void runVideo()}>
                  {requiresComposition ? `生成 ${targetDurationSeconds}s 多段视频` : `生成 ${videoProviderLabel(videoProvider)} 视频`}
                </Button>
              ) : null}
            </Space>
          </Space>
        </div>

        <div className="podi-product-commercialization__panel podi-product-commercialization__result">
          <div className="podi-product-commercialization__panel-head">
            <Typography.Text strong>输出与交付</Typography.Text>
            <Space size="small">
              {result ? (
                <Button size="small" variant="outline" onClick={downloadContentPackage}>
                  下载图文包
                </Button>
              ) : null}
            </Space>
          </div>

          {!result ? (
            <div className="podi-product-commercialization__empty">
              <Typography.Text theme="secondary">{meta.emptyText}</Typography.Text>
            </div>
          ) : (
            <Space direction="vertical" size="medium" style={{ width: '100%' }}>
              <section className="podi-result-section">
                <Typography.Text strong>产品理解</Typography.Text>
                <div className="podi-product-commercialization__facts">
                  <span>置信度 {String((productCard.confidence as any) ?? '-')}</span>
                  <span>缺失 {asArray(productCard.missingFields).length} 项</span>
                  <span>推断 {Object.keys(asRecord(productCard.inferredFacts)).length} 项</span>
                  <span>配图策略 {String(visualAssetPlan.mode || visualSupportMode)}</span>
                </div>
                {asArray(productCard.missingFields).length > 0 ? (
                  <Alert theme="warning" message={`字段缺失：${asArray(productCard.missingFields).join('、')}`} />
                ) : null}
              </section>

              {!isVideoMode ? (
                <>
                  <section className="podi-result-section">
                    <div className="podi-product-commercialization__panel-head">
                      <Typography.Text strong>模型生成证据</Typography.Text>
                      <Tag theme={themeForGeneration(copyGeneration.method)} variant="light">
                        {copyGenerationLabel(copyGeneration.method)}
                      </Tag>
                    </div>
                    <div className="podi-product-commercialization__facts">
                      <span>provider {String(copyGeneration.provider || '-')}</span>
                      <span>model {String(copyGeneration.model || '-')}</span>
                      <span>fallback {String(copyGeneration.fallback ?? '-')}</span>
                    </div>
                    {String(copyGeneration.method || '') === 'template_fallback' ? (
                      <Alert
                        theme="error"
                        message="当前是模板兜底，没有通过大模型/VL 生成；只能用于排障，不能作为文案能力验收通过。"
                      />
                    ) : (
                      <Alert theme="success" message={String(copyGeneration.evidence || '已返回结构化电商文案内容包。')} />
                    )}
                  </section>

                  <section className="podi-result-section">
                    <Typography.Text strong>商家内容策略</Typography.Text>
                    <div className="podi-product-commercialization__strategy-summary">
                      <div>
                        <Typography.Text theme="secondary">核心角度</Typography.Text>
                        <Typography.Text>{String(commercePositioning.coreAngle || '-')}</Typography.Text>
                      </div>
                      <div>
                        <Typography.Text theme="secondary">目标人群</Typography.Text>
                        <Typography.Text>{formatCopyValue(commercePositioning.targetCustomers || [])}</Typography.Text>
                      </div>
                      <div>
                        <Typography.Text theme="secondary">购买场景</Typography.Text>
                        <Typography.Text>{formatCopyValue(commercePositioning.purchaseOccasions || [])}</Typography.Text>
                      </div>
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

                  {visualSupportMode !== 'none' ? (
                    <section className="podi-result-section">
                      <div className="podi-product-commercialization__panel-head">
                        <Typography.Text strong>配图建议与生成</Typography.Text>
                        <Typography.Text theme="secondary">
                          {visualSupportMode === 'generate' ? '建议来自文案模型；点击后调用产品设计能力生成图片' : '当前只输出配图建议'}
                        </Typography.Text>
                      </div>
                      {modelImageBriefs.length > 0 ? (
                        <div className="podi-product-commercialization__briefs">
                          {modelImageBriefs.map((brief, index) => (
                            <div key={`${brief.id || index}`} className="podi-product-commercialization__brief">
                              <Typography.Text strong>{String(brief.label || brief.id || `配图 ${index + 1}`)}</Typography.Text>
                              <Typography.Text theme="secondary">{String(brief.usage || '')}</Typography.Text>
                              <pre>{String(brief.prompt || '')}</pre>
                            </div>
                          ))}
                        </div>
                      ) : null}
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
                                <Typography.Text theme={visual.status === 'failed' ? 'error' : 'secondary'}>
                                  {businessRunStatusLabel(visual.status)} · runId={visual.runId}
                                </Typography.Text>
                              ) : (
                                <Typography.Text theme="secondary">尚未生成</Typography.Text>
                              )}
                              {visual?.error ? <Typography.Text theme="error">{visual.error}</Typography.Text> : null}
                              <Button
                                size="small"
                                variant="outline"
                                loading={status === 'visual'}
                                disabled={visualSupportMode !== 'generate' || !canRunPaidAction}
                                onClick={() => void generateVisualScene(scene)}
                              >
                                生成{label}
                              </Button>
                            </div>
                          );
                        })}
                      </div>
                    </section>
                  ) : null}

                  {channelUsageGuide.length > 0 ? (
                    <section className="podi-result-section">
                      <Typography.Text strong>渠道使用建议</Typography.Text>
                      <div className="podi-product-commercialization__channel-list">
                        {channelUsageGuide.map((item, index) => (
                          <div key={`${item.channel || index}`}>
                            <Typography.Text strong>{String(item.channel || `渠道 ${index + 1}`)}</Typography.Text>
                            <Typography.Text>{String(item.howToUse || '')}</Typography.Text>
                            <Typography.Text theme="secondary">资产：{formatCopyValue(item.assets || [])}</Typography.Text>
                          </div>
                        ))}
                      </div>
                    </section>
                  ) : null}
                </>
              ) : (
                <section className="podi-result-section">
                  <Typography.Text strong>视频规划</Typography.Text>
                  <div className="podi-product-commercialization__facts">
                    <span>{videoProviderLabel(videoProvider)}</span>
                    <span>{selectedScenario?.label || videoScenario}</span>
                    <span>{targetDurationSeconds}s</span>
                    <span>{aspectRatio}</span>
                  </div>
                  <pre>{prettyJson(videoPlan)}</pre>
                </section>
              )}

              {videoUrls.length > 0 ? (
                <section className="podi-result-section">
                  <Typography.Text strong>视频结果</Typography.Text>
                  {videoUrls.map((url, index) => (
                    <div key={`${url}-${index}`} className="podi-product-commercialization__video">
                      <video src={url} controls />
                      <Button variant="outline" onClick={() => window.open(url, '_blank', 'noreferrer')}>
                        打开视频
                      </Button>
                    </div>
                  ))}
                </section>
              ) : null}

              <section className="podi-result-section">
                <Typography.Text strong>审核与下一步</Typography.Text>
                <div className="podi-product-commercialization__review">
                  <div className="podi-product-commercialization__facts">
                    <span>审核分 {String(review.score ?? '-')}</span>
                    <span>提示 {asArray(review.issues).length}</span>
                    <span>{review.videoReady ? '可联动产品视频' : '需补齐视频素材'}</span>
                  </div>
                  <div className="podi-product-commercialization__review-grid">
                    <div>
                      <Typography.Text theme="secondary">审核提示</Typography.Text>
                      <div className="podi-product-commercialization__review-list">
                        {asArray(review.issues).length > 0 ? (
                          asArray(review.issues).map((item, index) => {
                            const issue = asRecord(item);
                            return (
                              <div key={`${String(issue.code || 'issue')}-${index}`}>
                                <Tag theme={getReviewIssueTheme(issue.level)} variant="light">
                                  {getReviewIssueLabel(issue.level)}
                                </Tag>
                                <div>
                                  <strong>{String(issue.code || '审核提示')}</strong>
                                  <p>{String(issue.message || '请核对商品事实后再发布。')}</p>
                                </div>
                              </div>
                            );
                          })
                        ) : (
                          <div>
                            <Tag theme="success" variant="light">通过</Tag>
                            <div>
                              <strong>暂无阻断项</strong>
                              <p>仍需人工核对商品事实、平台规则和禁用声明。</p>
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                    <div>
                      <Typography.Text theme="secondary">下一步</Typography.Text>
                      <ol className="podi-product-commercialization__next-list">
                        {(asArray(review.nextActions).map((item) => String(item || '').trim()).filter(Boolean).length > 0
                          ? asArray(review.nextActions).map((item) => String(item || '').trim()).filter(Boolean)
                          : ['核对事实后复制文案，按需要生成配图；视频请进入产品视频能力。']
                        ).map((item, index) => (
                          <li key={`${item}-${index}`}>{item}</li>
                        ))}
                      </ol>
                    </div>
                  </div>
                </div>
              </section>
            </Space>
          )}
        </div>
      </div>
    </section>
  );
}
