import { Alert, Button, Card, Col, Dialog, Input, InputNumber, Row, Select, Space, Tag, Textarea, Typography } from 'tdesign-react';
import type { ComfyuiAgent, ComfyuiDesktopRelease, ComfyuiEnrollCode } from '../../../types/admin';
import { StatusBadge } from '../shared/ui';
import { formatDateTime } from './formatters';

type SelectOption = {
  label: string;
  value: string;
};

type TagMeta = {
  theme: 'default' | 'primary' | 'success' | 'warning' | 'danger';
  text: string;
};

type DesktopAgentRow = {
  agent: ComfyuiAgent;
  update: {
    status?: string | null;
    currentVersion?: string | null;
    targetVersion?: string | null;
    failureReason?: string | null;
  };
};

type ComfyuiDesktopPanelProps = {
  centerUrl: string;
  installReleaseId: string;
  releaseOptions: SelectOption[];
  hasWindowsX64Release: boolean;
  releases: ComfyuiDesktopRelease[];
  selectedRelease?: ComfyuiDesktopRelease | null;
  activeRelease?: ComfyuiDesktopRelease | null;
  installCommand: string;
  agentRows: DesktopAgentRow[];
  agentLoading: boolean;
  agentError?: string | null;
  enrollCodes: ComfyuiEnrollCode[];
  enrollCodesLoading: boolean;
  enrollCodesError?: string | null;
  enrollCodeRole: string;
  enrollCodeTtlSeconds: number;
  enrollCodeMaxUses: number;
  enrollCodeNote: string;
  enrollCodeCreating: boolean;
  releaseStatusFilter: string;
  releaseStatusOptions: ReadonlyArray<SelectOption>;
  releasesLoading: boolean;
  releasesError?: string | null;
  releaseDialogOpen: boolean;
  releaseSaving: boolean;
  releaseForm: Partial<ComfyuiDesktopRelease>;
  releasePayloadInput: string;
  releaseFormError?: string | null;
  getUpdateTag: (status?: string | null) => TagMeta;
  onInstallReleaseChange: (releaseId: string) => void;
  onCopyText: (text: string) => void;
  onRefreshAgents: () => void;
  onEnrollRoleChange: (role: string) => void;
  onEnrollTtlChange: (seconds: number) => void;
  onEnrollMaxUsesChange: (maxUses: number) => void;
  onEnrollNoteChange: (note: string) => void;
  onCreateEnrollCode: () => void;
  onRefreshEnrollCodes: () => void;
  onReleaseStatusFilterChange: (status: string) => void;
  onRefreshReleases: () => void;
  onCreateRelease: () => void;
  onEditRelease: (release: ComfyuiDesktopRelease) => void;
  onToggleReleaseStatus: (release: ComfyuiDesktopRelease) => void;
  onCloseReleaseDialog: () => void;
  onSaveRelease: () => void;
  onReleaseFormPatch: (patch: Partial<ComfyuiDesktopRelease>) => void;
  onReleasePayloadInputChange: (value: string) => void;
};

