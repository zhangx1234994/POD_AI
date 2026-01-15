import { Sparkles, CircleCheck } from 'lucide-react';
import { AI_ACTIONS } from '@/constants/sidebar';
import { TaskStatus, BaseTask } from '@/types/task';
import { TASK_STATUS_UI_CONFIG } from '@/constants';
import { CHINESE_TO_ACTION } from '@/constants/task';
import type { ImageItem } from '@/types/upload';
import { generateImageFilename } from './imageUtils';
import { fileToBase64 } from './imageUtils';

/** 任务相关小工具：生成 taskId */
export function generateTaskId(): string {
  const chars = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ';
  let prefix = '';
  for (let i = 0; i < 3; i++) {
    prefix += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  const ts = Date.now().toString();
  return `${prefix}${ts}`;
}

/** 根据任务状态获取对应的 UI 配置 */
export const getStatusConfig = (status: string): { label?: string; color?: string; icon?: any; bg?: string } => {
  const key = normalizeStatusKey(status);
  if (status === undefined || status === null || status === '') return {
    label: '',
    icon: '',
    color: '',
    bg: '',
  };
  return TASK_STATUS_UI_CONFIG[key] || TASK_STATUS_UI_CONFIG.PENDING;
};

/** 标准化任务状态键 */
export const normalizeStatusKey = (status: string | number | undefined | null): string => {
  if (status === undefined || status === null || status === '') return '';
  const s = String(status).trim();
  const upper = s.toUpperCase();

  // Normalize common backend status variants to our canonical keys
  let key = upper;
  if (upper === 'PROCESSING' || upper === 'RUNNING') key = 'RUNNING';
  if (upper === 'COMPLETED' || upper === 'SUCCEEDED' || upper === 'SUCCESS') key = 'COMPLETED';
  if (upper === 'FAILED' || upper === 'FAILURE') key = 'FAILED';
  if (upper === 'CANCELED' || upper === 'CANCELLED') key = 'CANCELLED';
  if (upper === 'PENDING' || upper === 'QUEUED') key = 'PENDING';

  return key;
};

/** 将 action 映射为中文标签 */
export const mapActionToChinese = (action: string = ''): string => {
  const normalized = action?.replace(/\-\d+$/, '') || '';
  switch (normalized) {
    case 'hires':
      return '无损放大';
    case 'replace':
      return '局部替换';
    case 'erase':
      return '智能擦除';
    case 'crop':
      return '智能裁剪';
    case 'matting':
      return '智能抠图';
    case 'pattern-extract':
      return '印花提取';
    case 'img2img':
      return '图生图';
    case 'txt2img':
      return '文生图';
    case 'seamless':
      return '连续图案';
    case 'twoway':
      return '两方连续';
    case 'extend':
      return '智能扩图';
    case 'merge':
      return '图像融合';
    case 'edit':
      return 'AI图片编辑器';
    case 'fission':
      return '图片裂变';
    case 'style-transfer':
      return '风格转化';
    case 'pattern-template':
      return '图案模板';
    case 'ai-workflow':
      return 'AI工作流';
    default:
      return action || '未知任务';
  }
};

/** 将中文标签映射为 action */
export const mapChineseToAction = (chinese: string | undefined): string | undefined => {
  if (!chinese) return undefined;
  const key = chinese.trim();
  if (!key) return undefined;
  // 仅在输入包含中文字符时才尝试映射中文action（避免英文或 taskId 被当成中文去映射）
  const hasCJK = /[\u4e00-\u9fff]/.test(key);
  if (!hasCJK) return undefined;

  // 优先精确匹配
  if (CHINESE_TO_ACTION[key]) return CHINESE_TO_ACTION[key];
  // 尝试模糊匹配：如果映射中的中文标签包含输入（输入为子串），例如输入 '无' 匹配 '无损放大'
  const found = Object.keys(CHINESE_TO_ACTION).find((k) => k.includes(key));
  return found ? CHINESE_TO_ACTION[found] : undefined;
};

/**
 * 将各种形式的状态值（字符串/数字/null/undefined）标准化为统一的任务状态
 *
 * 支持：
 * - 数字：0,1,2,3,4 或 100,200,300,400 等约定值
 * - 字符串：大小写不敏感，支持常见别名（如 'success', 'in_progress', 'cancelled' 等）
 *
 * @param status - 原始状态值
 * @returns 标准化后的状态（'pending' | 'processing' | 'completed' | 'failed' | 'canceled'）
 */
export const mapStatus = (
  status: string | number | null | undefined
): 'pending' | 'processing' | 'completed' | 'failed' | 'canceled' => {
  // --- 1. 处理 nullish 或空字符串 ---
  if (status == null || (typeof status === 'string' && status.trim() === '')) {
    return 'pending';
  }

  // --- 2. 统一转换为小写字符串（用于文本匹配）---
  const normalizedStr = String(status).toLowerCase().trim();

  // --- 3. 数字状态映射（包括字符串形式的数字，如 "2"）---
  const numValue = Number(normalizedStr);
  if (!Number.isNaN(numValue)) {
    switch (numValue) {
      case 0:
      case 100:
        return 'pending';
      case 1:
      case 200:
        return 'processing';
      case 2:
      case 300:
        return 'completed';
      case 3:
      case 400:
        return 'failed';
      case 4:
        return 'canceled';
      default:
        // 非预期数字，继续尝试文本匹配或 fallback
        break;
    }
  }

  // --- 4. 精确的文本映射（避免模糊正则）---
  // 使用 Set 进行 O(1) 查找，语义清晰，避免正则误匹配
  const statusMap: Record<string, Set<string>> = {
    pending: new Set(['pending', 'pend', 'queued', 'queue', 'waiting', 'wait']),
    processing: new Set(['processing', 'process', 'running', 'in_progress', 'in progress']),
    completed: new Set(['completed', 'complete', 'success', 'succeeded', 'ok']),
    failed: new Set(['failed', 'fail', 'failure', 'error']),
    canceled: new Set(['canceled', 'cancelled', 'cancel', 'aborted']),
  };

  for (const [canonical, variants] of Object.entries(statusMap)) {
    if (variants.has(normalizedStr)) {
      return canonical as any; // TypeScript 类型安全由 keys 保证
    }
  }

  // --- 5. 未知状态统一降级为 'pending' ---
  return 'pending';
};

// `getThumbnailUrl` 已迁移到 `imageUtils`，请从 '@/utils/imageUtils' 导入。

/** 渲染 action 对应的图标 */
export const renderActionIcon = (action?: string, className = 'w-4 h-4') => {
  const iconClass = className;
  if (!action) return <Sparkles className={iconClass} />;

  const normalized = String(action).replace(/\-\d+$/, '').toLowerCase();

  const tool = (AI_ACTIONS || []).find((t) => {
    const id = String(t.id).toLowerCase();
    return id === normalized || normalized.includes(id) || id.includes(normalized);
  });

  if (tool && tool.icon) {
    const Icon = tool.icon as any;
    return <Icon className={iconClass} />;
  }

  if (normalized === 'completed') return <CircleCheck className={iconClass} />;

  return <Sparkles className={iconClass} />;
};

/** 根据任务状态返回对应的进度百分比 */
export const progressByStatus = (status: TaskStatus): number => {
  const key = normalizeStatusKey(status as any);
  if (key === 'COMPLETED') return 100;
  if (key === 'RUNNING' || key === 'PROCESSING') return 50;
  return 0;
};

/** 从 action 字符串中提取 tooltype */
export const extractTooltypeFromAction = (actionStr?: string): string | undefined => {
  if (!actionStr || typeof actionStr !== 'string') return undefined;

  // 移除数字后缀
  const actionWithoutSuffix = actionStr.replace(/\-\d+$/, '');

  // 尝试从action中提取tooltype
  const actionParts = actionWithoutSuffix.split('-');
  if (actionParts.length > 1) {
    const potentialTooltype = actionParts[actionParts.length - 1];

    // 简单验证提取的tooltype是否合理
    if (potentialTooltype && !/^\d+$/.test(potentialTooltype)) {
      return potentialTooltype;
    }
  }

  return undefined;
};

/** 构建任务列表查询参数 */
export const buildTaskListParams = (
  userId: string,
  page: number,
  size: number,
  actionStr?: string,
  startTime?: string,
  endTime?: string
): Record<string, unknown> => {
  // 明确说明：前端组件内部状态使用0-based页码，与后端API期望一致
  // 确保page参数直接传递给后端，不需要额外转换
  const params: any = { user_id: userId, page, size };

  if (actionStr) {
    params.action = actionStr;

    // 从action中提取tooltype
    const tooltype = extractTooltypeFromAction(actionStr);
    if (tooltype) {
      params.tooltype = tooltype;
    }
  }

  // 添加时间范围过滤参数
  if (startTime) {
    params.start_time = startTime;
  }

  if (endTime) {
    params.end_time = endTime;
  }

  return params;
};

/**
 * 获取任务ID
 */
export const getTaskId = (task: BaseTask): string => {
  return (task as any).taskId || (task as any).task_id;
};

/**
 * 获取任务状态的标准化字符串
 */
export const getTaskStatus = (task: BaseTask): string => {
  const status = task.originalStatus ?? task.status;
  return String(status).toLowerCase();
};

/**
 * 比较两个任务是否发生变化
 * 主要比较状态、图片URL、进度等关键字段
 */
export const isTaskChanged = (oldTask: BaseTask, newTask: BaseTask): boolean => {
  if (!oldTask || !newTask) return true;

  // 比较状态
  const oldStatus = getTaskStatus(oldTask);
  const newStatus = getTaskStatus(newTask);
  if (oldStatus !== newStatus) return true;

  // 比较图片URL (通常是任务完成后的结果)
  const oldImg = oldTask.imgUrl || oldTask.imageUrl || oldTask.thumbnail;
  const newImg = newTask.imgUrl || newTask.imageUrl || newTask.thumbnail;
  if (oldImg !== newImg) return true;

  // 比较进度 (如果存在)
  if (oldTask.progress !== newTask.progress) return true;

  // 比较错误信息 (如果存在)
  if (oldTask.error !== newTask.error) return true;

  return false;
};

/**
 * 比较新旧任务列表，判断是否有变化
 * @param currentTasks 当前任务列表
 * @param newTasks 新获取的任务列表
 * @returns 是否有变化
 */
export const hasTaskListChanged = (currentTasks: BaseTask[], newTasks: BaseTask[]): boolean => {
  if (!currentTasks || !newTasks) return true;
  if (currentTasks.length !== newTasks.length) return true;

  // 创建ID映射以便快速查找
  const currentTaskMap = new Map(currentTasks.map((t) => [getTaskId(t), t]));

  for (const newTask of newTasks) {
    const id = getTaskId(newTask);
    const currentTask = currentTaskMap.get(id);

    if (!currentTask) return true; // 新任务中有旧列表中没有的任务
    if (isTaskChanged(currentTask, newTask)) return true;
  }

  return false;
};

/**
 * 无感更新任务列表
 * 只有在检测到变化时才返回新的列表，否则返回 null
 */
export const updateTaskListSeamlessly = <T extends BaseTask>(
  currentTasks: T[],
  newTasks: T[]
): { hasChanges: boolean; updatedList: T[] } => {
  // 如果长度不同，直接视为变化
  if (currentTasks.length !== newTasks.length) {
    return { hasChanges: true, updatedList: newTasks };
  }

  // 检查内容是否变化
  if (hasTaskListChanged(currentTasks, newTasks)) {
    return { hasChanges: true, updatedList: newTasks };
  }

  return { hasChanges: false, updatedList: currentTasks };
};

export type PreparedImageItem = { filename: string; base64?: string; ossUrl?: string; source?: string; o_size?: { width: number; height: number } };

/** 准备图片列表用于任务提交 */
export async function prepareImageList(
  imgs: ImageItem[],
  options?: { filenamePrefix?: string }
): Promise<PreparedImageItem[]> {
  const imageList: PreparedImageItem[] = [];
  if (!imgs || imgs.length === 0) return imageList;

  const baseTimestamp = Date.now();
  const prefix = options?.filenamePrefix || 'img';

  for (let i = 0; i < imgs.length; i++) {
    const img = imgs[i] as any;
    const filename = generateImageFilename(img.name || `${prefix}_${baseTimestamp}_${i}.png`, i > 0 ? i : undefined, true);
    
    // 获取图片原始尺寸
    const o_size = { width: img.width || 1024, height: img.height || 1024 };

    if (img.ossUrl) {
      imageList.push({ filename, ossUrl: img.ossUrl, source: img.source, o_size });
      continue;
    }

    if (img.file) {
      const base64 = await fileToBase64(img.file);
      imageList.push({ filename, base64, source: img.source, o_size });
      continue;
    }

    if (img.preview) {
      const prev = img.preview;
      if (typeof prev === 'string' && prev.startsWith('data:')) {
        const base64 = prev.includes(',') ? prev.split(',')[1] : prev;
        imageList.push({ filename, base64, source: img.source, o_size });
      } else {
        imageList.push({ filename, ossUrl: prev, source: img.source, o_size });
      }
    }
  }

  return imageList;
}

export default {
  generateTaskId,
  getStatusConfig,
  normalizeStatusKey,
  mapActionToChinese,
  mapChineseToAction,
  mapStatus,
  renderActionIcon,
  progressByStatus,
  extractTooltypeFromAction,
  buildTaskListParams,
  getTaskId,
  getTaskStatus,
  isTaskChanged,
  hasTaskListChanged,
  updateTaskListSeamlessly,
  prepareImageList,
};
