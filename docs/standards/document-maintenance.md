# 文档维护规范

本规范用于统一项目文档的维护方式，避免“文档越来越多，但没人知道该看哪份”。

## 1. 文档分层

所有文档按 5 层理解：

1. **现行真源**
   - 当前执行口径
   - 决策、接口、契约、边界都以此为准
2. **模块入口**
   - 带路文档
   - 负责说明该模块该看什么、当前状态是什么
3. **阶段记录 / 历史基线**
   - 记录当时方案、测试包、旧阶段结论
   - 保留用于追溯，不直接指导当前实现
4. **草案 / WIP**
   - 未定稿，不可直接当作执行依据
5. **周报归档**
   - 用于吸收零散过程记录
   - 负责按周汇总“本周做了什么、结论是什么、来源文件有哪些”

## 2. 现行真源最小集合

以下文档应始终保持可用：

- `docs/README.md`
- `docs/api/INDEX.md`
- `docs/eval/eval-platform.md`
- `docs/coze/toolbox-inventory.md`
- `docs/comfyui/README.md`
- `docs/strategy/README.md`
- `docs/weekly/README.md`
- `docs/standards/error-catalog.md`
- `docs/standards/error-contract.md`
- `docs/standards/interface-consistency.md`
- `docs/standards/delivery-methodology.md`

## 3. 每次开发后的最小同步要求

发生以下变更时，必须同步更新文档：

### 3.1 新增功能 / 新工作流 / 新工具箱

至少更新：

- 对应模块入口文档
- 接口模块文档
- 若涉及 Coze / ComfyUI，则同步更新 `toolbox-inventory` 或 `comfyui/README`

### 3.2 参数、状态词、错误码变化

至少更新：

- `docs/api/modules/*.md`
- `docs/standards/error-catalog.md`
- `docs/standards/error-contract.md`
- `docs/standards/interface-consistency.md`

### 3.3 结构调整 / 口径变化

至少更新：

- `docs/README.md`
- 对应模块入口文档
- 如属平台级变化，再更新 `docs/strategy/README.md` 和相关真源

### 3.4 核心文档定期整理

涉及平台边界、能力定义、Agent、路由、客户端/中台职责、错误契约或发版门禁的结论，不允许只停留在聊天记录里。

每轮重要讨论或开发结束后，至少检查：

- `docs/README.md`
- `docs/strategy/README.md`
- `docs/strategy/todo-master-2026q2.md`
- 当前主题真源，例如 `ability-definition-v0.6.md`、`business-agent-runtime-v0.6.md`
- 涉及接口时同步 `docs/api/INDEX.md`、错误码总表和接口一致性规范

整理规则：

1. 短期过程写入唯一 TODO 或测试记录。
2. 长期口径提炼进真源文档。
3. 入口索引只保留“现在该看什么”，不堆过程。
4. 如果新结论推翻旧方案，必须在旧文档开头标注历史或迁移状态。
5. 封版或发版前必须复查核心入口，避免代码已经变了但文档仍指向旧主线。

## 4. 索引文档写法

索引文档只做三件事：

1. 说明当前该看什么
2. 标注哪些是历史资料
3. 指向更细的模块文档

索引文档不要堆：

- 大段设计过程
- 重复接口细节
- 已过时的长列表

## 4.1 过程文档处理方式

零散过程文档默认不再直接堆进主索引。更推荐：

1. 先把本周过程沉淀进 `docs/weekly/YYYY-Wxx.md`
2. 再把真正长期有效的结论提炼进模块入口或真源文档
3. 原始过程文档只保留回溯价值，不再直接作为主入口阅读对象

## 5. 历史文档处理规则

历史文档默认不删除，但要满足：

1. 仍有回溯价值
2. 不会误导当前开发
3. 已在入口文档中被标明“历史 / 阶段记录”

如果一份文档既旧又无回溯价值，应考虑归档或移出主索引。

### 5.1 历史路径与断链规则

历史文档可以保留已经移除的目录名或旧路径，但必须满足：

1. 文档入口明确说明该路径已移除或只作为历史引用。
2. 不把已移除路径放在“现行真源”或“当前代码位置”里。
3. 自动断链检查时，`podi-client-web/`、`podi-client-v2/`、`podi-design-web-dev/` 这类已移除客户端目录只能作为历史引用白名单处理。
4. `docs/CREDENTIALS.local.md` 是本地忽略文件，可以在规范中引用，但不能要求它存在于仓库。

如果某个历史路径重新启用，必须先更新 `docs/README.md`、对应模块入口和 `AGENTS.md`，再把它移出历史引用白名单。

入口文档的本地路径引用由 `scripts/check_doc_entry_references.py` 检查，并已接入 `scripts/release_source_preflight.sh`。检查范围覆盖总索引、平台边界、架构、业务模型、API、管理端、评测端、Coze、ComfyUI、测试、周报和历史客户端入口。新增入口文档或新增历史白名单时，必须同步更新脚本。

## 6. 命名建议

- 平台入口：`README.md`
- 模块入口：模块目录下 `README.md`
- 决策类：`<topic>-decision-YYYYqN.md`
- 路线类：`<topic>-roadmap.md`
- 阶段计划：`YYYY-MM-DD-<topic>-<plan>.md`
- 复盘类：按日期命名

## 7. 整理优先级

做文档整理时，顺序固定：

1. 总索引 `docs/README.md`
2. 模块索引 `docs/api/INDEX.md`、`docs/strategy/README.md`、对应现行模块入口；若涉及历史客户端资料，再更新 `docs/client/README.md`
3. 周报归档 `docs/weekly/README.md`
4. 当前真源文档
5. 历史资料与阶段记录

## 8. 当前执行原则

文档不是为了“全”，而是为了“准”和“好找”。

判断一轮整理是否有效，只看三件事：

1. 新同学能否在 5 分钟内找到当前有效文档
2. 开发同学能否快速知道参数和口径该看哪份
3. 历史资料是否还能保留，而又不误导当前判断

## 9. 发版与更新信号准则

发版、更新服务器、通知运维时，只认远端 `origin/main`，不认本地脏工作区。

### 9.1 唯一发版真源

以下内容才可以作为“可更新”的依据：

1. 目标提交已经进入远端 `origin/main`
2. 服务端实际拉取的是 `main`
3. 若涉及前端服务，运行中的进程必须来自这份已更新目录

以下内容不能单独作为发版依据：

1. 本地功能已经改好
2. 本地某个分支已有提交
3. 本地 `git log` 看得到目标 commit
4. 当前工作区里存在未提交改动或临时文件

### 9.2 更新信号规则

只有在同时满足以下条件时，才可以给出“现在可以更新服务器”的信号：

1. 已确认目标提交存在于 `origin/main`
2. 已确认本次更新需要的迁移、seed、重启步骤
3. 已明确更新范围：
   - backend
   - admin web
   - eval web
   - 其他服务

如果任一条件不满足，默认结论应是：

- 先不要更新服务器

### 9.3 脏工作区处理规则

当本地工作区同时存在以下情况时，禁止直接用它判断线上应该有什么：

1. 当前分支不是 `main`
2. 本地有未推送提交
3. 本地有大量未提交改动
4. 存在临时目录、截图、测试产物、可视化回归缓存

此时应先分清三件事：

1. `origin/main` 里到底有什么
2. 当前本地分支比 `origin/main` 多了什么
3. 当前工作区的未提交改动是什么

只有完成这一步，才能判断：

- 是代码没推上去
- 还是服务器没拉到最新 `main`
- 还是服务进程跑错了目录
