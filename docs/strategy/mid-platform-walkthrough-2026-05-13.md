# 中台走查与当前待办合并（2026-05-13）

本轮不新增功能，目标是把 2026-05-12 至 2026-05-13 图裂变、评测端、发布和线上监控中暴露的问题沉淀成可执行清单。

## 1. 当前项目进度判断

已完成并可保留为基线：

- 114 控制面发布 SOP 已固化，发布脚本能完成源检查、测试、构建、打包、部署和 smoke。
- 三个新交付接口已接入测评端：GPT Image 2 + VL 控制版、ComfyUI VL 控制卡版、裂变质量评估。
- ComfyUI 颜色锁定裂变 v2 已替换原测评入口，不再作为新增功能卡片展示；角标口径为“已优化”。
- 测评端 `bili` 已恢复为“重绘幅度”口径，不再描述为“相似度”。
- ComfyUI 最近一批 30 个测试样本均成功回填，且实际分布到两台节点：`executor_comfyui_seamless_117` 14 条、`executor_comfyui_pattern_extract_158` 16 条。
- ComfyUI 优化样本包已生成：`deliverables/comfyui_fission_quality_pack_20260513.zip`。

本轮已经收口的部分：

- 数据库查询结构性问题已修：增加业务运行和步骤索引，查询改为先轻字段后详情。
- 火山 VL 请求突增保护已补 backend 侧退避重试；更细的全局限速后续在 vendor-api-ops 调度层增强。
- 能力调用日志 pending 残留已补 reconciliation，读取列表前自动按任务终态收口。
- 评测端和管理端对“文字/VL/结构化输出”的“回填”文案已改为更中性的结果语义。

仍不能视为“完成”的部分：

- 对外接口交付材料虽然已有雏形，但还需要按“每个接口独立包”继续标准化。
- 当前唯一 TODO 文档历史内容仍很多，但最新真实问题已提升为当前执行单。
- 管理端整体信息架构和视觉表达仍需继续重构，本轮只先修正最误导的错误提示。

## 2. 已确认问题清单

### P0-1 数据库查询触发 `Out of sort memory`

现象：

- 测评端打开 GPT Image 2 + VL 控制版时曾报 `BUSINESS_RUN_GET_FAILED`。
- 线上直接查询最近图裂变业务记录也能复现：
  - `business_runs WHERE business_key='fission' ORDER BY created_at DESC LIMIT 20`
  - 查询返回大 JSON 字段时触发 `pymysql.err.OperationalError: (1038, 'Out of sort memory')`。

初步判断：

- 数据量并不大，根因更像索引与查询形态不合理。
- `business_runs` 目前没有覆盖 `(business_key, created_at)` 的索引，查询需要排序；同时一次性选择 `request_payload/result_payload` 等大 JSON 字段会放大排序内存。
- `business_run_steps` 查询也有 `ORDER BY step_order, created_at`，应确认是否有 `(run_id, step_order, id/created_at)` 覆盖索引。

整改结果：

- 已补数据库迁移：`business_runs(business_key, created_at)`、`business_runs(business_key, status, created_at)`、`business_run_steps(run_id, step_order, id)`。
- 列表、分类和用量汇总已改为先查轻字段 ID，再按需加载大 JSON。
- 步骤排序已改为窄字段排序，避免排序阶段拖入 JSON 过程信息。

### P0-2 火山 VL 触发请求突增保护

现象：

- 能力日志 `40146`，时间 `2026-05-13 16:28:48`，能力 `火山 · Doubao-Seed-2.0-lite VL`。
- 上游错误：`RequestBurstTooFast / TooManyRequests`。
- 完整错误：`System protection triggered by request burst. Please slow down traffic growth and increase requests gradually before retrying`。

初步判断：

- 不是图片参数错误，也不是 Key 缺失。
- 最近 6 小时火山 VL 成功 91 次，失败 1 次；同一分钟附近仍有成功样本，属于上游限速/保护类瞬时失败。
- 当前平台已经能把错误标成失败，但还缺少模型级平滑限速和重试策略。

整改结果：

- backend executor 已识别 `RequestBurstTooFast/TooManyRequests/429/5xx` 等可重试结果。
- Doubao VL 默认最多 3 次退避重试，OpenAI/KIE 默认最多 2 次，退避间隔带随机抖动。
- 更细的 provider/model 全局限速和 `rate_limited` 统计继续保留为 vendor-api-ops 后续增强项。

### P0-3 火山 VL 存在 `pending` 日志残留

现象：

- 线上发现 `volcengine_doubao_seed_2_0_lite` 仍有 `pending` 日志残留。
- 样本：`40159`、`40036`、`40034`，均为 `source=ability-task:vl`，无耗时、无错误、无结果。

影响：

- 管理端能力调用列表会让用户误以为仍在“输出填写中”或任务未结束。
- 后续统计成功率和失败率时可能被污染。

