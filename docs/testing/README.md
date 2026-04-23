# 测试与演练入口

本目录只放两类东西：

1. 当前仍然有效的测试计划
2. 迁移、灰度、回滚当天要直接执行的 runbook / checklist

## Coze 控制面迁移相关

- `COZE_CONTROL_PLANE_MIGRATION_CHECKLIST.md`
  - 迁移前后的总检查清单
- `COZE_CONTROL_PLANE_MIGRATION_DRILL_v1.md`
  - 迁移前演练步骤
- `COZE_CONTROL_PLANE_RUNBOOK_v1.md`
  - 迁移当天一页执行清单
- `COZE_SERVER_COMMANDS_v1.md`
  - Coze 主机命令级清单
- `IMAGE_OPS_SMOKE_CHECKLIST_v1.md`
  - `image-ops` 专项 smoke 清单
- `DESKTOP_CENTERURL_CUTOVER_RUNBOOK_v1.md`
  - 桌面端第二阶段切换 runbook

## 其他测试计划

- `COZE_WORKFLOW_TEST_PLAN.md`
- `COMFYUI_TASK_STATE_REGRESSION_PLAN.md`
- `AUTH_BILLING_TEST_PLAN.md`
- `STATUS_ERROR_ONLINE_SMOKE_CHECKLIST.md`

## 使用原则

1. 迁移当天优先看：
   - `COZE_CONTROL_PLANE_RUNBOOK_v1.md`
   - `COZE_SERVER_COMMANDS_v1.md`
2. 需要完整口径时再回到：
   - `docs/strategy/coze-mid-platform-migration-v1.md`
   - `docs/strategy/coze-migration-inventory-v1.md`
3. 需要脚本时，对照：
   - `scripts/run_coze_control_plane_cutover.sh`
   - `scripts/rollback_coze_control_plane.sh`
   - `scripts/rollback_verify_coze_control_plane.sh`
   - `scripts/check_coze_control_plane_bundle.sh`
