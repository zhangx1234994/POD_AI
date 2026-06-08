import { useCallback, useEffect, useState } from 'react';
import { Alert, Button, Card, Input, Space, Table, Tag, Typography } from 'tdesign-react';
import { adminApi } from '../../../services/adminApi';
import type {
  BusinessApiContractEnumDoc,
  BusinessApiKey,
  BusinessApiKeyUsageLog,
  BusinessApiKeyUsageRunGroup,
  BusinessApiKeyUsageSummary,
  BusinessDeliveryContractAuditItem,
  BusinessDeliveryContractAuditResponse,
  BusinessFeatureReleaseCheck,
  PublicAbility,
} from '../../../types/admin';
import { businessKeyLabel } from './businessLabels';

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

type BusinessApiEnumDoc = BusinessApiContractEnumDoc;

type BusinessDeliveryContract = {
  key: string;
  name: string;
  path: string;
  docsPath: string;
  sampleFiles: string[];
  enumFields: string[];
  errorCodes: string[];
  note: string;
  audit?: BusinessDeliveryContractAuditItem | null;
};

type BusinessDeliveryContractState = {
  ok: boolean;
  missingSamples: string[];
  missingEnums: string[];
  missingErrorCodes: boolean;
  summary: string;
  requiredEvidence: string[];
};

type FeatureReleaseChecklistItem = {
  key: string;
  name: string;
  entry: string;
  mustCheck: string[];
  releaseEvidence: string;
  currentRisk: string;
  status: DeliveryGuardStatus;
  summary?: string;
  blockers?: string[];
  warnings?: string[];
  evidence?: BusinessFeatureReleaseCheck['evidence'];
  businessKey?: string | null;
  version?: string | null;
  requiresGpuRun?: boolean;
  costSensitive?: boolean;
};

type DeliveryGuardStatus = 'done' | 'doing' | 'todo';
type DeliveryDecisionStatus = 'ready' | 'attention' | 'blocked';

type DeliveryGuard = {
  key: string;
  title: string;
  detail: string;
  status: DeliveryGuardStatus;
  owner: string;
  action: string;
};

