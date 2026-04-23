# Coze 控制面迁移检查清单

本清单只用于：

- Coze + 中台同机迁移
- toolbox 全部改指向 backend
- 执行面仍在外部机器

配套文档：

- `docs/strategy/coze-migration-inventory-v1.md`
- `docs/testing/COZE_CONTROL_PLANE_MIGRATION_DRILL_v1.md`
- `docs/testing/COZE_CONTROL_PLANE_RUNBOOK_v1.md`
- `docs/testing/COZE_SERVER_COMMANDS_v1.md`
- `docs/testing/IMAGE_OPS_SMOKE_CHECKLIST_v1.md`
- `scripts/run_coze_control_plane_cutover.sh`
- `scripts/rollback_coze_control_plane.sh`

## 一、迁移前固定信息

上线前先记录：

- `origin/main` commit
- `alembic current`
- backend `.env` 备份
- `config/executors.yaml` 备份
- 当前 toolbox URL 清单
- 当前 active eval workflows 清单

## 二、配置核对

### backend 环境变量

- MySQL 正确
- Redis 正确
- OSS 正确
- `COZE_BASE_URL` 正确
- `COZE_API_TOKEN` 正确
- `COZE_TRUSTED_IPS` 正确
- `PODI_INTERNAL_BASE_URL` 正确
- `DISABLE_LOCAL_HEAVY_IMAGE_TASKS=true`
- 若已拆出图片原子能力：
  - `IMAGE_OPS_BASE_URL` 正确
  - `IMAGE_OPS_SERVICE_TOKEN` 正确
  - `IMAGE_OPS_TIMEOUT_SECONDS` 正确
  - `IMAGE_OPS_LOCAL_FALLBACK_ENABLED=false`

### image-ops 服务

- `image-ops-service` 已部署
- `/health` 返回 `200`
- 鉴权 token 与 backend 配置一致
- 运行方式固定为 `systemd` 或 `docker`，不能靠手工临时启动

### 执行节点

- 普通 ComfyUI 节点带 `comfyui-general`
- 高清放大节点带 `upscale` / `high-mem`
- 高清放大节点 `fallback_to_default = false`
- 可直接对照模板：`config/executors.coze-control-plane.example.yaml`
- 若 `upscale_resize` 已拆到 `image-ops`：
  - Coze 主机本机不允许再承担高清放大兜底

## 三、部署步骤

1. 拉取 `origin/main`
2. 部署 backend 到固定目录
3. `alembic upgrade head`
4. 执行 executor/workflow/ability seed
5. 重启 backend

## 四、接口检查

- `/health` 返回 `200`
- `/api/abilities` 返回 `200`
- `/api/evals/workflow-versions` 返回 `200`
- `/api/coze/podi/openapi.json` 返回 `200`
- `/api/coze/podi/comfyui/openapi.json` 返回 `200`

## 五、Toolbox 检查

抽检当前正在使用的 standalone toolbox：

- outpaint
- fission
- E7 fission
- bg remove
- head cutout
- text enhance
- 四方裂变

检查项：

1. OpenAPI `200`
2. contract 未变化
3. Coze 可导入

## 六、Coze workflow 抽检

至少逐条抽检：

- 四方连续
- 多图融合
- 背景抠图
- 头部抠像
- E7 图裂变
- 文字增强
- 四方连续裂变
- 新高质量裂变
- 扩图主线

每条确认：

1. main workflow 提交成功
2. callback 可取图
3. OSS 最终链接可访问

## 七、路由检查

- 普通裂变、扩图、抠图命中外部 ComfyUI
- 高清放大命中高内存节点
- 高清放大在无专机时正确失败
- 不允许 fallback 到 Coze 主机本机
- `set_dpi` / `expand_mask_color` 若已切到 `image-ops`，应确认不再走本地实现

## 八、图片原子能力检查

至少单独抽检：

- `upscale_resize`
- `set_dpi`
- `expand_mask_color`

确认：

1. 调用成功
2. 返回结果仍由 backend 统一输出
3. Coze 主机本机未承担高内存放大
4. 若 `image-ops` 不可用：
   - 高清放大正确失败
   - 轻量工具是否允许本地回退符合当前配置

## 九、OSS 检查

当前阶段要求：

- 对外仍返回公网地址
- 如果开启内网下载试点，单独检查：
  - backend 拉图
  - Coze 调用链路
  - ComfyUI 拉图

异常时要求：

- 能独立切回公网地址
- 不与 backend 切流绑死

## 十、资源观察

迁移后至少观察一轮业务高峰：

- CPU
- 内存
- swap
- 磁盘

重点确认：

- backend 稳定
- Coze 稳定
- 没有重任务落到控制面主机

## 十一、前端检查（如果同批迁移）

- `8199` 是 build 产物
- `8200` 是 build 产物
- 不允许出现：
  - `@vite/client`
  - `/src/main.tsx`

## 十二、回滚步骤

1. 恢复 toolbox 指向到旧 backend host
2. 恢复 Coze workflow 中引用的旧 OpenAPI/toolbox
3. 切回旧 backend 服务入口
4. 若已拆出 `image-ops`，先恢复图片原子能力到旧实现或旧服务
5. 停止新 backend
6. 如果启用了 OSS 内网灰度，先切回公网下载链路
7. 保留数据库，不做 destructive 回滚

## 十三、推荐执行命令

迁移后建议至少执行一次：

```bash
bash scripts/check_coze_control_plane_bundle.sh
```
