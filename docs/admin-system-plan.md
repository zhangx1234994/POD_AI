# Admin 系统拆分与规划

## 目标
1. **独立入口**：运维/管理员使用专属控制台（独立域名/端口），不与客户端 UI 混用资源或 session。
2. **安全鉴权**：所有 `/api/admin/**` 接口要求单独的管理员身份校验（首版用 `X-Admin-Token`，后续可接企业 SSO/OIDC）。
3. **工作流导入/解析**：工作流文件必须上传或粘贴 JSON，由后台解析校验后落库，禁止在客户端随意编辑结构。
4. **运营友好**：可视化地管理执行器、工作流、绑定、API Key，支撑 ComfyUI 工作流版本管理、节点健康监控等。

## 架构拆分

```
web-client (现有)          admin-console（新）
└── podi-design-web-dev    └── podi-admin-web
    ├── 登录 & 用户视角        ├── 管理员登录页
    └── /admin/* 移除          └── 仪表盘/导入/监控
```

| 层级 | 客户端 | 管理端 |
|------|--------|--------|
| 域名 | `app.podi.local` | `admin.podi.local` |
| 鉴权 | 用户 JWT / cookie | 管理员 token / SSO |
| API 访问 | `/api/tasks`, `/api/media`, ... | `/api/admin/**`（新增 header 校验） |

## 后端改造
1. 在 `Settings` 中新增 `ADMIN_API_TOKEN`，默认 `admin-dev-token`。
2. 新建 `app/deps/admin_auth.py`，校验 `X-Admin-Token` 请求头。
3. `admin_integrations` 路由统一 `Depends(require_admin)`，未来可扩展为基于用户体系的 `AdminUser`。
4. 后续扩展：
   - 增加管理员审计日志（记录每次 CRUD）。
   - Admin 登录 API（账号+密码/OIDC）发放短期 token，替换当前固定 token。

## 前端改造（admin-console）

### 目录
```
podi-admin-web/
├── src/
│   ├── App.tsx
│   ├── main.tsx
│   ├── components/LoginGate.tsx   # 输入 token，存入 localStorage
│   ├── pages/IntegrationDashboard.tsx
│   └── services/adminApi.ts       # fetch + X-Admin-Token
├── vite.config.ts
├── package.json
└── README.md
```

### 功能
1. **登录门控**：首次访问要求输入管理员 token，保存在 `localStorage`（仅供开发阶段使用）。
2. **仪表页**：延续原先的执行器/工作流/绑定/API Key CRUD，但移除依赖客户端 UI 库，采用轻量组件。
3. **工作流导入**：新增 “导入 JSON” 按钮，支持粘贴或上传 `.json`，自动解析填充 Form，再提交给后端。
4. **环境配置**：通过 `VITE_API_BASE_URL` 指向后台，默认 `http://localhost:8099`.

### 后续路线
| 阶段 | 内容 |
|------|------|
| P0 | 独立项目 + Token 登录 + 基础 CRUD |
| P1 | 工作流文件导入校验 + 节点健康监控 + API Key 使用图表 |
| P2 | 接入企业 SSO / RBAC + 操作审计 + 多租户配置 |

## 运维与部署
1. Admin 前端独立打包（`npm run build`）后部署到 `admin.podi.local` 或另一个 bucket。
2. API 通过 Nginx 拦截 `/api/admin/**`，注入或校验 `X-Admin-Token`，并限制仅内网可访问。
3. 记录待办：为 ComfyUI 工作流导入提供专属 OSS bucket（仅管理员可写），方便做版本备份。
