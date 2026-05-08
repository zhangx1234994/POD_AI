# 2026-05-09 管理端候选版本交付清单

## 1. 本次候选版本范围

本次候选版本只包含管理端产品化和文档记录，不改业务执行链路、ComfyUI 路由、第三方 API 执行面或测评端工作流契约。

本地 `main` 相对 `origin/main` 多 10 个提交：

- `ccdb09e7` 管理端通用操作闭环组件
- `d3e1bd15` 模型弹药库、运行线路闭环说明
- `d466b8cd` 能力评测、ComfyUI 资源闭环说明
- `acbb6110` 账号权限、账单框架闭环说明
- `ffd8eb83` 调度监控、系统配置闭环说明
- `64e3e5d0` 高级编排、调度事件闭环说明
- `573230ce` 历史密钥、路由策略闭环说明
- `e8e5dc94` API 开放页业务方开通前检查
- `c3dd1fe8` 管理端 10 个入口候选页面走查记录
- `58d1a8ee` 候选版本本地回归记录

## 2. 本地已验证

- 后端全量测试：`468 passed, 24 warnings`
- 管理端构建：`podi-admin-web npm run build` 通过
- 测评端类型检查和构建：`podi-eval-web npm run lint`、`npm run build` 通过，未出现 Vite 大包体警告
- 文档入口检查：`python3 scripts/check_doc_entry_references.py` 通过
- Alembic 单 head：`20260504_add_package_catalogs`
- 管理端 10 个入口本地浏览器走查通过，控制台 error/warning 为 0
- 临时产物已清理，`git diff --check` 通过

## 3. 需要更新的服务器

首轮只需要更新 Coze / 中台主机：

- `114.55.0.56`
- 服务范围：backend 可按现有 SOP 更新并重启；管理端 `8199` 必须重新构建静态产物；测评端 `8200` 可随标准发布流程一起构建验证

不需要更新能力服务器：

- `117.50.80.158`
- `117.50.216.233`

原因：本次没有修改 `image-ops-service`、`vendor-api-ops`、ComfyUI 工作流、执行节点配置或第三方执行适配。

## 4. 线上更新后必须验证

1. 管理端登录
- 账号：`admin`
- 密码：`admin123`
- 验证：`8199` 能登录，页面不是旧版本缓存。

2. 管理端关键入口
- `#nav=overview`：可见“运营驾驶舱”和“当前结论”
- `#nav=api-exposure`：可见“业务方开通前检查”
- `#nav=business`：可见“三主业务当前结论”
- `#nav=ability-logs`：可见“能力调用排障总览”
- `#nav=comfyui-management&comfyTab=tasks`：可见“任务衔接诊断”和“真实命中”
- `#nav=bindings`：可见“路由策略闭环”

3. 后端基础链路
- `/health` 返回正常
- `/api/business/openapi.json` 可访问
- `/api/abilities` 可访问
- `/api/coze/podi/openapi.json` 可访问

4. 业务链路 smoke
- 运行轻量发布 smoke，确认 Coze 工具箱没有 `INTERNAL_ONLY`
- 至少跑三主业务 route-preview，不消耗真实生图额度
- 如业务窗口允许，再跑花纹提取、图裂变、扩图各 1 条真实巡检

## 5. 回滚口径

如果 114 更新后管理端无法访问或页面明显异常：

1. 先回滚 114 上的前端静态产物或切回上一版 commit
2. backend 没有本次业务逻辑变更，优先不要动数据库
3. Coze 工具箱和 117/233 能力服务不需要回滚

