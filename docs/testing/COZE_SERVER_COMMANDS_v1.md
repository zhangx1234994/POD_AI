# Coze 主机迁移命令清单 v1

> 用途：迁移当天直接照着执行。  
> 约束：不在命令窗口临时决定目录、服务名、env 文件位置。

## 1. 目录假设

以下命令都基于：

```text
/srv/pod
```

并假设 Coze 主机已经可用：

```bash
python3.11
```

如果系统默认 `python3` 仍然是旧版本，迁移相关脚本统一显式带：

```bash
PYTHON_BIN=python3.11
```

## 2. backend

### 写入环境变量

```bash
cd /srv/pod
bash scripts/prod_write_backend_env.sh
```

### 安装目录

```bash
mkdir -p /srv/pod
cd /srv/pod
```

### 安装依赖

```bash
cd /srv/pod/backend
python3 -m venv .venv
./.venv/bin/pip install -U pip
./.venv/bin/pip install -e .
```

### 迁移

```bash
cd /srv/pod/backend
./.venv/bin/alembic upgrade head
```

### 安装 systemd

```bash
cp /srv/pod/deploy/systemd/podi-backend.service /etc/systemd/system/podi-backend.service
systemctl daemon-reload
systemctl enable podi-backend
systemctl restart podi-backend
systemctl status podi-backend
```

## 3. image-ops

### 写入环境变量

```bash
cd /srv/pod
bash scripts/prod_write_image_ops_env.sh
```

### 安装依赖

```bash
cd /srv/pod/image-ops-service
python3 -m pip install -U pip
python3 -m pip install .
```

### 安装 systemd

```bash
cp /srv/pod/image-ops-service/deploy/image-ops.service /etc/systemd/system/image-ops.service
systemctl daemon-reload
systemctl enable image-ops
systemctl restart image-ops
systemctl status image-ops
```

## 4. admin / eval

### 构建

```bash
cd /srv/pod/podi-admin-web
npm install
npm run build

cd /srv/pod/podi-eval-web
npm install
npm run build
```

### 安装 systemd

```bash
cp /srv/pod/deploy/systemd/podi-admin-web.service /etc/systemd/system/podi-admin-web.service
cp /srv/pod/deploy/systemd/podi-eval-web.service /etc/systemd/system/podi-eval-web.service
systemctl daemon-reload
systemctl enable podi-admin-web podi-eval-web
systemctl restart podi-admin-web podi-eval-web
systemctl status podi-admin-web
systemctl status podi-eval-web
```

## 5. 基础检查

```bash
curl http://127.0.0.1:8099/health
curl http://127.0.0.1:8301/health
curl http://127.0.0.1:8099/api/abilities
curl http://127.0.0.1:8099/api/evals/workflow-versions
```

## 5.1 迁移前基线采集

```bash
cd /srv/pod
BACKEND_URL=http://127.0.0.1:8099 \
ADMIN_URL=http://127.0.0.1:8199 \
EVAL_URL=http://127.0.0.1:8200 \
IMAGE_OPS_URL=http://127.0.0.1:8301 \
bash scripts/capture_coze_control_plane_baseline.sh
```

## 6. bundle 联调

```bash
cd /srv/pod
BACKEND_URL=http://127.0.0.1:8099 \
ADMIN_URL= \
EVAL_URL= \
IMAGE_OPS_URL=http://127.0.0.1:8301 \
PYTHON_BIN=/srv/pod/backend/.venv/bin/python \
bash scripts/check_coze_control_plane_bundle.sh
```

## 6.0 先看执行计划（推荐）

```bash
cd /srv/pod
DEPLOY_SCOPE=backend-image-ops \
PYTHON_BIN=python3.11 \
IMAGE_PATH="/srv/pod/testdata/sample.png" \
bash scripts/run_coze_control_plane_cutover.sh plan
```

## 6.1 一键执行（推荐）

### 首轮保守迁移：只动 backend + image-ops

```bash
cd /srv/pod
DEPLOY_SCOPE=backend-image-ops \
PYTHON_BIN=python3.11 \
IMAGE_PATH="/srv/pod/testdata/sample.png" \
POLL_SECONDS=90 \
bash scripts/run_coze_control_plane_cutover.sh full
```

### 同批带上 admin / eval

```bash
cd /srv/pod
DEPLOY_SCOPE=full \
PYTHON_BIN=python3.11 \
IMAGE_PATH="/srv/pod/testdata/sample.png" \
POLL_SECONDS=90 \
bash scripts/run_coze_control_plane_cutover.sh full
```

## 6.2 image-ops 真链路 smoke

```bash
cd /srv/pod
BACKEND_URL=http://127.0.0.1:8099 \
SERVICE_API_TOKEN="<service_api_token>" \
BACKEND_ENV_FILE=/srv/pod/backend/.env \
/srv/pod/backend/.venv/bin/python scripts/smoke_image_ops_via_backend.py
```

## 6.3 Coze 主工作流 smoke

```bash
cd /srv/pod
IMAGE_PATH="/srv/pod/testdata/sample.png" \
POLL_SECONDS=90 \
bash scripts/smoke_coze_primary_workflows.sh
```

## 6.4 回滚模板

```bash
cd /srv/pod
OLD_BACKEND_URL="http://117.50.80.158:8099" \
CONFIRM_TOOLBOX_ROLLBACK_DONE=1 \
bash scripts/rollback_coze_control_plane.sh
```

## 6.5 回滚后验证

```bash
cd /srv/pod
OLD_BACKEND_URL="http://117.50.80.158:8099" \
IMAGE_PATH="/srv/pod/testdata/sample.png" \
bash scripts/rollback_verify_coze_control_plane.sh
```

## 6.6 迁移前后基线对比

```bash
cd /srv/pod
python3 scripts/compare_coze_control_plane_baselines.py \
  --before runtime/baseline_before \
  --after runtime/baseline_after
```

## 7. 日志命令

```bash
journalctl -u podi-backend -f
journalctl -u image-ops -f
journalctl -u podi-admin-web -f
journalctl -u podi-eval-web -f
```

## 8. 最小结论

迁移当天只要服务名、目录、端口都按这份清单执行，就不会出现“目录对不上、服务名乱、日志找不到”的低级问题。
