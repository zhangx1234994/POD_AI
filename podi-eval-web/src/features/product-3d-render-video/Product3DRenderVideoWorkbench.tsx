import { useMemo, useRef, useState } from 'react';
import { Alert, Button, Input, Select, Space, Tag, Textarea, Typography, MessagePlugin } from 'tdesign-react';
import { evalApi } from '../../api';
import type { Product3DRenderVideoRequest, Product3DRenderVideoResponse } from '../../api';

type WorkStatus = 'idle' | 'uploading' | 'previewing';

const MODEL_OPTIONS = [
  { label: '1660 杯子', value: 'cup_1660' },
  { label: '2551 笔记本电脑背包', value: 'backpack_2551' },
];

const MATERIAL_SLOTS: Record<string, string[]> = {
  cup_1660: ['front', 'mouth', 'cover', 'bottom', 'handshank', 'else', 'else1'],
  backpack_2551: [
    'front',
    'bottom',
    'back',
    'top',
    'left',
    'right',
    'sideleft',
    'sideright',
    'qitaDZ',
    'qitaBD',
    'zipper',
    'zipper02',
    'zipperB',
    'qitaSL',
    'stitch',
    'qitaWGBB',
    'qitaWG',
    'qitaWG001',
    'inside',
  ],
};

const CAMERA_OPTIONS = [
  { label: '360 环绕', value: 'orbit_360' },
  { label: '慢速推进', value: 'slow_push_in' },
  { label: '细节扫过', value: 'detail_sweep' },
];

const SCENE_OPTIONS = [
  { label: '干净摄影棚', value: 'clean_studio' },
  { label: '电商白底', value: 'marketplace_white' },
  { label: '深色质感棚', value: 'premium_dark' },
];

