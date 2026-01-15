// ========== 简单的任务管理器实现 ==========
import type { Task } from '@/types/task';

/* 使用Map存储任务，提供增删查改功能 */
const tasks = new Map<string, Task>();

export const taskManager = {
  add(task: Task) {
    if (!task.id) throw new Error('Task.id is required');
    tasks.set(task.id, task);
  },
  remove(taskId: string) {
    tasks.delete(taskId);
  },
  get(taskId: string) {
    return tasks.get(taskId);
  },
  getAll() {
    return Array.from(tasks.values());
  },
  clear() {
    tasks.clear();
  },
  // 测试用
  __reset() {
    tasks.clear();
  },
};
