# Release Preflight Checklist (Test Machine)

Goal: run these checks on the test machine before deploying to the production server.

## 0) Recommended Env (Stable Mode)

- `EVAL_PUBLIC_ENABLED=true`
- `EVAL_FANOUT_MAX_WORKERS=1` (sequential fan-out for stability)
- `EVAL_RUN_MAX_WORKERS=2` (keep pressure low during validation)
- `COZE_BASE_URL=...`
- `COZE_API_TOKEN=...`
- Optional (legacy fallback only): `COZE_COMFYUI_CALLBACK_WORKFLOW_ID=...`

## 1) Multi-ComfyUI Connectivity

From the PODI backend host (8099), confirm it can reach *each* ComfyUI executor baseUrl
(以管理端“执行节点”配置为准，主服务器可能调整):

- `http://<comfyui-host-1>:8079/`
- `http://<comfyui-host-2>:8079/`

If one host is not reachable, ComfyUI tasks may "generate but never refresh" because we
cannot poll `/history/{promptId}` to finalize the job.

## 2) Critical Flows (Must Pass)

### A) Continuous Pattern (四方/两方连续图)

- Start one run in the eval platform.
- Expectation:
  - Eval UI shows `running` first.
  - Within the timeout window, the run becomes `succeeded` and images appear.

If it gets stuck on `running`, check:
- `/api/coze/podi/tasks/get` response field `debugResponse` (it carries the last error hint)
- `ability_tasks.error_message` in DB

### B) Image Variation (图裂变, ComfyUI callback type)

- Run `count=4` (fan-out) in eval UI.
- Expectation:
  - Images appear incrementally ("1 ready, 2 ready..."), not only at the end.
  - No duplicate jobs appear on the ComfyUI side after backend restart.

### C) KIE / Multi-modal generation

- Run one KIE workflow end-to-end.
- Expectation:
  - If KIE status polling is slow/flaky, the error should include upstream status/body snippet
    (e.g. `KIE_STATUS_HTTP_502 body='...'`) instead of a generic `KIE_STATUS_HTTP_ERROR`.

## 3) Restart Safety (No Duplicate ComfyUI Submissions)

This verifies we don't "resubmit running ComfyUI jobs" on backend restart.

Steps:
1) Submit a long-running ComfyUI task (it will stay `running` after submit).
2) Restart the PODI backend process.
3) Confirm ComfyUI does NOT get new jobs for the same task.

## 4) Build/Tests (Quick Gate)

- Backend: `python3 -m pytest -q backend/tests`
- Eval UI: `npm -C podi-eval-web run build`
- Admin UI: `npm -C podi-admin-web run lint`

## 5) Pricing Completeness Audit (Cost Safety Gate)

- Run pricing audit before release (avoid “调用成功但成本统计缺失”):
  - 全量：`python3 backend/scripts/audit_ability_pricing.py`
  - 指定厂商：`python3 backend/scripts/audit_ability_pricing.py --provider kie`
  - JSON：`python3 backend/scripts/audit_ability_pricing.py --json`
- Exit code:
  - `0`：通过（无缺失）
  - `2`：存在缺失项（需补齐 `metadata.pricing`）

## 6) Auth & Billing Gate (Q2)

- 钱包迁移与初始化（若本次发版包含钱包改动）：
  - `cd backend && python3 -m alembic upgrade head`
  - `python3 backend/scripts/init_wallet_accounts.py --dry-run`
  - `python3 backend/scripts/init_wallet_accounts.py --apply`
- 认证链路（若本次发版包含认证改动）：
  - 登录成功 / 登录失败（错误码正确）
  - refresh 成功 / refresh 过期
  - 会话注销后不可继续 refresh
- 计费链路（若本次发版包含钱包改动）：
  - 成功任务扣费一次（无重复扣费）
  - `POST /api/wallet/v1/expenses` 在相同 `userId+traceId` 下不重复扣费
  - 失败/取消任务不扣费
  - 账单明细可追溯 `task_id + trace_id`
  - 若配置了 `WALLET_CALLBACK_TOKEN`：未携带 token 的充值回调应返回 `RECHARGE_CALLBACK_UNAUTHORIZED`
  - 若配置了 `WALLET_CALLBACK_SIGNING_SECRET`：签名缺失/错误返回 `RECHARGE_CALLBACK_SIGNATURE_INVALID`，过期返回 `RECHARGE_CALLBACK_SIGNATURE_EXPIRED`
