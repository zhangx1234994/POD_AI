# PODI 发布 SOP（唯一执行入口）

本 SOP 固化 114 控制面发布流程，目标是减少每次上线的手工尝试、网络等待和漏检。除非明确标记为紧急修复，否则所有 backend / 管理端 / 测评端上线都按本文执行。

## 1. 发布原则

- **origin/main 是正式发版真源**：正式上线前必须确认本地 `HEAD` 与 `origin/main` 一致。
- **114 只承载控制面**：backend、管理端静态产物、测评端静态产物部署到 114；ComfyUI、image-ops、vendor-api-ops 只在对应能力机更新。
- **前端只部署 build 产物**：8199/8200 禁止长期跑 Vite dev。
- **先验证再切流**：上线成功不等于验收成功，必须跑健康检查、发布 smoke 和必要业务巡检。
- **失败先回滚入口，再排查新环境**：不要在线上半更新状态边跑边修。
- **每次事故都反哺 SOP**：上线过程中新增的真实问题，必须同步到 `docs/standards/issue-improvement-log.md`。

## 2. 标准发布命令

在本地仓库根目录执行：

```bash
SSHPASS='<临时或本机环境里的 SSH 密码>' \
bash scripts/release_114_control_plane.sh
```

推荐使用 SSH key，这样不需要 `SSHPASS`。脚本默认发布：

- `backend/`
- `docs/`
- `scripts/`
- `deploy/`
- `podi-admin-web/dist`
- `podi-eval-web/dist`

脚本默认会执行：

1. 发版源检查：`scripts/release_source_preflight.sh`
2. 后端关键测试：业务 API、任务归属、发布 smoke、打包脚本
3. 管理端和测评端 `npm run lint`
4. 管理端和测评端 `npm run build`
5. 生成干净发布包，去掉 `.venv`、`.env`、`node_modules`、`._*`、`.DS_Store`
6. 上传到 114 的 `/srv/pod/.deploy_tmp/<commit>/`
7. 保留线上 `backend/.env` 和 `backend/.venv`
8. 远端执行 `alembic upgrade head`
9. 重启 `podi-backend`、`podi-admin-web`、`podi-eval-web`
10. 写入 `/srv/pod/DEPLOYED_COMMIT`、`.release_commit`、`.release_time`
11. 执行远端健康检查、`scripts/deploy_preflight.sh` 和 `podi_release_smoke.py`

## 3. 常用参数

| 参数 | 默认 | 用途 |
| --- | --- | --- |
| `TARGET_HOST` | `114.55.0.56` | 发布目标机器 |
| `TARGET_USER` | `root` | SSH 用户 |
| `TARGET_ROOT` | `/srv/pod` | 线上部署目录 |
| `RUN_SOURCE_PREFLIGHT` | `1` | 是否确认 `origin/main`、迁移链、脏文件 |
| `RUN_TESTS` | `1` | 是否跑后端关键测试 |
| `RUN_FRONTEND_LINT` | `1` | 是否跑管理端/测评端类型检查 |
| `RUN_FRONTEND_BUILD` | `1` | 是否重新构建前端 |
| `RUN_SMOKE` | `1` | 是否跑远端发布 smoke |
| `RUN_LIVE_PATROL` | `0` | 是否跑真实业务出图巡检 |
| `INSTALL_DEPS` | `auto` | 依赖变更时设为 `1` |
| `SMOKE_ALLOW_COMFYUI_WARNINGS` | `0` | 临时接受 ComfyUI 兼容 warning，必须记录原因 |

示例：只做控制面发布，不跑真实出图：

```bash
bash scripts/release_114_control_plane.sh
```

示例：依赖变更后发布：

```bash
INSTALL_DEPS=1 bash scripts/release_114_control_plane.sh
```

示例：上线前带真实业务巡检：

```bash
RUN_LIVE_PATROL=1 bash scripts/release_114_control_plane.sh
```

## 4. 发布前门禁

脚本执行前必须满足：

- 本地工作区干净。
- 最近提交已推到 `origin/main`。
- 需要上线的前后端改动已经完成本地自测。
- 若修改接口参数、状态、错误码，已同步：
  - `docs/api/INDEX.md` 或对应模块文档
  - `docs/standards/error-catalog.md`
  - 测评端文案或管理端页面
- 若修改数据库迁移，`alembic heads` 只有一个 head。

阻断发布的情况：

- GitHub 不可达且无法确认 `origin/main`。
- 工作区有未提交改动。
- Alembic 当前库版本不在代码迁移链中。
- 后端关键测试、前端构建、远端 health 任一失败。
- `tasks/get` 出现 `401 INTERNAL_ONLY`。
- 核心业务默认版本缺失或无可执行配方。
- 成功任务没有 OSS 回填或缺执行节点证据。

