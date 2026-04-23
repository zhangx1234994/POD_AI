# Coze 主机迁移命令清单 v1

> 用途：迁移当天直接照着执行。  
> 约束：不在命令窗口临时决定目录、服务名、env 文件位置。

## 1. 目录假设

以下命令都基于：

```text
/srv/pod
```

## 2. backend

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

## 6. bundle 联调

```bash
cd /srv/pod
BACKEND_URL=http://127.0.0.1:8099 \
ADMIN_URL=http://127.0.0.1:8199 \
EVAL_URL=http://127.0.0.1:8200 \
IMAGE_OPS_URL=http://127.0.0.1:8301 \
bash scripts/check_coze_control_plane_bundle.sh
```

## 6.1 image-ops 真链路 smoke

```bash
cd /srv/pod
BACKEND_URL=http://127.0.0.1:8099 \
SERVICE_API_TOKEN="<service_api_token>" \
python3 scripts/smoke_image_ops_via_backend.py
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
