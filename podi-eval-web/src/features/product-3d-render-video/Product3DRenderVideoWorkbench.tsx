import { type PointerEvent as ReactPointerEvent, useEffect, useMemo, useRef, useState } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { DRACOLoader } from 'three/examples/jsm/loaders/DRACOLoader.js';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { Alert, Button, Input, Select, Space, Tag, Typography, MessagePlugin } from 'tdesign-react';
import { evalApi } from '../../api';
import type {
  BusinessRunPollResult,
  Product3DRenderVideoCatalogResponse,
  Product3DRenderVideoRequest,
  Product3DRenderVideoResponse,
} from '../../api';

type WorkStatus = 'idle' | 'uploading' | 'previewing' | 'server_rendering';
type ModelKey = string;
type CameraPreset = string;
type CameraDistance = string;
type ScenePreset = string;
type SlotTextureState = Record<string, string>;
type TextureSlotEntry = { materialSlot: string; imageUrl: string; label: string };
type MotionPathPoint = { x: number; y: number };
type SelectOption = { label: string; value: string; desc?: string };
type ModelProfile = {
  title: string;
  file: string;
  modelUrl: string;
  summary: string;
  firstSlot: string;
  materialSlots: string[];
};
type SceneProfile = {
  label: string;
  value: ScenePreset;
  desc: string;
  model: string;
  placement: string;
  props: string[];
  fusion: {
    landingZone: string;
    productScale: string;
    occlusionRule: string;
    propDepth: string;
  };
  assetId: string;
  source: string;
  license: string;
  renderFidelity: string;
  assetStatus: 'ready' | 'planned' | 'needs_review';
  renderElements: SceneElementProfile[];
  visualAcceptance?: SceneVisualAcceptanceProfile;
  highFidelityCandidates: Array<{
    displayName?: string;
    provider: string;
    kind: string;
    license: string;
    ingestStage: string;
    workerReadiness: string;
    status?: string;
    blockingReasons?: string[];
    promotionNextAction?: string;
  }>;
};
type SceneVisualAcceptanceProfile = {
  status: string;
  summary: string;
  checks: SceneAcceptanceCheck[];
  candidateSummary: {
    total: number;
    cc0Count: number;
    readyCount: number;
    blockedCount: number;
  };
  candidateAssets: Array<{
    assetId: string;
    displayName: string;
    provider: string;
    kind: string;
    license: string;
    status: string;
    blockingReasons: string[];
    promotionNextAction: string;
  }>;
};
type SceneAcceptanceCheck = {
  code: string;
  label: string;
  status: string;
  evidence: string;
};
type SceneElementProfile = {
  elementId: string;
  label: string;
  type: string;
  depthLayer: string;
  zone: string;
  occlusion: string;
};
type SceneAssetSourceProfile = {
  provider: string;
  sourceType: string;
  license: string;
  commercialUse: boolean;
  ingestStatus: string;
};
type CameraDistanceProfile = {
  cameraZ: number;
  cameraY: number;
  fov: number;
  pathScale: number;
  frameHeightRatio: number;
  breathingRoom: number;
};
type PreviewStatus = { state: 'loading' | 'ready' | 'error'; message: string };
type VideoExportStatus = 'idle' | 'recording' | 'ready' | 'error';
type CameraPathPlaybackStatus = 'idle' | 'playing' | 'confirmed' | 'error';
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
type ServerRenderRunState = {
  runId: string;
  status: string;
  elapsedSeconds?: number;
  videoUrls: string[];
  imageUrls: string[];
  manifestUrls: string[];
  resultPayload?: Record<string, unknown> | null;
};
type Product3DPreviewHandle = {
  playCameraPath: (
    durationSeconds: number,
    cameraPreset: CameraPreset,
    cameraDistance: CameraDistance,
  ) => Promise<void>;
  exportVideo: (
    durationSeconds: number,
    cameraPreset: CameraPreset,
    cameraDistance: CameraDistance,
    aspectRatio: string,
  ) => Promise<ExportedPreviewVideo>;
};

const DEFAULT_MODEL_OPTIONS: SelectOption[] = [
  { label: '1660 杯子', value: 'cup_1660' },
  { label: '2551 笔记本电脑背包', value: 'backpack_2551' },
];

const MODEL_PROFILES: Record<string, ModelProfile> = {
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

const CAMERA_OPTIONS: SelectOption[] = [
  { label: '360 环绕', value: 'orbit_360', desc: '商品完整转一圈，验证轮廓和贴图连续性。' },
  { label: '主视觉转台', value: 'hero_turntable', desc: '更稳的商品页首屏动效，适合主视觉视频。' },
  { label: '慢速推进', value: 'slow_push_in', desc: '从全景推进到主贴图区，突出商品主体。' },
  { label: '细节扫过', value: 'detail_sweep', desc: '横向扫过材质和贴图，适合细节展示。' },
  { label: '俯拍揭示', value: 'top_reveal', desc: '从顶部结构过渡到正面，适合杯子和包袋。' },
  { label: '社媒弧线', value: 'social_arc', desc: '节奏更快的弧形推拉，适合短视频素材。' },
];

const SCENE_OPTIONS: SceneProfile[] = [
  {
    label: '干净摄影棚',
    value: 'clean_studio',
    desc: '中性背景，适合通用质检和展示。',
    model: '无缝弧形背景 + 柔光地台',
    placement: '商品居中落在地台接触面，保留完整轮廓。',
    props: ['softbox', 'contact shadow', 'sweep backdrop'],
    fusion: {
      landingZone: '中心椭圆落地区',
      productScale: '商品占画面 56-70%',
      occlusionRule: '无道具遮挡商品轮廓',
      propDepth: '灯光和背景都在商品后方',
    },
    assetId: 'podi.scene.procedural.clean_studio.v1',
    source: 'PODI 程序化场景',
    license: '内部生成 · 可商用',
    renderFidelity: 'MVP 程序化',
    assetStatus: 'ready',
    renderElements: [
      { elementId: 'cyclorama_backdrop', label: 'Cyclorama Backdrop', type: 'seamless_backdrop', depthLayer: 'background', zone: 'full_frame', occlusion: 'never_cross_product_silhouette' },
      { elementId: 'matte_floor', label: 'Matte Floor', type: 'floor_plane', depthLayer: 'surface', zone: 'bottom_20_percent', occlusion: 'shadow_receiver_only' },
    ],
    highFidelityCandidates: [
      {
        provider: 'Poly Haven',
        kind: 'studio HDRI',
        license: 'CC0',
        ingestStage: 'staging_candidate',
        workerReadiness: '待 worker 导入测试',
      },
      {
        provider: 'ambientCG',
        kind: 'studio PBR material',
        license: 'CC0',
        ingestStage: 'staging_candidate',
        workerReadiness: '待 worker 导入测试',
      },
    ],
  },
  {
    label: '电商白底',
    value: 'marketplace_white',
    desc: '平台商品图风格，不加道具。',
    model: '白底摄影棚 + 极轻地面阴影',
    placement: '商品占画面主体，不出现任何干扰道具。',
    props: ['white sweep', 'catalog shadow'],
    fusion: {
      landingZone: '纯白中心落地区',
      productScale: '商品占画面 66-78%',
      occlusionRule: '禁止任何前景道具',
      propDepth: '仅保留地面阴影',
    },
    assetId: 'podi.scene.procedural.marketplace_white.v1',
    source: 'PODI 程序化场景',
    license: '内部生成 · 可商用',
    renderFidelity: 'MVP 程序化',
    assetStatus: 'ready',
    renderElements: [
      { elementId: 'white_catalog_backdrop', label: 'White Catalog Backdrop', type: 'catalog_backdrop', depthLayer: 'background', zone: 'full_frame', occlusion: 'no_props_or_text' },
      { elementId: 'subtle_contact_shadow_receiver', label: 'Subtle Contact Shadow Receiver', type: 'floor_plane', depthLayer: 'surface', zone: 'bottom_20_percent', occlusion: 'shadow_receiver_only' },
    ],
    highFidelityCandidates: [
      {
        provider: 'Poly Haven',
        kind: 'neutral studio HDRI',
        license: 'CC0',
        ingestStage: 'staging_candidate',
        workerReadiness: '待 worker 导入测试',
      },
    ],
  },
  {
    label: '深色质感棚',
    value: 'premium_dark',
    desc: '轮廓光和深色背景，强调质感。',
    model: '深色棚拍台 + 侧后轮廓光',
    placement: '商品前景居中，背景只承担边缘高光。',
    props: ['rim light', 'dark plinth', 'soft top light'],
    fusion: {
      landingZone: '深色台面中心',
      productScale: '商品占画面 56-68%',
      occlusionRule: '轮廓光不能吞掉贴图边界',
      propDepth: '台面在商品下方，灯光在后侧',
    },
    assetId: 'podi.scene.procedural.premium_dark.v1',
    source: 'PODI 程序化场景',
    license: '内部生成 · 可商用',
    renderFidelity: 'MVP 程序化',
    assetStatus: 'ready',
    renderElements: [
      { elementId: 'charcoal_sweep', label: 'Charcoal Sweep', type: 'studio_sweep', depthLayer: 'background', zone: 'full_frame', occlusion: 'rim_light_cannot_hide_edges' },
      { elementId: 'low_dark_plinth', label: 'Low Dark Plinth', type: 'display_plinth', depthLayer: 'surface', zone: 'bottom_22_percent', occlusion: 'below_product_only' },
    ],
    highFidelityCandidates: [
      {
        provider: 'ambientCG',
        kind: 'dark PBR material',
        license: 'CC0',
        ingestStage: 'staging_candidate',
        workerReadiness: '待 worker 导入测试',
      },
    ],
  },
  {
    label: '桌面生活场景',
    value: 'desktop_lifestyle',
    desc: '产品放到桌面场景，适合杯子/办公用品。',
    model: '木质桌面 + 背景小物',
    placement: '商品压在桌面前区，道具后置且不遮挡贴图。',
    props: ['wood table', 'book block', 'soft cube'],
    fusion: {
      landingZone: '桌面前区落点',
      productScale: '按真实桌面比例放置',
      occlusionRule: '背景小物不得跨过商品外轮廓',
      propDepth: '书本和方块在商品后排',
    },
    assetId: 'podi.scene.procedural.desktop_lifestyle.v1',
    source: 'PODI 程序化场景',
    license: '内部生成 · 可商用',
    renderFidelity: 'MVP 程序化',
    assetStatus: 'ready',
    renderElements: [
      { elementId: 'wood_tabletop', label: 'Wood Tabletop', type: 'table_surface', depthLayer: 'surface', zone: 'bottom_27_percent', occlusion: 'shadow_receiver_only' },
      { elementId: 'rear_book_block', label: 'Rear Book Block', type: 'soft_prop', depthLayer: 'rear_prop', zone: 'left_rear', occlusion: 'behind_product_only' },
      { elementId: 'rear_soft_cube', label: 'Rear Soft Cube', type: 'soft_prop', depthLayer: 'rear_prop', zone: 'right_rear', occlusion: 'behind_product_only' },
    ],
    highFidelityCandidates: [
      {
        provider: 'ambientCG',
        kind: 'wood tabletop material',
        license: 'CC0',
        ingestStage: 'staging_candidate',
        workerReadiness: '待 worker 导入测试',
      },
      {
        provider: 'Poly Haven',
        kind: 'soft indoor HDRI',
        license: 'CC0',
        ingestStage: 'staging_candidate',
        workerReadiness: '待 worker 导入测试',
      },
    ],
  },
  {
    label: '礼品桌面场景',
    value: 'gift_table',
    desc: '轻道具礼品氛围，不遮挡商品。',
    model: '礼品桌面 + 后排礼盒',
    placement: '商品仍是最大主体，礼盒只做背景氛围。',
    props: ['gift box', 'ribbon block', 'warm table'],
    fusion: {
      landingZone: '礼品桌面中心',
      productScale: '商品必须大于礼盒道具',
      occlusionRule: '礼盒和丝带不得覆盖贴图槽',
      propDepth: '礼品道具固定在后排',
    },
    assetId: 'podi.scene.procedural.gift_table.v1',
    source: 'PODI 程序化场景',
    license: '内部生成 · 可商用',
    renderFidelity: 'MVP 程序化',
    assetStatus: 'ready',
    renderElements: [
      { elementId: 'warm_gift_table', label: 'Warm Gift Table', type: 'table_surface', depthLayer: 'surface', zone: 'bottom_26_percent', occlusion: 'shadow_receiver_only' },
      { elementId: 'rear_gift_box_left', label: 'Rear Gift Box Left', type: 'neutral_gift_prop', depthLayer: 'rear_prop', zone: 'left_rear', occlusion: 'behind_product_no_text' },
    ],
    highFidelityCandidates: [
      {
        provider: 'ambientCG',
        kind: 'paper/cardboard material',
        license: 'CC0',
        ingestStage: 'staging_candidate',
        workerReadiness: '待 worker 导入测试',
      },
    ],
  },
  {
    label: '货架陈列场景',
    value: 'retail_shelf',
    desc: '模拟市场端陈列素材，避免虚假包装信息。',
    model: '三层浅景深货架',
    placement: '商品位于前排中央，货架不出现可读标签。',
    props: ['shelf rails', 'display depth', 'neutral lighting'],
    fusion: {
      landingZone: '货架前排中心',
      productScale: '商品贴近前排展示位',
      occlusionRule: '货架层板不能穿过商品主体',
      propDepth: '层板和立柱保持在背景层',
    },
    assetId: 'podi.scene.procedural.retail_shelf.v1',
    source: 'PODI 程序化场景',
    license: '内部生成 · 可商用',
    renderFidelity: 'MVP 程序化',
    assetStatus: 'ready',
    renderElements: [
      { elementId: 'rear_shelf_rail_mid', label: 'Rear Shelf Rail Mid', type: 'shelf_rail', depthLayer: 'background', zone: 'middle_rear', occlusion: 'cannot_intersect_product_body' },
      { elementId: 'front_display_shelf', label: 'Front Display Shelf', type: 'shelf_surface', depthLayer: 'surface', zone: 'bottom_23_percent', occlusion: 'product_stands_in_front' },
    ],
    highFidelityCandidates: [
      {
        provider: 'internal/CC0',
        kind: 'generic retail shelf model',
        license: '需入库审核',
        ingestStage: 'license_review',
        workerReadiness: '待 worker 导入测试',
      },
    ],
  },
];
const CAMERA_DISTANCE_OPTIONS: SelectOption[] = [
  { label: '远景完整商品', value: 'wide', desc: '默认推荐，优先保证商品完整入画。' },
  { label: '标准商品镜头', value: 'standard', desc: '商品主体更大，仍保留上下呼吸空间。' },
  { label: '近景细节镜头', value: 'close', desc: '适合补充材质细节，不建议作为唯一视频。' },
];

const CAMERA_DISTANCE_PROFILES: Record<string, CameraDistanceProfile> = {
  wide: { cameraZ: 4.35, cameraY: 0.45, fov: 35, pathScale: 0.42, frameHeightRatio: 0.56, breathingRoom: 1.52 },
  standard: { cameraZ: 3.55, cameraY: 0.36, fov: 38, pathScale: 0.32, frameHeightRatio: 0.66, breathingRoom: 1.34 },
  close: { cameraZ: 2.85, cameraY: 0.3, fov: 42, pathScale: 0.22, frameHeightRatio: 0.78, breathingRoom: 1.18 },
};

const DEFAULT_MOTION_PATH: MotionPathPoint[] = [
  { x: 0.22, y: 0.66 },
  { x: 0.5, y: 0.5 },
  { x: 0.78, y: 0.42 },
];

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function asString(value: unknown, fallback = ''): string {
  const text = String(value ?? '').trim();
  return text || fallback;
}

function asStringArray(value: unknown): string[] {
  return asArray(value).map((item) => asString(item)).filter(Boolean);
}

function asNumber(value: unknown, fallback: number): number {
  const next = Number(value);
  return Number.isFinite(next) ? next : fallback;
}

function asBool(value: unknown): boolean {
  return value === true;
}

function licenseLabel(value: unknown): string {
  if (typeof value === 'string') return value;
  const record = asRecord(value);
  const rawType = asString(record.type, '未记录授权');
  const type = rawType === 'internal_procedural' ? '内部生成' : rawType;
  if (record.commercialUse === true) return `${type} · 可商用`;
  if (record.commercialUse === false) return `${type} · 待确认商用授权`;
  return type;
}

function sourceLabel(value: unknown): string {
  const text = asString(value, 'podi_internal');
  if (text === 'podi_internal') return 'PODI 程序化场景';
  return text;
}

function renderFidelityLabel(value: unknown): string {
  const text = asString(value);
  if (text === 'mvp_procedural') return 'MVP 程序化';
  return text || '待确认';
}

function sceneDepthLayerLabel(value: string): string {
  if (value === 'background') return '背景层';
  if (value === 'surface') return '承载面';
  if (value === 'rear_prop') return '后排道具';
  return value || '层级待确认';
}

function sceneElementLabel(value: string): string {
  return value
    .replace(/^rear_/, '后排 ')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase())
    .trim();
}

