# 部署（Prod-like，开发机/线上一致）

目标：让“开发机所见即所得”，线上部署只需要 `git pull` + 一条命令，不再出现 `npm run dev` 造成的样式/资源错配。

## 端口约定
- 后端 API：`8099`
- 管理端（静态）：`8199`
- 测评端（静态）：`8200`

## 前置条件
- 服务器已安装 Docker + Docker Compose（`docker compose version` 可用）
- 云端 MySQL 可访问（后端使用 `backend/.env` 中的 `DATABASE_URL`）

## 一次性准备
1) 配置后端环境变量文件（线上/开发机都一致）
- 复制：`backend/.env.example` → `backend/.env`
- 至少填写：`DATABASE_URL`，其余按需要补齐（OSS / Coze / Key 等）

2) （可选）检查执行节点配置
- 默认读取 `config/executors.yaml`
- YAML 内允许 `${ENV}`，会从 `backend/.env` 解析

## 一键部署（推荐）
在仓库根目录执行：
```bash
bash scripts/deploy_prodlike.sh
```

脚本会：
- 构建镜像（后端 + 两个前端）
- 启动容器（端口保持一致）
- 后端启动前自动执行 `alembic upgrade head`
- 最后用 `/health` 做健康检查

## 日志与排查
```bash
docker compose -f docker-compose.prodlike.yml ps
docker compose -f docker-compose.prodlike.yml logs -f backend
docker compose -f docker-compose.prodlike.yml logs -f admin-web
docker compose -f docker-compose.prodlike.yml logs -f eval-web
```

## 常见坑（务必避免）
- 线上不要用 `npm run dev`：Vite dev server 会引入 websocket/HMR，且容易因缓存/代理导致“样式乱、资源错配”。
- 迁移必须跑：新字段/表未迁移会导致管理端接口 500/502。

## API 访问方式（保持开发机/线上一致）
- 管理端页面：`http://<host>:8199/`
- 测评端页面：`http://<host>:8200/`
- 两个前端都通过同源代理访问后端：`/api/*` → `backend:8099`
  - 好处：不依赖 `VITE_API_BASE_URL`，避免“线上/开发机域名不同导致接口地址漂移”。
