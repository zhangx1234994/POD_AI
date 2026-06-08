import { Button, Card, Col, Row, Select, Space, Table, Tag, Typography } from 'tdesign-react';
import type { AbilityHealthSummaryItem, AbilityHealthSummaryResponse } from '../../../types/admin';
import { getAbilityHealthTag } from './abilityLogs';
import { formatDateTime } from './formatters';

export type AbilityHealthFilter = 'needs_test' | 'stale' | 'failed' | 'unknown' | 'degraded' | 'healthy' | 'all';

const AbilityMetricCard = ({ label, value, sub }: { label: string; value: number | string; sub?: string }) => (
  <Card bordered className="podi-metric-card">
    <Space direction="vertical" size="small">
      <Typography.Text theme="secondary">{label}</Typography.Text>
      <Typography.Title level="h2" style={{ margin: 0 }}>
        {value}
      </Typography.Title>
      {sub ? <Typography.Text theme="secondary">{sub}</Typography.Text> : null}
    </Space>
  </Card>
);

const resolveAbilityHealthAction = (row: AbilityHealthSummaryItem): { theme: 'success' | 'warning' | 'danger' | 'default'; text: string; detail: string } => {
  if (row.healthStatus === 'failed') {
    return {
      theme: 'danger',
      text: '先排查失败',
      detail: '看最近失败日志，修复后再跑能力测试。',
    };
  }
  if (row.healthStatus === 'degraded') {
    return {
      theme: 'warning',
      text: '先复测',
      detail: '成功率下降，发布前不要直接绑定业务默认版本。',
    };
  }
  if (row.needsTest) {
    return {
      theme: 'warning',
      text: row.latestLogAt ? '重新复测' : '先跑测试',
      detail: row.latestLogAt ? '最近测试结果已过期，先补一条新样本。' : '还没有有效调用记录，先跑通一条真实样本。',
    };
  }
  if (row.healthStatus === 'healthy') {
    return {
      theme: 'success',
      text: '可继续',
      detail: '当前健康正常，可进入业务绑定或小流量验证。',
    };
  }
  return {
    theme: 'default',
    text: '先补样本',
    detail: '缺少足够样本，先跑能力测试确认输出回填。',
  };
};

export function AbilityHealthPanel({
  summary,
  filter,
  filteredItems,
  exporting,
  onFilterChange,
  onExport,
  getProviderLabel,
}: {
  summary: AbilityHealthSummaryResponse;
  filter: AbilityHealthFilter;
  filteredItems: AbilityHealthSummaryItem[];
  exporting: boolean;
  onFilterChange: (value: AbilityHealthFilter) => void;
  onExport: () => void;
  getProviderLabel: (provider: string) => string;
}) {
  return (
    <Space direction="vertical" size="middle" style={{ width: '100%', marginBottom: 16 }}>
      <Row gutter={[12, 12]}>
        <Col xs={24} sm={12} lg={4}>
          <AbilityMetricCard label="正常" value={summary.healthy} sub="最近调用成功" />
        </Col>
        <Col xs={24} sm={12} lg={4}>
          <AbilityMetricCard label="需关注" value={summary.degraded} sub="最近失败但总体可用" />
        </Col>
        <Col xs={24} sm={12} lg={4}>
          <AbilityMetricCard label="异常" value={summary.failed} sub="需要优先排查" />
        </Col>
        <Col xs={24} sm={12} lg={4}>
          <AbilityMetricCard label="未测试" value={summary.unknown} sub="没有有效调用记录" />
        </Col>
        <Col xs={24} sm={12} lg={4}>
          <AbilityMetricCard label="需要复测" value={summary.needsTestCount} sub={`超过 ${summary.staleHours} 小时或异常`} />
        </Col>
        <Col xs={24} sm={12} lg={4}>
          <AbilityMetricCard label="能力总数" value={summary.total} sub={`更新：${formatDateTime(summary.generatedAt)}`} />
        </Col>
      </Row>

      {summary.items.length > 0 ? (
        <Card
          bordered
          title={
            <Space align="center" style={{ justifyContent: 'space-between', width: '100%', flexWrap: 'wrap' }}>
              <div>
                <Typography.Text strong>复测清单</Typography.Text>
                <div>
                  <Typography.Text theme="secondary">默认只看需要复测；导出会按当前筛选生成 CSV。</Typography.Text>
                </div>
              </div>
              <Space>
                <Select
                  value={filter}
                  onChange={(value) => onFilterChange(String(value) as AbilityHealthFilter)}
                  style={{ width: 180 }}
                  options={[
                    { label: '需要复测', value: 'needs_test' },
                    { label: '异常', value: 'failed' },
                    { label: '未测试', value: 'unknown' },
                    { label: '超过 24 小时', value: 'stale' },
                    { label: '需关注', value: 'degraded' },
                    { label: '正常', value: 'healthy' },
                    { label: '全部', value: 'all' },
                  ]}
                />
                <Button variant="outline" loading={exporting} onClick={onExport}>
                  导出清单
                </Button>
              </Space>
            </Space>
          }
        >
          <Table
            rowKey="abilityId"
            size="small"
            data={filteredItems}
            columns={[
              {
                colKey: 'ability',
                title: '能力',
                cell: ({ row }) => (
                  <Space direction="vertical" size={2}>
                    <Typography.Text strong>{row.displayName}</Typography.Text>
                    <Typography.Text theme="secondary">
                      {getProviderLabel(row.provider)} · {row.capabilityKey}
                    </Typography.Text>
                  </Space>
                ),
              },
              {
                colKey: 'health',
                title: '健康状态',
                width: 140,
                cell: ({ row }) => {
                  const tag = getAbilityHealthTag(row.healthStatus);
                  return (
                    <Space direction="vertical" size={2}>
                      <Tag theme={tag.theme} variant="light">
                        {tag.text}
                      </Tag>
                      {row.needsTest ? (
                        <Typography.Text theme="warning" style={{ fontSize: 12 }}>
                          建议复测
                        </Typography.Text>
                      ) : null}
                    </Space>
                  );
                },
              },
              {
                colKey: 'last',
                title: '最近有效调用',
                width: 220,
                cell: ({ row }) => (
                  <Space direction="vertical" size={2}>
                    <Typography.Text theme="secondary">
                      {row.latestLogAt ? formatDateTime(row.latestLogAt) : '暂无记录'}
                    </Typography.Text>
                    <Typography.Text theme="secondary">
                      成功率：{typeof row.successRate === 'number' ? `${(row.successRate * 100).toFixed(1)}%` : '—'}
                    </Typography.Text>
                  </Space>
                ),
              },
              {
                colKey: 'nextAction',
                title: '当前要做',
                minWidth: 260,
                cell: ({ row }) => {
                  const action = resolveAbilityHealthAction(row);
                  return (
                    <Space direction="vertical" size={2}>
                      <Tag theme={action.theme} variant="light">
                        {action.text}
                      </Tag>
                      <Typography.Text theme="secondary">{action.detail}</Typography.Text>
                    </Space>
                  );
                },
              },
            ]}
            empty={<Typography.Text theme="secondary">当前筛选下暂无能力。</Typography.Text>}
          />
        </Card>
      ) : null}
    </Space>
  );
}
