# Coze 控制面迁移真实对象清单 v1

> 目的：把迁移当天真正要切换的 host、服务、工具箱、工作流、配置文件固定成对象清单。  
> 范围：只记录当前仓库和 Coze 真源里已经存在、且会影响切换结果的对象。  
> 核对时间：2026-04-23

## 1. 当前真实主机与职责

| 对象 | 当前地址 / 位置 | 当前职责 | 迁移后目标 |
| --- | --- | --- | --- |
| Coze 主机 | `114.55.0.56:8888` | Coze 画布、workflow 真源、Coze MySQL/Redis/服务容器 | 同机承载 Coze + backend 控制面 |
| 旧 backend 主机 | `117.50.80.158:8099` | 中台 API、OpenAPI、任务查询、管理/评测依赖接口 | 迁出控制面职责，保留为回滚目标 |
| ComfyUI 节点 A | `117.50.216.233:8079` | 四方连续及通用 ComfyUI 执行 | 继续只做执行节点 |
| ComfyUI 节点 B | `117.50.80.158:8079` | 印花提取、裂变、扩图等通用 ComfyUI 执行 | 继续只做执行节点 |
| `image-ops` | 当前在 backend 本地实现 | `upscale_resize / set_dpi / expand_mask_color` | 独立服务，默认 `8301` |

## 2. 迁移当天必须切换的 backend 相关对象

### 2.1 对外入口

这些入口迁移后都必须统一落到 **Coze 同机 backend host**：

- `/api/coze/podi/openapi.json`
- `/api/coze/podi/comfyui/openapi.json`
- `/api/coze/podi/utils/openapi.json`
- `/api/coze/podi/tasks/get`
- `/api/coze/podi/comfyui/queue-summary`
- `/api/coze/podi/comfyui/lora-catalog`
- `/api/coze/podi/comfyui/lora-catalog/default`

### 2.2 单功能 ComfyUI 工具箱

这些是迁移当天必须逐条校验的独立 toolbox：

| OpenAPI | 实际工具路径 | 说明 |
| --- | --- | --- |
| `/api/coze/podi/comfyui/execute/duotu-ronghe/openapi.json` | `/api/coze/podi/tools/comfyui/duotu_ronghe` | 多图融合 |
| `/api/coze/podi/comfyui/execute/yinhua-tiqu-lora-8step/openapi.json` | `/api/coze/podi/tools/comfyui/yinhua_tiqu_lora_8step` | 8 步加速可换 LoRA |
| `/api/coze/podi/comfyui/execute/e7-flux2-liebian/openapi.json` | `/api/coze/podi/tools/comfyui/e7_flux2_liebian` | E7 图裂变 |
| `/api/coze/podi/comfyui/execute/flux-strong-hq-softstyle-fission/openapi.json` | `/api/coze/podi/tools/comfyui/flux_strong_hq_softstyle_fission` | 新高质量裂变 |
| `/api/coze/podi/comfyui/execute/beijing-koutu/openapi.json` | `/api/coze/podi/tools/comfyui/beijing_koutu` | 背景抠图 |
| `/api/coze/podi/comfyui/execute/toubu-kouxiang/openapi.json` | `/api/coze/podi/tools/comfyui/toubu_kouxiang` | 头部抠像 |
| `/api/coze/podi/comfyui/execute/flux2-klein-9b-outpaint/openapi.json` | `/api/coze/podi/tools/comfyui/flux2_klein_9b_outpaint` | 新扩图 |
| `/api/coze/podi/comfyui/execute/flux2-9b-liebian-sifang/openapi.json` | `/api/coze/podi/tools/comfyui/flux2_9b_liebian_sifang` | 四方连续裂变 |
| `/api/coze/podi/comfyui/execute/qwen2512-print-shape-text-enhance/openapi.json` | `/api/coze/podi/tools/comfyui/qwen2512_print_shape_text_enhance` | 裂变文字强化 |

## 3. Coze 工作流真实清单（迁移抽检对象）

### 3.1 当前主工作流

| workflow_id | 名称 | 用途 |
| --- | --- | --- |
| `7598563505054154752` | `lianxu` | 四方连续 |
| `7598587935331450880` | `comfyuo_tukuozhan` | 旧扩图 |
| `7631174682116358144` | `comfyuo_tukuozhan_1` | 新扩图 |
| `7615600173695107072` | `comfyui_duotu` | 多图融合 |
| `7629023903431524352` | `koubeijing` | 背景抠图 |
| `7629023041988591616` | `koutou` | 头部抠像 |
| `7622190276932534272` | `Liebian_comfyui_zaod` | E7 图裂变（有 prompt） |
| `7622193261276299264` | `Liebian_comfyui_zaod_1` | E7 图裂变（无 prompt） |
| `7629024620879806464` | `Liebian_comfyui_wenzi` | 裂变文字强化 |
| `7629026792103215104` | `Liebian_comfyui_wenzi_1` | 四方连续裂变 |
| `7631838631375667200` | `Liebian_comfyui_20260423` | 新高质量裂变 |

### 3.2 历史 / 兼容工作流

