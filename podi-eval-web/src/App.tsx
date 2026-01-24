import { useEffect, useMemo, useState } from 'react';
import { evalApi } from './api';
import type { EvalRun, EvalWorkflowVersion, SchemaField } from './types';

type RunWithLatest = EvalRun & {
  latest_annotation?: { rating: number; comment?: string | null; created_at: string; created_by: string } | null;
};

type Notice = { type: 'error' | 'success' | 'info'; message: string };

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
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
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
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-6"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="w-full max-w-5xl rounded-2xl border border-slate-800 bg-slate-950 shadow-xl">
        <div className="flex items-center justify-between gap-3 border-b border-slate-800 px-4 py-3">
          <div className="min-w-0">
            <div className="text-sm font-semibold text-slate-100 truncate">{title || '预览'}</div>
            <div className="text-[11px] text-slate-500 truncate">{url}</div>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setZoomed((z) => !z)}
              className="rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-xs font-semibold text-slate-200 hover:border-slate-700"
            >
              {zoomed ? '缩小' : '放大'}
            </button>
            <a
              href={url}
              target="_blank"
              rel="noreferrer"
              download
              className="rounded-xl bg-emerald-500/80 px-3 py-2 text-xs font-semibold text-white hover:bg-emerald-500"
            >
              下载
            </a>
            <button
              type="button"
              onClick={onClose}
              className="rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-xs font-semibold text-slate-200 hover:border-slate-700"
            >
              关闭
            </button>
          </div>
        </div>
        <div className="max-h-[80vh] overflow-auto p-4">
          <img
            src={url}
            alt="preview"
            className={`mx-auto rounded-xl bg-black/20 object-contain transition ${zoomed ? 'w-auto max-w-none scale-150 origin-top' : 'max-h-[70vh] w-full'}`}
          />
          <div className="mt-2 text-[11px] text-slate-500">提示：按 Esc 或点击遮罩层可关闭。</div>
        </div>
      </div>
    </div>
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
  return (
    <button
      type="button"
      onClick={onClick}
      className={`group w-full rounded-2xl border bg-slate-950/40 p-4 text-left transition ${
        active ? 'border-sky-500/70 shadow-[0_0_0_2px_rgba(56,189,248,0.15)]' : 'border-slate-800 hover:border-slate-700'
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-sm font-semibold text-white truncate">{wf.name}</div>
          <div className="mt-1 text-[11px] text-slate-500 truncate">{wf.workflow_id}</div>
        </div>
        <div className="shrink-0 text-right">
          {metric?.avgRating ? (
            <div className="text-sm font-semibold text-amber-200">{metric.avgRating.toFixed(2)}</div>
          ) : (
            <div className="text-sm font-semibold text-slate-500">—</div>
          )}
          <div className="text-[11px] text-slate-500">{metric?.ratingCount ? `${metric.ratingCount}票` : '未评分'}</div>
        </div>
      </div>
      <div className="mt-3 text-xs text-slate-400 line-clamp-2">{wf.notes || '—'}</div>
      <div className="mt-3 inline-flex items-center gap-2 text-[11px] text-slate-500">
        <span className="rounded-full bg-slate-800/50 px-2 py-0.5">{wf.version}</span>
        <span className="rounded-full bg-slate-800/50 px-2 py-0.5">{normalizeCategory(wf.category)}</span>
      </div>
    </button>
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
      <label className="block">
        <div className="text-xs text-slate-300">
          {label} {required ? <span className="text-rose-400">*</span> : null}
        </div>
        <select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="mt-1 w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-sm text-slate-100"
        >
          {options.map((opt) => (
            <option key={String(opt.value)} value={String(opt.value)}>
              {String(opt.label ?? opt.value)}
            </option>
          ))}
        </select>
      </label>
    );
  }

  if (type === 'textarea') {
    return (
      <label className="block">
        <div className="text-xs text-slate-300">
          {label} {required ? <span className="text-rose-400">*</span> : null}
        </div>
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          rows={4}
          className="mt-1 w-full rounded-xl border border-slate-800 bg-slate-950 p-3 text-sm text-slate-100"
        />
      </label>
    );
  }

  return (
    <label className="block">
      <div className="text-xs text-slate-300">
        {label} {required ? <span className="text-rose-400">*</span> : null}
      </div>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-sm text-slate-100"
      />
    </label>
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
                {outputs.length === 0 ? <div className="text-sm text-slate-500">{run.status === 'running' || run.status === 'queued' ? '生成中…' : '暂无输出'}</div> : null}
              </div>
            </div>
          );
        })}
        {runs.length === 0 ? <div className="text-sm text-slate-500">暂无任务。</div> : null}
      </div>
    </div>
  );
}

function NoticeBar({ notice, onClose }: { notice: Notice | null; onClose: () => void }) {
  if (!notice) return null;
  return (
    <div className="fixed left-1/2 top-4 z-[60] w-[min(920px,calc(100vw-2rem))] -translate-x-1/2">
      <div
        className={`rounded-2xl border px-4 py-3 text-sm shadow-xl backdrop-blur ${
          notice.type === 'error'
            ? 'border-rose-500/40 bg-rose-500/10 text-rose-100'
            : notice.type === 'success'
              ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-100'
              : 'border-slate-700 bg-slate-900/60 text-slate-100'
        }`}
      >
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 break-words">{notice.message}</div>
          <button
            type="button"
            onClick={onClose}
            className="shrink-0 rounded-lg border border-white/10 bg-white/5 px-2 py-1 text-xs hover:bg-white/10"
          >
            关闭
          </button>
        </div>
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

export function App() {
  const [notice, setNotice] = useState<Notice | null>(null);
  const pushNotice = (n: Notice) => {
    setNotice(n);
    window.setTimeout(() => {
      setNotice((cur) => (cur?.message === n.message ? null : cur));
    }, 6500);
  };

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
      pushNotice({ type: 'error', message: String((err as any)?.message || err) });
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
      pushNotice({ type: 'error', message: String((err as any)?.message || err) });
    }
  };

  const loadTasks = async () => {
    try {
      const resp = await evalApi.listRunsWithLatestAnnotation({ limit: 80, offset: 0 });
      setTaskRuns((resp.items || []) as RunWithLatest[]);
    } catch (err) {
      console.error(err);
      pushNotice({ type: 'error', message: String((err as any)?.message || err) });
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
        pushNotice({ type: 'error', message: String((err as any)?.message || err) });
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
      pushNotice({ type: 'error', message: '请先填写或上传图片 URL' });
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
      pushNotice({ type: 'error', message: `请补齐必填参数：${missing.join('、')}` });
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
      pushNotice({ type: 'success', message: '已提交运行，稍后会自动刷新结果' });
    } catch (err) {
      console.error(err);
      pushNotice({ type: 'error', message: String((err as any)?.message || err) });
    } finally {
      setIsRunning(false);
    }
  };

  const annotate = async (runId: string, rating: number, comment: string) => {
    try {
      await evalApi.createAnnotation(runId, { rating, comment: comment.trim() || undefined });
      await refreshMetrics();
      if (selectedTool) await loadRunsForTool(selectedTool.id);
      pushNotice({ type: 'success', message: '已保存评分/备注' });
    } catch (err) {
      console.error(err);
      pushNotice({ type: 'error', message: String((err as any)?.message || err) });
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

  const header = (
    <header className="border-b border-slate-800 bg-slate-900/40">
      <div className="mx-auto max-w-[1400px] px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="text-lg font-semibold">PODI · 能力评测</div>
          <div className="text-xs text-slate-400">工具箱式评测 · 免登录 · 评分沉淀 · UI v2</div>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => {
              setActiveView('home');
              setSelectedTool(null);
            }}
            className={`rounded-xl px-3 py-2 text-xs font-semibold transition ${
              activeView === 'home' ? 'bg-sky-500/20 text-sky-200 border border-sky-500/40' : 'bg-slate-950 border border-slate-800 text-slate-300 hover:border-slate-700'
            }`}
          >
            工具箱
          </button>
          <button
            type="button"
            onClick={() => {
              setActiveView('tasks');
              setSelectedTool(null);
            }}
            className={`rounded-xl px-3 py-2 text-xs font-semibold transition ${
              activeView === 'tasks' ? 'bg-sky-500/20 text-sky-200 border border-sky-500/40' : 'bg-slate-950 border border-slate-800 text-slate-300 hover:border-slate-700'
            }`}
          >
            任务管理
          </button>
          <button
            type="button"
            onClick={() => {
              setActiveView('docs');
              setSelectedTool(null);
            }}
            className={`rounded-xl px-3 py-2 text-xs font-semibold transition ${
              activeView === 'docs'
                ? 'bg-sky-500/20 text-sky-200 border border-sky-500/40'
                : 'bg-slate-950 border border-slate-800 text-slate-300 hover:border-slate-700'
            }`}
          >
            文档
          </button>
          <button
            type="button"
            onClick={async () => {
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
                pushNotice({ type: 'error', message: String((err as any)?.message || err) });
              }
            }}
            className={`rounded-xl px-3 py-2 text-xs font-semibold transition ${
              activeView === 'admin'
                ? 'bg-sky-500/20 text-sky-200 border border-sky-500/40'
                : 'bg-slate-950 border border-slate-800 text-slate-300 hover:border-slate-700'
            }`}
          >
            维护
          </button>
          <div className="ml-2 text-xs text-slate-400">
            raterId: <span className="font-mono text-slate-200">{raterId || '...'}</span>
          </div>
        </div>
      </div>
    </header>
  );

  if (activeView === 'admin') {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-50">
        {header}
        <NoticeBar notice={notice} onClose={() => setNotice(null)} />
        <div className="mx-auto max-w-[1400px] px-6 py-6">
          <div className="rounded-3xl border border-slate-800 bg-slate-900/30 p-5">
            <div className="flex items-end justify-between">
              <div>
                <div className="text-lg font-semibold">功能维护</div>
                <div className="text-xs text-slate-400">维护各功能的名称/备注/分类/状态（需要 EVAL_ADMIN_TOKEN）。</div>
              </div>
              <button
                type="button"
                onClick={async () => {
                  if (!adminToken) return;
                  try {
                    const list = await evalApi.adminListWorkflowVersions(adminToken);
                    setAdminWorkflows(list);
                    pushNotice({ type: 'success', message: '已刷新列表' });
                  } catch (err) {
                    console.error(err);
                    pushNotice({ type: 'error', message: String((err as any)?.message || err) });
                  }
                }}
                className="rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-xs text-slate-200 hover:border-slate-700"
              >
                刷新列表
              </button>
            </div>
            <div className="mt-4 space-y-3">
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
              {adminWorkflows.length === 0 ? <div className="text-sm text-slate-500">暂无数据。</div> : null}
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (activeView === 'docs') {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-50">
        {header}
        <NoticeBar notice={notice} onClose={() => setNotice(null)} />
        <div className="mx-auto max-w-[1400px] px-6 py-6">
          <div className="rounded-3xl border border-slate-800 bg-slate-900/30 p-5">
            <div className="flex items-end justify-between gap-3">
              <div>
                <div className="text-lg font-semibold">开发文档 · Coze 工作流</div>
                <div className="text-xs text-slate-400">
                  从后端自动生成（active 工作流 + 入参/出参 schema）。{docsGeneratedAt ? `生成时间：${docsGeneratedAt}` : ''}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={async () => {
                    try {
                      await navigator.clipboard.writeText(docsMarkdown || '');
                      pushNotice({ type: 'success', message: '已复制到剪贴板' });
                    } catch (err) {
                      console.error(err);
                      pushNotice({ type: 'error', message: '复制失败（浏览器不支持或权限不足）' });
                    }
                  }}
                  className="rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-xs text-slate-200 hover:border-slate-700"
                >
                  复制全文
                </button>
              </div>
            </div>
            <div className="mt-4">
              {docsLoading ? (
                <div className="text-sm text-slate-400">加载中…</div>
              ) : docsMarkdown ? (
                <pre className="max-h-[70vh] overflow-auto rounded-2xl border border-slate-800 bg-slate-950/40 p-4 font-mono text-[12px] text-slate-200 whitespace-pre-wrap">
                  {docsMarkdown}
                </pre>
              ) : (
                <div className="text-sm text-slate-500">暂无文档内容。</div>
              )}
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (activeView === 'tasks') {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-50">
        {header}
        <NoticeBar notice={notice} onClose={() => setNotice(null)} />
        <Lightbox url={lightbox?.url || ''} title={lightbox?.title} onClose={() => setLightbox(null)} />
        <div className="mx-auto max-w-[1400px] px-6 py-6">
          <TaskTable runs={taskRuns} workflowMap={workflowMap} />
        </div>
      </div>
    );
  }

  if (activeView === 'tool' && selectedTool) {
    const metric = metrics[selectedTool.id];
    const doc = buildCozeDoc(selectedTool, formUrl.trim());
    return (
      <div className="min-h-screen bg-slate-950 text-slate-50">
        {header}
        <NoticeBar notice={notice} onClose={() => setNotice(null)} />
        <Lightbox url={lightbox?.url || ''} title={lightbox?.title} onClose={() => setLightbox(null)} />
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
                  <div className="mt-1 flex gap-2">
                    <input
                      value={formUrl}
                      onChange={(e) => setFormUrl(e.target.value)}
                      placeholder="支持粘贴 URL 或上传本地图片"
                      className="w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-600"
                    />
                    <label className="shrink-0 rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-xs text-slate-200 hover:border-slate-700 cursor-pointer">
                      {uploading ? '上传中…' : '上传'}
                      <input
                        type="file"
                        accept="image/*"
                        className="hidden"
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
                            pushNotice({ type: 'error', message: String((err as any)?.message || err) });
                          } finally {
                            setUploading(false);
                            e.target.value = '';
                          }
                        }}
                      />
                    </label>
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
                <button
                  type="button"
                  disabled={!formUrl.trim() || isRunning}
                  onClick={() => void runTool()}
                  className={`rounded-xl px-4 py-2 text-sm font-semibold transition ${
                    !formUrl.trim() || isRunning ? 'bg-slate-700/40 text-slate-400' : 'bg-sky-500/80 text-white hover:bg-sky-500'
                  }`}
                >
                  {isRunning ? '运行中…' : '开始生成'}
                </button>
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
                    return (
                      <div className="rounded-2xl border border-slate-800 bg-slate-950/30 p-4 text-sm text-slate-300">
                        正在生成中…
                        <div className="mt-2 text-xs text-slate-500">run: {latest.id}</div>
                      </div>
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
                  const imgs = latest.result_image_urls_json || [];
                  if (!imgs.length) {
                    return <div className="text-sm text-slate-500">该次运行无图片输出。</div>;
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
                    <select
                      value={filterStatus}
                      onChange={(e) => setFilterStatus(e.target.value)}
                      className="rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-xs text-slate-200"
                    >
                      <option value="all">全部状态</option>
                      <option value="queued">queued</option>
                      <option value="running">running</option>
                      <option value="succeeded">succeeded</option>
                      <option value="failed">failed</option>
                    </select>
                    <select
                      value={filterRating}
                      onChange={(e) => setFilterRating(e.target.value)}
                      className="rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-xs text-slate-200"
                    >
                      <option value="all">全部评分</option>
                      {[1, 2, 3, 4, 5].map((n) => (
                        <option key={n} value={String(n)}>
                          {n}
                        </option>
                      ))}
                    </select>
                    <label className="flex items-center gap-2 text-xs text-slate-300">
                      <input
                        type="checkbox"
                        checked={filterUnrated}
                        onChange={(e) => setFilterUnrated(e.target.checked)}
                        className="h-4 w-4 rounded border-slate-700 bg-slate-950"
                      />
                      未打分
                    </label>
                    <input
                      value={search}
                      onChange={(e) => setSearch(e.target.value)}
                      placeholder="搜索备注/错误…"
                      className="w-56 rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-xs text-slate-200 placeholder:text-slate-600"
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
      </div>
    );
  }

  // Home (toolbox) view
  return (
    <div className="min-h-screen bg-slate-950 text-slate-50">
      {header}
      <NoticeBar notice={notice} onClose={() => setNotice(null)} />
      <Lightbox url={lightbox?.url || ''} title={lightbox?.title} onClose={() => setLightbox(null)} />
      <div className="mx-auto max-w-[1400px] px-6 py-6 grid gap-6 lg:grid-cols-[280px_1fr]">
        <aside className="rounded-3xl border border-slate-800 bg-slate-900/30 p-4">
          <div className="text-sm font-semibold">分类</div>
          <div className="mt-1 text-xs text-slate-400">左侧选分类，右侧是该分类的功能卡片</div>
          <div className="mt-4 space-y-2">
            {orderedCategories.map((cat) => {
              const active = activeCategory === cat;
              return (
                <button
                  key={cat}
                  type="button"
                  onClick={() => setActiveCategory(cat)}
                  className={`w-full rounded-2xl border px-3 py-2 text-left transition ${
                    active ? 'border-sky-500/70 bg-sky-500/10 text-white' : 'border-white/5 text-slate-300 hover:border-slate-500/60'
                  }`}
                >
                  <div className="text-sm font-semibold">{cat}</div>
                  <div className="text-xs text-slate-500">{(grouped[cat] || []).length} 个功能</div>
                </button>
              );
            })}
          </div>
        </aside>

        <main>
          <div className="mb-4">
            <div className="text-lg font-semibold">{normalizeCategory(activeCategory)}</div>
            <div className="text-xs text-slate-400">点击卡片进入该功能的评测页面（左侧测试，右侧出图，底部打标）。</div>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {toolList.map((wf) => (
              <ToolCard
                key={wf.id}
                wf={wf}
                active={false}
                metric={metrics[wf.id]}
                onClick={() => openTool(wf)}
              />
            ))}
            {toolList.length === 0 ? <div className="text-sm text-slate-500">该分类暂无功能。</div> : null}
          </div>
        </main>
      </div>
    </div>
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
  const outputs = run.result_image_urls_json || [];
  const [rating, setRating] = useState<number>(run.latest_annotation?.rating || 0);
  const [savedComment, setSavedComment] = useState<string>(String(run.latest_annotation?.comment || ''));
  const [commentDraft, setCommentDraft] = useState<string>(String(run.latest_annotation?.comment || ''));
  const [savingRating, setSavingRating] = useState(false);
  const [savingComment, setSavingComment] = useState(false);
  const [lastSavedAt, setLastSavedAt] = useState<string>('');
  const [rowError, setRowError] = useState<string>('');

  const commentDirty = commentDraft !== savedComment;

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
              <div className="text-sm text-slate-500">{run.status === 'running' || run.status === 'queued' ? '生成中…' : '暂无输出'}</div>
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
