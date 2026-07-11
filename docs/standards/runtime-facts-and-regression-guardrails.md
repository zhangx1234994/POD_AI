# 中台运行事实与回归防错口径

最后更新：2026-07-07

本文只记录当前执行必须依赖的固定事实和高频回归防线。任何排查、发版、验收、文档更新，先对照本文，避免靠临时记忆判断。

## 0. 当前环境总口径（2026-06-20 起）

当前项目已经进入自有商业化准备阶段，运行环境口径发生变化：

- `114.55.0.56` 已移交给之前甲方，**不再作为本项目控制面、测试环境、发布环境或巡检目标使用**。
- 新服务器和新数据库未采购完成前，backend、管理端、测评端、数据库和客户端联调均优先在本机闭环。
- 当前不再把 Coze 作为业务接入或能力编排入口；花纹提取、裂变、扩图、图编辑等能力统一走中台业务 API / 中台能力调度。
- 历史 Coze 文档、脚本和错误码只作为兼容/追溯材料，不作为新开发、测试或验收入口。
- `158/5090/117.50.80.158` 与 `233/4090/117.50.216.233` 两台 ComfyUI 执行面暂时仍可用于业务流程打通和样例验证，但属于过渡资源，后续需要迁移到自有执行资源或第三方按次调用平台。
- `flux2_9b_liebian_sifang` 是连续图候选生成主链路，固定使用 `158/5090/117.50.80.158`。`233/4090/117.50.216.233` 已移交且曾出现异常满负载，不再作为该能力的降级节点；候选生成失败必须明确失败或排队，不能静默切换到 233。
- ComfyUI 服务器历史上存在白名单限制；当前用户会放开白名单以便本机联调。若本机仍连接失败，先按网络/白名单/公网连通性排查，不能直接认定工作流或模型异常。
- 新服务器 / 新数据库采购完成后，必须先更新本文，再更新发布 SOP、环境变量、数据库连接、密钥和验收脚本。

## 0A. 本机验收边界（2026-07-07 起）

当前本机可以启动 backend 做接口、路由、契约和同步能力检查，但如果本机 backend 连接的是远程数据库，后台业务队列会自动禁用，避免开发机误消费线上任务。

这类场景下看到以下现象属于保护机制，不应直接判定为业务失败：

- backend 启动日志出现 `auto disabled on macOS with a remote database`。
- 正式异步业务提交返回 `BACKGROUND_WORKERS_DISABLED`。
- `image-edit/runs`、`fission-evaluate/runs` 等需要后台消费的任务不能在本机完成真实闭环。

本机允许作为验收依据的项目：

- `/health`。
- 业务 OpenAPI / Coze 兼容 OpenAPI 是否可生成。
- `route-preview` 选版是否正确。
- `/api/business/capabilities`、`/api/business/image-edit/component-config` 等只读配置接口。
- 缺参、非法枚举、鉴权失败等提交前错误契约。
- 文字强化裂变第一步 `/api/business/text-fission/prompts` 这类同步准备接口。
- 单元测试、契约测试、脚本语法检查、前端静态包视觉检查。
- ComfyUI 队列概览、workflow compatibility 这类只读兼容检查。

本机不能替代真实业务验收的项目：

- 需要 `BusinessRun` 后台队列消费的异步任务闭环。
- GPU 生图、视频生成、OSS 回填、计费扣减和业务结果入库。
- 多任务并发排队、执行节点真实负载、长任务超时和失败重试。

如果要证明“所有业务真实跑通”，必须使用以下任一环境：

1. 隔离测试数据库 + 本机后台 worker。
2. 新控制面服务器 + 新数据库。
3. 明确批准的线上验收窗口。

不能为了本机快速验证而关闭上述保护机制去消费远程生产/准生产队列。

vendor-api / KIE 本机检查口径：

- `vendor-api-ops` 白名单拒绝（`VENDOR_API_CLIENT_FORBIDDEN`）优先按“调用来源不在白名单”处理，不直接判断模型或业务失败。
- KIE 直连 smoke 需要本地环境变量 `KIE_API_KEY`；仓库、文档和示例文件不得写入真实 key。
- 若 backend 通过中台 Key 池调用 vendor-api-ops，优先检查 Key 池、executor 指向、`VENDOR_API_BASE_URL` 和 `VENDOR_API_ALLOWED_CLIENTS`，不要把 ComfyUI 执行节点加入 vendor-api 白名单。

## 1. 服务器与端口固定口径

| 名称 | 机器 / 地址 | 职责 | 固定端口 | 备注 |
| --- | --- | --- | --- | --- |
| 本机开发 / 当前测试面 | `127.0.0.1` / 本机 | backend、管理端、测评端、本地数据库、客户端联调 | 按本地启动命令；backend 常用 `8099`，管理端常用 `8199`，测评端按本地端口 | 新服务器完成前的默认测试和验收环境。 |
| 114 历史控制面 | `114.55.0.56` | 已移交甲方 | 历史端口：backend `8099`；管理端 `8199`；测评端 `8200`；Coze `8888` | **禁用**：不再连接、不部署、不巡检、不读取数据；仅作为历史记录。 |
| 158 / 5090 | `117.50.80.158` | GPU 执行面、image-ops、vendor-api-ops | ComfyUI `8079`；image-ops `8200`；vendor-api-ops `8310` | executor ID：`executor_comfyui_pattern_extract_158`。 |
| 233 / 4090 | `117.50.216.233` | GPU 执行面 | ComfyUI `8079` | executor ID：`executor_comfyui_seamless_117`。 |

