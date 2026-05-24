export type ImageEditTool = 'point' | 'rect' | 'circle' | 'freehand';

export type ImageEditPoint = { x: number; y: number };

export type ImageEditMark = {
  id: string;
  name: string;
  type: ImageEditTool;
  points: ImageEditPoint[];
  created_at: number;
};

export type ImageEditSkill =
  | 'local_modify'
  | 'reference_element_transfer'
  | 'remove_inpaint'
  | 'color_reference_correction'
  | 'canvas_outpaint';

export type ImageEditOutpaintSettings = {
  expandLeft: number;
  expandRight: number;
  expandTop: number;
  expandBottom: number;
  anchor: string;
  preserveOriginal: boolean;
};

export const IMAGE_EDIT_SKILL_OPTIONS = [
  {
    value: 'local_modify',
    label: '局部修改',
    description: '改颜色、材质或局部细节；不需要参考图时优先使用。',
  },
  {
    value: 'reference_element_transfer',
    label: '参考图替换',
    description: '用参考图里的对象、材质或风格替换主图指定位置，必须上传参考图。',
  },
  {
    value: 'remove_inpaint',
    label: '删除修补',
    description: '删除水印、杂物或瑕疵并补齐背景，需要先标注位置或提供蒙版。',
  },
  {
    value: 'color_reference_correction',
    label: '补色校正',
    description: '只迁移参考图的颜色、明度、饱和度和冷暖关系，不复制结构。',
  },
  {
    value: 'canvas_outpaint',
    label: '扩展画布',
    description: '把原图放入更大的目标画布，只让模型补全外扩区域。',
  },
] as const;

export const DEFAULT_IMAGE_EDIT_OUTPAINT_SETTINGS: ImageEditOutpaintSettings = {
  expandLeft: 256,
  expandRight: 256,
  expandTop: 256,
  expandBottom: 256,
  anchor: 'center',
  preserveOriginal: true,
};

export const IMAGE_EDIT_OUTPAINT_ANCHOR_OPTIONS = [
  { label: '居中扩展', value: 'center' },
  { label: '向右扩展', value: 'left' },
  { label: '向左扩展', value: 'right' },
  { label: '向下扩展', value: 'top' },
  { label: '向上扩展', value: 'bottom' },
];

export const IMAGE_EDIT_REFERENCE_REQUIRED_SKILLS = new Set<string>([
  'reference_element_transfer',
  'color_reference_correction',
]);

export const IMAGE_EDIT_SIZE_OPTIONS = [
  { label: '自动，跟随原图', value: 'auto' },
  { label: '1K 方图 1024x1024', value: '1024x1024' },
  { label: '1K 横图 1536x1024', value: '1536x1024' },
  { label: '1K 竖图 1024x1536', value: '1024x1536' },
  { label: '2K 方图 2048x2048', value: '2048x2048' },
  { label: '2K 横图 2048x1152', value: '2048x1152' },
  { label: '4K 横图 3840x2160（高成本）', value: '3840x2160' },
  { label: '4K 竖图 2160x3840（高成本）', value: '2160x3840' },
];

export const IMAGE_EDIT_QUALITY_OPTIONS = [
  { label: '自动', value: 'auto' },
  { label: '快速预览', value: 'preview' },
  { label: '正式候选', value: 'production' },
  { label: '高质量', value: 'premium' },
];

export const normalizeImageEditQuality = (value: string): string => {
  const raw = String(value || '').trim();
  if (raw === 'low') return 'preview';
  if (raw === 'medium') return 'production';
  if (raw === 'high') return 'premium';
  if (IMAGE_EDIT_QUALITY_OPTIONS.some((item) => item.value === raw)) return raw;
  return 'auto';
};

export const IMAGE_EDIT_OUTPUT_FORMAT_OPTIONS = [
  { label: 'PNG', value: 'png' },
  { label: 'JPEG', value: 'jpeg' },
  { label: 'WEBP', value: 'webp' },
];

export const formatEditorToolLabel = (tool: ImageEditTool): string => {
  switch (tool) {
    case 'point':
      return '点选';
    case 'rect':
      return '矩形框选';
    case 'circle':
      return '圆形框选';
    case 'freehand':
      return '手绘';
    default:
      return '标注';
  }
};

export const formatEditorMarkMention = (_mark: ImageEditMark, index: number): string => `@标注${index + 1}`;

export const formatEditorReferenceMention = (index: number): string => `#参考图${index + 1}`;

