import { useState } from 'react';
import { Alert, Button, Col, Dialog, Row, Space, Tag, Typography } from 'tdesign-react';
import type { AbilityInvocationLog, DispatchLogEntry, JsonRecord } from '../../../types/admin';
import { toDisplayErrorMessage } from '../../../utils/errorMessageMap';
import { getAbilityLogStatusTag, resolveAbilityLogAction, resolveLogOutputSummary } from './abilityLogs';
import { formatDate, formatDateTime, formatDurationMs } from './formatters';
import { StatusBadge } from '../shared/ui';

type StatusTheme = 'default' | 'primary' | 'success' | 'warning' | 'danger';

const abilitySourceLabels: Record<string, string> = {
  'admin-test': '控制台测试',
  workflow: '工作流',
  task: '任务调度',
  'ability-api': '能力接口',
  'ability-task': '异步任务',
  ability_api: '能力接口',
  ability_task: '异步任务',
};

const formatAbilitySource = (value?: string | null) => {
  if (!value) return '未知来源';
  return abilitySourceLabels[value] ?? value;
};

const getAbilitySourceTagTheme = (value?: string | null): StatusTheme => {
  const v = value || '';
  if (v === 'admin-test') return 'primary';
  if (v === 'ability-api' || v === 'ability_api') return 'warning';
  if (v === 'ability-task' || v === 'ability_task') return 'default';
  if (v === 'workflow') return 'success';
  if (v === 'task') return 'warning';
  return 'default';
};

const stringifyJSON = (value?: string | JsonRecord | null) => {
  if (!value) return '';
  if (typeof value === 'string') return value;
  return JSON.stringify(value, null, 2);
};

const formatRawResponse = (record?: JsonRecord | null, max = 2000) => {
  if (!record) return '';
  const raw = stringifyJSON(record);
  return raw.length > max ? `${raw.slice(0, max)}…` : raw;
};

function CodeBlock({ value, maxHeight = 320 }: { value: string; maxHeight?: number }) {
  const [copied, setCopied] = useState(false);
  return (
    <div style={{ position: 'relative' }}>
      <Button
        size="small"
        variant="text"
        style={{ position: 'absolute', top: 6, right: 6, zIndex: 1 }}
        onClick={async () => {
          try {
            await navigator.clipboard.writeText(value);
            setCopied(true);
            window.setTimeout(() => setCopied(false), 1200);
          } catch {
            // Clipboard may be unavailable in restricted browser contexts.
          }
        }}
      >
        {copied ? '已复制' : '复制'}
      </Button>
      <pre
        style={{
          marginTop: 8,
          padding: 12,
          paddingRight: 56,
          borderRadius: 8,
          border: '1px solid var(--td-border-level-1-color)',
          background: 'var(--td-bg-color-secondarycontainer)',
          color: 'var(--td-text-color-primary)',
          fontSize: 12,
          lineHeight: 1.5,
          maxHeight,
          overflow: 'auto',
        }}
      >
        {value}
      </pre>
    </div>
  );
}

