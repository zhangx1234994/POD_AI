# Coze 控制面迁移实施包 v1

## 目标

把当前这版迁移工作收成一个可审计、可执行、可回滚的实施包。

这份文档不重复展开细节，只负责回答两个问题：

1. 这版迁移包已经包含哪些内容
2. 真正实施时应该先看哪几份文档、跑哪几个脚本

## 实施包内容

### 1. 目标与边界

- `coze-mid-platform-migration-v1.md`
- `image-ops-service-split-v1.md`
- `coze-migration-config-matrix-v1.md`
- `coze-migration-status-summary-2026-04-24.md`

### 2. 真实对象与切换范围

- `coze-migration-inventory-v1.md`
- `coze-host-reference-phasing-v1.md`
- `coze-host-cutover-sequence-v1.md`
- `coze-desktop-centerurl-cutover-v1.md`

### 3. 主机与目录约定

- `coze-server-layout-v1.md`

### 4. 迁移当天执行材料

- `docs/testing/COZE_CONTROL_PLANE_RUNBOOK_v1.md`
- `docs/testing/COZE_SERVER_COMMANDS_v1.md`
- `docs/testing/COZE_CONTROL_PLANE_MIGRATION_CHECKLIST.md`
- `docs/testing/IMAGE_OPS_SMOKE_CHECKLIST_v1.md`
- `docs/testing/DESKTOP_CENTERURL_CUTOVER_RUNBOOK_v1.md`

### 5. 部署与检查脚本

- `scripts/deploy_coze_backend_image_ops_only.sh`
- `scripts/deploy_coze_control_plane_nodocker.sh`
- `scripts/run_coze_control_plane_cutover.sh`
- `scripts/check_coze_control_plane_bundle.sh`
- `scripts/smoke_image_ops_via_backend.py`
- `scripts/smoke_coze_primary_workflows.sh`
- `scripts/rollback_coze_control_plane.sh`
- `scripts/rollback_verify_coze_control_plane.sh`
- `scripts/prod_write_backend_env.sh`
- `scripts/prod_write_image_ops_env.sh`
- `scripts/prod_write_coze_control_plane_envs.sh`

### 6. `image-ops` 服务材料

- `image-ops-service/`
- `image-ops-service/deploy/image-ops.service`
- `image-ops-service/deploy/README.md`
- `docker-compose.image-ops.yml`

## 推荐阅读顺序

### 开始评审这版迁移包时

1. `coze-control-plane-migration-pack-v1.md`
2. `coze-mid-platform-migration-v1.md`
3. `coze-migration-inventory-v1.md`
4. `docs/testing/COZE_CONTROL_PLANE_RUNBOOK_v1.md`

### 迁移当天

1. `docs/testing/COZE_SERVER_COMMANDS_v1.md`
2. `scripts/run_coze_control_plane_cutover.sh plan`
3. `scripts/run_coze_control_plane_cutover.sh full`

### 出问题时

1. `scripts/rollback_coze_control_plane.sh`
2. `scripts/rollback_verify_coze_control_plane.sh`

## 当前范围不包含

这版明确不包含：

- OSS 内网地址硬切
- 桌面端 `CenterUrl` 首轮切换
- ComfyUI 执行节点搬迁
- 把重图像任务放回 Coze 主机本机执行

## 通过标准

只有当下面三件事都成立，这版迁移包才算完整：

1. 文档真源齐全
2. 脚本入口齐全
3. 回滚路径存在且可执行
