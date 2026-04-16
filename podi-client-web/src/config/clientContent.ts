import { clientVisualRegistry } from './clientVisuals';

export type ContentSignal = {
  label: string;
  title: string;
};

export type ContentCard = {
  label: string;
  title: string;
  note: string;
};

export type StudioRibbonItem = {
  label: string;
  value: string;
};

export type StudioShowcaseFallback = {
  id: string;
  label: string;
  title: string;
  subtitle: string;
  image: string;
};

export type StudioSuggestion = {
  key: string;
  label: string;
};

export type ImageExample = {
  id: string;
  label: string;
  title: string;
  image: string;
};

export const homeHeroSignals: ContentSignal[] = [
  {
    label: '为什么现在开始',
    title: '首屏先解释路径，不让用户在目录里迷路。',
  },
  {
    label: '为什么值得继续',
    title: '结果会回到当前页，也会进入任务与资产中心。',
  },
  {
    label: '为什么不是一次性工具',
    title: '余额、套餐、模板和复跑都属于同一条生产链。',
  },
];

export const homeLayerCards: ContentCard[] = [
  {
    label: '获客与转化前台',
    title: '行业案例、试用入口、价格锚点在同一条叙事里。',
    note: '首页先解决为什么注册、为什么现在开始、为什么值得继续付费。',
  },
  {
    label: '生产工作台',
    title: 'Studio 承接所有高频业务动作，结果回到当前页。',
    note: '不是只会提交任务，而是支持继续创作、回看结果和进入下一步工作流。',
  },
  {
    label: '资产与经营中心',
    title: '素材、模板、账单、套餐都围绕复用和续费设计。',
    note: '目标不是一次性出图，而是形成个人与团队的持续生产系统。',
  },
];

export const studioRibbon: StudioRibbonItem[] = [
  {
    label: '推荐流程',
    value: '灵感输入 -> 选择智能体 -> 进入具体能力页',
  },
  {
    label: '适合人群',
    value: '设计师 / 商拍运营 / 打样协同',
  },
  {
    label: '当前方向',
    value: '先把高频入口和闭环做顺',
  },
];

export const studioShowcaseFallbacks: StudioShowcaseFallback[] = [
  {
    id: 'showcase-agent',
    label: '今日主打',
    title: '时尚设计智能体',
    subtitle: '适合先从品牌方向和款式意图起手',
    image: clientVisualRegistry.studioAgentFashion.url,
  },
  {
    id: 'showcase-design',
    label: '研发设计',
    title: '春夏印花方向白板',
    subtitle: '提取、连续、放大一条线推进',
    image: clientVisualRegistry.studioBoardDesign.url,
  },
  {
    id: 'showcase-commerce',
    label: '视觉商拍',
    title: '电商主图裂变板',
    subtitle: '主图、套图、视频持续扩展',
    image: clientVisualRegistry.studioBoardCommerce.url,
  },
];

export const studioWorkbenchPrompt =
  '例如：帮我做一组春夏女装印花方向，先出 3 个款式，再提取其中一个图案做四方连续。';

export const studioWorkbenchSuggestions: StudioSuggestion[] = [
  { key: 'pattern', label: '春夏印花方向' },
  { key: 'commerce', label: '电商主图裂变' },
  { key: 'seamless', label: '面料纹理连续' },
];

export const studioCreateBoardCard = {
  label: '我的白板',
  title: '开始新设计',
  summary: '从灵感参考、参考图、结果图继续推进一个新的设计项目。',
  image: clientVisualRegistry.studioBoardCreate.url,
};

export const workspacePreviewExamples: ImageExample[] = [
  {
    id: 'workspace-preview-design',
    label: '示例 1',
    title: '春季新款',
    image: clientVisualRegistry.workspacePreviewDesign.url,
  },
  {
    id: 'workspace-preview-commerce',
    label: '示例 2',
    title: '夏季单品',
    image: clientVisualRegistry.workspacePreviewCommerce.url,
  },
];
