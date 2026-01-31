import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  Alert,
  Button,
  Card,
  Col,
  ConfigProvider,
  Dialog,
  Input,
  Layout,
  Menu,
  Rate,
  Row,
  Select,
  Space,
  Switch,
  Table,
  Tabs,
  Tag,
  Textarea,
  Typography,
  MessagePlugin,
} from 'tdesign-react';
import zhCN from 'tdesign-react/es/locale/zh_CN';
import { evalApi } from './api';
import type { EvalRun, EvalWorkflowVersion, SchemaField, WorkflowDoc } from './types';

type RunWithLatest = EvalRun & {
  latest_annotation?: { rating: number; comment?: string | null; created_at: string; created_by: string } | null;
};

// Keep the evaluation UI sidebar fixed to these 4 business-facing groups.
const CATEGORY_ORDER = ['花纹提取类', '图延伸类', '四方/两方连续图类', '图裂变', '通用类'];

const normalizeCategory = (category: string | undefined | null): string => {
  const c = String(category || '').trim();
  if (!c) return '通用类';
  if (CATEGORY_ORDER.includes(c)) return c;
  // Legacy/internal keys -> business labels
  if (c === 'pattern_extract' || c === 'pattern' || c === 'pattern-extract') return '花纹提取类';
  if (c === 'image_extend' || c === 'image_extension' || c === '图扩展' || c === '图延伸') return '图延伸类';
  if (c === 'continuous_pattern' || c === 'continuous' || c === 'lianxu') return '四方/两方连续图类';
  if (c === '图裂变' || c === 'variation' || c === 'image_variation' || c === 'liebain' || c === 'liebiam') return '图裂变';
  if (c === 'general' || c === 'common') return '通用类';
  return '通用类';
};

const getFields = (wf: EvalWorkflowVersion | null): SchemaField[] => {
  const schema = wf?.parameters_schema as any;
  const fields = schema?.fields;
  if (!Array.isArray(fields)) return [];
  return fields.filter((f: any) => f && typeof f === 'object' && typeof f.name === 'string');
};

const formatDuration = (ms?: number | null) => {
  if (!ms) return '—';
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
};

const fmtTime = (iso: string) => {
  try {
    const raw = String(iso || '').trim();
    if (!raw) return '—';
    // If backend returns a naive ISO string (no timezone), treat it as UTC.
    const hasTz = /Z$|[+-]\\d{2}:?\\d{2}$/.test(raw);
    const normalized = hasTz ? raw : `${raw}Z`;
    // Force CN business timezone regardless of server/browser settings.
    return new Date(normalized).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false });
  } catch {
    return iso;
  }
};

const formatJsonPreview = (value: unknown, maxLen = 1200): string => {
  try {
    if (value == null) return '';
    // Coze "JSON output" is often a JSON string.
    if (typeof value === 'string') {
      const s = value.trim();
      if (!s) return '';
      if ((s.startsWith('{') && s.endsWith('}')) || (s.startsWith('[') && s.endsWith(']'))) {
        try {
          const parsed = JSON.parse(s);
          const pretty = JSON.stringify(parsed, null, 2);
          return pretty.length > maxLen ? `${pretty.slice(0, maxLen)}…` : pretty;
        } catch {
          return s.length > maxLen ? `${s.slice(0, maxLen)}…` : s;
        }
      }
      return s.length > maxLen ? `${s.slice(0, maxLen)}…` : s;
    }
    const pretty = JSON.stringify(value, null, 2);
    return pretty.length > maxLen ? `${pretty.slice(0, maxLen)}…` : pretty;
  } catch {
    return String(value || '');
  }
};

const renderOptionTags = (options?: Array<{ label: string; value: string } | string>): ReactNode => {
  if (!Array.isArray(options) || options.length === 0) return '—';
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
      {options.map((opt, idx) => {
        if (typeof opt === 'string') {
          const value = opt.trim();
          return (
            <Tag key={`${value}-${idx}`} size="small" variant="light">
              {value}
            </Tag>
          );
        }
        const value = String(opt.value || opt.label || '').trim();
        return (
          <Tag key={`${value}-${idx}`} size="small" variant="light">
            {value}
          </Tag>
        );
      })}
    </div>
  );
};

const OMIT_PARAM_KEYS = new Set([
  'url',
  'image',
  'images',
  'image_url',
  'image_urls',
  'imageurl',
  'imageurls',
  'input_url',
  'input_urls',
  'inputurl',
  'inputurls',
  'input_oss_url',
  'input_oss_urls',
  'oss_url',
  'oss_urls',
]);

const filterDisplayParams = (
  params: Record<string, unknown> | null | undefined,
): Record<string, unknown> | null => {
  if (!params || typeof params !== 'object' || Array.isArray(params)) return null;
  const entries = Object.entries(params).filter(([key]) => {
    const normalized = key.trim().toLowerCase();
    return !OMIT_PARAM_KEYS.has(normalized);
  });
  if (entries.length === 0) return null;
  return Object.fromEntries(entries);
};

const buildCozeDoc = (wf: EvalWorkflowVersion, urlExample: string) => {
  const paramsExample: Record<string, unknown> = {};
  for (const f of getFields(wf)) {
    if (f.name === 'url') {
      paramsExample.url = urlExample || 'https://...';
      continue;
    }
    const options = Array.isArray((f as any).options) ? ((f as any).options as any[]) : null;
    if (options && options.length > 0) {
      paramsExample[f.name] = String(options[0].value);
      continue;
    }
    if (typeof (f as any).defaultValue === 'string') {
      paramsExample[f.name] = (f as any).defaultValue;
      continue;
    }
    paramsExample[f.name] = '';
  }
  return [
    'curl -X POST "$COZE_BASE_URL/v1/workflow/run" \\',
    '  -H "Authorization: Bearer $COZE_API_TOKEN" \\',
    '  -H "Content-Type: application/json" \\',
    `  -d '${JSON.stringify({ workflow_id: wf.workflow_id, parameters: paramsExample }, null, 2)}'`,
  ].join('\n');
};

const isLikelyImageUrl = (url: string): boolean => {
  const u = String(url || '').trim();
  if (!u.startsWith('http://') && !u.startsWith('https://')) return false;
  const lower = u.toLowerCase();
  // Coze debug URLs (HTML) are not image assets; avoid showing broken thumbnails.
  if (lower.includes('/work_flow') || (lower.includes('/workflow') && lower.includes('execute_id='))) return false;
  if (lower.includes('execute_mode=') && lower.includes('execute_id=')) return false;
  // Common image extensions and ComfyUI `/view?filename=xxx.png`.
  if (/\.(png|jpe?g|webp|gif|bmp)(\?|$)/.test(lower)) return true;
  if (lower.includes('filename=') && /filename=[^&]+\.(png|jpe?g|webp|gif|bmp)(\&|$)/.test(lower)) return true;
  // OSS storedUrl often carries an extension, but keep a small allowlist for safety.
  if (lower.includes('.aliyuncs.com') || lower.includes('.oss-')) return true;
  return false;
};

const filterImageUrls = (urls: unknown): string[] => {
  if (!Array.isArray(urls)) return [];
  return urls
    .filter((u) => typeof u === 'string')
    .map((u) => u.trim())
    .filter((u) => u && isLikelyImageUrl(u));
};

