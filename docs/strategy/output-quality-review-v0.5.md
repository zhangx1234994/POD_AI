# v0.5 出图效果复盘与质量标签体系

最后更新：2026-05-26

本文定义 v0.5 进入迭代期后的出图效果复盘口径。目标不是做大而全的标注平台，而是让运营、能力工程师和运维能定期回答三个问题：

- 哪类图效果不好。
- 哪类图稳定性不高。
- 下一步应该调参、分流、换 LoRA / workflow，还是暂停推荐。

## 1. 产品原则

- 少就是多：业务页默认只展示结论、样例池状态、主要标签和下一步动作。
- 先轻量抽检，再做持久化：第一阶段复用现有运行摘要和业务 runId；第二阶段再落库人工标注。
- 质量问题必须和链路问题分开：接口失败、队列卡住、OSS 回填失败先归为链路问题；只有成功出图后才进入效果复盘。
- 每次默认版本切换前必须有样例证据，没有固定样例对照不切默认。

## 2. 复盘对象

v0.5 首批只覆盖五个核心业务：

| 业务 | 固定样例池 | 重点观察 |
| --- | --- | --- |
| 花纹提取 | 干净花纹、复杂背景、布料纹理 | 主体残留、边缘脏污、纹理断裂、颜色偏移 |
| 图裂变 | 单主体、满版图案、颜色敏感、复杂纹理、业务真实图 | 结构偏移、主体变形、图案密度变化、色差过大 |
| 图编辑 | 删除、替换、补色、参考图、扩展画布 | 指令未执行、参考图丢失、局部边缘不自然、原图被误改 |
| 扩图 | 四边、单边、横向、纵向扩展 | 接缝明显、背景穿帮、主体拉伸、比例失真 |
| 文字裂变 | 中文密集、英文数字、低对比文字 | 文字错字、版式漂移、笔画糊化、语义丢失 |

## 3. 质量档位

| 档位 | 含义 | 推荐动作 |
| --- | --- | --- |
| `excellent` | 可作为展示样例或推荐样例 | 加入优秀样例池，保留参数和版本 |
| `usable` | 业务可用，有轻微瑕疵 | 可继续小流量，记录问题标签 |
| `borderline` | 勉强可用，需要人工判断 | 进入候选复盘，优先对比调参或分流 |
| `bad` | 明显不可用 | 标记问题标签，停止作为推荐样例 |
| `blocked` | 输出缺失、链路失败或无法判断 | 回到 runId 链路排障，不进入质量判断 |

## 4. 标签结构

每条人工复盘记录最少包含：

- `business_key`：业务入口。
- `run_id`：中台业务 runId。
- `business_version_id`：业务版本。
- `output_index`：第几张输出图。
- `quality_grade`：质量档位。
- `input_tags[]`：输入图标签。
- `issue_tags[]`：问题标签。
- `next_action`：建议动作。
- `reviewer` / `reviewed_at`：复盘人和时间。

建议动作枚举：

| 动作 | 使用场景 |
| --- | --- |
| `accept` | 效果稳定，可作为样例或继续推荐 |
| `tune_params` | 参数可修复，例如重绘幅度、尺寸、提示词 |
| `route_split` | 某类输入明显不适合当前默认链路 |
| `switch_lora` | LoRA / workflow 候选更适合该类图 |
| `manual_review` | 业务价值高，但需要人工复核 |
| `pause_recommendation` | 不建议继续给业务方推荐 |

## 5. 页面实现分阶段

### 5.1 已完成阶段

管理端业务能力页已新增“出图效果复盘”面板：

