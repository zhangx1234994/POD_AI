# 图编辑真实样本回归记录（2026-05-22）

## 结论

- 目标能力：图编辑 · GPT Image 2 通用改图
- 业务 Key：`image_edit`
- 版本：`gpt-image2-editor-v1`
- 测试环境：114 线上中台 `http://114.55.0.56:8099`
- 测试档位：`quality=preview`、`size=auto`
- 测试结果：四种模式各 2 条真实任务，8/8 成功。
- 结果图访问：8 个 OSS 结果链接均返回 HTTP 200。

本次验证覆盖了提交、轮询、GPT Image 2 调用、OSS 回填、轻量结果返回的完整闭环。

## 样本包

本地样本包：

```text
deliverables/image_edit_patrol/image_edit_real_patrol_20260521_161551.zip
```

样本包内容：

- `summary.json`：本次巡检总表。
- `<case>/request.json`：提交入参。
- `<case>/submit.response.json`：提交返回。
- `<case>/poll.records.json`：轮询过程。
- `<case>/final.response.json`：最终结果。

## 样本明细

| 模式 | 次数 | runId | 结果 | OSS 结果图 |
| --- | --- | --- | --- | --- |
| 局部修改 | 1 | `608c8f85ec3144dda6d9dd75f73a4769` | 成功 | `https://podiaidesign.oss-cn-hangzhou.aliyuncs.com/test/abilities/system/20260521/fc66b29f-1779351284.png` |
| 参考图替换 | 1 | `3a6c1998b117405ebfd421e91293a275` | 成功 | `https://podiaidesign.oss-cn-hangzhou.aliyuncs.com/test/abilities/system/20260521/d4cfc304-1779351336.png` |
| 删除修补 | 1 | `34f06bb207fc4340b746d99d1a025f9b` | 成功 | `https://podiaidesign.oss-cn-hangzhou.aliyuncs.com/test/abilities/system/20260521/b741d17a-1779351388.png` |
| 补色校正 | 1 | `bc1e39e48bb3432ca0eae8ee0c41b1a5` | 成功 | `https://podiaidesign.oss-cn-hangzhou.aliyuncs.com/test/abilities/system/20260521/e74067d1-1779351423.png` |
| 局部修改 | 2 | `08299a370ec640d7ac8bd6eae792f807` | 成功 | `https://podiaidesign.oss-cn-hangzhou.aliyuncs.com/test/abilities/system/20260521/c1516264-1779351465.png` |
| 参考图替换 | 2 | `93c80a78805345b98b903ce82829f31b` | 成功 | `https://podiaidesign.oss-cn-hangzhou.aliyuncs.com/test/abilities/system/20260521/17ff6f1c-1779351518.png` |
| 删除修补 | 2 | `3f4f405553d246c18a9e25a4aeb1ea67` | 成功 | `https://podiaidesign.oss-cn-hangzhou.aliyuncs.com/test/abilities/system/20260521/ffca00fd-1779351569.png` |
| 补色校正 | 2 | `103803d75d2a4baa8ce0f75ab889151b` | 成功 | `https://podiaidesign.oss-cn-hangzhou.aliyuncs.com/test/abilities/system/20260521/9863fd26-1779351617.png` |

## 覆盖范围

- `local_modify`：局部修改。
- `reference_element_transfer`：参考图替换。
- `remove_inpaint`：删除修补。
- `color_reference_correction`：补色校正。
- 默认轻量结果口径：成功结果通过 `imageUrls/assets` 返回，不默认暴露大体积调试 payload。
- 调试口径：巡检脚本使用 `detail=full` 保留编译和步骤证据，便于内部排查。

## 管理端链路抽查

通过 `/api/admin/business/runs/{runId}` 抽查 8 条样本，均可串起：

- 业务：`image_edit`
- 版本：`gpt-image2-editor-v1`
- 状态：`succeeded`
- 结果：每条 1 张图
- 成本：每条 `0.08`
- 底层能力：`OpenAI · GPT Image 2 图片编辑`
- 子步骤：`primary=succeeded`

能力任务与日志编号：

| runId | abilityTaskId | abilityLogId |
| --- | --- | --- |
| `608c8f85ec3144dda6d9dd75f73a4769` | `t1.image_edit.auto.ad59477f885240289192c0fab299535f` | `45259` |
| `3a6c1998b117405ebfd421e91293a275` | `t1.image_edit.auto.fd1c9138700d49c095b84104b6927ded` | `45260` |
| `34f06bb207fc4340b746d99d1a025f9b` | `t1.image_edit.auto.ce33c26f15e44ef7bb4966ce5b54f54f` | `45261` |
| `bc1e39e48bb3432ca0eae8ee0c41b1a5` | `t1.image_edit.auto.785c0eb69e2b4edaad207ed0232a688a` | `45262` |
| `08299a370ec640d7ac8bd6eae792f807` | `t1.image_edit.auto.4e81a63c77b240bcab532cf62be04299` | `45263` |
| `93c80a78805345b98b903ce82829f31b` | `t1.image_edit.auto.36707dfd93bc45d1b3b1af524e1aaa5f` | `45264` |
| `3f4f405553d246c18a9e25a4aeb1ea67` | `t1.image_edit.auto.72ac1445a244420b9156b12d7106bd95` | `45265` |
| `103803d75d2a4baa8ce0f75ab889151b` | `t1.image_edit.auto.9a32a78e83434c6292874c27c219639c` | `45266` |

## 遗留风险

- 本次验证证明链路可用，但没有评价模型结果是否符合业务审美；效果评估仍需要人工或业务测试同学标注。
- 本次使用同一张主图和参考图，后续正式交付前还应补 3-5 类业务图，包括商品图、花纹图、海报图、文字图和复杂背景图。
- 蒙版硬约束链路未在本次 8 条中覆盖，后续如果开放画笔蒙版，需要单独补真实样本。