function buildSceneRenderElements(rawElements: unknown, fallbackProps: string[]): SceneElementProfile[] {
  const elements = asArray(rawElements)
    .map((item) => asRecord(item))
    .filter((item) => asString(item.elementId));
  if (elements.length) {
    return elements.slice(0, 6).map((item) => {
      const elementId = asString(item.elementId);
      return {
        elementId,
        label: sceneElementLabel(elementId),
        type: asString(item.type, 'scene_element'),
        depthLayer: asString(item.depthLayer, 'background'),
        zone: asString(item.zone, 'scene_zone'),
        occlusion: asString(item.occlusion, 'behind_product_only'),
      };
    });
  }
  return fallbackProps.slice(0, 4).map((item, index) => ({
    elementId: `fallback_${index + 1}`,
    label: item,
    type: 'legacy_scene_hint',
    depthLayer: index === 0 ? 'background' : 'rear_prop',
    zone: 'scene_hint',
    occlusion: 'behind_product_only',
  }));
}

function buildModelProfiles(catalog: Product3DRenderVideoCatalogResponse | null): Record<string, ModelProfile> {
  const items = asArray(catalog?.models)
    .map((item) => asRecord(item))
    .filter((item) => asString(item.modelKey));
  if (!items.length) return MODEL_PROFILES;

  const profiles: Record<string, ModelProfile> = {};
  for (const item of items) {
    const key = asString(item.modelKey);
    const materialSlots = asStringArray(item.materialSlots);
    const file = asString(item.preferredFile, `${key}.glb`);
    const notes = asStringArray(item.notes);
    profiles[key] = {
      title: asString(item.displayName, key),
      file,
      modelUrl: `/models/product-3d/${file}`,
      summary:
        notes[0] ||
        `${asString(item.productType, '3D 商品模型')} · ${materialSlots.length || 0} 个可贴图材质槽 · ${
          asBool(item.hasUv) ? '已有 UV' : 'UV 待确认'
        }`,
      firstSlot: asString(item.recommendedMaterialSlot, materialSlots[0] || 'front'),
      materialSlots: materialSlots.length ? materialSlots : ['front'],
    };
  }
  return Object.keys(profiles).length ? profiles : MODEL_PROFILES;
}

function buildModelOptions(profiles: Record<string, ModelProfile>): SelectOption[] {
  const options = Object.entries(profiles).map(([value, profile]) => ({ label: profile.title, value }));
  return options.length ? options : DEFAULT_MODEL_OPTIONS;
}

function buildCameraOptions(catalog: Product3DRenderVideoCatalogResponse | null): SelectOption[] {
  const options = asArray(catalog?.cameraPresets)
    .map((item) => asRecord(item))
    .map((item) => ({
      label: asString(item.label, asString(item.key)),
      value: asString(item.key),
      desc: asString(item.description, asString(item.shootingGoal, '按当前镜头路径录制。')),
    }))
    .filter((item) => item.value);
  return options.length ? options : CAMERA_OPTIONS;
}

function buildCameraDistanceOptions(catalog: Product3DRenderVideoCatalogResponse | null): SelectOption[] {
  const options = asArray(catalog?.cameraDistances)
    .map((item) => asRecord(item))
    .map((item) => ({
      label: asString(item.label, asString(item.key)),
      value: asString(item.key),
      desc: asString(item.description, '按当前远近档位安全取景。'),
    }))
    .filter((item) => item.value);
  return options.length ? options : CAMERA_DISTANCE_OPTIONS;
}

function buildCameraDistanceProfiles(catalog: Product3DRenderVideoCatalogResponse | null): Record<string, CameraDistanceProfile> {
  const profiles: Record<string, CameraDistanceProfile> = { ...CAMERA_DISTANCE_PROFILES };
  for (const raw of asArray(catalog?.cameraDistances)) {
    const item = asRecord(raw);
    const key = asString(item.key);
    if (!key) continue;
    const fallback = profiles[key] || CAMERA_DISTANCE_PROFILES.wide;
    const frameHeightRatio = asNumber(item.frameHeightRatio, fallback.frameHeightRatio);
    profiles[key] = {
      cameraZ: asNumber(item.cameraZ, fallback.cameraZ),
      cameraY: fallback.cameraY,
      fov: asNumber(item.fov, fallback.fov),
      pathScale: fallback.pathScale,
      frameHeightRatio,
      breathingRoom: Math.max(1.12, 1 + asNumber(item.safeMarginRatio, fallback.breathingRoom - 1)),
    };
  }
  return profiles;
}

