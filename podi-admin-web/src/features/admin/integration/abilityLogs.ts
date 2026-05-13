import type { AbilityInvocationLog } from '../../../types/admin';

const getJsonRecord = (value: unknown): Record<string, any> | null => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  return value as Record<string, any>;
};

const collectAssetUrls = (assets: unknown): string[] => {
  if (!Array.isArray(assets)) return [];
  const urls: string[] = [];
  assets.forEach((asset) => {
    if (!asset || typeof asset !== 'object') return;
    const row = asset as Record<string, any>;
    const candidate = row.ossUrl || row.url || row.sourceUrl;
    if (typeof candidate === 'string' && candidate.trim()) {
      urls.push(candidate.trim());
    }
  });
  return urls;
};

const collectStringUrls = (items: unknown): string[] => {
  if (!Array.isArray(items)) return [];
  const urls: string[] = [];
  items.forEach((item) => {
    if (typeof item === 'string' && item.trim()) {
      urls.push(item.trim());
      return;
    }
    if (!item || typeof item !== 'object') return;
    const row = item as Record<string, any>;
    const candidate = row.ossUrl || row.url || row.sourceUrl;
    if (typeof candidate === 'string' && candidate.trim()) {
      urls.push(candidate.trim());
    }
  });
  return urls;
};

const collectTexts = (items: unknown): string[] => {
  if (!Array.isArray(items)) return [];
  return items
    .map((item) => {
      if (typeof item === 'string') return item.trim();
      if (!item || typeof item !== 'object') return '';
      const row = item as Record<string, any>;
      const candidate = row.text || row.content || row.value || row.output;
      return typeof candidate === 'string' ? candidate.trim() : '';
    })
    .filter(Boolean);
};

const dedupUrls = (items: string[]) => {
  const seen = new Set<string>();
  return items.filter((item) => {
    if (!item || seen.has(item)) return false;
    seen.add(item);
    return true;
  });
};

