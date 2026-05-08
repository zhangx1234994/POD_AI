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
- `COZE_CONTROL_PLANE_CONSERVATIVE_DRILL_2026-04-24.md`
  - 2026-04-24 在 `114.55.0.56` 上的真实保守演练记录
- `COZE_FIRST_WAVE_SMOKE_2026-04-24.md`
  - 第一段 Coze 控制面部署后、替换 toolbox 前的全量 smoke 记录
- `COZE_SERVER_COMMANDS_v1.md`
  - Coze 主机命令级清单
- `IMAGE_OPS_SMOKE_CHECKLIST_v1.md`
  - `image-ops` 专项 smoke 清单
- `DESKTOP_CENTERURL_CUTOVER_RUNBOOK_v1.md`
  - 桌面端第二阶段切换 runbook
- `COZE_MIGRATION_PACK_SELF_CHECK_v1.md`
  - 迁移包本地统一自检说明
- `scripts/capture_coze_control_plane_baseline.sh`
  - 迁移前/后基线采集
- `scripts/compare_coze_control_plane_baselines.py`
  - 迁移前后差异对比

## 其他测试计划

- `ABILITY_TEST_LEDGER.md`
  - 能力测试台账与上线闸门；所有能力发版前先看这里
- `API_EXPOSURE_SMOKE_CHECKLIST.md`
  - 管理端“API 开放”页对应的业务 API、原子能力 API、Coze 工具箱冒烟清单；默认不消耗生图额度。
- `backend/scripts/patrol_business_api.py`
  - 花纹提取 / 图裂变 / 扩图三条业务 API 巡检；默认只做路由预览，真实出图需显式 `--mode live --image-url <url>`。
  - 真实出图前脚本会先检查图片 URL 是否可访问，避免样例图失效误报为能力失败。
  - 发布验收时必须加 `--require-executor-evidence`，确认任务成功之外还能看到实际执行节点，避免只看终态漏掉路由问题。
- `scripts/run_podi_health_watch.sh` / `scripts/install_business_health_watch.sh`
  - 114 业务链路定时自检入口。轻量检查每 15 分钟跑一次，不消耗生图；真实巡检每天单并发跑一次，覆盖三大业务和 production 测评工作流。
  - 每次执行会把 JSON 报告写入 `reports/health-watch/`；真实巡检默认同步写入管理端“发版巡检记录”，便于上线证据追溯。
- `RELEASE_REGRESSION_REPORT_2026-04-30.md`
  - 2026-04-30 文档治理与发布前完整回归记录
- `RELEASE_REGRESSION_REPORT_2026-05-03.md`
  - 2026-05-03 事故整改后核心链路、业务计费口径与管理端构建回归记录
- `RELEASE_REGRESSION_REPORT_2026-05-06.md`
  - 2026-05-06 管理端易用性、ComfyUI 兼容性降级、能力调用排障、账号/账单/业务门禁回归记录
- `COZE_WORKFLOW_TEST_PLAN.md`
- `COMFYUI_TASK_STATE_REGRESSION_PLAN.md`
- `AUTH_BILLING_TEST_PLAN.md`
- `STATUS_ERROR_ONLINE_SMOKE_CHECKLIST.md`

## 使用原则

1. 平时能力上线优先看：
   - `ABILITY_TEST_LEDGER.md`
   - `API_EXPOSURE_SMOKE_CHECKLIST.md`
   - `backend/scripts/patrol_business_api.py`
   - `COZE_WORKFLOW_TEST_PLAN.md`
2. 迁移当天优先看：
   - `COZE_CONTROL_PLANE_RUNBOOK_v1.md`
   - `COZE_SERVER_COMMANDS_v1.md`
3. 需要完整口径时再回到：
   - `docs/strategy/coze-mid-platform-migration-v1.md`
   - `docs/strategy/coze-migration-inventory-v1.md`
4. 需要脚本时，对照：
   - `scripts/run_coze_control_plane_cutover.sh`
   - `scripts/rollback_coze_control_plane.sh`
   - `scripts/rollback_verify_coze_control_plane.sh`
   - `scripts/check_coze_control_plane_bundle.sh`
   - `scripts/selfcheck_coze_migration_pack.sh`