type DeliveryDecision = {
  status: DeliveryDecisionStatus;
  title: string;
  summary: string;
  risk: string;
  action: string;
  details: string[];
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
    key: 'fission',
    name: '图裂变',
    summary: '基于原图生成变化图、风格变体或高质量裂变图。',
    nativeStatus: 'ready',
    accent: 'success',
  },
  {
    key: 'image_edit',
    name: '图编辑',
    summary: '组件型通用改图入口，支持标注、参考图、蒙版和编辑指令。',
    nativeStatus: 'ready',
    accent: 'success',
  },
  {
    key: 'fission_evaluate',
    name: '裂变评分',
    summary: '评估裂变结果质量和逻辑合理性，辅助业务决定是否重跑。',
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
    businessKey: 'fission',
  },
  {
    key: 'image-edit-run',
    name: '图编辑',
    method: 'POST',
    path: '/api/business/image-edit/runs',
    purpose: '提交组件型改图任务，返回 runId 后查询结果。',
    audience: '业务主入口 / 托管组件',
    businessKey: 'image_edit',
  },
  {
    key: 'fission-evaluate-run',
    name: '裂变生成图评估',
    method: 'POST',
    path: '/api/business/fission-evaluate/runs',
    purpose: '输入原图和裂变结果图，判断质量和逻辑是否通过。',
    audience: '业务主入口 / 质检',
    businessKey: 'fission_evaluate',
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
    businessKey: 'fission',
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

const FALLBACK_BUSINESS_API_STATUS_DOCS: BusinessApiEnumDoc[] = [
  { field: 'status / taskStatus', value: 'queued', meaning: '已进入中台队列，还没开始执行。', action: '按 retryAfterSeconds 继续查询。' },
  { field: 'status / taskStatus', value: 'running', meaning: '正在执行或等待结果回填。', action: '按 retryAfterSeconds 继续查询。' },
  { field: 'status / taskStatus', value: 'succeeded', meaning: '任务成功，结果字段可读取。', action: '读取 imageUrls / videoUrls / texts / resultPayload。' },
  { field: 'status / taskStatus', value: 'failed', meaning: '任务失败或无法继续。', action: '读取 errorCode / errorMessage，并按错误码处理。' },
  { field: 'variation_strength', value: 'conservative', meaning: 'GPT Image 2 保守裂变，更接近原图。', action: '希望变化小的时候使用。' },
  { field: 'variation_strength', value: 'same_series', meaning: 'GPT Image 2 同系列裂变，默认推荐。', action: '常规业务优先使用。' },
  { field: 'variation_strength', value: 'creative_same_series', meaning: 'GPT Image 2 更开放的同系列变化。', action: '需要更明显变化时使用。' },
  { field: 'quality', value: 'preview', meaning: '快速预览档。', action: '适合内部测试和批量初筛。' },
  { field: 'quality', value: 'candidate', meaning: '候选质量档。', action: '适合交给业务方看效果。' },
  { field: 'quality', value: 'premium', meaning: '高质量档。', action: '成本更高，正式精品样本再用。' },
  { field: 'size', value: 'auto', meaning: '默认按原图尺寸和比例处理。', action: '不确定尺寸时优先使用。' },
  { field: 'size', value: '1024x1024 / 1536x1024 / 1024x1536', meaning: '常用 1K 正方形、横图、竖图。', action: '业务明确尺寸时传入。' },
  { field: 'profile', value: 'pattern_risk_routed_v4', meaning: 'ComfyUI 智能风险路由，默认推荐。', action: '常规裂变优先使用。' },
  { field: 'profile', value: 'pattern_color_lock_strict_v2', meaning: '严格颜色锁定，更像原图但裂变感更弱。', action: '颜色一致性要求高时使用。' },
  { field: 'variation_preset', value: 'default-high', meaning: '高幅度默认配置。', action: '希望变化明显时使用。' },
  { field: 'variation_preset', value: 'safe', meaning: '保守稳定配置。', action: '希望更接近原图时使用。' },
  { field: 'variation_preset', value: 'object-strong', meaning: '对象变化更强。', action: '主体变化不足时使用。' },
  { field: 'variation_preset', value: 'color-free', meaning: '配色更自由。', action: '颜色不需要强锁定时使用。' },
  { field: 'decision', value: 'pass', meaning: '裂变评分通过。', action: '可以接受当前生成图。' },
  { field: 'decision', value: 'needs_refission', meaning: '建议二次裂变。', action: '业务侧可重新提交裂变任务。' },
  { field: 'decision', value: 'reject', meaning: '不建议使用。', action: '拒绝当前结果或人工复核。' },
  { field: 'endpoint_kind', value: 'submit', meaning: '业务方提交任务。', action: '用于确认任务是否真正进入中台。' },
  { field: 'endpoint_kind', value: 'poll', meaning: '业务方查询结果。', action: '用于判断是否按 retryAfterSeconds 合理轮询。' },
  { field: 'endpoint_kind', value: 'callback', meaning: '业务回调相关请求。', action: '用于排查终态通知。' },
  { field: 'status_group', value: 'success', meaning: 'HTTP 成功且没有平台错误码。', action: '可继续看业务任务详情。' },
  { field: 'status_group', value: 'error', meaning: 'HTTP 异常或存在平台错误码。', action: '按错误码和 runId 排查。' },
  { field: 'issueCode', value: 'HAS_ERROR', meaning: '同一个 runId 链路中存在错误。', action: '打开业务任务详情，先看失败步骤。' },
  { field: 'issueCode', value: 'POLL_WITHOUT_SUBMIT', meaning: '当前窗口只看到查询，没有看到提交。', action: '放宽时间窗口或核对 runId。' },
  { field: 'issueCode', value: 'POLLING_TOO_FREQUENT', meaning: '同一个 runId 轮询次数偏高。', action: '业务方应按 retryAfterSeconds 控制查询频率。' },
];

const REQUIRED_BUSINESS_API_ENUM_FIELDS = [
  'status / taskStatus',
  'variation_strength',
  'quality',
  'size',
  'profile',
  'variation_preset',
  'decision',
  'endpoint_kind',
  'status_group',
  'issueCode',
];

const REQUIRED_DELIVERY_SAMPLE_FILES = [
  'request.example.json',
  'submit.response.example.json',
  'poll.request.example.json',
  'poll.running.response.example.json',
  'poll.succeeded.response.example.json',
  'poll.failed.response.example.json',
];

const BUSINESS_DELIVERY_CONTRACTS: BusinessDeliveryContract[] = [
  {
    key: 'gpt-image2-fission',
    name: 'GPT Image 2 + VL 受控裂变',
    path: '/api/business/fission/runs',
    docsPath: 'docs/api/examples/fission-business-delivery/01_gpt_image2_controlled_fission/README.md',
    sampleFiles: REQUIRED_DELIVERY_SAMPLE_FILES,
    enumFields: ['status / taskStatus', 'variation_strength', 'quality', 'size'],
    errorCodes: [
      'BUSINESS_IMAGE_URL_REQUIRED',
      'BUSINESS_RUN_TEMPORARY_UNAVAILABLE',
      'VENDOR_API_EXECUTION_FAILED',
    ],
    note: '一次请求固定一张图；多图请提交多次，得到多个 runId。',
  },
  {
    key: 'comfyui-colorlock-fission',
    name: 'ComfyUI 颜色锁定裂变',
    path: '/api/business/fission/runs',
    docsPath: 'docs/api/examples/fission-business-delivery/02_comfyui_colorlock_fission/README.md',
    sampleFiles: REQUIRED_DELIVERY_SAMPLE_FILES,
    enumFields: ['status / taskStatus', 'profile', 'variation_preset'],
    errorCodes: [
      'BUSINESS_IMAGE_URL_REQUIRED',
      'COMFYUI_TIMEOUT',
      'ABILITY_TASK_FAILED',
    ],
    note: '沿用重绘幅度约定；颜色锁定默认开启，参数区间只做建议不硬拦。',
  },
  {
    key: 'fission-score',
    name: '裂变生成图评估',
    path: '/api/business/fission-evaluate/runs',
    docsPath: 'docs/api/examples/fission-business-delivery/03_fission_generated_image_score/README.md',
    sampleFiles: REQUIRED_DELIVERY_SAMPLE_FILES,
    enumFields: ['status / taskStatus', 'decision'],
    errorCodes: [
      'VL_EVAL_IMAGE_REQUIRED',
      'ABILITY_TASK_FAILED',
    ],
    note: '只负责评分，不自动二次裂变；业务方自行决定是否重跑裂变。',
  },
];

const FEATURE_RELEASE_CHECKLIST: FeatureReleaseChecklistItem[] = [
  {
    key: 'gpt-image2-vl-controlled',
    name: 'GPT Image 2 + VL 受控裂变',
    entry: '/api/business/fission/runs',
    mustCheck: [
      '参数：imageUrl、variation_strength、quality、size、maskUrl',
      '默认：一次请求固定一张图，多图必须提交多次',
      '结果：默认轻量返回，detail=full 才看底层步骤',
      '页面：名称不随版本改动，尺寸默认跟原图走',
    ],
    releaseEvidence: '交付目录 01 + 业务任务 runId + OpenAI 能力调用记录',
    currentRisk: '商业模型质量波动属于模型侧；平台重点确认入参、出参、轮询和错误码。',
    status: 'done',
  },
  {
    key: 'comfyui-colorlock',
    name: 'ComfyUI 颜色锁定裂变',
    entry: '/api/business/fission/runs',
    mustCheck: [
      '参数：bili、width、height、profile、variation_preset、reference_lock、color_lock',
      '默认：bili 是重绘幅度，按约定映射 denoise，不叫相似度',
      '节点：158/233 都要通过 workflow 兼容检查',
      '结果：OSS 回填，测评端能并排或滑块查看原图/结果图',
    ],
    releaseEvidence: '交付目录 02 + ComfyUI workflow 兼容检查 + 业务样本包',
    currentRisk: '如果 233 缺 String 等自定义节点，必须先补节点或明确降级，不把双机视为完全健康。',
    status: 'doing',
  },
  {
    key: 'fission-score',
    name: '裂变生成图评估',
    entry: '/api/business/fission-evaluate/runs',
    mustCheck: [
      '参数：originalImageUrl、generatedImageUrl、context',
      '枚举：decision 必须能解释通过、需复核、不通过',
      '结果：评分文本和结构化 JSON 都能被业务读取',
      '错误：缺原图或结果图返回 VL_EVAL_IMAGE_REQUIRED',
    ],
    releaseEvidence: '交付目录 03 + 裂变任务结果图 + 评分 runId',
    currentRisk: '评分只给判断，不自动二次裂变；业务编排自行决定是否重跑。',
    status: 'done',
  },
  {
    key: 'legacy-seamless-fission',
    name: '旧四方连续裂变',
    entry: 'Coze 工具箱 / 既有工作流',
    mustCheck: [
      '节点：String、KSampler、SaveImage 等必需节点在目标机器存在',
      '路由：158/233 不应长期只命中一台机器',
      '失败：队列满或节点缺失要给可读错误',
      '回填：生图完成后必须能进入任务查询结果',
    ],
    releaseEvidence: 'Coze 工作流巡检 + ComfyUI 兼容检查 + 能力调用记录',
    currentRisk: '该类仍依赖旧工作流，优先用 workflow-compatibility 检查节点差异。',
    status: 'doing',
  },
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
    businessKey: 'fission',
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

function buildBusinessApiContractChecks(enumDocs: BusinessApiEnumDoc[]): DeliveryGuard[] {
  const enumFields = new Set(enumDocs.map((item) => item.field));
  const missingEnums = REQUIRED_BUSINESS_API_ENUM_FIELDS.filter((field) => !enumFields.has(field));
  const incompleteDeliveryContracts = BUSINESS_DELIVERY_CONTRACTS.filter((item) => {
    const missingContractEnums = item.enumFields.filter((field) => !enumFields.has(field));
    return (
      missingContractEnums.length > 0 ||
      REQUIRED_DELIVERY_SAMPLE_FILES.some((file) => !item.sampleFiles.includes(file)) ||
      item.errorCodes.length === 0
    );
  });
  return [
    {
      key: 'business-api-enums',
      title: missingEnums.length ? '枚举缺口' : '枚举已固化',
      detail: missingEnums.length
        ? `缺少这些字段的枚举说明：${missingEnums.join('、')}`
        : '任务状态、裂变参数、评分结果、接口调用中心枚举已经统一展示；文档真源是 docs/standards/business-api-enums.md。',
      status: missingEnums.length ? 'todo' : 'done',
      owner: '接口契约',
      action: '新增字段时，先补枚举文档，再同步页面和交付包。',
    },
    {
      key: 'business-api-examples',
      title: incompleteDeliveryContracts.length ? '交付样例有缺口' : '样例已覆盖',
      detail: incompleteDeliveryContracts.length
        ? `这些接口交付材料仍需补齐：${incompleteDeliveryContracts.map((item) => item.name).join('、')}`
        : '三个交付接口均按独立目录提供提交请求、查询请求、提交返回、排队中、成功、失败返回。',
      status: incompleteDeliveryContracts.length ? 'todo' : 'done',
      owner: '交付材料',
      action: '新增业务接口必须补齐同样 6 类 JSON 样例。',
    },
    {
      key: 'business-api-smoke',
      title: '发版自检已覆盖',
      detail: 'podi_release_smoke.py 已增加 business_api_usage_center，检查接口调用中心可访问、分页正常、runId 聚合可用。',
      status: 'done',
      owner: '上线检查',
      action: '上线后必须看该检查项；失败时先修接口调用中心，不继续发版。',
    },
  ];
}

function businessDeliveryContractState(row: BusinessDeliveryContract): BusinessDeliveryContractState {
  if (row.audit) {
    const missingSamples = row.audit.missingSamples || [];
    const missingEnums = [...(row.audit.missingEnums || []), ...(row.audit.missingEnumSource || [])];
    const missingErrorCodes = (row.audit.missingErrorCodes || []).length > 0 || (row.audit.missingErrorCatalog || []).length > 0;
    return {
      ok: Boolean(row.audit.ok),
      missingSamples,
      missingEnums,
      missingErrorCodes,
      requiredEvidence: row.audit.requiredEvidence?.length ? row.audit.requiredEvidence : [`文档：${row.docsPath}`],
      summary: row.audit.summary || (row.audit.ok ? '请求、响应、错误、枚举都已覆盖。' : '交付材料存在缺口。'),
    };
  }
  const enumFields = new Set(FALLBACK_BUSINESS_API_STATUS_DOCS.map((item) => item.field));
  const missingSamples = REQUIRED_DELIVERY_SAMPLE_FILES.filter((file) => !row.sampleFiles.includes(file));
  const missingEnums = row.enumFields.filter((field) => !enumFields.has(field));
  const missingErrorCodes = row.errorCodes.length === 0;
  const ok = missingSamples.length === 0 && missingEnums.length === 0 && !missingErrorCodes;
  const requiredEvidence = [
    `文档：${row.docsPath}`,
    `样例：${REQUIRED_DELIVERY_SAMPLE_FILES.join('、')}`,
    `枚举：${row.enumFields.join('、') || '无'}`,
    `错误码：${row.errorCodes.join('、') || '无'}`,
    '总表：docs/standards/business-api-enums.md、docs/standards/error-catalog.md',
  ];
  return {
    ok,
    missingSamples,
    missingEnums,
    missingErrorCodes,
    requiredEvidence,
    summary: ok
      ? '请求、响应、错误、枚举都已覆盖。'
      : [
          missingSamples.length ? `缺样例 ${missingSamples.join('、')}` : '',
          missingEnums.length ? `缺枚举 ${missingEnums.join('、')}` : '',
          missingErrorCodes ? '缺错误码' : '',
        ].filter(Boolean).join('；'),
  };
}

function businessDeliveryGapMessages(rows: BusinessDeliveryContract[]): string[] {
  return rows.flatMap((row) => {
    const state = businessDeliveryContractState(row);
    if (state.ok) return [];
    return [`${row.name}：${state.summary}`];
  });
}

function deliveryDecisionTheme(status: DeliveryDecisionStatus): 'success' | 'warning' | 'danger' {
  if (status === 'ready') return 'success';
  if (status === 'attention') return 'warning';
  return 'danger';
}

function deliveryDecisionLabel(status: DeliveryDecisionStatus): string {
  if (status === 'ready') return '可交付';
  if (status === 'attention') return '需复核';
  return '暂缓交付';
}

function buildDeliveryDecision({
  contractChecks,
  deliveryContracts,
  releaseChecklist,
  activeKeyCount,
  usageCount,
  pollingTooFrequent,
}: {
  contractChecks: DeliveryGuard[];
  deliveryContracts: BusinessDeliveryContract[];
  releaseChecklist: FeatureReleaseChecklistItem[];
  activeKeyCount: number;
  usageCount: number;
  pollingTooFrequent: boolean;
}): DeliveryDecision {
  const contractGaps = contractChecks.filter((item) => item.status === 'todo');
  const deliveryGaps = deliveryContracts.filter((item) => !businessDeliveryContractState(item).ok);
  const reviewFeatures = releaseChecklist.filter((item) => item.status !== 'done');
  const details = [
    ...contractGaps.map((item) => `${item.title}：${item.detail}`),
    ...deliveryGaps.map((item) => `${item.name}：${businessDeliveryContractState(item).summary}`),
    ...reviewFeatures.map((item) => `${item.name}：${item.currentRisk}`),
  ];

  if (contractGaps.length > 0 || deliveryGaps.length > 0) {
    return {
      status: 'blocked',
      title: '对外材料还不能直接交付',
      summary: `存在 ${contractGaps.length + deliveryGaps.length} 个接口契约或样例缺口。`,
      risk: '业务方拿到文档后可能不知道状态、错误或参数枚举怎么处理。',
      action: '先补齐枚举、JSON 样例和错误码，再输出交付包。',
      details,
    };
  }

  if (reviewFeatures.length > 0 || pollingTooFrequent || activeKeyCount === 0) {
    const warnings = [
      reviewFeatures.length ? `${reviewFeatures.length} 个功能发版前仍需复核` : '',
      pollingTooFrequent ? '当前窗口轮询频率偏高' : '',
      activeKeyCount === 0 ? '还没有启用的业务 API Key' : '',
    ].filter(Boolean);
    return {
      status: 'attention',
      title: '接口材料可用，但上线前还要复核',
      summary: warnings.join('；') || '存在上线前提醒。',
      risk: pollingTooFrequent
        ? '业务方过频查询会拖慢接口调用中心和数据库查询。'
        : '功能或 Key 状态没有完全闭环，容易在真实接入时漏看。',
      action: activeKeyCount === 0
        ? '先创建业务 Key，再让业务方用真实 Key 跑一次提交和查询。'
        : '按逐功能上线检查表完成复核，并保留 runId 证据。',
      details,
    };
  }

  return {
    status: 'ready',
    title: usageCount > 0 ? '业务接口具备交付条件' : '业务接口材料已就绪',
    summary: usageCount > 0 ? '已有接口调用记录，材料、枚举、样例和调用中心都能闭环。' : '当前暂无真实调用，但交付材料、枚举和页面检查均已通过。',
    risk: '继续关注真实业务的轮询频率、失败码和结果回填。',
    action: '交付时让业务方保存 runId，并按页面示例完成提交和查询。',
    details,
  };
}

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
  allowedBusinessKeys: 'fission,product_design,image_edit,image_edit_chat,fission_evaluate,outpaint,pattern_extract,text_fission',
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
  if (/图编辑|图像编辑|改图|image[-_ ]?edit|editor/.test(text)) return 'image_edit';
  if (/裂变|fission|variation|softstyle|e7/.test(text)) return 'fission';
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

function businessApiRunStatusLabel(value?: string | null): string {
  if (value === 'queued' || value === 'pending' || value === 'planned') return '排队中';
  if (value === 'running') return '运行中';
  if (value === 'succeeded') return '成功';
  if (value === 'failed') return '失败';
  if (value === 'timeout') return '超时';
  if (value === 'cancelled' || value === 'canceled') return '已取消';
  return value || '未关联任务';
}

function businessApiRunStatusTheme(value?: string | null): 'success' | 'primary' | 'warning' | 'danger' | 'default' {
  if (value === 'succeeded') return 'success';
  if (value === 'running') return 'primary';
  if (value === 'queued' || value === 'pending' || value === 'planned') return 'warning';
  if (value === 'failed' || value === 'timeout' || value === 'cancelled' || value === 'canceled') return 'danger';
  return 'default';
}

function businessApiRunResultLabel(row: BusinessApiKeyUsageRunGroup): string {
  const imageCount = Number(row.resultImageCount || 0);
  const videoCount = Number(row.resultVideoCount || 0);
  const textCount = Number(row.resultTextCount || 0);
  const parts = [
    imageCount > 0 ? `${imageCount} 张图` : '',
    videoCount > 0 ? `${videoCount} 个视频` : '',
    textCount > 0 ? `${textCount} 条文字` : '',
  ].filter(Boolean);
  return parts.join(' / ') || '暂无结果';
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
  if (row.runStatus === 'failed' || row.runStatus === 'timeout' || row.runStatus === 'cancelled') {
    return { needsAttention: true, code: 'BUSINESS_RUN_FAILED', hint: row.runError || '接口提交成功，但业务任务最终失败。' };
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
  const [businessApiQuickLookup, setBusinessApiQuickLookup] = useState('');
  const [businessApiKeyLoading, setBusinessApiKeyLoading] = useState(false);
  const [businessApiUsageExporting, setBusinessApiUsageExporting] = useState(false);
  const [businessApiKeySaving, setBusinessApiKeySaving] = useState(false);
  const [businessApiKeyError, setBusinessApiKeyError] = useState('');
  const [businessApiKeyNotice, setBusinessApiKeyNotice] = useState('');
  const [businessApiKeyForm, setBusinessApiKeyForm] = useState<BusinessApiKeyFormState>(DEFAULT_BUSINESS_API_KEY_FORM);
  const [businessDeliveryAudit, setBusinessDeliveryAudit] = useState<BusinessDeliveryContractAuditResponse | null>(null);
  const [businessDeliveryAuditError, setBusinessDeliveryAuditError] = useState('');

  const loadBusinessDeliveryAudit = useCallback(async () => {
    setBusinessDeliveryAuditError('');
    try {
      const res = await adminApi.getBusinessDeliveryContracts();
      setBusinessDeliveryAudit(res);
    } catch (err) {
      setBusinessDeliveryAuditError(String((err as Error)?.message || err));
    }
  }, []);

  useEffect(() => {
    void loadBusinessDeliveryAudit();
  }, [loadBusinessDeliveryAudit]);

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
      setBusinessApiKeyUsageTotal(usageRes.pagination?.total ?? usageRes.total ?? 0);
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
    setBusinessApiQuickLookup('');
  };

  const applyBusinessApiQuickLookup = (field: 'runId' | 'requestId' | 'traceId') => {
    const value = businessApiQuickLookup.trim();
    if (!value) {
      setBusinessApiKeyError('请先粘贴 runId、requestId 或 traceId。');
      return;
    }
    setBusinessApiKeyUsagePage(1);
    setBusinessApiKeyError('');
    setBusinessApiUsageFilters((prev) => ({
      ...prev,
      windowHours: '0',
      runId: field === 'runId' ? value : '',
      requestId: field === 'requestId' ? value : '',
      traceId: field === 'traceId' ? value : '',
    }));
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

  const handleCopyBusinessApiRunEvidence = (row: BusinessApiKeyUsageRunGroup) => {
    const issue = businessApiUsageIssue(row);
    onCopy(
      [
        `runId: ${row.runId || '-'}`,
        `业务: ${businessKeyLabel(row.businessKey || '')}`,
        `版本: ${row.runVersion || '-'}`,
        `状态: ${businessApiRunStatusLabel(row.runStatus)}`,
        `调用方: ${row.apiKeyName || '-'} ${row.apiKeyPreview || ''}`.trim(),
        `提交/轮询/回调/异常: ${row.submitCount || 0}/${row.pollCount || 0}/${row.callbackCount || 0}/${row.errorCount || 0}`,
        `结果: ${businessApiRunResultLabel(row)}`,
        `提示: ${issue.hint || '暂无异常'}`,
      ].join('\n'),
    );
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
  const businessApiRunIssueCount = businessApiKeyUsageGroups.filter((row) => businessApiUsageIssue(row).needsAttention).length;
  const recentBusinessApiUsage = businessApiKeyUsage[0];
  const businessApiUsageCount = businessApiKeyUsageSummary.total || businessApiKeyUsageTotal;
  const usagePageCount = Math.max(1, Math.ceil((businessApiKeyUsageTotal || 0) / BUSINESS_API_USAGE_PAGE_SIZE));
  const usagePageStart =
    businessApiKeyUsageTotal > 0 ? (businessApiKeyUsagePage - 1) * BUSINESS_API_USAGE_PAGE_SIZE + 1 : 0;
  const usagePageEnd = Math.min(businessApiKeyUsageTotal, businessApiKeyUsagePage * BUSINESS_API_USAGE_PAGE_SIZE);
  const businessApiPollingRatio =
    businessApiKeyUsageSummary.submitCount > 0
      ? businessApiKeyUsageSummary.pollCount / businessApiKeyUsageSummary.submitCount
      : businessApiKeyUsageSummary.pollCount > 0
        ? businessApiKeyUsageSummary.pollCount
        : 0;
  const businessApiPollingTooFrequent = businessApiPollingRatio >= 30;
  const highlightedBusinessApiRun =
    businessApiKeyUsageGroups.find((row) => businessApiUsageIssue(row).needsAttention) || businessApiKeyUsageGroups[0] || null;
  const businessApiStatusDocs =
    businessDeliveryAudit?.enumDocs && businessDeliveryAudit.enumDocs.length > 0
      ? businessDeliveryAudit.enumDocs
      : FALLBACK_BUSINESS_API_STATUS_DOCS;
  const businessApiContractChecks = buildBusinessApiContractChecks(businessApiStatusDocs);
  const deliveryAuditByKey = new Map((businessDeliveryAudit?.items || []).map((item) => [item.key, item]));
  const businessDeliveryContractRows = BUSINESS_DELIVERY_CONTRACTS.map((item) => ({
    ...item,
    audit: deliveryAuditByKey.get(item.key) || null,
  }));
  const featureReleaseChecklistRows =
    businessDeliveryAudit?.featureReleaseChecks && businessDeliveryAudit.featureReleaseChecks.length > 0
      ? businessDeliveryAudit.featureReleaseChecks
      : FEATURE_RELEASE_CHECKLIST;
  const businessDeliveryGapRows = businessDeliveryGapMessages(businessDeliveryContractRows);
  const deliveryDecision = buildDeliveryDecision({
    contractChecks: businessApiContractChecks,
    deliveryContracts: businessDeliveryContractRows,
    releaseChecklist: featureReleaseChecklistRows,
    activeKeyCount: activeBusinessApiKeyCount,
    usageCount: businessApiUsageCount,
    pollingTooFrequent: businessApiPollingTooFrequent,
  });

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Alert
        theme="info"
        message="这里按“接口调用”视角组织：先看业务 API 和调用清单，再看 API Key；Coze 工具箱只是另一种接入方式，不再作为业务任务主线。"
      />

      <div className="podi-api-exposure-hero">
        <div>
          <Typography.Text theme="secondary">中台对外能力入口</Typography.Text>
          <Typography.Title level="h3" style={{ margin: '6px 0 8px' }}>
            业务 API、调用清单、Coze 工具箱分开管理
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

      <Card bordered className={`podi-api-delivery-decision podi-api-delivery-decision--${deliveryDecision.status}`}>
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Space align="center" style={{ justifyContent: 'space-between', width: '100%', flexWrap: 'wrap' }}>
            <div>
              <Typography.Text theme="secondary">接口交付状态</Typography.Text>
              <Typography.Title level="h4" style={{ margin: '4px 0' }}>
                {deliveryDecision.title}
              </Typography.Title>
            </div>
            <Tag theme={deliveryDecisionTheme(deliveryDecision.status)} variant="light">
              {deliveryDecisionLabel(deliveryDecision.status)}
            </Tag>
          </Space>
          <div className="podi-api-delivery-decision__grid">
            <section>
              <span>当前状态</span>
              <strong>{deliveryDecision.summary}</strong>
            </section>
            <section>
              <span>主要风险</span>
              <strong>{deliveryDecision.risk}</strong>
            </section>
            <section>
              <span>下一步</span>
              <strong>{deliveryDecision.action}</strong>
            </section>
          </div>
          <details className="podi-api-delivery-decision__details">
            <summary>展开原始检查项</summary>
            {deliveryDecision.details.length ? (
              <ul>
                {deliveryDecision.details.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            ) : (
              <Typography.Text theme="secondary">当前没有契约缺口，继续按上线 SOP 保留真实 runId 证据。</Typography.Text>
            )}
          </details>
        </Space>
      </Card>

      <Card bordered className="podi-api-usage-priority-card">
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Space align="center" style={{ justifyContent: 'space-between', width: '100%', flexWrap: 'wrap' }}>
            <div>
              <Typography.Text theme="secondary">业务接口运行速览</Typography.Text>
              <Typography.Title level="h4" style={{ margin: '4px 0' }}>
                先看业务方有没有正确提交和轮询
              </Typography.Title>
              <Typography.Text theme="secondary">
                这里按 runId 聚合最近调用。先判断接口调用是否正常，再下钻到业务运行详情看 VL、生图、评分和回调步骤。
              </Typography.Text>
            </div>
            <Space>
              <Button size="small" variant="outline" loading={businessApiKeyLoading} onClick={loadBusinessApiKeyAudit}>
                刷新调用
              </Button>
              <Button
                size="small"
                theme="primary"
                variant="outline"
                onClick={() => document.getElementById('business-api-usage-center')?.scrollIntoView({ behavior: 'smooth', block: 'start' })}
              >
                查看完整调用中心
              </Button>
            </Space>
          </Space>
          <div className="podi-business-api-key-summary">
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
              <span>接口异常</span>
              <strong>{formatNumber(failedBusinessApiUsageCount)}</strong>
              <small>状态码异常或有错误码</small>
            </div>
            <div>
              <span>关联任务</span>
              <strong>{formatNumber(businessApiKeyUsageSummary.uniqueRunCount)}</strong>
              <small>去重 runId</small>
            </div>
            <div>
              <span>问题 runId</span>
              <strong>{formatNumber(businessApiRunIssueCount)}</strong>
              <small>聚合后仍需排查</small>
            </div>
          </div>
          <Table
            rowKey="runId"
            size="small"
            data={businessApiKeyUsageGroups.slice(0, 5)}
            loading={businessApiKeyLoading}
            columns={[
              {
                colKey: 'runId',
                title: 'runId',
                ellipsis: true,
                cell: ({ row }) => (
                  <Space direction="vertical" size={2}>
                    <Space>
                      <Typography.Text code>{row.runId || '-'}</Typography.Text>
                      {row.runId ? <CopyButton value={row.runId} onCopy={onCopy} /> : null}
                      {row.runId ? (
                        <Button size="small" variant="text" onClick={() => handleOpenBusinessRun(row.runId)}>
                          打开业务详情
                        </Button>
                      ) : null}
                    </Space>
                    <Typography.Text theme="secondary">
                      {businessKeyLabel(row.businessKey || '')} · {row.apiKeyName || '未知 Key'}
                    </Typography.Text>
                  </Space>
                ),
              },
              {
                colKey: 'counts',
                title: '提交 / 轮询 / 异常',
                width: 210,
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
                  </Space>
                ),
              },
              {
                colKey: 'runStatus',
                title: '业务任务',
                width: 190,
                cell: ({ row }) => (
                  <Space direction="vertical" size={2}>
                    <Tag size="small" theme={businessApiRunStatusTheme(row.runStatus)} variant="light">
                      {businessApiRunStatusLabel(row.runStatus)}
                    </Tag>
                    <Typography.Text theme="secondary">{businessApiRunResultLabel(row)}</Typography.Text>
                  </Space>
                ),
              },
              {
                colKey: 'issue',
                title: '问题判断',
                width: 260,
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
                      暂无明显问题
                    </Tag>
                  );
                },
              },
              {
                colKey: 'lastSeenAt',
                title: '最近调用',
                width: 180,
                cell: ({ row }) => <Typography.Text theme="secondary">{formatDateTime(row.lastSeenAt)}</Typography.Text>,
              },
            ]}
            empty={<Typography.Text theme="secondary">当前筛选范围内还没有业务接口调用记录。</Typography.Text>}
          />
        </Space>
      </Card>

      <Card bordered className="podi-api-business-map-card">
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <div>
            <Typography.Text strong>按业务找接口</Typography.Text>
            <div>
              <Typography.Text theme="secondary">
                同一个业务下同时展示原生 API、Coze 工具箱和原子能力数量。业务方优先看原生 API；排障时先用下面的接口调用中心按 runId 聚合查看。
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

      <Card bordered>
        <Space direction="vertical" size="small" style={{ width: '100%' }}>
          <div>
            <Typography.Text strong>业务接口交付检查</Typography.Text>
            <div>
              <Typography.Text theme="secondary">
                这里检查接口交付材料是否能直接给业务方使用：枚举、成功/失败样例、上线后自检必须同时齐全。
              </Typography.Text>
            </div>
          </div>
          <Table
            rowKey="key"
            size="small"
            data={businessApiContractChecks}
            columns={[
              {
                colKey: 'status',
                title: '状态',
                width: 110,
                cell: ({ row }) => (
                  <Tag theme={deliveryGuardTheme(row.status)} variant="light">
                    {row.status === 'done' ? '已完成' : row.status === 'doing' ? '处理中' : '待补齐'}
                  </Tag>
                ),
              },
              {
                colKey: 'title',
                title: '检查项',
                width: 180,
                cell: ({ row }) => <Typography.Text strong>{row.title}</Typography.Text>,
              },
              {
                colKey: 'detail',
                title: '当前口径',
                ellipsis: true,
              },
              {
                colKey: 'action',
                title: '以后怎么做',
                ellipsis: true,
              },
            ]}
          />
          <div>
            <Typography.Text strong>三个交付接口逐项检查</Typography.Text>
            <div>
              <Typography.Text theme="secondary">
                这里按业务方实际拿到的交付材料检查：每个接口都必须有独立文档、6 类 JSON 样例、枚举说明和常见错误码。
              </Typography.Text>
            </div>
          </div>
          <Alert
            theme={businessDeliveryGapRows.length ? 'warning' : 'success'}
            message={
              businessDeliveryGapRows.length
                ? `交付材料存在缺口：${businessDeliveryGapRows.join('；')}`
                : '三个接口当前都具备独立文档、6 类 JSON 样例、枚举说明和错误码说明；如后续新增字段，先补文档再发版。'
            }
          />
          {businessDeliveryAuditError ? (
            <Alert theme="warning" message={`交付材料实时审计读取失败：${businessDeliveryAuditError}。当前表格先显示本地内置检查口径。`} />
          ) : (
            <Alert
              theme={businessDeliveryAudit?.ok === false ? 'warning' : 'success'}
              message={
                businessDeliveryAudit
                  ? `后端实时审计：${businessDeliveryAudit.summary}；检查时间 ${formatDateTime(businessDeliveryAudit.checkedAt)}。`
                  : '正在读取后端交付材料实时审计结果。'
              }
            />
          )}
          <Table
            rowKey="key"
            size="small"
            data={businessDeliveryContractRows}
            columns={[
              {
                colKey: 'name',
                title: '接口',
                width: 220,
                cell: ({ row }) => (
                  <Space direction="vertical" size={2}>
                    <Typography.Text strong>{row.name}</Typography.Text>
                    <Typography.Text code>{row.path}</Typography.Text>
                  </Space>
                ),
              },
              {
                colKey: 'samples',
                title: '请求/响应样例',
                width: 160,
                cell: ({ row }) => {
                  const state = businessDeliveryContractState(row);
                  return (
                    <Tag theme={state.missingSamples.length ? 'danger' : 'success'} variant="light">
                      {state.missingSamples.length ? `缺 ${state.missingSamples.length} 类` : '6 类齐全'}
                    </Tag>
                  );
                },
              },
              {
                colKey: 'enums',
                title: '枚举',
                width: 170,
                cell: ({ row }) => {
                  const state = businessDeliveryContractState(row);
                  return (
                    <Tag theme={state.missingEnums.length ? 'danger' : 'success'} variant="light">
                      {state.missingEnums.length ? `缺 ${state.missingEnums.length} 项` : `${row.enumFields.length} 项已覆盖`}
                    </Tag>
                  );
                },
              },
              {
                colKey: 'errors',
                title: '错误码',
                width: 140,
                cell: ({ row }) => {
                  const state = businessDeliveryContractState(row);
                  return (
                    <Tag theme={state.missingErrorCodes ? 'danger' : 'success'} variant="light">
                      {state.missingErrorCodes ? '缺错误码' : `${row.errorCodes.length} 个`}
                    </Tag>
                  );
                },
              },
              {
                colKey: 'docsPath',
                title: '交付材料',
                ellipsis: true,
                cell: ({ row }) => <Typography.Text code>{row.docsPath}</Typography.Text>,
              },
              {
                colKey: 'summary',
                title: '当前结论',
                ellipsis: true,
                cell: ({ row }) => {
                  const state = businessDeliveryContractState(row);
                  return <Typography.Text theme={state.ok ? 'success' : 'error'}>{state.summary}</Typography.Text>;
                },
              },
              {
                colKey: 'evidence',
                title: '检查依据',
                ellipsis: true,
                cell: ({ row }) => {
                  const state = businessDeliveryContractState(row);
                  return (
                    <Space direction="vertical" size={2}>
                      {state.requiredEvidence.map((item) => (
                        <Typography.Text key={item} theme="secondary">
                          {item}
                        </Typography.Text>
                      ))}
                    </Space>
                  );
                },
              },
            ]}
          />
          <div>
            <Typography.Text strong>逐功能上线检查表</Typography.Text>
            <div>
              <Typography.Text theme="secondary">
                这里不是功能清单，而是上线前必须逐项核对的清单；特别是 ComfyUI 类能力必须看真实 payload、目标机器节点和结果回填。
              </Typography.Text>
            </div>
          </div>
          <Table
            rowKey="key"
            size="small"
            data={featureReleaseChecklistRows}
            columns={[
              {
                colKey: 'status',
                title: '状态',
                width: 110,
                cell: ({ row }) => (
                  <Tag theme={deliveryGuardTheme(row.status)} variant="light">
                    {row.status === 'done' ? '已固化' : row.status === 'doing' ? '需复核' : '待补齐'}
                  </Tag>
                ),
              },
              {
                colKey: 'name',
                title: '功能',
                width: 230,
                cell: ({ row }) => (
                  <Space direction="vertical" size={2}>
                    <Typography.Text strong>{row.name}</Typography.Text>
                    <Typography.Text code>{row.entry}</Typography.Text>
                    {row.version ? <Typography.Text theme="secondary">版本：{row.version}</Typography.Text> : null}
                  </Space>
                ),
              },
              {
                colKey: 'mustCheck',
                title: '上线前必须看',
                ellipsis: true,
                cell: ({ row }) => (
                  <Space direction="vertical" size={2}>
                    {row.mustCheck.map((item) => (
                      <Typography.Text key={item} theme="secondary">
                        {item}
                      </Typography.Text>
                    ))}
                  </Space>
                ),
              },
              {
                colKey: 'releaseEvidence',
                title: '证据状态',
                ellipsis: true,
                cell: ({ row }) => (
                  <Space direction="vertical" size={2}>
                    <Typography.Text theme="secondary">{row.releaseEvidence}</Typography.Text>
                    {(row.evidence || []).slice(0, 3).map((item) => (
                      <Tag key={item.key} size="small" theme={deliveryGuardTheme(item.status)} variant="light">
                        {item.title}：{item.status === 'done' ? '已通过' : item.status === 'doing' ? '需复核' : '待补齐'}
                      </Tag>
                    ))}
                  </Space>
                ),
              },
              {
                colKey: 'currentRisk',
                title: '当前结论',
                ellipsis: true,
                cell: ({ row }) => (
                  <Space direction="vertical" size={2}>
                    <Typography.Text
                      theme={row.status === 'done' ? 'success' : row.status === 'doing' ? 'warning' : 'error'}
                    >
                      {(row.blockers || []).length
                        ? `存在 ${(row.blockers || []).length} 个阻断项`
                        : (row.warnings || []).length
                          ? `存在 ${(row.warnings || []).length} 个复核项`
                          : row.summary || row.currentRisk}
                    </Typography.Text>
                    {(row.blockers || []).slice(0, 2).map((item) => (
                      <Typography.Text key={item} theme="error">
                        {item}
                      </Typography.Text>
                    ))}
                    {!(row.blockers || []).length && (row.warnings || []).slice(0, 2).map((item) => (
                      <Typography.Text key={item} theme="warning">
                        {item}
                      </Typography.Text>
                    ))}
                  </Space>
                ),
              },
            ]}
          />
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
              <summary>常用参数和状态枚举</summary>
              <Typography.Text theme="secondary">
                枚举来源：{businessDeliveryAudit?.contractSource || '前端离线兜底'}；版本：
                {businessDeliveryAudit?.contractVersion || '本地内置'}。
              </Typography.Text>
              <Table
                rowKey="value"
                size="small"
                data={businessApiStatusDocs}
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

      <div id="business-api-usage-center" className="podi-anchor-target">
        <Card bordered>
          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
            <Space align="center" style={{ justifyContent: 'space-between', width: '100%', flexWrap: 'wrap' }}>
              <div>
                <Typography.Text strong>接口调用中心</Typography.Text>
                <div>
                  <Typography.Text theme="secondary">
                    先确认业务方有没有正确提交任务、有没有拿 runId 轮询、失败集中在哪一步；Key 管理是低频操作，已折叠到下方。
                  </Typography.Text>
                </div>
              </div>
              <Button size="small" variant="outline" loading={businessApiKeyLoading} onClick={loadBusinessApiKeyAudit}>
                刷新调用记录
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
            <div>
              <span>问题 runId</span>
              <strong>{formatNumber(businessApiRunIssueCount)}</strong>
              <small>聚合后仍需排查</small>
            </div>
          </div>
          <div className="podi-business-api-trace-console">
            <div className="podi-business-api-trace-console__lookup">
              <Typography.Text strong>业务方反馈编号</Typography.Text>
              <Typography.Text theme="secondary">
                对方只要给 runId、requestId 或 traceId，就先在这里查；系统会取消时间窗口限制，避免旧任务查不到。
              </Typography.Text>
              <div className="podi-business-api-trace-console__input">
                <Input
                  value={businessApiQuickLookup}
                  placeholder="粘贴 runId / requestId / traceId"
                  onChange={(value) => setBusinessApiQuickLookup(String(value))}
                  onEnter={() => applyBusinessApiQuickLookup('runId')}
                />
                <Button theme="primary" onClick={() => applyBusinessApiQuickLookup('runId')}>
                  按 runId 查
                </Button>
                <Button variant="outline" onClick={() => applyBusinessApiQuickLookup('requestId')}>
                  按 requestId 查
                </Button>
                <Button variant="outline" onClick={() => applyBusinessApiQuickLookup('traceId')}>
                  按 traceId 查
                </Button>
              </div>
            </div>
            <div className="podi-business-api-trace-console__focus">
              <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
                <Typography.Text strong>当前优先排查</Typography.Text>
                {highlightedBusinessApiRun?.runId ? (
                  <Button size="small" variant="text" onClick={() => handleCopyBusinessApiRunEvidence(highlightedBusinessApiRun)}>
                    复制排障摘要
                  </Button>
                ) : null}
              </Space>
              {highlightedBusinessApiRun ? (
                <Space direction="vertical" size={6} style={{ width: '100%' }}>
                  <Space size={6} breakLine>
                    <Tag theme={businessApiUsageIssue(highlightedBusinessApiRun).needsAttention ? 'warning' : 'success'} variant="light">
                      {businessApiUsageIssue(highlightedBusinessApiRun).needsAttention ? '需要处理' : '链路正常'}
                    </Tag>
                    <Typography.Text code>{highlightedBusinessApiRun.runId || '-'}</Typography.Text>
                    {highlightedBusinessApiRun.runId ? (
                      <Button size="small" variant="text" onClick={() => handleOpenBusinessRun(highlightedBusinessApiRun.runId)}>
                        打开任务详情
                      </Button>
                    ) : null}
                  </Space>
                  <Typography.Text>
                    {businessKeyLabel(highlightedBusinessApiRun.businessKey || '')} ·{' '}
                    {businessApiRunStatusLabel(highlightedBusinessApiRun.runStatus)} · {businessApiRunResultLabel(highlightedBusinessApiRun)}
                  </Typography.Text>
                  <Typography.Text theme="secondary">
                    提交 {highlightedBusinessApiRun.submitCount || 0} 次，轮询 {highlightedBusinessApiRun.pollCount || 0} 次，回调{' '}
                    {highlightedBusinessApiRun.callbackCount || 0} 次，异常 {highlightedBusinessApiRun.errorCount || 0} 次。
                  </Typography.Text>
                  <Typography.Text theme={businessApiUsageIssue(highlightedBusinessApiRun).needsAttention ? 'warning' : 'secondary'}>
                    下一步：{businessApiUsageIssue(highlightedBusinessApiRun).hint || '打开任务详情，确认结果图、成本和底层能力日志。'}
                  </Typography.Text>
                </Space>
              ) : (
                <Typography.Text theme="secondary">当前筛选范围内暂无可排查的 runId。</Typography.Text>
              )}
            </div>
          </div>
          <details className="podi-business-api-key-admin">
            <summary>
              <span>Key 管理（低频操作）</span>
              <small>
                当前 {businessApiKeys.length} 个 Key，启用 {activeBusinessApiKeyCount} 个；展开后可创建、停用或查看 Key 范围。
              </small>
            </summary>
            <Space direction="vertical" size="middle" style={{ width: '100%' }}>
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
                  <small>常用：fission、product_design、image_edit、image_edit_chat、fission_evaluate、outpaint、pattern_extract、text_fission。</small>
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
                              {businessKeyLabel(item)}
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
            </Space>
          </details>
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
          <Alert
            theme="info"
            message="这里看“外部请求有没有打进来”；业务是否真正完成，请点击 runId 打开业务任务详情，再看每一步处理结果。"
          />
          <Alert
            theme={businessApiPollingTooFrequent ? 'warning' : 'success'}
            message={
              businessApiPollingTooFrequent
                ? `当前窗口平均每个提交约 ${businessApiPollingRatio.toFixed(1)} 次查询，偏高。请业务方按 retryAfterSeconds 或 5-10 秒间隔轮询。`
                : '轮询频率未发现明显异常。业务方仍应保存 runId，并按 retryAfterSeconds 查询结果。'
            }
          />
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
                <option value="image_edit">图编辑</option>
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
                      {row.runId ? (
                        <Button size="small" variant="text" onClick={() => handleCopyBusinessApiRunEvidence(row)}>
                          复制摘要
                        </Button>
                      ) : null}
                    </Space>
                    <Typography.Text theme="secondary">
                      {businessKeyLabel(row.businessKey || '')} · {row.apiKeyName || '未知 Key'}
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
                colKey: 'runStatus',
                title: '业务任务',
                width: 210,
                cell: ({ row }) => (
                  <Space direction="vertical" size={2}>
                    <Space size={4} breakLine>
                      <Tag size="small" theme={businessApiRunStatusTheme(row.runStatus)} variant="light">
                        {businessApiRunStatusLabel(row.runStatus)}
                      </Tag>
                      {row.runVersion ? (
                        <Tag size="small" variant="light">
                          版本 {row.runVersion}
                        </Tag>
                      ) : null}
                    </Space>
                    <Typography.Text theme="secondary">{businessApiRunResultLabel(row)}</Typography.Text>
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
                      {businessKeyLabel(row.businessKey || '')} · {row.runId || row.requestId || row.traceId || '-'}
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
      </div>

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
