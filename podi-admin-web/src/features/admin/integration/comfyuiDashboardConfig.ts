export type ComfyuiManageTab =
  | 'lora'
  | 'templates'
  | 'servers'
  | 'assets'
  | 'agents'
  | 'desktop'
  | 'manifests'
  | 'tasks'
  | 'alerts';

export type ComfySyncStepTab = 'servers' | 'manifests' | 'tasks';
export type ComfyuiTabGroup = '资源目录' | '同步发布' | '节点运维';
export type ComfySyncStepStatus = 'blocked' | 'pending' | 'in_progress' | 'done';

export const comfyuiTabMeta: Record<ComfyuiManageTab, { label: string; group: ComfyuiTabGroup }> = {
  lora: { label: '素材库', group: '资源目录' },
  assets: { label: '资源清单', group: '资源目录' },
  templates: { label: '模板管理', group: '资源目录' },
  servers: { label: '服务器', group: '同步发布' },
  manifests: { label: '清单发布（版本）', group: '同步发布' },
  tasks: { label: '下发任务（执行记录）', group: '同步发布' },
  agents: { label: '代理服务', group: '节点运维' },
  alerts: { label: '告警', group: '节点运维' },
  desktop: { label: '桌面端部署', group: '节点运维' },
};

export const comfyuiTabOrder: ComfyuiManageTab[] = [
  'lora',
  'assets',
  'templates',
  'servers',
  'manifests',
  'tasks',
  'agents',
  'alerts',
  'desktop',
];

export const comfyuiTabGroupOrder: ComfyuiTabGroup[] = ['资源目录', '同步发布', '节点运维'];

export const comfyuiGroupMeta: Record<ComfyuiTabGroup, { hint: string; primaryTab: ComfyuiManageTab }> = {
  资源目录: {
    hint: '能力部署底账：维护模型、LoRA、插件和模板版本，确认每台机器缺什么。',
    primaryTab: 'lora',
  },
  同步发布: {
    hint: '服务器纳管主线：先看节点差异，再发布清单，最后下发同步任务。',
    primaryTab: 'servers',
  },
  节点运维: {
    hint: '运行健康与轻 agent 预留：查看心跳、告警、安装包和受控同步状态。',
    primaryTab: 'agents',
  },
};

export const comfyuiGroupBadge: Record<ComfyuiTabGroup, string> = {
  资源目录: 'R1',
  同步发布: 'R2',
  节点运维: 'R3',
};

export const comfyuiSyncStepMeta: Array<{ tab: ComfySyncStepTab; step: string; title: string; hint: string }> = [
  { tab: 'servers', step: '步骤 1', title: '服务器对比', hint: '确认节点可用、用途标签、并发上限与资源差异。' },
  { tab: 'manifests', step: '步骤 2', title: '清单发布', hint: '确认目标版本，避免不同机器 workflow / 模型不一致。' },
  { tab: 'tasks', step: '步骤 3', title: '任务下发', hint: '观察同步回执和调度衔接，不让 GPU 空转或任务断档。' },
];

export const comfySyncStepStatusMeta: Record<
  ComfySyncStepStatus,
  { theme: 'warning' | 'primary' | 'default' | 'success'; text: string }
> = {
  blocked: { theme: 'warning', text: '前置未满足' },
  pending: { theme: 'default', text: '待处理' },
  in_progress: { theme: 'primary', text: '进行中' },
  done: { theme: 'success', text: '已完成' },
};

export const comfyuiSyncGuideMeta: Record<ComfySyncStepTab, { entry: string; done: string; failure: string }> = {
  servers: {
    entry: '至少有 1 台 ComfyUI 服务器，并选定主服务器作为基线。',
    done: '主服务器差异已确认，并完成一次“保存对齐结果”。',
    failure: '刷新失败先查节点地址/连通性；差异异常先导出差异，再到“节点运维 > 告警”排障。',
  },
  manifests: {
    entry: '服务器差异已核对，明确目标角色（full/lite）与版本号。',
    done: '至少 1 个目标清单已发布，可用于任务下发。',
    failure: '发布失败先校验角色、版本与 JSON 内容；必要时回滚到最近稳定版本再重试。',
  },
  tasks: {
    entry: '已选择代理服务 + 清单（或清单地址），动作列表已确认。',
    done: '任务出现回执并进入最终状态（回调成功/失败）。',
    failure: '长时间等待先看任务事件，再检查代理服务心跳与队列；修复后执行“推送”重试。',
  },
};

