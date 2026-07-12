# 业务端静态发布与版本一致性门禁

## 目标

业务端 Git 版本、构建产物和线上实际生效版本必须一致。任何一个环节不一致，都可能导致用户加载过期脚本、页面回退或功能异常。

## 发布顺序

1. 在待发布的 Git 提交上执行 `podi-client-web` 的 `npm run lint && npm run build`。
2. 同一次发布上传 `dist/index.html` 和 `dist/assets/` 到 `/srv/podi/prelaunch/static/client/`。
3. 更新 Nginx 时，`/etc/nginx/sites-available/podi-prelaunch` 与 `/etc/nginx/sites-enabled/podi-prelaunch` 的 SHA-256 必须一致；建议后续将 enabled 文件改为符号链接，禁止维护两份独立副本。
4. 备份 Nginx 配置只能放在 `/etc/nginx/` 等非 `sites-enabled` 目录。`sites-enabled/*` 会被 Nginx 全量加载，备份文件放入该目录会导致重复 server 配置。
5. 执行 `nginx -t` 后再 `systemctl reload nginx`。

## 缓存策略

- `index.html` 和所有 SPA 回退页必须返回 `Cache-Control: no-store, no-cache, must-revalidate`。
- `/assets/<hash>.*` 只能服务实际存在的构建文件；不存在时必须返回 `404`，绝不能返回 `index.html`。
- 已存在的哈希静态文件可使用 `Cache-Control: public, max-age=31536000, immutable`。

## 强制验收

每次发布后执行以下检查，并记录结果：

1. 请求首页，确认响应中的 JavaScript 文件名与刚构建的 `dist/index.html` 一致，且 HTML 响应不缓存。
2. 请求一个已淘汰的构建脚本，确认返回 `404`，而非 HTML。
3. 请求当前构建脚本，确认返回 `200` 和 immutable 缓存头。
4. 用真实浏览器访问当前入口、`/products` 和旧入口 `/products/design`；旧入口必须归一到当前路由，控制台不得出现错误。
5. 发布完成后将源码提交推送到 `main`。线上产物必须能追溯到该提交；未经 Git 提交的前端文件不得直接替换线上版本。

## 回滚

回滚只允许回到一个已验证的 Git 提交及其完整构建产物；同时恢复对应 Nginx 配置。禁止仅替换 `index.html` 或仅替换部分 `assets/`。