- 使用现有 `BusinessUsageSummaryResponse` 和当前页 `BusinessRun[]` 推导可抽检样本。
- 按五个核心业务展示固定样例池、样本状态、输入标签、问题标签和下一步动作。
- 新增 `business_output_reviews` 表，支持按 `runId + outputIndex` 保存单张结果的质量档位、输入标签、问题标签、建议动作和备注。
- 管理端 runId 详情已接入“出图质量标注”，运营可直接在结果预览旁逐张保存标注。
- 业务页读取近窗口质量汇总，展示已标注数量、质量档位分布、业务 TopN 输入/问题标签。
- 当前发布门禁不再读取中台质量标注作为阻断项：质量结论以看板侧为准；中台 `business_output_reviews` 只保留历史观察、导出和问题分析价值。
- TopN 输入/问题标签已带样例下钻：点击标签可打开对应 runId，runId 详情会定位并高亮具体输出序号。
- 质量汇总已增加版本维度 `byVersion`，用于把质量样本归因到具体业务版本 / LoRA / workflow 候选。
- 管理端业务能力页已新增“候选版本对照”面板，按核心业务聚合默认、候选、草稿版本，展示路由、workflow、LoRA、模型、最近运行和版本级质量样例。
- 候选版本对照面板已接入固定样例复跑入口：运营可选择样例类型、填写输入图和备注，复用草稿运行链路提交带 `metadata.qualitySample` 的复跑任务。
- 固定样例复跑已升级为“批量样例集”：每个核心业务可一次选择多个样例和多个版本，提交时写入统一 `batchId`，完成后按 `byBatch` 汇总同批质量对照。
- 固定样例 URL 已开始沉淀到 `business_quality_samples`，支持按业务保存、复用、停用和归档样例资产。
- 固定样例库维护已补齐 OSS 直传、批量导入 upsert、dryRun 预检查和 `business_quality_sample_versions` 版本快照，便于运营追溯样例变化。
- 分流 / LoRA / workflow 候选治理已开始沉淀到 `business_quality_action_rules`，支持把问题标签、输入标签、建议动作、目标候选版本和状态记成轻量台账。
- 业务流程监控摘要已接入 `flowEvidence` 链路证据：七阶段阶段耗时、路由命中、候选命中、LoRA 命中和 workflow 命中会随 `/api/admin/business/usage-summary` 返回，管理端用于按命中项分组抽检效果。

限制：

- 质量治理台账先记录候选策略和证据，不会自动改线上路由、LoRA 或 workflow。
- 样例库当前保存 URL 和默认参数，尚未接入 OSS 上传、批量导入和样例版本历史。

### 5.2 下一阶段

管理端继续增加：

- 问题标签到分流规则、LoRA / workflow 候选的关联台账继续补充验证指标和自动推荐；当前 `flowEvidence` 只做观察统计，不自动改线上策略。
- 固定样例库的保存、复用、版本管理和同批结果导出。
- 默认版本切换前的同批样例对照和回滚口径检查。

### 5.3 已接入的标注接口

本轮新增业务输出复盘表 `business_output_reviews`，以业务 runId 和输出序号为唯一标识。

管理端使用方式：

1. 进入“业务能力”→“业务调用清单”。
2. 打开某条 runId 详情。
3. 在“出图质量标注”中逐张查看输出结果。
4. 保存质量档位、输入标签、问题标签、下一步动作和备注。
5. 返回业务页“出图效果复盘”，查看近 7 天标注汇总和 TopN 标签。
6. 点击 TopN 标签或“最近质量样例”的“打开 runId”，回到具体输出图继续复核。
7. 进入“候选版本对照”，按业务查看默认/候选/草稿版本的质量证据和路由配置。
8. 对需要验证的候选版本点击“跑固定样例”，提交同一类输入图进行复跑。
9. 对默认版和候选版点击“批量复跑样例集”，选择同批样例和目标版本；同批任务会写入同一个 `batchId`。
10. 输出完成并标注后，查看“近期同批质量对照”，比较默认版和候选版在同一批样例上的可用/风险数量。
11. 常用样例可保存到“固定样例库”，后续批量复跑时直接复用，不再反复手填 URL。
12. 对稳定复现的问题，点击“记录治理项”，把问题标签、输入标签、候选动作和目标版本沉淀到治理台账。

#### GET `/api/admin/business/quality-samples`

用途：读取固定质量样例库。管理端按业务筛选后，用于单样例复跑和批量样例集复跑。

查询参数：

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `business_key` | 空 | 可选，按业务过滤 |
| `status` | 空 | 可选，按 `active` / `inactive` / `archived` 过滤 |
| `include_archived` | `false` | 是否包含已归档样例 |
| `limit` | `200` | 返回条数，1-500 |

响应：

