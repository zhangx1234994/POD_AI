# Release Preflight Checklist (Test Machine)

Goal: run these checks on the test machine before deploying to the production server.

## 0) Recommended Env (Stable Mode)

- `EVAL_PUBLIC_ENABLED=true`
- `EVAL_FANOUT_MAX_WORKERS=1` (stable patrol mode; capacity test uses a separate script)
- `EVAL_RUN_MAX_WORKERS=12`
- `EVAL_COMFYUI_RUN_MAX_WORKERS=10` (feed the two-node ComfyUI queue; executor max_concurrency is still the safety gate)
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
  --max-production-per-category 2 \
  --business-summary-window-hours 24 \
  --max-unresolved-business-issues 0 \
  --max-business-governance-warnings 0 \
  --max-billing-issues 0 \
  --max-unpriced-billing-runs 0 \
  --admin-token "$SERVICE_API_TOKEN" \
  --eval-admin-token "$EVAL_ADMIN_TOKEN"
```

This smoke command now covers the no-cost release chain in one pass:

- backend health
- Coze toolbox OpenAPI server URL
- Coze internal `tasks/get` boundary
- ComfyUI queue summary and routing blockers
- ComfyUI active workflow compatibility: missing custom nodes, missing model files, and routing/binding mismatch
- eval workflow public catalog governance
- core business route-preview for pattern extract, fission, and outpaint
- core business default-version governance: active default, primary ability binding, executable recipe, runtime blockers, and governance warnings
- business usage summary: unresolved issue buckets, recent unresolved issue schema, and retest recovery signal
- commercial billing report: succeeded-but-unpriced runs, billing issues, revenue/cost summary schema
- auth scope summary: active admin presence, account scope schema, business API permission boundary, and blocking auth risks
- eval operations health when `--eval-admin-token` is provided

If a release intentionally carries known historical issues, raise
`--max-unresolved-business-issues` explicitly for that run and record the reason
in the release note. Do not silently remove this gate.

Eval operations gate:

```bash
backend/.venv/bin/python backend/scripts/check_eval_operations_health.py \
  --stale-minutes 30 \
  --submit-grace-minutes 5 \
  --recent-hours 24
```

Core business API gate:

```bash
backend/.venv/bin/python backend/scripts/patrol_business_api.py \
  --base-url http://127.0.0.1:8099 \
  --mode route \
  --business all
```

真实出图闭环必须单独执行，不能只看路由预览。巡检脚本会先检查样例图 URL；手动执行前也建议先确认 HTTP 200，避免失效 OSS 链接误报为能力失败：

```bash
PATROL_IMAGE_URL="https://podiaidesign.oss-cn-hangzhou.aliyuncs.com/test/abilities/98904c502d9d4dd78432ec2bd1f79def/20260424/228be55f-1777009905.jpg"
curl -fsSI "$PATROL_IMAGE_URL"

backend/.venv/bin/python backend/scripts/patrol_business_api.py \
  --base-url http://127.0.0.1:8099 \
  --mode live \
  --business pattern_extract,fission,outpaint \
  --image-url "$PATROL_IMAGE_URL" \
  --timeout 1200 \
  --interval 10 \
  --require-executor-evidence
```

若这轮真实巡检准备用作发布验收依据，并且当前账号/服务令牌具备管理权限，可以在同一轮通过后自动写入业务版本验收记录：

```bash
backend/.venv/bin/python backend/scripts/patrol_business_api.py \
  --base-url http://127.0.0.1:8099 \
  --token "$SERVICE_API_TOKEN" \
  --mode live \
  --business pattern_extract,fission,outpaint \
  --image-url "$PATROL_IMAGE_URL" \
  --timeout 1200 \
  --interval 10 \
  --require-executor-evidence \
  --record-acceptance \
  --acceptance-note "发布前真实业务巡检通过：业务链路、执行节点证据、OSS 结果回填均正常。"
```

注意：`--record-acceptance` 只允许在 `--mode live` 下使用，并且只有所有被选中的业务都通过后才会写入；任一业务失败时不会写入部分验收，避免把不完整结果误当成上线依据。

若这轮巡检还要沉淀到管理端“发版巡检记录”，加上 `--report` 与 `--record-release-patrol`。脚本会写出 JSON 报告，并把本轮结果写入 `/api/admin/dashboard/release-patrol/records`；命令记录会自动隐藏 `--token` 的值。

```bash
backend/.venv/bin/python backend/scripts/patrol_business_api.py \
  --base-url http://127.0.0.1:8099 \
  --token "$SERVICE_API_TOKEN" \
  --mode live \
  --business pattern_extract,fission,outpaint \
  --image-url "$PATROL_IMAGE_URL" \
  --timeout 1200 \
  --interval 10 \
  --require-executor-evidence \
  --record-acceptance \
  --report "reports/business_patrol_$(date +%Y%m%d_%H%M%S).json" \
  --record-release-patrol \
  --release-patrol-note "发布前真实业务巡检完成，已沉淀到总览发版巡检记录。"
