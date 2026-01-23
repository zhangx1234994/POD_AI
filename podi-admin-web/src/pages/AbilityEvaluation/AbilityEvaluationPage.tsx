import { useEffect, useMemo, useState } from 'react';
import { adminApi } from '../../services/adminApi';
import type { EvalDatasetItem, EvalRun, EvalWorkflowVersion } from '../../types/eval';
import { EvaluationInputPanel } from './components/EvaluationInputPanel';
import { EvaluationResultPanel } from './components/EvaluationResultPanel';
import { EvaluationSidebar } from './components/EvaluationSidebar';

type Notice = { type: 'error' | 'success' | 'info'; message: string };

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

export function AbilityEvaluationPage() {
  const [notice, setNotice] = useState<Notice | null>(null);
  const pushNotice = (n: Notice) => {
    setNotice(n);
    window.setTimeout(() => {
      setNotice((cur) => (cur?.message === n.message ? null : cur));
    }, 6500);
  };

  const [workflows, setWorkflows] = useState<EvalWorkflowVersion[]>([]);
  const [datasetItems, setDatasetItems] = useState<EvalDatasetItem[]>([]);
  const [selectedWorkflow, setSelectedWorkflow] = useState<EvalWorkflowVersion | null>(null);
  const [selectedDatasetItem, setSelectedDatasetItem] = useState<EvalDatasetItem | null>(null);
  const [inputImages, setInputImages] = useState<string[]>([]);
  const [parameters, setParameters] = useState<Record<string, any>>({});
  const [evaluationResults, setEvaluationResults] = useState<EvalRun[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const [isSavingWorkflowNotes, setIsSavingWorkflowNotes] = useState(false);
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [createError, setCreateError] = useState<string>('');
  const [isCreating, setIsCreating] = useState(false);
  const [createDraft, setCreateDraft] = useState<{
    name: string;
    category: string;
    version: string;
    workflow_id: string;
    outputKind: 'image' | 'callback';
    notes: string;
  }>({
    name: '',
    category: '通用类',
    version: 'v1',
    workflow_id: '',
    outputKind: 'image',
    notes: '',
  });
  const [createFields, setCreateFields] = useState<
    Array<{
      name: string;
      label: string;
      type: string;
      required: boolean;
      description: string;
      defaultValue: string;
      optionsText: string;
    }>
  >([
    {
      name: 'url',
      label: '图片 URL',
      type: 'text',
      required: true,
      description: '图片地址（OSS 或公网 URL）',
      defaultValue: '',
      optionsText: '',
    },
  ]);

  const activeCategory = selectedWorkflow?.category || '';
  const filteredDatasetItems = useMemo(
    () => (activeCategory ? datasetItems.filter((item) => item.category === activeCategory) : datasetItems),
    [datasetItems, activeCategory],
  );

  const refreshRuns = async (workflowId?: string) => {
    const wfId = workflowId ?? selectedWorkflow?.id;
    if (!wfId) return;
    try {
      const res = await adminApi.listEvalRuns({ workflow_version_id: wfId, limit: 50, offset: 0 });
      setEvaluationResults(res.items || []);
    } catch (err) {
      console.error(err);
      pushNotice({ type: 'error', message: String((err as any)?.message || err) });
    }
  };

  useEffect(() => {
    void refreshWorkflows();
  }, []);

  const refreshWorkflows = async () => {
    try {
      const wfs = await adminApi.listEvalWorkflowVersions({ status: 'active' });
      const normalized = (wfs || []).map((w) => ({ ...w, category: normalizeCategory(w.category) }));
      setWorkflows(normalized);
      if ((!selectedWorkflow || !wfs?.some((w) => w.id === selectedWorkflow.id)) && wfs && wfs.length > 0) {
        setSelectedWorkflow({ ...wfs[0], category: normalizeCategory(wfs[0].category) });
      }
    } catch (err) {
      console.error(err);
      pushNotice({ type: 'error', message: String((err as any)?.message || err) });
    }
  };

  useEffect(() => {
    (async () => {
      try {
        const items = await adminApi.listEvalDatasetItems(activeCategory ? { category: activeCategory } : undefined);
        setDatasetItems(items || []);
        if (items && items.length > 0) {
          setSelectedDatasetItem(items[0]);
          setInputImages([items[0].oss_url]);
        } else {
          setSelectedDatasetItem(null);
        }
      } catch (err) {
        console.error(err);
        pushNotice({ type: 'error', message: String((err as any)?.message || err) });
      }
    })();
  }, [activeCategory]);

  useEffect(() => {
    if (!selectedWorkflow) return;
    void refreshRuns(selectedWorkflow.id);
    const timer = window.setInterval(() => {
      const hasRunning = evaluationResults.some((r) => r.status === 'queued' || r.status === 'running');
      if (hasRunning) {
        void refreshRuns(selectedWorkflow.id);
      }
    }, 2000);
    return () => window.clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedWorkflow?.id, evaluationResults.length]);

  const handleWorkflowSelect = (workflow: EvalWorkflowVersion) => {
    setSelectedWorkflow({ ...workflow, category: normalizeCategory(workflow.category) });
    setParameters({});
    setInputImages([]);
    setSelectedDatasetItem(null);
    void refreshRuns(workflow.id);
  };

  const handleDatasetItemSelect = (datasetItem: EvalDatasetItem) => {
    setSelectedDatasetItem(datasetItem);
    setInputImages([datasetItem.oss_url]);
  };

  const handleImageChange = (url: string) => setInputImages([url]);

  const handleParameterChange = (newParameters: Record<string, any>) => {
    setParameters(newParameters);
  };

  const handleRunEvaluation = async () => {
    if (!selectedWorkflow) return;
    const url = inputImages[0];
    if (!url) {
      pushNotice({ type: 'error', message: '请先填写图片 URL 或选择样例' });
      return;
    }

    // Validate required fields from schema (except `prompt`: backend will fallback).
    const schema = (selectedWorkflow.parameters_schema || {}) as any;
    const fields = Array.isArray(schema?.fields) ? (schema.fields as any[]) : [];
    const missing: string[] = [];
    for (const f of fields) {
      if (!f || typeof f !== 'object') continue;
      if (!f.required) continue;
      const name = String(f.name || '');
      if (!name || name === 'url' || name === 'prompt') continue;
      const v = String((parameters as any)?.[name] ?? '').trim();
      if (!v) missing.push(String(f.label || name));
    }
    if (missing.length > 0) {
      pushNotice({ type: 'error', message: `请补齐必填参数：${missing.join('、')}` });
      return;
    }

    setIsRunning(true);
    try {
      const run = await adminApi.createEvalRun({
        workflow_version_id: selectedWorkflow.id,
        dataset_item_id: selectedDatasetItem?.id ?? null,
        input_oss_urls_json: [url],
        parameters_json: { ...parameters, url },
      });
      setEvaluationResults((prev) => [run, ...prev]);
      await refreshRuns(selectedWorkflow.id);
      pushNotice({ type: 'success', message: '已提交运行，稍后会自动刷新结果' });
    } catch (error) {
      console.error('Failed to run evaluation:', error);
      pushNotice({ type: 'error', message: String((error as any)?.message || error) });
    } finally {
      setIsRunning(false);
    }
  };

  const handleAnnotate = async (runId: string, annotation: { rating: number; comment?: string }) => {
    try {
      await adminApi.createEvalAnnotation(runId, annotation);
      if (selectedWorkflow) await refreshRuns(selectedWorkflow.id);
      pushNotice({ type: 'success', message: '已保存评分/备注' });
    } catch (err) {
      console.error(err);
      pushNotice({ type: 'error', message: String((err as any)?.message || err) });
      throw err;
    }
  };

  const handleSaveWorkflowNotes = async (workflowVersionId: string, notes: string) => {
    setIsSavingWorkflowNotes(true);
    try {
      const updated = await adminApi.updateEvalWorkflowVersion(workflowVersionId, { notes });
      setWorkflows((prev) => prev.map((w) => (w.id === updated.id ? updated : w)));
      setSelectedWorkflow((prev) => (prev && prev.id === updated.id ? updated : prev));
      pushNotice({ type: 'success', message: '已保存功能介绍' });
    } catch (err) {
      console.error(err);
      pushNotice({ type: 'error', message: String((err as any)?.message || err) });
    } finally {
      setIsSavingWorkflowNotes(false);
    }
  };

  const resetCreateForm = () => {
    setCreateError('');
    setCreateDraft({ name: '', category: '通用类', version: 'v1', workflow_id: '', outputKind: 'image', notes: '' });
    setCreateFields([
      {
        name: 'url',
        label: '图片 URL',
        type: 'text',
        required: true,
        description: '图片地址（OSS 或公网 URL）',
        defaultValue: '',
        optionsText: '',
      },
    ]);
  };

  const openCreate = () => {
    resetCreateForm();
    setIsCreateOpen(true);
  };

  const parseSelectOptions = (text: string): Array<{ label: string; value: string }> => {
    return (text || '')
      .split('\n')
      .map((l) => l.trim())
      .filter(Boolean)
      .map((line) => {
        const sepIdx = line.includes('=') ? line.indexOf('=') : line.includes(':') ? line.indexOf(':') : -1;
        if (sepIdx > 0) {
          const label = line.slice(0, sepIdx).trim();
          const value = line.slice(sepIdx + 1).trim();
          return { label: label || value, value: value || label };
        }
        return { label: line, value: line };
      })
      .filter((o) => o.value);
  };

  const handleCreateWorkflow = async () => {
    setCreateError('');
    const wfId = (createDraft.workflow_id || '').trim();
    const name = (createDraft.name || '').trim();
    const category = normalizeCategory(createDraft.category);
    if (!wfId) return setCreateError('workflow_id 不能为空');
    if (!name) return setCreateError('名称不能为空');
    if (workflows.some((w) => w.workflow_id === wfId)) return setCreateError(`已存在同 workflow_id：${wfId}`);

    const fields = createFields
      .map((f) => ({
        name: (f.name || '').trim(),
        label: (f.label || '').trim(),
        type: (f.type || 'text').trim(),
        required: Boolean(f.required),
        description: (f.description || '').trim(),
        defaultValue: (f.defaultValue || '').trim(),
        optionsText: f.optionsText || '',
      }))
      .filter((f) => f.name);

    // Basic schema sanity: unique field names.
    const seenNames = new Set<string>();
    for (const f of fields) {
      if (seenNames.has(f.name)) return setCreateError(`字段名重复：${f.name}`);
      seenNames.add(f.name);
    }

    // Ensure url is present (backend also aliases Url/URL, but url keeps UI consistent).
    if (!fields.some((f) => f.name === 'url')) {
      fields.unshift({
        name: 'url',
        label: '图片 URL',
        type: 'text',
        required: true,
        description: '图片地址（OSS 或公网 URL）',
        defaultValue: '',
        optionsText: '',
      });
    }

    const schemaFields = fields.map((f) => {
      const base: any = {
        name: f.name,
        label: f.label || f.name,
        type: f.type || 'text',
        required: Boolean(f.required),
      };
      if (f.description) base.description = f.description;
      if (f.defaultValue) base.defaultValue = f.defaultValue;
      if (f.type === 'select') {
        const options = parseSelectOptions(f.optionsText);
        if (options.length > 0) base.options = options;
      }
      return base;
    });

    const outputDesc = createDraft.outputKind === 'callback' ? '回调 task id' : '图片 URL';
    const payload: Partial<EvalWorkflowVersion> = {
      category,
      name,
      version: (createDraft.version || 'v1').trim() || 'v1',
      workflow_id: wfId,
      status: 'active',
      notes: (createDraft.notes || '').trim() || null,
      parameters_schema: { fields: schemaFields } as any,
      output_schema: { fields: [{ name: 'output', type: 'text', description: outputDesc }] } as any,
    };

    setIsCreating(true);
    try {
      const created = await adminApi.createEvalWorkflowVersion(payload);
      await refreshWorkflows();
      setSelectedWorkflow(created);
      setIsCreateOpen(false);
      pushNotice({ type: 'success', message: '已创建并启用工作流' });
    } catch (err) {
      console.error(err);
      setCreateError(String((err as any)?.message || err) || '创建失败，请检查后台日志/权限或参数格式');
    } finally {
      setIsCreating(false);
    }
  };

  return (
    <div className="flex h-[720px] overflow-hidden rounded-3xl border border-slate-800 bg-slate-950/30">
      <NoticeBar notice={notice} onClose={() => setNotice(null)} />
      <EvaluationSidebar
        workflows={workflows}
        selectedWorkflow={selectedWorkflow}
        onWorkflowSelect={handleWorkflowSelect}
        onCreateWorkflow={openCreate}
        onRefreshWorkflows={refreshWorkflows}
      />

      <div className="flex-1 flex flex-col overflow-hidden">
        <EvaluationInputPanel
          selectedWorkflow={selectedWorkflow}
          selectedDatasetItem={selectedDatasetItem}
          datasetItems={filteredDatasetItems}
          inputImages={inputImages}
          parameters={parameters}
          isRunning={isRunning}
          isSavingWorkflowNotes={isSavingWorkflowNotes}
          onDatasetItemSelect={handleDatasetItemSelect}
          onImageChange={handleImageChange}
          onParameterChange={handleParameterChange}
          onRunEvaluation={handleRunEvaluation}
          onSaveWorkflowNotes={handleSaveWorkflowNotes}
        />

        <EvaluationResultPanel results={evaluationResults} onAnnotate={handleAnnotate} />
      </div>

      {isCreateOpen ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="w-full max-w-3xl rounded-2xl border border-slate-800 bg-slate-950 p-4 text-slate-100">
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="text-sm font-semibold">新增工作流（快速配置）</div>
                <div className="mt-1 text-xs text-slate-400">输出字段固定为 `output`，可选“图片地址 / 回调 id”。</div>
              </div>
              <button
                type="button"
                onClick={() => setIsCreateOpen(false)}
                className="rounded-lg border border-slate-800 bg-slate-950 px-2 py-1 text-xs text-slate-200 hover:border-slate-700"
              >
                关闭
              </button>
            </div>

            <div className="mt-4 grid gap-3 md:grid-cols-2">
              <label className="block">
                <div className="text-xs text-slate-300">名称 *</div>
                <input
                  value={createDraft.name}
                  onChange={(e) => setCreateDraft((p) => ({ ...p, name: e.target.value }))}
                  className="mt-1 w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-sm"
                  placeholder="例如：花纹提取 · tiqu_xxx"
                />
              </label>
              <label className="block">
                <div className="text-xs text-slate-300">workflow_id *</div>
                <input
                  value={createDraft.workflow_id}
                  onChange={(e) => setCreateDraft((p) => ({ ...p, workflow_id: e.target.value }))}
                  className="mt-1 w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-sm"
                  placeholder="Coze workflow_id"
                />
              </label>
              <label className="block">
                <div className="text-xs text-slate-300">分类</div>
                <select
                  value={createDraft.category}
                  onChange={(e) => setCreateDraft((p) => ({ ...p, category: e.target.value }))}
                  className="mt-1 w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-sm"
                >
                  <option value="花纹提取类">花纹提取类</option>
                  <option value="图延伸类">图延伸类</option>
                  <option value="四方/两方连续图类">四方/两方连续图类</option>
                  <option value="通用类">通用类</option>
                </select>
              </label>
              <label className="block">
                <div className="text-xs text-slate-300">输出类型</div>
                <select
                  value={createDraft.outputKind}
                  onChange={(e) => setCreateDraft((p) => ({ ...p, outputKind: e.target.value as any }))}
                  className="mt-1 w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-sm"
                >
                  <option value="image">图片地址（output=图片 URL）</option>
                  <option value="callback">需要回调（output=回调 id）</option>
                </select>
              </label>
              <label className="block md:col-span-2">
                <div className="text-xs text-slate-300">功能介绍（notes）</div>
                <textarea
                  value={createDraft.notes}
                  onChange={(e) => setCreateDraft((p) => ({ ...p, notes: e.target.value }))}
                  rows={2}
                  className="mt-1 w-full rounded-xl border border-slate-800 bg-slate-950 p-3 text-xs"
                  placeholder="给运营/测试看的说明：用途、注意事项、参数含义…"
                />
              </label>
            </div>

            <div className="mt-4 rounded-2xl border border-slate-800 bg-slate-950/40 p-3">
              <div className="flex items-center justify-between gap-2">
                <div className="text-sm font-semibold">输入字段</div>
                <button
                  type="button"
                  onClick={() =>
                    setCreateFields((prev) => [
                      ...prev,
                      { name: '', label: '', type: 'text', required: false, description: '', defaultValue: '', optionsText: '' },
                    ])
                  }
                  className="rounded-lg border border-slate-800 bg-slate-950 px-2 py-1 text-xs text-slate-200 hover:border-slate-700"
                >
                  + 添加字段
                </button>
              </div>

              <div className="mt-3 space-y-2">
                {createFields.map((f, idx) => (
                  <div key={idx} className="grid gap-2 md:grid-cols-6">
                    <input
                      value={f.name}
                      onChange={(e) =>
                        setCreateFields((prev) => prev.map((x, i) => (i === idx ? { ...x, name: e.target.value } : x)))
                      }
                      className="rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-xs md:col-span-1"
                      placeholder="name"
                    />
                    <input
                      value={f.label}
                      onChange={(e) =>
                        setCreateFields((prev) => prev.map((x, i) => (i === idx ? { ...x, label: e.target.value } : x)))
                      }
                      className="rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-xs md:col-span-1"
                      placeholder="label"
                    />
                    <select
                      value={f.type}
                      onChange={(e) =>
                        setCreateFields((prev) => prev.map((x, i) => (i === idx ? { ...x, type: e.target.value } : x)))
                      }
                      className="rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-xs md:col-span-1"
                    >
                      <option value="text">text</option>
                      <option value="textarea">textarea</option>
                      <option value="select">select</option>
                      <option value="switch">switch</option>
                    </select>
                    <input
                      value={f.defaultValue}
                      onChange={(e) =>
                        setCreateFields((prev) =>
                          prev.map((x, i) => (i === idx ? { ...x, defaultValue: e.target.value } : x)),
                        )
                      }
                      className="rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-xs md:col-span-1"
                      placeholder="default"
                    />
                    <label className="flex items-center gap-2 rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-xs md:col-span-1">
                      <input
                        type="checkbox"
                        checked={Boolean(f.required)}
                        onChange={(e) =>
                          setCreateFields((prev) => prev.map((x, i) => (i === idx ? { ...x, required: e.target.checked } : x)))
                        }
                      />
                      必填
                    </label>
                    <button
                      type="button"
                      onClick={() => setCreateFields((prev) => prev.filter((_, i) => i !== idx))}
                      className="rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-xs text-slate-200 hover:border-slate-700 md:col-span-1"
                    >
                      删除
                    </button>

                    <input
                      value={f.description}
                      onChange={(e) =>
                        setCreateFields((prev) =>
                          prev.map((x, i) => (i === idx ? { ...x, description: e.target.value } : x)),
                        )
                      }
                      className="rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-xs md:col-span-3"
                      placeholder="description"
                    />
                    {f.type === 'select' ? (
                      <textarea
                        value={f.optionsText}
                        onChange={(e) =>
                          setCreateFields((prev) => prev.map((x, i) => (i === idx ? { ...x, optionsText: e.target.value } : x)))
                        }
                        rows={2}
                        className="rounded-xl border border-slate-800 bg-slate-950 p-2 text-xs md:col-span-3"
                        placeholder={'options（一行一个）：\n1 · Banana Pro=1\n2 · Flux2=2'}
                      />
                    ) : (
                      <div className="md:col-span-3" />
                    )}
                  </div>
                ))}
              </div>
            </div>

            {createError ? <div className="mt-3 text-xs text-rose-300">{createError}</div> : null}

            <div className="mt-4 flex items-center justify-end gap-2">
              <button
                type="button"
                onClick={resetCreateForm}
                className="rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-xs text-slate-200 hover:border-slate-700"
              >
                重置
              </button>
              <button
                type="button"
                disabled={isCreating}
                onClick={handleCreateWorkflow}
                className={`rounded-xl px-4 py-2 text-xs font-semibold transition ${
                  isCreating ? 'bg-slate-700/40 text-slate-400' : 'bg-sky-500/80 text-white hover:bg-sky-500'
                }`}
              >
                {isCreating ? '创建中…' : '创建并启用'}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
  const normalizeCategory = (category: string | undefined | null): string => {
    const c = String(category || '').trim();
    if (c === '花纹提取类' || c === '图延伸类' || c === '四方/两方连续图类' || c === '通用类') return c;
    if (c === 'pattern_extract' || c === 'pattern') return '花纹提取类';
    if (c === 'image_extend' || c === '图扩展' || c === '图延伸') return '图延伸类';
    if (c === 'continuous') return '四方/两方连续图类';
    if (c === 'general' || c === 'common') return '通用类';
    return '通用类';
  };