function Lightbox({
  url,
  title,
  onClose,
}: {
  url: string;
  title?: string;
  onClose: () => void;
}) {
  const [zoomed, setZoomed] = useState(false);

  useEffect(() => {
    setZoomed(false);
  }, [url]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  if (!url) return null;

  return (
    <Dialog
      visible
      header={title || '预览'}
      onClose={onClose}
      onCancel={onClose}
      footer={
        <Space style={{ justifyContent: 'space-between', width: '100%' }}>
          <Typography.Text theme="secondary" style={{ maxWidth: 560 }} ellipsis>
            {url}
          </Typography.Text>
          <Space>
            <Switch value={zoomed} onChange={(v) => setZoomed(Boolean(v))} />
            <Typography.Text theme="secondary">放大</Typography.Text>
            <Button variant="outline" onClick={() => window.open(url, '_blank', 'noreferrer')}>
              新窗口打开
            </Button>
          </Space>
        </Space>
      }
    >
      <div style={{ maxHeight: '70vh', overflow: 'auto' }}>
        <img
          src={url}
          alt="preview"
          style={{
            display: 'block',
            margin: '0 auto',
            maxWidth: zoomed ? 'none' : '100%',
            width: zoomed ? 'auto' : '100%',
            maxHeight: zoomed ? 'none' : '70vh',
            objectFit: 'contain',
          }}
        />
      </div>
    </Dialog>
  );
}

function ToolCard({
  wf,
  active,
  metric,
  onClick,
}: {
  wf: EvalWorkflowVersion;
  active: boolean;
  metric?: { ratingCount: number; avgRating: number | null };
  onClick: () => void;
}) {
  const ratingText = metric?.avgRating ? metric.avgRating.toFixed(2) : '—';
  const ratingCountText = metric?.ratingCount ? `${metric.ratingCount}票` : '未评分';
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') onClick();
      }}
      style={{ cursor: 'pointer', height: '100%' }}
    >
      <Card
        bordered
        style={{
          height: '100%',
          borderColor: active ? 'var(--td-brand-color)' : undefined,
        }}
      >
        <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
          <Space align="start" style={{ justifyContent: 'space-between', width: '100%' }}>
            <Space direction="vertical" size={2} style={{ minWidth: 0 }}>
              <Typography.Text strong ellipsis>
                {wf.name}
              </Typography.Text>
              <Typography.Text theme="secondary" style={{ fontSize: 12 }} ellipsis>
                {wf.workflow_id}
              </Typography.Text>
            </Space>
            <Space direction="vertical" size={2} style={{ alignItems: 'flex-end' }}>
              <Typography.Text>{ratingText}</Typography.Text>
              <Typography.Text theme="secondary" style={{ fontSize: 12 }}>
                {ratingCountText}
              </Typography.Text>
            </Space>
          </Space>

          <div
            className="podi-clamp-2"
            style={{
              marginTop: 8,
              fontSize: 12,
              lineHeight: '18px',
              minHeight: 36, // Reserve exactly 2 lines so all cards align.
              color: 'var(--td-text-color-secondary)',
            }}
          >
            {wf.notes || '—'}
          </div>

          <div style={{ marginTop: 12 }}>
            <Space breakLine>
              <Tag variant="light">{wf.version}</Tag>
              <Tag variant="light">{normalizeCategory(wf.category)}</Tag>
            </Space>
          </div>
        </div>
      </Card>
    </div>
  );
}

function ParamField({
  field,
  value,
  onChange,
}: {
  field: SchemaField;
  value: string;
  onChange: (v: string) => void;
}) {
  const label = field.label ?? field.name;
  const required = Boolean(field.required);
  const options = Array.isArray((field as any).options) ? ((field as any).options as any[]) : null;
  const type = (field.type || '').toLowerCase();

  if (options && options.length > 0) {
    return (
      <Space direction="vertical" size={4} style={{ width: '100%' }}>
        <Typography.Text>
          {label} {required ? <Typography.Text theme="error">*</Typography.Text> : null}
        </Typography.Text>
        <Select
          value={value}
          onChange={(v) => onChange(String(v))}
          options={options.map((opt) => ({ label: String(opt.label ?? opt.value), value: String(opt.value) }))}
        />
      </Space>
    );
  }

  if (type === 'textarea') {
    return (
      <Space direction="vertical" size={4} style={{ width: '100%' }}>
        <Typography.Text>
          {label} {required ? <Typography.Text theme="error">*</Typography.Text> : null}
        </Typography.Text>
        <Textarea value={value} onChange={(v) => onChange(String(v))} autosize={{ minRows: 3, maxRows: 8 }} />
      </Space>
    );
  }

  return (
    <Space direction="vertical" size={4} style={{ width: '100%' }}>
      <Typography.Text>
        {label} {required ? <Typography.Text theme="error">*</Typography.Text> : null}
      </Typography.Text>
      <Input value={value} onChange={(v) => onChange(String(v))} />
    </Space>
  );
}

function TaskTable({
  runs,
  workflowMap,
}: {
  runs: RunWithLatest[];
  workflowMap: Record<string, EvalWorkflowVersion>;
}) {
  return (
    <Card
      bordered
      title={
        <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
          <div>
            <Typography.Text strong>任务管理</Typography.Text>
            <div>
              <Typography.Text theme="secondary">
                实时刷新：queued/running 会持续轮询；ComfyUI 类回调出图后才算完成。
              </Typography.Text>
            </div>
          </div>
          <Typography.Text theme="secondary">最近 {runs.length} 条</Typography.Text>
        </Space>
      }
    >
      <Table
        size="small"
        rowKey="id"
        data={runs}
        empty={<Typography.Text theme="secondary">暂无任务。</Typography.Text>}
        columns={[
          {
            colKey: 'created_at',
            title: '时间',
            width: 180,
            cell: ({ row }) => <Typography.Text>{fmtTime(row.created_at)}</Typography.Text>,
          },
          {
            colKey: 'workflow',
            title: '工作流',
            minWidth: 240,
            cell: ({ row }) => {
              const wf = workflowMap[row.workflow_version_id];
              return (
                <Space direction="vertical" size={2}>
                  <Typography.Text strong>{wf ? wf.name : row.workflow_version_id}</Typography.Text>
                  <Typography.Text theme="secondary" style={{ fontSize: 12 }} ellipsis>
                    {wf?.workflow_id || '—'}
                  </Typography.Text>
                </Space>
              );
            },
          },
          {
            colKey: 'status',
            title: '状态',
            width: 150,
            cell: ({ row }) => (
              <Space direction="vertical" size={2}>
                <Tag variant="light">{row.status}</Tag>
                <Typography.Text theme="secondary" style={{ fontSize: 12 }}>
                  耗时：{formatDuration(row.duration_ms)}
                </Typography.Text>
              </Space>
            ),
          },
          {
            colKey: 'rating',
            title: '评分',
            width: 120,
            cell: ({ row }) =>
              row.latest_annotation?.rating ? (
                <Tag theme="warning" variant="light">
                  {row.latest_annotation.rating}
                </Tag>
              ) : (
                <Typography.Text theme="secondary">未评分</Typography.Text>
              ),
          },
          {
            colKey: 'output',
            title: '输出',
            minWidth: 220,
            cell: ({ row }) => {
              const outputs = filterImageUrls(row.result_image_urls_json);
              const jsonPreview = formatJsonPreview((row as any).result_output_json, 240);
              if (outputs.length > 0) {
                return (
                  <Space breakLine>
                    <Typography.Text theme="secondary">{outputs.length} 张</Typography.Text>
                    <Button size="small" variant="text" onClick={() => window.open(outputs[0], '_blank', 'noreferrer')}>
                      打开首张
                    </Button>
                  </Space>
                );
              }
              if (jsonPreview) {
                return (
                  <Typography.Text theme="secondary" style={{ fontFamily: 'monospace', fontSize: 12 }} ellipsis>
                    {jsonPreview}
                  </Typography.Text>
                );
              }
              return (
                <Typography.Text theme="secondary">
                  {row.status === 'running' || row.status === 'queued' ? '生成中…' : '暂无输出'}
                </Typography.Text>
              );
            },
          },
          {
            colKey: 'actions',
            title: '操作',
            width: 220,
            cell: ({ row }) => (
              <Space>
                {row.coze_debug_url ? (
                  <Button
                    size="small"
                    variant="outline"
                    onClick={() => window.open(row.coze_debug_url || '', '_blank', 'noreferrer')}
                  >
                    debug_url
                  </Button>
                ) : null}
                {row.error_message ? <Typography.Text theme="error">失败</Typography.Text> : null}
              </Space>
            ),
          },
        ]}
      />
    </Card>
  );
}

function ImageTile({
  url,
  title,
  onOpen,
}: {
  url: string;
  title: string;
  onOpen: () => void;
}) {
  const [loaded, setLoaded] = useState(false);
  const [failed, setFailed] = useState(false);
  return (
    <button
      type="button"
      onClick={onOpen}
      className="relative block rounded-2xl border border-slate-800 bg-slate-950/30 p-2 hover:border-slate-700"
    >
      {!loaded && !failed ? (
        <div className="absolute inset-2 rounded-xl border border-slate-800 bg-slate-950/60 flex items-center justify-center text-xs text-slate-400">
          加载中…
        </div>
      ) : null}
      {failed ? (
        <div className="absolute inset-2 rounded-xl border border-rose-500/30 bg-rose-500/5 flex flex-col items-center justify-center gap-2 text-xs text-rose-200 px-3">
          <div className="font-semibold">图片加载失败</div>
          <div className="break-all text-[10px] text-rose-300/80">{url}</div>
        </div>
      ) : null}
      <img
        src={url}
        alt={title}
        loading="lazy"
        onLoad={() => setLoaded(true)}
        onError={() => setFailed(true)}
        className="h-56 w-full rounded-xl object-contain"
      />
    </button>
  );
}

function SkeletonTile({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="relative block rounded-2xl border border-slate-800 bg-slate-950/30 p-2">
      <div className="h-56 w-full rounded-xl border border-slate-800 bg-slate-950/60 animate-pulse" />
      <div className="mt-2 px-1">
        <div className="text-xs font-semibold text-slate-200">{title}</div>
        {subtitle ? <div className="mt-1 text-[11px] text-slate-500 break-all">{subtitle}</div> : null}
      </div>
    </div>
  );
}