```json
{
  "total": 1,
  "items": [
    {
      "id": "bizsample_xxx",
      "businessKey": "fission",
      "sampleKey": "dense-pattern-a",
      "label": "满版图案 A",
      "description": "高密度图案，检查重复瑕疵。",
      "imageUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/...",
      "prompt": "保持主体结构",
      "generatedImageUrl": null,
      "inputTags": ["满版图案"],
      "defaultParams": {"quality": "preview"},
      "status": "active",
      "sortOrder": 10,
      "createdByUsername": "admin",
      "createdAt": "2026-05-26T00:00:00",
      "updatedAt": "2026-05-26T00:00:00"
    }
  ]
}
```

错误：

| 错误码 | 场景 | 处理 |
| --- | --- | --- |
| `AUTHORIZATION_REQUIRED` / `ADMIN_ONLY` | 未登录或非管理员 | 重新登录管理端或使用管理员账号 |
| `BUSINESS_QUALITY_SAMPLE_STATUS_INVALID` | `status` 非法 | 使用 `active` / `inactive` / `archived` |

#### GET `/api/evals/business/quality-samples`

用途：测评端只读复用固定质量样例。管理端仍是唯一维护入口；测评端用该接口把“推荐业务入口”和“质量样例池”打通，业务方可以直接套用同一批输入图做验收。

查询参数：

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `business_key` | 空 | 可选，按业务过滤 |
| `status` | `active` | 仅允许 `active` / `inactive`，不暴露 `archived` |
| `limit` | `200` | 返回条数，1-500 |

响应同管理端样例列表对象，但不提供新增、更新、归档动作。

错误：

| 错误码 | 场景 | 处理 |
| --- | --- | --- |
| `NOT_FOUND` | 公共测评接口未启用 | 检查 `EVAL_PUBLIC_ENABLED` |
| `UNAUTHORIZED` | 配置了 `EVAL_PUBLIC_TOKEN` 且 token 不匹配 | 传 `X-Eval-Token` 或检查配置 |
| `BUSINESS_QUALITY_SAMPLE_STATUS_INVALID` | `status` 非法或试图读取归档样例 | 使用 `active` / `inactive` |

#### POST `/api/admin/business/quality-samples`

用途：新增固定质量样例。

请求：

```json
{
  "businessKey": "fission",
  "sampleKey": "dense-pattern-a",
  "label": "满版图案 A",
  "description": "高密度图案，检查重复瑕疵。",
  "imageUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/...",
  "prompt": "保持主体结构",
  "generatedImageUrl": null,
  "inputTags": ["满版图案"],
  "defaultParams": {"quality": "preview"},
  "status": "active",
  "sortOrder": 10,
  "changeNote": "运营新增验收样例"
}
```

响应同单条样例对象。

错误：

| 错误码 | 场景 | 处理 |
| --- | --- | --- |
| `BUSINESS_QUALITY_SAMPLE_BUSINESS_KEY_REQUIRED` | 缺少业务标识 | 选择样例所属业务 |
| `BUSINESS_QUALITY_SAMPLE_LABEL_REQUIRED` | 缺少样例名称 | 填写可读名称 |
| `BUSINESS_QUALITY_SAMPLE_IMAGE_URL_REQUIRED` | 缺少图片 URL | 填写公网图片 URL |
| `BUSINESS_QUALITY_SAMPLE_IMAGE_URL_INVALID` | URL 非 HTTP(S) | 先上传到 OSS 或使用公网 URL |
| `BUSINESS_QUALITY_SAMPLE_STATUS_INVALID` | 状态非法 | 使用 `active` / `inactive` / `archived` |
| `BUSINESS_QUALITY_SAMPLE_KEY_DUPLICATED` | 同一业务下样例 Key 重复 | 换一个 `sampleKey` |

#### POST `/api/admin/business/quality-samples/import`

用途：批量导入或更新固定质量样例。管理端支持粘贴 JSON 数组或 CSV，服务端按 `businessKey + sampleKey` 幂等 upsert；`dryRun=true` 只做预检查，不写库。

请求：

```json
{
  "businessKey": "fission",
  "dryRun": false,
  "changeNote": "运营批量导入",
  "items": [
    {
      "sampleKey": "dense-pattern-a",
      "label": "满版图案 A",
      "imageUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/...",
      "prompt": "保持主体结构",
      "inputTags": ["满版图案"],
      "defaultParams": {"quality": "preview"},
      "status": "active",
      "sortOrder": 10
    }
  ]
}
```

响应：

