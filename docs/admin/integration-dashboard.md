# 管理端 · Integration Dashboard（子功能说明）

> 版本：2026-02-05  
> 目标：面向运营/研发，解释每个模块的**职责、输入输出、与后端契约**，同时标注注意事项。

## 1. 总览（Overview）

- 入口：管理端 `podi-admin-web` → Integration Dashboard
- 目标：统一管理 **执行节点 / 能力 / 工作流 / 绑定 / API Key / 测试 / 日志**

## 2. 执行节点（Executors）

### 职责
- 注册执行节点（ComfyUI / 商业模型 / 其他厂商）
- 查看节点状态、并发配置、基础信息

### 后端接口
- `GET /api/admin/executors`
- `POST /api/admin/executors`
- `PUT /api/admin/executors/{id}`
- `DELETE /api/admin/executors/{id}`

### 注意事项
- 执行节点信息来自 `config/executors.yaml` + 数据库同步
- **不要在能力中硬编码节点地址**

## 3. 能力管理（Abilities）

### 职责
- 配置 `input_schema` / 默认参数 / metadata
- 统一能力调用入口：`/api/abilities`

### 后端接口
- `GET /api/admin/abilities`
- `POST /api/admin/abilities`
- `PUT /api/admin/abilities/{id}`
- `DELETE /api/admin/abilities/{id}`

### 注意事项
- 输入字段必须与业务文档一致（尤其是 `url`）
- 枚举字段必须提供 options

## 4. 工作流（Workflows）

### 职责
- 管理 ComfyUI workflow JSON
- 版本更新与绑定关系

### 后端接口
- `GET /api/admin/workflows`
- `POST /api/admin/workflows`
- `PUT /api/admin/workflows/{id}`
- `DELETE /api/admin/workflows/{id}`

## 5. 绑定（Workflow Bindings）

### 职责
- 将能力与 workflow + executor 绑定
- 控制路由与优先级

### 后端接口
- `GET /api/admin/workflow-bindings`
- `POST /api/admin/workflow-bindings`
- `PUT /api/admin/workflow-bindings/{id}`
- `DELETE /api/admin/workflow-bindings/{id}`

## 6. API Key 管理

### 职责
- 维护第三方凭证（可多 key 轮换）
- 控制启用/禁用

### 后端接口
- `GET /api/admin/api-keys`
- `POST /api/admin/api-keys`
- `PUT /api/admin/api-keys/{id}`
- `DELETE /api/admin/api-keys/{id}`

## 7. 能力测试（Ability Test）

### 职责
- 根据 schema 动态渲染表单
- 选择执行节点并提交测试
- 展示结果（文本/图片/视频）

### 后端接口（按 provider）
- Baidu: `/api/admin/tests/baidu/*`
- Volcengine: `/api/admin/tests/volcengine/*`
- ComfyUI: `/api/admin/tests/comfyui/*`
- KIE: `/api/admin/tests/kie/*`

### 注意事项
- 输入统一 `url`
- 回调类输出为 `taskId`

## 8. 能力调用（Ability Logs & Metrics）

### 职责
- 指标与清单统一在一个功能内（Tab 切换）
- 按能力聚合调用次数、成功率、耗时分位，评估稳定性与成本趋势
- 查询最近调用记录（支持按厂商/能力/来源/状态筛选）
- 快捷查看“失败/回调异常”
- 快速定位失败原因
- 展示回调 ID（便于业务侧查询任务状态）

### 后端接口
- `GET /api/admin/abilities/{id}/logs`
- `GET /api/admin/abilities/logs`
- `GET /api/admin/abilities/logs/metrics`

## 9. ComfyUI 管理

### 职责
- 维护 LoRA / 模型 / 插件资源清单
- 维护 ComfyUI 版本清单（tag/commit/下载地址）
- 多台 ComfyUI 服务器对齐（基准对比、差异快照）
- 管理 ComfyUI 模板（Workflow JSON、依赖与允许运行节点）
- 管理 Agent / Manifest / 任务下发（与 ComfyUI 服务器一致性同步）

### 后端接口
- `GET /api/admin/comfyui/loras`
- `POST /api/admin/comfyui/loras`
- `PUT /api/admin/comfyui/loras/{id}`
- `DELETE /api/admin/comfyui/loras/{id}`
- `GET /api/admin/comfyui/model-catalog`
- `POST /api/admin/comfyui/model-catalog`
- `PUT /api/admin/comfyui/model-catalog/{id}`
- `DELETE /api/admin/comfyui/model-catalog/{id}`
- `GET /api/admin/comfyui/plugin-catalog`
- `POST /api/admin/comfyui/plugin-catalog`
- `PUT /api/admin/comfyui/plugin-catalog/{id}`
- `DELETE /api/admin/comfyui/plugin-catalog/{id}`
- `GET /api/admin/comfyui/version-catalog`
- `POST /api/admin/comfyui/version-catalog`
- `PUT /api/admin/comfyui/version-catalog/{id}`
- `DELETE /api/admin/comfyui/version-catalog/{id}`
- `POST /api/admin/comfyui/version-catalog/sync`
- `GET /api/admin/comfyui/models?executorId=...&includeNodes=true`
- `GET /api/admin/comfyui/system-stats?executorId=...`
- `POST /api/admin/comfyui/server-diff`
- `GET /api/admin/comfyui/server-diff`
- `GET /api/admin/comfyui/agents`
- `POST /api/admin/comfyui/agents`
- `PUT /api/admin/comfyui/agents/{agent_id}`
- `DELETE /api/admin/comfyui/agents/{agent_id}`
- `POST /api/admin/comfyui/agents/{agent_id}/token`
- `GET /api/admin/comfyui/manifests`
- `POST /api/admin/comfyui/manifests`
- `GET /api/admin/comfyui/manifests/{id}`
- `PUT /api/admin/comfyui/manifests/{id}`
- `GET /api/admin/comfyui/tasks`
- `POST /api/admin/comfyui/tasks`
- `GET /api/admin/comfyui/tasks/{task_id}`
- `POST /api/admin/comfyui/tasks/{task_id}/push`
- `GET /api/admin/comfyui/tasks/{task_id}/events`
- `GET /api/admin/comfyui/alerts`

### 注意事项
- 对齐快照只记录差异与建议清单；模型/插件的实际安装需由 ComfyUI 服务器侧执行。
- 选择基准服务器后，再刷新各节点模型与插件列表，以保证对比准确。
- 插件差异支持按仓库去重导出，便于任务下发时避免重复安装同一仓库。

## 10. ComfyUI 队列状态（Queue）

### 职责
- 展示节点运行中/排队数量

### 后端接口
- `/api/admin/comfyui/queue-status`
- `/api/admin/comfyui/queue-summary`

### 注意事项
- 队列满会直接返回错误码（详见 `docs/standards/queue-and-error-standards.md`）

## 11. 问题与优化记录

详见 `docs/standards/issue-improvement-log.md`
