# 第三方 API 接入整体拆分方案 v2

> 日期：2026-04-24  
> 状态：implementing  
> 背景：Coze 服务器访问 `api.openai.com` 超时，第三方 API 能力需要独立执行面承载网络、Key、限流和厂商错误适配。

## 1. 目标

建立独立的 `vendor-api-ops` 服务，专门承载第三方 API 原子能力。火山、百度、KIE、OpenAI、中转站以及后续第三方图像 API 都按同一执行面接入。

目标链路：

```text
Coze
  -> backend / toolbox
    -> vendor-api executor
      -> vendor-api-ops
        -> OpenAI / 火山 / 百度 / KIE / 其他厂商
```

对 Coze、测评端、管理端统一保持 backend 任务模型：提交任务得到 `taskId`，再通过 `/api/coze/podi/tasks/get` 轮询结果。即使上游是同步 API，也由 backend 包装成平台任务，避免 Coze 感知厂商同步/异步差异。

## 2. 非目标

- 不把 OpenAI 等第三方 API 调用塞进 image-ops。
- 不让 Coze 直接调用 vendor-api-ops。
- 不在 Coze 工作流中保存 API Key。
- 不让 backend 直接保存 OpenAI/KIE/火山/百度等第三方 Key 作为长期权威。
- 不强行把所有模型参数压成固定字段；每个能力继续使用独立 schema。

## 3. 服务职责

vendor-api-ops 负责：

- API Key 运行时托管。
- provider/model 级别调用适配。
- 同步、异步、轮询、回调型厂商接口适配。
- 代理和国际出口配置。
- 限流、并发、冷却、熔断。
- 厂商错误归一。
- 调用耗时、用量、成本基础数据回传。

backend 负责：

- 能力目录。
- executor 选择。
- Coze 工具箱 contract。
- 任务状态、日志、OSS 回填。
- 管理端和评测端展示。
- 对外只返回平台 `taskId`、平台状态和自有 OSS 结果链接。

## 4. 双层契约

### 平台能力契约

backend 维护 `Ability.input_schema`，继续作为管理端、测评端、Coze 工具箱字段来源。字段可以因能力不同而不同：

- OpenAI 图片编辑：`image_url`、`mask_url`、`prompt`、`size`、`quality`。
- KIE：`input_urls`、`aspect_ratio`、`resolution`。
- 火山：`sequential_image_generation`、`max_images`、`response_format`。

### vendor 执行契约

backend 只向 vendor-api-ops 传：

- `provider`
- `capabilityKey`
- `model`
- `apiType`
- `inputs`
- `assets`
- `taskPolicy`

vendor-api-ops 返回统一 envelope：

```json
{
  "success": true,
  "status": "queued|running|succeeded|failed",
  "provider": "openai",
  "model": "gpt-image-2",
  "vendorInvocationId": "vinv_xxx",
  "vendorTaskId": "upstream_xxx",
  "result": {
    "images": [{"url": "...", "b64": null, "role": "output"}],
    "videos": [],
    "texts": [],
    "json": {},
    "usage": {},
    "cost": {}
  },
  "error": null,
  "raw": {}
}
```

## 5. 已落地 v1 范围

### vendor-api-ops

- `GET /health`
- `GET /v1/providers`
- `POST /v1/providers/{provider}/egress-check`
- `POST /v1/invocations`
- `GET /v1/invocations/{vendorInvocationId}`
- `POST /v1/keys`
- `GET /v1/keys`
- `PATCH /v1/keys/{keyId}`
- Provider 目录已覆盖 `openai`、`openai_compatible`、`volcengine`、`baidu`、`kie`。
- Key 读取只返回 `keyPreview`，不返回明文。
- Key、invocation、usage log 已落 SQLite 持久化，默认路径 `runtime/vendor-api-ops.sqlite3`。
- KIE 已接真实 submit/poll adapter：提交 `/api/v1/jobs/createTask`，轮询 `/api/v1/jobs/recordInfo`。
- OpenAI / OpenAI-compatible 已接真实 Images API 风格 adapter：图片生成走 `/v1/images/generations`，图片编辑走 `/v1/images/edits`，支持原图、蒙版、多参考图、`size`、`quality` 等字段。
- 火山已接真实 Ark 风格 adapter：图文对话走 `/api/v3/chat/completions`，生图走 `/api/v3/images/generations`，视频提交链路保留 `/api/v3/contents/generations/tasks` passthrough。
- 百度图像处理已接真实 adapter：先换取 OAuth token，再按能力 `request_endpoint` 提交 form 表单；输入支持 `image_base64`、`imageBase64`、`image_url` 和 input assets。

标准错误结构：

```json
{
  "success": false,
  "errorCode": "VENDOR_API_KEY_MISSING",
  "message": "OpenAI API Key 未配置",
  "suggestion": "请在 vendor-api-ops 环境变量或 Key 管理中配置可用 Key"
}
```

### backend

