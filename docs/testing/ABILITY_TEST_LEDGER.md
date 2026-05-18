# 能力测试台账与上线闸门

> 目的：所有能力上线前必须有可执行、可追溯的测试记录，不能依赖人工随便点几下发现问题。

## 1. 上线闸门

每次发版前必须按顺序执行：

| 顺序 | 检查项 | 命令/动作 | 阻断规则 |
| --- | --- | --- | --- |
| 1 | 静态覆盖审计 | `cd backend && python3 scripts/audit_ability_test_coverage.py --probe-comfyui --fail-on P1` | 出现 P0/P1 不允许上线 |
| 2 | 后端单测 | `cd backend && python3 -m pytest tests/test_ability_test_coverage_audit.py tests/test_ability_catalog_cleanup.py tests/test_routing_governance.py tests/test_comfyui_queue_routing.py -q` | 失败不允许上线 |
| 3 | 测评工作流巡检 | `cd backend && python3 scripts/patrol_eval_workflows.py --base-url http://127.0.0.1:8099 --role production --max-in-flight 1 --timeout 1800` | 失败、成功无输出、无 taskId 不允许上线 |
| 4 | 运行健康检查 | `cd backend && python3 scripts/check_eval_operations_health.py` | critical 不允许上线，warning 必须记录原因 |
| 5 | 前端构建 | `cd podi-admin-web && npm run build`；`cd podi-eval-web && npm run build` | 构建失败不允许上线 |

说明：

| 级别 | 含义 | 处理 |
| --- | --- | --- |
| P0 | 会导致业务入口整体不可用 | 立即修复，不允许绕过 |
| P1 | 会导致能力误路由、任务无法提交、节点不可达、测试节点误入生产 | 立即修复，不允许上线 |
| P2 | 会导致测试不完整、表单不清晰、追踪信息不充分 | 可带记录进入下一轮，但必须排期 |
| P3 | 低风险改进 | 记录即可 |

## 2. 功能测试台账

| 功能族 | 当前入口 | 必测用例 | 必查链路 | 记录位置 |
| --- | --- | --- | --- | --- |
| 图裂变 | 测评端、Coze 工具箱、中台业务 API | 原图 URL、裂变幅度、数量 1、回调查询 | Coze 提交 -> 中台任务 -> ComfyUI 158/233 路由 -> OSS 回填 -> 测评端展示 | 巡检报告 + 能力调用记录 |
| 扩图 | 测评端、Coze 工具箱、中台业务 API | 原图 URL、上下左右扩展、宽高、数量 1 | Coze 提交 -> 中台任务 -> ComfyUI 路由 -> OSS 回填 -> 输出尺寸变化 | 巡检报告 + 能力调用记录 |
| 花纹提取 | 管理端能力测试、业务 API | 原图 URL、输出宽高、LoRA 默认值 | 管理端上传 -> OSS -> ComfyUI -> OSS 回填 -> 预览 | 能力调用记录 |
| 抠图/头部抠像 | 测评端、Coze 工具箱 | 原图 URL、默认参数 | Coze 提交 -> 中台任务 -> ComfyUI 路由 -> 透明图/结果图回填 | 巡检报告 + 能力调用记录 |
| 多图融合 | 测评端、Coze 工具箱 | 多图 URL、提示词、输出数量 1 | 参数数组 -> Coze -> 中台 -> ComfyUI -> OSS 多图结果 | 巡检报告 |
| 四方连续 | 测评端、Coze 工具箱 | 原图 URL、是否连续、输出数量 1 | Coze -> 中台任务 -> ComfyUI -> 中心/边缘结果检查 | 巡检报告 |
| 文字增强 | 测评端、Coze 工具箱 | 原图 URL、提示词、重绘幅度 | Coze -> 中台任务 -> ComfyUI -> OSS 回填 | 巡检报告 |
| 高清放大/DPI | image-ops、中台工具箱 | 原图 URL、目标尺寸/DPI | 中台 -> image-ops -> OSS 回填；不得落到 Coze 主机本机执行 | 能力调用记录 + 服务健康 |
| 百度图像处理 | 管理端能力测试 | 图片 URL、无损放大分辨率、普通处理默认参数 | 管理端上传 -> OSS -> 百度执行节点 -> OSS 回填 | 能力调用记录 |
| 火山能力 | 管理端能力测试、vendor-api-ops | 文生图、图文理解、视频任务 | 中台 -> vendor-api-ops -> 火山 -> OSS/文本回填 | 能力调用记录 + vendor 记录 |
| KIE 能力 | 管理端能力测试、vendor-api-ops | 图生图、文生视频、余额不足错误 | 中台 -> vendor-api-ops -> KIE 创建任务 -> 轮询 -> OSS 回填 | 能力调用记录 + vendor 记录 |
| OpenAI 能力 | 管理端能力测试、vendor-api-ops | 文生图、图片编辑、蒙版、多图 | 中台 -> vendor-api-ops -> OpenAI -> OSS 回填；不暴露 Key | 能力调用记录 + vendor 记录 |
| VL 图像理解 | 管理端能力测试、业务 API | 图片 URL、结构化分析 | 中台 -> provider -> JSON 输出；不要求图片回填 | 能力调用记录 |
| 管理端 | 8199 build 产物 | 能力、执行节点、ComfyUI 管理、日志分页 | 登录 -> 数据加载 -> 详情可读 -> 翻页可用 | 前端构建 + 手工走查截图 |
| 测评端 | 8200 build 产物 | 首页分组、功能卡片、任务提交、任务追踪 | 选择功能 -> 提交 -> 轮询 -> 结果展示/错误展示 | 巡检报告 + 手工走查截图 |