export const summarizeEditorMarkGeometry = (mark: ImageEditMark): string => {
  const points = mark.points || [];
  const first = points[0];
  const second = points[1];
  const fmt = (value: number) => Math.round(Number(value || 0));
  if (mark.type === 'point' && first) return `@point(${fmt(first.x)},${fmt(first.y)})`;
  if (mark.type === 'rect' && first && second) {
    return `@rect(${fmt(first.x)},${fmt(first.y)} → ${fmt(second.x)},${fmt(second.y)})`;
  }
  if (mark.type === 'circle' && first && second) {
    return `@circle(${fmt(first.x)},${fmt(first.y)} → ${fmt(second.x)},${fmt(second.y)})`;
  }
  if (mark.type === 'freehand') return `@path(${points.length}点)`;
  return '@region';
};

export const selectEditorReferenceUrlsForSkill = (skill: string, prompt: string, refs: string[]): string[] => {
  if (IMAGE_EDIT_REFERENCE_REQUIRED_SKILLS.has(skill)) return refs;
  if (!prompt) return [];
  return refs.filter((_, index) => prompt.includes(formatEditorReferenceMention(index)));
};

export const getImageEditQuickPrompts = (skill: string): string[] => {
  switch (skill) {
    case 'reference_element_transfer':
      return [
        '用参考图的对象或材质替换圈出的区域，保持主图构图、光照和背景不变。',
        '只参考参考图的质感，不要直接拼贴参考图内容。',
      ];
    case 'remove_inpaint':
      return ['删除圈出的内容，并自然补齐背景。', '去掉圈出的水印或杂物，保持画面干净自然。'];
    case 'color_reference_correction':
      return [
        '参考参考图的颜色、明暗和冷暖关系，校正主图整体色调，不改变结构。',
        '只迁移配色感觉，不复制参考图里的图案、文字或元素。',
      ];
    case 'canvas_outpaint':
      return [
        '自然补全外扩区域，延续原图背景、纹理、光照和图案密度，原图主体保持不变。',
        '把画面向外延展成完整场景，不新增主体，不改变原图已有内容。',
      ];
    default:
      return ['把圈出的区域改成更适合的颜色或材质，其他区域保持不变。', '优化局部细节，保持整体风格一致。'];
  }
};

export const serializeEditorSelectionHints = (
  marks: ImageEditMark[],
  imageSize: { width: number; height: number },
): Array<Record<string, unknown>> => {
  const width = Math.round(Number(imageSize.width || 0));
  const height = Math.round(Number(imageSize.height || 0));
  return marks.map((mark, index) => ({
    type: mark.type,
    label: `标注${index + 1}`,
    mention: formatEditorMarkMention(mark, index),
    geometryText: summarizeEditorMarkGeometry(mark),
    points: (mark.points || []).map((point) => ({
      x: Math.round(Number(point.x || 0)),
      y: Math.round(Number(point.y || 0)),
    })),
    imageSize: width > 0 && height > 0 ? { width, height } : undefined,
  }));
};

export const buildImageEditTaskSummary = (args: {
  skillLabel: string;
  prompt: string;
  marks: ImageEditMark[];
  refs: string[];
  maskUrl: string;
  size: string;
  quality: string;
  mainUrl: string;
}): string => {
  const scope =
    args.maskUrl.trim()
      ? '使用蒙版限定修改区域'
      : args.marks.length > 0
        ? `使用 ${args.marks.length} 个圈选区域定位修改位置`
        : '未圈选位置，按整图/文字说明理解';
  const refs = args.refs.length > 0 ? `已加入 ${args.refs.length} 张参考图` : '未加入参考图';
  const marks =
    args.marks.length > 0
      ? args.marks.map((mark, index) => `${formatEditorMarkMention(mark, index)} ${summarizeEditorMarkGeometry(mark)}`).join('；')
      : '未标注';
  return [
    `改图方式：${args.skillLabel}`,
    `主图：${args.mainUrl.trim() ? '已提供' : '待提供'}`,
    `修改目标：${args.prompt.trim() || '待填写'}`,
    `修改范围：${scope}`,
    `标注清单：${marks}`,
    `参考图：${refs}`,
    `输出：尺寸 ${args.size || 'auto'}，质量 ${args.quality || 'auto'}`,
    '',
    '说明：提交后，中台会自动生成一张红色编号的标注定位图传给模型，帮助模型理解 @标注 对应位置；蒙版仍然是唯一硬限制。',
  ].join('\n');
};
