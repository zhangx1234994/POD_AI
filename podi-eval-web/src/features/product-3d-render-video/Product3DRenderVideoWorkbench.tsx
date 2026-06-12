import { useMemo, useRef, useState } from 'react';
import { Alert, Button, Input, Select, Space, Tag, Textarea, Typography, MessagePlugin } from 'tdesign-react';
import { evalApi } from '../../api';
import type { Product3DRenderVideoRequest, Product3DRenderVideoResponse } from '../../api';

type WorkStatus = 'idle' | 'uploading' | 'previewing';
type ModelKey = 'cup_1660' | 'backpack_2551';
type CameraPreset = 'orbit_360' | 'slow_push_in' | 'detail_sweep';
type ScenePreset = 'clean_studio' | 'marketplace_white' | 'premium_dark';

const MODEL_OPTIONS = [
  { label: '1660 杯子', value: 'cup_1660' },
  { label: '2551 笔记本电脑背包', value: 'backpack_2551' },
];

const MODEL_PROFILES: Record<
  ModelKey,
  {
    title: string;
    file: string;
    summary: string;
    firstSlot: string;
    materialSlots: string[];
  }
> = {
  cup_1660: {
    title: '1660 杯子',
    file: '1660.glb',
    summary: '适合杯身正面贴图、360 环绕和慢速推进。模型已有 UV；当前没有内置相机和动画。',
    firstSlot: 'front',
    materialSlots: ['front', 'mouth', 'cover', 'bottom', 'handshank', 'else', 'else1'],
  },
  backpack_2551: {
    title: '2551 笔记本电脑背包',
    file: '2551.glb',
    summary: '适合背包正面贴图、细节扫过和白底展示。材质槽较多，首版建议只验证 front。',
    firstSlot: 'front',
    materialSlots: [
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
  },
};

const SLOT_LABELS: Record<string, string> = {
  front: '正面主贴图区',
  mouth: '杯口',
  cover: '杯盖',
  bottom: '底部',
  handshank: '把手',
  back: '背面',
  top: '顶部',
  left: '左侧',
  right: '右侧',
  sideleft: '左侧面',
  sideright: '右侧面',
  inside: '内里',
  zipper: '拉链',
  zipper02: '拉链 02',
  zipperB: '拉链 B',
  stitch: '缝线',
  qitaDZ: '其他底座',
  qitaBD: '其他包带',
  qitaSL: '其他塑料件',
  qitaWGBB: '其他外观包边',
  qitaWG: '其他外观',
  qitaWG001: '其他外观 001',
  else: '其他材质 1',
  else1: '其他材质 2',
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

function asBool(value: unknown): boolean {
  return value === true;
}

function splitLines(value: string): string[] {
  return value
    .split(/[\n,，;；|]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function slotLabel(slot: string): string {
  return SLOT_LABELS[slot] || slot;
}

export function Product3DRenderVideoWorkbench() {
  const uploadRef = useRef<HTMLInputElement | null>(null);
  const [modelKey, setModelKey] = useState<ModelKey>('cup_1660');
  const [textureImageUrl, setTextureImageUrl] = useState('');
  const [textureImageUrlsText, setTextureImageUrlsText] = useState('');
  const [materialSlot, setMaterialSlot] = useState('front');
  const [cameraPreset, setCameraPreset] = useState<CameraPreset>('orbit_360');
  const [scenePreset, setScenePreset] = useState<ScenePreset>('clean_studio');
  const [durationSeconds, setDurationSeconds] = useState(6);
  const [aspectRatio, setAspectRatio] = useState('16:9');
  const [result, setResult] = useState<Product3DRenderVideoResponse | null>(null);
  const [status, setStatus] = useState<WorkStatus>('idle');
  const [error, setError] = useState('');

  const modelProfile = MODEL_PROFILES[modelKey];
  const materialOptions = useMemo(
    () => modelProfile.materialSlots.map((slot) => ({ label: `${slotLabel(slot)} · ${slot}`, value: slot })),
    [modelProfile],
  );

  const textureImageUrls = useMemo(() => {
    const urls = splitLines(textureImageUrlsText);
    const mainUrl = textureImageUrl.trim();
    if (mainUrl && !urls.includes(mainUrl)) urls.unshift(mainUrl);
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
  const textureApplication = asRecord(renderPlan.textureApplication);
  const camera = asRecord(renderPlan.camera);
  const scene = asRecord(renderPlan.scene);
  const review = asRecord(result?.review);
  const issues = asArray(review.issues).map((item) => asRecord(item));
  const activeSlot = String(textureApplication.materialSlot || materialSlot);

  return (
    <section className="podi-product-commercialization podi-product-3d-render">
      <div className="podi-product-commercialization__head">
        <div>
          <Typography.Text theme="primary">3D 贴图渲染 · 技术预览</Typography.Text>
          <Typography.Title level="h3" style={{ margin: '4px 0' }}>
            固定模型区域贴图与渲染方案
          </Typography.Title>
          <Typography.Text theme="secondary">
            这不是 KIE/Vidu 大模型视频。当前只验证模型、UV、材质槽和镜头方案，后续接 Three.js/Blender 预览与渲染 worker。
          </Typography.Text>
        </div>
        <Space align="center">
          <Tag theme="primary" variant="light">确定性渲染</Tag>
          <Tag theme="success" variant="light">材质槽 / UV</Tag>
          <Tag theme="warning" variant="light">不生成 MP4</Tag>
        </Space>
      </div>

      {error ? <Alert theme="error" message={error} /> : null}
      <Alert
        theme="warning"
        message="当前页面不是正式可交付视频能力：还没有 3D 画布贴图预览，也不会触发付费视频生成。它只用于确认贴图应该落在哪个固定区域。"
      />

      <div className="podi-product-commercialization__studio">
        <main className="podi-product-commercialization__stage-main">
          <section className="podi-product-commercialization__stage-panel">
            <div className="podi-product-commercialization__stage-title">
              <span>STEP 1</span>
              <Typography.Title level="h4">选择受控 3D 模型</Typography.Title>
              <Typography.Text theme="secondary">模型决定可贴图区域。这里不输入“生成需求”，先选模型资产。</Typography.Text>
            </div>
            <div className="podi-product-3d-render__model-row">
              <Select
                label="模型"
                value={modelKey}
                onChange={(v) => {
                  const key = String(v) as ModelKey;
                  setModelKey(key);
                  setMaterialSlot(MODEL_PROFILES[key].firstSlot);
                  setResult(null);
                }}
                options={MODEL_OPTIONS}
              />
              <div className="podi-product-3d-render__model-meta">
                <strong>{modelProfile.file}</strong>
                <span>{modelProfile.summary}</span>
              </div>
            </div>
          </section>

          <section className="podi-product-commercialization__stage-panel">
            <div className="podi-product-commercialization__stage-title">
              <span>STEP 2</span>
              <Typography.Title level="h4">选择固定贴图区域</Typography.Title>
              <Typography.Text theme="secondary">贴图会落到模型的材质槽上。首版先验证单区域贴图，避免多面贴图混乱。</Typography.Text>
            </div>
            <div className="podi-product-3d-render__slot-layout">
              <div className="podi-product-3d-render__slot-map" aria-label="模型贴图区域示意">
                <div className={`podi-product-3d-render__slot-shape podi-product-3d-render__slot-shape--${modelKey}`}>
                  <span>{slotLabel(materialSlot)}</span>
                  <small>{materialSlot}</small>
                </div>
                <p>示意图只表达区域归属，不代表最终贴图重合效果。真实重合预览需要接 Three.js 画布。</p>
              </div>
              <div className="podi-product-3d-render__slot-list">
                {modelProfile.materialSlots.map((slot) => (
                  <button
                    key={slot}
                    type="button"
                    className={`podi-product-3d-render__slot ${slot === materialSlot ? 'is-active' : ''}`}
                    onClick={() => {
                      setMaterialSlot(slot);
                      setResult(null);
                    }}
                  >
                    <strong>{slotLabel(slot)}</strong>
                    <span>{slot}</span>
                  </button>
                ))}
              </div>
              <Select label="材质槽精确值" value={materialSlot} onChange={(v) => setMaterialSlot(String(v))} options={materialOptions} />
            </div>
          </section>

          <section className="podi-product-commercialization__stage-panel">
            <div className="podi-product-commercialization__stage-title">
              <span>STEP 3</span>
              <Typography.Title level="h4">上传贴图</Typography.Title>
              <Typography.Text theme="secondary">贴图是花纹、Logo 或设计图。它会按选中的材质槽贴到模型固定区域。</Typography.Text>
            </div>
            <div className="podi-product-commercialization__strategy-workbench">
              <div className="podi-field-stack">
                <Typography.Text>主贴图 URL</Typography.Text>
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
              <details className="podi-product-commercialization__interface-note">
                <summary>
                  <span>多贴图预留</span>
                  <small>当前只建议验证主贴图</small>
                </summary>
                <Textarea
                  value={textureImageUrlsText}
                  onChange={(v) => setTextureImageUrlsText(String(v))}
                  placeholder="每行一个 URL；后续用于多材质/多面贴图。"
                  autosize={{ minRows: 3, maxRows: 6 }}
                />
              </details>
            </div>
          </section>

          <section className="podi-product-commercialization__stage-panel">
            <div className="podi-product-commercialization__stage-title">
              <span>STEP 4</span>
              <Typography.Title level="h4">选择渲染预设</Typography.Title>
              <Typography.Text theme="secondary">这些是确定性参数，不是大模型提示词。</Typography.Text>
            </div>
            <div className="podi-product-commercialization__controls">
              <Select label="镜头" value={cameraPreset} onChange={(v) => setCameraPreset(String(v) as CameraPreset)} options={CAMERA_OPTIONS} />
              <Select label="场景" value={scenePreset} onChange={(v) => setScenePreset(String(v) as ScenePreset)} options={SCENE_OPTIONS} />
              <Select
                label="时长"
                value={String(durationSeconds)}
                onChange={(v) => setDurationSeconds(Number(v) || 6)}
                options={DURATION_OPTIONS}
              />
              <Input label="比例" value={aspectRatio} onChange={(v) => setAspectRatio(String(v))} />
            </div>
            <Button theme="primary" loading={status === 'previewing'} onClick={() => void previewPlan()}>
              检查 3D 贴图方案
            </Button>
          </section>

          <section className="podi-product-commercialization__stage-panel">
            <div className="podi-product-commercialization__stage-title">
              <span>RESULT</span>
              <Typography.Title level="h4">资产准备度与下一步</Typography.Title>
              <Typography.Text theme="secondary">这里只看可执行条件，不把方案当成视频结果。</Typography.Text>
            </div>
            {!result ? (
              <div className="podi-product-commercialization__empty">
                <Typography.Text theme="secondary">还没有检查结果。完成模型、贴图区域和贴图输入后点击检查。</Typography.Text>
              </div>
            ) : (
              <Space direction="vertical" size="medium" style={{ width: '100%' }}>
                <div className="podi-product-commercialization__strategy-summary">
                  <div>
                    <Typography.Text theme="secondary">模型文件</Typography.Text>
                    <Typography.Text>{String(model.preferredFile || modelProfile.file)}</Typography.Text>
                  </div>
                  <div>
                    <Typography.Text theme="secondary">准备度</Typography.Text>
                    <Typography.Text>{String(readiness.score ?? '-')}</Typography.Text>
                  </div>
                  <div>
                    <Typography.Text theme="secondary">贴图区域</Typography.Text>
                    <Typography.Text>{slotLabel(activeSlot)}</Typography.Text>
                  </div>
                </div>
                <div className="podi-product-commercialization__package-flow">
                  {[
                    { label: '模型目录', value: asBool(readiness.modelReady) ? '已识别' : '待归档' },
                    { label: 'UV', value: asBool(readiness.uvReady) ? '可贴图' : '需修复' },
                    { label: '贴图', value: asBool(readiness.textureProvided) ? `${textureImageUrls.length} 张` : '缺失' },
                    { label: '3D 画布', value: '待接入' },
                    { label: '渲染 worker', value: asBool(readiness.renderWorkerReady) ? '可执行' : '待接入' },
                  ].map((item) => (
                    <div key={item.label}>
                      <strong>{item.label}</strong>
                      <span>{item.value}</span>
                    </div>
                  ))}
                </div>
                <div className="podi-product-commercialization__shot-list">
                  <div>
                    <strong>贴图动作</strong>
                    <span>把主贴图应用到 {slotLabel(activeSlot)}，保持模型 UV，不做大模型重绘。</span>
                    <small>{String(textureApplication.mode || 'single_slot_texture')}</small>
                  </div>
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
            <Typography.Text strong>贴图预览</Typography.Text>
            <div className="podi-product-commercialization__side-image">
              {textureImageUrl ? <img src={textureImageUrl} alt="当前贴图" /> : <span>等待贴图</span>}
            </div>
            <div className="podi-product-commercialization__facts">
              <span>{modelProfile.title}</span>
              <span>{slotLabel(materialSlot)}</span>
              <span>{textureImageUrls.length} 张贴图</span>
            </div>
          </div>
          <div className="podi-product-commercialization__side-card">
            <Typography.Text strong>能力边界</Typography.Text>
            <p>3D 渲染视频是确定性渲染路线：模型、材质槽、UV、相机和灯光决定结果。它不调用 GPT Image 2、KIE 或 Vidu。</p>
          </div>
          <div className="podi-product-commercialization__side-card">
            <Typography.Text strong>下一步才是真验收</Typography.Text>
            <p>接入 Three.js 画布后，需要能看到贴图与模型区域是否重合；接入渲染 worker 后，再输出 MP4、封面帧和 manifest。</p>
          </div>
        </aside>
      </div>
    </section>
  );
}
