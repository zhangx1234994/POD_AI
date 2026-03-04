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
  COZE_SUBMIT_FAILED: '工作流提交失败',
  TASK_NOT_FOUND: '任务不存在或已失效',
  TASK_TIMEOUT: '任务执行超时',
  CALLBACK_TASK_NOT_RESOLVED: '回调任务未解析成功',
  Q1001: 'ComfyUI 队列已满',
  Q2001: '商业模型队列已满',
  COMFYUI_TIMEOUT: 'ComfyUI 执行超时',
  COMFYUI_SUBMIT_ERROR: 'ComfyUI 提交失败',
  AGENT_PUSH_FAILED: '任务下发到代理服务失败',
  KIE_TIMEOUT: 'KIE 任务超时',
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

export const extractErrorCode = (message: string): string => {
  const text = parseErrorPayload(message);
  if (!text) return '';
  const queueMatched = text.match(/ERR\|([A-Z0-9_]+)\|/);
  if (queueMatched?.[1]) return queueMatched[1];
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
