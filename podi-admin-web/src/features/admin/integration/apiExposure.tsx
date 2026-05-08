import { Alert, Button, Card, Space, Table, Tag, Typography } from 'tdesign-react';
import type { PublicAbility } from '../../../types/admin';
import { OperationFlowCard } from '../shared/ui';

type ApiEndpoint = {
  key: string;
  name: string;
  method: 'GET' | 'POST';
  path: string;
  purpose: string;
  audience: string;
};

type ToolboxEndpoint = {
  key: string;
  name: string;
  path: string;
  purpose: string;
  status: '主入口' | '专项工具箱' | '查询工具箱';
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

const BUSINESS_ENDPOINTS: ApiEndpoint[] = [
  {
    key: 'business-openapi',
    name: '业务 OpenAPI',
    method: 'GET',
    path: '/api/business/openapi.json',
    purpose: '业务方或内部系统导入稳定业务接口。',
    audience: '业务接入 / 开发联调',
  },
  {
    key: 'pattern-run',
    name: '花纹提取',
    method: 'POST',
    path: '/api/business/pattern-extract/runs',
    purpose: '提交花纹提取任务，底层版本由中台决定。',
    audience: '业务主入口',
  },
  {
    key: 'fission-run',
    name: '图裂变',
    method: 'POST',
    path: '/api/business/fission/runs',
    purpose: '提交图裂变任务，返回 runId 后查询结果。',
    audience: '业务主入口',
  },
  {
    key: 'outpaint-run',
    name: '扩图',
    method: 'POST',
    path: '/api/business/outpaint/runs',
    purpose: '提交扩图任务，宽高和四向扩展量由参数控制。',
    audience: '业务主入口',
  },
  {
    key: 'business-get',
    name: '查询业务任务',
    method: 'POST',
    path: '/api/business/runs/get',
    purpose: '统一按 runId 查询状态、图片、错误和调试信息。',
    audience: '业务接入 / 回调兜底',
  },
  {
    key: 'pattern-preview',
    name: '花纹提取路由预览',
    method: 'POST',
    path: '/api/business/pattern-extract/route-preview',
    purpose: '不提交真实任务，只验证当前业务方会命中哪个版本。',
    audience: '灰度 / 上线前验证',
  },
  {
    key: 'fission-preview',
    name: '图裂变路由预览',
    method: 'POST',
    path: '/api/business/fission/route-preview',
    purpose: '不提交真实任务，只验证图裂变默认、灰度或指定版本命中。',
    audience: '灰度 / 上线前验证',
  },
  {
    key: 'outpaint-preview',
    name: '扩图路由预览',
    method: 'POST',
    path: '/api/business/outpaint/route-preview',
    purpose: '不提交真实任务，只验证扩图默认、灰度或指定版本命中。',
    audience: '灰度 / 上线前验证',
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
  },
  {
    key: 'ability-detail',
    name: '能力详情',
    method: 'GET',
    path: '/api/abilities/{abilityId}',
    purpose: '查看单个能力的输入字段、默认参数和运行要求。',
    audience: '开发接入 / 排障',
  },
  {
    key: 'ability-invoke',
    name: '调用能力',
    method: 'POST',
    path: '/api/abilities/{abilityId}/invoke',
    purpose: '直接触发原子能力，适合内部编排、测评和高级开发。',
    audience: '开发接入 / 测评',
  },
  {
    key: 'ability-options',
    name: '表单选项',
    method: 'GET',
    path: '/api/abilities/options',
    purpose: '读取能力表单需要的候选值，减少前端硬编码。',
    audience: '前端 / 工具开发',
  },
];

const COZE_TOOLBOX_ENDPOINTS: ToolboxEndpoint[] = [
  {
    key: 'coze-main',
    name: 'PODI 综合工具箱',
    path: '/api/coze/podi/openapi.json',
    purpose: 'Coze 导入全部可用能力工具和任务查询。',
    status: '主入口',
  },
  {
    key: 'coze-comfyui',
    name: 'ComfyUI 工具箱',
    path: '/api/coze/podi/comfyui/openapi.json',
    purpose: 'Coze 导入 ComfyUI 类能力。',
    status: '专项工具箱',
  },
  {
    key: 'coze-fission',
    name: '高质量图裂变',
    path: '/api/coze/podi/comfyui/execute/flux-strong-hq-softstyle-fission/openapi.json',
    purpose: '新高质量裂变工作流专项导入口。',
    status: '专项工具箱',
  },
  {
    key: 'coze-outpaint',
    name: '扩图主线',
    path: '/api/coze/podi/comfyui/execute/flux2-klein-9b-outpaint/openapi.json',
    purpose: '扩图主线工作流专项导入口。',
    status: '专项工具箱',
  },
  {
    key: 'coze-bg-remove',
    name: '背景抠图',
    path: '/api/coze/podi/comfyui/execute/beijing-koutu/openapi.json',
    purpose: '背景抠图专项导入口。',
    status: '专项工具箱',
  },
  {
    key: 'coze-head-cutout',
    name: '头部抠像',
    path: '/api/coze/podi/comfyui/execute/toubu-kouxiang/openapi.json',
    purpose: '头部抠像专项导入口。',
    status: '专项工具箱',
  },
  {
    key: 'coze-kie',
    name: 'KIE 模型工具箱',
    path: '/api/coze/podi/kie/openapi.json',
    purpose: 'Coze 导入 KIE 类商业模型工具。',
    status: '专项工具箱',
  },
  {
    key: 'coze-tasks',
    name: '任务查询',
    path: '/api/coze/podi/tasks/get',
    purpose: 'Coze 工作流按 taskId 查询最终图片、视频、文字或错误。',
    status: '查询工具箱',
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

function deliveryGuardLabel(status: DeliveryGuardStatus): string {
  if (status === 'done') return '已完成';
  if (status === 'doing') return '进行中';
  return '待处理';
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

      <OperationFlowCard
        title="业务方最短接入路径"
        description="给业务方只讲这一条路径即可：提交业务任务，保存 runId，用统一查询或回调拿结果。"
        summary="推荐默认路径：业务方不选模型、不选工作流，只按固定参数提交业务任务。"
        summaryTheme="success"
        extra={
          <Tag theme="success" variant="light">
            推荐默认路径
          </Tag>
        }
        steps={[
          {
            key: 'select-business-api',
            title: '选业务接口',
            detail: '花纹提取、图裂变、扩图优先走 /api/business/*/runs。',
            action: '不要让业务方选择模型、工作流或执行节点。',
            done: '入口清楚',
            theme: 'success',
          },
          {
            key: 'submit-run',
            title: '提交任务',
            detail: '业务方只传图片、参数、traceId、callbackUrl。',
            action: '由中台负责版本、路由、排队和结果回填。',
            done: '参数稳定',
            theme: 'primary',
          },
          {
            key: 'save-run-id',
            title: '保存 runId',
            detail: '提交成功后必须保存 runId。',
            action: '页面、回调兜底、客服排障都用 runId 追踪。',
            done: '可追踪',
            theme: 'primary',
          },
          {
            key: 'query-or-callback',
            title: '查询或接回调',
            detail: '统一调用 /api/business/runs/get 查询状态和结果。',
            action: '有回调时也保留轮询，作为业务方兜底方式。',
            done: '拿到结果',
            theme: 'primary',
          },
          {
            key: 'handle-error-code',
            title: '按错误码处理',
            detail: '队列满、缺参、依赖失败、超时都要给明确错误。',
            action: '提示稍后重试或联系平台，不让业务方猜原因。',
            done: '错误可处理',
            theme: 'warning',
          },
        ]}
      />

      <Card bordered className="podi-api-onboarding-card">
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Space align="center" style={{ justifyContent: 'space-between', width: '100%', flexWrap: 'wrap' }}>
            <div>
              <Typography.Text strong>业务方开通前检查</Typography.Text>
              <div>
                <Typography.Text theme="secondary">
                  业务接入不是只给一个接口地址；开通范围、版本命中、回调兜底和错误提示必须先确认。
                </Typography.Text>
              </div>
            </div>
            <Tag theme="warning" variant="light">
              上线前必须逐项确认
            </Tag>
          </Space>
          <div className="podi-api-onboarding-grid">
            {BUSINESS_ONBOARDING_CHECKS.map((item) => (
              <section key={item.key} className={`podi-api-onboarding-item podi-api-onboarding-item--${item.theme}`}>
                <Space direction="vertical" size={8} style={{ width: '100%' }}>
                  <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
                    <Tag theme={item.theme} variant="light">
                      {item.tag}
                    </Tag>
                    <Typography.Text theme="secondary">业务接入</Typography.Text>
                  </Space>
                  <Typography.Text strong>{item.title}</Typography.Text>
                  <Typography.Text theme="secondary">{item.detail}</Typography.Text>
                  <Typography.Text theme={item.theme === 'warning' ? 'warning' : 'secondary'}>下一步：{item.action}</Typography.Text>
                </Space>
              </section>
            ))}
          </div>
        </Space>
      </Card>

      <Card bordered className="podi-api-delivery-card">
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Space align="center" style={{ justifyContent: 'space-between', width: '100%', flexWrap: 'wrap' }}>
            <div>
              <Typography.Text strong>同步交付门禁</Typography.Text>
              <div>
                <Typography.Text theme="secondary">
                  后续不再等全部功能做完才改前端；接口、页面、文档、错误和冒烟检查必须同批推进。
                </Typography.Text>
              </div>
            </div>
            <Tag theme="primary" variant="light">
              A2 / A3 / A4 已补齐
            </Tag>
          </Space>
          <div className="podi-api-guard-grid">
            {API_DELIVERY_GUARDS.map((item) => (
              <div key={item.key} className={`podi-api-guard-card podi-api-guard-card--${item.status}`}>
                <Space direction="vertical" size={8} style={{ width: '100%' }}>
                  <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
                    <Tag theme={deliveryGuardTheme(item.status)} variant="light">
                      {deliveryGuardLabel(item.status)}
                    </Tag>
                    <Typography.Text theme="secondary">{item.owner}</Typography.Text>
                  </Space>
                  <Typography.Text strong>{item.title}</Typography.Text>
                  <Typography.Text theme="secondary">{item.detail}</Typography.Text>
                  <Typography.Text theme={item.status === 'todo' ? 'warning' : 'secondary'}>下一步：{item.action}</Typography.Text>
                </Space>
              </div>
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
