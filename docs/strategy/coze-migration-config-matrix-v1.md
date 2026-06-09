# Coze 控制面迁移配置矩阵 v1

## 目标

把迁移当天真正需要核对的配置拆成三层：

1. Coze 主机上的 `backend`
2. 独立的 `image-ops-service`
3. 外部执行节点 `config/executors.yaml`

这样可以避免迁移时：

- 环境变量写对了，但执行节点没改
- `image-ops` 起起来了，但 token 不一致
- Coze 与中台同机后，高清放大仍然误跑本机

## 一、backend（Coze 主机）

配置文件：

- `backend/.env`
- 推荐生成脚本：`scripts/prod_write_backend_env.sh`

关键变量：

| 变量 | 作用 | 建议值/说明 |
| --- | --- | --- |
| `DATABASE_URL` | 中台数据库 | 优先独立库 |
| `COZE_BASE_URL` | Coze 地址 | 指向同机 Coze |
| `COZE_API_TOKEN` | Coze 访问凭证 | 现网有效 token |
| `COZE_TRUSTED_IPS` | 信任 Coze 源 IP | 同机或实际入口 IP |
| `OSS_*` | OSS 上传/下载 | 首轮继续公网地址为对外真源 |
| `OUTPUT_IMAGE_DEFAULT_DPI` | 生成结果入 OSS 前写入的 DPI/PPI 元数据 | 默认 `150`；设为 `0` 保持上游原始字节 |
| `IMAGE_OPS_BASE_URL` | 图片原子服务地址 | 例如 `http://127.0.0.1:8301` 或独立机器地址 |
| `IMAGE_OPS_SERVICE_TOKEN` | backend 调 image-ops 的鉴权 | 必须与 image-ops 保持一致 |
| `IMAGE_OPS_TIMEOUT_SECONDS` | 图片原子服务超时 | 建议 `120` |
| `IMAGE_OPS_LOCAL_FALLBACK_ENABLED` | 轻量工具本地兜底 | Coze 主机建议 `false` |
| `DISABLE_LOCAL_HEAVY_IMAGE_TASKS` | 禁止本机重图像任务 | Coze 主机必须 `true` |

硬约束：

- Coze 主机上：
  - `DISABLE_LOCAL_HEAVY_IMAGE_TASKS=true`
  - `IMAGE_OPS_LOCAL_FALLBACK_ENABLED=false`

这两项一起生效，才能保证高清放大不会回落到控制面主机本机。

## 二、image-ops-service

配置文件：

- `image-ops-service/.env`
- 推荐生成脚本：`scripts/prod_write_image_ops_env.sh`

关键变量：

| 变量 | 作用 | 建议值/说明 |
| --- | --- | --- |
| `IMAGE_OPS_SERVICE_TOKEN` | 内部鉴权 token | 必须与 backend 一致 |
| `IMAGE_OPS_HOST` | 监听地址 | Coze 同机部署默认 `127.0.0.1`；独立内网专机才允许改为内网地址 |
| `IMAGE_OPS_PORT` | 服务端口 | `8301` |

当前服务能力：

- `upscale-resize`
- `set-dpi`
- `expand-mask-color`

当前不负责：

- OSS 上传
- 对外 URL 返回
- 任务日志
- Coze/OpenAPI

这些仍然由 backend 统一处理。

## 三、执行节点（外部机器）

配置文件：

- `config/executors.yaml`
- 或迁移模板：`config/executors.coze-control-plane.example.yaml`

关键原则：

### 普通 ComfyUI

- 必须带标签：
  - `comfyui-general`

### 高清放大专机

- 若高清放大未来改成 ComfyUI/专机执行，必须带标签：
  - `upscale`
  - `high-mem`
- 必须：
  - `max_concurrency: 1`
  - `fallback_to_default = false`

### 中台约束

当前 backend 已经默认把普通 ComfyUI 能力补齐：

- `required_executor_tags=["comfyui-general"]`

因此执行节点缺标签时，迁移后会直接路由失败，而不是静默误打别的节点。

## 四、能力归类真源

当前纳入 `image-ops` 管理范围的能力：

- `expand_mask_color`
- `set_dpi`
- `upscale_resize`

真源位置：

- `backend/app/services/image_ops_registry.py`
- `backend/app/constants/abilities.py`

其中：

| 能力 | heavy | local_fallback_allowed | execution_target |
| --- | --- | --- | --- |
| `expand_mask_color` | false | true | `image_ops` |
| `set_dpi` | false | true | `image_ops` |
| `upscale_resize` | true | false | `image_ops` |

## 五、迁移当天最小核对顺序

1. `backend/.env` 是否已填：
   - `IMAGE_OPS_BASE_URL`
   - `IMAGE_OPS_SERVICE_TOKEN`
   - `DISABLE_LOCAL_HEAVY_IMAGE_TASKS=true`
2. `image-ops-service/.env` 是否与 backend token 一致
3. `config/executors.yaml` 是否已明确普通/高内存节点标签
4. 运行：

```bash
bash scripts/check_coze_control_plane_bundle.sh
```

5. 单独抽检：
   - `upscale_resize`
   - `set_dpi`
   - `expand_mask_color`

## 六、回滚时优先恢复哪些配置

1. 先恢复 toolbox 指向旧 backend
2. 再恢复 `IMAGE_OPS_BASE_URL` 到旧地址，或清空
3. 若必须让旧环境本机兜底，再恢复：
   - `IMAGE_OPS_LOCAL_FALLBACK_ENABLED=true`
   - `DISABLE_LOCAL_HEAVY_IMAGE_TASKS=false`

注意：

- 回滚时不要先改数据库
- 先恢复流量入口和执行路径，再处理持久层问题

## 七、推荐写入顺序

如果迁移当天需要在 Coze 主机上现场生成 env，建议顺序固定为：

```bash
bash scripts/prod_write_backend_env.sh
bash scripts/prod_write_image_ops_env.sh
```

或者直接使用总入口：

```bash
bash scripts/prod_write_coze_control_plane_envs.sh
```
