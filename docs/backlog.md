# PODI 待办事项列表（2026-02-05）

> 注：勾选表示已完成，⚠ 表示高优先级；后续迭代时请更新日期与状态。

## 高优先级
- [ ] ⚠ 统一认证体系落地（参考 `docs/auth-plan.md`）：**进行中**。已完成 `users` 表、`/api/auth/login|refresh`、管理端登录页改造；下一步是扩展客户端登录与 RBAC 审计。
- [ ] ⚠ AI 组件库 / Pipeline Builder：定义 `ai_components` 模型、管理端配置界面、TaskDispatcher 支持多阶段执行。
- [ ] ⚠ 监控与告警：为 executors/pipeline 记录指标（成功率、耗时、错误码），管理端提供图表与告警阈值。
- [ ] ⚠ 原子能力治理：为每个 Ability 补齐 `metadata.pricing`、`SLA`、`自检计划` 字段，并把“成本/成功率/最近自检”透出到管理端；实现 `IntegrationTestService` 的定时巡检与结果看板。
- [ ] ⚠ Composable Workflow 可视化：以托管/官方 Coze Studio 为主，后续要把节点级监控、断点调试、并发/重试配置全面接入，并推动 TaskDispatcher 支持节点依赖树与 trace_id。
- [ ] ⚠ ComfyUI 资源清单补齐（下载/来源）：缺失基座模型与插件下载地址（例如 `四方连续.safetensors`、核心 custom_nodes 清单）。

## 中优先级
- [ ] 管理端的用户 & 积分管理页面：包含用户列表、积分调整、账户冻结等操作。
- [ ] 更多 AI 能力组件：百度图像修复/上色、阿里云百炼、火山引擎等，统一接入组件库与测试面板。
- [ ] 工作流版本管理：支持草稿/发布、版本对比、一键回滚。
- [ ] 任务调度器增强：支持异步节点、重试策略、任务优先级队列。
- [ ] 能力调用成本统计：结合 `ability_invocation_logs` 聚合每个能力/节点/用户的调用次数、总成本、均价，输出周报并对接预算。
- [ ] 向量库能力接入（Faiss/Milvus/阿里OpenSearch）：将 `vector_index.upsert/search/delete` 视为原子能力，纳入成本、自检、日志与统一 API。

## 低优先级 / 规划中
- [ ] Agent 工作流编排：允许 prompt 生成器、规划器、执行器组合成更复杂的链路。
- [ ] DevOps 自动化：将后端/前端/管理端纳入 CI/CD，自动部署并运行单测。
- [ ] 秘钥加密存储与审计：`executors.config` & `api_keys.key` 引入 KMS/加密字段，记录谁查看/修改。

## 已完成（近期）
- [x] 管理端独立化（`podi-admin-web`）：包含执行节点、工作流、绑定、API Key 管理及百度能力测试面板。
- [x] 百度图像处理执行器接入与测试接口 `/api/admin/tests/baidu/quality-upgrade`。
- [x] 统一能力 API (`/api/abilities`, `/api/abilities/{id}/invoke`, `/api/ability-tasks`) 与能力日志 (`ability_invocation_logs`) 上线，支持回调、异步任务、成本字段。
- [x] ComfyUI 运维能力落地：LoRA/模型下拉 (`/api/admin/comfyui/models`)、队列状态面板 (`/api/admin/comfyui/queue-status`)、多节点配置与日志透出。
- [x] ComfyUI Agent 管理落地：Agent/Manifest/任务下发、事件回执与心跳告警（`/api/agent/*`、`/api/admin/comfyui/agents|manifests|tasks`）。
- [x] 管理端“能力详情”抽屉重构：新增统一接口说明、实时测试、调用记录、成本占位、执行节点/LoRA 选择器。