```json
{
  "total": 1,
  "created": 1,
  "updated": 0,
  "skipped": 0,
  "failed": 0,
  "dryRun": false,
  "items": [
    {
      "index": 0,
      "action": "created",
      "sampleId": "bizsample_xxx",
      "businessKey": "fission",
      "sampleKey": "dense-pattern-a",
      "label": "满版图案 A",
      "errorCode": null,
      "message": "已新增"
    }
  ]
}
```

错误：

| 错误码 | 场景 | 处理 |
| --- | --- | --- |
| `BUSINESS_QUALITY_SAMPLE_IMPORT_EMPTY` | `items` 为空 | 重新粘贴导入内容 |
| `BUSINESS_QUALITY_SAMPLE_IMPORT_LIMIT_EXCEEDED` | 单次超过 200 条 | 拆分批次导入 |
| `BUSINESS_QUALITY_SAMPLE_BUSINESS_KEY_REQUIRED` | 条目和请求都缺少业务标识 | 选择默认业务或在条目中填写 `businessKey` |
| `BUSINESS_QUALITY_SAMPLE_KEY_REQUIRED` | 条目缺少 `sampleKey` | 填写稳定样例 Key |
| `BUSINESS_QUALITY_SAMPLE_KEY_DUPLICATED` | 同批或同业务样例 Key 重复 | 去重后重试 |
| `BUSINESS_QUALITY_SAMPLE_LABEL_REQUIRED` | 条目缺少样例名称 | 填写可读名称 |
| `BUSINESS_QUALITY_SAMPLE_IMAGE_URL_REQUIRED` | 条目缺少图片 URL | 先上传到 OSS 再导入 |
| `BUSINESS_QUALITY_SAMPLE_IMAGE_URL_INVALID` | URL 非 HTTP(S) | 使用公网 OSS URL |
| `BUSINESS_QUALITY_SAMPLE_STATUS_INVALID` | 状态非法 | 使用 `active` / `inactive` / `archived` |

#### GET `/api/admin/business/quality-samples/{sample_id}/versions`

用途：查看固定样例每次新增、更新、导入、归档时的快照。用于追溯“运营换了哪张图/参数之后效果变化”。

查询参数：

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `limit` | `50` | 返回条数，1-100 |

错误：

| 错误码 | 场景 | 处理 |
| --- | --- | --- |
| `BUSINESS_QUALITY_SAMPLE_NOT_FOUND` | 样例不存在 | 刷新样例库 |

#### PATCH `/api/admin/business/quality-samples/{sample_id}`

用途：更新固定质量样例的名称、URL、参数、标签或状态。

错误：

| 错误码 | 场景 | 处理 |
| --- | --- | --- |
| `BUSINESS_QUALITY_SAMPLE_NOT_FOUND` | 样例不存在 | 刷新样例库 |
| `BUSINESS_QUALITY_SAMPLE_KEY_REQUIRED` | 更新后的样例 Key 为空 | 填写稳定 Key |
| `BUSINESS_QUALITY_SAMPLE_KEY_DUPLICATED` | 同一业务下样例 Key 重复 | 换一个 `sampleKey` |
| `BUSINESS_QUALITY_SAMPLE_LABEL_REQUIRED` | 样例名称为空 | 填写可读名称 |
| `BUSINESS_QUALITY_SAMPLE_IMAGE_URL_INVALID` | URL 非 HTTP(S) | 先上传到 OSS 或使用公网 URL |
| `BUSINESS_QUALITY_SAMPLE_STATUS_INVALID` | 状态非法 | 使用 `active` / `inactive` / `archived` |

#### DELETE `/api/admin/business/quality-samples/{sample_id}`

用途：归档固定质量样例。接口不会物理删除样例，便于复盘历史批次。

错误：

| 错误码 | 场景 | 处理 |
| --- | --- | --- |
| `BUSINESS_QUALITY_SAMPLE_NOT_FOUND` | 样例不存在 | 刷新样例库 |

#### GET `/api/admin/business/quality-action-rules`

用途：读取质量治理台账。管理端按业务筛选后，用于查看哪些输入图应分流、调参、换 LoRA / workflow 或暂停推荐。

查询参数：

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `business_key` | 空 | 可选，按业务过滤 |
| `status` | 空 | 可选，按 `draft` / `candidate` / `validated` / `default` / `paused` / `rejected` / `archived` 过滤 |
| `action_type` | 空 | 可选，按治理动作过滤 |
| `include_archived` | `false` | 是否包含已归档台账 |
| `limit` | `200` | 返回条数，1-500 |

