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

## 2) 测评端/管理端 “样式错乱 / 页面结构乱”
这是最常见的“静态资源版本不一致”问题（index.html 缓存 + assets hash）。

检查浏览器 Network：
- `index.html` 必须 `no-store`
- `assets/*.js|css` 应该 200/304，不应 404

本仓库的 nginx 配置已做到：
- `/index.html`：`Cache-Control: no-store`
- `/assets/*`：`max-age=31536000, immutable`

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