## 3. 当前已固化检查

| 检查 | 覆盖问题 |
| --- | --- |
| `audit_ability_test_coverage.py` | active 测试节点、ComfyUI 节点不可达、ComfyUI 能力只路由到单机、能力 schema 为空、公开测评工作流 schema 缺失、第三方能力缺少模型绑定/模型验收/计价 |
| `patrol_eval_workflows.py` | 生产主入口能否提交、轮询、拿到图片、视频、文字/VL 或结构化输出，并输出结果类型汇总 |
| `check_eval_operations_health.py` | 长时间运行、提交卡住、成功无结果、近期失败聚合 |
| `test_comfyui_queue_routing.py` | 队列路由、排队满后的换机与失败契约 |
| `test_ability_catalog_cleanup.py` | 种子同步能修复旧能力元数据和空 schema |

## 4. 新能力接入要求

新增或修改任何能力时，必须按顺序完成下面流程。不能只把能力跑通就结束；页面、文档、错误和测试证据必须同批落地。

### 4.1 标准接入流程

| 顺序 | 项目 | 必须完成 | 阻断规则 |
| --- | --- | --- | --- |
| 1 | 能力归类 | 先判断是图片、视频、文字、VL 图像理解、结构化结果还是普通资源；同时确定入口是业务 API、原子能力 API、Coze 工具箱，或三者都需要。 | 类型不清不允许进入页面和工具箱，避免后续仍按“生图”单一口径展示。 |
| 2 | 能力定义 | `backend/app/constants/abilities.py` 或后台能力表必须补齐 `defaults`、`input_schema.fields`、`metadata`、输出类型说明；字段必须有中文 + English 标签和描述。 | 缺 schema、隐藏必填字段、字段描述只有英文或只有底层节点名，均不允许上线。 |
| 3 | 路由配置 | `config/executors.yaml`、能力元数据和数据库最终态必须一致；普通能力覆盖所有可用普通节点，专用能力写明 `required_executor_tags` / `allowed_executor_ids` / `fallback_to_default`。 | 普通 ComfyUI 能力只绑单机、重能力允许 fallback、数据库最终态与代码不一致，均阻断。 |
| 4 | 页面露出 | 管理端能力目录、能力测试、能力调用记录必须能看到该能力；若是业务能力，还要在业务能力页/API 开放页露出；若是评测能力，还要同步测评端卡片和分组。 | 能力只能通过手工 curl 或隐藏地址使用，视为未完成。 |
| 5 | API 契约 | 对应模块文档必须写清请求、响应、错误；能力 API 见 `docs/api/modules/abilities.md`，业务 API 见 `docs/api/modules/business.md`，Coze 工具箱见 `docs/api/modules/coze.md`。 | 新接口或新字段没有文档，或者文档只有成功示例没有错误示例，均阻断。 |
| 6 | 错误口径 | 缺参、鉴权失败、依赖不可用、队列满、超时、上游失败、成功无回填必须有错误码和中文提示；新增错误码必须写入 `docs/standards/error-catalog.md`。 | 返回裸上游错误、只有英文、无错误码、错误码未登记，均阻断。 |
| 7 | 自动检查 | 至少补一个单测、契约测试或纳入 `audit_ability_test_coverage.py`；ComfyUI 能力还要覆盖路由/依赖检查，第三方能力还要覆盖 Key/计价/验收门禁。 | 只有人工点页面，没有自动测试或审计覆盖，不能标记完成。 |
| 8 | 实跑记录 | 至少跑一次管理端能力测试、业务巡检或测评端巡检，并记录报告路径、runId/taskId、输出类型和 OSS 回填情况。 | 没有可追溯的真实或半真实记录，不能进入默认版本或公开评测入口。 |
| 9 | 交付记录 | 更新唯一 TODO、回归报告和本台账；说明已测内容、未测风险、是否需要服务器更新。 | 完成项未标记、回归报告未记录，视为流程未收口。 |