响应：

```json
{
  "total": 1,
  "items": [
    {
      "id": "bizqar_xxx",
      "businessKey": "fission",
      "ruleKey": "dense-pattern-switch-lora",
      "title": "满版图案切候选 LoRA",
      "description": "满版图案结构偏移时切候选 LoRA。",
      "issueTags": ["结构偏移"],
      "inputTags": ["满版图案"],
      "actionType": "switch_lora",
      "targetBusinessVersionId": "cap_xxx",
      "targetVersion": "v0.5-candidate",
      "targetLabel": "图裂变候选版",
      "targetRef": "candidate-lora.safetensors",
      "targetParams": {"denoise": 0.48},
      "sampleBatchId": "batch_xxx",
      "evidenceReviewIds": ["review_xxx"],
      "status": "candidate",
      "priority": 0,
      "ownerUsername": "admin",
      "createdAt": "2026-05-26T00:00:00",
      "updatedAt": "2026-05-26T00:00:00"
    }
  ]
}
```

错误：

| 错误码 | 场景 | 处理 |
| --- | --- | --- |
| `AUTHORIZATION_REQUIRED` / `ADMIN_ONLY` | 未登录或非管理员 | 重新登录管理端或使用管理员账号 |
| `BUSINESS_QUALITY_ACTION_STATUS_INVALID` | `status` 非法 | 使用允许状态 |
| `BUSINESS_QUALITY_ACTION_TYPE_INVALID` | `action_type` 非法 | 使用允许动作 |

#### POST `/api/admin/business/quality-action-rules`

用途：新增质量治理项。该接口只记录策略和证据，不自动改线上路由。

请求：

```json
{
  "businessKey": "fission",
  "ruleKey": "dense-pattern-switch-lora",
  "title": "满版图案切候选 LoRA",
  "description": "满版图案结构偏移时切候选 LoRA。",
  "issueTags": ["结构偏移"],
  "inputTags": ["满版图案"],
  "actionType": "switch_lora",
  "targetBusinessVersionId": "cap_xxx",
  "targetRef": "candidate-lora.safetensors",
  "targetParams": {"denoise": 0.48},
  "sampleBatchId": "batch_xxx",
  "evidenceReviewIds": ["review_xxx"],
  "status": "candidate",
  "priority": 0
}
```

响应同单条治理项对象。

错误：

| 错误码 | 场景 | 处理 |
| --- | --- | --- |
| `BUSINESS_QUALITY_ACTION_BUSINESS_KEY_REQUIRED` | 缺少业务标识 | 选择治理项所属业务 |
| `BUSINESS_QUALITY_ACTION_TITLE_REQUIRED` | 缺少标题 | 填写可读标题 |
| `BUSINESS_QUALITY_ACTION_TYPE_INVALID` | 动作类型非法 | 使用允许动作 |
| `BUSINESS_QUALITY_ACTION_STATUS_INVALID` | 状态非法 | 使用允许状态 |
| `BUSINESS_QUALITY_ACTION_KEY_DUPLICATED` | 同一业务下规则 Key 重复 | 换一个 `ruleKey` |
| `BUSINESS_QUALITY_ACTION_TARGET_VERSION_NOT_FOUND` | 目标候选版本不存在或不属于该业务 | 刷新候选版本后重新选择 |

#### PATCH `/api/admin/business/quality-action-rules/{rule_id}`

用途：更新质量治理项的标题、标签、动作、目标版本、状态或说明。

错误：

| 错误码 | 场景 | 处理 |
| --- | --- | --- |
| `BUSINESS_QUALITY_ACTION_NOT_FOUND` | 台账不存在 | 刷新治理台账 |
| `BUSINESS_QUALITY_ACTION_KEY_REQUIRED` | 更新后的规则 Key 为空 | 填写稳定 Key |
| `BUSINESS_QUALITY_ACTION_KEY_DUPLICATED` | 同一业务下规则 Key 重复 | 换一个 `ruleKey` |
| `BUSINESS_QUALITY_ACTION_TITLE_REQUIRED` | 标题为空 | 填写可读标题 |
| `BUSINESS_QUALITY_ACTION_TYPE_INVALID` | 动作类型非法 | 使用允许动作 |
| `BUSINESS_QUALITY_ACTION_STATUS_INVALID` | 状态非法 | 使用允许状态 |
| `BUSINESS_QUALITY_ACTION_TARGET_VERSION_NOT_FOUND` | 目标候选版本不存在或不属于该业务 | 刷新候选版本后重新选择 |

