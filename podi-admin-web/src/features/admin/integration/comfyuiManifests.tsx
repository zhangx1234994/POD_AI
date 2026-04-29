import { Alert, Button, Card, Col, Dialog, Input, Row, Select, Space, Switch, Textarea, Typography } from 'tdesign-react';
import type {
  ComfyuiAgentManifest,
  ComfyuiManifestDriftResponse,
  ComfyuiRepairJob,
  ComfyuiRepairPlan,
  JsonRecord,
} from '../../../types/admin';
import { StatusBadge } from '../shared/ui';
import { formatDateTime } from './formatters';

type ManifestEditorMode = 'wizard' | 'json';

type ComfyuiManifestsPanelProps = {
  manifests: ComfyuiAgentManifest[];
  loading: boolean;
  error?: string | null;
  roleFilter: string;
  statusFilter: string;
  actionLoading: Record<number, boolean>;
  assistOpen: boolean;
  repairJobs: ComfyuiRepairJob[];
  repairRunningCount: number;
  repairFailedCount: number;
  dialogOpen: boolean;
  saving: boolean;
  form: Partial<ComfyuiAgentManifest>;
  editorMode: ManifestEditorMode;
  includeInactive: boolean;
  wizardPreview: JsonRecord;
  contentInput: string;
  formError?: string | null;
  driftDialogOpen: boolean;
  driftTitle?: string | null;
  driftError?: string | null;
  driftLoading: boolean;
  driftText: string;
  driftData?: ComfyuiManifestDriftResponse | null;
  repairPlan?: ComfyuiRepairPlan | null;
  repairPlanLoading: boolean;
  repairJobLoading: boolean;
  onRoleFilterChange: (value: string) => void;
  onStatusFilterChange: (value: string) => void;
  onRefreshManifests: () => void;
  onCreateManifest: () => void;
  onEditManifest: (manifest: ComfyuiAgentManifest) => void;
  onPublishManifest: (manifestId: number) => void;
  onRollbackManifest: (manifestId: number) => void;
  onOpenDrift: (manifest: ComfyuiAgentManifest) => void;
  onRefreshRepairJobs: () => void;
  onCloseDialog: () => void;
  onSaveManifest: () => void;
  onFormPatch: (patch: Partial<ComfyuiAgentManifest>) => void;
  onEditorModeChange: (mode: ManifestEditorMode) => void;
  onIncludeInactiveChange: (value: boolean) => void;
  onGenerateFromWizard: () => void;
  onContentInputChange: (value: string) => void;
  onCloseDriftDialog: () => void;
  onCopyText: (value: string) => void;
  onDownloadJson: (payload: unknown, filename: string) => void;
  onGenerateRepairPlan: () => void;
  onCreateRepairJob: () => void;
};

const countPreviewItems = (value: unknown) => (Array.isArray(value) ? value.length : 0);

