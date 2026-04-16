import type { NavItem, RoleCase, ShortcutItem, StudioAgent, ToolItem } from '../types';
import { buildEditorialVisual } from './clientVisuals';

const img = (seed: string) => buildEditorialVisual(seed, 900);

export const designTools: ToolItem[] = [
  { key: 'text-to-style', title: '以文生款', subtitle: '文字出款', description: '输入设计意图，快速生成款式方向。', path: '/design/text-to-style', accent: 'sky', group: '新款设计' },
  { key: 'style-to-style', title: '以款生款', subtitle: '参考改款', description: '上传参考款，快速做同风格延展。', path: '/design/style-to-style', accent: 'amber', group: '新款设计' },
  { key: 'sketch-to-style', title: '线稿成款', subtitle: '线稿转款', description: '把线稿快速转成完整服装效果图。', path: '/design/sketch-to-style', accent: 'violet', group: '新款设计' },
  { key: 'style-to-sketch', title: '款生线稿', subtitle: '成衣转线稿', description: '把成衣效果图抽成可继续设计的线稿。', path: '/design/style-to-sketch', accent: 'cyan', group: '新款设计' },
  { key: 'fusion', title: '融合创款', subtitle: '多图融合', description: '两到三张图融合出新的创意方向。', path: '/design/fusion', accent: 'rose', group: '新款设计' },
  { key: 'local-redraw', title: '局部改款', subtitle: '局部重绘', description: '针对局部结构、花型、配色做调整。', path: '/design/local-redraw', accent: 'amber', group: '改款设计' },
  { key: 'garment-recolor', title: '服装配色', subtitle: '成衣换色', description: '快速替换服装主色与辅色方案。', path: '/design/garment-recolor', accent: 'rose', group: '改款设计' },
  { key: 'ai-pattern', title: 'AI图案', subtitle: '图案生成', description: '输入描述直接生成印花和花型素材。', path: '/design/ai-pattern', accent: 'sky', group: '图案设计' },
  { key: 'pattern-extract', title: '图案提取', subtitle: '花型提取', description: '把实拍花型提取为干净设计稿。', path: '/design/pattern-extract', accent: 'emerald', group: '图案设计' },
  { key: 'pattern-fusion', title: '图案融合', subtitle: '花型融合', description: '让不同印花快速形成新的组合图案。', path: '/design/pattern-fusion', accent: 'violet', group: '图案设计' },
  { key: 'pattern-recolor', title: '图案配色', subtitle: '花型试色', description: '围绕现有图案快速尝试配色方案。', path: '/design/pattern-recolor', accent: 'amber', group: '图案设计' },
  { key: 'pattern-craft', title: 'AI图案工艺', subtitle: '工艺表达', description: '把图案和工艺效果结合成更接近成品的表达。', path: '/design/pattern-craft', accent: 'rose', group: '图案设计' },
  { key: 'seamless', title: '四方连续', subtitle: '连续纹理', description: '一键生成无缝连续纹理，适合印花和面料。', path: '/design/seamless', accent: 'cyan', group: '图案设计' },
];

export const toolboxTools: ToolItem[] = [
  { key: 'upscale', title: 'AI超清', subtitle: '清晰增强', description: '快速提高画面清晰度与细节表现。', path: '/toolbox/upscale', accent: 'sky', group: '图像处理' },
  { key: 'remove', title: 'AI消除', subtitle: '杂物移除', description: '去除杂物、水印或局部干扰元素。', path: '/toolbox/remove', accent: 'rose', group: '图像处理' },
  { key: 'cutout', title: '智能抠图', subtitle: '主体分离', description: '把主体和背景快速分离，便于二次设计。', path: '/toolbox/cutout', accent: 'emerald', group: '图像处理' },
  { key: 'lossless-zoom', title: '无损放大', subtitle: '大图放大', description: '适合大图输出和印刷前处理。', path: '/toolbox/lossless-zoom', accent: 'emerald', group: '图像处理' },
  { key: 'vectorize', title: '转矢量图', subtitle: '矢量转换', description: '把位图尽量转换成可继续编辑的矢量表达。', path: '/toolbox/vectorize', accent: 'violet', group: '图像处理' },
  { key: 'recolor', title: '调色', subtitle: '颜色调整', description: '快速尝试不同色调与风格方案。', path: '/toolbox/recolor', accent: 'amber', group: '图像处理' },
  { key: 'outpaint', title: 'AI扩图', subtitle: '边缘补全', description: '对画布四边进行自然补全。', path: '/toolbox/outpaint', accent: 'amber', group: '图像处理' },
  { key: 'resize', title: '高质量缩放', subtitle: '尺寸缩放', description: '快速调整尺寸并保留关键纹理。', path: '/toolbox/resize', accent: 'rose', group: '图像处理' },
  { key: 'dpi', title: 'DPI处理', subtitle: '印刷参数', description: '适合印刷前的最终参数处理。', path: '/toolbox/dpi', accent: 'violet', group: '图像处理' },
];