#### DELETE `/api/admin/business/quality-action-rules/{rule_id}`

用途：归档质量治理项。接口不会物理删除，便于复盘历史决策。

错误：

| 错误码 | 场景 | 处理 |
| --- | --- | --- |
| `BUSINESS_QUALITY_ACTION_NOT_FOUND` | 台账不存在 | 刷新治理台账 |

#### GET `/api/admin/business/runs/{run_id}/output-reviews`

用途：读取某个业务 runId 下已经保存的输出图复盘记录。

响应：

```json
{
  "total": 1,
  "items": [
    {
      "id": "bizreview_xxx",
      "runId": "run_xxx",
      "businessKey": "fission",
      "version": "v1",
      "outputIndex": 0,
      "outputUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/...",
      "qualityGrade": "bad",
      "inputTags": ["满版图案"],
      "issueTags": ["结构偏移"],
      "nextAction": "route_split",
      "note": "主体结构明显偏移。",
      "reviewerUsername": "admin",
      "createdAt": "2026-05-26T00:00:00",
      "updatedAt": "2026-05-26T00:00:00"
    }
  ]
}
```

错误：

| 错误码 | 场景 | 处理 |
| --- | --- | --- |
| `AUTHORIZATION_REQUIRED` / `ADMIN_ONLY` | 未登录或非管理员 | 重新登录管理端或使用管理员账号 |
| `BUSINESS_RUN_NOT_FOUND` | runId 不存在 | 核对业务调用记录 |

#### POST `/api/admin/business/runs/{run_id}/output-reviews`

用途：新增或更新某个业务 runId 下的输出图复盘记录。`outputIndex` 从 0 开始，对应输出图列表顺序。

请求：

```json
{
  "items": [
    {
      "outputIndex": 0,
      "qualityGrade": "usable",
      "inputTags": ["颜色敏感"],
      "issueTags": ["色差过大"],
      "nextAction": "tune_params",
      "note": "颜色略偏，可通过提示词或参考图约束优化。"
    }
  ]
}
```

响应同读取接口。

错误：

| 错误码 | 场景 | 处理 |
| --- | --- | --- |
| `BUSINESS_RUN_NOT_FOUND` | runId 不存在 | 核对业务调用记录 |
| `BUSINESS_OUTPUT_REVIEW_ITEMS_REQUIRED` | `items` 为空 | 至少提交一条输出复盘 |
| `BUSINESS_OUTPUT_REVIEW_LIMIT_EXCEEDED` | 单次超过 100 条 | 分批提交 |
| `BUSINESS_OUTPUT_REVIEW_GRADE_INVALID` | `qualityGrade` 非法 | 使用本文第 3 节定义的质量档位 |
| `BUSINESS_OUTPUT_REVIEW_ACTION_INVALID` | `nextAction` 非法 | 使用本文第 4 节定义的建议动作 |

#### GET `/api/admin/business/output-reviews/summary`

用途：按近窗口聚合质量复盘结果，用于业务能力页 TopN；默认版本切换门禁也会读取同一张 `business_output_reviews` 表，但按候选业务版本过滤近 168 小时证据。

查询参数：

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `window_hours` | `168` | 统计窗口，1-2160 小时 |
| `business_key` | 空 | 可选，按业务过滤 |
| `version` | 空 | 可选，按业务版本过滤 |
| `limit` | `20` | 最近记录数量，1-100 |

响应：

