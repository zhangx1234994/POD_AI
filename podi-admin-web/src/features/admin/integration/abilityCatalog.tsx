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
import { GuidanceQueueCard, OperationFlowCard, type GuidanceQueueItem } from '../shared/ui';
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

type AbilityVendorRisk = {
  theme: 'success' | 'warning' | 'danger' | 'default';
  text: string;
  detail: string;
};

type AbilityReadinessItem = {
  ability: Ability;
  action: string;
  issues: string[];
  outputLabel: string;
  readiness: 'ready' | 'blocked' | 'attention';
  readinessText: string;
  theme: 'success' | 'warning' | 'danger';
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
  const unclearOutputCount = abilities.filter((item) => resolveAbilityOutputProfile(item).kind === 'asset').length;
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
  if (unclearOutputCount > 0) {
    items.push({
      theme: 'warning',
      title: '输出类型待补',
      detail: `${unclearOutputCount} 个能力还没有明确是图片、视频、文字还是图像理解，后续接入业务前要补齐。`,
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

const buildAbilityReadiness = ({
  abilities,
  healthItems,
  templateSummaryByAbility,
  pricingByAbility,
  getAbilitySchemaIssues,
  describePricing,
  resolveVendorRiskForAbility,
}: {
  abilities: Ability[];
  healthItems: AbilityHealthSummaryItem[];
  templateSummaryByAbility: Record<string, AbilityTemplateSummary>;
  pricingByAbility: Record<string, AbilityPricing>;
  getAbilitySchemaIssues: (ability: Ability | null) => string[];
  describePricing: (pricing: AbilityPricing | null) => string;
  resolveVendorRiskForAbility: (ability: Ability) => AbilityVendorRisk;
}) => {
  const healthByAbility = new Map(healthItems.map((item) => [item.abilityId, item]));

  const items: AbilityReadinessItem[] = abilities.map((ability) => {
    const issues: string[] = [];
    const health = healthByAbility.get(ability.id);
    const templateSummary = templateSummaryByAbility[ability.id];
    const pricing = pricingByAbility[ability.id] || pricingByAbility[`${ability.provider}:${ability.capability_key}`] || null;
    const schemaIssues = getAbilitySchemaIssues(ability);
    const outputProfile = resolveAbilityOutputProfile(ability);
    const vendorRisk = resolveVendorRiskForAbility(ability);

    if (ability.status !== 'active') issues.push('未启用');
    if (health?.healthStatus === 'failed') issues.push('最近测试失败');
    if (health?.healthStatus === 'degraded') issues.push('成功率下降');
    if (health?.needsTest) issues.push('需要复测');
    if (health?.stale) issues.push('测试过期');
    if (schemaIssues.length > 0) issues.push('表单说明不完整');
    if (!templateSummary?.currentId) issues.push('模板未发布');
    if (describePricing(pricing) === '—') issues.push('缺成本口径');
    if (vendorRisk.theme === 'warning' || vendorRisk.theme === 'danger') issues.push(vendorRisk.text);

    let action = '可进入业务版本配置';
    if (issues.includes('最近测试失败')) action = '先复测或修运行线路';
    else if (issues.includes('成功率下降') || issues.includes('需要复测') || issues.includes('测试过期')) action = '先补一次能力复测';
    else if (issues.includes('表单说明不完整')) action = '先补字段说明和默认值';
    else if (issues.includes('模板未发布')) action = '先发布能力模板';
    else if (issues.includes('缺成本口径')) action = '先补成本和计价口径';
    else if (vendorRisk.theme === 'warning' || vendorRisk.theme === 'danger') action = '先到模型弹药库处理';
    else if (issues.includes('未启用')) action = '确认是否启用或归档';

    const readiness = issues.length === 0 ? 'ready' : issues.some((issue) => ['最近测试失败', '未启用'].includes(issue)) ? 'blocked' : 'attention';
    return {
      ability,
      action,
      issues,
      outputLabel: outputProfile.label,
      readiness,
      readinessText: readiness === 'ready' ? '可接业务' : readiness === 'blocked' ? '暂不能接' : '需处理',
      theme: readiness === 'ready' ? 'success' : readiness === 'blocked' ? 'danger' : 'warning',
    };
  });

  const readyCount = items.filter((item) => item.readiness === 'ready').length;
  const blockedCount = items.filter((item) => item.readiness === 'blocked').length;
  const attentionCount = items.filter((item) => item.readiness === 'attention').length;
  const noEvidenceCount = items.filter((item) => item.issues.includes('需要复测') || item.issues.includes('测试过期')).length;
  const contractIssueCount = items.filter(
    (item) => item.issues.includes('表单说明不完整') || item.issues.includes('模板未发布') || item.issues.includes('缺成本口径'),
  ).length;

  return {
    items,
    priorityItems: items
      .filter((item) => item.readiness !== 'ready')
      .sort((a, b) => {
        const weight = { blocked: 0, attention: 1, ready: 2 };
        return weight[a.readiness] - weight[b.readiness] || b.issues.length - a.issues.length;
      })
      .slice(0, 8),
    summary: {
      readyCount,
      blockedCount,
      attentionCount,
      noEvidenceCount,
      contractIssueCount,
    },
  };
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
  const guidanceItems: GuidanceQueueItem[] = actionItems.map((item) => ({
    key: `${item.title}-${item.detail}`,
    theme: item.theme,
    title: item.title,
    detail: item.detail,
    action: item.filter ? '查看对应清单' : undefined,
    onClick: item.filter ? () => onHealthFilterChange(item.filter as AbilityHealthFilter) : undefined,
  }));
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
  const readiness = buildAbilityReadiness({
    abilities,
    healthItems,
    templateSummaryByAbility,
    pricingByAbility,
    getAbilitySchemaIssues,
    describePricing,
    resolveVendorRiskForAbility,
  });
  const outputSummaryCounts = abilities.reduce(
    (acc, ability) => {
      const profile = resolveAbilityOutputProfile(ability);
      acc[profile.kind] = (acc[profile.kind] || 0) + 1;
      return acc;
    },
    {} as Record<string, number>,
  );
  const categorySummary = Array.from(
    readiness.items
      .reduce((map, item) => {
        const key = item.ability.category || 'other';
        const current = map.get(key) || {
          key,
          label: getCategoryLabel(key),
          total: 0,
          ready: 0,
          blocked: 0,
          attention: 0,
          sampleNames: [] as string[],
        };
        current.total += 1;
        if (item.readiness === 'ready') current.ready += 1;
        if (item.readiness === 'blocked') current.blocked += 1;
        if (item.readiness === 'attention') current.attention += 1;
        if (current.sampleNames.length < 3) current.sampleNames.push(item.ability.display_name);
        map.set(key, current);
        return map;
      }, new Map<string, { key: string; label: string; total: number; ready: number; blocked: number; attention: number; sampleNames: string[] }>())
      .values(),
  ).sort((a, b) => b.total - a.total || a.label.localeCompare(b.label, 'zh-Hans-CN'));

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
      <OperationFlowCard
        title="能力接入闭环"
        description="先确认能力面向什么业务，再补表单、绑定线路、跑测试，最后才允许进入业务版本。"
        summary="能力目录不是底层配置仓库。每个能力都必须能回答：谁用、怎么填、走哪条线路、测试证据在哪里。"
        summaryTheme="primary"
        style={{ marginBottom: 12 }}
        steps={[
          {
            key: 'classify-output',
            title: '先确认能力类型',
            detail: '区分图片、视频、文字、图像理解和资源输出。',
            action: '避免所有能力都塞进“生图”，后续日志、测评和计费都按类型处理。',
            done: '类型清楚',
            theme: 'primary',
          },
          {
            key: 'complete-form',
            title: '补齐业务表单',
            detail: '字段名称、中文说明、默认值和错误提示要让非技术同学看得懂。',
            action: '先补 schema 和模板，再让 Coze、测评端或业务 API 使用。',
            done: '表单可用',
            theme: 'warning',
          },
          {
            key: 'bind-route',
            title: '绑定模型或线路',
            detail: '商业模型走模型弹药库，ComfyUI 能力走运行线路。',
            action: '不要把执行器、模型编号、节点名暴露成普通用户主动作。',
            done: '线路明确',
            theme: 'primary',
          },
          {
            key: 'test-and-release',
            title: '测试后再发布',
            detail: '能力测试通过、模板发布、成本口径确认后，再绑定到业务版本。',
            action: '把测试证据沉淀到调用日志和业务上线证据里。',
            done: '证据完整',
            theme: 'success',
          },
        ]}
      />

      <Card bordered style={{ marginBottom: 12 }} title="能力输出分布">
        <Row gutter={[12, 12]}>
          {[
            ['图片能力', outputSummaryCounts.image || 0, '生成、编辑、处理图片结果'],
            ['视频能力', outputSummaryCounts.video || 0, '生视频或视频处理结果'],
            ['文字能力', outputSummaryCounts.text || 0, '文字增强、文案生成等'],
            ['图像理解', outputSummaryCounts.structured || 0, '看图分析、标签、结构化判断'],
            ['资源能力', outputSummaryCounts.asset || 0, '文件、链接或未归类输出'],
          ].map(([label, value, detail]) => (
            <Col key={String(label)} xs={12} md={4} lg={2}>
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

      <Card bordered style={{ marginBottom: 12 }} title="按业务分类看能力">
        <Typography.Text theme="secondary">
          这里用于确认能力是否已经按业务意图归口。带“旧分类”或“待归类”的能力，后续要迁到花纹提取、图裂变、扩图等明确分类。
        </Typography.Text>
        <Row gutter={[12, 12]} style={{ marginTop: 12 }}>
          {categorySummary.map((item) => {
            const theme = item.blocked > 0 ? 'danger' : item.attention > 0 ? 'warning' : 'success';
            return (
              <Col key={item.key} xs={12} md={4} lg={3}>
                <div
                  style={{
                    border: '1px solid var(--td-border-level-1-color)',
                    borderRadius: 12,
                    padding: 12,
                    height: '100%',
                  }}
                >
                  <Space direction="vertical" size={6} style={{ width: '100%' }}>
                    <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
                      <Typography.Text strong>{item.label}</Typography.Text>
                      <Tag theme={theme} variant="light">
                        {item.total}
                      </Tag>
                    </Space>
                    <Typography.Text theme="secondary">
                      可接 {item.ready} · 需处理 {item.attention} · 暂不能接 {item.blocked}
                    </Typography.Text>
                    <Typography.Text theme="secondary">
                      {item.sampleNames.length > 0 ? item.sampleNames.join('、') : '暂无能力'}
                    </Typography.Text>
                  </Space>
                </div>
              </Col>
            );
          })}
        </Row>
      </Card>

      <Card bordered style={{ marginBottom: 12 }} title="能力上线总览">
        <Typography.Text theme="secondary">
          这里先回答“哪些能力可以接业务，哪些能力必须先处理”。底层执行器、工作流、模型编号只作为详情排障信息。
        </Typography.Text>
        <Row gutter={[12, 12]} style={{ marginTop: 12 }}>
          {[
            ['可接业务', readiness.summary.readyCount, '健康、模板、表单、成本和模型状态都没有明显阻塞', 'success'],
            ['暂不能接', readiness.summary.blockedCount, '能力未启用或最近测试失败，不能绑定到主业务默认版本', 'danger'],
            ['需处理', readiness.summary.attentionCount, '复测、成本、模板、表单或模型状态仍需补齐', 'warning'],
            ['缺证据', readiness.summary.noEvidenceCount, '最近复测缺失或过期，发版前需要重新跑样例', 'warning'],
            ['契约缺口', readiness.summary.contractIssueCount, '表单、模板、成本不完整，会影响业务方或 Coze 使用', 'warning'],
          ].map(([label, value, detail, theme]) => (
            <Col key={String(label)} xs={12} md={4} lg={2}>
              <div
                style={{
                  border: '1px solid var(--td-border-level-1-color)',
                  borderRadius: 12,
                  padding: 12,
                  height: '100%',
                }}
              >
                <Space direction="vertical" size={4}>
                  <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
                    <Typography.Text theme="secondary">{label}</Typography.Text>
                    <Tag theme={theme as 'success' | 'warning' | 'danger'} variant="light">
                      {value}
                    </Tag>
                  </Space>
                  <Typography.Text theme="secondary">{detail}</Typography.Text>
                </Space>
              </div>
            </Col>
          ))}
        </Row>

        <div style={{ marginTop: 12 }}>
          <Table
            size="small"
            rowKey="id"
            data={readiness.priorityItems.map((item) => ({ ...item, id: item.ability.id }))}
            columns={[
              {
                colKey: 'ability',
                title: '优先处理能力',
                minWidth: 240,
                cell: ({ row }) => (
                  <Space direction="vertical" size={2}>
                    <Typography.Text strong>{row.ability.display_name}</Typography.Text>
                    <Typography.Text theme="secondary">{row.outputLabel}</Typography.Text>
                  </Space>
                ),
              },
              {
                colKey: 'readiness',
                title: '判断',
                width: 120,
                cell: ({ row }) => (
                  <Tag theme={row.theme} variant="light">
                    {row.readinessText}
                  </Tag>
                ),
              },
              {
                colKey: 'issues',
                title: '原因',
                minWidth: 260,
                cell: ({ row }) => (
                  <Space size="small" breakLine>
                    {row.issues.slice(0, 4).map((issue: string) => (
                      <Tag key={`${row.id}-${issue}`} theme={row.theme} variant="light" size="small">
                        {issue}
                      </Tag>
                    ))}
                    {row.issues.length > 4 ? (
                      <Tag theme="default" variant="light" size="small">
                        +{row.issues.length - 4}
                      </Tag>
                    ) : null}
                  </Space>
                ),
              },
              {
                colKey: 'action',
                title: '下一步',
                minWidth: 220,
                cell: ({ row }) => <Typography.Text>{row.action}</Typography.Text>,
              },
            ]}
            empty={<Typography.Text theme="secondary">当前没有需要优先处理的能力。</Typography.Text>}
          />
        </div>
      </Card>

      <Card bordered style={{ marginBottom: 12 }} title="能力和模型怎么对应">
        <Alert
          theme="info"
          message="商业模型先在“模型弹药库”维护密钥、出网和模型目录；能力目录只引用稳定后的模型。ComfyUI、平台工具这类本地/执行节点能力可以不绑定商业模型。"
        />
      </Card>

      <GuidanceQueueCard items={guidanceItems} maxItems={6} style={{ marginBottom: 12 }} />

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
                    <Typography.Text theme="secondary">{outputProfile.detail}</Typography.Text>
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
              title: '业务分类',
              width: 260,
              cell: ({ row }) => {
                const vendorRisk = resolveVendorRiskForAbility(row);
                return (
                  <Space direction="vertical" size={2}>
                    <Typography.Text>{getCategoryLabel(row.category)}</Typography.Text>
                    <Typography.Text theme="secondary">{getAbilityTypeLabel(row.ability_type)}</Typography.Text>
                    <Space size={6} breakLine>
                      <Tag variant="light" size="small">
                        {getProviderLabel(row.provider)}
                      </Tag>
                      <Tag theme={vendorRisk.theme} variant="light" size="small">
                        {vendorRisk.text}
                      </Tag>
                      {row.version ? (
                        <Tag variant="light" size="small">
                          {row.version}
                        </Tag>
                      ) : null}
                    </Space>
                  </Space>
                );
              },
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
              title: '底层信息',
              width: 220,
              cell: ({ row }) => {
                const bound = row.executor_id ? executors.find((executor) => executor.id === row.executor_id) : null;
                const model = resolveVendorModelForAbility(row);
                const workflow = row.workflow_id ? workflowsById[row.workflow_id] : null;
                return (
                  <details className="podi-ability-technical-details">
                    <summary>查看底层</summary>
                    <div className="podi-ability-technical-details__body">
                      <Typography.Text theme="secondary">能力标识：{row.capability_key}</Typography.Text>
                      <Typography.Text theme="secondary">
                        运行线路：{bound ? `${bound.name} · ${bound.type}` : '自动选择可用线路'}
                      </Typography.Text>
                      {workflow ? (
                        <Typography.Text theme="secondary">工作流：{workflow.name || row.workflow_id}</Typography.Text>
                      ) : row.workflow_id ? (
                        <Typography.Text theme="secondary">工作流：{row.workflow_id}</Typography.Text>
                      ) : null}
                      {row.vendor_model_id ? (
                        <Typography.Text theme="secondary">模型：{model?.displayName || row.vendor_model_id}</Typography.Text>
                      ) : null}
                    </div>
                  </details>
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
