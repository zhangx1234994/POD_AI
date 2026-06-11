# 中台运行事实与回归防错口径

最后更新：2026-06-10

本文只记录当前执行必须依赖的固定事实和高频回归防线。任何排查、发版、验收、文档更新，先对照本文，避免靠临时记忆判断。

## 1. 服务器与端口固定口径

| 名称 | 机器 / 地址 | 职责 | 固定端口 | 备注 |
| --- | --- | --- | --- | --- |
| 114 控制面 | `114.55.0.56` | backend、管理端、测评端、Coze 接入控制 | backend `8099`；管理端 `8199`；测评端 `8200`；Coze `8888` | 业务状态、任务、路由、接口文档、OSS 回填和管理端都在这里闭环。 |
| 158 / 5090 | `117.50.80.158` | GPU 执行面、image-ops、vendor-api-ops | ComfyUI `8079`；image-ops `8200`；vendor-api-ops `8310` | executor ID：`executor_comfyui_pattern_extract_158`。 |
| 233 / 4090 | `117.50.216.233` | GPU 执行面 | ComfyUI `8079` | executor ID：`executor_comfyui_seamless_117`。 |

硬规则：

- 任何沟通、日志、复盘和发布记录禁止只写“117 服务器”。必须写清 `158/5090/117.50.80.158` 或 `233/4090/117.50.216.233`。
- 114 是控制面；158 和 233 是执行面。普通 backend、管理端、测评端发版不应该更新 GPU 机器。
- ComfyUI 公网端口可能有白名单。开发机直连 `117.*:8079` 超时或 502，不能直接判断 GPU 服务异常；最终以 114 控制面或已放行机器上的 `/system_stats`、`/queue`、`/object_info` 为准。
- 本地临时静态代理可以为了避开端口占用使用 `8299` 等端口，但必须在报告中写成“本地临时端口”。线上和正式脚本口径仍是测评端 `8200`。

## 2. 执行节点命名口径

| executor ID | 标准显示名 | 机器 | 常见用途 |
| --- | --- | --- | --- |
| `executor_comfyui_pattern_extract_158` | ComfyUI 5090 · 158 · 117.50.80.158 | 158 / 5090 | 默认承接多数 ComfyUI 主线能力。 |
| `executor_comfyui_seamless_117` | ComfyUI 4090 · 233 · 117.50.216.233 | 233 / 4090 | 承接通用/备用/部分历史工作流。 |

如果 release smoke 或兼容检查出现缺模型、缺节点，必须先回答三个问题：

1. 报警绑定的是哪个 executor，不能只看 IP 前缀。
2. 这个 workflow 是当前默认主线、候选、保底，还是历史兼容。
3. 当前业务真实路由是否会命中它；如果不会，记录为兼容风险，不直接扩大为线上事故。

## 3. 模型与插件依赖核对

模型和插件缺失要按 workflow 级别核对，不能只看 ComfyUI 服务健康。

当前已知高风险依赖示例：

| 依赖 | 涉及 workflow | 业务位置 | 核对口径 |
| --- | --- | --- | --- |
| `qwen-image/instantx/Qwen-Image-InstantX-ControlNet-Inpainting.safetensors` | `huawen_kuotu`、`qwen2512_print_shape_text_enhance` | 花纹扩图保底版、裂变文字强化 | 从 114 或白名单机器查 ComfyUI `/object_info`；同时注意 workflow JSON 里是否使用反斜杠路径。 |

处理原则：

- 文件系统存在模型，只说明模型已落盘；最终还要确认 ComfyUI `/object_info` 能枚举到同一个相对路径，并且 workflow JSON 使用的路径字符串与 ComfyUI 返回值一致。
- 优先补齐服务器同构，不优先在中台写特殊路由。
- 只有业务止血时才临时限制路由，并写清恢复条件。
- 如果某模型只影响候选/保底工作流，中台无异常不矛盾；但发版兼容检查仍要记录。

## 4. 图片尺寸与 DPI 口径

图片交付有两个不同概念：

- **像素尺寸**：`width/height`、`size`、目标画布、ComfyUI 节点入参和最终输出图片的实际像素。
- **DPI/PPI 元数据**：上传 OSS 前写入的图片元信息，不改变像素尺寸。

硬规则：

- 用户显式传入 `width/height` 时，业务层必须保留目标画布，不允许静默回退成原图尺寸或默认尺寸。
- 底层为了安全倍数做归一化时必须可解释，例如 `228x1350` 进入 ComfyUI 可以归一为 `224x1344`，但不能回到原图 `1072x1344`。
- 验收不能只看接口返回成功；必须核对最终图片像素、实际 ability payload、业务 metadata 和页面展示。
- `OUTPUT_IMAGE_DEFAULT_DPI=150` 只处理结果图元数据，不承担放大、裁切、目标画布修复职责。

图裂变尺寸回归最低测试矩阵：

| 场景 | 预期 |
| --- | --- |
| 不传 `width/height` | 跟随原图或当前业务版本默认策略。 |
| 只传 `width` 或只传 `height` | 按接口契约补齐或拒绝；不能静默产生不可解释尺寸。 |
| 同时传 `width/height` | 显式目标优先，进入 payload 和 metadata。 |
| `size` 预设 + 显式 `width/height` | 显式 `width/height` 优先。 |
| 非 8/16 倍数尺寸 | 按安全倍数归一，metadata 记录请求值和归一值。 |
| 目标比例与原图差异大 | 走比例重构或 `direct_target_size`；不能回退原图尺寸。 |
| 最终出图 | 下载结果图检查像素尺寸，不能只检查 run succeeded。 |

## 5. 发版前必查

涉及 backend、管理端、测评端、业务能力、Agent、路由、图片处理任一项时，发布前至少执行：

```bash
python -m pytest backend/tests/test_business_api_contract.py -q
python -m pytest backend/tests/test_comfyui_new_toolbox_inputs.py -q
cd podi-admin-web && npm run lint
cd ../podi-eval-web && npm run lint
```

发布到 114 后至少执行：

```bash
curl -fsS http://127.0.0.1:8099/health
BACKEND_URL=http://127.0.0.1:8099 \
ADMIN_URL=http://127.0.0.1:8199 \
EVAL_URL=http://127.0.0.1:8200 \
bash scripts/deploy_preflight.sh
backend/.venv/bin/python backend/scripts/podi_release_smoke.py \
  --base-url http://127.0.0.1:8099 \
  --expect-server-url "$(awk -F= '/^PODI_INTERNAL_BASE_URL=/{print $2; exit}' backend/.env)"
```

如果改动影响图片尺寸、路由或结果后处理，还必须补真实业务任务，记录：

```text
业务入口：
runId：
请求尺寸：
实际 payload 尺寸：
metadata 尺寸证据：
结果图片实际像素：
执行节点：
OSS URL：
页面展示：
结论：
```

## 6. 防止重复返工的写法要求

- 结论必须写“当前事实 + 证据 + 风险”，不能只写“应该没问题”。
- 任何“临时绕过”“本地端口”“候选能力”“保底版本”都必须写明，不得混成正式主线。
- 发现回归后，除修代码外，必须同时补：测试断言、接口文档、SOP 或问题日志。缺任意一项都视为未闭环。
