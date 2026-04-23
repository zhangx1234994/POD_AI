# Coze 工作流直调参考

> 适用对象：AI 绘图团队、Coze 编排同学  
> 目标：直接按 Coze 当前线上实际契约调用工作流，不再混用中台工具箱契约。  
> 核对时间：2026-04-23  
> 核对真源：Coze 服务器 `114.55.0.56:8888` 的 MySQL `opencoze.workflow_meta / workflow_version`

## 1. 调用方式

当前 Coze 调用入口统一为：

```bash
curl -X POST "$COZE_BASE_URL/v1/workflow/run" \
  -H "Authorization: Bearer $COZE_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_id": "<WORKFLOW_ID>",
    "parameters": {}
  }'
```

约定：

- `COZE_BASE_URL`：当前环境的 Coze 地址
- `COZE_API_TOKEN`：当前环境可用的访问凭证
- 本文所有入参、出参，均以 Coze 当前线上 `workflow_version` 为准

## 2. 结果类型说明

大部分 ComfyUI 工作流不会直接返回图片链接，而是先返回：

- `output`：任务编号 / task id
- `ip`：执行机器信息
- 部分工作流还会返回 `prompt`

这类工作流需要再调用通用回调 workflow 取最终图片：

- 回调 workflow：`7597556718159003648`
- 名称：`comfyui_huidiao`
- 入参：`taskid`
- 出参：`images`

回调调用示例：

```bash
curl -X POST "$COZE_BASE_URL/v1/workflow/run" \
  -H "Authorization: Bearer $COZE_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_id": "7597556718159003648",
    "parameters": {
      "taskid": "t1.comfyui.xxx"
    }
  }'
```

## 3. 评测端当前主工作流

这一组是当前评测端最核心、最常用、也最应该优先回归的 Coze workflow。

### 3.1 四方连续

- Coze workflow：`7598563505054154752`
- 名称：`lianxu`
- 当前版本：`v0.0.4`
- 发布时间：`2026-02-02 21:02:44`
- 入参：
  - `url`，必填，图片
  - `patternType`，必填
  - `height`，必填
  - `width`，必填
- 出参：
  - `output`
  - `ip`
- 备注：
  - 需要走回调 workflow 取最终图片

### 3.2 旧版 ComfyUI 扩图

- Coze workflow：`7598587935331450880`
- 名称：`comfyuo_tukuozhan`
- 当前版本：`v0.0.16`
- 发布时间：`2026-03-19 18:37:02`
- 入参：
  - `url`，必填
  - `expand_bottom`，必填
  - `expand_left`，必填
  - `expand_right`，必填
  - `expand_top`，必填
- 出参：
  - `output`
  - `ip`
- 备注：
  - 需要走回调 workflow 取最终图片

### 3.3 FLUX2-Klein 扩图

- Coze workflow：`7631174682116358144`
- 名称：`comfyuo_tukuozhan_1`
- 当前版本：`v0.0.1`
- 发布时间：`2026-04-21 11:38:01`
- 入参：
  - `url`，必填
  - `expand_bottom`
  - `expand_left`
  - `expand_right`
  - `expand_top`
- 出参：
  - `output`
  - `ip`
- 备注：
  - 需要走回调 workflow 取最终图片
  - 这是当前推荐的新扩图路线

### 3.4 多图融合

- Coze workflow：`7615600173695107072`
- 名称：`comfyui_duotu`
- 当前版本：`v0.0.3`
- 发布时间：`2026-04-02 09:09:32`
- 入参：
  - `url`，必填
  - `image_url_2`
  - `image_url_3`
  - `negative_prompt`
  - `prompt`
  - `height`
  - `width`
- 出参：
  - `output`
  - `prompt`
- 备注：
  - 需要走回调 workflow 取最终图片

### 3.5 背景抠图

- Coze workflow：`7629023903431524352`
- 名称：`koubeijing`
- 当前版本：`v0.0.1`
- 发布时间：`2026-04-15 16:31:33`
- 入参：
  - `url`，必填
- 出参：
  - `output`
  - `ip`
- 备注：
  - 需要走回调 workflow 取最终图片

### 3.6 头部抠像

- Coze workflow：`7629023041988591616`
- 名称：`koutou`
- 当前版本：`v0.0.1`
- 发布时间：`2026-04-15 16:28:42`
- 入参：
  - `url`，必填
