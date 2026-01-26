import { useMemo, useState } from 'react';
import type { EvalRun } from '../../../types/eval';

type Props = {
  results: EvalRun[];
  onAnnotate: (runId: string, payload: { rating: number; comment?: string }) => Promise<void> | void;
};

const formatDuration = (ms?: number | null) => {
  if (!ms) return '—';
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
};

export function EvaluationResultPanel({ results, onAnnotate }: Props) {
  const sorted = useMemo(
    () => results.slice().sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()),
    [results],
  );
  const [ratings, setRatings] = useState<Record<string, number>>({});
  const [comments, setComments] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState<Record<string, boolean>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});

  const submit = async (runId: string) => {
    const rating = ratings[runId];
    if (!rating) {
      setErrors((prev) => ({ ...prev, [runId]: '请先选择评分（1-5）' }));
      return;
    }
    setSubmitting((prev) => ({ ...prev, [runId]: true }));
    setErrors((prev) => ({ ...prev, [runId]: '' }));
    try {
      await onAnnotate(runId, { rating, comment: comments[runId] || undefined });
    } catch (err) {
      console.error(err);
      setErrors((prev) => ({ ...prev, [runId]: String((err as any)?.message || err) }));
    } finally {
      setSubmitting((prev) => ({ ...prev, [runId]: false }));
    }
  };

  return (
    <div className="flex-1 overflow-y-auto p-4">
      <div className="mb-3 flex items-end justify-between">
        <div>
          <div className="text-sm font-semibold text-slate-900 dark:text-slate-100">结果与打分</div>
          <div className="text-xs text-slate-700 dark:text-slate-400">评分 1-5，备注可选；结果会写入 MySQL。</div>
        </div>
        <div className="text-xs text-slate-700 dark:text-slate-500">最近 {sorted.length} 条</div>
      </div>

      <div className="space-y-4">
        {sorted.map((run) => {
          const status = run.status;
          const images = run.result_image_urls_json || [];
          const hasImages = images.length > 0;
          return (
            <div key={run.id} className="rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-950/40">
              <div className="flex flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
                <div>
                  <div className="text-xs text-slate-600 dark:text-slate-500">Run</div>
                  <div className="break-all text-sm font-semibold text-slate-900 dark:text-slate-100">{run.id}</div>
                  <div className="mt-1 flex flex-wrap items-center gap-3 text-xs text-slate-700 dark:text-slate-400">
                    <span className="rounded-full bg-slate-100 px-2 py-0.5 text-slate-700 dark:bg-slate-800/60 dark:text-slate-300">{status}</span>
                    <span>耗时：{formatDuration(run.duration_ms)}</span>
                    {run.podi_task_id ? <span>task: {run.podi_task_id}</span> : null}
                    {run.coze_debug_url ? (
                      <a className="text-sky-400 underline" href={run.coze_debug_url} target="_blank" rel="noreferrer">
                        debug_url
                      </a>
                    ) : null}
                  </div>
                  {run.error_message ? <div className="mt-2 text-xs text-rose-700 dark:text-rose-400">{run.error_message}</div> : null}
                </div>
                <div className="flex items-center gap-2">
                  <div className="text-xs text-slate-700 dark:text-slate-400">评分</div>
                  <div className="flex gap-1">
                    {[1, 2, 3, 4, 5].map((n) => (
                      <button
                        key={`${run.id}-rating-${n}`}
                        type="button"
                        onClick={() => setRatings((prev) => ({ ...prev, [run.id]: n }))}
                        className={`h-8 w-8 rounded-lg border text-sm transition ${
                          (ratings[run.id] || 0) === n
                            ? 'border-amber-500 bg-amber-100 text-amber-900 dark:border-amber-400/80 dark:bg-amber-400/20 dark:text-amber-200'
                            : 'border-slate-300 bg-white text-slate-700 hover:bg-slate-50 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-300 dark:hover:border-slate-700'
                        }`}
                      >
                        {n}
                      </button>
                    ))}
                  </div>
                  <button
                    type="button"
                    disabled={!ratings[run.id] || submitting[run.id]}
                    onClick={() => void submit(run.id)}
                    className={`rounded-lg px-3 py-2 text-xs font-semibold transition ${
                      !ratings[run.id] || submitting[run.id]
                        ? 'bg-slate-200 text-slate-500 dark:bg-slate-700/40 dark:text-slate-400'
                        : 'bg-emerald-600 text-white hover:bg-emerald-500'
                    }`}
                  >
                    {submitting[run.id] ? '提交中…' : '提交'}
                  </button>
                </div>
              </div>
              {errors[run.id] ? <div className="mt-2 text-xs text-rose-700 dark:text-rose-300">{errors[run.id]}</div> : null}

              <div className="mt-3 grid gap-3 lg:grid-cols-2">
                <div>
                  <div className="mb-1 text-xs text-slate-600 dark:text-slate-500">备注（可选）</div>
                  <textarea
                    value={comments[run.id] || ''}
                    onChange={(e) => setComments((prev) => ({ ...prev, [run.id]: e.target.value }))}
                    rows={3}
                    className="w-full rounded-xl border border-slate-300 bg-white p-3 text-sm text-slate-900 placeholder:text-slate-400 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100 dark:placeholder:text-slate-600"
                    placeholder="问题描述/优化建议…"
                  />
                </div>
                <div>
                  <div className="mb-1 text-xs text-slate-600 dark:text-slate-500">输出图片</div>
                  {hasImages ? (
                    <div className="grid grid-cols-2 gap-2">
                      {images.map((imgUrl, idx) => (
                        <a
                          key={`${run.id}-img-${idx}`}
                          href={imgUrl}
                          target="_blank"
                          rel="noreferrer"
                          className="block rounded-xl border border-slate-200 bg-slate-50 p-1 hover:border-slate-300 dark:border-slate-800 dark:bg-slate-950/30 dark:hover:border-slate-700"
                        >
                          <img src={imgUrl} alt={`result ${idx + 1}`} className="h-40 w-full rounded-lg object-contain" />
                        </a>
                      ))}
                    </div>
                  ) : (
                    <div className="text-sm text-slate-700 dark:text-slate-500">
                      {status === 'running' || status === 'queued' ? '等待生成中…' : '暂无输出'}
                    </div>
                  )}
                </div>
              </div>
            </div>
          );
        })}
        {sorted.length === 0 && <div className="text-sm text-slate-700 dark:text-slate-500">暂无运行记录。</div>}
      </div>
    </div>
  );
}
