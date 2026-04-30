# 发布前回归记录（2026-04-30）

## 1. 本轮范围

本轮用于验证文档治理、发布门禁、管理端与测评端构建是否仍满足阶段性上线条件。

覆盖范围：

- 后端自动化测试
- 管理端类型检查与生产构建
- 测评端生产构建
- 发布源预检
- 工作区脏文件检查

未覆盖范围：

- 线上 Coze 工作流真实提交
- 线上 ComfyUI 队列压测
- KIE 余额恢复后的商业模型真实回归
- 前端页面重构后的视觉验收

## 2. 执行结果

| 项目 | 命令 | 结果 |
| --- | --- | --- |
| 后端单测 | `python3 -m pytest backend/tests -q` | 通过：316 passed, 14 warnings |
| 管理端类型检查 | `npm run lint` in `podi-admin-web` | 通过 |
| 管理端生产构建 | `npm run build` in `podi-admin-web` | 通过 |
| 测评端生产构建 | `npm run build` in `podi-eval-web` | 通过，有既有 Vite 大包体警告 |
| 发布源预检 | `ALLOW_DIRTY=1 CHECK_GIT_SYNC=0 bash scripts/release_source_preflight.sh` | 通过：PASS=4 WARN=0 FAIL=0 |

## 3. 观察到的问题

### 3.1 后端告警

后端测试通过，但仍有既有 Pydantic/FastAPI deprecation warning：

- `Field(..., env=...)` 在 Pydantic V2 中已弃用。
- class-based `Config` 在 Pydantic V2 中已弃用。
- FastAPI `on_event` 已建议迁移到 lifespan。
- 少量 Pydantic alias 使用方式告警。

这些不是本轮阻断项，但需要在依赖升级前纳入技术债处理。

### 3.2 前端大包体

测评端构建通过，但仍有 Vite chunk size warning。该问题本轮不阻断上线，已按约定放入后续前端整体整改阶段统一处理。

管理端构建通过，当前最大块主要来自 `IntegrationDashboard`、`storage-vendor`、TDesign 等模块，后续前端整改阶段需要结合路由拆包和模块懒加载治理。

## 4. 当前上线判断

从本地自动化与构建结果看，当前版本满足“代码层和构建层可继续推进”的最低条件。

正式更新服务器前仍需确认：

- 目标提交已经推送到 `origin/main`。
- 114 / 117 对应服务按本轮变更范围更新。
- 更新后执行线上 smoke，至少覆盖 backend health、Coze toolbox OpenAPI、`tasks/get`、管理端页面、测评端首页。
- KIE 余额问题如果仍未恢复，相关商业模型失败需要继续标为已知非阻断风险。

## 5. 前端整改安排

前端整体整改不插入当前版本。建议节奏：

1. 当前版本先完成文档治理、发布门禁、回归记录和线上更新。
2. 下一轮先产出前端整改方案，不直接大改代码。
3. 改造顺序固定为：管理端 -> 测评端 -> 客户端。
4. 管理端优先处理信息架构、页面分组、用户主路径、文案口径、Vite 大包体。
5. 测评端等管理端结构稳定后再统一整理工作流卡片、功能分组、评测操作路径。

*记录时间: 2026-04-30*
