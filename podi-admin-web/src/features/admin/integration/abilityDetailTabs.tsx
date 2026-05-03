import { useState } from 'react';
import { Alert, Button, Card, Col, Input, Row, Select, Space, Tag, Textarea, Typography } from 'tdesign-react';
import type { Ability, AbilityTemplateStateResponse, AbilityTemplateValidateResponse } from '../../../types/admin';
import { StatusBadge } from '../shared/ui';
import { resolveAbilityOutputProfile } from './abilityOutputProfile';
import { formatDateTime } from './formatters';

type AbilityHealthView = {
  status: string;
  checkedAt: string;
  successRateText: string;
};

const formatJsonValue = (value?: unknown) => (value ? JSON.stringify(value, null, 2) : '');

function InfoCard({ title, items }: { title: string; items: { label: string; value: string }[] }) {
  return (
    <Card title={title} bordered>
      <Space direction="vertical" size="small" style={{ width: '100%' }}>
        {items.map((item) => (
          <Row key={item.label} gutter={12} align="middle">
            <Col span={10}>
              <Typography.Text theme="secondary">{item.label}</Typography.Text>
            </Col>
            <Col span={14}>
              <Typography.Text>{item.value || '—'}</Typography.Text>
            </Col>
          </Row>
        ))}
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

export function AbilityOverviewTab({
  selectedAbility,
  schemaIssues,
  tags,
  defaultExecutorLabel,
  workflowLabel,
  pricingText,
  health,
  getProviderLabel,
  getCategoryLabel,
  getAbilityTypeLabel,
}: {
  selectedAbility?: Ability | null;
  schemaIssues: string[];
  tags: string[];
  defaultExecutorLabel: string;
  workflowLabel: string;
  pricingText: string;
  health: AbilityHealthView;
  getProviderLabel: (value: string) => string;
  getCategoryLabel: (value: string) => string;
  getAbilityTypeLabel: (value?: string | null) => string;
}) {
  if (!selectedAbility) {
    return (
      <Alert
        theme="info"
        message="请先在左侧“能力目录”中选中一条能力，系统会在此处展示能力描述、默认节点、成本与标签。"
      />
    );
  }

  const outputProfile = resolveAbilityOutputProfile(selectedAbility);
  const baseItems = [
    { label: '能力标识', value: selectedAbility.capability_key || '—' },
    { label: '版本', value: selectedAbility.version || 'v1' },
    { label: '能力类型', value: getAbilityTypeLabel(selectedAbility.ability_type) || '—' },
    { label: '输出类型', value: outputProfile.label },
    { label: '默认节点', value: defaultExecutorLabel || '按厂商类型自动匹配' },
    { label: '关联工作流', value: workflowLabel || '未绑定' },
  ];

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      {schemaIssues.length > 0 ? (
        <Alert theme="warning" title="能力配置不完整" message={`请补齐：${schemaIssues.join(' / ')}`} />
      ) : null}
      <Card bordered>
        <Space align="start" style={{ justifyContent: 'space-between', width: '100%' }}>
          <Space direction="vertical" size={2}>
            <Typography.Text theme="secondary">
              {getProviderLabel(selectedAbility.provider)} · {getCategoryLabel(selectedAbility.category)}
            </Typography.Text>
            <Typography.Title level="h4" style={{ margin: 0 }}>
              {selectedAbility.display_name}
            </Typography.Title>
            <Typography.Text theme="secondary">
              {selectedAbility.description || '暂无描述，建议在能力管理中补充。'}
            </Typography.Text>
            <Space breakLine>
              <Tag theme={outputProfile.theme} variant="light">
                {outputProfile.label}
              </Tag>
              {[...outputProfile.outputTags, ...outputProfile.inputTags].map((tag) => (
                <Tag key={`selected-ability-profile-${tag}`} theme="primary" variant="outline">
                  {tag}
                </Tag>
              ))}
              {tags.map((tag, index) => (
                <Tag key={`selected-ability-tag-${index}`} theme="primary" variant="light">
                  {tag}
                </Tag>
              ))}
            </Space>
          </Space>
          <StatusBadge status={selectedAbility.status} />
        </Space>
      </Card>

      <Row gutter={[12, 12]}>
        <Col xs={24} md={12}>
          <InfoCard title="基础信息" items={baseItems} />
        </Col>
        <Col xs={24} md={12}>
          <Card bordered title="计价信息">
            <Space direction="vertical" size="small">
              <Typography.Text>{pricingText}</Typography.Text>
              {pricingText === '—' ? (
                <Typography.Text theme="secondary">
                  可在能力高级配置中设置币种、计费单位和价格；ComfyUI 默认按 ¥0.30 / 每张计算。
                </Typography.Text>
              ) : null}
            </Space>
          </Card>
        </Col>
      </Row>

      <Row gutter={[12, 12]}>
        <Col xs={24} md={12}>
          <InfoCard
            title="健康巡检"
            items={[
              { label: '状态', value: health.status },
              { label: '最近巡检', value: health.checkedAt },
            ]}
          />
        </Col>
        <Col xs={24} md={12}>
          <InfoCard
            title="成功率（近 24h）"
            items={[
              { label: '成功率', value: health.successRateText },
              { label: '来源', value: '能力调用记录' },
            ]}
          />
        </Col>
      </Row>
    </Space>
  );
}

export function AbilityParamsTab({
  selectedAbility,
  schemaIssues,
}: {
  selectedAbility?: Ability | null;
  schemaIssues: string[];
}) {
  if (!selectedAbility) {
    return (
      <div className="rounded-2xl border border-dashed border-slate-700 bg-slate-950/30 p-4 text-sm text-slate-400">
        请在能力目录中选择一个能力后查看默认参数与输入表单。
      </div>
    );
  }
  const showParamIssues = schemaIssues.filter((issue) => ['缺少输入表单配置', '缺少默认参数'].includes(issue));
  return (
    <div className="space-y-4 text-xs text-slate-400">
      {showParamIssues.length > 0 ? (
        <Alert theme="warning" title="参数配置提醒" message={`尚未补齐：${showParamIssues.join(' / ')}`} />
      ) : null}
      <div>
        <div className="text-slate-500">默认参数</div>
        {selectedAbility.default_params ? (
          <CodeBlock value={formatJsonValue(selectedAbility.default_params)} maxHeight={260} />
        ) : (
          <p className="mt-1">未配置，测试时可以在实时测试的高级参数中补充。</p>
        )}
      </div>
      <div>
        <div className="text-slate-500">输入表单配置</div>
        {selectedAbility.input_schema ? (
          <CodeBlock value={formatJsonValue(selectedAbility.input_schema)} maxHeight={260} />
        ) : (
          <p className="mt-1">尚未提供输入表单配置，页面将只保留高级参数区。</p>
        )}
      </div>
    </div>
  );
}

export function AbilityMetadataTab({
  selectedAbility,
  schemaIssues,
  workflowLabel,
  pricingText,
  health,
  templateState,
  templateLoading,
  templateActionLoading,
  templateVersionLabel,
  templateRollbackId,
  templateNotes,
  templateError,
  templateValidateResult,
  onRefreshTemplate,
  onValidateTemplate,
  onPublishTemplate,
  onRollbackTemplate,
  onTemplateVersionLabelChange,
  onTemplateRollbackIdChange,
  onTemplateNotesChange,
  getAbilityTypeLabel,
}: {
  selectedAbility?: Ability | null;
  schemaIssues: string[];
  workflowLabel: string;
  pricingText: string;
  health: AbilityHealthView;
  templateState?: AbilityTemplateStateResponse | null;
  templateLoading: boolean;
  templateActionLoading: boolean;
  templateVersionLabel: string;
  templateRollbackId: string;
  templateNotes: string;
  templateError?: string | null;
  templateValidateResult?: AbilityTemplateValidateResponse | null;
  onRefreshTemplate: (abilityId: string) => void;
  onValidateTemplate: () => void;
  onPublishTemplate: () => void;
  onRollbackTemplate: () => void;
  onTemplateVersionLabelChange: (value: string) => void;
  onTemplateRollbackIdChange: (value: string) => void;
  onTemplateNotesChange: (value: string) => void;
  getAbilityTypeLabel: (value?: string | null) => string;
}) {
  if (!selectedAbility) {
    return (
      <div className="rounded-2xl border border-dashed border-slate-700 bg-slate-950/30 p-4 text-sm text-slate-400">
        请选择能力以查看高级配置、工作流标识、计价规则等信息。
      </div>
    );
  }
  const showMetadataIssues = schemaIssues.filter((issue) => ['缺少高级配置', '缺少计价'].includes(issue));
  const history = templateState?.history || [];
  return (
    <div className="space-y-4 text-xs text-slate-400">
      {showMetadataIssues.length > 0 ? (
        <Alert
          theme="warning"
          title="高级配置缺失"
          message={`尚未补齐：${showMetadataIssues.join(' / ')}。建议补充调用类型、计价规则、运行要求等字段。`}
        />
      ) : null}
      <div>
        <div className="text-slate-500">能力高级配置</div>
        {selectedAbility.metadata ? (
          <CodeBlock value={formatJsonValue(selectedAbility.metadata)} maxHeight={320} />
        ) : (
          <p className="mt-1">暂无高级配置，建议补充工作流标识、调用类型、计价规则、运行要求等信息。</p>
        )}
      </div>
      <Card bordered title="能力模板版本">
        <Space direction="vertical" size="small" style={{ width: '100%' }}>
          <Typography.Text theme="secondary">
            模板用于固化当前能力参数与元信息，支持校验、发布与回滚。
          </Typography.Text>
          <Space align="center" size="small">
            <Button
              size="small"
              variant="outline"
              loading={templateLoading}
              onClick={() => onRefreshTemplate(selectedAbility.id)}
            >
              刷新
            </Button>
            <Button size="small" variant="outline" loading={templateActionLoading} onClick={onValidateTemplate}>
              校验模板
            </Button>
            <Button size="small" theme="primary" loading={templateActionLoading} onClick={onPublishTemplate}>
              发布模板
            </Button>
          </Space>
          <Row gutter={[12, 12]}>
            <Col span={12}>
              <Typography.Text theme="secondary">版本标签（选填）</Typography.Text>
              <Input
                value={templateVersionLabel}
                onChange={(value) => onTemplateVersionLabelChange(String(value))}
                placeholder="例如：2026-02-26-kie-v2"
              />
            </Col>
            <Col span={12}>
              <Typography.Text theme="secondary">
                当前版本：{templateState?.current_template_id || '未发布'}
              </Typography.Text>
              <Select
                value={templateRollbackId}
                onChange={(value) => onTemplateRollbackIdChange(String(value))}
                options={[
                  { label: '请选择要回滚的版本', value: '' },
                  ...history.map((item) => ({
                    label: `${item.version_label || item.id} · ${item.action} · ${formatDateTime(item.created_at)}`,
                    value: item.id,
                  })),
                ]}
              />
            </Col>
          </Row>
          <div>
            <Typography.Text theme="secondary">说明（发布/回滚备注）</Typography.Text>
            <Textarea
              value={templateNotes}
              onChange={(value) => onTemplateNotesChange(String(value))}
              autosize={{ minRows: 2, maxRows: 4 }}
              placeholder="例如：补齐 image_urls 规则 + 更新默认参数"
            />
          </div>
          <Space align="center" size="small">
            <Button
              size="small"
              variant="outline"
              theme="warning"
              loading={templateActionLoading}
              disabled={!templateRollbackId}
              onClick={onRollbackTemplate}
            >
              回滚到所选版本
            </Button>
          </Space>
          {templateError ? <Alert theme="error" message={templateError} /> : null}
          {templateValidateResult ? (
            <Alert
              theme={templateValidateResult.ok ? 'success' : 'warning'}
              title={templateValidateResult.ok ? '模板校验通过' : '模板校验未通过'}
              message={[
                templateValidateResult.errors.length > 0
                  ? `错误：${templateValidateResult.errors.join('；')}`
                  : '错误：无',
                templateValidateResult.warnings.length > 0
                  ? `提醒：${templateValidateResult.warnings.join('；')}`
                  : '提醒：无',
              ].join(' ｜ ')}
            />
          ) : null}
          <div className="max-h-[240px] overflow-auto rounded-2xl border border-slate-200/70 dark:border-slate-800">
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-slate-50 text-[11px] text-slate-600 dark:bg-slate-900/80 dark:text-slate-400">
                <tr className="text-left">
                  <th className="px-3 py-2">模板编号</th>
                  <th className="px-3 py-2">标签</th>
                  <th className="px-3 py-2">动作</th>
                  <th className="px-3 py-2">时间</th>
                  <th className="px-3 py-2">备注</th>
                </tr>
              </thead>
              <tbody>
                {history.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-4 py-6 text-center text-slate-500">
                      {templateLoading ? '加载中…' : '暂无模板历史'}
                    </td>
                  </tr>
                ) : (
                  history.map((item) => (
                    <tr key={`ability-template-${item.id}`} className="border-t border-slate-100 dark:border-slate-800">
                      <td className="px-3 py-2 text-slate-700 dark:text-slate-300">{item.id}</td>
                      <td className="px-3 py-2 text-slate-700 dark:text-slate-300">{item.version_label || '—'}</td>
                      <td className="px-3 py-2 text-slate-700 dark:text-slate-300">{item.action}</td>
                      <td className="px-3 py-2 text-slate-600 dark:text-slate-400">{formatDateTime(item.created_at)}</td>
                      <td className="px-3 py-2 text-slate-600 dark:text-slate-400">{item.notes || '—'}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </Space>
      </Card>
      <div className="rounded-2xl border border-slate-800 bg-slate-950/40 p-4 text-[11px] text-slate-400 space-y-1">
        <div className="text-[11px] uppercase tracking-widest text-slate-500">调度与成本要点</div>
        <p>能力类型：{getAbilityTypeLabel(selectedAbility.ability_type)}</p>
        <p>关联工作流：{workflowLabel || '未绑定'}</p>
        <p>最近健康检查：{health.checkedAt}</p>
        <p>成功率：{health.successRateText}</p>
        <p>计价：{pricingText}</p>
      </div>
    </div>
  );
}
