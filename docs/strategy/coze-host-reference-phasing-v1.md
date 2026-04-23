# Coze 迁移 host 引用分批清理方案 v1

> 目的：把仓库里出现的 backend host / 本机代理地址按迁移批次分层，避免“该保留的本机代理也被一起改掉”或“应该首轮切的旧地址漏掉”。  
> 配套真源：`docs/strategy/coze-migration-inventory-v1.md`

## 1. 分批原则

### 首轮必须清理

满足任一条件，就属于首轮必须处理：

1. 会影响 Coze toolbox 导入或调用
2. 会影响 backend / image-ops / Coze workflow 实际切流
3. 会把旧 backend host 暴露给业务、AI 团队、Coze 平台

### 首轮允许保留

满足以下条件，可在首轮保留：

1. 只是同机部署用的本地反代地址
2. 只是脚本默认值，且明确只在同机环境下使用
3. 不参与 Coze toolbox / backend 对外契约

### 第二阶段再处理

满足以下条件，放到第二阶段：

1. 桌面端安装包 / Agent `CenterUrl`
2. 历史说明文档
3. 不参与首轮切流的旧部署脚本

## 2. 首轮必须清理的对象

### 2.1 对外文档与导入入口

这些文档里的 `<podi-backend-host>` 或示例地址，首轮必须与新 backend host 保持一致：

- `docs/coze/toolbox-inventory.md`
- `docs/coze-integration.md`
- `docs/coze-plugin-podi.md`
- `docs/api/modules/coze.md`

处理要求：

- 对外示例统一使用新 backend host
- 本地联调地址可以保留，但必须明确标成“本地开发”
- 不允许再出现旧 backend host

### 2.2 切流检查脚本

这些脚本属于迁移当天会直接跑的对象：

- `backend/scripts/check_coze_control_plane_migration.py`
- `scripts/check_coze_control_plane_bundle.sh`

处理要求：

- 默认值允许是 `127.0.0.1`，因为它们面向同机演练
- 但必须支持传入新 backend host / image-ops host
- 不能写死旧 backend host

## 3. 首轮允许保留的对象

### 3.1 同机前端代理

这些地址在 Coze 主机同机部署时仍然成立，首轮不需要替换：

- `podi-admin-web/nginx.conf` 的 `proxy_pass http://127.0.0.1:8099`
- `podi-eval-web/nginx.conf` 的 `proxy_pass http://127.0.0.1:8099`
- `scripts/prodlike_restart_web_static.sh`
- `scripts/node_static_proxy.mjs`

原因：

- 它们不是旧 backend host
- 它们代表“前端与 backend 同机”
- 切到 Coze 主机后反而应该继续保留

### 3.2 本地开发默认值

以下默认值可以继续保留：

- `http://127.0.0.1:8099`
- `http://127.0.0.1:8199`
- `http://127.0.0.1:8200`
- `http://127.0.0.1:8301`

前提：

- 只能出现在本地开发或同机演练上下文
- 不能伪装成线上真值

## 4. 第二阶段再处理的对象

这些对象不参与首轮 Coze + backend 切流，但必须登记：

- `comfyui-desktop/installer/podi-agent.iss`
- `comfyui-desktop/installer/install_windows.ps1`
- `comfyui-desktop/installer/build_windows.ps1`
- `comfyui-desktop/installer/publish_windows_release.ps1`
- `comfyui-desktop/README.md`
- `docs/api/modules/agent.md`

原因：

- 它们依赖桌面端 `CenterUrl`
- 桌面端切 host 不应该和 Coze 控制面迁移绑成同一批
- 应该在第二阶段单独验证安装包、Agent 注册、心跳和任务拉取

## 5. 风险值判断规则

### 5.1 发现以下值，需要立即判断归类

- `117.50.80.158:8099`
- `127.0.0.1:8099`
- `host.docker.internal:8099`
- `<podi-backend-host>`

### 5.2 判定口径

- `117.50.80.158:8099`
  - 默认按旧 backend host 处理
  - 首轮正式切流中不允许再出现
- `127.0.0.1:8099`
  - 先判断是否是同机代理 / 演练脚本
  - 是则可保留，不是则需要进一步核查
- `host.docker.internal:8099`
  - 只允许本地 Docker 调试说明中出现
  - 不允许出现在导入 Coze 的 OpenAPI 或线上说明里
- `<podi-backend-host>`
  - 可保留为模板占位
  - 但迁移当天必须有明确替换值

## 6. 推荐检查方式

迁移前先跑：

```bash
python3 scripts/collect_coze_migration_inventory.py --root .
python3 scripts/check_coze_host_cutover_refs.py --root .
```

前者给 inventory 快照，后者按批次规则报风险。

## 7. 最小结论

首轮真正要清的是：

- 旧 backend host
- 对外导入文档里的 backend 示例
- 会影响 toolbox / workflow 切流的路径

首轮不该误伤的是：

- 同机前端代理
- 本地演练默认值
- 桌面端 `CenterUrl`
