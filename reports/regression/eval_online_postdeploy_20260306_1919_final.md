# Eval Online Postdeploy Final 2026-03-06 19:19

- total: `24`
- ok: `24`
- fail: `0`

## Conclusion

- 当前线上版本在全量 24 个激活 Coze 工作流上最终全部通过。
- 首轮失败的 6 条并不是部署损坏，而是回归入参组织不规范：测试图格式与默认展示文案传值（如 `跟随原图（默认）/原图比例（默认）`）混入了商业模型请求。
- 改用 PNG 测试图，并按真实枚举值/空值重新组织 `aspect_ratio`、`resolution` 后，这 6 条全部成功。

| workflow_id | 名称 | 最终结果 | 来源 | 备注 |
|---|---|---|---|---|
| 7598563505054154752 | 两方四方连续图 | succeeded / success | initial-pass |  |
| 7598587935331450880 | ComfyUI 扩图 | succeeded / success | initial-pass |  |
| 7597723984687267840 | 商业模型 扩图 | succeeded / success | initial-pass |  |
| 7601077530077954048 | 图裂变 ·商业模型免提示词 | succeeded / success | png-retry | 首轮回归入参组织不规范，PNG + 正确传值补跑成功 |
| 7598848725942796288 | 图裂变 · 商业模型有提示词 | succeeded / success | png-retry | 首轮回归入参组织不规范，PNG + 正确传值补跑成功 |
| 7598820684801769472 | 图裂变 ·comfyui提示词 | succeeded / success | initial-pass |  |
| 7598841920114130944 | 图裂变 · comfyui无提示词 | succeeded / success | initial-pass |  |
| 7601080398864449536 | 花纹提取 · 商业模型有提示词 | succeeded / success | png-retry | 首轮回归入参组织不规范，PNG + 正确传值补跑成功 |
| 7598559869544693760 | 花纹提取·商业模型免提示词 | succeeded / success | png-retry | 首轮回归入参组织不规范，PNG + 正确传值补跑成功 |
| 7598545860393172992 | 花纹提取—comfyui提示词版本 | succeeded / success | initial-pass |  |
| 7597530887256801280 | 花纹提取—comfyui无提示词版本 | succeeded / success | initial-pass |  |
| 7612002440056930304 | LoRA 查询 · lora_catalog_query | succeeded / success | initial-pass |  |
| 7604714915110060032 | AI 图片编辑器 · nano_banana_pro_edit | succeeded / success | png-retry | 首轮回归入参组织不规范，PNG + 正确传值补跑成功 |
| 7602916576198656000 | 多模型生图 · shengtu_shangye | succeeded / success | png-retry | 首轮回归入参组织不规范，PNG + 正确传值补跑成功 |
| 7600254097513512960 | 图片打标签 · Biaoqian_tiqu_3 | succeeded / success | initial-pass |  |
| 7601054603211177984 | ComfyUI 队列监控 · comfyui_duilie | succeeded / success | initial-pass |  |
| 7600254796297142272 | 图片打标签 · Biaoqian_tiqu_3_1 | succeeded / success | initial-pass |  |
| 7597767702970630144 | 图片打标签 · Biaoqian_tiqu | succeeded / success | initial-pass |  |
| 7598080013539213312 | 图片打标签 · Biaoqian_tiqu_1 | succeeded / success | initial-pass |  |
| 7598589746561941504 | DPI 增分 | succeeded / success | initial-pass |  |
| 7597760543788630016 | 8K 高清放大 | succeeded / success | initial-pass |  |
| 7597701996124045312 | 四步急速生图 | succeeded / success | initial-pass |  |
| 7597702948247830528 | 八步急速生图 | succeeded / success | initial-pass |  |
| 7597556718159003648 | ComfyUI 回调 · comfyui_huidiao | succeeded / success | initial-pass |  |