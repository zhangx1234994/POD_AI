import { Alert, Button, Card, Col, Row, Select, Space, Table, Tag, Typography } from 'tdesign-react';
import type { AbilityLogMetricBucket, AbilityLogMetricsResponse } from '../../../types/admin';
import { ActionBar } from '../shared/ui';

type SelectOption = {
  label: string;
  value: string | number;
};

export function AbilityLogMetricsPanel({
  windowHours,
  provider,
  capabilityKey,
  providerOptions,
  capabilityOptions,
  metrics,
  loading,
  error,
  onWindowHoursChange,
  onProviderChange,
  onCapabilityKeyChange,
  onRefresh,
  getProviderLabel,
}: {
  windowHours: number;
  provider: string;
  capabilityKey: string;
  providerOptions: string[];
  capabilityOptions: SelectOption[];
  metrics?: AbilityLogMetricsResponse | null;
  loading: boolean;
  error?: string | null;
  onWindowHoursChange: (value: number) => void;
  onProviderChange: (value: string) => void;
  onCapabilityKeyChange: (value: string) => void;
  onRefresh: () => void;
  getProviderLabel: (value: string) => string;
}) {
  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <ActionBar>
        <Space align="center" style={{ justifyContent: 'space-between', width: '100%', flexWrap: 'wrap' }}>
          <div>
            <Typography.Text strong>调用指标</Typography.Text>
            <div>
              <Typography.Text theme="secondary">窗口：近 {windowHours} 小时（前 8）</Typography.Text>
            </div>
          </div>
          <Space>
            <Button variant="outline" loading={loading} onClick={onRefresh}>
              刷新指标
            </Button>
          </Space>
        </Space>
      </ActionBar>

      {error ? <Alert theme="error" message={error} /> : null}

      <Row gutter={[12, 12]}>
        <Col flex="160px">
          <Select
            value={windowHours}
            onChange={(value) => onWindowHoursChange(Math.max(1, Number(value) || 24))}
            options={[
              { label: '近 6 小时', value: 6 },
              { label: '近 12 小时', value: 12 },
              { label: '近 24 小时', value: 24 },
              { label: '近 72 小时', value: 72 },
              { label: '近 7 天', value: 168 },
              { label: '近 30 天', value: 720 },
            ]}
          />
        </Col>
        <Col flex="180px">
          <Select
            value={provider}
            onChange={(value) => onProviderChange(String(value))}
            options={[
              { label: '全部厂商', value: 'all' },
              ...providerOptions.map((item) => ({ label: getProviderLabel(item), value: item })),
            ]}
          />
        </Col>
        <Col flex="260px">
          <Select
            value={capabilityKey}
            onChange={(value) => onCapabilityKeyChange(String(value))}
            disabled={provider === 'all'}
            options={[
              { label: provider === 'all' ? '请先选择厂商' : '全部能力', value: 'all' },
              ...capabilityOptions,
            ]}
          />
        </Col>
      </Row>

      {metrics ? (
        <Row gutter={[12, 12]}>
          <Col xs={24} sm={12} lg={6}>
            <Card bordered>
              <Space direction="vertical" size={2}>
                <Typography.Text theme="secondary">调用总次数</Typography.Text>
                <Typography.Text style={{ fontSize: 20, fontWeight: 600 }}>{metrics.total_count ?? 0}</Typography.Text>
              </Space>
            </Card>
          </Col>
          <Col xs={24} sm={12} lg={6}>
            <Card bordered>
              <Space direction="vertical" size={2}>
                <Typography.Text theme="secondary">成功 / 失败</Typography.Text>
                <Typography.Text style={{ fontSize: 20, fontWeight: 600 }}>
                  {(metrics.total_success_count ?? 0)} / {(metrics.total_failed_count ?? 0)}
                </Typography.Text>
              </Space>
            </Card>
          </Col>
          <Col xs={24} sm={12} lg={6}>
            <Card bordered>
              <Space direction="vertical" size={2}>
                <Typography.Text theme="secondary">总成本（估算）</Typography.Text>
                <Typography.Text style={{ fontSize: 20, fontWeight: 600 }}>
                  {metrics.total_cost !== null && metrics.total_cost !== undefined ? metrics.total_cost.toFixed(4) : '—'}
                </Typography.Text>
              </Space>
            </Card>
          </Col>
          <Col xs={24} sm={12} lg={6}>
            <Card bordered>
              <Space direction="vertical" size={2}>
                <Typography.Text theme="secondary">单次均价（估算）</Typography.Text>
                <Typography.Text style={{ fontSize: 20, fontWeight: 600 }}>
                  {metrics.avg_cost_per_call !== null && metrics.avg_cost_per_call !== undefined ? metrics.avg_cost_per_call.toFixed(4) : '—'}
                </Typography.Text>
              </Space>
            </Card>
          </Col>
          <Col xs={24} sm={12} lg={6}>
            <Card bordered>
              <Space direction="vertical" size={2}>
                <Typography.Text theme="secondary">未计价调用数</Typography.Text>
                <Typography.Text style={{ fontSize: 20, fontWeight: 600 }}>{metrics.uncosted_count ?? 0}</Typography.Text>
              </Space>
            </Card>
          </Col>
        </Row>
      ) : null}

      {metrics ? <Alert theme="warning" message="成本为估算值；跨币种不做直接换算汇总。建议按厂商或币种筛选后查看。" /> : null}

      {metrics ? (
        <Row gutter={[12, 12]}>
          <Col xs={24} lg={12}>
            <Card bordered title="按厂商成本（估算）">
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                {(metrics.provider_totals || []).length === 0 ? (
                  <Typography.Text theme="secondary">暂无</Typography.Text>
                ) : (
                  (metrics.provider_totals || []).slice(0, 8).map((item) => (
                    <Tag key={`provider-${item.key}`} variant="light">
                      {item.key}：{item.total_cost !== null && item.total_cost !== undefined ? item.total_cost.toFixed(4) : '—'}
                    </Tag>
                  ))
                )}
              </div>
            </Card>
          </Col>
          <Col xs={24} lg={12}>
            <Card bordered title="按币种成本（估算）">
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                {(metrics.currency_totals || []).length === 0 ? (
                  <Typography.Text theme="secondary">暂无</Typography.Text>
                ) : (
                  (metrics.currency_totals || []).slice(0, 8).map((item) => (
                    <Tag key={`currency-${item.key}`} variant="light">
                      {item.key}：{item.total_cost !== null && item.total_cost !== undefined ? item.total_cost.toFixed(4) : '—'}
                    </Tag>
                  ))
                )}
              </div>
            </Card>
          </Col>
        </Row>
      ) : null}

      {metrics?.buckets && metrics.buckets.length > 0 ? (
        <Card bordered title={`近 ${metrics.window_hours}h 指标（前 8）`}>
          <div className="overflow-x-auto">
            <Table
              size="small"
              rowKey="__key"
              data={(metrics.buckets as AbilityLogMetricBucket[])
                .slice(0, 8)
                .map((bucket) => ({ ...bucket, __key: `${bucket.ability_provider}:${bucket.capability_key}` }))}
              columns={[
                {
                  colKey: 'ability',
                  title: '能力',
                  cell: ({ row }) => (
                    <Space direction="vertical" size={2}>
                      <Typography.Text strong>{row.capability_key}</Typography.Text>
                      <Typography.Text theme="secondary">{row.ability_provider}</Typography.Text>
                    </Space>
                  ),
                },
                {
                  colKey: 'count',
                  title: '次数',
                  width: 120,
                  cell: ({ row }) => (
                    <Typography.Text theme="secondary">
                      {row.count}（{row.success_count}/{row.failed_count}）
                    </Typography.Text>
                  ),
                },
                {
                  colKey: 'success_rate',
                  title: '成功率',
                  width: 120,
                  cell: ({ row }) => (
                    <Typography.Text>
                      {row.success_rate !== null && row.success_rate !== undefined ? `${(row.success_rate * 100).toFixed(1)}%` : '—'}
                    </Typography.Text>
                  ),
                },
                {
                  colKey: 'p50',
                  title: '常规 / 慢请求耗时',
                  width: 160,
                  cell: ({ row }) => (
                    <Typography.Text theme="secondary">
                      {row.p50_duration_ms ?? '—'}ms / {row.p95_duration_ms ?? '—'}ms
                    </Typography.Text>
                  ),
                },
                {
                  colKey: 'cost',
                  title: '成本（总/均）',
                  width: 160,
                  cell: ({ row }) => (
                    <Typography.Text theme="secondary">
                      {row.total_cost !== null && row.total_cost !== undefined ? row.total_cost.toFixed(4) : '—'} /{' '}
                      {row.avg_cost !== null && row.avg_cost !== undefined ? row.avg_cost.toFixed(4) : '—'}
                    </Typography.Text>
                  ),
                },
              ]}
            />
          </div>
        </Card>
      ) : (
        <Typography.Text theme="secondary">暂无指标数据。</Typography.Text>
      )}
    </Space>
  );
}
