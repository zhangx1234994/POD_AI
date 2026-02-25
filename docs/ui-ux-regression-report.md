# 管理端 + 测评端 UI/UX 回归报告（阶段性）

## 已覆盖
- 管理端统一壳层（侧栏/头部/内容）与主题变量接入。
- 管理端 URL 导航同步：`#nav=<section>`。
- 测评端统一壳层（顶栏 Tabs + 左侧分类）与主题变量接入。
- 测评端 URL 导航同步：`?view=&category=&tool=`。
- 两端状态标签统一映射（`mapStatusToBadge` + `StatusBadge`）。
- 新增 Playwright 截图回归基线配置与 smoke 用例（admin/eval 各 2 条）。

## 已覆盖错误路径
- API 不可达（503）时壳层可用与错误提示。
- URL 参数异常时回退默认页面（overview/home）。

## 未覆盖风险
- 未完成 13 个管理端导航页 + 6 个测评端视图的全量截图基线。
- 未完成真实后端联调态（缺参/超时/并发限制）的逐场景自动化。
- 暂无 Figma 节点，尚未执行 1:1 像素对照。

## 下一步建议
1. 补齐全导航截图基线（default/loading/empty/error）。
2. 为关键流程补 API mock 场景矩阵（缺参/依赖失败/并发限制/超时）。
3. 收到 Figma node-id 后逐页对照并输出偏差清单。
