# 能力展示层规范

适用范围：`/api/abilities`、`/api/abilities/options`、管理端能力目录，以及未来所有直接面向业务用户的能力列表。

## 目标

能力展示层的作用是把中台内部治理概念翻译成业务能理解的语言，避免业务侧直接理解：

- `governance.scopes`
- `release_status`
- `route_policy`
- `quality_status`
- `routing.selection_policy`

这些字段继续保留在中台内部使用，但业务侧默认只看简化后的展示层。

## 真源位置

- 内部治理：`Ability.extra_metadata.governance`
- 路由真源：`Ability.extra_metadata.routing`
- 业务展示：`Ability.extra_metadata.presentation`

## 展示层字段

`presentation` 当前统一为：

- `visible`
- `sort_order`
- `category_label`
- `usage_hint`
- `operation_label`

字段含义：

- `visible`：是否建议在业务列表展示
- `sort_order`：业务列表排序值，数值越小越靠前
- `category_label`：给业务看的分类名称
- `usage_hint`：一句话使用提示
- `operation_label`：一句话动作名称，例如“图像扩展”“抠图”“图像裂变”

## 设计原则

1. 业务侧看到的是动作和结果，不是技术原因。
2. 展示层文案必须短、直接、可执行，不写中台术语。
3. 同一能力的展示层应由后端真源生成，不允许前端各写一套映射。
4. `businessStatus` 与 `presentation` 一起构成业务可见层：
   - `businessStatus` 负责“能不能用、稳不稳定”
   - `presentation` 负责“它是干什么的、该怎么用”

## 默认策略

若未显式配置 `presentation`，后端应自动推导：

- `visible`：默认随能力状态为 `active`
- `sort_order`：按能力大类分桶
- `category_label`：按能力大类映射到业务名称
- `usage_hint`：按 provider / ability_type / governance scopes 推导
- `operation_label`：按 capability key 和 category 关键词推导

## 禁止事项

1. 不允许前端写死能力业务文案映射作为唯一来源。
2. 不允许把 `routing_policy`、`fallback_to_default`、`required_executor_tags` 直接展示给业务用户。
3. 不允许用展示层字段替代中台内部治理字段；两层职责不同。

## 与下线规则的关系

- 展示层只负责“业务怎么理解这个能力”。
- 是否继续公开暴露，由 `metadata.deprecation` 与 `governance.release_status` 共同决定。
- 一旦能力进入 `deprecated`，且下线模式为 `hide_public/internal_only/delete_candidate`，公共能力列表必须自动隐藏，不能继续依赖前端手工过滤。
