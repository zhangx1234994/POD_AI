import { useCallback, useEffect, useState } from 'react';
import { Alert, Button, Card, Input, Space, Table, Tag, Typography } from 'tdesign-react';
import { adminApi } from '../../../services/adminApi';
import type {
  BusinessApiKey,
  BusinessApiKeyUsageLog,
  BusinessApiKeyUsageRunGroup,
  BusinessApiKeyUsageSummary,
  PublicAbility,
} from '../../../types/admin';

type ApiEndpoint = {
  key: string;
  name: string;
  method: 'GET' | 'POST';
  path: string;
  purpose: string;
  audience: string;
  businessKey: string;
};

type ToolboxEndpoint = {
  key: string;
  name: string;
  path: string;
  purpose: string;
  status: '主入口' | '专项工具箱' | '查询工具箱';
  businessKey: string;
};

type BusinessInterfaceGroup = {
  key: string;
  name: string;
  summary: string;
  nativeStatus: 'ready' | 'planning' | 'internal';
  accent: 'success' | 'primary' | 'warning' | 'default';
};

type BusinessApiParamDoc = {
  key: string;
  required: boolean;
  description: string;
  example: string;
};

type BusinessApiEnumDoc = {
  field: string;
  value: string;
  meaning: string;
  action: string;
};

type DeliveryGuardStatus = 'done' | 'doing' | 'todo';

type DeliveryGuard = {
  key: string;
  title: string;
  detail: string;
  status: DeliveryGuardStatus;
  owner: string;
  action: string;
};

type OnboardingCheck = {
  key: string;
  title: string;
  detail: string;
  action: string;
  tag: string;
  theme: 'success' | 'primary' | 'warning';
};

type BusinessApiKeyFormState = {
  name: string;
  key: string;
  tenantId: string;
  clientId: string;
  allowedBusinessKeys: string;
  expireAt: string;
};

type BusinessApiUsageFilters = {
  windowHours: string;
  apiKeyId: string;
  businessKey: string;
  endpointKind: string;
  statusGroup: string;
  path: string;
  runId: string;
  requestId: string;
  traceId: string;
  errorCode: string;
};

type ApiExposurePanelProps = {
  publicAbilities: PublicAbility[];
  publicAbilitiesLoading: boolean;
  cozeAbilityStats: {
    total: number;
    mapped: number;
  };
  onRefreshPublicAbilities: () => void;
  onCopy: (value: string) => void;
  onOpenBusinessRun?: (runId: string) => void;
  getProviderLabel: (value: string) => string;
  getCategoryLabel: (value: string) => string;
};

const BUSINESS_INTERFACE_GROUPS: BusinessInterfaceGroup[] = [
  {
    key: 'pattern_extract',
    name: '花纹提取',
    summary: '从商品或素材图提取可复用花纹资产。',
    nativeStatus: 'ready',
    accent: 'success',
  },
  {
    key: 'image_fission',
    name: '图裂变',
    summary: '基于原图生成变化图、风格变体或高质量裂变图。',
    nativeStatus: 'ready',
    accent: 'success',
  },
  {
    key: 'outpaint',
    name: '扩图',
    summary: '向上下左右扩展画面，补背景和构图。',
    nativeStatus: 'ready',
    accent: 'success',
  },
  {
    key: 'seamless_pattern',
    name: '连续图',
    summary: '生成或检查两方、四方连续图。',
    nativeStatus: 'planning',
    accent: 'primary',
  },
  {
    key: 'cutout',
    name: '抠图',
    summary: '背景抠图、头部抠像和主体提取。',
    nativeStatus: 'planning',
    accent: 'primary',
  },
  {
    key: 'image_enhancement',
    name: '图像增强',
    summary: '放大、DPI、清晰度和尺寸修复。',
    nativeStatus: 'internal',
    accent: 'warning',
  },
  {
    key: 'vision_analysis',
    name: '图像理解',
    summary: 'VL 图片分析、标签和提示词建议。',
    nativeStatus: 'planning',
    accent: 'primary',
  },
];

const BUSINESS_ENDPOINTS: ApiEndpoint[] = [
  {
    key: 'business-openapi',
    name: '业务 OpenAPI',
    method: 'GET',
    path: '/api/business/openapi.json',
    purpose: '业务方或内部系统导入稳定业务接口。',
    audience: '业务接入 / 开发联调',
    businessKey: 'platform_tools',
  },
  {
    key: 'pattern-run',
    name: '花纹提取',
    method: 'POST',
    path: '/api/business/pattern-extract/runs',
    purpose: '提交花纹提取任务，底层版本由中台决定。',
    audience: '业务主入口',
    businessKey: 'pattern_extract',
  },
  {
    key: 'fission-run',
    name: '图裂变',
    method: 'POST',
    path: '/api/business/fission/runs',
    purpose: '提交图裂变任务，返回 runId 后查询结果。',
    audience: '业务主入口',
    businessKey: 'image_fission',
  },
  {
    key: 'fission-evaluate-run',
    name: '裂变生成图评估',
    method: 'POST',
    path: '/api/business/fission-evaluate/runs',
    purpose: '输入原图和裂变结果图，判断质量和逻辑是否通过。',
    audience: '业务主入口 / 质检',
    businessKey: 'image_fission',
  },
  {
    key: 'outpaint-run',
    name: '扩图',
    method: 'POST',
    path: '/api/business/outpaint/runs',
    purpose: '提交扩图任务，宽高和四向扩展量由参数控制。',
    audience: '业务主入口',
    businessKey: 'outpaint',
  },
  {
    key: 'business-get',
    name: '查询业务任务',
    method: 'POST',
    path: '/api/business/runs/get',
    purpose: '统一按 runId 查询状态、图片、错误和调试信息。',
    audience: '业务接入 / 回调兜底',
    businessKey: 'platform_tools',
  },
  {
    key: 'pattern-preview',
    name: '花纹提取路由预览',
    method: 'POST',
    path: '/api/business/pattern-extract/route-preview',
    purpose: '不提交真实任务，只验证当前业务方会命中哪个版本。',
    audience: '灰度 / 上线前验证',
    businessKey: 'pattern_extract',
  },
  {
    key: 'fission-preview',
    name: '图裂变路由预览',
    method: 'POST',
    path: '/api/business/fission/route-preview',
    purpose: '不提交真实任务，只验证图裂变默认、灰度或指定版本命中。',
    audience: '灰度 / 上线前验证',
    businessKey: 'image_fission',
  },
  {
    key: 'outpaint-preview',
    name: '扩图路由预览',
    method: 'POST',
    path: '/api/business/outpaint/route-preview',
    purpose: '不提交真实任务，只验证扩图默认、灰度或指定版本命中。',
    audience: '灰度 / 上线前验证',
    businessKey: 'outpaint',
  },
];

const ABILITY_ENDPOINTS: ApiEndpoint[] = [
  {
    key: 'ability-list',
    name: '能力清单',
    method: 'GET',
    path: '/api/abilities',
    purpose: '读取已开放原子能力、字段说明、健康状态和能力编号。',
    audience: '开发接入 / 上层编排',
    businessKey: 'platform_tools',
  },
  {
    key: 'ability-detail',
    name: '能力详情',
    method: 'GET',
    path: '/api/abilities/{abilityId}',
    purpose: '查看单个能力的输入字段、默认参数和运行要求。',
    audience: '开发接入 / 排障',
    businessKey: 'platform_tools',
  },
  {
    key: 'ability-invoke',
    name: '调用能力',
    method: 'POST',
    path: '/api/abilities/{abilityId}/invoke',
    purpose: '直接触发原子能力，适合内部编排、测评和高级开发。',
    audience: '开发接入 / 测评',
    businessKey: 'platform_tools',
  },
  {
    key: 'ability-options',
    name: '表单选项',
    method: 'GET',
    path: '/api/abilities/options',
    purpose: '读取能力表单需要的候选值，减少前端硬编码。',
    audience: '前端 / 工具开发',
    businessKey: 'platform_tools',
  },
];

