# 接口总索引（统一入口）

本文件只负责两件事：

1. 指向当前有效的接口模块文档
2. 规定接口文档更新时必须同步的规范入口

> 统一后端服务端口：`8099`
> 前端端口：管理端 `8199`，评测端 `8200`（通过同源代理调用后端 `/api/*`）

---

## 模块文档目录

| 模块 | 文档 |
| --- | --- |
| 总览 | `docs/api/modules/overview.md` |
| 认证与用户 | `docs/api/modules/auth.md` |
| 媒资与上传 | `docs/api/modules/media.md` |
| 业务能力接口 | `docs/api/modules/business.md` |
| 图裂变业务接入 Demo | `docs/api/examples/business-fission-quickstart.md` |
| 图裂变交付契约图 | `docs/api/examples/fission-delivery-contract-2026-05-12.md` |
| 统一能力调用 | `docs/api/modules/abilities.md` |
| Coze 插件 | `docs/api/modules/coze.md` |
| ComfyUI 管理 | `docs/api/modules/comfyui-admin.md` |
| ComfyUI Agent | `docs/api/modules/agent.md` |
| 评测平台 | `docs/api/modules/eval.md` |
| 管理端核心 | `docs/api/modules/admin-core.md` |
| 管理端账单 | `docs/api/modules/admin-billing.md` |
| 任务与调度 | `docs/api/modules/tasks.md` |
| 通知/钱包 | `docs/api/modules/notify-wallet.md` |

---

## 管理端 API 开放页对应关系

管理端“API 开放”页分为三类入口：

| 页面分组 | 模块文档 | 回归清单 |
| --- | --- | --- |
| 中台自有业务 API | `docs/api/modules/business.md` | `docs/testing/API_EXPOSURE_SMOKE_CHECKLIST.md` |
| 中台原子能力 API | `docs/api/modules/abilities.md` | `docs/testing/API_EXPOSURE_SMOKE_CHECKLIST.md` |
| Coze 工具箱 API | `docs/api/modules/coze.md` | `docs/testing/API_EXPOSURE_SMOKE_CHECKLIST.md` |

这三类入口任意新增或改名时，必须同步更新管理端页面、模块文档、错误码说明和冒烟清单。

后续页面展示不再按三类入口平铺为主，而是优先按业务分类组织。分类真源见：

- `docs/standards/business-interface-taxonomy.md`

同一业务分类下同时展示“原生业务 API / Coze 工具箱 / 原子能力 API / 测评入口”，避免业务方在多个技术列表中找同一个功能。

---

## 维护规则

1. 新增/变更接口必须同步更新对应模块文档。
2. 若模块出现新增字段或错误码，必须同步 `docs/standards/error-catalog.md`。
3. 评测端/管理端参数变更需同步前端与文档。
4. 涉及状态词、错误处理、结果预览回填逻辑时，必须同步 `docs/standards/interface-consistency.md`。
5. 若接口属于当前平台主链路，应同时检查 `docs/README.md` 是否需要补入口说明。