export const shootTools: ToolItem[] = [
  { key: 'garment-tryon', title: '服装上身', subtitle: '真人试衣', description: '把平铺服装快速生成真人上身展示图。', path: '/shoot/garment-tryon', accent: 'sky', group: '模特拍摄' },
  { key: 'swap-background', title: '换模特背景', subtitle: '背景替换', description: '一键更换模特和背景，快速做营销图。', path: '/shoot/swap-background', accent: 'amber', group: '模特拍摄' },
  { key: 'change-pose', title: '换姿势', subtitle: '姿势替换', description: '保持主体风格，替换模特姿态和镜头角度。', path: '/shoot/change-pose', accent: 'violet', group: '模特拍摄' },
  { key: 'garment-retouch', title: '服装精修', subtitle: '商业精修', description: '针对服装图做进一步精修和商业增强。', path: '/shoot/garment-retouch', accent: 'rose', group: '模特拍摄' },
  { key: 'shoes-tryon', title: '鞋子上身', subtitle: '鞋类试穿', description: '把鞋类产品挂到真人穿搭场景中。', path: '/shoot/shoes-tryon', accent: 'emerald', group: '模特拍摄' },
  { key: 'bag-tryon', title: '包包上身', subtitle: '箱包试背', description: '快速生成包类产品的真人搭配图。', path: '/shoot/bag-tryon', accent: 'cyan', group: '模特拍摄' },
  { key: 'hat-tryon', title: '帽子上身', subtitle: '帽饰试戴', description: '快速生成帽类产品的佩戴展示图。', path: '/shoot/hat-tryon', accent: 'amber', group: '模特拍摄' },
  { key: 'marketing-variants', title: '裂变套图', subtitle: '营销套图', description: '一张主图生成多种营销版本。', path: '/shoot/marketing-variants', accent: 'sky', group: '模特拍摄' },
  { key: 'garment-flatlay', title: '服装转平铺', subtitle: '转平铺', description: '把真人或复杂展示图整理成平铺视角。', path: '/shoot/garment-flatlay', accent: 'rose', group: '静物拍摄' },
  { key: 'detail-shots', title: '服装细节图', subtitle: '细节补图', description: '生成领口、袖口、面料和工艺等细节表达。', path: '/shoot/detail-shots', accent: 'amber', group: '静物拍摄' },
  { key: 'pattern-tryon', title: '图案上身', subtitle: '图案展示', description: '把图案快速挂到服装或展示场景。', path: '/shoot/pattern-tryon', accent: 'violet', group: '静物拍摄' },
  { key: 'fabric-tryon', title: '面料上身', subtitle: '面料展示', description: '把面料纹理挂到成衣展示场景中。', path: '/shoot/fabric-tryon', accent: 'emerald', group: '静物拍摄' },
  { key: 'image-to-video', title: '图生视频', subtitle: '短视频生成', description: '静态图扩展为动感短视频。', path: '/shoot/image-to-video', accent: 'rose', group: '视频生成' },
  { key: 'curtain-preview', title: '窗帘试挂', subtitle: '空间试挂', description: '把窗帘、家纺效果快速挂到空间场景中。', path: '/shoot/curtain-preview', accent: 'cyan', group: '其他' },
];

