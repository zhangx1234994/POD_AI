import { useEffect, useMemo, useState } from 'react';
import type { EvalDatasetItem, EvalWorkflowVersion } from '../../../types/eval';

type SchemaField = {
  name: string;
  label?: string;
  type?: string;
  required?: boolean;
  description?: string;
  options?: { label: string; value: string }[];
  defaultValue?: string;
};

type Props = {
  selectedWorkflow: EvalWorkflowVersion | null;
  datasetItems: EvalDatasetItem[];
  selectedDatasetItem: EvalDatasetItem | null;
  inputImages: string[];
  parameters: Record<string, any>;
  isRunning: boolean;
  isSavingWorkflowNotes?: boolean;
  onDatasetItemSelect: (item: EvalDatasetItem) => void;
  onImageChange: (url: string) => void;
  onParameterChange: (next: Record<string, any>) => void;
  onRunEvaluation: () => void;
  onSaveWorkflowNotes?: (workflowId: string, notes: string) => void;
};

const getSchemaFields = (workflow: EvalWorkflowVersion | null): SchemaField[] => {
  if (!workflow?.parameters_schema) return [];
  const maybe = workflow.parameters_schema as Record<string, any>;
  const fields = maybe?.fields;
  if (!Array.isArray(fields)) return [];
  return fields
    .filter((f) => f && typeof f === 'object' && typeof f.name === 'string')
    .map((f) => ({
      name: String(f.name),
      label: typeof f.label === 'string' ? f.label : undefined,
      type: typeof f.type === 'string' ? f.type : undefined,
      required: Boolean(f.required),
      description: typeof f.description === 'string' ? f.description : undefined,
      options: Array.isArray(f.options)
        ? f.options
            .filter((o: any) => o && typeof o === 'object' && typeof o.value === 'string')
            .map((o: any) => ({ label: String(o.label ?? o.value), value: String(o.value) }))
        : undefined,
      defaultValue: typeof f.defaultValue === 'string' ? f.defaultValue : undefined,
    }));
};

