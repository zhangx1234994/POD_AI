import { useEffect, useMemo, useRef, useState } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { DRACOLoader } from 'three/examples/jsm/loaders/DRACOLoader.js';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { Alert, Button, Input, Select, Space, Tag, Textarea, Typography, MessagePlugin } from 'tdesign-react';
import { evalApi } from '../../api';
import type { Product3DRenderVideoRequest, Product3DRenderVideoResponse } from '../../api';

type WorkStatus = 'idle' | 'uploading' | 'previewing';
type ModelKey = 'cup_1660' | 'backpack_2551';
type CameraPreset = 'orbit_360' | 'slow_push_in' | 'detail_sweep';
type ScenePreset = 'clean_studio' | 'marketplace_white' | 'premium_dark';
type SlotTextureState = Record<string, string>;
type TextureSlotEntry = { materialSlot: string; imageUrl: string; label: string };
type PreviewStatus = { state: 'loading' | 'ready' | 'error'; message: string };

const MODEL_OPTIONS = [
  { label: '1660 杯子', value: 'cup_1660' },
  { label: '2551 笔记本电脑背包', value: 'backpack_2551' },
];

const MODEL_PROFILES: Record<
  ModelKey,
  {
    title: string;
    file: string;
    modelUrl: string;
    summary: string;
    firstSlot: string;
    materialSlots: string[];
  }
