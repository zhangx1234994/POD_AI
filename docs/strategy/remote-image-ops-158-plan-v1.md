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
    -> 117.50.80.158:8301 image-ops
```

## 端口

| 端口 | 服务 | 对外策略 |
| --- | --- | --- |
| `8079` | ComfyUI 执行服务 | 只允许 backend / 运维来源访问 |
| `8301` | image-ops 图片原子能力 | 只允许 `114.55.0.56` 访问 |
| `8099` | 旧 backend | 迁移后停止 |
| `8199` | 旧 admin | 迁移后停止 |
| `8200` | 旧 eval | 迁移后停止 |

## image-ops 配置

`117.50.80.158` 上的 `/srv/pod/image-ops-service/.env`：

```env
IMAGE_OPS_SERVICE_TOKEN=<same-as-backend>
IMAGE_OPS_HOST=0.0.0.0
IMAGE_OPS_PORT=8301
```

如果后续有内网地址，`IMAGE_OPS_HOST` 优先绑定内网 IP，不使用 `0.0.0.0`。

Coze 主机 backend 的 `/srv/pod/backend/.env`：

```env
IMAGE_OPS_BASE_URL=http://117.50.80.158:8301
IMAGE_OPS_SERVICE_TOKEN=<same-as-image-ops>
IMAGE_OPS_TIMEOUT_SECONDS=120
IMAGE_OPS_LOCAL_FALLBACK_ENABLED=false
DISABLE_LOCAL_HEAVY_IMAGE_TASKS=true
```

## 启动顺序

1. 在 `117.50.80.158` 部署并启动 `image-ops-service`
2. 从 Coze 主机验证 `curl http://117.50.80.158:8301/health`
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
- `117.50.80.158:8301` 不允许非授权来源访问

## 回滚

优先回滚 backend 配置，不做破坏性操作：

1. 把 `IMAGE_OPS_BASE_URL` 改回上一个可用地址，或临时改回 Coze 同机 `http://127.0.0.1:8301`
2. 重启 Coze 主机 backend
3. 再处理 `117.50.80.158` 上的 image-ops 服务

不得把 `IMAGE_OPS_LOCAL_FALLBACK_ENABLED` 临时打开作为长期解决方案。若必须临时打开，只能用于短时间验证，且高清放大仍受 `DISABLE_LOCAL_HEAVY_IMAGE_TASKS=true` 保护。
