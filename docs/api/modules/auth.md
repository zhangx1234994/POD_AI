# 认证与用户接口

> 当前状态：登录、刷新、注册、登出、会话列表、邀请码和用户列表接口已进入第一阶段实现。
> 第一阶段仍保留 `users.role` 作为角色来源，暂不单独拆 `user_roles` 表。

## 用途

- 提供账号登录、刷新 token、邀请码注册和会话注销能力。
- 让后续业务 API、计费统计、管理端操作都能识别调用方、业务方和客户端来源。

## 鉴权

- `POST /api/auth/login`、`POST /api/auth/refresh`、`POST /api/auth/register` 不需要 Bearer。
- `POST /api/auth/logout`、`GET /api/auth/sessions` 需要当前用户 Bearer。
- `GET /api/auth/sessions/all`、`POST /api/auth/sessions/{sessionId}/revoke` 仅管理员可用。
- `POST /api/auth/invite-codes`、`GET /api/auth/invite-codes`、`POST /api/auth/invite-codes/{inviteId}/disable`、`GET /api/auth/users` 仅管理员可用。

---

## 1) 登录

### POST /api/auth/login

**用途**：用用户名或邮箱登录，并创建一条可追踪的登录会话。

**请求体**

```json
{
  "username": "admin",
  "email": "admin@example.com",
  "password": "<your_password>"
}
```

`username` 与 `email` 至少提供一个。

**响应体**

```json
{
  "accessToken": "<jwt>",
  "tokenType": "bearer",
  "expiresIn": 3600,
  "refreshToken": "<jwt>",
  "role": "admin",
  "user": {
    "id": "user_admin",
    "username": "admin",
    "email": "admin@example.com",
    "role": "admin",
    "status": "active",
    "displayName": "管理员",
    "tenantId": null,
    "clientId": null,
    "createdAt": "2026-04-25T10:00:00",
    "lastLoginAt": "2026-04-25T10:20:00"
  }
}
```

**错误**

- `LOGIN_IDENTIFIER_REQUIRED`：缺少用户名和邮箱。
- `INVALID_CREDENTIALS`：账号或密码错误。
- `LOGIN_RATE_LIMITED`：同一账号和 IP 在 10 分钟内连续失败次数过多。
- `USER_NOT_FOUND`：用户不存在。
- `USER_INACTIVE`：用户被禁用。

---

## 2) 刷新 Token

### POST /api/auth/refresh

**用途**：用 `refreshToken` 换取新的登录态。刷新成功后旧 refresh 会话会被标记为 `rotated`，不能再次使用。

**请求体**

```json
{
  "refreshToken": "<jwt>"
}
```

**响应体**

```json
{
  "accessToken": "<new_jwt>",
  "tokenType": "bearer",
  "expiresIn": 3600,
  "refreshToken": "<new_refresh_jwt>",
  "role": "admin",
  "user": {
    "id": "user_admin",
    "username": "admin",
    "email": "admin@example.com",
    "role": "admin",
    "status": "active"
  }
}
```

**错误**

- `INVALID_REFRESH_TOKEN`：refreshToken 无效、类型不对或解析失败。
- `SESSION_NOT_FOUND`：refreshToken 对应会话不存在。
- `SESSION_REVOKED`：会话已登出或已被轮换。
- `SESSION_EXPIRED`：会话已过期。
- `USER_NOT_FOUND` / `USER_INACTIVE`：用户不存在或被禁用。

---

## 3) 邀请码注册

### POST /api/auth/register

**用途**：通过管理员生成的邀请码注册账号。注册成功后立即返回登录态。

**请求体**

```json
{
  "email": "designer@example.com",
  "username": "designer_a",
  "password": "StrongPass123",
  "inviteCode": "ABCD1234",
  "displayName": "业务设计师 A"
}
```

兼容旧字段：`invite_code`、`display_name`。

**响应体**

与登录接口一致，包含 `accessToken`、`refreshToken`、`role` 和 `user`。

**错误**

- `USERNAME_REQUIRED`：用户名为空。
- `PASSWORD_TOO_SHORT`：密码长度小于 8 位。
- `USER_ALREADY_EXISTS`：用户名或邮箱已存在。
- `INVITE_CODE_INVALID`：邀请码不存在或为空。
- `INVITE_CODE_INACTIVE`：邀请码未启用。
- `INVITE_CODE_EXPIRED`：邀请码已过期。
- `INVITE_CODE_USED`：邀请码使用次数已达上限。

---

## 4) 登出

### POST /api/auth/logout

**用途**：注销当前 refresh 会话，或注销当前用户全部会话。

**请求体**

```json
{
  "refreshToken": "<jwt>",
  "allSessions": false
}
```

**响应体**

```json
{
  "ok": true
}
```

**错误**

- `INVALID_REFRESH_TOKEN`：refreshToken 无效。
- `SESSION_NOT_FOUND`：指定会话不存在。
- `INVALID_TOKEN` / `INVALID_TOKEN_PAYLOAD`：当前 Bearer 无效。

---

## 5) 当前用户会话列表

### GET /api/auth/sessions

**用途**：查看当前账号的登录会话，用于后续管理端展示和异常登录排查。

**响应体**

