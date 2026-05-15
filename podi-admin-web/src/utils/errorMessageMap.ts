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
  INTERNAL_ONLY: '接口只允许内部服务调用',
  VENDOR_API_KEY_MISSING: '第三方密钥不可用或未命中',
  VENDOR_API_EXECUTION_FAILED: '第三方模型调用失败',
  BUSINESS_RUN_TIMEOUT: '业务任务等待超时',
  BUSINESS_RUN_GET_FAILED: '业务任务结果查询异常',
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
  if (/system protection triggered by request burst/i.test(text)) {
    return '上游触发请求保护：请求过快，请降低并发或拉长重试间隔。';
  }
  if (/out of sort memory/i.test(text)) {
    return '数据库排序内存不足：请缩小查询范围或联系中台优化索引。';
  }
  if (/api[-_ ]?key|apikey|key.*missing|missing.*key/i.test(text)) {
    return '第三方密钥不可用或未命中：先检查中台 Key 池、能力绑定和执行节点配置。';
  }
  const code = extractErrorCode(text);
  const mapped = code ? ERROR_CODE_MESSAGE_MAP[code] : '';
  if (mapped) return `${mapped}（${code}）`;
  return text;
};
