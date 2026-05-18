# 业务控制点盘点矩阵（2026-05-19）

目的：找清楚“一个业务参数或规则到底应该在哪里改”，避免业务链条继续出现多处控制点。

适用业务：花纹提取、图裂变、扩图、裂变评分。

## 1. 结论

当前已经比 v0.1 收敛很多，但仍存在 4 类重复控制点：

1. **业务版本真源已经基本在 `BusinessCapability`，但前端仍有不少兜底映射。**
   - 典型位置：`podi-eval-web/src/App.tsx` 的版本名、角标、分类、参数文案兜底。
   - 处理原则：保留兜底，但新增或修改业务时必须先改业务版本 schema / metadata，再让前端读取派生结果。

2. **OpenAPI 已经能合并业务 schema，但还有手写兼容 schema。**
   - 典型位置：`backend/app/routers/business.py`。
   - 处理原则：对外兼容字段继续保留，新增字段必须从 `BusinessCapability.input_schema` 派生。

3. **交付文档和样例仍是静态文件。**
   - 典型位置：`docs/api/examples/fission-business-delivery/`、`docs/api/modules/business.md`。
   - 处理原则：短期继续静态维护，但发布 smoke 必须校验；v0.3 后续应增加按业务版本导出交付材料。

4. **逐功能上线门禁目前有一份后端静态规格。**
   - 典型位置：`backend/app/routers/business.py` 的 `FEATURE_RELEASE_AUDIT_SPECS`。
   - 处理原则：短期可接受，后续应下沉到业务版本 metadata 或组件目录，避免每加功能都改代码。

## 2. 当前真源优先级

| 优先级 | 真源 | 负责内容 | 说明 |
| --- | --- | --- | --- |
| 1 | `BusinessCapability` 数据库记录 | 业务版本、输入 schema、输出 schema、recipe、metadata、默认版本 | 运行时真源 |
| 2 | `backend/app/services/business_seed.py` | 默认业务版本和初始配方 | 初始化真源，不应成为长期唯一配置入口 |
| 3 | `backend/app/routers/business.py` | 对外业务 API、OpenAPI 兼容层、发布审计接口 | 应读取业务版本，少写业务规则 |
| 4 | `backend/app/routers/evals_public.py` | 测评端业务条目派生 | 应读取业务版本，不重复维护参数 |
| 5 | 管理端 / 测评端前端 | 展示和交互兜底 | 只做展示，不做业务规则真源 |
| 6 | `docs/api/examples/*` | 对外交付样例 | 必须被 smoke 校验，未来应可自动导出 |

## 3. 核心业务控制点矩阵

### 3.1 花纹提取

| 控制项 | 当前位置 | 当前问题 | v0.3 处理 |
| --- | --- | --- | --- |
| 业务入口 | `/api/business/pattern-extract/runs` | 入口稳定 | 保留 |
| 默认版本 | `BusinessCapability` / `business_seed.py` | seed 仍是主要编辑入口 | 后续从管理端复制草稿编辑 |
| 输入字段 | `BusinessCapability.input_schema`，OpenAPI 合并 | 基本已派生 | 保留为真源 |
| 输出字段 | `_image_generation_output_schema()` | 与图裂变/扩图共用 | 后续抽成图片输出组件 |
| 测评入口 | `evals_public.py` 从业务版本派生 | 已收敛 | 保留 |
| 管理端入口描述 | `podi-admin-web/src/features/admin/integration/business.tsx` | 仍有业务文案兜底 | 降为兜底，优先读 metadata |
| 交付文档 | `docs/api/modules/business.md` | 静态文档 | 后续由业务版本导出样例 |

### 3.2 图裂变

| 控制项 | 当前位置 | 当前问题 | v0.3 处理 |
| --- | --- | --- | --- |
| 业务入口 | `/api/business/fission/runs` | 入口稳定，但内部版本线多 | 保留一个入口，版本族在业务版本内管理 |
| GPT Image 2 版本 | `BusinessCapability` / `business_seed.py` / 交付目录 01 | 前端和文档仍有少量版本名兜底 | 版本名只从业务 metadata 派生，前端兜底保留但不作为真源 |
| ComfyUI 颜色锁定版本 | `BusinessCapability` / `business_seed.py` / 交付目录 02 | `bili/profile/reference_lock/color_lock` 在多处出现 | 字段真源固定在业务 schema，交付文档和门禁只校验 |
| 旧 Coze 裂变 | Coze 工具箱 / 旧工作流 / 门禁审计 | 不属于自有业务版本，证据链独立 | 作为 legacy 版本族展示，不再混入新业务版本 |
| `bili` 语义 | schema、测评端兜底、文档、发布 SOP | 已统一为重绘幅度，但历史字段仍会出现 | 保留兼容识别；新增页面禁止写“相似度” |
| 结果展示 | 测评端沉浸式工作台 | 已按结果组/本图参数收敛 | 保留，后续从业务组件输出类型派生 |
| 逐功能门禁 | `FEATURE_RELEASE_AUDIT_SPECS` | 静态规格 | 后续迁入业务版本 metadata 或组件目录 |

