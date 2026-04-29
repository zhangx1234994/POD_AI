import type { Dispatch, SetStateAction } from 'react';
import { Button, Input, InputNumber, Popup, Select, Space, Switch, Tag, Typography } from 'tdesign-react';
import type { Executor, JsonRecord, Workflow, WorkflowFormState } from '../../../types/admin';
import { StatusBadge } from '../shared/ui';
import { ComfyuiTemplateEditorStatus } from './comfyuiTemplateEditorStatus';

type SelectOption = {
  label: string;
  value: string;
};

type WorkflowEditTab = 'base' | 'io' | 'params' | 'executors' | 'advanced';
type WorkflowParamScope = 'internal' | 'all';

type ComfyInputMapItem = {
  field: string;
  nodeId: string;
  inputKey: string;
  valueType?: string;
};

type ComfyNode = {
  id: string;
  title: string;
  classType: string;
  inputs: string[];
};

type ComfyNodeInputDetail = {
  key: string;
  value: unknown;
  linked: boolean;
  linkRef?: string;
};

type ComfyNodeDetail = {
  id: string;
  title: string;
  classType: string;
  inputs: ComfyNodeInputDetail[];
};

type ComfyWorkflowDependencies = {
  ok: boolean;
  nodes: string[];
  models: {
    unet: string[];
    clip: string[];
    vae: string[];
    lora: string[];
  };
  dynamic: {
    unet: number;
    clip: number;
    vae: number;
    lora: number;
  };
};

type WorkflowExecutorStatus = {
  ready: boolean;
  ok: boolean;
  missing: {
    unet: string[];
    clip: string[];
    vae: string[];
    lora: string[];
    nodes: string[];
  };
};

type ComfyuiTemplatesPanelProps = {
  comfyServerRefreshing: boolean;
  comfyExecutors: Executor[];
  refreshComfyuiServers: () => void;
  comfyServersLoadedCount: number;
  workflows: Workflow[];
  extractAllowedExecutorIds: (metadata?: string | JsonRecord | null) => string[];
  executors: Executor[];
  comfyWorkflowDepsMap: Record<string, ComfyWorkflowDependencies>;
  resolveWorkflowExecutors: (workflow: Workflow) => Executor[];
  evaluateWorkflowOnExecutor: (deps: ComfyWorkflowDependencies, executor: Executor) => WorkflowExecutorStatus;
  parseJSON: (value?: string | JsonRecord) => JsonRecord;
  setWorkflowForm: Dispatch<SetStateAction<WorkflowFormState>>;
  stringifyJSON: (value?: string | JsonRecord) => string;
  setWorkflowFormAllowedExecutors: Dispatch<SetStateAction<string[]>>;
  normalizeInputNodeMap: (metadata?: JsonRecord | null) => ComfyInputMapItem[];
  setWorkflowInputMap: Dispatch<SetStateAction<ComfyInputMapItem[]>>;
  normalizeOutputNodeIds: (metadata?: JsonRecord | null) => string[];
  setWorkflowOutputNodeIds: Dispatch<SetStateAction<string[]>>;
  setWorkflowOutputPickerNodeId: Dispatch<SetStateAction<string>>;
  setWorkflowOutputShowAll: Dispatch<SetStateAction<boolean>>;
  handleWorkflowClone: (workflow: Workflow) => void;
  handleDelete: (kind: 'executor' | 'workflow' | 'binding' | 'apikey', id: string) => void | Promise<void>;
  workflowForm: WorkflowFormState;
  extractComfyuiWorkflowDependencies: (definition?: string | JsonRecord) => ComfyWorkflowDependencies;
  downloadJson: (payload: unknown, filename: string) => void;
  workflowEditTab: WorkflowEditTab;
  setWorkflowEditTab: Dispatch<SetStateAction<WorkflowEditTab>>;
  statusOptions: SelectOption[];
  handleWorkflowFile: (files: FileList | null) => void;
  workflowDefinitionError: string;
  workflowDefinitionNotice: string;
  workflowMetadataError: string;
  workflowCanMap: boolean;
  comfyWorkflowNodes: ComfyNode[];
  workflowInputMap: ComfyInputMapItem[];
  workflowOutputNodeIds: string[];
  workflowInputPickerNodeId: string;
  setWorkflowInputPickerNodeId: Dispatch<SetStateAction<string>>;
  setWorkflowInputPickerKeys: Dispatch<SetStateAction<string[]>>;
  comfyWorkflowNodeMap: Map<string, ComfyNode>;
  workflowInputPickerKeys: string[];
  addWorkflowInputMappingsForNode: () => void;
  addWorkflowInputMap: () => void;
  updateWorkflowInputMap: (index: number, patch: Partial<ComfyInputMapItem>) => void;
  removeWorkflowInputMap: (index: number) => void;
  workflowOutputShowAll: boolean;
  updateWorkflowOutputNodes: (nodeIds: string[]) => void;
  workflowOutputPickerNodeId: string;
  addWorkflowOutputNode: () => void;
  removeWorkflowOutputNode: (nodeId: string) => void;
  workflowMappingErrors: string[];
  workflowNodeSearch: string;
  setWorkflowNodeSearch: Dispatch<SetStateAction<string>>;
  workflowParamScope: WorkflowParamScope;
  setWorkflowParamScope: Dispatch<SetStateAction<WorkflowParamScope>>;
  filteredWorkflowNodeDetails: ComfyNodeDetail[];
  workflowInterfaceNodeIds: Set<string>;
  addWorkflowOutputNodeById: (nodeId: string) => void;
  addWorkflowInputMapEntry: (nodeId: string, inputKey: string) => void;
  updateWorkflowNodeInputValue: (nodeId: string, inputKey: string, value: unknown) => void;
  workflowFormAllowedExecutors: string[];
  syncWorkflowMetadata: (options: { allowedExecutorIds?: string[]; inputMap?: ComfyInputMapItem[]; outputNodeIds?: string[] }) => void;
  workflowFormErrors: string[];
  workflowSubmitDisabled: boolean;
  handleWorkflowSubmit: () => void;
  defaultWorkflowForm: WorkflowFormState;
  setWorkflowFormErrors: Dispatch<SetStateAction<string[]>>;
};

