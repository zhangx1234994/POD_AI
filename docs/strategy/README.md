# 战略工作区

本目录只承载平台级方向、当前执行清单和治理规则。接口细节、模块说明、测试报告不放在这里展开。

## 当前必读

1. `todo-master-2026q2.md`
2. `v0.7-ability-productization-agent-orchestration-plan.md`
3. `v0.7-kickoff-meeting-2026-06-09.md`
4. `market-side-ai-capability-plan-2026-06-11.md`
5. `market-side-ai-technical-plan-2026-06-11.md`
6. `market-side-ai-ability-contracts-2026-06-11.md`
7. `market-side-3d-render-video-assets-2026-06-12.md`
8. `product-commercialization-remediation-2026-06-10.md`
9. `../standards/version-acceptance-template.md`
10. `../standards/agent-runtime-regression-matrix.md`
11. `../standards/eval-ability-interaction-state-model.md`
12. `ability-definition-v0.6.md`
13. `business-agent-runtime-v0.6.md`
14. `ability-governance-operating-model-v0.6.md`
15. `ability-api-gap-v0.6.md`
16. `client-parallel-preview-v0.6-handoff.md`
17. `v0.6-closure-inventory-2026-06-07.md`
18. `v0.6-closure-standardization-plan.md`
19. `v0.6.3-control-plane-hardening-plan.md`
20. `project-half-year-review-2026-05-26.md`
21. `platform-polish-v0.5-decision-plan.md`
22. `output-quality-review-v0.5.md`

## 当前阶段

- 当前阶段：`v0.7 中台能力产品化与 Agent 编排版` 正式规划。
- 当前目标：把 v0.6 已封版的能力底座推进到可产品化、可观测、可优化、可被 Agent 和客户端稳定调用的阶段。
- 当前会议材料：`v0.7-kickoff-meeting-2026-06-09.md`，用于 2026-06-09 会议确认下阶段目标和 P0 范围。
- 当前重点：v0.7 子版本拆分、市场端 AI 能力产品化、全局交互治理、Agent Runtime v2、首批能力产品化、质量迭代、控制面预聚合和文档入口切换。
- 当前市场端口径：产品图 / 设计图是最高优先级事实源，产品导出 JSON 只是可选说明材料；产品视频按“脚本、分镜、首尾帧、分段视频、可选合成片”的素材包能力建设，不再只以最终合成片作为唯一交付物。
- 当前市场端能力契约：`product_image_set`、`model_scene_image`、`promo_video` 已形成草案，但仍是待实现能力；线上继续用 `product_commercialization` 试验入口验证文案、配图和大模型视频素材包。3D 渲染视频是独立技术路线，当前先开放 `product_3d_render_video` 方案预览，不与 KIE/Vidu 大模型视频混用。
- 当前基线：114 线上封版提交 `516ba656`，已通过 smoke、真实业务巡检、图编辑抽检、测评端 production 巡检和页面回归。
- 当前 Agent 约束：对话式改图可暂时归在图编辑分类下，但长期归宿是 Agent Runtime；可视化/画布式图编辑和对话式 Agent 改图必须保持命名、交互、API 边界和能力定义拆分。
- 当前非目标：低代码工作流编辑器、一次全自动端到端承诺、客户端直连原子能力、正式支付、全品类一次性覆盖、重型通用 Agent 平台、在本仓库实现新客户端。

## 阶段记录

这些文档保留为背景，不直接作为当前任务清单：

- `business-orchestration-workbench-v0.3-plan.md`
- `business-orchestration-workbench-v0.4-plan.md`
- `business-control-plane-v0.2-plan.md`
- `business-orchestration-control-plane-v1.md`
- `mid-platform-gap-and-roadmap-2026-05-07.md`
- `mid-platform-detailed-execution-plan-2026-05-07.md`
- `core-business-chain-review-2026-05-03.md`

## 迁移和历史方案

以下文档仅用于追溯当时决策：

- `coze-*.md`
- `image-ops-service-split-v1.md`
- `remote-image-ops-158-plan-v1.md`

当前执行优先看：

- `docs/README.md`
- `docs/strategy/v0.7-ability-productization-agent-orchestration-plan.md`
- `docs/strategy/v0.7-kickoff-meeting-2026-06-09.md`
- `docs/strategy/market-side-ai-capability-plan-2026-06-11.md`
- `docs/strategy/market-side-ai-technical-plan-2026-06-11.md`
- `docs/strategy/market-side-ai-ability-contracts-2026-06-11.md`
- `docs/standards/version-acceptance-template.md`
- `docs/standards/agent-runtime-regression-matrix.md`
- `docs/standards/eval-ability-interaction-state-model.md`
- `docs/strategy/ability-governance-operating-model-v0.6.md`
- `docs/strategy/ability-definition-v0.6.md`
- `docs/strategy/ability-api-gap-v0.6.md`
- `docs/strategy/business-agent-runtime-v0.6.md`
- `docs/strategy/client-parallel-preview-v0.6-handoff.md`
- `docs/strategy/v0.6-closure-standardization-plan.md`
- `docs/strategy/v0.6-closure-inventory-2026-06-07.md`
- `docs/strategy/v0.6.3-control-plane-hardening-plan.md`
- `docs/strategy/mid-platform-completeness-v0.6-plan.md`
- `docs/strategy/todo-master-2026q2.md`
- `docs/standards/release-sop.md`

兼容调用上下文的历史实现记录可查 `docs/strategy/project-context-backend-design-v0.6.md` 和 `docs/strategy/end-to-end-business-object-api-v0.6.md`。这两份文档不再作为中台主视角入口，后续新方案统一以能力和调用上下文表述。

## 使用规则

1. 新任务先进入 `todo-master-2026q2.md`，否则不算当前任务。
2. 新方案必须说明目标、范围、非目标、验收标准和测试计划。
3. 已完成阶段方案保留，但不得继续当成待办清单。
4. 文档冲突时，按“当前回顾 -> 唯一 TODO -> 当前方案 -> 标准规范 -> 历史资料”的顺序判断。
5. 每轮重要开发结束后，更新 `project-current-review-YYYY-MM-DD.md` 或当前回顾文档。

最后更新：2026-06-11
