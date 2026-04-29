import { Alert, Button, Select, Space, Switch, Tag, Typography } from 'tdesign-react';

type ComfyuiTabMeta = {
  label: string;
  group: string;
};

type ComfyuiGroupMeta = {
  hint: string;
  primaryTab: string;
};

type ComfyuiSyncStep = {
  tab: string;
  step: string;
  title: string;
  hint: string;
  metric: string;
  status: string;
};

type ComfyuiSyncGuide = {
  progress: string;
  entry: string;
  done: string;
  failure: string;
};

type SyncStatusMeta = {
  theme: 'default' | 'primary' | 'success' | 'warning' | 'danger';
  text: string;
};

type ComfyuiManagementHeaderProps = {
  activeTab: string;
  activeTabMeta: ComfyuiTabMeta;
  groupOrder: string[];
  groupMap: Record<string, string[]>;
  groupMeta: Record<string, ComfyuiGroupMeta>;
  groupBadge: Record<string, string>;
  tabMeta: Record<string, ComfyuiTabMeta>;
  activeGroupTabs: string[];
  tabHelpText: Record<string, string>;
  syncSteps: ComfyuiSyncStep[];
  syncStepStatusMeta: Record<string, SyncStatusMeta>;
  syncCurrentStep?: ComfyuiSyncStep | null;
  syncCurrentGuide?: ComfyuiSyncGuide | null;
  showTestNodes: boolean;
  hiddenExecutorCount: number;
  hiddenAgentCount: number;
  serversAssistOpen: boolean;
  manifestsAssistOpen: boolean;
  taskAdvancedOpen: boolean;
  onTabChange: (tab: string) => void;
  onRefreshCurrentStep: () => void;
  onToggleServersAssist: () => void;
  onToggleManifestsAssist: () => void;
  onCreateManifest: () => void;
  onToggleTaskAdvanced: () => void;
  onScrollToTaskCreate: () => void;
  onShowTestNodesChange: (value: boolean) => void;
};

const governanceFocusItems = [
  {
    title: '服务器纳管',
    body: '登记节点地址、用途标签、启停状态和并发上限，先保证调度目标清楚。',
  },
  {
    title: '能力部署',
    body: '检查 workflow、模型、LoRA、插件版本是否一致，不在这里替代 ComfyUI 编排后台。',
  },
  {
    title: '运行健康',
    body: '关注在线状态、队列、连续失败、回填失败，轻 agent 后续只增强观测和受控同步。',
  },
  {
    title: '调度效果',
    body: '看任务是否均匀分发、GPU 是否空转、任务之间是否断档。',
  },
];

