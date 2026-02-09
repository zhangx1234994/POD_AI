# 认证与用户接口

## 用途

- 提供登录与刷新 token 能力。
- 返回 `accessToken` 作为 Bearer Token，用于其它接口鉴权。

## 鉴权

- `POST /api/auth/login`、`POST /api/auth/refresh` **不需要** Bearer。
- 其它业务接口均需 `Authorization: Bearer <accessToken>`。

---

## 1) 登录

### POST /api/auth/login

**用途**：获取访问 token（支持用户名或邮箱）。

**请求体**

```json
{
  "username": "admin",
  "email": "admin@example.com",
  "password": "Admin123"
}
```

> 说明：`username` 与 `email` 至少提供一个。

**响应体**

```json
{
  "accessToken": "<jwt>",
  "tokenType": "bearer",
  "expiresIn": 86400,
  "refreshToken": "<jwt>",
  "role": "admin"
}
```

**错误**

- `INVALID_CREDENTIALS`（账号/密码错误）
- `USER_NOT_FOUND` / `USER_INACTIVE`

**示例**

```bash
curl -X POST http://127.0.0.1:8099/api/auth/login \
  -H "Content-Type: application/json" \
  -d username:admin
```

---

## 2) 刷新 Token

### POST /api/auth/refresh

**用途**：用 `refreshToken` 换取新的 `accessToken`。

**请求体**

```json
{
  "refreshToken": "<jwt>"
}
```

**响应体**

```json
{
  "accessToken": "<jwt>",
  "tokenType": "bearer",
  "expiresIn": 86400,
  "refreshToken": "<jwt>",
  "role": "admin"
}
```

**错误**

- `INVALID_TOKEN` / `INVALID_TOKEN_PAYLOAD`
- `USER_NOT_FOUND`

**示例**

```bash
curl -X POST http://127.0.0.1:8099/api/auth/refresh \
  -H "Content-Type: application/json" \
  -d {refreshToken:<refresh_token>}
```
