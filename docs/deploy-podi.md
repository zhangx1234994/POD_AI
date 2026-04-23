# 生产环境部署（Coze 同机 backend 控制面）

目标：Coze 和 backend 部署在同一台控制面服务器；ComfyUI/高清放大继续作为外部执行节点存在。

## 1. 拉代码

```bash
git clone --recurse-submodules https://github.com/zhangx1234994/POD_AI.git
cd POD_AI
```

## 2. 生成后端配置（推荐：一条命令）

为了避免把密钥提交到 Git，我们用脚本在服务器本地生成 `backend/.env`：

```bash
bash scripts/prod_write_backend_env.sh
```

最少需要填写：
- `DATABASE_URL`

可选：
- `SERVICE_API_TOKEN`（推荐：Coze → PODI 走固定 token）
- `COZE_TRUSTED_IPS`（当 Coze 与 backend 不在同一台机器时必填）
- `VOLCENGINE_API_KEY` / `KIE_API_KEY` / `BAIDU_API_KEY` / `BAIDU_SECRET_KEY`
- `PODI_INTERNAL_BASE_URL`（容器或反代内部调用 backend 用）
- `DISABLE_LOCAL_HEAVY_IMAGE_TASKS=true`（迁移到 Coze 主机时建议默认开启，避免本机跑高清放大）

## 3. 启动后端（FastAPI）

```bash
cd backend
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
./.venv/bin/alembic upgrade head
./.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8099
```

## 4. Coze 导入插件

在 Coze 侧导入 OpenAPI：

`http://<PODI_HOST_OR_DOMAIN>:8099/api/coze/podi/openapi.json`

说明：
- 生产环境不要用 `host.docker.internal`。
- 生产建议开启 `SERVICE_API_TOKEN`，并让 Coze 侧统一带 `Authorization: Bearer <token>`。
- toolbox 统一只指向 backend，不允许直连任何 ComfyUI 地址。
