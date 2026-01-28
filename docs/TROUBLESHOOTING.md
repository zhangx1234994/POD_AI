# 常见问题排查（部署/运行）

## 1) 管理端提示 “Bad Gateway / 部分数据加载失败”
先区分是网关 502 还是后端 401/500：

1) 后端是否存活
```bash
curl -i http://127.0.0.1:8099/health
```

2) 带 Token 访问管理端 API（从浏览器 localStorage 取 `podi_admin_access_token`）
```bash
curl -i -H "Authorization: Bearer <TOKEN>" http://127.0.0.1:8099/api/admin/dashboard/metrics
curl -i -H "Authorization: Bearer <TOKEN>" http://127.0.0.1:8099/api/admin/dashboard/logs
curl -i -H "Authorization: Bearer <TOKEN>" http://127.0.0.1:8099/api/admin/executors
```

- 若 127.0.0.1:8099 返回 200，但浏览器仍显示 502 → 代理/Nginx 配置或超时问题
- 若 500 → 看后端日志：`docker compose logs -f backend`
- 若 401/INVALID_TOKEN → 管理端 token 失效（重新登录；或清理浏览器 localStorage 里的 `podi_admin_access_token` / `podi_admin_refresh_token`）

## 2) 测评端/管理端 “样式错乱 / 页面结构乱”
这是最常见的“静态资源版本不一致”问题（index.html 缓存 + assets hash）。

检查浏览器 Network：
- `index.html` 必须 `no-store`
- `assets/*.js|css` 应该 200/304，不应 404

本仓库的 nginx 配置已做到：
- `/index.html`：`Cache-Control: no-store`
- `/assets/*`：`max-age=31536000, immutable`

补充说明：
- Chrome 控制台里出现 `Unchecked runtime.lastError: ...` 通常来自浏览器扩展（插件）而非站点自身，可忽略；
  以 Network 面板里的 XHR/Fetch 失败请求为准。

## 3) Unknown column / 表结构缺字段
说明迁移没跑：
```bash
cd backend
alembic upgrade head
```
在 Docker 模式下后端启动会自动执行迁移；如果失败，查看后端日志。

## 4) Coze 调用报 429 EXECUTOR_BUSY
这是后端的“执行节点并发闸门”保护：
- 说明命中的 executor 没有空闲并发位
处理方式：
1) 调大执行节点 `max_concurrency`（例如 KIE 从 2 提到 4）
2) 调用侧对 429 做指数退避重试（1s/2s/4s... + 抖动，3~5 次）

## 5) 评测/管理端 API 502（Bad Gateway）
优先定位“哪一跳坏了”：

1) 直接访问后端（绕过前端端口）
```bash
curl -i http://127.0.0.1:8099/health
curl -i "http://127.0.0.1:8099/api/evals/runs/with-latest-annotation?workflow_version_id=<id>&limit=50&offset=0"
```

2) 若后端 200 但前端 502：
- 使用 prod-like 静态托管（不要 `npm run dev`）
- 检查反代/同源代理进程是否存活（8199/8200）
