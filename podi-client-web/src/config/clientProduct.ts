import { buildEditorialVisual, clientVisualRegistry } from './clientVisuals';

export type ProductMetric = {
  label: string;
  value: string;
  note: string;
};

export type ProductWorkflow = {
  id: string;
  title: string;
  subtitle: string;
  note: string;
  path: string;
  category: 'design' | 'shoot' | 'toolbox';
  accent: 'sky' | 'amber' | 'emerald' | 'rose' | 'violet' | 'cyan';
};

export type ProductScenario = {
  id: string;
  label: string;
  title: string;
  summary: string;
  outcome: string;
  path: string;
  image: string;
};

export type StudioRoute = {
  id: string;
  title: string;
  summary: string;
  steps: string[];
  path: string;
};

export type ProductTemplate = {
  id: string;
  title: string;
  summary: string;
  prompt: string;
  path: string;
  category: 'design' | 'shoot' | 'toolbox';
};

export const productNorthStar = {
  title: '行业 SaaS 设计生产平台',
  subtitle: '不是把模型摆上来，而是把设计、商拍、处理、资产沉淀和续费路径组织成一个可持续使用的生产系统。',
  primaryCta: { label: '进入工作室', path: '/studio' },
  secondaryCta: { label: '查看案例路径', path: '/design/text-to-style' },
  helper: '第一阶段先盯住获客、激活、留存、变现 4 段漏斗，把高频工作流做深。',
};

export const funnelMetrics: ProductMetric[] = [
  { label: '首任务发起率', value: 'AARRR-01', note: '注册后是否真正进入工作流' },
  { label: '首任务成功可回看率', value: 'AARRR-02', note: '结果是否回到当前页并可继续操作' },
  { label: '7日二次任务率', value: 'AARRR-03', note: '用户有没有从一次试用进入持续使用' },
  { label: '结果沉淀率', value: 'AARRR-04', note: '结果有没有进入素材与模板体系' },
  { label: '低余额转化率', value: 'AARRR-05', note: '高频用户是否顺滑进入付费路径' },
];

export const launchWorkflows: ProductWorkflow[] = [
  {
    id: 'design-text',
    title: '以文生款',
    subtitle: '一句话起稿',
    note: '适合新用户第一次体验，从灵感直接进入款式方向。',
    path: '/design/text-to-style',
    category: 'design',
    accent: 'sky',
  },
  {
    id: 'design-style',
    title: '以款生款',
    subtitle: '高频改款',
    note: '适合设计团队围绕稳定参考款快速做延展与讨论。',
    path: '/design/style-to-style',
    category: 'design',
    accent: 'amber',
  },
  {
    id: 'design-pattern',
    title: '图案提取',
    subtitle: '沉淀图案资产',
    note: '适合把一次性图片转成可持续复用的设计资产。',
    path: '/design/pattern-extract',
    category: 'design',
    accent: 'emerald',
  },
  {
    id: 'shoot-variants',
    title: '裂变套图',
    subtitle: '营销主图扩展',
    note: '适合电商运营快速批量拿到不同场景的营销图。',
    path: '/shoot/marketing-variants',
    category: 'shoot',
    accent: 'rose',
  },
  {
    id: 'shoot-video',
    title: '图生视频',
    subtitle: '把静态图变动销素材',
    note: '适合把已验证的主图继续扩展为短视频素材。',
    path: '/shoot/image-to-video',
    category: 'shoot',
    accent: 'violet',
  },
  {
    id: 'tool-upscale',
    title: 'AI超清',
    subtitle: '交付前增强',
    note: '适合把最终结果收口成更适合详情页和交付的终稿。',
    path: '/toolbox/upscale',
    category: 'toolbox',
    accent: 'cyan',
  },
];

