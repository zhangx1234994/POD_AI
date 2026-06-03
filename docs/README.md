# POD AI Studio 文档入口

本文只解决一个问题：现在该看哪些文档。历史资料可以追溯，但不能直接当作当前执行依据。

## 5 分钟阅读顺序

1. `docs/strategy/mid-platform-completeness-v0.6-plan.md`
2. `docs/strategy/ability-governance-operating-model-v0.6.md`
3. `docs/strategy/ability-definition-v0.6.md`
4. `docs/strategy/ability-api-gap-v0.6.md`
5. `docs/strategy/business-agent-runtime-v0.6.md`
6. `docs/strategy/client-parallel-preview-v0.6-handoff.md`
7. `docs/strategy/todo-master-2026q2.md`
8. `docs/standards/business-mainline-contract.md`
9. `docs/standards/external-api-boundary.md`
10. `docs/api/INDEX.md`

## 当前真源

| 类型 | 文档 | 用途 |
| --- | --- | --- |
| 当前方案 | `docs/strategy/mid-platform-completeness-v0.6-plan.md` | v0.6 中台能力治理、客户端支撑底座和各端边界 |
| 能力治理模型 | `docs/strategy/ability-governance-operating-model-v0.6.md` | 能力优先、调用上下文只作为证据索引的统一评审口径 |
| 能力定义 | `docs/strategy/ability-definition-v0.6.md` | 中台业务能力、原子能力、输入输出、质量和错误边界 |
| 能力缺口 | `docs/strategy/ability-api-gap-v0.6.md` | 现有业务 API 盘点、产品图/组图/模特图/视频缺口和实施顺序 |
| 业务 Agent | `docs/strategy/business-agent-runtime-v0.6.md` | 对话式图编辑 Agent 的边界、Runtime、API 和升级门槛 |
| 客户端交接 | `docs/strategy/client-parallel-preview-v0.6-handoff.md` | 给客户端团队或新 agent 的业务组装边界、页面和验收说明 |
| 兼容调用上下文 | `docs/strategy/project-context-backend-design-v0.6.md` | 历史命名的兼容实现记录；不作为中台主概念继续扩展 |
| 当前回顾 | `docs/strategy/project-half-year-review-2026-05-26.md` | 半年度复盘、数据证据、阶段结论和下一阶段方向 |
| 唯一 TODO | `docs/strategy/todo-master-2026q2.md` | 当前任务池 |
| 交付方法论 | `docs/standards/delivery-methodology.md` | 交付顺序、多视角批判、自我批判和六顶思考帽评审准则 |
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

- 当前开发主线是 `v0.6 中台能力治理与客户端支撑底座版`。
- `origin/main` 是唯一发版真源；本地完成不代表可以更新服务器。
- 当前仓库不包含客户端代码；`docs/client/` 只保留历史资料。客户端从 v0.6 开始并行重启，但由独立团队或 agent 执行，必须遵守中台侧输出的业务 API 和边界。
- Coze 保留为接入层和快速实验入口；中台逐步承载业务版本、灰度、统计、回滚和排障。
- 业务调用以 `runId` 为主线；VL、ComfyUI、OpenAI、评分、回填、回调和计费都归入这个任务。
- 下一阶段优先补能力 API 完整性、能力版本治理、路由质量证据、调用上下文、素材资产、业务 run 关联、选择记录和交付包证据；业务流程由客户端组装，中台负责能力治理和证据沉淀。项目/工作单不是中台主视角，现有 `projectId` 只作为兼容上下文字段。
- 对话式 Agent 先作为中台高级能力试点：Agent 负责讨论和方案卡片，确认后仍调用 `/api/business/*` 标准业务 run。
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
