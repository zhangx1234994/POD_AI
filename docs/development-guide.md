# POD AI Studio 开发指南（精简版）

本仓库当前以 “后端 + 管理端 + 评测站点” 为主：

- `backend/`：FastAPI + Celery（端口默认 `8099`）
- `podi-admin-web/`：管理端（端口默认 `8199`）
- `podi-eval-web/`：能力评测站点（端口默认 `8200`）

## 固定端口（铁律）

以下端口为 **固定约定**，不得随意更改：

- 后端：`8099`
- 管理端：`8199`
- 评测端：`8200`

如端口被占用，先清理旧进程再启动，避免临时改端口导致配置混乱。

历史客户端 `podi-design-web-dev/` 已移除，后续将以新的客户端形态重构。

## 1) 后端启动

```bash
cd backend
uv sync   # 或 pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8099
```

（可选）Celery worker：

```bash
cd backend
celery -A app.core.celery_app worker -l info
```

健康检查：

```bash
curl :8099/health
```

## 2) 管理端启动

```bash
cd podi-admin-web
npm install
npm run dev -- --port 8199
```

类型检查：

```bash
cd podi-admin-web
npm run lint
```

## 3) 评测站点启动

```bash
cd podi-eval-web
npm install
npm run dev -- --port 8200
```

## 4) 常见问题

端口占用优先清理旧进程再重启服务：

```bash
lsof -i tcp:<port>
kill <pid>
```
