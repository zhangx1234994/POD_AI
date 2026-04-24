# image-ops 迁移后 Smoke 检查清单 v1

> 目标：迁移后不只看 `/health`，还要确认 3 条图片原子能力真的走到了 `image-ops`。  
> 适用范围：`expand_mask_color / set_dpi / upscale_resize`

## 1. 前置条件

必须先确认：

- `image-ops` `/health` 返回 `200`
- backend `/health` 返回 `200`
- backend 已配置：
  - `IMAGE_OPS_BASE_URL`
  - `IMAGE_OPS_SERVICE_TOKEN`
  - `IMAGE_OPS_LOCAL_FALLBACK_ENABLED=false`
  - `DISABLE_LOCAL_HEAVY_IMAGE_TASKS=true`

## 2. 检查目标

### 2.1 `expand_mask_color`

验证点：

1. backend 能成功调用
2. 返回图片仍可访问
3. 不报 `EXPAND_MASK_REMOTE_FAILED`

### 2.2 `set_dpi`

验证点：

1. backend 能成功调用
2. 返回结果正常
3. 不报 `SET_DPI_REMOTE_FAILED`

### 2.3 `upscale_resize`

验证点：

1. backend 能成功调用 `image-ops`
2. 不走本机 fallback
3. 不报 `LOCAL_HEAVY_IMAGE_TASK_DISABLED`
4. 不报 `UPSCALE_REMOTE_FAILED`

## 3. 最小接口抽检

### image-ops 直连

```bash
curl http://<image-ops-host>:8301/health
```

### backend 统一能力接口

优先通过 backend 的统一能力调用链路抽检，不要只直接打 `image-ops`。

至少确认：

- `podi.expand_mask_color`
- `podi.set_dpi`
- `podi.upscale_resize`

推荐命令：

```bash
python3 scripts/smoke_image_ops_via_backend.py \
  --backend-base http://127.0.0.1:8099 \
  --backend-env-file /srv/pod/backend/.env \
  --require-remote-image-ops
```

`--require-remote-image-ops` 会强制校验：

- `IMAGE_OPS_BASE_URL` 已配置
- `IMAGE_OPS_LOCAL_FALLBACK_ENABLED=false`
- `DISABLE_LOCAL_HEAVY_IMAGE_TASKS=true`

## 4. 通过标准

以下条件同时满足才算通过：

1. `image-ops` 健康正常
2. 3 条能力均可经 backend 成功执行
3. 高清放大未出现本机兜底
4. backend 未出现对应 remote error

## 5. 失败定位

### `EXPAND_MASK_REMOTE_FAILED / SET_DPI_REMOTE_FAILED / UPSCALE_REMOTE_FAILED`

优先检查：

- `IMAGE_OPS_BASE_URL`
- `IMAGE_OPS_SERVICE_TOKEN`
- `image-ops` 服务日志

### `LOCAL_HEAVY_IMAGE_TASK_DISABLED`

说明：

- backend 已禁止本机跑重任务
- 同时远端 `image-ops` 又不可用

先修 `image-ops` 连通性，不要临时把本机重任务保护关掉。

## 6. 最小结论

`image-ops` 迁移成功的标准不是健康检查，而是：

- 3 条图片原子能力都已经稳定经过 backend -> image-ops 这条链路。
