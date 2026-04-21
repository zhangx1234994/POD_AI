# 中台冗余入口清理决定（2026 Q2）

> 这份文档只记录已经真正落到后端真源的清理决定，不写“可能以后考虑”。

## 已生效的第一批清理

### 1. `comfyui.huawen_kuotu`

处理方式：

- 标记为 `deprecated`
- 公共入口自动隐藏
- 明确替代能力为：
  - `comfyui.flux2_klein_9b_outpaint`

原因：

- 当前扩图能力已经有统一入口
- 两套扩图 workflow 同时暴露会增加业务理解成本
- 旧入口继续公开暴露的价值低于维护成本

当前真源：

- `metadata.governance.release_status = deprecated`
- `metadata.deprecation.replacement_capability_key = flux2_klein_9b_outpaint`
- `metadata.deprecation.retirement_mode = hide_public`

### 2. `podi.expand_mask_color`

处理方式：

- 收回内部
- 不再在公共能力列表展示

原因：

- 这是内部中间步骤能力
- 业务侧无法独立判断何时该用、怎么用
- 继续公开暴露只会增加误用概率

当前真源：

- `metadata.governance.scopes = ["internal", "admin"]`
- `metadata.presentation.visible = false`

## 当前执行原则

后续任何能力如果满足以下任一条件，都优先考虑走同样的清理路径：

1. 已有更统一的替代入口
2. 主要服务内部链路，而不是业务动作
3. 业务无法独立理解其使用条件
4. 多暴露一个入口只会增加发布、培训和维护成本
