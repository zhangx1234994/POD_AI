# 文档清理盘点（2026-04-30）

## 1. 本轮结论

本轮先做低风险治理，不批量删除历史文档。

原因：

- `docs/` 当前共有 223 份文档，其中不少是阶段方案、迁移记录、测试包和复盘材料。
- 大量文档仍有追溯价值，直接删除会丢失决策背景。
- 真正风险不是“文件多”，而是入口口径过期，让后续开发误把历史文档当当前事实。

本轮已先修正最容易误导的入口口径：

- 当前仓库已不包含客户端代码目录。
- `docs/client/` 只作为历史客户端资料入口。
- 当前开发主线是 `backend/`、`podi-admin-web/`、`podi-eval-web/`、`image-ops-service/`、`vendor-api-ops/`。
- `AGENTS.md` 已同步当前凭证、KIE dispatcher、火山模型同步与执行节点标签口径。

## 2. 文档分区

### 2.1 现行真源

优先维护这些文档：

- `docs/README.md`
- `docs/PLATFORM_SURFACES.md`
- `docs/strategy/README.md`
- `docs/strategy/todo-master-2026q2.md`
- `docs/architecture.md`
- `docs/BUSINESS_MODEL.md`
- `docs/api/INDEX.md`
- `docs/admin/integration-dashboard.md`
- `docs/eval/eval-platform.md`
- `docs/comfyui/README.md`
- `docs/coze/toolbox-inventory.md`
- `docs/standards/error-catalog.md`
- `docs/standards/error-contract.md`
- `docs/standards/interface-consistency.md`
- `docs/release-preflight.md`

### 2.2 历史资料

保留但不作为当前执行口径：

- `docs/client/`
- `docs/handover/`
- `docs/plans/2026-04-16-experience-center-redesign/`
- `docs/project-takeover-prep-2026-03-12.md`
- `docs/TODO_PLATFORM.md`
- `docs/COMPONENT_INTERACTIONS.md`

### 2.3 测试与过程记录

保留用于追溯和回归：

- `docs/testing/`
- `docs/retrospectives/`
- `docs/weekly/`
- `docs/coze/*2026-04-24*`
- `docs/strategy/*migration*`

### 2.4 草案

默认不可作为执行依据：

- `docs/wip/`

## 3. 后续清理规则

后续清理按三步执行：

1. 入口先行：先修 `docs/README.md`、模块 `README.md`、`docs/strategy/README.md`。
2. 标记状态：历史文档先在入口中标明身份，不直接删除。
3. 再做归档：确认 30 天无引用且已有替代文档后，再移动到 `docs/archive/YYYYMM/`。

## 4. 当前待处理脏点

### P0

- 文档入口已经修正客户端当前状态，但深层历史文档仍大量引用旧客户端目录。
- `docs/CREDENTIALS.md` 已改为去敏配置清单；真实凭证只能放环境变量、密钥系统或本地忽略文件。
- 根目录 `AGENTS.md` 已清理过期 TODO，不再把已完成能力当作待办。
- `docs/project-takeover-prep-2026-03-12.md` 已补历史文档提示，并校正凭证与执行节点标签路由口径。
- `docs/client/tech-review-2026-04-16/README.md` 已补齐，避免客户端历史评审入口断链。
- `docs/handover/README.md` 已补齐，明确交接资料默认是历史参考，旧客户端内容不能当当前事实。
- `AGENTS.md` 的“休假前暂停点”已替换为当前唯一待办池与恢复工作顺序。

### P1

- `docs/client/` 入口已改为历史归档口径；深层历史正文仍保留原始语境，后续按需压缩。
- `docs/handover/` 和 `docs/client/tech-review-2026-04-16/` 仍有大量重复正文，可后续继续压缩到周报或历史索引。
- `docs/plans/2026-04-16-experience-center-redesign/` 文件较多，应确认是否仍有当前价值。

### P2

- `docs/BUSINESS_MODEL.md`、`docs/COZE_INTEGRATION_GUIDE.md` 篇幅较长，后续可拆成当前摘要和历史附录。
- 旧的 mock、dev server、临时测试说明需要逐步从主入口移出。

## 5. 验收标准

一轮文档清理算完成，需要满足：

- 新同学从 `docs/README.md` 进入，不会把历史客户端资料当当前代码。
- 每个现行模块都有明确入口。
- 历史资料保留但不出现在“现行真源”列表。
- 发布前检查仍能通过，无 AppleDouble、无 Alembic 多 head、无未解释的临时产物。

*最后更新: 2026-04-30*
