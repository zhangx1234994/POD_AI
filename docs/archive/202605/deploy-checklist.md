状态: archived
归档原因: 旧部署检查清单已被统一发布 SOP 覆盖。
替代文档: docs/standards/release-sop.md

# 部署检查清单（Server / 无 Docker）

> 版本：2026-02-03  
> 目标：避免“部署后才发现 502/登录失败”的问题。

> 现行 114 控制面发布优先使用 `docs/standards/release-sop.md` 和 `scripts/release_114_control_plane.sh`。本文作为底层检查清单和手工排障参考。

## 0) 推荐一键发布

```bash
bash scripts/release_114_control_plane.sh
```

如本机没有 SSH key，可临时使用：

```bash
SSHPASS='<SSH 密码>' bash scripts/release_114_control_plane.sh
```

## 1) 部署前确认

- [ ] 发版源已通过检查：`bash scripts/release_source_preflight.sh`
- [ ] 后端环境变量已更新（`backend/.env`）
- [ ] 如果是在 114 的 `/srv/pod` 已复制代码后执行迁移，先跑：`CHECK_GIT_SYNC=0 CHECK_DB_CURRENT=1 bash scripts/release_source_preflight.sh`
- [ ] 端口约定固定：8099 / 8199 / 8200；如启用第三方 API 执行面，额外开放 8310
- [ ] 若使用 Nginx 反代：`proxy_pass` 指向 `127.0.0.1:8099`
- [ ] 只有改到 `image-ops-service`、ComfyUI 工作流执行服务或 117 本机配置时，才需要更新 117；普通 backend/admin/eval 发版只更新 114

## 2) 服务启动顺序

1. 后端（FastAPI）  
2. 管理端静态站点（8199）  
3. 评测端静态站点（8200）
4. 第三方 API 执行面 vendor-api-ops（8310，按需）

## 3) 一键预检查（必须执行）

```bash
BACKEND_URL=http://127.0.0.1:8099 \
ADMIN_URL=http://127.0.0.1:8199 \
EVAL_URL=http://127.0.0.1:8200 \
bash scripts/deploy_preflight.sh
```

如需发版前附带状态/错误专项回归（推荐夜间窗口）：

```bash
BACKEND_URL=http://127.0.0.1:8099 \
ADMIN_URL=http://127.0.0.1:8199 \
EVAL_URL=http://127.0.0.1:8200 \
RUN_STATUS_ERROR_CHECKS=1 \
bash scripts/deploy_preflight.sh
```

通过标准：
- 后端 `/health` 返回 200
- 管理端 `/api/admin/workflows` 不是 502（允许 401）
- 评测 `/api/evals/workflow-versions` 返回 200 或 404

## 4) 手工补丁包打包

如果需要从本地临时打补丁到 114，不再直接使用系统 `tar`。统一使用下面脚本，避免 macOS 扩展属性、`.DS_Store` 和服务器时间差造成的解包警告：

```bash
python3 scripts/package_release_archive.py \
  --output /tmp/pod_patch_<commit>.tgz \
  backend/app/services/example.py \
  docs/strategy/todo-master-2026q2.md
```

前端静态产物需要只打包 `dist` 目录内容时：

```bash
npm run build
python3 ../scripts/package_release_archive.py \
  --root dist \
  --output /tmp/podi_eval_dist_<commit>.tgz \
  .
```

服务器解包仍使用：

```bash
tar --no-same-owner -xzf /tmp/pod_patch_<commit>.tgz -C /srv/pod
```

## 5) 常见失败定位

- 502：**管理端反代未指向后端**（Nginx 配置错误）
- 401：token 失效（登录即可）
- 404：评测端公开接口未开启（`EVAL_PUBLIC_ENABLED` 关闭）

## 6) 最终确认

- [ ] 管理端能登录
- [ ] 能力列表可加载
- [ ] 评测端文档页可打开
