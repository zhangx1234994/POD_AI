# 媒资与上传接口

## 用途

- 为前端上传图片/视频提供 OSS 临时凭证。
- 统一处理上传回调与签名下载。
- OSS 地址采用“前端公网、后端可选内网”的拆分策略：`OSS_ENDPOINT`
  返回给浏览器直传，必须是公网可访问地址；`OSS_INTERNAL_ENDPOINT`
  仅供后端服务端上传/下载使用，可配置为同地域内网地址。

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

**配置注意**

- 浏览器直传使用 `ossCredentials.endpoint`，不要配置为内网地址。
- 后端把第三方结果、ComfyUI 输出、系统回填图片落到 OSS 时，优先使用
  `OSS_INTERNAL_ENDPOINT`；未配置时回退到 `OSS_ENDPOINT`。
- 对外返回的图片链接始终使用 `OSS_PUBLIC_DOMAIN`，默认保持公网稳定地址。

---

## 3) OSS 回调

### POST /api/media/v1/oss-callback

**用途**：OSS 上传完成后回调。后端会校验 bucket、object key 范围、文件大小，并记录任务、动作、用户与对象信息，便于后续排障。

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

**错误**

- `MEDIA_CALLBACK_BUCKET_MISMATCH`（400）：回调 bucket 与当前配置不一致。
- `MEDIA_CALLBACK_OBJECT_REQUIRED`（400）：缺少 object key。
- `MEDIA_CALLBACK_OBJECT_INVALID`（400）：object key 格式非法。
- `MEDIA_CALLBACK_OBJECT_OUT_OF_SCOPE`（400）：object key 不在当前 `OSS_ROOT_PREFIX` 范围内。
- `MEDIA_CALLBACK_SIZE_INVALID`（400）：文件大小无效。

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
