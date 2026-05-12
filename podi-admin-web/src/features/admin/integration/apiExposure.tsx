import { Alert, Button, Card, Space, Table, Tag, Typography } from 'tdesign-react';
import type { PublicAbility } from '../../../types/admin';

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

type ApiExposurePanelProps = {
  publicAbilities: PublicAbility[];
  publicAbilitiesLoading: boolean;
  cozeAbilityStats: {
    total: number;
    mapped: number;
  };
  onRefreshPublicAbilities: () => void;
  onCopy: (value: string) => void;
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
  -H "Authorization: Bearer <业务方 accessToken 或 SERVICE_API_TOKEN>" \\
  -H "Content-Type: application/json" \\
  -d '{
    "imageUrl": "https://example.com/input.png",
    "prompt": "保持主体风格，生成 4 张变化图",
    "source": "partner-api",
    "channel": "open-api",
    "callbackUrl": "https://your-service.example.com/callback",
    "traceId": "biz_trace_001"
  }'`;
}

function buildBusinessQueryExample(): string {
  return `curl -X POST <backend-host>/api/business/runs/get \\
  -H "Authorization: Bearer <业务方 accessToken 或 SERVICE_API_TOKEN>" \\
  -H "Content-Type: application/json" \\
  -d '{
    "runId": "<提交接口返回的 runId>"
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
  getProviderLabel,
  getCategoryLabel,
}: ApiExposurePanelProps) {
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
              给业务方一个固定入口，传图、参数、回调地址；中台内部切默认版本、灰度、路由和回滚，不需要 Coze 工作流 ID。
            </Typography.Text>
            <Tag theme="success" variant="light">
              提交后保存 runId，再轮询结果
            </Tag>
            <CodeExample value={buildBusinessRunExample()} onCopy={onCopy} />
            <CodeExample value={buildBusinessQueryExample()} onCopy={onCopy} />
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
