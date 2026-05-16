# 2026-05 文档归档

本批次清理目标：把已经被新标准取代、但仍有追溯价值的顶层历史文档移出主入口，避免后续开发误读。

| 归档文档 | 当前替代入口 |
| --- | --- |
| `COZE_INTEGRATION_GUIDE.md` | `docs/api/modules/coze.md`、`docs/coze/toolbox-inventory.md` |
| `COZE_WORKFLOWS.md` | `docs/eval/eval-platform.md`、`docs/coze/comfyui-workflow-mapping.md` |
| `coze-integration.md` | `docs/api/modules/coze.md` |
| `coze-plugin-podi.md` | `docs/api/modules/coze.md` |
| `DEPLOYMENT.md` | `docs/standards/release-sop.md` |
| `deploy-checklist.md` | `docs/standards/release-sop.md`、`docs/standards/per-feature-release-checklist.md` |
| `deploy-podi.md` | `docs/standards/release-sop.md` |
| `TODO_PLATFORM.md` | `docs/strategy/todo-master-2026q2.md` |
| `error-codes.md` | `docs/standards/error-catalog.md`、`docs/standards/error-contract.md` |
| `smart-polling-mechanism.md` | `docs/standards/business-mainline-contract.md`、`docs/api/INDEX.md` |
| `async-task-monitoring.md` | `docs/standards/business-mainline-contract.md` |
| `task-submission-flow.md` | `docs/standards/business-mainline-contract.md`、`docs/api/modules/business.md` |
| `workflow-platform-requirements.md` | `docs/strategy/business-orchestration-control-plane-v1.md` |

规则：

1. 归档文档只允许追加“归档说明”或修复断链，不再作为现行方案维护。
2. 新开发引用文档时，优先引用当前替代入口。
3. 如果归档文档再次具备现行价值，必须先从 `docs/strategy/todo-master-2026q2.md` 立项，再恢复到对应模块目录。