const FISSION_API_PARAMS: BusinessApiParamDoc[] = [
  {
    key: 'imageUrl',
    required: true,
    description: '原图地址。必须是中台、Coze 和能力服务器都能访问的图片 URL。',
    example: 'https://example.com/input.png',
  },
  {
    key: 'version',
    required: false,
    description: '指定图裂变版本。不传时使用中台默认版本；当前 GPT Image 2 受控版传 gpt-image2-vl-v2，ComfyUI 颜色锁定版传 comfyui-vl-control-v2。',
    example: 'gpt-image2-vl-v2',
  },
  {
    key: 'prompt',
    required: false,
    description: '业务提示词。图裂变已有 VL 分析和默认系统提示词，不传也可以运行；传入后作为补充要求。',
    example: '保持主体关系，生成更适合商品使用的花纹变化',
  },
  {
    key: 'bili',
    required: false,
    description: 'ComfyUI 裂变重绘幅度，沿用旧约定。值越大变化越明显，值越小越接近原图。',
    example: '50%',
  },
  {
    key: 'profile',
    required: false,
    description: 'ComfyUI 裂变配置：pattern_risk_routed_v4、pattern_color_lock_v2、pattern_color_lock_strict_v2、pattern_default_v1。',
    example: 'pattern_risk_routed_v4',
  },
  {
    key: 'variation_preset',
    required: false,
    description: '测评/业务参数预设：default-high、safe、object-strong、color-free。显式传入的 bili/reference_lock/color_lock 优先。',
    example: 'object-strong',
  },
  {
    key: 'pattern_risk_type',
    required: false,
    description: 'VL 图案风险类型：element_pattern、object_variation、text_or_logo、border_or_layout、unknown。通常由中台自动生成。',
    example: 'object_variation',
  },
  {
    key: 'width / height',
    required: false,
    description: '输出宽高。测评端上传图片后默认取原图宽高，业务方也可以手动指定。',
    example: '2000 / 2000',
  },
  {
    key: 'variation_strength',
    required: false,
    description: 'GPT Image 2 版本的裂变幅度：conservative、same_series、creative_same_series。默认 same_series。',
    example: 'same_series',
  },
  {
    key: 'quality',
    required: false,
    description: 'GPT Image 2 质量档位：preview、candidate、premium。',
    example: 'preview',
  },
  {
    key: 'size',
    required: false,
    description: 'GPT Image 2 输出尺寸预设，例如 auto、1024x1024、1536x1024、1024x1536。',
    example: 'auto',
  },
  {
    key: 'maskUrl',
    required: false,
    description: '蒙版图片 URL。需要局部编辑时传入；普通裂变可不传。',
    example: 'https://example.com/mask.png',
  },
  {
    key: 'callbackUrl',
    required: false,
    description: '终态回调地址。不传时业务方自行轮询 runId。',
    example: 'https://your-service.example.com/podi/callback',
  },
  {
    key: 'requestId / traceId',
    required: false,
    description: '业务方请求编号和链路编号，用于幂等、日志关联和排障。',
    example: 'biz-request-001 / biz-trace-001',
  },
  {
    key: 'source / channel',
    required: false,
    description: '调用来源和接入渠道，例如 partner-api、open-api、coze-workflow。',
    example: 'partner-api / open-api',
  },
];

const BUSINESS_API_STATUS_DOCS: BusinessApiEnumDoc[] = [
  { field: 'status / taskStatus', value: 'queued', meaning: '已进入中台队列，还没开始执行。', action: '按 retryAfterSeconds 继续查询。' },
  { field: 'status / taskStatus', value: 'running', meaning: '正在执行或等待结果回填。', action: '按 retryAfterSeconds 继续查询。' },
  { field: 'status / taskStatus', value: 'succeeded', meaning: '任务成功，结果字段可读取。', action: '读取 imageUrls / videoUrls / texts / resultPayload。' },
  { field: 'status / taskStatus', value: 'failed', meaning: '任务失败或无法继续。', action: '读取 errorCode / errorMessage，并按错误码处理。' },
  { field: 'decision', value: 'pass', meaning: '裂变评分通过。', action: '可以接受当前生成图。' },
  { field: 'decision', value: 'needs_refission', meaning: '建议二次裂变。', action: '业务侧可重新提交裂变任务。' },
  { field: 'decision', value: 'reject', meaning: '不建议使用。', action: '拒绝当前结果或人工复核。' },
];

const FISSION_EVALUATE_API_PARAMS: BusinessApiParamDoc[] = [
  {
    key: 'originalImageUrl',
    required: true,
    description: '裂变前原图 URL，用于判断生成图是否保留原始主体、边界和业务逻辑。',
    example: 'https://example.com/original.png',
  },
  {
    key: 'generatedImageUrl',
    required: true,
    description: '裂变后的结果图 URL。评分只判断这张图，不会自动二次裂变。',
    example: 'https://example.com/generated.png',
  },
  {
    key: 'context',
    required: false,
    description: '业务上下文，例如裂变版本、提示词、重绘幅度、配置名。传得越完整，评分解释越准确。',
    example: '{"business":"fission","version":"gpt-image2-vl-v2"}',
  },
  {
    key: 'callbackUrl',
    required: false,
    description: '终态回调地址。不传时业务方自行轮询 runId。',
    example: 'https://your-service.example.com/podi/callback',
  },
  {
    key: 'requestId / traceId',
    required: false,
    description: '业务方请求编号和链路编号，用于和裂变任务、评分任务关联。',
    example: 'biz-eval-001 / trace-eval-001',
  },
];

const COZE_TOOLBOX_ENDPOINTS: ToolboxEndpoint[] = [
  {
    key: 'coze-main',
    name: 'PODI 综合工具箱',
    path: '/api/coze/podi/openapi.json',
    purpose: 'Coze 导入全部可用能力工具和任务查询。',
    status: '主入口',
    businessKey: 'platform_tools',
  },
  {
    key: 'coze-comfyui',
    name: 'ComfyUI 工具箱',
    path: '/api/coze/podi/comfyui/openapi.json',
    purpose: 'Coze 导入 ComfyUI 类能力。',
    status: '专项工具箱',
    businessKey: 'platform_tools',
  },
  {
    key: 'coze-fission',
    name: '高质量图裂变',
    path: '/api/coze/podi/comfyui/execute/flux-strong-hq-softstyle-fission/openapi.json',
    purpose: '新高质量裂变工作流专项导入口。',
    status: '专项工具箱',
    businessKey: 'image_fission',
  },
  {
    key: 'coze-outpaint',
    name: '扩图主线',
    path: '/api/coze/podi/comfyui/execute/flux2-klein-9b-outpaint/openapi.json',
    purpose: '扩图主线工作流专项导入口。',
    status: '专项工具箱',
    businessKey: 'outpaint',
  },
  {
    key: 'coze-bg-remove',
    name: '背景抠图',
    path: '/api/coze/podi/comfyui/execute/beijing-koutu/openapi.json',
    purpose: '背景抠图专项导入口。',
    status: '专项工具箱',
    businessKey: 'cutout',
  },
  {
    key: 'coze-head-cutout',
    name: '头部抠像',
    path: '/api/coze/podi/comfyui/execute/toubu-kouxiang/openapi.json',
    purpose: '头部抠像专项导入口。',
    status: '专项工具箱',
    businessKey: 'cutout',
  },
  {
    key: 'coze-kie',
    name: 'KIE 模型工具箱',
    path: '/api/coze/podi/kie/openapi.json',
    purpose: 'Coze 导入 KIE 类商业模型工具。',
    status: '专项工具箱',
    businessKey: 'platform_tools',
  },
  {
    key: 'coze-tasks',
    name: '任务查询',
    path: '/api/coze/podi/tasks/get',
    purpose: 'Coze 工作流按 taskId 查询最终图片、视频、文字或错误。',
    status: '查询工具箱',
    businessKey: 'platform_tools',
  },
];

const API_DELIVERY_GUARDS: DeliveryGuard[] = [
  {
    key: 'frontend-surface',
    title: '页面已露出',
    detail: '业务 API、原子能力 API、Coze 工具箱已经在管理端分开展示。',
    status: 'done',
    owner: '管理端',
    action: '后续新增入口必须同步加到本页。',
  },
  {
    key: 'docs-contract',
    title: '文档已对齐',
    detail: '页面接口清单已对齐 business / abilities / coze 三份接口文档和总索引。',
    status: 'done',
    owner: '接口文档',
    action: '后续新增或改名接口必须同批更新页面与模块文档。',
  },
  {
    key: 'error-contract',
    title: '错误口径已补齐',
    detail: '缺参、鉴权、队列满、依赖失败、超时已按三类 API 写入处理口径。',
    status: 'done',
    owner: '错误契约',
    action: '后续新增错误必须同步错误码总表和对应模块文档。',
  },
  {
    key: 'smoke-check',
    title: '冒烟清单已补齐',
    detail: 'OpenAPI、任务查询、工具箱导入地址已有可复跑清单，真实出图继续走业务巡检脚本。',
    status: 'done',
    owner: '回归门禁',
    action: '阶段发版前按清单执行，并把实际结果写入回归报告。',
  },
];