function buildSceneOptions(catalog: Product3DRenderVideoCatalogResponse | null): SceneProfile[] {
  const scenes = asArray(catalog?.scenePresets)
    .map((item) => asRecord(item))
    .filter((item) => asString(item.key));
  if (!scenes.length) return SCENE_OPTIONS;

  const options = scenes.map((item) => {
    const key = asString(item.key);
    const fallback = SCENE_OPTIONS.find((scene) => scene.value === key);
    const asset = asRecord(item.asset);
    const placement = asRecord(item.placement);
    const fusion = asRecord(item.fusion);
    const candidates = asArray(asset.externalCandidates)
      .map((candidate) => asRecord(candidate))
      .map((candidate) => ({
        displayName: asString(candidate.displayName, asString(candidate.assetId)),
        provider: asString(candidate.provider, '待确认来源'),
        kind: asString(candidate.kind, 'scene asset'),
        license: asString(candidate.license, '待确认授权'),
        ingestStage: asString(candidate.ingestStage, 'staging_candidate'),
        workerReadiness: sceneCandidateWorkerReadinessLabel(asRecord(candidate.workerReadiness)),
        status: asString(candidate.status, 'candidate'),
        blockingReasons: asStringArray(candidate.blockingReasons),
        promotionNextAction: asString(candidate.promotionNextAction, '完成授权、视觉和 worker 导入测试后再入库。'),
      }));
    const safeZones = asStringArray(placement.safeZones);
    const geometry = asStringArray(asset.geometry);
    const fallbackSceneProps = fallback?.props || (safeZones.length ? safeZones : geometry);
    const renderElements = buildSceneRenderElements(item.renderElements, fallbackSceneProps);
    return {
      label: asString(item.label, fallback?.label || key),
      value: key,
      desc: fallback?.desc || asString(item.background, '场景背景待确认'),
      model: fallback?.model || asString(item.sceneModel, key),
      placement:
        fallback?.placement ||
        [asString(placement.anchor), asString(placement.scalePolicy)].filter(Boolean).join(' · ') ||
        asString(item.background, '按当前场景规则放置商品。'),
      props: fallback?.props || (safeZones.length ? safeZones : geometry),
      fusion: {
        landingZone: fallback?.fusion.landingZone || asString(fusion.landingZone, 'center_product_zone'),
        productScale: fallback?.fusion.productScale || asString(fusion.productScale, 'fit product safe bounds'),
        occlusionRule: fallback?.fusion.occlusionRule || asString(fusion.occlusionPolicy, asString(fusion.occlusionRule, 'props cannot occlude product')),
        propDepth: fallback?.fusion.propDepth || asString(fusion.propDepth, 'props stay behind product'),
      },
      assetId: asString(asset.assetId, `podi.scene.${key}`),
      source: sourceLabel(asset.source),
      license: licenseLabel(asset.license),
      renderFidelity: renderFidelityLabel(asset.renderFidelity),
      assetStatus: asString(asset.assetStatus, 'planned') as SceneProfile['assetStatus'],
      renderElements: renderElements.length ? renderElements : fallback?.renderElements || [],
      visualAcceptance: buildSceneVisualAcceptanceProfile(item.sceneVisualAcceptance, fallback?.visualAcceptance),
      highFidelityCandidates: candidates.length
        ? candidates
        : [
          {
            displayName: 'PODI procedural scene',
            provider: 'PODI',
            kind: 'procedural scene',
            license: 'internal',
            ingestStage: 'ready_scene_asset',
            workerReadiness: '当前渲染器可用',
            status: 'ready_scene_asset',
            blockingReasons: [],
            promotionNextAction: '当前程序化场景可执行。',
          },
        ],
    };
  });
  return options.length ? options : SCENE_OPTIONS;
}

function sceneCandidateStageLabel(stage: string): string {
  if (stage === 'staging_candidate') return '待入库';
  if (stage === 'license_review') return '授权复核';
  if (stage === 'ready_scene_asset') return '已入库';
  return stage || '待确认';
}

function sceneCandidateWorkerReadinessLabel(readiness: Record<string, unknown>): string {
  const highFidelity = asString(readiness.highFidelityWorker);
  if (highFidelity === 'requires_asset_import_test') return '待 worker 导入测试';
  if (highFidelity === 'ready') return '高保真 worker 可用';
  return highFidelity || '待 worker 测试';
}

function buildSceneVisualAcceptanceProfile(value: unknown, fallback?: SceneVisualAcceptanceProfile): SceneVisualAcceptanceProfile | undefined {
  const record = asRecord(value);
  if (!Object.keys(record).length) return fallback;
  const candidateSummary = asRecord(record.candidateSummary);
  const checks = asArray(record.checks)
    .map((item) => asRecord(item))
    .map((item) => ({
      code: asString(item.code, 'SCENE_ACCEPTANCE_CHECK'),
      label: asString(item.label, asString(item.code, '验收项')),
      status: asString(item.status, 'pending'),
      evidence: asString(item.evidence, '待补充证据'),
    }));
  const candidateAssets = asArray(record.candidateAssets)
    .map((item) => asRecord(item))
    .map((item) => ({
      assetId: asString(item.assetId, asString(item.displayName, 'candidate')),
      displayName: asString(item.displayName, asString(item.assetId, '候选资产')),
      provider: asString(item.provider, '待确认来源'),
      kind: asString(item.kind, 'scene asset'),
      license: asString(item.license, '待确认授权'),
      status: asString(item.status, 'candidate_review_required'),
      blockingReasons: asStringArray(item.blockingReasons),
      promotionNextAction: asString(item.promotionNextAction, '完成授权、视觉和 worker 导入测试后再入库。'),
    }));
  return {
    status: asString(record.status, fallback?.status || 'pending'),
    summary: asString(record.summary, fallback?.summary || '场景验收待后端确认。'),
    checks,
    candidateSummary: {
      total: asNumber(candidateSummary.total, candidateAssets.length),
      cc0Count: asNumber(candidateSummary.cc0Count, candidateAssets.filter((item) => item.license.toUpperCase() === 'CC0').length),
      readyCount: asNumber(candidateSummary.readyCount, candidateAssets.filter((item) => item.status === 'ready_scene_asset').length),
      blockedCount: asNumber(candidateSummary.blockedCount, candidateAssets.filter((item) => item.blockingReasons.length > 0).length),
    },
    candidateAssets,
  };
}

function sceneAcceptanceStatusLabel(status: string): string {
  if (status === 'mvp_ready') return '当前可执行';
  if (status === 'ready_scene_asset') return '已入库';
  if (status === 'candidate_review_required') return '待入库验收';
  if (status === 'planned') return '计划中';
  if (status === 'passed') return '通过';
  if (status === 'blocked') return '阻断';
  if (status === 'warning') return '需注意';
  if (status === 'not_applicable') return '不适用';
  return status || '待确认';
}

function sceneAcceptanceTheme(status: string): 'success' | 'warning' | 'danger' | 'primary' {
  if (status === 'mvp_ready' || status === 'ready_scene_asset' || status === 'passed') return 'success';
  if (status === 'blocked') return 'danger';
  if (status === 'planned' || status === 'candidate_review_required' || status === 'warning') return 'warning';
  return 'primary';
}

function buildSceneAssetSourceProfiles(catalog: Product3DRenderVideoCatalogResponse | null): SceneAssetSourceProfile[] {
  const sources = asArray(catalog?.sceneAssetSources).map((item) => asRecord(item));
  if (!sources.length) {
    return [
      {
        provider: 'Poly Haven',
        sourceType: 'HDRI / 3D models',
        license: 'CC0',
        commercialUse: true,
        ingestStatus: 'candidate_source',
      },
      {
        provider: 'ambientCG',
        sourceType: 'PBR materials / models',
        license: 'CC0',
        commercialUse: true,
        ingestStatus: 'candidate_source',
      },
    ];
  }
  return sources.map((item) => ({
    provider: asString(item.provider, '待确认来源'),
    sourceType: asString(item.sourceType, 'scene asset source'),
    license: asString(item.license, '待确认授权'),
    commercialUse: asBool(item.commercialUse),
    ingestStatus: asString(item.ingestStatus, 'candidate_source'),
  }));
}

function sceneSourceStatusLabel(status: string): string {
  if (status === 'candidate_source') return '候选来源';
  if (status === 'needs_license_review') return '需授权复核';
  if (status === 'ready') return '已入库';
  return status || '待确认';
}

function sceneSourceTheme(source: SceneAssetSourceProfile): 'success' | 'warning' | 'primary' {
  if (!source.commercialUse || source.ingestStatus === 'needs_license_review') return 'warning';
  if (source.license.toUpperCase().includes('CC0')) return 'success';
  return 'primary';
}

