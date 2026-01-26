import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import {
  Alert,
  Button,
  Card,
  Col,
  ConfigProvider,
  Dialog,
  Input,
  Layout,
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
import type { EvalRun, EvalWorkflowVersion, SchemaField } from './types';

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
    // Force CN business timezone regardless of server/browser settings.
    return new Date(iso).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false });
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
      style={{ cursor: 'pointer' }}
    >
      <Card
        bordered
        style={{
          borderColor: active ? 'var(--td-brand-color)' : undefined,
        }}
      >
        <Space direction="vertical" size="small" style={{ width: '100%' }}>
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

          <Typography.Text theme="secondary" style={{ fontSize: 12 }}>
            {wf.notes || '—'}
          </Typography.Text>

          <Space breakLine>
            <Tag variant="light">{wf.version}</Tag>
            <Tag variant="light">{normalizeCategory(wf.category)}</Tag>
          </Space>
        </Space>
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
    <div className="rounded-3xl border border-slate-800 bg-slate-900/30 p-5">
      <div className="flex items-end justify-between">
        <div>
          <div className="text-lg font-semibold">任务管理</div>
          <div className="text-xs text-slate-400">实时刷新：queued/running 会持续轮询；ComfyUI 类回调出图后才算完成。</div>
        </div>
        <div className="text-xs text-slate-500">最近 {runs.length} 条</div>
      </div>

      <div className="mt-4 space-y-3">
        {runs.map((run) => {
          const wf = workflowMap[run.workflow_version_id];
          const inputUrl = (run.input_oss_urls_json || [])[0] || '';
          const outputs = run.result_image_urls_json || [];
          const outputJson = (run as any).result_output_json;
          const jsonPreview = formatJsonPreview(outputJson, 420);
          return (
            <div key={run.id} className="rounded-2xl border border-slate-800 bg-slate-950/40 p-4">
              <div className="flex flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
                <div>
                  <div className="text-sm font-semibold">{wf ? wf.name : run.workflow_version_id}</div>
                  <div className="mt-1 flex flex-wrap items-center gap-3 text-xs text-slate-400">
                    <span className="rounded-full bg-slate-800/60 px-2 py-0.5">{run.status}</span>
                    <span>耗时：{formatDuration(run.duration_ms)}</span>
                    {run.podi_task_id ? <span className="font-mono">task: {run.podi_task_id}</span> : null}
                    {run.coze_debug_url ? (
                      <a className="text-sky-400 underline" href={run.coze_debug_url} target="_blank" rel="noreferrer">
                        debug_url
                      </a>
                    ) : null}
                    {run.latest_annotation?.rating ? (
                      <span className="text-amber-200">评分：{run.latest_annotation.rating}</span>
                    ) : (
                      <span className="text-slate-500">未评分</span>
                    )}
                  </div>
                  {run.error_message ? <div className="mt-2 text-xs text-rose-400">{run.error_message}</div> : null}
                </div>
                <div className="text-xs text-slate-500">{fmtTime(run.created_at)}</div>
              </div>

              <div className="mt-3 grid gap-2 lg:grid-cols-6">
                {inputUrl ? (
                  <a href={inputUrl} target="_blank" rel="noreferrer" className="block rounded-xl border border-slate-800 bg-slate-950/30 p-1">
                    <img src={inputUrl} alt="input" className="h-24 w-full rounded-lg object-contain" />
                  </a>
                ) : null}
                {outputs.slice(0, 5).map((u, idx) => (
                  <a key={`${run.id}-out-${idx}`} href={u} target="_blank" rel="noreferrer" className="block rounded-xl border border-slate-800 bg-slate-950/30 p-1">
                    <img
                      src={u}
                      alt="output"
                      loading="lazy"
                      onError={(e) => {
                        // Avoid showing broken-image icons in the task table.
                        (e.currentTarget as HTMLImageElement).style.display = 'none';
                      }}
                      className="h-24 w-full rounded-lg object-contain"
                    />
                  </a>
                ))}
                {outputs.length === 0 && jsonPreview ? (
                  <div className="lg:col-span-5 rounded-xl border border-slate-800 bg-slate-950/30 p-3">
                    <div className="text-[11px] font-semibold text-slate-300">输出 JSON</div>
                    <pre className="mt-2 max-h-28 overflow-auto whitespace-pre-wrap break-words text-[11px] text-slate-200">{jsonPreview}</pre>
                  </div>
                ) : null}
                {outputs.length === 0 && !jsonPreview ? (
                  <div className="text-sm text-slate-500">{run.status === 'running' || run.status === 'queued' ? '生成中…' : '暂无输出'}</div>
                ) : null}
              </div>
            </div>
          );
        })}
        {runs.length === 0 ? <div className="text-sm text-slate-500">暂无任务。</div> : null}
      </div>
    </div>
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
      defaults[f.name] = opt ? String(opt) : def ? String(def) : '';
    }
    setFormParams(defaults);
    setActiveView('tool');
  };

  const runTool = async () => {
    if (!selectedTool) return;
    const url = formUrl.trim();
    if (!url) {
      pushNotice('error', '请先填写或上传图片 URL');
      return;
    }

    // Validate required fields in schema (except `prompt`: backend will fallback to " ").
    const missing: string[] = [];
    for (const f of getFields(selectedTool)) {
      if (!(f as any)?.required) continue;
      if (f.name === 'url' || f.name === 'prompt') continue;
      const v = String((formParams as any)?.[f.name] ?? '').trim();
      if (!v) missing.push((f as any).label || f.name);
    }
    if (missing.length > 0) {
      pushNotice('error', `请补齐必填参数：${missing.join('、')}`);
      return;
    }

    setIsRunning(true);
    try {
      const parameters: Record<string, unknown> = { url };
      for (const [k, v] of Object.entries(formParams)) {
        if (v === '') continue;
        parameters[k] = v;
      }
      await evalApi.createRun({
        workflow_version_id: selectedTool.id,
        input_oss_urls_json: [url],
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

  const openAdmin = useCallback(async () => {
    // "Private-ish": require a token, stored locally. No normal login.
    const token = adminToken || window.prompt('请输入 EVAL_ADMIN_TOKEN（仅管理员维护功能名/备注）') || '';
    if (!token.trim()) return;
    localStorage.setItem('podi_eval_admin_token', token.trim());
    setAdminToken(token.trim());
    setActiveView('admin');
    setSelectedTool(null);
    try {
      const list = await evalApi.adminListWorkflowVersions(token.trim());
      setAdminWorkflows(list);
    } catch (err) {
      console.error(err);
      pushNotice('error', String((err as any)?.message || err));
    }
  }, [adminToken, pushNotice]);

  const headerNavValue = activeView === 'tool' ? 'home' : activeView;

  const header = (
    <Layout.Header
      style={{
        borderBottom: '1px solid var(--td-component-border)',
        background: 'var(--td-bg-color-container)',
        padding: '0 16px',
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
      <Layout style={{ minHeight: '100vh' }}>
        {header}
        <Layout.Content style={{ padding: 16, background: 'var(--td-bg-color-page)' }}>
          <div style={{ maxWidth: 1400, margin: '0 auto' }}>{content}</div>
        </Layout.Content>
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
          </Space>
        }
      >
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          {adminWorkflows.map((wf) => (
            <AdminWorkflowRow
              key={wf.id}
              wf={wf}
              adminToken={adminToken}
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
        }
      >
        {docsLoading ? (
          <Typography.Text theme="secondary">加载中…</Typography.Text>
        ) : docsMarkdown ? (
          <pre
            style={{
              maxHeight: '70vh',
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
            {docsMarkdown}
          </pre>
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
        <div className="mx-auto max-w-[1400px] px-6 py-6">
          <div className="mb-4 flex items-start justify-between gap-4">
            <div>
              <button
                type="button"
                onClick={() => setActiveView('home')}
                className="mb-2 inline-flex items-center gap-2 rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-xs text-slate-200 hover:border-slate-700"
              >
                ← 返回功能列表
              </button>
              <div className="text-xl font-semibold">{selectedTool.name}</div>
              <div className="mt-1 text-xs text-slate-400">{selectedTool.notes || '—'}</div>
              <div className="mt-2 flex items-center gap-3 text-xs text-slate-400">
                <span className="rounded-full bg-slate-800/60 px-2 py-0.5">{normalizeCategory(selectedTool.category)}</span>
                <span className="rounded-full bg-slate-800/60 px-2 py-0.5">{selectedTool.version}</span>
                {metric?.avgRating ? (
                  <span className="text-amber-200">综合评分：{metric.avgRating.toFixed(2)} / 5（{metric.ratingCount}票）</span>
                ) : (
                  <span className="text-slate-500">综合评分：暂无</span>
                )}
              </div>
            </div>
            <div className="text-right text-xs text-slate-500">
              <div>workflow_id</div>
              <div className="font-mono text-slate-300">{selectedTool.workflow_id}</div>
            </div>
          </div>

          <div className="grid gap-6 lg:grid-cols-[520px_1fr]">
            <div className="rounded-3xl border border-slate-800 bg-slate-900/30 p-5">
              <div className="text-sm font-semibold">左侧：测试参数</div>
              <div className="mt-4">
                <label className="block">
                  <div className="text-xs text-slate-300">
                    图片 URL <span className="text-rose-400">*</span>
                  </div>
                  <div className="mt-1">
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
                  </div>
                </label>
                {formUrl.trim() ? (
                  <div className="mt-3">
                    <div className="text-xs text-slate-500 mb-1">原图预览</div>
                    <img src={formUrl.trim()} alt="input" className="h-56 w-full rounded-2xl border border-slate-800 bg-slate-950/30 object-contain" />
                  </div>
                ) : null}
              </div>

              <div className="mt-4 space-y-3">
                {toolFields
                  .filter((f) => f.name !== 'url')
                  .map((f) => (
                    <ParamField key={f.name} field={f} value={formParams[f.name] ?? ''} onChange={(v) => setFormParams((p) => ({ ...p, [f.name]: v }))} />
                  ))}
              </div>

              <div className="mt-4 flex justify-end">
                <Button theme="primary" loading={isRunning} disabled={!formUrl.trim()} onClick={() => void runTool()}>
                  开始生成
                </Button>
              </div>

              <div className="mt-5 rounded-2xl border border-slate-800 bg-slate-950/40 p-3">
                <div className="text-xs text-slate-400 mb-2">业务接入文档（Coze OpenAPI）</div>
                <pre className="max-h-48 overflow-auto rounded-xl bg-slate-950 p-3 font-mono text-[11px] text-slate-200">{doc}</pre>
              </div>
            </div>

            <div className="rounded-3xl border border-slate-800 bg-slate-900/30 p-5">
              <div className="text-sm font-semibold">右侧：生成结果</div>
              <div className="mt-3 text-xs text-slate-400">点击图片可在页面内放大预览；下方历史可筛选/打标。</div>
              <div className="mt-4 grid gap-3 lg:grid-cols-3">
                {(() => {
                  const latest = toolRuns[0] || null; // runs are loaded per-tool (ordered desc by created_at)
                  if (!latest) {
                    return <div className="text-sm text-slate-500">暂无记录（先在左侧运行一次）。</div>;
                  }
                  if (latest.status === 'queued' || latest.status === 'running') {
                    const rawCount = Number((latest.parameters_json as any)?.count);
                    const count = Number.isFinite(rawCount) && rawCount > 1 ? Math.min(Math.max(rawCount, 2), 12) : 1;
                    const imgs = filterImageUrls(latest.result_image_urls_json);
                    const remain = Math.max(0, count - imgs.length);
                    return (
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
                          <SkeletonTile key={`sk-${latest.id}-${idx}`} title={`生成中… #${imgs.length + idx + 1}`} subtitle={`run: ${latest.id}`} />
                        ))}
                      </>
                    );
                  }
                  if (latest.status === 'failed') {
                    return (
                      <div className="rounded-2xl border border-slate-800 bg-slate-950/30 p-4 text-sm text-rose-300">
                        生成失败
                        {latest.error_message ? <div className="mt-2 text-xs text-rose-400">{latest.error_message}</div> : null}
                        <div className="mt-2 text-xs text-slate-500">run: {latest.id}</div>
                      </div>
                    );
                  }
                  const imgs = filterImageUrls(latest.result_image_urls_json);
                  if (!imgs.length) {
                    const jsonPreview = formatJsonPreview((latest as any).result_output_json, 2400);
                    return (
                      <div className="rounded-2xl border border-slate-800 bg-slate-950/30 p-4 text-sm text-slate-300">
                        {jsonPreview ? (
                          <>
                            <div className="font-semibold">输出 JSON</div>
                            <pre className="mt-3 max-h-96 overflow-auto whitespace-pre-wrap break-words rounded-xl border border-slate-800 bg-slate-950/60 p-3 text-[12px] text-slate-100">
                              {jsonPreview}
                            </pre>
                          </>
                        ) : (
                          <>该次运行无图片输出。</>
                        )}
                        {latest.coze_debug_url ? (
                          <div className="mt-2 text-xs">
                            <a className="text-sky-400 underline" href={latest.coze_debug_url} target="_blank" rel="noreferrer">
                              打开 Coze debug_url
                            </a>
                          </div>
                        ) : null}
                      </div>
                    );
                  }
                  return imgs.map((img, idx) => (
                    <ImageTile
                      key={`latest-${idx}`}
                      url={img}
                      title={`最新结果 #${idx + 1}`}
                      onOpen={() => setLightbox({ url: img, title: `最新结果 #${idx + 1}` })}
                    />
                  ));
                })()}
              </div>

              <div className="mt-6 border-t border-slate-800 pt-5">
                <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
                  <div>
                    <div className="text-sm font-semibold">历史记录（打标区）</div>
                    <div className="text-xs text-slate-500">每条记录包含原图 + 结果图；支持筛选与备注。</div>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Select
                      value={filterStatus}
                      onChange={(v) => setFilterStatus(String(v))}
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
                      options={[
                        { label: '全部评分', value: 'all' },
                        ...[1, 2, 3, 4, 5].map((n) => ({ label: String(n), value: String(n) })),
                      ]}
                    />
                    <Space align="center" size="small">
                      <Switch value={filterUnrated} onChange={(v) => setFilterUnrated(Boolean(v))} />
                      <Typography.Text theme="secondary">未打分</Typography.Text>
                    </Space>
                    <Input
                      value={search}
                      onChange={(v) => setSearch(String(v))}
                      placeholder="搜索备注/错误…"
                      clearable
                    />
                  </div>
                </div>

                <div className="mt-4 space-y-4">
                  {filteredRuns.map((run) => (
                    <HistoryRow
                      key={run.id}
                      run={run}
                      onAnnotate={annotate}
                      onOpenImage={(url, title) => setLightbox({ url, title })}
                    />
                  ))}
                  {filteredRuns.length === 0 ? <div className="text-sm text-slate-500">暂无记录。</div> : null}
                </div>
              </div>
            </div>
          </div>
        </div>
    );
  }

  // Home (toolbox) view
  return shell(
    <Row gutter={[12, 12]}>
      <Col xs={24} lg={6}>
        <Card bordered title="分类">
          <Space direction="vertical" size="small" style={{ width: '100%' }}>
            <Typography.Text theme="secondary">左侧选分类，右侧是该分类的功能卡片</Typography.Text>
            <Space direction="vertical" size="small" style={{ width: '100%' }}>
              {orderedCategories.map((cat) => (
                <Button
                  key={cat}
                  theme={activeCategory === cat ? 'primary' : 'default'}
                  variant={activeCategory === cat ? 'base' : 'outline'}
                  onClick={() => setActiveCategory(cat)}
                  style={{ justifyContent: 'space-between' }}
                >
                  <span>{cat}</span>
                  <span style={{ opacity: 0.7 }}>{(grouped[cat] || []).length}</span>
                </Button>
              ))}
            </Space>
          </Space>
        </Card>
      </Col>
      <Col xs={24} lg={18}>
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          <div>
            <Typography.Title level="h4" style={{ margin: 0 }}>
              {normalizeCategory(activeCategory)}
            </Typography.Title>
            <Typography.Text theme="secondary">
              点击卡片进入该功能的评测页面（左侧测试，右侧出图，底部打标）。
            </Typography.Text>
          </div>
          <Row gutter={[12, 12]}>
            {toolList.map((wf) => (
              <Col key={wf.id} xs={24} sm={12} lg={8}>
                <ToolCard wf={wf} active={false} metric={metrics[wf.id]} onClick={() => openTool(wf)} />
              </Col>
            ))}
            {toolList.length === 0 ? (
              <Col span={24}>
                <Alert theme="info" message="该分类暂无功能。" />
              </Col>
            ) : null}
          </Row>
        </Space>
      </Col>
    </Row>
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
    <div className="rounded-2xl border border-slate-800 bg-slate-950/40 p-4">
      <div className="flex flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
        <div className="min-w-0">
          <div className="text-xs text-slate-500">Run</div>
          <div className="text-sm font-semibold text-slate-100 break-all">{run.id}</div>
          <div className="mt-1 flex flex-wrap items-center gap-3 text-xs text-slate-400">
            <span className="rounded-full bg-slate-800/60 px-2 py-0.5">{run.status}</span>
            <span>耗时：{formatDuration(run.duration_ms)}</span>
            {run.podi_task_id ? <span className="font-mono">task: {run.podi_task_id}</span> : null}
            {run.coze_debug_url ? (
              <a className="text-sky-400 underline" href={run.coze_debug_url} target="_blank" rel="noreferrer">
                debug_url
              </a>
            ) : null}
            <span className="text-slate-500">{fmtTime(run.created_at)}</span>
          </div>
          {run.error_message ? <div className="mt-2 text-xs text-rose-400">{run.error_message}</div> : null}
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1">
            {[1, 2, 3, 4, 5].map((n) => {
              const active = rating === n;
              return (
                <button
                  key={`${run.id}-r-${n}`}
                  type="button"
                  onClick={async () => {
                    if (savingRating || savingComment) return;
                    setRating(n);
                    setSavingRating(true);
                    setRowError('');
                    try {
                      // Save rating immediately. Keep last saved comment to avoid clearing it.
                      await onAnnotate(run.id, n, savedComment);
                      setLastSavedAt(new Date().toISOString());
                    } catch (err) {
                      console.error(err);
                      setRowError(String((err as any)?.message || err));
                    } finally {
                      setSavingRating(false);
                    }
                  }}
                  className={`h-9 w-9 rounded-xl border text-sm transition ${
                    active
                      ? 'border-amber-400/80 bg-amber-400/25 text-amber-100 shadow-[0_0_0_2px_rgba(251,191,36,0.12)]'
                      : 'border-slate-800 bg-slate-950 text-slate-200 hover:border-slate-700'
                  }`}
                >
                  {n}
                </button>
              );
            })}
          </div>
          <div className="ml-2 text-xs text-slate-400">
            {savingRating || savingComment ? (
              <span className="text-slate-300">保存中…</span>
            ) : rating ? (
              <span className="text-amber-200">已评分 {rating}</span>
            ) : (
              <span className="text-slate-500">未评分</span>
            )}
            {lastSavedAt ? <span className="ml-2 text-slate-500">({fmtTime(lastSavedAt)})</span> : null}
          </div>
        </div>
      </div>

      <div className="mt-3 grid gap-3 lg:grid-cols-[220px_1fr]">
        <div>
          {rowError ? <div className="mb-2 text-xs text-rose-300">{rowError}</div> : null}
          <div className="flex items-center justify-between gap-2 mb-1">
            <div className="text-xs text-slate-500">备注（可选）</div>
            <button
              type="button"
              disabled={!commentDirty || savingRating || savingComment}
              onClick={async () => {
                if (!rating) {
                  setRowError('请先点一个评分（1-5），再保存备注。');
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
              className={`rounded-xl px-3 py-2 text-xs font-semibold transition ${
                !commentDirty || savingRating || savingComment
                  ? 'bg-slate-700/40 text-slate-400'
                  : 'bg-emerald-500/80 text-white hover:bg-emerald-500'
              }`}
            >
              保存备注
            </button>
          </div>
          <textarea
            value={commentDraft}
            onChange={(e) => setCommentDraft(e.target.value)}
            rows={3}
            className="w-full rounded-xl border border-slate-800 bg-slate-950 p-3 text-sm text-slate-100"
            placeholder="问题描述/优化建议…"
          />
        </div>
        <div>
          <div className="text-xs text-slate-500 mb-1">原图 / 结果</div>
          <div className="grid gap-2 lg:grid-cols-4">
            {inputUrl ? (
              <button
                type="button"
                onClick={() => onOpenImage(inputUrl, '原图')}
                className="block rounded-xl border border-slate-800 bg-slate-950/30 p-1 hover:border-slate-700"
              >
                <img src={inputUrl} alt="input" className="h-32 w-full rounded-lg object-contain" />
              </button>
            ) : null}
            {outputs.length > 0 ? (
              outputs.map((u, idx) => (
                <button
                  key={`${run.id}-out-${idx}`}
                  type="button"
                  onClick={() => onOpenImage(u, `结果图 #${idx + 1}`)}
                  className="block rounded-xl border border-slate-800 bg-slate-950/30 p-1 hover:border-slate-700"
                >
                  <img
                    src={u}
                    alt="output"
                    loading="lazy"
                    onError={(e) => {
                      (e.currentTarget as HTMLImageElement).style.display = 'none';
                    }}
                    className="h-32 w-full rounded-lg object-contain"
                  />
                </button>
              ))
            ) : (
              (() => {
                if (run.status !== 'running' && run.status !== 'queued') {
                  if (jsonPreview) {
                    return (
                      <pre className="lg:col-span-3 max-h-72 overflow-auto whitespace-pre-wrap break-words rounded-xl border border-slate-800 bg-slate-950/60 p-3 text-[12px] text-slate-100">
                        {jsonPreview}
                      </pre>
                    );
                  }
                  return <div className="text-sm text-slate-500">暂无输出</div>;
                }
                const rawCount = Number((run.parameters_json as any)?.count);
                const count = Number.isFinite(rawCount) && rawCount > 1 ? Math.min(Math.max(rawCount, 2), 12) : 1;
                const remain = Math.max(0, count - outputs.length);
                return (
                  <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                    {Array.from({ length: remain }).map((_, idx) => (
                      <div
                        key={`${run.id}-sk-${idx}`}
                        className="h-32 w-full rounded-xl border border-slate-800 bg-slate-950/60 animate-pulse"
                        title="生成中…"
                      />
                    ))}
                  </div>
                );
              })()
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function AdminWorkflowRow({
  wf,
  adminToken,
  onSaved,
}: {
  wf: EvalWorkflowVersion;
  adminToken: string;
  onSaved: (next: EvalWorkflowVersion) => void;
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
                setRowError(String((err as any)?.message || err));
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
