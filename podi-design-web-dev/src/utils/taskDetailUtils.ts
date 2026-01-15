import { TaskDetailItem } from '@/types/task';
import { mapActionToChinese, getStatusConfig } from '@/utils/taskUtils';
import { parseToTimestamp, formatDuration } from '@/utils/timeUtils';

export function selectPrimaryTask(items: TaskDetailItem[] | undefined | null): TaskDetailItem | null {
  if (!items || items.length === 0) return null;

  const withTime = items.filter((it) => !!it.createTime);
  if (withTime.length > 0) {
    withTime.sort((a, b) => {
      const ta = new Date(a.createTime || '').getTime() || 0;
      const tb = new Date(b.createTime || '').getTime() || 0;
      return tb - ta;
    });
    return withTime[0];
  }

  return items[0] || null;
}

export function buildPrimaryTaskFromDetail(responseData: any) {
  if (!responseData) return null;
  const processedItems: any[] = Array.isArray(responseData.items)
    ? responseData.items
    : responseData.items
    ? [responseData.items]
    : [];

  const pendingCount = responseData.pending_count ?? responseData.pendingCount ?? responseData.pending ?? 0;
  const runningCount = responseData.running_count ?? responseData.runningCount ?? responseData.running ?? 0;
  const successCount = responseData.success_count ?? responseData.successCount ?? responseData.success ?? 0;
  const failedCount = responseData.failed_count ?? responseData.failedCount ?? responseData.failed ?? 0;
  const totalCount = responseData.total ?? responseData.totalCount ?? responseData.subTaskCount ?? 0;

  const finalStatus = responseData.task_status ?? "PENDING";

  const firstItem = Array.isArray(processedItems) && processedItems.length > 0 ? processedItems[0] : (responseData.items && responseData.items[0]) || null;
  const createdAt = firstItem?.createdAt ?? firstItem?.createTime ?? firstItem?.created_at ?? null;
  const finishedAt = processedItems.reduce((max: number, item: any) => {
    const finished = item.finishedAt ?? null;
    return finished ? Math.max(max, parseToTimestamp(finished) || 0) : max;
  }, Number.MIN_SAFE_INTEGER);
  
  let duration = undefined;
  if (finalStatus === 'PENDING') {
    duration = '等待中';
  } else if (finalStatus === 'RUNNING') {
    if (createdAt) {
      try {
        const s = parseToTimestamp(createdAt);
        if (typeof s === 'number' && !Number.isNaN(s)) {
          const now = Date.now();
          const durMs = Math.max(0, now - s);
          const durSec = Math.floor(durMs / 1000);
          duration = formatDuration(durSec);
        }
      } catch (e) {
        duration = undefined;
      }
    }
  } else if (createdAt && finishedAt) {
    try {
      const s = parseToTimestamp(createdAt);
      const f = parseToTimestamp(finishedAt);
      if (typeof s === 'number' && typeof f === 'number' && !Number.isNaN(s) && !Number.isNaN(f)) {
        const durMs = Math.max(0, f - s);
        const durSec = Math.floor(durMs / 1000);
        duration = formatDuration(durSec);
      }
    } catch (e) {
      duration = undefined;
    }
  }

  const workflowParams = firstItem?.workflowParams ?? firstItem?.workflow_params ?? null;

  const action = firstItem.action ?? null;
  const taskId = firstItem.taskId ?? null;
  const actionLabel = mapActionToChinese(String(action ?? ''));
  const shortId = (taskId || '').toString().slice(0, 8);

  const statusCfg = getStatusConfig(finalStatus ?? '');

  const primary = {
    action,
    actionLabel,
    taskId,
    taskName: `${actionLabel} - ${shortId}`,
    status: finalStatus ?? null,
    statusCfg: statusCfg ?? null,
    successCount,
    totalCount,
    pendingCount,
    runningCount,
    failedCount,
    createTime: createdAt,
    updateTime: finishedAt,
    duration,
    durationDisplay: duration,
    workflowParams,
  };

  console.log('Built primary task from detail:', primary);

  return primary;
}
