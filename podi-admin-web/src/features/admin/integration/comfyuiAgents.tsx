import { Alert, Button, Card, Col, Dialog, Input, Popup, Row, Select, Space, Switch, Tag, Textarea, Typography } from 'tdesign-react';
import type { ComfyuiAgent } from '../../../types/admin';
import { StatusBadge } from '../shared/ui';
import { formatDateTime } from './formatters';

type SelectOption = {
  label: string;
  value: string;
};

type ComfyuiAgentFormState = Partial<ComfyuiAgent>;

type ComfyuiAgentsPanelProps = {
  agents: ComfyuiAgent[];
  loading: boolean;
  error?: string | null;
  statusFilter: string;
  statusOptions: SelectOption[];
  tokenError?: string | null;
  tokenDialogOpen: boolean;
  tokenLoading: boolean;
  primarySaving: Record<string, boolean>;
  formDialogOpen: boolean;
  formEditing: boolean;
  formSaving: boolean;
  form: ComfyuiAgentFormState;
  configInput: string;
  formError?: string | null;
  tokenAgentId: string;
  tokenValue: string;
  tokenExpiresAt: string;
  resolveBaseUrl: (agent: ComfyuiAgent) => string;
  isPrimaryAgent: (agent: ComfyuiAgent) => boolean;
  onStatusFilterChange: (status: string) => void;
  onRefresh: () => void;
  onCreate: () => void;
  onEdit: (agent: ComfyuiAgent, baseUrl: string) => void;
  onIssueToken: (agentId: string) => void;
  onSetPrimary: (agent: ComfyuiAgent) => void;
  onDelete: (agentId: string) => void;
  onCloseForm: () => void;
  onSaveForm: () => void;
  onFormPatch: (patch: ComfyuiAgentFormState) => void;
  onConfigInputChange: (value: string) => void;
  onCloseToken: () => void;
  onCopyText: (text: string) => void;
};

const stringifyMetrics = (value: unknown) => {
  if (!value || typeof value !== 'object') return '';
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return '';
  }
};

