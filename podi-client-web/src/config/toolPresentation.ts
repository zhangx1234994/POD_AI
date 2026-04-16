import type { ShellMode } from '../types/workspace';

export type ToolCaseView = {
  badge: string;
  title: string;
  note: string;
};

export type ToolFollowup = {
  label: string;
  path: string;
  note: string;
};

export type ToolPresentation = {
  heroTitle?: string;
  heroNote?: string;
  workflowTags?: string[];
  quickRecipes?: string[];
  caseViews?: ToolCaseView[];
  followups?: ToolFollowup[];
};

const defaultByMode: Record<ShellMode, ToolPresentation> = {
  design: {
    heroTitle: '先把方向跑通，再继续改款、提图案、做连续纹理。',
    heroNote: '设计工作流的重点不是一次出满所有图，而是快速得到可讨论、可复用、可继续加工的方向稿。',
    workflowTags: ['灵感收束', '方向稿', '图案资产'],
    quickRecipes: [
      '保留主体轮廓，强化成衣感和面料层次，突出高级时装表达。',
      '围绕当前参考款做新色和新图案变体，保持结构稳定。',
      '让图案更适合面料连续使用，画面更干净，便于后续加工。',
    ],
    caseViews: [
      { badge: '方向图', title: '企划方向', note: '适合讨论系列风格与结构' },
      { badge: '延展图', title: '变体延展', note: '适合继续改款和配色' },
      { badge: '资产图', title: '图案沉淀', note: '适合提取成素材与模板' },
      { badge: '商拍预演', title: '营销过渡', note: '适合继续转到视觉商拍' },
    ],
    followups: [
      { label: '继续做图案提取', path: '/design/pattern-extract', note: '把方向图整理成可复用花型资产' },
      { label: '继续做四方连续', path: '/design/seamless', note: '让花型适配面料和连续铺陈' },
      { label: '转到视觉商拍', path: '/shoot/marketing-variants', note: '把当前方向继续变成营销素材' },
    ],
  },
  shoot: {
    heroTitle: '先拿到能打的主图，再补细节、套图和视频。',
    heroNote: '商拍工作流的关键是让结果直接进入转化场景，而不是只停在一张示例图。',
    workflowTags: ['营销主图', '详情页', '动销素材'],
    quickRecipes: [
      '围绕当前产品生成高质感电商主图，背景干净，突出主体细节。',
      '保留主体不变，生成多角度营销套图，适合详情页和渠道投放。',
      '补充更强的商业氛围、可信场景和材质细节，用于转化素材。',
    ],
    caseViews: [
      { badge: '主图', title: '点击入口', note: '适合首图和渠道封面' },
      { badge: '详情', title: '卖点补强', note: '适合详情页和导购图' },
      { badge: '视频', title: '动态延展', note: '适合继续做短视频' },
      { badge: '套图', title: '批量产出', note: '适合多平台同步投放' },
    ],
    followups: [
      { label: '继续做细节图', path: '/shoot/detail-shots', note: '补足详情页局部证据和卖点' },
      { label: '继续做图生视频', path: '/shoot/image-to-video', note: '把静态结果延展成动销素材' },
      { label: '转到工具箱', path: '/toolbox/upscale', note: '对终稿做清晰度与尺寸收口' },
    ],
  },
  toolbox: {
    heroTitle: '先把结果收口，再决定尺寸、清晰度和交付参数。',
    heroNote: '工具箱不是孤立动作，而是让前面得到的结果真正变成可交付终稿。',
    workflowTags: ['终稿增强', '尺寸收口', '交付参数'],
    quickRecipes: [
      '提升画面清晰度与边缘质量，保留主体纹理与真实质感。',
      '在不破坏主体的前提下补足边缘区域，适配更多版式尺寸。',
      '让结果更适合印刷或交付，细节更稳定，参数更规整。',
    ],
    caseViews: [
      { badge: '增强前', title: '原始结果', note: '先看哪里需要增强和收口' },
      { badge: '增强后', title: '终稿提升', note: '适合详情页和交付' },
      { badge: '尺寸版', title: '版式适配', note: '适合不同渠道尺寸' },
      { badge: '交付版', title: '最终参数', note: '适合印刷与归档' },
    ],
    followups: [
      { label: '继续做高质量缩放', path: '/toolbox/resize', note: '匹配具体版式与投放尺寸' },
      { label: '继续做 DPI 处理', path: '/toolbox/dpi', note: '适配印刷和终稿参数' },
      { label: '回到素材中心', path: '/assets', note: '把终稿沉淀为后续模板和资产' },
    ],
  },
};

