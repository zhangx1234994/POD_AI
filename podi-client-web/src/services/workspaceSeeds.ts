import type { UploadResult } from '../types/media';
import type { WorkspaceLocationState } from '../types/workspace';

type TemplateSeedInput = {
  id: string;
  title: string;
  prompt: string;
};

type AssetSeedInput = {
  image: string;
  title: string;
  source?: string;
  type?: 'image' | 'video';
  tags?: string[];
  pathHint?: string;
  origin?: 'upload' | 'result';
  abilityKey?: string | null;
  provider?: string | null;
};

function buildUpload(image: string, title: string): UploadResult {
  return {
    url: image,
    objectKey: image,
    name: title,
    size: 0,
  };
}

export function buildTemplateLocationState(template: TemplateSeedInput): WorkspaceLocationState {
  return {
    seedDraft: {
      formValues: { prompt: template.prompt },
      source: 'template',
      templateId: template.id,
      templateTitle: template.title,
      focusField: 'prompt',
    },
  };
}

export function buildAssetLocationState(asset: AssetSeedInput): WorkspaceLocationState {
  return {
    seedDraft: {
      uploads: [buildUpload(asset.image, asset.title)],
      formValues: { prompt: `${asset.title}：延续当前画面风格与主体视觉。` },
      source: 'asset',
      focusField: 'prompt',
    },
  };
}

function buildContinueState(
  asset: AssetSeedInput,
  {
    prompt,
    source,
    includeUpload = asset.type !== 'video',
  }: {
    prompt: string;
    source: string;
    includeUpload?: boolean;
  },
): WorkspaceLocationState {
  return {
    seedDraft: {
      uploads: includeUpload ? [buildUpload(asset.image, asset.title)] : [],
      formValues: { prompt },
      source,
      focusField: 'prompt',
    },
  };
}

const abilityTransitionMap: Record<string, { path: string; prompt: (asset: AssetSeedInput) => string; source: string; includeUpload?: boolean }> = {
  doubao_seedream_4_5: {
    path: '/design/style-to-style',
    prompt: (asset) => `${asset.title}：沿用这次生成出来的款式方向，继续做版型、细节和风格延展。`,
    source: 'asset-design-direction',
  },
  yinhua_tiqu: {
    path: '/design/seamless',
    prompt: (asset) => `${asset.title}：基于当前图案继续生成可用于面料与印花的四方连续纹理。`,
    source: 'asset-pattern',
  },
  sifang_lianxu: {
    path: '/design/pattern-recolor',
    prompt: (asset) => `${asset.title}：延续当前连续纹理结构，探索更适合系列化应用的新配色。`,
    source: 'asset-seamless',
  },
  nano_banana_pro_image_to_image: {
    path: '/shoot/marketing-variants',
    prompt: (asset) => `${asset.title}：围绕当前结果继续扩展适合电商详情页和活动页的营销画面。`,
    source: 'asset-commerce',
  },
  nano_banana_2_image_to_image: {
    path: '/shoot/marketing-variants',
    prompt: (asset) => `${asset.title}：围绕当前结果继续扩展适合电商详情页和活动页的营销画面。`,
    source: 'asset-commerce',
  },
  quality_upgrade: {
    path: '/toolbox/dpi',
    prompt: (asset) => `${asset.title}：在清晰度提升后继续做交付前的 DPI 与输出参数收口。`,
    source: 'asset-delivery',
  },
  upscale_resize: {
    path: '/toolbox/dpi',
    prompt: (asset) => `${asset.title}：在尺寸缩放后继续做交付前的 DPI 与输出参数收口。`,
    source: 'asset-delivery',
  },
  set_dpi: {
    path: '/shoot/marketing-variants',
    prompt: (asset) => `${asset.title}：基于已完成交付参数的终稿，继续扩展营销主图和详情页画面。`,
    source: 'asset-delivery-finished',
  },
  seedance_1_5_pro: {
    path: '/shoot/marketing-variants',
    prompt: (asset) => `${asset.title}：围绕现有视频结果延展新的营销主图与详情页画面，保持主体风格一致。`,
    source: 'asset-video',
    includeUpload: false,
  },
};