### 4.2 第三方 API / 模型接入额外门禁

| 项目 | 要求 |
| --- | --- |
| 模型目录 | `vendor_model_catalog` 必须有 provider、model、apiType、能力类型、上线状态、是否需要国际出口。 |
| Key 管理 | 中台 Key 池必须存在 active Key；验证结果、最近失败和冷却状态要能在管理端“模型弹药库”看到。 |
| 计价策略 | `costPolicy` 必须能说明计费单位、单价、币种、套餐消耗和数量字段；缺计价不能进入核心业务默认版本。 |
| 验收记录 | 新模型或新版本必须有人工验收或自动验收记录；核心业务默认版本不能绕过验收。 |
| 出网验证 | OpenAI、KIE、中转站等需要国际出口的模型，必须有最近 7 天带 Key 的出网验证成功记录。 |
| 统计可查 | 最近调用数、成功率、失败分布、耗时和成本字段必须可查，不能只在 vendor-api-ops 日志里看。 |

### 4.3 ComfyUI 工作流接入额外门禁

| 项目 | 要求 |
| --- | --- |
| 工作流文件 | workflow JSON、workflow seed、binding seed 必须同批提交，不能只手工导入线上。 |
| 节点说明 | `input_schema.fields` 描述里必须写清关键节点号和业务含义，方便 AI 工作流同学定位。 |
| 双机兼容 | 普通能力必须通过 158 / 233 的 `/object_info` 依赖检查；缺模型、缺节点、缺 LoRA 必须在发版前暴露。 |
| 路由策略 | 普通能力默认允许两台普通节点；高清放大、重采样等重任务必须专用标签且 `fallback_to_default=false`。 |
| 输出回填 | 上游返回 URL、Base64、`filename/subfolder/type` 三种输出时，都必须能落 OSS 并返回平台自有链接。 |
| 队列错误 | 所有候选节点队列满时必须返回 `COMFYUI_QUEUE_FULL` 和稍后重试建议，不能长期 running。 |

### 4.4 完成判定

一个新能力只有同时满足下面条件，才允许在 TODO 中标记 `done`：

| 判定项 | 通过标准 |
| --- | --- |
| 页面可见 | 管理端或测评端能看到能力名称、业务分类、发布时间或接入状态。 |
| 文档可查 | API 文档、错误码、测试台账能找到对应说明。 |
| 错误可读 | 缺参、依赖失败、队列满、超时等错误能给出中文动作建议。 |
| 测试可复跑 | 有 pytest、审计脚本、巡检脚本或冒烟清单覆盖。 |
| 证据可追溯 | 能定位到 runId/taskId/logId、执行节点、输出类型和 OSS 回填链接。 |

## 5. 本次事故补充规则

本次问题的直接原因是数据库里 ComfyUI 能力路由元数据过旧，导致多数能力只允许路由到 158。后续要求：

| 规则 | 原因 |
| --- | --- |
| 不能只看代码里的能力常量，必须审计数据库最终态 | 线上真正参与调度的是数据库记录 |
| ComfyUI 普通能力不能只绑定一台机器 | 否则 GPU 利用率低，单机故障会放大 |
| 执行节点名称必须带 GPU 和尾号 | 避免 `117` 这种无法区分机器的描述 |
| 测试节点必须 inactive | 避免 mock 节点进入生产候选池 |
