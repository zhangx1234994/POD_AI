import type { AppShellNavItem } from '../../../types/ui';

export const integrationNavItems = [
  {
    id: 'overview',
    label: '总体概览',
    shortLabel: 'OV',
    group: 'overview',
    groupLabel: '总览',
    description: '平台状态、主业务状态、待处理事项',
  },
  {
    id: 'business',
    label: '业务能力',
    shortLabel: 'BZ',
    group: 'business',
    groupLabel: '业务能力',
    description: '业务版本、发布时间、默认入口',
  },
  {
    id: 'ability-evals',
    label: '能力评测',
    shortLabel: 'EV',
    group: 'business',
    groupLabel: '业务能力',
    description: 'Coze 工作流试运行 + 评分',
  },
  {
    id: 'vendor-models',
    label: '模型弹药库',
    shortLabel: 'MD',
    group: 'vendor',
    groupLabel: '模型与 API',
    description: '第三方模型、密钥、出网与成本',
  },
  {
    id: 'apikeys',
    label: '历史密钥',
    shortLabel: 'AK',
    group: 'vendor',
    groupLabel: '模型与 API',
    description: '历史凭证配额管理',
  },
  {
    id: 'abilities',
    label: '能力目录',
    shortLabel: 'AB',
    group: 'atomic',
    groupLabel: '原子能力',
    description: '原子能力列表、健康、测试与成本',
  },
  {
    id: 'executors',
    label: '运行线路',
    shortLabel: 'EX',
    group: 'execution',
    groupLabel: '执行资源',
    description: '能力运行线路、并发和健康',
  },
  {
    id: 'comfyui-management',
    label: 'ComfyUI 资源',
    shortLabel: 'CF',
    group: 'execution',
    groupLabel: '执行资源',
    description: 'LoRA/模型/模板',
  },
  {
    id: 'bindings',
    label: '路由策略',
    shortLabel: 'BD',
    group: 'execution',
    groupLabel: '执行资源',
    description: '能力入口到运行线路的分配规则',
    advanced: true,
  },
  {
    id: 'workflow-builder',
    label: '高级编排',
    shortLabel: 'WF',
    group: 'execution',
    groupLabel: '执行资源',
    description: 'Coze 编排画布与运行观察',
    advanced: true,
  },
  {
    id: 'ability-logs',
    label: '能力调用',
    shortLabel: 'LG',
    group: 'usage',
    groupLabel: '调用与成本',
    description: '全局历史记录',
  },
  {
    id: 'billing',
    label: '账单框架',
    shortLabel: 'BI',
    group: 'usage',
    groupLabel: '调用与成本',
    description: '成本核对、流水、对账雏形',
    advanced: true,
  },
  {
    id: 'monitor',
    label: '调度监控',
    shortLabel: 'MO',
    group: 'usage',
    groupLabel: '调用与成本',
    description: '队列、任务和运行线路健康',
  },
  {
    id: 'logs',
    label: '调度事件',
    shortLabel: 'TL',
    group: 'usage',
    groupLabel: '调用与成本',
    description: '任务追踪',
    advanced: true,
  },
  {
    id: 'auth',
    label: '账号权限',
    shortLabel: 'AU',
    group: 'system',
    groupLabel: '系统与权限',
    description: '用户、会话、邀请码',
  },
  {
    id: 'system',
    label: '系统配置',
    shortLabel: 'SY',
    group: 'system',
    groupLabel: '系统与权限',
    description: '环境、OSS、待办',
  },
] as const satisfies readonly AppShellNavItem[];

export type IntegrationNavId = (typeof integrationNavItems)[number]['id'];

export const isIntegrationNavId = (value: string): value is IntegrationNavId =>
  integrationNavItems.some((item) => item.id === value);

export const isAdvancedIntegrationNav = (value: IntegrationNavId): boolean =>
  Boolean((integrationNavItems.find((item) => item.id === value) as AppShellNavItem | undefined)?.advanced);