export function AbilityLogDetailDialog({
  detail,
  visible,
  durationMs,
  resolveError,
  resolveLoading,
  onClose,
  onResolve,
}: {
  detail: AbilityInvocationLog | null;
  visible: boolean;
  durationMs: number | null;
  resolveError: string | null;
  resolveLoading: boolean;
  onClose: () => void;
  onResolve: () => void | Promise<void>;
}) {
  return (
    <Dialog
      header={detail ? `能力调用详情：${detail.id}` : '能力调用详情'}
      visible={visible}
      width={860}
      confirmBtn={null}
      cancelBtn="关闭"
      onClose={onClose}
      onCancel={onClose}
    >
      {detail ? (
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          {(() => {
            const action = resolveAbilityLogAction(detail);
            const alertTheme =
              action.theme === 'danger'
                ? 'error'
                : action.theme === 'success'
                  ? 'success'
                  : action.theme === 'warning'
                    ? 'warning'
                    : 'info';
            return <Alert theme={alertTheme} message={`${action.title}：${action.detail}`} />;
          })()}
          <Row gutter={[12, 12]}>
            <Col span={12}>
              <Typography.Text theme="secondary">能力</Typography.Text>
              <div>
                <Typography.Text strong>{detail.ability_name || detail.capability_key}</Typography.Text>
              </div>
              <Typography.Text theme="secondary">{detail.ability_provider}</Typography.Text>
            </Col>
            <Col span={12}>
              <Typography.Text theme="secondary">状态</Typography.Text>
              <div>
                <Tag theme={getAbilityLogStatusTag(detail.status).theme} variant="light">
                  {getAbilityLogStatusTag(detail.status).text}
                </Tag>
              </div>
              <Typography.Text theme="secondary">
                {formatDateTime(detail.created_at)} · {formatDurationMs(durationMs)}
              </Typography.Text>
            </Col>
            <Col span={12}>
              <Typography.Text theme="secondary">来源</Typography.Text>
              <div>
                <Tag theme={getAbilitySourceTagTheme(detail.source)} variant="light">
                  {formatAbilitySource(detail.source)}
                </Tag>
              </div>
            </Col>
            <Col span={12}>
              <Typography.Text theme="secondary">节点</Typography.Text>
              <div>
                <Typography.Text>{detail.executor_name || detail.executor_type || detail.executor_id || '—'}</Typography.Text>
              </div>
            </Col>
          </Row>
          <Row gutter={[12, 12]}>
            <Col span={12}>
              <Typography.Text theme="secondary">回调编号</Typography.Text>
              <div>
                <Typography.Text style={{ fontFamily: 'monospace' }}>{detail.callback_id || '—'}</Typography.Text>
              </div>
            </Col>
            <Col span={12}>
              <Typography.Text theme="secondary">请求追踪</Typography.Text>
              <div>
                <Typography.Text style={{ fontFamily: 'monospace' }}>{detail.trace_id || '—'}</Typography.Text>
              </div>
              {detail.workflow_run_id ? (
                <Typography.Text theme="secondary" style={{ display: 'block', marginTop: 4 }}>
                  工作流编号：<span style={{ fontFamily: 'monospace' }}>{detail.workflow_run_id}</span>
                </Typography.Text>
              ) : null}
            </Col>
          </Row>

          {(() => {
            const resolveMeta = (detail.response_payload || {}) as Record<string, unknown>;
            const resolvePromptId = resolveMeta.promptId || resolveMeta.taskId;
            const output = resolveLogOutputSummary(detail);
            if (!output.hasOutput) {
              if ((detail.ability_provider || '').toLowerCase() === 'comfyui' && resolvePromptId) {
                return (
                  <div>
                    <Typography.Text theme="secondary">输出资源</Typography.Text>
                    <div style={{ marginTop: 8 }}>
                      <Space direction="vertical" size="small">
                        <Typography.Text theme="secondary">当前为提交态结果，尚未解析到图片、视频或文字输出。</Typography.Text>
                        {resolveError ? <Alert theme="error" message={resolveError} /> : null}
                        <Button variant="outline" loading={resolveLoading} onClick={onResolve}>
                          拉取回调结果
                        </Button>
                      </Space>
                    </div>
                  </div>
                );
              }
              return null;
            }
            return (
              <div>
                <Typography.Text theme="secondary">输出资源：{output.label}</Typography.Text>
                <div style={{ marginTop: 8 }}>
                  <Space direction="vertical" size="small">
                    {output.textPreview ? (
                      <div
                        style={{
                          padding: 12,
                          borderRadius: 8,
                          border: '1px solid var(--td-border-level-1-color)',
                          background: 'var(--td-bg-color-secondarycontainer)',
                          whiteSpace: 'pre-wrap',
                        }}
                      >
                        {output.textPreview}
                      </div>
                    ) : null}
                    {output.primaryUrl && output.primaryKind === 'image' ? (
                      <img src={output.primaryUrl} alt="preview" style={{ maxWidth: '100%', maxHeight: 420, display: 'block' }} />
                    ) : null}
                    {output.primaryUrl && output.primaryKind !== 'image' ? (
                      <Button variant="outline" onClick={() => window.open(output.primaryUrl, '_blank', 'noreferrer')}>
                        {output.primaryKind === 'video' ? '打开视频链接' : '打开资源链接'}
                      </Button>
                    ) : null}
                  </Space>
                  {resolveError ? <Alert theme="error" message={resolveError} /> : null}
                </div>
              </div>
            );
          })()}

          {detail.request_payload ? (
            <div>
              <Typography.Text theme="secondary">请求内容（排障）</Typography.Text>
              <CodeBlock value={formatRawResponse(detail.request_payload)} maxHeight={260} />
            </div>
          ) : null}

          {detail.response_payload ? (
            <div>
              <Typography.Text theme="secondary">响应内容（排障）</Typography.Text>
              <CodeBlock value={formatRawResponse(detail.response_payload)} maxHeight={260} />
            </div>
          ) : null}

          {(() => {
            const hasCallback =
              detail.callback_status ||
              detail.callback_http_status ||
              detail.callback_started_at ||
              detail.callback_finished_at ||
              detail.callback_payload ||
              detail.callback_response ||
              detail.callback_error;
            if (!hasCallback) return null;
            return (
              <div>
                <Typography.Text theme="secondary">回调记录</Typography.Text>
                <Space direction="vertical" size="small" style={{ marginTop: 8, width: '100%' }}>
                  <Space align="center" size="small">
                    {detail.callback_status ? (
                      <Tag theme={getAbilityLogStatusTag(detail.callback_status).theme} variant="light">
                        {getAbilityLogStatusTag(detail.callback_status).text}
                      </Tag>
                    ) : null}
                    {typeof detail.callback_http_status === 'number' ? (
                      <Typography.Text theme="secondary">HTTP {detail.callback_http_status}</Typography.Text>
                    ) : null}
                    {detail.callback_started_at ? (
                      <Typography.Text theme="secondary">开始：{formatDateTime(detail.callback_started_at)}</Typography.Text>
                    ) : null}
                    {detail.callback_finished_at ? (
                      <Typography.Text theme="secondary">完成：{formatDateTime(detail.callback_finished_at)}</Typography.Text>
                    ) : null}
                  </Space>
                  {detail.callback_payload ? (
                    <div>
                      <Typography.Text theme="secondary">回调请求内容</Typography.Text>
                      <CodeBlock value={formatRawResponse(detail.callback_payload)} maxHeight={240} />
                    </div>
                  ) : null}
                  {detail.callback_response ? (
                    <div>
                      <Typography.Text theme="secondary">回调响应内容</Typography.Text>
                      <CodeBlock value={formatRawResponse(detail.callback_response)} maxHeight={240} />
                    </div>
                  ) : null}
                  {detail.callback_error ? <Alert theme="error" message={toDisplayErrorMessage(detail.callback_error)} /> : null}
                </Space>
              </div>
            );
          })()}

          {detail.error_message ? <Alert theme="error" message={toDisplayErrorMessage(detail.error_message)} /> : null}
        </Space>
      ) : null}
    </Dialog>
  );
}

