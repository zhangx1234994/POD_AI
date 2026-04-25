# 多端暴露矩阵

## 1. 目标

明确每个能力应该出现在哪些端，避免：

- 内部能力过早进入客户端
- 同一能力在不同端口径漂移
- Coze 工具箱暴露过多技术细节

## 2. 暴露级别

| 标记 | 含义 | 适用场景 |
| --- | --- | --- |
| `internal_only` | 仅内部可见 | 占位工具、调试工具、辅助处理 |
| `admin_and_eval` | 管理端与评测端可见 | 未产品化、待验证、需观察能力 |
| `client_enabled` | 客户端可见 | 已形成稳定用户动作的能力 |
| `coze_enabled` | Coze 可见 | 适合 Agent/流程编排调用的能力 |
| `advanced_only` | 只在高级模式出现 | 参数多、风险高、理解成本高 |

说明：

- 一个能力可以同时拥有多个暴露属性
- `client_enabled` 不等于必须 `coze_enabled`
- `coze_enabled` 不等于必须进入普通客户端

## 3. 各表面应看见什么

### 3.1 客户端

应看见：

- 高价值、高频、用户能理解的工具
- 已经有稳定结果和下一步链路的能力

不应默认看见：

- 调试型工具
- 占位工具
- 仅适合技术同学的参数查询工具
- 尚未完成产品命名的能力

### 3.2 Coze

应看见：

- 业务动作明确
- 入参相对稳定
- 输出可预测
- 适合 Agent 串起来的能力

不应默认看见：

- 纯内部处理工具
- 需要强人工理解的实验能力
- 参数过多且未做对外翻译的能力

### 3.3 管理端

应看见：

- 全量能力
- 节点、workflow、binding 等内部对象
- 运行状态与日志追溯

### 3.4 评测端

应看见：

- 可验证、可回归、可比较的能力
- 参数、错误、证据、回归结果

## 4. 当前高频能力建议矩阵

| abilityKey | 对外名 | Client | Coze | Admin | Eval | 备注 |
| --- | --- | --- | --- | --- | --- | --- |
| `doubao_seedream_4_5` | 以文生款 | 是 | 否 | 是 | 是 | 当前更适合作为客户端工具，不急着直接放 Coze |
| `nano_banana_pro_image_to_image` | 以款生款 | 是 | 是 | 是 | 是 | 主路径能力 |
| `duotu_ronghe` | 融合创款 | 是 | 是 | 是 | 是 | Coze 已有单工具箱 |
| `yinhua_tiqu` | 图案提取 | 是 | 是 | 是 | 是 | 主路径能力 |
| `sifang_lianxu` | 四方连续 | 是 | 可选 | 是 | 是 | Coze 可保留，但客户端优先级更高 |
| `nano_banana_2_image_to_image` | 裂变套图 / 上身展示 / 背景替换 | 是 | 是 | 是 | 是 | 同一底层能力服务多个对外动作 |
| `doubao_seedance_1_5_pro` | 图生视频 | 是 | 可选 | 是 | 是 | 客户端优先，Coze 视业务编排需要开放 |
| `quality_upgrade` | AI超清 / 细节图 | 是 | 是 | 是 | 是 | 对外名要按场景区分 |
| `huawen_kuotu` | AI扩图 | 是 | 否 | 是 | 是 | 先客户端稳定，再决定是否开 Coze |
| `upscale_resize` | 高质量缩放 | 是 | 否 | 是 | 是 | 更偏终稿处理，不必强推 Coze |
| `set_dpi` | DPI处理 | 是 | 否 | 是 | 是 | 偏工具型，保留客户端即可 |

## 5. 当前内部能力建议矩阵

| abilityKey | 当前显示名 | 建议暴露级别 | 原因 |
| --- | --- | --- | --- |
| `expand_mask_color` | 扩边占位图 | `internal_only` | 是内部补边辅助工具，不是用户动作 |
| `yinhua_tiqu_lora_8step` | 8步加速可换LoRA | `admin_and_eval` + `coze_enabled` | 可保留给 Coze/内部灰度，不建议直接进普通客户端 |
| `beijing_koutu` | 背景抠图 | `admin_and_eval` + `coze_enabled` | 有明确用途，但客户端暂不必直接裸露 |
| `toubu_kouxiang` | 头部抠像 | `admin_and_eval` + `coze_enabled` | 明显偏流程子能力 |
| `flux2_9b_liebian_sifang` | FLUX2裂变+四方 | `admin_and_eval` + `coze_enabled` | 业务链路明确，但用户理解成本较高 |
| `qwen2512_print_shape_text_enhance` | 裂变文字强化 | `admin_and_eval` + `coze_enabled` | 适合作为编排节点，不适合做主工具名 |
| `e7_flux2_liebian` | E7裂变重绘 | `admin_and_eval` + `coze_enabled` | 业务工具箱可保留，但客户端先不直接裸露 |
| `jisu_chuli` | 极速处理版 | `admin_and_eval` + `advanced_only` | 当前更像通用编辑底座，不是稳定产品动作 |
| `zhongsu_tisheng` | 中速提质版 | `admin_and_eval` + `advanced_only` | 当前更像底座，不是用户语言 |

## 6. 一条重要规则

同一个底层能力可以服务多个产品动作，但不应让底层能力名主导用户入口。

典型例子：

- `nano_banana_2_image_to_image`

它现在对应：

- 裂变套图
- 服装上身
- 换背景
- 换姿势
- 图案上身
- 面料上身

这说明它是**底层通用能力**，不是用户应该直接看见的名字。

## 7. 后续落地方式

建议把暴露矩阵落到 `metadata.presentation` 或独立配置层，至少包含：

- `surfaces.client`
- `surfaces.coze`
- `surfaces.admin`
- `surfaces.eval`
- `surfaces.advancedOnly`

在代码没完全收口前，先允许文档和前端壳层做显式映射，但最终应以中台为真源。
