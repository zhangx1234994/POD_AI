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
type CameraPreset = 'orbit_360' | 'slow_push_in' | 'detail_sweep' | 'hero_turntable' | 'top_reveal' | 'social_arc';
type ScenePreset = 'clean_studio' | 'marketplace_white' | 'premium_dark' | 'desktop_lifestyle' | 'gift_table' | 'retail_shelf';
type SlotTextureState = Record<string, string>;
type TextureSlotEntry = { materialSlot: string; imageUrl: string; label: string };
type PreviewStatus = { state: 'loading' | 'ready' | 'error'; message: string };
type VideoExportStatus = 'idle' | 'recording' | 'ready' | 'error';
type VideoExportFormat = 'mp4' | 'webm';
type VideoRecorderChoice = {
  mimeType: string;
  format: VideoExportFormat;
  extension: VideoExportFormat;
  label: string;
};
type ExportedPreviewVideo = {
  blob: Blob;
  mimeType: string;
  format: VideoExportFormat;
  extension: VideoExportFormat;
  label: string;
};
type Product3DPreviewHandle = {
  exportVideo: (durationSeconds: number, cameraPreset: CameraPreset) => Promise<ExportedPreviewVideo>;
};

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

const CAMERA_OPTIONS: Array<{ label: string; value: CameraPreset; desc: string }> = [
  { label: '360 环绕', value: 'orbit_360', desc: '商品完整转一圈，验证轮廓和贴图连续性。' },
  { label: '主视觉转台', value: 'hero_turntable', desc: '更稳的商品页首屏动效，适合主视觉视频。' },
  { label: '慢速推进', value: 'slow_push_in', desc: '从全景推进到主贴图区，突出商品主体。' },
  { label: '细节扫过', value: 'detail_sweep', desc: '横向扫过材质和贴图，适合细节展示。' },
  { label: '俯拍揭示', value: 'top_reveal', desc: '从顶部结构过渡到正面，适合杯子和包袋。' },
  { label: '社媒弧线', value: 'social_arc', desc: '节奏更快的弧形推拉，适合短视频素材。' },
];

const SCENE_OPTIONS: Array<{ label: string; value: ScenePreset; desc: string }> = [
  { label: '干净摄影棚', value: 'clean_studio', desc: '中性背景，适合通用质检和展示。' },
  { label: '电商白底', value: 'marketplace_white', desc: '平台商品图风格，不加道具。' },
  { label: '深色质感棚', value: 'premium_dark', desc: '轮廓光和深色背景，强调质感。' },
  { label: '桌面生活场景', value: 'desktop_lifestyle', desc: '产品放到桌面场景，适合杯子/办公用品。' },
  { label: '礼品桌面场景', value: 'gift_table', desc: '轻道具礼品氛围，不遮挡商品。' },
  { label: '货架陈列场景', value: 'retail_shelf', desc: '模拟市场端陈列素材，避免虚假包装信息。' },
];
const CAMERA_OPTION_MAP = Object.fromEntries(CAMERA_OPTIONS.map((item) => [item.value, item]));
const SCENE_OPTION_MAP = Object.fromEntries(SCENE_OPTIONS.map((item) => [item.value, item]));

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