type ThemeMode = 'light' | 'dark';

function readTheme(): ThemeMode {
  const stored = window.localStorage.getItem('podi.eval.theme');
  return stored === 'dark' ? 'dark' : 'light';
}

export function App() {
  const [theme, setTheme] = useState<ThemeMode>(() => readTheme());
  useEffect(() => {
    const isDark = theme === 'dark';
    // TDesign dark mode is driven by `t-theme-dark` class.
    document.documentElement.classList.toggle('t-theme-dark', isDark);
    // Keep Tailwind dark variants working during migration.
    document.documentElement.classList.toggle('dark', isDark);
    window.localStorage.setItem('podi.eval.theme', theme);
  }, [theme]);

  const pushNotice = useCallback((type: 'error' | 'success' | 'info', message: string) => {
    const content = message || '未知错误';
    if (type === 'error') MessagePlugin.error({ content, duration: 5000 });
    else if (type === 'success') MessagePlugin.success({ content, duration: 3500 });
    else MessagePlugin.info({ content, duration: 3500 });
  }, []);

  const [raterId, setRaterId] = useState<string>('');
  const [workflows, setWorkflows] = useState<EvalWorkflowVersion[]>([]);
  const [metrics, setMetrics] = useState<Record<string, { ratingCount: number; avgRating: number | null }>>({});

  const [activeCategory, setActiveCategory] = useState<string>('通用类');
  const [activeView, setActiveView] = useState<'home' | 'tool' | 'tasks' | 'admin' | 'docs'>('home');
  const [selectedTool, setSelectedTool] = useState<EvalWorkflowVersion | null>(null);

  const [formUrl, setFormUrl] = useState('');
  const [formParams, setFormParams] = useState<Record<string, string>>({});
  const [isRunning, setIsRunning] = useState(false);
  const [uploading, setUploading] = useState(false);
  const uploadInputRef = useRef<HTMLInputElement | null>(null);

  // Keep tool run history and global task list separate.
  // Otherwise, in-flight requests from one view can overwrite the other's list.
  const [toolRuns, setToolRuns] = useState<RunWithLatest[]>([]);
  const [taskRuns, setTaskRuns] = useState<RunWithLatest[]>([]);
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [filterRating, setFilterRating] = useState<string>('all');
  const [filterUnrated, setFilterUnrated] = useState<boolean>(false);
  const [search, setSearch] = useState<string>('');
  const [lightbox, setLightbox] = useState<{ url: string; title?: string } | null>(null);

  // Simple "private" admin token stored in localStorage.
  const [adminToken, setAdminToken] = useState<string>(() => localStorage.getItem('podi_eval_admin_token') || '');
  const [adminWorkflows, setAdminWorkflows] = useState<EvalWorkflowVersion[]>([]);
  const [docsMarkdown, setDocsMarkdown] = useState<string>('');
  const [docsLoading, setDocsLoading] = useState<boolean>(false);
  const [docsGeneratedAt, setDocsGeneratedAt] = useState<string>('');
  const [docsWorkflows, setDocsWorkflows] = useState<WorkflowDoc[]>([]);
  const [docsView, setDocsView] = useState<'structured' | 'markdown'>('structured');

  const workflowMap = useMemo(() => {
    const m: Record<string, EvalWorkflowVersion> = {};
    for (const wf of workflows) m[wf.id] = wf;
    return m;
  }, [workflows]);

  const grouped = useMemo(() => {
    const m: Record<string, EvalWorkflowVersion[]> = {};
    for (const wf of workflows) {
      const key = normalizeCategory(wf.category);
      m[key] = m[key] || [];
      m[key].push(wf);
    }
    return m;
  }, [workflows]);

  const orderedCategories = useMemo(() => {
    // Always show the 4 business categories (fixed sidebar).
    return CATEGORY_ORDER.slice();
  }, [grouped]);

  const toolList = useMemo(() => {
    const list = (grouped[activeCategory] || []).slice().sort((a, b) => a.name.localeCompare(b.name));
    return list;
  }, [grouped, activeCategory]);

  const toolFields = useMemo(() => getFields(selectedTool), [selectedTool]);
  const requiresImage = useMemo(
    () => toolFields.some((f) => f.name === 'url' || f.name === 'Url'),
    [toolFields],
  );

  const refreshMetrics = async () => {
    const resp = await evalApi.workflowMetrics().catch(() => ({ metrics: {} }));
    setMetrics(resp.metrics || {});
  };

  const loadBootstrap = async () => {
    try {
      const me = await evalApi.me();
      setRaterId(me.raterId);
      const wfs = await evalApi.listWorkflowVersions();
      setWorkflows(wfs || []);
      if (wfs && wfs.length > 0) {
        const counts: Record<string, number> = {};
        for (const wf of wfs) {
          const k = normalizeCategory(wf.category);
          counts[k] = (counts[k] || 0) + 1;
        }
        const firstNonEmpty = CATEGORY_ORDER.find((k) => (counts[k] || 0) > 0);
        setActiveCategory(firstNonEmpty || '通用类');
      }
      await refreshMetrics();
    } catch (err) {
      console.error(err);
      pushNotice('error', String((err as any)?.message || err));
    }
  };

  const loadRunsForTool = async (workflowVersionId: string) => {
    try {
      const resp = await evalApi.listRunsWithLatestAnnotation({
        workflow_version_id: workflowVersionId,
        status: filterStatus !== 'all' ? filterStatus : undefined,
        unrated: filterUnrated,
        limit: 80,
        offset: 0,
      });
      setToolRuns((resp.items || []) as RunWithLatest[]);
    } catch (err) {
      console.error(err);
      pushNotice('error', String((err as any)?.message || err));
    }
  };

  const loadTasks = async () => {
    try {
      const resp = await evalApi.listRunsWithLatestAnnotation({ limit: 80, offset: 0 });
      setTaskRuns((resp.items || []) as RunWithLatest[]);
    } catch (err) {
      console.error(err);
      pushNotice('error', String((err as any)?.message || err));
    }
  };

  useEffect(() => {
    void loadBootstrap();
  }, []);

  useEffect(() => {
    if (activeView !== 'tool' || !selectedTool) return;
    void loadRunsForTool(selectedTool.id);
    const timer = window.setInterval(() => {
      const hasPending = toolRuns.some((r) => r.status === 'queued' || r.status === 'running');
      if (hasPending) void loadRunsForTool(selectedTool.id);
    }, 2000);
    return () => window.clearInterval(timer);
  }, [activeView, selectedTool?.id, filterStatus, filterUnrated, toolRuns]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (activeView !== 'tasks') return;
    void loadTasks();
    const timer = window.setInterval(() => void loadTasks(), 2000);
    return () => window.clearInterval(timer);
  }, [activeView]);

  useEffect(() => {
    if (activeView !== 'docs') return;
    setDocsLoading(true);
    void (async () => {
      try {
        const res = await evalApi.getWorkflowDocs();
        setDocsMarkdown(String(res.markdown || ''));
        setDocsGeneratedAt(String(res.generatedAt || ''));
        setDocsWorkflows(Array.isArray(res.workflows) ? res.workflows : []);
      } catch (err) {
        console.error(err);
        pushNotice('error', String((err as any)?.message || err));
      } finally {
        setDocsLoading(false);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeView]);

  const openTool = (wf: EvalWorkflowVersion) => {
    setSelectedTool(wf);
    setFormUrl('');
    // Prevent showing previous tool's results while the new tool's history is loading.
    setToolRuns([]);
    setFilterStatus('all');
    setFilterRating('all');
    setFilterUnrated(false);
    setSearch('');
    const defaults: Record<string, string> = {};
    for (const f of getFields(wf)) {
      if (f.name === 'url') continue;
      const opt = Array.isArray((f as any).options) && (f as any).options.length > 0 ? (f as any).options[0]?.value : undefined;
      const def = typeof (f as any).defaultValue === 'string' ? (f as any).defaultValue : undefined;
      if (def !== undefined) {
        defaults[f.name] = String(def);
      } else if (opt !== undefined) {
        defaults[f.name] = String(opt);
      } else {
        defaults[f.name] = '';
      }
    }
    setFormParams(defaults);
    setActiveView('tool');
  };

  const groupedDocs = useMemo(() => {
    const map = new Map<string, WorkflowDoc[]>();
    for (const wf of docsWorkflows) {
      const cat = normalizeCategory(wf.category);
      if (!map.has(cat)) map.set(cat, []);
      map.get(cat)!.push(wf);
    }
    const ordered: { category: string; items: WorkflowDoc[] }[] = [];
    for (const cat of CATEGORY_ORDER) {
      if (map.has(cat)) ordered.push({ category: cat, items: map.get(cat)! });
    }
    for (const [cat, items] of map.entries()) {
      if (!ordered.some((entry) => entry.category === cat)) {
        ordered.push({ category: cat, items });
      }
    }
    for (const entry of ordered) {
      entry.items.sort((a, b) => String(a.name).localeCompare(String(b.name)));
    }
    return ordered;
  }, [docsWorkflows]);

  const toAnchorId = (value: string) => `doc-cat-${String(value).replace(/\s+/g, '-')}`;

  const runTool = async () => {
    if (isRunning) return;
    if (!selectedTool) return;
    const url = formUrl.trim();
    const requiresImage = toolFields.some((f) => f.name === 'url' || f.name === 'Url');
    if (requiresImage && !url) {
      pushNotice('error', '请先填写或上传图片 URL');
      return;
    }

    // Validate required fields in schema (except `prompt`: backend will fallback to " ").
    const missing: string[] = [];
    for (const f of getFields(selectedTool)) {
      if (!(f as any)?.required) continue;
      if (f.name === 'url' || f.name === 'Url' || f.name === 'prompt') continue;
      const v = String((formParams as any)?.[f.name] ?? '').trim();
      if (!v) missing.push((f as any).label || f.name);
    }
    if (missing.length > 0) {
      pushNotice('error', `请补齐必填参数：${missing.join('、')}`);
      return;
    }

    setIsRunning(true);
    try {
      const normalizeNumericParam = (key: string, value: string): string => {
        const pixelKeys = new Set([
          'width',
          'height',
          'expand_left',
          'expand_right',
          'expand_top',
          'expand_bottom',
          'expandLeft',
          'expandRight',
          'expandTop',
          'expandBottom',
          'left',
          'right',
          'top',
          'bottom',
          'bianchang',
        ]);
        if (!pixelKeys.has(key)) return value;
        const raw = String(value || '').trim();
        if (!raw) return raw;
        let num = '';
        for (const ch of raw) {
          if (ch >= '0' && ch <= '9') {
            num += ch;
          } else if (num) {
            break;
          }
        }
        return num || raw;
      };

      const parameters: Record<string, unknown> = {};
      if (requiresImage && url) {
        parameters.url = url;
      }
      for (const [k, v] of Object.entries(formParams)) {
        if (v === '') continue;
        if (typeof v === 'string') {
          parameters[k] = normalizeNumericParam(k, v);
        } else {
          parameters[k] = v;
        }
      }
      await evalApi.createRun({
        workflow_version_id: selectedTool.id,
        input_oss_urls_json: requiresImage && url ? [url] : [],
        parameters_json: parameters,
      });
      await loadRunsForTool(selectedTool.id);
      await refreshMetrics();
      pushNotice('success', '已提交运行，稍后会自动刷新结果');
    } catch (err) {
      console.error(err);
      pushNotice('error', String((err as any)?.message || err));
    } finally {
      setIsRunning(false);
    }
  };

  const annotate = async (runId: string, rating: number, comment: string) => {
    try {
      await evalApi.createAnnotation(runId, { rating, comment: comment.trim() || undefined });
      await refreshMetrics();
      if (selectedTool) await loadRunsForTool(selectedTool.id);
      pushNotice('success', '已保存评分/备注');
    } catch (err) {
      console.error(err);
      pushNotice('error', String((err as any)?.message || err));
    }
  };

  const filteredRuns = useMemo(() => {
    let out = toolRuns.slice();
    if (filterRating !== 'all') {
      const target = Number(filterRating);
      out = out.filter((r) => r.latest_annotation?.rating === target);
    }
    const keyword = search.trim().toLowerCase();
    if (keyword) {
      out = out.filter((r) => {
        const comment = (r.latest_annotation?.comment || '').toLowerCase();
        const err = (r.error_message || '').toLowerCase();
        return comment.includes(keyword) || err.includes(keyword);
      });
    }
    return out;
  }, [toolRuns, filterRating, search]);

  const promptAdminToken = useCallback(
    async (opts?: { force?: boolean }) => {
      const force = Boolean(opts?.force);
      const tokenInput =
        (!force && adminToken) || window.prompt('请输入 EVAL_ADMIN_TOKEN（仅管理员维护功能名/备注）') || '';
      if (!tokenInput.trim()) return;
      const token = tokenInput.trim();
      localStorage.setItem('podi_eval_admin_token', token);
      setAdminToken(token);
      setActiveView('admin');
      setSelectedTool(null);
      try {
        const list = await evalApi.adminListWorkflowVersions(token);
        setAdminWorkflows(list);
        pushNotice('success', '已加载维护列表');
      } catch (err) {
        console.error(err);
        pushNotice('error', String((err as any)?.message || err));
      }
    },
    [adminToken, pushNotice],
  );

  const openAdmin = useCallback(async () => {
    void promptAdminToken();
  }, [promptAdminToken]);

  const headerNavValue = activeView === 'tool' ? 'home' : activeView;

  const header = (
    <Layout.Header
      style={{
        borderBottom: '1px solid var(--td-component-border)',
        background: 'var(--td-bg-color-container)',
        padding: '0 24px',
      }}
    >
      <Space align="center" style={{ justifyContent: 'space-between', width: '100%', height: '100%' }}>
        <Space direction="vertical" size={2}>
          <Typography.Text strong>PODI · 能力评测</Typography.Text>
          <Typography.Text theme="secondary">工具箱式评测 · 免登录 · 评分沉淀</Typography.Text>
        </Space>
        <Space align="center">
          <Tabs
            value={headerNavValue}
            onChange={(v) => {
              const next = String(v) as any;
              if (next === 'admin') {
                void openAdmin();
                return;
              }
              setActiveView(next);
              setSelectedTool(null);
            }}
          >
            <Tabs.TabPanel value="home" label="工具箱" />
            <Tabs.TabPanel value="tasks" label="任务管理" />
            <Tabs.TabPanel value="docs" label="文档" />
            <Tabs.TabPanel value="admin" label="维护" />
          </Tabs>
          <Button variant="outline" onClick={() => setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'))}>
            {theme === 'dark' ? '深色' : '浅色'}
          </Button>
          <Typography.Text theme="secondary">
            raterId:{' '}
            <span style={{ fontFamily: 'monospace' }}>{raterId || '...'}</span>
          </Typography.Text>
        </Space>
      </Space>
    </Layout.Header>
  );

  const shell = (content: ReactNode) => (
    <ConfigProvider globalConfig={zhCN}>
      <Layout style={{ height: '100vh' }}>
        {header}
        <Layout>
          <Layout.Aside
            style={{
              width: 260,
              borderRight: '1px solid var(--td-component-border)',
              background: 'var(--td-bg-color-container)',
              padding: 16,
              overflow: 'auto',
            }}
          >
            <Space direction="vertical" size="small" style={{ width: '100%' }}>
              <div>
                <Typography.Text theme="secondary">导航</Typography.Text>
                <Typography.Title level="h5" style={{ margin: '6px 0 0' }}>
                  测试大类
                </Typography.Title>
                <Typography.Text theme="secondary">选择分类后，右侧展示对应能力卡片。</Typography.Text>
              </div>
              <Menu
                value={activeCategory}
                theme={theme === 'dark' ? 'dark' : 'light'}
                onChange={(value: string | number) => {
                  const next = String(value);
                  setActiveCategory(next);
                  // Categories are the primary navigation for the toolbox.
                  setSelectedTool(null);
                  setActiveView('home');
                }}
              >
                {CATEGORY_ORDER.map((cat) => (
                  <Menu.MenuItem key={cat} value={cat}>
                    <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
                      <span>{cat}</span>
                      <Typography.Text theme="secondary">{(grouped[cat] || []).length}</Typography.Text>
                    </Space>
                  </Menu.MenuItem>
                  ))}
                </Menu>
            </Space>
          </Layout.Aside>
          <Layout.Content style={{ padding: 24, background: 'var(--td-bg-color-page)', overflow: 'auto' }}>
            <div style={{ maxWidth: 1400, margin: '0 auto' }}>{content}</div>
          </Layout.Content>
        </Layout>
      </Layout>
      <Lightbox url={lightbox?.url || ''} title={lightbox?.title} onClose={() => setLightbox(null)} />
    </ConfigProvider>
  );

  if (activeView === 'admin') {
    return shell(
      <Card
        bordered
        title={
          <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
            <div>
              <Typography.Text strong>功能维护</Typography.Text>
              <div>
                <Typography.Text theme="secondary">
                  维护各功能的名称/备注/分类/状态（需要 `EVAL_ADMIN_TOKEN`）。
                </Typography.Text>
              </div>
            </div>
            <Button
              variant="outline"
              disabled={!adminToken}
              onClick={async () => {
                if (!adminToken) return;
                try {
                  const list = await evalApi.adminListWorkflowVersions(adminToken);
                  setAdminWorkflows(list);
                  pushNotice('success', '已刷新列表');
                } catch (err) {
                  console.error(err);
                  pushNotice('error', String((err as any)?.message || err));
                }
              }}
            >
              刷新列表
            </Button>
            <Button
              variant="outline"
              onClick={() => {
                void promptAdminToken({ force: true });
              }}
            >
              重新输入 Token
            </Button>
          </Space>
        }
      >
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          {adminWorkflows.map((wf) => (
            <AdminWorkflowRow
              key={wf.id}
              wf={wf}
              adminToken={adminToken}
              onAuthInvalid={() => {
                localStorage.removeItem('podi_eval_admin_token');
                setAdminToken('');
                pushNotice('error', '认证已失效，请重新输入 EVAL_ADMIN_TOKEN');
              }}
              onSaved={(next) => {
                setAdminWorkflows((prev) => prev.map((x) => (x.id === next.id ? next : x)));
              }}
            />
          ))}
          {adminWorkflows.length === 0 ? <Typography.Text theme="secondary">暂无数据。</Typography.Text> : null}
        </Space>
      </Card>,
    );
  }

  if (activeView === 'docs') {

    const paramColumns = [
      {
        colKey: 'name',
        title: '字段',
        cell: ({ row }: { row: SchemaField }) => (
          <Space direction="vertical" size={2}>
            <Typography.Text code>{row.name}</Typography.Text>
            {row.label ? (
              <Typography.Text theme="secondary" style={{ fontSize: 12 }}>
                {row.label}
              </Typography.Text>
            ) : null}
          </Space>
        ),
      },
      {
        colKey: 'required',
        title: '必填',
        width: 70,
        cell: ({ row }: { row: SchemaField }) => (row.required ? '是' : '否'),
      },
      {
        colKey: 'type',
        title: '类型',
        width: 110,
        cell: ({ row }: { row: SchemaField }) => <Typography.Text code>{row.type || 'text'}</Typography.Text>,
      },
      {
        colKey: 'defaultValue',
        title: '默认值',
        width: 140,
        cell: ({ row }: { row: SchemaField }) => (row.defaultValue ? String(row.defaultValue) : '—'),
      },
      {
        colKey: 'options',
        title: '枚举值',
        cell: ({ row }: { row: SchemaField }) => renderOptionTags(row.options),
      },
      {
        colKey: 'description',
        title: '说明',
        cell: ({ row }: { row: SchemaField }) => (row.description ? row.description : '—'),
      },
    ];

    const outputColumns = [
      {
        colKey: 'name',
        title: '字段',
        cell: ({ row }: { row: SchemaField }) => (
          <Space direction="vertical" size={2}>
            <Typography.Text code>{row.name}</Typography.Text>
            {row.label ? (
              <Typography.Text theme="secondary" style={{ fontSize: 12 }}>
                {row.label}
              </Typography.Text>
            ) : null}
          </Space>
        ),
      },
      {
        colKey: 'type',
        title: '类型',
        width: 110,
        cell: ({ row }: { row: SchemaField }) => <Typography.Text code>{row.type || 'text'}</Typography.Text>,
      },
      {
        colKey: 'description',
        title: '说明',
        cell: ({ row }: { row: SchemaField }) => (row.description ? row.description : '—'),
      },
    ];

    return shell(
      <Card
        bordered
        title={
          <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
            <div>
              <Typography.Text strong>开发文档 · Coze 工作流</Typography.Text>
              <div>
                <Typography.Text theme="secondary">
                  从后端自动生成（active 工作流 + 入参/出参 schema）。{docsGeneratedAt ? `生成时间：${docsGeneratedAt}` : ''}
                </Typography.Text>
              </div>
            </div>
            <Space align="center">
              <Button
                variant={docsView === 'structured' ? 'base' : 'outline'}
                onClick={() => setDocsView('structured')}
              >
                结构化
              </Button>
              <Button variant={docsView === 'markdown' ? 'base' : 'outline'} onClick={() => setDocsView('markdown')}>
                Markdown
              </Button>
              <Button
                variant="outline"
                onClick={async () => {
                  try {
                    await navigator.clipboard.writeText(docsMarkdown || '');
                    pushNotice('success', '已复制到剪贴板');
                  } catch (err) {
                    console.error(err);
                    pushNotice('error', '复制失败（浏览器不支持或权限不足）');
                  }
                }}
              >
                复制全文
              </Button>
            </Space>
          </Space>
        }
      >
        {docsLoading ? (
          <Typography.Text theme="secondary">加载中…</Typography.Text>
        ) : docsView === 'structured' && groupedDocs.length > 0 ? (
          <Space direction="vertical" size="large" style={{ width: '100%' }}>
            <Card bordered>
              <Space direction="vertical" size={6} style={{ width: '100%' }}>
                <Typography.Text strong>目录</Typography.Text>
                <Space style={{ flexWrap: 'wrap' }}>
                  {groupedDocs.map((group) => (
                    <a
                      key={group.category}
                      href={`#${toAnchorId(group.category)}`}
                      style={{ color: 'var(--td-text-color-primary)' }}
                    >
                      {group.category}（{group.items.length}）
                    </a>
                  ))}
                </Space>
              </Space>
            </Card>

            {groupedDocs.map((group) => (
              <Space key={group.category} direction="vertical" size="large" style={{ width: '100%' }}>
                <div id={toAnchorId(group.category)}>
                  <Typography.Title level="h3" style={{ margin: 0 }}>
                    {group.category}
                  </Typography.Title>
                </div>

                {group.items.map((wf) => {
              const params = Array.isArray(wf.parameters) ? wf.parameters : [];
              const outputs = Array.isArray(wf.outputs) ? wf.outputs : [];
              const requestBody =
                wf.request?.body ?? {
                  workflow_id: wf.workflow_id,
                  parameters: {},
                };
              const requestJson = JSON.stringify(requestBody, null, 2);
              const requestPath = wf.request?.path || '/v1/workflow/run';
              const requestMethod = wf.request?.method || 'POST';

                  return (
                    <Card key={wf.workflow_id} bordered>
                  <Space direction="vertical" size="medium" style={{ width: '100%' }}>
                    <Space align="center" style={{ flexWrap: 'wrap' }}>
                      <Typography.Title level="h4" style={{ margin: 0 }}>
                        {wf.name}
                      </Typography.Title>
                      <Tag variant="light">输出类型: {wf.output_kind || 'image_url'}</Tag>
                    </Space>
                    <Typography.Text theme="secondary">workflow_id: {wf.workflow_id}</Typography.Text>
                    {wf.notes ? <Typography.Text>备注：{wf.notes}</Typography.Text> : null}

                    <Space direction="vertical" size={4}>
                      <Typography.Text strong>调用方式</Typography.Text>
                      <Typography.Text theme="secondary">
                        {requestMethod} {requestPath}
                      </Typography.Text>
                      <pre
                        style={{
                          border: '1px solid var(--td-border-level-1-color)',
                          background: 'var(--td-bg-color-secondarycontainer)',
                          borderRadius: 8,
                          padding: 12,
                          fontFamily: 'monospace',
                          fontSize: 12,
                          whiteSpace: 'pre-wrap',
                          margin: 0,
                        }}
                      >
                        {requestJson}
                      </pre>
                    </Space>

                    <Space direction="vertical" size={4}>
                      <Typography.Text strong>入参 parameters</Typography.Text>
                      {params.length > 0 ? (
                        <Table rowKey="name" data={params} columns={paramColumns} size="small" bordered />
                      ) : (
                        <Typography.Text theme="secondary">无参数</Typography.Text>
                      )}
                    </Space>

                    <Space direction="vertical" size={4}>
                      <Typography.Text strong>出参 data</Typography.Text>
                      {outputs.length > 0 ? (
                        <Table rowKey="name" data={outputs} columns={outputColumns} size="small" bordered />
                      ) : (
                        <Typography.Text theme="secondary">默认关注 data.output（图片 URL 或回调 task id）</Typography.Text>
                      )}
                    </Space>
                  </Space>
                    </Card>
                  );
                })}
              </Space>
            ))}
          </Space>
        ) : docsMarkdown ? (
          <div
            style={{
              maxHeight: '70vh',
              overflow: 'auto',
              border: '1px solid var(--td-border-level-1-color)',
              background: 'var(--td-bg-color-secondarycontainer)',
              borderRadius: 8,
              padding: 12,
            }}
          >
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                h1: ({ children }) => <Typography.Title level="h3">{children}</Typography.Title>,
                h2: ({ children }) => <Typography.Title level="h4">{children}</Typography.Title>,
                h3: ({ children }) => <Typography.Title level="h5">{children}</Typography.Title>,
                p: ({ children }) => <Typography.Paragraph>{children}</Typography.Paragraph>,
                code: ({ children }) => (
                  <code style={{ background: 'var(--td-bg-color-secondarycontainer)', padding: '0 4px', borderRadius: 4 }}>
                    {children}
                  </code>
                ),
                pre: ({ children }) => (
                  <pre
                    style={{
                      background: 'var(--td-bg-color-secondarycontainer)',
                      padding: 12,
                      borderRadius: 8,
                      overflow: 'auto',
                      fontSize: 12,
                    }}
                  >
                    {children}
                  </pre>
                ),
                table: ({ children }) => (
                  <table style={{ width: '100%', borderCollapse: 'collapse', marginBottom: 12 }}>{children}</table>
                ),
                th: ({ children }) => (
                  <th style={{ border: '1px solid var(--td-border-level-1-color)', padding: 6, textAlign: 'left' }}>
                    {children}
                  </th>
                ),
                td: ({ children }) => (
                  <td style={{ border: '1px solid var(--td-border-level-1-color)', padding: 6 }}>{children}</td>
                ),
                ul: ({ children }) => <ul style={{ paddingLeft: 20 }}>{children}</ul>,
                ol: ({ children }) => <ol style={{ paddingLeft: 20 }}>{children}</ol>,
              }}
            >
              {docsMarkdown}
            </ReactMarkdown>
          </div>
        ) : (
          <Typography.Text theme="secondary">暂无文档内容。</Typography.Text>
        )}
      </Card>,
    );
  }

  if (activeView === 'tasks') {
    return shell(<TaskTable runs={taskRuns} workflowMap={workflowMap} />);
  }

  if (activeView === 'tool' && selectedTool) {
    const metric = metrics[selectedTool.id];
    const doc = buildCozeDoc(selectedTool, formUrl.trim());
    return shell(
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
          <Button
            variant="outline"
            onClick={() => {
              setActiveView('home');
              setSelectedTool(null);
            }}
          >
            返回功能列表
          </Button>
          <Typography.Text theme="secondary" style={{ fontFamily: 'monospace' }}>
            workflow_id: {selectedTool.workflow_id}
          </Typography.Text>
        </Space>

        <Card bordered>
          <Space align="start" style={{ justifyContent: 'space-between', width: '100%' }}>
            <Space direction="vertical" size={4} style={{ minWidth: 0 }}>
              <Typography.Title level="h4" style={{ margin: 0 }}>
                {selectedTool.name}
              </Typography.Title>
              <Typography.Text theme="secondary">{selectedTool.notes || '—'}</Typography.Text>
              <Space breakLine>
                <Tag variant="light">{normalizeCategory(selectedTool.category)}</Tag>
                <Tag variant="light">{selectedTool.version}</Tag>
                {metric?.avgRating ? (
                  <Tag theme="warning" variant="light">
                    综合评分：{metric.avgRating.toFixed(2)} / 5（{metric.ratingCount}票）
                  </Tag>
                ) : (
                  <Tag variant="light">综合评分：暂无</Tag>
                )}
              </Space>
            </Space>
          </Space>
        </Card>

        <Row gutter={[12, 12]}>
          {/* TDesign Grid uses a 12-column system; keep spans within 12 to avoid wrapping/empty gaps. */}
          <Col xs={12} xl={5}>
            <Card bordered title="测试参数">
              <Space direction="vertical" size="large" style={{ width: '100%' }}>
                {requiresImage ? (
                  <>
                    <Space direction="vertical" size={4} style={{ width: '100%' }}>
                      <Typography.Text>
                        图片 URL <Typography.Text theme="error">*</Typography.Text>
                      </Typography.Text>
                      <Space align="center" style={{ width: '100%' }}>
                        <div style={{ flex: 1 }}>
                          <Input
                            value={formUrl}
                            onChange={(v) => setFormUrl(String(v))}
                            placeholder="支持粘贴 URL 或上传本地图片"
                            clearable
                          />
                        </div>
                        <Button variant="outline" loading={uploading} onClick={() => uploadInputRef.current?.click()}>
                          上传
                        </Button>
                        <input
                          ref={uploadInputRef}
                          type="file"
                          accept="image/*"
                          style={{ display: 'none' }}
                          disabled={uploading}
                          onChange={async (e) => {
                            const file = e.target.files?.[0];
                            if (!file) return;
                            setUploading(true);
                            try {
                              const res = await evalApi.uploadImage(file);
                              setFormUrl(res.url);
                            } catch (err) {
                              console.error(err);
                              pushNotice('error', String((err as any)?.message || err));
                            } finally {
                              setUploading(false);
                              e.target.value = '';
                            }
                          }}
                        />
                      </Space>
                    </Space>

                    {formUrl.trim() ? (
                      <Card bordered title="原图预览">
                        <img
                          src={formUrl.trim()}
                          alt="input"
                          style={{ height: 240, width: '100%', objectFit: 'contain', cursor: 'pointer' }}
                          onClick={() => setLightbox({ url: formUrl.trim(), title: '原图' })}
                        />
                      </Card>
                    ) : null}
                  </>
                ) : null}

                <Space direction="vertical" size="large" style={{ width: '100%' }}>
                  {toolFields
                    .filter((f) => f.name !== 'url' && f.name !== 'Url')
                    .map((f) => (
                      <ParamField
                        key={f.name}
                        field={f}
                        value={formParams[f.name] ?? ''}
                        onChange={(v) => setFormParams((p) => ({ ...p, [f.name]: v }))}
                      />
                    ))}
                </Space>

                <Space style={{ justifyContent: 'flex-end', width: '100%' }}>
                  <Button
                    theme="primary"
                    loading={isRunning}
                    disabled={isRunning || (requiresImage ? !formUrl.trim() : false)}
                    onClick={() => void runTool()}
                  >
                    开始生成
                  </Button>
                </Space>

                <Card
                  bordered
                  title={
                    <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
                      <Typography.Text strong>业务接入文档（Coze OpenAPI）</Typography.Text>
                      <Button
                        size="small"
                        variant="outline"
                        onClick={async () => {
                          try {
                            await navigator.clipboard.writeText(doc);
                            pushNotice('success', '已复制到剪贴板');
                          } catch {
                            pushNotice('error', '复制失败（浏览器不支持或权限不足）');
                          }
                        }}
                      >
                        复制
                      </Button>
                    </Space>
                  }
                >
                  <pre
                    style={{
                      maxHeight: 240,
                      overflow: 'auto',
                      border: '1px solid var(--td-border-level-1-color)',
                      background: 'var(--td-bg-color-secondarycontainer)',
                      borderRadius: 8,
                      padding: 12,
                      fontFamily: 'monospace',
                      fontSize: 12,
                      whiteSpace: 'pre',
                    }}
                  >
                    {doc}
                  </pre>
                </Card>
              </Space>
            </Card>
          </Col>

          <Col xs={12} xl={7}>
            <Card bordered title="生成结果">
              <Space direction="vertical" size="large" style={{ width: '100%' }}>
                <Typography.Text theme="secondary">点击图片可放大预览；下方历史可筛选/打标。</Typography.Text>
                {(() => {
                  const latest = toolRuns[0] || null;
                  const status = String(latest?.status || '');
                  const statusTheme = status === 'failed' ? 'danger' : status === 'succeeded' ? 'success' : 'warning';
                  const rawCount = Number((latest?.parameters_json as any)?.count);
                  const expectedCount =
                    Number.isFinite(rawCount) && rawCount > 1 ? Math.min(Math.max(rawCount, 2), 12) : latest ? 1 : 0;
                  const imgs = latest ? filterImageUrls(latest.result_image_urls_json) : [];
                  const remain = latest ? Math.max(0, expectedCount - imgs.length) : 0;

                  return (
                    <Space direction="vertical" size="large" style={{ width: '100%' }}>
                      <Card bordered title="当前运行状态">
                        {!latest ? (
                          <Space direction="vertical" size="small" style={{ width: '100%' }}>
                            <Alert theme="info" message="暂无记录（先在左侧运行一次）。" />
                            <Typography.Text theme="secondary">
                              提示：多数工作流 50~80s 出图；如长时间无输出，可点右上 debug_url 排查。
                            </Typography.Text>
                          </Space>
                        ) : (
                          <Row gutter={[12, 12]}>
                            <Col xs={12} md={4}>
                              <Space direction="vertical" size={2}>
                                <Typography.Text theme="secondary">状态</Typography.Text>
                                <Tag theme={statusTheme as any} variant="light">
                                  {status || '—'}
                                </Tag>
                              </Space>
                            </Col>
                            <Col xs={12} md={4}>
                              <Space direction="vertical" size={2}>
                                <Typography.Text theme="secondary">run</Typography.Text>
                                <Typography.Text style={{ fontFamily: 'monospace' }} ellipsis>
                                  {latest.id}
                                </Typography.Text>
                              </Space>
                            </Col>
                            <Col xs={12} md={4}>
                              <Space direction="vertical" size={2}>
                                <Typography.Text theme="secondary">预期出图</Typography.Text>
                                <Typography.Text>{expectedCount || '—'}</Typography.Text>
                              </Space>
                            </Col>
                            <Col xs={12} md={4}>
                              <Space direction="vertical" size={2}>
                                <Typography.Text theme="secondary">已完成</Typography.Text>
                                <Typography.Text>{imgs.length}</Typography.Text>
                              </Space>
                            </Col>
                            <Col xs={12} md={4}>
                              <Space direction="vertical" size={2}>
                                <Typography.Text theme="secondary">创建时间</Typography.Text>
                                <Typography.Text>{fmtTime(latest.created_at)}</Typography.Text>
                              </Space>
                            </Col>
                            <Col xs={12} md={4}>
                              <Space direction="vertical" size={2}>
                                <Typography.Text theme="secondary">操作</Typography.Text>
                                <Space>
                                  {latest.coze_debug_url ? (
                                    <Button
                                      size="small"
                                      variant="outline"
                                      onClick={() => window.open(latest.coze_debug_url!, '_blank', 'noreferrer')}
                                    >
                                      debug_url
                                    </Button>
                                  ) : null}
                                  {latest.error_message ? (
                                    <Button
                                      size="small"
                                      variant="outline"
                                      theme="danger"
                                      onClick={() => pushNotice('error', latest.error_message || '生成失败')}
                                    >
                                      查看错误
                                    </Button>
                                  ) : null}
                                </Space>
                              </Space>
                            </Col>
                            {latest.error_message ? (
                              <Col span={12}>
                                <Alert theme="error" message={latest.error_message} />
                              </Col>
                            ) : null}
                          </Row>
                        )}
                      </Card>

                      <div className="grid gap-3 lg:grid-cols-3">
                        {!latest ? (
                          <Card bordered title="输出">
                            <Typography.Text theme="secondary">
                              暂无运行记录，先在左侧填写参数并点击“开始生成”。
                            </Typography.Text>
                          </Card>
                        ) : status === 'queued' || status === 'running' ? (
                          <>
                            {imgs.map((img, idx) => (
                              <ImageTile
                                key={`latest-${latest.id}-${idx}`}
                                url={img}
                                title={`最新结果 #${idx + 1}`}
                                onOpen={() => setLightbox({ url: img, title: `最新结果 #${idx + 1}` })}
                              />
                            ))}
                            {Array.from({ length: remain }).map((_, idx) => (
                              <SkeletonTile
                                key={`sk-${latest.id}-${idx}`}
                                title={`生成中… #${imgs.length + idx + 1}`}
                                subtitle={`run: ${latest.id}`}
                              />
                            ))}
                          </>
                        ) : status === 'failed' ? (
                          <Alert theme="error" message={`生成失败（run: ${latest.id}）：${latest.error_message || '—'}`} />
                        ) : imgs.length === 0 ? (
                          <Card bordered title="输出">
                            {(() => {
                              const jsonPreview = formatJsonPreview((latest as any).result_output_json, 2400);
                              return jsonPreview ? (
                                <pre
                                  style={{
                                    maxHeight: 420,
                                    overflow: 'auto',
                                    border: '1px solid var(--td-border-level-1-color)',
                                    background: 'var(--td-bg-color-secondarycontainer)',
                                    borderRadius: 8,
                                    padding: 12,
                                    fontFamily: 'monospace',
                                    fontSize: 12,
                                    whiteSpace: 'pre-wrap',
                                  }}
                                >
                                  {jsonPreview}
                                </pre>
                              ) : (
                                <Typography.Text theme="secondary">该次运行无图片输出。</Typography.Text>
                              );
                            })()}
                          </Card>
                        ) : (
                          imgs.map((img, idx) => (
                            <ImageTile
                              key={`latest-${idx}`}
                              url={img}
                              title={`最新结果 #${idx + 1}`}
                              onOpen={() => setLightbox({ url: img, title: `最新结果 #${idx + 1}` })}
                            />
                          ))
                        )}
                      </div>
                    </Space>
                  );
                })()}
              </Space>
            </Card>
          </Col>
        </Row>

        <Card
          bordered
          title={
            <div className="podi-card-titlebar">
              <div className="podi-card-titlebar__left">
                <Typography.Text strong>历史记录（打标区）</Typography.Text>
                <div>
                  <Typography.Text theme="secondary">每条记录包含原图 + 结果图；支持筛选与备注。</Typography.Text>
                </div>
              </div>
              <div className="podi-card-titlebar__right">
                <Select
                  value={filterStatus}
                  onChange={(v) => setFilterStatus(String(v))}
                  style={{ width: 140 }}
                  options={[
                    { label: '全部状态', value: 'all' },
                    { label: 'queued', value: 'queued' },
                    { label: 'running', value: 'running' },
                    { label: 'succeeded', value: 'succeeded' },
                    { label: 'failed', value: 'failed' },
                  ]}
                />
                <Select
                  value={filterRating}
                  onChange={(v) => setFilterRating(String(v))}
                  style={{ width: 140 }}
                  options={[
                    { label: '全部评分', value: 'all' },
                    ...[1, 2, 3, 4, 5].map((n) => ({ label: String(n), value: String(n) })),
                  ]}
                />
                <div className="podi-inline">
                  <Switch value={filterUnrated} onChange={(v) => setFilterUnrated(Boolean(v))} />
                  <Typography.Text theme="secondary">未打分</Typography.Text>
                </div>
                <Input
                  value={search}
                  onChange={(v) => setSearch(String(v))}
                  style={{ width: 240 }}
                  placeholder="搜索备注/错误…"
                  clearable
                />
              </div>
            </div>
          }
        >
          <Space direction="vertical" size="large" style={{ width: '100%' }}>
            {filteredRuns.map((run) => (
              <HistoryRow
                key={run.id}
                run={run}
                onAnnotate={annotate}
                onOpenImage={(url, title) => setLightbox({ url, title })}
              />
            ))}
            {filteredRuns.length === 0 ? <Typography.Text theme="secondary">暂无记录。</Typography.Text> : null}
          </Space>
        </Card>
      </Space>,
    );
  }

  // Home (toolbox) view
  return shell(
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <div>
        <Typography.Title level="h4" style={{ margin: 0 }}>
          {normalizeCategory(activeCategory)}
        </Typography.Title>
        <Typography.Text theme="secondary">
          点击卡片进入该功能的评测页面（左侧测试，右侧出图，底部打标）。
        </Typography.Text>
      </div>
      {toolList.length === 0 ? <Alert theme="info" message="该分类暂无功能。" /> : null}
      <div className="podi-tool-grid">
        {toolList.map((wf) => (
          <ToolCard key={wf.id} wf={wf} active={false} metric={metrics[wf.id]} onClick={() => openTool(wf)} />
        ))}
      </div>
    </Space>
  );
}

function HistoryRow({
  run,
  onAnnotate,
  onOpenImage,
}: {
  run: RunWithLatest;
  onAnnotate: (runId: string, rating: number, comment: string) => Promise<void>;
  onOpenImage: (url: string, title?: string) => void;
}) {
  const inputUrl = (run.input_oss_urls_json || [])[0] || '';
  const outputs = filterImageUrls(run.result_image_urls_json);
  const [rating, setRating] = useState<number>(run.latest_annotation?.rating || 0);
  const [savedComment, setSavedComment] = useState<string>(String(run.latest_annotation?.comment || ''));
  const [commentDraft, setCommentDraft] = useState<string>(String(run.latest_annotation?.comment || ''));
  const [savingRating, setSavingRating] = useState(false);
  const [savingComment, setSavingComment] = useState(false);
  const [lastSavedAt, setLastSavedAt] = useState<string>('');
  const [rowError, setRowError] = useState<string>('');

  const commentDirty = commentDraft !== savedComment;
  const jsonPreview = formatJsonPreview((run as any).result_output_json, 1200);
  const displayParams = filterDisplayParams(run.parameters_json as Record<string, unknown> | null);
  const paramsPreview = formatJsonPreview(displayParams, 1000);

  // Sync state when the latest annotation changes due to refresh/polling.
  // Do not clobber an in-progress comment draft.
  useEffect(() => {
    const nextRating = run.latest_annotation?.rating || 0;
    const nextComment = String(run.latest_annotation?.comment || '');
    setRating(nextRating);
    setSavedComment(nextComment);
    setCommentDraft((prev) => (prev === savedComment ? nextComment : prev));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [run.latest_annotation?.created_at]);

  return (
    <Card bordered>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <div className="podi-history-row-head">
          <div className="podi-history-row-head__meta">
            <Typography.Text strong style={{ fontFamily: 'monospace' }} ellipsis>
              run: {run.id}
            </Typography.Text>
            <div className="podi-history-row-head__meta-line">
              <Tag size="small" variant="light">
                {run.status}
              </Tag>
              <Typography.Text theme="secondary">耗时：{formatDuration(run.duration_ms)}</Typography.Text>
              <Typography.Text theme="secondary">{fmtTime(run.created_at)}</Typography.Text>
              {run.podi_task_id ? (
                <Typography.Text theme="secondary" style={{ fontFamily: 'monospace' }} ellipsis>
                  task: {run.podi_task_id}
                </Typography.Text>
              ) : null}
              {run.coze_debug_url ? (
                <Button
                  size="small"
                  variant="text"
                  onClick={() => window.open(run.coze_debug_url || '', '_blank', 'noreferrer')}
                >
                  debug_url
                </Button>
              ) : null}
            </div>
            {run.error_message ? <Alert theme="error" message={run.error_message} /> : null}
          </div>

          <div className="podi-history-row-head__rate">
            <div className="podi-inline">
              <Typography.Text theme="secondary">评分</Typography.Text>
              <Rate
                value={rating}
                onChange={async (v) => {
                  const next = Number(v) || 0;
                  if (savingRating || savingComment) return;
                  setRating(next);
                  setSavingRating(true);
                  setRowError('');
                  try {
                    await onAnnotate(run.id, next, savedComment);
                    setLastSavedAt(new Date().toISOString());
                  } catch (err) {
                    console.error(err);
                    setRowError(String((err as any)?.message || err));
                  } finally {
                    setSavingRating(false);
                  }
                }}
              />
            </div>
            <Typography.Text theme="secondary" style={{ fontSize: 12, textAlign: 'right' }}>
              {savingRating || savingComment ? '保存中…' : lastSavedAt ? `已保存 ${fmtTime(lastSavedAt)}` : rating ? '已评分' : '未评分'}
            </Typography.Text>
          </div>
        </div>

        <Row gutter={[12, 12]} className="podi-history-row-grid">
          <Col xs={24} lg={8} className="podi-history-row-col">
            <Card
              bordered
              title={
                <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
                  <Typography.Text strong>备注</Typography.Text>
                  <Button
                    size="small"
                    theme="primary"
                    disabled={!commentDirty || savingRating || savingComment}
                    loading={savingComment}
                    onClick={async () => {
                      if (!rating) {
                        setRowError('请先评分（1-5），再保存备注。');
                        return;
                      }
                      setSavingComment(true);
                      setRowError('');
                      try {
                        await onAnnotate(run.id, rating, commentDraft);
                        setSavedComment(commentDraft);
                        setLastSavedAt(new Date().toISOString());
                      } catch (err) {
                        console.error(err);
                        setRowError(String((err as any)?.message || err));
                      } finally {
                        setSavingComment(false);
                      }
                    }}
                  >
                    保存
                  </Button>
                </Space>
              }
            >
              <Space direction="vertical" size="small" style={{ width: '100%' }}>
                {rowError ? <Alert theme="error" message={rowError} /> : null}
                <Textarea
                  value={commentDraft}
                  onChange={(v) => setCommentDraft(String(v))}
                  autosize={{ minRows: 3, maxRows: 8 }}
                  placeholder="问题描述/优化建议…"
                />
                <div className="podi-history-row-params">
                  <Typography.Text theme="secondary">参数</Typography.Text>
                  {paramsPreview ? (
                    <pre className="podi-history-row-params__pre">{paramsPreview}</pre>
                  ) : (
                    <Typography.Text theme="secondary" style={{ fontSize: 12 }}>
                      当前记录仅包含图片 URL。
                    </Typography.Text>
                  )}
                </div>
              </Space>
            </Card>
          </Col>
          <Col xs={24} lg={16} className="podi-history-row-col">
            <Card bordered title="原图 / 结果">
              <div className="podi-image-grid">
                {inputUrl ? (
                  <Button
                    variant="outline"
                    onClick={() => onOpenImage(inputUrl, '原图')}
                    style={{ padding: 6, height: 'auto' }}
                  >
                    <img src={inputUrl} alt="input" style={{ height: 128, width: '100%', objectFit: 'contain' }} />
                  </Button>
                ) : null}

                {outputs.length > 0 ? (
                  outputs.map((u, idx) => (
                    <Button
                      key={`${run.id}-out-${idx}`}
                      variant="outline"
                      onClick={() => onOpenImage(u, `结果图 #${idx + 1}`)}
                      style={{ padding: 6, height: 'auto' }}
                    >
                      <img src={u} alt="output" loading="lazy" style={{ height: 128, width: '100%', objectFit: 'contain' }} />
                    </Button>
                  ))
                ) : run.status !== 'running' && run.status !== 'queued' ? (
                  jsonPreview ? (
                    <pre
                      className="podi-image-grid__full"
                      style={{
                        maxHeight: 280,
                        overflow: 'auto',
                        border: '1px solid var(--td-border-level-1-color)',
                        background: 'var(--td-bg-color-secondarycontainer)',
                        borderRadius: 8,
                        padding: 12,
                        fontFamily: 'monospace',
                        fontSize: 12,
                        whiteSpace: 'pre-wrap',
                      }}
                    >
                      {jsonPreview}
                    </pre>
                  ) : (
                    <Typography.Text theme="secondary">暂无输出</Typography.Text>
                  )
                ) : (
                  <Typography.Text theme="secondary">生成中…</Typography.Text>
                )}
              </div>
            </Card>
          </Col>
        </Row>
      </Space>
    </Card>
  );
}

function AdminWorkflowRow({
  wf,
  adminToken,
  onSaved,
  onAuthInvalid,
}: {
  wf: EvalWorkflowVersion;
  adminToken: string;
  onSaved: (next: EvalWorkflowVersion) => void;
  onAuthInvalid: () => void;
}) {
  const [name, setName] = useState(wf.name);
  const [notes, setNotes] = useState(wf.notes || '');
  const [category, setCategory] = useState(normalizeCategory(wf.category));
  const [status, setStatus] = useState(wf.status);
  const [saving, setSaving] = useState(false);
  const [rowError, setRowError] = useState<string>('');

  const dirty = name !== wf.name || notes !== (wf.notes || '') || category !== normalizeCategory(wf.category) || status !== wf.status;

  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-950/40 p-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0 flex-1">
          <div className="text-xs text-slate-500">workflow_id</div>
          <div className="mt-1 font-mono text-xs text-slate-300 break-all">{wf.workflow_id}</div>

          <div className="mt-3 grid gap-3 lg:grid-cols-2">
            <label className="block">
              <div className="text-xs text-slate-300">名称</div>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="mt-1 w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-sm text-slate-100"
              />
            </label>
            <label className="block">
              <div className="text-xs text-slate-300">分类</div>
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                className="mt-1 w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-sm text-slate-100"
              >
                {CATEGORY_ORDER.map((key) => (
                  <option key={key} value={key}>
                    {key}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <label className="block mt-3">
            <div className="text-xs text-slate-300">备注</div>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={3}
              className="mt-1 w-full rounded-xl border border-slate-800 bg-slate-950 p-3 text-sm text-slate-100"
            />
          </label>
        </div>

        <div className="shrink-0 w-full lg:w-56">
          <label className="block">
            <div className="text-xs text-slate-300">状态</div>
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value)}
              className="mt-1 w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-sm text-slate-100"
            >
              <option value="active">active</option>
              <option value="inactive">inactive</option>
            </select>
          </label>

          <button
            type="button"
            disabled={!dirty || saving}
            onClick={async () => {
              setSaving(true);
              setRowError('');
              try {
                const next = await evalApi.adminUpdateWorkflowVersion(adminToken, wf.id, {
                  name,
                  notes,
                  category,
                  status,
                });
                onSaved(next);
              } catch (err) {
                console.error(err);
                const message = String((err as any)?.message || err);
                setRowError(message);
                if (message.includes('认证已失效')) {
                  onAuthInvalid();
                }
              } finally {
                setSaving(false);
              }
            }}
            className={`mt-3 w-full rounded-xl px-3 py-2 text-sm font-semibold transition ${
              !dirty || saving ? 'bg-slate-700/40 text-slate-400' : 'bg-emerald-500/80 text-white hover:bg-emerald-500'
            }`}
          >
            {saving ? '保存中…' : '保存'}
          </button>
          {rowError ? <div className="mt-2 text-xs text-rose-300 break-words">{rowError}</div> : null}

          <div className="mt-3 text-xs text-slate-500">
            更新时间：{wf.updated_at}
          </div>
        </div>
      </div>
    </div>
  );
}