const toolOverrides: Record<string, ToolPresentation> = {
  'text-to-style': {
    quickRecipes: [
      '设计一组春夏女装方向，轻复古，高级成衣质感，突出面料层次和轮廓控制。',
      '围绕都市通勤风做新款方向，颜色克制，强调高级面料与利落结构。',
      '生成适合品牌企划会讨论的成衣概念图，风格统一，细节完整，可继续延展。',
    ],
    caseViews: [
      { badge: '方向图', title: '品牌方向', note: '适合企划讨论与初版视觉定调' },
      { badge: '成衣图', title: '结构表达', note: '适合继续进入改款与细化' },
      { badge: '延展图', title: '系列扩展', note: '适合衍生更多同风格方向' },
      { badge: '商拍预演', title: '营销预览', note: '适合转入商拍线继续裂变' },
    ],
    followups: [
      { label: '继续做以款生款', path: '/design/style-to-style', note: '把当前方向继续扩成更多变体' },
      { label: '继续做图案提取', path: '/design/pattern-extract', note: '如果方向稳定，就开始整理花型资产' },
      { label: '转到视觉商拍', path: '/shoot/marketing-variants', note: '把方向图延展成营销素材' },
    ],
  },
  fusion: {
    quickRecipes: [
      '保留图一主体结构，参考图二图案语言与图三配色，生成一个完整新款方向。',
      '以主图为产品定义，其他参考图只提供风格和氛围，不覆盖主体比例与结构。',
      '融合多张参考图的材质、色感与花型关系，得到更适合研发讨论的新方向。',
    ],
    caseViews: [
      { badge: '主图', title: '主体定义', note: '锁定结构、比例与产品关系' },
      { badge: '融合图', title: '风格收束', note: '整合多个参考图的关键信息' },
      { badge: '配色图', title: '色感尝试', note: '适合继续推多色版本' },
      { badge: '展示图', title: '落地预演', note: '适合转入营销素材线' },
    ],
    followups: [
      { label: '继续做局部改款', path: '/design/local-redraw', note: '把大方向定下来后继续微调局部' },
      { label: '继续做图案配色', path: '/design/pattern-recolor', note: '围绕当前融合结果继续试色' },
      { label: '转到商拍套图', path: '/shoot/marketing-variants', note: '把融合结果变成展示素材' },
    ],
  },
  'pattern-extract': {
    quickRecipes: [
      '只保留图案主体，清理背景和干扰元素，输出干净、可继续处理的印花稿。',
      '保留花型边缘和关键纹理，让图案更适合后续配色与连续化处理。',
      '提取主体图案，不要文字、水印、阴影和多余背景，画面尽量规整。',
    ],
    caseViews: [
      { badge: '原稿', title: '图案主体', note: '重点保留花型核心结构' },
      { badge: '净稿', title: '背景清理', note: '去掉杂物、水印和干扰' },
      { badge: '工艺稿', title: '可编辑资产', note: '适合继续做连续与配色' },
      { badge: '成品稿', title: '沉淀素材', note: '适合进入面料与印花流程' },
    ],
    followups: [
      { label: '继续做四方连续', path: '/design/seamless', note: '让提取后的花型适合连续使用' },
      { label: '继续做图案配色', path: '/design/pattern-recolor', note: '围绕当前花型继续做多色版本' },
      { label: '转到工具箱', path: '/toolbox/upscale', note: '对提取结果做清晰度增强' },
    ],
  },
  seamless: {
    quickRecipes: [
      '让边缘自然连续，保留主花元素和节奏，适合面料与印花连续使用。',
      '提升连续边缘的自然度，避免接缝感，让整体排布更适合大面积铺陈。',
      '保留主图案关系和层次，生成更稳定的四方连续纹理。',
    ],
    caseViews: [
      { badge: '单元', title: '主花单元', note: '保留主图案与节奏关系' },
      { badge: '连续', title: '边缘自然', note: '重点观察接缝自然度' },
      { badge: '铺陈', title: '大面积预览', note: '适合面料与家纺铺陈' },
      { badge: '交付', title: '印刷前预览', note: '适合继续放大和做 DPI' },
    ],
    followups: [
      { label: '继续做无损放大', path: '/toolbox/lossless-zoom', note: '把连续纹理提升到更高交付尺寸' },
      { label: '继续做 DPI 处理', path: '/toolbox/dpi', note: '让结果更接近印刷交付要求' },
      { label: '回到素材库', path: '/assets', note: '把连续纹理沉淀成后续复用资产' },
    ],
  },
  'marketing-variants': {
    quickRecipes: [
      '围绕当前产品输出多张电商营销图，突出主体、材质细节和转化氛围。',
      '生成适合详情页、封面和渠道投放的多版本套图，风格统一但镜头丰富。',
      '保持产品定义不变，扩展出不同背景、构图和卖点表达的营销图。',
    ],
    caseViews: [
      { badge: '封面', title: '主图点击', note: '适合渠道封面与首图' },
      { badge: '详情', title: '转化素材', note: '适合详情页和种草图' },
      { badge: '卖点', title: '场景变化', note: '适合做多镜头卖点表达' },
      { badge: '活动', title: '渠道投放', note: '适合继续转视频或横版' },
    ],
    followups: [
      { label: '继续做细节图', path: '/shoot/detail-shots', note: '补足详情页局部卖点' },
      { label: '继续做图生视频', path: '/shoot/image-to-video', note: '从套图延展到动态内容' },
      { label: '转到工具箱', path: '/toolbox/upscale', note: '对主图和套图做清晰度增强' },
    ],
  },
  'detail-shots': {
    quickRecipes: [
      '围绕当前产品补充领口、面料、工艺、配件等细节图，画面更适合详情页。',
      '生成更适合电商详情页展示的局部特写，突出材质和工艺证据。',
      '让细节图更聚焦卖点，背景干净，主体边缘清楚。',
    ],
    caseViews: [
      { badge: '材质', title: '面料证据', note: '突出真实纹理与质感' },
      { badge: '工艺', title: '做工细节', note: '突出缝线、压纹、结构' },
      { badge: '配件', title: '局部卖点', note: '适合详情页局部模块' },
      { badge: '组合', title: '详情补强', note: '适合并回套图与详情页' },
    ],
    followups: [
      { label: '继续做裂变套图', path: '/shoot/marketing-variants', note: '把细节素材并入完整电商套图' },
      { label: '继续做图生视频', path: '/shoot/image-to-video', note: '让细节素材延展为动态内容' },
      { label: '回到任务中心', path: '/tasks', note: '集中查看所有营销素材生成进度' },
    ],
  },
  upscale: {
    quickRecipes: [
      '提升画面清晰度与细节，保留主体真实质感，避免过度锐化。',
      '增强主体纹理和边缘质量，让结果更适合详情页和交付使用。',
      '在保留原有结构与颜色的前提下提高解析度和整体观感。',
    ],
    caseViews: [
      { badge: '增强前', title: '原始画面', note: '对比边缘和细节保留' },
      { badge: '增强后', title: '清晰结果', note: '适合主图与详情页使用' },
      { badge: '局部', title: '纹理观察', note: '重点看材质和边缘提升' },
      { badge: '交付', title: '终稿预览', note: '适合继续缩放和 DPI' },
    ],
    followups: [
      { label: '继续做高质量缩放', path: '/toolbox/resize', note: '进一步匹配具体版式尺寸' },
      { label: '继续做 DPI 处理', path: '/toolbox/dpi', note: '适配印刷与交付参数' },
      { label: '回到素材库', path: '/assets', note: '把增强结果沉淀为新素材' },
    ],
  },
  outpaint: {
    quickRecipes: [
      '保持主体不变，自然向四周补全画面，适配更多版式和构图需求。',
      '在不破坏原图风格的前提下向边缘延展，保证背景和空间关系自然。',
      '扩展画布区域，保留主体完整性与原有材质质感。',
    ],
    caseViews: [
      { badge: '原图', title: '主体区域', note: '保留原有主体定义不变' },
      { badge: '扩展', title: '边缘补全', note: '重点看空间与背景关系' },
      { badge: '版式', title: '新画幅', note: '适合更多渠道尺寸需求' },
      { badge: '营销', title: '后续裂变', note: '适合再进营销套图流程' },
    ],
    followups: [
      { label: '继续做 AI 超清', path: '/toolbox/upscale', note: '对扩图结果继续提高清晰度' },
      { label: '继续做高质量缩放', path: '/toolbox/resize', note: '适配不同渠道和版式尺寸' },
      { label: '转到商拍套图', path: '/shoot/marketing-variants', note: '把扩图后的主体继续做营销图' },
    ],
  },
};

export function getToolPresentation(toolKey: string, mode: ShellMode): ToolPresentation {
  return {
    ...defaultByMode[mode],
    ...toolOverrides[toolKey],
  };
}
