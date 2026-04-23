# Image Ops 内部接口

## 说明

`image-ops-service` 是中台拆出来的**自研图片原子能力服务**。

它的职责只有一层：

- 执行图片原子处理

它**不负责**：

- 对外业务 OpenAPI
- Coze toolbox
- OSS 上传
- 任务日志
- 对外结果链接

这些仍由 `backend` 统一处理。

因此这份文档属于**内部接口文档**，主要给迁移、运维和中台开发使用。

---

## 1) 健康检查

### GET /health

**用途**：确认 `image-ops-service` 进程存活。

**响应示例**

```json
{
  "status": "ok"
}
```

---

## 2) 通用约束

### 鉴权

- 当 `IMAGE_OPS_SERVICE_TOKEN` 已配置时：
  - 必须携带 `Authorization: Bearer <token>`
- 未配置时：
  - 允许无鉴权调用
  - 仅建议用于本地开发或临时验证

### 请求体

```json
{
  "imageBase64": "<base64>",
  "params": {}
}
```

字段说明：

- `imageBase64`：必填，原图 base64
- `params`：必填，对应操作参数

### 返回体

```json
{
  "contentBase64": "<base64>",
  "contentType": "image/png",
  "fileExt": ".png"
}
```

字段说明：

- `contentBase64`：处理后的图片内容
- `contentType`：图片 MIME 类型
- `fileExt`：建议文件后缀

---

## 3) 设置 DPI

### POST /internal/image-ops/set-dpi

**用途**：只修改 DPI/PPI 元数据，不改变像素尺寸。

**请求示例**

```json
{
  "imageBase64": "<base64>",
  "params": {
    "dpi": 300
  }
}
```

**常见错误**

- `IMAGE_OPS_UNAUTHORIZED`
- `IMAGE_OPS_IMAGE_INVALID`
- `IMAGE_OPS_INVALID_RESPONSE`

---

## 4) 高清缩放

### POST /internal/image-ops/upscale-resize

**用途**：按长边像素做高质量缩放。

**请求示例**

```json
{
  "imageBase64": "<base64>",
  "params": {
    "max_long_edge": 4096,
    "output_format": "png"
  }
}
```

**说明**

- 当前属于重能力
- 在 Coze 控制面迁移后，默认不允许本机兜底执行
- backend 侧若配置：
  - `DISABLE_LOCAL_HEAVY_IMAGE_TASKS=true`
  - 且 `image-ops` 不可用
  - 会返回 `LOCAL_HEAVY_IMAGE_TASK_DISABLED`

**常见错误**

- `IMAGE_OPS_UNAUTHORIZED`
- `IMAGE_OPS_IMAGE_INVALID`
- `UPSCALE_REMOTE_FAILED`
- `LOCAL_HEAVY_IMAGE_TASK_DISABLED`

---

## 5) 扩边占位图

### POST /internal/image-ops/expand-mask-color

**用途**：给图片扩边并填充透明或固定颜色区域。

**请求示例**

```json
{
  "imageBase64": "<base64>",
  "params": {
    "expand_left": 100,
    "expand_right": 0,
    "expand_top": 0,
    "expand_bottom": 0
  }
}
```

**常见错误**

- `IMAGE_OPS_UNAUTHORIZED`
- `IMAGE_OPS_IMAGE_INVALID`
- `EXPAND_MASK_REMOTE_FAILED`

---

## 6) backend 与 image-ops 的关系

当前中台管理的能力只有：

- `expand_mask_color`
- `set_dpi`
- `upscale_resize`

真源位置：

- `backend/app/services/image_ops_registry.py`
- `backend/app/constants/abilities.py`

backend 调用 `image-ops` 的行为由这些变量控制：

- `IMAGE_OPS_BASE_URL`
- `IMAGE_OPS_SERVICE_TOKEN`
- `IMAGE_OPS_TIMEOUT_SECONDS`
- `IMAGE_OPS_LOCAL_FALLBACK_ENABLED`
- `DISABLE_LOCAL_HEAVY_IMAGE_TASKS`

---

## 7) 部署入口

参考：

- `image-ops-service/README.md`
- `image-ops-service/deploy/README.md`
- `docker-compose.image-ops.yml`
- `scripts/prodlike_restart_image_ops.sh`
