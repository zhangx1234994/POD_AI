export const evalBusinessCategoryOrder = [
  '花纹提取',
  '图裂变',
  '扩图',
  '连续图',
  '抠图',
  '图像融合',
  '图像增强',
  '图像理解',
  '文本与提示词',
  '生视频',
  '平台工具',
];

export const normalizeEvalBusinessCategory = (category: string | undefined | null): string => {
  const c = String(category || '').trim();
  if (!c) return '平台工具';
  if (evalBusinessCategoryOrder.includes(c)) return c;
  if (c === '花纹提取类' || c === 'pattern_extract' || c === 'pattern' || c === 'pattern-extract') return '花纹提取';
  if (c === '图延伸类' || c === 'image_extend' || c === 'image_extension' || c === '图扩展' || c === '图延伸') return '扩图';
  if (c === '四方/两方连续图类' || c === 'continuous' || c === 'continuous_pattern' || c === 'lianxu') return '连续图';
  if (c === 'image_fission' || c === 'fission' || c === 'variation' || c === 'image_variation' || c === 'liebain' || c === 'liebiam') {
    return '图裂变';
  }
  if (c === 'cutout' || c === 'background_remove' || c === 'matting') return '抠图';
  if (c === 'image_composition' || c === 'composition' || c === 'fusion') return '图像融合';
  if (c === 'image_enhancement' || c === 'enhancement' || c === 'upscale') return '图像增强';
  if (c === 'vision_analysis' || c === 'vision' || c === 'vl') return '图像理解';
  if (c === 'text_prompt' || c === 'text_generation' || c === 'prompt') return '文本与提示词';
  if (c === 'video_generation' || c === 'video') return '生视频';
  return '平台工具';
};
