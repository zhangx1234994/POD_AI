import axios from 'axios';
import { getToken } from '@/utils/http';
import { TaskSummaryResponse, TaskDetailResponse } from '../types/task';

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

export const workflowApi = {
  /**
   * Get task summary list
   * @param userId User ID
   * @param page Page number (0-based)
   * @param size Page size
   * @param action Action type (optional)
   * @param timeFilter Time filter (optional)
   * @param startTime Start time (optional, ISO string or timestamp)
   * @param endTime End time (optional, ISO string or timestamp)
   */
  getTaskSummary: async (
    userId: string,
    page: number = 0,
    size: number = 10,
    action?: string,
    timeFilter?: string,
    startTime?: string,
    endTime?: string,
    status?: string,
    search?: string,
    sourceTimestamp?: string | number
  ) => {
    const params: any = {
      userId,
      page,
      size,
    };

    if (action) {
      params.action = action;
    }

    if (status) {
      params.status = status;
    }

    if (search) {
      params.search = search;
    }

    if (sourceTimestamp !== undefined && sourceTimestamp !== null) {
      params.pollTs = sourceTimestamp;
    }

    const response = await taskHttp.get('/v1', { params });
    const payload = response.data || {};
    const items = Array.isArray(payload.items) ? payload.items : [];
    const normalizedItems = items.map((item: any, index: number) => {
      const statusRaw = (item.status || 'pending').toString();
      const normalizedStatus = statusRaw.toUpperCase();
      return {
      id: item.taskId || item.id || index,
      taskId: item.taskId || item.id,
      userId,
      status: normalizedStatus,
      action: item.action,
      name: item.name,
      createTime: item.createdAt,
      updateTime: item.updatedAt,
      subTaskCount: 1,
      successCount: item.status === 'completed' ? 1 : 0,
      failedCount: item.status === 'failed' ? 1 : 0,
      runningCount: item.status === 'processing' ? 1 : 0,
      pendingCount: item.status === 'pending' ? 1 : 0,
      progress: item.progress,
      workflowParams: item.workflowParams,
      resultUrl: item.resultUrl,
    };
    });
    const total = payload.total ?? normalizedItems.length;
    const currentPage = payload.page ?? page;
    const currentSize = payload.size ?? size;
    const totalPages =
      currentSize > 0 ? Math.ceil(total / currentSize) : 0;

    return {
      data: {
        items: normalizedItems,
        total,
        size: currentSize,
        totalPages,
        hasPrevious: currentPage > 0,
        hasNext: (currentPage + 1) * currentSize < total,
        page: currentPage,
      },
    } as { data: TaskSummaryResponse };
  },

  /**
   * Get task detail by task ID
   * @param taskId Task ID
   * @param userId User ID
   * @param page Page number for subtasks
   * @param size Page size for subtasks
   */
  getTaskDetail: async (taskId: string, userId: string, page: number = 0, size: number = 10) => {
    console.warn('getTaskDetail is not implemented for the new task service');
    return {
      total: 0,
      size,
      totalPages: 0,
      page,
      items: [],
    } as TaskDetailResponse;
  },
};
