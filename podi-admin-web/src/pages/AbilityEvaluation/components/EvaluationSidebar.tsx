import type { EvalWorkflowVersion } from '../../../types/eval';
import { evalBusinessCategoryOrder, normalizeEvalBusinessCategory } from '../evalBusinessCategories';

type Props = {
  workflows: EvalWorkflowVersion[];
  selectedWorkflow: EvalWorkflowVersion | null;
  onWorkflowSelect: (workflow: EvalWorkflowVersion) => void;
  onCreateWorkflow?: () => void;
  onRefreshWorkflows?: () => void;
};

export function EvaluationSidebar({ workflows, selectedWorkflow, onWorkflowSelect, onCreateWorkflow, onRefreshWorkflows }: Props) {
  const grouped = workflows.reduce<Record<string, EvalWorkflowVersion[]>>((acc, wf) => {
    const key = normalizeEvalBusinessCategory(wf.category);
    acc[key] = acc[key] || [];
    acc[key].push(wf);
    return acc;
  }, {});

  const categories = evalBusinessCategoryOrder.filter((c) => (grouped[c] || []).length > 0);

  return (
    <aside className="w-72 overflow-y-auto border-r border-slate-200 bg-white/70 p-4 dark:border-slate-800 dark:bg-slate-950/40">
      <div className="mb-3">
        <div className="flex items-center justify-between gap-2">
          <div>
            <div className="text-sm font-semibold text-slate-900 dark:text-slate-100">业务分组</div>
            <div className="text-xs text-slate-700 dark:text-slate-400">先选业务，再进入评测版本</div>
          </div>
          <div className="flex items-center gap-2">
            {typeof onRefreshWorkflows === 'function' ? (
              <button
                type="button"
                onClick={onRefreshWorkflows}
                className="rounded-lg border border-slate-300 bg-white px-2 py-1 text-xs text-slate-700 hover:bg-slate-50 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-200 dark:hover:border-slate-700"
              >
                刷新
              </button>
            ) : null}
            {typeof onCreateWorkflow === 'function' ? (
              <button
                type="button"
                onClick={onCreateWorkflow}
                className="rounded-lg bg-sky-500/80 px-2 py-1 text-xs font-semibold text-white hover:bg-sky-500"
              >
                新增
              </button>
            ) : null}
          </div>
        </div>
      </div>
      <div className="space-y-4">
        {categories.map((cat) => (
          <div key={cat}>
            <div className="mb-2 text-xs font-semibold tracking-wide text-slate-600 dark:text-slate-500">{cat}</div>
            <div className="space-y-2">
              {grouped[cat]
                .slice()
                .sort((a, b) => a.name.localeCompare(b.name))
                .map((wf) => {
                  const active = selectedWorkflow?.id === wf.id;
                  return (
                    <button
                      key={wf.id}
                      type="button"
                      onClick={() => onWorkflowSelect(wf)}
                      className={`w-full rounded-xl border px-3 py-2 text-left transition ${
                        active
                          ? 'border-sky-500/60 bg-sky-500/10 text-slate-900 dark:text-white'
                          : 'border-slate-200/70 bg-transparent text-slate-800 hover:border-slate-300 dark:border-white/5 dark:text-slate-300 dark:hover:border-slate-500/60'
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <div className="text-sm font-semibold text-slate-900 dark:text-slate-100">{wf.name}</div>
                        <div className="text-[11px] text-slate-700 dark:text-slate-400">{wf.version}</div>
                      </div>
                      {wf.notes ? <div className="mt-1 text-xs text-slate-700 line-clamp-2 dark:text-slate-500">{wf.notes}</div> : null}
                      <details className="mt-1 text-xs text-slate-700 dark:text-slate-400" onClick={(event) => event.stopPropagation()}>
                        <summary className="cursor-pointer list-none">查看工作流 ID</summary>
                        <div className="mt-1 break-all">{wf.workflow_id}</div>
                      </details>
                    </button>
                  );
                })}
            </div>
          </div>
        ))}
        {workflows.length === 0 && <div className="text-sm text-slate-700 dark:text-slate-500">暂无工作流版本，请先在后端录入。</div>}
      </div>
    </aside>
  );
}
