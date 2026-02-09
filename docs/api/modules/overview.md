# 接口文档总览

## 1. 用途

- 统一说明后端访问方式、鉴权类型、错误契约与通用约定。
- 具体接口的入参与返回，以各模块文档为准。

## 2. 基础信息

- **后端服务端口**：`8099`
- **管理端**：`8199`（同源代理 `/api/*`）
- **评测端**：`8200`（同源代理 `/api/*`）
- **健康检查**：`GET /health`
- **OpenAPI**：`GET /docs`、`GET /openapi.json`

> 建议本地统一使用 `http://127.0.0.1:8099`，避免 `localhost` 带来的代理/缓存差异。

## 3. 鉴权类型

### 3.1 用户/管理员 Bearer Token

- 获取：`POST /api/auth/login` → `accessToken`
- 使用：`Authorization: Bearer <accessToken>`
- 管理端接口会校验管理员权限（错误码 `ADMIN_ONLY`）

### 3.2 Agent Token（ComfyUI 服务器管理）

- **scope=agent**：用于心跳/告警
- **scope=task**：用于任务回执/manifest
- 调试可启用 `AGENT_DEBUG_TOKENS`（仅开发环境）

### 3.3 Coze 插件（内部调用）

- 允许内网请求（`COZE_TRUSTED_IPS`）
- 或使用 `SERVICE_API_TOKEN` 作为 Bearer Token

### 3.4 评测平台 Token

- 公共评测：`EVAL_PUBLIC_TOKEN`（Header: `X-Eval-Token` 或 URL `?token=`）
- 评测管理：`EVAL_ADMIN_TOKEN`（Header: `X-Eval-Admin-Token` 或 URL `?admin_token=`）

## 4. 通用响应与错误契约

- 大部分接口返回 **JSON**。
- 部分老接口返回 `{code, data, message}`，以具体模块文档为准。
- **错误契约**与错误码总表：
  - `docs/standards/error-contract.md`
  - `docs/standards/error-catalog.md`
- 队列类错误遵循强约束格式：`ERR|<CODE>|<message>`（如 `Q1001`）。

## 5. 任务/回调 ID 约定

- 能力任务 `taskId` 支持新旧两种格式：
  - 新格式：`t1.<provider>.<executorId>.<hex>`（可解析路由）
  - 旧格式：`<hex>`（仍兼容）
- `/api/coze/podi/tasks/get` 会同时兼容两种格式。

## 6. 通用参数约定

- **分页**：部分接口使用 `limit/offset`，部分使用 `page/size`；以接口说明为准。
- **时间**：统一 ISO8601（UTC），管理端展示为本地时区。
- **图片参数**：多数流程统一 `url`（字符串），详见评测与能力接口说明。