export const comfyuiTabHelpText: Record<ComfyuiManageTab, string> = {
  lora: '素材库：只维护业务会引用的 LoRA 底账，重点确认文件名、基座模型和触发词是否可靠。',
  assets: '资源清单：维护模型、插件、ComfyUI 版本目录，作为后续集成包和机器差异检查的依据。',
  templates: '模板管理：维护可复用 workflow 模板和节点映射；具体编排仍在 ComfyUI 或业务配方中完成。',
  servers: '服务器：查看执行节点、用途标签、并发上限和基线差异，用于定位哪台机器缺资源或不该承接某类任务。',
  manifests: '清单发布（版本）：定义某类服务器应该达到的 workflow / 模型 / 插件版本，便于灰度和回滚。',
  tasks: '下发任务（执行记录）：跟踪清单同步和调度衔接，重点看任务是否连续、是否均匀分发、是否成功回填。',
  agents: '代理服务：轻 agent 先作为观测与受控同步通道，不把它做成第一阶段强依赖。',
  alerts: '告警：查看离线、队列堆积、连续失败、回填失败、磁盘异常等会影响业务的信号。',
  desktop: '桌面端部署：面向未来集成包发布，当前仅保留安装包、版本和升级状态的基础管理。',
};

const comfyAgentActionLabels: Record<string, string> = {
  sync_models: '同步模型',
  sync_plugins: '同步插件',
  sync_workflows: '同步工作流',
  restart: '重启服务',
};

export const isComfyuiManageTab = (value: string): value is ComfyuiManageTab =>
  comfyuiTabOrder.includes(value as ComfyuiManageTab);

export const readComfyuiTabFromParams = (params: URLSearchParams | null): ComfyuiManageTab | null => {
  if (!params) return null;
  const value = params.get('comfyTab') || params.get('comfy_tab') || params.get('tab') || '';
  return isComfyuiManageTab(value) ? value : null;
};

export const createComfyuiGroupMap = (): Record<ComfyuiTabGroup, ComfyuiManageTab[]> => {
  const map: Record<ComfyuiTabGroup, ComfyuiManageTab[]> = {
    资源目录: [],
    同步发布: [],
    节点运维: [],
  };
  for (const tab of comfyuiTabOrder) {
    map[comfyuiTabMeta[tab].group].push(tab);
  }
  return map;
};

export const formatComfyAgentActions = (actions?: string[] | null) => {
  if (!actions || actions.length === 0) return '—';
  return actions.map((action) => comfyAgentActionLabels[action] || action).join('、');
};

interface ComfySyncStepStateParams {
  activeTab: ComfyuiManageTab;
  baselineExecutorId: string;
  diffLogCount: number;
  executorCount: number;
  manifestCount: number;
  publishedManifestCount: number;
  runningTaskCount: number;
  visibleTaskCount: number;
}

export const buildComfySyncSteps = ({
  activeTab,
  baselineExecutorId,
  diffLogCount,
  executorCount,
  manifestCount,
  publishedManifestCount,
  runningTaskCount,
  visibleTaskCount,
}: ComfySyncStepStateParams) => {
  const serversDone = Boolean(baselineExecutorId) && diffLogCount > 0;
  const manifestsDone = publishedManifestCount > 0;
  const tasksDone = visibleTaskCount > 0 && runningTaskCount === 0;
  return comfyuiSyncStepMeta.map((step) => {
    let status: ComfySyncStepStatus = 'pending';
    if (step.tab === 'servers') {
      status = serversDone ? 'done' : step.tab === activeTab ? 'in_progress' : 'pending';
    } else if (step.tab === 'manifests') {
      if (!baselineExecutorId) {
        status = 'blocked';
      } else if (manifestsDone) {
        status = 'done';
      } else {
        status = step.tab === activeTab ? 'in_progress' : 'pending';
      }
    } else if (!manifestsDone) {
      status = 'blocked';
    } else if (tasksDone) {
      status = 'done';
    } else {
      status = step.tab === activeTab ? 'in_progress' : 'pending';
    }

    if (step.tab === 'servers') {
      return { ...step, metric: `${executorCount} 台节点`, status };
    }
    if (step.tab === 'manifests') {
      return { ...step, metric: `${publishedManifestCount}/${manifestCount} 已发布`, status };
    }
    return { ...step, metric: `${runningTaskCount} 运行中 / ${visibleTaskCount} 总任务`, status };
  });
};

export const buildComfySyncGuide = ({
  activeTab,
  baselineExecutorId,
  manifestCount,
  publishedManifestCount,
  runningTaskCount,
  visibleTaskCount,
}: Pick<
  ComfySyncStepStateParams,
  'activeTab' | 'baselineExecutorId' | 'manifestCount' | 'publishedManifestCount' | 'runningTaskCount' | 'visibleTaskCount'
>) => {
  if (activeTab !== 'servers' && activeTab !== 'manifests' && activeTab !== 'tasks') {
    return null;
  }
  const baseGuide = comfyuiSyncGuideMeta[activeTab];
  const progress =
    activeTab === 'servers'
      ? baselineExecutorId
        ? `当前进度：已选主服务器 ${baselineExecutorId}`
        : '当前进度：待选择主服务器'
      : activeTab === 'manifests'
        ? `当前进度：已发布 ${publishedManifestCount}/${manifestCount} 个清单`
        : `当前进度：运行中 ${runningTaskCount} / 总任务 ${visibleTaskCount}`;
  return {
    ...baseGuide,
    progress,
  };
};
