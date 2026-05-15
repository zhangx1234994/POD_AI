# Coze 当前能力路由与工具箱切换清单

日期：2026-04-24

## 结论

当前 Coze 控制面已经具备继续切换工具箱的基础：

- Coze 主机 backend：`114.55.0.56:8099`
- 管理端：`114.55.0.56:8199`
- 测评端：`114.55.0.56:8200`
- Coze：`114.55.0.56:8888`
- image-ops：`117.50.80.158:8200`
- vendor-api-ops：`117.50.80.158:8310`

当前核心链路应固定为：

```text
Coze Workflow
  -> Coze 同机 backend
    -> external ComfyUI / image-ops / vendor-api-ops
```

Coze 不应直接调用 ComfyUI、image-ops 或 vendor-api-ops。

## 当前服务健康状态

| 对象 | 地址 | 状态 | 说明 |
| --- | --- | --- | --- |
| backend | `http://114.55.0.56:8099/health` | 正常 | 本机 `/health` 返回 `ok` |
| admin | `http://114.55.0.56:8199` | 正常 | 端口监听中 |
| eval | `http://114.55.0.56:8200` | 正常 | 端口监听中 |
| Coze | `http://114.55.0.56:8888` | 正常 | Docker 端口监听中 |
| image-ops | `http://117.50.80.158:8200/health` | 正常 | Coze 主机可访问 |
| vendor-api-ops | `http://117.50.80.158:8310/health` | 正常 | Coze 主机可访问 |

## 当前 backend 环境口径

| 配置 | 当前值 | 判断 |
| --- | --- | --- |
| `IMAGE_OPS_BASE_URL` | `http://117.50.80.158:8200` | 已外拆 |
| `IMAGE_OPS_LOCAL_FALLBACK_ENABLED` | `false` | 符合 Coze 主机不跑本地图像重任务原则 |
| `DISABLE_LOCAL_HEAVY_IMAGE_TASKS` | `true` | 符合高清放大不落 Coze 主机原则 |
| `VENDOR_API_ENABLED` | `true` | 已启用 vendor-api-ops |
| `VENDOR_API_BASE_URL` | `http://117.50.80.158:8310` | 已指向 158 / 5090 执行面 |
| `VENDOR_API_LEGACY_FALLBACK_ENABLED` | `true` | 迁移期可接受；全量 smoke 后建议关闭 |
| `COZE_TRUSTED_IPS` | `114.55.0.56,127.0.0.1` | 同机 Coze 调用 backend 可通过 |

## 当前 active 能力统计

| provider | active 数量 | 当前路由 |
| --- | ---: | --- |
| `baidu` | 7 | backend 优先路由到 vendor-api-ops domestic |
| `comfyui` | 14 | backend 路由到外部 ComfyUI |
| `kie` | 4 | backend 优先路由到 vendor-api-ops domestic |
| `openai` | 1 | backend 路由到 vendor-api-ops global-egress |
| `podi` | 3 | backend 路由到 image-ops |
| `volcengine` | 5 | backend 优先路由到 vendor-api-ops domestic |

## 当前 executor 状态

| executor | type | baseUrl | 状态 | 判断 |
| --- | --- | --- | --- | --- |
| `executor_vendor_api_domestic_default` | `vendor_api` | `http://117.50.80.158:8310` | active | 国内三方 API 执行面，承载 baidu/volcengine/kie |
| `executor_vendor_api_global_default` | `vendor_api` | `http://117.50.80.158:8310` | active | global-egress 执行面，承载 openai/openai_compatible |
| `executor_comfyui_pattern_extract_158` | `comfyui` | `http://117.50.80.158:8079` | active | 158 / 5090 ComfyUI 通用节点 |
| `executor_comfyui_seamless_117` | `comfyui` | `http://117.50.216.233:8079` | active | 233 / 4090 ComfyUI 通用节点 |
| `executor_baidu_image_default` | `baidu` | `https://aip.baidubce.com` | active | legacy executor，迁移期 fallback 仍可能使用 |
| `executor_volcengine_default` | `volcengine` | `https://ark.cn-beijing.volces.com` | active | legacy executor，迁移期 fallback 仍可能使用 |
| `executor_kie_market_default` | `kie` | `https://api.kie.ai` | active | legacy executor，迁移期 fallback 仍可能使用 |
| `executor_mock_history_history_success_no_images_62359` | `comfyui` | `http://127.0.0.1:62359` | inactive | 已禁用，避免测试 executor 被误选 |

## 当前能力路由清单

### ComfyUI 能力

