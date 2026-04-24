# Coze 第一段控制面 Smoke 记录（2026-04-24）

## 范围

本次只验证第一段迁移：

- Coze 主机 `114.55.0.56`
- backend `8099`
- 同机 `image-ops` `127.0.0.1:8301`
- 不替换 Coze 工具箱
- 不调整 `117.50.80.158` 的服务形态

## 部署状态

- `podi-backend`：active
- `image-ops`：active
- `8099`：公网可访问
- `8301`：只监听 `127.0.0.1`，公网不可访问
- `8199 / 8200`：未启动，本阶段不迁移前端

## 控制面检查

通过：

- `/health`
- `/api/abilities`
- `/api/evals/workflow-versions`
- `/api/coze/podi/openapi.json`
- `/api/coze/podi/comfyui/openapi.json`
- `image-ops /health`

## 图片原子能力检查

命令：

```bash
python3 scripts/smoke_image_ops_via_backend.py \
  --backend-base http://127.0.0.1:8099 \
  --backend-env-file /srv/pod/backend/.env \
  --require-remote-image-ops
```

结果：通过。

覆盖能力：

- `expand_mask_color`
- `set_dpi`
- `upscale_resize`

环境约束已满足：

- `IMAGE_OPS_BASE_URL=http://127.0.0.1:8301`
- `IMAGE_OPS_LOCAL_FALLBACK_ENABLED=false`
- `DISABLE_LOCAL_HEAVY_IMAGE_TASKS=true`

## Coze Workflow Smoke

输入图：

- `/srv/pod/runtime/coze_smoke_input.jpg`

报告：

- `/srv/pod/runtime/coze_primary_workflows_20260424_153241.json`
- `/srv/pod/runtime/coze_primary_workflows_20260424_153241.md`
- `/srv/pod/runtime/coze_primary_workflows_20260424_153719.json`
- `/srv/pod/runtime/coze_primary_workflows_20260424_153719.md`

全量结果：12 次提交全部成功，任务最终均为 `succeeded`。

通过 workflow：

- `7598563505054154752` 两方四方连续图
- `7598587935331450880` ComfyUI 扩图
- `7631174682116358144` ComfyUI 扩图 · `flux2_klein_9b_outpaint`
- `7629026792103215104` 四方连续裂变 · `flux2_9b_liebian_sifang`
- `7622190276932534272` 图裂变 · `Liebian_comfyui_20260328`
- `7622193261276299264` 图裂变 · `Liebian_comfyui_20260328_1`
- `7631838631375667200` 图裂变 · `Liebian_comfyui_20260423`
- `7629024620879806464` 文字增强 · `qwen2512_print_shape_text_enhance`
- `7615600173695107072` 多图融合 · `duotu_ronghe`
- `7629023041988591616` 头部抠像 · `toubu_kouxiang`
- `7629023903431524352` 背景抠图 · `beijing_koutu`

## 发现与修正

- 部署脚本原先会整体替换目录，存在擦除服务器 `.env` 的风险；已改为同步时保留 `.env`。
- macOS 打包会带入 `._*` AppleDouble 文件，Alembic 会把它们误当迁移文件；已在部署同步后删除 `._*`。
- smoke 脚本对指定 workflow id 未去重，导致 `7629026792103215104` 在全量报告中重复执行；已改为按请求清单顺序执行且同一 id 只跑一次。

## 当前结论

第一段“Coze 主机 backend + 同机 image-ops”已经具备切 toolbox 前的基础条件。

下一步仍不直接切换全部工具箱，建议先整理 toolbox host 替换清单和回滚清单，再按批次替换。

## 第一批 Toolbox 切换后 Smoke

切换时间：2026-04-24

已切换范围：

- 仅第一批 standalone ComfyUI 工具箱
- 旧入口：`http://117.50.80.158:8099`
- 新入口：`http://114.55.0.56:8099`
- 未切换：`PODI Utils`、`PODI Abilities` 聚合工具箱、图片原子能力聚合入口

备份：

- `/srv/pod/runtime/coze_toolbox_apply_20260424_165223.sql`
- `/srv/pod/runtime/coze_toolbox_post_apply_20260424_165300.sql`

第一次全量 active workflow 巡检报告：

- `/srv/pod/runtime/coze_first_wave_after_toolbox_cutover_20260424.json`
- `/srv/pod/runtime/coze_first_wave_after_toolbox_cutover_20260424.md`

发现：

- 第一批 standalone workflow 初次失败不是 OpenAPI 契约问题，而是新 backend 返回 `401 INTERNAL_ONLY`。
- 后端日志显示 Coze 调工具时来源 IP 为 `114.55.0.56`。
- Coze 主机 backend `.env` 当时没有配置 `COZE_TRUSTED_IPS`。

修正：

- 已在 Coze 主机 backend `.env` 增加 `COZE_TRUSTED_IPS=114.55.0.56,127.0.0.1`。
- 已重启 `podi-backend`，`/health` 正常。

修正后第一批 workflow 重跑报告：

- `/srv/pod/runtime/coze_first_wave_after_trusted_ips_20260424.json`
- `/srv/pod/runtime/coze_first_wave_after_trusted_ips_20260424.md`

重跑 workflow：

- `7629026792103215104` 四方连续裂变 · `flux2_9b_liebian_sifang`
- `7598587935331450880` ComfyUI 扩图
- `7631174682116358144` ComfyUI 扩图 · `flux2_klein_9b_outpaint`
- `7622190276932534272` 图裂变 · `Liebian_comfyui_20260328`
- `7622193261276299264` 图裂变 · `Liebian_comfyui_20260328_1`
- `7631838631375667200` 图裂变 · `Liebian_comfyui_20260423`
- `7629024620879806464` 文字增强 · `qwen2512_print_shape_text_enhance`
- `7615600173695107072` 多图融合 · `duotu_ronghe`
- `7629023041988591616` 头部抠像 · `toubu_kouxiang`
- `7629023903431524352` 背景抠图 · `beijing_koutu`

结果：10 条全部提交成功，pending 任务二次轮询后均为 `succeeded`。

收尾确认：

- 近 10 分钟 `podi-backend` 日志无新增 `401`。
- `PODI Utils` 与 `PODI Abilities` 聚合插件仍保持 `http://117.50.80.158:8099`，未纳入第一批切换。