- 出参：
  - `output`
  - `ip`
- 备注：
  - 需要走回调 workflow 取最终图片

### 3.7 E7 图裂变（有 prompt 版本）

- Coze workflow：`7622190276932534272`
- 名称：`Liebian_comfyui_zaod`
- 当前版本：`v0.0.8`
- 发布时间：`2026-03-31 08:02:19`
- 入参：
  - `url`，必填
  - `height`
  - `width`
  - `prompt`
  - `bili`，必填
- 出参：
  - `output`
  - `prompt`
  - `ip`
- 备注：
  - 需要走回调 workflow 取最终图片
  - 这是 E7 图裂变当前主线之一

### 3.8 E7 图裂变（无 prompt 版本）

- Coze workflow：`7622193261276299264`
- 名称：`Liebian_comfyui_zaod_1`
- 当前版本：`v0.0.9`
- 发布时间：`2026-03-31 07:59:21`
- 入参：
  - `url`，必填
  - `height`
  - `width`
  - `bili`，必填
- 出参：
  - `output`
  - `prompt`
  - `ip`
- 备注：
  - 需要走回调 workflow 取最终图片
  - 这是 E7 图裂变当前主线之一

### 3.9 裂变文字强化

- Coze workflow：`7629024620879806464`
- 名称：`Liebian_comfyui_wenzi`
- 当前版本：`v0.0.3`
- 发布时间：`2026-04-16 12:13:51`
- 入参：
  - `url`，必填
  - `prompt`
  - `bili`，必填
- 出参：
  - `output`
  - `prompt`
  - `ip`
- 备注：
  - 需要走回调 workflow 取最终图片

### 3.10 四方连续裂变

- Coze workflow：`7629026792103215104`
- 名称：`Liebian_comfyui_wenzi_1`
- 当前版本：`v0.0.2`
- 发布时间：`2026-04-16 06:32:15`
- 入参：
  - `url`，必填
  - `prompt`
- 出参：
  - `output`
  - `prompt`
  - `ip`
- 备注：
  - 需要走回调 workflow 取最终图片

### 3.11 多元素花纹裂变（新高质量版）

- Coze workflow：`7631838631375667200`
- 名称：`Liebian_comfyui_20260423`
- 当前版本：`v0.0.1`
- 发布时间：`2026-04-23 06:42:54`
- 入参：
  - `url`，必填，图片
  - `height`
  - `width`
  - `bili`，必填
- 出参：
  - `output`
  - `prompt`
  - `ip`
- 备注：
  - 需要走回调 workflow 取最终图片
  - 当前 Coze workflow **没有**暴露 `prompt / image_desc`
  - 如果需要 `prompt / image_desc`，那是中台工具箱侧的能力，不是这条 Coze workflow 当前对外契约

## 4. 评测端仍可见的历史/兼容工作流

这一组不是当前最推荐的新主线，但在评测端或历史链路里仍然存在。AI 团队如果要做兼容回归，不能漏掉它们。

### 4.1 花纹提取 · 原生旧版

- Coze workflow：`7597530887256801280`
- 名称：`tiqu_comfyui_20260123`
- 当前版本：`v0.0.6`
- 发布时间：`2026-01-23 18:13:42`
- 入参：
  - `url`，必填
  - `height`
  - `width`
  - `lora`
- 出参：
  - `output`
  - `prompt`
  - `ip`
- 备注：
  - 需要走回调 workflow 取最终图片
  - 属于老的花纹提取主线之一

### 4.2 花纹提取 · 带提示词拼接版

- Coze workflow：`7598545860393172992`
- 名称：`tiqu_comfyui_20260123_2`
- 当前版本：`v0.0.5`
- 发布时间：`2026-01-26 16:20:00`
- 入参：
  - `url`，必填
  - `height`
  - `width`
  - `prompt`
  - `is_raw_prompt`
  - `lora`
- 出参：
  - `output`
  - `prompt`
  - `ip`
- 备注：
  - 需要走回调 workflow 取最终图片
  - `is_raw_prompt=1` 表示只用用户提示词

### 4.3 花纹提取 · 多模型批量版

- Coze workflow：`7598559869544693760`
- 名称：`tiqu_duoMoxing_2_1`
- 当前版本：`v0.0.3`
- 发布时间：`2026-01-26 17:14:11`
- 入参：
  - `moxing`，必填
  - `url`，必填
  - `aspect_ratio`
  - `resolution`
