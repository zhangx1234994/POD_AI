# Coze 控制面迁移一页执行清单 v1

> 用途：迁移当天只看这一页，不再来回翻长文档。  
> 前提：以 `docs/strategy/coze-migration-inventory-v1.md` 为对象清单真源。

## 1. 先确认这次迁移只做什么

本批次只做：

- Coze + backend 同机
- `image-ops` 独立运行
- toolbox 全部指向新 backend

本批次不做：

- OSS 内网地址切换
- 桌面端 `CenterUrl` 切换
- ComfyUI 执行节点搬迁

## 2. 迁移前冻结

先记录：

- `origin/main` commit
- `alembic current`
- 旧 backend host
- 新 backend host
- `image-ops` host

## 3. 部署顺序

### A. 新 backend

```bash
cd backend
alembic upgrade head
```

然后确认：

```bash
curl http://<new-backend-host>:8099/health
curl http://<new-backend-host>:8099/api/abilities
curl http://<new-backend-host>:8099/api/evals/workflow-versions
```

### B. 新 image-ops

二选一：

```bash
docker compose -f docker-compose.image-ops.yml up -d
```

或：

```bash
bash scripts/prodlike_restart_image_ops.sh
```

然后确认：

```bash
curl http://<image-ops-host>:8301/health
```

### C. 配置 backend 执行路径

必须确认：

- `IMAGE_OPS_BASE_URL` 正确
- `IMAGE_OPS_LOCAL_FALLBACK_ENABLED=false`
- `DISABLE_LOCAL_HEAVY_IMAGE_TASKS=true`

### D. 联调检查

```bash
BACKEND_URL=http://<new-backend-host>:8099 \
ADMIN_URL=http://127.0.0.1:8199 \
EVAL_URL=http://127.0.0.1:8200 \
IMAGE_OPS_URL=http://<image-ops-host>:8301 \
bash scripts/check_coze_control_plane_bundle.sh
```

## 4. toolbox 切流

统一切这几类入口：

- `/api/coze/podi/openapi.json`
- `/api/coze/podi/comfyui/openapi.json`
- standalone toolbox

要求：

- 一次性切完
- 不分散到多天
- 不在这一批修改 contract

## 5. 工作流抽检

至少抽检：

- 四方连续
- 新扩图
- 多图融合
- 背景抠图
- 头部抠像
- E7 图裂变
- 裂变文字强化
- 四方连续裂变
- 新高质量裂变

每条确认：

1. main workflow 可提交
2. 回调 workflow `7597556718159003648` 可取图
3. 最终 OSS 链接可访问

## 6. 前端检查

如果同批处理 `8199 / 8200`：

- 必须是 build 产物
- 不能出现 `@vite/client`
- 不能出现 `/src/main.tsx`

## 7. 回滚顺序

如果失败：

1. 先把 toolbox 地址切回旧 backend
2. 再恢复 Coze workflow 引用的旧 toolbox
3. 再停新 backend / image-ops

不要反过来做。

## 8. 当天只看这三个结果

1. Coze 是否已经只认新 backend
2. backend 是否已经只把图片原子能力发给 `image-ops`
3. Coze 主工作流是否仍能稳定出图