> = {
  cup_1660: {
    title: '1660 杯子',
    file: '1660.glb',
    modelUrl: '/models/product-3d/1660.glb',
    summary: '适合杯身正面贴图、360 环绕和慢速推进。模型已有 UV；当前没有内置相机和动画。',
    firstSlot: 'front',
    materialSlots: ['front', 'mouth', 'cover', 'bottom', 'handshank', 'else', 'else1'],
  },
  backpack_2551: {
    title: '2551 笔记本电脑背包',
    file: '2551.glb',
    modelUrl: '/models/product-3d/2551.glb',
    summary: '适合背包正面贴图、细节扫过和白底展示。材质槽较多，建议先从 front 验证方向，再扩展多槽贴图。',
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

function slotLabel(slot: string): string {
  return SLOT_LABELS[slot] || slot;
}

function disposeMaterial(material: THREE.Material) {
  const maybeTextured = material as THREE.Material & {
    map?: THREE.Texture | null;
    normalMap?: THREE.Texture | null;
    roughnessMap?: THREE.Texture | null;
    metalnessMap?: THREE.Texture | null;
  };
  maybeTextured.map?.dispose();
  maybeTextured.normalMap?.dispose();
  maybeTextured.roughnessMap?.dispose();
  maybeTextured.metalnessMap?.dispose();
  material.dispose();
}

function disposeObject(object: THREE.Object3D) {
  object.traverse((child) => {
    const mesh = child as THREE.Mesh;
    if (!mesh.isMesh) return;
    mesh.geometry?.dispose();
    if (Array.isArray(mesh.material)) mesh.material.forEach(disposeMaterial);
    else if (mesh.material) disposeMaterial(mesh.material);
  });
}

function fitModelToView(root: THREE.Object3D, modelKey: ModelKey) {
  const box = new THREE.Box3().setFromObject(root);
  const center = box.getCenter(new THREE.Vector3());
  const size = box.getSize(new THREE.Vector3());
  const maxDimension = Math.max(size.x, size.y, size.z) || 1;
  const targetSize = modelKey === 'backpack_2551' ? 2.25 : 2;
  root.position.sub(center);
  root.scale.setScalar(targetSize / maxDimension);
}

async function loadTexture(url: string, loader: THREE.TextureLoader): Promise<THREE.Texture> {
  return new Promise((resolve, reject) => {
    loader.load(
      url,
      (texture) => {
        texture.colorSpace = THREE.SRGBColorSpace;
        texture.flipY = false;
        texture.wrapS = THREE.ClampToEdgeWrapping;
        texture.wrapT = THREE.ClampToEdgeWrapping;
        texture.needsUpdate = true;
        resolve(texture);
      },
      undefined,
      reject,
    );
  });
}

function applyMaterialState(
  material: THREE.Material,
  texture: THREE.Texture | undefined,
  materialSlot: string,
  activeMaterialSlot: string,
): THREE.Material {
  const next = material.clone() as THREE.Material & {
    color?: THREE.Color;
    emissive?: THREE.Color;
    emissiveIntensity?: number;
    map?: THREE.Texture | null;
    roughness?: number;
    metalness?: number;
  };

  if (texture) {
    next.map = texture;
    if (next.color instanceof THREE.Color) next.color.set(0xffffff);
    next.roughness = Math.max(0.42, Number(next.roughness ?? 0.7));
    next.metalness = Math.min(0.08, Number(next.metalness ?? 0));
  }

  if (materialSlot === activeMaterialSlot && next.emissive instanceof THREE.Color) {
    next.emissive.set(0x0f62fe);
    next.emissiveIntensity = texture ? 0.1 : 0.18;
  }

  next.name = material.name;
  next.needsUpdate = true;
  return next;
}

async function applySlotTextures(
  root: THREE.Object3D,
  textureSlotEntries: TextureSlotEntry[],
  activeMaterialSlot: string,
): Promise<number> {
  const textureLoader = new THREE.TextureLoader();
  textureLoader.setCrossOrigin('anonymous');
  const textureBySlot = new Map<string, THREE.Texture>();
  let failedTextureCount = 0;

  await Promise.all(
    textureSlotEntries.map(async (entry) => {
      try {
        const texture = await loadTexture(entry.imageUrl, textureLoader);
        textureBySlot.set(entry.materialSlot, texture);
      } catch {
        failedTextureCount += 1;
      }
    }),
  );

  root.traverse((child) => {
    const mesh = child as THREE.Mesh;
    if (!mesh.isMesh || !mesh.material) return;

    const materials = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
    const nextMaterials = materials.map((material) => {
      const materialSlot = material.name || '';
      return applyMaterialState(material, textureBySlot.get(materialSlot), materialSlot, activeMaterialSlot);
    });

    mesh.material = Array.isArray(mesh.material) ? nextMaterials : nextMaterials[0];
  });

  return failedTextureCount;
}

function Product3DModelPreview({
  modelKey,
  modelProfile,
  materialSlot,
  textureSlotEntries,
}: {
  modelKey: ModelKey;
  modelProfile: (typeof MODEL_PROFILES)[ModelKey];
  materialSlot: string;
  textureSlotEntries: TextureSlotEntry[];
}) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const [previewStatus, setPreviewStatus] = useState<PreviewStatus>({
    state: 'loading',
    message: '正在加载真实 3D 模型',
  });

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return undefined;

    let disposed = false;
    let animationFrame = 0;
    let modelRoot: THREE.Object3D | null = null;

    host.replaceChildren();
    setPreviewStatus({ state: 'loading', message: '正在加载真实 3D 模型' });

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.domElement.setAttribute('aria-label', `${modelProfile.title} 真实 3D 预览`);
    renderer.domElement.setAttribute('role', 'img');
    host.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0xf6f8fb);

    const camera = new THREE.PerspectiveCamera(38, 1, 0.1, 100);
    camera.position.set(0.25, modelKey === 'backpack_2551' ? 0.25 : 0.36, 3.25);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.enablePan = false;
    controls.autoRotate = true;
    controls.autoRotateSpeed = 0.65;
    controls.target.set(0, 0, 0);

    scene.add(new THREE.HemisphereLight(0xffffff, 0xd7dde8, 2.2));
    const keyLight = new THREE.DirectionalLight(0xffffff, 2.4);
    keyLight.position.set(3, 4, 5);
    scene.add(keyLight);
    const rimLight = new THREE.DirectionalLight(0xbfd7ff, 1.4);
    rimLight.position.set(-3, 2.5, -4);
    scene.add(rimLight);

    const resize = () => {
      const rect = host.getBoundingClientRect();
      const width = Math.max(280, Math.floor(rect.width));
      const height = Math.max(320, Math.floor(rect.height || 380));
      renderer.setSize(width, height, false);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
    };

    const resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(host);
    resize();

    const dracoLoader = new DRACOLoader();
    dracoLoader.setDecoderPath('/libs/draco/');
    const loader = new GLTFLoader();
    loader.setDRACOLoader(dracoLoader);
    loader.load(
      modelProfile.modelUrl,
      async (gltf) => {
        if (disposed) return;
        modelRoot = gltf.scene;
        fitModelToView(modelRoot, modelKey);
        scene.add(modelRoot);
        controls.update();

        const failedTextureCount = await applySlotTextures(modelRoot, textureSlotEntries, materialSlot);
        if (disposed) return;
        const appliedCount = Math.max(0, textureSlotEntries.length - failedTextureCount);
        setPreviewStatus({
          state: 'ready',
          message:
            failedTextureCount > 0
              ? `${appliedCount} 个贴图已应用，${failedTextureCount} 个贴图加载失败`
              : textureSlotEntries.length > 0
                ? `已按材质名应用 ${textureSlotEntries.length} 个贴图`
                : '模型已加载，等待贴图',
        });
      },
      undefined,
      (error) => {
        const detail = error instanceof Error && error.message ? `：${error.message}` : '';
        if (!disposed) setPreviewStatus({ state: 'error', message: `模型加载失败，请检查 GLB/Draco 文件${detail}` });
      },
    );

    const animate = () => {
      controls.update();
      renderer.render(scene, camera);
      animationFrame = window.requestAnimationFrame(animate);
    };
    animate();

    return () => {
      disposed = true;
      window.cancelAnimationFrame(animationFrame);
      resizeObserver.disconnect();
      controls.dispose();
      dracoLoader.dispose();
      if (modelRoot) disposeObject(modelRoot);
      renderer.dispose();
      host.replaceChildren();
    };
  }, [materialSlot, modelKey, modelProfile, textureSlotEntries]);

  return (
    <div className="podi-product-3d-render__model-preview">
      <div ref={hostRef} className="podi-product-3d-render__model-canvas" />
      <div className="podi-product-3d-render__model-preview-head">
        <strong>{modelProfile.title}</strong>
        <span>{textureSlotEntries.length}/{modelProfile.materialSlots.length} 个贴图点已绑定</span>
      </div>
      <div className={`podi-product-3d-render__model-preview-status is-${previewStatus.state}`}>
        <span>{previewStatus.message}</span>
        <small>可拖拽旋转 · 自动慢转 · 材质名直连模型槽位</small>
      </div>
    </div>
  );
}

