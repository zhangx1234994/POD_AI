# 核心业务链路体检（2026-05-03）

## 范围

本次只看当前真正的主业务：

- 花纹提取
- 图裂变
- 扩图

目标不是继续堆功能，而是按真实业务链路检查：入口是否清楚、版本是否可控、路由是否合理、执行是否可观测、失败是否能被发现、后续框架是否还成立。

## 标准业务流程

```mermaid
flowchart LR
  A["业务方 / Coze / 客户端"] --> B["业务 API"]
  B --> C["选择业务版本"]
  C --> D["创建 BusinessRun 与步骤"]
  D --> E["提交原子能力任务"]
  E --> F["选择 ComfyUI 执行节点"]
  F --> G["ComfyUI 执行"]
  G --> H["结果下载并回填 OSS"]
  H --> I["业务任务终态"]
  I --> J["回调 / 轮询 / 管理端日志"]
```

关键口径：

- 业务方只应该理解业务 API，不应该理解 ComfyUI 节点、workflow、executor。
- Coze 可以继续作为接入层和实验层，但不应该承载核心业务编排。
- 中台负责版本、灰度、回滚、路由、任务、回填、统计和错误语义。
- ComfyUI 只负责执行，不能承担平台逻辑。

## 当前结论

整体框架方向是成立的：中台业务层已经具备版本、默认版本、保底版本、灰度预览、业务运行记录、步骤记录和接入方策略。

但这次体检发现一个明确缺口：业务版本库已经把花纹提取列为核心业务，管理端也按“花纹提取 / 图裂变 / 扩图”展示，但公开业务 API 之前只暴露图裂变和扩图。也就是说，口径上花纹提取是主业务，接口上还没有完整闭环。

本次已补齐：

- `POST /api/business/pattern-extract/runs`
- `POST /api/business/pattern-extract/route-preview`
- 业务 OpenAPI 中的花纹提取工具定义
- 花纹提取顶层参数透传：`prompt`、`negative_prompt`、`width`、`height`、`batch`、`lora`、`timeout`
- 业务接口文档与错误码总表
- 契约测试与参数透传单测

## 三条主链路现状

### 花纹提取

当前版本：

- 默认版：`biz_pattern_extract_v1_yinhua_tiqu`
- 主能力：`comfyui_yinhua_tiqu`
- 保底版：`biz_pattern_extract_rollback_lora_8step`
- 保底能力：`comfyui_yinhua_tiqu_lora_8step`

已确认：

- 数据库中默认版和保底版都存在且为 active。
- 底层能力都已配置两台 ComfyUI：`117.50.216.233` 和 `117.50.80.158`。
- 本次已补齐公开业务入口和 OpenAPI。

仍需继续：

- 把 Coze 中相关花纹提取工作流逐步切到业务 API。
- 管理端运行详情需要展示“本次实际打到哪台 ComfyUI、当时队列情况、回填了哪些 OSS 链接”。

### 图裂变

当前版本：

- 默认版：`biz_fission_v1_flux_strong_hq_softstyle`
- 主能力：`comfyui_flux_strong_hq_softstyle_fission`
- 保底版：`biz_fission_rollback_e7_flux2_liebian`
- 保底能力：`comfyui_e7_flux2_liebian`

已确认：

- 公开业务入口已存在：`POST /api/business/fission/runs`。
- 路由元数据已修复为两台 ComfyUI 都可参与，不再只打到 158。
- 图裂变支持 `bili`、`width`、`height`、`image_desc`、`batch_size` 等顶层参数。

仍需继续：

- Coze 里仍有一批历史工作流直接走旧工具箱或底层 workflow，后续应逐步用业务 API 替换。
- 需要把“业务 API 图裂变真实出图”纳入定期自检，而不是只巡检 Coze 工作流。

### 扩图

当前版本：

- 默认版：`biz_outpaint_v1_flux2_klein_9b`
- 主能力：`comfyui_flux2_klein_9b_outpaint`
- 保底版：`biz_outpaint_rollback_huawen_kuotu`
- 保底能力：`comfyui_huawen_kuotu`

已确认：

- 公开业务入口已存在：`POST /api/business/outpaint/runs`。
- 路由元数据已修复为两台 ComfyUI 都可参与。
- 扩图支持上下左右扩展量、宽高和超时时间顶层传参。

仍需继续：

- 需要一条稳定的业务 API 出图自检样例，验证图像尺寸变化、OSS 回填和业务终态。
- 扩图结果质量属于工作流问题，但“尺寸是否改变、是否回填、是否能轮询到终态”属于中台必须覆盖的问题。

## 框架判断

当前分层合理，但必须坚持一个原则：业务 API 是产品入口，底层能力只是弹药库。

如果继续让 Coze 工作流、评测工作流、管理端测试、业务 API 各自表达一套业务概念，后续一定会反复出现“页面看着有、接口没有”“工具能跑、工作流不生效”“业务成功但中台没记录”的问题。

后续应固定为：

- 业务入口：`/api/business/*`
- 能力执行：`/api/abilities/*`
- Coze 工具箱：优先导入业务 API，只有实验和过渡期才使用底层能力工具箱
- 评测端：既要评测 Coze 工作流，也要评测业务 API 主链路
- 管理端：先按业务展示，再下钻到底层能力和执行节点

