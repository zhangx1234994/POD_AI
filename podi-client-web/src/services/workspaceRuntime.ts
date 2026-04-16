import type { AbilityTask } from './clientApi';
import type { UploadResult } from '../types/media';
import type { ResultState, TaskDisplayStatus } from '../types/workspace';

export type { TaskDisplayStatus };

type TaskSummarySource = {
  status?: string | null;
  errorMessage?: string | null;
  provider?: string | null;
  resultPayload?: Record<string, unknown> | null;
};

export function extractPreviewUrl(payload: Record<string, unknown> | null | undefined): string | null {
  if (!payload) return null;
  const buckets = ['images', 'videos', 'assets'];
  for (const key of buckets) {
    const items = payload[key];
    if (!Array.isArray(items)) continue;
    for (const item of items) {
      if (!item || typeof item !== 'object') continue;
      const maybe = item as Record<string, unknown>;
      const url = maybe.ossUrl || maybe.sourceUrl || maybe.base64;
      if (typeof url === 'string' && url.trim()) return url;
    }
  }
  const texts = payload.texts;
  if (Array.isArray(texts) && typeof texts[0] === 'string') return texts[0];
  return null;
}

export function mapTaskStatus(status: string): TaskDisplayStatus['status'] {
  if (status === 'queued') return 'queued';
  if (status === 'running') return 'running';
  if (status === 'succeeded') return 'success';
  return 'failed';
}

export function describeTaskSummary(task: TaskSummarySource): string {
  if (task.errorMessage) return task.errorMessage;
  if (task.status === 'queued') return '任务已进入队列，正在等待系统调度。';
  if (task.status === 'running') return '任务正在处理中，可稍后继续回来查看。';
  if (task.status === 'succeeded') {
    return extractPreviewUrl(task.resultPayload) ? '结果已生成，可直接查看并继续创作。' : '任务已完成。';
  }
  return `${task.provider || '任务'} · ${task.status || 'unknown'}`;
}

function toUpload(url: string, name?: string): UploadResult {
  return {
    url,
    objectKey: url,
    name: name || url.split('/').pop() || 'seed-image',
    size: 0,
  };
}

export function buildWorkspaceSeedFromTask(task: AbilityTask, includeResult = false) {
  const requestPayload =
    task.requestPayload && typeof task.requestPayload === 'object'
      ? (task.requestPayload as Record<string, unknown>)
      : null;

  const uploads: UploadResult[] = [];
  const images = requestPayload?.images;
  if (Array.isArray(images)) {
    for (const item of images) {
      if (!item || typeof item !== 'object') continue;
      const image = item as Record<string, unknown>;
      const url = image.ossUrl || image.url || image.sourceUrl;
      if (typeof url === 'string' && url.trim()) {
        uploads.push(toUpload(url, typeof image.name === 'string' ? image.name : undefined));
      }
    }
  }
  if (!uploads.length && typeof requestPayload?.imageUrl === 'string' && requestPayload.imageUrl.trim()) {
    uploads.push(toUpload(requestPayload.imageUrl));
  }

  const rawInputs =
    requestPayload?.inputs && typeof requestPayload.inputs === 'object'
      ? (requestPayload.inputs as Record<string, unknown>)
      : null;
  const formValues = rawInputs
    ? Object.fromEntries(
        Object.entries(rawInputs)
          .filter(([, value]) => ['string', 'number', 'boolean'].includes(typeof value))
          .map(([key, value]) => [key, String(value)]),
      )
    : {};

  if (!includeResult) {
    return { uploads, formValues };
  }

  const preview = extractPreviewUrl(task.resultPayload);
  return {
    uploads,
    formValues,
    result: {
      status: mapTaskStatus(task.status),
      taskId: task.id,
      message: describeTaskSummary(task),
      mediaUrl: preview && /^https?:/.test(preview) ? preview : undefined,
      text: preview && !/^https?:/.test(preview) ? preview : undefined,
    } satisfies ResultState,
  };
}
