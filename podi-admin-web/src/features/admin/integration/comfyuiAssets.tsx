import { Alert, Button, Card, Col, Dialog, Input, Popup, Row, Select, Space, Tag, Textarea, Typography } from 'tdesign-react';
import type { ComfyuiModelCatalogItem, ComfyuiPluginCatalogItem, ComfyuiVersionCatalogItem, Executor } from '../../../types/admin';
import { StatusBadge } from '../shared/ui';
import { formatDateTime } from './formatters';

type SelectOption = {
  label: string;
  value: string;
};

type ComfyuiAssetsPanelProps = {
  executors: Executor[];
  versionItems: ComfyuiVersionCatalogItem[];
  versionLoading: boolean;
  versionError?: string | null;
  versionSearch: string;
  versionStatus: string;
  versionServerLoading: boolean;
  versionSyncing: boolean;
  versionUsage: Map<string, string[]>;
  versionDialogOpen: boolean;
  versionSaving: boolean;
  versionForm: Partial<ComfyuiVersionCatalogItem>;
  versionFormError?: string | null;
  modelItems: ComfyuiModelCatalogItem[];
  modelLoading: boolean;
  modelError?: string | null;
  modelSearch: string;
  modelType: string;
  modelStatus: string;
  modelDialogOpen: boolean;
  modelSaving: boolean;
  modelForm: Partial<ComfyuiModelCatalogItem>;
  modelFormTags: string;
  modelFormError?: string | null;
  pluginItems: ComfyuiPluginCatalogItem[];
  pluginLoading: boolean;
  pluginError?: string | null;
  pluginSearch: string;
  pluginStatus: string;
  pluginDialogOpen: boolean;
  pluginSaving: boolean;
  pluginForm: Partial<ComfyuiPluginCatalogItem>;
  pluginFormTags: string;
  pluginFormError?: string | null;
  statusOptions: ReadonlyArray<SelectOption>;
  modelTypeOptions: ReadonlyArray<SelectOption>;
  onVersionSearchChange: (value: string) => void;
  onVersionStatusChange: (value: string) => void;
  onRefreshVersionUsage: () => void;
  onSyncVersions: () => void;
  onCreateVersion: () => void;
  onEditVersion: (item: ComfyuiVersionCatalogItem) => void;
  onDeleteVersion: (id: number) => void;
  onCloseVersionDialog: () => void;
  onSaveVersion: () => void;
  onVersionFormPatch: (patch: Partial<ComfyuiVersionCatalogItem>) => void;
  onModelSearchChange: (value: string) => void;
  onModelTypeChange: (value: string) => void;
  onModelStatusChange: (value: string) => void;
  onCreateModel: () => void;
  onEditModel: (item: ComfyuiModelCatalogItem) => void;
  onDeleteModel: (id: number) => void;
  onCloseModelDialog: () => void;
  onSaveModel: () => void;
  onModelFormPatch: (patch: Partial<ComfyuiModelCatalogItem>) => void;
  onModelTagsChange: (value: string) => void;
  onPluginSearchChange: (value: string) => void;
  onPluginStatusChange: (value: string) => void;
  onCreatePlugin: () => void;
  onEditPlugin: (item: ComfyuiPluginCatalogItem) => void;
  onDeletePlugin: (id: number) => void;
  onClosePluginDialog: () => void;
  onSavePlugin: () => void;
  onPluginFormPatch: (patch: Partial<ComfyuiPluginCatalogItem>) => void;
  onPluginTagsChange: (value: string) => void;
};

const toSelectOptions = (options: ReadonlyArray<SelectOption>) => options.map((item) => ({ ...item }));

const openExternalUrl = (url?: string | null) => {
  if (!url) return;
  window.open(url, '_blank', 'noreferrer');
};

