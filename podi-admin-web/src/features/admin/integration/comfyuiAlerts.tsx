import { Alert, Button, Card, Input, InputNumber, Popup, Select, Space, Typography } from 'tdesign-react';
import type { ComfyuiAgentAlert } from '../../../types/admin';
import { formatDateTime } from './formatters';

type SelectOption = {
  label: string;
  value: string;
};

type ComfyuiAlertsPanelProps = {
  alerts: ComfyuiAgentAlert[];
  loading: boolean;
  error?: string | null;
  agentFilter: string;
  agentOptions: SelectOption[];
  typeFilter: string;
  limit: number;
  onAgentFilterChange: (value: string) => void;
  onTypeFilterChange: (value: string) => void;
  onLimitChange: (value: number) => void;
  onRefresh: () => void;
};

const stringifyPayload = (value: unknown) => {
  if (!value || typeof value !== 'object') return '';
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return '';
  }
};

export function ComfyuiAlertsPanel({
  alerts,
  loading,
  error,
  agentFilter,
  agentOptions,
  typeFilter,
  limit,
  onAgentFilterChange,
  onTypeFilterChange,
  onLimitChange,
  onRefresh,
}: ComfyuiAlertsPanelProps) {
  return (
    <div className="space-y-4">
      <Card bordered title="代理服务告警">
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
            <Space align="center" size="small">
              <Select
                value={agentFilter}
                onChange={(value) => onAgentFilterChange(String(value))}
                options={[{ label: '全部代理服务', value: 'all' }, ...agentOptions]}
              />
              <Input value={typeFilter} onChange={(value) => onTypeFilterChange(String(value))} placeholder="告警类型（如 disk_low）" />
              <InputNumber min={1} max={200} value={limit} onChange={(value) => onLimitChange(Number(value) || 50)} />
              <Button size="small" variant="outline" onClick={onRefresh}>
                刷新
              </Button>
            </Space>
            <Typography.Text theme="secondary">{alerts.length ? `共 ${alerts.length} 条` : '暂无告警'}</Typography.Text>
          </Space>
          {error ? <Alert theme="error" message={error} /> : null}
          <div className="max-h-[420px] overflow-auto rounded-2xl border border-slate-200/70 dark:border-slate-800">
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-slate-50 text-[11px] text-slate-600 dark:bg-slate-900/80 dark:text-slate-400">
                <tr className="text-left">
                  <th className="px-3 py-2">时间</th>
                  <th className="px-3 py-2">代理服务</th>
                  <th className="px-3 py-2">类型</th>
                  <th className="px-3 py-2">内容</th>
                  <th className="px-3 py-2">详情</th>
                </tr>
              </thead>
              <tbody>
                {alerts.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-4 py-6 text-center text-slate-500">
                      {loading ? '加载中…' : '暂无告警'}
                    </td>
                  </tr>
                ) : (
                  alerts.map((alert) => {
                    const payloadText = stringifyPayload(alert.payload);
                    return (
                      <tr key={`comfy-agent-alert-${alert.id}`} className="border-t border-slate-100 dark:border-slate-800">
                        <td className="px-3 py-2 text-slate-600 dark:text-slate-400">{formatDateTime(alert.created_at)}</td>
                        <td className="px-3 py-2 text-slate-700 dark:text-slate-300">{alert.agentId}</td>
                        <td className="px-3 py-2 text-slate-700 dark:text-slate-300">{alert.alertType}</td>
                        <td className="px-3 py-2 text-slate-700 dark:text-slate-300">{alert.message || '—'}</td>
                        <td className="px-3 py-2 text-slate-600 dark:text-slate-400">
                          {payloadText ? (
                            <Popup
                              placement="left"
                              trigger="hover"
                              content={<div className="max-w-[360px] whitespace-pre-wrap text-xs text-slate-700">{payloadText}</div>}
                            >
                              <button className="text-sky-400">查看</button>
                            </Popup>
                          ) : (
                            '—'
                          )}
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
    </div>
  );
}
