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
- 查询结果统一调用：`POST /api/business/runs/get`，默认返回轻量字段 `status/taskStatus/imageUrls/videoUrls/texts/error`。
- 需要排查底层版本、步骤、执行节点和回填证据时，在查询请求中加 `"detail": "full"`，普通业务接入不要默认开启。
- 旧 Coze 轮询兼容：可以把 `runId` 填入 `/api/coze/podi/tasks/get` 的 `taskId` 字段。
- 业务方不需要理解 ComfyUI、Coze、执行节点、VL 模型或底层 taskId。

## 统一返回字段

提交接口返回：

| 字段 | 说明 |
| --- | --- |
| `runId` | 业务任务 ID。业务方必须保存这个 ID，用它查询结果、排查问题和做回调关联。 |
| `status` | 当前业务任务状态，常见值为 `queued`、`running`、`succeeded`、`failed`。提交成功时通常是 `queued` 或 `running`。 |
| `taskStatus` | 兼容 Coze 的状态字段，含义与 `status` 一致。 |
| `taskId` | 底层能力任务 ID，可能为空或稍后生成。普通业务不需要依赖它。 |
| `businessKey` / `version` | 本次提交命中的业务能力和版本。 |
| `debugUrl` | 可选的中台排障链接；没有则为空。 |
| `requestId` | 本次业务请求 ID。业务方传入则原样关联；未传则由中台生成。 |
| `traceId` | 链路追踪 ID，用于把业务系统、中台和能力调用串起来排查。 |
| `retryAfterSeconds` | 建议首次轮询等待秒数。 |

提交接口不会默认返回 `routeInfo`、`steps`、`requestPayload`、`costBreakdown` 等内部排障字段；这些内容只在管理端或查询接口 `detail=full` 时使用。

查询接口默认返回轻量结果：

| 字段 | 说明 |
| --- | --- |
| `runId` | 业务任务 ID。 |
| `status` / `taskStatus` | 当前状态。`queued/running` 继续轮询，`succeeded/failed/cancelled` 为终态。 |
| `imageUrl` | 第一张结果图 URL；没有图片时为空。 |
| `imageUrls` | 全部结果图 URL。两个裂变接口当前每次固定 1 张。 |
| `videoUrl` / `videoUrls` | 视频结果字段，本次三个接口通常为空，保留给后续视频能力。 |
| `text` | 第一段文本结果或简短状态说明。评分接口可读取该字段。 |
| `texts` | 全部文本结果。评分接口优先读取这里的结构化评分说明。 |
| `resultPayload` | 轻量结构化结果。评分接口可能返回 `decision/score/problem_tags/reason/next_action`。 |
| `error` / `errorMessage` | 失败原因，已经做过脱敏和简化。 |
| `errorCode` | 标准错误码，例如 `BUSINESS_IMAGE_URL_REQUIRED`、`BUSINESS_RUN_TEMPORARY_UNAVAILABLE`。 |
| `debugResponse` | 给调用方看的轻量排障提示，不包含密钥、SQL 原文或大段内部响应。 |
| `retryAfterSeconds` | 建议下次查询或重试的等待秒数；为空时按 5-10 秒轮询即可。 |
| `expectedImageCount` | 预计出图数量；裂变生成接口当前为 1。 |
| `durationMs` | 中台记录的任务耗时，单位毫秒。 |
| `createdAt` / `startedAt` / `finishedAt` | 任务创建、开始、完成时间。 |

排障时可以给查询接口增加 `"detail": "full"`，此时会返回底层步骤、执行节点、VL 中间结果和回填证据。普通业务接入不要默认开启完整模式，避免返回内容过重。

## 本地运行准备

复制环境变量模板：

```bash
cp .env.example .env
```

填写或确认：

```bash
PODI_BACKEND=http://114.55.0.56:8099
PODI_API_KEY=业务方实际 Key
PODI_IMAGE_URL=https://example.com/input.png
```

正式交付包会额外包含 `business_api_key.env`，Demo 会自动读取其中的 `PODI_BUSINESS_API_KEY`。如果你不想改环境变量，直接把图片地址通过命令行环境变量传入即可。

运行某个接口 Demo：

```bash
cd 01_gpt_image2_controlled_fission
python3 demo.py
```

## 业务方最小接入

1. 提交任务，拿到 `runId`。
2. 每 5-10 秒调用 `/api/business/runs/get` 查询。
3. `status=succeeded` 时读取 `imageUrls` 或评分结果；评分接口优先读 `texts`，必要时读轻量 `resultPayload`。
4. `status=failed` 时记录 `runId`、`requestId`、`traceId` 给中台排查。