硬规则：

- 任何沟通、日志、复盘和发布记录禁止只写“117 服务器”。必须写清 `158/5090/117.50.80.158` 或 `233/4090/117.50.216.233`。
- 114 现在是历史控制面，不再使用；158 和 233 仅作为临时执行面。普通 backend、管理端、测评端测试在本机完成，后续新服务器上线前不得默认发布到 114。
- ComfyUI 公网端口可能有白名单。开发机直连 `117.*:8079` 超时或 502，不能直接判断 GPU 服务异常；当前以已放行本机、临时本机后端、或后续新控制面复核 `/system_stats`、`/queue`、`/object_info` 为准。
- 本地临时静态代理可以为了避开端口占用使用 `8299` 等端口，但必须在报告中写成“本地临时端口”。新服务器未上线前，本机测试必须写清实际端口，不能沿用历史 114 的端口口径。

## 1A. Coze 退役口径

当前项目彻底放弃 Coze 作为主链路：

- 新业务不再设计 Coze workflow。
- 新接口不再以 `/api/coze/*` 作为交付入口。
- 花纹提取、裂变、扩图、图编辑等能力不再经 Coze 触发，统一走中台业务 API / 能力 API。
- 管理端、测评端、客户端和接口文档应优先展示中台能力，不再把 Coze 工具箱放入主路径。
- 历史 Coze 资料只能用于迁移追溯、旧接口兼容和错误码解释；不得作为当前验收标准。

## 2. 执行节点命名口径

| executor ID | 标准显示名 | 机器 | 常见用途 |
| --- | --- | --- | --- |
| `executor_comfyui_pattern_extract_158` | ComfyUI 5090 · 158 · 117.50.80.158 | 158 / 5090 | 默认承接多数 ComfyUI 主线能力。 |
| `executor_comfyui_seamless_117` | ComfyUI 4090 · 233 · 117.50.216.233 | 233 / 4090 | 承接通用/备用/部分历史工作流。 |

连续图专用补充：`flux2_9b_liebian_sifang` 只允许 `executor_comfyui_pattern_extract_158`；其他历史 workflow 的双机绑定不构成对该能力的回退许可。

如果 release smoke 或兼容检查出现缺模型、缺节点，必须先回答三个问题：

1. 报警绑定的是哪个 executor，不能只看 IP 前缀。
2. 这个 workflow 是当前默认主线、候选、保底，还是历史兼容。
3. 当前业务真实路由是否会命中它；如果不会，记录为兼容风险，不直接扩大为线上事故。

## 3. 模型与插件依赖核对

模型和插件缺失要按 workflow 级别核对，不能只看 ComfyUI 服务健康。

当前已知高风险依赖示例：

| 依赖 | 涉及 workflow | 业务位置 | 核对口径 |
| --- | --- | --- | --- |
| `qwen-image/instantx/Qwen-Image-InstantX-ControlNet-Inpainting.safetensors` | `huawen_kuotu`、`qwen2512_print_shape_text_enhance` | 花纹扩图保底版、裂变文字强化 | 从已放行本机、临时本机后端或未来新控制面查 ComfyUI `/object_info`；同时注意 workflow JSON 里是否使用反斜杠路径。 |

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
- 用户显式传入的业务目标尺寸优先级最高。当前主线图裂变（`flux_strong_hq_softstyle_fission` / `comfyui-vl-control-v2`）必须保持显式 `width/height` 原值，例如 `1000x1600` 必须进入 ComfyUI 节点并输出为 `1000x1600`，不得静默变为 `992x1600`。
- 只有明确依赖 latent 安全倍数的历史工作流才允许做 8/16 倍数归一化；归一化必须在对应能力文档、metadata 或测试断言里可解释，不能作为所有图片能力的默认策略。
- 验收不能只看接口返回成功；必须核对最终图片像素、实际 ability payload、业务 metadata 和页面展示。
- `OUTPUT_IMAGE_DEFAULT_DPI=150` 只处理结果图元数据，不承担放大、裁切、目标画布修复职责。

图裂变尺寸回归最低测试矩阵：

| 场景 | 预期 |
| --- | --- |
| 不传 `width/height` | 跟随原图或当前业务版本默认策略。 |
| 只传 `width` 或只传 `height` | 按接口契约补齐或拒绝；不能静默产生不可解释尺寸。 |
| 同时传 `width/height` | 显式目标优先，进入 payload 和 metadata。 |
| `size` 预设 + 显式 `width/height` | 显式 `width/height` 优先。 |
| 非 8/16 倍数尺寸 | 主线图裂变保持用户显式尺寸；仅历史或明确依赖 latent 倍数的工作流允许归一，并必须记录请求值和实际值。 |
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

发布到远端控制面后至少执行。注意：2026-06-20 起 114 已禁用，以下命令只适用于未来新服务器；在新服务器未就绪前只做本机验证。

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

如果改动影响图片尺寸、路由或结果后处理，还必须补真实业务任务。新服务器未就绪前可在本机 backend + 临时 ComfyUI 执行面跑通，记录：

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
