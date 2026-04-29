import { Alert, Button, Card, Col, Dialog, Input, Row, Select, Space, Tag, Textarea, Typography } from 'tdesign-react';
import type { ComfyuiLora, ComfyuiLoraCatalogResponse, Executor } from '../../../types/admin';
import { StatusBadge } from '../shared/ui';

type SelectOption = {
  label: string;
  value: string;
};

type ComfyuiLorasPanelProps = {
  executors: Executor[];
  executorId: string;
  executor?: Executor | null;
  catalog?: ComfyuiLoraCatalogResponse | null;
  loading: boolean;
  error?: string | null;
  cachedBaseModels: string[];
  baseModelOptions: string[];
  formBaseModels: string[];
  items: ComfyuiLora[];
  untracked: string[];
  installedCount: number;
  serverScanned: boolean;
  search: string;
  statusFilter: string;
  statusOptions: SelectOption[];
  dialogOpen: boolean;
  saving: boolean;
  form: Partial<ComfyuiLora>;
  tagsInput: string;
  triggersInput: string;
  formError?: string | null;
  onExecutorChange: (executorId: string) => void;
  onRefreshLibrary: () => void;
  onRefreshBaseModels: () => void;
  onRefreshUntracked: () => void;
  onCreateLora: () => void;
  onClearBaseModels: (executorId: string) => void;
  onRemoveBaseModel: (executorId: string, model: string) => void;
  onSearchChange: (value: string) => void;
  onStatusFilterChange: (value: string) => void;
  onCreateFromUntracked: (fileName: string) => void;
  onEditLora: (item: ComfyuiLora) => void;
  onDeleteLora: (id: number) => void;
  onCloseDialog: () => void;
  onSaveLora: () => void;
  onFormPatch: (patch: Partial<ComfyuiLora>) => void;
  onBaseModelsChange: (baseModels: string[]) => void;
  onTagsInputChange: (value: string) => void;
  onTriggersInputChange: (value: string) => void;
};

const normalizeTextList = (value: string) =>
  String(value || '')
    .split(/[\n,，]/)
    .map((item) => item.trim())
    .filter(Boolean);

