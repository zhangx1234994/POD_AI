import { useMemo, useRef, useState } from 'react';
import { Alert, Button, Input, Select, Space, Tag, Textarea, Typography, MessagePlugin } from 'tdesign-react';
import { evalApi } from '../../api';
import type { ProductCommercializationRequest, ProductCommercializationResponse } from '../../api';

const DEFAULT_PRODUCT_FIELDS = {
  模板名称: '女款长袜（3D打印）',
  英文名称: "Women's knitted woolen socks",
  产品材质: '包纱、涤纶、尼龙、橡筋',
  生产工艺: '3D印花',
  具体成分: '65%涤纶，15%氨纶，20%尼龙',
  二级分类: '穿搭配件',
  建议售价: '10',
};

const COPY_SCENARIOS = [
  { key: 'listing_title', label: '商品标题' },
  { key: 'bullet_points', label: '五点描述' },
  { key: 'detail_description', label: '详情描述' },
  { key: 'ad_short_copy', label: '广告短文案' },
  { key: 'keyword_pack', label: '关键词包' },
];

type ProductCommercializationMode = 'copy' | 'video';

const MODE_COPY: ProductCommercializationMode = 'copy';
const MODE_VIDEO: ProductCommercializationMode = 'video';

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
    subtitle: '产品设计完成后，生成海外上架文案、配图建议、关键词和审核提示。',
    inputHint: '字段缺失不阻塞，系统会标记推断和缺项。',
    outputHint: '只生成文案与配图建议，不触发视频成本动作。',
    emptyText: '先生成一次文案内容包，检查字段理解、语言、市场和配图策略。',
    previewButton: '生成文案与配图建议',
    tags: [
      { label: '上架文案', theme: 'primary' },
      { label: '配图建议', theme: 'success' },
      { label: '多语言', theme: 'warning' },
    ],
  },
  video: {
    title: '产品视频生成',
    subtitle: '产品设计完成后，先生成视频分镜，再显式调用 Veo Fast 生成商品展示视频。',
    inputHint: '产品图是必填素材；字段用于约束视频提示词。',
    outputHint: '预览只生成分镜；点击视频按钮才会触发 Veo Fast 成本动作。',
    emptyText: '先生成一次视频分镜，确认商品图、市场、比例和素材需求，再生成视频。',
    previewButton: '生成视频分镜',
    tags: [
      { label: '视频分镜', theme: 'primary' },
      { label: 'Veo Fast', theme: 'success' },
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

function delay(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function getNestedString(payload: Record<string, unknown> | null | undefined, key: string): string {
  const value = payload?.[key];
  return typeof value === 'string' ? value : '';
}

function getVideoUrls(result: ProductCommercializationResponse | null): string[] {
  const videoResult = result?.videoResult;
  if (!videoResult || typeof videoResult !== 'object') return [];
  const urls = (videoResult as Record<string, unknown>).videoUrls;
  return Array.isArray(urls) ? urls.filter((item): item is string => typeof item === 'string' && item.length > 0) : [];
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

export function ProductCommercializationWorkbench({ mode = MODE_COPY }: { mode?: ProductCommercializationMode }) {
  const meta = MODE_META[mode] || MODE_META.copy;
  const isVideoMode = mode === MODE_VIDEO;
  const [productImageUrl, setProductImageUrl] = useState('');
  const [productFieldsText, setProductFieldsText] = useState(prettyJson(DEFAULT_PRODUCT_FIELDS));
  const [extraPrompt, setExtraPrompt] = useState('');
  const [outputLanguage, setOutputLanguage] = useState<'en-US' | 'zh-CN' | 'bilingual'>('en-US');
  const [marketRegion, setMarketRegion] = useState<'US' | 'UK' | 'EU' | 'global'>('US');
  const [visualSupportMode, setVisualSupportMode] = useState<'none' | 'recommendation' | 'generate'>('recommendation');
  const [videoScenario, setVideoScenario] = useState<'product_showcase_short' | 'social_ad_short' | 'detail_explainer'>('product_showcase_short');
  const [aspectRatio, setAspectRatio] = useState('16:9');
  const durationSeconds = 8;
  const [targetDurationSeconds, setTargetDurationSeconds] = useState(8);
  const [copyScenarios, setCopyScenarios] = useState<string[]>(COPY_SCENARIOS.map((item) => item.key));
  const [result, setResult] = useState<ProductCommercializationResponse | null>(null);
  const [status, setStatus] = useState<'idle' | 'previewing' | 'video' | 'uploading'>('idle');
  const [error, setError] = useState('');
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

  const buildPayload = (): ProductCommercializationRequest => {
    if (parsedFields === null) {
      throw new Error('产品字段 JSON 格式不正确');
    }
    return {
      productImageUrl: productImageUrl.trim() || undefined,
      productFields: parsedFields,
      extraPrompt: extraPrompt.trim() || undefined,
      outputLanguage,
      marketRegion,
      copyScenarios,
      visualSupportMode,
      videoScenario,
      aspectRatio,
      durationSeconds,
      targetDurationSeconds,
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

  const pollProductVideoRun = async (runId: string) => {
    let retryAfterSeconds = 3;
    const startedAt = Date.now();
    for (let attempt = 0; attempt < 180; attempt += 1) {
      if (attempt > 0) {
        await delay(Math.max(2, Math.min(15, retryAfterSeconds)) * 1000);
      }
      const poll = await evalApi.getBusinessRun(runId, 'full');
      if (activeVideoRunIdRef.current !== runId) return;
      const runStatus = String(poll.status || poll.taskStatus || 'running');
      retryAfterSeconds = Number(poll.retryAfterSeconds || 5);
      setVideoRun({
        runId,
        status: runStatus,
        elapsedSeconds: Math.max(0, Math.round((Date.now() - startedAt) / 1000)),
      });

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

      if (runStatus === 'succeeded') return;
      if (runStatus === 'failed' || runStatus === 'cancelled') {
        throw new Error(String(poll.errorMessage || poll.error || poll.debugResponse || `视频任务${businessRunStatusLabel(runStatus)}`));
      }
    }
    throw new Error('视频任务轮询超时，请复制 runId 到任务追踪继续排查');
  };

  const runVideo = async () => {
    setError('');
    if (!productImageUrl.trim()) {
      setError('生成视频必须先提供产品图 URL');
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
      await pollProductVideoRun(runId);
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

  const copyPackage = result?.copyPackage || null;
  const productCard = result?.productCard || null;
  const visualAssetPlan = result?.visualAssetPlan || null;
  const videoPlan = result?.videoPlan || null;
  const review = result?.review || null;
  const videoUrls = getVideoUrls(result);
  const requiresComposition = targetDurationSeconds > durationSeconds;

  return (
    <section className="podi-product-commercialization">
      <div className="podi-product-commercialization__head">
        <div>
          <Typography.Text theme="primary">v0.7 新能力试点</Typography.Text>
          <Typography.Title level="h3" style={{ margin: '4px 0' }}>
            {meta.title}
          </Typography.Title>
          <Typography.Text theme="secondary">
            {meta.subtitle}
          </Typography.Text>
        </div>
        <Space align="center">
          {meta.tags.map((tag) => (
            <Tag key={tag.label} theme={tag.theme} variant="light">
              {tag.label}
            </Tag>
          ))}
        </Space>
      </div>

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
            <Typography.Text strong>输入</Typography.Text>
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
              <Typography.Text>产品导出字段 JSON</Typography.Text>
              <Textarea
                value={productFieldsText}
                onChange={(v) => setProductFieldsText(String(v))}
                autosize={{ minRows: 8, maxRows: 14 }}
                status={parsedFields === null ? 'error' : 'default'}
              />
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
              <Select
                label="配图"
                value={visualSupportMode}
                onChange={(v) => setVisualSupportMode(String(v) as any)}
                disabled={isVideoMode}
                options={[
                  { label: '只给建议', value: 'recommendation' },
                  { label: '不需要配图', value: 'none' },
                  { label: '建议生成', value: 'generate' },
                ]}
              />
              {isVideoMode ? (
                <>
                  <Select
                    label="视频"
                    value={videoScenario}
                    onChange={(v) => setVideoScenario(String(v) as any)}
                    options={[
                      { label: '商品展示短视频', value: 'product_showcase_short' },
                      { label: '社媒广告短视频', value: 'social_ad_short' },
                      { label: '详情讲解短视频', value: 'detail_explainer' },
                    ]}
                  />
                  <Input label="比例" value={aspectRatio} onChange={(v) => setAspectRatio(String(v))} />
                  <Input label="Veo 单段" value="8 秒" disabled />
                  <Input
                    label="目标成片"
                    value={String(targetDurationSeconds)}
                    onChange={(v) => {
                      const nextValue = Number(v);
                      setTargetDurationSeconds(Math.max(8, Math.min(60, Number.isFinite(nextValue) ? nextValue : 8)));
                    }}
                  />
                </>
              ) : null}
            </div>
            {!isVideoMode ? (
              <div className="podi-product-commercialization__chips" aria-label="文案场景">
                {COPY_SCENARIOS.map((item) => (
                  <button
                    key={item.key}
                    type="button"
                    className={copyScenarios.includes(item.key) ? 'is-active' : ''}
                    onClick={() => toggleScenario(item.key)}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            ) : null}
            <div className="podi-field-stack">
              <Typography.Text>补充要求</Typography.Text>
              <Textarea
                value={extraPrompt}
                onChange={(v) => setExtraPrompt(String(v))}
                placeholder={isVideoMode ? '例如：突出材质纹理和商品轮廓，不要出现文字和水印。' : '例如：偏节日礼品场景，避免夸张承诺。'}
                autosize={{ minRows: 3, maxRows: 6 }}
              />
            </div>
            <Space>
              <Button theme="primary" loading={status === 'previewing'} disabled={copyScenarios.length === 0} onClick={() => void runPreview()}>
                {meta.previewButton}
              </Button>
              {isVideoMode ? (
                <Button
                  theme="success"
                  loading={status === 'video'}
                  disabled={!productImageUrl.trim()}
                  onClick={() => void runVideo()}
                >
                  {requiresComposition ? '生成并合成长视频' : '生成 Veo Fast 视频'}
                </Button>
              ) : null}
            </Space>
          </Space>
        </div>

        <div className="podi-product-commercialization__panel podi-product-commercialization__result">
          <div className="podi-product-commercialization__panel-head">
            <Typography.Text strong>输出</Typography.Text>
            <Typography.Text theme="secondary">{meta.outputHint}</Typography.Text>
          </div>
          {!result ? (
            <div className="podi-product-commercialization__empty">
              <Typography.Text theme="secondary">{meta.emptyText}</Typography.Text>
            </div>
          ) : (
            <Space direction="vertical" size="medium" style={{ width: '100%' }}>
              <section className="podi-result-section">
                <Typography.Text strong>产品理解卡</Typography.Text>
                <div className="podi-product-commercialization__facts">
                  <span>置信度 {String((productCard?.confidence as any) ?? '-')}</span>
                  <span>缺失 {asArray(productCard?.missingFields).length} 项</span>
                  <span>推断 {Object.keys((productCard?.inferredFacts as Record<string, unknown>) || {}).length} 项</span>
                </div>
                <pre>{prettyJson(productCard)}</pre>
              </section>
              {!isVideoMode ? (
                <>
                  <section className="podi-result-section">
                    <Typography.Text strong>文案包</Typography.Text>
                    <pre>{prettyJson(copyPackage)}</pre>
                  </section>
                  <section className="podi-result-section">
                    <Typography.Text strong>配图建议</Typography.Text>
                    <pre>{prettyJson(visualAssetPlan)}</pre>
                  </section>
                </>
              ) : (
                <section className="podi-result-section">
                  <Typography.Text strong>视频分镜</Typography.Text>
                  <Typography.Text theme="secondary">{getNestedString(videoPlan, 'videoPrompt')}</Typography.Text>
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
                <pre>{prettyJson(review)}</pre>
              </section>
            </Space>
          )}
        </div>
      </div>
    </section>
  );
}
