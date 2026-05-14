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

## 线上验证记录（2026-05-14）

114 控制面已更新并完成稳定性复核：

| 检查项 | 结果 |
| --- | --- |
| 线上 commit | `1485d93f` |
| backend/admin/eval 健康 | 通过，`/health`、8199、8200 均可访问 |
| Coze OpenAPI server 地址 | 通过，`servers[0].url=http://172.17.0.1:8099` |
| 发布 smoke | 通过，health、OpenAPI、`tasks/get`、测评目录、业务路由均通过 |
| ComfyUI 队列汇总 | 通过，2 台可用，总容量 20，空闲 20 |
| ComfyUI 节点健康 | 158 与 233 均通过 `/system_stats`、`/queue`、`/object_info` |
| 业务 route-preview | 花纹提取、图裂变、扩图 3 条主业务均命中默认版本 |
| 旧测评异常补全 | `fa74aaffb62b41a085c5b443481c6675` 已从超时残留补全为成功并回填图片 |
| 早检导出 | 2026-05-13 业务运行 188 条，业务失败 0 条 |

早检需关注项：

- 能力调用 6 条需关注：4 条历史 pending 收口、1 条火山 VL 请求突增保护、1 条裂变评分巡检缺双图参数。
- 测评运行 1 条需关注：裂变评分巡检缺双图参数。
- 数据库/OSS 清理审计：数据库需复核分组 0 类，OSS 候选对象 0 个。

结论：本版本已具备线上稳定运行条件。下一阶段不继续围绕事故修复，而是进入当前版本固化、项目清理、业务 API 交付材料和前端产品化。

## 结论

本地候选版本回归与 114 线上稳定性复核均已通过。后续新增改动仍必须按 SOP 重新跑本地门禁和线上 smoke，不能复用本次结论。
