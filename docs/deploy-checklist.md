# 部署检查清单（Server / 无 Docker）

> 版本：2026-02-03  
> 目标：避免“部署后才发现 502/登录失败”的问题。

## 1) 部署前确认

- [ ] 后端环境变量已更新（`backend/.env`）
- [ ] 端口约定固定：8099 / 8199 / 8200
- [ ] 若使用 Nginx 反代：`proxy_pass` 指向 `127.0.0.1:8099`

## 2) 服务启动顺序

1. 后端（FastAPI）  
2. 管理端静态站点（8199）  
3. 评测端静态站点（8200）

## 3) 一键预检查（必须执行）

```bash
BACKEND_URL=http://127.0.0.1:8099 \
ADMIN_URL=http://127.0.0.1:8199 \
EVAL_URL=http://127.0.0.1:8200 \
bash scripts/deploy_preflight.sh
```

通过标准：
- 后端 `/health` 返回 200
- 管理端 `/api/admin/workflows` 不是 502（允许 401）
- 评测 `/api/evals/workflow-versions` 返回 200 或 404

## 4) 常见失败定位

- 502：**管理端反代未指向后端**（Nginx 配置错误）
- 401：token 失效（登录即可）
- 404：评测端公开接口未开启（`EVAL_PUBLIC_ENABLED` 关闭）

## 5) 最终确认

- [ ] 管理端能登录
- [ ] 能力列表可加载
- [ ] 评测端文档页可打开

