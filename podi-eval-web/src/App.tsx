import { useEffect, useMemo, useState } from 'react';
import { evalApi } from './api';
import type { EvalRun, EvalWorkflowVersion, SchemaField } from './types';

const CATEGORY_LABELS: Record<string, string> = {
  pattern_extract: '花纹提取类',
  image_extend: '图延伸类',
  continuous_pattern: '四方/两方连续图类',
  image_variation: '图略变类',
  general: '通用类',
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

export function App() {
  const [raterId, setRaterId] = useState<string>('');
  const [workflows, setWorkflows] = useState<EvalWorkflowVersion[]>([]);
  const [selected, setSelected] = useState<EvalWorkflowVersion | null>(null);
  const [activeCategory, setActiveCategory] = useState<string>('general');
  const [activeView, setActiveView] = useState<'toolbox' | 'tasks'>('toolbox');
  const [params, setParams] = useState<Record<string, any>>({});
  const [url, setUrl] = useState<string>('');
  const [runs, setRuns] = useState<EvalRun[]>([]);
  const [loading, setLoading] = useState(false);
  const [onlyUnrated, setOnlyUnrated] = useState(false);
  const [draftRatings, setDraftRatings] = useState<Record<string, number>>({});
  const [draftComments, setDraftComments] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState<Record<string, boolean>>({});
  const [workflowMetrics, setWorkflowMetrics] = useState<Record<string, { ratingCount: number; avgRating: number | null }>>({});

  const fields = useMemo(() => getFields(selected), [selected]);
  const grouped = useMemo(() => {
    const map: Record<string, EvalWorkflowVersion[]> = {};
    for (const wf of workflows) {
      const key = wf.category || 'general';
      map[key] = map[key] || [];
      map[key].push(wf);
    }
    return map;
  }, [workflows]);
  const categories = useMemo(() => Object.keys(grouped).sort(), [grouped]);
  const workflowMap = useMemo(() => {
    const m: Record<string, EvalWorkflowVersion> = {};
    for (const wf of workflows) m[wf.id] = wf;
    return m;
  }, [workflows]);

  const refreshRuns = async (workflowVersionId: string) => {
    const res = await evalApi.listRuns({ workflow_version_id: workflowVersionId, limit: 50, offset: 0, unrated: onlyUnrated });
    setRuns(res.items || []);
  };

  useEffect(() => {
    (async () => {
      const me = await evalApi.me();
      setRaterId(me.raterId);
      const wfs = await evalApi.listWorkflowVersions();
      setWorkflows(wfs || []);
      const metrics = await evalApi.workflowMetrics().catch(() => ({ metrics: {} }));
      setWorkflowMetrics(metrics.metrics || {});
      if (wfs && wfs.length > 0) {
        // Default to the first category with workflows; otherwise keep "general".
        const first = wfs[0];
        setActiveCategory(first.category || 'general');
        setSelected(first);
      }
    })().catch((err) => console.error(err));
  }, []);

  useEffect(() => {
    if (!selected) return;
    setParams({});
    setUrl('');
    void refreshRuns(selected.id);
  }, [selected?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!selected) return;
    void refreshRuns(selected.id);
  }, [onlyUnrated]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!selected) return;
    const timer = window.setInterval(() => {
      const hasPending = runs.some((r) => r.status === 'queued' || r.status === 'running');
      if (hasPending) void refreshRuns(selected.id);
    }, 2000);
    return () => window.clearInterval(timer);
  }, [selected?.id, runs]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (activeView !== 'tasks') return;
    const timer = window.setInterval(() => {
      void evalApi
        .listRuns({ limit: 80, offset: 0 })
        .then((res) => setRuns(res.items || []))
        .catch((err) => console.error(err));
    }, 2000);
    return () => window.clearInterval(timer);
  }, [activeView]);

  const runOnce = async () => {
    if (!selected) return;
    if (!url.trim()) return;
    setLoading(true);
    try {
      const payloadParams = { ...params, url: url.trim() };
      const run = await evalApi.createRun({
        workflow_version_id: selected.id,
        input_oss_urls_json: [url.trim()],
        parameters_json: payloadParams,
      });
      setRuns((prev) => [run, ...prev]);
      await refreshRuns(selected.id);
    } finally {
      setLoading(false);
    }
  };

  const annotate = async (runId: string) => {
    const rating = draftRatings[runId];
    if (!rating) return;
    const comment = (draftComments[runId] || '').trim() || undefined;
    setSubmitting((prev) => ({ ...prev, [runId]: true }));
    try {
      await evalApi.createAnnotation(runId, { rating, comment });
      // refresh metrics + runs
      const metrics = await evalApi.workflowMetrics().catch(() => ({ metrics: {} }));
      setWorkflowMetrics(metrics.metrics || {});
      if (selected) await refreshRuns(selected.id);
    } finally {
      setSubmitting((prev) => ({ ...prev, [runId]: false }));
    }
  };

  const toolboxWorkflows = grouped[activeCategory] || [];
  const selectedMetrics = selected ? workflowMetrics[selected.id] : undefined;
  const docCurl = useMemo(() => {
    if (!selected) return '';
    const paramsExample: Record<string, unknown> = {};
    for (const f of getFields(selected)) {
      if (f.name === 'url') {
        paramsExample.url = 'https://...';
        continue;
      }
      if (Array.isArray((f as any).options) && (f as any).options.length > 0) {
        paramsExample[f.name] = String((f as any).options[0].value);
      } else if (typeof (f as any).defaultValue === 'string') {
        paramsExample[f.name] = (f as any).defaultValue;
      } else {
        paramsExample[f.name] = '';
      }
    }
    return [
      'curl -X POST "$COZE_BASE_URL/v1/workflow/run" \\',
      '  -H "Authorization: Bearer $COZE_API_TOKEN" \\',
      '  -H "Content-Type: application/json" \\',
      `  -d '${JSON.stringify({ workflow_id: selected.workflow_id, parameters: paramsExample }, null, 2)}'`,
    ].join('\n');
  }, [selected]);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-50">
      <header className="border-b border-slate-800 bg-slate-900/40">
        <div className="mx-auto max-w-[1400px] px-6 py-4 flex items-center justify-between">
          <div>
            <div className="text-lg font-semibold">PODI · 能力评测</div>
            <div className="text-xs text-slate-400">无需登录 · 试运行 + 打分 + 备注（写入 MySQL）</div>
          </div>
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setActiveView('toolbox')}
              className={`rounded-xl px-3 py-2 text-xs font-semibold transition ${
                activeView === 'toolbox' ? 'bg-sky-500/20 text-sky-200 border border-sky-500/40' : 'bg-slate-950 border border-slate-800 text-slate-300 hover:border-slate-700'
              }`}
            >
              工具箱
            </button>
            <button
              type="button"
              onClick={async () => {
                setActiveView('tasks');
                const res = await evalApi.listRuns({ limit: 80, offset: 0 }).catch(() => ({ total: 0, items: [] as EvalRun[] }));
                setRuns(res.items || []);
              }}
              className={`rounded-xl px-3 py-2 text-xs font-semibold transition ${
                activeView === 'tasks' ? 'bg-sky-500/20 text-sky-200 border border-sky-500/40' : 'bg-slate-950 border border-slate-800 text-slate-300 hover:border-slate-700'
              }`}
            >
              任务管理
            </button>
            <div className="text-xs text-slate-400">
              raterId: <span className="font-mono text-slate-200">{raterId || '...'}</span>
            </div>
          </div>
        </div>
      </header>

      {activeView === 'tasks' ? (
        <div className="mx-auto max-w-[1400px] px-6 py-6">
          <div className="rounded-3xl border border-slate-800 bg-slate-900/30 p-5">
            <div className="flex items-end justify-between">
              <div>
                <div className="text-lg font-semibold">任务管理</div>
                <div className="text-xs text-slate-400">实时刷新：queued/running 会持续轮询。ComfyUI 类任务：回调解析到图片后才算完成。</div>
              </div>
              <div className="text-xs text-slate-500">最近 {runs.length} 条</div>
            </div>
            <div className="mt-4 space-y-3">
              {runs.map((run) => {
                const wf = workflowMap[run.workflow_version_id];
                const images = run.result_image_urls_json || [];
                return (
                  <div key={run.id} className="rounded-2xl border border-slate-800 bg-slate-950/40 p-4">
                    <div className="flex flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
                      <div>
                        <div className="text-sm font-semibold">{wf ? wf.name : run.workflow_version_id}</div>
                        <div className="mt-1 flex flex-wrap items-center gap-3 text-xs text-slate-400">
                          <span className="rounded-full bg-slate-800/60 px-2 py-0.5">{run.status}</span>
                          <span>耗时：{formatDuration(run.duration_ms)}</span>
                          {run.podi_task_id ? <span>task: {run.podi_task_id}</span> : null}
                          {run.coze_debug_url ? (
                            <a className="text-sky-400 underline" href={run.coze_debug_url} target="_blank" rel="noreferrer">
                              debug_url
                            </a>
                          ) : null}
                        </div>
                        {run.error_message ? <div className="mt-2 text-xs text-rose-400">{run.error_message}</div> : null}
                      </div>
                      <div className="text-xs text-slate-400">{new Date(run.created_at).toLocaleString()}</div>
                    </div>
                    <div className="mt-3 grid gap-2 lg:grid-cols-6">
                      {(run.input_oss_urls_json || []).slice(0, 2).map((u, idx) => (
                        <a key={`${run.id}-in-${idx}`} href={u} target="_blank" rel="noreferrer" className="block rounded-xl border border-slate-800 bg-slate-950/30 p-1">
                          <img src={u} alt="input" className="h-24 w-full rounded-lg object-contain" />
                        </a>
                      ))}
                      {images.slice(0, 4).map((u, idx) => (
                        <a key={`${run.id}-out-${idx}`} href={u} target="_blank" rel="noreferrer" className="block rounded-xl border border-slate-800 bg-slate-950/30 p-1">
                          <img src={u} alt="output" className="h-24 w-full rounded-lg object-contain" />
                        </a>
                      ))}
                      {images.length === 0 ? <div className="text-sm text-slate-500">{run.status === 'running' || run.status === 'queued' ? '生成中…' : '暂无输出'}</div> : null}
                    </div>
                  </div>
                );
              })}
              {runs.length === 0 && <div className="text-sm text-slate-500">暂无任务。</div>}
            </div>
          </div>
        </div>
      ) : (
        <div className="mx-auto max-w-[1400px] px-6 py-6 flex gap-6">
          <aside className="w-64 shrink-0 rounded-3xl border border-slate-800 bg-slate-900/30 p-4">
            <div className="text-sm font-semibold">分类</div>
            <div className="mt-1 text-xs text-slate-400">五类工具箱</div>
            <div className="mt-4 space-y-2">
              {categories.map((cat) => {
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

          <aside className="w-96 shrink-0 rounded-3xl border border-slate-800 bg-slate-900/30 p-4 overflow-y-auto max-h-[calc(100vh-120px)]">
            <div className="text-sm font-semibold">功能</div>
            <div className="mt-1 text-xs text-slate-400">点击功能开始测试与打标</div>
            <div className="mt-4 space-y-2">
              {toolboxWorkflows
                .slice()
                .sort((a, b) => a.name.localeCompare(b.name))
                .map((wf) => {
                  const active = selected?.id === wf.id;
                  const m = workflowMetrics[wf.id];
                  return (
                    <button
                      key={wf.id}
                      type="button"
                      onClick={() => setSelected(wf)}
                      className={`w-full rounded-2xl border px-3 py-2 text-left transition ${
                        active ? 'border-sky-500/70 bg-sky-500/10' : 'border-white/5 hover:border-slate-500/60'
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <div className="text-sm font-semibold">{wf.name}</div>
                        {m?.avgRating ? (
                          <div className="text-[11px] text-amber-200">{m.avgRating.toFixed(2)} / 5</div>
                        ) : (
                          <div className="text-[11px] text-slate-500">未评分</div>
                        )}
                      </div>
                      <div className="mt-1 text-[11px] text-slate-500 break-all">{wf.workflow_id}</div>
                      {m?.ratingCount ? <div className="mt-1 text-[11px] text-slate-500">样本：{m.ratingCount}</div> : null}
                    </button>
                  );
                })}
              {toolboxWorkflows.length === 0 && <div className="text-sm text-slate-500">该分类暂无功能。</div>}
            </div>
          </aside>

        <main className="flex-1 space-y-6">
          <section className="rounded-3xl border border-slate-800 bg-slate-900/30 p-5">
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="text-lg font-semibold">{selected ? selected.name : '请选择工作流'}</div>
                <div className="mt-1 text-xs text-slate-400">{selected?.notes || '—'}</div>
                {selectedMetrics?.avgRating ? (
                  <div className="mt-2 text-xs text-amber-200">综合评分：{selectedMetrics.avgRating.toFixed(2)} / 5（{selectedMetrics.ratingCount} 票）</div>
                ) : (
                  <div className="mt-2 text-xs text-slate-500">综合评分：暂无</div>
                )}
              </div>
              <div className="flex items-center gap-3">
                <label className="flex items-center gap-2 text-xs text-slate-300">
                  <input
                    type="checkbox"
                    checked={onlyUnrated}
                    onChange={(e) => setOnlyUnrated(e.target.checked)}
                    className="h-4 w-4 rounded border-slate-700 bg-slate-950"
                  />
                  只看未打分
                </label>
                <button
                  type="button"
                  onClick={() => selected && refreshRuns(selected.id)}
                  className="rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-slate-200 hover:border-slate-500"
                >
                  刷新
                </button>
              </div>
            </div>

            <div className="mt-4 grid gap-4 lg:grid-cols-2">
              <div className="rounded-2xl border border-slate-800 bg-slate-950/40 p-4">
                <div className="text-sm font-semibold">输入</div>
                <div className="mt-3">
                  <div className="text-xs text-slate-400 mb-1">图片 URL（字段名固定为 url）</div>
                  <input
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                    placeholder="https://podi.oss-.../xxx.jpg"
                    className="w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-600"
                  />
                </div>
                {url && (
                  <div className="mt-3">
                    <div className="text-xs text-slate-500 mb-1">预览</div>
                    <img src={url} alt="input" className="max-h-72 w-full rounded-xl border border-slate-800 object-contain" />
                  </div>
                )}
              </div>

              <div className="rounded-2xl border border-slate-800 bg-slate-950/40 p-4">
                <div className="text-sm font-semibold">参数</div>
                <div className="mt-2 text-xs text-slate-500">参数 schema 来自后端录入；没有 schema 的字段可后续补。</div>
                <div className="mt-3 rounded-xl border border-slate-800 bg-slate-950/50 p-3">
                  <div className="text-xs text-slate-400 mb-2">业务接入文档（Coze OpenAPI）</div>
                  <pre className="max-h-40 overflow-auto rounded-lg bg-slate-950 p-2 font-mono text-[11px] text-slate-200">{docCurl}</pre>
                </div>
                <div className="mt-3 space-y-3">
                  {fields
                    .filter((f) => f.name !== 'url')
                    .map((field) => {
                      const key = field.name;
                      const label = field.label ?? key;
                      const required = Boolean(field.required);
                      const value = (params as any)[key] ?? field.defaultValue ?? '';
                      const options = Array.isArray((field as any).options) ? ((field as any).options as any[]) : null;

                      if (options && options.length > 0) {
                        return (
                          <label key={key} className="block">
                            <div className="text-xs text-slate-300">
                              {label} {required ? <span className="text-rose-400">*</span> : null}
                            </div>
                            <select
                              value={String(value)}
                              onChange={(e) => setParams((prev) => ({ ...prev, [key]: e.target.value }))}
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

                      const isTextarea = (field.type || '').toLowerCase() === 'textarea';
                      if (isTextarea) {
                        return (
                          <label key={key} className="block">
                            <div className="text-xs text-slate-300">
                              {label} {required ? <span className="text-rose-400">*</span> : null}
                            </div>
                            <textarea
                              rows={4}
                              value={String(value)}
                              onChange={(e) => setParams((prev) => ({ ...prev, [key]: e.target.value }))}
                              className="mt-1 w-full rounded-xl border border-slate-800 bg-slate-950 p-3 text-sm text-slate-100"
                            />
                          </label>
                        );
                      }

                      return (
                        <label key={key} className="block">
                          <div className="text-xs text-slate-300">
                            {label} {required ? <span className="text-rose-400">*</span> : null}
                          </div>
                          <input
                            value={String(value)}
                            onChange={(e) => setParams((prev) => ({ ...prev, [key]: e.target.value }))}
                            className="mt-1 w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-sm text-slate-100"
                          />
                        </label>
                      );
                    })}
                  {fields.length <= 1 && <div className="text-xs text-slate-500">该工作流暂未录入更多参数 schema。</div>}
                </div>

                <div className="mt-4 flex justify-end">
                  <button
                    type="button"
                    disabled={!selected || !url.trim() || loading}
                    onClick={() => void runOnce()}
                    className={`rounded-xl px-4 py-2 text-sm font-semibold transition ${
                      !selected || !url.trim() || loading ? 'bg-slate-700/40 text-slate-400' : 'bg-sky-500/80 hover:bg-sky-500'
                    }`}
                  >
                    {loading ? '运行中…' : '开始评测'}
                  </button>
                </div>
              </div>
            </div>
          </section>

          <section className="rounded-3xl border border-slate-800 bg-slate-900/30 p-5">
            <div className="flex items-end justify-between">
              <div>
                <div className="text-sm font-semibold">结果列表</div>
                <div className="text-xs text-slate-400">等待中会自动轮询刷新；点击图片可打开原图。</div>
              </div>
              <div className="text-xs text-slate-500">共 {runs.length} 条</div>
            </div>
            <div className="mt-4 space-y-4">
              {runs.map((run) => {
                const images = run.result_image_urls_json || [];
                const inputUrl = (run.input_oss_urls_json || [])[0] || '';
                return (
                  <div key={run.id} className="rounded-2xl border border-slate-800 bg-slate-950/40 p-4">
                    <div className="flex flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
                      <div>
                        <div className="text-xs text-slate-500">Run</div>
                        <div className="text-sm font-semibold break-all">{run.id}</div>
                        <div className="mt-1 flex flex-wrap items-center gap-3 text-xs text-slate-400">
                          <span className="rounded-full bg-slate-800/60 px-2 py-0.5">{run.status}</span>
                          <span>耗时：{formatDuration(run.duration_ms)}</span>
                          {run.podi_task_id ? <span>task: {run.podi_task_id}</span> : null}
                          {run.coze_debug_url ? (
                            <a className="text-sky-400 underline" href={run.coze_debug_url} target="_blank" rel="noreferrer">
                              debug_url
                            </a>
                          ) : null}
                        </div>
                        {run.error_message ? <div className="mt-2 text-xs text-rose-400">{run.error_message}</div> : null}
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="flex items-center gap-1">
                          {[1, 2, 3, 4, 5].map((n) => {
                            const active = draftRatings[run.id] === n;
                            return (
                              <button
                                key={`${run.id}-r-${n}`}
                                type="button"
                                onClick={() => setDraftRatings((prev) => ({ ...prev, [run.id]: n }))}
                                className={`h-9 w-9 rounded-xl border text-sm transition ${
                                  active
                                    ? 'border-amber-400/80 bg-amber-400/20 text-amber-200'
                                    : 'border-slate-800 bg-slate-950 text-slate-200 hover:border-amber-400/70 hover:bg-amber-400/10'
                                }`}
                                title={`打分 ${n}`}
                              >
                                {n}
                              </button>
                            );
                          })}
                        </div>
                        <button
                          type="button"
                          disabled={!draftRatings[run.id] || submitting[run.id]}
                          onClick={() => void annotate(run.id)}
                          className={`rounded-xl px-3 py-2 text-xs font-semibold transition ${
                            !draftRatings[run.id] || submitting[run.id]
                              ? 'bg-slate-700/40 text-slate-400'
                              : 'bg-emerald-500/80 text-white hover:bg-emerald-500'
                          }`}
                        >
                          {submitting[run.id] ? '提交中…' : '提交'}
                        </button>
                      </div>
                    </div>
                    <div className="mt-3">
                      <div className="text-xs text-slate-500 mb-1">备注（可选）</div>
                      <textarea
                        value={draftComments[run.id] || ''}
                        onChange={(e) => setDraftComments((prev) => ({ ...prev, [run.id]: e.target.value }))}
                        rows={2}
                        className="w-full rounded-xl border border-slate-800 bg-slate-950 p-3 text-sm text-slate-100"
                        placeholder="问题描述/优化建议…"
                      />
                    </div>
                    <div className="mt-3 grid gap-2 lg:grid-cols-4">
                      {inputUrl ? (
                        <a
                          href={inputUrl}
                          target="_blank"
                          rel="noreferrer"
                          className="block rounded-xl border border-slate-800 bg-slate-950/30 p-1 hover:border-slate-700"
                        >
                          <img src={inputUrl} alt="input" className="h-40 w-full rounded-lg object-contain" />
                        </a>
                      ) : null}
                      {images.length > 0 ? (
                        images.map((img, idx) => (
                          <a
                            key={`${run.id}-img-${idx}`}
                            href={img}
                            target="_blank"
                            rel="noreferrer"
                            className="block rounded-xl border border-slate-800 bg-slate-950/30 p-1 hover:border-slate-700"
                          >
                            <img src={img} alt={`result ${idx + 1}`} className="h-40 w-full rounded-lg object-contain" />
                          </a>
                        ))
                      ) : (
                        <div className="text-sm text-slate-500">{run.status === 'running' || run.status === 'queued' ? '生成中…' : '暂无输出'}</div>
                      )}
                    </div>
                  </div>
                );
              })}
              {runs.length === 0 && <div className="text-sm text-slate-500">暂无记录。</div>}
            </div>
          </section>
        </main>
      </div>
      )}
    </div>
  );
}
