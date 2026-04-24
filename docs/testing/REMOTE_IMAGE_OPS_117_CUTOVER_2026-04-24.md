# 117 Image Ops 切换记录（2026-04-24）

## 目标

将 Coze backend 的图片原子能力执行面从 Coze 本机 `127.0.0.1:8301` 切到 `117.50.80.158:8200`，避免高清放大等图片处理继续占用 Coze 主机资源。

## 当前拓扑

- Coze backend：`114.55.0.56:8099`
- Admin：`114.55.0.56:8199`
- Eval：`114.55.0.56:8200`
- ComfyUI：`117.50.80.158:8079`
- Image Ops：`117.50.80.158:8200`
- `117.50.80.158:8099`：已停止，不再作为控制面入口

## 已执行

1. `117.50.80.158:8200` 已部署为 image-ops。
2. Coze backend 已切换：

```env
IMAGE_OPS_BASE_URL=http://117.50.80.158:8200
IMAGE_OPS_LOCAL_FALLBACK_ENABLED=false
DISABLE_LOCAL_HEAVY_IMAGE_TASKS=true
```

3. Coze 插件表剩余 `117.50.80.158:8099` host 已统一切到 `114.55.0.56:8099`。
4. 插件表备份：

```text
/srv/pod/runtime/coze_remaining_plugin_host_cutover_20260424_183011.sql
```

## 验证

### Post-Coze 检查

命令：

```bash
cd /srv/pod
/srv/pod/backend/.venv/bin/python /srv/pod/scripts/check_remote_image_ops_cutover.py --phase post-coze
```

结果：通过。

覆盖：

- Coze backend health
- `117.50.80.158:8200/health`
- backend `IMAGE_OPS_BASE_URL`
- `expand_mask_color`
- `set_dpi`
- `upscale_resize`

### Coze Workflow 抽测

报告：

- `/srv/pod/runtime/coze_after_remote_image_ops_20260424.md`
- `/srv/pod/runtime/coze_after_remote_image_ops_20260424.json`

通过 workflow：

- `7598589746561941504` DPI 增分
- `7597760543788630016` 8K 高清放大
- `7631174682116358144` ComfyUI 扩图 · `flux2_klein_9b_outpaint`
- `7631838631375667200` 图裂变 · `Liebian_comfyui_20260423`
- `7629023041988591616` 头部抠像 · `toubu_kouxiang`
- `7629023903431524352` 背景抠图 · `beijing_koutu`

结果：6 条全部成功。

## 回滚

如需回滚图片原子能力执行面，在 Coze 主机执行：

```bash
cd /srv/pod
IMAGE_OPS_BASE_URL=http://127.0.0.1:8301 \
  bash scripts/switch_backend_image_ops_base.sh
```

如需回滚插件 host，可使用备份 SQL 或将插件 host 重新改回旧入口。但当前目标架构下，`117.50.80.158:8099` 不再作为控制面入口，默认不建议回滚到旧 host。
