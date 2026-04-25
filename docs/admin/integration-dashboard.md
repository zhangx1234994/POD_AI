# 管理端 · Integration Dashboard（子功能说明）

> 版本：2026-02-06  
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
- 在同一页内完成“能力列表 + 能力详情 + 实时测试 + 调用记录”（工作区合并）

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

### 第三方 API 治理摘要
- `GET /api/admin/vendor-api/governance/summary`
- 汇总供应商、模型目录、原子能力、密钥来源、最近调用统计和缺口提示。
- 该接口面向后续前端重构使用，前端可以先展示“哪些供应商可用、哪些缺密钥、哪些最近失败”，不需要让用户理解底层 executor。

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
- 2026-03-05 起，“能力详情/测试”已并入“能力管理”页内工作区；旧侧栏入口已下线，仅保留 hash 兼容（`#nav=ability-tests` 自动跳转到能力目录测试 Tab）。

## 8. 能力调用（Ability Logs & Metrics）

### 职责
- 指标与清单统一在一个功能内（Tab 切换）
- 按能力聚合调用次数、成功率、耗时分位，评估稳定性与成本趋势
- 查询最近调用记录（支持按厂商/能力/来源/状态筛选）
- 快捷查看“失败/回调异常”
- 快速定位失败原因
- 展示回调 ID（便于业务侧查询任务状态）
- 列表状态拆分为两段：`提交`（是否成功提交）+ `回调阶段`（回调/结果回填是否完成）
- `提交` 文案统一：提交中/提交成功/提交失败/已取消（兼容 `success/succeeded/completed/...`）
- `回调阶段` 文案统一：待回调/回调中/回调成功/回调失败/结果回填中/结果已回填/未配置
- 结果预览统一兜底：优先 `stored_url`、其次 `result_assets`，再回退 `response_payload.images/assets/resultUrls`
- 耗时展示统一优先 `duration_ms`（全链路耗时），仅历史脏数据时回退 `response_payload.durationMs`

### 后端接口
- `GET /api/admin/abilities/{id}/logs`
- `GET /api/admin/abilities/logs`
- `GET /api/admin/abilities/logs/metrics`

## 8.1. 业务能力（Business Capabilities）

### 职责
- 管理图裂变、扩图等业务版本，控制默认版本、灰度比例和发布时间
- 把底层原子能力、VL 前置分析和灰度策略组合成业务侧可理解的版本
- 让运营通过表单配置“伴随式 VL”或“串联式 VL”，减少手写 JSON

### VL 配置口径
- 伴随模式：主出图任务立即提交，VL 只做记录和观测。
- 串联模式：先跑 VL，成功后再提交主出图任务；VL 失败时主任务不提交。
- “用 VL 结果补主任务提示词”开启后，业务层会把 `promptCard.imageDesc` 回填到图裂变 `image_desc`，把 `promptCard.positivePrompt` 回填到图裂变/扩图 `prompt`。

### 后端接口
- `GET /api/admin/business/capabilities`
- `POST /api/admin/business/capabilities`
- `PUT /api/admin/business/capabilities/{id}`
- `GET /api/admin/business/runs`
- `GET /api/admin/business/usage-summary`

## 9. ComfyUI 管理

### 职责
- 维护 LoRA / 模型 / 插件资源清单
- 维护 ComfyUI 版本清单（tag/commit/下载地址）
- 多台 ComfyUI 服务器对齐（基准对比、差异快照）
- 管理 ComfyUI 模板（Workflow JSON、依赖与允许运行节点）
- 管理 **代理服务 / 清单 / 任务下发**（与 ComfyUI 服务器一致性同步）

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
- **LoRA 素材库默认只加载“库内记录”**，避免首次打开卡顿；如需发现服务器上的“未入库 LoRA”，点击“查看未入库 LoRA”按钮再扫描执行节点。
- 模型清单应尽量维护“模型名称”（display_name），列表会优先显示名称，空时回退文件名。
- 版本清单支持“增量同步版本”（拉取线上 tag），并可通过“刷新服务器版本”标记当前在用版本。
- 对齐快照只记录差异与建议清单；模型/插件的实际安装需由 ComfyUI 服务器侧执行。
- 选择基准服务器后，再刷新各节点模型与插件列表，以保证对比准确。
- 插件差异支持按仓库去重导出，便于任务下发时避免重复安装同一仓库。
- 子页签命名已统一为业务语义：
  - `清单发布（版本）`：定义目标版本清单
  - `下发任务（执行记录）`：查看清单/动作下发结果
  - 避免“清单/任务”语义过泛导致误解

## 9.1 交互与自适配约束（2026-03 更新）

- Header 操作区允许自动换行，窄屏不再挤压到不可点击。
- 全局壳层在超窄屏（<980）会进一步压缩侧栏、Header 与内容区间距，优先保障主工作区。
- ComfyUI 管理页顶部分组按钮允许换行，避免 1024~1366 宽度下超出容器。
- ComfyUI 管理页“模块选择 + 上下模块 + 显示测试节点”改为响应式工具条，小屏自动分行并去掉多余顶边距。
- ComfyUI 管理页新增“当前模块（所属分类）”提示，降低“清单/任务”语义理解成本。
- ComfyUI 管理页二级导航改为“分类 + 模块”双下拉，并保留“上一模块/下一模块”，减少多行按钮造成的认知负担。
- ComfyUI 二级模块支持 hash 同步（`#nav=comfyui-management&comfyTab=...`），刷新/分享链接可保持当前模块上下文。
- ComfyUI 页新增“三段流程导览卡”（资源目录/同步发布/节点运维），用于提示标准操作顺序，降低新人学习成本。
- 进入“同步发布”时，额外显示“服务器对比 -> 清单发布 -> 任务下发”的三步执行面板，并展示每步关键计数。
- 三步执行面板增加状态徽章（前置未满足/待处理/进行中/已完成），帮助运维判断当前是否可进入下一步。
- “同步发布”顶部新增操作条，仅保留一个主 CTA（按步骤动态：下一步/新增清单/创建任务），并提供当前步骤刷新入口。
- “同步发布”新增统一引导卡：每一步都展示“进入条件 / 完成条件 / 失败后建议”，减少口径不一致。
- “服务器对比”步骤新增“辅助面板折叠”，默认聚焦主对比区；新增服务器与历史对齐按需展开。
- “清单发布”步骤新增“修复任务折叠”，默认聚焦清单发布；修复回执按需展开查看。
- 在“任务下发”步骤中，监控与历史区域默认折叠，仅保留任务创建主工作区；需要排障时再展开查看。
- “任务下发”列表列名统一为“提交阶段 / 回调阶段 / 最终状态”，与状态契约一致。
- “任务下发”失败原因列接入高频错误码映射（如 `Q1001`/`AGENT_PUSH_FAILED`），默认展示“可读文案 + 错误码”。
- “能力调用记录”与“能力详情错误提示”同步接入错误码映射，统一展示口径。
- 固定宽度选择器改为 `min(100%, Npx)`，保证小屏先可用再保证密度。
- 1366 以下自动将多列表单列（`Col 12/10/8/6/4`）切换为单列，优先保证可读性与可操作性。
- 内容区统一右侧滚动容器，避免外层 `overflow` 导致内页被截断。
- 侧栏宽度按窗口尺寸分级收紧（248/200/176），优先保证主工作区操作空间。
- 侧栏新增“收紧侧栏/展开侧栏”开关，并持久化到本地（localStorage），便于每位管理员按屏幕习惯固定布局。

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