export function ComfyuiManagementHeader({
  activeTab,
  activeTabMeta,
  groupOrder,
  groupMap,
  groupMeta,
  groupBadge,
  tabMeta,
  activeGroupTabs,
  tabHelpText,
  syncSteps,
  syncStepStatusMeta,
  syncCurrentStep,
  syncCurrentGuide,
  showTestNodes,
  hiddenExecutorCount,
  hiddenAgentCount,
  serversAssistOpen,
  manifestsAssistOpen,
  taskAdvancedOpen,
  onTabChange,
  onRefreshCurrentStep,
  onToggleServersAssist,
  onToggleManifestsAssist,
  onCreateManifest,
  onToggleTaskAdvanced,
  onScrollToTaskCreate,
  onShowTestNodesChange,
}: ComfyuiManagementHeaderProps) {
  const isSyncGroup = activeTabMeta.group === '同步发布';
  const hiddenDataMessage =
    hiddenExecutorCount > 0 || hiddenAgentCount > 0
      ? `（已隐藏测试数据：执行节点 ${hiddenExecutorCount}，代理服务 ${hiddenAgentCount}）`
      : '';

  return (
    <Space direction="vertical" size="small" style={{ marginBottom: 16, width: '100%' }}>
      <div className="rounded-2xl border border-slate-200/70 bg-slate-50/70 px-3 py-2 text-xs text-slate-600 dark:border-slate-800 dark:bg-slate-950/40 dark:text-slate-300">
        当前纳管视图：<strong>{activeTabMeta.label}</strong>（{activeTabMeta.group}）
      </div>
      <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-4">
        {governanceFocusItems.map((item) => (
          <div
            key={item.title}
            className="rounded-2xl border border-slate-200/70 bg-white px-3 py-3 dark:border-slate-800 dark:bg-slate-950/40"
          >
            <div className="text-xs font-semibold text-slate-900 dark:text-white">{item.title}</div>
            <div className="mt-1 text-xs leading-5 text-slate-600 dark:text-slate-300">{item.body}</div>
          </div>
        ))}
      </div>
      <div className="rounded-2xl border border-slate-200/70 bg-white px-3 py-3 dark:border-slate-800 dark:bg-slate-950/40">
        <div className="podi-comfy-level-label">纳管分区</div>
        <div className="podi-comfy-group-grid">
          {groupOrder.map((group) => {
            const groupTabs = groupMap[group] || [];
            const active = group === activeTabMeta.group;
            const leadTab = groupMeta[group]?.primaryTab || groupTabs[0] || activeTab;
            return (
              <button
                key={`comfy-group-${group}`}
                type="button"
                className={`podi-comfy-group-card${active ? ' is-active' : ''}${group === '同步发布' ? ' podi-comfy-group-card--subgroup' : ''}`}
                onClick={() => {
                  const nextTab = groupTabs.includes(activeTab) ? activeTab : leadTab;
                  onTabChange(nextTab);
                }}
              >
                <div className="podi-comfy-group-card__header">
                  <span className="podi-comfy-group-card__badge">{groupBadge[group]}</span>
                  <span className="podi-comfy-group-card__title">{group}</span>
                </div>
                <div className="podi-comfy-group-card__hint">{groupMeta[group]?.hint || ''}</div>
                {group === '同步发布' ? (
                  <div className="podi-comfy-group-card__subnote">二级流程 · 服务器对比 / 清单发布 / 任务下发</div>
                ) : null}
              </button>
            );
          })}
        </div>
        {isSyncGroup ? (
          <div className="podi-comfy-sync-steps">
            {syncSteps.map((step) => {
              const active = step.tab === activeTab;
              const statusMeta = syncStepStatusMeta[step.status] || syncStepStatusMeta.pending;
              return (
                <button
                  key={`comfy-sync-step-${step.tab}`}
                  type="button"
                  className={`podi-comfy-sync-step${active ? ' is-active' : ''}`}
                  onClick={() => onTabChange(step.tab)}
                >
                  <div className="podi-comfy-sync-step__head">
                    <span className="podi-comfy-sync-step__step">{step.step}</span>
                    <Space align="center" size="small">
                      <Tag size="small" theme={statusMeta.theme} variant="light">
                        {statusMeta.text}
                      </Tag>
                      {active ? (
                        <Tag size="small" theme="primary" variant="light">
                          当前
                        </Tag>
                      ) : null}
                    </Space>
                  </div>
                  <div className="podi-comfy-sync-step__title">{step.title}</div>
                  <div className="podi-comfy-sync-step__hint">{step.hint}</div>
                  <div className="podi-comfy-sync-step__metric">{step.metric}</div>
                </button>
              );
            })}
          </div>
        ) : null}
        {isSyncGroup ? (
          <div className="podi-comfy-sync-action-bar">
            <div className="podi-comfy-sync-action-bar__desc">
              <div className="podi-comfy-sync-action-bar__title">
                {syncCurrentStep ? `${syncCurrentStep.step} · ${syncCurrentStep.title}` : '同步发布'}
              </div>
              <div className="podi-comfy-sync-action-bar__hint">
                {syncCurrentStep?.hint || '按步骤执行，减少回滚与误下发。'}
              </div>
            </div>
            <Space align="center" size="small" style={{ flexWrap: 'wrap' }}>
              <Button size="small" variant="outline" onClick={onRefreshCurrentStep}>
                刷新当前步骤
              </Button>
              {activeTab === 'servers' ? (
                <>
                  <Button size="small" variant="outline" onClick={onToggleServersAssist}>
                    {serversAssistOpen ? '收起辅助面板' : '展开辅助面板'}
                  </Button>
                  <Button size="small" theme="primary" onClick={() => onTabChange('manifests')}>
                    下一步：清单发布
                  </Button>
                </>
              ) : null}
              {activeTab === 'manifests' ? (
                <>
                  <Button size="small" variant="outline" onClick={onToggleManifestsAssist}>
                    {manifestsAssistOpen ? '收起修复任务' : '展开修复任务'}
                  </Button>
                  <Button size="small" theme="primary" onClick={onCreateManifest}>
                    主操作：新增清单
                  </Button>
                </>
              ) : null}
              {activeTab === 'tasks' ? (
                <>
                  <Button size="small" variant="outline" onClick={onToggleTaskAdvanced}>
                    {taskAdvancedOpen ? '收起监控与历史' : '展开监控与历史'}
                  </Button>
                  <Button size="small" theme="primary" onClick={onScrollToTaskCreate}>
                    主操作：创建任务
                  </Button>
                </>
              ) : null}
            </Space>
          </div>
        ) : null}
        {isSyncGroup && syncCurrentGuide ? (
          <div className="rounded-2xl border border-slate-200/70 bg-slate-50/70 px-3 py-3 dark:border-slate-800 dark:bg-slate-950/40">
            <div className="text-xs text-slate-600 dark:text-slate-300">{syncCurrentGuide.progress}</div>
            <div className="mt-2 grid gap-2 xl:grid-cols-3">
              <div className="rounded-xl border border-slate-200 bg-white px-3 py-2 dark:border-slate-800 dark:bg-slate-900/60">
                <div className="text-[11px] font-semibold text-slate-900 dark:text-white">进入条件</div>
                <div className="mt-1 text-xs text-slate-600 dark:text-slate-300">{syncCurrentGuide.entry}</div>
              </div>
              <div className="rounded-xl border border-slate-200 bg-white px-3 py-2 dark:border-slate-800 dark:bg-slate-900/60">
                <div className="text-[11px] font-semibold text-slate-900 dark:text-white">完成条件</div>
                <div className="mt-1 text-xs text-slate-600 dark:text-slate-300">{syncCurrentGuide.done}</div>
              </div>
              <div className="rounded-xl border border-slate-200 bg-white px-3 py-2 dark:border-slate-800 dark:bg-slate-900/60">
                <div className="text-[11px] font-semibold text-slate-900 dark:text-white">失败后建议</div>
                <div className="mt-1 text-xs text-slate-600 dark:text-slate-300">{syncCurrentGuide.failure}</div>
              </div>
            </div>
          </div>
        ) : null}
        <div className="podi-comfy-module-bar">
          <div className="podi-comfy-module-controls">
            <div style={{ width: 'min(100%, 320px)' }}>
              <Typography.Text theme="secondary">模块</Typography.Text>
              <Select
                value={activeTab}
                onChange={(value) => onTabChange(String(value))}
                options={activeGroupTabs.map((tab) => ({
                  label: tabMeta[tab]?.label || tab,
                  value: tab,
                }))}
              />
            </div>
          </div>
          <Space align="center" size="small" className="podi-comfy-module-switch">
            <Switch value={showTestNodes} onChange={(value) => onShowTestNodesChange(Boolean(value))} />
            <Typography.Text theme="secondary">显示测试节点</Typography.Text>
          </Space>
        </div>
      </div>
      <Alert theme="info" message={`${tabHelpText[activeTab] || ''}${hiddenDataMessage}`} />
    </Space>
  );
}
