# Coze 服务器承载中台的迁移方案 v1

## 目标

本次迁移只做一件事：

- **让 Coze 和中台控制面同机**
- **让 ComfyUI/高清放大/其他重能力只承担执行职责**

迁移后固定拓扑：

```text
Coze Workflow
  -> Coze 同机 backend
    -> ability/workflow routing
      -> ComfyUI 普通节点
      -> ComfyUI 高清放大专用节点
      -> 其他云能力节点
```

## 硬约束

1. Coze 不再直接接触任何 ComfyUI 地址。
2. toolbox / OpenAPI / 任务查询统一只指向 backend。
3. backend 统一负责参数翻译、执行节点选择、并发限制、fallback、回调聚合、OSS 落盘。
4. ComfyUI 节点只负责执行，不承担平台逻辑。
5. 高清放大、重采样、重内存批处理**不允许**落到 Coze 主机本机执行。
6. 发布与服务器更新只认 `origin/main`。
7. 自研图片原子能力逐步拆到独立 `image-ops` 服务，中台只保留统一入口和任务口径。

## 当前前提

- Coze 主机：8G 内存 / 1G swap / 49G 磁盘
- 这台机器适合控制面，不适合高内存图像执行
- OSS 内网地址替换纳入保留问题，但不与首轮迁移绑定

## 配套真源

- `docs/strategy/coze-migration-inventory-v1.md`
- `docs/strategy/coze-migration-config-matrix-v1.md`
- `docs/strategy/coze-host-cutover-sequence-v1.md`
- `docs/testing/COZE_CONTROL_PLANE_MIGRATION_DRILL_v1.md`

## 迁移范围

### 本次迁入 Coze 主机

- `backend`
- backend 对应数据库迁移与 seed
- Coze 插件/OpenAPI 文档
- 任务查询与评测文档接口

### 可选同批迁移

- `podi-admin-web`
- `podi-eval-web`

要求：

- 只能 `build + static/preview`
- 禁止长期使用 `vite dev`

### 本次不迁入 Coze 主机

- ComfyUI 执行服务
- `image-ops` 图片处理服务
- 高清放大执行服务
- 任何高内存图像执行能力

## 能力拆分与路由规则

### 1. 控制面能力

只在 backend 内处理：

- 任务状态
- 文档
- toolbox OpenAPI
- 日志
- 轻量 PODI 工具

### 2. 普通执行能力

路由到普通 ComfyUI 或其他云能力节点：

- 允许有限 fallback
- 普通 ComfyUI 默认标签：`comfyui-general`
- 可直接参考：`config/executors.coze-control-plane.example.yaml`

### 3. 重执行能力

- 高清放大
- 重采样
- 重内存批处理

规则：

- 必须单独 executor
- `fallback_to_default = false`
- 没命中 executor 时直接报错
- 不允许静默回落到默认节点
- 推荐单独配置专机示例：`config/executors.coze-control-plane.example.yaml`

## 当前已落地的迁移约束

### 1. ComfyUI 普通执行标签

当前默认普通 ComfyUI 节点标签：

- `comfyui-general`

backend 路由归一化规则：

- 当能力为 `executor_type = comfyui`
- 且没有显式 `required_executor_tags`
- 默认补齐 `required_executor_tags = ["comfyui-general"]`

这样可以保证后续迁移时，普通图裂变 / 扩图 / 抠图等默认不会误打到非普通节点。

### 2. 高清放大本地禁跑开关

新增环境变量：

- `DISABLE_LOCAL_HEAVY_IMAGE_TASKS=true`

含义：

- 禁止 backend 本机执行 `upscale_resize`
- 请求会快速失败并返回 `LOCAL_HEAVY_IMAGE_TASK_DISABLED`

用途：

- 当 backend 部署到 Coze 主机时，避免本机因为高内存缩放任务占满资源

建议：

- 迁移到 Coze 主机后默认开启

### 3. 自研图片原子能力拆分基线

当前这批能力：

- `upscale_resize`
- `set_dpi`
- `expand_mask_color`

已经不再直接绑死本地函数调用，而是统一先经过：

- `backend/app/services/image_ops_client.py`

调用规则：

1. 未配置 `IMAGE_OPS_BASE_URL`
   - 继续本地执行
2. 配置了 `IMAGE_OPS_BASE_URL`
   - 改为调用独立 `image-ops` 服务
3. `upscale_resize` 遇到 `DISABLE_LOCAL_HEAVY_IMAGE_TASKS=true`
   - 不允许本机兜底
   - 必须走外部服务或专机