export function ComfyuiManifestsPanel({
  manifests,
  loading,
  error,
  roleFilter,
  statusFilter,
  actionLoading,
  assistOpen,
  repairJobs,
  repairRunningCount,
  repairFailedCount,
  dialogOpen,
  saving,
  form,
  editorMode,
  includeInactive,
  wizardPreview,
  contentInput,
  formError,
  driftDialogOpen,
  driftTitle,
  driftError,
  driftLoading,
  driftText,
  driftData,
  repairPlan,
  repairPlanLoading,
  repairJobLoading,
  onRoleFilterChange,
  onStatusFilterChange,
  onRefreshManifests,
  onCreateManifest,
  onEditManifest,
  onPublishManifest,
  onRollbackManifest,
  onOpenDrift,
  onRefreshRepairJobs,
  onCloseDialog,
  onSaveManifest,
  onFormPatch,
  onEditorModeChange,
  onIncludeInactiveChange,
  onGenerateFromWizard,
  onContentInputChange,
  onCloseDriftDialog,
  onCopyText,
  onDownloadJson,
  onGenerateRepairPlan,
  onCreateRepairJob,
}: ComfyuiManifestsPanelProps) {
  return (
    <div className="space-y-4">
      <Card bordered title="同步清单">
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
            <Space align="center" size="small">
              <Input value={roleFilter} onChange={(value) => onRoleFilterChange(String(value))} placeholder="过滤角色（如 full / lite）" />
              <Select
                value={statusFilter}
                onChange={(value) => onStatusFilterChange(String(value))}
                options={[
                  { label: '全部状态', value: 'all' },
                  { label: '草稿', value: 'draft' },
                  { label: '已发布', value: 'published' },
                  { label: '已回滚', value: 'rolled_back' },
                  { label: '启用（兼容）', value: 'active' },
                  { label: '停用（兼容）', value: 'inactive' },
                ]}
              />
              <Button size="small" variant="outline" onClick={onRefreshManifests}>
                刷新
              </Button>
            </Space>
            <Button theme="primary" onClick={onCreateManifest}>
              新增清单
            </Button>
          </Space>
          {error ? <Alert theme="error" message={error} /> : null}
          <div className="max-h-[420px] overflow-auto rounded-2xl border border-slate-200/70 dark:border-slate-800">
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-slate-50 text-[11px] text-slate-600 dark:bg-slate-900/80 dark:text-slate-400">
                <tr className="text-left">
                  <th className="px-3 py-2">ID</th>
                  <th className="px-3 py-2">角色</th>
                  <th className="px-3 py-2">版本</th>
                  <th className="px-3 py-2">状态</th>
                  <th className="px-3 py-2">清单地址</th>
                  <th className="px-3 py-2">更新时间</th>
                  <th className="px-3 py-2 text-right">操作</th>
                </tr>
              </thead>
              <tbody>
                {manifests.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-4 py-6 text-center text-slate-500">
                      {loading ? '加载中…' : '暂无清单'}
                    </td>
                  </tr>
                ) : (
                  manifests.map((manifest) => (
                    <tr key={`comfy-manifest-${manifest.id}`} className="border-t border-slate-100 dark:border-slate-800">
                      <td className="px-3 py-2 text-slate-900 dark:text-white">{manifest.id}</td>
                      <td className="px-3 py-2 text-slate-700 dark:text-slate-300">{manifest.role}</td>
                      <td className="px-3 py-2 text-slate-700 dark:text-slate-300">{manifest.version}</td>
                      <td className="px-3 py-2">
                        <StatusBadge status={manifest.status} />
                      </td>
                      <td className="px-3 py-2 text-slate-600 dark:text-slate-400">{manifest.downloadUrl || manifest.download_url || '—'}</td>
                      <td className="px-3 py-2 text-slate-600 dark:text-slate-400">
                        {manifest.updated_at ? formatDateTime(manifest.updated_at) : '—'}
                      </td>
                      <td className="px-3 py-2 text-right space-x-2">
                        <button className="text-sky-400" onClick={() => onEditManifest(manifest)}>
                          编辑
                        </button>
                        <button
                          className="text-emerald-500"
                          disabled={Boolean(actionLoading[manifest.id]) || manifest.status === 'published'}
                          onClick={() => onPublishManifest(manifest.id)}
                        >
                          发布
                        </button>
                        <button
                          className="text-amber-500"
                          disabled={Boolean(actionLoading[manifest.id])}
                          onClick={() => onRollbackManifest(manifest.id)}
                        >
                          回滚
                        </button>
                        <button className="text-violet-500" onClick={() => onOpenDrift(manifest)}>
                          漂移
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

      {assistOpen ? (
        <Card bordered title="修复任务（增量补齐）">
          <Space direction="vertical" size="small" style={{ width: '100%' }}>
            <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
              <Typography.Text theme="secondary">从“漂移”一键生成后会自动出现在这里，便于追踪执行进度。</Typography.Text>
              <Button size="small" variant="outline" onClick={onRefreshRepairJobs}>
                刷新
              </Button>
            </Space>
            <div className="max-h-[260px] overflow-auto rounded-2xl border border-slate-200/70 dark:border-slate-800">
              <table className="w-full text-xs">
                <thead className="sticky top-0 bg-slate-50 text-[11px] text-slate-600 dark:bg-slate-900/80 dark:text-slate-400">
                  <tr className="text-left">
                    <th className="px-3 py-2">任务号</th>
                    <th className="px-3 py-2">清单</th>
                    <th className="px-3 py-2">状态</th>
                    <th className="px-3 py-2">提交/成功/失败</th>
                    <th className="px-3 py-2">更新时间</th>
                  </tr>
                </thead>
                <tbody>
                  {repairJobs.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="px-4 py-6 text-center text-slate-500">
                        暂无修复任务
                      </td>
                    </tr>
                  ) : (
                    repairJobs.map((job) => (
                      <tr key={`repair-job-${job.id}`} className="border-t border-slate-100 dark:border-slate-800">
                        <td className="px-3 py-2 text-slate-900 dark:text-white">{job.id}</td>
                        <td className="px-3 py-2 text-slate-600 dark:text-slate-400">{job.manifestId}</td>
                        <td className="px-3 py-2">
                          <StatusBadge status={job.status} />
                        </td>
                        <td className="px-3 py-2 text-slate-600 dark:text-slate-400">
                          {job.submittedTaskCount}/{job.succeededTaskCount}/{job.failedTaskCount}
                        </td>
                        <td className="px-3 py-2 text-slate-600 dark:text-slate-400">{formatDateTime(job.updatedAt)}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </Space>
        </Card>
      ) : (
        <Alert
          theme="info"
          message={`修复任务已折叠：运行中 ${repairRunningCount} 条，失败 ${repairFailedCount} 条。需要追踪修复回执时，可在顶部“展开修复任务”。`}
        />
      )}

      <Dialog
        header={form.id ? '编辑清单' : '新增清单'}
        visible={dialogOpen}
        width={720}
        confirmBtn={saving ? { loading: true } : undefined}
        onClose={onCloseDialog}
        onConfirm={onSaveManifest}
      >
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Row gutter={[12, 12]}>
            <Col span={12}>
              <Typography.Text theme="secondary">角色</Typography.Text>
              <Input value={form.role || ''} onChange={(value) => onFormPatch({ role: String(value) })} placeholder="full / lite" />
            </Col>
            <Col span={12}>
              <Typography.Text theme="secondary">版本号</Typography.Text>
              <Input value={form.version || ''} onChange={(value) => onFormPatch({ version: String(value) })} placeholder="2026.02.05-001" />
            </Col>
          </Row>
          <Row gutter={[12, 12]}>
            <Col span={12}>
              <Typography.Text theme="secondary">状态</Typography.Text>
              <Select
                value={form.status || 'draft'}
                onChange={(value) => onFormPatch({ status: String(value) })}
                options={[
                  { label: '草稿', value: 'draft' },
                  { label: '已发布', value: 'published' },
                  { label: '已回滚', value: 'rolled_back' },
                ]}
              />
            </Col>
            <Col span={12}>
              <Typography.Text theme="secondary">清单地址</Typography.Text>
              <Input
                value={form.downloadUrl || form.download_url || ''}
                onChange={(value) => onFormPatch({ downloadUrl: String(value) })}
                placeholder="https://example.com/manifest.json"
              />
            </Col>
          </Row>
          <div>
            <Typography.Text theme="secondary">备注</Typography.Text>
            <Input value={form.notes || ''} onChange={(value) => onFormPatch({ notes: String(value) })} placeholder="可选" />
          </div>
          <Space align="center" size="small">
            <Button
              size="small"
              variant={editorMode === 'wizard' ? 'outline' : 'text'}
              theme={editorMode === 'wizard' ? 'primary' : 'default'}
              onClick={() => onEditorModeChange('wizard')}
            >
              向导模式
            </Button>
            <Button
              size="small"
              variant={editorMode === 'json' ? 'outline' : 'text'}
              theme={editorMode === 'json' ? 'primary' : 'default'}
              onClick={() => onEditorModeChange('json')}
            >
              JSON 高级模式
            </Button>
          </Space>
          {editorMode === 'wizard' ? (
            <Card bordered size="small" title="清单构建向导">
              <Space direction="vertical" size="small" style={{ width: '100%' }}>
                <Space align="center" size="small">
                  <Switch value={includeInactive} onChange={(value) => onIncludeInactiveChange(Boolean(value))} />
                  <Typography.Text theme="secondary">包含停用资源（默认仅启用）</Typography.Text>
                </Space>
                <Typography.Text theme="secondary">
                  将从资源目录自动生成清单：模型（含 LoRA） {countPreviewItems(wizardPreview.models)} 项，插件{' '}
                  {countPreviewItems(wizardPreview.plugins)} 项，工作流 {countPreviewItems(wizardPreview.workflows)} 项。
                </Typography.Text>
                <Button size="small" variant="outline" onClick={onGenerateFromWizard}>
                  生成清单内容
                </Button>
              </Space>
            </Card>
          ) : null}
          <div>
            <Typography.Text theme="secondary">清单内容（JSON）</Typography.Text>
            <Textarea
              value={contentInput}
              onChange={(value) => onContentInputChange(String(value))}
              autosize={{ minRows: 6, maxRows: 16 }}
              className="font-mono text-xs"
            />
          </div>
          {formError ? <Alert theme="error" message={formError} /> : null}
        </Space>
      </Dialog>

      <Dialog
        header={`清单漂移对比 · ${driftTitle || ''}`}
        visible={driftDialogOpen}
        width={760}
        confirmBtn={{ content: '关闭' }}
        onClose={onCloseDriftDialog}
        onConfirm={onCloseDriftDialog}
      >
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          {driftError ? <Alert theme="error" message={driftError} /> : null}
          {driftLoading ? <Alert theme="info" message="正在拉取差异，请稍候…" /> : null}
          <Space align="center" size="small" style={{ justifyContent: 'space-between', width: '100%' }}>
            <Typography.Text theme="secondary">对比内容包含版本、模型、插件、工作流差异，便于判断是否需要补齐同步。</Typography.Text>
            <Space size="small">
              <Button size="small" variant="outline" disabled={!driftText} onClick={() => onCopyText(driftText)}>
                复制原始数据
              </Button>
              <Button
                size="small"
                variant="outline"
                disabled={!driftData}
                onClick={() => {
                  if (!driftData) return;
                  const ts = new Date().toISOString().replace(/[:.]/g, '-');
                  onDownloadJson(driftData, `comfyui-manifest-drift-${ts}.json`);
                }}
              >
                导出原始数据
              </Button>
            </Space>
          </Space>
          <Space align="center" size="small">
            <Button size="small" variant="outline" loading={repairPlanLoading} onClick={onGenerateRepairPlan}>
              生成修复计划
            </Button>
            <Button size="small" theme="primary" loading={repairJobLoading} disabled={!repairPlan} onClick={onCreateRepairJob}>
              一键下发修复任务
            </Button>
          </Space>
          {repairPlan ? (
            <Alert
              theme="info"
              message={`修复计划：可执行 ${repairPlan.summary.executableAgents} 台，跳过 ${repairPlan.summary.skippedAgents} 台，动作总数 ${repairPlan.summary.totalActions}。`}
            />
          ) : null}
          <Textarea value={driftText} readonly autosize={{ minRows: 10, maxRows: 20 }} className="font-mono text-xs" />
          {repairPlan ? (
            <Textarea value={JSON.stringify(repairPlan, null, 2)} readonly autosize={{ minRows: 8, maxRows: 16 }} className="font-mono text-xs" />
          ) : null}
        </Space>
      </Dialog>
    </div>
  );
}
