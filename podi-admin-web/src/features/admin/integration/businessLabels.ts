import type { BusinessCapability } from '../../../types/admin';

export const coreBusinessKeys = ['pattern_extract', 'fission', 'outpaint'] as const;

export const businessKeyLabel = (key?: string | null) => {
  if (key === 'pattern_extract') return '花纹提取';
  if (key === 'fission') return '图裂变';
  if (key === 'outpaint') return '扩图';
  return key || '未命名业务';
};

export const businessBillingStatusLabel = (status?: string | null) => {
  if (status === 'billable') return '可计费';
  if (status === 'unpriced') return '待定价';
  if (status === 'no_charge') return '不计费';
  if (status === 'billing_pending') return '待完成';
  return '未记录';
};

export const businessBillingStatusTheme = (status?: string | null) => {
  if (status === 'billable') return 'success';
  if (status === 'unpriced') return 'warning';
  if (status === 'no_charge') return 'default';
  return 'primary';
};

export const businessRunStepStatusLabel = (status?: string | null) => {
  if (status === 'planned') return '待执行';
  if (status === 'queued') return '排队中';
  if (status === 'running') return '执行中';
  if (status === 'succeeded') return '已完成';
  if (status === 'failed') return '失败';
  if (status === 'cancelled') return '已取消';
  if (status === 'skipped') return '已跳过';
  return status || '未知';
};

export const businessCapabilityLatestRunLabel = (item: BusinessCapability) => {
  const latest = item.latestRun;
  if (!latest) return '暂无调用';
  const imageCount = Number(latest.imageCount ?? latest.image_count ?? 0);
  const videoCount = Number(latest.videoCount ?? latest.video_count ?? 0);
  if (latest.error) return String(latest.error);
  if (imageCount > 0) return `${imageCount} 张图`;
  if (videoCount > 0) return `${videoCount} 个视频`;
  return businessRunStepStatusLabel(latest.status);
};

export const businessCapabilityRunMetricsLabel = (item: BusinessCapability) => {
  const metrics = item.runMetrics;
  if (!metrics || !Number(metrics.total || 0)) return '近24小时暂无调用';
  const total = Number(metrics.total || 0);
  const succeeded = Number(metrics.succeeded || 0);
  const failed = Number(metrics.failed || 0);
  const running = Number(metrics.running || 0) + Number(metrics.queued || 0);
  const rawRate = metrics.successRate ?? metrics.success_rate;
  const successRate = typeof rawRate === 'number' ? Math.round(rawRate * 100) : Math.round((succeeded / total) * 100);
  return `近24小时 ${total} 次 · 成功 ${succeeded} · 失败 ${failed} · 进行中 ${running} · 成功率 ${successRate}%`;
};
