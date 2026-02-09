# 接口总索引（统一入口）

本文件是**接口目录**与分模块索引。每个模块都有独立接口文档（含用途/说明/示例），便于查询与对外交付。

> 统一后端服务端口：`8099`  
> 前端端口：管理端 `8199`，评测端 `8200`（通过同源代理调用后端 `/api/*`）

---

## 模块文档目录

| 模块 | 文档 |
| --- | --- |
| 总览 | `docs/api/modules/overview.md` |
| 认证与用户 | `docs/api/modules/auth.md` |
| 媒资与上传 | `docs/api/modules/media.md` |
| 统一能力调用 | `docs/api/modules/abilities.md` |
| Coze 插件 | `docs/api/modules/coze.md` |
| ComfyUI 管理 | `docs/api/modules/comfyui-admin.md` |
| ComfyUI Agent | `docs/api/modules/agent.md` |
| 评测平台 | `docs/api/modules/eval.md` |
| 管理端核心 | `docs/api/modules/admin-core.md` |
| 任务与调度 | `docs/api/modules/tasks.md` |
| 通知/钱包 | `docs/api/modules/notify-wallet.md` |

---

## 维护规则

1. 新增/变更接口必须同步更新对应模块文档。  
2. 若模块出现新增字段或错误码，必须同步 `docs/standards/error-catalog.md`。  
3. 评测端/管理端参数变更需同步前端与文档。
