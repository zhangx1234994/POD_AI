# 对外接口边界审计 2026-05-14

## 范围

本次审计覆盖：

- FastAPI 路由注册表。
- 业务 API OpenAPI。
- 现有 API 文档与接口标准文档。
- 业务方近期反馈的“返回体过重”“接口边界不清”“回调/轮询概念混用”问题。

审计命令：

```bash
python3 scripts/audit_external_api_boundaries.py --summary
python3 -m pytest backend/tests/test_business_api_contract.py -q
```

本地审计结果：

- 已登记路由：338 个。
- 未分类路由：0 个。
- 业务 API：11 个，其中业务文档入口 1 个。
- 管理端 API：203 个。
- Coze 工具箱：29 个。
- 评测 API：29 个。
- 原子能力与异步任务 API：7 个。
- 历史兼容、媒资、通知、钱包、积分等非业务接口仍需要后续收口。

## 当前结论

正式业务交付入口应收敛为 `/api/business/*`。`/api/coze/podi/*` 是 Coze 工具箱入口，`/api/abilities/*` 是内部/高级开发入口，`/api/evals/*` 是内部评测入口，`/api/admin/*` 是管理员入口。普通业务方不应直接接原子能力、Coze 工具箱、历史任务中心或媒资上传接口。

## 已确认符合预期

| 项目 | 结论 |
| --- | --- |
| 业务提交接口 | `/api/business/{business}/runs` 已改成轻量回执，不再默认返回 `routeInfo/steps/requestPayload`。 |
| 业务查询接口 | `/api/business/runs/get` 默认轻量返回；`detail=full` 才返回完整排障字段。 |
| Coze 兼容查询 | `/api/coze/podi/tasks/get` 已兼容业务 `runId`，但正式业务文档仍以 `/api/business/runs/get` 为主。 |
| 业务 API Key | 已支持 `X-PODI-API-Key` 和调用记录表，可看到每个 Key 的调用路径、业务、状态码、耗时和 runId。 |
| Coze 执行边界 | 工具执行接口调用 `_require_internal`，未命中可信内网或服务 Token 会返回 `INTERNAL_ONLY`。 |

## 已本次修正

| 问题 | 处理 |
| --- | --- |
| 历史文档把 `/api/abilities` 写成普通业务系统统一入口。 | 改为“内部编排、测评、高级开发入口”；普通业务方优先使用 `/api/business/*`。 |
| `tenantId/clientId` 容易被业务方误认为必传。 | OpenAPI 与业务文档改为“通常不需要传，由业务 API Key 绑定；显式传入必须匹配 Key/账号范围”。 |
| “回调”与“轮询”概念混用。 | 标准中明确：业务方常规链路是提交后拿 `runId` 轮询；`callbackUrl` 是可选 Webhook。 |
| 缺少可复用的接口边界检查手段。 | 新增 `scripts/audit_external_api_boundaries.py`，按路径前缀输出接口层级和鉴权提示。 |

## 需要后续治理的风险

### P1：历史兼容接口仍有无鉴权路由

涉及范围：

- `/api/tasks/v1/*`
- `/api/wallet/v1/*`
- `/api/op/v1/*`
- `/api/os/v1/*`
- `/api/notify/v1/event`
- `/api/media/v1/upload-key`
- `/api/media/v1/signed-download`

结论：这些接口不能进入业务方交付材料。下一步需要二选一：

- 仅内网反代可访问，并在 Nginx/安全组上挡住公网。
- 补鉴权并迁移前端调用。
- 确认已无依赖后删除。

### P1：`/api/media/v1/upload-key` 可按任意 `userId` 申请上传 Key

当前该接口支撑测评端和管理端上传链路，但它不是业务方接口。后续应改为：

- 管理端/测评端登录态或评测 Token 申请。
- 上传 Key 绑定真实调用者。
- 业务方上传如需开放，另走业务 API Key 范围下的专用接口。

### P2：`GET /api/abilities` 和 `GET /api/abilities/options` 当前可无登录读取

这对管理端/测评端联调方便，但会暴露能力名称、schema、provider 和部分默认参数。短期处理是明确“不作为业务接口”；中期建议：

- 若公网暴露 backend，则这两个清单接口也加登录或网关限制。
- 管理端 API 开放页读取时使用管理员 Token。
- 测评端读取时使用评测 Token 或后端聚合接口。

### P2：`/api/business/capabilities` 当前允许可信内网无 Key 读取

这是为了 Coze 同机和巡检脚本兼容。若将来开放到公网网关，建议要求业务 API Key 或只保留 `/api/business/openapi.json` 公开。

### P3：旧文档仍有历史客户端和旧任务中心引用

这些内容不一定是线上风险，但会干扰业务方和新开发理解。后续按文档清理计划处理，原则是历史资料必须标注“非当前主线”。

## 对业务方交付口径

业务方只需要拿到：

1. `X-PODI-API-Key`
2. 提交接口：`POST /api/business/{business}/runs`
3. 查询接口：`POST /api/business/runs/get`
4. 参数说明
5. 返回字段说明
6. 错误码和重试建议
7. 可运行 Demo

不交付：

- `/api/abilities/*`
- `/api/coze/podi/*`
- `/api/evals/*`
- `/api/admin/*`
- `/api/media/*`
- ComfyUI 地址
- vendor-api-ops 地址
- image-ops 地址
- 第三方模型 Key

## 下一步建议

1. 把历史兼容接口从公网访问面收紧，优先处理 `/api/media` 和 `/api/notify`。
2. 管理端“API 开放”页按业务分类展示：业务 API 在前，Coze 工具箱和原子能力作为同业务下的技术入口。
3. 每个业务交付包按“一个接口一个目录”组织，避免三个接口混在一个 README 里。
4. 发版 SOP 加入接口边界审计脚本输出，发现未分类接口即阻断。