```json
{
  "windowHours": 168,
  "filters": {"window_hours": 168, "business_key": null, "version": null, "limit": 20},
  "total": 12,
  "byGrade": [{"key": "usable", "label": "可用", "total": 8}],
  "byBusiness": [
    {
      "businessKey": "fission",
      "label": "图裂变",
      "total": 5,
      "reviewed": 5,
      "bad": 1,
      "topIssueTags": [
        {
          "key": "结构偏移",
          "label": "结构偏移",
          "total": 1,
          "sampleReviews": [
            {
              "id": "bizreview_xxx",
              "runId": "run_xxx",
              "businessKey": "fission",
              "outputIndex": 0,
              "outputUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/...",
              "qualityGrade": "bad",
              "inputTags": ["满版图案"],
              "issueTags": ["结构偏移"],
              "createdAt": "2026-05-26T00:00:00",
              "updatedAt": "2026-05-26T00:00:00"
            }
          ]
        }
      ],
      "topInputTags": [{"key": "满版图案", "label": "满版图案", "total": 2, "sampleReviews": []}]
    }
  ],
  "topIssueTags": [],
  "topInputTags": [],
  "byVersion": [
    {
      "businessKey": "fission",
      "version": "gpt-image2-vl-v2",
      "businessVersionId": "bizver_xxx",
      "label": "图裂变 · gpt-image2-vl-v2",
      "total": 4,
      "reviewed": 4,
      "good": 2,
      "risk": 1,
      "topIssueTags": [{"key": "结构偏移", "label": "结构偏移", "total": 1, "sampleReviews": []}],
      "topInputTags": [{"key": "满版图案", "label": "满版图案", "total": 2, "sampleReviews": []}],
      "sampleReviews": []
    }
  ],
  "byBatch": [
    {
      "batchId": "qsample-fission-1770000000000",
      "businessKey": "fission",
      "sampleKey": "dense-pattern",
      "sampleLabel": "满版图案",
      "label": "图裂变 · 满版图案",
      "total": 4,
      "reviewed": 4,
      "good": 2,
      "risk": 1,
      "versions": [
        {
          "businessVersionId": "biz_fission_v1",
          "version": "v1",
          "label": "v1",
          "total": 2,
          "reviewed": 2,
          "good": 1,
          "risk": 1,
          "sampleReviews": []
        }
      ],
      "topIssueTags": [],
      "topInputTags": [],
      "sampleReviews": []
    }
  ],
  "recentReviews": []
}
```

#### GET `/api/admin/business/output-reviews/export`

用途：导出近窗口质量复盘明细，运营可按 `batchId` 复盘同一批固定样例在默认版/候选版上的表现，也可导出业务窗口内全部标注结果。

查询参数：

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `window_hours` | `168` | 导出窗口，1-2160 小时 |
| `business_key` | 空 | 可选，按业务过滤 |
| `version` | 空 | 可选，按业务版本过滤 |
| `batch_id` | 空 | 可选，按固定样例复跑批次过滤 |
| `limit` | `5000` | 最大导出行数，1-10000 |

响应：`text/csv; charset=utf-8`，带 UTF-8 BOM。列包含 `batch_id`、业务、样例 Key、样例名称、runId、版本 ID、版本、输出序号、质量档位、下一步动作、输入标签、问题标签、输出 URL、备注、标注人、创建时间、更新时间。

错误：

| 错误码 | 场景 | 处理 |
| --- | --- | --- |
| `ADMIN_ONLY` | 非管理员访问 | 使用管理员账号 |
| `422` | 查询参数超出范围 | 修正 `window_hours` / `limit` |

默认切换门禁：

2026-06-12 口径调整：业务结果质量判断以后以看板侧为准。中台 `business_output_reviews`
属于历史观察表，不再阻断发版、默认切换或 release smoke。核心能力是否可封版，
必须回到真实接口巡检、runId、结果图、执行节点和看板侧质量结论。

| 规则 | 结果 |
| --- | --- |
| 核心业务候选版本近 168 小时没有中台质量复盘记录 | 不阻断；看板侧质检为准 |
| 已复盘但没有 `excellent` / `usable` 样本 | 不阻断；仅作为历史观察 |
| 已有可用样本，但同时存在 `borderline` / `bad` / `blocked` | 不阻断；看板侧决定是否复核或分流 |

## 6. 迭代节奏

- 每日：抽看最近成功样本，标出明显不可用和异常类型。
- 每周：每个核心业务固定样例池跑一批，输出 TopN 质量问题。
- 切默认前：必须对当前默认和候选版本跑同一批固定样例，保留样例、标签、结论和回滚口径。

## 7. 验收标准

- 运营能看懂哪几个业务现在值得推荐。
- 能力工程师能看到哪类输入图效果差，并知道应该调参、分流还是换 LoRA。
- 运维能区分链路故障和质量问题，不把节点失败误判成效果差。
- 默认版本切换有样例证据，不再只凭单张测试图或主观印象。
