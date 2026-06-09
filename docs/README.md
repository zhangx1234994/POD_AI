# POD AI Studio 文档入口

本文只解决一个问题：现在该看哪些文档。历史资料可以追溯，但不能直接当作当前执行依据。

## 5 分钟阅读顺序

1. `docs/strategy/todo-master-2026q2.md`
2. `docs/strategy/v0.7-ability-productization-agent-orchestration-plan.md`
3. `docs/strategy/v0.7-kickoff-meeting-2026-06-09.md`
4. `docs/standards/version-acceptance-template.md`
5. `docs/standards/agent-runtime-regression-matrix.md`
6. `docs/standards/eval-ability-interaction-state-model.md`
7. `docs/strategy/ability-definition-v0.6.md`
8. `docs/strategy/business-agent-runtime-v0.6.md`
9. `docs/strategy/ability-governance-operating-model-v0.6.md`
10. `docs/strategy/ability-api-gap-v0.6.md`
11. `docs/strategy/client-parallel-preview-v0.6-handoff.md`
12. `docs/strategy/v0.6-closure-inventory-2026-06-07.md`
13. `docs/strategy/v0.6-closure-standardization-plan.md`
14. `docs/strategy/v0.6.3-control-plane-hardening-plan.md`
15. `docs/standards/release-sop.md`
16. `docs/api/INDEX.md`

## 当前真源

| 类型 | 文档 | 用途 |
| --- | --- | --- |
| 唯一 TODO | `docs/strategy/todo-master-2026q2.md` | 当前任务池 |
| 当前方案 | `docs/strategy/v0.7-ability-productization-agent-orchestration-plan.md` | v0.7 能力产品化、Agent 编排、交互治理和质量迭代规划 |
| 会议决策包 | `docs/strategy/v0.7-kickoff-meeting-2026-06-09.md` | 2026-06-09 v0.7 kickoff 的目标选择、P0 范围、非目标、角色视角和拍板事项 |
| 上阶段封版方案 | `docs/strategy/v0.6-closure-standardization-plan.md` | v0.6 收口、缺失补齐、交互纠偏、接口文档和机制标准化 |
| 上阶段盘点 | `docs/strategy/v0.6-closure-inventory-2026-06-07.md` | v0.6 收口 P0/P1/P2 缺口、证据和整改批次 |
| v0.6.3 封版方案 | `docs/strategy/v0.6.3-control-plane-hardening-plan.md` | v0.6.3 控制面承压、Agent 样板整改、能力治理降噪和封版门禁 |
| 阶段基准 | `docs/strategy/mid-platform-completeness-v0.6-plan.md` | v0.6 中台能力治理、客户端支撑底座和各端边界；当前作为 v0.7 基线 |
| 能力治理模型 | `docs/strategy/ability-governance-operating-model-v0.6.md` | 能力优先、调用上下文只作为证据索引的统一评审口径 |
| 能力定义 | `docs/strategy/ability-definition-v0.6.md` | 中台业务能力、原子能力、输入输出、质量和错误边界 |
| 能力缺口 | `docs/strategy/ability-api-gap-v0.6.md` | 现有业务 API 盘点、产品图/组图/模特图/视频缺口和实施顺序 |
| 业务 Agent | `docs/strategy/business-agent-runtime-v0.6.md` | 对话式图编辑 Agent 的边界、Runtime、API 和升级门槛 |
| 客户端交接 | `docs/strategy/client-parallel-preview-v0.6-handoff.md` | 给客户端团队或新 agent 的业务组装边界、页面和验收说明 |
| 兼容调用上下文 | `docs/strategy/project-context-backend-design-v0.6.md` | 历史命名的兼容实现记录；不作为中台主概念继续扩展 |
| 当前回顾 | `docs/strategy/project-half-year-review-2026-05-26.md` | 半年度复盘、数据证据、阶段结论和下一阶段方向 |
| 交付方法论 | `docs/standards/delivery-methodology.md` | 交付顺序、多视角批判、自我批判和六顶思考帽评审准则 |
| 版本验收模板 | `docs/standards/version-acceptance-template.md` | 每个新版本开工前的验收标准和封版记录模板 |
| Agent 回归矩阵 | `docs/standards/agent-runtime-regression-matrix.md` | Agent Runtime 的多轮、路由、幂等、错误和交互回归标准 |
| 测评端状态模型 | `docs/standards/eval-ability-interaction-state-model.md` | 能力分类页、工作台、Agent、结果、历史和排障的交互状态标准 |
| 业务线上状态 | `docs/standards/business-lifecycle-status.md` | 区分线上可用、受限可用、生产推荐、待补验收和历史版本 |
| 上阶段方案 | `docs/strategy/platform-polish-v0.5-decision-plan.md` | v0.5 平台打磨、业务流可视化、流程监控和效果复盘方案 |
| 质量复盘 | `docs/strategy/output-quality-review-v0.5.md` | 固定样例池、质量档位、输入标签、问题标签和复盘节奏 |
| 上轮回顾 | `docs/strategy/project-current-review-2026-05-22.md` | v0.4/v0.4.1 阶段背景和问题复盘 |
| 业务主线 | `docs/standards/business-mainline-contract.md` | `runId`、业务版本、步骤、回填、回调、计费口径 |
| 控制点索引 | `docs/strategy/control-point-and-file-index-2026-05-19.md` | 参数、字段、默认值该从哪里改 |
| API 索引 | `docs/api/INDEX.md` | 对外接口和后台接口入口 |
| 错误规范 | `docs/standards/error-catalog.md` / `docs/standards/error-contract.md` | 错误码和错误返回 |
| 发布 SOP | `docs/standards/release-sop.md` | 114 控制面更新、验证、回滚 |
| 上线检查 | `docs/standards/per-feature-release-checklist.md` | 每个功能上线前逐项检查 |

