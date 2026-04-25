# 能力展示层约定

目标：在**不改接口路径、不改执行链路、不破坏现有业务兼容**的前提下，把底层能力对象翻译成更适合用户理解的表现层。

## 原则

1. 调度层对象继续保留：`ability / workflow / executor / binding / task`
2. 用户侧优先展示业务语言：`工具 / 模板 / 任务 / 结果 / 下一步`
3. 展示层配置只做增量，不删除旧字段
4. 没有展示层配置时，前端与 Coze 出口必须回退到旧逻辑

## 当前兼容做法

公共能力接口 `GET /api/abilities` 允许额外返回：

- `presentation.name`
- `presentation.summary`
- `presentation.formIntro`
- `presentation.expectedOutput`

同时会对 `inputSchema.fields[*]` 做用户侧清洗：

- 优先保留中文标签
- 隐藏纯技术节点提示（如 `节点 111 · ...`）
- 将明显技术参数标记为 `advanced=true`

这些变化都是**向后兼容**的：

- 不改原有字段名
- 不改入参结构
- 不影响旧客户端继续读取 `displayName / inputSchema / metadata`

## metadata 增量约定

能力可在 `metadata.presentation` 下补充用户侧展示配置：

```json
{
  "presentation": {
    "summary": "适合先出方向稿。",
    "formIntro": "先写清楚你想要的风格、品类和重点。",
    "expectedOutput": "会先返回可继续修改的方向图。",
    "fields": {
      "prompt": {
        "label": "创作说明",
        "placeholder": "描述你这次要生成什么",
        "description": "一句话说清楚风格、主体和重点",
        "advanced": false
      },
      "seed": {
        "advanced": true
      }
    }
  }
}
```

## 适用范围

- 客户端工作台
- Coze 工具 OpenAPI 描述
- 未来的轻量业务前台

管理端高级配置页不强制使用该展示层，避免损失技术可维护性。