export function ComfyuiDesktopPanel({
  centerUrl,
  installReleaseId,
  releaseOptions,
  hasWindowsX64Release,
  releases,
  selectedRelease,
  activeRelease,
  installCommand,
  agentRows,
  agentLoading,
  agentError,
  enrollCodes,
  enrollCodesLoading,
  enrollCodesError,
  enrollCodeRole,
  enrollCodeTtlSeconds,
  enrollCodeMaxUses,
  enrollCodeNote,
  enrollCodeCreating,
  releaseStatusFilter,
  releaseStatusOptions,
  releasesLoading,
  releasesError,
  releaseDialogOpen,
  releaseSaving,
  releaseForm,
  releasePayloadInput,
  releaseFormError,
  getUpdateTag,
  onInstallReleaseChange,
  onCopyText,
  onRefreshAgents,
  onEnrollRoleChange,
  onEnrollTtlChange,
  onEnrollMaxUsesChange,
  onEnrollNoteChange,
  onCreateEnrollCode,
  onRefreshEnrollCodes,
  onReleaseStatusFilterChange,
  onRefreshReleases,
  onCreateRelease,
  onEditRelease,
  onToggleReleaseStatus,
  onCloseReleaseDialog,
  onSaveRelease,
  onReleaseFormPatch,
  onReleasePayloadInputChange,
}: ComfyuiDesktopPanelProps) {
  return (
    <div className="space-y-4">
      <Card bordered title="桌面端一键安装（Windows）">
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Alert theme="info" message={`当前中台地址：${centerUrl}（安装包内已固定中台地址，安装后自动握手接入）`} />
          <div style={{ width: 'min(100%, 440px)' }}>
            <Typography.Text theme="secondary">选择安装版本（Windows / x64）</Typography.Text>
            <Select
              value={installReleaseId}
              onChange={(value) => onInstallReleaseChange(String(value))}
              options={releaseOptions.length > 0 ? releaseOptions : [{ label: '暂无可用版本', value: '' }]}
            />
          </div>
          {!hasWindowsX64Release && releases.length > 0 ? (
            <Alert
              theme="warning"
              message="当前没有“Windows/x64”标准安装包，已回退展示其它平台版本。建议在下方发布一个 Windows x64 且状态为启用的版本。"
            />
          ) : null}
          <Space align="center" size="small">
            <Button size="small" variant="outline" onClick={() => onCopyText(installCommand)}>
              复制安装命令
            </Button>
            <Button
              size="small"
              variant="outline"
              disabled={!selectedRelease?.downloadUrl}
              onClick={() => {
                const url = (selectedRelease?.downloadUrl || '').trim();
                if (!url) return;
                window.open(url, '_blank', 'noopener,noreferrer');
              }}
            >
              下载安装包
            </Button>
            <Typography.Text theme="secondary">目标版本：{selectedRelease?.version || '未选择'}</Typography.Text>
            {activeRelease?.id && selectedRelease?.id === activeRelease.id ? (
              <Tag theme="success" variant="light">
                当前启用
              </Tag>
            ) : null}
          </Space>
          <Textarea value={installCommand} readonly autosize={{ minRows: 6, maxRows: 12 }} className="font-mono text-xs" />
        </Space>
      </Card>

      <Card bordered title="升级状态">
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
            <Typography.Text theme="secondary">查看每台代理服务的桌面端版本、目标版本与升级状态。</Typography.Text>
            <Button size="small" variant="outline" onClick={onRefreshAgents}>
              刷新
            </Button>
          </Space>
          {agentError ? <Alert theme="error" message={agentError} /> : null}
          <div className="max-h-[320px] overflow-auto rounded-2xl border border-slate-200/70 dark:border-slate-800">
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-slate-50 text-[11px] text-slate-600 dark:bg-slate-900/80 dark:text-slate-400">
                <tr className="text-left">
                  <th className="px-3 py-2">机器/代理</th>
                  <th className="px-3 py-2">当前版本</th>
                  <th className="px-3 py-2">目标版本</th>
                  <th className="px-3 py-2">升级状态</th>
                  <th className="px-3 py-2">最近心跳</th>
                  <th className="px-3 py-2">失败原因</th>
                </tr>
              </thead>
              <tbody>
                {agentRows.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-4 py-6 text-center text-slate-500">
                      {agentLoading ? '加载中…' : '暂无代理服务'}
                    </td>
                  </tr>
                ) : (
                  agentRows.map(({ agent, update }) => {
                    const statusTag = getUpdateTag(update.status);
                    const machineLabel = agent.name || agent.host || '未命名机器';
                    return (
                      <tr key={`comfy-desktop-agent-${agent.id}`} className="border-t border-slate-100 dark:border-slate-800">
                        <td className="px-3 py-2">
                          <div className="font-medium text-slate-900 dark:text-white">{machineLabel}</div>
                          <div className="text-[11px] text-slate-500 dark:text-slate-400">{agent.id}</div>
                        </td>
                        <td className="px-3 py-2 text-slate-700 dark:text-slate-300">{update.currentVersion || '—'}</td>
                        <td className="px-3 py-2 text-slate-700 dark:text-slate-300">{update.targetVersion || '—'}</td>
                        <td className="px-3 py-2">
                          <Tag theme={statusTag.theme} variant="light">
                            {statusTag.text}
                          </Tag>
                        </td>
                        <td className="px-3 py-2 text-slate-600 dark:text-slate-400">
                          {formatDateTime(agent.last_heartbeat_at || agent.last_seen_at)}
                        </td>
                        <td className="px-3 py-2 text-slate-600 dark:text-slate-400">{update.failureReason || '—'}</td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </Space>
      </Card>

      <Card bordered title="注册码（手动接入备用）">
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Row gutter={[12, 12]}>
            <Col span={6}>
              <Typography.Text theme="secondary">角色</Typography.Text>
              <Select
                value={enrollCodeRole}
                onChange={(value) => onEnrollRoleChange(String(value))}
                options={[
                  { label: '全量型（full）', value: 'full' },
                  { label: '轻量型（lite）', value: 'lite' },
                ]}
              />
            </Col>
            <Col span={6}>
              <Typography.Text theme="secondary">有效期（秒）</Typography.Text>
              <InputNumber value={enrollCodeTtlSeconds} min={60} max={7 * 24 * 3600} onChange={(value) => onEnrollTtlChange(Number(value) || 600)} />
            </Col>
            <Col span={6}>
              <Typography.Text theme="secondary">最大使用次数</Typography.Text>
              <InputNumber value={enrollCodeMaxUses} min={1} max={99} onChange={(value) => onEnrollMaxUsesChange(Number(value) || 1)} />
            </Col>
            <Col span={6}>
              <Typography.Text theme="secondary">备注</Typography.Text>
              <Input value={enrollCodeNote} onChange={(value) => onEnrollNoteChange(String(value))} placeholder="例如：158 主机首装" />
            </Col>
          </Row>
          <Space align="center" size="small">
            <Button theme="primary" loading={enrollCodeCreating} onClick={onCreateEnrollCode}>
              生成注册码
            </Button>
            <Button size="small" variant="outline" onClick={onRefreshEnrollCodes}>
              刷新
            </Button>
          </Space>
          {enrollCodesError ? <Alert theme="error" message={enrollCodesError} /> : null}
          <div className="max-h-[260px] overflow-auto rounded-2xl border border-slate-200/70 dark:border-slate-800">
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-slate-50 text-[11px] text-slate-600 dark:bg-slate-900/80 dark:text-slate-400">
                <tr className="text-left">
                  <th className="px-3 py-2">注册码</th>
                  <th className="px-3 py-2">角色</th>
                  <th className="px-3 py-2">状态</th>
                  <th className="px-3 py-2">使用次数</th>
                  <th className="px-3 py-2">过期时间</th>
                  <th className="px-3 py-2 text-right">操作</th>
                </tr>
              </thead>
              <tbody>
                {enrollCodes.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-4 py-6 text-center text-slate-500">
                      {enrollCodesLoading ? '加载中…' : '暂无注册码'}
                    </td>
                  </tr>
                ) : (
                  enrollCodes.map((item) => (
                    <tr key={`comfy-enroll-${item.id}`} className="border-t border-slate-100 dark:border-slate-800">
                      <td className="px-3 py-2 font-mono text-[11px] text-slate-800 dark:text-slate-200">{item.code}</td>
                      <td className="px-3 py-2 text-slate-700 dark:text-slate-300">{item.role}</td>
                      <td className="px-3 py-2">
                        <StatusBadge status={item.status} />
                      </td>
                      <td className="px-3 py-2 text-slate-600 dark:text-slate-400">
                        {item.usedCount}/{item.maxUses}
                      </td>
                      <td className="px-3 py-2 text-slate-600 dark:text-slate-400">{formatDateTime(item.expiresAt)}</td>
                      <td className="px-3 py-2 text-right">
                        <button className="text-sky-400" onClick={() => onCopyText(item.code)}>
                          复制
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

      <Card bordered title="桌面端安装包版本">
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
            <Space align="center" size="small">
              <Select
                value={releaseStatusFilter}
                onChange={(value) => onReleaseStatusFilterChange(String(value))}
                options={[{ label: '全部状态', value: 'all' }, ...releaseStatusOptions.map((item) => ({ label: item.label, value: item.value }))]}
              />
              <Button size="small" variant="outline" onClick={onRefreshReleases}>
                刷新
              </Button>
            </Space>
            <Button theme="primary" onClick={onCreateRelease}>
              新增安装包
            </Button>
          </Space>
          {releasesError ? <Alert theme="error" message={releasesError} /> : null}
          <div className="max-h-[360px] overflow-auto rounded-2xl border border-slate-200/70 dark:border-slate-800">
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-slate-50 text-[11px] text-slate-600 dark:bg-slate-900/80 dark:text-slate-400">
                <tr className="text-left">
                  <th className="px-3 py-2">版本</th>
                  <th className="px-3 py-2">通道</th>
                  <th className="px-3 py-2">状态</th>
                  <th className="px-3 py-2">系统</th>
                  <th className="px-3 py-2">下载地址</th>
                  <th className="px-3 py-2">发布时间</th>
                  <th className="px-3 py-2 text-right">操作</th>
                </tr>
              </thead>
              <tbody>
                {releases.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-4 py-6 text-center text-slate-500">
                      {releasesLoading ? '加载中…' : '暂无安装包版本'}
                    </td>
                  </tr>
                ) : (
                  releases.map((item) => (
                    <tr
                      key={`comfy-desktop-release-${item.id}`}
                      className={`border-t border-slate-100 cursor-pointer dark:border-slate-800 ${
                        String(item.id) === installReleaseId ? 'bg-sky-50/60 dark:bg-sky-900/20' : ''
                      }`}
                      onClick={() => onInstallReleaseChange(String(item.id))}
                    >
                      <td className="px-3 py-2 text-slate-900 dark:text-white">{item.version}</td>
                      <td className="px-3 py-2 text-slate-700 dark:text-slate-300">{item.channel}</td>
                      <td className="px-3 py-2">
                        <StatusBadge status={item.status} />
                      </td>
                      <td className="px-3 py-2 text-slate-700 dark:text-slate-300">
                        {item.osType}/{item.arch}
                      </td>
                      <td className="px-3 py-2 text-slate-600 dark:text-slate-400">{item.downloadUrl}</td>
                      <td className="px-3 py-2 text-slate-600 dark:text-slate-400">
                        {item.publishedAt ? formatDateTime(item.publishedAt) : '—'}
                      </td>
                      <td className="px-3 py-2 text-right space-x-2">
                        <button
                          className="text-cyan-500"
                          onClick={(event) => {
                            event.stopPropagation();
                            const url = (item.downloadUrl || '').trim();
                            if (!url) return;
                            window.open(url, '_blank', 'noopener,noreferrer');
                          }}
                        >
                          下载
                        </button>
                        <button
                          className="text-sky-400"
                          onClick={(event) => {
                            event.stopPropagation();
                            onInstallReleaseChange(String(item.id));
                            onEditRelease(item);
                          }}
                        >
                          编辑
                        </button>
                        <button
                          className="text-emerald-500"
                          onClick={(event) => {
                            event.stopPropagation();
                            onToggleReleaseStatus(item);
                          }}
                        >
                          {item.status === 'active' ? '停用' : '启用'}
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
        header={releaseForm.id ? '编辑安装包版本' : '新增安装包版本'}
        visible={releaseDialogOpen}
        width={760}
        confirmBtn={releaseSaving ? { loading: true } : undefined}
        onClose={onCloseReleaseDialog}
        onConfirm={onSaveRelease}
      >
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Row gutter={[12, 12]}>
            <Col span={12}>
              <Typography.Text theme="secondary">版本号</Typography.Text>
              <Input value={releaseForm.version || ''} onChange={(value) => onReleaseFormPatch({ version: String(value) })} placeholder="例如 0.1.0" />
            </Col>
            <Col span={12}>
              <Typography.Text theme="secondary">通道</Typography.Text>
              <Input
                value={releaseForm.channel || 'stable'}
                onChange={(value) => onReleaseFormPatch({ channel: String(value) })}
                placeholder="stable / beta"
              />
            </Col>
          </Row>
          <Row gutter={[12, 12]}>
            <Col span={8}>
              <Typography.Text theme="secondary">系统</Typography.Text>
              <Select
                value={releaseForm.osType || 'windows'}
                onChange={(value) => onReleaseFormPatch({ osType: String(value) })}
                options={[
                  { label: 'Windows', value: 'windows' },
                  { label: 'Linux', value: 'linux' },
                  { label: 'macOS', value: 'macos' },
                ]}
              />
            </Col>
            <Col span={8}>
              <Typography.Text theme="secondary">架构</Typography.Text>
              <Select
                value={releaseForm.arch || 'x64'}
                onChange={(value) => onReleaseFormPatch({ arch: String(value) })}
                options={[
                  { label: 'x64', value: 'x64' },
                  { label: 'arm64', value: 'arm64' },
                ]}
              />
            </Col>
            <Col span={8}>
              <Typography.Text theme="secondary">状态</Typography.Text>
              <Select
                value={releaseForm.status || 'active'}
                onChange={(value) => onReleaseFormPatch({ status: String(value) })}
                options={releaseStatusOptions.map((item) => ({ label: item.label, value: item.value }))}
              />
            </Col>
          </Row>
          <div>
            <Typography.Text theme="secondary">下载地址</Typography.Text>
            <Input value={releaseForm.downloadUrl || ''} onChange={(value) => onReleaseFormPatch({ downloadUrl: String(value) })} placeholder="https://..." />
          </div>
          <Row gutter={[12, 12]}>
            <Col span={12}>
              <Typography.Text theme="secondary">SHA256</Typography.Text>
              <Input value={releaseForm.sha256 || ''} onChange={(value) => onReleaseFormPatch({ sha256: String(value) })} placeholder="安装包校验值" />
            </Col>
            <Col span={12}>
              <Typography.Text theme="secondary">最小代理版本（可选）</Typography.Text>
              <Input
                value={releaseForm.minAgentVersion || ''}
                onChange={(value) => onReleaseFormPatch({ minAgentVersion: String(value) })}
                placeholder="例如 0.1.0"
              />
            </Col>
          </Row>
          <div>
            <Typography.Text theme="secondary">备注（可选）</Typography.Text>
            <Input value={releaseForm.notes || ''} onChange={(value) => onReleaseFormPatch({ notes: String(value) })} placeholder="发布说明" />
          </div>
          <div>
            <Typography.Text theme="secondary">扩展参数（JSON，可选）</Typography.Text>
            <Textarea
              value={releasePayloadInput}
              onChange={(value) => onReleasePayloadInputChange(String(value))}
              autosize={{ minRows: 3, maxRows: 8 }}
              className="font-mono text-xs"
              placeholder='{"fileSize": 123456}'
            />
          </div>
          {releaseFormError ? <Alert theme="error" message={releaseFormError} /> : null}
        </Space>
      </Dialog>
    </div>
  );
}
