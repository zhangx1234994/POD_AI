# 发布前回归记录（2026-05-03）

## 1. 本轮范围

本轮用于验证事故整改后的核心代码链路、业务能力计费口径、管理端展示和发布守护是否仍满足阶段性上线条件。

覆盖范围：

- 后端发布 smoke、业务 API、业务能力管理、ComfyUI 队列路由、评测巡检、能力调用日志摘要。
- 管理端 TypeScript 类型检查。
- 管理端生产构建。
- 工作区差异空白检查。

未覆盖范围：

- 线上 Coze 工作流真实提交。
- 线上三大业务真实出图。
- 线上 ComfyUI 双机容量压测。
- KIE 余额恢复后的真实商业模型回归。
- 管理端登录后的人工视觉验收。

## 2. 执行结果

| 项目 | 命令 | 结果 |
| --- | --- | --- |
| 后端重点回归 | `python3 -m pytest tests/test_podi_release_smoke.py tests/test_business_capability_admin.py tests/test_business_api_contract.py tests/test_admin_dashboard_release_governance.py tests/test_comfyui_queue_routing.py tests/test_comfyui_queue_health_writeback.py tests/test_patrol_eval_workflows.py tests/test_ability_log_service_extract.py -q` | 通过：85 passed, 14 warnings |
| 管理端类型检查 | `npm run lint` in `podi-admin-web` | 通过 |
| 管理端生产构建 | `npm run build` in `podi-admin-web` | 通过 |
| 空白差异检查 | `git diff --check` | 通过 |

## 3. 本轮确认的关键点

- `podi_release_smoke.py`、业务 API 契约、评测巡检和 ComfyUI 队列路由相关测试均通过，说明本地代码层没有复发 `INTERNAL_ONLY`、队列误判、成功无回填误判等事故类问题。
- 业务运行列表和详情已区分“可计费成本”和“实际上游成本”，失败、取消、超时会进入不计费口径。
- 管理端业务调用详情增加链路判定，按版本选择、能力下发、执行节点、输出回填、业务回调五段显示排查方向。
- 管理端能力调用日志支持图片、视频、文字和结构化结果摘要，不再只按图片能力理解所有输出。

## 4. 已知非阻断问题

- 后端仍存在既有 Pydantic/FastAPI 弃用警告，本轮不阻断，但后续依赖升级前需要专项处理。
- 管理端构建仍有较大的 `storage-vendor`、`tdesign-vendor` 依赖块；前端整体整改阶段统一处理，不作为本轮事故修复阻断项。
- KIE 余额问题暂时保留为外部依赖风险，相关真实商业模型回归需余额恢复后再跑。

## 5. 上线前还必须补的线上动作

正式更新服务器前后仍需执行：

1. 确认目标提交已推送到 `origin/main`。
2. 114 后端更新后运行 `podi_release_smoke.py`。
3. 用 `patrol_business_api.py --mode live --require-executor-evidence --image-url <样例图>` 跑花纹提取、图裂变、扩图真实链路。
4. 抽测 Coze 工作流到中台能力的路径，确认 toolbox 不再返回 `INTERNAL_ONLY`。
5. 打开管理端总览，确认“上线结论”和“线上自检守护”没有阻塞项。

当前判断：本地代码层通过阶段性上线前检查，但还不能替代线上真实业务链路验收。

*记录时间: 2026-05-03*
