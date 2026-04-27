# Release Preflight Checklist (Test Machine)

Goal: run these checks on the test machine before deploying to the production server.

## 0) Recommended Env (Stable Mode)

- `EVAL_PUBLIC_ENABLED=true`
- `EVAL_FANOUT_MAX_WORKERS=1` (stable patrol mode; capacity test uses a separate script)
- `EVAL_RUN_MAX_WORKERS=6`
- `EVAL_COMFYUI_RUN_MAX_WORKERS=2` (stable patrol mode; do not use this value to judge GPU capacity)
- `ABILITY_TASK_MAX_WORKERS=24`
- `COMFYUI_ROUTE_BY_QUEUE=true`
- `COMFYUI_QUEUE_BATCH_SIZE=10`
- `COZE_BASE_URL=...`
- `COZE_API_TOKEN=...`
- Optional (legacy fallback only): `COZE_COMFYUI_CALLBACK_WORKFLOW_ID=...`

## 0.0) Incident Gate: Real Business Chain Must Pass

This gate was added after the 2026-04-27 `INTERNAL_ONLY` incident. `/health`
is not enough. A release is not valid until the real chain passes:

```text
Eval UI / Coze
  -> backend toolbox
    -> ability task
      -> ComfyUI / vendor-api
        -> OSS result
```

Fast path on the backend/Coze host:

```bash
python3 backend/scripts/podi_release_smoke.py \
  --base-url http://127.0.0.1:8099 \
  --expect-server-url http://10.11.0.7:8099 \
  --max-production-per-category 2
```

Eval operations gate:

```bash
python3 backend/scripts/check_eval_operations_health.py \
  --stale-minutes 30 \
  --submit-grace-minutes 5 \
  --recent-hours 24
```

Expected:

- `health` passes.
- `coze_openapi` passes and shows the address Coze uses.
- `internal_tasks_get` returns `404 TASK_NOT_FOUND`, not `401 INTERNAL_ONLY`.
- `comfyui_queue_summary` returns all active ComfyUI executors.
- `eval_workflow_catalog` returns a non-empty public catalog, includes at least one `production` workflow, does not leak `legacy/auxiliary/disabled` roles, has no duplicate workflow IDs, and does not exceed 2 production entries in one business category.
- `check_eval_operations_health.py` returns `healthy` or only an accepted `warning`; `critical` blocks release. `EVAL_NO_RECENT_RUNS` means patrol did not run recently, and `EVAL_NO_RECENT_SUCCESS` means the recent business chain has no successful sample.
- `check_eval_operations_health.py` prints the real concurrency snapshot; if ComfyUI queue capacity is 20 but `evalFanoutMaxWorkers=1`, a single fission run is intentionally sequential and must not be treated as a GPU capacity issue without running `comfyui_capacity_probe.py`.
- `COMFYUI_EXECUTOR_UNREACHABLE` is not ignored: either restore the executor service or explicitly mark the executor offline before release.

Manual checks:

1. Public backend health:
   - `curl -fsS http://<backend-host>:8099/health`
   - Also confirm the listening PID belongs to the formal service, not an old manual process:
     `ss -ltnp | grep ':8099'` and `systemctl status podi-backend`
2. Coze toolbox OpenAPI server URL:
   - Run from the backend/Coze host: `curl -fsS http://127.0.0.1:8099/api/coze/podi/openapi.json`
   - Confirm `servers[0].url` is the address Coze can actually reach.
   - External callers may receive `401 INTERNAL_ONLY`; this is expected for protected toolbox surfaces.
3. Coze-side internal call:
   - From the Coze container/host, call `/api/coze/podi/tasks/get` with a fake task ID.
   - Expected: `404 TASK_NOT_FOUND`.
   - Failure: `401 INTERNAL_ONLY` means Coze still cannot call backend tools.
4. Full eval patrol:
   ```bash
   python3 backend/scripts/patrol_eval_workflows.py \
     --base-url http://<backend-host>:8099 \
     --timeout 1800
   ```
   Expected: all active workflows end in `succeeded`.
5. Eval operations health:
   ```bash
   python3 backend/scripts/check_eval_operations_health.py
   ```
   Expected: no stale running runs, no submit-stalled runs, no succeeded-without-output records, and no active ComfyUI executor with unreadable queue.
6. ComfyUI queue visibility:
   ```bash
   python3 backend/scripts/comfyui_capacity_probe.py
   ```
   Expected: all active ComfyUI executors return queue counts.

If any of the above fails, do not continue with frontend/admin acceptance.

## 0.1) Release Source of Truth (Must Check First)

Before any server update, verify the release target from `origin/main` instead of a local dirty workspace.

Required checks:

1. Confirm target commit is already in `origin/main`
   - `git fetch origin`
   - `git log --oneline -1 origin/main`
2. In the server working copy, confirm the repo is actually on `main`
   - `git branch --show-current`
   - `git rev-parse --short HEAD`
3. If the running service is frontend/dev-server based, confirm the process is started from this updated directory
   - do not assume “already restarted” means “already updated”

Do **not** use the following as the release signal by itself:

- “local branch has the code”
- “someone said it was updated”
- “current workspace can see the commit”
- “there is only one listening process on the port”

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

## 2.1) ComfyUI Capacity Gate (After Functional Patrol)

This is separate from the stable eval patrol. The goal is to verify that PODI can
feed ComfyUI queues tightly enough and that queue routing really uses the expected
executors.

Run on the backend host:

```bash
python3 backend/scripts/comfyui_capacity_probe.py \
  --capability-key <confirmed-safe-comfyui-capability> \
  --count 12 \
  --yes
```

Expected:

- queue snapshots show running/pending counts changing during the probe.
- task summary shows which executor each task used.
- a single executor does not exceed 10 queued + running tasks.
- if a capability is expected to be dual-machine capable, tasks should distribute across both machines.
- terminal status must not stay `running` after ComfyUI `/history` has `status=success`.
- if `/history` is `success` but `outputs` is empty, backend must close the task as `failed` with `COMFYUI_IMAGES_EMPTY` after the short grace period.
- for cache-prone workflows, use a unique output prefix or random seed so ComfyUI does not return an empty cached history.

If all tasks stay on one machine, check ability metadata:

- `allowed_executor_ids`
- `required_tags`
- `routing_policy`
- workflow/model/LoRA consistency across both ComfyUI nodes

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
  - `GET /api/wallet/v1/usage-summary` 统计口径与 ledger 对齐
  - 能力任务成功后应写入 `task_cost_snapshots`（含 `pricing_version`）
  - 失败/取消任务不扣费
  - 账单明细可追溯 `task_id + trace_id`
  - 若配置了 `WALLET_CALLBACK_TOKEN`：未携带 token 的充值回调应返回 `RECHARGE_CALLBACK_UNAUTHORIZED`
  - 若配置了 `WALLET_CALLBACK_SIGNING_SECRET`：签名缺失/错误返回 `RECHARGE_CALLBACK_SIGNATURE_INVALID`，过期返回 `RECHARGE_CALLBACK_SIGNATURE_EXPIRED`
