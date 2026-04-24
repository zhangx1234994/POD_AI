# PODI Image Ops Service

独立图片原子能力服务，用于承接这批自研图片处理能力：

- `upscale_resize`
- `set_dpi`
- `expand_mask_color`

设计目标：

- 只承接内部请求
- 不直接暴露给业务、Coze 或前端
- 中台继续保留统一 Ability/OpenAPI/OSS/日志口径

## 当前接口

- `GET /health`
- `POST /internal/image-ops/upscale-resize`
- `POST /internal/image-ops/set-dpi`
- `POST /internal/image-ops/expand-mask-color`

请求体统一为：

```json
{
  "imageBase64": "<base64>",
  "params": {}
}
```

返回体统一为：

```json
{
  "contentBase64": "<base64>",
  "contentType": "image/png",
  "fileExt": ".png"
}
```

## 环境变量

- `IMAGE_OPS_SERVICE_TOKEN`
- `IMAGE_OPS_HOST`，默认 `127.0.0.1`
- `IMAGE_OPS_PORT`

## 本地启动

```bash
cd image-ops-service
python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8301
```

独立能力机需要被 backend 访问时，才把 `--host` 改为内网 IP 或 `0.0.0.0`，并通过安全组限制来源。

## 测试

```bash
cd image-ops-service
python3 -m pytest tests/test_image_ops_api.py -q
```