export function Product3DRenderVideoWorkbench() {
  const uploadRef = useRef<HTMLInputElement | null>(null);
  const [modelKey, setModelKey] = useState<ModelKey>('cup_1660');
  const [slotTextureUrls, setSlotTextureUrls] = useState<SlotTextureState>({});
  const [uploadingSlot, setUploadingSlot] = useState('');
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

  const textureSlotEntries = useMemo(
    () =>
      modelProfile.materialSlots
        .map((slot) => ({
          materialSlot: slot,
          imageUrl: String(slotTextureUrls[slot] || '').trim(),
          label: slotLabel(slot),
        }))
        .filter((item) => item.imageUrl),
    [modelProfile.materialSlots, slotTextureUrls],
  );
  const textureImageUrls = useMemo(
    () => textureSlotEntries.map((item) => item.imageUrl).filter(Boolean).slice(0, 12),
    [textureSlotEntries],
  );
  const activeTextureImageUrl = String(slotTextureUrls[materialSlot] || '').trim();
  const primaryTextureImageUrl = activeTextureImageUrl || textureImageUrls[0] || '';
  const updateSlotTexture = (slot: string, url: string) => {
    setSlotTextureUrls((prev) => {
      const next = { ...prev };
      const cleaned = url.trim();
      if (cleaned) next[slot] = cleaned;
      else delete next[slot];
      return next;
    });
    setResult(null);
  };

  const uploadTexture = async (slot: string, file: File | null | undefined) => {
    if (!file) return;
    setError('');
    setUploadingSlot(slot);
    setStatus('uploading');
    try {
      const uploaded = await evalApi.uploadImage(file);
      updateSlotTexture(slot, uploaded.url);
      MessagePlugin.success(`${slotLabel(slot)}贴图已上传`);
    } catch (err) {
      setError(String((err as any)?.message || err || '上传失败'));
    } finally {
      setStatus('idle');
      setUploadingSlot('');
      if (uploadRef.current) uploadRef.current.value = '';
    }
  };

  const previewPlan = async () => {
    setError('');
    setStatus('previewing');
    try {
      const payload: Product3DRenderVideoRequest = {
        modelKey,
        textureImageUrl: primaryTextureImageUrl || undefined,
        textureImageUrls,
        textureSlots: textureSlotEntries,
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
            这不是 KIE/Vidu 大模型视频。当前用 Three.js 验证模型、UV、材质槽和镜头方案，后续接服务端 Blender 渲染 worker。
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
        message="当前页面不是正式可交付视频能力：现在已接入客户端真实 3D 预览，但不会触发付费视频生成；服务端渲染 worker 和 MP4 回填仍待接入。"
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
                  setSlotTextureUrls({});
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
              <Typography.Text theme="secondary">贴图会落到模型的材质槽上。可逐个区域绑定贴图，并在左侧确认绑定关系。</Typography.Text>
            </div>
            <div className="podi-product-3d-render__slot-layout">
              <div className="podi-product-3d-render__slot-map" aria-label="模型贴图区域示意">
                <Product3DModelPreview
                  modelKey={modelKey}
                  modelProfile={modelProfile}
                  materialSlot={materialSlot}
                  textureSlotEntries={textureSlotEntries}
                />
                <p>当前是真实 GLB/UV 客户端预览：贴图按材质名应用到模型表面，可拖拽检查位置和方向。后续服务端渲染 worker 会复用同一组槽位参数输出 MP4。</p>
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
                    <small>{slotTextureUrls[slot] ? '已绑定贴图' : '未贴图'}</small>
                  </button>
                ))}
              </div>
              <Select label="材质槽精确值" value={materialSlot} onChange={(v) => setMaterialSlot(String(v))} options={materialOptions} />
            </div>
          </section>

          <section className="podi-product-commercialization__stage-panel">
            <div className="podi-product-commercialization__stage-title">
              <span>STEP 3</span>
              <Typography.Title level="h4">给材质槽绑定贴图</Typography.Title>
              <Typography.Text theme="secondary">每个固定贴图点都可以单独绑定图片；不再用一张图代表所有区域。</Typography.Text>
            </div>
            <div className="podi-product-commercialization__strategy-workbench">
              <div className="podi-product-3d-render__active-texture">
                <div className="podi-product-commercialization__side-image">
                  {activeTextureImageUrl ? <img src={activeTextureImageUrl} alt={`${slotLabel(materialSlot)}贴图`} /> : <span>当前槽位未绑定贴图</span>}
                </div>
                <div className="podi-field-stack">
                  <Typography.Text strong>
                    当前贴图点：{slotLabel(materialSlot)} · {materialSlot}
                  </Typography.Text>
                  <Space align="center">
                    <Input
                      value={activeTextureImageUrl}
                      onChange={(v) => updateSlotTexture(materialSlot, String(v))}
                      placeholder="https://..."
                      clearable
                    />
                    <input
                      ref={uploadRef}
                      type="file"
                      accept="image/*"
                      style={{ display: 'none' }}
                      onChange={(event) => void uploadTexture(materialSlot, event.currentTarget.files?.[0])}
                    />
                    <Button
                      variant="outline"
                      loading={status === 'uploading' && uploadingSlot === materialSlot}
                      onClick={() => uploadRef.current?.click()}
                    >
                      上传到当前点
                    </Button>
                  </Space>
                  <Typography.Text theme="secondary">
                    先选左侧材质槽，再上传图片。贴图会立即应用到左侧真实 3D 模型，可拖拽检查位置、缩放和方向。
                  </Typography.Text>
                </div>
              </div>
              <div className="podi-product-3d-render__texture-table">
                {modelProfile.materialSlots.map((slot) => (
                  <div key={slot} className={slot === materialSlot ? 'is-active' : ''}>
                    <button type="button" onClick={() => setMaterialSlot(slot)}>
                      <strong>{slotLabel(slot)}</strong>
                      <span>{slot}</span>
                    </button>
                    <Input
                      value={String(slotTextureUrls[slot] || '')}
                      onChange={(v) => updateSlotTexture(slot, String(v))}
                      placeholder="可选贴图 URL"
                      clearable
                    />
                  </div>
                ))}
              </div>
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
                    { label: '贴图点', value: asBool(readiness.textureProvided) ? `${textureSlotEntries.length} 个已绑定` : '缺失' },
                    { label: '3D 预览', value: '已接入 GLB/UV' },
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
                    <span>按材质槽绑定贴图，保持模型 UV，不做大模型重绘。</span>
                    <small>{String(textureApplication.mode || 'slot_texture_mapping')} · {textureSlotEntries.length} 个槽位</small>
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
            <Typography.Text strong>当前贴图点</Typography.Text>
            <div className="podi-product-commercialization__side-image">
              {activeTextureImageUrl ? <img src={activeTextureImageUrl} alt="当前贴图" /> : <span>等待贴图</span>}
            </div>
            <div className="podi-product-commercialization__facts">
              <span>{modelProfile.title}</span>
              <span>{slotLabel(materialSlot)}</span>
              <span>{textureSlotEntries.length} 个槽位已贴图</span>
            </div>
          </div>
          <div className="podi-product-commercialization__side-card">
            <Typography.Text strong>能力边界</Typography.Text>
            <p>3D 渲染视频是确定性渲染路线：当前客户端已负责 Three.js 所见即所得预览，服务端后续负责异步渲染、MP4、封面帧和 OSS 回填。它不调用 GPT Image 2、KIE 或 Vidu。</p>
          </div>
          <div className="podi-product-commercialization__side-card">
            <Typography.Text strong>扩容判断</Typography.Text>
            <p>单人预览主要消耗浏览器；批量导出视频会消耗服务端渲染 worker。后续应独立建渲染 executor 池，再评估 CPU/GPU 扩容。</p>
          </div>
        </aside>
      </div>
    </section>
  );
}