```

Expected:

- `health` passes.
- `coze_openapi` passes and shows the address Coze uses.
- `internal_tasks_get` returns `404 TASK_NOT_FOUND`, not `401 INTERNAL_ONLY`.
- `comfyui_queue_summary` returns all active ComfyUI executors and does not report `unsupportedServers` or `backendBlockedServers`.
- `comfyui_workflow_compatibility` returns all active ComfyUI workflows as compatible on their routed executors. By default, both `failedCount>0` and `warningCount>0` block release; only use `--allow-comfyui-compat-warnings` for an explicit temporary exception.
- `eval_workflow_catalog` returns a non-empty public catalog, includes at least one `production` workflow, does not leak `legacy/auxiliary/disabled` roles, has no duplicate workflow IDs, and does not exceed 2 production entries in one business category.
- `business_route_pattern_extract / business_route_fission / business_route_outpaint` each select a valid business capability without submitting real image-generation tasks.
- `business_capability_governance` must show active default versions for pattern extract, fission, and outpaint, with no bottom-layer blocker, no governance warning by default, and a latest `passed` acceptance record. If a known warning is intentionally carried, raise `--max-business-governance-warnings` for that run and record the reason. Missing acceptance is not a warning; it blocks release.
- `commercial_report` must return the current billing report schema and no billing issue by default. If a release intentionally carries known billing exceptions, raise `--max-billing-issues` or `--max-unpriced-billing-runs` only for that run and document the reason.
- `auth_scope_summary` must show at least one active admin account, no blocking auth risk, business API permission boundary policies enforced, and role boundaries for admin/client/service token/Coze toolbox present. If this fails, the management console may be impossible to operate after release or business accounts may bypass isolation.
- `check_eval_operations_health.py` returns `healthy` or only an accepted `warning`; `critical` blocks release. `EVAL_NO_RECENT_RUNS` means patrol did not run recently, and `EVAL_NO_RECENT_SUCCESS` means the recent business chain has no successful sample.
- `check_eval_operations_health.py` prints the real concurrency snapshot; if ComfyUI queue capacity is 20 but `evalFanoutMaxWorkers=1`, a single fission run is intentionally sequential and must not be treated as a GPU capacity issue without running `comfyui_capacity_probe.py`.
- `COMFYUI_EXECUTOR_UNREACHABLE` is not ignored: either restore the executor service or explicitly mark the executor offline before release.
- `patrol_business_api.py --mode live` must show all three core businesses succeeded with output and executor evidence. If executor evidence is missing, the backend is not surfacing enough routing proof for release acceptance.
- After a ComfyUI machine restart, run the no-cost node health check before sending real jobs:
  ```bash
  python3 backend/scripts/check_comfyui_node_health.py \
    --backend-url http://127.0.0.1:8099 \
    --report "reports/comfyui-node-health_$(date +%Y%m%d_%H%M%S).json"
  ```
  This checks each executor's `/system_stats`, `/queue`, `/object_info`, and the backend `queue-summary`. It must pass before treating the node as available for production traffic.

The management console button **总览 -> 发布前门禁 -> 运行轻量门禁** calls `/api/admin/dashboard/release-preflight/run` and must surface the same core blockers:

- `business_capability_governance`
- `auth_scope_summary`
- `internal_tasks_get`
- `comfyui_queue_summary`

If the page does not show these items, treat the backend as not updated enough for release acceptance.

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
   - On the 114 Coze host, run the container-level smoke check:
     ```bash
     cd /srv/pod
     BACKEND_URL=http://114.55.0.56:8099 \
       bash scripts/smoke_coze_container_backend.sh
     ```
     This check must show:
     - Coze container reads backend OpenAPI: `200`
     - Coze container reaches `tasks/get`: `404 TASK_NOT_FOUND`
     - Optional external boundary check from a non-whitelisted machine:
       `EXPECT_EXTERNAL_BLOCKED=1 BACKEND_URL=http://114.55.0.56:8099 bash scripts/smoke_coze_container_backend.sh`
