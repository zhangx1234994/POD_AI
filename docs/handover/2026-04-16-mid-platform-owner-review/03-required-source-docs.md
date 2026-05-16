# 必读真源文档

改中台之前，先看真源，不允许凭记忆和猜测动手。

## 必读清单

### 1. 总入口

- `docs/README.md`
- 作用：明确当前有效文档、模块入口、哪些是历史资料

### 2. 接口总入口

- `docs/api/INDEX.md`
- 作用：找到模块接口文档，并确认接口变更必须同步哪些规范文档

### 3. Coze 工具箱

- `docs/coze/toolbox-inventory.md`
- 作用：确认当前工具箱清单、契约、字段口径与使用边界

### 4. ComfyUI

- `docs/comfyui/README.md`
- 作用：确认 Workflow、节点、执行节点、输出回填、常见问题

### 5. 评测端

- `docs/eval/eval-platform.md`
- 作用：确认评测端参数展示、测试流程、结果区口径

### 6. 错误契约

- `docs/standards/error-contract.md`
- 作用：确认错误返回结构、错误码分配、错误信息组织方式

### 7. 接口一致性

- `docs/standards/interface-consistency.md`
- 作用：确认状态词、错误处理、结果回填、跨端一致性原则

## 建议补读

- `docs/standards/error-catalog.md`
- `docs/api/abilities.md`
- `docs/admin/integration-dashboard.md`
- `docs/architecture.md`
- `docs/archive/202605/DEPLOYMENT.md`
- `docs/PLATFORM_SURFACES.md`

## 真源阅读后的最低输出

在任何中台任务开始前，至少要能说清 4 件事：

1. 当前问题或需求落在哪条主链路
2. 当前真源文档的现有口径是什么
3. 这次改动要动哪些代码与哪些文档
4. 哪些端和哪些外部系统可能被波及

说不清这 4 件事，不进入编码阶段。
