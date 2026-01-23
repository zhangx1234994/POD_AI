# 统一认证方案设计（FastAPI + React 技术栈）

## 目标
1. 为客户端与管理端提供统一的账号体系（用户名/邮箱 + 密码），支持后续扩展到 SSO/OAuth。
2. 在后端引入角色/权限控制，确保 `/api/admin/**`、用户/积分管理等接口只允许管理员访问。
3. 兼容现有的 Token 调度逻辑（任务提交、WebSocket 通知），并便于前端扩展登录/注销体验。

## 后端设计

### 技术选型
- 推荐集成 `fastapi-users`（或基于 `fastapi-jwt-auth` 自建），原因：内置密码哈希、JWT 管理、重置密码、邮件验证等能力，可快速落地。
- 若暂不引入第三方依赖，也可自建：使用 `passlib` 处理密码哈希，`pyjwt` 发放 Access/Refresh Token。

### 数据模型（新增）

| 表 | 关键字段 | 说明 |
|----|---------|------|
| `users` | `id`, `email`, `username`, `password_hash`, `status`, `role`, `last_login_at` | `role` 枚举：`user`、`admin`，后续可扩展为多角色；`status` 控制冻结/启用。 |
| `user_profiles`（可选） | `user_id`, `display_name`, `avatar`, `extra` | 存放用户扩展信息，客户端可显示昵称/头像。 |
| `auth_sessions`（可选） | `id`, `user_id`, `refresh_token`, `user_agent`, `expires_at` | 当需要实现多端登录与刷新机制时使用。 |

### 认证流程
1. **登录**：`POST /api/auth/login`（用户名/邮箱 + 密码）→ 返回 `access_token + refresh_token`，并附带 `role`、`expires_in`。
2. **刷新**：`POST /api/auth/refresh`，校验 `refresh_token` 后重新发放 `access_token`。
3. **注销**：`POST /api/auth/logout`，使关联的 refresh token 失效。
4. **注册/邀请**：客户端可开放自助注册；管理端支持“创建管理员”或“邀请用户”。

### 权限控制
- 封装依赖 `get_current_user` 和 `require_admin`：前者校验 JWT 并返回用户信息；后者在 `Depends` 中判断 `role == "admin"`。
- 现有 `/api/admin/**` 统一改走 `Depends(require_admin)`，替换掉临时的 `X-Admin-Token`。
- 在任务提交等接口中可选择性记录 `user_id`（便于审计、积分管理）。

### 数据迁移
1. 使用 Alembic 创建上述表，若已有用户数据则编写迁移脚本导入。
2. 在设置文件中移除 `ADMIN_API_TOKEN`，改为 JWT 配置项：`JWT_SECRET`, `JWT_EXPIRES_IN`, `JWT_REFRESH_EXPIRES_IN` 等。
3. 迁移完成后，更新文档/配置信息告知各环境管理员账号的初始化方式。

## 前端设计

### 客户端（待重构）
- 历史客户端 `podi-design-web-dev/` 已移除；客户端登录/注册页、用户视角能力调用等将随新客户端重构重新落地。
- 认证接口与模型保持不变：统一基于 `/api/auth/login`（Bearer Token）对接。

### 管理端（podi-admin-web）
- 替换现有的 Token 输入组件，改成账号密码登录页；提交后同样保存 JWT。
- 登录后在 `IntegrationDashboard` 等请求中附带 `Authorization`，不再使用 `X-Admin-Token`。
- 管理端额外提供“管理员管理”页面：创建/禁用管理员、重置密码。

## 待办拆解

1. **数据库 + 模型**
   - [x] 创建 Alembic 迁移，新增 `users` 表（见 `alembic/versions/dc175558f682_add_users_table.py`）。
   - [x] 实现 SQLAlchemy 模型 `app/models/user.py` 与基础 Pydantic Schema (`app/schemas/auth.py` 中 `UserRead`)。
2. **认证 API**
   - [x] 自建登录/刷新逻辑（`POST /api/auth/login`、`POST /api/auth/refresh`，参见 `app/routers/auth.py`）。
   - [ ] 替换 `/api/admin/**` 的鉴权依赖，移除旧的 `X-Admin-Token`，统一通过 JWT 校验。
3. **前端改造**
   - [ ] 新客户端：登录/注册页 + Token 存储。
   - [ ] 管理端登录页重写，后续扩展管理员管理界面。
4. **运营与配置**
   - [ ] 定义管理员初始化脚本（例如 `python scripts/create_admin.py`）。
   - [ ] 在 `AGENTS.md`、`README` 中记录新的环境变量与登录流程。

## 兼容性与过渡
- 新旧方案并行期：保留 `X-Admin-Token` 作为后备（通过配置开关控制），确保切换期间不会阻塞管理端操作。
- 客户端用户若尚未接入账号体系，可以先通过默认账户使用，逐步引导注册。
- 等认证体系稳定后，再引入更复杂的功能：角色分级（如运营、财务）、操作审计、多因素验证等。