4. Full eval patrol:
   ```bash
   python3 backend/scripts/patrol_eval_workflows.py \
     --base-url http://<backend-host>:8099 \
     --role production \
     --max-in-flight 1 \
     --timeout 1800
   ```
   Expected: all production entry workflows end in `succeeded`, and each succeeded run has at least one result image or structured output.
   Video and text/VL workflows are valid outputs too; patrol reports each item `outputKind` plus `outputKindSummary` as `image/video/text/structured/none` and should not fail them simply because `imageCount=0`.
   Failure examples: `INTERNAL_ONLY`, `COZE_WORKFLOW_ERROR`, `EVAL_SUCCEEDED_WITHOUT_OUTPUT`.
   This is a periodic self-check, not a load test. It must stay throttled to avoid filling ComfyUI queues by itself.
   If a full catalog sweep is needed, run it manually with `--role all` and keep `--max-in-flight` low unless queue capacity has just been verified.

   On the 114 production host, use the backend virtualenv instead of system Python:
   ```bash
   cd /srv/pod
   backend/.venv/bin/python backend/scripts/patrol_eval_workflows.py \
     --base-url http://127.0.0.1:8099 \
     --role production \
     --max-in-flight 1 \
     --timeout 1800
   ```
   Do not use `/usr/bin/python3` on 114; it is too old for the backend scripts.
5. Eval operations health:
   ```bash
   backend/.venv/bin/python backend/scripts/check_eval_operations_health.py
   ```
   Expected: no stale running runs, no submit-stalled runs, no succeeded-without-output records, and no active ComfyUI executor with unreadable queue.
6. ComfyUI queue visibility:
   ```bash
   backend/.venv/bin/python backend/scripts/comfyui_capacity_probe.py
   ```
   Expected: all active ComfyUI executors return queue counts.
   When submitting real capacity tasks with `--count`, the script now checks the sample image URL before enqueueing. A bad sample image is a preflight failure, not a ComfyUI capacity result.

Optional timers for 114 after manual confirmation:

```bash
cd /srv/pod
sudo scripts/install_eval_health_watch.sh
sudo scripts/install_business_health_watch.sh
```

Business health watch includes two layers:

- `podi-business-health-watch.timer`: every 15 minutes; checks release smoke, core business route preview, ComfyUI queue visibility, and recent eval operations health. It does not submit image-generation jobs.
- `podi-business-live-patrol.timer`: daily around 08:30; submits real single-concurrency patrols for pattern extract, fission, outpaint, and production eval workflows.

View the latest checks:

```bash
journalctl -u podi-eval-health-watch.service -n 80 --no-pager
journalctl -u podi-business-health-watch.service -n 120 --no-pager
journalctl -u podi-business-live-patrol.service -n 160 --no-pager
```

Rollback drill for business versions:

```bash
backend/.venv/bin/python backend/scripts/business_version_safety_audit.py
backend/.venv/bin/python backend/scripts/business_rollback_drill.py --business-key fission
backend/.venv/bin/python backend/scripts/business_rollback_drill.py --business-key outpaint
```

The safety audit verifies each core business has one active default version and at least one active non-default rollback target. The drill is read-only by default. Actual rollback requires `--apply --yes` and must not be used as a routine smoke check.

Timer exit code rule: `0=healthy`, `1=warning and systemd still treats it as completed`, `2=critical and systemd marks the unit failed`. The business live patrol is stricter: any failed real business chain should be treated as a release/operations blocker until classified.

If any of the above fails, do not continue with frontend/admin acceptance.

## 0.1) Release Source of Truth (Must Check First)

Before any server update, verify the release target from `origin/main` instead of a local dirty workspace.

Required checks:

1. Confirm target commit is already in `origin/main`.
2. Confirm the release source tree is clean.
3. Confirm Alembic migration files are a single valid chain.
4. Confirm the package does not contain macOS `._*` AppleDouble files.

Recommended command before packaging:

```bash
bash scripts/release_source_preflight.sh
```

If the package is being tested from a temporary worktree with intentional uncommitted
changes, use this only for local development validation, not for a formal release:

```bash
ALLOW_DIRTY=1 CHECK_GIT_SYNC=0 bash scripts/release_source_preflight.sh
```

On the production host, if the backend code has already been copied and the production
`.env` is present, also validate that the database's current Alembic revision exists
in the deployed code before running `alembic upgrade head`:

```bash
cd /srv/pod
CHECK_GIT_SYNC=0 CHECK_DB_CURRENT=1 bash scripts/release_source_preflight.sh
```

When packaging from macOS, disable AppleDouble metadata and exclude any existing
`._*` files:

```bash
COPYFILE_DISABLE=1 tar --exclude='._*' -czf /tmp/pod_release.tgz \
  backend scripts docs config podi-admin-web podi-eval-web
```

Do **not** use the following as the release signal by itself:

- “local branch has the code”
- “someone said it was updated”
- “current workspace can see the commit”
- “there is only one listening process on the port”
- “Alembic upgrade failed but the service can still start”

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
  --min-used-executors 2 \
  --min-peak-queue-total 8 \
  --min-successful-tasks 12 \
  --yes
```

Expected:

- queue snapshots show running/pending counts changing during the probe.
- task summary shows which executor each task used.
- report summary includes peak queue, peak running, peak pending, and per-executor peak queue counts.
- if `--min-*` thresholds are set, the script exits non-zero when observed queue/utilization does not meet expectation.
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
