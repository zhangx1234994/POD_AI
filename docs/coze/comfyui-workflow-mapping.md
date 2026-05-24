# ComfyUI 工作流与 Coze 对应表

> 适用对象：AI 绘图团队、Coze 编排同学、中台维护同学
> 目标：明确“当前在用的 ComfyUI workflow”分别对应哪条 Coze workflow 或哪条单功能工具箱，避免把历史链路、内部回调链路、现网主链路混在一起。
> 核对时间：2026-04-24
> 核对真源：Coze 服务器 `114.55.0.56:8888` 的 MySQL `opencoze.workflow_meta / workflow_version / workflow_snapshot`

## 当前验证结论（2026-04-24）

- 测评端 active workflow 共 30 个，已通过真实链路全量回归：30 成功、0 失败、0 超时。
- Coze 工具箱当前统一指向 `http://114.55.0.56:8099`。
- 旧 backend 地址 `117.50.80.158:8099` 不再作为当前 Coze 工具箱入口。
- `117.50.80.158` 当前主要作为能力执行服务器使用，承载 image-ops、vendor-api-ops 和相关能力执行面。
- 本文仍只描述 ComfyUI workflow 与 Coze workflow / 工具箱关系；第三方 API 能力归属见 `docs/plans/2026-04-24-vendor-api-ops-mvp.md`。

## 判断口径

- **ComfyUI workflow**：以仓库 `backend/app/services/workflow_seed.py` 中当前 active 的 workflow 为准。
- **Coze workflow**：优先以 Coze 服务器 MySQL 的 `workflow_meta / workflow_version` 为准，再参考中台仓库 `backend/app/services/eval_seed.py`。
- **单功能工具箱**：以 `docs/coze/toolbox-inventory.md` 中当前可导入的 OpenAPI 为准。
- **当前在用** 不等于 **一定只有一种接法**：
  - 有些链路同时存在 **独立 Coze workflow**
  - 也存在 **单功能工具箱直连**

## 当前在用主链路