export const landingScenarios: ProductScenario[] = [
  {
    id: 'scenario-design',
    label: '获客场景',
    title: '设计团队不想再在草图、参考图和讨论稿之间来回折返。',
    summary: '平台把以文生款、以款生款、图案提取和四方连续串成稳定工作流，减少“先导出、再找图、再重做”的损耗。',
    outcome: '目标结果：更快拿到可讨论、可继续改、可沉淀的方向稿。',
    path: '/design/text-to-style',
    image: clientVisualRegistry.landingDesign.url,
  },
  {
    id: 'scenario-commerce',
    label: '激活场景',
    title: '运营同学需要的不只是出图，而是主图、套图、视频都能在一个工作区连起来。',
    summary: '平台把裂变套图、细节图、图生视频和工具箱串成连续路径，让首个结果不是终点，而是下一步素材入口。',
    outcome: '目标结果：第一次产出就进入任务中心和素材中心，第二次回来不从零开始。',
    path: '/shoot/marketing-variants',
    image: clientVisualRegistry.landingCommerce.url,
  },
  {
    id: 'scenario-assets',
    label: '留存场景',
    title: '所有结果都要沉淀成资产，而不是一次性下载后散落在聊天记录里。',
    summary: '平台把原图、结果图、视频、模板、复跑路径都沉进资产层，让下一次创作从已有结果继续。',
    outcome: '目标结果：形成可复跑、可复用、可团队共享的素材与模板库。',
    path: '/assets',
    image: clientVisualRegistry.landingAssets.url,
  },
];

export const studioRoutes: StudioRoute[] = [
  {
    id: 'route-design',
    title: '先做设计方向，再进入图案资产化',
    summary: '适合季度上新、系列开发、品牌企划讨论。',
    steps: ['以文生款', '以款生款', '图案提取', '四方连续'],
    path: '/design/text-to-style',
  },
  {
    id: 'route-commerce',
    title: '先做营销主图，再裂变成多平台素材',
    summary: '适合详情页、活动图、渠道素材同步推进。',
    steps: ['裂变套图', '服装细节图', '图生视频', 'AI超清'],
    path: '/shoot/marketing-variants',
  },
  {
    id: 'route-delivery',
    title: '先拿到结果，再集中收口到可交付终稿',
    summary: '适合已经定稿的素材进入终稿增强和参数统一。',
    steps: ['AI超清', '高质量缩放', 'DPI处理', '沉淀到素材中心'],
    path: '/toolbox/upscale',
  },
];

export const templateLibrary: ProductTemplate[] = [
  {
    id: 'template-atelier',
    title: '春夏都市通勤系列',
    summary: '适合女装上新，强调高级成衣感、利落轮廓和可继续改款。',
    prompt: '围绕都市通勤女装生成一组系列方向，强调高级成衣感、面料层次、利落结构和雾感中性色。',
    path: '/design/text-to-style',
    category: 'design',
  },
  {
    id: 'template-pattern',
    title: '花型净稿与连续化',
    summary: '适合把实拍图案提成干净资产，再做连续纹理。',
    prompt: '只保留图案主体，清理背景和干扰，让结果适合继续做四方连续和配色。',
    path: '/design/pattern-extract',
    category: 'design',
  },
  {
    id: 'template-market',
    title: '电商主图裂变包',
    summary: '适合从一张主图扩展出详情页、活动图和渠道图。',
    prompt: '围绕当前产品输出多张电商营销图，背景干净，突出主体和卖点细节，适合详情页与活动页。',
    path: '/shoot/marketing-variants',
    category: 'shoot',
  },
  {
    id: 'template-video',
    title: '短视频种草延展',
    summary: '适合把已验证主图继续做短视频动销素材。',
    prompt: '保留主体风格和产品定义，将静态图延展成适合种草和电商投放的短视频画面。',
    path: '/shoot/image-to-video',
    category: 'shoot',
  },
  {
    id: 'template-delivery',
    title: '终稿增强与交付',
    summary: '适合把定稿图集中做超清、尺寸和 DPI 收口。',
    prompt: '提升画面清晰度与边缘质量，保留主体真实质感，让结果更适合详情页、印刷和最终交付。',
    path: '/toolbox/upscale',
    category: 'toolbox',
  },
];

export const commercialSignals = [
  {
    title: '免费试用不是终点',
    note: '首任务成功后，需要立刻把用户导向任务中心、素材中心和下一步推荐。',
  },
  {
    title: '余额必须始终可见',
    note: '用户每一步都要知道当前余额、预计消耗和升级入口，避免在提交时才理解商业规则。',
  },
  {
    title: '案例和模板是运营资产',
    note: '不是只做静态展示，而是都能反向带入动作，提升首任务发起率和二次使用率。',
  },
];

export const productVisualSupply = {
  currentSource: 'Unsplash editorial placeholders via clientVisualRegistry',
  currentControl: 'src/config/clientVisuals.ts',
  replacementMode: '后续替换为品牌案例图或运营素材库时，页面组件无需改动。',
  diagnosticPreview: buildEditorialVisual('photo-1515886657613-9f3515b0c78f'),
};