function optionMap<T extends { value: string }>(options: T[]): Record<string, T> {
  return Object.fromEntries(options.map((item) => [item.value, item]));
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

function getObjectCenterAndSize(root: THREE.Object3D) {
  const box = new THREE.Box3().setFromObject(root);
  const center = box.getCenter(new THREE.Vector3());
  const size = box.getSize(new THREE.Vector3());
  return { box, center, size };
}

function fitCameraToObject(
  camera: THREE.PerspectiveCamera,
  controls: OrbitControls,
  root: THREE.Object3D,
  distance: CameraDistance,
  modelKey: ModelKey,
  distanceProfiles: Record<string, CameraDistanceProfile> = CAMERA_DISTANCE_PROFILES,
) {
  const profile = distanceProfiles[distance] || distanceProfiles.wide || CAMERA_DISTANCE_PROFILES.wide;
  const { center, size } = getObjectCenterAndSize(root);
  const maxHeight = Math.max(0.2, size.y);
  const maxWidth = Math.max(0.2, size.x);
  const verticalFov = THREE.MathUtils.degToRad(camera.fov);
  const aspect = Math.max(0.1, camera.aspect || 16 / 9);
  const horizontalFov = 2 * Math.atan(Math.tan(verticalFov / 2) * aspect);
  const distanceForHeight = (maxHeight / Math.max(0.18, profile.frameHeightRatio)) / (2 * Math.tan(verticalFov / 2));
  const distanceForWidth = (maxWidth / Math.max(0.18, profile.frameHeightRatio)) / (2 * Math.tan(horizontalFov / 2));
  const safeZ = Math.max(profile.cameraZ, distanceForHeight, distanceForWidth) * profile.breathingRoom;
  const yOffset = modelKey === 'backpack_2551' ? -0.08 : 0.02;
  camera.position.set(center.x + 0.25, center.y + profile.cameraY + yOffset, center.z + safeZ);
  camera.near = Math.max(0.03, safeZ / 80);
  camera.far = Math.max(100, safeZ * 24);
  camera.updateProjectionMatrix();
  controls.target.set(center.x, center.y + yOffset, center.z);
  controls.update();
  return { safeCameraZ: safeZ, target: controls.target.clone(), position: camera.position.clone() };
}

function clamp01(value: number) {
  if (!Number.isFinite(value)) return 0;
  return Math.min(1, Math.max(0, value));
}

function normalizeMotionPath(points: MotionPathPoint[]): MotionPathPoint[] {
  const normalized = points
    .map((point) => ({ x: clamp01(point.x), y: clamp01(point.y) }))
    .filter((point) => Number.isFinite(point.x) && Number.isFinite(point.y))
    .slice(0, 12);
  return normalized.length >= 2 ? normalized : DEFAULT_MOTION_PATH;
}

function motionPathBounds(points: MotionPathPoint[]) {
  const path = normalizeMotionPath(points);
  const xs = path.map((point) => point.x);
  const ys = path.map((point) => point.y);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  return {
    minX,
    maxX,
    minY,
    maxY,
    spanX: maxX - minX,
    spanY: maxY - minY,
  };
}

function buildFramingSafetySummary(points: MotionPathPoint[], distance: CameraDistance, profile: CameraDistanceProfile) {
  const bounds = motionPathBounds(points);
  const safeMarginRatio = Math.max(0.04, profile.breathingRoom - 1);
  return {
    bounds,
    pointCount: normalizeMotionPath(points).length,
    frameHeightPercent: Math.round(profile.frameHeightRatio * 100),
    safeMarginPercent: Math.round(safeMarginRatio * 100),
    finalDeliveryRecommended: distance !== 'close',
    label:
      distance === 'close'
        ? '近景已强制完整入画，建议只作细节补充'
        : '当前镜头适合作为完整商品视频',
  };
}

function cameraPathProfileLabel(preset: CameraPreset, modelKey: ModelKey) {
  if (preset === 'orbit_360') return modelKey === 'cup_1660' ? '杯身 360 环绕，商品固定，镜头绕行一圈' : '主体半环绕检查轮廓与正面贴图';
  if (preset === 'detail_sweep') return '镜头横向扫过贴图和材质细节，商品不移动';
  if (preset === 'slow_push_in') return '镜头从完整商品推进到主贴图区';
  if (preset === 'top_reveal') return '镜头从上方过渡到正面，适合结构揭示';
  if (preset === 'social_arc') return '镜头走短弧线，节奏更适合社媒素材';
  if (preset === 'hero_turntable') return '主视觉稳定弧线，适合商品页首屏动效';
  return '按当前模板播放镜头轨迹，商品保持固定';
}

function buildCameraPlanPayload(params: {
  modelKey: ModelKey;
  materialSlot: string;
  cameraPreset: CameraPreset;
  cameraDistance: CameraDistance;
  scenePreset: ScenePreset;
  motionPath: MotionPathPoint[];
  durationSeconds: number;
  aspectRatio: string;
  confirmed: boolean;
}) {
  const points = normalizeMotionPath(params.motionPath);
  return {
    version: 'camera-plan-v1',
    template: params.cameraPreset,
    productMotion: 'fixed',
    cameraMotion: 'path_playback',
    playbackConfirmed: params.confirmed,
    confirmationRequiredBeforeRender: true,
    durationSeconds: params.durationSeconds,
    aspectRatio: params.aspectRatio,
    cameraDistance: params.cameraDistance,
    scenePreset: params.scenePreset,
    focusTarget: 'product_center',
    focusSlot: params.materialSlot,
    path: {
      coordinateSpace: 'normalized_camera_path_preview',
      points,
      pointCount: points.length,
    },
    constraints: {
      productFixed: true,
      keepFullProductInFrame: true,
      avoidTextureDistortion: true,
    },
    rationale: cameraPathProfileLabel(params.cameraPreset, params.modelKey),
  };
}

function createBox(size: [number, number, number], position: [number, number, number], color: number, roughness = 0.78) {
  const mesh = new THREE.Mesh(
    new THREE.BoxGeometry(size[0], size[1], size[2]),
    new THREE.MeshStandardMaterial({ color, roughness, metalness: 0.02 }),
  );
  mesh.position.set(position[0], position[1], position[2]);
  mesh.receiveShadow = true;
  mesh.castShadow = true;
  return mesh;
}

function createLandingZone(preset: ScenePreset) {
  const color = preset === 'premium_dark' ? 0x6b7280 : preset === 'marketplace_white' ? 0xd8dee8 : 0xb8c4d6;
  const mesh = new THREE.Mesh(
    new THREE.CircleGeometry(1.22, 56),
    new THREE.MeshBasicMaterial({
      color,
      transparent: true,
      opacity: preset === 'premium_dark' ? 0.22 : 0.16,
      depthWrite: false,
    }),
  );
  mesh.name = 'podi-product-landing-zone';
  mesh.rotation.x = -Math.PI / 2;
  mesh.scale.set(1.28, 0.52, 1);
  mesh.position.set(0, -1.145, 0.08);
  return mesh;
}

function createScenePresetGroup(preset: ScenePreset) {
  const group = new THREE.Group();
  group.name = `podi-scene-${preset}`;
  const isDark = preset === 'premium_dark';
  const isWhite = preset === 'marketplace_white';
  const floorColor = isDark ? 0x242833 : isWhite ? 0xffffff : 0xe8edf4;
  const wallColor = isDark ? 0x1f2430 : isWhite ? 0xffffff : 0xf3f5f8;
  const floor = new THREE.Mesh(
    new THREE.PlaneGeometry(8, 6),
    new THREE.MeshStandardMaterial({ color: floorColor, roughness: isDark ? 0.66 : 0.84, metalness: 0 }),
  );
  floor.rotation.x = -Math.PI / 2;
  floor.position.set(0, -1.16, 0.1);
  floor.receiveShadow = true;
  group.add(floor);
  group.add(createLandingZone(preset));

  const back = new THREE.Mesh(
    new THREE.PlaneGeometry(8, 3.2),
    new THREE.MeshStandardMaterial({ color: wallColor, roughness: 0.9, metalness: 0 }),
  );
  back.position.set(0, 0.45, -2.1);
  back.receiveShadow = true;
  group.add(back);

  if (preset === 'desktop_lifestyle') {
    group.add(createBox([4.8, 0.12, 2.4], [0, -1.08, 0], 0xc9a979, 0.62));
    group.add(createBox([0.52, 0.86, 0.18], [-1.55, -0.58, -1.08], 0xd9dee8, 0.7));
    group.add(createBox([0.42, 0.42, 0.42], [1.55, -0.8, -0.94], 0x9aa6b8, 0.8));
    group.add(createBox([1.35, 0.06, 0.46], [0.92, -1.0, -0.58], 0xe7d1a7, 0.68));
  }
  if (preset === 'gift_table') {
    group.add(createBox([4.6, 0.12, 2.3], [0, -1.08, 0], 0xe6d8c3, 0.7));
    group.add(createBox([0.58, 0.42, 0.58], [-1.35, -0.8, -0.92], 0xe6eef8, 0.72));
    group.add(createBox([0.46, 0.34, 0.5], [1.25, -0.83, -1.02], 0xd8b7a4, 0.72));
    group.add(createBox([1.08, 0.04, 0.28], [0.96, -0.67, -1.02], 0xefc4b1, 0.7));
  }
  if (preset === 'retail_shelf') {
    group.add(createBox([5.8, 0.12, 0.42], [0, -0.98, -1.08], 0xd7dde8, 0.76));
    group.add(createBox([5.8, 0.1, 0.36], [0, -0.2, -1.18], 0xe4e8ef, 0.78));
    group.add(createBox([5.8, 0.1, 0.32], [0, 0.58, -1.26], 0xe4e8ef, 0.78));
    group.add(createBox([0.08, 1.18, 0.26], [-2.46, -0.36, -1.04], 0xcbd5e1, 0.76));
    group.add(createBox([0.08, 1.18, 0.26], [2.46, -0.36, -1.04], 0xcbd5e1, 0.76));
  }
  if (preset === 'premium_dark') {
    group.add(createBox([4.8, 0.08, 2.2], [0, -1.1, -0.02], 0x303643, 0.58));
  }

  return group;
}

function delay(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function businessRunStatusLabel(status: string) {
  const normalized = String(status || '').toLowerCase();
  if (normalized === 'queued') return '排队中';
  if (normalized === 'running') return '生成中';
  if (normalized === 'succeeded') return '已完成';
  if (normalized === 'failed') return '失败';
  if (normalized === 'cancelled') return '已取消';
  return normalized || '未知状态';
}

function getRunVideoUrls(result: BusinessRunPollResult | null): string[] {
  if (!result) return [];
  const payload = (result.resultPayload || result.result || {}) as Record<string, unknown>;
  const videoResult = (payload.videoResult || {}) as Record<string, unknown>;
  const assetPackage = (payload.renderAssetPackage || {}) as Record<string, unknown>;
  const urls = [
    ...(Array.isArray(result.videoUrls) ? result.videoUrls : []),
    ...(Array.isArray(videoResult.videoUrls) ? (videoResult.videoUrls as string[]) : []),
    ...(typeof assetPackage.videoUrl === 'string' ? [assetPackage.videoUrl] : []),
  ];
  return Array.from(new Set(urls.map((url) => String(url || '').trim()).filter((url) => url.startsWith('http'))));
}

function getRunImageUrls(result: BusinessRunPollResult | null): string[] {
  if (!result) return [];
  const payload = (result.resultPayload || result.result || {}) as Record<string, unknown>;
  const assetPackage = (payload.renderAssetPackage || {}) as Record<string, unknown>;
  const urls = [
    ...(Array.isArray(result.imageUrls) ? result.imageUrls : []),
    ...(Array.isArray(result.image_urls) ? result.image_urls : []),
    ...(typeof assetPackage.coverFrameUrl === 'string' ? [assetPackage.coverFrameUrl] : []),
  ];
  return Array.from(new Set(urls.map((url) => String(url || '').trim()).filter((url) => url.startsWith('http'))));
}

function getRunManifestUrls(result: BusinessRunPollResult | null): string[] {
  if (!result) return [];
  const payload = (result.resultPayload || result.result || {}) as Record<string, unknown>;
  const assetPackage = (payload.renderAssetPackage || {}) as Record<string, unknown>;
  const assets = Array.isArray(assetPackage.assets) ? (assetPackage.assets as Array<Record<string, unknown>>) : [];
  const urls = [
    typeof assetPackage.manifestUrl === 'string' ? assetPackage.manifestUrl : '',
    ...assets
      .filter((asset) => String(asset.type || asset.assetType || '').toLowerCase() === 'manifest' || String(asset.role || '').toLowerCase() === 'render_manifest')
      .map((asset) => String(asset.ossUrl || asset.url || '').trim()),
  ];
  return Array.from(new Set(urls.map((url) => String(url || '').trim()).filter((url) => url.startsWith('http'))));
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

function exportVideoSizeForAspectRatio(aspectRatio: string): { width: number; height: number } {
  const [rawWidth, rawHeight] = String(aspectRatio || '16:9').split(':').map((item) => Number(item));
  const ratio = rawWidth > 0 && rawHeight > 0 ? rawWidth / rawHeight : 16 / 9;
  if (Math.abs(ratio - 1) < 0.02) return { width: 720, height: 720 };
  if (ratio < 0.75) return { width: 540, height: 960 };
  if (ratio < 0.95) return { width: 720, height: 900 };
  return { width: 960, height: 540 };
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

function enforceCameraMinimumDistance(camera: THREE.PerspectiveCamera, target: THREE.Vector3, minimumDistance: number) {
  const current = camera.position.distanceTo(target);
  if (!Number.isFinite(current) || current >= minimumDistance) return;
  const direction = camera.position.clone().sub(target).normalize();
  if (direction.lengthSq() <= 0) direction.set(0, 0.18, 1).normalize();
  camera.position.copy(target).add(direction.multiplyScalar(minimumDistance));
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
  scenePreset,
  cameraDistance,
  cameraDistanceProfiles,
  onExportHandle,
}: {
  modelKey: ModelKey;
  modelProfile: ModelProfile;
  materialSlot: string;
  textureSlotEntries: TextureSlotEntry[];
  scenePreset: ScenePreset;
  cameraDistance: CameraDistance;
  cameraDistanceProfiles: Record<string, CameraDistanceProfile>;
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
          distance: CameraDistance;
          originalPosition: THREE.Vector3;
          originalTarget: THREE.Vector3;
          minimumCameraDistance: number;
        }
      | null = null;

    host.replaceChildren();
    setPreviewStatus({ state: 'loading', message: '正在加载真实 3D 模型' });

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFShadowMap;
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.domElement.setAttribute('aria-label', `${modelProfile.title} 真实 3D 预览`);
    renderer.domElement.setAttribute('role', 'img');
    host.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(scenePreset === 'premium_dark' ? 0x1f2430 : scenePreset === 'marketplace_white' ? 0xffffff : 0xf6f8fb);
    scene.add(createScenePresetGroup(scenePreset));

    const distanceProfile = cameraDistanceProfiles[cameraDistance] || cameraDistanceProfiles.wide || CAMERA_DISTANCE_PROFILES.wide;
    const camera = new THREE.PerspectiveCamera(distanceProfile.fov, 1, 0.1, 100);
    camera.position.set(0.25, modelKey === 'backpack_2551' ? distanceProfile.cameraY - 0.1 : distanceProfile.cameraY, distanceProfile.cameraZ);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.enablePan = false;
    controls.autoRotate = true;
    controls.autoRotateSpeed = 0.65;
    controls.target.set(0, 0, 0);

    scene.add(new THREE.HemisphereLight(0xffffff, 0xd7dde8, 2.2));
    const keyLight = new THREE.DirectionalLight(0xffffff, 2.4);
    keyLight.position.set(3, 4, 5);
    keyLight.castShadow = true;
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
      if (modelRoot && !recording) fitCameraToObject(camera, controls, modelRoot, cameraDistance, modelKey, cameraDistanceProfiles);
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
        modelRoot.traverse((child) => {
          const mesh = child as THREE.Mesh;
          if (!mesh.isMesh) return;
          mesh.castShadow = true;
          mesh.receiveShadow = true;
        });
        scene.add(modelRoot);
        const framing = fitCameraToObject(camera, controls, modelRoot, cameraDistance, modelKey, cameraDistanceProfiles);

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
        camera.userData.minimumCameraDistance = Math.max(2, framing.safeCameraZ * 0.82);
      },
      undefined,
      (error) => {
        const detail = error instanceof Error && error.message ? `：${error.message}` : '';
        if (!disposed) setPreviewStatus({ state: 'error', message: `模型加载失败，请检查 GLB/Draco 文件${detail}` });
      },
    );

    const beginCameraPlayback = (seconds: number, preset: CameraPreset, distance: CameraDistance) => {
      if (!modelRoot) throw new Error('3D 模型还没有加载完成，请等待预览显示“已应用贴图”后再生成视频。');
      const framing = fitCameraToObject(camera, controls, modelRoot, distance, modelKey, cameraDistanceProfiles);
      const originalPosition = framing.position.clone();
      const originalTarget = framing.target.clone();
      const minimumCameraDistance = Math.max(2, framing.safeCameraZ * 0.82);
      const originalAutoRotate = controls.autoRotate;
      const originalAutoRotateSpeed = controls.autoRotateSpeed;
      recording = {
        startAt: performance.now(),
        durationMs: Math.max(1, seconds) * 1000,
        preset,
        distance,
        originalPosition,
        originalTarget,
        minimumCameraDistance,
      };
      controls.autoRotate = false;
      controls.autoRotateSpeed = 0;
      return {
        originalPosition,
        originalTarget,
        originalAutoRotate,
        originalAutoRotateSpeed,
        restore: () => {
          recording = null;
          camera.position.copy(originalPosition);
          controls.target.copy(originalTarget);
          controls.autoRotate = originalAutoRotate;
          controls.autoRotateSpeed = originalAutoRotateSpeed;
          controls.update();
        },
      };
    };

    const playCameraPath = async (seconds: number, preset: CameraPreset, distance: CameraDistance) => {
      const playback = beginCameraPlayback(seconds, preset, distance);
      try {
        await delay(Math.max(1, seconds) * 1000 + 120);
      } finally {
        playback.restore();
      }
    };

    const exportVideo = async (seconds: number, preset: CameraPreset, distance: CameraDistance, aspectRatio: string) => {
      if (!modelRoot) throw new Error('3D 模型还没有加载完成，请等待预览显示“已应用贴图”后再生成视频。');
      if (typeof MediaRecorder === 'undefined') throw new Error('当前浏览器不支持 MediaRecorder，无法本地录制 3D 预览视频。');
      if (!('captureStream' in renderer.domElement)) throw new Error('当前浏览器不支持 canvas.captureStream，无法导出 3D 预览视频。');

      const exportSize = exportVideoSizeForAspectRatio(aspectRatio);
      renderer.setSize(exportSize.width, exportSize.height, false);
      camera.aspect = exportSize.width / exportSize.height;
      camera.updateProjectionMatrix();

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

      const playback = beginCameraPlayback(seconds, preset, distance);
      recorder.start(100);
      try {
        await delay(Math.max(1, seconds) * 1000 + 160);
        if (recorder.state !== 'inactive') recorder.stop();
        return await stopped;
      } finally {
        playback.restore();
        resize();
      }
    };

    onExportHandle?.({ playCameraPath, exportVideo });

    const animate = () => {
      if (recording) {
        const progress = (performance.now() - recording.startAt) / recording.durationMs;
        applyCameraMotion(camera, controls, recording.preset, recording.originalPosition, recording.originalTarget, progress);
        enforceCameraMinimumDistance(camera, controls.target, recording.minimumCameraDistance);
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
  }, [cameraDistance, cameraDistanceProfiles, materialSlot, modelKey, modelProfile, onExportHandle, scenePreset, textureSlotEntries]);

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

function CameraPathEditor({
  value,
  onChange,
  cameraPreset,
  modelKey,
  confirmed,
  playbackStatus,
}: {
  value: MotionPathPoint[];
  onChange: (next: MotionPathPoint[]) => void;
  cameraPreset: CameraPreset;
  modelKey: ModelKey;
  confirmed: boolean;
  playbackStatus: CameraPathPlaybackStatus;
}) {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const drawingRef = useRef(false);
  const draftRef = useRef<MotionPathPoint[]>(value.length ? value : DEFAULT_MOTION_PATH);
  const points = value.length ? value : DEFAULT_MOTION_PATH;
  const polyline = points.map((point) => `${point.x * 100},${point.y * 100}`).join(' ');
  const startPoint = points[0] || DEFAULT_MOTION_PATH[0];
  const endPoint = points[points.length - 1] || DEFAULT_MOTION_PATH[DEFAULT_MOTION_PATH.length - 1];

  useEffect(() => {
    draftRef.current = value.length ? value : DEFAULT_MOTION_PATH;
  }, [value]);

  const readPoint = (event: ReactPointerEvent<SVGSVGElement>): MotionPathPoint => {
    const rect = svgRef.current?.getBoundingClientRect();
    if (!rect) return { x: 0.5, y: 0.5 };
    return {
      x: clamp01((event.clientX - rect.left) / Math.max(1, rect.width)),
      y: clamp01((event.clientY - rect.top) / Math.max(1, rect.height)),
    };
  };

  const addPoint = (point: MotionPathPoint) => {
    const current = draftRef.current.length ? draftRef.current : [point];
    const last = current[current.length - 1];
    if (Math.hypot(last.x - point.x, last.y - point.y) < 0.035) return;
    draftRef.current = [...current, point].slice(-12);
    onChange(draftRef.current);
  };

  return (
    <div className="podi-product-3d-render__motion-editor">
      <div>
        <Typography.Text strong>镜头轨迹预览</Typography.Text>
        <Typography.Text theme="secondary">
          商品固定在场景中；这里画的是相机路径和取景节奏。先播放确认镜头轨迹，再生成本地或服务端视频。
        </Typography.Text>
      </div>
      <svg
        ref={svgRef}
        viewBox="0 0 100 100"
        role="img"
        aria-label="3D 镜头轨迹编辑器"
        onPointerDown={(event) => {
          drawingRef.current = true;
          event.currentTarget.setPointerCapture(event.pointerId);
          draftRef.current = [readPoint(event)];
          onChange(draftRef.current);
        }}
        onPointerMove={(event) => {
          if (!drawingRef.current) return;
          addPoint(readPoint(event));
        }}
        onPointerUp={(event) => {
          drawingRef.current = false;
          event.currentTarget.releasePointerCapture(event.pointerId);
          if (draftRef.current.length < 2) onChange(DEFAULT_MOTION_PATH);
        }}
      >
        <rect className="podi-product-3d-render__motion-bg" x="0" y="0" width="100" height="100" rx="6" />
        <rect className="podi-product-3d-render__motion-safe-zone" x="8" y="12" width="84" height="74" rx="8" />
        <ellipse className="podi-product-3d-render__motion-floor" cx="50" cy="62" rx="24" ry="14" />
        <circle className="podi-product-3d-render__camera-product-anchor" cx="50" cy="56" r={modelKey === 'cup_1660' ? 8 : 10} />
        <path className="podi-product-3d-render__motion-guide" d="M 10 72 C 30 58, 58 48, 90 34" />
        <polyline className="podi-product-3d-render__motion-line" points={polyline} />
        {points.map((point, index) => (
          <circle className="podi-product-3d-render__motion-point" key={`${point.x}-${point.y}-${index}`} cx={point.x * 100} cy={point.y * 100} r={index === 0 ? 3.4 : 2.6} />
        ))}
        <text className="podi-product-3d-render__motion-label" x={clamp01(startPoint.x) * 100 + 4} y={clamp01(startPoint.y) * 100 - 4}>
          起点
        </text>
        <text className="podi-product-3d-render__motion-label" x={Math.max(6, clamp01(endPoint.x) * 100 - 18)} y={clamp01(endPoint.y) * 100 - 4}>
          终点
        </text>
        <text className="podi-product-3d-render__motion-label" x="42" y="58">
          商品固定
        </text>
      </svg>
      <div className="podi-product-3d-render__motion-actions">
        <Tag theme="primary" variant="light">{points.length} 个镜头点</Tag>
        <Tag theme="success" variant="light">商品固定</Tag>
        <Tag theme={confirmed ? 'success' : playbackStatus === 'playing' ? 'primary' : 'warning'} variant="light">
          {confirmed ? '轨迹已确认' : playbackStatus === 'playing' ? '正在播放' : '待播放确认'}
        </Tag>
        <Button size="small" variant="outline" onClick={() => onChange(DEFAULT_MOTION_PATH)}>
          恢复推荐轨迹
        </Button>
      </div>
      <Typography.Text theme="secondary">{cameraPathProfileLabel(cameraPreset, modelKey)}</Typography.Text>
    </div>
  );
}

export function Product3DRenderVideoWorkbench() {
  const uploadRef = useRef<HTMLInputElement | null>(null);
  const [modelKey, setModelKey] = useState<ModelKey>('cup_1660');
  const [catalog, setCatalog] = useState<Product3DRenderVideoCatalogResponse | null>(null);
  const [catalogStatus, setCatalogStatus] = useState<'loading' | 'ready' | 'fallback'>('loading');
  const [catalogError, setCatalogError] = useState('');
  const [slotTextureUrls, setSlotTextureUrls] = useState<SlotTextureState>({});
  const [uploadingSlot, setUploadingSlot] = useState('');
  const [materialSlot, setMaterialSlot] = useState('front');
  const [cameraPreset, setCameraPreset] = useState<CameraPreset>('orbit_360');
  const [cameraDistance, setCameraDistance] = useState<CameraDistance>('wide');
  const [scenePreset, setScenePreset] = useState<ScenePreset>('clean_studio');
  const [motionPath, setMotionPath] = useState<MotionPathPoint[]>(DEFAULT_MOTION_PATH);
  const [durationSeconds, setDurationSeconds] = useState(6);
  const [aspectRatio, setAspectRatio] = useState('16:9');
  const [result, setResult] = useState<Product3DRenderVideoResponse | null>(null);
  const [status, setStatus] = useState<WorkStatus>('idle');
  const [error, setError] = useState('');
  const [previewHandle, setPreviewHandle] = useState<Product3DPreviewHandle | null>(null);
  const [videoExportStatus, setVideoExportStatus] = useState<VideoExportStatus>('idle');
  const [cameraPathPlaybackStatus, setCameraPathPlaybackStatus] = useState<CameraPathPlaybackStatus>('idle');
  const [cameraPathConfirmed, setCameraPathConfirmed] = useState(false);
  const [videoExportError, setVideoExportError] = useState('');
  const videoOutputRef = useRef<HTMLDivElement | null>(null);
  const serverOutputRef = useRef<HTMLDivElement | null>(null);
  const [localVideo, setLocalVideo] = useState<{
    url: string;
    name: string;
    size: number;
    mimeType: string;
    format: VideoExportFormat;
    label: string;
  } | null>(null);
  const [serverRun, setServerRun] = useState<ServerRenderRunState | null>(null);

  useEffect(() => {
    let cancelled = false;
    setCatalogStatus('loading');
    setCatalogError('');
    evalApi
      .getProduct3DRenderVideoCatalog()
      .then((response) => {
        if (cancelled) return;
        if (!asArray(response.models).length || !asArray(response.scenePresets).length) {
          setCatalog(null);
          setCatalogStatus('fallback');
          setCatalogError('能力目录为空，已使用本地默认模型与场景配置。');
          return;
        }
        setCatalog(response);
        setCatalogStatus('ready');
      })
      .catch((err) => {
        if (cancelled) return;
        setCatalog(null);
        setCatalogStatus('fallback');
        setCatalogError(String((err as any)?.message || err || '能力目录读取失败，已使用本地默认配置。'));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const modelProfiles = useMemo(() => buildModelProfiles(catalog), [catalog]);
  const modelOptions = useMemo(() => buildModelOptions(modelProfiles), [modelProfiles]);
  const cameraOptions = useMemo(() => buildCameraOptions(catalog), [catalog]);
  const cameraOptionMap = useMemo(() => optionMap(cameraOptions), [cameraOptions]);
  const cameraDistanceOptions = useMemo(() => buildCameraDistanceOptions(catalog), [catalog]);
  const cameraDistanceOptionMap = useMemo(() => optionMap(cameraDistanceOptions), [cameraDistanceOptions]);
  const cameraDistanceProfiles = useMemo(() => buildCameraDistanceProfiles(catalog), [catalog]);
  const sceneOptions = useMemo(() => buildSceneOptions(catalog), [catalog]);
  const sceneOptionMap = useMemo(() => optionMap(sceneOptions), [sceneOptions]);
  const durationOptions = useMemo(() => {
    const values = Array.isArray(catalog?.durationOptions) && catalog.durationOptions.length ? catalog.durationOptions : [3, 5, 6, 8, 12];
    return values.map((seconds) => ({ label: `${seconds} 秒`, value: String(seconds) }));
  }, [catalog]);
  const aspectRatioOptions = useMemo(() => (catalog?.aspectRatioOptions?.length ? catalog.aspectRatioOptions : ['16:9', '1:1', '4:5', '9:16']), [catalog]);
  const modelProfile = modelProfiles[modelKey] || Object.values(modelProfiles)[0] || MODEL_PROFILES.cup_1660;
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
  const selectedSceneProfile = sceneOptionMap[scenePreset] || sceneOptions[0] || SCENE_OPTIONS[0];
  const sceneAssetSourceProfiles = useMemo(() => buildSceneAssetSourceProfiles(catalog), [catalog]);
  const selectedDistanceProfile = cameraDistanceProfiles[cameraDistance] || cameraDistanceProfiles.wide || CAMERA_DISTANCE_PROFILES.wide;
  const localFramingSafety = useMemo(
    () => buildFramingSafetySummary(motionPath, cameraDistance, selectedDistanceProfile),
    [cameraDistance, motionPath, selectedDistanceProfile],
  );

  useEffect(() => {
    if (modelProfiles[modelKey]) return;
    const next = Object.keys(modelProfiles)[0] || 'cup_1660';
    setModelKey(next);
    setMaterialSlot(modelProfiles[next]?.firstSlot || 'front');
    setSlotTextureUrls({});
    setResult(null);
    clearLocalVideo();
  }, [modelKey, modelProfiles]);

  useEffect(() => {
    if (modelProfile.materialSlots.includes(materialSlot)) return;
    setMaterialSlot(modelProfile.firstSlot || modelProfile.materialSlots[0] || 'front');
    setResult(null);
    clearLocalVideo();
  }, [materialSlot, modelProfile]);

  useEffect(() => {
    if (cameraOptionMap[cameraPreset]) return;
    setCameraPreset(cameraOptions[0]?.value || 'orbit_360');
    setResult(null);
    clearLocalVideo();
  }, [cameraOptionMap, cameraOptions, cameraPreset]);

  useEffect(() => {
    if (cameraDistanceOptionMap[cameraDistance]) return;
    setCameraDistance(cameraDistanceOptions[0]?.value || 'wide');
    setResult(null);
    clearLocalVideo();
  }, [cameraDistance, cameraDistanceOptionMap, cameraDistanceOptions]);

  useEffect(() => {
    if (sceneOptionMap[scenePreset]) return;
    setScenePreset(sceneOptions[0]?.value || 'clean_studio');
    setResult(null);
    clearLocalVideo();
  }, [sceneOptionMap, sceneOptions, scenePreset]);

  function clearLocalVideo() {
    setLocalVideo((prev) => {
      if (prev?.url) URL.revokeObjectURL(prev.url);
      return null;
    });
    setServerRun(null);
    setVideoExportStatus('idle');
    setCameraPathPlaybackStatus('idle');
    setCameraPathConfirmed(false);
    setVideoExportError('');
  }

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

  useEffect(() => {
    if (!serverRun?.videoUrls.length) return;
    window.requestAnimationFrame(() => {
      serverOutputRef.current?.scrollIntoView({ block: 'center', behavior: 'smooth' });
    });
  }, [serverRun?.videoUrls.length]);

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

  const buildRequestPayload = (outputMode: 'plan_only' | 'render_video'): Product3DRenderVideoRequest => ({
    modelKey,
    textureImageUrl: primaryTextureImageUrl || undefined,
    textureImageUrls,
    textureSlots: textureSlotEntries,
    materialSlot,
    cameraPreset,
    cameraDistance,
    scenePreset,
    motionPath: normalizeMotionPath(motionPath),
    cameraPlan: buildCameraPlanPayload({
      modelKey,
      materialSlot,
      cameraPreset,
      cameraDistance,
      scenePreset,
      motionPath,
      durationSeconds,
      aspectRatio,
      confirmed: cameraPathConfirmed,
    }),
    durationSeconds,
    aspectRatio,
    outputMode,
    source: 'eval-product-3d-render-video',
    requestId: `eval-p3d-${Date.now()}`,
  });

  const previewPlan = async () => {
    setError('');
    setStatus('previewing');
    try {
      const response = await evalApi.previewProduct3DRenderVideo(buildRequestPayload('plan_only'));
      setResult(response);
    } catch (err) {
      setError(String((err as any)?.message || err || '方案预览失败'));
    } finally {
      setStatus('idle');
    }
  };

  const playAndConfirmCameraPath = async () => {
    setError('');
    setVideoExportError('');
    if (!previewHandle) {
      setCameraPathPlaybackStatus('error');
      setVideoExportError('3D 预览还没有准备好，请等待模型加载完成后再播放镜头轨迹。');
      return;
    }
    setCameraPathPlaybackStatus('playing');
    setCameraPathConfirmed(false);
    try {
      await previewHandle.playCameraPath(durationSeconds, cameraPreset, cameraDistance);
      setCameraPathConfirmed(true);
      setCameraPathPlaybackStatus('confirmed');
      MessagePlugin.success('镜头轨迹已播放并确认，可以生成预览或服务端视频');
    } catch (err) {
      setCameraPathPlaybackStatus('error');
      setVideoExportError(String((err as any)?.message || err || '镜头轨迹播放失败'));
    }
  };

  const exportLocalPreviewVideo = async () => {
    setError('');
    setVideoExportError('');
    if (!cameraPathConfirmed) {
      setVideoExportStatus('error');
      setVideoExportError('请先播放并确认镜头轨迹，再生成本地预览视频。');
      return;
    }
    if (!previewHandle) {
      setVideoExportStatus('error');
      setVideoExportError('3D 预览还没有准备好，请等待模型加载完成后再生成本地视频。');
      return;
    }
    setVideoExportStatus('recording');
    try {
      const exported = await previewHandle.exportVideo(durationSeconds, cameraPreset, cameraDistance, aspectRatio);
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

  const pollServerRenderRun = async (
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
    throw new Error('服务端渲染轮询超时，请复制 runId 到任务追踪继续排查');
  };

  const runServerRenderVideo = async () => {
    setError('');
    setVideoExportError('');
    if (!cameraPathConfirmed) {
      setError('请先播放并确认镜头轨迹，再提交服务端 MP4/OSS 视频。');
      return;
    }
    if (!primaryTextureImageUrl) {
      setError('服务端生成视频必须先给至少一个材质槽绑定贴图。');
      return;
    }
    setStatus('server_rendering');
    setServerRun(null);
    try {
      const submitted = await evalApi.submitProduct3DRenderVideoRun(buildRequestPayload('render_video'));
      const runId = String(submitted.runId || submitted.id || submitted.taskId || '').trim();
      if (!runId) throw new Error('服务端未返回 runId');
      setServerRun({
        runId,
        status: String(submitted.status || submitted.taskStatus || 'queued'),
        elapsedSeconds: 0,
        videoUrls: getRunVideoUrls(submitted),
        imageUrls: getRunImageUrls(submitted),
        manifestUrls: getRunManifestUrls(submitted),
        resultPayload: submitted.resultPayload || submitted.result || null,
      });
      const finalPoll = await pollServerRenderRun(runId, (poll, elapsedSeconds) => {
        setServerRun({
          runId,
          status: String(poll.status || poll.taskStatus || 'running'),
          elapsedSeconds,
          videoUrls: getRunVideoUrls(poll),
          imageUrls: getRunImageUrls(poll),
          manifestUrls: getRunManifestUrls(poll),
          resultPayload: poll.resultPayload || poll.result || null,
        });
      });
      const videoUrls = getRunVideoUrls(finalPoll);
      if (!videoUrls.length) throw new Error('服务端任务已完成但没有返回视频 URL');
      setServerRun((prev) => ({
        runId,
        status: 'succeeded',
        elapsedSeconds: prev?.elapsedSeconds,
        videoUrls,
        imageUrls: getRunImageUrls(finalPoll),
        manifestUrls: getRunManifestUrls(finalPoll),
        resultPayload: finalPoll.resultPayload || finalPoll.result || null,
      }));
      MessagePlugin.success('服务端 3D 渲染视频已生成');
    } catch (err) {
      setError(String((err as any)?.message || err || '服务端视频生成失败'));
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
  const framingSafety = asRecord(renderPlan.framingSafety || asRecord(asRecord(camera.framing).safety));
  const framingSafetyBounds = asRecord(framingSafety.motionPathBounds);
  const review = asRecord(result?.review);
  const issues = asArray(review.issues).map((item) => asRecord(item));
  const selectedSceneAcceptance = selectedSceneProfile.visualAcceptance;
  const resultSceneAcceptance = buildSceneVisualAcceptanceProfile(renderPlan.sceneVisualAcceptance, selectedSceneAcceptance);
  const activeSceneAcceptance = resultSceneAcceptance || selectedSceneAcceptance;
  const sceneAcceptanceChecks = activeSceneAcceptance?.checks || [];
  const sceneAcceptanceCandidates = activeSceneAcceptance?.candidateAssets || [];
  const activeSlot = String(textureApplication.materialSlot || materialSlot);
  const shouldShowLocalVideoPanel = Boolean(localVideo || videoExportStatus === 'recording');
  const shouldShowServerRunPanel = Boolean(serverRun);
  const localVideoStatusText =
    videoExportStatus === 'recording'
      ? `录制中 · ${durationSeconds}s`
      : localVideo
        ? `${Math.max(1, Math.round(localVideo.size / 1024))} KB · ${localVideo.label}`
        : '尚未生成';
  const serverVideoStatusText = serverRun
    ? `${businessRunStatusLabel(serverRun.status)} · runId=${serverRun.runId}`
    : '尚未提交';
  const localVideoPanel = (
    <div ref={videoOutputRef} className="podi-product-3d-render__video-output">
      <div className="podi-product-commercialization__panel-head">
        <Typography.Text strong>本地预览视频</Typography.Text>
        <Typography.Text theme="secondary">{localVideoStatusText}</Typography.Text>
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
          theme="info"
          message="正在按当前镜头预设录制，请保持页面打开。"
        />
      )}
    </div>
  );
  const serverRunPanel = (
    <div ref={serverOutputRef} className="podi-product-3d-render__video-output podi-product-3d-render__video-output--server">
      <div className="podi-product-commercialization__panel-head">
        <Typography.Text strong>服务端 OSS 视频</Typography.Text>
        <Typography.Text theme="secondary">
          {serverRun
            ? `${businessRunStatusLabel(serverRun.status)} · runId=${serverRun.runId}${serverRun.elapsedSeconds ? ` · ${serverRun.elapsedSeconds}s` : ''}`
            : '尚未提交'}
        </Typography.Text>
      </div>
      {serverRun?.videoUrls.length ? (
        <>
          <video src={serverRun.videoUrls[0]} controls poster={serverRun.imageUrls[0]} />
          <div className="podi-product-3d-render__server-assets" aria-label="服务端渲染交付资产">
            <div>
              <Typography.Text theme="secondary">封面帧</Typography.Text>
              {serverRun.imageUrls[0] ? <img src={serverRun.imageUrls[0]} alt="服务端渲染封面帧" /> : <span>无封面帧</span>}
            </div>
            <div>
              <Typography.Text theme="secondary">交付证据</Typography.Text>
              <strong>runId={serverRun.runId}</strong>
              <span>MP4 {serverRun.videoUrls.length} 个 · 封面 {serverRun.imageUrls.length} 张 · manifest {serverRun.manifestUrls.length} 个</span>
            </div>
          </div>
          <Space>
            <Button variant="outline" onClick={() => window.open(serverRun.videoUrls[0], '_blank', 'noreferrer')}>
              打开 OSS 视频
            </Button>
            {serverRun.imageUrls[0] ? (
              <Button variant="outline" onClick={() => window.open(serverRun.imageUrls[0], '_blank', 'noreferrer')}>
                打开封面帧
              </Button>
            ) : null}
            {serverRun.manifestUrls[0] ? (
              <Button variant="outline" onClick={() => window.open(serverRun.manifestUrls[0], '_blank', 'noreferrer')}>
                打开 manifest
              </Button>
            ) : null}
            <Button
              theme="primary"
              onClick={() => {
                const anchor = document.createElement('a');
                anchor.href = serverRun.videoUrls[0];
                anchor.download = `podi-3d-server-${serverRun.runId}.mp4`;
                document.body.appendChild(anchor);
                anchor.click();
                anchor.remove();
              }}
            >
              下载 MP4
            </Button>
          </Space>
        </>
      ) : (
        <Alert
          theme={status === 'server_rendering' ? 'info' : 'warning'}
          message={
            status === 'server_rendering'
              ? `服务端正在生成 MP4${serverRun?.runId ? `，runId=${serverRun.runId}` : ''}`
              : '还没有服务端视频。点击“生成服务端 MP4/OSS 视频”后，这里会显示可交付的 OSS 视频。'
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
            这不是 KIE/Vidu 大模型视频。当前用 Three.js 做所见即所得预览，服务端轻量渲染负责 MP4、封面和 OSS 回填。
          </Typography.Text>
        </div>
        <Space align="center">
          <Tag theme={catalogStatus === 'ready' ? 'success' : catalogStatus === 'loading' ? 'primary' : 'warning'} variant="light">
            {catalogStatus === 'ready' ? '能力目录已同步' : catalogStatus === 'loading' ? '读取能力目录' : '本地默认配置'}
          </Tag>
          <Tag theme="primary" variant="light">确定性渲染</Tag>
          <Tag theme="success" variant="light">材质槽 / UV</Tag>
          <Tag theme="warning" variant="light">本地预览</Tag>
          <Tag theme="primary" variant="light">OSS 视频</Tag>
        </Space>
      </div>

      {error ? <Alert theme="error" message={error} /> : null}
      {videoExportError ? <Alert theme="error" message={videoExportError} /> : null}
      <Alert
        theme="info"
        message="当前有两条输出路径：浏览器本地预览用于快速看贴图和镜头；服务端 MP4/OSS 走统一业务 run，生成后可在任务追踪和接口结果中复用。"
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
                  setMaterialSlot(modelProfiles[key]?.firstSlot || 'front');
                  setSlotTextureUrls({});
                  setResult(null);
                  clearLocalVideo();
                }}
                options={modelOptions}
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
                  scenePreset={scenePreset}
                  cameraDistance={cameraDistance}
                  cameraDistanceProfiles={cameraDistanceProfiles}
                  onExportHandle={setPreviewHandle}
                />
                <p>当前是真实 GLB/UV 客户端预览：贴图按材质名应用到模型表面，可拖拽检查位置和方向。服务端 MP4 会复用同一组槽位、场景、镜头和路径参数。</p>
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
              <Typography.Title level="h4">选择镜头方案并确认轨迹</Typography.Title>
              <Typography.Text theme="secondary">商品保持固定，镜头按轨迹运动。先播放确认镜头，再生成本地预览或服务端视频。</Typography.Text>
            </div>
            <div className="podi-product-commercialization__controls">
              <Select
                label="镜头"
                value={cameraPreset}
                onChange={(v) => {
                  setCameraPreset(String(v) as CameraPreset);
                  setResult(null);
                  clearLocalVideo();
                }}
                options={cameraOptions}
              />
              <Select
                label="镜头远近"
                value={cameraDistance}
                onChange={(v) => {
                  setCameraDistance(String(v) as CameraDistance);
                  setResult(null);
                  clearLocalVideo();
                }}
                options={cameraDistanceOptions}
              />
              <Select
                label="场景"
                value={scenePreset}
                onChange={(v) => {
                  setScenePreset(String(v) as ScenePreset);
                  setResult(null);
                  clearLocalVideo();
                }}
                options={sceneOptions}
              />
              <Select
                label="时长"
                value={String(durationSeconds)}
                onChange={(v) => {
                  setDurationSeconds(Number(v) || 6);
                  setResult(null);
                  clearLocalVideo();
                }}
                options={durationOptions}
              />
              <Select
                label="比例"
                value={aspectRatio}
                onChange={(v) => {
                  setAspectRatio(String(v));
                  setResult(null);
                  clearLocalVideo();
                }}
                options={aspectRatioOptions.map((item) => ({ label: item, value: item }))}
              />
            </div>
            <div className="podi-product-3d-render__execution-panel" aria-label="3D 视频生成主操作">
              <div className="podi-product-3d-render__video-actions">
                <Button theme="primary" loading={status === 'previewing'} onClick={() => void previewPlan()}>
                  1. 检查 3D 贴图方案
                </Button>
                <Button
                  theme="success"
                  loading={cameraPathPlaybackStatus === 'playing'}
                  disabled={!previewHandle || cameraPathPlaybackStatus === 'playing'}
                  onClick={() => void playAndConfirmCameraPath()}
                >
                  2. 播放并确认镜头轨迹
                </Button>
                <Button
                  theme="success"
                  loading={videoExportStatus === 'recording'}
                  disabled={!previewHandle || !cameraPathConfirmed || videoExportStatus === 'recording'}
                  onClick={() => void exportLocalPreviewVideo()}
                >
                  3. 生成本地预览视频
                </Button>
                <Button
                  theme="primary"
                  loading={status === 'server_rendering'}
                  disabled={!primaryTextureImageUrl || !cameraPathConfirmed || status === 'server_rendering'}
                  onClick={() => void runServerRenderVideo()}
                >
                  4. 生成服务端 MP4/OSS 视频
                </Button>
              </div>
              <Typography.Text theme="secondary">
                主执行区：先检查方案，再播放镜头轨迹确认，最后生成本地预览或提交服务端 MP4/OSS。调整镜头、场景或轨迹后需要重新确认。
              </Typography.Text>
              <div className="podi-product-3d-render__execution-status" aria-label="3D 视频输出状态">
                <div>
                  <strong>镜头轨迹</strong>
                  <span>
                    {cameraPathConfirmed
                      ? '已播放确认'
                      : cameraPathPlaybackStatus === 'playing'
                        ? `播放中 · ${durationSeconds}s`
                        : '待播放确认'}
                  </span>
                </div>
                <div>
                  <strong>本地预览</strong>
                  <span>{localVideoStatusText}</span>
                </div>
                <div>
                  <strong>服务端 OSS</strong>
                  <span>{serverVideoStatusText}</span>
                </div>
              </div>
            </div>
            {shouldShowLocalVideoPanel ? localVideoPanel : null}
            {shouldShowServerRunPanel ? serverRunPanel : null}
            <div className="podi-product-3d-render__scene-rail" aria-label="场景模型选择">
              {sceneOptions.map((item) => (
                <button
                  key={item.value}
                  type="button"
                  className={item.value === scenePreset ? 'is-active' : ''}
                  onClick={() => {
                    setScenePreset(item.value);
                    setResult(null);
                    clearLocalVideo();
                  }}
                >
                  <div className={`podi-product-3d-render__scene-thumb is-${item.value}`} aria-hidden="true">
                    <span className="podi-product-3d-render__scene-thumb-backdrop" />
                    <span className="podi-product-3d-render__scene-thumb-floor" />
                    <span className="podi-product-3d-render__scene-thumb-prop is-left" />
                    <span className="podi-product-3d-render__scene-thumb-product" />
                    <span className="podi-product-3d-render__scene-thumb-prop is-right" />
                  </div>
                  <strong>{item.label}</strong>
                  <span>{item.desc}</span>
                  <small>{item.model}</small>
                  <small>{item.fusion.occlusionRule}</small>
                  <small>{item.source} · {item.renderFidelity}</small>
                </button>
              ))}
            </div>
            <div className="podi-product-3d-render__shooting-brief" aria-label="当前 3D 拍摄方案">
              <div>
                <Typography.Text theme="secondary">场景模型</Typography.Text>
                <Typography.Text strong>{selectedSceneProfile.model}</Typography.Text>
                <small>{selectedSceneProfile.placement}</small>
              </div>
              <div>
                <Typography.Text theme="secondary">融合检查</Typography.Text>
                <Typography.Text strong>{selectedSceneProfile.fusion.landingZone}</Typography.Text>
                <small>{selectedSceneProfile.fusion.productScale} · {selectedSceneProfile.fusion.occlusionRule}</small>
              </div>
              {activeSceneAcceptance ? (
                <div>
                  <Typography.Text theme="secondary">场景验收</Typography.Text>
                  <Space size="small" breakLine>
                    <Tag theme={sceneAcceptanceTheme(activeSceneAcceptance.status)} variant="light">
                      {sceneAcceptanceStatusLabel(activeSceneAcceptance.status)}
                    </Tag>
                    <Tag theme="primary" variant="light">
                      候选 {activeSceneAcceptance.candidateSummary.total} · 待处理 {activeSceneAcceptance.candidateSummary.blockedCount}
                    </Tag>
                  </Space>
                  <small>{activeSceneAcceptance.summary}</small>
                  <Space size="small" breakLine>
                    {sceneAcceptanceChecks.slice(0, 5).map((item) => (
                      <Tag key={item.code} theme={sceneAcceptanceTheme(item.status)} variant="light">
                        {item.label} · {sceneAcceptanceStatusLabel(item.status)}
                      </Tag>
                    ))}
                  </Space>
                </div>
              ) : null}
              <div>
                <Typography.Text theme="secondary">场景资产</Typography.Text>
                <Typography.Text strong>{selectedSceneProfile.assetId}</Typography.Text>
                <small>{selectedSceneProfile.license} · {selectedSceneProfile.renderFidelity}</small>
              </div>
              <div>
                <Typography.Text theme="secondary">高保真候选</Typography.Text>
                <Space size="small" breakLine>
                  {(sceneAcceptanceCandidates.length ? sceneAcceptanceCandidates : selectedSceneProfile.highFidelityCandidates).map((item) => (
                    <Tag
                      key={`${item.provider}-${item.kind}-${item.license}-${item.displayName || ''}`}
                      theme={sceneAcceptanceTheme(item.status || (item.license === 'CC0' ? 'planned' : 'blocked'))}
                      variant="light"
                    >
                      {item.displayName && item.displayName !== item.provider
                        ? `${item.provider} · ${item.displayName}`
                        : item.provider}
                      {' · '}
                      {item.kind} · {item.license}
                    </Tag>
                  ))}
                </Space>
                <small>
                  {(sceneAcceptanceCandidates[0]?.blockingReasons || selectedSceneProfile.highFidelityCandidates[0]?.blockingReasons || []).slice(0, 3).join(' / ')
                    || selectedSceneProfile.highFidelityCandidates[0]?.workerReadiness
                    || '待 worker 测试'}
                  ；候选资产入库前必须记录来源、授权、版本并通过视觉/导入验收。
                </small>
              </div>
              <div>
                <Typography.Text theme="secondary">来源治理</Typography.Text>
                <Space size="small" breakLine>
                  {sceneAssetSourceProfiles.slice(0, 3).map((item) => (
                    <Tag key={`${item.provider}-${item.ingestStatus}`} theme={sceneSourceTheme(item)} variant="light">
                      {item.provider} · {item.license} · {sceneSourceStatusLabel(item.ingestStatus)}
                    </Tag>
                  ))}
                </Space>
                <small>业务执行只选场景预设；外部素材必须先过授权、版本、视觉和性能验收。</small>
              </div>
              <div>
                <Typography.Text theme="secondary">场景结构</Typography.Text>
                <Space size="small" breakLine>
                  {selectedSceneProfile.renderElements.slice(0, 4).map((item) => (
                    <Tag key={`${item.elementId}-${item.depthLayer}`} theme="primary" variant="light">
                      {sceneDepthLayerLabel(item.depthLayer)} · {item.label}
                    </Tag>
                  ))}
                </Space>
                <small>
                  {selectedSceneProfile.renderElements[0]?.occlusion || selectedSceneProfile.fusion.occlusionRule}
                </small>
              </div>
              <div>
                <Typography.Text theme="secondary">场景道具</Typography.Text>
                <Space size="small" breakLine>
                  {selectedSceneProfile.props.map((item) => (
                    <Tag key={item} theme="primary" variant="light">{item}</Tag>
                  ))}
                </Space>
              </div>
              <div>
                <Typography.Text theme="secondary">安全取景</Typography.Text>
                <Typography.Text strong>{localFramingSafety.frameHeightPercent}% 画面高度</Typography.Text>
                <small>保留 {localFramingSafety.safeMarginPercent}% 呼吸空间；{localFramingSafety.label}。</small>
              </div>
              <div>
                <Typography.Text theme="secondary">镜头轨迹范围</Typography.Text>
                <Typography.Text strong>
                  X {Math.round(localFramingSafety.bounds.spanX * 100)}% · Y {Math.round(localFramingSafety.bounds.spanY * 100)}%
                </Typography.Text>
                <small>{localFramingSafety.pointCount} 个镜头点；轨迹驱动相机运动，商品固定在场景中。</small>
              </div>
            </div>
            <CameraPathEditor
              value={motionPath}
              onChange={(next) => {
                setMotionPath(next);
                setResult(null);
                clearLocalVideo();
              }}
              cameraPreset={cameraPreset}
              modelKey={modelKey}
              confirmed={cameraPathConfirmed}
              playbackStatus={cameraPathPlaybackStatus}
            />
            <div className="podi-product-3d-render__preset-summary">
              <div>
                <Typography.Text strong>镜头模板 · {cameraOptionMap[cameraPreset]?.label || cameraPreset}</Typography.Text>
                <Typography.Text theme="secondary">{cameraOptionMap[cameraPreset]?.desc || '按当前镜头路径录制。'}</Typography.Text>
              </div>
              <div>
                <Typography.Text strong>镜头远近 · {cameraDistanceOptionMap[cameraDistance]?.label || cameraDistance}</Typography.Text>
                <Typography.Text theme="secondary">{cameraDistanceOptionMap[cameraDistance]?.desc || '按当前远近档位安全取景。'}</Typography.Text>
              </div>
              <div>
                <Typography.Text strong>场景模型 · {sceneOptionMap[scenePreset]?.label || scenePreset}</Typography.Text>
                <Typography.Text theme="secondary">{selectedSceneProfile.placement || sceneOptionMap[scenePreset]?.desc || '按当前场景摆放商品。'}</Typography.Text>
              </div>
            </div>
          </section>

          <section className="podi-product-commercialization__stage-panel">
            <div className="podi-product-commercialization__stage-title">
              <span>RESULT</span>
              <Typography.Title level="h4">资产准备度与下一步</Typography.Title>
              <Typography.Text theme="secondary">这里展示方案检查、本地预览和服务端 MP4/OSS 输出状态。</Typography.Text>
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
                    {
                      label: '场景资产',
                      value: `${asBool(readiness.sceneAssetReady) ? '已就绪' : '待核验'} · ${String(readiness.sceneAssetId || selectedSceneProfile.assetId)}`,
                    },
                    { label: '3D 预览', value: '已接入 GLB/UV' },
                    { label: '渲染 worker', value: serverRun?.videoUrls.length ? '已输出 MP4' : asBool(readiness.renderWorkerReady) ? '可执行' : '待生成' },
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
                    <strong>融合规则</strong>
                    <span>{String(asRecord(scene.fusion).landingZone || selectedSceneProfile.fusion.landingZone)}</span>
                    <small>{String(asRecord(scene.fusion).occlusionRule || selectedSceneProfile.fusion.occlusionRule)}</small>
                  </div>
                  {activeSceneAcceptance ? (
                    <div>
                      <strong>场景验收合同</strong>
                      <span>
                        {sceneAcceptanceStatusLabel(activeSceneAcceptance.status)} · 候选 {activeSceneAcceptance.candidateSummary.total} · 阻断 {activeSceneAcceptance.candidateSummary.blockedCount}
                      </span>
                      <small>
                        {sceneAcceptanceChecks
                          .slice(0, 4)
                          .map((item) => `${item.label}:${sceneAcceptanceStatusLabel(item.status)}`)
                          .join(' / ')}
                      </small>
                    </div>
                  ) : null}
                  <div>
                    <strong>镜头 · {String(camera.label || cameraPreset)}</strong>
                    <span>{String(camera.description || '')}</span>
                    <small>
                      {durationSeconds}s · {aspectRatio} · {String(asRecord(camera.framing).mode || 'fit_product_safe_bounds')}
                    </small>
                  </div>
                  <div>
                    <strong>取景合同</strong>
                    <span>
                      {String(framingSafety.cameraDistance || cameraDistance)} · {Math.round(asNumber(framingSafety.frameHeightRatio, selectedDistanceProfile.frameHeightRatio) * 100)}% 画面高度 · 安全边距 {Math.round(asNumber(framingSafety.safeMarginRatio, selectedDistanceProfile.breathingRoom - 1) * 100)}%
                    </span>
                    <small>
                      镜头轨迹跨度 X {Math.round(asNumber(framingSafetyBounds.spanX, localFramingSafety.bounds.spanX) * 100)}% / Y {Math.round(asNumber(framingSafetyBounds.spanY, localFramingSafety.bounds.spanY) * 100)}% · {cameraPathConfirmed ? '已播放确认' : '待播放确认'} · {framingSafety.finalDeliveryRecommended === false ? '近景仅建议作细节补充' : '可作为完整商品视频'}
                    </small>
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
            <Typography.Text strong>能力目录</Typography.Text>
            <p>
              {catalogStatus === 'ready'
                ? `已同步 ${modelOptions.length} 个模型 / ${sceneOptions.length} 个场景 · ${catalog?.version || 'catalog'}`
                : catalogStatus === 'loading'
                  ? '正在读取后端能力目录。'
                  : `后端目录不可用，当前使用本地兜底配置。${catalogError}`}
            </p>
          </div>
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
            <p>3D 渲染视频是确定性渲染路线：客户端负责 Three.js 所见即所得预览，服务端负责 MP4、封面帧和 OSS 回填。它不调用 GPT Image 2、KIE 或 Vidu。</p>
          </div>
          <div className="podi-product-commercialization__side-card">
            <Typography.Text strong>当前视频</Typography.Text>
            <p>
              {videoExportStatus === 'recording'
                ? `正在录制 ${durationSeconds}s`
                : serverRun?.videoUrls.length
                  ? `OSS 视频已生成 · runId=${serverRun.runId}`
                  : localVideo
                    ? `已生成本地 ${durationSeconds}s ${localVideo.label}`
                    : '待生成本地预览或服务端 MP4'}
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
