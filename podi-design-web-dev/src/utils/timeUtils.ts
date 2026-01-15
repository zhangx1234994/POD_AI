// ========== 时间/日期格式化与解析工具函数 ==========
/**
 * 格式化日期时间为 "YYYY-MM-DD HH:mm:ss"（东八区）
 */
export function formatDateTime(value: string | number | Date): string {
  try {
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return '';
    return new Intl.DateTimeFormat('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
      timeZone: 'Asia/Shanghai',
    }).format(d);
  } catch {
    return '';
  }
};

/**
 * 将任意值解析为时间戳（毫秒），支持：时间戳、日期字符串、Date 对象
 * @returns 时间戳（ms），无效时返回 undefined
 */
export const parseToTimestamp = (v: any): number | undefined => {
  if (v === null || v === undefined) return undefined;
  if (typeof v === 'number') return v;

  const n = Number(v);
  if (!Number.isNaN(n) && String(v).trim() !== '') return n;

  const d = Date.parse(String(v));
  if (!Number.isNaN(d)) return d;

  return undefined;
};

/**
 * 将毫秒转换为人类可读的持续时间（如 "1时 30分、1分 30秒、30秒"）
 */
export const formatDurationFromMs = (ms: number): string => {
  const secs = Math.floor(ms / 1000);
  if (secs < 60) return `${secs}秒`;
  if (secs < 3600) return `${Math.floor(secs / 60)}分 ${secs % 60}秒`;
  const hours = Math.floor(secs / 3600);
  const mins = Math.floor((secs % 3600) / 60);
  return `${hours}时 ${mins}分`;
};

/**
 * 智能格式化持续时间（支持数字、字符串、带单位的值）
 */
export const formatDuration = (val: any): string => {
  if (val === null || val === undefined) return '-';
  if (typeof val === 'string') {
    if (/^\d+[smh]/.test(val) || /\d+m\s+\d+s/.test(val) || /\d+h\s+\d+m/.test(val)) return val;
    const n = Number(val);
    if (!Number.isNaN(n)) {
      return formatDurationFromMs(n < 1e12 ? n * 1000 : n);
    }
  }
  if (typeof val === 'number') {
    if (val > 1e12) return formatDurationFromMs(val);
    return formatDurationFromMs(val * 1000);
  }
  return '-';
};

/**
 * 格式化相对时间（如 "刚刚"、"5分钟前"、"3小时前"、"2天前"）
 */
export function formatRelativeTime(dateString: string): string {
  if (!dateString) return '';

  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);

  if (diffMins < 1) return '刚刚';
  if (diffMins < 60) return `${diffMins}分钟前`;

  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}小时前`;

  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays}天前`;
};

/**
 * 根据前端时间筛选选项返回起止时间（毫秒字符串）
 * timeFilter: 'custom' | 'today' | 'yesterday' | 'last3days' | 'last7days' | 'last30days'
 */
export const getTimeRange = (
  timeFilter: string,
  customDate?: { from?: Date; to?: Date }
): { startTime?: string; endTime?: string } => {
  let startTime: Date | undefined;
  let endTime: Date | undefined;

  switch (timeFilter) {
    case 'custom':
      if (customDate?.from) {
        startTime = new Date(customDate.from);
        startTime.setUTCHours(0, 0, 0, 0);

        if (customDate.to) {
          endTime = new Date(customDate.to);
          endTime.setUTCDate(endTime.getUTCDate() + 1);
          endTime.setUTCHours(0, 0, 0, 0);
        } else {
          endTime = new Date(customDate.from);
          endTime.setUTCDate(endTime.getUTCDate() + 1);
          endTime.setUTCHours(0, 0, 0, 0);
        }
      }
      break;
    case 'today':
      startTime = new Date();
      startTime.setUTCHours(0, 0, 0, 0);
      endTime = new Date();
      break;
    case 'yesterday':
      startTime = new Date();
      startTime.setUTCDate(startTime.getUTCDate() - 1);
      startTime.setUTCHours(0, 0, 0, 0);
      endTime = new Date();
      endTime.setUTCHours(0, 0, 0, 0);
      break;
    case 'last3days':
      startTime = new Date();
      startTime.setUTCDate(startTime.getUTCDate() - 3);
      startTime.setUTCHours(0, 0, 0, 0);
      endTime = new Date();
      break;
    case 'last7days':
      startTime = new Date();
      startTime.setUTCDate(startTime.getUTCDate() - 7);
      startTime.setUTCHours(0, 0, 0, 0);
      endTime = new Date();
      break;
    case 'last30days':
      startTime = new Date();
      startTime.setUTCDate(startTime.getUTCDate() - 30);
      startTime.setUTCHours(0, 0, 0, 0);
      endTime = new Date();
      break;
    default:
      return {};
  }

  return {
    startTime: startTime ? startTime.getTime().toString() : undefined,
    endTime: endTime ? endTime.getTime().toString() : undefined,
  };
};

export default {
  formatDateTime,
  parseToTimestamp,
  formatDurationFromMs,
  formatDuration,
  formatRelativeTime,
  getTimeRange,
};