const BUSINESS_ONBOARDING_CHECKS: OnboardingCheck[] = [
  {
    key: 'identity-scope',
    title: '先开通业务方身份',
    detail: '业务方账号或服务 Token 必须绑定 tenantId/clientId，不能把管理员账号当长期业务凭证。',
    action: '到账号权限页确认业务方范围；服务 Token 只用于系统级调用和巡检。',
    tag: '身份边界',
    theme: 'success',
  },
  {
    key: 'business-policy',
    title: '确认可调用业务',
    detail: '业务方只应该看到被授权的业务，例如花纹提取、图裂变、扩图。',
    action: '在业务能力页或业务方策略里确认 allowedBusinesses、并发和日额度。',
    tag: '权限与额度',
    theme: 'primary',
  },
  {
    key: 'route-preview',
    title: '先跑路由预览',
    detail: 'route-preview 不下发真实任务，适合确认默认版本、灰度和回滚命中。',
    action: '上线前先跑三主业务 route-preview，再跑一次真实样图巡检。',
    tag: '不消耗额度',
    theme: 'primary',
  },
  {
    key: 'callback-polling',
    title: '回调和轮询都保留',
    detail: 'callbackUrl 能减少业务方轮询，但回调失败时仍要用 runId 查询兜底。',
    action: '业务方保存 runId、traceId 和 requestId；客服排障也用这些编号。',
    tag: '结果兜底',
    theme: 'success',
  },
  {
    key: 'error-handling',
    title: '提前接好错误处理',
    detail: '队列满、依赖失败、超时、配额不足都属于可解释错误，不应该让业务方猜。',
    action: '按错误码给出“稍后重试 / 联系平台 / 补参数 / 补额度”的固定提示。',
    tag: '上线必查',
    theme: 'warning',
  },
];

const DEFAULT_BUSINESS_API_KEY_FORM: BusinessApiKeyFormState = {
  name: '',
  key: '',
  tenantId: '',
  clientId: '',
  allowedBusinessKeys: 'fission,fission_evaluate,outpaint,pattern_extract',
  expireAt: '',
};

const BUSINESS_API_USAGE_PAGE_SIZE = 50;

const DEFAULT_BUSINESS_API_USAGE_FILTERS: BusinessApiUsageFilters = {
  windowHours: '24',
  apiKeyId: 'all',
  businessKey: 'all',
  endpointKind: 'all',
  statusGroup: 'all',
  path: '',
  runId: '',
  requestId: '',
  traceId: '',
  errorCode: '',
};

const DEFAULT_BUSINESS_API_USAGE_SUMMARY: BusinessApiKeyUsageSummary = {
  total: 0,
  successCount: 0,
  errorCount: 0,
  submitCount: 0,
  pollCount: 0,
  callbackCount: 0,
  uniqueRunCount: 0,
  averageDurationMs: null,
};

function businessStatusLabel(status: BusinessInterfaceGroup['nativeStatus']): string {
  if (status === 'ready') return '原生 API 已具备';
  if (status === 'planning') return '待补原生 API';
  return '内部能力为主';
}

function businessStatusTheme(status: BusinessInterfaceGroup['nativeStatus']): 'success' | 'primary' | 'warning' | 'default' {
  if (status === 'ready') return 'success';
  if (status === 'planning') return 'primary';
  if (status === 'internal') return 'warning';
  return 'default';
}

function inferAbilityBusinessKey(ability: PublicAbility): string {
  const text = `${ability.id} ${ability.displayName} ${ability.category} ${ability.provider} ${ability.abilityType}`.toLowerCase();
  if (/花纹|印花|pattern|yinhua/.test(text)) return 'pattern_extract';
  if (/裂变|fission|variation|softstyle|e7/.test(text)) return 'image_fission';
  if (/扩图|延伸|outpaint|extend|klein/.test(text)) return 'outpaint';
  if (/连续|四方|两方|seamless|lianxu/.test(text)) return 'seamless_pattern';
  if (/抠图|抠像|去背|background|cutout|matting|koutu|kouxiang/.test(text)) return 'cutout';
  if (/融合|合成|多图|fusion|compose|merge/.test(text)) return 'image_composition';
  if (/放大|高清|dpi|增强|upscale|enhance|resize/.test(text)) return 'image_enhancement';
  if (/vl|视觉|理解|识别|描述|标签|vision|describe/.test(text)) return 'vision_analysis';
  if (/文字|文本|提示词|prompt|text/.test(text)) return 'text_prompt';
  if (/视频|video|seedance|sora/.test(text)) return 'video_generation';
  return 'platform_tools';
}

function methodTheme(method: string): 'success' | 'primary' | 'default' {
  if (method === 'POST') return 'primary';
  if (method === 'GET') return 'success';
  return 'default';
}

function toolboxStatusTheme(status: ToolboxEndpoint['status']): 'success' | 'warning' | 'default' {
  if (status === '主入口') return 'success';
  if (status === '专项工具箱') return 'warning';
  return 'default';
}

function deliveryGuardTheme(status: DeliveryGuardStatus): 'success' | 'warning' | 'default' {
  if (status === 'done') return 'success';
  if (status === 'doing') return 'warning';
  return 'default';
}

function apiKeyStatusTheme(status: string): 'success' | 'warning' | 'danger' | 'default' {
  if (status === 'active') return 'success';
  if (status === 'cooldown' || status === 'error') return 'warning';
  if (status === 'disabled' || status === 'exhausted') return 'danger';
  return 'default';
}

function apiKeyStatusLabel(status: string): string {
  if (status === 'active') return '启用';
  if (status === 'disabled') return '停用';
  if (status === 'cooldown') return '冷却';
  if (status === 'exhausted') return '额度用尽';
  if (status === 'error') return '异常';
  return status || '未知';
}

function formatDateTime(value?: string | null): string {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('zh-CN', { hour12: false });
}

function endpointKindLabel(value?: string | null): string {
  if (value === 'submit') return '提交任务';
  if (value === 'poll') return '轮询结果';
  if (value === 'callback') return '回调';
  return '全部接口';
}

function inferEndpointKind(path?: string | null): 'submit' | 'poll' | 'callback' | 'other' {
  const text = String(path || '');
  if (text === '/api/business/runs/get') return 'poll';
  if (text.includes('callback')) return 'callback';
  if (text.endsWith('/runs')) return 'submit';
  return 'other';
}

function endpointKindTheme(value?: string | null): 'success' | 'primary' | 'warning' | 'default' {
  const kind = value || 'other';
  if (kind === 'submit') return 'success';
  if (kind === 'poll') return 'primary';
  if (kind === 'callback') return 'warning';
  return 'default';
}

function businessApiUsageIssue(row: BusinessApiKeyUsageRunGroup): {
  needsAttention: boolean;
  code: string | null;
  hint: string | null;
} {
  if (row.needsAttention) {
    return { needsAttention: true, code: row.issueCode || 'NEEDS_ATTENTION', hint: row.issueHint || '该任务链路需要关注。' };
  }
  if ((row.errorCount || 0) > 0) {
    return { needsAttention: true, code: 'HAS_ERROR', hint: '该任务链路存在异常响应或错误码。' };
  }
  if ((row.pollCount || 0) > 0 && (row.submitCount || 0) === 0) {
    return { needsAttention: true, code: 'POLL_WITHOUT_SUBMIT', hint: '当前筛选范围内只有查询记录，没有提交记录。' };
  }
  if ((row.pollCount || 0) >= 30) {
    return { needsAttention: true, code: 'POLLING_TOO_FREQUENT', hint: '同一任务查询次数偏多，建议业务方按建议间隔轮询。' };
  }
  return { needsAttention: false, code: null, hint: null };
}