export function ComfyuiAssetsPanel({
  executors,
  versionItems,
  versionLoading,
  versionError,
  versionSearch,
  versionStatus,
  versionServerLoading,
  versionSyncing,
  versionUsage,
  versionDialogOpen,
  versionSaving,
  versionForm,
  versionFormError,
  modelItems,
  modelLoading,
  modelError,
  modelSearch,
  modelType,
  modelStatus,
  modelDialogOpen,
  modelSaving,
  modelForm,
  modelFormTags,
  modelFormError,
  pluginItems,
  pluginLoading,
  pluginError,
  pluginSearch,
  pluginStatus,
  pluginDialogOpen,
  pluginSaving,
  pluginForm,
  pluginFormTags,
  pluginFormError,
  statusOptions,
  modelTypeOptions,
  onVersionSearchChange,
  onVersionStatusChange,
  onRefreshVersionUsage,
  onSyncVersions,
  onCreateVersion,
  onEditVersion,
  onDeleteVersion,
  onCloseVersionDialog,
  onSaveVersion,
  onVersionFormPatch,
  onModelSearchChange,
  onModelTypeChange,
  onModelStatusChange,
  onCreateModel,
  onEditModel,
  onDeleteModel,
  onCloseModelDialog,
  onSaveModel,
  onModelFormPatch,
  onModelTagsChange,
  onPluginSearchChange,
  onPluginStatusChange,
  onCreatePlugin,
  onEditPlugin,
  onDeletePlugin,
  onClosePluginDialog,
  onSavePlugin,
  onPluginFormPatch,
  onPluginTagsChange,
}: ComfyuiAssetsPanelProps) {
  const hasComfyExecutors = executors.some((executor) => (executor.type || '').toLowerCase() === 'comfyui');

  return (
    <div className="space-y-4">
      <Card bordered title="ComfyUI 版本清单">
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
            <Space align="center" size="small">
              <Input value={versionSearch} onChange={(value) => onVersionSearchChange(String(value))} placeholder="搜索版本/commit/仓库" />
              <Select value={versionStatus} onChange={(value) => onVersionStatusChange(String(value))} options={[{ label: '全部状态', value: 'all' }, ...statusOptions]} />
            </Space>
            <Space align="center" size="small">
              <Button variant="outline" loading={versionServerLoading} onClick={onRefreshVersionUsage}>
                刷新服务器版本
              </Button>
              <Button variant="outline" loading={versionSyncing} onClick={onSyncVersions}>
                增量同步版本
              </Button>
              <Button theme="primary" onClick={onCreateVersion}>
                新增版本
              </Button>
            </Space>
          </Space>
          {hasComfyExecutors && versionUsage.size === 0 ? (
            <Typography.Text theme="secondary">提示：点击“刷新服务器版本”后，会在列表中标记当前在用版本。</Typography.Text>
          ) : null}
          {versionError ? <Alert theme="error" message={versionError} /> : null}
          <div className="max-h-[320px] overflow-auto rounded-2xl border border-slate-200/70 dark:border-slate-800">
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-slate-50 text-[11px] text-slate-600 dark:bg-slate-900/80 dark:text-slate-400">
                <tr className="text-left">
                  <th className="px-3 py-2">版本</th>
                  <th className="px-3 py-2">提交哈希</th>
                  <th className="px-3 py-2">下载</th>
                  <th className="px-3 py-2">来源</th>
                  <th className="px-3 py-2">状态</th>
                  <th className="px-3 py-2">更新时间</th>
                  <th className="px-3 py-2 text-right">操作</th>
                </tr>
              </thead>
              <tbody>
                {versionItems.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-4 py-6 text-center text-slate-500">
                      {versionLoading ? '加载中…' : '暂无记录'}
                    </td>
                  </tr>
                ) : (
                  versionItems.map((item) => {
                    const usage = new Set<string>();
                    const addUsage = (key?: string | null) => {
                      if (!key) return;
                      const list = versionUsage.get(String(key).trim());
                      if (!list) return;
                      list.forEach((name) => usage.add(name));
                    };
                    addUsage(item.version);
                    addUsage(item.commit_sha);
                    const usageList = Array.from(usage);
                    return (
                      <tr key={`comfyui-version-${item.id}`} className="border-t border-slate-100 dark:border-slate-800">
                        <td className="px-3 py-2 font-semibold text-slate-900 dark:text-white">
                          <Space size="small">
                            <span>{item.version}</span>
                            {usageList.length > 0 ? (
                              <Popup
                                placement="right"
                                trigger="hover"
                                content={<div className="max-w-[320px] whitespace-pre-wrap text-xs text-slate-700">在用服务器：{usageList.join('、')}</div>}
                              >
                                <Tag theme="success" variant="light">
                                  在用{usageList.length > 1 ? ` · ${usageList.length}台` : ''}
                                </Tag>
                              </Popup>
                            ) : null}
                          </Space>
                        </td>
                        <td className="px-3 py-2 text-slate-600 dark:text-slate-400">{item.commit_sha || '—'}</td>
                        <td className="px-3 py-2">{item.download_url ? <Button size="small" variant="text" onClick={() => openExternalUrl(item.download_url)}>打开</Button> : '—'}</td>
                        <td className="px-3 py-2">
                          {item.source_url || item.repo_url ? <Button size="small" variant="text" onClick={() => openExternalUrl(item.source_url || item.repo_url)}>打开</Button> : '—'}
                        </td>
                        <td className="px-3 py-2">
                          <StatusBadge status={item.status} />
                        </td>
                        <td className="px-3 py-2 text-slate-600 dark:text-slate-400">{item.updated_at ? formatDateTime(item.updated_at) : '—'}</td>
                        <td className="px-3 py-2 text-right space-x-2">
                          <button className="text-sky-400" onClick={() => onEditVersion(item)}>
                            编辑
                          </button>
                          <button className="text-red-400" onClick={() => onDeleteVersion(item.id)}>
                            删除
                          </button>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </Space>
      </Card>

      <Dialog
        header={versionForm.id ? '编辑版本' : '新增版本'}
        visible={versionDialogOpen}
        width={680}
        confirmBtn={versionSaving ? { loading: true } : undefined}
        onClose={onCloseVersionDialog}
        onConfirm={onSaveVersion}
      >
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Row gutter={[12, 12]}>
            <Col span={12}>
              <Typography.Text theme="secondary">版本号</Typography.Text>
              <Input value={versionForm.version || ''} onChange={(value) => onVersionFormPatch({ version: String(value) })} placeholder="例如 v0.2.x 或 标签/提交" disabled={Boolean(versionForm.id)} />
            </Col>
            <Col span={12}>
              <Typography.Text theme="secondary">提交哈希</Typography.Text>
              <Input value={versionForm.commit_sha || ''} onChange={(value) => onVersionFormPatch({ commit_sha: String(value) })} placeholder="可选" />
            </Col>
          </Row>
          <Row gutter={[12, 12]}>
            <Col span={12}>
              <Typography.Text theme="secondary">仓库地址</Typography.Text>
              <Input value={versionForm.repo_url || ''} onChange={(value) => onVersionFormPatch({ repo_url: String(value) })} placeholder="https://github.com/..." />
            </Col>
            <Col span={12}>
              <Typography.Text theme="secondary">来源地址</Typography.Text>
              <Input value={versionForm.source_url || ''} onChange={(value) => onVersionFormPatch({ source_url: String(value) })} placeholder="发布页/文档链接" />
            </Col>
          </Row>
          <Row gutter={[12, 12]}>
            <Col span={12}>
              <Typography.Text theme="secondary">下载地址</Typography.Text>
              <Input value={versionForm.download_url || ''} onChange={(value) => onVersionFormPatch({ download_url: String(value) })} placeholder="zip 或 git 地址" />
            </Col>
            <Col span={12}>
              <Typography.Text theme="secondary">发布时间</Typography.Text>
              <Input value={versionForm.released_at || ''} onChange={(value) => onVersionFormPatch({ released_at: String(value) })} placeholder="YYYY-MM-DDTHH:mm:ssZ" />
            </Col>
          </Row>
          <div>
            <Typography.Text theme="secondary">备注</Typography.Text>
            <Textarea value={versionForm.notes || ''} onChange={(value) => onVersionFormPatch({ notes: String(value) })} autosize={{ minRows: 3, maxRows: 5 }} />
          </div>
          <div>
            <Typography.Text theme="secondary">状态</Typography.Text>
            <Select value={versionForm.status || 'active'} onChange={(value) => onVersionFormPatch({ status: String(value) })} options={toSelectOptions(statusOptions)} />
          </div>
          {versionFormError ? <Alert theme="error" message={versionFormError} /> : null}
        </Space>
      </Dialog>

      <Card bordered title="模型清单">
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
            <Space align="center" size="small">
              <Input value={modelSearch} onChange={(value) => onModelSearchChange(String(value))} placeholder="搜索文件名/名称" />
              <Select value={modelType} onChange={(value) => onModelTypeChange(String(value))} options={[{ label: '全部类型', value: 'all' }, ...modelTypeOptions]} />
              <Select value={modelStatus} onChange={(value) => onModelStatusChange(String(value))} options={[{ label: '全部状态', value: 'all' }, ...statusOptions]} />
            </Space>
            <Button theme="primary" onClick={onCreateModel}>
              新增模型
            </Button>
          </Space>
          {modelError ? <Alert theme="error" message={modelError} /> : null}
          <div className="max-h-[360px] overflow-auto rounded-2xl border border-slate-200/70 dark:border-slate-800">
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-slate-50 text-[11px] text-slate-600 dark:bg-slate-900/80 dark:text-slate-400">
                <tr className="text-left">
                  <th className="px-3 py-2">名称</th>
                  <th className="px-3 py-2">文件名</th>
                  <th className="px-3 py-2">类型</th>
                  <th className="px-3 py-2">下载</th>
                  <th className="px-3 py-2">来源</th>
                  <th className="px-3 py-2">状态</th>
                  <th className="px-3 py-2 text-right">操作</th>
                </tr>
              </thead>
              <tbody>
                {modelItems.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-4 py-6 text-center text-slate-500">
                      {modelLoading ? '加载中…' : '暂无记录'}
                    </td>
                  </tr>
                ) : (
                  modelItems.map((item) => (
                    <tr key={`model-${item.id}`} className="border-t border-slate-100 dark:border-slate-800">
                      <td className="px-3 py-2 font-semibold text-slate-900 dark:text-white">{item.display_name || item.file_name || '—'}</td>
                      <td className="px-3 py-2 text-slate-600 dark:text-slate-400">{item.file_name}</td>
                      <td className="px-3 py-2 text-slate-600 dark:text-slate-400">{item.model_type}</td>
                      <td className="px-3 py-2">{item.download_url ? <Button size="small" variant="text" onClick={() => openExternalUrl(item.download_url)}>打开</Button> : '—'}</td>
                      <td className="px-3 py-2">{item.source_url ? <Button size="small" variant="text" onClick={() => openExternalUrl(item.source_url)}>打开</Button> : '—'}</td>
                      <td className="px-3 py-2">
                        <StatusBadge status={item.status} />
                      </td>
                      <td className="px-3 py-2 text-right space-x-2">
                        <button className="text-sky-400" onClick={() => onEditModel(item)}>
                          编辑
                        </button>
                        <button className="text-red-400" onClick={() => onDeleteModel(item.id)}>
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
        header={modelForm.id ? '编辑模型' : '新增模型'}
        visible={modelDialogOpen}
        width={640}
        confirmBtn={modelSaving ? { loading: true } : undefined}
        onClose={onCloseModelDialog}
        onConfirm={onSaveModel}
      >
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Row gutter={[12, 12]}>
            <Col span={12}>
              <Typography.Text theme="secondary">模型文件名</Typography.Text>
              <Input value={modelForm.file_name || ''} onChange={(value) => onModelFormPatch({ file_name: String(value) })} placeholder="例如 xxx.safetensors" disabled={Boolean(modelForm.id)} />
            </Col>
            <Col span={12}>
              <Typography.Text theme="secondary">对外名称</Typography.Text>
              <Input value={modelForm.display_name || ''} onChange={(value) => onModelFormPatch({ display_name: String(value) })} placeholder="例如 基座模型A" />
            </Col>
          </Row>
          <Row gutter={[12, 12]}>
            <Col span={12}>
              <Typography.Text theme="secondary">模型类型</Typography.Text>
              <Select value={modelForm.model_type || 'unet'} onChange={(value) => onModelFormPatch({ model_type: String(value) })} options={toSelectOptions(modelTypeOptions)} />
            </Col>
            <Col span={12}>
              <Typography.Text theme="secondary">状态</Typography.Text>
              <Select value={modelForm.status || 'active'} onChange={(value) => onModelFormPatch({ status: String(value) })} options={toSelectOptions(statusOptions)} />
            </Col>
          </Row>
          <div>
            <Typography.Text theme="secondary">下载地址</Typography.Text>
            <Input value={modelForm.download_url || ''} onChange={(value) => onModelFormPatch({ download_url: String(value) })} placeholder="https://..." />
          </div>
          <div>
            <Typography.Text theme="secondary">来源地址</Typography.Text>
            <Input value={modelForm.source_url || ''} onChange={(value) => onModelFormPatch({ source_url: String(value) })} placeholder="https://..." />
          </div>
          <div>
            <Typography.Text theme="secondary">标签（逗号或换行分隔）</Typography.Text>
            <Textarea value={modelFormTags} onChange={(value) => onModelTagsChange(String(value))} autosize={{ minRows: 2, maxRows: 4 }} />
          </div>
          <div>
            <Typography.Text theme="secondary">备注</Typography.Text>
            <Textarea value={modelForm.description || ''} onChange={(value) => onModelFormPatch({ description: String(value) })} autosize={{ minRows: 3, maxRows: 5 }} />
          </div>
          {modelFormError ? <Alert theme="error" message={modelFormError} /> : null}
        </Space>
      </Dialog>

      <Card bordered title="插件清单">
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
            <Space align="center" size="small">
              <Input value={pluginSearch} onChange={(value) => onPluginSearchChange(String(value))} placeholder="搜索节点标识、名称或包名" />
              <Select value={pluginStatus} onChange={(value) => onPluginStatusChange(String(value))} options={[{ label: '全部状态', value: 'all' }, ...statusOptions]} />
            </Space>
            <Button theme="primary" onClick={onCreatePlugin}>
              新增插件
            </Button>
          </Space>
          {pluginError ? <Alert theme="error" message={pluginError} /> : null}
          <div className="max-h-[360px] overflow-auto rounded-2xl border border-slate-200/70 dark:border-slate-800">
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-slate-50 text-[11px] text-slate-600 dark:bg-slate-900/80 dark:text-slate-400">
                <tr className="text-left">
                  <th className="px-3 py-2">节点标识</th>
                  <th className="px-3 py-2">名称</th>
                  <th className="px-3 py-2">包名</th>
                  <th className="px-3 py-2">版本</th>
                  <th className="px-3 py-2">下载</th>
                  <th className="px-3 py-2">来源</th>
                  <th className="px-3 py-2">状态</th>
                  <th className="px-3 py-2 text-right">操作</th>
                </tr>
              </thead>
              <tbody>
                {pluginItems.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="px-4 py-6 text-center text-slate-500">
                      {pluginLoading ? '加载中…' : '暂无记录'}
                    </td>
                  </tr>
                ) : (
                  pluginItems.map((item) => (
                    <tr key={`plugin-${item.id}`} className="border-t border-slate-100 dark:border-slate-800">
                      <td className="px-3 py-2 text-slate-700 dark:text-slate-300">{item.node_key}</td>
                      <td className="px-3 py-2 font-semibold text-slate-900 dark:text-white">{item.display_name}</td>
                      <td className="px-3 py-2 text-slate-600 dark:text-slate-400">{item.package_name || '—'}</td>
                      <td className="px-3 py-2 text-slate-600 dark:text-slate-400">{item.version || '—'}</td>
                      <td className="px-3 py-2">{item.download_url ? <Button size="small" variant="text" onClick={() => openExternalUrl(item.download_url)}>打开</Button> : '—'}</td>
                      <td className="px-3 py-2">{item.source_url ? <Button size="small" variant="text" onClick={() => openExternalUrl(item.source_url)}>打开</Button> : '—'}</td>
                      <td className="px-3 py-2">
                        <StatusBadge status={item.status} />
                      </td>
                      <td className="px-3 py-2 text-right space-x-2">
                        <button className="text-sky-400" onClick={() => onEditPlugin(item)}>
                          编辑
                        </button>
                        <button className="text-red-400" onClick={() => onDeletePlugin(item.id)}>
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
        header={pluginForm.id ? '编辑插件' : '新增插件'}
        visible={pluginDialogOpen}
        width={640}
        confirmBtn={pluginSaving ? { loading: true } : undefined}
        onClose={onClosePluginDialog}
        onConfirm={onSavePlugin}
      >
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Row gutter={[12, 12]}>
            <Col span={12}>
              <Typography.Text theme="secondary">节点标识</Typography.Text>
              <Input value={pluginForm.node_key || ''} onChange={(value) => onPluginFormPatch({ node_key: String(value) })} placeholder="例如 ImageResize+" disabled={Boolean(pluginForm.id)} />
            </Col>
            <Col span={12}>
              <Typography.Text theme="secondary">对外名称</Typography.Text>
              <Input value={pluginForm.display_name || ''} onChange={(value) => onPluginFormPatch({ display_name: String(value) })} placeholder="例如 图像缩放增强" />
            </Col>
          </Row>
          <Row gutter={[12, 12]}>
            <Col span={12}>
              <Typography.Text theme="secondary">包名</Typography.Text>
              <Input value={pluginForm.package_name || ''} onChange={(value) => onPluginFormPatch({ package_name: String(value) })} placeholder="例如 comfyui_essentials" />
            </Col>
            <Col span={12}>
              <Typography.Text theme="secondary">版本</Typography.Text>
              <Input value={pluginForm.version || ''} onChange={(value) => onPluginFormPatch({ version: String(value) })} placeholder="commit/tag" />
            </Col>
          </Row>
          <Row gutter={[12, 12]}>
            <Col span={12}>
              <Typography.Text theme="secondary">下载地址</Typography.Text>
              <Input value={pluginForm.download_url || ''} onChange={(value) => onPluginFormPatch({ download_url: String(value) })} placeholder="https://..." />
            </Col>
            <Col span={12}>
              <Typography.Text theme="secondary">来源地址</Typography.Text>
              <Input value={pluginForm.source_url || ''} onChange={(value) => onPluginFormPatch({ source_url: String(value) })} placeholder="https://..." />
            </Col>
          </Row>
          <div>
            <Typography.Text theme="secondary">标签（逗号或换行分隔）</Typography.Text>
            <Textarea value={pluginFormTags} onChange={(value) => onPluginTagsChange(String(value))} autosize={{ minRows: 2, maxRows: 4 }} />
          </div>
          <div>
            <Typography.Text theme="secondary">备注</Typography.Text>
            <Textarea value={pluginForm.description || ''} onChange={(value) => onPluginFormPatch({ description: String(value) })} autosize={{ minRows: 3, maxRows: 5 }} />
          </div>
          <div>
            <Typography.Text theme="secondary">状态</Typography.Text>
            <Select value={pluginForm.status || 'active'} onChange={(value) => onPluginFormPatch({ status: String(value) })} options={toSelectOptions(statusOptions)} />
          </div>
          {pluginFormError ? <Alert theme="error" message={pluginFormError} /> : null}
        </Space>
      </Dialog>
    </div>
  );
}
