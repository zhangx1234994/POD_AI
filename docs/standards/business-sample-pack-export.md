# 业务样本包导出规范

目标：把业务运行的原图、结果图、VL 内容和过程信息按固定格式导出，交给 AI / ComfyUI / 测试同学复盘，不再靠临时 SQL 或手工截图。

## 使用命令

在后端环境中执行：

```bash
cd backend
python scripts/export_business_sample_pack.py \
  --business-key fission \
  --version comfyui-vl-control-v2 \
  --date-from 2026-05-13 \
  --date-to 2026-05-14 \
  --limit 30
```

只导出 URL、不下载图片时：

```bash
cd backend
python scripts/export_business_sample_pack.py \
  --business-key fission \
  --status succeeded \
  --no-download-assets
```

常用筛选：

- `--business-key`：业务类型，例如 `fission`、`outpaint`、`pattern_extract`。
- `--version`：业务版本，例如 `comfyui-vl-control-v2`。
- `--business-version-id`：精确业务版本 ID。
- `--executor-id`：只导出实际命中某台执行节点的样本。
- `--date-from` / `--date-to`：时间窗口。
- `--limit`：导出数量。

## 输出内容

默认输出到：

```text
deliverables/business_sample_packs/
```

压缩包内包含：

- `README.md`：本次筛选条件和文件说明。
- `summary.csv`：人工查看总表。
- `manifest.json`：运行 ID、导出条件、错误和文件索引。
- `runs/<runId>/run.json`：单条业务详情，敏感字段已脱敏。
- `runs/<runId>/process.json`：业务链路、步骤、执行节点和回填证据。
- `runs/<runId>/vl.json`：VL 分析和控制卡摘要。
- `runs/<runId>/urls.json`：原图和结果图 URL。
- `runs/<runId>/assets/`：下载后的原图和结果图。

## 规则

- 导出包可以给外部协作同学；真实密钥、鉴权头、token、secret 会被脱敏。
- 对业务质量复盘，优先导出 `status=succeeded` 的样本；排障时可导出 `failed` 或指定执行节点。
- 每轮 ComfyUI 或商业模型优化后，至少导出一次样本包，和测试结论一起归档。
- 样本包不作为业务接口文档，接口交付材料仍按单接口目录维护。
