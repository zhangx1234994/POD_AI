import type { AiActionMetaParameter, AiActionMetadata } from '@/types/metadata';

/**
 * AI action 元数据配置
 * 每个 action（如 hires、fission）定义其参数列表、显示名称、可见性、格式化器等
 */
export const AI_ACTION_METADATA: Record<string, AiActionMetadata> = {
  "hires": {
    name: "无损放大",
    parameters: [
      {
        label: "放大倍数",
        key: "scale",
        type: "string",
        valueMap: { "2": "2倍", "3": "3倍", "4": "4倍" },
        priority: 1
      },
      {
        label: "模型",
        key: "model",
        type: "string",
        priority: 2,
        visible: false
      },
      {
        label: "提示词",
        key: "prompt",
        type: "string",
        priority: 3,
        visible: false
      },
      {
        label: "生图大小",
        key: "size",
        type: "string",
        priority: 4,
        visible: false
      },
      {
        label: "目标宽度",
        key: "width",
        type: "number",
        priority: 5,
        visible: false
      },
      {
        label: "目标高度",
        key: "height",
        type: "number",
        priority: 6,
        visible: false
      },
      {
        label: "原始图片尺寸",
        key: "o_size",
        type: "object",
        visible: false
      }
    ]
  },
  "fission": {
    name: "图片裂变",
    parameters: [
      {
        label: "参考原图强度",
        key: "reference_strength",
        type: "number",
        priority: 1
      },
      {
        label: "创意生成强度",
        key: "creative_strength",
        type: "number",
        priority: 2,
        visible: false
      },
      {
        label: "生成图片数量",
        key: "count",
        type: "number",
        priority: 3,
        visible: true
      },
      {
        label: "生图大小",
        key: "size",
        type: "string",
        priority: 4,
        visible: false
      },
      {
        label: "模型",
        key: "model",
        type: "string",
        priority: 5,
        visible: false
      },
      {
        label: "提示词",
        key: "prompt",
        type: "string",
        priority: 6,
        visible: false
      },
      {
        label: "原始图片尺寸",
        key: "o_size",
        type: "object",
        visible: false
      }
    ]
  },
  "pattern-extract": {
    name: "印花提取",
    parameters: [
      {
        label: "选择品类",
        key: "category",
        type: "string",
        valueMap: { "general": "通用", "cup": "杯子" },
        priority: 1,
        visible: true
      },
      {
        label: "模型",
        key: "model",
        type: "string",
        priority: 2,
        visible: false
      },
      {
        label: "提示词",
        key: "prompt",
        type: "string",
        priority: 3,
        visible: false
      },
      {
        label: "目标图片大小",
        key: "size",
        type: "string",
        priority: 5,
        visible: true,
        formatter: "formatImageSize"
      },
      {
        label: "生图大小",
        key: "resolution",
        type: "string",
        valueMap: { "original": "原图大小", "auto": "自定义", "1:1": "1:1正方形", "1:2": "1:2竖版", "2:1": "2:1横版" },
        priority: 4,
        visible: true
      },
      {
        label: "目标宽度",
        key: "width",
        type: "number",
        priority: 6,
        visible: false
      },
      {
        label: "目标高度",
        key: "height",
        type: "number",
        priority: 7,
        visible: false
      },
      {
        label: "原始图片尺寸",
        key: "o_size",
        type: "object",
        visible: false
      }
    ]
  },
  "seamless": {
    name: "连续图案",
    parameters: [
      {
        label: "图案类型",
        key: "patternType",
        type: "string",
        valueMap: { "seamless": "四方连续", "twoway": "两方连续" },
        priority: 1,
        visible: true
      },
      {
        label: "模型",
        key: "model",
        type: "string",
        priority: 2,
        visible: false
      },
      {
        label: "提示词",
        key: "prompt",
        type: "string",
        priority: 3,
        visible: false
      },
      {
        label: "目标图片大小",
        key: "size",
        type: "string",
        priority: 5,
        visible: true,
        formatter: "formatImageSize"
      },
      {
        label: "生图大小",
        key: "resolution",
        type: "string",
        valueMap: { "original": "原图大小", "auto": "自定义", "1:1": "1:1正方形", "1:2": "1:2竖版", "2:1": "2:1横版" },
        priority: 4,
        visible: true
      },
      {
        label: "目标宽度",
        key: "width",
        type: "number",
        priority: 6,
        visible: false
      },
      {
        label: "目标高度",
        key: "height",
        type: "number",
        priority: 7,
        visible: false
      },
      {
        label: "原始图片尺寸",
        key: "o_size",
        type: "object",
        visible: false
      }
    ]
  },
  "extend": {
    name: "智能扩图",
    parameters: [
      {
        label: "扩展风格",
        key: "prompt",
        type: "string",
        valueMap: { "general": "通用", "pattern": "花纹" },
        priority: 1,
        visible: true
      },
      {
        label: "模型",
        key: "model",
        type: "string",
        priority: 2,
        visible: false
      },
      {
        label: "生图大小",
        key: "size",
        type: "string",
        priority: 3,
        visible: false
      },
      {
        label: "扩展设置",
        key: "extend_type",
        type: "string",
        valueMap: { "scale": "按比例扩图", "customize": "自定义扩图" },
        priority: 3,
        visible: true
      },
      {
        labelGenerator: "extendLeft",
        key: "left",
        type: "number",
        formatter: "formatExtendValue",
        priority: 4,
        visible: true
      },
      {
        labelGenerator: "extendTop",
        key: "top",
        type: "number",
        formatter: "formatExtendValue",
        priority: 5,
        visible: true
      },
      {
        labelGenerator: "extendRight",
        key: "right",
        type: "number",
        formatter: "formatExtendValue",
        priority: 6,
        visible: true
      },
      {
        labelGenerator: "extendBottom",
        key: "bottom",
        type: "number",
        formatter: "formatExtendValue",
        priority: 7,
        visible: true
      },
      {
        label: "原始图片尺寸",
        key: "o_size",
        type: "object",
        visible: false
      }
    ]
  },
  "edit": {
    name: "AI图片编辑器",
    parameters: [
      {
        label: "效果描述",
        key: "prompt",
        type: "string",
        priority: 1,
        visible: true
      },
      {
        label: "模型",
        key: "model",
        type: "string",
        priority: 3,
        visible: false
      },
      {
        label: "生图大小",
        key: "size",
        type: "string",
        priority: 4,
        visible: false
      },
      {
        label: "输出宽度",
        key: "width",
        type: "number",
        priority: 5,
        visible: false
      },
      {
        label: "输出高度",
        key: "height",
        type: "number",
        priority: 6,
        visible: false
      },
      {
        label: "输出分辨率",
        key: "output_resolution",
        type: "string",
        valueMap: { "original": "原图自适应", "auto": "自动计算", "1:1": "1:1比例", "16:9": "16:9比例", "4:3": "4:3比例", "3:2": "3:2比例", "2:3": "2:3比例" },
        priority: 7,
        visible: true
      },
      {
        label: "原始图片尺寸",
        key: "o_size",
        type: "object",
        visible: false
      },
      {
        label: "标注区域信息",
        key: "maskElements",
        type: "array",
        visible: false
      },
      {
        label: "参考图",
        key: "aux_imageList",
        type: "array",
        priority: 100,
        visible: true
      }
    ]
  }
};

/**
 * 默认的 AI action 参数配置（用于兜底）
 * 当具体 action 未定义某些通用参数时，可合并此默认配置
 */
export const DEFAULT_AI_ACTION_PARAMETERS: AiActionMetaParameter[] = [
  {
    label: "反向提示词",
    key: "negative_prompt",
    type: "string",
    priority: 11
  },
  {
    label: "Steps",
    key: "steps",
    type: "number",
    priority: 12
  },
  {
    label: "Sampler",
    key: "sampler",
    type: "string",
    priority: 13
  },
  {
    label: "Seed",
    key: "seed",
    type: "number",
    priority: 14
  },
  {
    label: "Guidance",
    key: "cfg_scale",
    type: "number",
    priority: 15
  },
  {
    label: "引擎",
    key: "engine",
    type: "string",
    priority: 16
  },
  {
    label: "模型名称",
    key: "model_name",
    type: "string",
    priority: 17
  }
];

export default {
  AI_ACTION_METADATA,
  DEFAULT_AI_ACTION_PARAMETERS,
};
