// ========== AI 图像处理功能选项配置 ==========
// 此文件聚合 AI 图像处理工具页面中所有用户可选的静态配置选项。
// 用于表单、下拉菜单、单选组等 UI 控件。
// 将这些静态配置放到 constants 目录，便于复用、统一维护。
import generalPreview from '@/assets/images/extension_style_general.png';
import patternPreview from '@/assets/images/extension_style_pattern.png';
import fissionReferencePreview from '@/assets/images/fission_reference.png';
import type {
  PatternModeOption,
  ImageGenerationSizeOption,
  UpscaleFactorOption,
  ExtensionStyleOption,
  ExtensionRatioOption,
  ExtensionSettings,
  FissionGenerationCountOption,
  PatternExtractCategoryOption,
} from '@/types/options';

/** 图案类型选项（四方连续/两方连续） */
export const PATTERN_MODE_OPTIONS: PatternModeOption[] = [
  {
    key: 'seamless',
    title: '四方连续',
    desc: '可在水平和垂直方向无缝平铺，适合全覆盖图案设计',
    info:
      '四方连续功能会自动分析你的图片，生成可以在水平和垂直方向无缝平铺的图案。系统会智能处理边缘，确保图案在指定方向能够完美衔接。',
  },
  {
    key: 'twoway',
    title: '两方连续',
    desc: '可在水平或垂直方向无缝平铺，适合条纹和边框设计',
    info:
      '两方连续功能会自动分析你的图片，生成可以在水平或垂直方向无缝平贴的图案。系统会智能处理边缘，确保图案在指定方向能够完美衔接。',
  },
];

/** 生图大小选项 */
export const IMAGE_GENERATION_SIZE_OPTIONS: ImageGenerationSizeOption[] = [
  { key: '1:1', label: '1:1正方形', desc: '2000 × 2000 px' },
  { key: '1:2', label: '1:2竖版', desc: '900 × 1800 px' },
  { key: 'original', label: '原图大小', desc: '保持原始图片尺寸' },
  { key: '2:1', label: '2:1横版', desc: '1800 × 900 px' },
  { key: 'auto', label: '自定义', desc: '批量生成的所有图片将统一使用该尺寸，请合理设置宽高' },
];


/** 放大倍数选项 */
export const UPSCALE_FACTOR_OPTIONS: UpscaleFactorOption[] = [
  { key: '2', label: '2倍', desc: '适用于大多数场景' },
  { key: '4', label: '4倍', desc: '即将上线', disabled: true },
  { key: '8', label: '8倍', desc: '即将上线', disabled: true },
  { key: '16', label: '16倍', desc: '即将上线', disabled: true },
];

/** 智能扩图扩展风格选项 */
export const EXTENSION_STYLE_OPTIONS: ExtensionStyleOption[] = [
  {
    key: 'general',
    title: '通用',
    desc: '适用于自然图片和照片',
    info: '通用模式：适合自然图片和照片，能够智能扩展背景，保持图片的自然风格。',
    preview: generalPreview,
    previewDesc: '通用模式能够自然地扩展图片背景，适用于风景照和人物照等多种场景。',
  },
  {
    key: 'pattern',
    title: '花纹',
    desc: '适用于图案和纹理素材',
    info: '花纹模式：适合图案和纹理素材，能够智能延续图案，保持纹理的连续性。',
    preview: patternPreview,
    previewDesc: '花纹模式能够更好地延续图案的重复性，使扩展部分与原图无缝衔接。',
  },
];

/** 智能扩图扩展比例选项 */
export const EXTENSION_RATIO_OPTIONS: ExtensionRatioOption[] = [
  { key: '10', value: 10, label: '10%' },
  { key: '20', value: 20, label: '20%' },
  { key: '30', value: 30, label: '30%' },
  { key: '50', value: 50, label: '50%' },
  { key: 'custom', value: '', label: '请输入', hasInput: true },
];

/** 智能扩图功能的默认参数 */
export const EXTENSION_DEFAULTS: ExtensionSettings = {
  top: 0,
  bottom: 0,
  left: 0,
  right: 0,
  mode: 'ratio',
  ratioValue: 10,
  topPercent: 0,
  bottomPercent: 0,
  leftPercent: 0,
  rightPercent: 0,
  direction: 'all',
};

/** 图片裂变控制参数配置（注：这是配置项，非选项列表，保留原名） */
export const FISSION_CONTROL_SETTINGS = [
  {
    key: 'reference',
    label: '原图参考强度',
    lowLabel: '低相似',
    highLabel: '高相似',
    min: 0,
    max: 1,
    step: 0.01,
    preview: fissionReferencePreview,
    previewDesc: '原图参考强度决定生成图与原图的相似度，值越高越接近原图。',
  },
];

/** 图片裂变生成数量选项 */
export const FISSION_GENERATION_COUNT_OPTIONS: FissionGenerationCountOption[] = [
  { key: '1', value: 1, label: '一张' },
  { key: '2', value: 2, label: '两张' },
  { key: '3', value: 3, label: '三张' },
  { key: '4', value: 4, label: '四张' },
];

/** 印花提取类别选项 */
export const PATTERN_EXTRACT_CATEGORY_OPTIONS: PatternExtractCategoryOption[] = [
  { key: 'general', label: '通用', desc: '适用于所有场景的通用印花提取', badge: '推荐' },
  { key: 'cup', label: '杯子', desc: '专为马克杯、水杯等圆柱形产品优化' },
  { key: 'tshirt', label: 'T恤', desc: '专为服装印花优化，保留细节', badge: '敬请"宠"爱', disabled: true },
  { key: 'poster', label: '海报', desc: '专为平面印刷品优化', badge: '敬请"宠"爱', disabled: true },
];

/** 扩展默认导出，便于从默认聚合对象中读取 */
export default {
  PATTERN_MODE_OPTIONS,
  IMAGE_GENERATION_SIZE_OPTIONS,
  UPSCALE_FACTOR_OPTIONS,
  EXTENSION_STYLE_OPTIONS,
  EXTENSION_RATIO_OPTIONS,
  EXTENSION_DEFAULTS,
  FISSION_CONTROL_SETTINGS,
  FISSION_GENERATION_COUNT_OPTIONS,
  PATTERN_EXTRACT_CATEGORY_OPTIONS,
};
