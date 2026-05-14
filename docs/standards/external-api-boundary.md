# 对外接口边界规范

## 目标

把“能访问的接口”和“应该交付给业务方的接口”分开管理。

当前正式对业务方交付的主入口只有业务 API：`/api/business/*`。Coze 工具箱、原子能力、管理端、测评端、Agent、历史任务接口都不能在业务交付材料里混用，除非明确写明使用对象和风险。

## 分层标准

| 层级 | 使用对象 | 路径范围 | 是否给普通业务方 | 核心边界 |
| --- | --- | --- | --- | --- |
| 业务 API | 业务方、业务系统、后续客户端、MCP、技能 | `/api/business/*` | 是 | 只暴露业务参数、`runId`、轻量状态和结果；底层能力、执行节点、厂商细节默认隐藏。 |
| Coze 工具箱 API | Coze 工作流 | `/api/coze/podi/*` | 否 | OpenAPI 可导入；执行与轮询接口必须内网或服务 Token 放行，不允许直连 ComfyUI/vendor-api-ops/image-ops。 |
| 原子能力 API | 内部编排、测评、高级开发 | `/api/abilities/*`、`/api/ability-tasks/*` | 默认否 | 允许暴露技术参数和执行节点语义，不作为普通业务方第一接入口。 |
| 管理端 API | 管理员 | `/api/admin/*` | 否 | 必须管理员鉴权；用于配置、节点、密钥、日志、计费、验收和回滚。 |
| 测评 API | 内部测试与验收 | `/api/evals/*` | 否 | 可用评测 Token，但不承诺业务接入稳定性；只用于测试、打分和回归。 |
| 媒资/上传 API | 管理端、测评端、内部工具 | `/api/media/*` | 否 | 仅提供上传凭证、签名下载和 OSS 回调；不作为业务生成能力入口。 |
| Agent API | ComfyUI 轻 Agent、执行节点 | `/api/agent/*` | 否 | bootstrap 用接入码或安装 Key，运行期用 Agent Token；不允许业务系统调用。 |
| 历史兼容接口 | 老任务中心、旧积分钱包、通知 | `/api/tasks/v1/*`、`/api/wallet/*`、`/api/op/v1/*`、`/api/os/v1/*`、`/api/notify/*` | 否 | 只做兼容或内部页面支撑；新业务不得基于这些接口设计。 |

## 业务 API 硬约束

业务方正式交付材料只能默认出现以下形态：

- 提交：`POST /api/business/{business}/runs`
- 查询：`POST /api/business/runs/get`
- 可选预览：`POST /api/business/{business}/route-preview`
- 能力清单：`GET /api/business/capabilities`
- 文档：`GET /api/business/openapi.json`

响应要求：

- 提交接口只返回轻量回执：`runId/taskId/businessKey/version/status/taskStatus/traceId/requestId/retryAfterSeconds/error/errorCode/createdAt`。
- 查询接口默认只返回轻量结果：`runId/taskId/status/taskStatus/imageUrl/imageUrls/videoUrl/videoUrls/text/texts/resultPayload/error/errorCode/debugResponse/retryAfterSeconds`。
- `routeInfo/steps/requestPayload/resultPayload.raw/costBreakdown` 等排障字段只能在 `detail=full` 或管理端接口中出现。
- 业务方通常不需要传 `tenantId/clientId`。这两个值优先由业务 API Key 绑定；显式传入时必须与 Key 或账号范围一致。
- 对外错误不能泄露 SQL、密钥、厂商完整原始响应、服务器内网地址。

## Coze 与业务 API 的边界

- Coze 是接入层和实验层，不是长期业务编排真源。
- 新 Coze 工作流优先调用业务 API，而不是直接拼原子能力。
- 已上线旧 Coze 工作流继续兼容，但不能反向要求业务 API 跟随 Coze 的临时字段。
- `/api/coze/podi/tasks/get` 可以兼容查询业务 `runId`，目的是降低旧链路迁移成本；业务方正式文档仍应使用 `/api/business/runs/get`。
- 文档中必须区分“轮询查询”和“Webhook 回调”。业务方常规链路是提交后拿 `runId` 轮询，不是让 114 回调自己。

## 原子能力 API 的边界

原子能力接口可以给内部编排、测评端和高级开发使用，但不直接作为普通业务方接口，原因是：

- 入参更接近模型、工作流或执行节点，业务方不应该理解这些细节。
- 版本、灰度、回滚、计费、Key 使用记录应在业务层统一收口。
- 同一业务可能由 VL、ComfyUI、OpenAI、KIE、image-ops 多步组成，业务方只应看到一个业务任务。

如果确实要把原子能力开放给高级业务方，必须额外满足：

- 有单独交付材料。
- 有明确 API Key 范围。
- 有示例、错误码、成本、限流和回滚说明。
- 不得影响普通业务 API 的稳定契约。

## 新接口准入清单

新增或调整任何对外可见接口前，必须先回答：

1. 这个接口属于哪一层？
2. 普通业务方是否应该直接调用？
3. 鉴权方式是什么？
4. 是否会泄露执行节点、第三方 Key、SQL、内网地址或原始厂商响应？
5. 默认响应是否足够轻量？
6. 是否有请求示例、响应示例、错误码和轮询建议？
7. 是否已同步管理端、测评端、OpenAPI 和交付包？
8. 是否有自动化测试覆盖缺参、鉴权失败、上游失败、超时、并发限制？

## 发布检查

每次上线前至少执行：

```bash
python3 scripts/audit_external_api_boundaries.py --summary
python3 -m pytest backend/tests/test_business_api_contract.py -q
```

若审计报告出现未分类接口、新业务接口仍走历史任务中心、业务提交响应包含内部字段，禁止交付业务方测试。
