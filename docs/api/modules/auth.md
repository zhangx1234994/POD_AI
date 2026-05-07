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
- `POST /api/auth/invite-codes`、`GET /api/auth/invite-codes`、`POST /api/auth/invite-codes/{inviteId}/disable`、`GET /api/auth/users`、`PATCH /api/auth/users/{userId}`、`GET /api/auth/scope-summary` 仅管理员可用。

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
      "adminAudit": [],
      "createdAt": "2026-04-25T10:00:00",
      "lastLoginAt": "2026-04-25T10:20:00"
    }
  ]
}
```

**错误**

- `ADMIN_ONLY`
- `INVALID_TOKEN` / `INVALID_TOKEN_PAYLOAD`

---

## 12) 管理员调整用户

### PATCH /api/auth/users/{userId}

**用途**：调整用户显示名称、角色、状态、业务方和客户端归属。用于第一阶段账号权限页，不引入复杂多角色表。

**请求体**

```json
{
  "displayName": "业务方账号",
  "role": "client",
  "status": "active",
  "tenantId": "tenant-a",
  "clientId": "client-web",
  "note": "绑定业务方范围"
}
```

兼容旧字段：`display_name`、`tenant_id`、`client_id`。

**响应体**

与“管理员查询用户”中的单条用户一致，并会带最近调整记录：

```json
{
  "id": "user_xxx",
  "username": "client-a",
  "email": "client@example.com",
  "role": "client",
  "status": "active",
  "displayName": "业务方账号",
  "tenantId": "tenant-a",
  "clientId": "client-web",
  "adminAudit": [
    {
      "action": "update_auth_user",
      "actorUsername": "admin",
      "note": "绑定业务方范围",
      "changedFields": ["displayName", "tenantId", "clientId"],
      "createdAt": "2026-05-04T10:00:00"
    }
  ],
  "createdAt": "2026-04-25T10:00:00",
  "lastLoginAt": "2026-05-04T09:50:00"
}
```

**行为约束**

- 管理员不能把自己降权或停用，避免锁死管理端。
- 用户状态改为 `inactive` 或 `disabled` 时，该用户现有 active 会话会被立即踢出。

**错误**

- `ADMIN_ONLY`
- `USER_ID_REQUIRED`：用户 ID 为空。
- `USER_NOT_FOUND`：用户不存在。
- `ROLE_INVALID`：角色不在 `admin/user/client` 范围内。
- `USER_STATUS_INVALID`：状态不在 `active/inactive/disabled` 范围内。
- `AUTH_SELF_LOCKOUT_FORBIDDEN`：管理员不能停用或降权自己。

---

## 13) 管理员查询账号范围摘要

### GET /api/auth/scope-summary

**用途**：给管理端账号权限页提供“当前先处理什么”摘要，直接暴露账号、角色、业务方范围、会话和邀请码风险。

**响应体**

```json
{
  "generatedAt": "2026-05-04T10:00:00",
  "releaseReady": false,
  "blockingRiskCount": 0,
  "warningRiskCount": 2,
  "totals": {
    "users": 12,
    "activeUsers": 10,
    "adminUsers": 2,
    "clientUsers": 4,
    "unscopedClientUsers": 1,
    "activeSessions": 5,
    "activeInvites": 3,
    "unscopedActiveInvites": 1,
    "expiredActiveInvites": 0
  },
  "roles": [
    { "role": "admin", "count": 2, "activeCount": 2 },
    { "role": "client", "count": 4, "activeCount": 3 }
  ],
  "tenants": [
    {
      "tenantId": "tenant-a",
      "clientId": "client-web",
      "userCount": 2,
      "activeUserCount": 2,
      "clientUserCount": 2,
      "activeSessionCount": 1
    }
  ],
  "risks": [
    {
      "key": "unscoped_client_users",
      "title": "业务方账号未绑定",
      "severity": "warning",
      "count": 1,
      "detail": "业务方账号应绑定业务方标识，便于后续隔离、限额和账单统计。"
    }
  ],
  "checklist": [
    {
      "key": "client_users_scoped",
      "title": "业务方账号已绑定范围",
      "passed": false,
      "detail": "业务方账号需要绑定业务方标识，后续才能做隔离、额度和账单统计。",
      "action": "到账号权限页给业务方账号补 tenantId/clientId。"
    }
  ],
  "businessApiPolicy": [
    {
      "key": "client_user_bound_scope",
      "title": "业务方账号只能使用绑定范围",
      "detail": "业务方账号调用业务 API 时，系统会忽略外部伪造的业务方标识，强制使用账号绑定的 tenantId/clientId。",
      "enforced": true
    },
    {
      "key": "unscoped_client_user_blocked",
      "title": "未绑定业务方的账号不能调用业务 API",
      "detail": "role=client 且缺少 tenantId 的账号会被拒绝，避免调用记录、额度和账单归属不清。",
      "enforced": true
    },
    {
      "key": "admin_service_can_act_as_tenant",
      "title": "管理员和服务 Token 可代业务方发起任务",
      "detail": "Coze、巡检和后台任务仍可显式传入 tenantId/clientId，用于灰度、回归和代业务方排障。",
      "enforced": true
    }
  ],
  "roleBoundary": [
    {
      "key": "admin_user",
      "title": "管理员账号",
      "principal": "管理端管理员",
      "allowed": "维护用户、会话、邀请码、业务版本、发布门禁，并可在巡检或排障时显式代业务方发起任务。",
      "blocked": "不能把自己降权或停用；不应作为业务方长期接入凭证。",
      "enforced": true
    },
    {
      "key": "client_user",
      "title": "业务方账号",
      "principal": "业务接入方",
      "allowed": "只能在账号绑定的 tenantId/clientId 范围内提交业务 API 任务和查询结果。",
      "blocked": "不能伪造或越权传入其他业务方范围；未绑定 tenantId 时不能调用业务 API。",
      "enforced": true
    },
    {
      "key": "service_token",
      "title": "服务 Token",
      "principal": "Coze、巡检脚本、后台任务",
      "allowed": "用于系统级调用、发布前巡检和代业务方排障，可显式携带 tenantId/clientId。",
      "blocked": "不能发给业务方当登录账号使用；不能绕过业务运行日志、结算和结果回填链路。",
      "enforced": true
    },
    {
      "key": "coze_toolbox",
      "title": "Coze 工具箱",
      "principal": "Coze 工作流",
      "allowed": "只调用中台 toolbox 和业务 API，由中台统一路由、调度、回填和查询任务。",
      "blocked": "不能直连 ComfyUI、vendor-api-ops 或历史测试地址。",
      "enforced": true
    }
  ]
}
```

上线检查口径：

- `releaseReady=true` 表示没有阻塞和提醒项，账号权限可进入上线验收。
- `blockingRiskCount` 统计必须先处理的问题，例如没有 active 管理员。
- `warningRiskCount` 统计上线前建议处理的问题，例如业务方账号未绑定、邀请码未绑定或已过期。
- `checklist` 是给管理端展示的逐项验收清单，业务人员只需要看“已通过 / 需处理”和动作建议。
- `businessApiPolicy` 是业务 API 权限边界说明，发布 smoke 会校验关键规则存在且已生效。
- `roleBoundary` 是上线角色边界说明，发布 smoke 会校验管理员、业务方账号、服务 Token、Coze 工具箱四类调用方均有明确允许/禁止范围且已生效。

**错误**

- `ADMIN_ONLY`
- `INVALID_TOKEN` / `INVALID_TOKEN_PAYLOAD`
