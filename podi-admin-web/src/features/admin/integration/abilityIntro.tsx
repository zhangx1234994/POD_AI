import { useState } from 'react';
import { Alert, Button, Card, Col, Row, Space, Table, Tag, Typography } from 'tdesign-react';
import type { Ability, AbilityHealthSummaryResponse, PublicAbility } from '../../../types/admin';
import { resolveAbilityOutputProfile } from './abilityOutputProfile';

function MetricCard({ label, value, sub }: { label: string; value: number | string; sub?: string }) {
  return (
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
}

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
            // ignore clipboard errors
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

const publicAbilityToAbility = (row: PublicAbility): Ability => {
  const metadata = { ...(row.metadata || {}) };
  if (row.requiresImage !== undefined) metadata.requires_image_input = row.requiresImage;
  if (row.supportsMultipleImages !== undefined) metadata.supports_multiple_images = row.supportsMultipleImages;
  return {
    id: row.id,
    provider: row.provider,
    category: row.category,
    capability_key: row.capabilityKey,
    version: row.version,
    display_name: row.displayName,
    description: row.description,
    status: row.status,
    ability_type: row.abilityType,
    executor_id: row.executorId,
    workflow_id: row.workflowId,
    vendor_model_id: row.vendorModelId,
    coze_workflow_id: row.cozeWorkflowId,
    default_params: row.defaultParams,
    input_schema: row.inputSchema,
    metadata,
    last_health_check_at: row.lastHealthCheckAt,
    last_health_status: row.lastHealthStatus,
    success_rate: row.successRate,
    created_at: '',
    updated_at: '',
  };
};

export function AbilityOverviewSummaryPanel({
  abilityHealthSummary,
  abilityTotalFallback,
  filteredCount,
}: {
  abilityHealthSummary?: AbilityHealthSummaryResponse | null;
  abilityTotalFallback: number;
  filteredCount: number;
}) {
  return (
    <>
      <Row gutter={[12, 12]}>
        <Col xs={12} sm={6} lg={2}>
          <MetricCard label="能力总数" value={abilityHealthSummary?.total ?? abilityTotalFallback} sub="全部原子能力" />
        </Col>
        <Col xs={12} sm={6} lg={2}>
          <MetricCard label="正常" value={abilityHealthSummary?.healthy ?? 0} sub="最近调用成功" />
        </Col>
        <Col xs={12} sm={6} lg={2}>
          <MetricCard label="需关注" value={(abilityHealthSummary?.degraded ?? 0) + (abilityHealthSummary?.failed ?? 0)} sub="失败或降级" />
        </Col>
        <Col xs={12} sm={6} lg={2}>
          <MetricCard label="未测试" value={abilityHealthSummary?.unknown ?? 0} sub="缺少有效样本" />
        </Col>
        <Col xs={12} sm={6} lg={2}>
          <MetricCard label="需要复测" value={abilityHealthSummary?.needsTestCount ?? 0} sub="超时未测或异常" />
        </Col>
        <Col xs={12} sm={6} lg={2}>
          <MetricCard label="当前筛选" value={filteredCount} sub="能力列表结果" />
        </Col>
      </Row>
      <Card bordered style={{ marginTop: 12 }}>
        <Space direction="vertical" size="small" style={{ width: '100%' }}>
          <Typography.Text strong>普通用户只需要先看三件事</Typography.Text>
          <Row gutter={[12, 12]}>
            <Col xs={12} md={4}>
              <Alert theme="info" message="这个能力归属哪个业务阶段：源图处理、生成变化、尺寸适配、后处理，还是文本/VL。" />
            </Col>
            <Col xs={12} md={4}>
              <Alert theme="info" message="最近是否可用：正常、需关注、异常、未测试、需要复测。" />
            </Col>
            <Col xs={12} md={4}>
              <Alert theme="info" message="是否能直接测试：选择能力后进入详情页，参数表单和调用记录都在同一处。" />
            </Col>
          </Row>
        </Space>
      </Card>
    </>
  );
}

export function AbilityRoadmapPanel() {
  return (
    <div className="grid gap-3 md:grid-cols-3">
      {[
        { title: '图像工作流', status: '已接入', body: 'ComfyUI 工作流、图裂变、扩图、抠图等，按运行线路和标签路由。' },
        { title: '第三方模型', status: '已接入', body: 'OpenAI、KIE、火山、百度等统一走能力服务，密钥与出网能力独立管理。' },
        { title: '自研图像工具', status: '已拆分', body: '放大、DPI、扩边占位图等轻工具由 image-ops 承载，不占用 Coze 主机资源。' },
        { title: '图像理解', status: '进行中', body: 'VL 作为弹药库原子能力，用于图片描述、主体、风格、风险和提示词建议。' },
        { title: '向量检索', status: '规划中', body: '后续承载素材检索、模板匹配和知识库搜索，仍按能力、日志、自检统一治理。' },
        { title: '内容安全', status: '规划中', body: '鉴黄、版权风险、文字审核等独立成安全能力，避免散落在业务流程里。' },
      ].map((item) => (
        <div
          key={`future-ability-${item.title}`}
          className="rounded-2xl border border-slate-200 bg-white/80 p-4 text-sm dark:border-slate-800 dark:bg-slate-950/40"
        >
          <div className="flex items-center justify-between gap-3">
            <Typography.Text strong>{item.title}</Typography.Text>
            <Tag
              size="small"
              variant="light"
              theme={item.status === '已接入' || item.status === '已拆分' ? 'success' : item.status === '进行中' ? 'warning' : 'default'}
            >
              {item.status}
            </Tag>
          </div>
          <p className="mt-2 text-slate-600 dark:text-slate-400">{item.body}</p>
        </div>
      ))}
    </div>
  );
}

export function AbilityApiPanel({
  publicAbilities,
  publicAbilitiesLoading,
  abilityApiExample,
  onRefresh,
  onCopy,
  getProviderLabel,
  getCategoryLabel,
}: {
  publicAbilities: PublicAbility[];
  publicAbilitiesLoading: boolean;
  abilityApiExample: string;
  onRefresh: () => void;
  onCopy: (value: string) => void;
  getProviderLabel: (value: string) => string;
  getCategoryLabel: (value: string) => string;
}) {
  return (
    <Card bordered>
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        <Space align="start" style={{ justifyContent: 'space-between', width: '100%' }}>
          <Typography.Text theme="secondary">
            所有终端都应通过{' '}
            <Tag theme="primary" variant="outline" size="small">
              GET /api/abilities
            </Tag>{' '}
            查询能力，并使用{' '}
            <Tag theme="primary" variant="outline" size="small">
              POST /api/abilities/&lt;abilityId&gt;/invoke
            </Tag>{' '}
            触发；调度层会根据能力配置、路由规则与运行线路健康度自行分配资源。
          </Typography.Text>
          <Button variant="outline" size="small" loading={publicAbilitiesLoading} onClick={onRefresh}>
            刷新列表
          </Button>
        </Space>

        <details
          style={{
            border: '1px solid var(--td-border-level-1-color)',
            borderRadius: 12,
            padding: 12,
          }}
        >
          <summary style={{ cursor: 'pointer', fontWeight: 600 }}>开发接入示例（高级）</summary>
          <div style={{ marginTop: 12 }}>
            <Typography.Text theme="secondary">给开发同学联调用，可复制到接口调试工具。</Typography.Text>
            <CodeBlock value={abilityApiExample} maxHeight={260} />
          </div>
        </details>

        <div>
          <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
            <Typography.Text theme="secondary">能力 ID 清单</Typography.Text>
            <Typography.Text theme="secondary">更多细节见能力接口文档</Typography.Text>
          </Space>
          <div style={{ marginTop: 12 }}>
            <Table
              rowKey="id"
              size="small"
              data={publicAbilities}
              loading={publicAbilitiesLoading}
              maxHeight={360}
              columns={[
                {
                  colKey: 'displayName',
                  title: '能力',
                  ellipsis: true,
                  cell: ({ row }) => (
                    <Space direction="vertical" size={2}>
                      <Typography.Text>{row.displayName}</Typography.Text>
                      <Typography.Text theme="secondary">
                        {getProviderLabel(row.provider)} · {getCategoryLabel(row.category)}
                      </Typography.Text>
                      {row.description ? <Typography.Text theme="secondary">{row.description}</Typography.Text> : null}
                    </Space>
                  ),
                },
                {
                  colKey: 'id',
                  title: '能力编号',
                  width: 360,
                  cell: ({ row }) => (
                    <Space>
                      <Tag theme="default" variant="outline">
                        {row.id}
                      </Tag>
                      <Button size="small" variant="text" onClick={() => onCopy(row.id)}>
                        复制
                      </Button>
                    </Space>
                  ),
                },
                {
                  colKey: 'features',
                  title: '输入 / 输出',
                  width: 280,
                  cell: ({ row }) => {
                    const profile = resolveAbilityOutputProfile(publicAbilityToAbility(row));
                    const tags = [...profile.outputTags, ...profile.inputTags];
                    return (
                      <Space direction="vertical" size={4}>
                        <Tag theme={profile.theme} variant="light" size="small">
                          {profile.label}
                        </Tag>
                        <Typography.Text theme="secondary">{profile.detail}</Typography.Text>
                        <Space size={4} breakLine>
                          {tags.map((tag) => (
                            <Tag key={`${row.id}-public-profile-${tag}`} variant="light" size="small">
                              {tag}
                            </Tag>
                          ))}
                          {row.maxOutputImages ? (
                            <Tag variant="outline" size="small">
                              最高 {row.maxOutputImages} 张结果
                            </Tag>
                          ) : null}
                        </Space>
                      </Space>
                    );
                  },
                },
              ]}
              empty={<Typography.Text theme="secondary">暂无可用能力，请先在“能力管理”新增并设为 active。</Typography.Text>}
            />
          </div>
        </div>
      </Space>
    </Card>
  );
}
