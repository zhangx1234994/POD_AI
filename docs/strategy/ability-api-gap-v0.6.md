# v0.6 业务能力 API 缺口清单

最后更新：2026-06-03

本文从中台视角盘点客户端业务组装需要的能力包。它不是客户端流程方案，也不是项目方案。客户端决定业务步骤和页面动线；中台主语是业务能力，负责提供稳定的业务能力 API、版本治理、资产沉淀、质量证据、成本证据、错误契约和回滚口径。能力定义以 `docs/strategy/ability-definition-v0.6.md` 为准。

## 1. 盘点依据

代码真源：

- `backend/app/routers/business.py`
- `backend/app/services/business_seed.py`
- `backend/app/services/business_runs.py`
- `backend/app/constants/business_api_contract.py`
- `backend/app/constants/abilities.py`

当前业务 API 的 `businessKey` 真源为：

```text
pattern_extract
fission
text_fission
fission_evaluate
outpaint
image_edit
```

## 2. 已有业务能力

| 业务能力 | 对外入口 | 当前状态 | v0.6 判断 |
| --- | --- | --- | --- |
| 花纹提取 `pattern_extract` | `POST /api/business/pattern-extract/runs` | 已有默认版本和保底版本，底层为 ComfyUI 印花提取。 | 可作为客户端上游素材能力，需补可选调用上下文和输出资产证据。 |
| 图裂变 `fission` | `POST /api/business/fission/runs` | 已有 ComfyUI、GPT Image 2、颜色锁定、保底版本和 route-preview。 | 可作为候选裂变能力，需补输出资产沉淀和候选选择记录。 |
| 文字强化裂变 `text_fission` | `POST /api/business/text-fission/prompts` + `POST /api/business/text-fission/runs` | 已有两步式提示词确认链路。 | 适合文字要求强的素材，客户端可选择性使用。 |
| 裂变评分 `fission_evaluate` | `POST /api/business/fission-evaluate/runs` | 已有独立质量判断入口。 | 作为客户端可选质检能力，不自动决定下一步。 |
| 扩图 `outpaint` | `POST /api/business/outpaint/runs` | 已有默认版本和回滚版本。 | 可作为素材延展能力，需补调用上下文和输出资产类型。 |
| 图编辑 `image_edit` | `POST /api/business/image-edit/runs` + `GET /api/business/image-edit/component-config` | 已有 GPT Image 2 通用改图、托管组件配置、扩展画布等技能。 | 可作为产品图/局部修图的基础能力，但不能直接替代产品设计业务包装。 |
| 产品设计 `product_design` | `POST /api/business/product-design/runs` | 2026-06-03 已补首版业务包装，默认版本 `product-design-gpt-image2-v1`，底层复用 GPT Image 2 图片编辑能力。 | 进入 v0.6 实测和质量样例阶段；后续可按品类切路由。 |

结论：v0.6 不需要重做已有六类业务能力，优先补能力治理闭环、资产证据和缺失的下游业务包装。调用上下文只作为证据索引，不应取代能力治理主线。

## 3. v0.6 缺失能力包

### 3.1 产品设计图 `product_design`

目标：把花纹、裂变候选或参考图变成商品设计图。

建议优先级：P0。2026-06-03 首版已实现，剩余工作是上线验证、固定样例和效果治理。

中台职责：

- 已新增业务能力 `product_design`。
- 只暴露商品类型、使用场景、设计要求、输出比例、质量档位等业务参数。
- 底层可先复用 `image_edit` / GPT Image 2 / Seedream 等原子能力，但对客户端隐藏模型和路由。
- 输出资产类型建议为 `product_image`。

首版建议输入：

| 字段 | 说明 |
| --- | --- |
| `imageUrl` | 主参考图或花纹图。 |
| `clientContextId` | 可选客户端上下文 ID；兼容历史 `projectId`，但不作为中台产品概念。 |
| `inputAssetIds` | 可选输入资产。 |
| `productType` | 商品类型，例如服装、箱包、家纺。 |
| `designBrief` | 设计要求。 |
| `scene` | 白底、棚拍、生活方式、详情页等。 |
| `size` | 输出尺寸。 |
| `quality` | `preview` / `production` / `premium`。 |

首版非目标：

- 不承诺一次生成完整商品系列。
- 不让客户端选择底层模型、executor、workflow 或 LoRA。
- 不把客户端行业模板写入中台。

### 3.2 组图 / 多角度 `product_image_set`

目标：围绕一个商品方案生成一组可交付图片，例如主图、细节图、侧面图、背面图。

建议优先级：P1。

中台职责：

- 新增业务能力 `product_image_set`，或在产品设计稳定后再开独立包装。
- 对外返回多张能力输出资产，资产类型可细分为 `product_image` / `angle_image`。
- 记录每张图的 `sourceRunId/sourceOutputIndex/angleKey`。

首版建议：

- 不在 v0.6 P0 做复杂一致性承诺。
- 先支持客户端多次调用 `product_design` 并在输出资产里形成组图。
- 等稳定后再封装为单个 `product_image_set` 业务 API。