export function EvaluationInputPanel({
  selectedWorkflow,
  datasetItems,
  selectedDatasetItem,
  inputImages,
  parameters,
  isRunning,
  isSavingWorkflowNotes = false,
  onDatasetItemSelect,
  onImageChange,
  onParameterChange,
  onRunEvaluation,
  onSaveWorkflowNotes,
}: Props) {
  const [rawJson, setRawJson] = useState('');
  const [notesDraft, setNotesDraft] = useState('');
  const [jsonError, setJsonError] = useState<string>('');

  const fields = useMemo(() => getSchemaFields(selectedWorkflow), [selectedWorkflow]);
  const url = inputImages[0] || '';

  useEffect(() => {
    // Keep raw JSON editor in sync when workflow changes.
    setRawJson(JSON.stringify(parameters || {}, null, 2));
  }, [selectedWorkflow?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    setNotesDraft(String(selectedWorkflow?.notes || ''));
  }, [selectedWorkflow?.id, selectedWorkflow?.notes]);

  const useSchemaForm = fields.length > 0;

  const handleJsonApply = () => {
    try {
      const parsed = JSON.parse(rawJson || '{}');
      if (!parsed || typeof parsed !== 'object') return;
      onParameterChange(parsed);
      setJsonError('');
    } catch (err) {
      console.error(err);
      setJsonError('参数 JSON 解析失败，请检查格式');
    }
  };

  return (
    <div className="border-b border-slate-800 bg-slate-900/30 p-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="text-sm font-semibold text-slate-100">
            {selectedWorkflow ? `${selectedWorkflow.name} · ${selectedWorkflow.version}` : '请选择工作流'}
          </div>
          {selectedWorkflow?.notes ? (
            <div className="text-xs text-slate-400 mt-1 whitespace-pre-wrap">{selectedWorkflow.notes}</div>
          ) : null}
          <div className="text-xs text-slate-400 mt-1">
            约定：图片输入字段名使用 `url`（字符串）；其它参数尽量用字符串，后端再做类型转换。
          </div>
        </div>
        <button
          type="button"
          disabled={!selectedWorkflow || !url || isRunning}
          onClick={onRunEvaluation}
          className={`rounded-xl px-4 py-2 text-sm font-semibold transition ${
            !selectedWorkflow || !url || isRunning
              ? 'bg-slate-700/40 text-slate-400'
              : 'bg-sky-500/80 text-white hover:bg-sky-500'
          }`}
        >
          {isRunning ? '运行中…' : '试运行'}
        </button>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <div className="rounded-2xl border border-slate-800 bg-slate-950/40 p-4">
          <div className="flex items-center justify-between">
            <div className="text-sm font-semibold text-slate-100">输入图片 URL</div>
            <div className="text-xs text-slate-500">{selectedDatasetItem ? `样例：${selectedDatasetItem.name}` : ''}</div>
          </div>
          <div className="mt-2 flex gap-2">
            <input
              value={url}
              onChange={(e) => onImageChange(e.target.value)}
              placeholder="https://... (OSS 或公网 URL)"
              className="w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-600"
            />
          </div>
          {datasetItems.length > 0 && (
            <div className="mt-3">
              <div className="text-xs text-slate-500 mb-1">选择样例图</div>
              <select
                value={selectedDatasetItem?.id || ''}
                onChange={(e) => {
                  const id = e.target.value;
                  const item = datasetItems.find((it) => it.id === id);
                  if (item) onDatasetItemSelect(item);
                }}
                className="w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-sm text-slate-100"
              >
                <option value="">—</option>
                {datasetItems.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </div>
          )}
          {url && (
            <div className="mt-3">
              <div className="text-xs text-slate-500 mb-1">预览</div>
              <img src={url} alt="input preview" className="max-h-64 w-full rounded-xl border border-slate-800 object-contain" />
            </div>
          )}
        </div>

        <div className="rounded-2xl border border-slate-800 bg-slate-950/40 p-4">
          <div className="text-sm font-semibold text-slate-100">参数</div>
          <div className="mt-2 text-xs text-slate-500">未配置 schema 时可直接编辑 JSON。</div>

          {useSchemaForm ? (
            <div className="mt-3 space-y-3">
              {fields.map((field) => {
                const key = field.name;
                if (key === 'url') return null; // URL 已在左侧单独处理
                const value = parameters?.[key] ?? field.defaultValue ?? '';
                const label = field.label || key;
                const description = field.description || '';

                if (field.options && field.options.length > 0) {
                  return (
                    <label key={key} className="block">
                      <div className="text-xs text-slate-300">
                        {label} {field.required ? <span className="text-rose-400">*</span> : null}
                      </div>
                      {description && <div className="text-[11px] text-slate-500">{description}</div>}
                      <select
                        value={String(value)}
                        onChange={(e) => onParameterChange({ ...parameters, [key]: e.target.value })}
                        className="mt-1 w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-sm text-slate-100"
                      >
                        {field.options.map((opt) => (
                          <option key={opt.value} value={opt.value}>
                            {opt.label}
                          </option>
                        ))}
                      </select>
                    </label>
                  );
                }

                return (
                  <label key={key} className="block">
                    <div className="text-xs text-slate-300">
                      {label} {field.required ? <span className="text-rose-400">*</span> : null}
                    </div>
                    {description && <div className="text-[11px] text-slate-500">{description}</div>}
                    <input
                      value={String(value)}
                      onChange={(e) => onParameterChange({ ...parameters, [key]: e.target.value })}
                      placeholder={key}
                      className="mt-1 w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-600"
                    />
                  </label>
                );
              })}
            </div>
          ) : (
            <div className="mt-3">
              <textarea
                value={rawJson}
                onChange={(e) => setRawJson(e.target.value)}
                rows={10}
                className="w-full rounded-xl border border-slate-800 bg-slate-950 p-3 font-mono text-xs text-slate-100"
                placeholder='{"prompt":"...","height":"1200"}'
              />
              {jsonError ? <div className="mt-2 text-xs text-rose-300">{jsonError}</div> : null}
              <div className="mt-2 flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setRawJson(JSON.stringify({ ...parameters, url }, null, 2))}
                  className="rounded-xl border border-slate-800 bg-slate-950 px-3 py-1.5 text-xs text-slate-200 hover:border-slate-700"
                >
                  重置
                </button>
                <button
                  type="button"
                  onClick={handleJsonApply}
                  className="rounded-xl bg-slate-200/10 px-3 py-1.5 text-xs text-slate-100 hover:bg-slate-200/15"
                >
                  应用 JSON
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {selectedWorkflow && typeof onSaveWorkflowNotes === 'function' && (
        <div className="mt-4 rounded-2xl border border-slate-800 bg-slate-950/40 p-4">
          <div className="flex items-center justify-between gap-2">
            <div className="text-sm font-semibold text-slate-100">功能介绍（notes）</div>
            <button
              type="button"
              disabled={Boolean(isSavingWorkflowNotes)}
              onClick={() => onSaveWorkflowNotes(selectedWorkflow.id, notesDraft)}
              className={`rounded-xl px-3 py-1.5 text-xs font-semibold transition ${
                isSavingWorkflowNotes ? 'bg-slate-700/40 text-slate-400' : 'bg-sky-500/80 text-white hover:bg-sky-500'
              }`}
            >
              {isSavingWorkflowNotes ? '保存中…' : '保存'}
            </button>
          </div>
          <textarea
            value={notesDraft}
            onChange={(e) => setNotesDraft(e.target.value)}
            rows={3}
            className="mt-2 w-full rounded-xl border border-slate-800 bg-slate-950 p-3 text-xs text-slate-100"
            placeholder="这里写功能介绍、参数说明、注意事项…"
          />
        </div>
      )}
    </div>
  );
}
