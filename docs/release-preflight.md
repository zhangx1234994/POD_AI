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

From the PODI backend host (8099), confirm it can reach *each* ComfyUI executor baseUrl:

- `http://117.50.80.158:8079/`
- `http://117.50.216.233:8079/`

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

