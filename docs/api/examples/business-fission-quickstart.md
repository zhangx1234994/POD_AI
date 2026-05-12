# 图裂变业务接口接入 Demo

目标：业务方只接一个提交接口和一个查询接口。图裂变底层用 ComfyUI 还是 GPT Image 2 + VL，由中台版本控制。

## 1. 准备 Key

生产环境不要把真实 Key 写进文档或代码仓库。上线前在 114 后端机器执行：

```bash
cd /srv/pod/backend
python scripts/create_business_api_key.py \
  --id biz_key_fission_partner_001 \
  --name "业务方图裂变测试 Key" \
  --tenant-id partner \
  --client-id fission-api \
  --allowed-business-key fission
```

脚本会把 Key 写入中台 `api_keys` 表，并在终端输出一次完整 Key。业务方请求时放在请求头：

```http
X-PODI-API-Key: <脚本输出的 key>
```

## 2. 提交 GPT Image 2 + VL 控制版裂变

```bash
export PODI_BACKEND="http://114.55.0.56:8099"
export PODI_API_KEY="<脚本输出的 key>"

curl -X POST "$PODI_BACKEND/api/business/fission/runs" \
  -H "Content-Type: application/json" \
  -H "X-PODI-API-Key: $PODI_API_KEY" \
  -d '{
    "imageUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/demo/input.png",
    "version": "gpt-image2-vl-v1",
    "variation_strength": "high",
    "quality": "preview",
    "count": 1,
    "size": "1024x1024",
    "preserve_layout": true,
    "preserve_border": "auto",
    "preserve_count_density": true,
    "style_shift": "standard",
    "prompt": "保留系列感，元素要明显变化",
    "source": "partner-api",
    "channel": "open-api",
    "traceId": "trace-fission-001",
    "requestId": "req-fission-001"
  }'
```

成功后会返回：

```json
{
  "runId": "业务任务ID",
  "taskId": "底层能力任务ID，可能为空或稍后生成",
  "status": "queued",
  "imageUrls": []
}
```

## 3. 查询结果

业务方推荐使用业务查询接口：

```bash
curl -X POST "$PODI_BACKEND/api/business/runs/get" \
  -H "Content-Type: application/json" \
  -H "X-PODI-API-Key: $PODI_API_KEY" \
  -d '{"runId": "上一步返回的 runId"}'
```

为兼容 Coze 旧工具箱轮询方式，中台也支持把 `runId` 填到旧字段 `taskId`：

```bash
curl -X POST "$PODI_BACKEND/api/coze/podi/tasks/get" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <SERVICE_API_TOKEN>" \
  -d '{"taskId": "上一步返回的 runId"}'
```

注意：`/api/coze/podi/tasks/get` 是 Coze/内网兼容入口，外部业务默认使用 `/api/business/runs/get`。

## 4. 结果判断

业务查询接口按 `status` 判断：

- `queued` / `running`：继续等待，建议 5-10 秒后再查。
- `succeeded`：读取 `imageUrls`。
- `failed`：读取 `error` / `errorMessage`，记录 `runId` 给中台排查。

Coze 兼容查询接口按 `taskStatus` 判断：

- `queued` / `running`：继续等待。
- `succeeded`：读取 `imageUrls`。
- `failed`：读取 `debugResponse` / `errorCode`。

