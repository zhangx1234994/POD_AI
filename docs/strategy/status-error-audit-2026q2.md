# 状态与错误口径核对表（2026Q2）

> 目标：把“状态口径一致、错误可解释、文档可追溯”从原则变成可执行检查。  
> 对应待办：`docs/strategy/todo-master-2026q2.md` -> P0-4。  
> 检查周期：每周一次（建议周三），发布前必须再跑一次。

## 1. 核对矩阵（第一版）

| 领域 | 关键接口/页面 | 双阶段状态字段 | 错误码口径 | 文档一致性 | 测试覆盖 | 当前结论 |
| --- | --- | --- | --- | --- | --- | --- |
| 能力异步任务 | `/api/ability-tasks/*`、管理端能力调用列表 | 部分落地 | 已有主干错误码，已补前端映射 | 部分同步 | 部分覆盖 | ⚠️ 需补齐 |
| Coze 任务查询 | `/api/coze/podi/tasks/get`、测评端文档页 | 已落地（任务状态收敛） | 主要错误码已定义 | 已同步但有历史漂移风险 | 需补自动化 | ⚠️ 需巡检 |
| ComfyUI 任务下发 | `/api/admin/comfyui/tasks*`、ComfyUI 管理页 | 已落地（提交/回调/最终） | 已收敛，已接入错误映射 | 已同步 | 已有专项回归计划 | ⚠️ 回归待执行 |
| 修复任务 | `/api/admin/comfyui/repair-jobs*` | 已落地 | 失败项语义已分层 | 已同步 | 已有专项回归计划 | ⚠️ 回归待执行 |
| 批量评测/标注 | `/api/evals/batches/*` | 分页与进度已落地 | 需补“未结束不可标注”全链路错误演示 | 已同步 | 已补函数层+API层契约测试，待线上大样本回归 | ⚠️ 需补齐 |
| 桌面端 Agent | `/api/agent/*`、管理端桌面端部署页 | bootstrap 与任务口径分离 | 主要错误码可用，缺部署失败模板 | 部分同步 | 缺契约自动回归 | ⚠️ 需补齐 |

图例：
- ✅ 已完成
- ⚠️ 有缺口（可上线但不稳定）
- ❌ 未落地

## 2. 缺口清单（按优先级）

### P0（本周必须完成）
1. ✅ 补一份“状态映射核对表”到管理端/测评端文档引用处，避免“同义词漂移”。
2. ✅ 给 ComfyUI 任务与修复任务补 1 轮标准化回归计划（成功/失败/超时/重试）。
3. ✅ 补“错误码 -> 前端提示文案”映射，至少覆盖高频 20 条错误。

### P1（下周完成）
1. 给 Coze / Agent 接口加每日契约巡检（字段变更报警）。
2. 把评测端标注链路的错误演示写成固定示例（便于业务联调）。

### P2（后续优化）
1. 将“状态与错误核对”接入发版 preflight（脚本化）。
2. 将关键缺口转成自动化测试门禁（CI）。

## 3. 本周执行单（2026-03-04 ~ 2026-03-10）

1. `doing` 输出状态映射核对表 V1（本文档 + 关联链接）。
2. `done` 增补 ComfyUI 任务/修复任务回归用例清单（成功/失败/重试/超时）。
3. `done` 更新错误码映射文档（`docs/standards/error-message-map-v1.md`）。
4. `done` 在 `docs/admin/integration-dashboard.md` 与 `docs/eval/eval-platform.md` 补充状态/错误判读文案。
5. `done` 补充评测批次标注进度契约单测（`backend/tests/test_eval_review_progress_contract.py`），覆盖默认值、页码归一、404/403 错误码。
6. `done` 执行错误码目录扫描并补齐缺口（`scripts/check_error_catalog.py` 通过，新增 5 个错误码条目）。
7. `done` 输出回归报告（`docs/testing/STATUS_ERROR_REGRESSION_REPORT_2026-03-05.md`），沉淀覆盖清单与剩余风险。
8. `done` 补充批量评测标注 API 契约回归（`backend/tests/test_eval_review_api_contract.py`，覆盖 400/409 与分页归一口径）。
9. `done` 补充失败兜底错误码映射（`ABILITY_TASK_FAILED/ABILITY_TASK_CANCELLED/CALLBACK_FAILED`），减少线上 `error_code` 为空的失败记录。

## 4. 退出条件（Done 定义）

同时满足以下条件才可把 P0-4 置为 `done`：

1. 核对矩阵 6 个领域全部从 ⚠️ 变为 ✅。  
2. 文档真源同步完成（strategy + standards + admin/eval）。  
3. 发布前回归报告明确写出“已覆盖错误场景列表”。  

*最后更新: 2026-03-04*
