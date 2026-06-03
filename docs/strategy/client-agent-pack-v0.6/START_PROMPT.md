# START PROMPT

Copy the following prompt into a new agent thread.

```text
你负责新客户端 PODI Studio Preview。请先阅读并遵守：

- docs/strategy/client-agent-pack-v0.6/README.md
- docs/strategy/ability-governance-operating-model-v0.6.md
- docs/strategy/client-agent-pack-v0.6/01-agent-brief.md
- docs/strategy/client-agent-pack-v0.6/02-product-mvp.md
- docs/strategy/client-agent-pack-v0.6/03-ui-flow.md
- docs/strategy/client-agent-pack-v0.6/04-api-contract.md
- docs/strategy/client-agent-pack-v0.6/05-acceptance-checklist.md
- docs/strategy/client-agent-pack-v0.6/06-gap-log-template.md

任务目标：
从零开始实现 PODI Studio Preview 的客户端 MVP。客户端负责把中台业务能力组织成用户可操作的生产动线，中台负责能力治理和能力封装。不要把客户端做成项目管理系统；客户端主上下文使用 workItemId/clientContextId，projectId 只在复用兼容 /api/business/projects/* 时作为技术映射。不要复活旧 podi-client-web、podi-client-v2、podi-design-web-dev，也不要重构 backend、podi-admin-web、podi-eval-web。

硬边界：
客户端只能消费 /api/business/*、必要的兼容 /api/business/projects/* 和受控 /api/media/*。禁止调用 /api/admin/*、/api/evals/*、/api/abilities/*、/api/ability-tasks/*、/api/coze/*、ComfyUI、vendor-api、image-ops 内部地址。

首版只做这条能力工作台业务流：
能力工作台 -> 创建/打开工作单 -> 选择生产动作 -> 上传/登记素材 -> 花纹提取 -> 裂变候选 -> 选择候选 -> 产品图/组图占位或可用能力 -> 交付包草稿。

首版页面：
- /workbench
- /workbench/:workItemId
- /workbench/:workItemId/abilities/:abilityKey
- /assets
- /tasks
- /exports/:packageId

执行要求：
1. 先检查仓库当前是否已有新的客户端目录；如果没有，创建新的客户端工程目录，命名建议 podi-studio-preview。
2. 不使用历史客户端代码作为基础。
3. 做真实可运行页面，不做营销落地页，也不要做项目管理首页。
4. 使用业务动作语言隐藏技术细节，高级参数默认折叠。
5. 异步任务必须展示 queued/running/succeeded/failed 和 runId。
6. 发现中台 API 缺口时，按 docs/strategy/client-agent-pack-v0.6/06-gap-log-template.md 记录，不要绕过边界。
7. 完成后运行 lint/build，并用浏览器走查关键页面和交互。

最终汇报：
- 本地启动 URL
- 已实现页面和流程
- 调用的业务 API
- 发现的 API 缺口
- 测试和浏览器验证结果
- 剩余风险
```
