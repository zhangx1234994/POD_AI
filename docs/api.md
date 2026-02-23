# PODI API 总览（最新）

> 说明：本文件为 **最新 API 总览**，取代旧版散落文档。所有详细接口请以 `docs/api/INDEX.md` 与模块文档为准。

## 1. 统一入口

- **后端服务**：`http://<backend-host>:8099`
- **管理端**：`http://<backend-host>:8199`
- **评测端**：`http://<backend-host>:8200`
- **统一 API 前缀**：`/api/*`

## 2. 鉴权说明

- **管理端接口**：管理员 JWT（`Authorization: Bearer <accessToken>`）
- **能力调用接口**：用户 JWT 或 `SERVICE_API_TOKEN`
- **评测端公开接口**：`EVAL_PUBLIC_TOKEN`（可选）
- **评测端管理接口**：`EVAL_ADMIN_TOKEN`
- **Agent 接口**：`task_token / agent_token`（详见模块文档）

## 3. 模块文档索引

请以模块文档为准（每个模块包含用途/说明/示例/错误）：

- `docs/api/INDEX.md`：接口总索引（强制入口）
- `docs/api/modules/overview.md`：基础约定与端口
- `docs/api/modules/auth.md`：登录与刷新
- `docs/api/modules/abilities.md`：统一能力调用
- `docs/api/modules/admin-core.md`：管理端核心接口
- `docs/api/modules/comfyui-admin.md`：ComfyUI 管理
- `docs/api/modules/agent.md`：Agent 回执/心跳/清单
- `docs/api/modules/eval.md`：评测平台
- `docs/api/modules/coze.md`：Coze 插件/工具箱
- `docs/api/modules/media.md`：媒资上传与回调

## 4. 错误与契约

- 错误码总表：`docs/standards/error-catalog.md`
- 错误契约规范：`docs/standards/error-contract.md`

## 5. 更新规则

1. 接口新增/变更必须同步模块文档。  
2. 字段/错误码变更必须更新错误码总表。  
3. 评测端/管理端变更需同步文档与前端实现。  