function formatNumber(value?: number | null): string {
  if (value == null || Number.isNaN(value)) return '0';
  return new Intl.NumberFormat('zh-CN').format(value);
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function generateBusinessApiKeyValue(): string {
  const bytes = new Uint8Array(24);
  if (typeof window !== 'undefined' && window.crypto?.getRandomValues) {
    window.crypto.getRandomValues(bytes);
  } else {
    for (let i = 0; i < bytes.length; i += 1) {
      bytes[i] = Math.floor(Math.random() * 256);
    }
  }
  const token = Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('');
  return `podi_live_${token}`;
}

function parseAllowedBusinessKeys(value: string): string[] {
  return value
    .split(/[\s,，]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function normalizeDatetimeLocal(value: string): string | null {
  const trimmed = value.trim();
  if (!trimmed) return null;
  const date = new Date(trimmed);
  if (Number.isNaN(date.getTime())) return trimmed;
  return date.toISOString();
}

function buildAbilityInvokeExample(abilityId: string): string {
  return `curl -X POST <backend-host>/api/abilities/${abilityId}/invoke \\
  -H "Authorization: Bearer <accessToken 或 SERVICE_API_TOKEN>" \\
  -H "Content-Type: application/json" \\
  -d '{
    "inputs": {
      "prompt": "示例提示词",
      "image_url": "https://example.com/input.png"
    }
  }'`;
}

function buildBusinessRunExample(): string {
  return `curl -X POST <backend-host>/api/business/fission/runs \\
  -H "X-PODI-API-Key: <业务 API Key>" \\
  -H "Content-Type: application/json" \\
  -d '{
    "imageUrl": "https://example.com/input.png",
    "version": "gpt-image2-vl-v2",
    "prompt": "可选：保持主体风格，生成更适合商品使用的花纹变化",
    "variation_strength": "same_series",
    "quality": "preview",
    "size": "auto",
    "source": "partner-api",
    "channel": "open-api",
    "callbackUrl": "https://your-service.example.com/callback",
    "requestId": "biz_req_001",
    "traceId": "biz_trace_001"
  }'`;
}

function buildFissionEvaluateExample(): string {
  return `curl -X POST <backend-host>/api/business/fission-evaluate/runs \\
  -H "X-PODI-API-Key: <业务 API Key>" \\
  -H "Content-Type: application/json" \\
  -d '{
    "originalImageUrl": "https://example.com/original.png",
    "generatedImageUrl": "https://example.com/generated.png",
    "context": {
      "business": "fission",
      "version": "gpt-image2-vl-v2",
      "prompt": "保持系列感，元素要明显变化"
    },
    "source": "partner-api",
    "channel": "open-api",
    "requestId": "biz_eval_req_001",
    "traceId": "biz_eval_trace_001"
  }'`;
}

function buildBusinessQueryExample(): string {
  return `curl -X POST <backend-host>/api/business/runs/get \\
  -H "X-PODI-API-Key: <业务 API Key>" \\
  -H "Content-Type: application/json" \\
  -d '{
    "runId": "<提交接口返回的 runId>"
  }'`;
}

function buildCozeCompatibleQueryExample(): string {
  return `curl -X POST <backend-host>/api/coze/podi/tasks/get \\
  -H "Authorization: Bearer <SERVICE_API_TOKEN>" \\
  -H "Content-Type: application/json" \\
  -d '{
    "taskId": "<runId 或 taskId>"
  }'`;
}

function CopyButton({ value, onCopy, label = '复制' }: { value: string; onCopy: (value: string) => void; label?: string }) {
  return (
    <Button size="small" variant="text" onClick={() => onCopy(value)}>
      {label}
    </Button>
  );
}

function CodeExample({ value, onCopy }: { value: string; onCopy: (value: string) => void }) {
  return (
    <div className="podi-api-code-block">
      <CopyButton value={value} onCopy={onCopy} label="复制示例" />
      <pre>{value}</pre>
    </div>
  );
}

export function ApiExposurePanel({
  publicAbilities,
  publicAbilitiesLoading,
  cozeAbilityStats,
  onRefreshPublicAbilities,
  onCopy,
  onOpenBusinessRun,
  getProviderLabel,
  getCategoryLabel,
}: ApiExposurePanelProps) {
  const [businessApiKeys, setBusinessApiKeys] = useState<BusinessApiKey[]>([]);
  const [businessApiKeyUsage, setBusinessApiKeyUsage] = useState<BusinessApiKeyUsageLog[]>([]);
  const [businessApiKeyUsageGroups, setBusinessApiKeyUsageGroups] = useState<BusinessApiKeyUsageRunGroup[]>([]);
  const [businessApiKeyUsageSummary, setBusinessApiKeyUsageSummary] = useState<BusinessApiKeyUsageSummary>(
    DEFAULT_BUSINESS_API_USAGE_SUMMARY,
  );
  const [businessApiKeyUsageTotal, setBusinessApiKeyUsageTotal] = useState(0);
  const [businessApiKeyUsagePage, setBusinessApiKeyUsagePage] = useState(1);
  const [businessApiUsageFilters, setBusinessApiUsageFilters] = useState<BusinessApiUsageFilters>(
    DEFAULT_BUSINESS_API_USAGE_FILTERS,
  );
  const [businessApiKeyLoading, setBusinessApiKeyLoading] = useState(false);
  const [businessApiUsageExporting, setBusinessApiUsageExporting] = useState(false);
  const [businessApiKeySaving, setBusinessApiKeySaving] = useState(false);
  const [businessApiKeyError, setBusinessApiKeyError] = useState('');
  const [businessApiKeyNotice, setBusinessApiKeyNotice] = useState('');
  const [businessApiKeyForm, setBusinessApiKeyForm] = useState<BusinessApiKeyFormState>(DEFAULT_BUSINESS_API_KEY_FORM);
  const loadBusinessApiKeyAudit = useCallback(async () => {
    setBusinessApiKeyLoading(true);
    setBusinessApiKeyError('');
    try {
      const usageOffset = Math.max(0, businessApiKeyUsagePage - 1) * BUSINESS_API_USAGE_PAGE_SIZE;
      const [keysRes, usageRes] = await Promise.all([
        adminApi.listBusinessApiKeys(),
        adminApi.listBusinessApiKeyUsage({
          apiKeyId: businessApiUsageFilters.apiKeyId,
          businessKey: businessApiUsageFilters.businessKey,
          endpointKind: businessApiUsageFilters.endpointKind,
          statusGroup: businessApiUsageFilters.statusGroup,
          path: businessApiUsageFilters.path,
          runId: businessApiUsageFilters.runId,
          requestId: businessApiUsageFilters.requestId,
          traceId: businessApiUsageFilters.traceId,
          errorCode: businessApiUsageFilters.errorCode,
          windowHours: businessApiUsageFilters.windowHours,
          offset: usageOffset,
          limit: BUSINESS_API_USAGE_PAGE_SIZE,
          groupLimit: 30,
        }),
      ]);
      setBusinessApiKeys(keysRes.items || []);
      setBusinessApiKeyUsage(usageRes.items || []);
      setBusinessApiKeyUsageGroups(usageRes.groups || []);
      setBusinessApiKeyUsageSummary(usageRes.summary || DEFAULT_BUSINESS_API_USAGE_SUMMARY);
      setBusinessApiKeyUsageTotal(usageRes.total || 0);
    } catch (err) {
      setBusinessApiKeyError(String((err as Error)?.message || err));
    } finally {
      setBusinessApiKeyLoading(false);
    }
  }, [businessApiKeyUsagePage, businessApiUsageFilters]);

  useEffect(() => {
    void loadBusinessApiKeyAudit();
  }, [loadBusinessApiKeyAudit]);

  const updateBusinessApiKeyForm = (field: keyof BusinessApiKeyFormState, value: string) => {
    setBusinessApiKeyForm((prev) => ({ ...prev, [field]: value }));
  };

  const updateBusinessApiUsageFilter = (field: keyof BusinessApiUsageFilters, value: string) => {
    setBusinessApiKeyUsagePage(1);
    setBusinessApiUsageFilters((prev) => ({ ...prev, [field]: value }));
  };

  const resetBusinessApiUsageFilters = () => {
    setBusinessApiKeyUsagePage(1);
    setBusinessApiUsageFilters(DEFAULT_BUSINESS_API_USAGE_FILTERS);
  };

  const handleExportBusinessApiUsage = async () => {
    setBusinessApiUsageExporting(true);
    setBusinessApiKeyError('');
    try {
      const blob = await adminApi.exportBusinessApiKeyUsage({
        apiKeyId: businessApiUsageFilters.apiKeyId,
        businessKey: businessApiUsageFilters.businessKey,
        endpointKind: businessApiUsageFilters.endpointKind,
        statusGroup: businessApiUsageFilters.statusGroup,
        path: businessApiUsageFilters.path,
        runId: businessApiUsageFilters.runId,
        requestId: businessApiUsageFilters.requestId,
        traceId: businessApiUsageFilters.traceId,
        errorCode: businessApiUsageFilters.errorCode,
        windowHours: businessApiUsageFilters.windowHours,
        limit: 5000,
      });
      downloadBlob(blob, `business-api-usage-${Date.now()}.csv`);
    } catch (err) {
      setBusinessApiKeyError(String((err as Error)?.message || err));
    } finally {
      setBusinessApiUsageExporting(false);
    }
  };

  const handleOpenBusinessRun = (runId?: string | null) => {
    const normalized = String(runId || '').trim();
    if (!normalized) return;
    if (onOpenBusinessRun) {
      onOpenBusinessRun(normalized);
      return;
    }
    onCopy(normalized);
  };

  const handleGenerateBusinessApiKey = () => {
    updateBusinessApiKeyForm('key', generateBusinessApiKeyValue());
  };

  const handleCreateBusinessApiKey = async () => {
    const name = businessApiKeyForm.name.trim();
    const key = businessApiKeyForm.key.trim();
    if (!name || !key) {
      setBusinessApiKeyError('请先填写 Key 名称和 Key 值。');
      return;
    }
    setBusinessApiKeySaving(true);
    setBusinessApiKeyError('');
    setBusinessApiKeyNotice('');
    try {
      await adminApi.createBusinessApiKey({
        name,
        key,
        status: 'active',
        tenantId: businessApiKeyForm.tenantId.trim() || null,
        clientId: businessApiKeyForm.clientId.trim() || null,
        allowedBusinessKeys: parseAllowedBusinessKeys(businessApiKeyForm.allowedBusinessKeys),
        expireAt: normalizeDatetimeLocal(businessApiKeyForm.expireAt),
      });
      setBusinessApiKeyForm(DEFAULT_BUSINESS_API_KEY_FORM);
      setBusinessApiKeyNotice('业务 API Key 已创建。创建后只展示脱敏值，请把完整 Key 交给对应业务方保存。');
      await loadBusinessApiKeyAudit();
    } catch (err) {
      setBusinessApiKeyError(String((err as Error)?.message || err));
    } finally {
      setBusinessApiKeySaving(false);
    }
  };

  const handleToggleBusinessApiKeyStatus = async (row: BusinessApiKey) => {
    const nextStatus = row.status === 'active' ? 'disabled' : 'active';
    setBusinessApiKeySaving(true);
    setBusinessApiKeyError('');
    setBusinessApiKeyNotice('');
    try {
      await adminApi.updateBusinessApiKey(row.id, { status: nextStatus });
      setBusinessApiKeyNotice(`${row.name} 已${nextStatus === 'active' ? '启用' : '停用'}。`);
      await loadBusinessApiKeyAudit();
    } catch (err) {
      setBusinessApiKeyError(String((err as Error)?.message || err));
    } finally {
      setBusinessApiKeySaving(false);
    }
  };

  const activeAbilities = publicAbilities.filter((item) => item.status === 'active');
  const imageAbilities = publicAbilities.filter((item) => {
    const text = `${item.category} ${item.abilityType} ${item.displayName}`.toLowerCase();
    return item.requiresImage || text.includes('image') || text.includes('图');
  });
  const videoAbilities = publicAbilities.filter((item) => {
    const text = `${item.category} ${item.abilityType} ${item.displayName}`.toLowerCase();
    return text.includes('video') || text.includes('视频');
  });
  const textAbilities = publicAbilities.filter((item) => {
    const text = `${item.category} ${item.abilityType} ${item.displayName}`.toLowerCase();
    return text.includes('text') || text.includes('文字') || text.includes('vl') || text.includes('图像理解');
  });
  const firstAbilityId = activeAbilities[0]?.id || '{abilityId}';
  const businessInterfaceRows = BUSINESS_INTERFACE_GROUPS.map((group) => {
    const nativeEndpoints = BUSINESS_ENDPOINTS.filter((item) => item.businessKey === group.key);
    const cozeToolboxes = COZE_TOOLBOX_ENDPOINTS.filter((item) => item.businessKey === group.key);
    const atomicCount = publicAbilities.filter((item) => inferAbilityBusinessKey(item) === group.key).length;
    return {
      ...group,
      nativeEndpoints,
      cozeToolboxes,
      atomicCount,
    };
  });
  const activeBusinessApiKeyCount = businessApiKeys.filter((item) => item.status === 'active').length;
  const failedBusinessApiUsageCount = businessApiKeyUsageSummary.errorCount;
  const recentBusinessApiUsage = businessApiKeyUsage[0];
  const businessApiUsageCount = businessApiKeyUsageSummary.total || businessApiKeyUsageTotal;
  const usagePageCount = Math.max(1, Math.ceil((businessApiKeyUsageTotal || 0) / BUSINESS_API_USAGE_PAGE_SIZE));
  const usagePageStart =
    businessApiKeyUsageTotal > 0 ? (businessApiKeyUsagePage - 1) * BUSINESS_API_USAGE_PAGE_SIZE + 1 : 0;
  const usagePageEnd = Math.min(businessApiKeyUsageTotal, businessApiKeyUsagePage * BUSINESS_API_USAGE_PAGE_SIZE);

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Alert
        theme="info"
        message="中台现在有两种能力应用方式：业务/API 方直接调用中台自有 API；Coze 通过 OpenAPI 工具箱导入。正式业务优先走业务 API，Coze 工具箱继续保留为接入和实验入口。"
      />

      <div className="podi-api-exposure-hero">
        <div>
          <Typography.Text theme="secondary">中台对外能力入口</Typography.Text>
          <Typography.Title level="h3" style={{ margin: '6px 0 8px' }}>
            业务 API、原子能力 API、Coze 工具箱分开管理
          </Typography.Title>
          <Typography.Text theme="secondary">
            业务方不需要理解模型、节点、Coze 或 ComfyUI；中台负责版本、路由、调度、回填、计费和排障。
          </Typography.Text>
        </div>
        <div className="podi-api-exposure-stats">
          <div>
            <span>开放能力</span>
            <strong>{publicAbilities.length}</strong>
            <small>active {activeAbilities.length}</small>
          </div>
          <div>
            <span>Coze 绑定</span>
            <strong>
              {cozeAbilityStats.mapped}/{cozeAbilityStats.total}
            </strong>
            <small>流程 ID</small>
          </div>
          <div>
            <span>能力类型</span>
            <strong>
              {imageAbilities.length}/{videoAbilities.length}/{textAbilities.length}
            </strong>
            <small>图 / 视频 / 文字</small>
          </div>
        </div>
      </div>

      <Card bordered className="podi-api-business-map-card">
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <div>
            <Typography.Text strong>按业务找接口</Typography.Text>
            <div>
              <Typography.Text theme="secondary">
                同一个业务下同时展示原生 API、Coze 工具箱和原子能力数量。业务方优先看原生 API，排障和实验再看后两类。
              </Typography.Text>
            </div>
          </div>
          <div className="podi-api-business-map">
            {businessInterfaceRows.map((group) => (
              <section key={group.key} className={`podi-api-business-card podi-api-business-card--${group.accent}`}>
                <Space direction="vertical" size={8} style={{ width: '100%' }}>
                  <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
                    <Typography.Text strong>{group.name}</Typography.Text>
                    <Tag theme={businessStatusTheme(group.nativeStatus)} variant="light">
                      {businessStatusLabel(group.nativeStatus)}
                    </Tag>
                  </Space>
                  <Typography.Text theme="secondary">{group.summary}</Typography.Text>
                  <div className="podi-api-business-card__metrics">
                    <span>原生 {group.nativeEndpoints.length}</span>
                    <span>Coze {group.cozeToolboxes.length}</span>
                    <span>原子 {group.atomicCount}</span>
                  </div>
                  <div className="podi-api-business-card__paths">
                    {group.nativeEndpoints.slice(0, 2).map((endpoint) => (
                      <button key={endpoint.key} type="button" onClick={() => onCopy(endpoint.path)}>
                        {endpoint.name}
                      </button>
                    ))}
                    {group.cozeToolboxes.slice(0, 1).map((toolbox) => (
                      <button key={toolbox.key} type="button" onClick={() => onCopy(toolbox.path)}>
                        {toolbox.name}
                      </button>
                    ))}
                  </div>
                </Space>
              </section>
            ))}
          </div>
          <div className="podi-api-check-strip">
            {BUSINESS_ONBOARDING_CHECKS.map((item) => (
              <Tag key={item.key} theme={item.theme} variant="light">
                {item.title}
              </Tag>
            ))}
            {API_DELIVERY_GUARDS.map((item) => (
              <Tag key={item.key} theme={deliveryGuardTheme(item.status)} variant="light">
                {item.title}
              </Tag>
            ))}
          </div>
        </Space>
      </Card>

      <div className="podi-api-mode-grid">
        <Card bordered className="podi-api-mode-card podi-api-mode-card--primary">
          <Space direction="vertical" size="small" style={{ width: '100%' }}>
            <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
              <Typography.Text strong>中台自有业务 API</Typography.Text>
              <Tag theme="success" variant="light">
                推荐业务接入
              </Tag>
            </Space>
            <Typography.Text theme="secondary">
              给业务方一个固定入口，传图、参数、回调地址；中台内部切默认版本、灰度、路由和回滚，不需要 Coze 工作流 ID。当前 GPT Image 2 受控裂变固定一次返回 1 张图，多张图请提交多次。
            </Typography.Text>
            <Tag theme="success" variant="light">
              提交后保存 runId，再轮询结果
            </Tag>
            <CodeExample value={buildBusinessRunExample()} onCopy={onCopy} />
            <CodeExample value={buildBusinessQueryExample()} onCopy={onCopy} />
            <details className="podi-api-param-details" open>
              <summary>图裂变参数说明</summary>
              <Table
                rowKey="key"
                size="small"
                data={FISSION_API_PARAMS}
                columns={[
                  {
                    colKey: 'key',
                    title: '参数',
                    width: 160,
                    cell: ({ row }) => <Typography.Text code>{row.key}</Typography.Text>,
                  },
                  {
                    colKey: 'required',
                    title: '是否必填',
                    width: 90,
                    cell: ({ row }) => (
                      <Tag theme={row.required ? 'danger' : 'default'} variant="light">
                        {row.required ? '必填' : '可选'}
                      </Tag>
                    ),
                  },
                  {
                    colKey: 'description',
                    title: '说明',
                    ellipsis: true,
                  },
                  {
                    colKey: 'example',
                    title: '示例',
                    ellipsis: true,
                  },
                ]}
              />
            </details>
            <details className="podi-api-param-details">
              <summary>裂变生成图评估接口</summary>
              <Typography.Text theme="secondary">
                评分接口是独立业务接口：输入原图和结果图，返回 runId 后继续用业务查询接口轮询；它只评分，不自动二次裂变。
              </Typography.Text>
              <CodeExample value={buildFissionEvaluateExample()} onCopy={onCopy} />
              <Table
                rowKey="key"
                size="small"
                data={FISSION_EVALUATE_API_PARAMS}
                columns={[
                  {
                    colKey: 'key',
                    title: '参数',
                    width: 180,
                    cell: ({ row }) => <Typography.Text code>{row.key}</Typography.Text>,
                  },
                  {
                    colKey: 'required',
                    title: '是否必填',
                    width: 90,
                    cell: ({ row }) => (
                      <Tag theme={row.required ? 'danger' : 'default'} variant="light">
                        {row.required ? '必填' : '可选'}
                      </Tag>
                    ),
                  },
                  {
                    colKey: 'description',
                    title: '说明',
                    ellipsis: true,
                  },
                  {
                    colKey: 'example',
                    title: '示例',
                    ellipsis: true,
                  },
                ]}
              />
            </details>
            <details className="podi-api-param-details">
              <summary>兼容 Coze 旧查询方式</summary>
              <Typography.Text theme="secondary">
                业务 API 推荐用 runId 查询；Coze 或内网旧工具箱可以把 runId 当 taskId 调用旧任务查询。
              </Typography.Text>
              <CodeExample value={buildCozeCompatibleQueryExample()} onCopy={onCopy} />
            </details>
            <details className="podi-api-param-details">
              <summary>统一状态和评分枚举</summary>
              <Table
                rowKey="value"
                size="small"
                data={BUSINESS_API_STATUS_DOCS}
                columns={[
                  { colKey: 'field', title: '字段', width: 160 },
                  {
                    colKey: 'value',
                    title: '取值',
                    width: 150,
                    cell: ({ row }) => <Typography.Text code>{row.value}</Typography.Text>,
                  },
                  { colKey: 'meaning', title: '含义', ellipsis: true },
                  { colKey: 'action', title: '业务方动作', ellipsis: true },
                ]}
              />
            </details>
          </Space>
        </Card>
        <Card bordered className="podi-api-mode-card">
          <Space direction="vertical" size="small" style={{ width: '100%' }}>
            <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
              <Typography.Text strong>中台原子能力 API</Typography.Text>
              <Tag theme="primary" variant="light">
                开发 / 编排使用
              </Tag>
            </Space>
            <Typography.Text theme="secondary">
              直接调用某个能力编号，适合内部编排、测评端、高级开发和后续 MCP/技能承载。
            </Typography.Text>
            <CodeExample value={buildAbilityInvokeExample(firstAbilityId)} onCopy={onCopy} />
          </Space>
        </Card>
        <Card bordered className="podi-api-mode-card">
          <Space direction="vertical" size="small" style={{ width: '100%' }}>
            <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
              <Typography.Text strong>Coze 工具箱</Typography.Text>
              <Tag theme="warning" variant="light">
                已接通，少改动
              </Tag>
            </Space>
            <Typography.Text theme="secondary">
              Coze 只导入工具箱，不承载中台治理；后续新业务优先沉淀到中台自有 API。
            </Typography.Text>
            <div className="podi-api-toolbox-highlight">
              <span>主导入地址</span>
              <code>/api/coze/podi/openapi.json</code>
              <CopyButton value="/api/coze/podi/openapi.json" onCopy={onCopy} />
            </div>
          </Space>
        </Card>
      </div>

      <Card bordered>
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Space align="center" style={{ justifyContent: 'space-between', width: '100%', flexWrap: 'wrap' }}>
            <div>
              <Typography.Text strong>业务 API Key 与调用记录</Typography.Text>
              <div>
                <Typography.Text theme="secondary">
                  当前先做身份识别和审计，暂不强制限流；后续计费、套餐和业务方排障都会复用这份记录。
                </Typography.Text>
              </div>
            </div>
            <Button size="small" variant="outline" loading={businessApiKeyLoading} onClick={loadBusinessApiKeyAudit}>
              刷新 Key 记录
            </Button>
          </Space>
          <div className="podi-business-api-key-summary">
            <div>
              <span>业务 Key</span>
              <strong>{businessApiKeys.length}</strong>
              <small>启用 {activeBusinessApiKeyCount}</small>
            </div>
            <div>
              <span>接口调用</span>
              <strong>{formatNumber(businessApiUsageCount)}</strong>
              <small>当前筛选范围</small>
            </div>
            <div>
              <span>提交任务</span>
              <strong>{formatNumber(businessApiKeyUsageSummary.submitCount)}</strong>
              <small>真正发起业务</small>
            </div>
            <div>
              <span>轮询结果</span>
              <strong>{formatNumber(businessApiKeyUsageSummary.pollCount)}</strong>
              <small>查询 runId 结果</small>
            </div>
            <div>
              <span>需关注</span>
              <strong>{formatNumber(failedBusinessApiUsageCount)}</strong>
              <small>状态码异常或有错误码</small>
            </div>
            <div>
              <span>关联任务</span>
              <strong>{formatNumber(businessApiKeyUsageSummary.uniqueRunCount)}</strong>
              <small>去重 runId</small>
            </div>
          </div>
          <div className="podi-business-api-key-form">
            <div className="podi-business-api-key-form__field">
              <label>Key 名称</label>
              <Input
                value={businessApiKeyForm.name}
                placeholder="例如：业务方 A · 图裂变接入"
                onChange={(value) => updateBusinessApiKeyForm('name', String(value))}
              />
            </div>
            <div className="podi-business-api-key-form__field podi-business-api-key-form__field--wide">
              <label>Key 值</label>
              <Space>
                <Input
                  value={businessApiKeyForm.key}
                  placeholder="点击生成，或粘贴已有 Key"
                  onChange={(value) => updateBusinessApiKeyForm('key', String(value))}
                />
                <Button variant="outline" onClick={handleGenerateBusinessApiKey}>
                  生成
                </Button>
              </Space>
            </div>
            <div className="podi-business-api-key-form__field">
              <label>租户 ID</label>
              <Input
                value={businessApiKeyForm.tenantId}
                placeholder="可选，例如 tenant-a"
                onChange={(value) => updateBusinessApiKeyForm('tenantId', String(value))}
              />
            </div>
            <div className="podi-business-api-key-form__field">
              <label>客户端 ID</label>
              <Input
                value={businessApiKeyForm.clientId}
                placeholder="可选，例如 open-api"
                onChange={(value) => updateBusinessApiKeyForm('clientId', String(value))}
              />
            </div>
            <div className="podi-business-api-key-form__field podi-business-api-key-form__field--wide">
              <label>可调用业务</label>
              <Input
                value={businessApiKeyForm.allowedBusinessKeys}
                placeholder="留空表示全部；多个用逗号分隔"
                onChange={(value) => updateBusinessApiKeyForm('allowedBusinessKeys', String(value))}
              />
              <small>常用：fission、fission_evaluate、outpaint、pattern_extract。</small>
            </div>
            <div className="podi-business-api-key-form__field">
              <label>过期时间</label>
              <input
                type="datetime-local"
                value={businessApiKeyForm.expireAt}
                onChange={(event) => updateBusinessApiKeyForm('expireAt', event.currentTarget.value)}
              />
            </div>
            <div className="podi-business-api-key-form__actions">
              <Button theme="primary" loading={businessApiKeySaving} onClick={handleCreateBusinessApiKey}>
                创建业务 Key
              </Button>
              <Typography.Text theme="secondary">完整 Key 只在创建时可见；列表只展示脱敏值和调用记录。</Typography.Text>
            </div>
          </div>
          {businessApiKeyNotice ? <Alert theme="success" message={businessApiKeyNotice} /> : null}
          {businessApiKeyError ? <Alert theme="error" message={businessApiKeyError} /> : null}
          <Table
            rowKey="id"
            size="small"
            data={businessApiKeys}
            loading={businessApiKeyLoading}
            maxHeight={260}
            columns={[
              {
                colKey: 'name',
                title: 'Key',
                cell: ({ row }) => (
                  <Space direction="vertical" size={2}>
                    <Typography.Text>{row.name}</Typography.Text>
                    <Typography.Text theme="secondary">{row.keyPreview || '-'}</Typography.Text>
                  </Space>
                ),
              },
              {
                colKey: 'status',
                title: '状态',
                width: 100,
                cell: ({ row }) => (
                  <Tag theme={apiKeyStatusTheme(row.status)} variant="light">
                    {apiKeyStatusLabel(row.status)}
                  </Tag>
                ),
              },
              {
                colKey: 'scope',
                title: '业务方范围',
                ellipsis: true,
                cell: ({ row }) => (
                  <Space direction="vertical" size={2}>
                    <Typography.Text>{row.tenantId || '未绑定租户'}</Typography.Text>
                    <Typography.Text theme="secondary">{row.clientId || '未绑定客户端'}</Typography.Text>
                  </Space>
                ),
              },
              {
                colKey: 'allowedBusinessKeys',
                title: '可调用业务',
                width: 180,
                cell: ({ row }) =>
                  row.allowedBusinessKeys?.length ? (
                    <Space size={4} breakLine>
                      {row.allowedBusinessKeys.map((item) => (
                        <Tag key={item} size="small">
                          {item}
                        </Tag>
                      ))}
                    </Space>
                  ) : (
                    <Typography.Text theme="secondary">全部业务</Typography.Text>
                  ),
              },
              {
                colKey: 'usageCount',
                title: '累计调用',
                width: 100,
                cell: ({ row }) => <Typography.Text>{row.usageCount || 0}</Typography.Text>,
              },
              {
                colKey: 'expireAt',
                title: '过期时间',
                width: 180,
                cell: ({ row }) => <Typography.Text theme="secondary">{formatDateTime(row.expireAt)}</Typography.Text>,
              },
              {
                colKey: 'operation',
                title: '操作',
                width: 110,
                cell: ({ row }) => (
                  <Button
                    size="small"
                    variant="outline"
                    theme={row.status === 'active' ? 'danger' : 'primary'}
                    loading={businessApiKeySaving}
                    onClick={() => void handleToggleBusinessApiKeyStatus(row)}
                  >
                    {row.status === 'active' ? '停用' : '启用'}
                  </Button>
                ),
              },
            ]}
            empty={<Typography.Text theme="secondary">暂无业务 API Key。后续业务接入前先在这里开 Key。</Typography.Text>}
          />
          <div className="podi-business-api-usage-header">
            <div>
              <Typography.Text strong>接口调用中心</Typography.Text>
              <div>
                <Typography.Text theme="secondary">
                  这里用来判断业务方是否调用了正确接口、是否频繁轮询、失败码是什么，以及每个 runId 背后的完整调用轨迹。
                </Typography.Text>
              </div>
            </div>
            <Space>
              <Typography.Text theme="secondary">
                最近：{recentBusinessApiUsage ? formatDateTime(recentBusinessApiUsage.createdAt) : '暂无调用'}
              </Typography.Text>
              <Button
                size="small"
                variant="outline"
                loading={businessApiUsageExporting}
                onClick={() => void handleExportBusinessApiUsage()}
              >
                导出调用记录
              </Button>
              <Button size="small" variant="outline" onClick={resetBusinessApiUsageFilters}>
                重置筛选
              </Button>
            </Space>
          </div>
          <div className="podi-business-api-usage-filters">
            <label>
              时间窗口
              <select
                value={businessApiUsageFilters.windowHours}
                onChange={(event) => updateBusinessApiUsageFilter('windowHours', event.currentTarget.value)}
              >
                <option value="1">近 1 小时</option>
                <option value="6">近 6 小时</option>
                <option value="24">近 24 小时</option>
                <option value="72">近 72 小时</option>
                <option value="168">近 7 天</option>
                <option value="0">不限制</option>
              </select>
            </label>
            <label>
              业务 Key
              <select
                value={businessApiUsageFilters.apiKeyId}
                onChange={(event) => updateBusinessApiUsageFilter('apiKeyId', event.currentTarget.value)}
              >
                <option value="all">全部 Key</option>
                {businessApiKeys.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              业务类型
              <select
                value={businessApiUsageFilters.businessKey}
                onChange={(event) => updateBusinessApiUsageFilter('businessKey', event.currentTarget.value)}
              >
                <option value="all">全部业务</option>
                <option value="fission">图裂变</option>
                <option value="fission_evaluate">裂变评分</option>
                <option value="outpaint">扩图</option>
                <option value="pattern_extract">花纹提取</option>
              </select>
            </label>
            <label>
              接口动作
              <select
                value={businessApiUsageFilters.endpointKind}
                onChange={(event) => updateBusinessApiUsageFilter('endpointKind', event.currentTarget.value)}
              >
                <option value="all">全部动作</option>
                <option value="submit">提交任务</option>
                <option value="poll">轮询结果</option>
                <option value="callback">回调</option>
              </select>
            </label>
            <label>
              结果
              <select
                value={businessApiUsageFilters.statusGroup}
                onChange={(event) => updateBusinessApiUsageFilter('statusGroup', event.currentTarget.value)}
              >
                <option value="all">全部结果</option>
                <option value="success">成功</option>
                <option value="error">失败或异常</option>
              </select>
            </label>
            <label>
              接口路径
              <Input
                value={businessApiUsageFilters.path}
                placeholder="/api/business/fission/runs"
                onChange={(value) => updateBusinessApiUsageFilter('path', String(value))}
              />
            </label>
            <label>
              runId
              <Input
                value={businessApiUsageFilters.runId}
                placeholder="按任务查"
                onChange={(value) => updateBusinessApiUsageFilter('runId', String(value))}
              />
            </label>
            <label>
              requestId
              <Input
                value={businessApiUsageFilters.requestId}
                placeholder="业务请求 ID"
                onChange={(value) => updateBusinessApiUsageFilter('requestId', String(value))}
              />
            </label>
            <label>
              traceId
              <Input
                value={businessApiUsageFilters.traceId}
                placeholder="链路 ID"
                onChange={(value) => updateBusinessApiUsageFilter('traceId', String(value))}
              />
            </label>
            <label>
              错误码
              <Input
                value={businessApiUsageFilters.errorCode}
                placeholder="BUSINESS_RUN_ID_REQUIRED"
                onChange={(value) => updateBusinessApiUsageFilter('errorCode', String(value))}
              />
            </label>
          </div>
          <Table
            rowKey="runId"
            size="small"
            data={businessApiKeyUsageGroups}
            loading={businessApiKeyLoading}
            maxHeight={260}
            columns={[
              {
                colKey: 'runId',
                title: '按任务聚合',
                ellipsis: true,
                cell: ({ row }) => (
                  <Space direction="vertical" size={2}>
                    <Space>
                      <Typography.Text code>{row.runId || '-'}</Typography.Text>
                      {row.runId ? <CopyButton value={row.runId} onCopy={onCopy} /> : null}
                      {row.runId ? (
                        <Button size="small" variant="text" onClick={() => handleOpenBusinessRun(row.runId)}>
                          打开任务
                        </Button>
                      ) : null}
                    </Space>
                    <Typography.Text theme="secondary">
                      {row.businessKey || '-'} · {row.apiKeyName || '未知 Key'}
                    </Typography.Text>
                  </Space>
                ),
              },
              {
                colKey: 'counts',
                title: '调用构成',
                width: 220,
                cell: ({ row }) => (
                  <Space size={4} breakLine>
                    <Tag size="small" theme="success" variant="light">
                      提交 {row.submitCount || 0}
                    </Tag>
                    <Tag size="small" theme="primary" variant="light">
                      轮询 {row.pollCount || 0}
                    </Tag>
                    <Tag size="small" theme={row.errorCount ? 'danger' : 'default'} variant="light">
                      异常 {row.errorCount || 0}
                    </Tag>
                    <Tag size="small" variant="light">
                      总计 {row.totalCount || 0}
                    </Tag>
                  </Space>
                ),
              },
              {
                colKey: 'issue',
                title: '链路提示',
                width: 220,
                cell: ({ row }) => {
                  const issue = businessApiUsageIssue(row);
                  return issue.needsAttention ? (
                    <Space direction="vertical" size={2}>
                      <Tag size="small" theme="warning" variant="light">
                        {issue.code}
                      </Tag>
                      <Typography.Text theme="secondary">{issue.hint}</Typography.Text>
                    </Space>
                  ) : (
                    <Tag size="small" theme="success" variant="light">
                      暂无异常
                    </Tag>
                  );
                },
              },
              {
                colKey: 'result',
                title: '最后结果',
                width: 150,
                cell: ({ row }) => (
                  <Space direction="vertical" size={2}>
                    <Tag theme={row.lastStatusCode && row.lastStatusCode >= 400 ? 'danger' : 'success'} variant="light">
                      {row.lastStatusCode || '-'}
                    </Tag>
                    {row.lastErrorCode ? <Typography.Text theme="error">{row.lastErrorCode}</Typography.Text> : null}
                  </Space>
                ),
              },
              {
                colKey: 'lastSeenAt',
                title: '最近调用',
                width: 180,
                cell: ({ row }) => <Typography.Text theme="secondary">{formatDateTime(row.lastSeenAt)}</Typography.Text>,
              },
            ]}
            empty={<Typography.Text theme="secondary">当前筛选范围内没有可聚合的 runId。</Typography.Text>}
          />
          <Table
            rowKey="id"
            size="small"
            data={businessApiKeyUsage}
            loading={businessApiKeyLoading}
            maxHeight={320}
            columns={[
              {
                colKey: 'createdAt',
                title: '时间',
                width: 170,
                cell: ({ row }) => <Typography.Text theme="secondary">{formatDateTime(row.createdAt)}</Typography.Text>,
              },
              {
                colKey: 'apiKeyName',
                title: '调用方',
                width: 180,
                cell: ({ row }) => (
                  <Space direction="vertical" size={2}>
                    <Typography.Text>{row.apiKeyName || '未知 Key'}</Typography.Text>
                    <Typography.Text theme="secondary">{row.apiKeyPreview || '-'}</Typography.Text>
                  </Space>
                ),
              },
              {
                colKey: 'path',
                title: '接口',
                ellipsis: true,
                cell: ({ row }) => (
                  <Space direction="vertical" size={2}>
                    <Space>
                      <Tag theme={endpointKindTheme(inferEndpointKind(row.path))} variant="light">
                        {endpointKindLabel(inferEndpointKind(row.path))}
                      </Tag>
                      <Typography.Text>
                        {row.method} {row.path}
                      </Typography.Text>
                    </Space>
                    <Typography.Text theme="secondary">
                      {row.businessKey || '-'} · {row.runId || row.requestId || row.traceId || '-'}
                    </Typography.Text>
                    {row.runId ? (
                      <Button size="small" variant="text" onClick={() => handleOpenBusinessRun(row.runId)}>
                        打开业务任务
                      </Button>
                    ) : null}
                  </Space>
                ),
              },
              {
                colKey: 'statusCode',
                title: '结果',
                width: 120,
                cell: ({ row }) => (
                  <Space direction="vertical" size={2}>
                    <Tag theme={row.statusCode && row.statusCode >= 400 ? 'danger' : 'success'} variant="light">
                      {row.statusCode || '-'}
                    </Tag>
                    {row.errorCode ? <Typography.Text theme="error">{row.errorCode}</Typography.Text> : null}
                  </Space>
                ),
              },
              {
                colKey: 'durationMs',
                title: '耗时',
                width: 90,
                cell: ({ row }) => <Typography.Text>{row.durationMs == null ? '-' : `${row.durationMs}ms`}</Typography.Text>,
              },
            ]}
            empty={<Typography.Text theme="secondary">暂无调用记录。业务 API Key 调用业务接口后会自动写入。</Typography.Text>}
          />
          <div className="podi-business-api-usage-pagination">
            <Typography.Text theme="secondary">
              显示 {usagePageStart}-{usagePageEnd} / {businessApiKeyUsageTotal}
            </Typography.Text>
            <Space>
              <Button
                size="small"
                variant="outline"
                disabled={businessApiKeyUsagePage <= 1}
                onClick={() => setBusinessApiKeyUsagePage((prev) => Math.max(1, prev - 1))}
              >
                上一页
              </Button>
              <Typography.Text>
                第 {businessApiKeyUsagePage} / {usagePageCount} 页
              </Typography.Text>
              <Button
                size="small"
                variant="outline"
                disabled={businessApiKeyUsagePage >= usagePageCount}
                onClick={() => setBusinessApiKeyUsagePage((prev) => Math.min(usagePageCount, prev + 1))}
              >
                下一页
              </Button>
            </Space>
          </div>
        </Space>
      </Card>

      <Card bordered>
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Space align="center" style={{ justifyContent: 'space-between', width: '100%', flexWrap: 'wrap' }}>
            <div>
              <Typography.Text strong>中台自有 API 清单</Typography.Text>
              <div>
                <Typography.Text theme="secondary">业务 API 是对业务方稳定承诺；原子能力 API 是能力内核入口。</Typography.Text>
              </div>
            </div>
            <Button size="small" variant="outline" loading={publicAbilitiesLoading} onClick={onRefreshPublicAbilities}>
              刷新能力清单
            </Button>
          </Space>
          <Table
            rowKey="key"
            size="small"
            data={[...BUSINESS_ENDPOINTS, ...ABILITY_ENDPOINTS]}
            columns={[
              {
                colKey: 'name',
                title: '接口',
                cell: ({ row }) => (
                  <Space direction="vertical" size={2}>
                    <Typography.Text>{row.name}</Typography.Text>
                    <Typography.Text theme="secondary">{row.audience}</Typography.Text>
                  </Space>
                ),
              },
              {
                colKey: 'method',
                title: '方式',
                width: 90,
                cell: ({ row }) => (
                  <Tag theme={methodTheme(row.method)} variant="light">
                    {row.method}
                  </Tag>
                ),
              },
              {
                colKey: 'path',
                title: '地址',
                ellipsis: true,
                cell: ({ row }) => (
                  <Space>
                    <Typography.Text code>{row.path}</Typography.Text>
                    <CopyButton value={row.path} onCopy={onCopy} />
                  </Space>
                ),
              },
              {
                colKey: 'purpose',
                title: '用途',
                ellipsis: true,
              },
            ]}
          />
        </Space>
      </Card>

      <Card bordered>
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Space align="center" style={{ justifyContent: 'space-between', width: '100%', flexWrap: 'wrap' }}>
            <div>
              <Typography.Text strong>开放能力编号</Typography.Text>
              <div>
                <Typography.Text theme="secondary">调用原子能力 API 时必须使用这里的能力编号，不要让业务方自己拼底层工作流。</Typography.Text>
              </div>
            </div>
            <Space>
              <Tag theme="success" variant="light">
                图片 {imageAbilities.length}
              </Tag>
              <Tag theme="primary" variant="light">
                视频 {videoAbilities.length}
              </Tag>
              <Tag theme="default" variant="light">
                文字/VL {textAbilities.length}
              </Tag>
            </Space>
          </Space>
          <Table
            rowKey="id"
            size="small"
            data={publicAbilities.slice(0, 12)}
            loading={publicAbilitiesLoading}
            maxHeight={420}
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
                  </Space>
                ),
              },
              {
                colKey: 'id',
                title: '能力编号',
                width: 360,
                cell: ({ row }) => (
                  <Space>
                    <Typography.Text code>{row.id}</Typography.Text>
                    <CopyButton value={row.id} onCopy={onCopy} />
                  </Space>
                ),
              },
              {
                colKey: 'status',
                title: '状态',
                width: 120,
                cell: ({ row }) => (
                  <Tag theme={row.status === 'active' ? 'success' : 'default'} variant="light">
                    {row.status === 'active' ? '可调用' : row.status}
                  </Tag>
                ),
              },
              {
                colKey: 'features',
                title: '输入能力',
                width: 220,
                cell: ({ row }) => (
                  <Space size={4} breakLine>
                    {row.requiresImage ? <Tag size="small">需要图片</Tag> : null}
                    {row.supportsMultipleImages ? <Tag size="small">支持多图</Tag> : null}
                    {row.maxOutputImages ? <Tag size="small">最多 {row.maxOutputImages} 张</Tag> : null}
                    {!row.requiresImage && !row.supportsMultipleImages && !row.maxOutputImages ? (
                      <Typography.Text theme="secondary">按表单字段</Typography.Text>
                    ) : null}
                  </Space>
                ),
              },
            ]}
            empty={<Typography.Text theme="secondary">暂无开放能力，请先在能力目录启用能力。</Typography.Text>}
          />
          {publicAbilities.length > 12 ? (
            <Typography.Text theme="secondary">这里只展示前 12 个能力；完整清单可通过 `GET /api/abilities` 或“能力目录”查看。</Typography.Text>
          ) : null}
        </Space>
      </Card>

      <Card bordered>
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <div>
            <Typography.Text strong>Coze 工具箱导入地址</Typography.Text>
            <div>
              <Typography.Text theme="secondary">这条链路当前只做可见和校验，不作为下一阶段重点改造对象。</Typography.Text>
            </div>
          </div>
          <Table
            rowKey="key"
            size="small"
            data={COZE_TOOLBOX_ENDPOINTS}
            columns={[
              {
                colKey: 'name',
                title: '工具箱',
                cell: ({ row }) => (
                  <Space direction="vertical" size={2}>
                    <Typography.Text>{row.name}</Typography.Text>
                    <Typography.Text theme="secondary">{row.purpose}</Typography.Text>
                  </Space>
                ),
              },
              {
                colKey: 'status',
                title: '定位',
                width: 130,
                cell: ({ row }) => (
                  <Tag theme={toolboxStatusTheme(row.status)} variant="light">
                    {row.status}
                  </Tag>
                ),
              },
              {
                colKey: 'path',
                title: '地址',
                ellipsis: true,
                cell: ({ row }) => (
                  <Space>
                    <Typography.Text code>{row.path}</Typography.Text>
                    <CopyButton value={row.path} onCopy={onCopy} />
                  </Space>
                ),
              },
            ]}
          />
        </Space>
      </Card>
    </Space>
  );
}
