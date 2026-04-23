# Coze 控制面迁移 Host 切换顺序 v1

## 目标

把 Coze 与中台同机迁移时，所有 host 相关的切换动作固定成**单一顺序**。

避免出现：

- backend 已切新 host，但 toolbox 仍指向旧 host
- Coze workflow 已重导入，但 `tasks/get` 还在旧 host
- `image-ops` 已启用，但 backend 仍然走本地

## 一、涉及的 host

迁移时要明确只有这几类 host：

1. **Coze host**
   - 例如：`http://114.55.0.56:8888`
2. **backend host**
   - 例如：`http://114.55.0.56:8099`
3. **image-ops host**
   - 例如：`http://114.55.0.56:8301`
   - 或独立机器地址
4. **ComfyUI executor host**
   - 例如：`http://117.50.80.158:8079`
   - 只用于 backend 内部路由，不允许被 Coze toolbox 直接引用

## 二、切换原则

1. Coze 只认 backend host
2. backend 再去找：
   - image-ops
   - ComfyUI
   - 其他执行节点
3. 不允许 Coze toolbox 直接连 ComfyUI
4. 不允许一部分 toolbox 指新 backend，一部分还指旧 backend

## 三、标准切换顺序

### 第一步：新 backend 和 image-ops 先就绪

先确认新环境已可用：

1. 新 backend `/health` 为 `200`
2. 新 `image-ops` `/health` 为 `200`
3. `alembic upgrade head` 已完成
4. seed 已执行
5. `config/executors.yaml` 已指向正确执行节点

此时：

- Coze 仍跑旧 host
- toolbox 仍指旧 backend

### 第二步：只切 backend 内部执行路径

先切 backend 自己的内部配置：

- `IMAGE_OPS_BASE_URL`
- `DISABLE_LOCAL_HEAVY_IMAGE_TASKS=true`
- `IMAGE_OPS_LOCAL_FALLBACK_ENABLED=false`

确认：

- backend 调 `image-ops` 正常
- 高清放大不会落到 Coze 主机本机

此时仍然**不动 Coze toolbox**。

### 第三步：切 toolbox host

把 Coze 所有 toolbox 统一改到新 backend host：

- `/api/coze/podi/openapi.json`
- `/api/coze/podi/comfyui/openapi.json`
- 所有 standalone toolbox

要求：

- 同一批切换
- 不要分散到多天
- 切换后立即重导入或批量校验

### 第四步：校验 Coze workflow

按主工作流逐条抽检：

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
2. callback 能取图
3. 最终 OSS 链接可访问

### 第五步：再处理 admin/eval 前端

前端不是切流关键路径，所以放在最后。

要求：

- build 产物运行
- 不允许 dev server

## 四、迁移当天推荐命令顺序

### 1. 先验 backend + image-ops

```bash
bash scripts/check_coze_control_plane_bundle.sh
```

### 2. 再验 toolbox OpenAPI

抽检：

- `/api/coze/podi/openapi.json`
- `/api/coze/podi/comfyui/openapi.json`
- 新旧单功能工具箱

### 3. 最后验 Coze workflow

走真实 workflow 提交和回调，不只看 OpenAPI。

## 五、回滚顺序

如果切换失败，回滚顺序固定为：

1. **先恢复 toolbox 指向旧 backend**
2. 再恢复 Coze workflow 中引用的旧 OpenAPI
3. 再处理 backend / image-ops 内部配置
4. 最后再看是否需要停新服务

不要反过来做。

如果先停新 backend，再改 toolbox：

- Coze 会直接打空
- 故障面更大

## 六、禁止事项

迁移当天禁止：

1. 一边切 toolbox，一边改 contract
2. 一边切 host，一边改数据库结构
3. 一边切 Coze workflow，一边改能力参数语义
4. 一部分 workflow 走新 backend，另一部分还走旧 backend

## 七、与 OSS 的关系

OSS 内外网地址切换不和本次 host 切换绑在同一批。

本次只要求：

- 对外仍返回公网稳定地址
- 内部链路提速后续再灰度

## 八、最小结论

迁移时只记一件事：

**先让新 backend 和 image-ops 就绪，再统一切 toolbox host，最后再校验 Coze workflow。**
