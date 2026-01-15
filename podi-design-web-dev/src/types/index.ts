// 任务视图类型定义
export interface TaskView {
  id: string | number;
  type: string;
  status: TaskStatus;
  imgUrl?: string;
  imageUrl?: string;
  output_url?: string;
  result_url?: string;
  createTime?: string;
  updateTime?: string;
  [key: string]: any;
}

// 处理任务类型
export interface ProcessingJob {
  id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  progress: number;
  input: string;
  output?: string;
}

// 批处理项类型
export interface BatchItem {
  id: string;
  file: File;
  name: string;
  status: 'queued' | 'processing' | 'completed' | 'failed';
  progress: number;
  result?: string;
  error?: string;
}

// 任务状态类型
export type TaskStatus = 'pending' | 'processing' | 'completed' | 'failed' | 'unknown';

// 全局设置类型
export interface GlobalSettings {
  selectedTool: string;
  imageSize: string;
  enhancePrompt: boolean;
  prompt: string;
  negativePrompt: string;
  [key: string]: any;
}
