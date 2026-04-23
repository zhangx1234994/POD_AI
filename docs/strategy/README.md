# 战略工作区（唯一真源）

本目录只负责平台级方向、执行优先级和治理规则，不承载接口细节或模块级实现说明。

## 文档清单

- `platform-vision-and-goals-2026.md`：平台愿景与核心目标（中台 / 测评端 / 客户端 / 对话式助手统一叙事）
- `strategy-one-page-2026q2.md`：战略一页纸（北极星、KPI、90天里程碑）
- `todo-master-2026q2.md`：唯一待办池（P0/P1/P2）
- `context-cleanup-policy.md`：上下文清理、归档与文档治理规则
- `doc-governance-owners-2026q2.md`：文档治理 owner 与发布前核对动作
- `status-error-audit-2026q2.md`：状态与错误口径核对表（P0-4 执行面）
- `auth-scheme-decision-2026q2.md`：认证方案选型结论（Q2）
- `auth-billing-implementation-checklist-2026q2.md`：认证与计费实施清单（开发顺序与门槛）
- `mid-platform-cleanup-decisions-2026q2.md`：已经真正落地到中台真源的清理/下线决定
- `coze-mid-platform-migration-v1.md`：Coze + 中台同机迁移方案、路由约束、回滚与 OSS 保留问题
- `coze-control-plane-migration-pack-v1.md`：当前迁移实施包总入口（文档、脚本、回滚路径一览）
- `coze-migration-config-matrix-v1.md`：Coze 控制面迁移时 backend / image-ops / executor 的配置矩阵
- `coze-host-cutover-sequence-v1.md`：Coze 迁移当天的 host 切换顺序与回滚顺序
- `coze-migration-inventory-v1.md`：Coze 控制面迁移的真实对象清单（host / toolbox / workflow / 文件级切换项）
- `coze-host-reference-phasing-v1.md`：迁移时哪些 host 引用首轮必须清、哪些允许保留到第二阶段
- `coze-desktop-centerurl-cutover-v1.md`：桌面端 `CenterUrl` 的第二阶段切换方案
- `coze-server-layout-v1.md`：Coze 主机目录、systemd 服务名、日志与端口约定
- `image-ops-service-split-v1.md`：自研图片原子能力拆分方案（高清放大 / DPI / 扩边占位图）
- `weekly-review-template.md`：每周回顾模板（目标/待办/文档治理）

## 使用规则

1. 所有战略级新增任务，必须先登记到 `todo-master-2026q2.md`。
2. 状态只允许：`todo / doing / blocked / done / archived`。
3. 已归档内容不得回写主文档，只允许在归档文档追加说明。
4. 每周至少一次回顾：目标偏差、任务偏差、文档偏差。

## 与旧文档关系

- `docs/TODO_PLATFORM.md` 作为历史路线图保留，不再作为新增任务入口。
- 既有架构文档（如 `docs/architecture.md`、`docs/BUSINESS_MODEL.md`）继续保留为背景材料。
- 客户端竞品对标和测试包文档继续保留，但平台级方向请优先以 `platform-vision-and-goals-2026.md` 与 `strategy-one-page-2026q2.md` 为准。

## 维护原则

1. 战略级新增任务，先写入 `todo-master-2026q2.md`。
2. 若战略变化影响平台边界或对外叙事，需同步：
   - `docs/README.md`
   - `docs/PLATFORM_SURFACES.md`
   - `docs/BUSINESS_MODEL.md`
3. 旧战略材料可以保留，但不应继续作为索引入口。

*最后更新: 2026-03-19*
