# 图裂变业务接口交付材料模板

本目录是给业务方交付包的 Git 内模板，不包含真实 Key。正式交付时复制本目录到交付目录，补一份本地 `.env`，再压缩给业务方。

## 目录

| 目录 | 接口 | 说明 |
| --- | --- | --- |
| `01_gpt_image2_controlled_fission/` | `POST /api/business/fission/runs` | GPT Image 2 受控裂变，一次请求固定生成 1 张图。 |
| `02_comfyui_colorlock_fission/` | `POST /api/business/fission/runs` | ComfyUI 颜色锁定裂变，默认重绘幅度 15%。 |
| `03_fission_generated_image_score/` | `POST /api/business/fission-evaluate/runs` | 裂变生成图评分，只评分，不自动二次裂变。 |

## 统一约定

- 鉴权请求头：`X-PODI-API-Key: <业务 Key>`。
- Key 授权范围：两个生成接口需要 `fission`；评分接口需要 `fission_evaluate`。
- 提交成功后保存 `runId`。
- 查询结果统一调用：`POST /api/business/runs/get`。
- 旧 Coze 轮询兼容：可以把 `runId` 填入 `/api/coze/podi/tasks/get` 的 `taskId` 字段。
- 业务方不需要理解 ComfyUI、Coze、执行节点、VL 模型或底层 taskId。

## 本地运行准备

复制环境变量模板：

```bash
cp .env.example .env
```

填写：

```bash
PODI_BACKEND=http://114.55.0.56:8099
PODI_API_KEY=业务方实际 Key
PODI_IMAGE_URL=https://example.com/input.png
```

运行某个接口 Demo：

```bash
cd 01_gpt_image2_controlled_fission
python3 demo.py
```

## 业务方最小接入

1. 提交任务，拿到 `runId`。
2. 每 5-10 秒调用 `/api/business/runs/get` 查询。
3. `status=succeeded` 时读取 `imageUrls` 或评分结果。
4. `status=failed` 时记录 `runId`、`requestId`、`traceId` 给中台排查。
