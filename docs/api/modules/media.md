# 媒资与上传接口

## 用途

- 为前端上传图片/视频提供 OSS 临时凭证。
- 统一处理上传回调与签名下载。

## 鉴权

- 默认无 Bearer（通过 `uploadKey` 二次校验）。
- 如需强制鉴权，可在网关层做限制。

---

## 1) 获取上传密钥

### POST /api/media/v1/upload-key

**用途**：发放短效 `uploadKey`，用于换取 OSS STS。

**请求体**

```json
{
  "userId": "u_123"
}
```

**响应体**

```json
{
  "uploadKey": "<jwt>",
  "expiresAt": "2026-02-09T10:00:00Z",
  "expiresIn": 900
}
```

**错误**

- `AUTHORIZATION_REQUIRED`（如被网关限制）

---

## 2) 获取 OSS STS

### POST /api/media/v1/sts

**用途**：使用 `uploadKey` 交换 OSS 临时凭证。

**请求体**

```json
{
  "uploadKey": "<upload_key>",
  "taskId": "task_20260209_0001",
  "action": "ability-test",
  "fileName": "input.png",
  "mimeType": "image/png",
  "fileSize": 102400,
  "channel": "admin"
}
```

**响应体**

```json
{
  "ossCredentials": {
    "accessKeyId": "<ak>",
    "accessKeySecret": "<sk>",
    "securityToken": "<sts>",
    "endpoint": "oss-cn-hangzhou.aliyuncs.com",
    "publicDomain": "https://podi.oss-cn-hangzhou.aliyuncs.com",
    "bucket": "podi",
    "region": "oss-cn-hangzhou",
    "expiration": 1700000000,
    "isTemporary": true,
    "rootPrefix": "podi/u_123/20260209/"
  },
  "objectKey": "podi/u_123/20260209/input.png",
  "host": "https://podi.oss-cn-hangzhou.aliyuncs.com"
}
```

**错误**

- `INVALID_TOKEN` / `UNAUTHORIZED`

---

## 3) OSS 回调

### POST /api/media/v1/oss-callback

**用途**：OSS 上传完成后回调，当前仅落日志（待补齐签名校验）。

**请求体**

```json
{
  "bucket": "podi",
  "object": "podi/u_123/20260209/input.png",
  "size": 102400,
  "mimeType": "image/png",
  "meta": {
    "taskId": "task_20260209_0001",
    "action": "ability-test",
    "userId": "u_123"
  }
}
```

**响应**：`204 No Content`

---

## 4) 签名下载

### POST /api/media/v1/signed-download

**用途**：生成临时下载链接（默认 300s）。

**请求体**

```json
{
  "objectKey": "podi/u_123/20260209/input.png",
  "ttl": 300
}
```

**响应体**

```json
{
  "url": "https://podi.oss-cn-hangzhou.aliyuncs.com/..."
}
```

**错误**

- `objectKey is required`（400）
