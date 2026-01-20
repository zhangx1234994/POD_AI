# 生产环境部署（PODI 后端/管理端）

目标：Coze 部署在 A 服务器，PODI（后端 + 管理端）部署在 B 服务器。对外只暴露管理端（以及必要的 PODI API）。

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
- `VOLCENGINE_API_KEY` / `KIE_API_KEY` / `BAIDU_API_KEY` / `BAIDU_SECRET_KEY`
- `PODI_INTERNAL_BASE_URL`（Coze 导入 OpenAPI 用；Coze 在另一台机器时必须能访问到 PODI）

## 3. 启动后端（FastAPI）

```bash
cd backend
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
./.venv/bin/alembic upgrade head
./.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8099
```

## 4. Coze 导入插件

在 Coze 服务器上导入 OpenAPI：

`http://<PODI_HOST_OR_DOMAIN>:8099/api/coze/podi/openapi.json`

说明：
- 不要用 `host.docker.internal`（那是同机容器访问宿主机的域名）。
- 生产建议开启 `SERVICE_API_TOKEN`，并让 Coze 侧统一带 `Authorization: Bearer <token>`。