function delay(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function getPreferredVideoRecorderChoice(): VideoRecorderChoice | null {
  if (typeof MediaRecorder === 'undefined') return null;
  const choices: VideoRecorderChoice[] = [
    { mimeType: 'video/mp4;codecs="avc1.42E01E,mp4a.40.2"', format: 'mp4', extension: 'mp4', label: 'MP4' },
    { mimeType: 'video/mp4;codecs="avc1.42E01E"', format: 'mp4', extension: 'mp4', label: 'MP4' },
    { mimeType: 'video/mp4', format: 'mp4', extension: 'mp4', label: 'MP4' },
    { mimeType: 'video/webm;codecs=vp9', format: 'webm', extension: 'webm', label: 'WebM' },
    { mimeType: 'video/webm;codecs=vp8', format: 'webm', extension: 'webm', label: 'WebM' },
    { mimeType: 'video/webm', format: 'webm', extension: 'webm', label: 'WebM' },
  ];
  return choices.find((choice) => MediaRecorder.isTypeSupported(choice.mimeType)) || null;
}

function applyCameraMotion(
  camera: THREE.PerspectiveCamera,
  controls: OrbitControls,
  preset: CameraPreset,
  originalPosition: THREE.Vector3,
  originalTarget: THREE.Vector3,
  progress: number,
) {
  const eased = 0.5 - Math.cos(Math.min(1, Math.max(0, progress)) * Math.PI) / 2;
  if (preset === 'slow_push_in') {
    camera.position.set(
      originalPosition.x * (1 - eased * 0.28),
      originalPosition.y + eased * 0.08,
      Math.max(1.85, originalPosition.z - eased * 0.85),
    );
    controls.target.copy(originalTarget);
    return;
  }
  if (preset === 'detail_sweep') {
    camera.position.set(
      originalPosition.x + Math.sin(eased * Math.PI * 2) * 0.42,
      originalPosition.y + Math.sin(eased * Math.PI) * 0.14,
      Math.max(1.9, originalPosition.z - 0.25),
    );
    controls.target.set(originalTarget.x + Math.cos(eased * Math.PI * 2) * 0.08, originalTarget.y + 0.04, originalTarget.z);
    return;
  }
  if (preset === 'hero_turntable') {
    const radius = Math.max(2.65, originalPosition.length());
    const angle = -0.55 + eased * 1.1;
    camera.position.set(Math.sin(angle) * radius * 0.52, originalPosition.y + 0.08, Math.cos(angle) * radius * 0.78);
    controls.target.copy(originalTarget);
    return;
  }
  if (preset === 'top_reveal') {
    camera.position.set(
      originalPosition.x * (1 - eased),
      originalPosition.y + (1 - eased) * 1.05 + eased * 0.12,
      Math.max(2.15, originalPosition.z - eased * 0.45),
    );
    controls.target.set(originalTarget.x, originalTarget.y + (1 - eased) * 0.28, originalTarget.z);
    return;
  }
  if (preset === 'social_arc') {
    const radius = Math.max(2.35, originalPosition.length());
    const angle = -0.85 + eased * 1.7;
    camera.position.set(Math.sin(angle) * radius * 0.64, originalPosition.y + Math.sin(eased * Math.PI) * 0.16, Math.cos(angle) * radius * 0.72);
    controls.target.set(originalTarget.x, originalTarget.y + 0.03, originalTarget.z);
    return;
  }
  const radius = Math.max(2.25, originalPosition.length());
  const angle = eased * Math.PI * 2;
  camera.position.set(Math.sin(angle) * radius * 0.68, originalPosition.y, Math.cos(angle) * radius * 0.68);
  controls.target.copy(originalTarget);
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
  onExportHandle,
}: {
  modelKey: ModelKey;
  modelProfile: (typeof MODEL_PROFILES)[ModelKey];
  materialSlot: string;
  textureSlotEntries: TextureSlotEntry[];
  onExportHandle?: (handle: Product3DPreviewHandle | null) => void;
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
    let recording:
      | {
          startAt: number;
          durationMs: number;
          preset: CameraPreset;
          originalPosition: THREE.Vector3;
          originalTarget: THREE.Vector3;
        }
      | null = null;

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

    const exportVideo = async (seconds: number, preset: CameraPreset) => {
      if (!modelRoot) throw new Error('3D 模型还没有加载完成，请等待预览显示“已应用贴图”后再生成视频。');
      if (typeof MediaRecorder === 'undefined') throw new Error('当前浏览器不支持 MediaRecorder，无法本地录制 3D 预览视频。');
      if (!('captureStream' in renderer.domElement)) throw new Error('当前浏览器不支持 canvas.captureStream，无法导出 3D 预览视频。');

      const stream = renderer.domElement.captureStream(30);
      const recorderChoice = getPreferredVideoRecorderChoice();
      if (!recorderChoice) throw new Error('当前浏览器不支持 MP4/WebM 本地录制，无法导出 3D 预览视频。');
      const recorder = new MediaRecorder(stream, { mimeType: recorderChoice.mimeType });
      const chunks: BlobPart[] = [];
      const stopped = new Promise<ExportedPreviewVideo>((resolve, reject) => {
        recorder.ondataavailable = (event) => {
          if (event.data.size > 0) chunks.push(event.data);
        };
        recorder.onerror = () => reject(new Error('本地视频录制失败，请刷新页面后重试。'));
        recorder.onstop = () => {
          stream.getTracks().forEach((track) => track.stop());
          const mimeType = recorder.mimeType || recorderChoice.mimeType;
          const format: VideoExportFormat = mimeType.includes('mp4') ? 'mp4' : 'webm';
          resolve({
            blob: new Blob(chunks, { type: mimeType }),
            mimeType,
            format,
            extension: format,
            label: format === 'mp4' ? 'MP4' : 'WebM',
          });
        };
      });

      const originalPosition = camera.position.clone();
      const originalTarget = controls.target.clone();
      const originalAutoRotate = controls.autoRotate;
      const originalAutoRotateSpeed = controls.autoRotateSpeed;
      recording = {
        startAt: performance.now(),
        durationMs: Math.max(1, seconds) * 1000,
        preset,
        originalPosition,
        originalTarget,
      };
      controls.autoRotate = false;
      controls.autoRotateSpeed = 0;
      recorder.start(100);
      try {
        await delay(Math.max(1, seconds) * 1000 + 160);
        if (recorder.state !== 'inactive') recorder.stop();
        return await stopped;
      } finally {
        recording = null;
        camera.position.copy(originalPosition);
        controls.target.copy(originalTarget);
        controls.autoRotate = originalAutoRotate;
        controls.autoRotateSpeed = originalAutoRotateSpeed;
        controls.update();
      }
    };

    onExportHandle?.({ exportVideo });

    const animate = () => {
      if (recording) {
        const progress = (performance.now() - recording.startAt) / recording.durationMs;
        applyCameraMotion(camera, controls, recording.preset, recording.originalPosition, recording.originalTarget, progress);
      }
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
      onExportHandle?.(null);
      host.replaceChildren();
    };
  }, [materialSlot, modelKey, modelProfile, onExportHandle, textureSlotEntries]);

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
  const [previewHandle, setPreviewHandle] = useState<Product3DPreviewHandle | null>(null);
  const [videoExportStatus, setVideoExportStatus] = useState<VideoExportStatus>('idle');
  const [videoExportError, setVideoExportError] = useState('');
  const videoOutputRef = useRef<HTMLDivElement | null>(null);
  const [localVideo, setLocalVideo] = useState<{
    url: string;
    name: string;
    size: number;
    mimeType: string;
    format: VideoExportFormat;
    label: string;
  } | null>(null);

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

  const clearLocalVideo = () => {
    setLocalVideo((prev) => {
      if (prev?.url) URL.revokeObjectURL(prev.url);
      return null;
    });
    setVideoExportStatus('idle');
    setVideoExportError('');
  };

  const updateSlotTexture = (slot: string, url: string) => {
    setSlotTextureUrls((prev) => {
      const next = { ...prev };
      const cleaned = url.trim();
      if (cleaned) next[slot] = cleaned;
      else delete next[slot];
      return next;
    });
    setResult(null);
    clearLocalVideo();
  };

  useEffect(
    () => () => {
      if (localVideo?.url) URL.revokeObjectURL(localVideo.url);
    },
    [localVideo],
  );

  useEffect(() => {
    if (!localVideo) return;
    window.requestAnimationFrame(() => {
      videoOutputRef.current?.scrollIntoView({ block: 'center', behavior: 'smooth' });
    });
  }, [localVideo]);

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

  const exportLocalPreviewVideo = async () => {
    setError('');
    setVideoExportError('');
    if (!previewHandle) {
      setVideoExportStatus('error');
      setVideoExportError('3D 预览还没有准备好，请等待模型加载完成后再生成本地视频。');
      return;
    }
    setVideoExportStatus('recording');
    try {
      const exported = await previewHandle.exportVideo(durationSeconds, cameraPreset);
      if (exported.blob.size <= 0) throw new Error('本地视频导出为空，请重新录制。');
      const url = URL.createObjectURL(exported.blob);
      setLocalVideo((prev) => {
        if (prev?.url) URL.revokeObjectURL(prev.url);
        return {
          url,
          name: `podi-3d-${modelKey}-${durationSeconds}s-${Date.now()}.${exported.extension}`,
          size: exported.blob.size,
          mimeType: exported.mimeType,
          format: exported.format,
          label: exported.label,
        };
      });
      setVideoExportStatus('ready');
      MessagePlugin.success(`本地 3D 预览视频已生成：${exported.label}`);
    } catch (err) {
      setVideoExportStatus('error');
      setVideoExportError(String((err as any)?.message || err || '本地视频生成失败'));
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
  const localVideoPanel = (
    <div ref={videoOutputRef} className="podi-product-3d-render__video-output">
      <div className="podi-product-commercialization__panel-head">
        <Typography.Text strong>本地预览视频</Typography.Text>
        <Typography.Text theme="secondary">
          {videoExportStatus === 'recording'
            ? '正在录制当前 3D 画面'
            : localVideo
              ? `${Math.max(1, Math.round(localVideo.size / 1024))} KB · ${localVideo.label}`
              : '尚未生成'}
        </Typography.Text>
      </div>
      {localVideo ? (
        <>
          {localVideo.format === 'webm' ? (
            <Alert theme="warning" message="当前浏览器不支持直接录制 MP4，已回退为 WebM。请在支持 MP4 MediaRecorder 的 Chrome/Safari 环境重试，或后续走服务端 MP4 worker。" />
          ) : null}
          <video src={localVideo.url} controls />
          <Space>
            <Button variant="outline" onClick={() => window.open(localVideo.url, '_blank', 'noreferrer')}>
              打开视频
            </Button>
            <Button
              theme="primary"
              onClick={() => {
                const anchor = document.createElement('a');
                anchor.href = localVideo.url;
                anchor.download = localVideo.name;
                document.body.appendChild(anchor);
                anchor.click();
                anchor.remove();
              }}
            >
              下载 {localVideo.label}
            </Button>
          </Space>
        </>
      ) : (
        <Alert
          theme={videoExportStatus === 'recording' ? 'info' : 'warning'}
          message={
            videoExportStatus === 'recording'
              ? '正在按当前镜头预设录制，请保持页面打开。'
              : '还没有视频结果。点击“生成本地预览视频”后会在这里回放并下载 MP4；不支持 MP4 的浏览器会明确回退 WebM。'
          }
        />
      )}
    </div>
  );

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
          <Tag theme="warning" variant="light">本地 MP4</Tag>
        </Space>
      </div>

      {error ? <Alert theme="error" message={error} /> : null}
      {videoExportError ? <Alert theme="error" message={videoExportError} /> : null}
      <Alert
        theme="info"
        message="当前优先在浏览器内按真实 3D 预览录制 MP4 并下载；若浏览器不支持 MP4 会明确回退 WebM。服务端 Blender/MP4/OSS 异步渲染 worker 后续独立接入。"
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
                  onExportHandle={setPreviewHandle}
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
              <Typography.Title level="h4">选择拍摄模板并生成视频</Typography.Title>
              <Typography.Text theme="secondary">这些是确定性拍摄参数，不是大模型提示词；选完即可录制当前 3D 画面。</Typography.Text>
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
            <div className="podi-product-3d-render__preset-summary">
              <div>
                <Typography.Text strong>镜头模板 · {CAMERA_OPTION_MAP[cameraPreset]?.label || cameraPreset}</Typography.Text>
                <Typography.Text theme="secondary">{CAMERA_OPTION_MAP[cameraPreset]?.desc || '按当前镜头路径录制。'}</Typography.Text>
              </div>
              <div>
                <Typography.Text strong>场景模型 · {SCENE_OPTION_MAP[scenePreset]?.label || scenePreset}</Typography.Text>
                <Typography.Text theme="secondary">{SCENE_OPTION_MAP[scenePreset]?.desc || '按当前场景摆放商品。'}</Typography.Text>
              </div>
            </div>
            <div className="podi-product-3d-render__video-actions">
              <Button theme="primary" loading={status === 'previewing'} onClick={() => void previewPlan()}>
                1. 检查 3D 贴图方案
              </Button>
              <Button
                theme="success"
                loading={videoExportStatus === 'recording'}
                disabled={!previewHandle || videoExportStatus === 'recording'}
                onClick={() => void exportLocalPreviewVideo()}
              >
                2. 生成并预览 {durationSeconds}s MP4
              </Button>
            </div>
            <Typography.Text theme="secondary">
              “检查方案”只校验资产和参数；“生成本地预览视频”会直接录制当前 Three.js 画面，优先生成可下载 MP4。
            </Typography.Text>
            {localVideoPanel}
          </section>

          <section className="podi-product-commercialization__stage-panel">
            <div className="podi-product-commercialization__stage-title">
              <span>RESULT</span>
              <Typography.Title level="h4">资产准备度与下一步</Typography.Title>
              <Typography.Text theme="secondary">这里同时展示方案检查和本地 MP4 视频输出；服务端 MP4/OSS 渲染 worker 仍待接入。</Typography.Text>
            </div>
            {!result ? (
              <Space direction="vertical" size="medium" style={{ width: '100%' }}>
                <div className="podi-product-commercialization__empty">
                  <Typography.Text theme="secondary">还没有方案检查结果。完成模型、贴图区域和贴图输入后点击检查。</Typography.Text>
                </div>
              </Space>
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
            <p>3D 渲染视频是确定性渲染路线：当前客户端已负责 Three.js 所见即所得预览和本地 MP4 导出，服务端后续负责异步渲染、封面帧和 OSS 回填。它不调用 GPT Image 2、KIE 或 Vidu。</p>
          </div>
          <div className="podi-product-commercialization__side-card">
            <Typography.Text strong>当前视频</Typography.Text>
            <p>
              {videoExportStatus === 'recording'
                ? `正在录制 ${durationSeconds}s`
                : localVideo
                  ? `已生成 ${durationSeconds}s ${localVideo.label}，可预览下载`
                  : '待生成本地预览视频'}
            </p>
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
