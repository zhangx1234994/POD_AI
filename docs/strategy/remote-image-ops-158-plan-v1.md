# 117.50.80.158 能力服务拆分方案 v1

## 目标

`117.50.80.158` 后续目标是只保留能力执行面，不再承载中台控制面。第一轮切换为降低风险，会暂时保留旧 backend 作为回滚入口：

- 保留：ComfyUI 执行服务、`image-ops-service`
- 第一轮保留：旧 backend `8099`
- 第一轮停止/替换：旧 eval `8200`
- 后续再停：旧 admin、旧 backend、临时 dev server
- Coze 主机 backend 统一调用 `117.50.80.158` 上的能力服务

## 推荐拓扑

```text
Coze Workflow
  -> 114.55.0.56:8099 backend
    -> 117.50.80.158:8079 ComfyUI
    -> 117.50.80.158:8200 image-ops
```

说明：本方案按“不新增 117 端口”的口径调整。优先复用 `117.50.80.158:8200`，因为测评端不是高频业务入口，且 Coze 主机已经承接了新的测评端；这样可以暂时保留 `117.50.80.158:8099` 旧 backend 作为回滚口。

## 端口

| 端口 | 服务 | 对外策略 |
| --- | --- | --- |
| `8079` | ComfyUI 执行服务 | 只允许 backend / 运维来源访问 |
| `8099` | 旧 backend | 第一轮先保留，作为回滚入口 |
| `8199` | 旧 admin | 迁移后停止 |
| `8200` | image-ops 图片原子能力 | 复用旧 eval 端口，只允许 `114.55.0.56` 访问 |

保留口径：

- 不新增 `8301` 公网端口。
- `8301` 只作为本地开发或 Coze 同机临时 image-ops 端口。
- 117 正式能力机阶段，Coze backend 优先使用 `http://117.50.80.158:8200` 访问 image-ops。
- 如后续确认旧 backend 完全不再需要，再考虑把 image-ops 改到 `8099`。

## image-ops 配置

`117.50.80.158` 上的 `/srv/pod/image-ops-service/.env`：

```env
IMAGE_OPS_SERVICE_TOKEN=<same-as-backend>
IMAGE_OPS_HOST=0.0.0.0
IMAGE_OPS_PORT=8200
```

如果后续有内网地址，`IMAGE_OPS_HOST` 优先绑定内网 IP，不使用 `0.0.0.0`。

Coze 主机 backend 的 `/srv/pod/backend/.env`：

```env
IMAGE_OPS_BASE_URL=http://117.50.80.158:8200
IMAGE_OPS_SERVICE_TOKEN=<same-as-image-ops>
IMAGE_OPS_TIMEOUT_SECONDS=120
IMAGE_OPS_LOCAL_FALLBACK_ENABLED=false
DISABLE_LOCAL_HEAVY_IMAGE_TASKS=true
```

## 启动顺序

1. 在 Coze 主机执行 pre 检查：

```bash
cd /srv/pod
python3.11 scripts/check_remote_image_ops_cutover.py --phase pre
```

2. 在 `117.50.80.158` 停止旧 eval。
3. 在 `117.50.80.158` 部署并启动 `image-ops-service` 到 `8200`。
4. 从 Coze 主机执行 post-117 检查：

```bash
cd /srv/pod
python3.11 scripts/check_remote_image_ops_cutover.py --phase post-117
```

5. 修改 Coze 主机 backend 的 `IMAGE_OPS_BASE_URL` 并重启 backend。
6. 执行 post-coze 检查：

```bash
cd /srv/pod
python3.11 scripts/check_remote_image_ops_cutover.py --phase post-coze
```

## 通过标准

- `expand_mask_color / set_dpi / upscale_resize` 三项都通过 backend 调用成功
- `upscale_resize` 没有本机 fallback
- Coze 主机内存没有因高清放大明显上涨
- `117.50.80.158:8200` 只允许 Coze backend 来源访问 image-ops

## 回滚

优先回滚 backend 配置，不做破坏性操作：

1. 把 `IMAGE_OPS_BASE_URL` 改回上一个可用地址，或临时改回 Coze 同机 `http://127.0.0.1:8301`
2. 重启 Coze 主机 backend
3. 如需恢复旧 117 eval，再停止 image-ops 并重新启动 eval 到 `8200`

不得把 `IMAGE_OPS_LOCAL_FALLBACK_ENABLED` 临时打开作为长期解决方案。若必须临时打开，只能用于短时间验证，且高清放大仍受 `DISABLE_LOCAL_HEAVY_IMAGE_TASKS=true` 保护。

## 117 执行命令口径

在 `117.50.80.158` 拉取新版本后，准备 `.env`：

```bash
cd /srv/pod
DEFAULT_IMAGE_OPS_HOST=0.0.0.0 DEFAULT_IMAGE_OPS_PORT=8200 \
  bash scripts/prod_write_image_ops_env.sh
```

部署 image-ops only：

```bash
cd /srv/pod
REUSE_8200=1 bash scripts/deploy_image_ops_only.sh
```

`REUSE_8200=1` 是故意设计的保护开关：只有明确复用旧 eval 端口时，脚本才会停止 `podi-eval-web` 并占用 `8200`。

## Coze 主机切换命令

确认 `117.50.80.158:8200/health` 可访问后，在 Coze 主机执行：

```bash
cd /srv/pod
IMAGE_OPS_BASE_URL=http://117.50.80.158:8200 \
  bash scripts/switch_backend_image_ops_base.sh
```

回到 Coze 同机临时 image-ops：

```bash
cd /srv/pod
IMAGE_OPS_BASE_URL=http://127.0.0.1:8301 \
  bash scripts/switch_backend_image_ops_base.sh
```