export const shortcuts: ShortcutItem[] = [
  { key: 'text-to-style', title: '以文生款', subtitle: '一句话生成新款方向', path: '/design/text-to-style', accent: 'sky' },
  { key: 'pattern-extract', title: '图案提取', subtitle: '从实拍图提取干净印花', path: '/design/pattern-extract', accent: 'amber' },
  { key: 'seamless', title: '四方连续', subtitle: '直接做无缝连续纹理', path: '/design/seamless', accent: 'emerald' },
  { key: 'outpaint', title: 'AI扩图', subtitle: '向四边延展并补全图像', path: '/toolbox/outpaint', accent: 'rose' },
  { key: 'upscale', title: 'AI超清', subtitle: '快速提高清晰度与质感', path: '/toolbox/upscale', accent: 'violet' },
  { key: 'video', title: '图生视频', subtitle: '静态图延展成动态短视频', path: '/shoot/image-to-video', accent: 'cyan' },
];

export const studioAgents: StudioAgent[] = [
  {
    id: 'fashion',
    title: '时尚设计智能体',
    subtitle: '从灵感、关键词、参考图快速收敛成款式方向',
    accent: 'sky',
    path: '/design/text-to-style',
    image: img('photo-1515886657613-9f3515b0c78f'),
  },
  {
    id: 'pattern',
    title: '图案设计智能体',
    subtitle: '围绕印花、花型、连续纹理做高频设计动作',
    accent: 'emerald',
    path: '/design/pattern-extract',
    image: img('photo-1496747611176-843222e1e57c'),
  },
  {
    id: 'style',
    title: '款式设计智能体',
    subtitle: '把改款、融合、配色、线稿等动作串成工作流',
    accent: 'rose',
    path: '/design/fusion',
    image: img('photo-1529139574466-a303027c1d8b'),
  },
  {
    id: 'commerce',
    title: '电商营销智能体',
    subtitle: '围绕套图、视频、精修、细节图做商拍输出',
    accent: 'amber',
    path: '/shoot/marketing-variants',
    image: img('photo-1503342217505-b0a15ec3261c'),
  },
];

export const roleCases: RoleCase[] = [
  {
    id: 'vera',
    role: '服装设计师',
    name: 'Vera',
    headline: '把灵感图、参考款和草图快速收束成可讨论的成衣方向。',
    uplift: '500%',
    savings: '85%',
    accent: 'sky',
    image: img('photo-1529139574466-a303027c1d8b'),
  },
  {
    id: 'brand',
    role: '电商品牌',
    name: '风尚织造',
    headline: '围绕主图、套图和视频做高频营销内容裂变。',
    uplift: '600%',
    savings: '80%',
    accent: 'amber',
    image: img('photo-1503342217505-b0a15ec3261c'),
  },
  {
    id: 'stella',
    role: '外贸业务员',
    name: 'Stella',
    headline: '在更短时间里把客户意向、样图和成图串成提案闭环。',
    uplift: '200%',
    savings: '95%',
    accent: 'rose',
    image: img('photo-1483985988355-763728e1935b'),
  },
  {
    id: 'student',
    role: '学生 / 创作者',
    name: '林凡',
    headline: '从 0 到 1 快速搭起个人作品线和概念表达。',
    uplift: '0-1',
    savings: '79%',
    accent: 'emerald',
    image: img('photo-1496747611176-843222e1e57c'),
  },
];

export const navItems: NavItem[] = [
  { key: 'home', label: '首页', path: '/home' },
  { key: 'studio', label: '工作室', path: '/studio', badge: String(designTools.length) },
  { key: 'design', label: 'AI研发设计', path: '/design/text-to-style', badge: String(shootTools.length) },
  { key: 'shoot', label: 'AI视觉商拍', path: '/shoot/marketing-variants', badge: String(toolboxTools.length) },
  { key: 'toolbox', label: 'AI工具箱', path: '/toolbox/upscale' },
  { key: 'tasks', label: '任务中心', path: '/tasks' },
  { key: 'assets', label: '我的素材', path: '/assets' },
];
