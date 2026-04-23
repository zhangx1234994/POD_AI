# Coze 控制面迁移演练步骤 v1

> 目标：按真实 inventory 做一次“可照着执行”的迁移演练，不在迁移当天靠临场判断。  
> 前提：以 `docs/strategy/coze-migration-inventory-v1.md` 为对象清单真源。

## 1. 演练范围

本次演练只覆盖：

- 新 backend 就绪
- 新 `image-ops` 就绪
- toolbox host 切换
- Coze 主工作流抽检
- 回滚路径验证

本次不覆盖：

- OSS 内网地址切换
- 桌面端 `CenterUrl` 切换
- 新增能力 contract 调整

## 2. 演练前冻结项

演练开始前必须冻结：

1. `origin/main` commit
2. `alembic current`
3. `config/executors.yaml`
4. Coze toolbox 当前导入地址
5. 主工作流清单

## 3. 演练准备

### 3.1 新 backend 主机准备

1. 部署 backend 到固定目录
2. 准备 `backend/.env`
3. 运行：

```bash
cd backend
alembic upgrade head
```

4. 执行 seed
5. 确认：

```bash
curl http://<new-backend-host>:8099/health
curl http://<new-backend-host>:8099/api/abilities
curl http://<new-backend-host>:8099/api/evals/workflow-versions
```

### 3.2 新 image-ops 准备

二选一：

```bash
docker compose -f docker-compose.image-ops.yml up -d
```

或：

```bash
bash scripts/prodlike_restart_image_ops.sh
```

确认：

```bash
curl http://<image-ops-host>:8301/health
```

### 3.3 bundle 联调

```bash
bash scripts/check_coze_control_plane_bundle.sh
```

要求：

- backend 检查通过
- admin / eval 若在同机部署，也能通过
- image-ops 检查通过

## 4. 演练切换顺序

### 第一步：只切 backend 内部执行路径

在新 backend 环境中确认：

- `IMAGE_OPS_BASE_URL=http://<image-ops-host>:8301`
- `IMAGE_OPS_LOCAL_FALLBACK_ENABLED=false`
- `DISABLE_LOCAL_HEAVY_IMAGE_TASKS=true`

验证：

- `set_dpi`
- `expand_mask_color`
- `upscale_resize`

其中：

- `upscale_resize` 必须走 `image-ops`
- 不允许回落本机执行

### 第二步：抽检 OpenAPI

逐条检查：

```bash
curl http://<new-backend-host>:8099/api/coze/podi/openapi.json
curl http://<new-backend-host>:8099/api/coze/podi/comfyui/openapi.json
curl http://<new-backend-host>:8099/api/coze/podi/comfyui/execute/flux-strong-hq-softstyle-fission/openapi.json
curl http://<new-backend-host>:8099/api/coze/podi/comfyui/execute/flux2-klein-9b-outpaint/openapi.json
```

核对点：

- 返回 `200`
- 不出现 `host.docker.internal`
- 不出现旧 backend host
- 不出现直接 ComfyUI host 泄漏

### 第三步：切 toolbox host

把 Coze 当前导入的 toolbox 地址统一替换成新 backend host。

禁止做法：

- 只切一半 toolbox
- 一边切 host 一边改入参 contract
- 一边切 toolbox 一边改 workflow 节点逻辑

### 第四步：抽检 Coze workflow

主工作流至少抽检这 11 条：

- `7598563505054154752`
- `7598587935331450880`
- `7631174682116358144`
- `7615600173695107072`
- `7629023903431524352`
- `7629023041988591616`
- `7622190276932534272`
- `7622193261276299264`
- `7629024620879806464`
- `7629026792103215104`
- `7631838631375667200`

每条都确认：

1. main workflow 能提交
2. 如果返回 `output=taskId`，则回调 workflow `7597556718159003648` 能取到图
3. 最终 OSS 链接能打开

### 第五步：最后处理前端

如果同批迁移 `8199 / 8200`：

- 只允许 build 产物运行
- 不允许 `vite dev`

核对：

- 页面源码不出现 `@vite/client`
- 不出现 `/src/main.tsx`

## 5. 演练通过标准

以下条件同时满足，才算演练通过：

1. backend `/health` 稳定 `200`
2. `image-ops` `/health` 稳定 `200`
3. toolbox OpenAPI 全部可访问
4. 主工作流抽检成功率达到预期
5. 高清放大未落到 Coze 主机本机
6. 未出现旧 backend host 泄漏

## 6. 演练失败后的回滚步骤

### 6.1 快速回滚

1. 先把 toolbox 地址切回旧 backend host
2. 再恢复 Coze workflow 里引用的旧 toolbox
3. 再停新 backend / image-ops

### 6.2 禁止反向回滚

不要先停新 backend，再去改 toolbox。  
否则 Coze 会直接打空。

## 7. 演练记录模板

每次演练至少记录：

- 演练时间
- `origin/main` commit
- backend host
- image-ops host
- 切换的 toolbox 数量
- 抽检成功的 workflow 数量
- 是否触发回滚
- 发现的问题和后续动作

## 8. 最小结论

演练不解决所有问题，只验证三件事：

1. Coze 能否只认新 backend
2. backend 能否稳定调外部执行节点和 `image-ops`
3. 回滚是否足够简单