const DURATION_OPTIONS = [3, 5, 6, 8, 12].map((seconds) => ({ label: `${seconds} 秒`, value: String(seconds) }));

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function splitLines(value: string): string[] {
  return value
    .split(/[\n,，;；|]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

export function Product3DRenderVideoWorkbench() {
  const uploadRef = useRef<HTMLInputElement | null>(null);
  const [modelKey, setModelKey] = useState<'cup_1660' | 'backpack_2551'>('cup_1660');
  const [textureImageUrl, setTextureImageUrl] = useState('');
  const [textureImageUrlsText, setTextureImageUrlsText] = useState('');
  const [materialSlot, setMaterialSlot] = useState('front');
  const [cameraPreset, setCameraPreset] = useState<'orbit_360' | 'slow_push_in' | 'detail_sweep'>('orbit_360');
  const [scenePreset, setScenePreset] = useState<'clean_studio' | 'marketplace_white' | 'premium_dark'>('clean_studio');
  const [durationSeconds, setDurationSeconds] = useState(6);
  const [aspectRatio, setAspectRatio] = useState('16:9');
  const [extraPrompt, setExtraPrompt] = useState('');
  const [result, setResult] = useState<Product3DRenderVideoResponse | null>(null);
  const [status, setStatus] = useState<WorkStatus>('idle');
  const [error, setError] = useState('');

  const materialOptions = useMemo(
    () => (MATERIAL_SLOTS[modelKey] || ['front']).map((slot) => ({ label: slot, value: slot })),
    [modelKey],
  );

  const textureImageUrls = useMemo(() => {
    const urls = splitLines(textureImageUrlsText);
    if (textureImageUrl.trim() && !urls.includes(textureImageUrl.trim())) urls.unshift(textureImageUrl.trim());
    return urls.slice(0, 6);
  }, [textureImageUrl, textureImageUrlsText]);

  const uploadTexture = async (file: File | null | undefined) => {
    if (!file) return;
    setError('');
    setStatus('uploading');
    try {
      const uploaded = await evalApi.uploadImage(file);
      setTextureImageUrl(uploaded.url);
      MessagePlugin.success('贴图已上传');
    } catch (err) {
      setError(String((err as any)?.message || err || '上传失败'));
    } finally {
      setStatus('idle');
      if (uploadRef.current) uploadRef.current.value = '';
    }
  };

  const previewPlan = async () => {
    setError('');
    setStatus('previewing');
    try {
      const payload: Product3DRenderVideoRequest = {
        modelKey,
        textureImageUrl: textureImageUrl.trim() || undefined,
        textureImageUrls,
        materialSlot,
        cameraPreset,
        scenePreset,
        durationSeconds,
        aspectRatio,
        outputMode: 'plan_only',
        extraPrompt: extraPrompt.trim() || undefined,
        source: 'eval-product-3d-render-video',
        requestId: `eval-p3d-${Date.now()}`,
      };
      const response = await evalApi.previewProduct3DRenderVideo(payload);
      setResult(response);
    } catch (err) {
      setError(String((err as any)?.message || err || '方案预览失败'));
    } finally {
      setStatus('idle');
    }
  };

  const model = asRecord(result?.model);
  const readiness = asRecord(result?.assetReadiness);
  const renderPlan = asRecord(result?.renderPlan);
  const camera = asRecord(renderPlan.camera);
  const scene = asRecord(renderPlan.scene);
  const review = asRecord(result?.review);
  const issues = asArray(review.issues).map((item) => asRecord(item));

  return (
    <section className="podi-product-commercialization podi-product-3d-render">
      <div className="podi-product-commercialization__head">
        <div>
          <Typography.Text theme="primary">3D 渲染视频能力</Typography.Text>
          <Typography.Title level="h3" style={{ margin: '4px 0' }}>
            3D 模型贴图与镜头方案
          </Typography.Title>
          <Typography.Text theme="secondary">不用 KIE/Vidu 生视频；通过 3D 模型、贴图、场景和相机路径产出可控商品动效。</Typography.Text>
        </div>
        <Space align="center">
          <Tag theme="primary" variant="light">独立能力</Tag>
          <Tag theme="success" variant="light">Three.js / Blender</Tag>
          <Tag theme="warning" variant="light">预览阶段</Tag>
        </Space>
      </div>

      {error ? <Alert theme="error" message={error} /> : null}
      <Alert theme="info" message="当前只生成渲染方案和资产准备度，不触发成本动作，也不会返回 MP4。真实渲染 worker 接入后再开放异步任务。" />

      <div className="podi-product-commercialization__studio">
        <main className="podi-product-commercialization__stage-main">
          <section className="podi-product-commercialization__stage-panel">
            <div className="podi-product-commercialization__stage-title">
              <span>STEP 1</span>
              <Typography.Title level="h4">选择模型与贴图</Typography.Title>
              <Typography.Text theme="secondary">先验证模型、材质槽、UV 和贴图输入，不急于生成视频。</Typography.Text>
            </div>
            <div className="podi-product-commercialization__strategy-workbench">
              <div className="podi-product-commercialization__controls">
                <Select
                  label="3D 模型"
                  value={modelKey}
                  onChange={(v) => {
                    const key = String(v) as 'cup_1660' | 'backpack_2551';
                    setModelKey(key);
                    setMaterialSlot('front');
                  }}
                  options={MODEL_OPTIONS}
                />
                <Select label="贴图材质槽" value={materialSlot} onChange={(v) => setMaterialSlot(String(v))} options={materialOptions} />
                <Select label="镜头预设" value={cameraPreset} onChange={(v) => setCameraPreset(String(v) as any)} options={CAMERA_OPTIONS} />
                <Select label="场景预设" value={scenePreset} onChange={(v) => setScenePreset(String(v) as any)} options={SCENE_OPTIONS} />
                <Select
                  label="时长"
                  value={String(durationSeconds)}
                  onChange={(v) => setDurationSeconds(Number(v) || 6)}
                  options={DURATION_OPTIONS}
                />
                <Input label="比例" value={aspectRatio} onChange={(v) => setAspectRatio(String(v))} />
              </div>
              <div className="podi-field-stack">
                <Typography.Text>贴图 URL</Typography.Text>
                <Space align="center">
                  <Input value={textureImageUrl} onChange={(v) => setTextureImageUrl(String(v))} placeholder="https://..." clearable />
                  <input
                    ref={uploadRef}
                    type="file"
                    accept="image/*"
                    style={{ display: 'none' }}
                    onChange={(event) => void uploadTexture(event.currentTarget.files?.[0])}
                  />
                  <Button variant="outline" loading={status === 'uploading'} onClick={() => uploadRef.current?.click()}>
                    上传
                  </Button>
                </Space>
              </div>
              <div className="podi-field-stack">
                <Typography.Text>更多贴图 URL（可选）</Typography.Text>
                <Textarea
                  value={textureImageUrlsText}
                  onChange={(v) => setTextureImageUrlsText(String(v))}
                  placeholder="每行一个 URL；后续用于多面/多材质贴图。"
                  autosize={{ minRows: 3, maxRows: 6 }}
                />
              </div>
              <div className="podi-field-stack">
                <Typography.Text>补充镜头要求</Typography.Text>
                <Textarea
                  value={extraPrompt}
                  onChange={(v) => setExtraPrompt(String(v))}
                  placeholder="例如：杯子慢速转一圈，开头给正面花纹，结尾停在把手侧。"
                  autosize={{ minRows: 3, maxRows: 6 }}
                />
              </div>
              <Button theme="primary" loading={status === 'previewing'} onClick={() => void previewPlan()}>
                生成 3D 渲染方案
              </Button>
            </div>
          </section>

          <section className="podi-product-commercialization__stage-panel">
            <div className="podi-product-commercialization__stage-title">
              <span>STEP 2</span>
              <Typography.Title level="h4">方案与可执行度</Typography.Title>
              <Typography.Text theme="secondary">这里确认模型资产和渲染管线，不把计划当成视频结果。</Typography.Text>
            </div>
            {!result ? (
              <div className="podi-product-commercialization__empty">
                <Typography.Text theme="secondary">还没有方案。请选择模型和贴图后生成预览。</Typography.Text>
              </div>
            ) : (
              <Space direction="vertical" size="medium" style={{ width: '100%' }}>
                <div className="podi-product-commercialization__strategy-summary">
                  <div>
                    <Typography.Text theme="secondary">模型</Typography.Text>
                    <Typography.Text>{String(model.displayName || modelKey)}</Typography.Text>
                  </div>
                  <div>
                    <Typography.Text theme="secondary">准备度</Typography.Text>
                    <Typography.Text>{String(readiness.score ?? '-')}</Typography.Text>
                  </div>
                  <div>
                    <Typography.Text theme="secondary">材质槽</Typography.Text>
                    <Typography.Text>{String(asRecord(renderPlan.textureApplication).materialSlot || materialSlot)}</Typography.Text>
                  </div>
                </div>
                <div className="podi-product-commercialization__package-flow">
                  {[
                    { label: '模型', value: readiness.modelReady ? '已识别' : '待确认' },
                    { label: 'UV', value: readiness.uvReady ? '可贴图' : '需处理' },
                    { label: '贴图', value: readiness.textureProvided ? `${textureImageUrls.length} 张` : '缺失' },
                    { label: '渲染服务', value: readiness.renderWorkerReady ? '可执行' : '待接入' },
                  ].map((item) => (
                    <div key={item.label}>
                      <strong>{item.label}</strong>
                      <span>{item.value}</span>
                    </div>
                  ))}
                </div>
                <div className="podi-product-commercialization__shot-list">
                  <div>
                    <strong>场景 · {String(scene.label || scenePreset)}</strong>
                    <span>{String(scene.lighting || '')}</span>
                    <small>{String(scene.background || '')}</small>
                  </div>
                  <div>
                    <strong>镜头 · {String(camera.label || cameraPreset)}</strong>
                    <span>{String(camera.description || '')}</span>
                    <small>{durationSeconds}s · {aspectRatio}</small>
                  </div>
                </div>
                {issues.length > 0 ? (
                  <div className="podi-product-commercialization__review-list">
                    {issues.map((issue, index) => (
                      <div key={`${String(issue.code || 'issue')}-${index}`}>
                        <Tag theme="warning" variant="light">提示</Tag>
                        <div>
                          <strong>{String(issue.code || '审核提示')}</strong>
                          <p>{String(issue.message || '请补齐资产后再渲染。')}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : null}
                <details className="podi-product-commercialization__debug">
                  <summary>调试 JSON</summary>
                  <pre>{JSON.stringify({ model, assetReadiness: readiness, renderPlan }, null, 2)}</pre>
                </details>
              </Space>
            )}
          </section>
        </main>

        <aside className="podi-product-commercialization__studio-side">
          <div className="podi-product-commercialization__side-card">
            <Typography.Text strong>当前模型</Typography.Text>
            <div className="podi-product-commercialization__facts">
              <span>{modelKey === 'cup_1660' ? '杯子' : '背包'}</span>
              <span>{materialSlot}</span>
              <span>{textureImageUrls.length} 张贴图</span>
            </div>
            {textureImageUrl ? (
              <div className="podi-product-commercialization__side-image">
                <img src={textureImageUrl} alt="当前贴图" />
              </div>
            ) : (
              <div className="podi-product-commercialization__side-image">
                <span>等待贴图</span>
              </div>
            )}
          </div>
          <div className="podi-product-commercialization__side-card">
            <Typography.Text strong>能力边界</Typography.Text>
            <p>这条能力是 3D 渲染链路，后续接渲染 worker；不走大模型视频生成，不占用 KIE/Vidu 成本。</p>
          </div>
        </aside>
      </div>
    </section>
  );
}
