# API 开放入口冒烟清单

用途：阶段发版前快速确认管理端“API 开放”页展示的业务 API、原子能力 API、Coze 工具箱入口仍可访问，且错误口径没有退化成 500 或 `INTERNAL_ONLY`。

默认只做不消耗生图额度的检查；真实出图仍使用 `backend/scripts/patrol_business_api.py --mode live`。

## 1. 前置条件

- backend 已启动，默认地址：`http://127.0.0.1:8099`。
- 如果不是可信内网访问 Coze 工具箱，需要设置服务 Token：

```bash
export BACKEND_URL=http://127.0.0.1:8099
export SERVICE_API_TOKEN=<server-token>
```

本地可信环境可只设置：

```bash
export BACKEND_URL=http://127.0.0.1:8099
```

## 2. 必测入口

| 类型 | 命令 | 期望 |
| --- | --- | --- |
| 健康检查 | `curl -fsS "$BACKEND_URL/health"` | 返回 200。 |
| 业务 OpenAPI | `curl -fsS "$BACKEND_URL/api/business/openapi.json"` | 返回 200，包含三主业务提交、路由预览、任务查询。 |
| 原子能力清单 | `curl -fsS "$BACKEND_URL/api/abilities"` | 返回 200，包含 `items`。 |
| 原子能力表单选项 | `curl -fsS "$BACKEND_URL/api/abilities/options"` | 返回 200，前端选项来源可用。 |
| Coze 综合工具箱 | `curl -fsS "$BACKEND_URL/api/coze/podi/openapi.json"` | 返回 200；若返回 `INTERNAL_ONLY`，说明可信内网或 Token 配置错误。 |
| Coze ComfyUI 工具箱 | `curl -fsS "$BACKEND_URL/api/coze/podi/comfyui/openapi.json"` | 返回 200。 |
| 高质量图裂变工具箱 | `curl -fsS "$BACKEND_URL/api/coze/podi/comfyui/execute/flux-strong-hq-softstyle-fission/openapi.json"` | 返回 200。 |
| 扩图主线工具箱 | `curl -fsS "$BACKEND_URL/api/coze/podi/comfyui/execute/flux2-klein-9b-outpaint/openapi.json"` | 返回 200。 |
| 背景抠图工具箱 | `curl -fsS "$BACKEND_URL/api/coze/podi/comfyui/execute/beijing-koutu/openapi.json"` | 返回 200。 |
| 头部抠像工具箱 | `curl -fsS "$BACKEND_URL/api/coze/podi/comfyui/execute/toubu-kouxiang/openapi.json"` | 返回 200。 |
| KIE 工具箱 | `curl -fsS "$BACKEND_URL/api/coze/podi/kie/openapi.json"` | 返回 200。 |

## 3. 必测无额度业务 API

这组检查用于证明三主业务可以先走中台自有业务 API 做路由验证，不需要 Coze 工作流 ID，也不会消耗生图额度。

```bash
curl -sS -X POST "$BACKEND_URL/api/business/fission/route-preview" \
  -H "Content-Type: application/json" \
  -d '{
    "source": "partner-api",
    "channel": "open-api",
    "traceId": "smoke-route-fission-001",
    "tenantId": "smoke-tenant",
    "clientId": "smoke-client"
  }'
```

期望：

- 返回 200。
- 返回 `selectedCapabilityId/selectedVersion/selectedBy`。
- 不创建 `runId`，不进入 ComfyUI 队列。
- 不要求 `coze_workflow_id`、`workflowId` 或 Coze 工具箱上下文。

花纹提取和扩图同样使用：

```bash
curl -sS -X POST "$BACKEND_URL/api/business/pattern-extract/route-preview" \
  -H "Content-Type: application/json" \
  -d '{"source":"partner-api","channel":"open-api","traceId":"smoke-route-pattern-001"}'

curl -sS -X POST "$BACKEND_URL/api/business/outpaint/route-preview" \
  -H "Content-Type: application/json" \
  -d '{"source":"partner-api","channel":"open-api","traceId":"smoke-route-outpaint-001"}'
```

## 4. 必测错误口径

### 4.1 业务任务查询不存在

```bash
curl -sS -X POST "$BACKEND_URL/api/business/runs/get" \
  -H "Content-Type: application/json" \
  -d '{"runId":"not-exists"}'
```

期望：返回 `BUSINESS_RUN_NOT_FOUND` 或等价 404；不能返回 500。

### 4.2 Coze task 查询不存在

```bash
curl -sS -X POST "$BACKEND_URL/api/coze/podi/tasks/get" \
  -H "Content-Type: application/json" \
  -d '{"taskId":"not-exists"}'
```

期望：返回 `TASK_NOT_FOUND` 或等价 404；不能返回 `INTERNAL_ONLY` 或 500。

### 4.3 业务提交缺主图

```bash
curl -sS -X POST "$BACKEND_URL/api/business/fission/runs" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"缺少 imageUrl 的错误口径检查"}'
```

期望：返回 `BUSINESS_IMAGE_URL_REQUIRED`；不能进入队列。

## 5. 可选真实链路

真实出图回归使用现有脚本：

```bash
cd backend
python scripts/patrol_business_api.py \
  --base-url "$BACKEND_URL" \
  --mode live \
  --require-executor-evidence \
  --image-url "<可访问样例图 URL>"
```

需要把真实巡检结果留到管理端总览的“发版巡检记录”时，追加：

```bash
python scripts/patrol_business_api.py \
  --base-url "$BACKEND_URL" \
  --token "$SERVICE_API_TOKEN" \
  --mode live \
  --require-executor-evidence \
  --image-url "<可访问样例图 URL>" \
  --report "reports/business_patrol_$(date +%Y%m%d_%H%M%S).json" \
  --record-release-patrol
```

验收必须看到：

- 花纹提取、图裂变、扩图至少各有一次终态。
- 成功任务有 `runId/taskId/imageUrls`。
- 结果里能看到实际执行节点证据。
- 失败任务必须有标准错误码和中文可处理原因。

## 6. 失败处理

- OpenAPI 失败：先检查 backend 是否启动、路由是否注册、服务是否更新到目标版本。
- `INTERNAL_ONLY`：先检查 Coze/backend 是否同机可信访问，或是否带 `SERVICE_API_TOKEN`。
- 队列满：应返回明确队列/并发错误，不允许长期 `running`。
- 上游成功但无输出：视为失败，必须排查 OSS 回填、ComfyUI history 和能力调用日志。