## 近期优先级

1. 补业务 API 定期自检脚本
- 覆盖花纹提取、图裂变、扩图。
- 每条都检查提交成功、轮询终态、OSS 链接、底层任务 ID、实际执行节点。
- 已落地 `backend/scripts/patrol_business_api.py`。默认 `--mode route` 只做路由预览，不消耗出图；需要真实出图时显式执行 `--mode live --image-url <url>`。

2. 管理端运行详情补链路证据
- 每次业务运行必须能看到业务版本、主能力、执行节点、队列状态、能力任务、OSS 回填、失败原因。
- 这比继续扩页面功能更重要。
- 已补充：`BusinessRun.flowSummary` 汇总业务版本、原子能力、执行节点、输出回填和回调状态；`steps[].executionEvidence` 透出步骤级能力日志、执行节点和 OSS 证据。
- 已修复：业务层结果 URL 提取兼容 `storedUrl/stored_url/ossUrl/url/sourceUrl`，避免“底层完成但业务运行无回填”的假阴性。

3. Coze 工具箱逐步切到业务 API
- 新业务工作流默认只调用业务 API。
- 老工作流先保留，但必须标记为历史或过渡，不再作为主入口扩展。

4. 测评端分层
- 公开测评端按业务能力分组。
- 内部测评端保留底层 workflow 维度。
- 卡片上明确“业务主入口 / Coze 工作流 / 底层能力 / 历史保留”。

5. 前端整体整改
- 等上述链路证据稳定后，再做管理端整体交互重构。
- 重构方向应是“先总后分”：先看业务是否健康，再看版本，再看执行节点和底层日志。

## 本次验证

已执行：

```bash
cd backend
python3 -m py_compile app/routers/business.py app/schemas/business.py app/services/business_runs.py
python3 -m pytest tests/test_business_api_contract.py tests/test_business_capability_admin.py::test_business_run_accepts_flat_fission_params tests/test_business_capability_admin.py::test_business_run_accepts_flat_pattern_extract_params tests/test_business_seed_rollback_safety.py -q
python3 scripts/business_version_safety_audit.py --json
python3 -m pytest tests/test_business_capability_admin.py tests/test_business_api_contract.py tests/test_business_seed_rollback_safety.py tests/test_business_version_safety_audit.py tests/test_patrol_business_api.py -q
cd ../podi-admin-web && npm run lint
```

结果：

- 编译通过。
- 业务 API 契约、图裂变顶层参数、花纹提取顶层参数、业务保底版本测试通过。
- 业务版本安全垫检查已覆盖花纹提取、图裂变、扩图，三项均有默认版本和保底版本。
- 业务运行详情链路证据、`storedUrl` 回填兼容、管理端类型检查均通过。

## 线上自检记录

2026-05-02 23:05-23:10 对 114 后端执行核心业务 API 自检：

- `GET /health` 正常。
- 路由预览：
  - `fission` 通过，默认版本为 `biz_fission_v1_flux_strong_hq_softstyle`。
  - `outpaint` 通过，默认版本为 `biz_outpaint_v1_flux2_klein_9b`。
  - `pattern_extract` 返回 404，说明 114 当前运行版本还没有花纹提取业务入口；更新 114 后必须补测。
- 第一次真实闭环使用旧 bucket 样例图，OSS 返回 `NoSuchBucket`，导致图裂变/扩图均失败为 `COMFYUI_IMAGE_UPLOAD_FAILED`。该问题不是 ComfyUI 能力故障，而是巡检样例图失效。
- 已将巡检相关脚本和文档样例图切到当前可访问地址：`https://podiaidesign.oss-cn-hangzhou.aliyuncs.com/test/abilities/98904c502d9d4dd78432ec2bd1f79def/20260424/228be55f-1777009905.jpg`。真实出图巡检前必须先 `curl -I` 确认样例图可访问。
- 第二次真实闭环通过：
  - 图裂变 runId=`e31b70555c6245288678bd075fadf5dc`，abilityLogId=`36927`，输出 1 张图，命中 `ComfyUI 5090 · 158 · 117.50.80.158`。
  - 扩图 runId=`6c6b07af3d7440b3bccd2a0f062f4669`，abilityLogId=`36928`，输出 1 张图，命中 `ComfyUI 4090 · 233 · 117.50.216.233`。
- 114 当前业务详情接口尚未返回 `flowSummary`，但能力日志原始字段已有 `executor_id/executor_name/stored_url`。本地代码已补 `flowSummary` 和步骤级 `executionEvidence`，更新 114 后应使用 `patrol_business_api.py --require-executor-evidence` 再跑一次。巡检脚本已补强制执行节点证据检查，缺失时不算通过。

## 后续检查口径

每次再看这三条主业务时，必须沿同一条链路检查：

1. 业务 API 是否有入口。
2. 默认版本和保底版本是否存在。
3. 底层能力是否 active。
4. 路由是否包含 158 和 233 两台 ComfyUI。
5. 队列满时是否返回明确错误，而不是挂起。
6. ComfyUI 成功但无图时是否失败并给出原因。
7. OSS 链接是否回填到业务任务。
8. Coze 和测评端是否能查到同一个任务链路。
