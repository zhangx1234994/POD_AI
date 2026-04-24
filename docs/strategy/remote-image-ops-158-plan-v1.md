# 117.50.80.158 能力服务拆分方案 v1

## 目标

`117.50.80.158` 后续只保留能力执行面，不再承载中台控制面：

- 保留：ComfyUI 执行服务、`image-ops-service`
- 停止：旧 backend、admin、eval、临时 dev server
- Coze 主机 backend 统一调用 `117.50.80.158` 上的能力服务

## 推荐拓扑

```text
Coze Workflow
  -> 114.55.0.56:8099 backend
    -> 117.50.80.158:8079 ComfyUI
    -> 117.50.80.158:8099 image-ops
```

说明：本方案按“不新增 117 端口”的口径调整。`117.50.80.158:8099` 迁移前是旧 backend，迁移后改为 image-ops 能力服务。因此切换 117 时会失去旧 backend 的原地回滚入口，回滚入口以 Coze 主机同机 image-ops 或重新启动旧 backend 为准。

## 端口

| 端口 | 服务 | 对外策略 |
| --- | --- | --- |
| `8079` | ComfyUI 执行服务 | 只允许 backend / 运维来源访问 |
| `8099` | image-ops 图片原子能力 | 迁移后复用旧 backend 端口，只允许 `114.55.0.56` 访问 |
| `8199` | 旧 admin | 迁移后停止 |
| `8200` | 旧 eval | 迁移后停止 |

保留口径：

- 不新增 `8301` 公网端口。
- `8301` 只作为本地开发或 Coze 同机临时 image-ops 端口。
- 117 正式能力机阶段，Coze backend 使用 `http://117.50.80.158:8099` 访问 image-ops。

## image-ops 配置

`117.50.80.158` 上的 `/srv/pod/image-ops-service/.env`：

```env
IMAGE_OPS_SERVICE_TOKEN=<same-as-backend>
IMAGE_OPS_HOST=0.0.0.0
IMAGE_OPS_PORT=8099
```

如果后续有内网地址，`IMAGE_OPS_HOST` 优先绑定内网 IP，不使用 `0.0.0.0`。

Coze 主机 backend 的 `/srv/pod/backend/.env`：

```env
IMAGE_OPS_BASE_URL=http://117.50.80.158:8099
IMAGE_OPS_SERVICE_TOKEN=<same-as-image-ops>
IMAGE_OPS_TIMEOUT_SECONDS=120
IMAGE_OPS_LOCAL_FALLBACK_ENABLED=false
DISABLE_LOCAL_HEAVY_IMAGE_TASKS=true
```

## 启动顺序

1. 在 `117.50.80.158` 停止旧 backend/admin/eval
2. 在 `117.50.80.158` 部署并启动 `image-ops-service` 到 `8099`
3. 从 Coze 主机验证 `curl http://117.50.80.158:8099/health`
3. 修改 Coze 主机 backend 的 `IMAGE_OPS_BASE_URL`
4. 重启 Coze 主机 backend
5. 执行：

```bash
python3 scripts/smoke_image_ops_via_backend.py \
  --backend-base http://127.0.0.1:8099 \
  --backend-env-file /srv/pod/backend/.env \
  --require-remote-image-ops
```

## 通过标准

- `expand_mask_color / set_dpi / upscale_resize` 三项都通过 backend 调用成功
- `upscale_resize` 没有本机 fallback
- Coze 主机内存没有因高清放大明显上涨
- `117.50.80.158:8099` 只允许 Coze backend 来源访问 image-ops

## 回滚

优先回滚 backend 配置，不做破坏性操作：

1. 把 `IMAGE_OPS_BASE_URL` 改回上一个可用地址，或临时改回 Coze 同机 `http://127.0.0.1:8301`
2. 重启 Coze 主机 backend
3. 如需恢复旧 117 backend，再停止 image-ops 并重新启动旧 backend 到 `8099`

不得把 `IMAGE_OPS_LOCAL_FALLBACK_ENABLED` 临时打开作为长期解决方案。若必须临时打开，只能用于短时间验证，且高清放大仍受 `DISABLE_LOCAL_HEAVY_IMAGE_TASKS=true` 保护。

## 117 执行命令口径

在 `117.50.80.158` 拉取新版本后，准备 `.env`：

```bash
cd /srv/pod
DEFAULT_IMAGE_OPS_HOST=0.0.0.0 DEFAULT_IMAGE_OPS_PORT=8099 \
  bash scripts/prod_write_image_ops_env.sh
```

部署 image-ops only：

```bash
cd /srv/pod
REUSE_8099=1 bash scripts/deploy_image_ops_only.sh
```

`REUSE_8099=1` 是故意设计的保护开关：只有明确复用旧 backend 端口时，脚本才会停止 `podi-backend` 并占用 `8099`。

## Coze 主机切换命令

确认 `117.50.80.158:8099/health` 可访问后，在 Coze 主机执行：

```bash
cd /srv/pod
IMAGE_OPS_BASE_URL=http://117.50.80.158:8099 \
  bash scripts/switch_backend_image_ops_base.sh
```

回到 Coze 同机临时 image-ops：

```bash
cd /srv/pod
IMAGE_OPS_BASE_URL=http://127.0.0.1:8301 \
  bash scripts/switch_backend_image_ops_base.sh
```
