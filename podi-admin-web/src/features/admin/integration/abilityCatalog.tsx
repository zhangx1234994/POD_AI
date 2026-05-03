import { Alert, Button, Card, Col, Input, Row, Select, Space, Table, Tag, Typography } from 'tdesign-react';
import type {
  Ability,
  AbilityHealthSummaryItem,
  AbilityHealthSummaryResponse,
  AbilityInvocationLog,
  Executor,
  VendorGovernanceSummaryResponse,
  VendorModel,
  Workflow,
} from '../../../types/admin';
import { mapStatusToBadge } from '../shared/status';
import { getAbilityLogStatusTag, resolveLogDurationMs } from './abilityLogs';
import { resolveAbilityOutputProfile } from './abilityOutputProfile';
import { AbilityHealthPanel, type AbilityHealthFilter } from './abilityHealth';
import { formatDateTime } from './formatters';
import { statusOptions } from './formOptions';

type AbilityPricing = {
  currency?: string;
  unit?: string;
  listPrice?: number;
  discountPrice?: number;
};

type AbilityTemplateSummary = {
  currentId: string | null;
  historyCount: number;
  latestAt: string | null;
  latestAction: string | null;
  latestLabel: string | null;
};

const renderStatusTag = (status?: string | null) => {
  const meta = mapStatusToBadge(status);
  return (
    <Tag theme={meta.theme} variant="light">
      {status || meta.text}
    </Tag>
  );
};

const buildAbilityActionItems = ({
  healthSummary,
  abilities,
  templateSummaryByAbility,
  pricingByAbility,
  getAbilitySchemaIssues,
  describePricing,
}: {
  healthSummary?: AbilityHealthSummaryResponse | null;
  abilities: Ability[];
  templateSummaryByAbility: Record<string, AbilityTemplateSummary>;
  pricingByAbility: Record<string, AbilityPricing>;
  getAbilitySchemaIssues: (ability: Ability | null) => string[];
  describePricing: (pricing: AbilityPricing | null) => string;
}) => {
  const schemaIssueCount = abilities.filter((item) => getAbilitySchemaIssues(item).length > 0).length;
  const unpublishedTemplateCount = abilities.filter((item) => {
    const summary = templateSummaryByAbility[item.id];
    return !summary?.currentId;
  }).length;
  const missingPricingCount = abilities.filter((item) => {
    const pricing = pricingByAbility[item.id] || pricingByAbility[`${item.provider}:${item.capability_key}`] || null;
    return describePricing(pricing) === '—';
  }).length;
  const items: Array<{
    theme: 'success' | 'warning' | 'danger' | 'default';
    title: string;
    detail: string;
    filter?: AbilityHealthFilter;
  }> = [];

  if (Number(healthSummary?.failed || 0) > 0) {
    items.push({
      theme: 'danger',
      title: '先处理异常能力',
      detail: `${healthSummary?.failed || 0} 个能力最近测试失败，先筛选“异常”并复测。`,
      filter: 'failed',
    });
  }
  if (Number(healthSummary?.degraded || 0) > 0) {
    items.push({
      theme: 'warning',
      title: '关注降级能力',
      detail: `${healthSummary?.degraded || 0} 个能力成功率下降，发布前不要直接切业务默认版本。`,
      filter: 'degraded',
    });
  }
  if (Number(healthSummary?.needsTestCount || 0) > 0 || Number(healthSummary?.staleCount || 0) > 0) {
    items.push({
      theme: 'warning',
      title: '补齐复测',
      detail: `${healthSummary?.needsTestCount || 0} 个需要复测，${healthSummary?.staleCount || 0} 个结果过期。`,
      filter: Number(healthSummary?.needsTestCount || 0) > 0 ? 'needs_test' : 'stale',
    });
  }
  if (schemaIssueCount > 0) {
    items.push({
      theme: 'warning',
      title: '表单字段有缺口',
      detail: `${schemaIssueCount} 个能力的入参说明不完整，Coze 或测评端会更难理解。`,
    });
  }
  if (unpublishedTemplateCount > 0) {
    items.push({
      theme: 'warning',
      title: '模板未发布',
      detail: `${unpublishedTemplateCount} 个能力没有当前模板，修改后要先发布模板再给业务使用。`,
    });
  }
  if (missingPricingCount > 0) {
    items.push({
      theme: 'warning',
      title: '成本未设置',
      detail: `${missingPricingCount} 个能力缺少成本口径，后续收费和利润统计会不准。`,
    });
  }
  if (items.length === 0) {
    items.push({
      theme: 'success',
      title: '能力目录当前稳定',
      detail: '健康、复测、模板、表单和成本没有明显阻塞，可继续接入新能力或做业务编排。',
    });
  }
  return items.slice(0, 6);
};

