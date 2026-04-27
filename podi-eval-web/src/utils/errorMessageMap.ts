const ERROR_CODE_MESSAGE_MAP: Record<string, string> = {
  AUTHORIZATION_REQUIRED: '当前请求未登录或登录已过期',
  INVALID_TOKEN: '登录状态无效',
  INVALID_CREDENTIALS: '账号或密码错误',
  USER_INACTIVE: '当前账号已被禁用',
  ADMIN_ONLY: '当前操作仅管理员可用',
  BATCH_ASSET_LIMIT_EXCEEDED: '本次上传素材超过上限',
  BATCH_REVIEW_NOT_READY: '批次尚未结束，暂不可标注',
  EXECUTOR_BUSY: '执行节点繁忙',
  EXECUTOR_NOT_FOUND: '执行节点不存在或已下线',
  INTERNAL_ONLY: '中台只允许内网或服务 Token 调用',
  PROMPT_REQUIRED: '缺少提示词',
  COZE_SUBMIT_FAILED: '工作流提交失败',
  COZE_WORKFLOW_ERROR: '工作流内部执行失败',
  FANOUT_PARTIAL_FAILED: '批量任务部分失败',
  TASK_NOT_FOUND: '任务不存在或已失效',
  TASK_TIMEOUT: '任务执行超时',
  TASK_IMAGES_EMPTY: '任务完成但没有返回图片',
  CALLBACK_TASK_NOT_RESOLVED: '回调任务未解析成功',
  CALLBACK_IMAGES_EMPTY: '回调没有解析到图片',
  Q1001: 'ComfyUI 队列已满',
  Q2001: '商业模型队列已满',
  COMFYUI_QUEUE_STATUS_ERROR: 'ComfyUI 队列读取失败',
  COMFYUI_TIMEOUT: 'ComfyUI 执行超时',
  COMFYUI_SUBMIT_ERROR: 'ComfyUI 提交失败',
  AGENT_PUSH_FAILED: '任务下发到代理服务失败',
  KIE_TIMEOUT: 'KIE 任务超时',
  VENDOR_CREDITS_INSUFFICIENT: '第三方账号余额不足',
  IMAGE_DOWNLOAD_FAILED: '图片下载失败',
};

const parseErrorPayload = (message: string): string => {
  const text = String(message || '').trim();
  if (!text) return '';
  try {
    const parsed = JSON.parse(text);
    if (typeof parsed?.detail === 'string') return parsed.detail;
    if (typeof parsed?.message === 'string') return parsed.message;
    if (typeof parsed?.error_message === 'string') return parsed.error_message;
  } catch {
    // ignore
  }
  return text;
};

const extractErrorCode = (message: string): string => {
  const text = parseErrorPayload(message);
  if (!text) return '';
  const queueMatched = text.match(/ERR\|([A-Z0-9_]+)\|/);
  if (queueMatched?.[1]) return queueMatched[1];
  const lowered = text.toLowerCase();
  if (lowered.includes('credits insufficient') || lowered.includes('insufficient balance') || lowered.includes('current balance')) {
    return 'VENDOR_CREDITS_INSUFFICIENT';
  }
  if (lowered.includes('internal_only')) return 'INTERNAL_ONLY';
  if (lowered.includes('prompt_required')) return 'PROMPT_REQUIRED';
  const fanoutMatched = text.match(/^(FANOUT_[A-Z0-9_]+)(?:\[([^\]]+)\])?/);
  if (fanoutMatched?.[2]) {
    const innerMatched = fanoutMatched[2].match(/\b([A-Z][A-Z0-9_]+)\s*=/);
    if (innerMatched?.[1]) return innerMatched[1];
  }
  if (fanoutMatched?.[1]) return fanoutMatched[1];
  const directMatch = text.match(/\b([A-Z][A-Z0-9_]{2,})\b/g);
  if (!directMatch?.length) return '';
  const code = directMatch.find((item) => item in ERROR_CODE_MESSAGE_MAP);
  return code || directMatch[0];
};

export const toDisplayErrorMessage = (message?: string | null): string => {
  const text = parseErrorPayload(String(message || ''));
  if (!text) return '';
  const code = extractErrorCode(text);
  const mapped = code ? ERROR_CODE_MESSAGE_MAP[code] : '';
  if (mapped) return `${mapped}（${code}）`;
  return text;
};
