/**
 * 全局常量
 */
import { Wand2, Images, Palette, Sparkles } from "lucide-react";
import type { AbilityDefinition, BatchGoalId, ProcessTaskType } from "../types";

export const abilities: AbilityDefinition[] = [
  {
    id: "clean",
    title: "图片标准化",
    desc: "去背景、统一尺寸、DPI 标记和轻量压缩",
    icon: Wand2,
    cost: "1-2 AI 积分/张",
    output: "处理图",
  },
  {
    id: "extend",
    title: "扩图",
    desc: "按目标比例补边扩图，保持主体不变",
    icon: Images,
    cost: "2 AI 积分/张",
    output: "处理图",
  },
  {
    id: "extract",
    title: "提取花纹",
    desc: "把喜欢的花纹从产品图里提取出来，变成可复用素材",
    icon: Palette,
    cost: "2-3 AI 积分/张",
    output: "花纹",
  },
  {
    id: "variation",
    title: "裂变生成",
    desc: "基于一张参考图生成相似风格图，快速扩展系列",
    icon: Sparkles,
    cost: "3-5 AI 积分/组",
    output: "裂变图",
  },
  {
    id: "seamless2",
    title: "两方连续",
    desc: "让左右边缘自然衔接，适合杯子、圆柱杯、包装侧边",
    icon: Images,
    cost: "2 AI 积分/张",
    output: "连续花纹",
  },
  {
    id: "seamless4",
    title: "四方连续",
    desc: "让上下左右都能无限平铺，适合窗帘、布料、壁纸和大面积印花",
    icon: Palette,
    cost: "2-3 AI 积分/张",
    output: "连续花纹",
  },
];

export const abilityOutputLabels: Record<BatchGoalId, string> = {
  clean: "处理图",
  extend: "处理图",
  extract: "花纹",
  variation: "裂变图",
  seamless2: "连续花纹",
  seamless4: "连续花纹",
};

export const processTaskTypeLabels: Record<ProcessTaskType, string> = {
  clean: "图片标准化",
  extend: "扩图",
  extract: "花纹提取",
  variation: "裂变生成",
  seamless2: "两方连续",
  seamless4: "四方连续",
  image_edit: "单图精修",
};

export const assetTypeLabels: Record<string, string> = {
  original: "原图",
  processed: "处理图",
  variation: "裂变图",
  pattern: "花纹",
  ai_generated: "AI 生成",
  product_preview: "产品预览",
};

export const visibilityLabels: Record<string, string> = {
  private: "私有",
  reviewing: "审核中",
  public: "已公开",
  removed: "已移除",
};

export const licenseModeLabels: Record<string, string> = {
  private: "仅自己可用",
  display_only: "仅展示",
  free_reuse: "免费复用",
  paid_points: "积分授权",
};

export const licenseSourceLabels: Record<string, string> = {
  created: "自己生成",
  uploaded: "自己上传",
  free_reuse: "免费获得",
  purchased: "已购授权",
  product_snapshot: "产品预览",
};
