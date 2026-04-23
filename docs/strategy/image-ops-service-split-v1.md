# 自研图片原子能力拆分方案 v1

## 目标

把这批**自研图片原子能力**从中台执行实现里拆出去：

- `upscale_resize`
- `set_dpi`
- `expand_mask_color`

拆分原则：

- 中台继续保留对外能力入口、OpenAPI、日志、任务口径
- 执行实现下沉到独立 `image-ops` 服务
- 业务、Coze、测评端不直接调用 `image-ops`

## 为什么要拆

这批能力具备同一类特征：

1. 是我们自己的实现，不依赖 Coze 画布或 ComfyUI workflow
2. 职责单一，属于图片加工，不属于控制面核心职责
3. 其中高清放大明显存在内存风险，不适合和 Coze 控制面同机

## 目标结构

```text
Coze / 管理端 / 测评端
  -> backend 中台
    -> image-ops 服务
    -> ComfyUI executor
    -> 其他云能力
```

## 当前已落地的拆分基线

本仓当前不是直接本地函数调用，而是先统一走：

- `backend/app/services/image_ops_client.py`

也就是说：

- 当前默认仍可本地执行
- 但一旦配置 `IMAGE_OPS_BASE_URL`
- backend 就会改为调用外部 `image-ops` 服务

这样后续外移时：

- 不改现有 ability id
- 不改对外 OpenAPI
- 不改 Coze workflow/toolbox 契约

## 当前仓库内已提供的服务骨架

本仓已经新增独立服务目录：

- `image-ops-service/`

当前已提供：

- `FastAPI` 应用入口：`image-ops-service/app/main.py`
- 内部接口：
  - `POST /internal/image-ops/upscale-resize`
  - `POST /internal/image-ops/set-dpi`
  - `POST /internal/image-ops/expand-mask-color`
- Bearer Token 鉴权
- 契约测试：`image-ops-service/tests/test_image_ops_api.py`

推荐启动方式：

```bash
cd image-ops-service
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8301
```

正式部署材料：

- `image-ops-service/Dockerfile`
- `image-ops-service/deploy/image-ops.service`
- `image-ops-service/deploy/README.md`

## 新配置项

- `IMAGE_OPS_BASE_URL`
- `IMAGE_OPS_SERVICE_TOKEN`
- `IMAGE_OPS_TIMEOUT_SECONDS`
- `IMAGE_OPS_LOCAL_FALLBACK_ENABLED`

额外控制项：

- `DISABLE_LOCAL_HEAVY_IMAGE_TASKS=true`

含义：

- 禁止本机执行 `upscale_resize`
- 要求必须走外部 `image-ops` 或专机

当前 `backend/.env.example` 已补齐上述变量，可直接作为迁移时的配置参考。

## 中台与 image-ops 的职责边界

### backend 中台保留

- Ability 定义
- OpenAPI / toolbox
- 参数校验
- 路由与任务状态
- OSS 对外地址
- 日志与错误码

### image-ops 负责

- 图片实际处理
- 同步或短任务处理
- 返回结果二进制内容与基础元信息

## 当前纳入 image-ops 管理范围的能力

当前已固化为代码真源的能力只有这三条：

- `expand_mask_color`
- `set_dpi`
- `upscale_resize`

对应真源：

- `backend/app/services/image_ops_registry.py`
- `backend/app/constants/abilities.py`

其中：

- `upscale_resize` 标记为重能力
- `set_dpi` / `expand_mask_color` 标记为轻量能力

## 推荐接口

建议 image-ops 服务内部接口固定为：

- `POST /internal/image-ops/upscale-resize`
- `POST /internal/image-ops/set-dpi`
- `POST /internal/image-ops/expand-mask-color`

请求体：

```json
{
  "imageBase64": "<base64>",
  "params": {}
}
```

返回体：

```json
{
  "contentBase64": "<base64>",
  "contentType": "image/png",
  "fileExt": ".png"
}
```

这样中台统一负责 OSS 上传和对外地址，不让 image-ops 自己定义另一套外部契约。

## 首轮部署建议

首轮拆分时建议：

1. 先把 `image-ops-service` 部署到独立机器
2. 中台配置：
   - `IMAGE_OPS_BASE_URL=http://<image-ops-host>:8301`
   - `IMAGE_OPS_SERVICE_TOKEN=...`
   - `IMAGE_OPS_LOCAL_FALLBACK_ENABLED=false`
3. Coze 控制面主机同步开启：
   - `DISABLE_LOCAL_HEAVY_IMAGE_TASKS=true`

这样可以保证高清放大不再落到 Coze 主机本机。

## 迁移顺序

### 第一阶段

先完成调用抽象：

- 已完成 `image_ops_client`
- 保持本地执行兼容

### 第二阶段

先外移 `upscale_resize`

原因：

- 风险最高
- 收益最大
- 最容易影响 Coze 控制面稳定性

### 第三阶段

再把：

- `set_dpi`
- `expand_mask_color`

一并迁到 `image-ops`

## 回滚策略

如果 image-ops 服务异常：

1. 若 `IMAGE_OPS_LOCAL_FALLBACK_ENABLED=true`
   - 中台自动回落本地执行
2. 若为高清放大且 `DISABLE_LOCAL_HEAVY_IMAGE_TASKS=true`
   - 直接失败
   - 不允许本机兜底拖垮控制面

## 当前建议

迁移到 Coze 主机时：

- backend 开启 `DISABLE_LOCAL_HEAVY_IMAGE_TASKS=true`
- 先只要求 `upscale_resize` 外部可用
- `set_dpi` / `expand_mask_color` 可短期保留本地兼容，但后续也建议迁出