这保证迁移到 Coze 主机时，不需要再改 ability id、OpenAPI 或 Coze 契约。
同时，能力归类已经固定到代码真源：

- `backend/app/services/image_ops_registry.py`
- `backend/app/constants/abilities.py`

## Toolbox 指向调整

迁移时所有 Coze 工具箱统一改成：

- 指向 **Coze 同机 backend**

统一检查：

- `/api/coze/podi/openapi.json`
- `/api/coze/podi/comfyui/openapi.json`
- 所有 standalone toolbox：
  - outpaint
  - fission
  - E7 fission
  - bg remove
  - head cutout
  - text enhance
  - 四方裂变等

要求：

1. 只换 host，不换 contract
2. Coze workflow 统一重导入或批量校验
3. `debug_url`、`task polling` 保持可用

## OSS 地址策略

### 第一阶段

- 继续沿用当前公网 OSS 地址作为对外真源
- backend 内部保留现有上传/下载逻辑
- 不在首轮迁移中改动所有外链形态

### 第二阶段

盘点所有 OSS 使用位置：

- backend 上传
- 中台回调取图
- Coze workflow 入参
- ComfyUI 下载源图
- 前端展示链接

### 第三阶段

在 backend 增加双地址策略：

- 对内执行链路优先内网地址
- 对外返回继续公网地址

### 第四阶段

按能力类型灰度切换：

1. 中台 -> OSS 下载
2. Coze / ComfyUI 内部拉图
3. 再评估是否保留部分公网回源

### 硬约束

1. 对外返回给业务、前端、AI 团队的地址默认继续使用公网稳定地址
2. 内网地址只用于内部提速，不直接暴露给外部调用方
3. OSS 地址切换必须可单独回退，不能与中台迁移绑成一次大切换

## 部署方式

### Coze 主机

- Coze：保留现有 Docker 部署
- backend：固定成单一正式运行方式
- admin/eval 前端：只允许 build 产物运行

推荐端口：

- `8888` Coze
- `8099` backend
- `8199` admin
- `8200` eval

## 迁移步骤

1. 在 Coze 主机部署 backend 到固定目录
2. 配置 backend 环境变量
3. 开启 `DISABLE_LOCAL_HEAVY_IMAGE_TASKS=true`
4. 若已拆出 `image-ops`，同步配置：
   - `IMAGE_OPS_BASE_URL`
   - `IMAGE_OPS_SERVICE_TOKEN`
   - `IMAGE_OPS_TIMEOUT_SECONDS`
   - `IMAGE_OPS_LOCAL_FALLBACK_ENABLED=false`（Coze 主机建议）
   - 服务部署方式参考：`image-ops-service/deploy/README.md`
5. 执行 `alembic upgrade head`
6. 执行 executor/workflow/ability seed
7. 校验 `/health`
8. 校验 `/api/abilities`
9. 校验 `/api/evals/workflow-versions`
10. 校验 toolbox OpenAPI
11. 抽检主线 Coze workflow
12. 单独抽检：
   - `upscale_resize`
   - `set_dpi`
   - `expand_mask_color`
13. 如已部署 `image-ops`，执行：
   - `python3 backend/scripts/check_coze_control_plane_migration.py --backend-base http://127.0.0.1:8099 --image-ops-base http://127.0.0.1:8301`
   - 或仓库内统一命令：
     - `bash scripts/check_coze_control_plane_bundle.sh`

## 数据库策略

- 优先独立中台数据库
- 如果必须共实例，也要保持数据库或 schema 边界清晰
- 不允许中台表和 Coze 核心表混用不清

## 回滚策略

触发条件：

- backend `/health` 不稳定
- toolbox 导入或调用大面积失败
- Coze workflow 失败率明显上升
- admin/eval 无法稳定访问
- Coze 主机资源持续异常
- OSS 内网化试点导致内部拉图失败率上升

回滚步骤：

1. 恢复 toolbox 指向到旧 backend host
2. 恢复 Coze workflow 中引用的旧 OpenAPI/toolbox
3. 切回旧 backend 服务入口
4. 停止新主机上的 backend 服务
5. 如果启用了 OSS 内网下载灰度，先恢复到公网地址
6. 保留数据库，不做 destructive 回滚

关键原则：

- 先切流回旧 backend，再处理新环境
- 不做边跑边修的半回滚

## 发布口径

迁移相关发布必须同时满足：

1. 目标提交已进入 `origin/main`
2. 更新范围明确
3. migration / seed / 重启步骤明确
4. smoke checklist 已执行

否则不允许发出“现在可以更新服务器”的信号。