const pathTransitionMap: Record<string, { path: string; prompt: (asset: AssetSeedInput) => string; source: string; includeUpload?: boolean }> = {
  '/design/text-to-style': {
    path: '/design/style-to-style',
    prompt: (asset) => `${asset.title}：沿用当前款式方向，继续做改款和结构延展。`,
    source: 'asset-design-direction',
  },
  '/design/style-to-style': {
    path: '/shoot/marketing-variants',
    prompt: (asset) => `${asset.title}：基于当前成衣结果继续扩展适合电商详情页和活动页的营销画面。`,
    source: 'asset-commerce',
  },
  '/design/pattern-extract': {
    path: '/design/seamless',
    prompt: (asset) => `${asset.title}：把当前提取稿继续做成可平铺应用的四方连续纹理。`,
    source: 'asset-pattern',
  },
  '/design/seamless': {
    path: '/design/pattern-recolor',
    prompt: (asset) => `${asset.title}：延续当前连续结构，探索新的系列化配色。`,
    source: 'asset-seamless',
  },
  '/design/pattern-recolor': {
    path: '/design/pattern-craft',
    prompt: (asset) => `${asset.title}：在当前配色基础上继续补图案工艺与成品质感表达。`,
    source: 'asset-pattern-craft',
  },
  '/toolbox/outpaint': {
    path: '/toolbox/upscale',
    prompt: (asset) => `${asset.title}：扩图完成后继续提升清晰度与边缘质量。`,
    source: 'asset-upscale',
  },
  '/toolbox/upscale': {
    path: '/toolbox/dpi',
    prompt: (asset) => `${asset.title}：清晰度处理完成后继续收口 DPI 和输出参数。`,
    source: 'asset-dpi',
  },
  '/shoot/marketing-variants': {
    path: '/shoot/detail-shots',
    prompt: (asset) => `${asset.title}：围绕当前营销主图继续补拍细节图和材质特写。`,
    source: 'asset-detail-shots',
  },
  '/shoot/detail-shots': {
    path: '/shoot/image-to-video',
    prompt: (asset) => `${asset.title}：围绕现有细节图继续生成短视频素材，保持主体质感一致。`,
    source: 'asset-video',
  },
};

export function resolveContinueCreationTarget(asset: AssetSeedInput) {
  if (asset.origin === 'upload' && asset.pathHint) {
    return {
      path: asset.pathHint,
      state: buildAssetLocationState(asset),
    };
  }

  const keywords = [asset.title, asset.source || '', asset.provider || '', asset.abilityKey || '', ...(asset.tags || [])].join(' ');
  const isVideo = asset.type === 'video';
  const abilityTransition = asset.abilityKey ? abilityTransitionMap[asset.abilityKey] : null;
  if (abilityTransition) {
    return {
      path: abilityTransition.path,
      state: buildContinueState(asset, {
        prompt: abilityTransition.prompt(asset),
        source: abilityTransition.source,
        includeUpload: abilityTransition.includeUpload,
      }),
    };
  }

  const pathTransition = asset.origin === 'result' && asset.pathHint ? pathTransitionMap[asset.pathHint] : null;
  if (pathTransition) {
    return {
      path: pathTransition.path,
      state: buildContinueState(asset, {
        prompt: pathTransition.prompt(asset),
        source: pathTransition.source,
        includeUpload: pathTransition.includeUpload,
      }),
    };
  }

  if (isVideo) {
    return {
      path: '/shoot/marketing-variants',
      state: buildContinueState(asset, {
        prompt: `${asset.title}：围绕现有视频结果延展新的营销主图与详情页画面，保持主体风格一致。`,
        source: 'asset-video',
        includeUpload: false,
      }),
    };
  }

  if (/图案提取|印花|花型/.test(keywords)) {
    return {
      path: '/design/seamless',
      state: buildContinueState(asset, {
        prompt: `${asset.title}：基于当前图案继续生成可用于面料与印花的四方连续纹理。`,
        source: 'asset-pattern',
      }),
    };
  }

  if (/连续|纹理/.test(keywords)) {
    return {
      path: '/design/pattern-recolor',
      state: buildContinueState(asset, {
        prompt: `${asset.title}：延续当前纹理结构，探索更适合系列化应用的新配色。`,
        source: 'asset-pattern',
      }),
    };
  }

  if (/扩图|主图|营销|商拍|细节/.test(keywords)) {
    return {
      path: '/shoot/marketing-variants',
      state: buildContinueState(asset, {
        prompt: `${asset.title}：围绕当前素材继续扩展适合电商详情页和活动页的营销画面。`,
        source: 'asset-commerce',
      }),
    };
  }

  if (/超清|缩放|DPI/.test(keywords)) {
    return {
      path: '/toolbox/upscale',
      state: buildContinueState(asset, {
        prompt: `${asset.title}：提升清晰度与边缘质量，准备进入终稿交付。`,
        source: 'asset-delivery',
      }),
    };
  }

  if (asset.pathHint) {
    return {
      path: asset.pathHint,
      state: buildAssetLocationState(asset),
    };
  }

  return {
    path: '/design/style-to-style',
    state: buildAssetLocationState(asset),
  };
}