| workflow_id | 名称 | 说明 |
| --- | --- | --- |
| `7597530887256801280` | `tiqu_comfyui_20260123` | 印花提取历史链路 |
| `7598545860393172992` | `tiqu_comfyui_20260123_2` | 印花提取历史链路 |
| `7598559869544693760` | `tiqu_duoMoxing_2_1` | 印花提取历史链路 |
| `7601080398864449536` | `tiqu_duoMoxing_20260130` | 印花提取历史链路 |
| `7598820684801769472` | `Liebian_comfyui_20260124` | 裂变历史链路 |
| `7598841920114130944` | `Liebian_comfyui_20260124_1` | 裂变历史链路 |

### 3.3 内部辅助工作流

| workflow_id | 名称 | 用途 |
| --- | --- | --- |
| `7597556718159003648` | `comfyui_huidiao` | 回调取图 |
| `7601054603211177984` | `comfyui_duilie` | 队列监控 |

## 4. 当前仓库里需要改 host 的文件清单

### 4.1 必须在迁移批次里处理

| 文件 | 当前内容 | 迁移要求 |
| --- | --- | --- |
| `config/executors.yaml` | 当前 ComfyUI 指向 `117.50.216.233:8079` / `117.50.80.158:8079` | 保留为执行节点，不改成 Coze 主机 |
| `backend/.env` | 当前 backend 环境变量真源 | 切到 Coze 同机数据库、Redis、OSS、image-ops |
| `image-ops-service/.env` | 新服务环境变量 | 明确鉴权 token、端口、临时目录 |
| `docker-compose.image-ops.yml` | `image-ops` 部署模板 | 迁移时可直接启动或按模板落 systemd |
| `scripts/check_coze_control_plane_bundle.sh` | bundle 联调脚本 | 迁移当天必须实际执行 |

### 4.2 必须在迁移后复核

| 文件 | 当前内容 | 说明 |
| --- | --- | --- |
| `podi-admin-web/nginx.conf` | `proxy_pass http://127.0.0.1:8099` | 如果 admin 同机部署，保持同机代理即可 |
| `podi-eval-web/nginx.conf` | `proxy_pass http://127.0.0.1:8099` | 如果 eval 同机部署，保持同机代理即可 |
| `scripts/prodlike_restart_web_static.sh` | 默认反代到 `127.0.0.1:8099` | 同机部署时有效，迁移后只需确认 backend 本机可达 |
| `scripts/node_static_proxy.mjs` | 依赖 `--api http://127.0.0.1:8099` | 同机静态站点运行时复核 |

### 4.3 暂不纳入首轮切换，但必须登记

| 文件 | 当前内容 | 处理策略 |
| --- | --- | --- |
| `comfyui-desktop/installer/podi-agent.iss` | `http://117.50.80.158:8099` | 第二阶段统一改到新 backend host |
| `comfyui-desktop/installer/install_windows.ps1` | `http://117.50.80.158:8099` | 第二阶段统一切换 |
| `comfyui-desktop/installer/build_windows.ps1` | `http://117.50.80.158:8099` | 第二阶段统一切换 |
| `comfyui-desktop/installer/publish_windows_release.ps1` | `http://117.50.80.158:8099` | 第二阶段统一切换 |
| `comfyui-desktop/README.md` | `http://117.50.80.158:8099` | 第二阶段同步文档更新 |

## 5. `image-ops` 迁移对象

当前纳入 `image-ops` 管理的能力只有 3 条：

| ability_id | operation | heavy | local_fallback_allowed |
| --- | --- | --- | --- |
| `expand_mask_color` | `expand-mask-color` | `false` | `true` |
| `set_dpi` | `set-dpi` | `false` | `true` |
| `upscale_resize` | `upscale-resize` | `true` | `false` |

迁移当天约束：

- `IMAGE_OPS_BASE_URL` 必须指向新 `image-ops`
- `IMAGE_OPS_LOCAL_FALLBACK_ENABLED=false`
- `DISABLE_LOCAL_HEAVY_IMAGE_TASKS=true`

## 6. 当前已知硬编码 / 特殊 host 风险

### 6.1 需要清掉的风险值

- `http://117.50.80.158:8099`
- `http://127.0.0.1:8099`
- `http://host.docker.internal:8099`

### 6.2 风险说明

- `117.50.80.158:8099`
  - 代表旧 backend host
  - 不能继续出现在 Coze toolbox、桌面端正式包、运维说明里
- `127.0.0.1:8099`
  - 只允许出现在“同机部署”的本地代理和联调脚本里
  - 不能被外部导入的 toolbox 文档直接引用
- `host.docker.internal`
  - 只允许本地 Docker 调试使用
  - 不允许泄漏进线上 OpenAPI

## 7. 迁移当天最小核对顺序

1. 先核新 backend 与 `image-ops` 健康
2. 再核 `config/executors.yaml` 仍然指向外部 ComfyUI
3. 再核所有 toolbox OpenAPI 都指向新 backend host
4. 再抽检上表中的 Coze 主工作流
5. 最后再处理 admin/eval 是否同机迁移

## 8. 最小结论

迁移当天真正要切的是：

- backend host
- image-ops host
- toolbox host

迁移当天**不能动**的是：

- ComfyUI executor host 的执行职责
- 高清放大落地策略
- Coze workflow 的参数 contract