```json
{
  "items": [
    {
      "id": "session_xxx",
      "status": "active",
      "ipAddress": "127.0.0.1",
      "userAgent": "Mozilla/5.0",
      "expiresAt": "2026-05-02T10:20:00",
      "revokedAt": null,
      "lastSeenAt": "2026-04-25T10:20:00",
      "createdAt": "2026-04-25T10:20:00"
    }
  ]
}
```

**错误**

- `INVALID_TOKEN` / `INVALID_TOKEN_PAYLOAD`
- `USER_NOT_FOUND`

---

## 6) 管理员生成邀请码

### POST /api/auth/invite-codes

**用途**：生成注册邀请码，并绑定角色、业务方、客户端和使用次数。

**请求体**

```json
{
  "role": "user",
  "tenantId": "tenant-a",
  "clientId": "client-web",
  "maxUses": 1,
  "expiresAt": "2026-05-25T00:00:00",
  "note": "业务方 A 首批账号"
}
```

兼容旧字段：`tenant_id`、`client_id`、`max_uses`、`expires_at`。

**响应体**

```json
{
  "id": "invite_xxx",
  "code": "ABCD1234",
  "role": "user",
  "tenantId": "tenant-a",
  "clientId": "client-web",
  "maxUses": 1,
  "usedCount": 0,
  "status": "active",
  "expiresAt": "2026-05-25T00:00:00",
  "createdBy": "user_admin",
  "note": "业务方 A 首批账号",
  "metadata": null,
  "createdAt": "2026-04-25T10:20:00",
  "updatedAt": "2026-04-25T10:20:00"
}
```

**错误**

- `ADMIN_ONLY`：非管理员访问。
- `ROLE_INVALID`：角色不在允许范围内。
- `INVITE_CODE_GENERATE_FAILED`：邀请码生成失败。

---

## 7) 管理员查询邀请码

### GET /api/auth/invite-codes

**用途**：查看最近的邀请码，用于管理端只读展示和追踪。

**响应体**

```json
{
  "items": [
    {
      "id": "invite_xxx",
      "code": "ABCD1234",
      "role": "user",
      "tenantId": "tenant-a",
      "clientId": "client-web",
      "maxUses": 1,
      "usedCount": 0,
      "status": "active",
      "expiresAt": null,
      "createdBy": "user_admin",
      "note": "业务方 A 首批账号",
      "metadata": null,
      "createdAt": "2026-04-25T10:20:00",
      "updatedAt": "2026-04-25T10:20:00"
    }
  ]
}
```

**错误**

- `ADMIN_ONLY`
- `INVALID_TOKEN` / `INVALID_TOKEN_PAYLOAD`

---

## 8) 管理员禁用邀请码

### POST /api/auth/invite-codes/{inviteId}/disable

**用途**：让未使用的邀请码立即失效，避免邀请码被继续注册。

**响应体**

与“管理员生成邀请码”一致，`status` 会变为 `disabled`。

**错误**

- `ADMIN_ONLY`
- `INVITE_CODE_NOT_FOUND`：邀请码记录不存在。
- `INVALID_TOKEN` / `INVALID_TOKEN_PAYLOAD`

---

## 9) 管理员查询全部会话

### GET /api/auth/sessions/all

**用途**：管理员查看全部账号的登录会话，用于排查异常登录和踢出登录态。

**响应体**

```json
{
  "items": [
    {
      "id": "session_xxx",
      "userId": "user_xxx",
      "username": "designer",
      "email": "designer@example.com",
      "displayName": "设计师",
      "status": "active",
      "ipAddress": "127.0.0.1",
      "userAgent": "Mozilla/5.0",
      "expiresAt": "2026-05-02T10:20:00",
      "revokedAt": null,
      "lastSeenAt": "2026-04-25T10:20:00",
      "createdAt": "2026-04-25T10:20:00"
    }
  ]
}
```

**错误**

- `ADMIN_ONLY`
- `INVALID_TOKEN` / `INVALID_TOKEN_PAYLOAD`

---

## 10) 管理员踢出会话

### POST /api/auth/sessions/{sessionId}/revoke

**用途**：管理员按会话 ID 踢出指定登录态。被踢出的 refreshToken 再刷新会返回 `SESSION_REVOKED`。

**响应体**

与“当前用户会话列表”中的单条会话一致，`status` 会变为 `revoked`。

**错误**

- `ADMIN_ONLY`
- `SESSION_NOT_FOUND`：指定会话不存在。
- `INVALID_TOKEN` / `INVALID_TOKEN_PAYLOAD`

---

## 11) 管理员查询用户

### GET /api/auth/users

**用途**：查看平台账号、角色、状态、业务方和客户端归属。

**响应体**

```json
{
  "items": [
    {
      "id": "user_admin",
      "username": "admin",
      "email": "admin@example.com",
      "role": "admin",
      "status": "active",
      "displayName": "管理员",
      "tenantId": null,
      "clientId": null,
      "createdAt": "2026-04-25T10:00:00",
      "lastLoginAt": "2026-04-25T10:20:00"
    }
  ]
}
```

**错误**

- `ADMIN_ONLY`
- `INVALID_TOKEN` / `INVALID_TOKEN_PAYLOAD`
