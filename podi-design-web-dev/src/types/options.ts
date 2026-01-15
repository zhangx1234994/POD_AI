// 类型定义：AI 图像处理页面使用的静态选项类型
// 将这些类型集中到 `src/types` 便于在代码中单独引用与维护。
export interface PatternModeOption {
  key: string;
  title: string;
  desc: string;
  info?: string;
}

export interface ImageGenerationSizeOption {
  key: string;
  label: string;
  desc: string;
}

export interface UpscaleFactorOption {
  key: string;
  label: string;
  desc: string;
  disabled?: boolean;
  badge?: string;
}

export interface ExtensionStyleOption {
  key: string;
  title: string;
  desc: string;
  info?: string;
  preview?: string;
  previewDesc?: string;
}

export interface ExtensionRatioOption {
  key: string;
  value?: number | string;
  label?: string;
  hasInput?: boolean;
}

export interface ExtensionSettings {
  top: number;
  bottom: number;
  left: number;
  right: number;
  mode: 'ratio' | 'custom' | 'directional';
  ratioValue: number;
  topPercent: number;
  bottomPercent: number;
  leftPercent: number;
  rightPercent: number;
  direction?: 'horizontal' | 'vertical' | 'all';
}

export interface FissionGenerationCountOption {
  key: string;
  value: number;
  label: string;
  desc?: string;
}

export interface PatternExtractCategoryOption {
  key: string;
  label: string;
  desc: string;
  badge?: string;
  disabled?: boolean;
}
