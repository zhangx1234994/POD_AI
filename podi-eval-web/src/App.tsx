import { useEffect, useMemo, useState } from 'react';
import { evalApi } from './api';
import type { EvalRun, EvalWorkflowVersion, SchemaField } from './types';

type RunWithLatest = EvalRun & {
  latest_annotation?: { rating: number; comment?: string | null; created_at: string; created_by: string } | null;
};

const CATEGORY_LABELS: Record<string, string> = {
  pattern_extract: '花纹提取类',
  image_extend: '图延伸类',
  continuous_pattern: '四方/两方连续图类',
  image_variation: '图略变类',
  general: '通用类',
};

const CATEGORY_ORDER = ['pattern_extract', 'image_extend', 'continuous_pattern', 'image_variation', 'general'];

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
        <span className="rounded-full bg-slate-800/50 px-2 py-0.5">{CATEGORY_LABELS[wf.category] ?? wf.category}</span>
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
                    <img src={u} alt="output" className="h-24 w-full rounded-lg object-contain" />
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

export function App() {
  const [raterId, setRaterId] = useState<string>('');
  const [workflows, setWorkflows] = useState<EvalWorkflowVersion[]>([]);
  const [metrics, setMetrics] = useState<Record<string, { ratingCount: number; avgRating: number | null }>>({});

  const [activeCategory, setActiveCategory] = useState<string>('general');
  const [activeView, setActiveView] = useState<'home' | 'tool' | 'tasks'>('home');
  const [selectedTool, setSelectedTool] = useState<EvalWorkflowVersion | null>(null);

  const [formUrl, setFormUrl] = useState('');
  const [formParams, setFormParams] = useState<Record<string, string>>({});
  const [isRunning, setIsRunning] = useState(false);

  const [runs, setRuns] = useState<RunWithLatest[]>([]);
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [filterRating, setFilterRating] = useState<string>('all');
  const [filterUnrated, setFilterUnrated] = useState<boolean>(false);
  const [search, setSearch] = useState<string>('');

  const workflowMap = useMemo(() => {
    const m: Record<string, EvalWorkflowVersion> = {};
    for (const wf of workflows) m[wf.id] = wf;
    return m;
  }, [workflows]);

  const grouped = useMemo(() => {
    const m: Record<string, EvalWorkflowVersion[]> = {};
    for (const wf of workflows) {
      const key = wf.category || 'general';
      m[key] = m[key] || [];
      m[key].push(wf);
    }
    return m;
  }, [workflows]);

  const orderedCategories = useMemo(() => {
    // Always show the 5 business categories even if empty (e.g. continuous_pattern placeholder).
    const out: string[] = CATEGORY_ORDER.slice();
    for (const k of Object.keys(grouped).sort()) if (!out.includes(k)) out.push(k);
    return out;
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
    const me = await evalApi.me();
    setRaterId(me.raterId);
    const wfs = await evalApi.listWorkflowVersions();
    setWorkflows(wfs || []);
    if (wfs && wfs.length > 0) {
      setActiveCategory(wfs[0].category || 'general');
    }
    await refreshMetrics();
  };

  const loadRunsForTool = async (workflowVersionId: string) => {
    const resp = await evalApi.listRunsWithLatestAnnotation({
      workflow_version_id: workflowVersionId,
      status: filterStatus !== 'all' ? filterStatus : undefined,
      unrated: filterUnrated,
      limit: 80,
      offset: 0,
    });
    setRuns((resp.items || []) as RunWithLatest[]);
  };

  const loadTasks = async () => {
    const resp = await evalApi.listRunsWithLatestAnnotation({ limit: 80, offset: 0 });
    setRuns((resp.items || []) as RunWithLatest[]);
  };

  useEffect(() => {
    void loadBootstrap();
  }, []);

  useEffect(() => {
    if (activeView !== 'tool' || !selectedTool) return;
    void loadRunsForTool(selectedTool.id);
    const timer = window.setInterval(() => {
      const hasPending = runs.some((r) => r.status === 'queued' || r.status === 'running');
      if (hasPending) void loadRunsForTool(selectedTool.id);
    }, 2000);
    return () => window.clearInterval(timer);
  }, [activeView, selectedTool?.id, filterStatus, filterUnrated, runs]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (activeView !== 'tasks') return;
    void loadTasks();
    const timer = window.setInterval(() => void loadTasks(), 2000);
    return () => window.clearInterval(timer);
  }, [activeView]);

  const openTool = (wf: EvalWorkflowVersion) => {
    setSelectedTool(wf);
    setFormUrl('');
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
    if (!formUrl.trim()) return;
    setIsRunning(true);
    try {
      const parameters: Record<string, unknown> = { url: formUrl.trim() };
      for (const [k, v] of Object.entries(formParams)) {
        if (v === '') continue;
        parameters[k] = v;
      }
      await evalApi.createRun({
        workflow_version_id: selectedTool.id,
        input_oss_urls_json: [formUrl.trim()],
        parameters_json: parameters,
      });
      await loadRunsForTool(selectedTool.id);
      await refreshMetrics();
    } finally {
      setIsRunning(false);
    }
  };

  const annotate = async (runId: string, rating: number, comment: string) => {
    await evalApi.createAnnotation(runId, { rating, comment: comment.trim() || undefined });
    await refreshMetrics();
    if (selectedTool) await loadRunsForTool(selectedTool.id);
  };

  const filteredRuns = useMemo(() => {
    let out = runs.slice();
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
  }, [runs, filterRating, search]);

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
          <div className="ml-2 text-xs text-slate-400">
            raterId: <span className="font-mono text-slate-200">{raterId || '...'}</span>
          </div>
        </div>
      </div>
    </header>
  );

  if (activeView === 'tasks') {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-50">
        {header}
        <div className="mx-auto max-w-[1400px] px-6 py-6">
          <TaskTable runs={runs} workflowMap={workflowMap} />
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
                <span className="rounded-full bg-slate-800/60 px-2 py-0.5">{CATEGORY_LABELS[selectedTool.category] ?? selectedTool.category}</span>
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
                  <input
                    value={formUrl}
                    onChange={(e) => setFormUrl(e.target.value)}
                    placeholder="https://podi.oss-.../xxx.jpg"
                    className="mt-1 w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-600"
                  />
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
              <div className="mt-3 text-xs text-slate-400">点击图片可打开原图；下方历史可筛选/打标。</div>
              <div className="mt-4 grid gap-3 lg:grid-cols-3">
                {(filteredRuns[0]?.result_image_urls_json || []).map((img, idx) => (
                  <a key={`latest-${idx}`} href={img} target="_blank" rel="noreferrer" className="block rounded-2xl border border-slate-800 bg-slate-950/30 p-2 hover:border-slate-700">
                    <img src={img} alt="latest" className="h-56 w-full rounded-xl object-contain" />
                  </a>
                ))}
                {(!filteredRuns[0] || (filteredRuns[0].result_image_urls_json || []).length === 0) && (
                  <div className="text-sm text-slate-500">暂无结果（先在左侧运行一次）。</div>
                )}
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
                    <HistoryRow key={run.id} run={run} onAnnotate={annotate} />
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
                  <div className="text-sm font-semibold">{CATEGORY_LABELS[cat] ?? cat}</div>
                  <div className="text-xs text-slate-500">{(grouped[cat] || []).length} 个功能</div>
                </button>
              );
            })}
          </div>
        </aside>

        <main>
          <div className="mb-4">
            <div className="text-lg font-semibold">{CATEGORY_LABELS[activeCategory] ?? activeCategory}</div>
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
}: {
  run: RunWithLatest;
  onAnnotate: (runId: string, rating: number, comment: string) => Promise<void>;
}) {
  const inputUrl = (run.input_oss_urls_json || [])[0] || '';
  const outputs = run.result_image_urls_json || [];
  const [rating, setRating] = useState<number>(run.latest_annotation?.rating || 0);
  const [comment, setComment] = useState<string>(String(run.latest_annotation?.comment || ''));
  const [submitting, setSubmitting] = useState(false);

  const submit = async () => {
    if (!rating) return;
    setSubmitting(true);
    try {
      await onAnnotate(run.id, rating, comment);
    } finally {
      setSubmitting(false);
    }
  };

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
                  onClick={() => setRating(n)}
                  className={`h-9 w-9 rounded-xl border text-sm transition ${
                    active ? 'border-amber-400/80 bg-amber-400/20 text-amber-200' : 'border-slate-800 bg-slate-950 text-slate-200 hover:border-slate-700'
                  }`}
                >
                  {n}
                </button>
              );
            })}
          </div>
          <button
            type="button"
            disabled={!rating || submitting}
            onClick={() => void submit()}
            className={`rounded-xl px-3 py-2 text-xs font-semibold transition ${
              !rating || submitting ? 'bg-slate-700/40 text-slate-400' : 'bg-emerald-500/80 text-white hover:bg-emerald-500'
            }`}
          >
            {submitting ? '提交中…' : '提交'}
          </button>
        </div>
      </div>

      <div className="mt-3 grid gap-3 lg:grid-cols-[220px_1fr]">
        <div>
          <div className="text-xs text-slate-500 mb-1">备注（可选）</div>
          <textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            rows={3}
            className="w-full rounded-xl border border-slate-800 bg-slate-950 p-3 text-sm text-slate-100"
            placeholder="问题描述/优化建议…"
          />
        </div>
        <div>
          <div className="text-xs text-slate-500 mb-1">原图 / 结果</div>
          <div className="grid gap-2 lg:grid-cols-4">
            {inputUrl ? (
              <a href={inputUrl} target="_blank" rel="noreferrer" className="block rounded-xl border border-slate-800 bg-slate-950/30 p-1 hover:border-slate-700">
                <img src={inputUrl} alt="input" className="h-32 w-full rounded-lg object-contain" />
              </a>
            ) : null}
            {outputs.length > 0 ? (
              outputs.map((u, idx) => (
                <a key={`${run.id}-out-${idx}`} href={u} target="_blank" rel="noreferrer" className="block rounded-xl border border-slate-800 bg-slate-950/30 p-1 hover:border-slate-700">
                  <img src={u} alt="output" className="h-32 w-full rounded-lg object-contain" />
                </a>
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
