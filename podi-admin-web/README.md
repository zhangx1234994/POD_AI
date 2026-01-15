# PODI Admin Console

独立的管理端前端项目，负责维护 AI 执行器、工作流、绑定策略与 API Key。

## 开发

```bash
cd podi-admin-web
npm install
npm run dev -- --host 0.0.0.0 --port 8199
```

默认代理到 `http://localhost:8099`，可通过 `.env` or `VITE_API_BASE_URL` 覆盖。

## 登录

当前版本使用统一账号体系：

1. 确保后端已创建管理员用户（默认示例：`admin / Admin123`）
2. 登录页输入用户名/密码获取 `accessToken` 与 `refreshToken`
3. 所有 `/api/admin/**` 请求自动携带 `Authorization: Bearer ...`

## TODO

- 接入企业 SSO，替换 token 输入
- 增加节点健康监控、工作流一键部署
- 支持 ComfyUI 工作流版本对比与日志审计
