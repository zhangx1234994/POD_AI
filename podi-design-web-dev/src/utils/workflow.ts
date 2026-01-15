import axios from 'axios';
import { http, getUserId, getToken } from '@/utils/http';
import { Task, FrontendTask, TaskStatus } from '@/types/task';
import { formatRelativeTime } from '@/utils/timeUtils';
import { mapActionToChinese } from '@/utils/taskUtils';

const taskHttp = axios.create({
  baseURL: '/api/tasks',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

taskHttp.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

/**
 * 提交图像处理任务（明确为 image processing）
 * 参数: action: 后端 Action 字符串, payload: 请求体参数
*/
export async function submitImageProcessingTask(
  action: string,
  payload: Record<string, any>
): Promise<any> {
  try {
    const {
      taskId,
      userId,
      channel,
      pointsCost,
      points,
      toolType,
      action: actionInPayload,
      ...workflowParams
    } = payload;

    const resolvedTaskId = taskId;
    const resolvedUser = userId || getUserId();
    const resolvedChannel = channel || 'web-ui';
    const numericPoints =
      Number(pointsCost ?? points ?? workflowParams?.imageList?.length ?? 1) || 1;

    const body = {
      taskId: resolvedTaskId,
      userId: resolvedUser,
      channel: resolvedChannel,
      action: action || actionInPayload || toolType,
      workflowParams: {
        ...workflowParams,
        action: action || actionInPayload || toolType,
      },
      points: Math.max(1, Math.round(numericPoints)),
    };
    const response = await taskHttp.post('/v1/submit', body);
    return response?.data;
  } catch (error) {
    console.error('提交图像处理任务失败:', error);
    throw error;
  }
};

/**
 * 公共的重绘方法，封装action、userId、原taskId、新生成taskId参数
 * 提交图像重绘/再生成任务（使用名词形式以保持命名一致） 
 * 注意: 与 submitImageProcessingTask 保持前缀一致
 */
export async function submitImageRegenerationTask(
  action: string,
  userId: string,
  originalTaskId: string,
  newTaskId: string,
  workflowParams?: Record<string, any>
): Promise<{ success: boolean; message?: string }> {
  try {
    // 构建重绘请求参数
    const payload = {
      userId,
      originalTaskId,
      taskId: newTaskId,
      action,
      workflowParams,
    };

    // 调用重绘接口
    await http.post(`/image-regenerate`, payload);

    return { success: true };
  } catch (error) {
    console.error('提交重绘任务失败:', error);
    return { success: false, message: '重绘失败，请稍后重试' };
  }
};

/** 获取当前用户的图像任务列表（明确为用户图像任务） */
export async function fetchUserImageTasks(
  action?: string,
  page: number = 0,
  size: number = 5
): Promise<{ tasks: FrontendTask[]; total: number; page: number; size: number }> {
  try {
    const userId = getUserId();
    const params: any = { userId, page, size };
    if (action) params.action = action;

    const response = await taskHttp.get('/v1', { params });
    const payload = response.data || {};
    const data = Array.isArray(payload.items) ? payload.items : [];

    const tasks = data.map((t: any) => {
      const status = (t.status as TaskStatus) || 'pending';
      return {
        id: t.taskId,
        taskId: t.taskId,
        userId,
        action: t.action,
        status,
        imageUrl: t.resultUrl,
        createdAt: t.createdAt,
        updatedAt: t.updatedAt,
        errorMessage: t.errorMessage,
        workflowParams: t.workflowParams,
      } as FrontendTask;
    });

    return {
      tasks,
      total: payload.total ?? tasks.length,
      page: payload.page ?? page,
      size: payload.size ?? size,
    };
  } catch (error) {
    console.error('获取任务列表失败:', error);
    throw error;
  }
};

/**
 * 获取任务统计数据（兼容不同后端字段命名）
 * 获取当前用户的任务统计（更正式的名称）
 */
export async function fetchUserTaskStatistics(userId?: string): Promise<any> {
  try {
    const uid = userId || getUserId();
    const params: any = { user_id: uid };
    const response = await http.get('/workflow-task/statistics', { params });
    const payload = response.data || {};
    if (payload && typeof payload === 'object' && payload.data) {
      return payload.data;
    }
    return payload;
  } catch (error) {
    console.error('获取任务统计数据失败:', error);
    throw error;
  }
};

/**
 * 初始化AI设计工作流
 * 初始化工作流模板
 */
export async function initializeWorkflowTemplate(action: string = 'ai-design'): Promise<any> {
  try {
    const response = await http.post(`/workflow-template/init?Action=${action}`);
    return response.data;
  } catch (error) {
    console.error('初始化工作流模板失败:', error);
    throw error;
  }
};

/**
 * 从响应数据创建任务对象
 * 将后端返回的原始任务数据标准化为前端统一的 Task 模型
 * 支持多种字段命名风格（如 snake_case / camelCase / custom），并处理状态码转换。
 * @param rawTask - 后端返回的原始任务对象（可能来自不同接口）
 * @returns 标准化的 Task 对象
 */
export function mapRawTaskToTaskModel(rawTask: Record<string, any>): Task {
  // --- 1. 状态处理 ---
  const numericStatusMap: Record<number, TaskStatus> = {
    0: 'pending',
    1: 'processing',
    2: 'completed',
    3: 'failed',
    4: 'canceled',
  };

  let statusInput = rawTask.taskStatus ?? rawTask.status;
  let status: TaskStatus = 'unknown';

  if (typeof statusInput === 'number' && numericStatusMap[statusInput] !== undefined) {
    status = numericStatusMap[statusInput];
  } else if (typeof statusInput === 'string') {
    // 安全地断言为 TaskStatus，防止非法字符串
    const knownStatuses: TaskStatus[] = ['pending', 'processing', 'completed', 'failed', 'canceled'];
    status = knownStatuses.includes(statusInput as TaskStatus) ? (statusInput as TaskStatus) : 'unknown';
  }

  // --- 2. Action 与名称 ---
  const action = rawTask.workflowParams?.action ?? rawTask.action;
  const name = action ? mapActionToChinese(action) : '未知任务';

  // --- 3. 图像 URL 兼容多个字段 ---
  const imageUrl =
    rawTask.imageUrl ??
    rawTask.imgUrl ??
    rawTask.output_url ??
    rawTask.result_url ??
    rawTask.thumbnail_url ??
    '';

  // --- 4. 时间处理 ---
  const createdAt =
    rawTask.createdAt ??
    rawTask.created_at ??
    new Date().toISOString();

  // --- 5. 构造并返回标准化任务对象 ---
  return {
    id: rawTask.taskId ?? rawTask.task_id ?? rawTask.id ?? Math.random().toString(36).slice(2),
    name,
    status,
    progress: status === 'completed' ? 100 : status === 'processing' ? 50 : 0,
    time: formatRelativeTime(createdAt),
    action: action ?? '',
    imageUrl,
    workflowParams: rawTask.workflowParams ?? {},
    promptId: rawTask.promptId ?? rawTask.taskId ?? undefined,
    params: rawTask.params ?? rawTask.workflowParams ?? {},
    originalStatus: rawTask.taskStatus ?? rawTask.status,
  };
};

export default {
  submitImageProcessingTask,
  submitImageRegenerationTask,
  fetchUserImageTasks,
  fetchUserTaskStatistics,
  initializeWorkflowTemplate,
  mapRawTaskToTaskModel,
};
