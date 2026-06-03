# v0.6 客户端业务组装并行开发交接方案

最后更新：2026-06-02

本文给客户端团队或独立 agent 使用。v0.6 主版本仍是中台能力治理与客户端支撑底座，见 `docs/strategy/mid-platform-completeness-v0.6-plan.md` 和 `docs/strategy/ability-governance-operating-model-v0.6.md`。客户端的核心职责是把中台业务能力组织成用户可操作的生产动线，不是接管中台能力治理，也不是把项目管理做成第一产品视角。

## 1. 客户端定位

建议客户端项目名：**PODI Studio Preview**。

客户端定位：

- 能力驱动的设计生产前台。
- 业务流程组装层。
- 中台业务能力的消费者。
- 业务方无自有前台时的托管生产工作台。
- 后续白标、私有化或 SaaS 前台的基线。

客户端负责：

- 行业业务动线。
- 工作单 / 素材 / 能力动作体验。
- 用户下一步推荐。
- 模板选择。
- 结果选择。
- 交付包体验。

客户端不负责：

- 能力管理。
- workflow 编辑。
- executor 选择。
- LoRA 底账。
- 密钥和路由配置。
- 原子能力测试。
- 中台监控。

## 2. 不能沿用的旧内容

仓库当前没有客户端代码目录。历史文档中的以下内容只作参考，不得直接复活：

- `podi-client-web/`
- `podi-client-v2/`
- `podi-design-web-dev/`
- 历史 `ready-for-test` 结论。
- 历史 Style3D 对标任务包。
- 历史本地素材沉淀方案。

客户端团队可以继承的产品原则：

- 客户端是能力使用工作台，不是能力市场，也不是项目管理系统。
- 用户进入后先做动作，不先理解中台。
- 结果进入资产，资产能继续创作。
- 任务中心解释状态，资产中心解释复用。
- 技术细节默认隐藏。

## 3. 接口边界

客户端只允许使用：

- `/api/business/*`
- 业务提交接口里的 `clientContextId/inputAssetIds/clientRequestId` 等调用上下文字段。
- 兼容调用上下文 API：当前后端路径仍是 `/api/business/projects/*`，只在需要登记资产、选择记录或交付证据时使用，不作为客户端产品主模型。
- `/api/media/*` 的上传凭证和受控媒资能力。

客户端禁止直接调用：

- `/api/admin/*`
- `/api/evals/*`
- `/api/abilities/*`
- `/api/ability-tasks/*`
- `/api/coze/podi/*`
- ComfyUI 节点地址。
- vendor-api-ops 地址。
- image-ops-service 内部地址。

如果客户端发现能力缺口，记录为中台能力 API 缺口，不允许绕过边界。

## 4. 业务流程由客户端定义，但以能力动作呈现

客户端可以定义如下样板动线：

```text
能力工作台
  -> 创建或打开工作单
  -> 选择生产动作
  -> 上传素材
  -> 花纹提取
  -> 裂变候选
  -> 选择候选
  -> 产品设计图
  -> 组图 / 多角度图
  -> 模特图
  -> 推广视频
  -> 导出交付包
```

但这条流程属于客户端模板，不属于中台固定流程。客户端 UI 可以使用“工作单”“任务”“素材夹”等业务语言；中台只接收调用上下文和证据字段，不应该让用户理解或感知后端兼容字段。

客户端每次调用中台业务能力时，应传入可选上下文：

- `clientContextId`
- `flowStepKey`
- `flowStepName`
- `flowTemplateId`
- `inputAssetIds`
- `clientRequestId`

兼容旧链路或需要使用 `/api/business/projects/*` 登记资产、选择和交付证据时，才传 `projectId`。中台只记录这些上下文和业务 run 证据，不决定下一步。

## 5. 首版页面结构

建议首版只做 6 个页面：

| 页面 | 作用 |
| --- | --- |
| `/workbench` | 能力动作入口、最近工作单、最近任务和素材。 |
| `/workbench/:workItemId` | 工作单总览、可用能力动作、最近资产和下一步建议。 |
| `/workbench/:workItemId/abilities/:abilityKey` | 单个能力动作工作台，提交、等待、看结果、选择。 |
| `/assets` | 我的素材和项目结果资产，支持继续创作。 |
| `/tasks` | 任务状态回看，按能力、工作单和客户端步骤聚合。 |
| `/exports/:packageId` | 交付包查看与下载。 |

首版不做复杂首页、营销页、钱包页和全量模板市场。先把“能力动作 -> 结果资产 -> 继续创作 -> 交付包”跑通。

## 6. 页面设计要求

客户端首屏必须遵守：

- 首屏只回答“现在可以用哪些能力动作、当前素材能做什么、下一步是什么”。
- 不展示 executor、workflow、LoRA 文件名、厂商原始错误。
- 高级参数默认折叠。
- 空态必须给动作，例如上传素材、选择候选、返回上一业务步骤。
- 异步任务必须显示等待状态和建议刷新/轮询节奏。
- 失败提示必须显示业务解释和 `runId`，不显示内部堆栈。

## 7. 需要中台提供的能力

客户端团队启动时可以先做 mock，但正式联调依赖：

- 工作单创建和查询。新客户端以自己的 `workItemId/clientContextId` 组织页面；如暂时复用后端兼容 API，其返回的 `projectId` 只作为技术映射。
- 工作单素材登记。
- 业务 run 支持写入 `clientContextId`、兼容 `projectId` 和 `flowStepKey`。
- 上下文 run 列表。
- 输出资产自动沉淀。
- 候选结果选择记录。
- 交付包生成。
- 交付包下载。

能力和调用上下文字段以 `docs/api/modules/business.md` 为准；`docs/strategy/end-to-end-business-object-api-v0.6.md` 只作为兼容实现背景。

## 8. 客户端 MVP 验收

客户端 Preview 具备验收条件时，必须通过：

1. 创建或打开一个工作单。
2. 上传至少一张素材。
3. 调用花纹提取业务 API，并传入 `clientContextId` 和 `flowStepKey`；如使用兼容资产 API，再带上 `projectId`。
4. 等待并展示业务结果。
5. 结果自动进入工作单资产。
6. 客户端调用裂变业务 API，并复用上一步资产。
7. 选择候选结果进入客户端下一步。
8. 至少跑到一个产品图或组图业务步骤。
9. 生成交付包草稿。
10. 任一失败业务 run 能看到 `runId` 和业务错误提示。

## 9. 新 agent 启动提示

给客户端 agent 的启动任务应明确：

```text
你只负责新客户端 PODI Studio Preview。
客户端负责业务流程组装，中台负责能力组装。
不要复活旧 podi-client-web 代码和旧测试结论。
不要重构 backend / podi-admin-web / podi-eval-web。
客户端只消费 /api/business/*、必要的兼容 /api/business/projects/* 和受控 media API。
如发现接口缺口，写入缺口清单，不自行调用 admin/evals/abilities/coze/comfyui。
先做能力工作台 MVP：工作单 -> 素材 -> 业务能力调用 -> 结果资产 -> 选择 -> 交付包。`clientContextId/workItemId` 是客户端主上下文；`projectId` 只在复用兼容 API 时作为技术映射。
```

## 10. 与中台团队协作方式

- 客户端每发现一个接口缺口，按“页面动作 -> 需要的数据 -> 当前不可满足原因 -> 建议 API”记录。
- 中台侧统一决定是否新增业务 API、复用已有业务 API 或调整能力包装。
- 客户端可以调整业务流程顺序，但不能把中台技术字段做进主界面。
- 客户端验收样例必须最终进入中台调用上下文证据、资产和业务 run 记录。
