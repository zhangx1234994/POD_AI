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
python3 -m pip install -U pip
python3 -m pip install .
```

4. 安装服务：

```bash
cp deploy/image-ops.service /etc/systemd/system/image-ops.service
systemctl daemon-reload
systemctl enable image-ops
systemctl start image-ops
systemctl status image-ops
```

## 方式二：docker

```bash
docker build -t podi-image-ops -f image-ops-service/Dockerfile .
docker run -d \
  --name podi-image-ops \
  --restart always \
  --env-file /srv/pod/image-ops-service/.env \
  -p 8301:8301 \
  podi-image-ops
```

## 验证

```bash
curl http://127.0.0.1:8301/health
python3 -m pytest tests/test_image_ops_api.py -q
```