| 业务功能 | ComfyUI workflow_key | 中台能力 / 工具箱 | 当前对应 Coze workflow | 当前对应 Coze 单功能工具箱 | Coze 当前对外入参 | 说明 |
| --- | --- | --- | --- | --- | --- | --- |
| 四方连续 | `sifang_lianxu` | `comfyui.sifang_lianxu` | `7598563505054154752` · `lianxu` | 当前未单独拆单功能工具箱 | `url / patternType / height / width` | Coze 侧当前仍沿用历史连续图 workflow。 |
| 花纹扩图 | `huawen_kuotu` | `comfyui.huawen_kuotu` | `7598587935331450880` · `comfyuo_tukuozhan` | 当前未单独拆单功能工具箱 | `url / expand_bottom / expand_left / expand_right / expand_top` | 当前主线是 ComfyUI 扩图；旧的“扩图多模型版本”见下方历史区。 |
| FLUX2-Klein 扩图 | `flux2_klein_9b_outpaint` | `comfyui.flux2_klein_9b_outpaint` | `7631174682116358144` · `comfyuo_tukuozhan_1` | `/api/coze/podi/comfyui/execute/flux2-klein-9b-outpaint/openapi.json` | `url / expand_bottom / expand_left / expand_right / expand_top` | 这条已经不只是工具箱直连，Coze 侧也有独立 workflow。当前 Coze workflow 不暴露 prompt / seed。2026-05-25 已替换为 `Flux 2 klein 9b-222` 工作流，外部入参不变。 |
| 多图融合 | `duotu_ronghe` | `comfyui.duotu_ronghe` | `7615600173695107072` · `comfyui_duotu` | `/api/coze/podi/comfyui/execute/duotu-ronghe/openapi.json` | `url / image_url_2 / image_url_3 / negative_prompt / prompt / height / width` | 评测端和工具箱两条链路都在用。 |
| 背景抠图 | `beijing_koutu` | `comfyui.beijing_koutu` | `7629023903431524352` · `koubeijing` | `/api/coze/podi/comfyui/execute/beijing-koutu/openapi.json` | `url` | 当前主线稳定。 |
| 头部抠像 | `toubu_kouxiang` | `comfyui.toubu_kouxiang` | `7629023041988591616` · `koutou` | `/api/coze/podi/comfyui/execute/toubu-kouxiang/openapi.json` | `url` | 当前主线稳定。 |
| E7 图裂变 | `e7_flux2_liebian` | `comfyui.e7_flux2_liebian` | **推荐主线**：`7622190276932534272` · `Liebian_comfyui_zaod`；配套无 prompt 版本：`7622193261276299264` · `Liebian_comfyui_zaod_1` | `/api/coze/podi/comfyui/execute/e7-flux2-liebian/openapi.json` | 有 prompt：`url / height / width / prompt / bili`；无 prompt：`url / height / width / bili` | 当前仓库内工具箱固定成 `e7_flux2_liebian`；Coze 侧历史上有多版 workflow，当前优先看 `20260328` 这一组。 |
| 裂变文字强化 | `qwen2512_print_shape_text_enhance` | `comfyui.qwen2512_print_shape_text_enhance` | `7629024620879806464` · `Liebian_comfyui_wenzi` | `/api/coze/podi/comfyui/execute/qwen2512-print-shape-text-enhance/openapi.json` | `url / prompt / bili` | 当前上游 prompt 质量仍在优化，但链路稳定。 |
| FLUX2 裂变 + 四方 | `flux2_9b_liebian_sifang` | `comfyui.flux2_9b_liebian_sifang` | `7629026792103215104` · `Liebian_comfyui_wenzi_1` | `/api/coze/podi/comfyui/execute/flux2-9b-liebian-sifang/openapi.json` | `url / prompt` | 同时出现在 `图裂变` 和 `四方/两方连续图类`；2026-05-16 233 恢复 `String` 后已强制跑通，恢复 233/158 双机路由。 |
| 多元素花纹裂变 | `flux_strong_hq_softstyle_fission` | `comfyui.flux_strong_hq_softstyle_fission` | `7631838631375667200` · `Liebian_comfyui_20260423` | `/api/coze/podi/comfyui/execute/flux-strong-hq-softstyle-fission/openapi.json` | `url / height / width / bili` | 新上的高质量图裂变。注意：当前 Coze workflow 没暴露 `prompt / image_desc`，这两个仍主要走工具箱侧。 |
| 印花提取（标准版） | `yinhua_tiqu` | `comfyui.yinhua_tiqu` | 当前没有单一主 id；现网历史链路主要见下方“印花提取历史族” | 当前无独立单功能工具箱 | 见下方历史族 | 这条在仓库内仍 active，但 Coze 侧没有整理成单一主 workflow。 |
| 8 步加速可换 LoRA | `yinhua_tiqu_lora_8step` | `comfyui.yinhua_tiqu_lora_8step` | 当前无独立 Coze workflow id | `/api/coze/podi/comfyui/execute/yinhua-tiqu-lora-8step/openapi.json` | 工具箱参数为 `url / lora / width / height / prompt / negative_prompt / batch` | 当前以单功能工具箱为主，不走独立 Coze workflow。 |

## 印花提取历史族

这组 workflow 都和当前仓库内的 `yinhua_tiqu / yinhua_tiqu_lora_8step` 业务域有关，但 Coze 侧历史版本较多，不能再把它们视为一个“唯一主 id”。

