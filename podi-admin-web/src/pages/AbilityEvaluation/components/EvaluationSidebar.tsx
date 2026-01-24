import type { EvalWorkflowVersion } from '../../../types/eval';

type Props = {
  workflows: EvalWorkflowVersion[];
  selectedWorkflow: EvalWorkflowVersion | null;
  onWorkflowSelect: (workflow: EvalWorkflowVersion) => void;
  onCreateWorkflow?: () => void;
  onRefreshWorkflows?: () => void;
};

export function EvaluationSidebar({ workflows, selectedWorkflow, onWorkflowSelect, onCreateWorkflow, onRefreshWorkflows }: Props) {
  const normalizeCategory = (category: string | undefined | null): string => {
    const c = String(category || '').trim();
    if (c === '花纹提取类' || c === '图延伸类' || c === '四方/两方连续图类' || c === '图裂变' || c === '通用类') return c;
    if (c === 'pattern_extract' || c === 'pattern') return '花纹提取类';
    if (c === 'image_extend' || c === '图扩展' || c === '图延伸') return '图延伸类';
    if (c === 'continuous') return '四方/两方连续图类';
    if (c === '图裂变' || c === 'variation' || c === 'image_variation' || c === 'liebain' || c === 'liebiam') return '图裂变';
    if (c === 'general' || c === 'common') return '通用类';
    return '通用类';
  };

  const grouped = workflows.reduce<Record<string, EvalWorkflowVersion[]>>((acc, wf) => {
    const key = normalizeCategory(wf.category);
    acc[key] = acc[key] || [];
    acc[key].push(wf);
    return acc;
  }, {});

  const categories = ['花纹提取类', '图延伸类', '四方/两方连续图类', '图裂变', '通用类'].filter((c) => (grouped[c] || []).length > 0);

  return (
    <aside className="w-72 border-r border-slate-800 bg-slate-950/40 p-4 overflow-y-auto">
      <div className="mb-3">
        <div className="flex items-center justify-between gap-2">
          <div>
            <div className="text-sm font-semibold text-slate-100">能力分组</div>
            <div className="text-xs text-slate-400">选择一个工作流版本进行评测</div>
          </div>
          <div className="flex items-center gap-2">
            {typeof onRefreshWorkflows === 'function' ? (
              <button
                type="button"
                onClick={onRefreshWorkflows}
                className="rounded-lg border border-slate-800 bg-slate-950 px-2 py-1 text-xs text-slate-200 hover:border-slate-700"
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
            <div className="mb-2 text-xs uppercase tracking-widest text-slate-500">{cat}</div>
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
                          ? 'border-sky-500/70 bg-sky-500/10 text-white'
                          : 'border-white/5 bg-transparent text-slate-300 hover:border-slate-500/60'
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <div className="text-sm font-semibold">{wf.name}</div>
                        <div className="text-[11px] text-slate-400">{wf.version}</div>
                      </div>
                      {wf.notes ? <div className="mt-1 text-xs text-slate-500 line-clamp-2">{wf.notes}</div> : null}
                      <div className="mt-1 text-xs text-slate-400 break-all">{wf.workflow_id}</div>
                    </button>
                  );
                })}
            </div>
          </div>
        ))}
        {workflows.length === 0 && <div className="text-sm text-slate-500">暂无工作流版本，请先在后端录入。</div>}
      </div>
    </aside>
  );
}
