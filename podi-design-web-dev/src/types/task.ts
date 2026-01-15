export type TaskStatus = 'PENDING' | 'PROCESSING' | 'COMPLETE' | 'FAILED' | 'UNKNOWN' | 'pending' | 'processing' | 'completed' | 'failed' | 'canceled' | 'unknown';

/* 基础任务接口定义 */
export interface BaseTask {
  id: string;
  status: string | number | TaskStatus;
  [key: string]: any;
}

/* 任务接口定义 */
export interface Task {
  id: string;
  name: string;
  status: TaskStatus;
  progress: number;
  time: string;
  thumbnail?: string;
  imageUrl?: string;
  imgUrl?: string;
  images?: string[];
  description?: string;
  action?: string;
  taskStatus?: string;
  inputImage?: string;
  workflowParams?: Record<string, unknown>;
  originalStatus?: string | number; // 添加原始状态字段
  promptId?: string; // 添加promptId字段，用于生成唯一键
  [key: string]: unknown; // 允许访问其他未知属性
}

/* 前端任务接口定义 */
export interface FrontendTask {
  id: string;
  name?: string;
  status: TaskStatus;
  progress?: number;
  time?: string;
  thumbnail?: string;
  imageUrl?: string;
  imgUrl?: string;
  description?: string;
  action?: string;
  taskStatus?: string;
  inputImage?: string;
  taskId?: string;
  userId?: string;
  createdAt?: string;
  updatedAt?: string;
  errorMessage?: string;
  workflowParams?: Record<string, any>;
  params?: Record<string, any>;
  originalStatus?: any;
  [key: string]: unknown;
};

/* 任务统计信息接口定义 */
export interface TaskStatistics {
  userId?: string;
  taskTotal?: any;
  subTaskTotal?: any;
  subTaskToday?: any;
  taskToday?: any;
};

/* 任务管理器接口定义 */
export interface TaskManager {
  addTask: (task: Task) => void;
  removeTask: (taskId: string) => void;
  getTask: (taskId: string) => Task | undefined;
  getAllTasks: () => Task[];
  clearTasks: () => void;
}

/* 总任务详情接口定义 */
export interface TaskSummaryItem {
  id: number;
  taskId: string;
  subTaskId?: string;
  userId: string;
  status: string;
  action: string; // 添加 action 属性
  name?: string; // 由 hook 补充的显示名称 (mapActionToChinese(action) - shortId)
  createTime?: string;
  updateTime?: string;
  originalImages?: string[];
  subTaskCount?: number;
  successCount?: number;
  failedCount?: number;
  runningCount?: number;
  pendingCount?: number;
  subTaskImages?: string[];
  progress?: number;
  resultUrl?: string;
  workflowParams?: Record<string, any>;
  // 退款信息（可选）：当任务失败并触发退款时，后端可返回此字段
  refund?: {
    amount?: number; // 总退款积分
    temp?: number; // 临时积分退款
    recharge?: number; // 充值积分退款
    time?: string; // 退款时间
  };
}

/* 总任务详情响应接口定义 */
export interface TaskSummaryResponse {
  total: number;
  size: number;
  totalPages: number;
  hasPrevious: boolean;
  hasNext: boolean;
  page: number;
  items: TaskSummaryItem[];
  pendingCount?: number;
  runningCount?: number;
  pending_count?: number;
  running_count?: number;
}

/* 任务详情接口定义 */
export interface TaskDetailItem {
  id: string | number;
  subTaskId: string;
  status: string;
  taskStatus?: string;
  imageUrl?: string;
  generatedImages?: string[]; // All output images
  images?: string[]; // Optional images array from API responses
  inputImage?: string; // Input image
  prompt?: string;
  createTime?: string;
  action?: string;
}

/* 任务详情响应接口定义 */
export interface TaskDetailResponse {
  total: number;
  size: number;
  totalPages: number;
  page: number;
  items: TaskDetailItem[];
}