### 3.3 模特图 `model_shot`

目标：把商品图或花纹应用到模特展示图。

建议优先级：P1。

中台职责：

- 新增业务能力 `model_shot`。
- 封装模特描述、姿态、场景、商品类别、图像一致性和合规策略。
- 输出资产类型建议为 `model_image`。

关键风险：

- 商品结构一致性。
- 人像合规和版权边界。
- 模特身份一致性。
- 商品与人体遮挡、比例和材质可信度。

首版建议：

- 先选单一品类和单一构图验证，例如服装正面半身或家纺场景。
- 不开放自由模特生成参数，先使用有限枚举。

### 3.4 推广视频 `promo_video`

目标：把产品图、模特图或成套素材生成短视频。

建议优先级：P1/P2。

现有原子能力基础：

- 火山 Seedance 1.5 图生视频。
- KIE Sora2 Pro 文生视频。

缺口：目前没有业务包装入口，客户端不能直接调用原子能力。

中台职责：

- 新增业务能力 `promo_video`。
- 对外隐藏火山/KIE/OpenAI 等厂商差异。
- 统一视频时长、比例、镜头策略、质量档位、输出 URL 和错误码。
- 输出资产类型建议为 `video`。

首版建议：

- 优先做图生视频，输入一个已选产品图或模特图。
- 文生视频作为后续补充，不作为首版默认路线。

## 4. 横向缺口

| 缺口 | 影响 | v0.6 处理方式 |
| --- | --- | --- |
| 能力治理视图不足 | 管理端还不能一眼判断某个能力的版本、路由、质量、成本和回滚状态。 | v0.6 管理端优先做能力治理入口，调用上下文只作为下钻证据。 |
| 调用上下文证据不足 | 客户端串联多个 run 后需要聚合证据，但不应成为中台主视角。 | 支持 `clientContextId`/兼容 `projectId`、`flowStepKey`、`inputAssetIds`、`clientRequestId`。 |
| 输出资产缺少可复用证据 | 结果只能在 run 里看，不能作为下一步输入。 | 支持任务成功后自动沉淀能力输出资产。 |
| 候选选择没有结构化记录 | 无法知道哪张图进入下一步。 | 增加 ProjectSelection。 |
| 交付包缺失 | 不能把最终图、视频和证据打包交付。 | 先做 manifest JSON，再做 ZIP。 |
| 下游能力未业务化 | 客户端可能想绕过中台调用原子能力。 | 补 `product_design/model_shot/promo_video` 等业务包装。 |
| 质量证据缺少上下文 | 运营能看单 run 质量，但多次调用的上下文看不完整。 | 输出资产记录质量标签，管理端优先按能力聚合，再按上下文下钻。 |

## 5. 推荐实施顺序

### P0：让已有能力可被治理和串联

1. 能力详情能看到默认版本、候选版本、回滚版本、路由、质量、成本和错误。
2. 调用上下文和资产 API 作为证据容器使用。
3. 业务 run 支持 `clientContextId`/兼容 `projectId`、`flowStepKey`、`inputAssetIds`、`clientRequestId`。
4. 输出自动沉淀为能力输出资产。
5. 候选选择记录。
6. 管理端能先按能力查状态，再按 runId 或客户端上下文查资产、错误和质量。

### P0：补产品设计业务包装

1. `done` 新增 `product_design` 业务能力 seed。
2. `done` 首版底层优先复用已稳定的图编辑 / GPT Image 2 商业模型路线。
3. `done` 补 API 文档、错误码和样例。
4. `doing` 补线上实测、固定质量样本和效果治理记录。
5. `done` 客户端只看到商品类型、设计要求、场景、尺寸和质量档位。

### P1：补组图和模特图

1. 先让客户端用多次 `product_design` 形成组图。
2. 再决定是否封装 `product_image_set`。
3. `model_shot` 先选一个品类和有限参数集验证。

### P2：补推广视频

1. 先包装图生视频 `promo_video`。
2. 再根据成本、耗时和稳定性决定文生视频路线。

## 6. 每个新能力的门禁

新增业务能力必须同时完成：

- `BusinessCapability` seed。
- 请求 schema。
- 响应 schema。
- 错误码总表。
- 业务 API 文档。
- route-preview 或管理端路由可视化。
- OSS 结果沉淀。
- 输出资产沉淀。
- 质量样例。
- 成本和调用记录。
- 后端测试覆盖缺参、依赖失败、超时、并发或队列限制。

## 7. 待决策

1. v0.6 首个客户端样板行业：服装、箱包、家纺三选一。
2. `product_design` 首版底层路线：GPT Image 2 图编辑优先，还是 Seedream 参考图生成优先。
3. `product_image_set` 是 v0.6 P1 独立业务 API，还是客户端多次调用 `product_design` 后再沉淀。
4. `promo_video` 首版只做图生视频，还是同时保留文生视频入口。
