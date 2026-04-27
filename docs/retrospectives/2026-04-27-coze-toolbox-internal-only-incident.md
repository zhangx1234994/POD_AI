# 2026-04-27 Coze 工具箱不可用事故复盘

## 结论

这是一次生产可用性事故。表面现象是 Coze 工作流调用工具箱返回 `401 INTERNAL_ONLY`，实际问题是迁移后缺少端到端巡检，导致服务健康但业务链路不可用。

本次暴露的问题：

- Coze 工作流调用 backend 工具箱失败。
- 服务 `/health` 正常，但真实业务链路不可用。
- ComfyUI 已完成但中台没有图片回填时，任务可能长期停在 `running`。
- ComfyUI 队列利用率不可见，无法判断 GPU 是否被充分喂满。
- 测评端工作流目录存在同名、旧版、灰度版混杂问题。

## 直接原因

Coze 工具箱 OpenAPI 中的服务地址、backend 内网访问保护、Coze 容器实际出网来源三者没有一起验证。服务 `/health` 正常不代表 Coze 工具箱能真正调用成功。

## 深层原因

1. **上线验收只覆盖服务存活，没有覆盖业务链路。**
- 只看 backend、admin、eval 是否启动，不能发现工具箱调用失败。

2. **缺少自动化全量测评巡检。**
- 测评端有 30+ 个工作流，但没有固定每日/每次发版后跑一遍。

3. **缺少 ComfyUI 队列与 GPU 利用率观测。**
- 当前只能看到部分任务列表，不能判断每台机器是否被喂满、任务之间是否有空档。

4. **ComfyUI 成功不等于有图。**
- `/history/{promptId}` 可能返回 `status=success` 但 `outputs={}`。
- 这种情况必须进入失败终态，不能让业务一直等。

5. **服务健康检查可能打到旧进程。**
- 114 上曾同时存在 systemd 服务和旧手工 uvicorn 进程，`/health` 正常但实际运行的不是最新代码。

## 已完成处置

- 修复 Coze 同机调用 backend 的 `INTERNAL_ONLY` 问题。
- 确认外部伪造内网头仍会被拒绝，避免放开安全边界。
- 跑完测评端全部 active 工作流巡检，确认主链路可用。
- 修复 ComfyUI 已成功但输出为空时中台任务长期 `running` 的问题：连续 3 次确认空输出后标记 `failed`，错误为 `COMFYUI_IMAGES_EMPTY` 或 `COMFYUI_ASSETS_EMPTY`。
- 修复背景抠图 `beijing_koutu` 被 ComfyUI 全缓存后 `/history` 无图片的问题：每次提交写入唯一输出前缀，保证 SaveImage 节点重新执行。
- 清理 114 服务器上长期占用 8099 的旧手工后端进程，恢复 `podi-backend.service` 作为唯一正式运行方式。
- 通过工具箱入口提交 4 个背景抠图任务，确认两台 ComfyUI 各承接 2 个，最终 `4/4` 成功。
- 新增发布后 smoke 脚本 `backend/scripts/podi_release_smoke.py`，在 114 主机内验证健康检查、OpenAPI、内部任务查询和 ComfyUI 队列。
- 新增评测运行健康检查 `backend/scripts/check_eval_operations_health.py` 和管理端接口 `/api/admin/evals/operations-health`，用于发现长期运行、提交卡住、成功无结果、近期失败、最近无评测业务、最近无成功样本等 `/health` 看不到的问题。
- 健康检查增加并发快照，直接输出评测总并发、ComfyUI 评测并发、单任务裂变并发、ComfyUI 队列容量和当前队列，避免把“稳定模式串行 fanout”误判成能力服务器没有吃满。

## 立即整改项

### P0-1 业务链路自动巡检

每次发版后必须执行：

```bash
python3 backend/scripts/podi_release_smoke.py \
  --base-url http://127.0.0.1:8099 \
  --expect-server-url http://10.11.0.7:8099
```

并定期执行：

```bash
python3 backend/scripts/patrol_eval_workflows.py \
  --base-url http://114.55.0.56:8099 \
  --timeout 1800
```

巡检前后执行：

```bash
python3 backend/scripts/check_eval_operations_health.py \
  --stale-minutes 30 \
  --submit-grace-minutes 5 \
  --recent-hours 24
```

验收：

- 所有 active 工作流最终成功。
- 报告中记录 Coze 执行 ID、中台任务 ID、图片数量、错误摘要。
- 健康检查不得出现 `critical`；若出现长期运行或提交卡住，必须先收口再继续发版。
- 任一失败必须进入事故看板或当日待办。

### P0-2 ComfyUI 队列压测与利用率验证

必须验证“单机 10、双机 20”不是纸面配置：

```bash
python3 backend/scripts/comfyui_capacity_probe.py \
  --capability-key <可压测能力key> \
  --count 12 \
  --yes
```

验收：

- 能看到每台 ComfyUI 的 running/pending。
- 能看到任务实际分配到哪个执行节点。
- 能判断是否存在“GPU 空着但中台没有继续喂任务”的空档。
- 压测能力必须先确认不会被 ComfyUI 全缓存；如果出现 `COMFYUI_IMAGES_EMPTY`，先排查 workflow 缓存或输出节点，而不是直接归因于并发。

### P0-3 发布门禁升级

每次发版必须同时满足：

- `/health` 正常。
- 端口 PID 属于正式服务，不是旧手工进程。
- 在 backend/Coze 主机内执行 `backend/scripts/podi_release_smoke.py` 通过。
- Coze 工具箱 OpenAPI 可访问，且 server 地址符合当前部署。
- Coze 容器内调用 `/api/coze/podi/tasks/get` 能进入 backend，不再被 `INTERNAL_ONLY` 错挡。
- 测评端主工作流巡检通过。
- ComfyUI 队列查询可用。

### P0-4 工作流目录治理

active 工作流必须拆清：

- 默认生产版本。
- 灰度版本。
- 历史保留版本。
- 查询/监控类辅助工具。

不允许让业务和运维面对一堆同名“图裂变”。

## 后续原则

- Coze 保留为业务入口和快速实验层。
- 中台负责业务版本、默认版本、灰度、回滚、调度、监控。
- 高并发任务由中台直接喂给能力节点，不依赖 Coze 循环慢慢提交。
- 前端优化可以继续，但必须排在链路巡检和调度可观测之后。
