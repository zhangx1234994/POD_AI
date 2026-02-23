# Admin 系统拆分与规划

## 目标
1. **独立入口**：运维/管理员使用专属控制台（独立域名/端口），不与客户端 UI 混用资源或 session。
2. **安全鉴权**：所有 `/api/admin/**` 接口要求管理员身份校验（当前基于 JWT + `require_admin`，后续可接企业 SSO/OIDC）。
3. **工作流导入/解析**：工作流文件必须上传或粘贴 JSON，由后台解析校验后落库，禁止在客户端随意编辑结构。
4. **运营友好**：可视化地管理执行器、工作流、绑定、API Key，支撑 ComfyUI 工作流版本管理、节点健康监控等。

## 架构拆分

```
web-client（待重构）        admin-console（现有）
└── (未落地)               └── podi-admin-web
    ├── (TBD)                 ├── 管理员登录页
    └── (TBD)                 └── 仪表盘/导入/监控
```

| 层级 | 客户端 | 管理端 |
|------|--------|--------|
| 域名 | `app.podi.local` | `admin.podi.local` |
| 鉴权 | 用户 JWT / cookie | 管理员 JWT / SSO |
| API 访问 | `/api/tasks`, `/api/media`, ... | `/api/admin/**`（`Authorization: Bearer`） |

## 后端改造
1. 管理端接口统一使用 `Depends(require_admin)`（已落地）。
2. 管理端登录基于 `/api/auth/login`，请求头使用 `Authorization: Bearer <token>`。
3. 旧的 `X-Admin-Token` 已废弃，不再作为默认方案。
4. 后续扩展：
   - 增加管理员审计日志（记录每次 CRUD）。
   - Admin 登录 API（账号+密码/OIDC）发放短期 token，后续可接 SSO。

## 前端改造（admin-console）

### 目录
```
podi-admin-web/
├── src/
│   ├── App.tsx
│   ├── main.tsx
│   ├── components/LoginGate.tsx   # 管理员登录页（账号密码）
│   ├── pages/IntegrationDashboard.tsx
│   └── services/adminApi.ts       # fetch + Authorization: Bearer
├── vite.config.ts
├── package.json
└── README.md
```

### 功能
1. **登录门控**：账号密码登录，保存 JWT 到 `localStorage`。
2. **仪表页**：延续原先的执行器/工作流/绑定/API Key CRUD，但移除依赖客户端 UI 库，采用轻量组件。
3. **工作流导入**：新增 “导入 JSON” 按钮，支持粘贴或上传 `.json`，自动解析填充 Form，再提交给后端。
4. **环境配置**：通过 `VITE_API_BASE_URL` 指向后台，默认 `http://127.0.0.1:8099`.

### 后续路线
| 阶段 | 内容 |
|------|------|
| P0 | 独立项目 + 账号密码登录（JWT） + 基础 CRUD |
| P1 | 工作流文件导入校验 + 节点健康监控 + API Key 使用图表 |
| P2 | 接入企业 SSO / RBAC + 操作审计 + 多租户配置 |

## 运维与部署
1. Admin 前端独立打包（`npm run build`）后部署到 `admin.podi.local` 或另一个 bucket。
2. API 通过 Nginx 拦截 `/api/admin/**`，仅内网可访问；鉴权使用 JWT。
3. 记录待办：为 ComfyUI 工作流导入提供专属 OSS bucket（仅管理员可写），方便做版本备份。