export function ComfyuiLorasPanel({
  executors,
  executorId,
  executor,
  catalog,
  loading,
  error,
  cachedBaseModels,
  baseModelOptions,
  formBaseModels,
  items,
  untracked,
  installedCount,
  serverScanned,
  search,
  statusFilter,
  statusOptions,
  dialogOpen,
  saving,
  form,
  tagsInput,
  triggersInput,
  formError,
  onExecutorChange,
  onRefreshLibrary,
  onRefreshBaseModels,
  onRefreshUntracked,
  onCreateLora,
  onClearBaseModels,
  onRemoveBaseModel,
  onSearchChange,
  onStatusFilterChange,
  onCreateFromUntracked,
  onEditLora,
  onDeleteLora,
  onCloseDialog,
  onSaveLora,
  onFormPatch,
  onBaseModelsChange,
  onTagsInputChange,
  onTriggersInputChange,
}: ComfyuiLorasPanelProps) {
  return (
    <div className="space-y-4">
      <Card bordered title="LoRA 素材库">
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
            <Space align="center" size="middle">
              <div style={{ width: 'min(100%, 260px)' }}>
                <Select
                  value={executorId}
                  onChange={(value) => onExecutorChange(String(value))}
                  options={[
                    { label: '请选择 ComfyUI 执行节点', value: '' },
                    ...executors.map((item) => ({
                      label: `${item.name} · ${item.id}`,
                      value: item.id,
                    })),
                  ]}
                />
              </div>
              <Button variant="outline" disabled={loading} onClick={onRefreshLibrary}>
                刷新库内 LoRA
              </Button>
              <Button variant="outline" disabled={!executorId} onClick={onRefreshBaseModels}>
                刷新基座模型
              </Button>
              <Button variant="outline" disabled={!executorId || loading} onClick={onRefreshUntracked}>
                查看未入库 LoRA
              </Button>
            </Space>
            <Button theme="primary" onClick={onCreateLora}>
              新增 LoRA
            </Button>
          </Space>

          {executor ? (
            <div className="text-xs text-slate-600 dark:text-slate-400">
              当前节点：{executor.name} · {executor.id} {catalog?.baseUrl ? `(${catalog.baseUrl})` : ''}
            </div>
          ) : (
            <Alert theme="warning" message="未选择执行节点，仅展示库内 LoRA；如需查看服务器安装/未入库，请先选择节点。" />
          )}

          {error ? <Alert theme="error" message={error} /> : null}

          {executorId && cachedBaseModels.length > 0 ? (
            <div className="rounded-2xl border border-slate-200/70 bg-slate-50/60 p-3 text-xs text-slate-700 dark:border-slate-800 dark:bg-slate-950/40 dark:text-slate-300">
              <div className="flex items-center justify-between">
                <div className="font-semibold">已缓存基座模型</div>
                <button className="text-[11px] text-slate-500 hover:text-slate-700 dark:hover:text-slate-200" onClick={() => onClearBaseModels(executorId)}>
                  清空
                </button>
              </div>
              <div className="mt-2 flex flex-wrap gap-2">
                {cachedBaseModels.map((model) => (
                  <button
                    key={`base-model-cache-${model}`}
                    className="rounded-full border border-slate-300 bg-white px-2 py-1 text-[11px] text-slate-600 hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-950/60 dark:text-slate-300 dark:hover:bg-slate-900/60"
                    onClick={() => onRemoveBaseModel(executorId, model)}
                  >
                    × {model}
                  </button>
                ))}
              </div>
              <div className="mt-2 text-[11px] text-slate-500">刷新基座模型仅做增补，不会清空已有缓存。</div>
            </div>
          ) : null}

          <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
            <Space align="center" size="small">
              <Input value={search} onChange={(value) => onSearchChange(String(value))} placeholder="搜索文件名/名称" />
              <Select
                value={statusFilter}
                onChange={(value) => onStatusFilterChange(String(value))}
                options={[{ label: '全部状态', value: 'all' }, ...statusOptions.map((option) => ({ label: option.label, value: option.value }))]}
              />
            </Space>
            <div className="text-xs text-slate-500">
              已入库 {items.length}
              {serverScanned ? ` · 服务器已安装 ${installedCount}` : ' · 未加载服务器清单'}
            </div>
          </Space>

          {serverScanned && untracked.length > 0 ? (
            <div className="rounded-2xl border border-dashed border-amber-300 bg-amber-50/60 p-3 text-xs text-amber-700">
              <div className="font-semibold">未入库 LoRA（来自执行节点）</div>
              <div className="mt-2 flex flex-wrap gap-2">
                {untracked.map((name) => (
                  <button
                    key={`lora-missing-${name}`}
                    className="rounded-full border border-amber-400/60 bg-white px-3 py-1 text-[11px] text-amber-700 hover:bg-amber-100"
                    onClick={() => onCreateFromUntracked(name)}
                  >
                    + {name}
                  </button>
                ))}
              </div>
            </div>
          ) : null}
          {serverScanned && untracked.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50/60 p-3 text-xs text-slate-500">未发现未入库 LoRA。</div>
          ) : null}

          <div className="max-h-[480px] overflow-auto rounded-2xl border border-slate-200/70 dark:border-slate-800">
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-slate-50 text-[11px] text-slate-600 dark:bg-slate-900/80 dark:text-slate-400">
                <tr className="text-left">
                  <th className="px-3 py-2">名称</th>
                  <th className="px-3 py-2">文件名</th>
                  <th className="px-3 py-2">基座模型</th>
                  <th className="px-3 py-2">触发词</th>
                  <th className="px-3 py-2">标签</th>
                  <th className="px-3 py-2">状态</th>
                  <th className="px-3 py-2">安装</th>
                  <th className="px-3 py-2 text-right">操作</th>
                </tr>
              </thead>
              <tbody>
                {items.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="px-4 py-6 text-center text-slate-500">
                      {loading ? '加载中…' : '暂无 LoRA 记录'}
                    </td>
                  </tr>
                ) : (
                  items.map((item) => (
                    <tr key={`lora-${item.id}`} className="border-t border-slate-100 dark:border-slate-800">
                      <td className="px-3 py-2 font-semibold text-slate-900 dark:text-white">{item.display_name}</td>
                      <td className="px-3 py-2 text-slate-700 dark:text-slate-300">{item.file_name}</td>
                      <td className="px-3 py-2 text-slate-700 dark:text-slate-300">
                        {(item.base_models && item.base_models.length > 0 ? item.base_models.join(', ') : item.base_model) || '—'}
                      </td>
                      <td className="px-3 py-2 text-slate-600 dark:text-slate-400">{item.trigger_words?.join(', ') || '—'}</td>
                      <td className="px-3 py-2 text-slate-600 dark:text-slate-400">{item.tags?.join(', ') || '—'}</td>
                      <td className="px-3 py-2">
                        <StatusBadge status={item.status} />
                      </td>
                      <td className="px-3 py-2">
                        {item.installed === true ? (
                          <Tag theme="success" variant="light">
                            已安装
                          </Tag>
                        ) : item.installed === false ? (
                          <Tag theme="default" variant="light">
                            未安装
                          </Tag>
                        ) : (
                          <Typography.Text theme="secondary">未检测</Typography.Text>
                        )}
                      </td>
                      <td className="px-3 py-2 text-right space-x-2">
                        <button className="text-sky-400" onClick={() => onEditLora(item)}>
                          编辑
                        </button>
                        <button className="text-red-400" onClick={() => onDeleteLora(item.id)}>
                          删除
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </Space>
      </Card>

      <Dialog
        header={form.id ? '编辑 LoRA' : '新增 LoRA'}
        visible={dialogOpen}
        width={640}
        confirmBtn={saving ? { loading: true } : undefined}
        onClose={onCloseDialog}
        onConfirm={onSaveLora}
      >
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Row gutter={[12, 12]}>
            <Col span={12}>
              <Typography.Text theme="secondary">LoRA 文件名（服务器）</Typography.Text>
              <Input
                value={form.file_name || ''}
                onChange={(value) => onFormPatch({ file_name: String(value) })}
                placeholder="例如 xxx.safetensors"
                disabled={Boolean(form.id)}
              />
            </Col>
            <Col span={12}>
              <Typography.Text theme="secondary">对外名称</Typography.Text>
              <Input value={form.display_name || ''} onChange={(value) => onFormPatch({ display_name: String(value) })} placeholder="例如 杯子 / 毛毯" />
            </Col>
          </Row>

          <Row gutter={[12, 12]}>
            <Col span={12}>
              <Typography.Text theme="secondary">适用基座模型（UNET，可多选）</Typography.Text>
              {baseModelOptions.length > 0 ? (
                <select
                  multiple
                  value={formBaseModels}
                  onChange={(event) => {
                    const selected = Array.from(event.target.selectedOptions).map((option) => option.value);
                    onBaseModelsChange(selected);
                  }}
                  className="mt-2 h-28 w-full rounded-2xl border border-slate-300 bg-white px-4 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-950/70 dark:text-white"
                >
                  {baseModelOptions.map((model) => (
                    <option key={`base-model-${model}`} value={model}>
                      {model}
                    </option>
                  ))}
                </select>
              ) : (
                <Input
                  value={formBaseModels.join(', ')}
                  onChange={(value) => onBaseModelsChange(normalizeTextList(String(value)))}
                  placeholder="逗号分隔多个基座模型"
                />
              )}
              <Typography.Text theme="secondary" style={{ fontSize: 12, display: 'block', marginTop: 6 }}>
                可多选；若列表为空请先刷新基座模型。
              </Typography.Text>
            </Col>
            <Col span={12}>
              <Typography.Text theme="secondary">状态</Typography.Text>
              <Select value={form.status || 'active'} onChange={(value) => onFormPatch({ status: String(value) })} options={statusOptions} />
            </Col>
          </Row>

          <div>
            <Typography.Text theme="secondary">触发词（逗号或换行分隔）</Typography.Text>
            <Textarea
              value={triggersInput}
              onChange={(value) => onTriggersInputChange(String(value))}
              autosize={{ minRows: 2, maxRows: 4 }}
              placeholder="例如: cup, 360, mockup"
            />
          </div>
          <div>
            <Typography.Text theme="secondary">标签（逗号或换行分隔）</Typography.Text>
            <Textarea
              value={tagsInput}
              onChange={(value) => onTagsInputChange(String(value))}
              autosize={{ minRows: 2, maxRows: 4 }}
              placeholder="例如: 服饰, 杯子, 抱枕"
            />
          </div>
          <div>
            <Typography.Text theme="secondary">备注</Typography.Text>
            <Textarea
              value={form.description || ''}
              onChange={(value) => onFormPatch({ description: String(value) })}
              autosize={{ minRows: 3, maxRows: 6 }}
              placeholder="适用场景、注意事项"
            />
          </div>
          {formError ? <Alert theme="error" message={formError} /> : null}
        </Space>
      </Dialog>
    </div>
  );
}