| Coze workflow id | 名称 | 当前判断 |
| --- | --- | --- |
| `7597530887256801280` | `tiqu_comfyui_20260123` | 最早主线之一，当前仍 active |
| `7598545860393172992` | `tiqu_comfyui_20260123_2` | 同一族的后续版本 |
| `7601080398864449536` | `tiqu_duoMoxing_20260130` | 多模型提取版本 |
| `7598559869544693760` | `tiqu_duoMoxing_2_1` | 多模型提取版本 |
| `7598560946579046400` | `tiqu_duoMoxing_2_2` | 当前在 `eval_seed` 里 inactive，不建议作为新主线 |

## 图裂变历史族

这组都属于老的 Coze 图裂变链路。当前如果要改 **E7 图裂变**，优先看 `e7_flux2_liebian` + `7622190276932534272 / 7622193261276299264`，不要再回到更早的 20260124 版本。

| Coze workflow id | 名称 | 当前判断 |
| --- | --- | --- |
| `7598841920114130944` | `Liebian_comfyui_20260124_1` | 老版本，无 prompt |
| `7598820684801769472` | `Liebian_comfyui_20260124` | 老版本，有 prompt |
| `7622193261276299264` | `Liebian_comfyui_zaod_1` | 当前仍 active；新版无 prompt 版本 |
| `7622190276932534272` | `Liebian_comfyui_zaod` | 当前推荐主线；新版有 prompt 版本 |
| `7601077530077954048` | `Liebian_shangye_20260130` | 商业模型裂变，不是当前 ComfyUI 主线 |
| `7598848725942796288` | `Liebian_shangye_20260124_1_1_1` | 商业模型裂变旧版本 |

## 图延伸历史替代关系

| 当前主线 | 历史 / 被替代链路 | 备注 |
| --- | --- | --- |
| `huawen_kuotu` → `7598587935331450880` | `7597723984687267840` · `扩图多模型版本` | 旧多模型扩图还在 `eval_seed` 中 active，但现在不应再作为 ComfyUI 主扩图链路理解。 |
| `flux2_klein_9b_outpaint` → `7631174682116358144` | `huawen_kuotu / 7598587935331450880` | 这是新的 FLUX2-Klein 扩图路线；现在 Coze 里也已有独立 workflow。 |

## 内部 / 辅助 Coze workflow

这些不是给 AI 绘图团队直接改业务效果用的，不要误当成业务主工作流。

| Coze workflow id | 名称 | 用途 |
| --- | --- | --- |
| `7597556718159003648` | `comfyui_huidiao` | 通用回调解析 / 拿最终图片 |
| `7601054603211177984` | `comfyui_duilie` | 队列状态与机器排队监控 |

## 给 AI 绘图团队的直接结论

### 现在最需要优先认清的几条

- **E7 图裂变主线**：`e7_flux2_liebian` ↔ `7622190276932534272 / 7622193261276299264`
- **图裂变新高质量版**：`flux_strong_hq_softstyle_fission` ↔ `7631838631375667200`
- **四方连续裂变**：`flux2_9b_liebian_sifang` ↔ `7629026792103215104`
- **裂变文字强化**：`qwen2512_print_shape_text_enhance` ↔ `7629024620879806464`
- **扩图主线**：`huawen_kuotu` ↔ `7598587935331450880`
- **新扩图路线**：`flux2_klein_9b_outpaint` ↔ `7631174682116358144`

### 使用建议

1. 先确认要改的是哪条 **ComfyUI workflow_key**
2. 再确认 Coze 侧到底对应：
   - 独立 workflow id
   - 还是单功能工具箱
3. 不要直接碰“历史族”或“内部辅助 workflow”
4. 如果发现 **工具箱参数** 和 **Coze workflow 入参** 不一致，以 Coze 服务器当前 `workflow_version.input_params` 为准

## 数据来源

- Coze 服务器 `114.55.0.56:8888` 的 MySQL `opencoze.workflow_meta / workflow_version / workflow_snapshot`
- `backend/app/services/workflow_seed.py`
- `backend/app/services/eval_seed.py`
- `docs/coze/toolbox-inventory.md`
- `docs/comfyui/README.md`