export function ComfyuiAgentsPanel({
  agents,
  loading,
  error,
  statusFilter,
  statusOptions,
  tokenError,
  tokenDialogOpen,
  tokenLoading,
  primarySaving,
  formDialogOpen,
  formEditing,
  formSaving,
  form,
  configInput,
  formError,
  tokenAgentId,
  tokenValue,
  tokenExpiresAt,
  resolveBaseUrl,
  isPrimaryAgent,
  onStatusFilterChange,
  onRefresh,
  onCreate,
  onEdit,
  onIssueToken,
  onSetPrimary,
  onDelete,
  onCloseForm,
  onSaveForm,
  onFormPatch,
  onConfigInputChange,
  onCloseToken,
  onCopyText,
}: ComfyuiAgentsPanelProps) {
  return (
    <div className="space-y-4">
      <Card bordered title="代理服务列表">
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
            <Space align="center" size="small">
              <Select
                value={statusFilter}
                onChange={(value) => onStatusFilterChange(String(value))}
                options={[
                  { label: '全部状态', value: 'all' },
                  ...statusOptions.map((option) => ({ label: option.label, value: option.value })),
                ]}
              />
              <Button size="small" variant="outline" onClick={onRefresh}>
                刷新
              </Button>
            </Space>
            <Button theme="primary" onClick={onCreate}>
              新增代理服务
            </Button>
          </Space>
          {error ? <Alert theme="error" message={error} /> : null}
          {tokenError && !tokenDialogOpen ? <Alert theme="error" message={tokenError} /> : null}
          <div className="max-h-[420px] overflow-auto rounded-2xl border border-slate-200/70 dark:border-slate-800">
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-slate-50 text-[11px] text-slate-600 dark:bg-slate-900/80 dark:text-slate-400">
                <tr className="text-left">
                  <th className="px-3 py-2">代理服务ID</th>
                  <th className="px-3 py-2">名称</th>
                  <th className="px-3 py-2">角色</th>
                  <th className="px-3 py-2">服务地址</th>
                  <th className="px-3 py-2">状态</th>
                  <th className="px-3 py-2">允许</th>
                  <th className="px-3 py-2">主节点</th>
                  <th className="px-3 py-2">心跳</th>
                  <th className="px-3 py-2">清单版本</th>
                  <th className="px-3 py-2">指标</th>
                  <th className="px-3 py-2 text-right">操作</th>
                </tr>
              </thead>
              <tbody>
                {agents.length === 0 ? (
                  <tr>
                    <td colSpan={11} className="px-4 py-6 text-center text-slate-500">
                      {loading ? '加载中…' : '暂无代理服务'}
                    </td>
                  </tr>
                ) : (
                  agents.map((agent) => {
                    const baseUrl = resolveBaseUrl(agent);
                    const metricsText = stringifyMetrics(agent.metrics);
                    const primary = isPrimaryAgent(agent);
                    return (
                      <tr key={`comfy-agent-${agent.id}`} className="border-t border-slate-100 dark:border-slate-800">
                        <td className="px-3 py-2 text-slate-900 dark:text-white">{agent.id}</td>
                        <td className="px-3 py-2 text-slate-700 dark:text-slate-300">{agent.name || '—'}</td>
                        <td className="px-3 py-2 text-slate-700 dark:text-slate-300">{agent.role || '—'}</td>
                        <td className="px-3 py-2 text-slate-600 dark:text-slate-400">{baseUrl || '—'}</td>
                        <td className="px-3 py-2">
                          <StatusBadge status={agent.status} />
                        </td>
                        <td className="px-3 py-2">
                          {agent.allowed ? (
                            <Tag theme="success" variant="light">
                              允许
                            </Tag>
                          ) : (
                            <Tag theme="warning" variant="light">
                              禁用
                            </Tag>
                          )}
                        </td>
                        <td className="px-3 py-2">
                          {primary ? (
                            <Tag theme="primary" variant="light">
                              是
                            </Tag>
                          ) : (
                            <Typography.Text theme="secondary">—</Typography.Text>
                          )}
                        </td>
                        <td className="px-3 py-2 text-slate-600 dark:text-slate-400">
                          {formatDateTime(agent.last_heartbeat_at || agent.last_seen_at)}
                        </td>
                        <td className="px-3 py-2 text-slate-600 dark:text-slate-400">
                          {agent.last_manifest_version || '—'}
                        </td>
                        <td className="px-3 py-2 text-slate-600 dark:text-slate-400">
                          {metricsText ? (
                            <Popup
                              placement="right"
                              trigger="hover"
                              content={<div className="max-w-[360px] whitespace-pre-wrap text-xs text-slate-700">{metricsText}</div>}
                            >
                              <button className="text-sky-400">查看</button>
                            </Popup>
                          ) : (
                            '—'
                          )}
                        </td>
                        <td className="px-3 py-2 text-right space-x-2">
                          <button className="text-sky-400" onClick={() => onEdit(agent, baseUrl)}>
                            编辑
                          </button>
                          <button className="text-emerald-400" disabled={tokenLoading} onClick={() => onIssueToken(agent.id)}>
                            令牌
                          </button>
                          <button
                            className="text-violet-500"
                            disabled={primary || !agent.role || Boolean(primarySaving[agent.id])}
                            onClick={() => onSetPrimary(agent)}
                          >
                            {primary ? '主节点' : '设为主节点'}
                          </button>
                          <button className="text-red-400" onClick={() => onDelete(agent.id)}>
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
        header={formEditing ? '编辑代理服务' : '新增代理服务'}
        visible={formDialogOpen}
        width={640}
        confirmBtn={formSaving ? { loading: true } : undefined}
        onClose={onCloseForm}
        onConfirm={onSaveForm}
      >
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Row gutter={[12, 12]}>
            <Col span={12}>
              <Typography.Text theme="secondary">代理服务ID</Typography.Text>
              <Input
                value={form.id || ''}
                onChange={(value) => onFormPatch({ id: String(value) })}
                placeholder="例如 comfyui-158"
                disabled={formEditing}
              />
            </Col>
            <Col span={12}>
              <Typography.Text theme="secondary">名称</Typography.Text>
              <Input value={form.name || ''} onChange={(value) => onFormPatch({ name: String(value) })} placeholder="例如 ComfyUI-158" />
            </Col>
          </Row>
          <Row gutter={[12, 12]}>
            <Col span={12}>
              <Typography.Text theme="secondary">角色</Typography.Text>
              <Input value={form.role || ''} onChange={(value) => onFormPatch({ role: String(value) })} placeholder="full / lite" />
            </Col>
            <Col span={12}>
              <Typography.Text theme="secondary">主机</Typography.Text>
              <Input value={form.host || ''} onChange={(value) => onFormPatch({ host: String(value) })} placeholder="117.50.80.158" />
            </Col>
          </Row>
          <div>
            <Typography.Text theme="secondary">服务地址</Typography.Text>
            <Input
              value={form.baseUrl || ''}
              onChange={(value) => onFormPatch({ baseUrl: String(value) })}
              placeholder="http://117.50.80.158:18079"
            />
          </div>
          <Row gutter={[12, 12]}>
            <Col span={12}>
              <Typography.Text theme="secondary">状态</Typography.Text>
              <Select
                value={form.status || 'active'}
                onChange={(value) => onFormPatch({ status: String(value) })}
                options={statusOptions}
              />
            </Col>
            <Col span={12}>
              <Typography.Text theme="secondary">允许执行</Typography.Text>
              <div className="mt-2">
                <Switch value={Boolean(form.allowed)} onChange={(value) => onFormPatch({ allowed: Boolean(value) })} />
              </div>
            </Col>
          </Row>
          <div>
            <Typography.Text theme="secondary">扩展配置（JSON）</Typography.Text>
            <Textarea
              value={configInput}
              onChange={(value) => onConfigInputChange(String(value))}
              autosize={{ minRows: 3, maxRows: 8 }}
              placeholder='{"baseUrl":"http://...","region":"hz"}'
            />
          </div>
          {formError ? <Alert theme="error" message={formError} /> : null}
        </Space>
      </Dialog>

      <Dialog
        header={`访问令牌 · ${tokenAgentId || ''}`}
        visible={tokenDialogOpen}
        width={720}
        confirmBtn={{ content: '关闭' }}
        onClose={onCloseToken}
        onConfirm={onCloseToken}
      >
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          {tokenError ? <Alert theme="error" message={tokenError} /> : null}
          <div className="text-xs text-slate-500">过期时间：{tokenExpiresAt ? formatDateTime(tokenExpiresAt) : '—'}</div>
          <Space align="center" size="small">
            <Button size="small" variant="outline" disabled={!tokenValue} onClick={() => onCopyText(tokenValue)}>
              复制令牌
            </Button>
          </Space>
          <Textarea value={tokenValue} readonly autosize={{ minRows: 6, maxRows: 10 }} className="font-mono text-xs" />
        </Space>
      </Dialog>
    </div>
  );
}
