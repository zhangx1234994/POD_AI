# 统一术语表（中台内核 vs 用户表面）

## 1. 使用原则

后续所有页面、文档、Coze 工具、客户端文案都遵守 3 条规则：

1. 对内保留技术名
2. 对外只讲业务动作
3. 厂商名和模型名默认不放到主标题

也就是说：

- 工程内部可以继续使用 `ability / workflow / executor / binding`
- 用户表面不直接暴露这些词

## 2. 核心术语映射

| 对内术语 | 对外术语 | 说明 |
| --- | --- | --- |
| ability | 工具 | 用户真正使用的是工具，不是能力对象 |
| workflow | 内部流程 | 默认隐藏，不作为用户主对象 |
| binding | 流程绑定 | 默认隐藏，仅内部配置可见 |
| executor | 执行节点 | 默认隐藏，仅管理端高级视图可见 |
| task | 任务 | 用户可见，但要用业务状态表达 |
| asset | 素材 / 结果 | 按上下文选词，不强制统一成单一技术词 |
| input_schema | 输入项配置 | 对用户不说 schema |
| metadata | 展示配置 / 系统信息 | 用户不直接看到 metadata 这个词 |
| provider | 服务来源 | 默认隐藏，必要时放在次级信息 |
| model_id | 模型版本 | 默认隐藏，必要时放在高级信息 |
| callback | 结果回传 | 用户不需要感知 callback |
| invocation | 调用记录 | 内部追踪词，不进用户主页面 |

## 3. 禁止直接外露的词

以下词默认不应直接出现在客户端主路径、首页标题、Coze 工具主标题中：

- executor
- binding
- workflow
- schema
- callback
- metadata
- provider
- model_id
- capability_key
- queue policy
- output node
- seed version

这些词如果必须出现，只能出现在：

- 管理端高级配置
- 评测端开发接入
- 运维/排障文档

## 4. 推荐对外表达

### 4.1 设计类

| 当前常见表达 | 推荐表达 |
| --- | --- |
| 文生图 | 以文生款 |
| 图生图 | 以款生款 / 参考改款 |
| 多图融合 | 融合创款 / 图案融合 |
| ComfyUI 四方连续 | 四方连续 |
| 印花提取 Workflow | 图案提取 |

### 4.2 商拍类

| 当前常见表达 | 推荐表达 |
| --- | --- |
| Nano Banana 2 图生图 | 裂变套图 / 上身展示 / 背景替换 |
| Seedance 图生视频 | 图生视频 |
| 中速提质版 | 服装精修 |
| quality_upgrade | 细节图 / AI 超清 |

### 4.3 工具类

| 当前常见表达 | 推荐表达 |
| --- | --- |
| quality_upgrade | AI超清 |
| upscale_resize | 高质量缩放 |
| set_dpi | DPI 处理 |
| huawen_kuotu | AI扩图 |
| expand_mask_color | 扩边占位图（仅内部） |

## 5. 高频能力对照表

| 路径 | abilityKey | 当前显示名 | 推荐对外名 | 一级场景 |
| --- | --- | --- | --- | --- |
| `/design/text-to-style` | `doubao_seedream_4_5` | 火山 · Doubao Seedream 4.5 | 以文生款 | 新款设计 |
| `/design/style-to-style` | `nano_banana_pro_image_to_image` | KIE · Nano Banana Pro 图生图 | 以款生款 | 新款设计 |
| `/design/fusion` | `duotu_ronghe` | ComfyUI · 多图融合 | 融合创款 | 新款设计 |
| `/design/pattern-extract` | `yinhua_tiqu` | ComfyUI · 印花提取 | 图案提取 | 图案设计 |
| `/design/seamless` | `sifang_lianxu` | ComfyUI · 四方连续 | 四方连续 | 图案设计 |
| `/shoot/marketing-variants` | `nano_banana_2_image_to_image` | KIE · Nano Banana 2 图生图 | 裂变套图 | 视觉商拍 |
| `/shoot/detail-shots` | `quality_upgrade` | 百度 · 无损放大 | 细节图 | 视觉商拍 |
| `/shoot/image-to-video` | `doubao_seedance_1_5_pro` | 火山 · Doubao Seedance 1.5 Pro | 图生视频 | 视觉商拍 |
| `/toolbox/upscale` | `quality_upgrade` | 百度 · 无损放大 | AI超清 | 终稿处理 |
| `/toolbox/outpaint` | `huawen_kuotu` | ComfyUI · 花纹扩图 | AI扩图 | 终稿处理 |
| `/toolbox/lossless-zoom` | `upscale_resize` | PODI · 高质量缩放 | 高质量缩放 | 终稿处理 |
| `/toolbox/dpi` | `set_dpi` | PODI · 设置 DPI | DPI处理 | 终稿处理 |

## 6. 厂商名使用规则

厂商名不是不能出现，而是不能主导用户判断。

建议规则：

1. 客户端标题默认不带厂商名
2. Coze 工具主标题默认不带厂商名
3. 管理端能力详情可展示厂商名
4. 评测端和开发接入页可展示完整厂商/模型信息

推荐格式：

- 主标题：`图案提取`
- 次级说明：`当前默认走 ComfyUI 工作流`

而不是：

- 主标题：`ComfyUI · 印花提取`

## 7. 状态词统一建议

用户面建议只保留：

- 排队中
- 处理中
- 已完成
- 失败
- 可继续

不要在用户面直接展示：

- pending
- running
- success
- callback_received
- dispatched
- polling

这些内部状态应在系统里继续存在，但不要直接主导用户界面。

## 8. 一句话要求

以后任何新能力如果不能回答：

- 用户面叫什么
- 属于哪个场景
- 做完之后下一步去哪

那它就还只是技术能力，不算产品能力。