- 出参：
  - `output`
  - `prompt`
- 备注：
  - 需要走回调 workflow 取最终图片
  - 这是多模型花纹提取的早期批量版本

### 4.4 花纹提取 · 多模型带提示词版

- Coze workflow：`7601080398864449536`
- 名称：`tiqu_duoMoxing_20260130`
- 当前版本：`v0.0.1`
- 发布时间：`2026-02-02 13:13:35`
- 入参：
  - `moxing`，必填
  - `url`，必填
  - `aspect_ratio`
  - `resolution`
  - `prompt`
- 出参：
  - `output`
  - `prompt`
- 备注：
  - 需要走回调 workflow 取最终图片
  - 是花纹提取的多模型后续版本

### 4.5 图裂变 · 20260124 旧版（有 prompt）

- Coze workflow：`7598820684801769472`
- 名称：`Liebian_comfyui_20260124`
- 当前版本：`v0.0.4`
- 发布时间：`2026-01-27 09:19:56`
- 入参：
  - `url`，必填
  - `height`
  - `width`
  - `prompt`
  - `bili`，必填
- 出参：
  - `output`
  - `prompt`
  - `ip`
- 备注：
  - 需要走回调 workflow 取最终图片
  - 属于老版图裂变链路

### 4.6 图裂变 · 20260124 旧版（无 prompt）

- Coze workflow：`7598841920114130944`
- 名称：`Liebian_comfyui_20260124_1`
- 当前版本：`v0.0.2`
- 发布时间：`2026-01-27 10:42:57`
- 入参：
  - `url`，必填
  - `height`
  - `width`
  - `bili`，必填
- 出参：
  - `output`
  - `prompt`
  - `ip`
- 备注：
  - 需要走回调 workflow 取最终图片
  - 属于老版图裂变链路

## 5. 内部辅助/排障类工作流

### 5.1 通用回调工作流

- Coze workflow：`7597556718159003648`
- 名称：`comfyui_huidiao`
- 当前版本：`v0.0.3`
- 发布时间：`2026-01-23 20:03:55`
- 入参：
  - `taskid`，必填
- 出参：
  - `images`
- 备注：
  - 大多数 ComfyUI workflow 都要依赖它拿最终图片

### 5.2 队列监控工作流

- Coze workflow：`7601054603211177984`
- 名称：`comfyui_duilie`
- 当前版本：`v0.0.1`
- 发布时间：`2026-02-02 11:20:31`
- 入参：
  - 无
- 出参：
  - `servers`
  - `timestamp`
  - `totalCount`
  - `totalPending`
  - `totalRunning`
- 备注：
  - 这是内部排障/监控 workflow，不是业务出图 workflow

## 6. 推荐测试样例

建议 AI 团队直调时固定做两段测试：

1. 主 workflow 提交
- 确认 `code=0`
- 记录：
  - `execute_id`
  - `debug_url`
  - `output`
  - `ip`
  - `prompt`（如果有）

2. 回调取图
- 把主 workflow 返回的 `output` 作为 `taskid`
- 调用 `7597556718159003648`
- 确认 `images` 能拿到最终图片链接

## 7. 两个容易踩坑的点

### 5.1 不要混用工具箱契约和 Coze workflow 契约

例如新高质量裂变：

- 中台工具箱 `flux_strong_hq_softstyle_fission` 对外是：
  - `url / prompt / image_desc / bili / width / height`
- 但 Coze workflow `7631838631375667200` 当前对外是：
  - `url / height / width / bili`

这两者不是同一个契约。

### 5.2 评测端的 `count` 不是 Coze workflow 入参

评测端内部会有 `count` 这种 fan-out 控制参数，但它不属于 Coze workflow 本身。

AI 团队如果直接调用 Coze，不要传：

- `count`

## 8. 建议给 AI 团队的最小核对项

每条 workflow 至少确认：

1. `workflow_id` 是否正确
2. 当前线上实际 `input_params` 是什么
3. 当前线上实际 `output_params` 是什么
4. `output` 是不是任务编号
5. 是否需要再走 `comfyui_huidiao`

如果以上 5 项没核对清楚，不要直接下结论说“工作流没生效”。