| capability | 展示名 | workflow | 当前 executor 约束 | Coze 可见性 |
| --- | --- | --- | --- | --- |
| `beijing_koutu` | 背景抠图 | `beijing_koutu` | 158 / 5090 + 233 / 4090 通用节点 | 默认可见 |
| `duotu_ronghe` | 多图融合 | `duotu_ronghe` | 158 / 5090 + 233 / 4090 通用节点 | 默认可见 |
| `e7_flux2_liebian` | E7裂变重绘 | `e7_flux2_liebian` | 158 / 5090 + 233 / 4090 通用节点 | 默认可见 |
| `flux2_9b_liebian_sifang` | FLUX2裂变+四方 | `flux2_9b_liebian_sifang` | 158 / 5090；233 缺 `String` 前不参与 | presentation 标记 `coze=false` |
| `flux2_klein_9b_outpaint` | FLUX2-Klein 扩图 | `flux2_klein_9b_outpaint` | 158 / 5090 + 233 / 4090 通用节点 | presentation 标记 `coze=true` |
| `flux_strong_hq_softstyle_fission` | 多元素花纹裂变 | `flux_strong_hq_softstyle_fission` | 158 / 5090 + 233 / 4090 通用节点 | presentation 标记 `coze=true` |
| `huawen_kuotu` | 花纹扩图 | `huawen_kuotu` | 158 / 5090；233 缺 `String` 前不参与 | 已 deprecated / hidden |
| `jisu_chuli` | 极速处理版 | `jisu_chuli` | 158 / 5090 + 233 / 4090 通用节点 | 默认可见 |
| `qwen2512_print_shape_text_enhance` | 裂变文字强化 | `qwen2512_print_shape_text_enhance` | 158 / 5090 + 233 / 4090 通用节点 | presentation 标记 `coze=true` |
| `sifang_lianxu` | 四方连续 | `sifang_lianxu` | 158 / 5090；233 缺 `String` 前不参与 | presentation 标记 `coze=false` |
| `toubu_kouxiang` | 头部抠像 | `toubu_kouxiang` | 158 / 5090 + 233 / 4090 通用节点 | 默认可见 |
| `yinhua_tiqu` | 印花提取 | `yinhua_tiqu` | 158 / 5090 + 233 / 4090 通用节点 | presentation 标记 `coze=true` |
| `yinhua_tiqu_lora_8step` | 8步加速可换LoRA | `yinhua_tiqu_lora_8step` | 158 / 5090 + 233 / 4090 通用节点 | 默认可见 |
| `zhongsu_tisheng` | 中速提质版 | `zhongsu_tisheng` | 158 / 5090 + 233 / 4090 通用节点 | 默认可见 |

说明：

- 当前 ComfyUI 能力仍使用 `allowed_executor_ids` 明确分流。
- `required_executor_tags` 为空，虽然 executor 自身带 `comfyui-general` tag，但能力侧尚未强制按 tag 过滤。
- `fallback_to_default=true` 仍存在，后续重任务或专机任务必须改为 `false`。

### image-ops 能力

| capability | operation | heavy | local fallback | 当前判断 |
| --- | --- | ---: | --- | --- |
| `expand_mask_color` | `expand-mask-color` | false | 允许定义层 fallback，但线上关闭 | 已外拆到 image-ops |
| `set_dpi` | `set-dpi` | false | 允许定义层 fallback，但线上关闭 | 已外拆到 image-ops |
| `upscale_resize` | `upscale-resize` | true | false | 符合高清/重能力不落 Coze 主机原则 |

### vendor-api-ops 能力

| provider | capability | 当前路由 | 备注 |
| --- | --- | --- | --- |
| `openai` | `gpt_image_2_edit` | vendor-api-ops global-egress | 新接入能力，不应走 backend legacy |
| `baidu` | `colourize` / `contrast_enhance` / `dehaze` / `denoise` / `quality_upgrade` / `remove_moire` / `stretch_restore` | vendor-api-ops domestic preferred | 仍有 legacy fallback executor |
| `volcengine` | `doubao_seedance_1_5_pro` / `doubao_seedream_4_0` / `doubao_seedream_4_5` / `doubao_seed_2_0_lite` / `doubao_seed_1_6_lite` / `doubao_seed_1_8` | vendor-api-ops domestic preferred | 当前 VL 统一走 Doubao-Seed-2.0-lite，1.8 仅保留历史兼容 |
| `kie` | `flux2_pro_image_to_image` / `nano_banana_2_image_to_image` / `nano_banana_pro_image_to_image` / `sora2_pro_text_to_video` | vendor-api-ops domestic preferred | 仍有 legacy fallback executor |

## 工具箱 OpenAPI 公网可导入状态

### 当前公网 200

这些 URL 已经可以从公网直接访问，适合用于 Coze 重新导入或灰度。执行接口仍受内网/Token 鉴权保护。