const classifyOutputUrl = (url?: string | null) => {
  const value = String(url || '').toLowerCase();
  if (/\.(png|jpg|jpeg|webp|gif|bmp|svg)(\?|#|$)/i.test(value)) return 'image' as const;
  if (/\.(mp4|mov|webm|m4v|avi|mkv)(\?|#|$)/i.test(value)) return 'video' as const;
  return 'asset' as const;
};

export const resolveLogPreviewUrls = (row: AbilityInvocationLog): string[] => {
  const responsePayload = getJsonRecord(row.response_payload);
  return dedupUrls([
    ...(typeof row.stored_url === 'string' && row.stored_url.trim() ? [row.stored_url.trim()] : []),
    ...collectAssetUrls(row.result_assets),
    ...collectAssetUrls(responsePayload?.assets),
    ...collectAssetUrls(responsePayload?.images),
    ...collectAssetUrls(responsePayload?.videos),
    ...collectStringUrls(responsePayload?.imageUrls),
    ...collectStringUrls(responsePayload?.videoUrls),
    ...collectStringUrls(responsePayload?.resultUrls),
    ...(typeof responsePayload?.imageUrl === 'string' && responsePayload.imageUrl.trim()
      ? [responsePayload.imageUrl.trim()]
      : []),
    ...(typeof responsePayload?.videoUrl === 'string' && responsePayload.videoUrl.trim()
      ? [responsePayload.videoUrl.trim()]
      : []),
  ]);
};

export const resolvePrimaryLogPreviewUrl = (row: AbilityInvocationLog): string => {
  const urls = resolveLogPreviewUrls(row);
  return urls[0] || '';
};

export const resolveLogOutputSummary = (row: AbilityInvocationLog) => {
  const responsePayload = getJsonRecord(row.response_payload);
  const serverSummary = row.output_summary;
  const urls = resolveLogPreviewUrls(row);
  const imageUrls = urls.filter((url) => classifyOutputUrl(url) === 'image');
  const videoUrls = urls.filter((url) => classifyOutputUrl(url) === 'video');
  const texts = [
    ...(typeof responsePayload?.text === 'string' && responsePayload.text.trim() ? [responsePayload.text.trim()] : []),
    ...collectTexts(responsePayload?.texts),
  ];
  const primaryUrl = (typeof serverSummary?.primary_url === 'string' && serverSummary.primary_url.trim()) || urls[0] || '';
  const primaryKind =
    typeof serverSummary?.primary_kind === 'string' && serverSummary.primary_kind
      ? serverSummary.primary_kind
      : texts.length > 0 && !primaryUrl
        ? 'text'
        : classifyOutputUrl(primaryUrl);
  const textPreview =
    (typeof serverSummary?.text_preview === 'string' && serverSummary.text_preview) ||
    (texts[0] ? (texts[0].length > 120 ? `${texts[0].slice(0, 117)}...` : texts[0]) : '');
  const imageCount = typeof serverSummary?.image_count === 'number' ? serverSummary.image_count : imageUrls.length;
  const videoCount = typeof serverSummary?.video_count === 'number' ? serverSummary.video_count : videoUrls.length;
  const textCount = typeof serverSummary?.text_count === 'number' ? serverSummary.text_count : texts.length;
  const structuredCount = typeof serverSummary?.structured_count === 'number' ? serverSummary.structured_count : 0;
  const assetCount =
    typeof serverSummary?.asset_count === 'number'
      ? serverSummary.asset_count
      : Math.max(0, urls.length - imageUrls.length - videoUrls.length);
  const labelParts = [
    imageCount > 0 ? `${imageCount} 张图` : '',
    videoCount > 0 ? `${videoCount} 个视频` : '',
    textCount > 0 ? `${textCount} 段文字` : '',
    structuredCount > 0 ? `${structuredCount} 个结构化结果` : '',
    assetCount > 0 ? `${assetCount} 个资源` : '',
  ].filter(Boolean);
  const hasOutput = Boolean(serverSummary?.has_output) || urls.length > 0 || texts.length > 0 || structuredCount > 0;
  return {
    urls,
    imageUrls,
    videoUrls,
    texts,
    primaryUrl,
    primaryKind,
    textPreview,
    imageCount,
    videoCount,
    textCount,
    structuredCount,
    assetCount,
    label: labelParts.join(' · ') || '无输出',
    hasOutput,
  };
};

export const resolveLogDurationMs = (row: AbilityInvocationLog): number | null => {
  if (typeof row.duration_ms === 'number') return row.duration_ms;
  const payload = getJsonRecord(row.response_payload);
  const candidate = payload?.durationMs ?? payload?.duration_ms;
  return typeof candidate === 'number' ? candidate : null;
};

export const getAbilityLogCallbackConfigured = (row: AbilityInvocationLog): boolean | null => {
  const payload = getJsonRecord(row.request_payload);
  const value = payload?.callbackConfigured;
  return typeof value === 'boolean' ? value : null;
};

export const isAbilityLogSuccessful = (status?: string | null): boolean => {
  const normalized = (status || '').trim().toLowerCase();
  return ['success', 'succeeded', 'completed', 'done', 'ok'].includes(normalized);
};

export const isAbilityLogFailed = (status?: string | null): boolean => {
  const normalized = (status || '').trim().toLowerCase();
  return ['failed', 'error', 'timeout', 'rejected'].includes(normalized);
};

const isAbilityLogActive = (status?: string | null): boolean => {
  const normalized = (status || '').trim().toLowerCase();
  return ['running', 'processing', 'in_progress', 'queued', 'pending', 'created'].includes(normalized);
};

export const isAbilityLogCallbackFailed = (row: AbilityInvocationLog): boolean => {
  const callbackStatus = (row.callback_status || '').trim().toLowerCase();
  return (
    isAbilityLogFailed(callbackStatus) ||
    Boolean(row.callback_error) ||
    (typeof row.callback_http_status === 'number' && row.callback_http_status >= 400)
  );
};

const hasComfyuiPromptMarker = (row: AbilityInvocationLog): boolean => {
  const payload = getJsonRecord(row.response_payload);
  return Boolean(payload?.promptId || payload?.prompt_id || payload?.taskId || payload?.task_id);
};

export type AbilityLogTroubleKind =
  | 'execution_failed'
  | 'callback_failed'
  | 'success_without_output'
  | 'active'
  | 'healthy'
  | 'needs_evidence';

export type AbilityLogTroubleSummaryItem = {
  key: AbilityLogTroubleKind;
  title: string;
  count: number;
  theme: 'success' | 'warning' | 'danger' | 'default';
  detail: string;
  action: string;
};

const abilityLogTroubleMeta: Record<
  AbilityLogTroubleKind,
  Omit<AbilityLogTroubleSummaryItem, 'key' | 'count'>
> = {
  execution_failed: {
    title: '执行失败',
    theme: 'danger',
    detail: '提交、厂商、节点或参数已经失败。',
    action: '先看错误摘要，再按原参数复测或切换节点。',
  },
  callback_failed: {
    title: '回调失败',
    theme: 'danger',
    detail: '结果已产生或进入回调阶段，但业务侧没有接住。',
    action: '复制回调编号，确认回调地址、鉴权和重试结果。',
  },
  success_without_output: {
    title: '成功无回填',
    theme: 'warning',
    detail: '任务状态成功，但没有解析到图片、视频、文字或结构化结果。',
    action: '打开详情拉取结果，确认上游输出字段和 OSS 沉淀。',
  },
  active: {
    title: '排队或执行中',
    theme: 'warning',
    detail: '任务还没进入终态，可能在队列、执行器或回调链路中。',
    action: '超过预期时先看 ComfyUI 队列和执行节点健康。',
  },
  healthy: {
    title: '已回填',
    theme: 'success',
    detail: '调用成功且已有可用输出。',
    action: '可作为验收样本或线上回归证据。',
  },
  needs_evidence: {
    title: '证据不足',
    theme: 'default',
    detail: '状态和输出证据都不完整。',
    action: '刷新记录或打开详情查看原始请求、响应和追踪编号。',
  },
};

export const resolveAbilityLogTroubleKind = (row: AbilityInvocationLog): AbilityLogTroubleKind => {
  const output = resolveLogOutputSummary(row);
  if (isAbilityLogFailed(row.status) || row.error_message) return 'execution_failed';
  if (isAbilityLogCallbackFailed(row)) return 'callback_failed';
  if (isAbilityLogSuccessful(row.status) && !output.hasOutput) return 'success_without_output';
  if (isAbilityLogActive(row.status)) return 'active';
  if (output.hasOutput) return 'healthy';
  return 'needs_evidence';
};

export const buildAbilityLogTroubleSummary = (rows: AbilityInvocationLog[]): AbilityLogTroubleSummaryItem[] => {
  const counts = rows.reduce(
    (acc, row) => {
      const kind = resolveAbilityLogTroubleKind(row);
      acc[kind] += 1;
      return acc;
    },
    {
      execution_failed: 0,
      callback_failed: 0,
      success_without_output: 0,
      active: 0,
      healthy: 0,
      needs_evidence: 0,
    } as Record<AbilityLogTroubleKind, number>,
  );
  return (Object.keys(abilityLogTroubleMeta) as AbilityLogTroubleKind[]).map((key) => ({
    key,
    count: counts[key],
    ...abilityLogTroubleMeta[key],
  }));
};

export const resolveAbilityLogAction = (row: AbilityInvocationLog) => {
  const output = resolveLogOutputSummary(row);
  const callbackFailed = isAbilityLogCallbackFailed(row);

  if (isAbilityLogFailed(row.status) || row.error_message) {
    return {
      theme: 'danger' as const,
      title: '先排查执行失败',
      detail: '看错误摘要和请求内容，必要时切换节点或按原参数复测。',
    };
  }

  if (callbackFailed) {
    return {
      theme: 'danger' as const,
      title: '先处理回调失败',
      detail: '复制回调编号，确认业务回调地址和鉴权，再执行回调重试。',
    };
  }

  if (isAbilityLogSuccessful(row.status) && !output.hasOutput) {
    if ((row.ability_provider || '').toLowerCase() === 'comfyui' && hasComfyuiPromptMarker(row)) {
      return {
        theme: 'warning' as const,
        title: '先拉取回调结果',
        detail: 'ComfyUI 已提交但没有解析到输出，进入详情拉取回调结果。',
      };
    }
    return {
      theme: 'warning' as const,
      title: '确认结果回填',
      detail: '执行成功但没有图片、视频或文字，先看响应内容再决定是否复测。',
    };
  }

  if (isAbilityLogActive(row.status)) {
    return {
      theme: 'warning' as const,
      title: '等待或切节点',
      detail: '任务仍在排队或执行；若长期不变，先看节点队列和执行器健康。',
    };
  }

  if (output.hasOutput) {
    return {
      theme: 'success' as const,
      title: '可作为样本',
      detail: '结果已回填，可用于验收、对比或排障留证。',
    };
  }

  return {
    theme: 'default' as const,
    title: '继续观察',
    detail: '当前记录证据不足，先刷新调用记录或打开详情查看上下文。',
  };
};

export const getAbilityLogSubmitTag = (row: AbilityInvocationLog) => {
  const normalized = (row.status || '').trim().toLowerCase();
  if (['failed', 'error', 'timeout', 'rejected'].includes(normalized)) {
    return { theme: 'danger' as const, text: '提交失败' };
  }
  if (['running', 'processing', 'in_progress', 'queued', 'pending', 'created'].includes(normalized)) {
    return { theme: 'warning' as const, text: '提交中' };
  }
  if (['success', 'succeeded', 'completed', 'done', 'ok'].includes(normalized)) {
    return { theme: 'success' as const, text: '提交成功' };
  }
  if (['cancelled', 'canceled', 'stopped', 'aborted'].includes(normalized)) {
    return { theme: 'default' as const, text: '已取消' };
  }
  return { theme: 'default' as const, text: row.status || '未知' };
};

export const getAbilityLogCallbackStageTag = (row: AbilityInvocationLog) => {
  const callbackConfigured = getAbilityLogCallbackConfigured(row);
  const callbackStatus = (row.callback_status || '').trim().toLowerCase();
  const callbackFailed = isAbilityLogCallbackFailed(row);
  const callbackFinished = Boolean(row.callback_finished_at);
  const output = resolveLogOutputSummary(row);
  if (callbackFailed) return { theme: 'danger' as const, text: '回调失败' };
  if (isAbilityLogSuccessful(callbackStatus)) return { theme: 'success' as const, text: '回调成功' };
  if (callbackStatus && ['running', 'processing', 'pending', 'queued'].includes(callbackStatus)) {
    return { theme: 'warning' as const, text: '回调中' };
  }
  if (callbackFinished && typeof row.callback_http_status === 'number' && row.callback_http_status < 400) {
    return { theme: 'success' as const, text: '回调成功' };
  }

  const hasCallbackId = Boolean(row.callback_id);
  const previewUrl = resolvePrimaryLogPreviewUrl(row);
  if (isAbilityLogSuccessful(row.status) && output.hasOutput) {
    if (output.textCount > 0 && output.imageCount === 0 && output.videoCount === 0) {
      return { theme: 'success' as const, text: '文字已入库' };
    }
    if (output.structuredCount > 0 && output.imageCount === 0 && output.videoCount === 0) {
      return { theme: 'success' as const, text: '结构化已入库' };
    }
    if (output.videoCount > 0 && output.imageCount === 0) {
      return { theme: 'success' as const, text: '视频已回填' };
    }
    return { theme: 'success' as const, text: previewUrl ? '输出已回填' : '结果已入库' };
  }
  if (callbackConfigured === true) {
    return { theme: 'warning' as const, text: '待回调' };
  }
  if (hasCallbackId) {
    if (previewUrl) return { theme: 'success' as const, text: '输出已回填' };
    if (isAbilityLogSuccessful(row.status)) return { theme: 'default' as const, text: '等待结果入库' };
    if (isAbilityLogFailed(row.status)) return { theme: 'danger' as const, text: '执行失败' };
    return { theme: 'default' as const, text: '可查询' };
  }
  if (callbackConfigured === false) {
    return { theme: 'default' as const, text: '未配置' };
  }
  return { theme: 'default' as const, text: '—' };
};

export const getAbilityLogStatusTag = (status?: string | null) => {
  const normalized = (status || '').trim().toLowerCase();
  if (['success', 'succeeded', 'completed', 'done', 'ok'].includes(normalized)) {
    return { theme: 'success' as const, text: '成功' };
  }
  if (['failed', 'error', 'timeout', 'rejected'].includes(normalized)) {
    return { theme: 'danger' as const, text: '失败' };
  }
  if (['running', 'processing', 'in_progress'].includes(normalized)) {
    return { theme: 'warning' as const, text: '执行中' };
  }
  if (['queued', 'pending', 'created'].includes(normalized)) {
    return { theme: 'warning' as const, text: '排队中' };
  }
  if (['cancelled', 'canceled', 'stopped', 'aborted'].includes(normalized)) {
    return { theme: 'default' as const, text: '已取消' };
  }
  return { theme: 'default' as const, text: status || '未知' };
};

export const getAbilityHealthTag = (status?: string | null) => {
  const normalized = (status || '').trim().toLowerCase();
  if (normalized === 'healthy') return { theme: 'success' as const, text: '正常' };
  if (normalized === 'degraded') return { theme: 'warning' as const, text: '需关注' };
  if (normalized === 'failed') return { theme: 'danger' as const, text: '异常' };
  return { theme: 'default' as const, text: '未测试' };
};
