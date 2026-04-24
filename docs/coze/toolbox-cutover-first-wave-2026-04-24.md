# Coze 工具箱第一段切换清单（2026-04-24）

## 目标

第一段只把 Coze 工具箱入口从旧中台切到 Coze 主机 backend：

- 旧入口：`http://117.50.80.158:8099`
- 新入口：`http://114.55.0.56:8099`

本阶段不调整 `117.50.80.158` 的服务形态，也不把图片原子能力切到远端能力机。

## 已验证前置条件

- `114.55.0.56:8099 /health` 正常
- `114.55.0.56:8099` 的全部静态 OpenAPI 返回 `200`
- `114.55.0.56` 同机 `image-ops` 只监听 `127.0.0.1:8301`
- 12 次主线 workflow smoke 全部成功，详见 `docs/testing/COZE_FIRST_WAVE_SMOKE_2026-04-24.md`

## 第一批建议切换

优先切这些 standalone 工具箱，原因是功能边界清楚、回滚简单。

| 功能 | 旧 OpenAPI | 新 OpenAPI |
| --- | --- | --- |
| 背景抠图 | `http://117.50.80.158:8099/api/coze/podi/comfyui/execute/beijing-koutu/openapi.json` | `http://114.55.0.56:8099/api/coze/podi/comfyui/execute/beijing-koutu/openapi.json` |
| 头部抠像 | `http://117.50.80.158:8099/api/coze/podi/comfyui/execute/toubu-kouxiang/openapi.json` | `http://114.55.0.56:8099/api/coze/podi/comfyui/execute/toubu-kouxiang/openapi.json` |
| FLUX2-Klein 扩图 | `http://117.50.80.158:8099/api/coze/podi/comfyui/execute/flux2-klein-9b-outpaint/openapi.json` | `http://114.55.0.56:8099/api/coze/podi/comfyui/execute/flux2-klein-9b-outpaint/openapi.json` |
| 多图融合 | `http://117.50.80.158:8099/api/coze/podi/comfyui/execute/duotu-ronghe/openapi.json` | `http://114.55.0.56:8099/api/coze/podi/comfyui/execute/duotu-ronghe/openapi.json` |
| E7 裂变重绘 | `http://117.50.80.158:8099/api/coze/podi/comfyui/execute/e7-flux2-liebian/openapi.json` | `http://114.55.0.56:8099/api/coze/podi/comfyui/execute/e7-flux2-liebian/openapi.json` |
| 多元素花纹裂变 | `http://117.50.80.158:8099/api/coze/podi/comfyui/execute/flux-strong-hq-softstyle-fission/openapi.json` | `http://114.55.0.56:8099/api/coze/podi/comfyui/execute/flux-strong-hq-softstyle-fission/openapi.json` |
| FLUX2 裂变+四方 | `http://117.50.80.158:8099/api/coze/podi/comfyui/execute/flux2-9b-liebian-sifang/openapi.json` | `http://114.55.0.56:8099/api/coze/podi/comfyui/execute/flux2-9b-liebian-sifang/openapi.json` |
| 裂变文字强化 | `http://117.50.80.158:8099/api/coze/podi/comfyui/execute/qwen2512-print-shape-text-enhance/openapi.json` | `http://114.55.0.56:8099/api/coze/podi/comfyui/execute/qwen2512-print-shape-text-enhance/openapi.json` |
| 8步加速可换 LoRA | `http://117.50.80.158:8099/api/coze/podi/comfyui/execute/yinhua-tiqu-lora-8step/openapi.json` | `http://114.55.0.56:8099/api/coze/podi/comfyui/execute/yinhua-tiqu-lora-8step/openapi.json` |

## 可同批切换，但建议低优先级

| 工具箱 | 新 OpenAPI | 说明 |
| --- | --- | --- |
| ComfyUI 聚合 | `http://114.55.0.56:8099/api/coze/podi/comfyui/openapi.json` | 如果 Coze 里已经改用 standalone，可暂不切聚合入口 |
| ComfyUI LoRA 查询 | `http://114.55.0.56:8099/api/coze/podi/comfyui/lora/openapi.json` | 查询类，风险低 |
| KIE 聚合 | `http://114.55.0.56:8099/api/coze/podi/kie/openapi.json` | 与本次主线图 workflow 关系较弱 |
| KIE 查询 | `http://114.55.0.56:8099/api/coze/podi/kie/catalog/openapi.json` | 查询类，风险低 |
| Baidu | `http://114.55.0.56:8099/api/coze/podi/baidu/openapi.json` | 如果当前 Coze workflow 没用，可放第二批 |
| Volcengine | `http://114.55.0.56:8099/api/coze/podi/volcengine/openapi.json` | 如果当前 Coze workflow 没用，可放第二批 |

## 本阶段暂缓

| 工具箱 | 原因 |
| --- | --- |
| `http://114.55.0.56:8099/api/coze/podi/utils/openapi.json` | PODI 图片原子能力工具箱，包含高清放大 / DPI / 扩边，占用第二段能力机迁移窗口 |
| `http://114.55.0.56:8099/api/coze/podi/openapi.json` | 聚合全部 provider，可能把 PODI 原子能力一起暴露给 Coze；第一段优先不用聚合入口 |

## 切换动作

执行方式：

1. 使用 `scripts/coze_toolbox_host_cutover.py plan` 只读检查第一批插件。
2. 使用 `scripts/coze_toolbox_host_cutover.py apply` 先备份再切换白名单插件。
3. 只更新 `plugin`、`plugin_draft`、`plugin_version` 的 `server_url` 与 `openapi_doc.servers[0].url`。
4. 不修改 workflow canvas，不修改 tool contract，不修改 PODI Utils / PODI Abilities 聚合插件。

执行结果：

- 第一批 9 个 standalone 插件已切到 `http://114.55.0.56:8099`。
- 回滚脚本可使用 `scripts/coze_toolbox_host_cutover.py rollback`。
- 备份位于 `/srv/pod/runtime/coze_toolbox_apply_20260424_165223.sql`。
- 修正 `COZE_TRUSTED_IPS=114.55.0.56,127.0.0.1` 后，10 条关联 workflow 重跑全部成功。

## 每批验证

每批切换后至少跑：

- 对应 workflow debug
- `POST /api/coze/podi/tasks/get` 轮询
- OSS 最终图片链接打开
- backend 日志无 `401 / 500 / *_REMOTE_FAILED`

## 回滚

如果某个工具箱异常：

1. 使用 `scripts/coze_toolbox_host_cutover.py rollback --plugin-id <plugin_id>` 只回滚该工具箱。
2. 不重启 Coze 主机 backend
3. 不修改 workflow canvas 或工具契约
4. 保留新 backend 继续服务其他已通过工具箱

如果批量异常：

1. 停止继续切换
2. 使用 `scripts/coze_toolbox_host_cutover.py rollback` 把第一批工具箱回到 `117.50.80.158:8099`
3. 保留 Coze 主机 backend 现场，用 smoke 报告和日志定位

## 第二段入口

等第一段稳定后，再处理 `117.50.80.158`：

- 只保留 `8079` ComfyUI 和 `8301` image-ops
- Coze backend 的 `IMAGE_OPS_BASE_URL` 改为 `http://117.50.80.158:8301`
- 再切 PODI 图片原子能力相关工具箱