## 5. 线上验证

发布脚本会自动跑轻量验证。需要人工复核时，使用：

```bash
ssh root@114.55.0.56
cd /srv/pod
cat DEPLOYED_COMMIT
curl -fsS http://127.0.0.1:8099/health
BACKEND_URL=http://127.0.0.1:8099 \
ADMIN_URL=http://127.0.0.1:8199 \
EVAL_URL=http://127.0.0.1:8200 \
bash scripts/deploy_preflight.sh
backend/.venv/bin/python backend/scripts/podi_release_smoke.py \
  --base-url http://127.0.0.1:8099
```

业务闭环验证：

```bash
backend/.venv/bin/python backend/scripts/patrol_business_api.py \
  --base-url http://127.0.0.1:8099 \
  --mode live \
  --business pattern_extract,fission,outpaint \
  --image-url "$PATROL_IMAGE_URL" \
  --timeout 1200 \
  --interval 10 \
  --require-executor-evidence
```

测评端生产入口巡检：

```bash
backend/.venv/bin/python backend/scripts/patrol_eval_workflows.py \
  --base-url http://127.0.0.1:8099 \
  --role production \
  --max-in-flight 1 \
  --timeout 1800
```

## 6. 117 / 233 / vendor-api-ops 更新边界

普通 backend、管理端、测评端改动只更新 114。

只有以下情况才更新能力机：

- 修改 `image-ops-service/`
- 修改 `vendor-api-ops/`
- 修改 ComfyUI 执行服务、模型文件、节点依赖或 workflow 执行包
- 明确要同步 158/233 的能力配置

更新能力机后必须回到 114 跑：

```bash
backend/.venv/bin/python backend/scripts/check_comfyui_node_health.py \
  --backend-url http://127.0.0.1:8099
backend/.venv/bin/python backend/scripts/patrol_business_api.py \
  --base-url http://127.0.0.1:8099 \
  --mode route \
  --business all
```

## 7. 失败处理

| 失败点 | 处理方式 |
| --- | --- |
| GitHub push/fetch 超时 | 不进入正式发布；网络恢复后重试。紧急发布必须口头确认并在复盘记录原因。 |
| 本地测试失败 | 停止发布，先修代码。 |
| 前端 build 失败 | 停止发布，不能用 dev server 顶替。 |
| `alembic upgrade head` 失败 | 不重启服务；先确认迁移链和生产当前 revision。 |
| 服务重启失败 | 先 `systemctl status` 和 `journalctl` 定位；必要时恢复上一版目录。 |
| smoke 失败 | 保持服务不扩流；按失败项处理，不能把 health 通过当作上线成功。 |
| 真实业务巡检失败 | 不交业务验收；确认是样例图、执行节点、OSS、回填还是业务配方问题。 |

## 8. 回滚口径

优先级：

1. 如果只是 Coze 工具箱错误，先恢复工具箱指向或插件版本。
2. 如果 backend 新版错误，恢复上一版代码目录并重启 `podi-backend`。
3. 如果前端新版错误，恢复上一版 `dist` 并重启对应静态服务。
4. 不做 destructive 数据库回滚；数据库只保留并修 forward migration。

回滚后仍要跑：

```bash
curl -fsS http://127.0.0.1:8099/health
bash scripts/deploy_preflight.sh
```

## 9. 发布记录

每次发布后记录最少字段：

```text
时间：
commit：
范围：backend/admin/eval/能力机
是否更新 117/233：
发布脚本结果：
smoke 结果：
真实业务巡检结果：
已知风险：
是否允许业务验收：
```

推荐沉淀到：

- `reports/releases/YYYYMMDD-HHMM-<commit>.md`
- `docs/standards/issue-improvement-log.md`（只有真实问题和改进项才写）

## 10. 本次 SOP 改进结论

2026-05-12 这轮暴露的主要问题：

- 手工 tar/ssh/restart 步骤过多，容易重复尝试。
- GitHub 网络不稳定时，push 等待没有明确超时和决策口径。
- 文档、OpenAPI、前端接入说明分散，容易修了代码但页面还不清楚。
- health 通过不等于业务闭环通过，必须固定 smoke 和业务巡检。

对应固化：

- 使用 `scripts/release_114_control_plane.sh` 作为 114 发布入口。
- `scripts/package_release_archive.py` 默认排除本地环境和 macOS 垃圾文件。
- 发布前后都以 commit 文件和 smoke 结果确认，不再靠“页面看起来变了”判断。
