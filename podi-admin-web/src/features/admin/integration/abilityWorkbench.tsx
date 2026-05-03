import type { ReactNode } from 'react';
import { Alert, Button, Card, Select, Space, Tabs, Tag, Typography } from 'tdesign-react';
import type { Ability } from '../../../types/admin';
import { resolveAbilityOutputProfile } from './abilityOutputProfile';

type AbilityTab = {
  id: string;
  label: string;
};

export function AbilityWorkbenchPanel({
  abilities,
  selectedAbility,
  selectedAbilityId,
  activeTab,
  tabs,
  onSelectAbility,
  onSelectAbilitiesSection,
  onTabChange,
  renderContent,
  getProviderLabel,
}: {
  abilities: Ability[];
  selectedAbility?: Ability | null;
  selectedAbilityId?: string | null;
  activeTab: string;
  tabs: readonly AbilityTab[];
  onSelectAbility: (id: string | null) => void;
  onSelectAbilitiesSection: () => void;
  onTabChange: (tab: string) => void;
  renderContent: (tab: string) => ReactNode;
  getProviderLabel: (provider: string) => string;
}) {
  const selectedOutputProfile = selectedAbility ? resolveAbilityOutputProfile(selectedAbility) : null;
  if (abilities.length === 0) {
    return (
      <Alert
        theme="warning"
        title="暂无可用能力"
        message="请先在能力列表新增并激活能力（例如：百度 · 无损放大），再执行详情测试。"
      />
    );
  }

  return (
    <Card bordered title="能力详情与链路自检">
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        <Space align="start" style={{ justifyContent: 'space-between', width: '100%' }}>
          <Typography.Text theme="secondary">
            选择能力后，可查看概览、参数、关键配置，并直接运行测试或查看调用记录。
          </Typography.Text>
          {selectedAbility ? (
            <Space direction="vertical" size={2} style={{ textAlign: 'right' }}>
              <Typography.Text theme="secondary">能力编号：{selectedAbility.id}</Typography.Text>
              <Typography.Text theme="secondary">能力标识：{selectedAbility.capability_key}</Typography.Text>
              {selectedOutputProfile ? (
                <Space size={4} style={{ justifyContent: 'flex-end', flexWrap: 'wrap' }}>
                  <Tag theme={selectedOutputProfile.theme} variant="light" size="small">
                    {selectedOutputProfile.label}
                  </Tag>
                  {[...selectedOutputProfile.outputTags, ...selectedOutputProfile.inputTags].slice(0, 4).map((tag) => (
                    <Tag key={`selected-ability-profile-${tag}`} variant="light" size="small">
                      {tag}
                    </Tag>
                  ))}
                </Space>
              ) : null}
            </Space>
          ) : null}
        </Space>

        <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
          <div style={{ width: 'min(100%, 420px)' }}>
            <Select
              value={selectedAbilityId ?? ''}
              onChange={(value) => onSelectAbility(String(value) || null)}
              options={[
                { label: '请选择（或在能力管理中新建）', value: '' },
                ...abilities.map((ability) => {
                  const profile = resolveAbilityOutputProfile(ability);
                  return {
                    label: `${ability.display_name} · ${profile.label} · ${getProviderLabel(ability.provider)}`,
                    value: ability.id,
                  };
                }),
              ]}
              placeholder="快速选择能力"
            />
          </div>
          <Button variant="outline" onClick={onSelectAbilitiesSection}>
            前往能力管理
          </Button>
        </Space>

        {!selectedAbility ? (
          <Alert theme="info" message="暂未选择能力，请先在下拉框选择，或回到“能力管理”点击一行。" />
        ) : (
          <Tabs
            theme="card"
            value={activeTab}
            onChange={(value) => onTabChange(String(value))}
            list={tabs.map((tab) => ({
              value: tab.id,
              label: tab.label,
              panel: <div style={{ paddingTop: 12 }}>{renderContent(tab.id)}</div>,
            }))}
          />
        )}
      </Space>
    </Card>
  );
}
