# 状态与错误口径回归报告（2026-03-05）

> 范围：P0-4「状态与错误口径统一落地检查」本地回归（契约与单测层）。

## 1. 本次执行项

1. `python3 -m pytest backend/tests/test_eval_review_progress_contract.py -q`
   - 结果：`6 passed`
   - 覆盖：
     - 标注进度默认值与页码归一
     - 标注进度写入 `metadata.review_state`
     - `BATCH_NOT_FOUND` / `BATCH_FORBIDDEN` 错误码契约

2. `python3 -m pytest backend/tests/test_task_status_contract.py backend/tests/test_ability_task_status_mapping.py backend/tests/test_ability_invoke_status.py backend/tests/test_coze_task_status_normalize.py -q`
   - 结果：`16 passed`
   - 覆盖：
     - submit/callback/final 三段状态映射
     - 能力任务失败/取消语义
     - Coze 状态归一与错误码提取

3. `python3 scripts/check_error_catalog.py`
   - 结果：`passed`
   - 处理：
     - 补齐错误码：`ABILITY_TASK_FAILED`、`ABILITY_TASK_CANCELLED`、`RUN_CREATE_FAILED`、`KIE_ABILITY_NOT_CONFIGURED`、`KIE_TASK_FAILED`

4. `python3 -m pytest backend/tests/test_eval_review_api_contract.py -q`
   - 结果：`5 passed`
   - 覆盖：
     - `GET /api/evals/batches/{id}/review-groups`：`BATCH_REVIEW_NOT_READY`（409）
     - `GET /api/evals/batches/{id}/review-groups`：`BATCH_REVIEW_PAGE_INVALID`（400）
     - `GET /api/evals/batches/{id}/review-groups`：`page_size` 强制归一为 20
     - `POST /api/evals/batches/{id}/review-progress`：`completed_page > current_page` 返回 `BATCH_REVIEW_PAGE_INVALID`（400）
     - `POST /api/evals/batches/{id}/review-progress`：批次未结束返回 `BATCH_REVIEW_NOT_READY`（409）

## 2. 结论

- 当前代码层面的状态映射与错误码目录已对齐，且具备基础回归保障。
- 批量评测“结果标注分页 + 断点续标”已补齐函数层 + API 层契约测试覆盖。

## 3. 未覆盖风险（需线上/联调补测）

1. ComfyUI 真实节点上的“回调晚到 + 结果补偿回填”端到端链路。
2. Agent 推送失败（`AGENT_PUSH_FAILED`）在 UI 的跨模块展示一致性。
3. 评测端大批量任务（1000+）下的状态列刷新稳定性与弱网提示。

## 4. 下一步建议

1. 夜间窗口执行一次线上手工回归（ComfyUI + KIE 各 1 轮）。
2. 已新增 `scripts/status_error_regression.sh` 并接入 `scripts/deploy_preflight.sh` 可选步骤（`RUN_STATUS_ERROR_CHECKS=1`）。
3. ✅ 已补 API 级集成测试：`backend/tests/test_eval_review_api_contract.py`。

## 5. 线上冒烟补充（2026-03-05 晚）

1. 远端预检查通过：
   - `BACKEND_URL=http://117.50.80.158:8099 ADMIN_URL=http://117.50.80.158:8199 EVAL_URL=http://117.50.80.158:8200 bash scripts/deploy_preflight.sh`
   - 结果：`PASS=5 FAIL=0`
2. Coze OpenAPI 可用：
   - `.../comfyui/lora/openapi.json`、`.../kie/catalog/openapi.json`、`.../kie/execute/nano-banana-2-image-to-image/openapi.json` 均返回 200。
3. 观察到一类历史失败记录：
   - 能力调用日志中 `status=failed` 且 `error_code` 为空（仅有 `error_message`）。
   - 已在代码补充兜底：失败场景默认回填 `ABILITY_TASK_FAILED` / `ABILITY_TASK_CANCELLED` / `CALLBACK_FAILED`。
4. Coze 查询接口兼容性增强（待部署）：
   - LoRA 查询新增 `lora_names`（兼容 `loraNames`）。
   - KIE 模型查询新增 `model_keys/media_types`（兼容 camelCase 字段）。
