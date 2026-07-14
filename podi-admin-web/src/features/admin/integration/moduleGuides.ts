import type { IntegrationNavId } from './navigation';

export type ModuleGuide = {
  audience: string;
  firstLook: string;
  nextAction: string;
  riskHint?: string;
};

export const moduleGuides: Record<IntegrationNavId, ModuleGuide> = {
  overview: {
    audience: '平台管理员',
    firstLook: '先看核心能力、发版结论和当前待处理事项。',
    nextAction: '有风险时直接跳到对应模块处理。',
  },
  business: {
    audience: '平台管理员 / 业务方只读',
    firstLook: '先看核心能力的默认版本、发布证据和最近失败。',
    nextAction: '测试通过后再申请默认版本切换；异常时先回滚。',
    riskHint: '默认版本会影响业务入口。',
  },
  'api-exposure': {
    audience: '平台管理员 / 开发接入方',
    firstLook: '先看接口调用中心，再看业务 API、API Key 和 Coze 工具箱。',
    nextAction: '业务方优先给业务 API；排障先按 runId 聚合查看调用清单；Coze 只导入工具箱。',
    riskHint: '不要让业务方直接理解底层模型、工作流和执行节点。',
  },
  'ability-evals': {
    audience: '平台管理员 / 测试人员',
    firstLook: '先确认生产主入口是否能提交、回调和回填结果。',
    nextAction: '失败时复制运行 ID，先回到业务任务清单定位，再看具体处理步骤。',
  },
  'vendor-models': {
    audience: '开发接入方',
    firstLook: '先看密钥、配额、出网和最近失败样本。',
    nextAction: '新模型先完成最小验收，再绑定到原子能力。',
    riskHint: '不要让业务直接依赖缺少验收证据的模型。',
  },
  apikeys: {
    audience: '开发接入方',
    firstLook: '先确认历史密钥是否仍被旧链路使用。',
    nextAction: '能迁移到模型弹药库的密钥优先迁移。',
    riskHint: '历史密钥只保留兼容，不作为新能力入口。',
  },
  abilities: {
    audience: '开发接入方 / 平台管理员',
    firstLook: '先看能力健康、复测清单和最近调用。',
    nextAction: '能力稳定后再交给业务能力组合使用。',
  },
  executors: {
    audience: '开发接入方',
    firstLook: '先看运行线路是否在线、并发是否合理。',
    nextAction: '服务器不可用时先下线或调整路由，避免任务打空。',
  },
  'comfyui-management': {
    audience: '开发接入方',
    firstLook: '先看服务器、模板、LoRA、任务四类状态。',
    nextAction: '节点配置变化后先做模板自检，再交给业务入口。',
  },
  bindings: {
    audience: '开发接入方',
    firstLook: '先看业务入口实际会分配到哪条运行线路。',
    nextAction: '高风险能力必须指定线路，不允许静默兜底。',
    riskHint: '错误路由会直接影响生产出图。',
  },
  'workflow-builder': {
    audience: '开发接入方',
    firstLook: '先看 Coze 流程绑定和最近运行情况。',
    nextAction: '正式业务优先沉淀到业务能力，Coze 只做接入和实验。',
  },
  'ability-logs': {
    audience: '平台管理员 / 开发接入方',
    firstLook: '这里看图片分析、生图、评分等后台步骤，不作为业务是否成功的第一判断入口。',
    nextAction: '先在业务任务里定位 runId，再下钻到这里确认 VL、模型、ComfyUI 或回调细节。',
  },
  billing: {
    audience: '平台管理员',
    firstLook: '先看异常扣费、待定价、套餐余量和月结风险。',
    nextAction: '当前阶段只处理框架和对账，不深挖支付闭环。',
  },
  'production-orders': {
    audience: '运营管理员',
    firstLook: '先核对支付状态、蜂鸟订单号和供应商回传，再处理自动提交异常。',
    nextAction: '正常订单无需人工确认；仅对已支付但未成功推送蜂鸟的订单执行重试。',
    riskHint: '效果图和物流必须以蜂鸟回传为准，不能用页面预览代替。',
  },
  monitor: {
    audience: '平台管理员 / 开发接入方',
    firstLook: '先看排队、执行中和 ComfyUI 队列是否符合预期。',
    nextAction: '队列异常时先检查运行线路，再检查业务提交量。',
  },
  logs: {
    audience: '开发接入方',
    firstLook: '先按任务 ID 或事件类型定位调度过程。',
    nextAction: '只在排障时进入，日常不需要盯这个页面。',
  },
  auth: {
    audience: '平台管理员',
    firstLook: '先看业务方账号归属、邀请码和异常会话。',
    nextAction: '业务方只读范围必须绑定清楚，避免越权查看。',
  },
  system: {
    audience: '平台管理员 / 开发接入方',
    firstLook: '先核对数据库、OSS、Coze 和关键开关。',
    nextAction: '配置只作为快照核对，变更回对应模块处理。',
  },
};
