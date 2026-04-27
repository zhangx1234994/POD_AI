# 测评 Workflow 展示层规范

## 目标

- 把评测工作流的显示逻辑从前端猜测改成中台真源。
- 让业务侧看到的是“怎么用”，不是原始技术 metadata。
- 保持 public/admin/eval 三端对同一工作流的展示口径一致。

## 真源位置

- 数据库存储：`eval_workflow_version.metadata.presentation`
- 后端规范化输出：`/api/evals/workflow-versions`、`/api/admin/evals/workflow-versions` 的 `presentation`

## 当前字段

- `visible`
  - 是否在业务侧列表显示
- `sortOrder`
  - 列表排序值，数值越小越靠前
- `categoryLabel`
  - 当前业务分类标签
- `usageHint`
  - 给业务的简化使用提示
- `operationLabel`
  - 业务可理解的动作名称，例如“图像裂变”“抠图”“图像延伸”
- `variantLabel`
  - 业务可理解的版本/变体名称，例如“高质量新版”“ComfyUI 新版”“商业模型”
- `entryMode`
  - 输入模式：`single_image / multi_image / parameter_only / parameter_form`
- `resultMode`
  - 结果模式：`image / callback_image / structured_json / text / unknown`
- `supportsBatch`
  - 是否推荐进入批量评测
- `recommendedRepeatCount`
  - 推荐重复次数，主要用于裂变类工作流

## 目录治理字段

接口会额外返回顶层 `governance`，用于区分同一分类下的工作流角色：

- `role=production`：生产主入口，优先展示和推荐使用
- `role=candidate`：灰度/对照版本，用于和主线做结果对比
- `role=legacy`：历史保留，不建议作为新评测入口
- `role=auxiliary`：辅助工具，主要用于查询、监控、回调等内部场景
- `role=disabled`：已停用

前端排序必须优先按 `governance.rank`，再按 `presentation.sortOrder`。业务卡片必须展示 `roleLabel` 和 `roleReason`，避免一堆同名“图裂变”无法分辨。

## 原则

1. `metadata` 继续保留作内部配置，不直接要求前端解析。
2. 前端优先消费顶层 `presentation`，不要自己推断展示逻辑。
3. 业务提示统一由中台给出，减少客户端和测评端各写一套文案。
4. 评测列表的排序和隐藏规则以展示层真源为准。
5. 工作流目录角色以顶层 `governance` 为准，前端不得再用名称或 ID 自行判断生产/灰度/历史。