- 新增 `vendor_api` executor 类型。
- `config/executors.yaml` 预置 `executor_vendor_api_domestic_default` 与 `executor_vendor_api_global_default`。
- Baidu/Volcengine/KIE/OpenAI/OpenAI-compatible 优先路由到 `vendor_api` executor。
- 保留 `VENDOR_API_LEGACY_FALLBACK_ENABLED` 作为迁移期回退开关。
- OpenAI 图片编辑能力已进入能力 seed，schema 包含蒙版、多图、尺寸和质量字段。
- `AbilityTask` running 任务可通过 `vendorInvocationId` 轮询 vendor-api-ops，而不是直接轮询第三方厂商。

## 6. 配置约定

推荐端口：

- Coze 主机 backend：`8099`
- 管理端 admin：`8199`
- 测评端 eval：`8200`
- image-ops：如独立部署，建议使用 `8301`
- vendor-api-ops：建议 `8310`

建议环境变量：

```env
VENDOR_API_OPS_PORT=8310
VENDOR_API_OPS_ADMIN_TOKEN=change-me
OPENAI_BASE_URL=https://api.openai.com
OPENAI_API_KEY=...
VOLCENGINE_BASE_URL=https://ark.cn-beijing.volces.com
VOLCENGINE_API_KEY=...
BAIDU_BASE_URL=https://aip.baidubce.com
BAIDU_API_KEY=...
BAIDU_SECRET_KEY=...
HTTPS_PROXY=
HTTP_PROXY=
```

backend 推荐环境变量：

```env
VENDOR_API_ENABLED=true
VENDOR_API_BASE_URL=http://117.50.80.158:8310
VENDOR_API_TIMEOUT_SECONDS=180
VENDOR_API_LEGACY_FALLBACK_ENABLED=true
```

如在国内服务器无法访问 OpenAI：

- vendor-api-ops 必须部署在有稳定国际出口的节点。
- 或配置明确代理。
- backend 只配置 executor baseUrl，不直接访问 OpenAI。

## 7. backend executor 约定

新增 executor 类型：

```yaml
- id: executor_vendor_api_global_default
  name: Vendor API Ops · Global Egress Node
  type: vendor_api
  base_url: http://<vendor-api-ops-host>:8310
  status: active
  max_concurrency: 4
  weight: 9
  config:
    providers: ["openai", "openai_compatible"]
    tags: ["vendor-api", "global-egress"]
    fallbackToDefault: false
```

路由规则：

- OpenAI 能力必须显式绑定 `executor_openai_global` 或 required tags。
- OpenAI 调用失败时，不允许 fallback 到 Coze 主机本地。
- 需要特殊网络出口的 provider，都必须标记 `global-egress`。

## 8. 错误码

已进入错误码总表或本版本新增：

- `VENDOR_API_EXECUTOR_UNAVAILABLE`
- `VENDOR_API_PROVIDER_NOT_SUPPORTED`
- `VENDOR_API_INVOCATION_NOT_FOUND`
- `VENDOR_API_CONCURRENCY_LIMITED`
- `VENDOR_API_KEY_DISABLED`
- `VENDOR_API_KEY_MISSING`
- `VENDOR_API_RATE_LIMITED`
- `VENDOR_API_TIMEOUT`
- `VENDOR_API_UPSTREAM_ERROR`
- `VENDOR_API_PROXY_UNAVAILABLE`
- `VENDOR_API_RESPONSE_INVALID`

## 9. 测试计划

上线前必须验证：

- Coze 主机访问 vendor-api-ops `/health` 正常。
- vendor-api-ops 所在机器访问 OpenAI 或中转站正常。
- backend 调用 vendor-api executor 正常。
- Coze 工具箱只指向 backend。
- 所有执行工具仍返回平台 `taskId`，`tasks/get` 能拿终态。
- 同步成功、异步提交后轮询、vendor 回调后查询、vendor 超时均有覆盖。
- Key 缺失、禁用、429 冷却、多 Key 轮换、额度耗尽均能归一错误。
- backend executor 并发、provider/model 并发、key 并发分别生效。
- URL 下载、Base64 上传、图片/视频回填、OSS 失败错误均能被平台归一。
- OpenAI Key 缺失时返回可读错误，不暴露敏感信息。
- OpenAI 网络超时时返回 `VENDOR_API_TIMEOUT` 或 `VENDOR_API_PROXY_UNAVAILABLE`。
- 调用日志中记录 provider/model/latency/status/errorCode。

## 10. 回滚

回滚原则：

- 不动 Coze 工作流编排。
- 先下线对应 backend ability 或改为 inactive。
- 保留 vendor-api-ops 服务和日志用于排查。
- 不删除 Key 数据。

如果 vendor-api-ops 异常：

1. backend 将对应 executor 标记 inactive。
2. Coze 工具箱继续存在，但调用返回“能力暂不可用”。
3. 修复服务后恢复 executor active。

## 11. 当前结论

- API 接入也是原子能力。
- 第三方 API 原子能力不放 image-ops。
- 新增 `vendor-api-ops` 作为第三方 API 执行面是后续标准路径。
- backend 继续统一暴露 Coze 工具箱；业务编排仍在 Coze 中完成。
- 统一的是任务状态、错误 envelope、日志关联和 OSS 输出，不是强行统一厂商参数。
