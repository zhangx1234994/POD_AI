# 部署（Prod-like，开发机/线上一致）

目标：让“开发机所见即所得”，线上部署只需要 `git pull` + 一条命令，不再出现 `npm run dev` 造成的样式/资源错配。

## 端口约定
- 后端 API：`8099`
- 管理端（静态）：`8199`
- 测评端（静态）：`8200`
- 第三方 API 执行面（vendor-api-ops，按需）：`8310`

> **固定端口（铁律）**：上述端口为统一约定，不要临时改动；若端口冲突，请先清理旧进程。

## 前置条件
- 云端 MySQL 可访问（后端使用 `backend/.env` 中的 `DATABASE_URL`）
- 如需服务器本地构建前端：已安装 Node.js（建议 18+）与 npm
- **无 Docker 场景优先**（云服务器常为虚拟化环境，无法安装 Docker）
- 若本次部署为 Coze 控制面迁移：
  - backend 与 Coze 同机
  - ComfyUI/高清放大继续外置
  - `DISABLE_LOCAL_HEAVY_IMAGE_TASKS=true`

## 一次性准备
1) 配置后端环境变量文件（线上/开发机都一致）
- 复制：`backend/.env.example` → `backend/.env`
- 至少填写：`DATABASE_URL`，其余按需要补齐（OSS / Coze / Key 等）

2) （可选）检查执行节点配置
- 默认读取 `config/executors.yaml`
- YAML 内允许 `${ENV}`，会从 `backend/.env` 解析
- `vendor-api-ops` 默认指向 `http://117.50.80.158:8310`；如迁移到其他机器，修改 `backend/.env` 的 `VENDOR_API_BASE_URL` 即可。

## 前端构建依赖（仅服务器本地构建时需要）
如果你选择在服务器上构建前端，请确保：
- Node.js 版本：**18+（建议 LTS）**
- npm 版本：**9+**

构建命令：
```bash
cd podi-admin-web && npm install && npm run build
cd podi-eval-web && npm install && npm run build
```
构建完成后将 `dist/` 作为静态产物发布（配合反代到 `/api`）。

## 一键部署（Docker 可用时）
在仓库根目录执行：
```bash
bash scripts/deploy_prodlike.sh
```

脚本会：
- 构建镜像（后端 + 两个前端）
- 启动容器（端口保持一致）
- 后端启动前自动执行 `alembic upgrade head`
- 最后用 `/health` 做健康检查

### image-ops（独立图片原子能力服务）

如果本次迁移已启用 `image-ops`，可单独使用：

```bash
docker compose -f docker-compose.image-ops.yml build --pull
docker compose -f docker-compose.image-ops.yml up -d
```

端口：
- `8301` image-ops，仅绑定 `127.0.0.1`

## 无 Docker（推荐）
如果服务器没有 Docker，可以用“prod-like（无 docker）”脚本，效果同样是：
- 前端不跑 `npm run dev`，使用静态构建产物 + 同源 `/api` 反代（Node 内置小代理）
- 后端启动前自动跑迁移

```bash
bash scripts/deploy_prodlike_nodocker.sh
```

端口保持一致：
- `8099` 后端
- `8199` 管理端
- `8200` 测评端
- `8310` vendor-api-ops（仅启用第三方 API 执行面时需要）

### image-ops（无 Docker 兜底）

若不用 systemd，也可直接使用仓库脚本启动：

```bash
bash scripts/prodlike_restart_image_ops.sh
```

端口：
- `8301` image-ops，仅绑定 `127.0.0.1`

## 部署检查清单（必须执行）

见：`docs/deploy-checklist.md`

如果本次为 Coze 控制面迁移，建议额外执行：

```bash
bash scripts/check_coze_control_plane_bundle.sh
```

## 日志与排查
```bash
docker compose -f docker-compose.prodlike.yml ps
docker compose -f docker-compose.prodlike.yml logs -f backend
docker compose -f docker-compose.prodlike.yml logs -f admin-web
docker compose -f docker-compose.prodlike.yml logs -f eval-web
docker compose -f docker-compose.image-ops.yml logs -f image-ops
```

## 常见坑（务必避免）
- 线上不要用 `npm run dev`：Vite dev server 会引入 websocket/HMR，且容易因缓存/代理导致“样式乱、资源错配”。
- 迁移必须跑：新字段/表未迁移会导致管理端接口 500/502。
- Coze 迁移后不要让 toolbox 直接指向 ComfyUI；Coze 只调 backend。

## API 访问方式（保持开发机/线上一致）
- 管理端页面：`http://<host>:8199/`
- 测评端页面：`http://<host>:8200/`
- 两个前端都通过同源代理访问后端：`/api/*` → `backend:8099`
  - 好处：不依赖 `VITE_API_BASE_URL`，避免“线上/开发机域名不同导致接口地址漂移”。