const formControlClass =
  'w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100 dark:placeholder:text-slate-500';
const formControlFlexClass =
  'flex-1 rounded-md border border-slate-300 bg-white px-3 py-2 text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100 dark:placeholder:text-slate-500';

export function ComfyuiTemplatesPanel(props: ComfyuiTemplatesPanelProps) {
  const {
  comfyServerRefreshing,
  comfyExecutors,
  refreshComfyuiServers,
  comfyServersLoadedCount,
  workflows,
  extractAllowedExecutorIds,
  executors,
  comfyWorkflowDepsMap,
  resolveWorkflowExecutors,
  evaluateWorkflowOnExecutor,
  parseJSON,
  setWorkflowForm,
  stringifyJSON,
  setWorkflowFormAllowedExecutors,
  normalizeInputNodeMap,
  setWorkflowInputMap,
  normalizeOutputNodeIds,
  setWorkflowOutputNodeIds,
  setWorkflowOutputPickerNodeId,
  setWorkflowOutputShowAll,
  handleWorkflowClone,
  handleDelete,
  workflowForm,
  extractComfyuiWorkflowDependencies,
  downloadJson,
  workflowEditTab,
  setWorkflowEditTab,
  statusOptions,
  handleWorkflowFile,
  workflowDefinitionError,
  workflowDefinitionNotice,
  workflowMetadataError,
  workflowCanMap,
  comfyWorkflowNodes,
  workflowInputMap,
  workflowOutputNodeIds,
  workflowInputPickerNodeId,
  setWorkflowInputPickerNodeId,
  setWorkflowInputPickerKeys,
  comfyWorkflowNodeMap,
  workflowInputPickerKeys,
  addWorkflowInputMappingsForNode,
  addWorkflowInputMap,
  updateWorkflowInputMap,
  removeWorkflowInputMap,
  workflowOutputShowAll,
  updateWorkflowOutputNodes,
  workflowOutputPickerNodeId,
  addWorkflowOutputNode,
  removeWorkflowOutputNode,
  workflowMappingErrors,
  workflowNodeSearch,
  setWorkflowNodeSearch,
  workflowParamScope,
  setWorkflowParamScope,
  filteredWorkflowNodeDetails,
  workflowInterfaceNodeIds,
  addWorkflowOutputNodeById,
  addWorkflowInputMapEntry,
  updateWorkflowNodeInputValue,
  workflowFormAllowedExecutors,
  syncWorkflowMetadata,
  workflowFormErrors,
  workflowSubmitDisabled,
  handleWorkflowSubmit,
  defaultWorkflowForm,
  setWorkflowFormErrors,
  } = props;

  return (
        <div className="space-y-4">
          <div className="text-sm text-slate-600 dark:text-slate-400">
            管理 ComfyUI 流程模板、输入输出字段和允许运行的线路。普通用户先确认模板是否可运行，再进入高级参数。
          </div>
          <div className="grid gap-3 md:grid-cols-3">
            <div className="rounded-2xl border border-slate-200/70 bg-white/80 px-4 py-3 text-xs dark:border-slate-800 dark:bg-slate-900/40">
              <div className="font-semibold text-slate-900 dark:text-white">先看可运行线路</div>
              <div className="mt-1 text-slate-500">每个模板至少要有一条可运行线路，否则业务调用会失败。</div>
            </div>
            <div className="rounded-2xl border border-slate-200/70 bg-white/80 px-4 py-3 text-xs dark:border-slate-800 dark:bg-slate-900/40">
              <div className="font-semibold text-slate-900 dark:text-white">再看输入输出</div>
              <div className="mt-1 text-slate-500">只暴露业务需要填写的字段，输出建议只选最终图片节点。</div>
            </div>
            <div className="rounded-2xl border border-slate-200/70 bg-white/80 px-4 py-3 text-xs dark:border-slate-800 dark:bg-slate-900/40">
              <div className="font-semibold text-slate-900 dark:text-white">最后改高级参数</div>
              <div className="mt-1 text-slate-500">JSON 和内部节点编号只给开发排查使用，不作为普通配置入口。</div>
            </div>
          </div>
          <Space align="center" size="small">
            <Button
              variant="outline"
              disabled={comfyServerRefreshing || comfyExecutors.length === 0}
              onClick={refreshComfyuiServers}
            >
              {comfyServerRefreshing ? '刷新中…' : '刷新线路能力'}
            </Button>
            <Typography.Text theme="secondary">
              已检查 {comfyServersLoadedCount}/{comfyExecutors.length} 条线路
            </Typography.Text>
          </Space>
          <div className="grid gap-6 lg:grid-cols-[320px_1fr] lg:items-start">
          <div className="rounded-2xl border border-slate-200/70 bg-white/80 p-4 dark:border-slate-800 dark:bg-slate-900/40 lg:sticky lg:top-4">
            <h3 className="mb-4 text-lg font-semibold text-slate-900 dark:text-white">流程模板列表</h3>
            <div className="max-h-[460px] overflow-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-left text-[11px] text-slate-700 dark:text-slate-400">
                    <th>业务入口</th>
                    <th>名称</th>
                    <th>版本</th>
                    <th>允许运行线路</th>
                    <th>可运行线路</th>
                    <th>状态</th>
                    <th>更新时间</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {workflows.map((wf) => (
                    <tr key={wf.id}>
                      <td className="text-slate-800 dark:text-slate-300">{wf.action}</td>
                      <td className="font-medium text-slate-900 dark:text-white">{wf.name}</td>
                      <td className="text-slate-800 dark:text-slate-300">{wf.version}</td>
                      <td className="text-xs text-slate-700 dark:text-slate-400">
                        {(() => {
                          const allowedIds = extractAllowedExecutorIds(wf.metadata);
                          if (allowedIds.length === 0) return '未限制（匹配任意 ComfyUI 线路）';
                          return allowedIds
                            .map((id) => {
                              const exec = executors.find((executor) => executor.id === id);
                              return exec ? `${exec.name}` : id;
                            })
                            .join('、');
                        })()}
                      </td>
                      <td className="text-xs text-slate-700 dark:text-slate-400">
                        {(() => {
                          if (!(wf.type || '').toLowerCase().includes('comfyui')) return '—';
                          const deps = comfyWorkflowDepsMap[wf.id];
                          if (!deps || !deps.ok) {
                            return (
                              <Tag theme="warning" variant="light">
                                未解析
                              </Tag>
                            );
                          }
                          const candidates = resolveWorkflowExecutors(wf);
                          if (candidates.length === 0) return '未绑定';
                          const statuses = candidates.map((executor) => ({
                            executor,
                            status: evaluateWorkflowOnExecutor(deps, executor),
                          }));
                          const okServers = statuses.filter((item) => item.status.ok);
                          const readyCount = statuses.filter((item) => item.status.ready).length;
                          const summary = (
                            <div className="space-y-2 text-xs text-slate-700">
                              <div className="font-semibold">
                                可运行 {okServers.length}/{candidates.length}
                              </div>
                              <div className="text-[11px] text-slate-500">
                                已拉取 {readyCount}/{candidates.length} 台
                              </div>
                              <div className="space-y-1">
                                {statuses.map((item) => {
                                  const missing = item.status.missing;
                                  const missingParts = [
                                    missing.unet.length ? `UNET ${missing.unet.length}` : null,
                                    missing.clip.length ? `CLIP ${missing.clip.length}` : null,
                                    missing.vae.length ? `VAE ${missing.vae.length}` : null,
                                    missing.lora.length ? `LoRA ${missing.lora.length}` : null,
                                    missing.nodes.length ? `插件 ${missing.nodes.length}` : null,
                                  ].filter(Boolean);
                                  return (
                                    <div key={`workflow-server-${wf.id}-${item.executor.id}`} className="flex justify-between gap-2">
                                      <span>{item.executor.name}</span>
                                      <span className="text-[11px] text-slate-500">
                                        {item.status.ready ? (item.status.ok ? '可用' : missingParts.join(' · ')) : '未拉取'}
                                      </span>
                                    </div>
                                  );
                                })}
                              </div>
                              {(deps.dynamic.unet + deps.dynamic.clip + deps.dynamic.vae + deps.dynamic.lora) > 0 ? (
                                <div className="text-[11px] text-amber-600">
                                  含动态模型输入，未完全校验。
                                </div>
                              ) : null}
                            </div>
                          );
                          return (
                            <Popup trigger="hover" placement="right" content={summary}>
                              <Tag theme={okServers.length > 0 ? 'success' : 'warning'} variant="light">
                                {okServers.length}/{candidates.length}
                              </Tag>
                            </Popup>
                          );
                        })()}
                      </td>
                      <td>
                        <StatusBadge status={wf.status || 'inactive'} />
                      </td>
                      <td className="text-xs text-slate-700 dark:text-slate-500">{wf.updated_at || '—'}</td>
                      <td className="text-right text-xs space-x-2">
                        <button
                          className="text-sky-400"
                          onClick={() => {
                            const { definition, metadata, ...rest } = wf;
                            const parsedMeta = (metadata ? parseJSON(metadata) : {}) as JsonRecord;
                            setWorkflowForm({
                              ...rest,
                              definition: stringifyJSON(definition),
                              metadata: stringifyJSON(metadata),
                            });
                            setWorkflowFormAllowedExecutors(extractAllowedExecutorIds(parsedMeta));
                            setWorkflowInputMap(normalizeInputNodeMap(parsedMeta));
                            setWorkflowOutputNodeIds(normalizeOutputNodeIds(parsedMeta));
                            setWorkflowOutputPickerNodeId('');
                            setWorkflowOutputShowAll(false);
                          }}
                        >
                          编辑
                        </button>
                        <button
                          className="text-emerald-400"
                          onClick={() => handleWorkflowClone(wf)}
                        >
                          复制为新版本
                        </button>
                        <button className="text-red-400" onClick={() => handleDelete('workflow', wf.id)}>
                          删除
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          <div className="rounded-2xl border border-slate-200/70 bg-white/80 p-4 space-y-3 dark:border-slate-800 dark:bg-slate-900/40">
            <h3 className="text-lg font-semibold text-slate-900 dark:text-white">
              {workflowForm.id ? '编辑流程模板' : '导入/新增流程模板'}
            </h3>
            <div className="flex flex-wrap gap-2">
              <button
                className="rounded border border-slate-300 bg-white px-3 py-1 text-xs text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-950/60 dark:text-slate-200 dark:hover:bg-slate-900/60"
                onClick={() => {
                  const deps = extractComfyuiWorkflowDependencies(workflowForm.definition);
                  if (!deps.ok) {
                    alert('流程模板 JSON 解析失败，无法导出依赖。');
                    return;
                  }
                  const payload = {
                    workflow: {
                      id: workflowForm.id || '',
                      action: workflowForm.action || '',
                      name: workflowForm.name || '',
                      version: workflowForm.version || '',
                    },
                    dependencies: deps,
                    generatedAt: new Date().toISOString(),
                  };
                  const suffix = workflowForm.action || workflowForm.name || 'workflow';
                  downloadJson(payload, `comfyui-workflow-deps-${suffix}.json`);
                }}
              >
                导出依赖清单
              </button>
            </div>
            <div className="flex flex-wrap gap-2 text-xs">
              {[
                { id: 'base', label: '基础信息' },
                { id: 'io', label: '输入/输出' },
                { id: 'params', label: '高级调参' },
                { id: 'executors', label: '运行线路' },
                { id: 'advanced', label: '高级 JSON' },
              ].map((tab) => (
                <button
                  key={`workflow-edit-tab-${tab.id}`}
                  className={`rounded-full px-3 py-1 ${
                    workflowEditTab === tab.id
                      ? 'bg-slate-900 text-white dark:bg-white dark:text-slate-900'
                      : 'border border-slate-300 bg-white text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-950/60 dark:text-slate-200 dark:hover:bg-slate-900/60'
                  }`}
                  onClick={() => setWorkflowEditTab(tab.id as typeof workflowEditTab)}
                >
                  {tab.label}
                </button>
              ))}
            </div>
            <ComfyuiTemplateEditorStatus
              workflowForm={workflowForm}
              workflowInputCount={workflowInputMap.length}
              workflowOutputCount={workflowOutputNodeIds.length}
              allowedExecutorCount={workflowFormAllowedExecutors.length}
              workflowDefinitionError={workflowDefinitionError}
              workflowMetadataError={workflowMetadataError}
              workflowMappingErrorCount={workflowMappingErrors.length}
              workflowFormErrorCount={workflowFormErrors.length}
            />
            {workflowEditTab === 'base' && (
            <div className="text-sm space-y-2">
              <input
                placeholder="业务入口，例如 pattern.extract"
                value={workflowForm.action || ''}
                onChange={(e) => setWorkflowForm({ ...workflowForm, action: e.target.value })}
                className={formControlClass}
              />
              <input
                placeholder="名称"
                value={workflowForm.name || ''}
                onChange={(e) => setWorkflowForm({ ...workflowForm, name: e.target.value })}
                className={formControlClass}
              />
              <div className="flex gap-3">
                <input
                  placeholder="版本"
                  value={workflowForm.version || ''}
                  onChange={(e) => setWorkflowForm({ ...workflowForm, version: e.target.value })}
                  className={formControlFlexClass}
                />
                <input
                  placeholder="类型"
                  value={workflowForm.type || ''}
                  onChange={(e) => setWorkflowForm({ ...workflowForm, type: e.target.value })}
                  className={formControlFlexClass}
                />
              </div>
              <select
                value={workflowForm.status || 'inactive'}
                onChange={(e) => setWorkflowForm({ ...workflowForm, status: e.target.value })}
                className={formControlClass}
              >
                {statusOptions.map((option) => (
                  <option key={`workflow-status-${option.value}`} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
              <label className="block text-xs text-slate-700 dark:text-slate-400">
                导入 JSON 文件
                <input
                  type="file"
                  accept=".json"
                  onChange={(e) => handleWorkflowFile(e.target.files)}
                  className="mt-1 block w-full text-xs text-slate-700 file:mr-3 file:rounded-lg file:border file:border-slate-300 file:bg-white file:px-3 file:py-1 file:text-xs file:text-slate-700 hover:file:bg-slate-50 dark:text-slate-300 dark:file:border-slate-700 dark:file:bg-slate-950/50 dark:file:text-slate-200 dark:hover:file:bg-slate-900/60"
                />
              </label>
              <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-xs text-slate-600 dark:border-slate-800 dark:bg-slate-950/40 dark:text-slate-400">
                导入后优先检查“输入/输出”和“运行线路”。只有需要排查模板内容或手动修改映射时，再进入“高级 JSON”。
              </div>
            </div>
            )}
            {workflowEditTab === 'advanced' && (
            <div className="text-sm space-y-3">
              <div className="rounded-2xl border border-amber-200/80 bg-amber-50/80 px-4 py-3 text-xs text-amber-700 dark:border-amber-900/50 dark:bg-amber-950/30 dark:text-amber-200">
                这里是开发排查区。修改配置原文可能影响输入输出映射、允许运行线路和调度结果；不确定时不要直接改。
              </div>
              <textarea
                rows={6}
                placeholder="流程模板 JSON（来自 ComfyUI 导出的 API JSON）"
                value={workflowForm.definition ?? ''}
                onChange={(e) => setWorkflowForm({ ...workflowForm, definition: e.target.value })}
                className={`${formControlClass} font-mono text-xs`}
              />
              {workflowDefinitionError ? (
                <div className="text-xs text-rose-500">{workflowDefinitionError}</div>
              ) : null}
              {workflowDefinitionNotice ? (
                <div className="text-xs text-amber-600">{workflowDefinitionNotice}</div>
              ) : null}
              <textarea
                rows={4}
                placeholder="高级配置原文（参数映射、依赖、允许运行线路等）"
                value={workflowForm.metadata ?? ''}
                onChange={(e) => setWorkflowForm({ ...workflowForm, metadata: e.target.value })}
                className={`${formControlClass} font-mono text-xs`}
              />
              {workflowMetadataError ? (
                <div className="text-xs text-rose-500">{workflowMetadataError}</div>
              ) : null}
            </div>
            )}
            {workflowEditTab === 'io' && (
              <div className="space-y-3">
                {workflowCanMap ? (
                  <div className="rounded-2xl border border-slate-200/70 bg-slate-50/80 p-3 space-y-3 dark:border-slate-800 dark:bg-slate-950/40">
                    <div className="flex items-center justify-between">
                      <div className="text-sm font-semibold text-slate-900 dark:text-white">输入输出映射（ComfyUI）</div>
                      <div className="text-[11px] text-slate-500">
                        {comfyWorkflowNodes.length > 0 ? `已解析 ${comfyWorkflowNodes.length} 个节点` : '未解析节点'}
                      </div>
                    </div>
                    <p className="text-xs text-slate-600 dark:text-slate-400">
                      选择需要给业务方填写的输入字段和最终输出节点。未选择输出节点时默认返回全部输出；输入未填写时将使用流程模板 JSON
                      默认值。
                    </p>
                    <div className="grid gap-2 md:grid-cols-3">
                      <div className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs dark:border-slate-800 dark:bg-slate-950/40">
                        <div className="text-slate-500">业务输入字段</div>
                        <div className="mt-1 text-base font-semibold text-slate-900 dark:text-white">{workflowInputMap.length}</div>
                      </div>
                      <div className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs dark:border-slate-800 dark:bg-slate-950/40">
                        <div className="text-slate-500">最终输出位置</div>
                        <div className="mt-1 text-base font-semibold text-slate-900 dark:text-white">
                          {workflowOutputNodeIds.length || '全部'}
                        </div>
                      </div>
                      <div className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs dark:border-slate-800 dark:bg-slate-950/40">
                        <div className="text-slate-500">已识别模板位置</div>
                        <div className="mt-1 text-base font-semibold text-slate-900 dark:text-white">{comfyWorkflowNodes.length}</div>
                      </div>
                    </div>
                    <div className="space-y-3">
                      <div className="rounded-2xl border border-slate-200/70 bg-white/70 p-3 space-y-2 dark:border-slate-800 dark:bg-slate-950/50">
                        <div className="text-xs text-slate-700 dark:text-slate-300">快速添加业务输入字段</div>
                        <div className="space-y-2">
                          <label className="block text-[11px] text-slate-600 dark:text-slate-400">来源位置（高级，含 ID）</label>
                          <select
                            value={workflowInputPickerNodeId}
                            onChange={(e) => {
                              setWorkflowInputPickerNodeId(e.target.value);
                              setWorkflowInputPickerKeys([]);
                            }}
                            className="w-full rounded-2xl border border-slate-300 bg-white px-3 py-2 text-xs text-slate-900 dark:border-slate-700 dark:bg-slate-950/70 dark:text-white"
                          >
                            <option value="">选择来源位置（含 ID）</option>
                            {comfyWorkflowNodes.map((node) => (
                              <option key={`workflow-picker-node-${node.id}`} value={node.id}>
                                #{node.id} · {node.title} · {node.classType}
                              </option>
                            ))}
                          </select>
                          <div className="flex items-center justify-between text-[11px] text-slate-600 dark:text-slate-400">
                            <span>可暴露字段（勾选）</span>
                            <div className="space-x-2">
                              <button
                                className="text-slate-500 hover:text-slate-700 dark:hover:text-slate-300"
                                onClick={() =>
                                  setWorkflowInputPickerKeys(
                                    comfyWorkflowNodeMap.get(workflowInputPickerNodeId)?.inputs || [],
                                  )
                                }
                                disabled={!workflowInputPickerNodeId}
                              >
                                全选
                              </button>
                              <button
                                className="text-slate-500 hover:text-slate-700 dark:hover:text-slate-300"
                                onClick={() => setWorkflowInputPickerKeys([])}
                                disabled={!workflowInputPickerNodeId}
                              >
                                清空
                              </button>
                            </div>
                          </div>
                          <div className="h-28 w-full overflow-auto rounded-2xl border border-slate-300 bg-white px-3 py-2 text-xs text-slate-900 dark:border-slate-700 dark:bg-slate-950/70 dark:text-white">
                            {!workflowInputPickerNodeId ? (
                              <div className="text-slate-500 dark:text-slate-500">请先选择来源位置</div>
                            ) : (
                              (comfyWorkflowNodeMap.get(workflowInputPickerNodeId)?.inputs || []).map((key) => (
                                <label
                                  key={`workflow-picker-input-${workflowInputPickerNodeId}-${key}`}
                                  className="flex items-center gap-2 py-0.5"
                                >
                                  <input
                                    type="checkbox"
                                    checked={workflowInputPickerKeys.includes(key)}
                                    onChange={(e) =>
                                      setWorkflowInputPickerKeys((prev) =>
                                        e.target.checked ? [...prev, key] : prev.filter((item) => item !== key),
                                      )
                                    }
                                  />
                                  <span>{key}</span>
                                </label>
                              ))
                            )}
                          </div>
                          <button
                            className="w-full rounded border border-slate-300 bg-white px-3 py-2 text-xs text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-700 dark:bg-slate-950/60 dark:text-slate-200 dark:hover:bg-slate-900/60"
                            onClick={addWorkflowInputMappingsForNode}
                            disabled={!workflowInputPickerNodeId || workflowInputPickerKeys.length === 0}
                          >
                            添加到映射
                          </button>
                        </div>
                        <p className="text-[11px] text-slate-600 dark:text-slate-500">
                          系统仍按位置 ID 保存配置；每个输入会自动生成一条映射，字段名默认等于原始输入名，可在下方继续调整。
                        </p>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-slate-700 dark:text-slate-400">业务输入字段</span>
                        <button
                          className="rounded border border-slate-300 bg-white px-2 py-1 text-xs text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-950/60 dark:text-slate-200 dark:hover:bg-slate-900/60"
                          onClick={addWorkflowInputMap}
                        >
                          添加映射
                        </button>
                      </div>
                      {workflowInputMap.length === 0 ? (
                        <div className="rounded-2xl border border-dashed border-slate-300 bg-white px-4 py-3 text-xs text-slate-600 dark:border-slate-700 dark:bg-slate-950/50 dark:text-slate-500">
                          尚未配置输入字段。可选择业务方需要填写的字段。
                        </div>
                      ) : (
                        <div className="space-y-2">
                          <div className="grid grid-cols-[1.2fr_1fr_1fr_0.6fr_auto] gap-2 text-[11px] text-slate-500">
                            <div>业务字段名</div>
                            <div>来源位置</div>
                            <div>原始输入名</div>
                            <div>类型</div>
                            <div></div>
                          </div>
                          {workflowInputMap.map((item, idx) => {
                            const node = comfyWorkflowNodeMap.get(item.nodeId);
                            const inputOptions = node?.inputs || [];
                            return (
                              <div
                                key={`workflow-input-${idx}`}
                                className="grid grid-cols-[1.2fr_1fr_1fr_0.6fr_auto] gap-2"
                              >
                                <input
                                  value={item.field}
                                  onChange={(e) => updateWorkflowInputMap(idx, { field: e.target.value })}
                                  placeholder="业务字段名，如 prompt / width"
                                  className="rounded-2xl border border-slate-300 bg-white px-3 py-2 text-xs text-slate-900 dark:border-slate-700 dark:bg-slate-950/70 dark:text-white"
                                />
                                <select
                                  value={item.nodeId}
                                  onChange={(e) => updateWorkflowInputMap(idx, { nodeId: e.target.value, inputKey: '' })}
                                  className="rounded-2xl border border-slate-300 bg-white px-3 py-2 text-xs text-slate-900 dark:border-slate-700 dark:bg-slate-950/70 dark:text-white"
                                >
                                  <option value="">选择来源位置</option>
                                  {comfyWorkflowNodes.map((nodeOption) => (
                                    <option key={`workflow-node-${nodeOption.id}`} value={nodeOption.id}>
                                      #{nodeOption.id} · {nodeOption.title}
                                    </option>
                                  ))}
                                </select>
                                <select
                                  value={item.inputKey}
                                  onChange={(e) => updateWorkflowInputMap(idx, { inputKey: e.target.value })}
                                  disabled={!item.nodeId}
                                  className="rounded-2xl border border-slate-300 bg-white px-3 py-2 text-xs text-slate-900 disabled:bg-slate-100 dark:border-slate-700 dark:bg-slate-950/70 dark:text-white dark:disabled:bg-slate-900/40"
                                >
                                  <option value="">选择输入</option>
                                  {inputOptions.map((key) => (
                                    <option key={`workflow-input-${item.nodeId}-${key}`} value={key}>
                                      {key}
                                    </option>
                                  ))}
                                </select>
                                <select
                                  value={item.valueType || ''}
                                  onChange={(e) => updateWorkflowInputMap(idx, { valueType: e.target.value })}
                                  className="rounded-2xl border border-slate-300 bg-white px-3 py-2 text-xs text-slate-900 dark:border-slate-700 dark:bg-slate-950/70 dark:text-white"
                                >
                                  <option value="">原样</option>
                                  <option value="string">string</option>
                                  <option value="int">int</option>
                                  <option value="float">float</option>
                                  <option value="bool">bool</option>
                                  <option value="json">json</option>
                                </select>
                                <button
                                  className="rounded border border-slate-200 bg-white px-2 py-1 text-xs text-slate-600 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-950/60 dark:text-slate-200 dark:hover:bg-slate-900/60"
                                  onClick={() => removeWorkflowInputMap(idx)}
                                >
                                  删除
                                </button>
                              </div>
                            );
                          })}
                        </div>
                      )}
                      <div className="mt-4 space-y-2">
                        <div className="flex items-center justify-between">
                          <span className="text-xs text-slate-700 dark:text-slate-400">最终输出位置（保存图片为主）</span>
                          <div className="space-x-2 text-[11px]">
                            <button
                              className="text-slate-500 hover:text-slate-700 dark:hover:text-slate-300"
                              onClick={() => setWorkflowOutputShowAll((prev) => !prev)}
                            >
                              {workflowOutputShowAll ? '仅显示 SaveImage' : '显示全部位置'}
                            </button>
                            <button
                              className="text-slate-500 hover:text-slate-700 dark:hover:text-slate-300"
                              onClick={() => updateWorkflowOutputNodes([])}
                            >
                              清空输出
                            </button>
                          </div>
                        </div>
                        <div className="grid grid-cols-[1fr_auto] gap-2">
                          <select
                            value={workflowOutputPickerNodeId}
                            onChange={(e) => setWorkflowOutputPickerNodeId(e.target.value)}
                            className="rounded-2xl border border-slate-300 bg-white px-3 py-2 text-xs text-slate-900 dark:border-slate-700 dark:bg-slate-950/70 dark:text-white"
                          >
                            <option value="">选择最终输出位置（含 ID）</option>
                            {(workflowOutputShowAll
                              ? comfyWorkflowNodes
                              : comfyWorkflowNodes.filter((node) => node.classType.toLowerCase().includes('saveimage'))
                            ).map((node) => (
                              <option key={`workflow-output-picker-${node.id}`} value={node.id}>
                                #{node.id} · {node.title} · {node.classType}
                              </option>
                            ))}
                          </select>
                          <button
                            className="rounded border border-slate-300 bg-white px-3 py-2 text-xs text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-700 dark:bg-slate-950/60 dark:text-slate-200 dark:hover:bg-slate-900/60"
                            onClick={addWorkflowOutputNode}
                            disabled={!workflowOutputPickerNodeId}
                          >
                            添加映射
                          </button>
                        </div>
                        {workflowOutputNodeIds.length === 0 ? (
                          <div className="rounded-2xl border border-dashed border-slate-300 bg-white px-4 py-3 text-xs text-slate-600 dark:border-slate-700 dark:bg-slate-950/50 dark:text-slate-500">
                            未选择最终输出位置时，默认返回全部输出（建议选择 SaveImage 位置）。
                          </div>
                        ) : (
                          <div className="space-y-2">
                            <div className="grid grid-cols-[1fr_auto] gap-2 text-[11px] text-slate-500">
                              <div>已选最终输出位置</div>
                              <div></div>
                            </div>
                            {workflowOutputNodeIds.map((nodeId) => {
                              const node = comfyWorkflowNodeMap.get(nodeId);
                              const label = node ? `#${node.id} · ${node.title} · ${node.classType}` : `#${nodeId}`;
                              return (
                                <div key={`workflow-output-picked-${nodeId}`} className="grid grid-cols-[1fr_auto] gap-2">
                                  <div className="rounded-2xl border border-slate-300 bg-white px-3 py-2 text-xs text-slate-900 dark:border-slate-700 dark:bg-slate-950/70 dark:text-white">
                                    {label}
                                  </div>
                                  <button
                                    className="rounded border border-slate-200 bg-white px-2 py-1 text-xs text-slate-600 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-950/60 dark:text-slate-200 dark:hover:bg-slate-900/60"
                                    onClick={() => removeWorkflowOutputNode(nodeId)}
                                  >
                                    删除
                                  </button>
                                </div>
                              );
                            })}
                          </div>
                        )}
                        <p className="text-[11px] text-slate-600 dark:text-slate-500">
                          输出建议只选最终 SaveImage 位置，避免返回无用的中间数据。
                        </p>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="rounded-2xl border border-dashed border-slate-300 bg-white px-4 py-6 text-xs text-slate-600 dark:border-slate-700 dark:bg-slate-950/50 dark:text-slate-500">
                    请先从左侧选择流程模板或导入流程模板 JSON，再配置输入/输出节点。
                  </div>
                )}
                {workflowMappingErrors.length > 0 ? (
                  <div className="rounded-2xl border border-rose-200/80 bg-rose-50/80 p-3 text-xs text-rose-600 dark:border-rose-900/50 dark:bg-rose-950/30">
                    <div className="font-semibold">映射校验未通过：</div>
                    <ul className="mt-2 list-disc space-y-1 pl-5">
                      {workflowMappingErrors.slice(0, 8).map((msg, idx) => (
                        <li key={`workflow-map-error-${idx}`}>{msg}</li>
                      ))}
                    </ul>
                    {workflowMappingErrors.length > 8 ? (
                      <div className="mt-2">…共 {workflowMappingErrors.length} 条</div>
                    ) : null}
                  </div>
                ) : null}
              </div>
            )}
            {workflowEditTab === 'params' && (
              <div className="space-y-3">
              {!workflowCanMap ? (
                <div className="rounded-2xl border border-dashed border-slate-300 bg-white px-4 py-6 text-xs text-slate-600 dark:border-slate-700 dark:bg-slate-950/50 dark:text-slate-500">
                  请先从左侧选择流程模板或导入流程模板 JSON，再调整高级参数。
                </div>
              ) : (
                    <div className="rounded-2xl border border-slate-200/70 bg-white/70 p-3 space-y-3 dark:border-slate-800 dark:bg-slate-950/50">
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div>
                          <div className="text-xs font-semibold text-slate-800 dark:text-slate-200">流程模板参数（高级）</div>
                          <div className="text-[11px] text-slate-500">
                            输入/输出节点作为业务接口；其他节点用于版本迭代与内部调参。
                          </div>
                        </div>
                        <div className="flex flex-wrap items-center gap-2 text-xs">
                          <Input
                            value={workflowNodeSearch}
                            onChange={(v) => setWorkflowNodeSearch(String(v))}
                            placeholder="搜索位置 ID / 名称 / 类型"
                          />
                          <Select
                            value={workflowParamScope}
                            onChange={(v) => setWorkflowParamScope(v === 'all' ? 'all' : 'internal')}
                            options={[
                              { label: '仅内部位置', value: 'internal' },
                              { label: '全部位置', value: 'all' },
                            ]}
                          />
                        </div>
                      </div>
                      {filteredWorkflowNodeDetails.length === 0 ? (
                        <div className="rounded-2xl border border-dashed border-slate-300 bg-white px-4 py-3 text-xs text-slate-600 dark:border-slate-700 dark:bg-slate-950/50 dark:text-slate-500">
                          暂无可编辑节点，请先导入流程模板 JSON 或切换筛选条件。
                        </div>
                      ) : (
                        <div className="max-h-[420px] space-y-2 overflow-auto pr-1">
                          {filteredWorkflowNodeDetails.map((node) => {
                            const isInterface = workflowInterfaceNodeIds.has(node.id);
                            return (
                              <div
                                key={`workflow-node-detail-${node.id}`}
                                className="rounded-2xl border border-slate-200/70 bg-white p-3 text-xs text-slate-700 dark:border-slate-800 dark:bg-slate-950/40 dark:text-slate-300"
                              >
                                <div className="flex flex-wrap items-center justify-between gap-2">
                                  <div className="font-semibold text-slate-900 dark:text-white">
                                    #{node.id} · {node.title} · {node.classType}
                                  </div>
                                  <div className="flex flex-wrap items-center gap-2">
                                    {isInterface ? (
                                      <Tag theme="primary" variant="light" size="small">
                                        已对外使用
                                      </Tag>
                                    ) : (
                                      <Tag theme="default" variant="light" size="small">
                                        内部位置
                                      </Tag>
                                    )}
                                      <Button
                                        size="small"
                                        theme="default"
                                        variant="text"
                                        onClick={() => addWorkflowOutputNodeById(node.id)}
                                      >
                                        设为最终输出
                                      </Button>
                                  </div>
                                </div>
                                {node.inputs.length === 0 ? (
                                  <div className="mt-2 text-[11px] text-slate-500">无可编辑参数</div>
                                ) : (
                                  <div className="mt-2 space-y-2">
                                    {node.inputs.map((input) => {
                                      if (input.linked) {
                                        return (
                                          <div key={`workflow-node-${node.id}-input-${input.key}`} className="flex items-center justify-between gap-3">
                                            <span className="text-slate-600">{input.key}</span>
                                            <span className="text-[11px] text-slate-400">连接 {input.linkRef || '上游节点'}</span>
                                          </div>
                                        );
                                      }
                                      const value = input.value;
                                      if (typeof value === 'boolean') {
                                        return (
                                          <div key={`workflow-node-${node.id}-input-${input.key}`} className="flex items-center justify-between gap-3">
                                            <span className="text-slate-600">{input.key}</span>
                                            <div className="flex items-center gap-2">
                                              <Button
                                                size="small"
                                                theme="default"
                                                variant="text"
                                                onClick={() => addWorkflowInputMapEntry(node.id, input.key)}
                                              >
                                                设为业务字段
                                              </Button>
                                              <Switch
                                                value={value}
                                                onChange={(v) => updateWorkflowNodeInputValue(node.id, input.key, Boolean(v))}
                                              />
                                            </div>
                                          </div>
                                        );
                                      }
                                      if (typeof value === 'number') {
                                        return (
                                          <div key={`workflow-node-${node.id}-input-${input.key}`} className="flex items-center justify-between gap-3">
                                            <span className="text-slate-600">{input.key}</span>
                                            <div className="flex items-center gap-2">
                                              <Button
                                                size="small"
                                                theme="default"
                                                variant="text"
                                                onClick={() => addWorkflowInputMapEntry(node.id, input.key)}
                                              >
                                                设为业务字段
                                              </Button>
                                              <InputNumber
                                                value={value}
                                                onChange={(v) => updateWorkflowNodeInputValue(node.id, input.key, Number(v))}
                                                placeholder="数值"
                                              />
                                            </div>
                                          </div>
                                        );
                                      }
                                      if (typeof value === 'string' || value === null || value === undefined) {
                                        return (
                                          <div key={`workflow-node-${node.id}-input-${input.key}`} className="flex items-center justify-between gap-3">
                                            <span className="text-slate-600">{input.key}</span>
                                            <div className="flex items-center gap-2">
                                              <Button
                                                size="small"
                                                theme="default"
                                                variant="text"
                                                onClick={() => addWorkflowInputMapEntry(node.id, input.key)}
                                              >
                                                设为业务字段
                                              </Button>
                                              <Input
                                                value={value ?? ''}
                                                onChange={(v) => updateWorkflowNodeInputValue(node.id, input.key, String(v))}
                                                placeholder="文本"
                                              />
                                            </div>
                                          </div>
                                        );
                                      }
                                      return (
                                        <div key={`workflow-node-${node.id}-input-${input.key}`} className="space-y-1">
                                          <div className="flex items-center justify-between gap-3">
                                            <span className="text-slate-600">{input.key}</span>
                                            <div className="flex items-center gap-2 text-[11px] text-slate-400">
                                              <Button
                                                size="small"
                                                theme="default"
                                                variant="text"
                                                onClick={() => addWorkflowInputMapEntry(node.id, input.key)}
                                              >
                                                设为业务字段
                                              </Button>
                                              <span>复杂结构</span>
                                            </div>
                                          </div>
                                          <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-[11px] text-slate-500 dark:border-slate-800 dark:bg-slate-900/50">
                                            {JSON.stringify(value)}
                                          </div>
                                          <div className="text-[11px] text-slate-400">
                                            复杂参数请在 JSON 编辑区修改。
                                          </div>
                                        </div>
                                      );
                                    })}
                                  </div>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>
                )}
              </div>
            )}
            {workflowEditTab === 'executors' && (
              <label className="block text-xs text-slate-700 dark:text-slate-400">
                允许运行线路（多选）
                {comfyExecutors.length > 0 ? (
                  <select
                    multiple
                    value={workflowFormAllowedExecutors}
                    onChange={(e) =>
                      (() => {
                        const next = Array.from(e.target.selectedOptions).map((option) => option.value);
                        setWorkflowFormAllowedExecutors(next);
                        syncWorkflowMetadata({ allowedExecutorIds: next });
                      })()
                    }
                    className="mt-1 h-32 w-full rounded-2xl border border-slate-300 bg-white px-4 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-950/70 dark:text-white"
                  >
                    {comfyExecutors.map((executor) => (
                      <option key={`workflow-executor-${executor.id}`} value={executor.id}>
                        {executor.name} · {executor.base_url || executor.type}
                      </option>
                    ))}
                  </select>
                ) : (
                  <div className="mt-1 rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-4 py-3 text-slate-700 dark:border-slate-700 dark:bg-slate-950/40 dark:text-slate-500">
                    还没有 ComfyUI 类型的运行线路，请先在“运行线路”中新建，再回到此处绑定允许运行的机器列表。
                  </div>
                )}
                <p className="mt-1 text-[11px] text-slate-700 dark:text-slate-500">
                  用于限制某个 ComfyUI 流程模板可以在哪些机器上执行；保存后会写入允许运行线路，调度器会据此路由。
                </p>
              </label>
            )}
              {workflowFormErrors.length > 0 ? (
                <div className="rounded-2xl border border-rose-200/80 bg-rose-50/80 p-3 text-xs text-rose-600 dark:border-rose-900/50 dark:bg-rose-950/30">
                  <div className="font-semibold">请先处理以下问题：</div>
                  <ul className="mt-2 list-disc space-y-1 pl-5">
                    {workflowFormErrors.slice(0, 8).map((msg, idx) => (
                      <li key={`workflow-form-error-${idx}`}>{msg}</li>
                    ))}
                  </ul>
                  {workflowFormErrors.length > 8 ? <div className="mt-2">…共 {workflowFormErrors.length} 条</div> : null}
                </div>
              ) : null}
              <div className="flex gap-3">
                <button
                  className={`flex-1 rounded py-2 text-white ${
                    workflowSubmitDisabled
                      ? 'bg-slate-400/60 text-slate-200 cursor-not-allowed'
                      : 'bg-sky-500/80 hover:bg-sky-500'
                  }`}
                  onClick={handleWorkflowSubmit}
                  disabled={workflowSubmitDisabled}
                >
                  保存
                </button>
                {workflowForm.id && (
                <button
                  className="rounded border border-slate-300 bg-white px-4 py-2 text-slate-700 hover:bg-slate-50 dark:border-slate-500 dark:bg-transparent dark:text-slate-200"
                  onClick={() => {
                    setWorkflowForm(defaultWorkflowForm);
                    setWorkflowFormAllowedExecutors([]);
                    setWorkflowInputMap([]);
                    setWorkflowOutputNodeIds([]);
                    setWorkflowOutputPickerNodeId('');
                    setWorkflowOutputShowAll(false);
                    setWorkflowFormErrors([]);
                  }}
                >
                  取消
                </button>
              )}
            </div>
            </div>
          </div>
        </div>
  );
}
