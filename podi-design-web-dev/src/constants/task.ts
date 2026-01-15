// ========== 任务/任务详情页相关常量 ==========
import { CircleCheck, XCircle, Clock, Hourglass } from 'lucide-react';

/** 任务状态对应的 UI 配置 */
export const TASK_STATUS_UI_CONFIG: Record<string, { label: string; icon: any; color: string; bg?: string }> = {
  COMPLETED: { label: '已完成', icon: CircleCheck, color: 'text-green-500', bg: 'bg-green-500' },
  RUNNING: { label: '进行中', icon: Hourglass, color: 'text-yellow-500', bg: 'bg-yellow-500' },
  FAILED: { label: '失败', icon: XCircle, color: 'text-red-500', bg: 'bg-red-500' },
  CANCELLED: { label: '已取消', icon: XCircle, color: 'text-gray-500', bg: 'bg-gray-500' },
  PENDING: { label: '等待中', icon: Clock, color: 'text-blue-500', bg: 'bg-blue-500' },
  QUEUED: { label: '排队中', icon: Clock, color: 'text-blue-500', bg: 'bg-blue-500' },
  PROCESSING: { label: '处理中', icon: Hourglass, color: 'text-yellow-500', bg: 'bg-yellow-500' },
};

/** 任务中心预览区域最多显示的任务数量 */
export const TASK_CENTER_PREVIEW_TASK_COUNT = 5;

/** 任务中心可见的页面路径集合（用于判断当前路由是否显示任务中心） */
export const TASK_CENTER_VISIBLE_ROUTES: Record<string, true> = {
  '/aitl/hires': true,
  '/aitl/fission': true,
  '/aitl/pattern-extract': true,
  '/aitl/seamless': true,
  '/aitl/extend': true,
  '/aitl/edit': true,
  '/dashboard': true,
  '/my-gallery': true,
  '/task-detail': true,
};

/** 任务详情页默认每页显示的图片数量，默认与最大上传数量保持一致 */
export const TASK_DETAIL_PAGE_SIZE = 50;

/** 任务详情页中图片卡片的宽度（单位：px） */
export const TASK_IMAGE_CARD_WIDTH = 200;

/** 任务详情页中图片卡片的高度（单位：px） */
export const TASK_IMAGE_CARD_HEIGHT = 200;

/**
 * 中文标签到 action key 的映射（用于从中文选择项快速映射为内部 action）
 */
export const CHINESE_TO_ACTION: Record<string, string> = {
  '无损放大': 'hires',
  '局部替换': 'replace',
  '智能擦除': 'erase',
  '智能裁剪': 'crop',
  '智能抠图': 'matting',
  '印花提取': 'pattern-extract',
  '图生图': 'img2img',
  '文生图': 'txt2img',
  '连续图案': 'seamless',
  '两方连续': 'twoway',
  '智能扩图': 'extend',
  '图像融合': 'merge',
  'AI图片编辑器': 'edit',
  '图片裂变': 'fission',
  '风格转化': 'style-transfer',
  '图案模板': 'pattern-template',
  'AI工作流': 'ai-workflow',
};

/** Action id 到提交按钮标签的映射 */
export const ACTION_TO_SUBMIT_LABEL: Record<string, string> = {
  hires: '开始无损放大',
  fission: '裂变并重塑图像',
  'pattern-extract': '提取图像印花',
  seamless: '生成连续图案',
  extend: '智能扩图并优化',
  edit: '启动AI图片编辑',
};

export default {
  TASK_STATUS_UI_CONFIG,
  TASK_CENTER_PREVIEW_TASK_COUNT,
  TASK_CENTER_VISIBLE_ROUTES,
  TASK_DETAIL_PAGE_SIZE,
  TASK_IMAGE_CARD_WIDTH,
  TASK_IMAGE_CARD_HEIGHT,
  CHINESE_TO_ACTION,
};