### 3.3 扩图

| 控制项 | 当前位置 | 当前问题 | v0.3 处理 |
| --- | --- | --- | --- |
| 业务入口 | `/api/business/outpaint/runs` | 入口稳定 | 保留 |
| 默认版本 | `BusinessCapability` / `business_seed.py` | 仍以 seed 管理 | 后续复制草稿编辑 |
| 路由预览 | `/api/business/outpaint/route-preview` | 有独立兼容 schema | 继续保留，但字段从业务 schema 派生 |
| 输入字段 | `imageUrl`、扩边方向、宽高、提示词 | OpenAPI 有手写兼容层 | 新字段必须先进入业务 schema |
| 测评入口 | `evals_public.py` 派生 | 已收敛 | 保留 |
| Coze 工具箱 | `docs/coze/toolbox-inventory.md` / Coze 模块文档 | 与原生 API 并存 | 作为接入方式，不作为业务主线真源 |

### 3.4 裂变评分

| 控制项 | 当前位置 | 当前问题 | v0.3 处理 |
| --- | --- | --- | --- |
| 业务入口 | `/api/business/fission-evaluate/runs` | 入口稳定 | 保留 |
| 兼容入口 | `/api/business/fission/evaluate/runs` | 历史兼容入口 | 保留兼容，但文档主推正式入口 |
| 输入字段 | `originalImageUrl`、`generatedImageUrl`、`context` | 基本清晰 | 保留为业务 schema 真源 |
| 输出字段 | `_fission_evaluate_output_schema()` | 文字/结构化结果容易被图片链路误判 | 已修正最近运行摘要；后续抽成评分组件输出 |
| 决策枚举 | `business-api-enums.md`、交付目录 03 | 静态文档 | 后续从评分组件 metadata 导出 |
| 业务关系 | 图裂变后的质检接口 | 不是自动二次裂变 | 保持独立业务入口，组合逻辑交给业务方或后续业务编排 |

## 4. 需要去重的文件级控制点

| 位置 | 当前承担内容 | 判断 | v0.3 动作 |
| --- | --- | --- | --- |
| `backend/app/services/business_seed.py` | 默认业务版本、schema、recipe、metadata | 保留初始化职责 | 后续增加组件化字段，减少手写重复 |
| `backend/app/routers/business.py` | 业务 API、OpenAPI、门禁审计 | 保留路由和兼容层 | 门禁规格逐步从业务版本/组件目录读取 |
| `backend/app/services/eval_seed.py` | 历史和原子工作流 seed | 保留历史工作流职责 | 新业务测评入口优先由 `evals_public.py` 派生 |
| `backend/app/routers/evals_public.py` | 测评目录派生 | 正确方向 | 继续加强派生，减少前端兜底 |
| `podi-eval-web/src/App.tsx` | 分类、名称、角标、参数展示兜底 | 必要但偏重 | 保留兼容兜底；新增业务必须优先读后端 presentation |
| `podi-admin-web/src/features/admin/integration/business.tsx` | 业务页面展示和编排图 | 正确方向 | 加入组件目录和草稿编辑 |
| `podi-admin-web/src/features/admin/integration/apiExposure.tsx` | 接口说明、API Key、调用中心、门禁展示 | 偏重但可接受 | 能派生的接口说明继续后端化 |
| `docs/api/examples/*` | 交付样例 | 短期保留 | 后续增加业务版本样例导出 |
| `docs/standards/per-feature-release-checklist.md` | 上线检查标准 | 保留标准 | 具体功能项后续从动态审计生成 |

## 5. 立即执行顺序

1. 先建“业务组件目录”接口和静态组件定义，覆盖当前四个核心业务。
2. 让业务链路图节点读取组件类型，右侧详情显示组件输入、输出、错误和可编辑字段。
3. 增加“复制为草稿 -> 编辑已有步骤字段 -> 保存草稿”的最小闭环。
4. 给草稿增加 validate，校验必需组件、字段、路由和输出。
5. 再把逐功能门禁从静态规格逐步迁到组件/业务版本 metadata。

## 6. 暂不处理

1. 不物理删除历史 Coze 文档。
2. 不重写所有交付文档。
3. 不取消前端兜底映射，避免历史数据展示出问题。
4. 不引入新的编排引擎，先复用现有 `@xyflow/react`。

