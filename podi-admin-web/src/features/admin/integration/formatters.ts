const currencySymbolMap: Record<string, string> = { CNY: '¥', USD: '$', EUR: '€' };

export const parseDateValue = (value?: string | null): Date | null => {
  if (!value) return null;
  const raw = String(value).trim();
  if (!raw) return null;

  // Server timestamps without timezone are stored as UTC and displayed in China time.
  const hasTimezone = /[zZ]|[+-]\d{2}:?\d{2}$/.test(raw);
  if (hasTimezone) {
    const d = new Date(raw);
    return Number.isNaN(d.getTime()) ? null : d;
  }

  const normalized = raw.includes(' ') && !raw.includes('T') ? raw.replace(' ', 'T') : raw;
  const isoUtc = `${normalized}Z`;
  const d = new Date(isoUtc);
  return Number.isNaN(d.getTime()) ? null : d;
};

export const formatDateTime = (value?: string | null) => {
  const date = parseDateValue(value);
  if (!date) return value || '';
  return date.toLocaleString('zh-CN', { hour12: false, timeZone: 'Asia/Shanghai' });
};

export const formatDate = (value: string) => {
  const date = parseDateValue(value);
  if (!date) return value;
  return date.toLocaleString('zh-CN', { hour12: false, timeZone: 'Asia/Shanghai' });
};

export const formatDurationMs = (value?: number | null) => {
  if (value === undefined || value === null) return '—';
  if (value < 1000) return `${value}ms`;
  return `${(value / 1000).toFixed(2)}s`;
};

export const formatDurationSeconds = (value?: number | null) => {
  if (value === undefined || value === null) return '—';
  if (value < 60) return `${value}s`;
  if (value < 3600) return `${Math.round(value / 60)}分钟`;
  return `${(value / 3600).toFixed(1)}小时`;
};

export const formatUnitLabel = (unit?: string) => {
  if (!unit) return '每次';
  const map: Record<string, string> = {
    per_image: '每张',
    per_call: '每次',
    per_minute: '每分钟',
    per_hour: '每小时',
    per_token: '每千文字单元',
  };
  return map[unit] ?? unit;
};

export const formatPriceValue = (value?: number, currency?: string) => {
  if (typeof value !== 'number' || Number.isNaN(value)) return '—';
  const symbol = currency ? currencySymbolMap[currency] || currency : '';
  return `${symbol}${value.toFixed(2)}`;
};

export const formatCurrencyTotals = (totals?: Record<string, number> | null) => {
  const entries = Object.entries(totals || {}).filter(([, value]) => typeof value === 'number' && !Number.isNaN(value));
  if (entries.length === 0) return '—';
  return entries.map(([currency, value]) => formatPriceValue(value, currency)).join(' / ');
};

export const formatRatePercent = (value?: number | null) => {
  if (typeof value !== 'number' || Number.isNaN(value)) return '—';
  return `${Math.round(value * 100)}%`;
};

export const formatBucketDigest = (bucket?: { total?: number; failed?: number; successRate?: number | null }) => {
  if (!bucket) return '—';
  return `${bucket.total || 0} 次 · 成功率 ${formatRatePercent(bucket.successRate)} · 失败 ${bucket.failed || 0}`;
};