export function DispatchLogDetailDialog({
  detail,
  visible,
  onClose,
}: {
  detail: DispatchLogEntry | null;
  visible: boolean;
  onClose: () => void;
}) {
  return (
    <Dialog
      header={detail ? `调度回执详情：${detail.id}` : '调度回执详情'}
      visible={visible}
      width={820}
      confirmBtn={null}
      cancelBtn="关闭"
      onClose={onClose}
      onCancel={onClose}
    >
      {detail ? (
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Row gutter={[12, 12]}>
            <Col span={12}>
              <Typography.Text theme="secondary">任务</Typography.Text>
              <div>
                <Typography.Text strong>{detail.tool_action || '—'}</Typography.Text>
              </div>
              <Typography.Text theme="secondary">{detail.task_id || '—'}</Typography.Text>
            </Col>
            <Col span={12}>
              <Typography.Text theme="secondary">事件类型</Typography.Text>
              <div>
                <StatusBadge status={detail.event_type} />
              </div>
              <Typography.Text theme="secondary">{formatDate(detail.created_at)}</Typography.Text>
            </Col>
            <Col span={12}>
              <Typography.Text theme="secondary">任务状态</Typography.Text>
              <div>
                <StatusBadge status={detail.task_status} />
              </div>
            </Col>
          </Row>
          {detail.payload ? (
            <div>
              <Typography.Text theme="secondary">回执内容</Typography.Text>
              <CodeBlock value={formatRawResponse(detail.payload)} maxHeight={320} />
            </div>
          ) : (
            <Typography.Text theme="secondary">无回执内容</Typography.Text>
          )}
        </Space>
      ) : null}
    </Dialog>
  );
}
