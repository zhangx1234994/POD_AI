# 管理端 + 测评端 UI/UX 回归报告（2026-02-25）

## 本轮范围
- 主战场：`podi-eval-web`（信息架构 + 视觉层级 + 交互顺滑度）。
- 管理端：完成一轮导航清晰化改造（搜索、单入口切换、上下模块跳转），其余模块结构暂不重写。
- 后端接口：未改动任何 `/api/*` 合约。

## 已覆盖清单
- 测评端导航语义统一：顶部主导航 + 条件侧栏（仅 home/tool 显示分类侧栏）。
- 测评端首页重构：Hero 轻量化 + 功能卡片网格主导 + ActionBar 高频入口。
- 工具页历史区交互优化：FilterBar 统一筛选器入口（状态/评分/未打分/关键词）。
- 状态视觉统一：`UnifiedStatus + mapStatusToBadge + StatusBadge` 覆盖 queued/running/succeeded/failed/cancelled。
- 视觉 token 扩展：`surface/panel/accent/success/warning/danger/info` 语义变量补齐。
- URL 状态同步保留：`?view=&category=&tool=` 支持刷新恢复与分享定位。
- 文档沉淀：新增 `docs/frontend/eval-interaction-principles.md`，固化交互理念与页面状态矩阵。
- 管理端导航体验优化：侧栏支持模块搜索、顶部支持单入口下拉切换，ActionBar 改为“当前模块语义 + 上下模块”。
- 管理端视觉回归：已补 `overview/executors` 两页截图基线并通过。

## 已覆盖错误场景
- API 不可达（503）：壳层可用，页面可显示错误提示。
- URL 参数异常：回退默认视图与默认分类。
- 单条运行失败：历史行内保留错误消息，评分/备注流程不阻断其他记录。
- 管理端 API 不可达（503）：登录后壳层可用，overview/executors 能稳定渲染 warning 状态。

## 本轮未覆盖风险
- 尚未完成“每页 default/loading/empty/error/success/disabled/dialog-open”全自动截图矩阵。
- LoRA 批测大样本（高并发 + 大文件）下的前端性能与节流策略未压测。
- 未接入 Figma 节点 1:1 对照，当前为“高保真实现 + 可对齐底座”。
- 管理端目前仅覆盖 2 个导航页视觉基线，尚未覆盖 13 个模块全量状态矩阵。

## 建议下一步
1. 扩展 Playwright 基线到 6 个视图并按状态拆场景（default/loading/empty/error）。
2. 增加关键错误路径 mock：缺参 / 依赖失败 / 并发限制 / 超时。
3. 管理端补齐 13 模块截图与关键弹窗状态（含高级模块开关场景）。
4. 收到 Figma 节点后执行 MCP 对照精修并输出像素偏差清单。
