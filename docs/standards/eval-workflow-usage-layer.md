# Eval Workflow Usage Layer

本规范定义评测 workflow 的“使用方式真源”，目标是让前端不再根据字段名、资源绑定、分类自己猜业务入口。

## 真源位置

- 数据存储：`EvalWorkflowVersion.metadata.usage`
- 对外响应：`EvalWorkflowVersionResponse.usage`
- 规则实现：`backend/app/services/eval_workflow_usage.py`

## 字段定义

### `single_run_enabled`

- 含义：是否支持普通单次发起
- 类型：`boolean`
- 默认：`true`

### `batch_enabled`

- 含义：是否适合进入批测/重复执行入口
- 类型：`boolean`
- 默认推导：
  - `presentation.supports_batch = true`
  - 或存在 `count` 字段
  - 或存在 `lora` 字段
  - 或分类属于 `图裂变 / 花纹提取类 / 四方/两方连续图类`

### `docs_enabled`

- 含义：是否建议在前端展示接口/使用说明入口
- 类型：`boolean`
- 默认：`true`

### `recommended_entry`

- 含义：业务默认入口，不要求前端再自行决策
- 类型：`string`
- 可选值（当前基线）：
  - `lora_batch`
  - `resource_form`
  - `single_image`
  - `parameter_form`
  - `direct_run`

### `supports_annotation`

- 含义：结果是否适合直接进入人工标注/打分
- 类型：`boolean`
- 默认推导：
  - `presentation.result_mode in {"image", "callback_image"}`

### `requires_resource_options`

- 含义：是否依赖资源目录（LoRA / model / plugin）下拉数据
- 类型：`boolean`
- 默认推导：
  - 参数 schema 中存在 `resourceType`
  - 或字段名可识别为 `lora / model / plugin`

### `resource_option_types`

- 含义：当前 workflow 依赖的资源目录类型列表
- 类型：`string[]`
- 当前支持：
  - `lora`
  - `model`
  - `plugin`

## 原则

1. 前端不能再用“字段名碰巧叫 `lora` / `count`”去推断业务入口。
2. `usage` 描述的是业务推荐方式，不是执行器内部细节。
3. 若 workflow 需要特殊入口，优先写进 `metadata.usage`，不要在前端加散乱白名单。
4. `presentation` 负责展示，`usage` 负责怎么用，两者不要混在一起。