## 模块入口

| 模块 | 入口 |
| --- | --- |
| 管理端 | `docs/admin/integration-dashboard.md` |
| 测评端 | `docs/eval/eval-platform.md` |
| Coze 工具箱 | `docs/coze/toolbox-inventory.md` |
| ComfyUI | `docs/comfyui/README.md` |
| 图编辑交付 | `docs/api/examples/image-edit-internal-handoff.md` |
| 图裂变交付 | `docs/api/examples/fission-delivery-contract-2026-05-12.md` |
| 文档治理 | `docs/standards/document-maintenance.md` |
| 早检 SOP | `docs/standards/morning-ops-check.md` |
| 样本包导出 | `docs/standards/business-sample-pack-export.md` |

## 当前阶段口径

- 当前阶段是 `v0.7 中台能力产品化与 Agent 编排版` 的正式规划期；先完成任务拆分、边界确认和验收标准，再进入代码实现。
- `origin/main` 是唯一发版真源；本地完成不代表可以更新服务器。
- 当前仓库不包含客户端代码；`docs/client/` 只保留历史资料。客户端从 v0.6 开始并行重启，但由独立团队或 agent 执行，必须遵守中台侧输出的业务 API 和边界。
- Coze 保留为接入层和快速实验入口；中台逐步承载业务版本、灰度、统计、回滚和排障。
- 业务调用以 `runId` 为主线；VL、ComfyUI、OpenAI、评分、回填、回调和计费都归入这个任务。
- v0.6 已以 `516ba656` 作为封版基线；v0.6/v0.6.3/v0.5 文档保留为阶段记录，不再作为当前执行入口。
- v0.7 优先做全局交互治理、Agent Runtime v2、能力产品化首批、质量迭代和控制面预聚合。业务流程由客户端组装，中台负责能力治理和证据沉淀。项目/工作单不是中台主视角，现有 `projectId` 只作为兼容上下文字段。
- 对话式 Agent 是中台高级能力试点：Agent 负责讨论、方案、确认和工具调用审计，确认后仍调用 `/api/business/*` 标准业务 run。它可以暂时放在图编辑分类下用于发现，但长期归宿是 Agent Runtime，不等同于可视化/画布式图编辑。
- 114 是控制面；158 和 233 是执行面，不为单台机器写业务特判。

## 历史资料

以下目录默认只用于追溯，不作为当前执行入口：

- `docs/archive/`
- `docs/client/`
- `docs/handover/`
- `docs/plans/`
- `docs/weekly/`
- `docs/retrospectives/`

如果历史资料与当前真源冲突，以当前真源为准。

## 文档维护规则

1. 新增战略任务，先写入 `docs/strategy/todo-master-2026q2.md`。
2. 新增或修改接口，必须更新 `docs/api/INDEX.md` 或对应模块文档。
3. 参数、状态、错误码变化，必须同步错误码总表和接口一致性规范。
4. 页面交互或业务动线变化，必须同步当前回顾或对应模块入口。
5. 过期 TODO、WIP 草稿和重复索引应删除或归档，不能继续进入阅读路径。

最后更新：2026-06-08
