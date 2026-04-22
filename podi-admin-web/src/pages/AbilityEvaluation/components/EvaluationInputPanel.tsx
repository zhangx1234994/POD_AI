import { useEffect, useMemo, useState } from 'react';
import type {
  EvalDatasetItem,
  EvalWorkflowDeprecation,
  EvalWorkflowPresentation,
  EvalWorkflowUsage,
  EvalWorkflowVersion,
} from '../../../types/eval';

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
  isSavingWorkflowBusinessMetadata?: boolean;
  onDatasetItemSelect: (item: EvalDatasetItem) => void;
  onImageChange: (url: string) => void;
  onParameterChange: (next: Record<string, any>) => void;
  onRunEvaluation: () => void;
  onSaveWorkflowNotes?: (workflowId: string, notes: string) => void;
  onSaveWorkflowBusinessMetadata?: (
    workflowId: string,
    metadata: {
      presentation: EvalWorkflowPresentation;
      usage: EvalWorkflowUsage;
      deprecation: EvalWorkflowDeprecation | null;
    },
  ) => void;
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
  isSavingWorkflowBusinessMetadata = false,
  onDatasetItemSelect,
  onImageChange,
  onParameterChange,
  onRunEvaluation,
  onSaveWorkflowNotes,
  onSaveWorkflowBusinessMetadata,
}: Props) {
  const [rawJson, setRawJson] = useState('');
  const [notesDraft, setNotesDraft] = useState('');
  const [jsonError, setJsonError] = useState<string>('');
  const [businessDraft, setBusinessDraft] = useState<{
    visible: boolean;
    sortOrder: string;
    categoryLabel: string;
    usageHint: string;
    operationLabel: string;
    batchEnabled: boolean;
    recommendedEntry: string;
    isDeprecated: boolean;
    replacementWorkflowId: string;
    replacementDisplayName: string;
    deprecationReason: string;
    retirementMode: string;
  }>({
    visible: true,
    sortOrder: '9999',
    categoryLabel: '',
    usageHint: '',
    operationLabel: '',
    batchEnabled: false,
    recommendedEntry: 'parameter_form',
    isDeprecated: false,
    replacementWorkflowId: '',
    replacementDisplayName: '',
    deprecationReason: '',
    retirementMode: 'hide_public',
  });

  const fields = useMemo(() => getSchemaFields(selectedWorkflow), [selectedWorkflow]);
  const url = inputImages[0] || '';

  useEffect(() => {
    // Keep raw JSON editor in sync when workflow changes.
    setRawJson(JSON.stringify(parameters || {}, null, 2));
  }, [selectedWorkflow?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    setNotesDraft(String(selectedWorkflow?.notes || ''));
  }, [selectedWorkflow?.id, selectedWorkflow?.notes]);

  useEffect(() => {
    const presentation = selectedWorkflow?.presentation || {};
    const usage = selectedWorkflow?.usage || {};
    const deprecation = selectedWorkflow?.deprecation || {};
    setBusinessDraft({
      visible: presentation.visible ?? true,
      sortOrder: String(presentation.sortOrder ?? 9999),
      categoryLabel: String(presentation.categoryLabel || selectedWorkflow?.category || ''),
      usageHint: String(presentation.usageHint || ''),
      operationLabel: String(presentation.operationLabel || ''),
      batchEnabled: Boolean(usage.batchEnabled),
      recommendedEntry: String(usage.recommendedEntry || 'parameter_form'),
      isDeprecated: Boolean(deprecation.isDeprecated),
      replacementWorkflowId: String(deprecation.replacementWorkflowId || ''),
      replacementDisplayName: String(deprecation.replacementDisplayName || ''),
      deprecationReason: String(deprecation.reason || ''),
      retirementMode: String(deprecation.retirementMode || 'hide_public'),
    });
  }, [selectedWorkflow]);

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

  const handleSaveBusinessMetadata = () => {
    if (!selectedWorkflow || typeof onSaveWorkflowBusinessMetadata !== 'function') return;
    const parsedSortOrder = Number.parseInt(String(businessDraft.sortOrder || '9999').trim(), 10);
    onSaveWorkflowBusinessMetadata(selectedWorkflow.id, {
      presentation: {
        visible: businessDraft.visible,
        sortOrder: Number.isFinite(parsedSortOrder) ? parsedSortOrder : 9999,
        categoryLabel: businessDraft.categoryLabel.trim(),
        usageHint: businessDraft.usageHint.trim(),
        operationLabel: businessDraft.operationLabel.trim(),
      },
      usage: {
        batchEnabled: businessDraft.batchEnabled,
        recommendedEntry: businessDraft.recommendedEntry.trim() || 'parameter_form',
      },
      deprecation: businessDraft.isDeprecated
        ? {
            isDeprecated: true,
            replacementWorkflowId: businessDraft.replacementWorkflowId.trim() || null,
            replacementDisplayName: businessDraft.replacementDisplayName.trim() || null,
            reason: businessDraft.deprecationReason.trim() || null,
            retirementMode: businessDraft.retirementMode.trim() || 'hide_public',
          }
        : null,
    });
  };

  return (
    <div className="max-h-[40vh] overflow-y-auto border-b border-slate-200 bg-slate-50/70 p-4 pr-1 dark:border-slate-800 dark:bg-slate-900/30">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="text-sm font-semibold text-slate-900 dark:text-slate-100">
            {selectedWorkflow ? `${selectedWorkflow.name} · ${selectedWorkflow.version}` : '请选择工作流'}
          </div>
          {selectedWorkflow?.notes ? (
            <div className="mt-1 whitespace-pre-wrap text-xs text-slate-700 dark:text-slate-400">{selectedWorkflow.notes}</div>
          ) : null}
          <div className="mt-1 text-xs text-slate-700 dark:text-slate-400">
            约定：图片输入字段名使用 `url`（字符串）；其它参数尽量用字符串，后端再做类型转换。
          </div>
        </div>
        <button
          type="button"
          disabled={!selectedWorkflow || !url || isRunning}
          onClick={onRunEvaluation}
          className={`rounded-xl px-4 py-2 text-sm font-semibold transition ${
            !selectedWorkflow || !url || isRunning
              ? 'bg-slate-200 text-slate-500 dark:bg-slate-700/40 dark:text-slate-400'
              : 'bg-sky-600 text-white hover:bg-sky-500'
          }`}
        >
          {isRunning ? '运行中…' : '试运行'}
        </button>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <div className="rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-950/40">
          <div className="flex items-center justify-between">
            <div className="text-sm font-semibold text-slate-900 dark:text-slate-100">输入图片 URL</div>
            <div className="text-xs text-slate-600 dark:text-slate-500">{selectedDatasetItem ? `样例：${selectedDatasetItem.name}` : ''}</div>
          </div>
          <div className="mt-2 flex gap-2">
            <input
              value={url}
              onChange={(e) => onImageChange(e.target.value)}
              placeholder="https://... (OSS 或公网 URL)"
              className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100 dark:placeholder:text-slate-600"
            />
          </div>
          {datasetItems.length > 0 && (
            <div className="mt-3">
              <div className="mb-1 text-xs text-slate-600 dark:text-slate-500">选择样例图</div>
              <select
                value={selectedDatasetItem?.id || ''}
                onChange={(e) => {
                  const id = e.target.value;
                  const item = datasetItems.find((it) => it.id === id);
                  if (item) onDatasetItemSelect(item);
                }}
                className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100"
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
              <div className="mb-1 text-xs text-slate-600 dark:text-slate-500">预览</div>
              <img
                src={url}
                alt="input preview"
                className="max-h-64 w-full rounded-xl border border-slate-200 object-contain dark:border-slate-800"
              />
            </div>
          )}
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-950/40">
          <div className="text-sm font-semibold text-slate-900 dark:text-slate-100">参数</div>
          <div className="mt-2 text-xs text-slate-600 dark:text-slate-500">未配置 schema 时可直接编辑 JSON。</div>

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
                      <div className="text-xs text-slate-700 dark:text-slate-300">
                        {label} {field.required ? <span className="text-rose-400">*</span> : null}
                      </div>
                      {description && <div className="text-[11px] text-slate-600 dark:text-slate-500">{description}</div>}
                      <select
                        value={String(value)}
                        onChange={(e) => onParameterChange({ ...parameters, [key]: e.target.value })}
                        className="mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100"
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
                    <div className="text-xs text-slate-700 dark:text-slate-300">
                      {label} {field.required ? <span className="text-rose-400">*</span> : null}
                    </div>
                    {description && <div className="text-[11px] text-slate-600 dark:text-slate-500">{description}</div>}
                    <input
                      value={String(value)}
                      onChange={(e) => onParameterChange({ ...parameters, [key]: e.target.value })}
                      placeholder={key}
                      className="mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100 dark:placeholder:text-slate-600"
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
                className="w-full rounded-xl border border-slate-300 bg-white p-3 font-mono text-xs text-slate-900 placeholder:text-slate-400 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100 dark:placeholder:text-slate-600"
                placeholder='{"prompt":"...","height":"1200"}'
              />
              {jsonError ? <div className="mt-2 text-xs text-rose-300">{jsonError}</div> : null}
              <div className="mt-2 flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setRawJson(JSON.stringify({ ...parameters, url }, null, 2))}
                  className="rounded-xl border border-slate-300 bg-white px-3 py-1.5 text-xs text-slate-700 hover:bg-slate-50 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-200 dark:hover:border-slate-700"
                >
                  重置
                </button>
                <button
                  type="button"
                  onClick={handleJsonApply}
                  className="rounded-xl bg-slate-900 px-3 py-1.5 text-xs text-white hover:bg-slate-800 dark:bg-slate-200/10 dark:text-slate-100 dark:hover:bg-slate-200/15"
                >
                  应用 JSON
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {selectedWorkflow && typeof onSaveWorkflowNotes === 'function' && (
        <div className="mt-4 rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-950/40">
          <div className="flex items-center justify-between gap-2">
            <div className="text-sm font-semibold text-slate-900 dark:text-slate-100">功能介绍（notes）</div>
            <button
              type="button"
              disabled={Boolean(isSavingWorkflowNotes)}
              onClick={() => onSaveWorkflowNotes(selectedWorkflow.id, notesDraft)}
              className={`rounded-xl px-3 py-1.5 text-xs font-semibold transition ${
                isSavingWorkflowNotes
                  ? 'bg-slate-200 text-slate-500 dark:bg-slate-700/40 dark:text-slate-400'
                  : 'bg-sky-600 text-white hover:bg-sky-500'
              }`}
            >
              {isSavingWorkflowNotes ? '保存中…' : '保存'}
            </button>
          </div>
          <textarea
            value={notesDraft}
            onChange={(e) => setNotesDraft(e.target.value)}
            rows={3}
            className="mt-2 w-full rounded-xl border border-slate-300 bg-white p-3 text-xs text-slate-900 placeholder:text-slate-400 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100 dark:placeholder:text-slate-600"
            placeholder="这里写功能介绍、参数说明、注意事项…"
          />
        </div>
      )}

      {selectedWorkflow && typeof onSaveWorkflowBusinessMetadata === 'function' && (
        <div className="mt-4 rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-950/40">
          <div className="flex items-center justify-between gap-2">
            <div>
              <div className="text-sm font-semibold text-slate-900 dark:text-slate-100">业务元数据</div>
              <div className="mt-1 text-xs text-slate-600 dark:text-slate-500">控制展示、推荐入口、批测能力和下线替代关系。</div>
            </div>
            <button
              type="button"
              disabled={Boolean(isSavingWorkflowBusinessMetadata)}
              onClick={handleSaveBusinessMetadata}
              className={`rounded-xl px-3 py-1.5 text-xs font-semibold transition ${
                isSavingWorkflowBusinessMetadata
                  ? 'bg-slate-200 text-slate-500 dark:bg-slate-700/40 dark:text-slate-400'
                  : 'bg-sky-600 text-white hover:bg-sky-500'
              }`}
            >
              {isSavingWorkflowBusinessMetadata ? '保存中…' : '保存业务设置'}
            </button>
          </div>

          <div className="mt-3 grid gap-3 md:grid-cols-2">
            <label className="block">
              <div className="text-xs text-slate-700 dark:text-slate-300">分类标签</div>
              <input
                value={businessDraft.categoryLabel}
                onChange={(e) => setBusinessDraft((prev) => ({ ...prev, categoryLabel: e.target.value }))}
                className="mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100"
              />
            </label>
            <label className="block">
              <div className="text-xs text-slate-700 dark:text-slate-300">排序值</div>
              <input
                value={businessDraft.sortOrder}
                onChange={(e) => setBusinessDraft((prev) => ({ ...prev, sortOrder: e.target.value }))}
                className="mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100"
              />
            </label>
            <label className="block md:col-span-2">
              <div className="text-xs text-slate-700 dark:text-slate-300">使用提示</div>
              <input
                value={businessDraft.usageHint}
                onChange={(e) => setBusinessDraft((prev) => ({ ...prev, usageHint: e.target.value }))}
                className="mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100"
              />
            </label>
            <label className="block">
              <div className="text-xs text-slate-700 dark:text-slate-300">操作标签</div>
              <input
                value={businessDraft.operationLabel}
                onChange={(e) => setBusinessDraft((prev) => ({ ...prev, operationLabel: e.target.value }))}
                className="mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100"
              />
            </label>
            <label className="block">
              <div className="text-xs text-slate-700 dark:text-slate-300">推荐入口</div>
              <select
                value={businessDraft.recommendedEntry}
                onChange={(e) => setBusinessDraft((prev) => ({ ...prev, recommendedEntry: e.target.value }))}
                className="mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100"
              >
                <option value="parameter_form">parameter_form</option>
                <option value="batch_upload">batch_upload</option>
                <option value="docs">docs</option>
              </select>
            </label>
          </div>

          <div className="mt-3 flex flex-wrap gap-4">
            <label className="inline-flex items-center gap-2 text-xs text-slate-700 dark:text-slate-300">
              <input
                type="checkbox"
                checked={businessDraft.visible}
                onChange={(e) => setBusinessDraft((prev) => ({ ...prev, visible: e.target.checked }))}
              />
              对公共列表可见
            </label>
            <label className="inline-flex items-center gap-2 text-xs text-slate-700 dark:text-slate-300">
              <input
                type="checkbox"
                checked={businessDraft.batchEnabled}
                onChange={(e) => setBusinessDraft((prev) => ({ ...prev, batchEnabled: e.target.checked }))}
              />
              支持批测
            </label>
            <label className="inline-flex items-center gap-2 text-xs text-slate-700 dark:text-slate-300">
              <input
                type="checkbox"
                checked={businessDraft.isDeprecated}
                onChange={(e) => setBusinessDraft((prev) => ({ ...prev, isDeprecated: e.target.checked }))}
              />
              标记为下线/替代
            </label>
          </div>

          {businessDraft.isDeprecated && (
            <div className="mt-3 grid gap-3 md:grid-cols-2">
              <label className="block">
                <div className="text-xs text-slate-700 dark:text-slate-300">替代 workflow_id</div>
                <input
                  value={businessDraft.replacementWorkflowId}
                  onChange={(e) => setBusinessDraft((prev) => ({ ...prev, replacementWorkflowId: e.target.value }))}
                  className="mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100"
                />
              </label>
              <label className="block">
                <div className="text-xs text-slate-700 dark:text-slate-300">替代显示名称</div>
                <input
                  value={businessDraft.replacementDisplayName}
                  onChange={(e) => setBusinessDraft((prev) => ({ ...prev, replacementDisplayName: e.target.value }))}
                  className="mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100"
                />
              </label>
              <label className="block">
                <div className="text-xs text-slate-700 dark:text-slate-300">下线模式</div>
                <select
                  value={businessDraft.retirementMode}
                  onChange={(e) => setBusinessDraft((prev) => ({ ...prev, retirementMode: e.target.value }))}
                  className="mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100"
                >
                  <option value="hide_public">hide_public</option>
                  <option value="admin_only">admin_only</option>
                  <option value="delete_candidate">delete_candidate</option>
                </select>
              </label>
              <label className="block md:col-span-2">
                <div className="text-xs text-slate-700 dark:text-slate-300">下线原因</div>
                <input
                  value={businessDraft.deprecationReason}
                  onChange={(e) => setBusinessDraft((prev) => ({ ...prev, deprecationReason: e.target.value }))}
                  className="mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100"
                />
              </label>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