export function AbilityCatalogPanel({
  healthError,
  healthLoading,
  healthSummary,
  healthFilter,
  healthItems,
  healthExporting,
  search,
  providerFilter,
  statusFilter,
  providerOptions,
  abilities,
  selectedAbilityId,
  workflowsById,
  vendorModels,
  vendorGovernanceSummary,
  executors,
  pricingByAbility,
  latestLogByAbility,
  templateSummaryByAbility,
  onRefreshHealth,
  onHealthFilterChange,
  onExportHealth,
  onCreate,
  onSearchChange,
  onProviderFilterChange,
  onStatusFilterChange,
  onSelectAbility,
  onOpenTemplate,
  onEdit,
  onDelete,
  getProviderLabel,
  getCategoryLabel,
  getAbilityTypeLabel,
  getAbilitySchemaIssues,
  describePricing,
}: {
  healthError?: string | null;
  healthLoading: boolean;
  healthSummary?: AbilityHealthSummaryResponse | null;
  healthFilter: AbilityHealthFilter;
  healthItems: AbilityHealthSummaryItem[];
  healthExporting: boolean;
  search: string;
  providerFilter: string;
  statusFilter: string;
  providerOptions: string[];
  abilities: Ability[];
  selectedAbilityId?: string | null;
  workflowsById: Record<string, Workflow>;
  vendorModels: VendorModel[];
  vendorGovernanceSummary?: VendorGovernanceSummaryResponse | null;
  executors: Executor[];
  pricingByAbility: Record<string, AbilityPricing>;
  latestLogByAbility: Record<string, AbilityInvocationLog>;
  templateSummaryByAbility: Record<string, AbilityTemplateSummary>;
  onRefreshHealth: () => void;
  onHealthFilterChange: (value: AbilityHealthFilter) => void;
  onExportHealth: () => void;
  onCreate: () => void;
  onSearchChange: (value: string) => void;
  onProviderFilterChange: (value: string) => void;
  onStatusFilterChange: (value: string) => void;
  onSelectAbility: (id: string) => void;
  onOpenTemplate: (ability: Ability) => void;
  onEdit: (ability: Ability) => void;
  onDelete: (id: string) => void;
  getProviderLabel: (value: string) => string;
  getCategoryLabel: (value: string) => string;
  getAbilityTypeLabel: (value?: string | null) => string;
  getAbilitySchemaIssues: (ability: Ability | null) => string[];
  describePricing: (pricing: AbilityPricing | null) => string;
}) {
  const actionItems = buildAbilityActionItems({
    healthSummary,
    abilities,
    templateSummaryByAbility,
    pricingByAbility,
    getAbilitySchemaIssues,
    describePricing,
  });
  const vendorModelById = new Map(vendorModels.map((item) => [Number(item.id), item]));
  const vendorGovernanceByProvider = new Map(
    (vendorGovernanceSummary?.providers || []).map((item) => [item.provider, item]),
  );
  const resolveVendorModelForAbility = (ability: Ability) => {
    const modelId = ability.vendor_model_id;
    if (modelId === undefined || modelId === null) return null;
    return vendorModelById.get(Number(modelId)) || null;
  };
  const resolveVendorRiskForAbility = (ability: Ability) => {
    const model = resolveVendorModelForAbility(ability);
    const provider = model?.provider || ability.provider;
    const governance = vendorGovernanceByProvider.get(provider);
    if (!model) return { theme: 'default' as const, text: '未绑定商业模型', detail: 'ComfyUI 或平台工具能力可以不绑定商业模型。' };
    if (!governance) return { theme: 'warning' as const, text: '缺厂商状态', detail: '模型已绑定，但还没有厂商健康数据。' };
    if ((governance.issues || []).length > 0) {
      return { theme: 'warning' as const, text: '厂商需检查', detail: (governance.suggestions || [])[0] || '请到模型弹药库查看密钥、出网或调用失败。' };
    }
    if (!governance.runtimeKeyConfigured) {
      return { theme: 'warning' as const, text: '缺可用密钥', detail: '请到模型弹药库配置密钥后再做真实调用。' };
    }
    return { theme: 'success' as const, text: '模型可用', detail: '模型目录和厂商状态当前没有明显阻塞。' };
  };
  const outputSummaryCounts = abilities.reduce(
    (acc, ability) => {
      const profile = resolveAbilityOutputProfile(ability);
      acc[profile.kind] = (acc[profile.kind] || 0) + 1;
      return acc;
    },
    {} as Record<string, number>,
  );

  return (
    <Card
      bordered
      title={
        <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
          <div>
            <Typography.Text strong>能力目录</Typography.Text>
            <div>
              <Typography.Text theme="secondary">先看健康、复测、表单和成本缺口，再进入单个能力测试或编辑。</Typography.Text>
            </div>
          </div>
          <Space>
            <Button variant="outline" loading={healthLoading} onClick={onRefreshHealth}>
              刷新健康
            </Button>
            <Button theme="primary" onClick={onCreate}>
              新增能力
            </Button>
          </Space>
        </Space>
      }
    >
      <Card bordered style={{ marginBottom: 12 }} title="能力接入顺序">
        <Row gutter={[12, 12]}>
          {[
            ['1', '先确认能力类型', '区分图片、视频、文字、图像理解，避免所有能力都塞进“生图”。'],
            ['2', '补齐业务表单', '字段名称、中文说明、默认值和错误提示要让非技术同学看得懂。'],
            ['3', '绑定模型或线路', '商业模型走模型弹药库，ComfyUI 能力走运行线路，不要让业务方理解底层节点。'],
            ['4', '测试后再发布', '能力测试通过、模板发布、成本口径确认后，再绑定到业务版本。'],
          ].map(([index, title, body]) => (
            <Col key={index} xs={12} md={3}>
              <div
                style={{
                  border: '1px solid var(--td-border-level-1-color)',
                  borderRadius: 12,
                  padding: 12,
                  height: '100%',
                }}
              >
                <Space direction="vertical" size={4}>
                  <Tag theme="primary" variant="light">
                    {index}
                  </Tag>
                  <Typography.Text strong>{title}</Typography.Text>
                  <Typography.Text theme="secondary">{body}</Typography.Text>
                </Space>
              </div>
            </Col>
          ))}
        </Row>
      </Card>

      <Card bordered style={{ marginBottom: 12 }} title="能力输出分布">
        <Row gutter={[12, 12]}>
          {[
            ['图片能力', outputSummaryCounts.image || 0, '生成、编辑、处理图片结果'],
            ['视频能力', outputSummaryCounts.video || 0, '生视频或视频处理结果'],
            ['文字能力', outputSummaryCounts.text || 0, '文字增强、文案生成等'],
            ['图像理解', outputSummaryCounts.structured || 0, 'VL 分析、标签、JSON 判断'],
          ].map(([label, value, detail]) => (
            <Col key={String(label)} xs={12} md={3}>
              <div
                style={{
                  border: '1px solid var(--td-border-level-1-color)',
                  borderRadius: 12,
                  padding: 12,
                  height: '100%',
                }}
              >
                <Space direction="vertical" size={4}>
                  <Typography.Text theme="secondary">{label}</Typography.Text>
                  <Typography.Title level="h3" style={{ margin: 0 }}>
                    {value}
                  </Typography.Title>
                  <Typography.Text theme="secondary">{detail}</Typography.Text>
                </Space>
              </div>
            </Col>
          ))}
        </Row>
      </Card>

      <Card bordered style={{ marginBottom: 12 }} title="能力和模型怎么对应">
        <Alert
          theme="info"
          message="商业模型先在“模型弹药库”维护密钥、出网和模型目录；能力目录只引用稳定后的模型。ComfyUI、平台工具这类本地/执行节点能力可以不绑定商业模型。"
        />
      </Card>

      <Card bordered style={{ marginBottom: 12 }} title="当前先处理什么">
        <Row gutter={[12, 12]}>
          {actionItems.map((item) => (
            <Col key={`${item.title}-${item.detail}`} xs={12} lg={actionItems.length === 1 ? 12 : 4}>
              <div
                style={{
                  border: '1px solid var(--td-border-level-1-color)',
                  borderRadius: 12,
                  padding: 12,
                  height: '100%',
                }}
              >
                <Space direction="vertical" size={4}>
                  <Tag theme={item.theme} variant="light">
                    {item.title}
                  </Tag>
                  <Typography.Text theme="secondary">{item.detail}</Typography.Text>
                  {item.filter ? (
                    <Button size="small" variant="text" onClick={() => onHealthFilterChange(item.filter as AbilityHealthFilter)}>
                      查看对应清单
                    </Button>
                  ) : null}
                </Space>
              </div>
            </Col>
          ))}
        </Row>
      </Card>

      {healthError ? (
        <div style={{ marginBottom: 12 }}>
          <Alert theme="error" message={healthError} />
        </div>
      ) : null}

      {healthSummary ? (
        <AbilityHealthPanel
          summary={healthSummary}
          filter={healthFilter}
          filteredItems={healthItems}
          exporting={healthExporting}
          onFilterChange={onHealthFilterChange}
          onExport={onExportHealth}
          getProviderLabel={getProviderLabel}
        />
      ) : null}

      <Row gutter={[12, 12]}>
        <Col span={4}>
          <Input value={search} onChange={(value) => onSearchChange(String(value))} placeholder="搜索名称/能力标识" />
        </Col>
        <Col span={4}>
          <Select
            value={providerFilter}
            onChange={(value) => onProviderFilterChange(String(value))}
            options={[
              { label: '全部厂商', value: 'all' },
              ...providerOptions.map((provider) => ({ label: getProviderLabel(provider), value: provider })),
            ]}
            placeholder="全部厂商"
          />
        </Col>
        <Col span={4}>
          <Select
            value={statusFilter}
            onChange={(value) => onStatusFilterChange(String(value))}
            options={[{ label: '全部状态', value: 'all' }, ...statusOptions]}
            placeholder="全部状态"
          />
        </Col>
      </Row>

      <div style={{ marginTop: 12 }}>
        <Table
          rowKey="id"
          size="small"
          data={abilities}
          columns={[
            {
              colKey: 'display_name',
              title: '名称',
              ellipsis: {
                props: { theme: 'light', placement: 'top' },
                content: ({ row }) => {
                  const issues = getAbilitySchemaIssues(row as Ability);
                  return (
                    <div className="max-w-[360px] text-xs text-slate-900 dark:text-slate-100">
                      <div className="font-semibold">{row.display_name}</div>
                      <div className="mt-1 text-slate-600 dark:text-slate-400">{row.description || '—'}</div>
                      {issues.length > 0 ? (
                        <div className="mt-2 flex flex-wrap gap-1">
                          {issues.map((issue) => (
                            <Tag key={`${row.id}-tooltip-${issue}`} theme="warning" variant="light" size="small">
                              {issue}
                            </Tag>
                          ))}
                        </div>
                      ) : null}
                    </div>
                  );
                },
              },
              cell: ({ row }) => {
                const issues = getAbilitySchemaIssues(row);
                const outputProfile = resolveAbilityOutputProfile(row);
                return (
                  <Space direction="vertical" size={2}>
                    <Typography.Text strong>{row.display_name}</Typography.Text>
                    <Typography.Text theme="secondary">{row.description || '—'}</Typography.Text>
                    <Space size="small" breakLine>
                      <Tag theme={outputProfile.theme} variant="light" size="small">
                        {outputProfile.label}
                      </Tag>
                      {outputProfile.outputTags.map((tag) => (
                        <Tag key={`${row.id}-output-${tag}`} theme="default" variant="light" size="small">
                          {tag}
                        </Tag>
                      ))}
                      {outputProfile.inputTags.map((tag) => (
                        <Tag key={`${row.id}-input-${tag}`} theme="primary" variant="outline" size="small">
                          {tag}
                        </Tag>
                      ))}
                    </Space>
                    {issues.length > 0 ? (
                      <Space size="small" breakLine>
                        {issues.map((issue) => (
                          <Tag key={`${row.id}-${issue}`} theme="warning" variant="light" size="small">
                            {issue}
                          </Tag>
                        ))}
                      </Space>
                    ) : null}
                  </Space>
                );
              },
            },
            {
              colKey: 'provider',
              title: '来源/分类',
              width: 260,
              cell: ({ row }) => (
                <Space direction="vertical" size={2}>
                  <Typography.Text>{getProviderLabel(row.provider)}</Typography.Text>
                  <Typography.Text theme="secondary">
                    {getCategoryLabel(row.category)} · {getAbilityTypeLabel(row.ability_type)}
                  </Typography.Text>
                  <Typography.Text theme="secondary">
                    能力标识：{row.capability_key}
                    {row.workflow_id ? ` · ${workflowsById[row.workflow_id]?.name || row.workflow_id}` : ''}
                  </Typography.Text>
                  {row.vendor_model_id ? (
                    <Space size={6} style={{ flexWrap: 'wrap' }}>
                      <Typography.Text theme="secondary">
                        模型：{resolveVendorModelForAbility(row)?.displayName || row.vendor_model_id}
                      </Typography.Text>
                      <Tag theme={resolveVendorRiskForAbility(row).theme} variant="light" size="small">
                        {resolveVendorRiskForAbility(row).text}
                      </Tag>
                    </Space>
                  ) : null}
                  {!row.vendor_model_id && row.provider !== 'comfyui' ? (
                    <Typography.Text theme="secondary">模型：未绑定商业模型</Typography.Text>
                  ) : null}
                  {row.version ? <Typography.Text theme="secondary">版本 {row.version}</Typography.Text> : null}
                </Space>
              ),
            },
            { colKey: 'status', title: '状态', width: 120, cell: ({ row }) => renderStatusTag(row.status) },
            {
              colKey: 'pricing',
              title: '成本',
              width: 180,
              cell: ({ row }) => {
                const pricing = pricingByAbility[row.id] || pricingByAbility[`${row.provider}:${row.capability_key}`] || null;
                const text = describePricing(pricing);
                return <Typography.Text theme="secondary">{text !== '—' ? text : '未设置'}</Typography.Text>;
              },
            },
            {
              colKey: 'executor',
              title: '运行方式',
              width: 220,
              cell: ({ row }) => {
                const bound = row.executor_id ? executors.find((executor) => executor.id === row.executor_id) : null;
                return (
                  <Typography.Text theme="secondary">
                    {bound ? `${bound.name} · ${bound.type}` : '自动选择可用线路'}
                  </Typography.Text>
                );
              },
            },
            {
              colKey: 'latest',
              title: '最近调用',
              width: 220,
              cell: ({ row }) => {
                const latestLog = latestLogByAbility[row.id];
                if (!latestLog) return <Typography.Text theme="secondary">—</Typography.Text>;
                const durationMs = resolveLogDurationMs(latestLog);
                const statusTag = getAbilityLogStatusTag(latestLog.status);
                return (
                  <Space direction="vertical" size={2}>
                    <Typography.Text theme="secondary">{formatDateTime(latestLog.created_at)}</Typography.Text>
                    <Space size="small">
                      <Tag theme={statusTag.theme} variant="light" size="small">
                        {statusTag.text}
                      </Tag>
                      {typeof durationMs === 'number' ? (
                        <Typography.Text theme="secondary">{durationMs}ms</Typography.Text>
                      ) : null}
                    </Space>
                  </Space>
                );
              },
            },
            {
              colKey: 'template',
              title: '发布模板',
              width: 240,
              cell: ({ row }) => {
                const summary = templateSummaryByAbility[row.id];
                if (!summary || (summary.historyCount === 0 && !summary.currentId)) {
                  return <Typography.Text theme="secondary">未发布</Typography.Text>;
                }
                const label = summary.latestLabel || summary.currentId || '已发布';
                return (
                  <Space direction="vertical" size={2}>
                    <Space align="center" size={4}>
                      <Tag theme={summary.currentId ? 'success' : 'warning'} variant="light" size="small">
                        {summary.currentId ? '已发布' : '有历史'}
                      </Tag>
                      <Typography.Text theme="secondary">{label}</Typography.Text>
                    </Space>
                    <Typography.Text theme="secondary">
                      历史 {summary.historyCount} 条
                      {summary.latestAt ? ` · ${formatDateTime(summary.latestAt)}` : ''}
                    </Typography.Text>
                  </Space>
                );
              },
            },
            {
              colKey: 'actions',
              title: '操作',
              width: 240,
              cell: ({ row }) => (
                <Space size="small">
                  <Button
                    size="small"
                    variant="text"
                    onClick={(event) => {
                      event?.stopPropagation?.();
                      onOpenTemplate(row);
                    }}
                  >
                    模板
                  </Button>
                  <Button
                    size="small"
                    variant="text"
                    onClick={(event) => {
                      event?.stopPropagation?.();
                      onEdit(row);
                    }}
                  >
                    编辑
                  </Button>
                  <Button
                    size="small"
                    variant="text"
                    theme="danger"
                    onClick={(event) => {
                      event?.stopPropagation?.();
                      onDelete(row.id);
                    }}
                  >
                    删除
                  </Button>
                </Space>
              ),
            },
          ]}
          onRowClick={({ row }) => onSelectAbility((row as Ability).id)}
          rowClassName={({ row }) => (((row as Ability).id === selectedAbilityId ? 'podi-row-selected' : ''))}
          empty={<Typography.Text theme="secondary">暂无满足筛选条件的能力。</Typography.Text>}
        />
      </div>
    </Card>
  );
}