整改结果：

- 增加能力日志 reconciliation：超过阈值仍 pending 且有对应 ability_task 终态时，按任务终态回填；无对应任务时标为 `ABILITY_LOG_STALE_PENDING` 失败。
- 管理端列表读取会触发收口，减少历史 pending 残留对用户判断的干扰。

### P0-4 文字/VL/结构化输出的“回填”文案不准确

现象：

- 文字类、VL 类能力在回调阶段显示“输出填写中”或类似文案，容易被误解成异常。

整改结果：

- 管理端能力调用、能力测试、业务运行详情统一改成“结果入库/成功无结果”等通用结果语义。
- 测评端运行阶段改成“等待结果/结果处理中/结果已完成/结果失败”。
- 更细的图片、视频、文本、结构化结果分型继续放到前端整体整改阶段做。

### P0-5 管理端错误提示过度技术化

现象：

- 本地走查时，总览页把非 systemd 环境不可读显示成巡检异常。
- 页面顶部直接展示“部分接口超时”等技术错误，非技术用户不知道下一步。
- 模型弹药库只看环境变量时容易误提示 Key 缺失，但实际中台 Key 池已有可用 Key。
- 能力调用列表的结果状态和错误详情占用认知空间。

整改结果：

- 总览页把非 systemd 本地环境标为“本地不可读”，不再计入线上阻塞。
- 全局加载错误改成“部分模块暂时没加载完整”，详情折叠，主提示给出重试和排查路径。
- 模型弹药库明确显示 Key 来源：中台密钥池、环境变量兜底或未配置。
- 能力调用列表避免继续使用“回填”作为通用结果状态。

### P0-5 测试样本包需要形成固定动作

现象：

- 本次 ComfyUI 团队需要原图、结果图、VL 内容、ComfyUI 参数和过程信息，之前没有固定导出入口。

已完成：

- 生成样本包：`deliverables/comfyui_fission_quality_pack_20260513.zip`。
- 包含 30 条成功样本、60 张原图/结果图、`summary.csv`、每条样本的 `process.json`、`vl_control_card.json`、`comfyui_params.json`。

整改方向：

- 后续把样本包导出脚本化：按业务版本、时间范围、状态、执行节点导出。
- 管理端或运维脚本里提供“导出给 AI/ComfyUI 团队”的固定流程。

### P1-1 对外接口交付材料仍需拆分

现象：

- 三个接口材料曾放在一起，业务开发可能看不清哪个接口该怎么接。

整改方向：

- 每个接口独立目录：
  - `README.md`：用途、参数、返回、错误码。
  - `demo.sh`：可直接运行。
  - `demo.py`：可直接运行。
  - `example_request.json` / `example_response.json`。
  - `poll_result_demo.*`：轮询结果示例。
- Key 不进仓库，只进入临时交付压缩包或单独安全通道。

### P1-2 测评端仍需围绕“测试效率”继续整理

问题点：

- 结果区空间利用率不高，原图/结果图对比组件太小。
- 批量上传适合放在单功能测试内，批量回归侧重批量任务与统计，但需要复用对比组件。
- 新版本、已优化、候选版本等角标必须来自数据，不允许靠名称硬编码。

整改方向：

- 单功能页：支持多图上传、逐任务对比、快速切换结果。
- 批量回归页：复用对比组件，但默认以列表和统计为主。
- 角标展示以 `metadata.badge/presentation.badges` 为准。

### P1-3 中台总览仍需从“技术视图”转成“业务验收视图”

问题点：

- 当前很多数据能查到，但不够像“验收面板”。
- 用户更关心“这个业务能不能交给业务方测试”“失败在哪里”“下一步谁处理”，而不是先看执行器、workflow、log id。

整改方向：

- 总览固定显示三条主链路：花纹提取、图裂变、扩图。
- 每条链路展示：最近成功、最近失败、执行节点分布、回填状态、模型限流、可交付结论。
- 进入详情再看底层能力、执行节点、日志。

## 3. 下一轮合并后的执行顺序

1. 先修数据库查询和索引问题，避免功能页继续因 `Out of sort memory` 挂掉。
2. 再修 VL 限流、退避重试和 pending 日志收口，减少偶发上游保护导致的失败。
3. 统一文字/VL/结构化结果的展示口径。
4. 把样本包导出固化成脚本或管理动作。
5. 拆分三个业务接口交付材料，给业务方可直接运行的独立 demo。
6. 再进入测评端和管理端的交互整理。

## 4. 本次样本包

本次交给 ComfyUI 团队的包：

```text
deliverables/comfyui_fission_quality_pack_20260513.zip
```

包内关键文件：

- `summary.csv`
- `raw/records.json`
- `case_xx_*/input_original.png`
- `case_xx_*/output_result.png`
- `case_xx_*/vl_control_card.json`
- `case_xx_*/comfyui_params.json`
- `case_xx_*/process.json`
