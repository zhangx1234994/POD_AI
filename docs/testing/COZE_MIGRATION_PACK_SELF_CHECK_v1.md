# Coze 迁移包本地自检 v1

## 目标

在推送或正式演练前，先对这版迁移包本身做一轮本地自检。

这里检查的不是线上服务，而是：

- 文档真源是否齐
- 关键脚本是否存在
- shell / python 辅助脚本是否至少能通过语法与基础执行
- 迁移包入口脚本能不能正常打印计划
- 基线采集 / 对比链路是否自洽

## 总入口

```bash
cd /private/tmp/pod_migration_plan
bash scripts/selfcheck_coze_migration_pack.sh
```

## 覆盖范围

这条自检脚本当前会检查：

1. shell 脚本语法
   - `run_coze_control_plane_cutover.sh`
   - `rollback_coze_control_plane.sh`
   - `rollback_verify_coze_control_plane.sh`
   - `deploy_coze_control_plane_nodocker.sh`
   - `deploy_coze_backend_image_ops_only.sh`
   - `check_coze_control_plane_bundle.sh`
   - `smoke_coze_primary_workflows.sh`
   - `capture_coze_control_plane_baseline.sh`
   - `prod_write_backend_env.sh`
   - `prod_write_image_ops_env.sh`
   - `prod_write_coze_control_plane_envs.sh`

2. python 脚本编译
   - `compare_coze_control_plane_baselines.py`
   - `check_coze_migration_pack_completeness.py`
   - `check_coze_host_cutover_refs.py`
   - `collect_coze_migration_inventory.py`
   - `smoke_image_ops_via_backend.py`

3. 迁移包完整性
   - `check_coze_migration_pack_completeness.py`

4. host 分批检查
   - `check_coze_host_cutover_refs.py`

5. inventory 收集
   - `collect_coze_migration_inventory.py`

6. cutover 计划输出
   - `run_coze_control_plane_cutover.sh plan`

7. 基线采集 / 对比
   - `capture_coze_control_plane_baseline.sh`
   - `compare_coze_control_plane_baselines.py`

## 通过标准

下面几项同时成立，才算这版迁移包通过本地自检：

1. `selfcheck_coze_migration_pack.sh` 退出码为 `0`
2. `check_coze_migration_pack_completeness.py` 返回 `status=ok`
3. `check_coze_host_cutover_refs.py` 没有首轮阻塞项
4. `baseline compare` 返回 `diffCount=0`

## 备注

这条自检不会真正部署服务，也不会访问真实线上 Coze workflow。  
它只验证：

- 迁移包本身是否完整
- 本地辅助脚本是否还能跑
- 迁移当天需要的入口链路有没有断
