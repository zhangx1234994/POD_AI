import type { EvalWorkflowVersion } from '../../../types/eval';

type Props = {
  workflows: EvalWorkflowVersion[];
  selectedWorkflow: EvalWorkflowVersion | null;
  onWorkflowSelect: (workflow: EvalWorkflowVersion) => void;
};

export function EvaluationSidebar({ workflows, selectedWorkflow, onWorkflowSelect }: Props) {
  const grouped = workflows.reduce<Record<string, EvalWorkflowVersion[]>>((acc, wf) => {
    const key = wf.category || 'uncategorized';
    acc[key] = acc[key] || [];
    acc[key].push(wf);
    return acc;
  }, {});

  const categories = Object.keys(grouped).sort();

  return (
    <aside className="w-72 border-r border-slate-800 bg-slate-950/40 p-4 overflow-y-auto">
      <div className="mb-3">
        <div className="text-sm font-semibold text-slate-100">能力分组</div>
        <div className="text-xs text-slate-400">选择一个工作流版本进行评测</div>
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

