# image-ops-service 部署说明

支持两种正式运行方式：

1. `systemd`
2. `docker`

## 方式一：systemd

目录建议：

- `/srv/pod/image-ops-service`

步骤：

1. 上传代码到目标目录
2. 准备 `.env`
3. 安装依赖：

```bash
cd /srv/pod/image-ops-service
python3.11 -m venv .venv
./.venv/bin/pip install -U pip
./.venv/bin/pip install -e .
```

4. 安装服务：

```bash
cp deploy/image-ops.service /etc/systemd/system/image-ops.service
systemctl daemon-reload
systemctl enable image-ops
systemctl start image-ops
systemctl status image-ops
```

### 监听地址

`.env` 中的 `IMAGE_OPS_HOST` 决定服务监听地址：

- Coze 同机部署：`IMAGE_OPS_HOST=127.0.0.1`
- 独立能力机部署：`IMAGE_OPS_HOST=0.0.0.0` 或内网 IP

独立能力机只允许 backend 访问 `8301`，不要面向公网全量开放。

### 复用旧中台端口

如果目标机器不新增端口，可以让 image-ops 复用旧 backend 端口，例如 `117.50.80.158:8099`：

```env
IMAGE_OPS_SERVICE_TOKEN=<same-as-backend>
IMAGE_OPS_HOST=0.0.0.0
IMAGE_OPS_PORT=8099
```

注意：

- 复用 `8099` 前必须停止旧 backend。
- Coze 主机 backend 对应配置为 `IMAGE_OPS_BASE_URL=http://117.50.80.158:8099`。
- 仍需通过安全组限制来源，只允许 Coze backend 主机访问。

## 方式二：docker

```bash
docker build -t podi-image-ops -f image-ops-service/Dockerfile .
docker run -d \
  --name podi-image-ops \
  --restart always \
  --env-file /srv/pod/image-ops-service/.env \
  -p 127.0.0.1:8301:8301 \
  podi-image-ops
```

独立能力机 Docker 模式如需被 Coze backend 访问，可显式发布到内网地址或受限公网地址，例如：

```bash
docker run -d \
  --name podi-image-ops \
  --restart always \
  --env-file /srv/pod/image-ops-service/.env \
  -p 0.0.0.0:8301:8301 \
  podi-image-ops
```

同时必须在安全组或防火墙中限制来源，只允许 Coze backend 主机访问。

## 验证

```bash
curl http://127.0.0.1:8301/health
python3.11 -m pytest tests/test_image_ops_api.py -q
```