| 工具箱 | OpenAPI |
| --- | --- |
| PODI 聚合工具箱 | `http://114.55.0.56:8099/api/coze/podi/openapi.json` |
| PODI Utils | `http://114.55.0.56:8099/api/coze/podi/utils/openapi.json` |
| ComfyUI 聚合工具箱 | `http://114.55.0.56:8099/api/coze/podi/comfyui/openapi.json` |
| ComfyUI LoRA 查询 | `http://114.55.0.56:8099/api/coze/podi/comfyui/lora/openapi.json` |
| 多图融合 | `http://114.55.0.56:8099/api/coze/podi/comfyui/execute/duotu-ronghe/openapi.json` |
| 8步加速可换LoRA | `http://114.55.0.56:8099/api/coze/podi/comfyui/execute/yinhua-tiqu-lora-8step/openapi.json` |
| E7裂变重绘 | `http://114.55.0.56:8099/api/coze/podi/comfyui/execute/e7-flux2-liebian/openapi.json` |
| 多元素花纹裂变 | `http://114.55.0.56:8099/api/coze/podi/comfyui/execute/flux-strong-hq-softstyle-fission/openapi.json` |
| 背景抠图 | `http://114.55.0.56:8099/api/coze/podi/comfyui/execute/beijing-koutu/openapi.json` |
| 头部抠像 | `http://114.55.0.56:8099/api/coze/podi/comfyui/execute/toubu-kouxiang/openapi.json` |
| FLUX2-Klein 扩图 | `http://114.55.0.56:8099/api/coze/podi/comfyui/execute/flux2-klein-9b-outpaint/openapi.json` |
| FLUX2裂变+四方 | `http://114.55.0.56:8099/api/coze/podi/comfyui/execute/flux2-9b-liebian-sifang/openapi.json` |
| 裂变文字强化 | `http://114.55.0.56:8099/api/coze/podi/comfyui/execute/qwen2512-print-shape-text-enhance/openapi.json` |
| KIE 模型查询 | `http://114.55.0.56:8099/api/coze/podi/kie/catalog/openapi.json` |
| KIE 单模型查询示例 | `http://114.55.0.56:8099/api/coze/podi/kie/catalog/nano-banana-pro-image-to-image/openapi.json` |
| KIE 单模型执行示例 | `http://114.55.0.56:8099/api/coze/podi/kie/execute/nano-banana-pro-image-to-image/openapi.json` |
| KIE 聚合执行工具箱 | `http://114.55.0.56:8099/api/coze/podi/kie/openapi.json` |
| Baidu 聚合工具箱 | `http://114.55.0.56:8099/api/coze/podi/baidu/openapi.json` |
| Volcengine 聚合工具箱 | `http://114.55.0.56:8099/api/coze/podi/volcengine/openapi.json` |

## 切换前阻塞项

1. `VENDOR_API_LEGACY_FALLBACK_ENABLED=true` 仍允许 baidu/volcengine/kie 在 vendor-api-ops 失败时回落到 legacy executor；全量 smoke 后应关闭。
2. ComfyUI 能力侧 `required_executor_tags` 为空，后续新增专机能力时必须显式补 tag 和 `fallback_to_default=false`。
3. OpenAPI 文档可公网导入，但实际执行接口仍受内网/Token 鉴权约束；切换 Coze 工具箱后必须逐条跑 workflow smoke。

## 建议切换顺序

### 第一批：只切 standalone ComfyUI 工具箱

优先切这些，因为 OpenAPI 已公网 200，能力契约清晰，且执行面不在 Coze 主机：

1. 背景抠图
2. 头部抠像
3. 多图融合
4. FLUX2-Klein 扩图
5. 多元素花纹裂变
6. E7 裂变重绘
7. 裂变文字强化

每切一个工具箱，立即验证：

- 工具箱导入成功
- main workflow 能提交
- 返回 `taskId`
- `/api/coze/podi/tasks/get` 能拿终态
- OSS 链接可访问

### 第二批：切 KIE 单模型工具箱

优先切单模型执行工具箱，不先切 KIE 聚合工具箱：

1. Nano Banana Pro 图生图
2. Nano Banana 2 图生图
3. Flux-2 Pro 图生图
4. Sora2 Pro 文生视频

切换前需要确认 vendor-api-ops 中对应 provider key、并发、轮询策略已经可观测。

### 第三批：处理聚合工具箱

如果业务确实需要聚合工具箱，再导入：

- `/api/coze/podi/openapi.json`
- `/api/coze/podi/comfyui/openapi.json`
- `/api/coze/podi/kie/openapi.json`
- `/api/coze/podi/baidu/openapi.json`
- `/api/coze/podi/volcengine/openapi.json`

默认仍建议保持单功能工具箱为主，降低 Coze 编排误用风险。

## 下一步执行项

1. 对第一批 standalone ComfyUI 工具箱做逐条 Coze 导入和 smoke。
2. 对 KIE 单模型执行工具箱做逐条 Coze 导入和 smoke。
3. smoke 稳定后关闭 `VENDOR_API_LEGACY_FALLBACK_ENABLED`，让三方 API 迁移边界变清晰。
4. 后续新增能力必须进入此清单，至少记录：provider、capability、执行面、OpenAPI、Coze 可见性、回滚方式。
