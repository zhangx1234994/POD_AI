# 候选版本回归记录（2026-05-14 稳定性收口）

## 范围

本次候选版本只覆盖稳定性、交付材料和清理治理，不新增复杂业务能力。

- 测评等待超时后，底层业务最终成功的状态归并。
- GPT Image 2 / ComfyUI 图裂变交付材料拆分与业务 API 文档补充。
- 每日早检、样本包导出、项目/数据库/OSS 清理审计固化。
- OSS 清理候选分组和小批量复核清单生成。

## 本地已执行

| 检查项 | 命令 | 结果 |
| --- | --- | --- |
| 后端重点回归 | `backend/.venv/bin/python -m pytest backend/tests/test_eval_public_output_compaction.py backend/tests/test_eval_service_parsing.py backend/tests/test_patrol_eval_workflows.py backend/tests/test_cleanup_audit.py backend/tests/test_business_api_contract.py backend/tests/test_export_business_sample_pack.py -q` | 通过，54 passed，12 warnings |
| 测评端类型检查 | `cd podi-eval-web && npm run lint` | 通过 |
| 管理端类型检查 | `cd podi-admin-web && npm run lint` | 通过 |
| 测评端生产构建 | `cd podi-eval-web && npm run build` | 通过 |
| 管理端生产构建 | `cd podi-admin-web && npm run build` | 通过 |
| 文档入口引用 | `python3 scripts/check_doc_entry_references.py` | 通过 |
| Alembic 单 head | `cd backend && ../backend/.venv/bin/alembic heads` | 通过，`20260513_add_business_run_query_indexes (head)` |
| 空白格式检查 | `git diff --check` | 通过 |
| 本地脏产物复扫 | `find` 排除 `.git/.venv/node_modules` 后扫描 `dist/__pycache__/.pytest_cache/*.log/*.tmp/.DS_Store` | 通过，未发现候选 |

## 已知说明

- 后端测试中的 warnings 为既有 Pydantic / FastAPI / passlib deprecation 警告，不是本次新增失败。
- 生产构建后已删除 `podi-admin-web/dist`、`podi-eval-web/dist` 和测试缓存，避免构建产物混入提交。
- OSS 清理仍是只读审计；本轮没有删除任何 OSS 对象。

## 线上待验证

部署 114 后必须执行：

1. `/health`、`/api/abilities`、`/api/evals/workflow-versions` 健康检查。
2. 确认 `20260513_add_business_run_query_indexes` migration 已在线上执行。
3. 复查测评端 `BUSINESS_RUN_TIMEOUT` 残留记录不再展示内部字典原文。
4. 抽测两个图裂变业务接口和裂变评分接口：提交、轮询、结果入库、页面展示。
5. 抽测 Coze 工具箱 `tasks/get` 和主线工作流，确认 Coze 到中台链路未回退。
6. 查看能力调用列表，确认文字/VL/结构化结果不再显示为“输出填写中”。

## 结论

本地候选版本回归通过，可以进入 114 控制面部署前准备。线上结果必须按 SOP 另行记录，不能把本地通过等同于线上通过。
